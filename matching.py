"""
Joining stories that are really one event (added 10 Nov 2026).

Why: group_stories.py compares WORDING (shared letter chunks). A breaking story changes its wording
during the day ("верижна катастрофа с 50 коли" -> "11 загинали и 48 ранени"), so on 10 Nov 2026 the
crash on Trakia motorway was shown as about 25 separate stories.

What this file does, after the normal grouping: two stories become one only when ALL of these hold
  1. their MEANING is very close (a small AI model turns each article into a "meaning fingerprint";
     the stories' average fingerprints must score >= MEANING, 0.70);
  2. their wording is at least somewhat alike (>= WORDING, 0.30);
  3. they started within START_GAP_HOURS (12 h) of each other, and the joined story's parts all
     start within SPAN_HOURS (24 h);
  4. they share a specific name or place (not one found in very many stories), and they do not name
     different Bulgarian towns/villages (places.json: the official EKATTE list of settlements);
  5. weather forecasts are joined only with another forecast for the same day (the day is read from
     the headlines: "7 ноември", "в неделя", "утре"); forecasts that name no day are left alone.
     Motorways (Тракия, Хемус, Струма...) count as places, so different roads are never joined.

Tested on 5-10 Nov 2026 (2197 stories): 75 joins, e.g. the Trakia crash (12 parts), the death of
Vezhdi Rashidov (13), the Krakow shooting (8). A join that is missed only leaves a duplicate; a wrong
join gives wrong outlet counts, so the rule is strict on purpose.

If the AI model can't be loaded (no internet, library missing - e.g. on David's PC), nothing is
joined and the stories stay exactly as group_stories.py made them.

The model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (free, runs on GitHub's
computer, ~470 MB download kept in GitHub's cache). Fingerprints are saved in data/embeddings.json,
so each article is processed once. Every join is written to data/merge_log.json (last 14 days).
"""

import base64
import json
import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MEANING = 0.70           # how close the meaning must be (0-1)
WORDING = 0.30           # how close the wording must be (0-1)
START_GAP_HOURS = 12     # two stories must have started within this many hours
SPAN_HOURS = 24          # all parts of a joined story must have started within this many hours
COMMON_NAME = 40         # a name found in more stories than this says little about which event it is
LOG_DAYS = 14

HERE = os.path.dirname(os.path.abspath(__file__))
WORD = re.compile(r"[\w-]+")
CAP = re.compile(r"[А-ЯA-Z][а-яa-z]{2,}$")
NOT_NAMES = {"нова", "бтв", "бнт", "бнр", "бта", "снимки", "видео", "обновена", "обновява", "ето", "още",
             "софия", "българия", "български", "българска", "българско", "българските"}
BIG_PLACES = {"София", "България"}     # mentioned in passing in too many unrelated stories
# motorways and passes count as places too: a story about "Хемус" is not joined to one about "Тракия"
ROADS = {"Тракия", "Хемус", "Струма", "Петрохан", "Витиня"}
WEATHER = re.compile(r"времето|прогноза|слънчев|мъгл|облачн|валеж|температур|градуса|застудява|затопля", re.I)
NOT_WEATHER = re.compile(r"катастроф|загин", re.I)   # "fog caused a crash" is not a forecast


def load_places():
    try:
        with open(os.path.join(HERE, "places.json"), encoding="utf-8") as f:
            return (set(json.load(f)) | ROADS) - BIG_PLACES
    except FileNotFoundError:
        return set(ROADS)


def names_in(text, places):
    """(Bulgarian places, other names) in a headline; other names are cut to 6 letters,
    so "Радев" and "Радева" count as the same name."""
    words = WORD.findall(text)
    found_places, found_names = set(), set()
    for k, w in enumerate(words):
        if w in places:
            found_places.add(w)
        elif k > 0 and CAP.match(w) and w.lower() not in NOT_NAMES:
            found_names.add(w.lower()[:6])
    return found_places, found_names


MONTHS = {m: k + 1 for k, m in enumerate(
    ["януари", "февруари", "март", "април", "май", "юни", "юли", "август", "септември", "октомври", "ноември", "декември"])}
