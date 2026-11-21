"""
Are the articles we collected still online? (added 5 Nov 2026)

An outlet that deletes an article is worth knowing about, so every collected article's link is
opened again a few times: about 1, 3, 7, 14 and 30 days after it was published. We read only the
answer's status (the page itself is not downloaded), respect robots.txt and each site's pause
between requests, and skip sites that refuse us anyway (BTA: permission covers the feed only;
Dnevnik and Capital: their pages refuse us).

An article counts as deleted ("gone") only if its link answers "no such page" (404 or 410), or
sends us to the site's front page or a section page, on TWO checks in a row - so a site that is
briefly down never counts. If it comes back later, it is marked "restored".
But if the page still shows the article's own headline, it is NOT deleted, whatever else the page
says (6 Nov 2026: 8 of the first 25 "deleted" were alive - Sega names a shorter address as its own,
Offnews moved a link, a Darik headline contained "не съществува").

The answers live in data/deleted.json: {link: {"outlet", "stage", "strikes", "last", "gone"?, "restored"?}}.
Outlets that refuse GitHub ("local" in feeds.py) are checked on David's PC: GitHub writes their due
links to data/link_check_local.json, fetch_local.py checks them and sends the answers back.
"""

import html
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from urllib.parse import urlparse

import requests

import headline_watch
from limits import within

STATE_FILE = os.path.join("data", "deleted.json")
LOCAL_TODO_FILE = os.path.join("data", "link_check_local.json")
# Links to look at again now, outside the schedule (in the repo, written by hand, e.g. after headline_audit.py
# found a headline that differs from ours): {"made": time, "why": ..., "links": [...]}. Each link is due once
# (until it has been checked after "made"); a different headline then goes through the normal two looks.
RECHECK_FILE = "recheck.json"
LOCAL_TODO_URL = "https://raw.githubusercontent.com/dvdtdrv/NewsReference/data/link_check_local.json"
# 21 Nov 2026: hours, not days, and three early visits: each visit also reads the page's headline
# (headline_watch.py), and headlines change mostly in the first day or two
SCHEDULE_HOURS = (3, 12, 36, 72, 168, 336, 720)
SCHEDULE_DAYS = (1, 3, 7, 14, 30)    # the old schedule, only to convert saved stages (see run)
SCHEDULE_VERSION = 2
PER_OUTLET = 60                      # at most this many checks per outlet per run (runs are every 30 min)
SECONDS = 4 * 60                     # at most this long per run; all outlets are checked side by side
PC_PER_OUTLET = 40                   # links per outlet in the PC's to-do list (150 until 21 Nov 2026, see PC_PAUSE)
# Pauses between two pages of ONE outlet (at least; robots.txt crawl-delay wins if longer). 21 Nov 2026: BG On Air's
# firewall blocked David's home connection ("403 Request forbidden by administrative rules", the whole site, also in his
# browser) after the PC opened ~230 of its pages in two rounds, one every ~1.6 s. The PC is a home connection: be gentle.
PC_PAUSE = 5
GITHUB_PAUSE = 2
GIVE_UP = 3                          # stop an outlet for this run after this many "can't tell" answers in a row
RECHECK_HOURS = 6                    # after a first "no such page", ask again this much later
TIMEOUT = 15
PROBE_SECONDS = 40                   # the most one check may take in total
RULES = 2                            # bump when the rules for "gone" change: re-check what was marked gone


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def checkable(outlet):
    return not (outlet.get("gentle") or outlet.get("page_images") is False)


def stage_for(published, now):
    """How many of the SCHEDULE_HOURS have passed since the article was published."""
    age = (now - datetime.fromisoformat(published)).total_seconds() / 3600
    return sum(1 for h in SCHEDULE_HOURS if age >= h)


def _recheck_list():
    try:
        with open(RECHECK_FILE, encoding="utf-8") as f:
            r = json.load(f)
        return r.get("made", ""), set(r.get("links", []))
    except (OSError, ValueError):
        return "", set()


RECHECK_MADE, RECHECK_LINKS = _recheck_list()


def is_due(entry, published, now, link=None):
    if link in RECHECK_LINKS and (entry or {}).get("last", "") < RECHECK_MADE:
        return True       # asked for by hand (recheck.json)
    soon = entry and (entry.get("soon_at") or entry.get("pending_at"))
    if soon and now - datetime.fromisoformat(soon) >= timedelta(minutes=headline_watch.RECHECK_MINUTES):
        return True       # the headline just changed: look again on the next run (did it change back?)
    if entry and entry.get("strikes"):
        last = datetime.fromisoformat(entry["last"])
        return now - last >= timedelta(hours=RECHECK_HOURS)
    return stage_for(published, now) > (entry or {}).get("stage", 0)


