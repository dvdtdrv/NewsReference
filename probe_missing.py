"""
Find a way to read new outlets (the TARGETS list below): a feed, or a news sitemap.

For each outlet it tries, slowly and politely:
  1. the site's robots.txt (what we're allowed to read, and where its sitemaps are),
  2. known and common feed addresses (/rss, /feed, /rss.xml ...), with and without "www.",
  3. feed links hidden in the homepage,
  4. the sitemaps listed in robots.txt (do they list recent articles with titles?).

Everything it finds is written to probe_report.txt. Nothing is changed in the project.
Run it with:   python probe_missing.py     (or double-click run_probe.bat)
"""

import re
import sys
import time
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import feedparser
import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

USER_AGENT = "NewsReferenceBot/0.1 (student project comparing Bulgarian news coverage)"
HEADERS = {"User-Agent": USER_AGENT}
TIMEOUT = 20
PAUSE = 1.5  # seconds between requests, to be polite

# Outlets to look into (the 13 asked for on 1 Nov 2026). Earlier probes: BTA, Club Z, BNR, Trud,
# Novini.bg, Offnews, Dir.bg, PIK - all settled now, see feeds.py.
TARGETS = [
    {"name": "DW (български)", "domain": "dw.com",
     "known": ["https://rss.dw.com/xml/rss-bul-all", "https://rss.dw.com/rdf/rss-bul-all"]},
    {"name": "Свободна точка", "domain": "svobodnatochka.bg", "known": []},
    {"name": "Boulevard Bulgaria", "domain": "boulevardbulgaria.bg", "known": []},
    {"name": "Darik", "domain": "dariknews.bg", "known": []},
    {"name": "Bloomberg TV Bulgaria", "domain": "bloombergtv.bg", "known": []},
    {"name": "Евроком", "domain": "eurocom.bg", "known": []},
    {"name": "BG On Air", "domain": "bgonair.bg", "known": []},
    {"name": "Euronews България", "domain": "euronewsbulgaria.com", "known": []},
    {"name": "Vesti.bg", "domain": "vesti.bg", "known": []},
    {"name": "Марица", "domain": "marica.bg", "known": []},
    {"name": "Moreto.net", "domain": "moreto.net", "known": []},
    {"name": "News.bg", "domain": "news.bg", "known": []},
    {"name": "Фокус", "domain": "focus-news.net", "known": []},
]

COMMON_PATHS = ["/rss", "/feed", "/rss.xml", "/feed.xml", "/rss.php", "/feed/", "/rss/",
                "/index.xml", "/bg/rss", "/news/rss", "/rss/news", "/feeds/all.rss",
                "/feeds/rss", "/api/rss", "/api/rss/main", "/rss/all", "/rss/latest", "/rss/news.xml"]

log_lines = []


def log(text=""):
    print(text)
    log_lines.append(text)


def get(url):
    """One polite request. Returns the response, or None on a connection error."""
    time.sleep(PAUSE)
    try:
        return requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as e:
        log(f"    could not connect to {url} ({type(e).__name__})")
        return None


def read_robots(base):
    """Fetch robots.txt; return (parser, list of sitemap URLs)."""
    rp = RobotFileParser()
    r = get(base + "/robots.txt")
    if r is None or r.status_code != 200:
        code = r.status_code if r is not None else "no answer"
        log(f"    robots.txt: not available ({code}) -> treated as 'everything allowed'")
        rp.parse([])
        return rp, []
    rp.parse(r.text.splitlines())
    sitemaps = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", r.text)
    disallows = re.findall(r"(?im)^\s*disallow:\s*(\S+)", r.text)
    log(f"    robots.txt: {len(disallows)} disallow rules, {len(sitemaps)} sitemaps listed")
    for d in disallows[:12]:
        log(f"      disallow {d}")
    return rp, sitemaps


def try_feed(rp, url):
    """Return a short description if url is a working feed, else None."""
    if not rp.can_fetch(USER_AGENT, url):
        log(f"    {url}: robots.txt disallows")
        return None
    r = get(url)
    if r is None:
        return None
    if r.status_code != 200:
        extra = f", Retry-After: {r.headers['Retry-After']}" if "Retry-After" in r.headers else ""
        log(f"    {url}: HTTP {r.status_code}{extra}")
        return None
    feed = feedparser.parse(r.content)
    if not feed.entries:
        log(f"    {url}: loads, but isn't a feed")
        return None
    newest = feed.entries[0].get("published") or feed.entries[0].get("updated") or "?"
    desc = f"{len(feed.entries)} items, first item dated {newest}"
    log(f"    {url}: FEED FOUND - {desc}")
    return desc


