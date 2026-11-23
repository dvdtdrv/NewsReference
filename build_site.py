"""
Step 3: build the website pages from the latest stories and the archive.

Takes site_template.html and writes:
  site/index.html               the front page: the 40 stories its first view shows (most covered, 24 hours)
  site/stories-48h.json         the front page's other stories of the last 48 hours, loaded in the background
  site/abonament.html           the subscription page
  site/tarsene.html             the search page (the index itself is made by build_search.mjs)
  site/archive/YYYY-MM-DD.html  one page per day in the archive (data/stories/YYYY-MM-DD.json)
  site/feed/YYYY-MM-DD-HH.json  „Всички новини“: every article of the last 7 days, one file per hour
  site/outlets.json             what the outlet window shows (info, totals), for pages other than medii.html
  site/version.json             the time of the last update (open pages check it and offer „Обнови“)
  site/pravila.html             the legal page (who runs the site, terms, privacy, cookies, copyright, corrections)
  site/periods/top-week.json    the most covered stories of the last week / month / year (also -month, -year),
                                which the front page loads when someone picks that period
  site/manifest.webmanifest, sw.js, icons   copied from web/, so phones can install the site as an app
  site/sitemap.xml, robots.txt  for search engines (21 Nov 2026): the list of all pages, and where that list is

The stories are put inside each page itself, so the pages work straight from your folder:
double-click site/index.html to open the site. (Since 23 Nov 2026 the front page opened that way shows only its
first 40 stories; the other lists need the site served over http, like the week and month lists always did.)

Run with:   python build_site.py
"""

import copy
import html
import json
import os
import re
from collections import Counter
from itertools import combinations
import shutil
from datetime import datetime, timedelta, timezone

from feeds import OUTLETS, UNTRACKED
from versions import changes_of, collapse

TEMPLATE = "site_template.html"
OUT_DIR = "site"
WEB_DIR = "web"   # manifest, icons and offline helper that make the site installable on phones
DAYS_DIR = os.path.join("data", "stories")
KEEP = ("outlet", "title", "link", "published", "image")
PERIODS = {"week": 7, "month": 30, "year": 365}   # the longer periods on the front page, in days
SITE_URL = "https://newsreference.bg/"   # the site's official address (21 Nov 2026), used by search engines
SHARE_IMAGE = SITE_URL + "icon-512.png"  # the picture shown when someone shares a link (Facebook, Viber...)
MONTHS_BG = ("януари", "февруари", "март", "април", "май", "юни", "юли", "август", "септември", "октомври",
             "ноември", "декември")
TOP_N = 100        # how many of the most covered stories each longer period keeps
PHOTOS_FILE = os.path.join("data", "page_images.json")   # each article's own photo (see collect.py)
# Outlets (or photographers, through their outlet) that asked us not to show their photos: write the outlet's
# name, as in feeds.py, into no_photos.json, e.g. ["BTA"]. Its cards then show the outlet's name instead of a photo.
try:
    with open("no_photos.json", encoding="utf-8") as f:
        NO_PHOTOS = set(json.load(f))
except (OSError, ValueError):
    NO_PHOTOS = set()

_photos = None


def photo_for(a):
    """The photo the article's own page picked, if we know it; else the one we stored."""
    global _photos
    if a.get("outlet") in NO_PHOTOS:
        return ""
    if _photos is None:
        try:
            with open(PHOTOS_FILE, encoding="utf-8") as f:
                _photos = json.load(f)
        except (OSError, ValueError):
            _photos = {}
    return _photos.get(a.get("link")) or a.get("image", "")


_feed_photos = None


def feed_photo(link):
    """The photo the outlet's feed gave for this article (collect.py keeps it as image_feed in the article
    archive). Stories don't carry it, so before 21 Nov 2026 the spare photo was lost: Fakti's own share photo
    is missing on its server for ~1 in 25 articles while its feed photo works, and those cards stayed empty."""
    global _feed_photos
    if _feed_photos is None:
        _feed_photos = {}
        folder = os.path.join("data", "articles")
        for name in (os.listdir(folder) if os.path.isdir(folder) else []):
            if name.endswith(".json"):
                with open(os.path.join(folder, name), encoding="utf-8") as f:
                    month = json.load(f)
                for x in (month["articles"] if isinstance(month, dict) else month):
                    if x.get("image_feed") and x.get("link"):
                        _feed_photos[x["link"]] = x["image_feed"]
    return _feed_photos.get(link, "")