def _old_stage_to_new(stage):
    """A stage counted on the old day schedule -> the same moment on the hour schedule."""
    if not stage:
        return 0
    hours = SCHEDULE_DAYS[min(stage, len(SCHEDULE_DAYS)) - 1] * 24
    return sum(1 for h in SCHEDULE_HOURS if h <= hours)


def _priority(a, state):
    """Order of the checks inside one outlet: second looks after a headline change (to confirm it) first, then articles
    younger than 4 days (headlines change early), oldest first within each group."""
    e = state.get(a["link"]) or {}
    young = (datetime.now(timezone.utc) - datetime.fromisoformat(a["published"])) < timedelta(days=4)
    first = e.get("soon_at") or e.get("pending_at") or (a["link"] in RECHECK_LINKS and e.get("last", "") < RECHECK_MADE)
    return (0 if first else 1 if young else 2, a["published"])


HEAD_BYTES = 400_000
NOT_FOUND = re.compile(r"\b404\b|не е намерен|не беше намерен|не съществува|не може да бъде намерен|"
                       r"няма такава страница|страницата не|page not found|not found", re.I)
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
OG_TITLE = re.compile(r"""<meta[^>]+property=["']og:title["'][^>]*content=["']([^"']*)["']""", re.I)
CANONICAL = re.compile(r"""<(?:link[^>]+rel=["']canonical["'][^>]*href|meta[^>]+property=["']og:url["'][^>]*content)=["']([^"']*)["']""", re.I)


def _front(url):
    return urlparse(url).path in ("", "/")


def _depth(url):
    return len([p for p in urlparse(url).path.split("/") if p])


def _plain(t):
    return re.sub(r"[^\w]+", " ", (t or "").lower()).strip()


def shows_headline(page_title, headlines):
    """True if the page's title is (one of) the article's own headline(s): then the article is there.
    Page titles often add the site's name ("... - Новини СЕГА"), so we compare the beginning."""
    page = _plain(page_title)
    for h in headlines or []:
        h = _plain(h)
        if len(h) < 12:
            continue
        if h in page or page[:len(h)] == h or SequenceMatcher(None, h, page[:len(h) + 10]).ratio() >= 0.75:
            return True
    return False


def headlines_of(a):
    """The headline we stored plus the earlier ones (an outlet may have renamed it)."""
    return [a.get("title")] + [v.get("title") for v in a.get("versions", [])]


def probe(link, headers, headlines=None):
    """_probe with a hard limit of PROBE_SECONDS in total (see limits.py): a stuck page counts as "can't tell".
    Returns (result, parts): parts = the page's own headline candidates (headline_watch.page_parts) or {}."""
    try:
        out = within(PROBE_SECONDS, _probe, link, headers, headlines)
    except requests.RequestException:
        return None, {}
    return out if isinstance(out, tuple) else (out, {})


def _probe(link, headers, headlines=None):
    """'ok', 'gone', or None if we couldn't tell (refused, timeout, server error).
    Rule 1 (6 Nov 2026): if the page shows the article's own headline, the article is there - whatever
    else the page says (Sega names a shorter address as its own, a Darik headline said "не съществува").
    Gone = "no such page" (404/410), or a redirect to the front page, or a page that says so itself
    (some sites answer 200 with a "404" page: Novini.bg), or a page that names the front page as its
    own address (og:url / canonical). Only the top of the page is read."""
    try:
        with requests.get(link, headers=headers, timeout=TIMEOUT, stream=True, allow_redirects=True) as r:
            status, final = r.status_code, r.url
            raw = b""
            if status == 200:
                for chunk in r.iter_content(16384):
                    raw += chunk
                    if len(raw) > HEAD_BYTES:
                        break
                    # stop once the page's title and its own address have both passed (not at the first
                    # "</head>": Novini.bg has an early fake one)
                    # and (21 Nov 2026) the page's visible headline <h1>, for headline_watch.py
                    low = raw.lower()
                    if (b"</title>" in low and (b"og:url" in low or b'rel="canonical"' in low) and b"<body" in low
                            and b"</h1>" in low):
                        break
            enc = r.encoding if r.encoding and r.encoding.lower() not in ("iso-8859-1", "latin-1") else ""
            if not enc:       # no charset from the server: the page's own <meta charset> (Moreto.net: windows-1251)
                m = re.search(rb"""charset\s*=\s*["']?([A-Za-z0-9_-]+)""", raw[:8000])
                enc = m.group(1).decode("ascii", "ignore") if m else "utf-8"
            try:
                "".encode(enc)
            except LookupError:
                enc = "utf-8"
    except requests.RequestException:
        return None
    if status in (404, 410):
        return "gone"
    if status != 200:
        return None
    if "challenge" in urlparse(final).path:
        return None       # a robot check page (Moreto.net): we can't tell
    head = raw.decode(enc, errors="replace")
    return _judge(head, link, final, headlines), headline_watch.page_parts(head)


