"""
Started by hand only (probe-catchup.yml, on David's PC). Changes nothing.

Question (23 Nov 2026): when the PC was off, can we read back the articles the PC outlets published meanwhile?
Their feeds only list the newest articles, so after a night off most of the night is lost ("catch-up reading").
For each `local` outlet this looks, once, at:
  - its robots.txt: which sitemaps it names, its crawl-delay
  - the feed/sitemap we read now: how many articles, how far back
  - the sitemaps robots.txt names (and, in a sitemap index, the newest-looking ones)
  - page 2 of its feed (?page=2 / ?paged=2), if robots.txt allows it
and writes how far back each one reaches and whether it carries headlines.
At most MAX_REQUESTS per outlet, a pause between requests; big sitemaps are read only in part.

Output: probe_catchup.json and probe_catchup.txt (downloads on the run's page).
Run by hand with:   python probe_catchup.py
"""

import json
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import feedparser
import requests

import collect
from feeds import OUTLETS

MAX_REQUESTS = 8          # per outlet, robots.txt included
PAUSE = 5                 # seconds between requests (more if the outlet's crawl-delay asks)
MAX_BYTES = 3_000_000     # read at most this much of one answer (some sitemaps are 10 MB)
DAY_AGO = datetime.now(timezone.utc) - timedelta(hours=24)
DATE = re.compile(r"<(?:lastmod|news:publication_date)>\s*([^<]+?)\s*<", re.I)


def get(url, headers, budget):
    """One polite request; returns (status, text) or (None, error). Counts against the outlet's budget."""
    if budget["left"] <= 0:
        return None, "request limit reached"
    if not collect.allowed(url):
        return None, "robots.txt disallows"
    budget["left"] -= 1
    time.sleep(budget["pause"])
    try:
        r = requests.get(url, headers=headers, timeout=30, stream=True)
        body = b""
        for chunk in r.iter_content(65536):
            body += chunk
            if len(body) >= MAX_BYTES:
                break
        r.close()
        return r.status_code, body.decode(r.encoding or "utf-8", errors="replace")
    except requests.RequestException as e:
        return None, type(e).__name__


def describe(text):
    """What a feed / sitemap answer holds: kind, items, headlines?, newest and oldest date."""
    if "Just a moment" in text[:3000]:
        return {"kind": "Cloudflare check (we stop here)"}
    if "<sitemapindex" in text[:2000]:
        locs = re.findall(r"<loc>\s*([^<]+?)\s*</loc>", text)
        return {"kind": "sitemap index", "sitemaps": locs[:40], "count": len(locs)}
    if "<urlset" in text[:3000]:
        dates = sorted(d for d in (collect.parse_date(x) for x in DATE.findall(text)) if d)
        return {"kind": "sitemap", "items": text.count("<url>"), "headlines": "<news:title" in text,
                "items_last_24h": sum(1 for d in dates if d >= DAY_AGO),
                "_links": re.findall(r"<loc>\s*([^<]+?)\s*</loc>", text)[:50],
                "newest": dates[-1].isoformat() if dates else None, "oldest": dates[0].isoformat() if dates else None,
                "cut_off": len(text.encode()) >= MAX_BYTES - 100_000}
    feed = feedparser.parse(text)
    if feed.entries:
        dates = sorted(d for d in (collect.parse_date(e.get("published") or e.get("updated")) for e in feed.entries) if d)
        return {"kind": "feed", "items": len(feed.entries), "headlines": bool(feed.entries[0].get("title")),
                "items_last_24h": sum(1 for d in dates if d >= DAY_AGO),
                "_links": [e.get("link") for e in feed.entries][:50],
                "newest": dates[-1].isoformat() if dates else None, "oldest": dates[0].isoformat() if dates else None}
    return {"kind": "unknown", "start": re.sub(r"\s+", " ", text[:200])}


def hours_back(info):
    if not info.get("oldest"):
        return None
    return round((datetime.now(timezone.utc) - datetime.fromisoformat(info["oldest"])).total_seconds() / 3600, 1)


def probe(outlet):
    headers = collect.BROWSER_HEADERS if outlet.get("as_browser") else collect.HEADERS
    base = f"https://{'www.' if outlet.get('feed', '').startswith('https://www.') else ''}{outlet['domain']}"
    budget = {"left": MAX_REQUESTS, "pause": PAUSE}
    out = {"outlet": outlet["name"], "checked": []}

    status, text = get(f"{base}/robots.txt", headers, budget)
    sitemaps, delay = [], None
    if status == 200 and "<html" not in text[:500].lower():
        sitemaps = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", text)
        m = re.search(r"(?im)^\s*crawl-delay:\s*([\d.]+)", text)
        delay = float(m.group(1)) if m else None
        budget["pause"] = max(PAUSE, delay or 0)
    out["robots"] = {"status": status, "sitemaps": sitemaps, "crawl_delay": delay}

    first = {}

    def look(url, why):
        status, text = get(url, headers, budget)
        info = {"url": url, "why": why, "status": status}
        if status == 200:
            info.update(describe(text))
            info["hours_back"] = hours_back(info)
            links = info.pop("_links", None)
            if why == "what we read now":
                first["links"] = links
            elif (why == "page 2 of the feed" and links and first.get("links")
                  and len(set(links) & set(first["links"])) >= len(links) / 2):   # mostly the same articles
                info["same_as_page_1"] = True       # the outlet ignores the page number
        elif status is None:
            info["note"] = text
        out["checked"].append(info)
        return info

    now_url = outlet.get("feed") or outlet.get("sitemap") or outlet.get("page")
    look(now_url, "what we read now")
    for sm in sitemaps[:2]:
        info = look(sm, "named in robots.txt")
        if info.get("kind") == "sitemap index":
            # the children whose names suggest news or the newest part; else the first one
            kids = info.get("sitemaps", [])
            pick = [k for k in kids if re.search(r"news|latest|novini|post|article|2026", k, re.I)][:2] or kids[:1]
            for k in pick:
                look(urljoin(sm, k), "inside the sitemap index")
    if outlet.get("feed"):
        for page in ("page=2", "paged=2"):
            look(now_url + ("&" if "?" in now_url else "?") + page, "page 2 of the feed")
    out["requests_used"] = MAX_REQUESTS - budget["left"]
    return out


def main():
    report = {"run_at": datetime.now(timezone.utc).isoformat(), "outlets": []}
    lines = []
    for outlet in OUTLETS:
        if not outlet.get("local"):
            continue
        r = probe(outlet)
        report["outlets"].append(r)
        lines.append(f"== {r['outlet']}  (robots.txt: {r['robots']['status']}, sitemaps named: "
                     f"{len(r['robots']['sitemaps'])}, crawl-delay: {r['robots']['crawl_delay']}, requests: {r['requests_used']})")
        for c in r["checked"]:
            extra = (f"{c.get('kind')}, {c.get('items', c.get('count', ''))} items ({c.get('items_last_24h')} from the "
                     f"last 24 h), headlines: {c.get('headlines')}, reaches back {c.get('hours_back')} h"
                     + (", SAME AS PAGE 1" if c.get("same_as_page_1") else "") + (", read only in part" if c.get("cut_off") else "")
                     if c.get("status") == 200 else c.get("note", ""))
            lines.append(f"   [{c['status']}] {c['why']}: {c['url']}\n        {extra}")
        print("\n".join(lines[-1 - len(r['checked']):]))
    with open("probe_catchup.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    with open("probe_catchup.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
