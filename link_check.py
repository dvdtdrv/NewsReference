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

STATE_FILE = os.path.join("data", "deleted.json")
LOCAL_TODO_FILE = os.path.join("data", "link_check_local.json")
LOCAL_TODO_URL = "https://raw.githubusercontent.com/dvdtdrv/NewsReference/data/link_check_local.json"
SCHEDULE_DAYS = (1, 3, 7, 14, 30)   # check each article about this many days after it was published
PER_OUTLET = 40                      # at most this many checks per outlet per run (runs are every 30 min)
SECONDS = 4 * 60                     # at most this long per run, all outlets together
RECHECK_HOURS = 6                    # after a first "no such page", ask again this much later
TIMEOUT = 15
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
    """How many of the SCHEDULE_DAYS have passed since the article was published."""
    age = (now - datetime.fromisoformat(published)).total_seconds() / 86400
    return sum(1 for d in SCHEDULE_DAYS if age >= d)


def is_due(entry, published, now):
    if entry and entry.get("strikes"):
        last = datetime.fromisoformat(entry["last"])
        return now - last >= timedelta(hours=RECHECK_HOURS)
    return stage_for(published, now) > (entry or {}).get("stage", 0)


HEAD_BYTES = 250_000
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
                    low = raw.lower()
                    if b"</title>" in low and (b"og:url" in low or b'rel="canonical"' in low) and b"<body" in low:
                        break
            enc = r.encoding if r.encoding and r.encoding.lower() not in ("iso-8859-1", "latin-1") else "utf-8"
    except requests.RequestException:
        return None
    if status in (404, 410):
        return "gone"
    if status != 200:
        return None
    if "challenge" in urlparse(final).path:
        return None       # a robot check page (Moreto.net): we can't tell
    head = raw.decode(enc, errors="replace")
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
    """{outlet: [articles due for a check]} for outlets on GitHub (local=False) or the PC (local=True)."""
    names = {o["name"]: o for o in outlets if checkable(o) and bool(o.get("local")) == local}
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
            if is_due(e, a["published"], now):
                due.setdefault(a["outlet"], []).append(a)
    for items in due.values():
        items.sort(key=lambda a: a["published"])     # the oldest first: they are the most overdue
    return due


def run(outlets, months_dir, now, allowed, crawl_delay, headers_for, local=None):
    """Check due links on this machine and apply answers the PC sent (local = its local_articles.json).
    Returns (checked, newly gone)."""
    state = _load(STATE_FILE, {})
    meta = state.pop("_meta", {})
    gone_before = sum(1 for e in state.values() if e.get("gone"))

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
        meta["pc_batch"] = local.get("fetched_at")

    # 2. our own checks
    due = due_articles(outlets, months_dir, state, now, local=False)
    by_name = {o["name"]: o for o in outlets}
    deadline = time.monotonic() + SECONDS
    results = []

    def work(name):
        headers = headers_for(by_name[name])
        done = 0
        for a in due[name]:
            if done >= PER_OUTLET or time.monotonic() > deadline:
                break
            if not allowed(a["link"]):
                continue
            results.append((a, probe(a["link"], headers, headlines_of(a))))
            done += 1
            time.sleep(crawl_delay(a["link"]))
        return done

    with ThreadPoolExecutor(max_workers=12) as pool:
        checked = sum(pool.map(work, list(due)))
    for a, result in results:
        apply(state, a["link"], a["outlet"], result, now, a["published"])

    # 3. tell the PC which links of its outlets are due
    local_due = due_articles(outlets, months_dir, state, now, local=True)
    _save(LOCAL_TODO_FILE, {"made": now.isoformat(), "links": [
        {"link": a["link"], "outlet": a["outlet"], "published": a["published"], "titles": headlines_of(a)}
        for items in local_due.values() for a in items[:PER_OUTLET]]})

    # forget checks of articles older than the schedule, unless they were deleted
    limit = (now - timedelta(days=SCHEDULE_DAYS[-1] + 2)).isoformat()
    state = {k: e for k, e in state.items() if e.get("gone") or e.get("restored") or e.get("last", "") >= limit}
    state["_meta"] = meta
    _save(STATE_FILE, state)
    state.pop("_meta")
    gone_now = sum(1 for e in state.values() if e.get("gone"))
    return checked, gone_now - gone_before


def check_on_pc(headers_for, outlets, allowed, crawl_delay, seconds=3 * 60):
    """On David's PC: check the links GitHub said are due for the local outlets.
    Returns {link: {"outlet", "published", "result"}} to send back."""
    try:
        todo = requests.get(LOCAL_TODO_URL, timeout=TIMEOUT).json().get("links", [])
    except (requests.RequestException, ValueError):
        return {}
    by_name = {o["name"]: o for o in outlets}
    deadline = time.monotonic() + seconds
    out = {}
    for item in todo:
        if time.monotonic() > deadline:
            break
        o = by_name.get(item["outlet"])
        if not o or not allowed(item["link"]):
            continue
        out[item["link"]] = {**{k: v for k, v in item.items() if k != "titles"},
                             "result": probe(item["link"], headers_for(o), item.get("titles"))}
        time.sleep(crawl_delay(item["link"]))
    return out