def _judge(head, link, final, headlines):
    t = TITLE.search(head)
    title = html.unescape(re.sub(r"\s+", " ", t.group(1))).strip() if t else ""
    og = OG_TITLE.search(head)
    og_title = html.unescape(og.group(1)).strip() if og else ""
    if shows_headline(title, headlines) or shows_headline(og_title, headlines):
        return "ok"       # the article's own headline is on the page
    if _front(final) and not _front(link):
        return "gone"     # sent to the front page: the article isn't there any more
    if _depth(final) < _depth(link):
        return "gone"     # sent up to a section page (Sega, Vesti.bg): the article isn't there any more
    if title and NOT_FOUND.search(title):
        return "gone"
    c = CANONICAL.search(head)
    if c and c.group(1).startswith("http") and not _front(link):
        if _front(c.group(1)) or _depth(c.group(1)) < _depth(link):
            return "gone"     # the page calls itself the front page or a section page (Novini.bg, Sega)
    return "ok"


def apply(state, link, outlet, result, now, published):
    e = state.setdefault(link, {"outlet": outlet, "stage": 0, "strikes": 0})
    e["last"] = now.isoformat()
    if result == "ok":
        e["strikes"] = 0
        e["stage"] = stage_for(published, now)
        if e.pop("gone", None):
            e["restored"] = now.isoformat()
    elif result == "gone":
        e["strikes"] = e.get("strikes", 0) + 1
        if e["strikes"] >= 2:
            e.setdefault("gone", now.isoformat())
            e["stage"] = stage_for(published, now)
            e["strikes"] = 0


def due_articles(outlets, months_dir, state, now, local):
    """{outlet: [articles due for a check]} for outlets on GitHub (local=False) or the PC (local=True).
    Outlets whose article pages refuse GitHub (photos_on_pc: Euronews BG, BG On Air) are checked on the PC too
    (21 Nov 2026); before, GitHub got "refused" for them every time and could never tell."""
    names = {o["name"]: o for o in outlets
             if checkable(o) and bool(o.get("local") or o.get("photos_on_pc")) == local}
    oldest = now - timedelta(days=SCHEDULE_DAYS[-1] + 1)
    due = {}
    for name in sorted(os.listdir(months_dir)) if os.path.isdir(months_dir) else []:
        if not name.endswith(".json") or name[:7] < oldest.strftime("%Y-%m"):
            continue
        for a in _load(os.path.join(months_dir, name), []):
            if a.get("outlet") not in names or not a.get("link") or not a.get("published"):
                continue
            if datetime.fromisoformat(a["published"]) < oldest:
                continue
            e = state.get(a["link"])
            if is_due(e, a["published"], now, a["link"]):
                due.setdefault(a["outlet"], []).append(a)
    for items in due.values():
        items.sort(key=lambda a: a["published"])     # the oldest first: they are the most overdue
    return due


