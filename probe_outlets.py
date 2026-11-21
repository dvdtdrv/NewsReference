"""
Can THIS computer read the outlets marked "local" in feeds.py (the ones read on David's PC)?

Asks each one's feed once, exactly like collect.py would (same robots.txt check, same name/headers),
and prints the answer. Reads only the feed itself: no article pages, no photos.
Used by the workflow "Test PC outlets from GitHub" (probe-outlets.yml) to see whether GitHub's servers
are let in now, e.g. after an outlet allows NewsReferenceBot. Run by hand with:   python probe_outlets.py
"""

import time

import feedparser
import requests

import collect
from feeds import OUTLETS


def main():
    ok = []
    for outlet in OUTLETS:
        if not outlet.get("local"):
            continue
        url = outlet.get("feed") or outlet.get("sitemap") or outlet.get("page")
        if not collect.allowed(url):
            print(f"{outlet['name']:<14} skipped: robots.txt disallows")
            continue
        headers = collect.BROWSER_HEADERS if outlet.get("as_browser") else collect.HEADERS
        t = time.monotonic()
        try:
            r = requests.get(url, headers=headers, timeout=30)
            items = len(feedparser.parse(r.content).entries) or r.content.count(b"<loc>")
            good = r.status_code == 200 and items > 0
            print(f"{outlet['name']:<14} {'OK     ' if good else 'REFUSED'} HTTP {r.status_code}, {items} items, "
                  f"{time.monotonic() - t:.1f} s")
            if good:
                ok.append(outlet["name"])
        except requests.RequestException as e:
            print(f"{outlet['name']:<14} REFUSED {type(e).__name__} after {time.monotonic() - t:.1f} s")
        time.sleep(collect.crawl_delay(url))
    print("Readable from here:", ", ".join(ok) or "none")


if __name__ == "__main__":
    main()
