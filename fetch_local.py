"""
Runs on David's PC (through the GitHub runner, every 30 minutes).

Some outlets refuse GitHub's servers but accept a normal Bulgarian internet connection. This script
reads only those outlets (marked "local" in feeds.py), in exactly the same way collect.py reads the
others, and saves the articles to local_articles.json. GitHub's main run then picks that file up.

Nothing here touches the archive: it only fetches and hands over.
Run by hand with:   python fetch_local.py
"""

import json
import time

import collect
from feeds import OUTLETS

OUT_FILE = "local_articles.json"


def main():
    result = {"fetched_at": collect.NOW.isoformat(), "outlets": {}}
    photos = collect.load_page_images()   # remembered article photos (kept outside the project folder)
    for outlet in OUTLETS:
        if not outlet.get("local"):
            continue
        articles, status, note = collect.fetch_outlet(outlet, {}, photos)
        result["outlets"][outlet["name"]] = {"status": status, "note": note, "articles": articles}
        print(f"{status:<8} {outlet['name']:<14} {len(articles):>4} articles  {note}")
        time.sleep(1)
    collect.save_page_images(photos)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    print(f"Saved {OUT_FILE}")


if __name__ == "__main__":
    main()
