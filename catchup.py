"""
Catch-up reading (23 Nov 2026): the articles the PC outlets published while David's PC was off.

Their feeds list only the newest articles (Marica 10 = ~2 h, Blitz/bTV 50 = ~7 h, Bloomberg TV 10 = ~3 h), so after a
night off most of the night was lost. probe_catchup.py (run on the PC) found what each outlet offers instead; feeds.py
names it as "catchup": {"sitemap": ..., "headlines": True/False}:
  - Marica, Blitz: a Google News sitemap WITH headlines (Marica ~3 days, Blitz 24 h): one extra request per round.
  - bTV, Bloomberg TV: a sitemap with links and times but NO headlines: each missed article's own page is opened
    once for its headline, time and photo; at most PAGES_PER_ROUND pages per outlet per round, PAUSE s apart
    (David's home connection: BG On Air blocked it after ~230 fast page loads), only links GitHub doesn't have
    (known_local.json on the data branch, written by collect.py, 7 days) and only from the last CATCHUP_HOURS.
Articles found this way are marked "catchup": collect.py only ADDS them, never treats them as renamed versions of
articles it already has (a sitemap or page can word a headline a little differently from the feed).
Runs only on the PC, from fetch_local.py.
"""

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import requests

import collect
import headline_watch
from limits import within

CATCHUP_HOURS = 24          # look back this far (an outlet's "catchup" can say "hours": Marica 72)
PAGES_PER_ROUND = 10        # article pages opened per outlet per PC round (every ~30 min)
PAUSE = 5                   # seconds between those pages (link_check.PC_PAUSE)
GIVE_UP = 3                 # this many refused pages in a row: stop for this round
USELESS = 5                 # the first this many pages gave no article (no headline or date found): stop the outlet
SITEMAP_BYTES = 600_000     # read at most this much of a sitemap (newest first; Bloomberg TV's is 10 MB)
PAGE_BYTES = 600_000        # and of an article page
PAGE_SECONDS = 25           # never longer than this for one page
SENT_HOURS = 3              # a link the PC sent but GitHub still doesn't list after this long: try it again
GAP_HOURS = 2               # the PC was off longer than this: also read the outlet's section pages ("sections")
GAP_PAGES = 3               # ... pages 1-3 of each section
# deep recovery, once by hand (local-fetch.yml started with deep = 1): the last 7 days, section pages as far back
# as needed (they stop by date), at most DEEP_ARTICLES article pages per outlet
DEEP = os.environ.get("CATCHUP_DEEP") == "1"
DEEP_HOURS = 7 * 24
DEEP_PAGES = 20
DEEP_ARTICLES = 100
GAP = False                 # set by load_known(): was the PC off for a while before this round?
KNOWN_URL = "https://raw.githubusercontent.com/dvdtdrv/NewsReference/data/known_local.json"
MEMORY_FILE = os.path.join(os.environ.get("NR_CACHE_DIR") or collect.DATA, "catchup_sent.json")

LOC = re.compile(r"<url>(.*?)</url>", re.S)
PUBLISHED = re.compile(r"""(?:property|itemprop|name)\s*=\s*["'](?:article:published_time|datePublished|pubdate)["'][^>]*?"""
                       r"""content\s*=\s*["']([^"']+)["']|"datePublished"\s*:\s*"([^"]+)\"""", re.I)


def _get(url, headers, limit):
    """Part of a page as text (at most `limit` bytes), or None if refused / unreachable."""
    def read():
        with requests.get(url, headers=headers, timeout=collect.TIMEOUT, stream=True) as r:
            if r.status_code != 200:
                return None
            body = b""
            for chunk in r.iter_content(65536):
                body += chunk
                if len(body) >= limit:
                    break
            return body.decode(r.encoding or "utf-8", errors="replace")
    try:
        return within(PAGE_SECONDS * 2, read)
    except Exception:
        return None


def load_known():
    """Links GitHub already has for these outlets ({link: published}, refreshed by every GitHub run), plus what this
    PC sent lately. Also notes whether the PC was off for a while (GAP)."""
    global GAP
    try:
        data = requests.get(KNOWN_URL, timeout=collect.TIMEOUT).json()
        known = data.get("published") or {link: "" for link in data.get("links", [])}
    except (requests.RequestException, ValueError):
        known = None                     # can't tell what GitHub has: open no pages this round
    sent = collect.load_json(MEMORY_FILE, {})
    now = datetime.now(timezone.utc)
    last = sent.pop("__last_run__", None)
    GAP = not last or datetime.fromisoformat(last) < now - timedelta(hours=GAP_HOURS)
    cutoff = (now - timedelta(hours=SENT_HOURS)).isoformat()
    sent = {k: v for k, v in sent.items() if v >= cutoff}
    return known, sent


def save_sent(sent):
    os.makedirs(os.path.dirname(MEMORY_FILE) or ".", exist_ok=True)
    collect.save_json(MEMORY_FILE, {**sent, "__last_run__": datetime.now(timezone.utc).isoformat()})


