"""
Step 3: build the website pages from the latest stories and the archive.

Takes site_template.html and writes:
  site/index.html               the front page: stories from the last 48 hours
  site/abonament.html           the subscription page
  site/tarsene.html             the search page (the index itself is made by build_search.mjs)
  site/archive/YYYY-MM-DD.html  one page per day in the archive (data/stories/YYYY-MM-DD.json)
  site/periods/top-week.json    the most covered stories of the last week / month / year (also -month, -year),
                                which the front page loads when someone picks that period
  site/manifest.webmanifest, sw.js, icons   copied from web/, so phones can install the site as an app

The stories are put inside each page itself, so the pages work straight from your folder:
double-click site/index.html to open the site.

Run with:   python build_site.py
"""

import copy
import json
import os
import shutil
from datetime import datetime, timedelta

from feeds import OUTLETS, UNTRACKED
from versions import collapse

TEMPLATE = "site_template.html"
OUT_DIR = "site"
WEB_DIR = "web"   # manifest, icons and offline helper that make the site installable on phones
DAYS_DIR = os.path.join("data", "stories")
KEEP = ("outlet", "title", "link", "published", "image")
PERIODS = {"week": 7, "month": 30, "year": 365}   # the longer periods on the front page, in days
TOP_N = 100        # how many of the most covered stories each longer period keeps
PHOTOS_FILE = os.path.join("data", "page_images.json")   # each article's own photo (see collect.py)
_photos = None


def photo_for(a):
    """The photo the article's own page picked, if we know it; else the one we stored."""
    global _photos
    if _photos is None:
        try:
            with open(PHOTOS_FILE, encoding="utf-8") as f:
                _photos = json.load(f)
        except (OSError, ValueError):
            _photos = {}
    return _photos.get(a.get("link")) or a.get("image", "")


def spare_photo(a):
    """A second photo to try if the first doesn't load (e.g. the outlet deleted it)."""
    first = photo_for(a)
    for other in (a.get("image_feed"), a.get("image")):
        if other and other != first:
            return other
    return ""


def slim(stories):
    """Keep only what the page uses, so it loads fast."""
    for s in stories:
        # one card per article even if the outlet renamed it (older saved stories may hold both)
        arts = collapse(s["articles"])
        s["articles"] = [{**{k: a.get(k, "") for k in KEEP}, "image": photo_for(a), "image2": spare_photo(a),
                          **({"was": [v["title"] for v in a["versions"]]} if a.get("versions") else {})}
                         for a in arts]
    return stories


def archive_days():
    """The days in the archive, newest first, with how many stories each has."""
    if not os.path.isdir(DAYS_DIR):
        return []
    days = []
    for name in sorted(os.listdir(DAYS_DIR), reverse=True):
        if name.endswith(".json"):
            with open(os.path.join(DAYS_DIR, name), encoding="utf-8") as f:
                days.append({"date": name[:-5], "count": len(json.load(f)["stories"])})
    return days


def period_tops(days, generated_at):
    """The most covered stories of the last week, month and year, from the archive.

    A story counts for a period if it was still being reported in it (its newest article is inside).
    Same order as the front page: most outlets first, then the most recently updated.
    Goes through the archive one day at a time and keeps only the best TOP_N, so a year fits in memory.
    """
    now = datetime.fromisoformat(generated_at)
    cutoffs = {k: now - timedelta(days=n) for k, n in PERIODS.items()}
    oldest_day = (now - timedelta(days=max(PERIODS.values()) + 1)).date().isoformat()
    key = lambda s: (s["outlet_count"], s["last_updated"])
    best = {k: {} for k in PERIODS}
    for day in days:                                   # newest first
        if day["date"] < oldest_day:
            break
        with open(os.path.join(DAYS_DIR, f"{day['date']}.json"), encoding="utf-8") as f:
            stories = json.load(f)["stories"]
        for s in stories:
            updated = datetime.fromisoformat(s["last_updated"])
            for k, cut in cutoffs.items():
                if updated >= cut:
                    old = best[k].get(s["id"])          # a story can sit in two archive days: keep the bigger one
                    if old is None or key(s) > key(old):
                        best[k][s["id"]] = s
        for k in best:                                 # keep memory small
            if len(best[k]) > TOP_N * 3:
                best[k] = dict(sorted(best[k].items(), key=lambda kv: key(kv[1]), reverse=True)[:TOP_N])
    return {k: slim(copy.deepcopy(sorted(v.values(), key=key, reverse=True)[:TOP_N])) for k, v in best.items()}


