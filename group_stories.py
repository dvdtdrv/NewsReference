"""
Group articles about the same event into stories, and note which outlets didn't cover each one.

How the grouping works, in plain words:
  1. Each headline (plus the start of its summary) is turned into a list of the short letter
     sequences it contains ("дер", "ера", "рай"...). Rare sequences count for more than common ones.
     This copes with Bulgarian word endings: "дерайлираха" and "дерайлирали" share most sequences.
  2. Two articles are compared by how many of those sequences they share (a score from 0 to 1).
  3. Articles are joined into a group when, on average, they score above SIMILARITY with the group.
  4. A group becomes a story when at least 2 different outlets are in it.

Reads data/articles.json and data/outlet_status.json (written by collect.py).
Writes data/stories.json (the last 48 hours, for the front page) and saves each story into
data/stories/YYYY-MM-DD.json by the day it started (kept forever, for the archive).

Run with:   python group_stories.py
"""

import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer

from feeds import OUTLETS, UNTRACKED
from versions import all_links, collapse, first_link

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

WINDOW_HOURS = 48     # only group articles from the last 48 hours
SIMILARITY = 0.35     # how alike articles must be to share a story (tested on 31 Oct headlines)
MIN_OUTLETS = 2       # a story needs at least this many different outlets
ACTIVE_HOURS = 3      # an outlet counts as "tracked right now" if we read it in the last 3 hours

FREEZE_HOURS = 36    # a story keeps updating in the archive for 36 h after it starts, then it's final

DATA = "data"
STORY_DAYS_DIR = os.path.join(DATA, "stories")   # one file per day, kept forever
NOW = datetime.now(timezone.utc)

try:
    from zoneinfo import ZoneInfo
    SOFIA = ZoneInfo("Europe/Sofia")             # handles summer/winter time
except Exception:                                # Windows without the tzdata package
    SOFIA = timezone(timedelta(hours=2))


def sofia_day(iso):
    return datetime.fromisoformat(iso).astimezone(SOFIA).date()


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def archive_stories(stories, tracked):
    """Save stories by the day they started, in data/stories/YYYY-MM-DD.json.

    While a story is fresh (started in the last FREEZE_HOURS) each run replaces its saved copy,
    so late articles get added. After that it's left as it is: by then the 48-hour window starts
    cutting off its oldest articles, and we want to keep the complete version."""
    os.makedirs(STORY_DAYS_DIR, exist_ok=True)
    first_time = not any(n.endswith(".json") for n in os.listdir(STORY_DAYS_DIR))
    # on the very first run, save everything we have, including stories older than FREEZE_HOURS
    cutoff = NOW - timedelta(hours=WINDOW_HOURS if first_time else FREEZE_HOURS)

    days = {}   # date -> that day's saved stories, loaded when needed

    def day_list(d):
        if d not in days:
            days[d] = read_json(os.path.join(STORY_DAYS_DIR, f"{d}.json"), {"stories": []})["stories"]
        return days[d]

    saved = 0
    for s in stories:
        if datetime.fromisoformat(s["first_seen"]) < cutoff:
            continue
        links = {l for a in s["articles"] for l in all_links(a)}
        s = dict(s)
        # find the saved copy of this story (it may sit on a neighbouring day) and merge with it:
        # the window may have cut the story's oldest articles, and the archive must keep them
        start = sofia_day(s["first_seen"])
        for d in (start - timedelta(days=1), start, start + timedelta(days=1)):
            kept = []
            for old in day_list(d):
                old_links = {l for a in old["articles"] for l in all_links(a)}
                if len(links & old_links) >= 0.5 * min(len(s["articles"]), len(old["articles"])):
                    extra = [a for a in old["articles"] if a["link"] not in links]
                    if extra:
                        # an old copy of an article the outlet has since renamed merges into the new one
                        arts = collapse(s["articles"] + extra, prefer={a["link"] for a in s["articles"]})
                        arts = sorted(arts, key=lambda a: a["published"])
                        outlets = list(dict.fromkeys(a["outlet"] for a in arts))
                        s.update(articles=arts, outlets=outlets, outlet_count=len(outlets),
                                 first_seen=arts[0]["published"], last_updated=arts[-1]["published"],
                                 not_covered=[o for o in s["not_covered"] if o not in outlets])
                        links |= {l for a in extra for l in all_links(a)}
                    continue   # the merged version is saved below
                kept.append(old)
            days[d] = kept
        day_list(sofia_day(s["first_seen"])).append(s)
        saved += 1

    for d, items in days.items():
        path = os.path.join(STORY_DAYS_DIR, f"{d}.json")
        if not items and not os.path.exists(path):
            continue
        items.sort(key=lambda s: (s["outlet_count"], s["last_updated"]), reverse=True)
        write_json(path, {"date": str(d), "updated_at": NOW.isoformat(),
                          "tracked_outlets": tracked, "stories": items})
    total_days = sum(1 for n in os.listdir(STORY_DAYS_DIR) if n.endswith(".json"))
    return saved, total_days


