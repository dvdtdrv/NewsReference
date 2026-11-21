"""
Headline changes seen on the article's own page (added 21 Nov 2026).

Why: a renamed article used to be noticed only if it showed up again in the outlet's feed under a new
headline. Feeds list only the latest items (bTV ~8 h, Dnes.bg ~1 h), and David's PC reads its 7 outlets
only while it is on (36% of the hours in the week to 21 Nov), so many changes were never seen and the
ranking under „Медии“ measured feed length as much as the outlets' behaviour. A test on 500 articles
aged 1-4 days found real renames the feeds never showed (Nova, Vesti.bg, Mediapool, Sega, Evrocom).

How: link_check.py already re-opens every article on a schedule (now 3 h, 12 h, 36 h, 3, 7, 14, 30 days).
At each visit we also read the page's own headline: the visible <h1> and og:title (and <title> as a
last resort). If none of them is the headline we know (or one of its earlier versions), the page shows
a new headline, and it is recorded at once, exactly like a rename seen in a feed: the newest headline
in "title", the old one in "versions" (versions.merge). (21 Nov 2026, David: one sighting counts; for a
few hours that day a second visit had to confirm it, but every first sighting in the test was confirmed.)

After every change we look again on the next run (RECHECK_MINUTES, ~30 min later instead of the next stage
hours later): if the page then shows an EARLIER headline again, that is recorded too, as a change back
(kind "reverted" on the site; the version gets "back": True). Some outlets test two headlines against
each other (A/B tests) or pull a headline and restore the old one, and both are worth seeing.

Noise we ignore: the site's name after the headline ("... - Mediapool.bg", "... | Новини"), a section
name in <h1> (Dir.bg), quote marks, broken quotes shown as ";" (Club Z), spacing and punctuation, and
generic page titles shorter than 20 characters (Sega's „Спорт - Новини СЕГА").
"""

import html
import re
from difflib import SequenceMatcher

H1 = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.I | re.S)
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
META = re.compile(r"<meta\b[^>]*>", re.I)
ATTR = re.compile(r"""(property|name|content)\s*=\s*(["'])(.*?)\2""", re.I | re.S)
SEP = re.compile(r"^(.*\S)\s+[-|—–:/•]\s+([^-|—–]{1,60})$")
MIN_LEN = 20            # shorter page headlines are generic ("Спорт - Новини СЕГА"), never a rename
RECHECK_MINUTES = 20    # after a change, look again on the next run (updates come every ~30 min)


def _text(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(html.unescape(s))).strip()


def page_parts(page):
    """The page's own headline candidates: {"h1", "og", "title"} (raw text, may be "")."""
    out = {"h1": "", "og": "", "title": ""}
    m = H1.search(page)
    if m:
        out["h1"] = _text(m.group(1))
    m = TITLE.search(page)
    if m:
        out["title"] = _text(m.group(1))
    for tag in META.findall(page):
        attrs = {k.lower(): v for k, _, v in ATTR.findall(tag)}
        if (attrs.get("property") or attrs.get("name") or "").lower() in ("og:title", "twitter:title") and attrs.get("content"):
            out["og"] = out["og"] or _text(attrs["content"])
    return out


def norm(s):
    s = html.unescape(s or "")
    s = re.sub(r"[„“”\"'«»‘’`;]", "", s)
    s = re.sub(r"[‐-―−]", "-", s)
    s = re.sub(r"\s*([:,.!?])\s*", r"\1 ", s)
    return re.sub(r"\s+", " ", s).strip(" .").lower()


def _variants(text):
    """The text, and the text with up to three trailing "<sep> name" parts cut off."""
    v = norm(text)
    out = [v] if v else []
    cur = text.strip()
    for _ in range(3):
        m = SEP.match(cur)
        if not m:
            break
        cur = m.group(1)
        out.append(norm(cur))
    return out


def same(a, b):
    """True if two headlines are the same text (ignoring quotes, spacing, punctuation, a cut-off end)."""
    x, y = norm(a), norm(b)
    if not x or not y:
        return False
    if x == y:
        return True
    short, long_ = sorted((x, y), key=len)
    if len(short) >= 25 and long_.startswith(short):
        return True                      # one of them is cut off or carries the site's name
    return SequenceMatcher(None, x, y).ratio() >= 0.97   # one comma or letter apart


def shows_known(parts, known):
    """True if the page shows one of the headlines we know (current or earlier)."""
    for k in known:
        for p in (parts.get("h1"), parts.get("og"), parts.get("title")):
            for v in _variants(p or ""):
                if same(v, k):
                    return True
    return False


def page_headline(parts):
    """The page's headline to record: <h1> if it looks like a headline, else og:title / <title> without
    the site's name. Returns "" if the page has nothing usable."""
    h1, og, title = parts.get("h1", ""), parts.get("og", ""), parts.get("title", "")
    if h1 and og:
        # Dir.bg adds a section to <h1> ("... | Лайф"): if og:title is <h1> without its tail, take og:title
        for v in _variants(h1)[1:]:
            if same(v, og):
                return og.strip()
    for c in (h1, og, title):
        c = (c or "").strip()
        if not c:
            continue
        if c is not h1:
            m = SEP.match(c)
            if m and len(m.group(1)) >= MIN_LEN:
                c = m.group(1)             # "Headline - Mediapool.bg" -> "Headline"
        if len(c) >= MIN_LEN:
            return c
    return ""


def judge(parts, known):
    """What the page says about the headline: None (same as we know, or can't tell) or the new headline."""
    if not parts or shows_known(parts, known):
        return None
    new = page_headline(parts)
    if not new or "\ufffd" in new or any(same(new, k) for k in known):
        return None     # nothing usable, garbled letters (wrong encoding), or a headline we know
    return new


def went_back(parts, known):
    """The EARLIER headline the page shows again instead of the current one (known[0]), else None.
    Only the page's main headline counts (page_headline: <h1> first), so a stale og:title next to a
    new <h1> is not a change back."""
    if not parts or not known or not known[0] or shows_known(parts, known[:1]):
        return None
    main = page_headline(parts)
    if not main or "\ufffd" in main:
        return None
    for k in known[1:]:
        if k and len(k) >= MIN_LEN and any(same(v, k) for v in _variants(main)):
            return k
    return None


def merge_new_headline(article, new_title, now_iso, back=False):
    """Record a new headline on one stored article (same link). back=True: the page shows an earlier
    headline again, so the chain becomes A -> B -> A. Returns True if it changed."""
    from versions import merge
    if not new_title or same(new_title, article.get("title")):
        return False
    if back:
        article["versions"] = list(article.get("versions", [])) + [
            {"title": article.get("title"), "link": article.get("link"), "until": now_iso, "back": True}]
        article["title"] = new_title
        article["collected"] = max(article.get("collected") or "", now_iso)
        return True
    return merge(article, {"title": new_title, "link": article.get("link"), "collected": now_iso})