def run(outlets, months_dir, now, allowed, crawl_delay, headers_for, local=None, archive=None):
    """Check due links on this machine and apply answers the PC sent (local = its local_articles.json).
    New headlines seen on the pages (headline_watch.py) are recorded in `archive` (the last 7 days, saved
    by collect.py afterwards) and in the monthly files. Returns (checked, newly gone, headlines changed)."""
    state = _load(STATE_FILE, {})
    meta = state.pop("_meta", {})
    gone_before = sum(1 for e in state.values() if e.get("gone"))
    if meta.get("schedule", 1) < SCHEDULE_VERSION:      # 21 Nov 2026: days -> hours, same moments kept
        for e in state.values():
            e["stage"] = _old_stage_to_new(e.get("stage", 0))
        meta["schedule"] = SCHEDULE_VERSION
    known = _known_headlines(months_dir, now)
    renames = {}

    # 0. (6 Nov 2026) the rules changed: everything marked "gone" so far is checked again from scratch
    if meta.get("rules", 1) < RULES:
        for e in state.values():
            if e.get("gone"):
                e.pop("gone")
                e["strikes"], e["stage"] = 0, 0
        meta["rules"] = RULES

    # 1. answers from David's PC for the outlets that refuse GitHub (each batch only once:
    #    two GitHub runs can pick up the same file, and one "no such page" must not count twice)
    if local and local.get("link_checks") and local.get("fetched_at") != meta.get("pc_batch"):
        for link, item in local["link_checks"].items():
            apply(state, link, item.get("outlet"), item.get("result"), now, item.get("published"))
            new = _headline(state, link, item.get("result"), item.get("page") or {}, known.get(link), now)
            if new:
                renames[link] = new
        meta["pc_batch"] = local.get("fetched_at")

    # 2. our own checks
    due = due_articles(outlets, months_dir, state, now, local=False)
    by_name = {o["name"]: o for o in outlets}
    deadline = time.monotonic() + SECONDS
    results = []

    def work(name):
        headers = headers_for(by_name[name])
        done = refused = 0
        for a in due[name]:
            if done >= PER_OUTLET or time.monotonic() > deadline or refused >= GIVE_UP:
                break             # (refused: the site stopped answering us - don't keep knocking)
            if not allowed(a["link"]):
                continue
            answer = probe(a["link"], headers, headlines_of(a))
            results.append((a, answer))
            refused = refused + 1 if answer[0] is None else 0
            done += 1
            time.sleep(max(GITHUB_PAUSE, crawl_delay(a["link"])))
        return done

    for items in due.values():
        items.sort(key=lambda a: _priority(a, state))
    # every outlet side by side (each still one request at a time, with its pause): with 12 at a time the
    # outlets late in the list (Nova, Vesti.bg, Darik) ran out of time every run and fell 1000+ checks behind
    with ThreadPoolExecutor(max_workers=max(1, len(due))) as pool:
        checked = sum(pool.map(work, list(due)))
    for a, (result, parts) in results:
        apply(state, a["link"], a["outlet"], result, now, a["published"])
        new = _headline(state, a["link"], result, parts, known.get(a["link"]) or headlines_of(a), now)
        if new:
            renames[a["link"]] = new
    renamed = _record_renames(renames, months_dir, archive, now)

    # 3. tell the PC which links of its outlets are due
    local_due = due_articles(outlets, months_dir, state, now, local=True)
    for items in local_due.values():
        items.sort(key=lambda a: _priority(a, state))
    _save(LOCAL_TODO_FILE, {"made": now.isoformat(), "links": [
        {"link": a["link"], "outlet": a["outlet"], "published": a["published"], "titles": headlines_of(a)}
        for items in local_due.values() for a in items[:PC_PER_OUTLET]]})

    # forget checks of articles older than the schedule, unless they were deleted
    limit = (now - timedelta(hours=SCHEDULE_HOURS[-1] + 48)).isoformat()
    state = {k: e for k, e in state.items() if e.get("gone") or e.get("restored") or e.get("last", "") >= limit}
    state["_meta"] = meta
    _save(STATE_FILE, state)
    state.pop("_meta")
    gone_now = sum(1 for e in state.values() if e.get("gone"))
    return checked, gone_now - gone_before, renamed


def _known_headlines(months_dir, now):
    """{link: [headline, earlier headlines...]} for the articles still on the schedule (any of their links)."""
    oldest = now - timedelta(hours=SCHEDULE_HOURS[-1] + 24)
    out = {}
    for name in sorted(os.listdir(months_dir)) if os.path.isdir(months_dir) else []:
        if name.endswith(".json") and name[:7] >= oldest.strftime("%Y-%m"):
            for a in _load(os.path.join(months_dir, name), []):
                if a.get("link"):
                    out[a["link"]] = headlines_of(a)
    return out


