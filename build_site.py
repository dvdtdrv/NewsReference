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
from versions import changes_of, collapse

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


MEDIA_ONLY = ("outlet_info", "headline_changes", "outlet_totals", "story_totals")   # data only medii.html needs
MIN_ARTICLES = 100   # fewer articles than this in the period: shown, but not ranked ("малко данни")
EXAMPLES = 150       # how many of each outlet's latest changes the page can show


def headline_changes():
    """For the ranking under „Медии“: per outlet, how many articles it renamed after publishing,
    what kind of changes they were (versions.change_kind) and how many it deleted.
    The rows go into the page; the examples go into site/changes.json, loaded on a click."""
    folder = os.path.join("data", "articles")
    if not os.path.isdir(folder):
        return None, {}
    try:
        with open(os.path.join("data", "deleted.json"), encoding="utf-8") as f:
            deleted = json.load(f)
        deleted.pop("_meta", None)
    except (OSError, ValueError):
        deleted = {}
    checked_outlets = {e.get("outlet") for e in deleted.values()}
    rows, examples, first, last, total = {}, {}, None, None, 0
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            month = json.load(f)
        for a in (month["articles"] if isinstance(month, dict) else month):
            o = a.get("outlet")
            r = rows.setdefault(o, {"outlet": o, "articles": 0, "renamed": 0, "changes": 0,
                                    "minor": 0, "update": 0, "live": 0, "major": 0, "deleted": 0})
            r["articles"] += 1
            total += 1
            p = a.get("published", "")
            first = min(first or p, p)
            last = max(last or p, p)
            ch = changes_of(a)
            if ch:
                r["renamed"] += 1
                for kind, old, new, when in ch:
                    r["changes"] += 1
                    r[kind] += 1
                    examples.setdefault(o, []).append({"kind": kind, "old": old, "new": new, "seen": when,
                                                      "published": p, "link": a.get("link")})
            g = deleted.get(a.get("link")) or next((deleted[v["link"]] for v in a.get("versions", [])
                                                    if v.get("link") in deleted), None)
            if g and g.get("gone"):
                r["deleted"] += 1
                examples.setdefault(o, []).append({"kind": "deleted", "new": a.get("title"), "seen": g["gone"],
                                                  "published": p, "link": a.get("link")})
    for r in rows.values():
        r["deleted_checked"] = r["outlet"] in checked_outlets
    for o, items in examples.items():
        items.sort(key=lambda x: (x.get("seen") or x["published"]), reverse=True)
        examples[o] = items[:EXAMPLES]
    summary = {"from": first, "to": last, "articles": total, "min_articles": MIN_ARTICLES,
               "deleted_checked": bool(deleted), "rows": sorted(rows.values(), key=lambda r: r["outlet"])}
    return summary, examples


def outlet_story_totals():
    """In how many stories of the whole archive each outlet took part, and how many stories there are.
    A story can sit in two archive days (it went on past midnight): it counts once, by its id."""
    seen = {}
    if os.path.isdir(DAYS_DIR):
        for name in sorted(os.listdir(DAYS_DIR)):
            if name.endswith(".json"):
                with open(os.path.join(DAYS_DIR, name), encoding="utf-8") as f:
                    for s in json.load(f)["stories"]:
                        seen.setdefault(s["id"], set()).update(a["outlet"] for a in s["articles"])
    counts = {}
    for outlets in seen.values():
        for o in outlets:
            counts[o] = counts.get(o, 0) + 1
    return {"stories": len(seen), "by_outlet": counts}


def front_page_data():
    with open(os.path.join("data", "stories.json"), encoding="utf-8") as f:
        data = json.load(f)
    slim(data["stories"])
    data["archive_days"] = archive_days()
    data["articles_total"] = total_articles()
    data["outlet_info"] = outlet_info()
    data["headline_changes"], _ = headline_changes()
    # every article we ever collected from each outlet (the whole archive, not just these 48 hours)
    data["outlet_totals"] = {r["outlet"]: r["articles"] for r in (data["headline_changes"] or {}).get("rows", [])}
    data["story_totals"] = outlet_story_totals()
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
    # everything except what only „Медии“ shows (the outlet info and the ranking are the biggest part)
    light = {k: v for k, v in front.items() if k not in MEDIA_ONLY}
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(render(light, template))

    # the examples behind the headline-change ranking, loaded when someone opens an outlet's row
    _, examples = headline_changes()
    with open(os.path.join(OUT_DIR, "changes.json"), "w", encoding="utf-8") as f:
        json.dump(examples, f, ensure_ascii=False, separators=(",", ":"))

    # the subscription page: same template and data, shown in "support" mode
    with open(os.path.join(OUT_DIR, "abonament.html"), "w", encoding="utf-8") as f:
        f.write(render({**light, "page": "support", "stories": []}, template))

    # the search page: same template, "search" mode; it needs no stories of its own
    with open(os.path.join(OUT_DIR, "tarsene.html"), "w", encoding="utf-8") as f:
        f.write(render({**light, "page": "search", "stories": []}, template))

    # „Медии“ (9 Nov 2026): its own page; the only page that carries the outlet info and the
    # headline-change ranking, so the front page and the archive pages stay small and fast
    # each outlet's newest articles from the front page's stories (the outlet window lists them)
    recent = {}
    for st in front["stories"]:
        for a in st["articles"]:
            recent.setdefault(a["outlet"], {})[a["link"]] = {k: a[k] for k in ("title", "link", "published")}
    recent = {o: sorted(v.values(), key=lambda a: a["published"], reverse=True)[:6] for o, v in recent.items()}
    with open(os.path.join(OUT_DIR, "medii.html"), "w", encoding="utf-8") as f:
        f.write(render({**front, "page": "media", "stories": [], "outlet_recent": recent}, template))

    # „Архив“ (9 Nov 2026): its own page with the list of days
    with open(os.path.join(OUT_DIR, "arhiv.html"), "w", encoding="utf-8") as f:
        f.write(render({**light, "page": "archive", "stories": []}, template))

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
            "base": "../",
        }
        with open(os.path.join(OUT_DIR, "archive", f"{day['date']}.html"), "w", encoding="utf-8") as f:
            f.write(render(data, template))

    print(f"Website built: site\\index.html and {len(days)} archive pages in site\\archive\\  "
          "(double-click site\\index.html to open)")


if __name__ == "__main__":
    main()