def homepage_feed_links(rp, base):
    if not rp.can_fetch(USER_AGENT, base + "/"):
        log("    homepage: robots.txt disallows")
        return []
    r = get(base + "/")
    if r is None or r.status_code != 200:
        log(f"    homepage: HTTP {r.status_code if r is not None else 'no answer'}")
        return []
    links = re.findall(r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]*>', r.text, re.I)
    hrefs = []
    for tag in links:
        m = re.search(r'href=["\']([^"\']+)', tag)
        if m:
            hrefs.append(urljoin(r.url, m.group(1)))
    # some sites (Dir.bg) link their feed as an ordinary link with "rss" or "feed" in it
    for href in re.findall(r'<a[^>]+href=["\']([^"\']*(?:rss|feed)[^"\']*)["\']', r.text, re.I):
        full = urljoin(r.url, href)
        if full not in hrefs and "facebook" not in full and "feedback" not in full.lower():
            hrefs.append(full)
    log(f"    homepage: {len(hrefs)} feed links found: {', '.join(hrefs[:4])}")
    return hrefs


def check_sitemap(rp, url, depth=0):
    """Describe a sitemap: how many URLs, newest date, whether it has headlines."""
    if depth > 1:
        return
    if not rp.can_fetch(USER_AGENT, url):
        log(f"    sitemap {url}: robots.txt disallows")
        return
    r = get(url)
    if r is None or r.status_code != 200:
        log(f"    sitemap {url}: HTTP {r.status_code if r is not None else 'no answer'}")
        return
    text = r.text
    if "<sitemapindex" in text:
        children = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", text)
        log(f"    sitemap {url}: index of {len(children)} sitemaps")
        # look inside the news sitemap if there is one, else the first one
        news = [c for c in children if "news" in c.lower()] or children[:1]
        for child in news[:2]:
            check_sitemap(rp, child, depth + 1)
        return
    urls = len(re.findall(r"<url>", text))
    dates = sorted(re.findall(r"<(?:lastmod|news:publication_date)>\s*([^<]+)", text))
    titles = re.findall(r"<news:title>\s*(?:<!\[CDATA\[)?([^<\]]+)", text)
    log(f"    sitemap {url}: {urls} articles, newest {dates[-1] if dates else 'no dates'}, "
        f"{'HAS HEADLINES (news sitemap)' if titles else 'no headlines'}")
    for t in titles[:3]:
        log(f"      e.g. {t.strip()[:90]}")


def probe(target):
    log(f"\n=== {target['name']} ({target['domain']}) ===")
    found = []
    for base in (f"https://www.{target['domain']}", f"https://{target['domain']}"):
        log(f"  {base}")
        rp, sitemaps = read_robots(base)
        # known URLs only once (retrying BTA's too often is what got us "too many requests")
        known = list(target["known"]) if base.startswith("https://www.") else []
        # feeds the site itself links to are the most likely right, so try those first
        candidates = known + homepage_feed_links(rp, base) + [base + p for p in COMMON_PATHS]
        seen = set()
        for url in candidates:
            if url in seen:
                continue
            seen.add(url)
            desc = try_feed(rp, url)
            if desc:
                found.append((url, desc))
                break  # one working feed is enough
        if found:
            break
        for sm in sitemaps[:3]:   # no feed: is there a news sitemap with headlines instead?
            check_sitemap(rp, sm)
    verdict = f"USE FEED {found[0][0]}" if found else "no feed found (see sitemap lines above)"
    log(f"  RESULT: {verdict}")
    return target["name"], verdict


def main():
    log("Probing outlets that check_feeds.py couldn't read. This takes a few minutes.")
    results = [probe(t) for t in TARGETS]
    log("\n=== SUMMARY ===")
    for name, verdict in results:
        log(f"  {name:<10} {verdict}")
    with open("probe_report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))
    print("\nSaved to probe_report.txt")


if __name__ == "__main__":
    main()