def _headline(state, link, result, parts, known, now):
    """headline_watch for one visit: returns (headline, back) once a different headline is CONFIRMED, else None.
    back=True: it is one of the article's EARLIER headlines again (a change back).

    21 Nov 2026 (David: precise beats fast - better not to count a mistake and correct it later): a different
    headline counts only if the page still shows it on the next look. The next look comes on the next run
    (soon_at, RECHECK_MINUTES: ~30 min, ~1 h for the PC outlets), not 3 h later as in the first version.
    Seen once and then gone again = not counted (a cache, a page variant, an error). After a confirmed change the
    article is looked at again on the next run too, so a quick change back is caught (and also needs two looks)."""
    e = state.get(link)
    if e is None or result != "ok" or not parts or not known:
        return None
    e.pop("soon_at", None)
    known = [k for k in known if k]
    new = headline_watch.judge(parts, known)
    # a change back counts only if the headline we hold is one we saw on the page ourselves ("page_title"):
    # a rename seen in a feed can have its two headlines in the wrong order (test 21 Nov: Vesti.bg), and the
    # page showing the "older" one then is not a change back
    back = None
    if not new and known and headline_watch.same(e.get("page_title"), known[0]):
        back = headline_watch.went_back(parts, known)
    seen = new or back
    waiting = e.get("pending")
    if not seen:
        for k in ("pending", "pending_back", "pending_at"):
            e.pop(k, None)          # the page shows the headline we hold: an unconfirmed sighting is dropped
        return None
    e["soon_at"] = now.isoformat()  # look again on the next run in either case
    if waiting and headline_watch.same(waiting, seen) and bool(e.get("pending_back")) == bool(back):
        for k in ("pending", "pending_back", "pending_at"):
            e.pop(k, None)
        e["page_title"] = seen
        return seen, bool(back)     # seen on two looks in a row: confirmed
    e["pending"], e["pending_back"], e["pending_at"] = seen, bool(back), now.isoformat()
    return None                     # first sighting: wait for the next look


def _record_renames(renames, months_dir, archive, now):
    """Write new headlines ({link: (headline, back)}) into the 7-day archive (in memory) and the monthly files."""
    if not renames:
        return 0
    stamp = now.isoformat()
    by_link = {}
    for a in archive or []:
        for link in [a.get("link")] + [v.get("link") for v in a.get("versions", [])]:
            by_link[link] = a
    done = set()
    for link, new in renames.items():
        a = by_link.get(link)
        if a is not None and headline_watch.merge_new_headline(a, new[0], stamp, new[1]):
            done.add(link)
    oldest = now - timedelta(hours=SCHEDULE_HOURS[-1] + 24)
    for name in sorted(os.listdir(months_dir)) if os.path.isdir(months_dir) else []:
        if not name.endswith(".json") or name[:7] < oldest.strftime("%Y-%m"):
            continue
        path = os.path.join(months_dir, name)
        items, changed = _load(path, []), False
        for a in items:
            links = [a.get("link")] + [v.get("link") for v in a.get("versions", [])]
            for link in links:
                if link in renames and headline_watch.merge_new_headline(a, *renames[link][:1], stamp, renames[link][1]):
                    changed = True
                    done.add(link)
                    break
        if changed:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=1)
    return len(done)


def check_on_pc(headers_for, outlets, allowed, crawl_delay, seconds=4 * 60):
    """On David's PC: check the links GitHub said are due for the local outlets, the outlets side by side.
    Returns {link: {"outlet", "published", "result", "page"}} to send back ("page": the page's headline
    candidates; GitHub decides whether the headline changed, see headline_watch.py)."""
    try:
        todo = requests.get(LOCAL_TODO_URL, timeout=TIMEOUT).json().get("links", [])
    except (requests.RequestException, ValueError):
        return {}
    by_name = {o["name"]: o for o in outlets}
    deadline = time.monotonic() + seconds
    out, groups = {}, {}
    for item in todo:
        groups.setdefault(item.get("outlet"), []).append(item)

    def work(name):
        o = by_name.get(name)
        refused = 0
        for item in groups[name]:
            if not o or time.monotonic() > deadline or refused >= GIVE_UP:
                break             # (refused: the site stopped answering this PC - don't keep knocking)
            if not allowed(item["link"]):
                continue
            result, parts = probe(item["link"], headers_for(o), item.get("titles"))
            out[item["link"]] = {**{k: v for k, v in item.items() if k != "titles"}, "result": result,
                                 **({"page": parts} if parts else {})}
            refused = refused + 1 if result is None else 0
            time.sleep(max(PC_PAUSE, crawl_delay(item["link"])))

    with ThreadPoolExecutor(max_workers=max(1, len(groups))) as pool:
        list(pool.map(work, list(groups)))
    return out