def section_links(cfg, headers, known, since, max_pages):
    """Article links from the outlet's section pages (bTV: България, Светът, Предавания; page 2 = ?page=2), newest
    first. A section stops when its page holds only articles we know to be older than `since`, or no articles."""
    out = []
    for base in cfg.get("sections", []):
        for n in range(1, max_pages + 1):
            url = base if n == 1 else f"{base}?page={n}"
            if not collect.allowed(url):
                break
            time.sleep(PAUSE)
            page = _get(url, headers, PAGE_BYTES)
            if page is None:
                break
            links = []
            for href in re.findall(r'href="([^"#?]+\.html)"', page):
                full = urljoin(base, href)
                if full.startswith(base) and full not in links:
                    links.append(full)
            dated = [datetime.fromisoformat(known[link]) for link in links if known.get(link)]
            if not links or (dated and max(dated) < since):
                break                    # this page is already older than we look back: nothing from it
            if dated and min(dated) < since:   # the page reaches past `since`: only the links above the oldest
                cut = max(i for i, link in enumerate(links) if known.get(link) and datetime.fromisoformat(known[link]) >= since)
                links = links[:cut + 1]
            out += [link for link in links if link not in out]
    return out


def sitemap_links(text):
    """[(link, time or None)] of a plain sitemap, in its own order."""
    out = []
    for block in LOC.findall(text):
        loc = re.search(r"<loc>\s*(.*?)\s*</loc>", block, re.S)
        when = re.search(r"<(?:news:publication_date|lastmod)>\s*(.*?)\s*</", block, re.S)
        if loc:
            out.append((collect.html.unescape(loc.group(1)), collect.parse_date(when.group(1)) if when else None))
    return out


def read_article(link, outlet, headers, sitemap_time):
    """One article page -> an article like the feed's (headline, time, photo), "" if the page is no article,
    None if the page refused us."""
    page = _get(link, headers, PAGE_BYTES)
    if page is None:
        return None
    title = headline_watch.page_headline(headline_watch.page_parts(page))
    if not title or len(title) < headline_watch.MIN_LEN:
        return ""
    m = PUBLISHED.search(page)
    when = collect.parse_date(m.group(1) or m.group(2)) if m else None
    when = when or sitemap_time
    if not when:
        return ""
    img = ""
    for tag in collect.OG_TAG.finditer(page):
        c = collect.OG_CONTENT.search(tag.group(0))
        if c:
            img = collect.fix_image_url(collect.html.unescape(c.group(1)), link, outlet.get("domain", ""))
            break
    return {"outlet": outlet["name"], "title": collect.clean_text(title), "link": link, "summary": "",
            "published": when.isoformat(), "image": img if collect.good_image(img) else "", "catchup": True}


def catch_up(outlet, fetched, headers, known, sent, photos):
    """The articles of `outlet` from the last CATCHUP_HOURS that neither the feed (`fetched`) nor GitHub has.
    Returns (articles, note)."""
    cfg = outlet.get("catchup") or {}
    url = cfg.get("sitemap")
    if not url or not collect.allowed(url):
        return [], ""
    time.sleep(PAUSE)
    text = _get(url, headers, SITEMAP_BYTES)
    if text is None:
        return [], "catch-up sitemap refused"
    have = {a.get("link") for a in fetched} | set(sent)
    since = datetime.now(timezone.utc) - timedelta(hours=DEEP_HOURS if DEEP else cfg.get("hours", CATCHUP_HOURS))

    if cfg.get("headlines"):             # Marica, Blitz: the sitemap itself has the headlines
        found = [a for a in collect.read_news_sitemap(text, outlet)
                 if a["link"] not in have and (known is None or a["link"] not in known)
                 and a.get("published") and datetime.fromisoformat(a["published"]) >= since]
        for a in found:
            a["catchup"] = True
            if a["link"] in photos:
                a["image"] = photos[a["link"]] or a.get("image", "")
        return found, f"catch-up: {len(found)} new from the sitemap" if found else ""

    if known is None:                     # bTV, Bloomberg TV: we must know what GitHub has before opening pages
        return [], "catch-up skipped (GitHub's list unreachable)"
    todo = [(link, t) for link, t in sitemap_links(text)
            if link not in have and link not in known and (t is None or t >= since)]
    todo.sort(key=lambda x: x[1] or since, reverse=True)
    if cfg.get("sections") and (GAP or DEEP):   # after a gap (or by hand): the section pages list much more
        listed = {link for link, _ in todo}
        todo += [(link, None) for link in section_links(cfg, headers, known, since, DEEP_PAGES if DEEP else GAP_PAGES)
                 if link not in have and link not in known and link not in listed]
    found, opened, refused = [], 0, 0
    for link, t in todo[:DEEP_ARTICLES if DEEP else PAGES_PER_ROUND]:
        if refused >= GIVE_UP or (opened >= USELESS and not found) or not collect.allowed(link):
            continue
        if opened:
            time.sleep(max(PAUSE, collect.crawl_delay(link)))
        opened += 1
        a = read_article(link, outlet, headers, t)
        if a is None:
            refused += 1
            continue
        refused = 0
        sent[link] = datetime.now(timezone.utc).isoformat()   # "" (not an article) is remembered too
        if a and datetime.fromisoformat(a["published"]) >= since:   # an old article the outlet only edited: leave it
            photos.setdefault(link, a["image"])
            found.append(a)
    left = max(0, len(todo) - opened)
    note = f"catch-up: {len(found)} from {opened} pages" + (f", {left} left for later rounds" if left else "")
    if opened >= USELESS and not found:
        note += " (stopped: the pages gave no headline/date)"
    return found, note if todo else ""