def spare_photo(a):
    """A second photo to try if the first doesn't load (e.g. the outlet deleted it)."""
    if a.get("outlet") in NO_PHOTOS:
        return ""
    first = photo_for(a)
    for other in (a.get("image_feed") or feed_photo(a.get("link")), a.get("image")):
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


def seo_head(path, title, description):
    """Tags for search engines and link previews (21 Nov 2026): the page's official address (canonical, so
    Google counts newsreference.bg and not the old github.io address), its title and description, and what
    Facebook, Viber, X and others show when someone shares the link."""
    url = SITE_URL + path
    t, d = html.escape(title, quote=True), html.escape(description, quote=True)
    return (
        f"<title>{t}</title>\n"
        f'<meta name="description" content="{d}">\n'
        f'<link rel="canonical" href="{url}">\n'
        '<meta property="og:type" content="website">\n'
        '<meta property="og:site_name" content="News Reference">\n'
        '<meta property="og:locale" content="bg_BG">\n'
        f'<meta property="og:url" content="{url}">\n'
        f'<meta property="og:title" content="{t}">\n'
        f'<meta property="og:description" content="{d}">\n'
        f'<meta property="og:image" content="{SHARE_IMAGE}">\n'
        '<meta name="twitter:card" content="summary">\n'
    )


def day_bg(day):
    """2026-11-20 -> 20 ноември 2026"""
    y, m, d = day.split("-")
    return f"{int(d)} {MONTHS_BG[int(m) - 1]} {y}"


def render(data, template, fragment_only=False, seo=None):
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")  # a headline containing "</script>" must not end the script
    page = template.replace("/*__DATA__*/", payload).replace("{{BASE}}", data.get("base", ""))
    if seo:   # (path, title, description): replaces the template's general title and description
        start = page.index("<title>")
        page = page[:start] + seo_head(*seo) + page[page.index("</title>", start) + len("</title>"):].lstrip("\n")
        d = page.index('<meta name="description"', start + 300)   # the template's own description: drop it
        page = page[:d] + page[page.index(">", d) + 1:].lstrip("\n")
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
    # 22 Nov 2026 (David): the front page's „истории" counts the whole archive, like „статии" (story_totals is medii-only)
    data["stories_total"] = data["story_totals"]["stories"]
    data["base"] = ""
    return data


GEO_FILE = "geo_bg.json"   # Bulgaria's border and the towns we look for in headlines (the map on the first screen)


