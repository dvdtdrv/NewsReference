"""
Spot one article that an outlet re-published under a new headline.

Many outlets change a headline after publishing ("...three flights" -> "...one landed in Plovdiv"),
and the headline is part of the link, so the link changes too, e.g. on Darik:
    .../bombeni-zaplahi-sreshtu-tri-poleta-do-sofiia-2471203
    .../bombeni-zaplahi-sreshtu-tri-poleta-do-sofiia-ediniiat-kacna-v-plovdiv-2471203
Same outlet, same article number (2471203), same time -> the same article, not two.
(5 Nov 2026: about 2% of the archive, 370-400 of 20 000 articles, were such versions.)

We keep ONE article: the newest headline and link, plus a list of its earlier headlines
in "versions" (the site can show "headline changed 2 times").

Used by collect.py (when collecting), group_stories.py (saved stories) and build_site.py.
"""

import re
from difflib import SequenceMatcher

# the article number at the END of the link: "...-2471203", "...-1420842news.html", "...877960.html"
_ID = re.compile(r"(?<![\d.])(\d{5,})(?:news)?(?:\.s?html?|\.php)?/?$")


def article_id(link):
    """The outlet's own number for the article, if its link ends with one (else None)."""
    path = (link or "").split("?")[0].split("#")[0]
    m = _ID.search(path)
    return m.group(1) if m else None


def similar(t1, t2):
    return SequenceMatcher(None, (t1 or "").lower(), (t2 or "").lower()).ratio()


def same_article(a, b):
    """True if a and b are two versions of one article (same outlet, renamed)."""
    if a.get("outlet") != b.get("outlet") or a.get("link") == b.get("link"):
        return a.get("outlet") == b.get("outlet") and a.get("link") == b.get("link")
    same_time = (a.get("published") or "")[:16] == (b.get("published") or "")[:16]
    ida, idb = article_id(a.get("link")), article_id(b.get("link"))
    if ida and ida == idb:
        # an id alone is not enough: Vesti.bg once gave two different articles the same number
        return same_time or similar(a.get("title"), b.get("title")) >= 0.5
    # no number in the link (Sega, Mediapool...): same minute and a very similar headline
    return same_time and similar(a.get("title"), b.get("title")) >= 0.6


def all_links(a):
    return [a.get("link")] + [v.get("link") for v in a.get("versions", [])]


def first_link(a):
    """The link the article was first seen under (stays the same when the headline changes)."""
    v = a.get("versions")
    return v[0]["link"] if v else a.get("link")


def merge(keep, newer):
    """Make `keep` the newest version: take `newer`'s headline and link, remember the old ones
    in keep["versions"] (oldest first). `published` stays the earliest time.
    Returns True if anything changed."""
    if keep is newer:
        return False
    before = (keep.get("title"), keep.get("link"), list(keep.get("versions", [])))
    history = list(keep.get("versions", [])) + list(newer.get("versions", []))
    history.append({"title": keep.get("title"), "link": keep.get("link")})
    for k in ("title", "link", "summary", "image"):
        if newer.get(k):
            keep[k] = newer[k]
    times = [t for t in (keep.get("published"), newer.get("published")) if t]
    if times:
        keep["published"] = min(times)
    if newer.get("collected"):
        keep["collected"] = max(keep.get("collected") or "", newer["collected"])
    versions, seen = [], {keep.get("title")}
    for v in history:                     # one entry per earlier headline
        if v.get("title") and v["title"] not in seen:
            seen.add(v["title"])
            versions.append({"title": v["title"], "link": v.get("link")})
    if versions:
        keep["versions"] = versions
    else:
        keep.pop("versions", None)
    return before != (keep.get("title"), keep.get("link"), keep.get("versions", []))


def newest_last(a):
    """Sort key: older versions first (by when we collected them, then by time)."""
    return (a.get("collected") or "", a.get("published") or "")


class Index:
    """Finds an earlier version of an article quickly (by outlet + number, outlet + minute, link)."""

    def __init__(self, articles=()):
        self.by_id, self.by_minute, self.by_link = {}, {}, {}
        for a in articles:
            self.add(a)

    def add(self, a):
        o = a.get("outlet")
        for link in all_links(a):
            self.by_link[link] = a
            i = article_id(link)
            if i:
                self.by_id.setdefault((o, i), []).append(a)
        self.by_minute.setdefault((o, (a.get("published") or "")[:16]), []).append(a)

    def find(self, a):
        if a.get("link") in self.by_link:
            return self.by_link[a["link"]]
        o = a.get("outlet")
        cands = list(self.by_id.get((o, article_id(a.get("link"))), [])) if article_id(a.get("link")) else []
        cands += self.by_minute.get((o, (a.get("published") or "")[:16]), [])
        for c in cands:
            if same_article(c, a):
                return c
        return None


def collapse(articles, prefer=None):
    """Merge versions of the same article in a list and return the shorter list (original order).
    The newest version wins: by `collected`, or the articles whose link is in `prefer`."""
    prefer = prefer or set()
    order = sorted(range(len(articles)),
                   key=lambda i: (articles[i].get("link") in prefer, newest_last(articles[i]), i))
    index, owner, kept = Index(), {}, []
    for i in order:
        a = dict(articles[i])
        found = index.find(a)
        if found is None:
            index.add(a)
            kept.append(a)
            owner[i] = a
        else:
            merge(found, a)
            index.add(found)
            owner[i] = found
    first = {}
    for i in range(len(articles)):
        first.setdefault(id(owner[i]), i)
    return sorted(kept, key=lambda a: first[id(a)])