def clean_saved_versions():
    """Once: merge renamed articles inside every saved story (added 5 Nov 2026, see versions.py).
    Later runs keep stories clean as they save them; this fixes the days saved before."""
    marker = os.path.join(DATA, "versions_cleaned.json")
    if os.path.exists(marker) or not os.path.isdir(STORY_DAYS_DIR):
        return 0
    # the monthly archive (collect.py ran first) already knows which version of each article is
    # the newest; use it, so a story shows the outlet's latest headline
    latest = {}
    months = os.path.join(DATA, "articles")
    for name in (os.listdir(months) if os.path.isdir(months) else []):
        if name.endswith(".json"):
            for a in read_json(os.path.join(months, name), []):
                for link in all_links(a):
                    latest[link] = a
    merged = 0
    for name in sorted(os.listdir(STORY_DAYS_DIR)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(STORY_DAYS_DIR, name)
        day = read_json(path, {"stories": []})
        changed = False
        for st in day["stories"]:
            arts, touched = [], False
            for a in st["articles"]:
                m = latest.get(a["link"])
                if m is not None and (m["link"] != a["link"] or (m.get("versions") and not a.get("versions"))):
                    a = {**a, "title": m["title"], "link": m["link"], "image": m.get("image") or a.get("image", ""),
                         "versions": m.get("versions", [])}
                    touched = True
                arts.append(a)
            arts = collapse(arts)
            if touched or len(arts) < len(st["articles"]):
                merged += len(st["articles"]) - len(arts)
                st["articles"] = sorted(arts, key=lambda a: a["published"])
                changed = True
        if changed:
            write_json(path, day)
    write_json(marker, {"done": NOW.isoformat(), "merged_articles": merged})
    return merged


def load(name, default):
    try:
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def clean_headline(title):
    """A calmer story title: drop media tags like (ВИДЕО), tone down shouting."""
    t = re.sub(r"\s*[\(\[][^)\]]*(видео|снимк|галерия|на живо|обновена|карта)[^)\]]*[\)\]]", "",
               title, flags=re.I)
    t = re.sub(r"!+", ".", t).strip(" .")
    return re.sub(r"\s+", " ", t)


def text_for(a):
    # the headline counts twice: it says what the story is; the summary adds detail
    return f"{a['title']} . {a['title']} . {(a.get('summary') or '')[:150]}".lower()


def main():
    articles = load("articles.json", [])
    status = {s["outlet"]: s for s in load("outlet_status.json", [])}
    start = NOW - timedelta(hours=WINDOW_HOURS)
    recent = [a for a in articles if datetime.fromisoformat(a["published"]) >= start]
    if len(recent) < 2:
        print("Not enough recent articles to group. Run collect.py first.")
        return

    # 1-2. compare every article with every other one
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=2)
    X = vectorizer.fit_transform([text_for(a) for a in recent])
    similarity = (X @ X.T).toarray()

    # 3. join articles into groups
    labels = AgglomerativeClustering(
        n_clusters=None, metric="precomputed", linkage="average",
        distance_threshold=1 - SIMILARITY,
    ).fit(1 - similarity).labels_
    groups = defaultdict(list)
    for i, label in enumerate(labels):
        groups[label].append(i)

    # which outlets can fairly be called "didn't cover it": read recently, and
    # our archive for them reaches back to before the story started
    covered_since = {}
    for a in articles:
        t = a["published"]
        if a["outlet"] not in covered_since or t < covered_since[a["outlet"]]:
            covered_since[a["outlet"]] = t
    # an outlet counts as tracked right now if we read it recently AND it gave us current articles
    # (PIK's feed answers, but with articles from two weeks ago)
    in_window = {a["outlet"] for a in recent}
    active = {name for name, s in status.items()
              if name in in_window and s.get("last_ok")
              and datetime.fromisoformat(s["last_ok"]) >= NOW - timedelta(hours=ACTIVE_HOURS)}

    # 4. turn groups into stories
    stories = []
    for members in groups.values():
        items = sorted((recent[i] for i in members), key=lambda a: a["published"])
        outlets = list(dict.fromkeys(a["outlet"] for a in items))  # in order of who reported first
        if len(outlets) < MIN_OUTLETS:
            continue
        # the headline that best represents the group = the one most similar to the others,
        # preferring calm headlines (no ALL-CAPS words, no "!")
        sub = similarity[np.ix_(members, members)]
        score = sub.mean(axis=1)
        for k, i in enumerate(members):
            t = recent[i]["title"]
            if "!" in t or re.search(r"\b[А-ЯA-Z]{4,}\b", t):
                score[k] -= 0.05
        central = recent[members[int(score.argmax())]]
        first_seen = items[0]["published"]
        not_covered = [o["name"] for o in OUTLETS
                       if o["name"] not in outlets and o["name"] in active
                       and covered_since.get(o["name"], "9999") <= first_seen]
        stories.append({
            # the id stays the same when the first article is renamed (its first link is kept)
            "id": hashlib.sha1(first_link(items[0]).encode()).hexdigest()[:10],
            "headline": clean_headline(central["title"]),
            "headline_source": "selected",   # picked from the outlets' headlines; "ai" once AI summaries exist
            "first_seen": first_seen,
            "last_updated": items[-1]["published"],
            "outlet_count": len(outlets),
            "outlets": outlets,
            "not_covered": not_covered,
            "articles": [{**{k: a.get(k, "") for k in ("outlet", "title", "link", "published", "image")},
                          **({"versions": a["versions"]} if a.get("versions") else {})}
                         for a in items],
        })

    stories.sort(key=lambda s: (s["outlet_count"], s["last_updated"]), reverse=True)
    result = {
        "generated_at": NOW.isoformat(),
        "window_hours": WINDOW_HOURS,
        "articles_in_window": len(recent),
        "tracked_outlets": [{"name": o["name"], "type": o["type"],
                             "active": o["name"] in active} for o in OUTLETS],
        "untracked_outlets": UNTRACKED,
        "stories": stories,
    }
    tmp = os.path.join(DATA, "stories.json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(DATA, "stories.json"))
    cleaned = clean_saved_versions()
    if cleaned:
        print(f"Archive: merged {cleaned} renamed articles in saved stories.")
    saved, total_days = archive_stories(stories, result["tracked_outlets"])

    print(f"Story archive (data\\stories\\): {saved} fresh stories saved; {total_days} days kept.")
    print(f"{len(recent)} articles from the last {WINDOW_HOURS} h -> {len(stories)} stories "
          f"covered by {MIN_OUTLETS}+ outlets.\n\nTop stories:")
    for s in stories[:10]:
        print(f"  {s['outlet_count']:>2} outlets  {s['headline'][:80]}")
        if s["not_covered"]:
            print(f"             not covered by: {', '.join(s['not_covered'])}")


if __name__ == "__main__":
    main()