WEEKDAYS = {"понеделник": 0, "вторник": 1, "сряда": 2, "четвъртък": 3, "петък": 4, "събота": 5, "неделя": 6}
DATE = re.compile(r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")\b", re.I)
DAY_WORD = re.compile(r"\b(" + "|".join(WEEKDAYS) + r")\b", re.I)
try:
    from zoneinfo import ZoneInfo
    SOFIA = ZoneInfo("Europe/Sofia")
except Exception:
    SOFIA = timezone(timedelta(hours=2))


def forecast_day(title, published):
    """The day a weather headline is about ("7 ноември", "в неделя", "утре", "днес"), or None."""
    day = datetime.fromisoformat(published).astimezone(SOFIA).date()
    low = title.lower()
    m = DATE.search(low)
    if m:
        try:
            return day.replace(month=MONTHS[m.group(2)], day=int(m.group(1)))
        except ValueError:
            return None
    m = DAY_WORD.search(low)
    if m:
        return day + timedelta(days=(WEEKDAYS[m.group(1)] - day.weekday()) % 7)
    if "утре" in low:
        return day + timedelta(days=1)
    if "днес" in low or "тази сутрин" in low:
        return day
    return None


def fingerprints(stories, cache_path):
    """Meaning fingerprint of every article (by link). Old ones come from the cache file."""
    try:
        with open(cache_path, encoding="utf-8") as f:
            cache = json.load(f)
    except (FileNotFoundError, ValueError):
        cache = {}
    wanted = {a["link"]: a["title"] for s in stories for a in s["articles"]}
    # a renamed headline gets a new fingerprint
    missing = [l for l, t in wanted.items() if l not in cache or cache[l].get("t") != t]
    if missing:
        from sentence_transformers import SentenceTransformer   # heavy: only loaded when needed
        model = SentenceTransformer(MODEL)
        vectors = model.encode([wanted[l] for l in missing], batch_size=64,
                               normalize_embeddings=True, show_progress_bar=False)
        for l, v in zip(missing, vectors):
            cache[l] = {"t": wanted[l], "v": base64.b64encode(v.astype(np.float16).tobytes()).decode()}
    cache = {l: cache[l] for l in wanted}            # keep only what is still on the front page
    tmp = cache_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    os.replace(tmp, cache_path)
    return {l: np.frombuffer(base64.b64decode(c["v"]), dtype=np.float16).astype(np.float32)
            for l, c in cache.items()}, len(missing)


