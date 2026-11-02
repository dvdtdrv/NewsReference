"""
Test: which photo does each outlet itself choose for its articles?

For a few recent articles per outlet it compares
  - the photo our collector takes from the feed, and
  - the photo the article page announces for sharing (og:image, the one Facebook/Viber previews show).
Writes probe_images.json. Reads only the top part of each page (where og:image is), respects robots.txt,
waits between requests, and skips BTA (its permission covers the feed only).

Run with:   python probe_images.py
"""

import json
import re
import sys
import time

import requests

import collect
from feeds import OUTLETS

PER_OUTLET = 4
HEAD_BYTES = 250_000
OG = re.compile(r"""<meta[^>]+(?:property|name)\s*=\s*["'](og:image(?::secure_url)?|twitter:image(?::src)?)["'][^>]*>""", re.I)
CONTENT = re.compile(r"""content\s*=\s*["']([^"']+)["']""", re.I)


def page_image(url, headers):
    with requests.get(url, headers=headers, timeout=collect.TIMEOUT, stream=True) as r:
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        raw = b""
        for chunk in r.iter_content(16384):
            raw += chunk
            if len(raw) > HEAD_BYTES or b"</head>" in raw.lower():
                break
    text = raw.decode(r.encoding or "utf-8", errors="replace")
    found = {}
    for m in OG.finditer(text):
        c = CONTENT.search(m.group(0))
        if c:
            found.setdefault(m.group(1).lower().split(":")[0], c.group(1))
    img = found.get("og") or found.get("twitter")
    return (collect.html.unescape(img) if img else ""), "ok"


def main():
    out = []
    for outlet in OUTLETS:
        if outlet.get("gentle"):
            out.append({"outlet": outlet["name"], "skipped": "permission covers the feed only"})
            continue
        try:
            articles, status, note = collect.fetch_outlet(outlet, {})
        except Exception as e:
            out.append({"outlet": outlet["name"], "error": str(e)[:200]})
            continue
        headers = collect.BROWSER_HEADERS if outlet.get("as_browser") else collect.HEADERS
        delay = 10 if outlet["name"] == "News.bg" else 1.5
        rows = []
        for a in [a for a in articles if a.get("link")][:PER_OUTLET]:
            row = {"title": a["title"][:90], "link": a["link"], "feed_image": a.get("image", "")}
            if not collect.allowed(a["link"]):
                row["page"] = "robots.txt disallows"
            else:
                try:
                    img, st = page_image(a["link"], headers)
                    row["page"] = st
                    row["og_image"] = collect.fix_image_url(img, a["link"], outlet.get("domain", "")) if img else ""
                except Exception as e:
                    row["page"] = f"error: {str(e)[:120]}"
                time.sleep(delay)
            rows.append(row)
        out.append({"outlet": outlet["name"], "feed_status": status, "articles": rows})
        print(outlet["name"], status, sum(1 for r in rows if r.get("og_image")), "/", len(rows), "with og:image")
    with open(sys.argv[1] if len(sys.argv) > 1 else "probe_images.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
