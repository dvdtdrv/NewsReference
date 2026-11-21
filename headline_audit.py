"""
One-off check, started by hand (workflow "Check every headline of one outlet", headline-audit.yml).

Opens EVERY archived article page of one outlet once and writes down the headline the page shows
(<h1>, og:title, <title>) next to the headlines we stored, into headline_audit.json. Nothing in the
archive changes: the file is handed back as a download and compared by hand / by Claude.

Why (21 Nov 2026, David): bTV showed almost no headline changes since 5 Nov. bTV's pages refuse
GitHub's servers, so this runs on David's PC like fetch_local.py, one page at a time with the site's
robots.txt pause (crawl-delay, at least 1 s), exactly as polite as the normal checks.

Run by hand with:   python headline_audit.py "bTV Novinite"
"""

import json
import sys
import time

import requests

import collect
import link_check
from feeds import OUTLETS

RAW = "https://raw.githubusercontent.com/dvdtdrv/NewsReference/data/articles/{}.json"
MONTHS = ("2026-10", "2026-11")
OUT_FILE = "headline_audit.json"
MAX_MINUTES = 80


def main(name):
    outlet = next(o for o in OUTLETS if o["name"] == name)
    headers = collect.BROWSER_HEADERS if outlet.get("as_browser") else collect.HEADERS
    articles = []
    for m in MONTHS:
        try:
            articles += [a for a in requests.get(RAW.format(m), timeout=60).json() if a.get("outlet") == name]
        except (requests.RequestException, ValueError) as e:
            print("could not read", m, e)
    articles.sort(key=lambda a: a.get("published", ""))
    print(f"{name}: {len(articles)} articles to open")
    out = {"outlet": name, "started": collect.NOW.isoformat(), "pages": []}
    deadline = time.monotonic() + MAX_MINUTES * 60
    for i, a in enumerate(articles):
        if time.monotonic() > deadline:
            print("time is up, stopping at", i)
            break
        link = a.get("link")
        if not link or not collect.allowed(link):
            continue
        result, parts = link_check.probe(link, headers, link_check.headlines_of(a))
        out["pages"].append({"link": link, "published": a.get("published"), "titles": link_check.headlines_of(a),
                             "result": result, "page": parts})
        if i % 50 == 0:
            print(i, result, (parts or {}).get("h1", "")[:80])
            with open(OUT_FILE, "w", encoding="utf-8") as f:     # saved as we go, in case the run is cut off
                json.dump(out, f, ensure_ascii=False)
        time.sleep(collect.crawl_delay(link))
    out["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print("done:", len(out["pages"]), "pages")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "bTV Novinite")