def find_joins(stories, vec):
    """Which stories to join -> (list of groups of story numbers, list of log lines)."""
    places = load_places()
    n = len(stories)
    centre = []
    for s in stories:
        v = np.mean([vec[a["link"]] for a in s["articles"]], axis=0)
        centre.append(v / (np.linalg.norm(v) or 1))
    meaning = np.array(centre) @ np.array(centre).T
    texts = [" ".join(a["title"] for a in s["articles"]).lower() for s in stories]
    X = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True,
                        min_df=2 if n > 1 else 1).fit_transform(texts)
    wording = (X @ X.T).toarray()

    story_places, story_names, forecast, about = [], [], [], []
    for s in stories:
        pc, nc = Counter(), Counter()
        for a in s["articles"]:
            p, nm = names_in(a["title"], places)
            pc.update(p); nc.update(nm)
        need = max(1, len(s["articles"]) // 4)   # a name counts if a quarter of the articles have it
        story_places.append({p for p, c in pc.items() if c >= need})
        story_names.append({x for x, c in nc.items() if c >= need})
        w = sum(bool(WEATHER.search(a["title"])) for a in s["articles"])
        forecast.append(w * 2 >= len(s["articles"]) and not NOT_WEATHER.search(s["headline"]))
        # the day a forecast is about: the one most of its headlines name (None if they name no day)
        days = Counter(d for d in (forecast_day(a["title"], a["published"]) for a in s["articles"]) if d)
        top = days.most_common(1)
        about.append(top[0][0] if forecast[-1] and top and top[0][1] * 2 >= len(s["articles"]) else None)
    in_stories = Counter(x for names in story_names for x in names)
    start = [datetime.fromisoformat(s["first_seen"]).timestamp() for s in stories]

    candidates = []
    for i in range(n):
        for j in range(i + 1, n):
            if meaning[i, j] < MEANING or wording[i, j] < WORDING:
                continue
            if abs(start[i] - start[j]) > START_GAP_HOURS * 3600:
                continue
            if forecast[i] or forecast[j]:
                # weather forecasts: joined only with another forecast for the same day
                if forecast[i] and forecast[j] and about[i] and about[i] == about[j]:
                    candidates.append((float(meaning[i, j] + wording[i, j]), i, j, [f"прогноза за {about[i]}"]))
                continue
            if story_places[i] and story_places[j] and not (story_places[i] & story_places[j]):
                continue                         # they name different towns/villages
            shared = ({x for x in story_names[i] & story_names[j] if in_stories[x] <= COMMON_NAME}
                      | (story_places[i] & story_places[j]))
            if shared:
                candidates.append((float(meaning[i, j] + wording[i, j]), i, j, sorted(shared)[:4]))

    parent = list(range(n))
    lo, hi = list(start), list(start)

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    log = []
    for score, i, j, shared in sorted(candidates, key=lambda c: -c[0]):     # the surest pairs first
        a, b = root(i), root(j)
        if a == b or max(hi[a], hi[b]) - min(lo[a], lo[b]) > SPAN_HOURS * 3600:
            continue
        parent[b] = a
        lo[a], hi[a] = min(lo[a], lo[b]), max(hi[a], hi[b])
        log.append({"a": stories[i]["headline"], "b": stories[j]["headline"], "shared": shared,
                    "meaning": round(float(meaning[i, j]), 2), "wording": round(float(wording[i, j]), 2)})
    groups = {}
    for i in range(n):
        groups.setdefault(root(i), []).append(i)
    return [g for g in groups.values() if len(g) > 1], log


def join_stories(stories, data_dir, now=None):
    """The stories with those about one event joined. On any problem: the stories unchanged."""
    now = now or datetime.now(timezone.utc)
    if len(stories) < 2:
        return stories, "nothing to join"
    try:
        vec, new = fingerprints(stories, os.path.join(data_dir, "embeddings.json"))
        groups, log = find_joins(stories, vec)
    except Exception as e:                       # never let this step stop the site from updating
        return stories, f"skipped ({type(e).__name__}: {str(e)[:120]})"

    gone, joined = set(), []
    for g in groups:
        parts = [stories[i] for i in g]
        main = max(parts, key=lambda s: (s["outlet_count"], len(s["articles"])))
        first = min(parts, key=lambda s: s["first_seen"])
        seen, articles = set(), []
        for a in sorted((a for s in parts for a in s["articles"]), key=lambda a: a["published"]):
            if a["link"] not in seen:
                seen.add(a["link"]); articles.append(a)
        outlets = list(dict.fromkeys(a["outlet"] for a in articles))
        # "didn't cover" is judged at the start of the story, as for every story
        not_covered = [o for o in first["not_covered"] if o not in outlets]
        joined.append({**main, "id": first["id"], "articles": articles, "outlets": outlets,
                       "outlet_count": len(outlets), "not_covered": not_covered,
                       "first_seen": articles[0]["published"], "last_updated": articles[-1]["published"]})
        gone.update(g)
    result = [s for i, s in enumerate(stories) if i not in gone] + joined

    log_path = os.path.join(data_dir, "merge_log.json")
    try:
        with open(log_path, encoding="utf-8") as f:
            old = json.load(f)
    except (FileNotFoundError, ValueError):
        old = []
    keep_from = (now - timedelta(days=LOG_DAYS)).isoformat()
    known = {(e["a"], e["b"]) for e in old}
    old = [e for e in old if e.get("at", "") >= keep_from]
    old += [{"at": now.isoformat(), **e} for e in log if (e["a"], e["b"]) not in known]
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(old, f, ensure_ascii=False, indent=1)
    return result, f"{len(stories)} stories -> {len(result)} ({len(joined)} joined; {new} new fingerprints)"
