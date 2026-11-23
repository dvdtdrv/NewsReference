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

import requests

import collect
import headline_watch
from limits import within

CATCHUP_HOURS = 24          # look back this far
PAGES_PER_ROUND = 10        # article pages opened per outlet per PC round (every ~30 min)
PAUSE = 5                   # seconds between those pages (link_check.PC_PAUSE)
GIVE_UP = 3                 # this many refused pages in a row: stop for this round
SITEMAP_BYTES = 600_000     # read at most this much of a sitemap (newest first; Bloomberg TV's is 10 MB)
PAGE_BYTES = 600_000        # and of an article page
PAGE_SECONDS = 25           # never longer than this for one page
SENT_HOURS = 3              # a link the PC sent but GitHub still doesn't list after this long: try it again
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
    """Links GitHub already has for these outlets (refreshed by every GitHub run), plus what this PC sent lately."""
    try:
        known = set(requests.get(KNOWN_URL, timeout=collect.TIMEOUT).json().get("links", []))
    except (requests.RequestException, ValueError):
        known = None                     # can't tell what GitHub has: open no pages this round
    sent = collect.load_json(MEMORY_FILE, {})
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=SENT_HOURS)).isoformat()
    sent = {k: v for k, v in sent.items() if v >= cutoff}
    return known, sent


def save_sent(sent):
    os.makedirs(os.path.dirname(MEMORY_FILE) or ".", exist_ok=True)
    collect.save_json(MEMORY_FILE, sent)


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
    since = datetime.now(timezone.utc) - timedelta(hours=CATCHUP_HOURS)

    if cfg.get("headlines"):             # Marica, Blitz: the sitemap itself has the headlines
        found = [a for a in collect.read_news_sitemap(text, outlet)
                 if a["link"] not in have and a.get("published") and datetime.fromisoformat(a["published"]) >= since]
        for a in found:
            a["catchup"] = True
            if a["link"] in photos:
                a["image"] = photos[a["link"]] or a.get("image", "")
        return found, f"catch-up: {len(found)} from the sitemap" if found else ""

    if known is None:                     # bTV, Bloomberg TV: we must know what GitHub has before opening pages
        return [], "catch-up skipped (GitHub's list unreachable)"
    todo = [(link, t) for link, t in sitemap_links(text)
            if link not in have and link not in known and (t is None or t >= since)]
    todo.sort(key=lambda x: x[1] or since, reverse=True)
    found, opened, refused = [], 0, 0
    for link, t in todo[:PAGES_PER_ROUND]:
        if refused >= GIVE_UP or not collect.allowed(link):
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
    return found, note if todo else ""