def hero_data(front):
    """The first screen's graphics (21 Nov 2026), from the last 24 hours:
    - the media wheel: every outlet's articles, when it last wrote, and how many stories each pair of outlets shared
    - the pulse: articles per hour
    - the map: towns named in the stories, with one story that has the town in its own headline
    Small on purpose (a few KB): the front page carries it, the other pages don't."""
    now = datetime.fromisoformat(front["generated_at"])
    since = now - timedelta(hours=24)
    try:
        with open(os.path.join("data", "articles.json"), encoding="utf-8") as f:
            articles = json.load(f)
    except (OSError, ValueError):
        return None

    def seen_at(a):   # an outlet whose clock runs ahead counts from when we first read the article
        t = datetime.fromisoformat(a["published"])
        c = a.get("collected")
        return min(t, datetime.fromisoformat(c)) if c else t

    recent = [(a, seen_at(a)) for a in articles]
    recent = [(a, t) for a, t in recent if since < t <= now + timedelta(minutes=5)]
    count, last = Counter(), {}
    hours = [0] * 24
    for a, t in recent:
        count[a["outlet"]] += 1
        last[a["outlet"]] = max(last.get(a["outlet"], t), t)
        hours[min(23, max(0, 23 - int((now - t).total_seconds() // 3600)))] += 1
    stories = [st for st in front["stories"] if datetime.fromisoformat(st["last_updated"]) > since]
    pairs = Counter()
    for st in stories:
        for a, b in combinations(sorted({x["outlet"] for x in st["articles"]}), 2):
            pairs[(a, b)] += 1
    names = [o["name"] for o in front.get("tracked_outlets", [])] or sorted(count)
    # around the wheel, outlets that share many stories sit next to each other: start with the busiest, then
    # always add the outlet that shares most with the last two placed
    shared = lambda x, y: pairs.get(tuple(sorted((x, y))), 0)
    order = [max(names, key=lambda o: count[o])]
    left = [o for o in names if o not in order]
    while left:
        nxt = max(left, key=lambda o: sum(shared(o, l) for l in order[-2:]) + count[o] * 0.01)
        order.append(nxt)
        left.remove(nxt)
    idx = {o: i for i, o in enumerate(order)}
    top_pairs = [[idx[a], idx[b], n] for (a, b), n in pairs.most_common(260) if a in idx and b in idx]
    places = []
    try:
        with open(GEO_FILE, encoding="utf-8") as f:
            geo = json.load(f)
    except (OSError, ValueError):
        geo = None
    if geo:
        for town, (x, y, forms) in geo["cities"].items():
            rx = re.compile(r"(?<![а-я])(?:" + forms + ")")
            hits = [st for st in stories
                    if rx.search(" ".join([st["headline"]] + [a["title"] for a in st["articles"]]).lower())]
            if not hits:
                continue
            own = [st for st in hits if rx.search(st["headline"].lower())]
            ex = max(own, key=lambda st: st["outlet_count"]) if own else None
            places.append({"n": town, "x": x, "y": y, "c": len(hits),
                           "h": ex["headline"] if ex else "", "id": ex["id"] if ex else ""})
        places.sort(key=lambda p: -p["c"])
    return {
        "stories": len(stories), "articles": len(recent), "hours": hours,
        "outlets": [{"n": o, "c": count[o], "last": last[o].isoformat(timespec="seconds") if o in last else None} for o in order],
        "pairs": top_pairs, "places": places[:40],
        "map": {"w": geo["width"], "h": geo["height"], "outline": geo["outline"]} if geo else None,
    }


FEED_HOURS = 1      # „Всички новини“: one file per hour, so a phone loads little at a time (~30 KB zipped)


def feed_files(front):
    """„Всички новини“ (12 Nov 2026): every article of the last 7 days, newest first, without grouping.
    Returns {file name: rows}; a row is [published, outlet, headline, link, story id, outlets in the story,
    archive day of the story ("" = the story is on the front page)]. The headline and the link only."""
    path = os.path.join("data", "articles.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        articles = json.load(f)
    # which story each article is in: the archived days first, then the front page's stories on top
    where = {}
    for day in front["archive_days"][:10]:
        with open(os.path.join(DAYS_DIR, f"{day['date']}.json"), encoding="utf-8") as f:
            for s in json.load(f)["stories"]:
                for a in s["articles"]:
                    where[a["link"]] = (s["id"], len(s["outlets"]), day["date"])
    for s in front["stories"]:
        for a in s["articles"]:
            where[a["link"]] = (s["id"], len(s["outlets"]), "")
    now = front["generated_at"]
    files = {}
    for a in articles:
        if not (a.get("title") and a.get("link") and a.get("published")):
            continue
        # some outlets stamp articles with a time that hadn't come yet when we read them (BNR: about an hour
        # ahead on most articles): an article can't be newer than the moment we first saw it, so use that
        try:
            d = datetime.fromisoformat(a["published"]).astimezone(timezone.utc)
            seen = datetime.fromisoformat(a.get("collected") or now).astimezone(timezone.utc)
        except ValueError:
            continue
        d = min(d, seen)
        key = d.strftime("%Y-%m-%d-") + f"{d.hour // FEED_HOURS * FEED_HOURS:02d}"
        sid, n, day = where.get(a["link"], (0, 0, ""))
        files.setdefault(key, []).append([d.strftime("%Y-%m-%dT%H:%M:%SZ"), a["outlet"], a["title"], a["link"], sid, n, day])
    for rows in files.values():
        rows.sort(key=lambda r: r[0], reverse=True)
    return files


FIRST_STORIES = 40                # stories inside index.html itself: the first two pages of „Покажи още истории“
REST_FILE = "stories-48h.json"    # the front page's other stories, loaded in the background


def split_front_stories(front):
    """Split the front page's stories (23 Nov 2026): the ones the first view shows (most covered in the last
    24 hours, FIRST_STORIES of them, in the page's own order) and the rest (in a file, loaded after the page shows).
    Must count like setView in site_template.html: outlets that wrote within the last 24 hours, at least 2,
    most first, then the newest update. JavaScript keeps times to the millisecond, so we do too."""
    def ms(iso):
        t = datetime.fromisoformat(iso)
        return t.replace(microsecond=t.microsecond // 1000 * 1000)
    cut = ms(front["generated_at"]) - timedelta(hours=24)
    stories = front["stories"]
    counted = [(s, len({a["outlet"] for a in s["articles"] if ms(a["published"]) >= cut})) for s in stories]
    counted = [x for x in counted if x[1] >= 2]
    counted.sort(key=lambda x: x[0]["last_updated"], reverse=True)   # stable sorts: newest update, then outlets
    counted.sort(key=lambda x: x[1], reverse=True)
    keep = {s["id"] for s, _ in counted[:FIRST_STORIES]}
    return [s for s in stories if s["id"] in keep], [s for s in stories if s["id"] not in keep]


def build(fragment_only=False):
    """The front page as one HTML string (used for the preview)."""
    with open(TEMPLATE, encoding="utf-8") as f:
        return render(front_page_data(), f.read(), fragment_only)


def write_sitemap(generated_at, archive_lastmods):
    """sitemap.xml lists every page for search engines (21 Nov 2026); robots.txt tells them where it is.
    (Cloudflare adds its own lines about AI use on top of our robots.txt.)"""
    main_pages = ("", "medii.html", "arhiv.html", "tarsene.html", "abonament.html", "pravila.html")
    rows = [(p, generated_at) for p in main_pages] + sorted(archive_lastmods.items(), reverse=True)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, when in rows:
        lines.append(f"  <url><loc>{SITE_URL}{path}</loc><lastmod>{when}</lastmod></url>")
    lines.append("</urlset>")
    with open(os.path.join(OUT_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(OUT_DIR, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}sitemap.xml\n")


def main():
    with open(TEMPLATE, encoding="utf-8") as f:
        template = f.read()
    os.makedirs(os.path.join(OUT_DIR, "archive"), exist_ok=True)

    # web app files (manifest, icons, offline helper) are copied as they are
    for name in os.listdir(WEB_DIR):
        shutil.copyfile(os.path.join(WEB_DIR, name), os.path.join(OUT_DIR, name))

    front = front_page_data()

    # „Всички новини“: the articles go into small files in site/feed/, the front page only lists the files
    feed = feed_files(front)
    shutil.rmtree(os.path.join(OUT_DIR, "feed"), ignore_errors=True)
    os.makedirs(os.path.join(OUT_DIR, "feed"), exist_ok=True)
    for key, rows in feed.items():
        with open(os.path.join(OUT_DIR, "feed", f"{key}.json"), "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, separators=(",", ":"))
    front["feed_files"] = sorted(feed, reverse=True)
    # 23 Nov 2026 (David: picking an outlet was slow): the same rows again, one file per outlet, so picking one
    # outlet loads one file instead of going through up to 170 hourly files one after another
    per_outlet, names = {}, {}
    for rows in feed.values():
        for r in rows:
            per_outlet.setdefault(r[1], {})[r[3]] = r          # by link: an article once
    for outlet, rows in per_outlet.items():
        slug = re.sub(r"[^a-z0-9]+", "-", outlet.lower()).strip("-") or "x"
        while f"o-{slug}" in names.values():                 # two names that read the same in Latin letters
            slug += "-2"
        names[outlet] = f"o-{slug}"
        with open(os.path.join(OUT_DIR, "feed", f"{names[outlet]}.json"), "w", encoding="utf-8") as f:
            json.dump(sorted(rows.values(), key=lambda r: r[0], reverse=True), f, ensure_ascii=False, separators=(",", ":"))
    front["feed_outlet_files"] = names
    front["feed_outlets"] = sorted({r[1] for rows in feed.values() for r in rows}, key=str.lower)
    # how many articles each outlet has in „Всички новини“ (the last 7 days), shown in the outlet menu
    front["feed_counts"] = dict(Counter(r[1] for rows in feed.values() for r in rows))

    # the time of this update, in a tiny file: open pages compare it with their own and offer to refresh
    with open(os.path.join(OUT_DIR, "version.json"), "w", encoding="utf-8") as f:
        json.dump({"generated_at": front["generated_at"]}, f)

    # everything except what only „Медии“ shows (the outlet info and the ranking are the biggest part)
    light = {k: v for k, v in front.items() if k not in MEDIA_ONLY}
    # 23 Nov 2026 (David): the front page carries only the stories its first view shows; the rest of the
    # 48 hours go to a file of their own, which the page loads in the background (2.7 MB -> under 1 MB)
    first, rest = split_front_stories(front)
    with open(os.path.join(OUT_DIR, REST_FILE), "w", encoding="utf-8") as f:
        json.dump(rest, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(render({**light, "stories": first, "stories_rest": REST_FILE if rest else None,
                        "hero": hero_data(front)}, template, seo=("", "News Reference – една новина, всички медии",
                                            "Новините от 36 български медии, групирани в истории: кои медии отразиха "
                                            "всяка новина, с какво заглавие и кои я премълчаха.")))

    # the examples behind the headline-change ranking, loaded when someone opens an outlet's row
    _, examples = headline_changes()
    with open(os.path.join(OUT_DIR, "changes.json"), "w", encoding="utf-8") as f:
        json.dump(examples, f, ensure_ascii=False, separators=(",", ":"))

    # the subscription page: same template and data, shown in "support" mode
    with open(os.path.join(OUT_DIR, "abonament.html"), "w", encoding="utf-8") as f:
        f.write(render({**light, "page": "support", "stories": []}, template,
                       seo=("abonament.html", "Подкрепи · News Reference",
                            "Подкрепи News Reference, независимия справочник на българските медии.")))

    # the search page: same template, "search" mode; it needs no stories of its own
    with open(os.path.join(OUT_DIR, "tarsene.html"), "w", encoding="utf-8") as f:
        f.write(render({**light, "page": "search", "stories": []}, template,
                       seo=("tarsene.html", "Търсене · News Reference",
                            "Търси във всички истории и заглавия на 36 български медии от архива на News Reference.")))

    # „Медии“ (9 Nov 2026): its own page; the only page that carries the outlet info and the
    # headline-change ranking, so the front page and the archive pages stay small and fast
    # each outlet's newest articles from the front page's stories (the outlet window lists them)
    recent = {}
    for st in front["stories"]:
        for a in st["articles"]:
            recent.setdefault(a["outlet"], {})[a["link"]] = {k: a[k] for k in ("title", "link", "published")}
    recent = {o: sorted(v.values(), key=lambda a: a["published"], reverse=True)[:6] for o, v in recent.items()}
    # the outlet window on the other pages (12 Nov 2026: a click on an outlet's name opens it in place):
    # the same data as on medii.html, in a file of its own, loaded on the first click
    with open(os.path.join(OUT_DIR, "outlets.json"), "w", encoding="utf-8") as f:
        json.dump({**{k: front[k] for k in ("outlet_info", "outlet_totals", "story_totals")}, "outlet_recent": recent},
                  f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(OUT_DIR, "medii.html"), "w", encoding="utf-8") as f:
        f.write(render({**front, "page": "media", "stories": [], "outlet_recent": recent}, template,
                       seo=("medii.html", "Медии · News Reference",
                            "36 български медии: кой ги притежава, откъде идват парите им, спорове, колко истории "
                            "отразяват и колко често сменят или трият заглавия.")))

    # „Правна информация“ (12 Nov 2026): who runs the site, terms, privacy, cookies, copyright, corrections
    with open(os.path.join(OUT_DIR, "pravila.html"), "w", encoding="utf-8") as f:
        f.write(render({**light, "page": "legal", "stories": []}, template,
                       seo=("pravila.html", "Правна информация · News Reference",
                            "Кой стои зад News Reference, условия, поверителност, авторски права и корекции.")))

    # „Архив“ (9 Nov 2026): its own page with the list of days
    with open(os.path.join(OUT_DIR, "arhiv.html"), "w", encoding="utf-8") as f:
        f.write(render({**light, "page": "archive", "stories": []}, template,
                       seo=("arhiv.html", "Архив · News Reference",
                            "Всички истории по дни: кои български медии отразиха всяка новина и с какво заглавие.")))

    days = front["archive_days"]
    lastmods = {}   # archive page -> when its stories last changed (for sitemap.xml)

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
        when = day_bg(day["date"])
        with open(os.path.join(OUT_DIR, "archive", f"{day['date']}.html"), "w", encoding="utf-8") as f:
            f.write(render(data, template, seo=(f"archive/{day['date']}.html", f"{when} · News Reference",
                                                f"Новините от {when}: кои български медии отразиха всяка история, "
                                                "с какво заглавие и кои я премълчаха.")))
        lastmods[f"archive/{day['date']}.html"] = saved["updated_at"]
    write_sitemap(front["generated_at"], lastmods)

    print(f"Website built: site\\index.html and {len(days)} archive pages in site\\archive\\  "
          "(double-click site\\index.html to open)")


if __name__ == "__main__":
    main()
