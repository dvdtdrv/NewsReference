"""
Collect new articles from every outlet in feeds.py and add them to the archive.

Each run:
  - reads every outlet's feed (or news sitemap), politely, respecting robots.txt,
  - adds articles it hasn't seen before to data/articles.json (the last KEEP_DAYS days),
  - copies every article into data/articles/YYYY-MM.json, which is never deleted,
  - records how each outlet did in data/outlet_status.json.

Sites marked gentle (BTA) are asked once per run; if they say "wait", we wait
as long as they ask before trying again. That waiting time is kept in data/state.json.

Run with:   python collect.py
"""

import html
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import feedparser
import requests

from feeds import OUTLETS

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

USER_AGENT = "NewsReferenceBot/0.1 (student project comparing Bulgarian news coverage)"
HEADERS = {"User-Agent": USER_AGENT}
# Used only for outlets marked as_browser in feeds.py, which gave written permission (permissions/).
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml;q=0.9, text/html;q=0.8, */*;q=0.5",
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}
TIMEOUT = 20
KEEP_DAYS = 7               # how long articles stay in the archive
DEFAULT_WAIT = 30 * 60      # if a site says "too many requests" without saying how long, wait 30 min

DATA = "data"
ARTICLES_FILE = os.path.join(DATA, "articles.json")      # last KEEP_DAYS days, used for grouping
MONTHS_DIR = os.path.join(DATA, "articles")              # every article ever collected, one file per month
STATUS_FILE = os.path.join(DATA, "outlet_status.json")
STATE_FILE = os.path.join(DATA, "state.json")

NOW = datetime.now(timezone.utc)
_robots = {}


# ---------------------------------------------------------------- small helpers

def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    tmp = path + ".tmp"   # write to a temp file first, so a crash never leaves a half-written file
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def clean_text(raw, limit=300):
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = html.unescape(re.sub(r"\s+", " ", text)).strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def parse_date(value):
    """Turn the many date formats feeds use into a UTC datetime (or None)."""
    if not value:
        return None
    value = value.strip()
    for parse in (lambda v: datetime.fromisoformat(v.replace("Z", "+00:00")),
                  parsedate_to_datetime):
        try:
            d = parse(value)
            if d.tzinfo is None:          # no timezone given: assume Bulgarian time
                d = d.replace(tzinfo=timezone(timedelta(hours=2)))
            return d.astimezone(timezone.utc)
        except (ValueError, TypeError):
            continue
    return None


def allowed(url):
    parts = urlparse(url)
    site = f"{parts.scheme}://{parts.netloc}"
    if site not in _robots:
        rp = RobotFileParser()
        try:
            r = requests.get(site + "/robots.txt", headers=HEADERS, timeout=TIMEOUT)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except requests.RequestException:
            rp.parse([])
        _robots[site] = rp
    return _robots[site].can_fetch(USER_AGENT, url)


# ---------------------------------------------------------------- reading one outlet

def find_image(e):
    """The article's main photo, if the feed gives one. Feeds put it in different places."""
    for m in e.get("media_content", []):
        if m.get("url") and (m.get("medium") in (None, "image") or "image" in m.get("type", "image")):
            return m["url"]
    for m in e.get("media_thumbnail", []):
        if m.get("url"):
            return m["url"]
    for link in e.get("links", []):
        if link.get("rel") == "enclosure" and link.get("type", "").startswith("image") and link.get("href"):
            return link["href"]
    # last resort: the first picture inside the summary or content
    body = (e.get("summary") or "") + "".join(c.get("value", "") for c in e.get("content", []))
    m = re.search(r"<img[^>]+src=[\"']([^\"']+)", body)
    return html.unescape(m.group(1)) if m else ""


def fix_image_url(url, link, domain):
    """Make a photo address absolute, and repair 'https://clubz.bg147/...' (missing slash in Club Z's feed)."""
    if not url:
        return ""
    url = urljoin(link or (f"https://{domain}/" if domain else ""), url)
    if not domain:
        return url
    m = re.match(r"^(https?://(?:www\.)?" + re.escape(domain) + r")(?=[^/:?#])", url)
    return m.group(1) + "/" + url[m.end():] if m else url


def read_feed(content, outlet):
    feed = feedparser.parse(content)
    out = []
    for e in feed.entries:
        # Read the date ourselves first: some feeds (PIK) write "2026-10-31 17:00:00" with no
        # timezone, which feedparser treats as UTC; that's Bulgarian time, 2 hours off.
        when = parse_date(e.get("published") or e.get("updated"))
        t = e.get("published_parsed") or e.get("updated_parsed")
        if when is None and t:
            when = datetime(*t[:6], tzinfo=timezone.utc)
        out.append({
            "outlet": outlet["name"],
            "title": clean_text(e.get("title")),
            "link": e.get("link") or e.get("id") or "",
            "summary": clean_text(e.get("summary")),
            "published": when.isoformat() if when else None,
            "image": fix_image_url(find_image(e), e.get("link"), outlet.get("domain", "")),
            "raw_date": e.get("published") or e.get("updated") or "",
        })
    return out


def read_news_sitemap(text, outlet):
    """A news sitemap lists each new article as <url> with its address, date and headline."""
    out = []
    for block in re.findall(r"<url>(.*?)</url>", text, re.S):
        loc = re.search(r"<loc>\s*(.*?)\s*</loc>", block, re.S)
        title = re.search(r"<news:title>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</news:title>", block, re.S)
        date = re.search(r"<(?:news:publication_date|lastmod)>\s*(.*?)\s*</", block, re.S)
        if not (loc and title):
            continue
        d = parse_date(date.group(1)) if date else None
        img = re.search(r"<image:loc>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</image:loc>", block, re.S)
        out.append({
            "outlet": outlet["name"],
            "title": clean_text(title.group(1)),
            "link": html.unescape(loc.group(1)),
            "summary": "",
            "published": d.isoformat() if d else None,
            "image": html.unescape(img.group(1)) if img else "",
        })
    return out


def relative_time(text):
    """'преди 15 минути' / 'преди 2 часа' / 'преди 1 ден' / 'току-що' -> a UTC datetime, or None."""
    t = text.strip().lower()
    if "току-що" in t or "сега" in t:
        return NOW
    m = re.search(r"(\d+)\s*(секунд|минут|час|ден|дни)", t)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    step = {"секунд": timedelta(seconds=1), "минут": timedelta(minutes=1), "час": timedelta(hours=1),
            "ден": timedelta(days=1), "дни": timedelta(days=1)}[unit]
    return NOW - n * step


def read_newsbg_page(text, outlet):
    """News.bg has no feed or sitemap, so we read its public "latest news" page (robots.txt allows it).
    Each item: a link with class "title", a photo, and a relative time like "преди 2 часа".
    The time is approximate (to the hour) the first time we see an older article; new articles
    show minutes, and an article keeps the time from when we first saw it."""
    out = []
    for block in re.findall(r'<div class="topic">(.*?)</li>', text, re.S):
        link = re.search(r'<a href="([^"]+)" class="title">\s*(.*?)\s*</a>', block, re.S)
        when = re.search(r'<p class="time">\s*(.*?)\s*</p>', block, re.S)
        img = re.search(r'<img src="([^"]+)"', block)
        if not link:
            continue
        d = relative_time(html.unescape(when.group(1))) if when else None
        out.append({
            "outlet": outlet["name"],
            "title": clean_text(link.group(2)),
            "link": html.unescape(link.group(1)),
            "summary": "",
            "published": d.isoformat() if d else None,
            "image": html.unescape(img.group(1)) if img else "",
        })
    return out


def fetch_outlet(outlet, state):
    """Returns (articles, status_word, note)."""
    name = outlet["name"]
    wait_until = state.get("wait_until", {}).get(name)
    if wait_until and datetime.fromisoformat(wait_until) > NOW:
        return [], "waiting", f"asked us to wait until {wait_until[11:16]} UTC"

    url = outlet.get("feed") or outlet.get("sitemap") or outlet.get("page")
    if not allowed(url):
        return [], "blocked", "robots.txt disallows"
    try:
        r = requests.get(url, headers=BROWSER_HEADERS if outlet.get("as_browser") else HEADERS,
                         timeout=TIMEOUT)
    except requests.RequestException as e:
        return [], "error", f"could not connect ({type(e).__name__})"

    if r.status_code == 429:
        try:
            seconds = int(r.headers.get("Retry-After", DEFAULT_WAIT))
        except ValueError:
            seconds = DEFAULT_WAIT
        until = NOW + timedelta(seconds=max(seconds, 60))
        state.setdefault("wait_until", {})[name] = until.isoformat()
        return [], "waiting", f"too many requests; will retry after {until.isoformat()[11:16]} UTC"
    if r.status_code != 200:
        return [], "error", f"HTTP {r.status_code}"

    state.get("wait_until", {}).pop(name, None)
    if outlet.get("feed"):
        articles = read_feed(r.content, outlet)
    elif outlet.get("sitemap"):
        articles = read_news_sitemap(r.text, outlet)
    else:
        articles = read_newsbg_page(r.text, outlet)
    if not articles:
        return [], "error", "no articles found in the response"
    return articles, "ok", ""


# ---------------------------------------------------------------- permanent archive

def save_monthly(articles):
    """Copy every article into data/articles/YYYY-MM.json, one file per month, kept forever.
    data/articles.json only holds the last KEEP_DAYS days (that's what grouping needs);
    the monthly files are the full history. Returns how many articles they hold in total."""
    os.makedirs(MONTHS_DIR, exist_ok=True)
    by_month = {}
    for a in articles:
        by_month.setdefault(a["published"][:7], []).append(a)
    for month, items in by_month.items():
        path = os.path.join(MONTHS_DIR, f"{month}.json")
        stored = load_json(path, [])
        index = {a["link"]: a for a in stored}
        changed = False
        for a in items:
            old = index.get(a["link"])
            if old is None:
                stored.append(a)
                index[a["link"]] = a
                changed = True
            elif a.get("image") and old.get("image") != a["image"]:
                old["image"] = a["image"]
                changed = True
        if changed:
            stored.sort(key=lambda a: a["published"])
            save_json(path, stored)
    total = 0
    for name in os.listdir(MONTHS_DIR):
        if name.endswith(".json"):
            total += len(load_json(os.path.join(MONTHS_DIR, name), []))
    return total


# ---------------------------------------------------------------- main

def main():
    os.makedirs(DATA, exist_ok=True)
    archive = load_json(ARTICLES_FILE, [])
    state = load_json(STATE_FILE, {})
    old_status = {s["outlet"]: s for s in load_json(STATUS_FILE, [])}

    by_link = {a["link"]: a for a in archive}
    seen_links = set(by_link)
    seen_titles = {(a["outlet"], a["title"].lower()) for a in archive}
    oldest_allowed = NOW - timedelta(days=KEEP_DAYS)
    newest_allowed = NOW + timedelta(hours=6)   # ignore articles dated in the future

    status = []
    print(f"Collecting from {len(OUTLETS)} outlets...\n")
    for outlet in OUTLETS:
        fetched, word, note = fetch_outlet(outlet, state)
        added = 0
        skipped = {"no link/title": 0, "no date": 0, "too old/future": 0}
        example_date = ""
        for a in fetched:
            if not a["link"] or not a["title"]:
                skipped["no link/title"] += 1
                continue
            if not a["published"]:
                skipped["no date"] += 1
                continue
            when = datetime.fromisoformat(a["published"])
            key = (a["outlet"], a["title"].lower())
            if when < oldest_allowed or when > newest_allowed:
                skipped["too old/future"] += 1
                example_date = example_date or f"e.g. date '{a.get('raw_date', '')}' read as {a['published'][:16]}"
                continue
            if a["link"] in seen_links or key in seen_titles:
                old = by_link.get(a["link"])
                if old is not None and a.get("image") and old.get("image") != a["image"]:
                    old["image"] = a["image"]   # fill in (or repair) the photo of an article we already have
                continue
            a["collected"] = NOW.isoformat()
            a.pop("raw_date", None)
            archive.append(a)
            by_link[a["link"]] = a
            seen_links.add(a["link"])
            seen_titles.add(key)
            added += 1
        reasons = ", ".join(f"{n} skipped: {why}" for why, n in skipped.items() if n)
        note = "; ".join(x for x in (note, reasons, example_date) if x)

        prev = old_status.get(outlet["name"], {})
        status.append({
            "outlet": outlet["name"],
            "type": outlet["type"],
            "method": "feed" if outlet.get("feed") else ("sitemap" if outlet.get("sitemap") else "page"),
            "status": word,
            "added_this_run": added,
            "last_ok": NOW.isoformat() if word == "ok" else prev.get("last_ok"),
            "first_ok": prev.get("first_ok") or (NOW.isoformat() if word == "ok" else None),
            "note": note,
        })
        print(f"{word:<8} {outlet['name']:<14} +{added:<4} {note}")
        time.sleep(1)  # one outlet at a time, with a pause

    saved_forever = save_monthly(archive)

    archive = [a for a in archive if datetime.fromisoformat(a["published"]) >= oldest_allowed]
    archive.sort(key=lambda a: a["published"], reverse=True)
    save_json(ARTICLES_FILE, archive)
    save_json(STATUS_FILE, status)
    save_json(STATE_FILE, state)

    ok = sum(1 for s in status if s["status"] == "ok")
    new = sum(s["added_this_run"] for s in status)
    with_photo = {}
    for a in archive:
        n = with_photo.setdefault(a["outlet"], [0, 0])
        n[0] += 1
        n[1] += bool(a.get("image"))
    print("\nPhotos per outlet: " + ", ".join(f"{o} {p}/{t}" for o, (t, p) in with_photo.items()))
    print(f"\n{ok} of {len(status)} outlets read. {new} new articles; last {KEEP_DAYS} days hold {len(archive)}.")
    print(f"Permanent archive (data\\articles\\): {saved_forever} articles in total.")


if __name__ == "__main__":
    main()