def render(data, template, fragment_only=False):
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")  # a headline containing "</script>" must not end the script
    page = template.replace("/*__DATA__*/", payload).replace("{{BASE}}", data.get("base", ""))
    if fragment_only:
        return page
    # wrap in a full HTML document: title, fonts and styles go in <head>, the rest in <body>
    head, body = page.split("<!--body-->", 1)
    return (
        '<!doctype html>\n<html lang="bg">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        f"{head}</head>\n<body>{body}</body>\n</html>\n"
    )


def total_articles():
    """How many articles the permanent archive holds (data/articles/YYYY-MM.json)."""
    folder = os.path.join("data", "articles")
    if not os.path.isdir(folder):
        return None
    total = 0
    for name in os.listdir(folder):
        if name.endswith(".json"):
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                month = json.load(f)
            total += len(month["articles"] if isinstance(month, dict) else month)
    return total


def outlet_info():
    """What the outlet window shows about each outlet: its website, plus what's written in outlets_info.json."""
    try:
        with open("outlets_info.json", encoding="utf-8") as f:
            written = json.load(f)
    except (OSError, ValueError):
        written = {}
    return {o["name"]: {"domain": o.get("domain", ""), **written.get(o["name"], {})} for o in OUTLETS}


def front_page_data():
    with open(os.path.join("data", "stories.json"), encoding="utf-8") as f:
        data = json.load(f)
    slim(data["stories"])
    data["archive_days"] = archive_days()
    data["articles_total"] = total_articles()
    data["outlet_info"] = outlet_info()
    data["base"] = ""
    return data


def build(fragment_only=False):
    """The front page as one HTML string (used for the preview)."""
    with open(TEMPLATE, encoding="utf-8") as f:
        return render(front_page_data(), f.read(), fragment_only)


def main():
    with open(TEMPLATE, encoding="utf-8") as f:
        template = f.read()
    os.makedirs(os.path.join(OUT_DIR, "archive"), exist_ok=True)

    # web app files (manifest, icons, offline helper) are copied as they are
    for name in os.listdir(WEB_DIR):
        shutil.copyfile(os.path.join(WEB_DIR, name), os.path.join(OUT_DIR, name))

    front = front_page_data()
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(render(front, template))

    # the subscription page: same template and data, shown in "support" mode
    with open(os.path.join(OUT_DIR, "abonament.html"), "w", encoding="utf-8") as f:
        f.write(render({**front, "page": "support"}, template))

    # the search page: same template, "search" mode; it needs no stories of its own
    with open(os.path.join(OUT_DIR, "tarsene.html"), "w", encoding="utf-8") as f:
        f.write(render({**front, "page": "search", "stories": []}, template))

    days = front["archive_days"]

    # the longer periods on the front page (week, month, year): loaded only when someone picks one
    os.makedirs(os.path.join(OUT_DIR, "periods"), exist_ok=True)
    for name, stories in period_tops(days, front["generated_at"]).items():
        with open(os.path.join(OUT_DIR, "periods", f"top-{name}.json"), "w", encoding="utf-8") as f:
            json.dump({"generated_at": front["generated_at"], "stories": stories}, f,
                      ensure_ascii=False, separators=(",", ":"))

    for day in days:
        with open(os.path.join(DAYS_DIR, f"{day['date']}.json"), encoding="utf-8") as f:
            saved = json.load(f)
        data = {
            "generated_at": saved["updated_at"],
            "archive_date": day["date"],
            "tracked_outlets": saved.get("tracked_outlets", []),
            "untracked_outlets": UNTRACKED,
            "stories": slim(saved["stories"]),
            "archive_days": days,
            "outlet_info": front["outlet_info"],
            "base": "../",
        }
        with open(os.path.join(OUT_DIR, "archive", f"{day['date']}.html"), "w", encoding="utf-8") as f:
            f.write(render(data, template))

    print(f"Website built: site\\index.html and {len(days)} archive pages in site\\archive\\  "
          "(double-click site\\index.html to open)")


if __name__ == "__main__":
    main()
