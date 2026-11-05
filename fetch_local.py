"""
Runs on David's PC (through the GitHub runner, every 30 minutes).

Some outlets refuse GitHub's servers but accept a normal Bulgarian internet connection. This script
reads only those outlets (marked "local" in feeds.py), plus the article photos of outlets marked
"photos_on_pc", in exactly the same way collect.py reads the
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
    result = {"fetched_at": collect.NOW.isoformat(), "outlets": {}, "photos": {}}
    photos = collect.load_page_images()   # remembered article photos (kept outside the project folder)
    for outlet in OUTLETS:
        if outlet.get("local"):
            articles, status, note = collect.fetch_outlet(outlet, {}, photos)
            result["outlets"][outlet["name"]] = {"status": status, "note": note, "articles": articles}
            print(f"{status:<8} {outlet['name']:<14} {len(articles):>4} articles  {note}")
            time.sleep(1)
        elif outlet.get("photos_on_pc"):
            # GitHub reads this outlet itself; only its article pages refuse GitHub, so we send the photos
            articles, status, note = collect.fetch_outlet(outlet, {}, photos)
            found = {a["link"]: photos[a["link"]] for a in articles if photos.get(a.get("link"))}
            result["photos"].update(found)
            print(f"{status:<8} {outlet['name']:<14} {len(found):>4} photos only  {note}")
            time.sleep(1)
    # are older articles of these outlets still online? GitHub says which links are due (link_check.py)
    import link_check
    result["link_checks"] = link_check.check_on_pc(
        lambda o: collect.BROWSER_HEADERS if o.get("as_browser") else collect.HEADERS,
        OUTLETS, collect.allowed, collect.crawl_delay)
    print(f"Checked {len(result['link_checks'])} older links of these outlets")
    collect.save_page_images(photos)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    print(f"Saved {OUT_FILE}")


if __name__ == "__main__":
    main()
