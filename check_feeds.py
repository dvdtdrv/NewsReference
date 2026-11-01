"""
Step 1 of the news site: check which Bulgarian outlets we can read.

For every outlet in feeds.py this script:
  1. checks the site's robots.txt to see if we're allowed to fetch the feed,
  2. downloads the RSS feed and reads it,
  3. if the outlet has no working feed, looks for a hidden feed link on its homepage,
  4. if that fails too, tries a Google News search for that site as a fallback.

It writes two files:
  feed_report.csv  - one row per outlet: what worked, how many articles, how fresh
  articles.json    - every article it collected (headline, link, short summary, time)

Run it from this folder with:   python check_feeds.py
"""

import csv
import html
import json
import re
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

try:
    import requests
    import feedparser
except ImportError:
    print("Missing libraries. Run this first:\n    pip install feedparser requests")
    sys.exit(1)

from feeds import OUTLETS

# Windows terminals sometimes can't print Cyrillic; this fixes it.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# How we introduce ourselves to websites. Honest name = good manners.
USER_AGENT = "NewsReferenceBot/0.1 (student project comparing Bulgarian news coverage)"
HEADERS = {"User-Agent": USER_AGENT}
TIMEOUT = 15  # seconds to wait for a site before giving up

_robots_cache = {}


# ---------------------------------------------------------------- helpers

def robots_allows(url):
    """Return (allowed, note). Reads each site's robots.txt once and remembers it."""
    parts = urlparse(url)
    site = f"{parts.scheme}://{parts.netloc}"
    if site not in _robots_cache:
        rp = RobotFileParser()
        try:
            r = requests.get(site + "/robots.txt", headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 200:
                rp.parse(r.text.splitlines())
            else:
                rp.parse([])  # no robots.txt = everything allowed
        except requests.RequestException:
            rp.parse([])
        _robots_cache[site] = rp
    allowed = _robots_cache[site].can_fetch(USER_AGENT, url)
    return allowed, "" if allowed else "robots.txt disallows this URL"


def clean_text(raw, limit=300):
    """Strip HTML tags and extra spaces from a feed summary, and shorten it."""
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = html.unescape(re.sub(r"\s+", " ", text)).strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def entry_time(entry):
    """Feeds store dates in different fields; take whichever exists."""
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    return datetime(*t[:6], tzinfo=timezone.utc) if t else None


def read_feed(url):
    """Download and parse one feed. Returns (status, feed_or_None, note)."""
    allowed, note = robots_allows(url)
    if not allowed:
        return "Blocked", None, note
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as e:
        return "Error", None, f"could not connect ({type(e).__name__})"
    if r.status_code != 200:
        return "Error", None, f"HTTP {r.status_code}"

    feed = feedparser.parse(r.content)  # feedparser tolerates broken XML
    if not feed.entries:
        return "Error", None, "page loaded but it isn't a feed (no items)"
    note = "XML has errors but is readable" if feed.bozo else ""
    return "OK", feed, note


class FeedLinkFinder(HTMLParser):
    """Finds <link rel="alternate" type="application/rss+xml" href="..."> in a page."""
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "link" and "alternate" in (a.get("rel") or "") and \
                a.get("type") in ("application/rss+xml", "application/atom+xml") and a.get("href"):
            self.links.append(a["href"])


def discover_feeds(domain):
    """Look at the outlet's homepage for feed links it advertises."""
    home = f"https://www.{domain}/" if not domain.startswith("www.") else f"https://{domain}/"
    allowed, _ = robots_allows(home)
    if not allowed:
        return []
    try:
        r = requests.get(home, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException:
        return []
    finder = FeedLinkFinder()
    finder.feed(r.text)
    return [urljoin(r.url, link) for link in finder.links]


def google_news_url(domain):
    """A Google News search limited to one site, in Bulgarian, as an RSS feed."""
    return f"https://news.google.com/rss/search?q=site:{domain}&hl=bg&gl=BG&ceid=BG:bg"


# ---------------------------------------------------------------- main

def check_outlet(outlet):
    """Try known feeds, then discovery, then Google News. Returns (report_row, articles)."""
    known = outlet.get("feeds") or ([outlet["feed"]] if outlet.get("feed") else [])
    outlet = {**outlet, "feeds": known}
    attempts = [("rss", url) for url in known]
    tried_notes = []

    def try_list(candidates):
        for method, url in candidates:
            status, feed, note = read_feed(url)
            if status == "OK":
                return method, url, feed, note
            tried_notes.append(f"{status}: {note} [{url}]")
        return None

    result = try_list(attempts)
    if not result:
        found = discover_feeds(outlet["domain"])
        result = try_list([("discovered", u) for u in found if u not in outlet["feeds"]])
    if not result:
        result = try_list([("google_news", google_news_url(outlet["domain"]))])

    if not result:
        row = {"outlet": outlet["name"], "method": "none", "feed_url": "",
               "status": "Not readable", "items": 0, "newest_utc": "",
               "note": " | ".join(tried_notes)}
        return row, []

    method, url, feed, note = result
    articles = []
    for e in feed.entries:
        t = entry_time(e)
        articles.append({
            "outlet": outlet["name"],
            "title": clean_text(e.get("title"), 300),
            "link": e.get("link", ""),
            "summary": clean_text(e.get("summary")),
            "published": t.isoformat() if t else None,
        })
    times = [a["published"] for a in articles if a["published"]]
    row = {"outlet": outlet["name"], "method": method, "feed_url": url,
           "status": "OK", "items": len(articles),
           "newest_utc": max(times)[:16].replace("T", " ") if times else "",
           "note": note}
    return row, articles


def main():
    rows, all_articles = [], []
    print(f"Checking {len(OUTLETS)} outlets...\n")
    for outlet in OUTLETS:
        row, articles = check_outlet(outlet)
        rows.append(row)
        all_articles.extend(articles)
        mark = "OK " if row["status"] == "OK" else "-- "
        print(f"{mark} {row['outlet']:<16} {row['method']:<12} {row['items']:>4} items  {row['note'][:70]}")
        time.sleep(1)  # be polite: one site at a time, with a short pause

    # utf-8-sig makes Excel show Cyrillic correctly
    with open("feed_report.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    with open("articles.json", "w", encoding="utf-8") as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)

    ok = [r for r in rows if r["status"] == "OK"]
    by_method = {m: sum(1 for r in ok if r["method"] == m) for m in ("rss", "discovered", "google_news")}
    print(f"\n{len(ok)} of {len(rows)} outlets readable "
          f"({by_method['rss']} via known RSS, {by_method['discovered']} discovered, "
          f"{by_method['google_news']} via Google News).")
    print(f"{len(all_articles)} articles saved to articles.json; details in feed_report.csv.")


if __name__ == "__main__":
    main()
