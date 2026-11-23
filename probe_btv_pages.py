"""
Started by hand only (probe-catchup.yml with check = btv-pages, on David's PC). Changes nothing.

Question (23 Nov 2026): bTV's sitemap lists only ~30 recent links, so catch-up reading can't recover most of what
bTV published while the PC was off. Do bTV's section pages (България, Светът, Предавания) list older articles,
page after page? For each section this opens page 1, finds the link to the next page, and opens page 2 and two
deeper pages (at most 4 pages per section, 5 s apart). It writes every article link each page shows, so the
links can be compared with the archive (which knows each article's date) to see how far back each page reaches.

Output: probe_btv_pages.json (a download on the run's page).
Run by hand with:   python probe_btv_pages.py
"""

import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests

import collect

SITE = "https://btvnovinite.bg"
SECTIONS = ["bulgaria", "svetut", "predavania"]
DEEPER = [5, 15]          # after page 2, these page numbers show how far back the pages go
PAUSE = 5
HEADERS = collect.BROWSER_HEADERS   # bTV allowed reading for this project as a browser (1 Nov 2026)


def get(url):
    if not collect.allowed(url):
        return None, "robots.txt disallows"
    time.sleep(PAUSE)
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        return r.status_code, r.text
    except requests.RequestException as e:
        return None, type(e).__name__


def article_links(page, section):
    found = re.findall(rf'href="((?:{re.escape(SITE)})?/{section}/[^"#?]+\.html)"', page)
    out = []
    for link in found:
        full = urljoin(SITE, link)
        if full not in out:
            out.append(full)
    return out


def next_page_url(page, section, base):
    """The address of page 2, as the page itself links to it (rel=next, or a link with 2 as page number)."""
    m = re.search(r'<link[^>]+rel="next"[^>]+href="([^"]+)"', page) or re.search(r'<a[^>]+rel="next"[^>]+href="([^"]+)"', page)
    if m:
        return urljoin(base, m.group(1).replace("&amp;", "&"))
    for href in re.findall(r'href="([^"]+)"', page):
        h = href.replace("&amp;", "&")
        if section in h and re.search(r"(?:[?&](?:page|p|pg)=2\b|/page/2/?$|/2/?$)", h):
            return urljoin(base, h)
    return None


def main():
    report = {"run_at": datetime.now(timezone.utc).isoformat(), "sections": []}
    for section in SECTIONS:
        base = f"{SITE}/{section}/"
        entry = {"section": section, "pages": []}
        status, page = get(base)
        entry["pages"].append({"n": 1, "url": base, "status": status,
                               "links": article_links(page, section) if status == 200 else [],
                               "note": "" if status == 200 else str(page)[:120]})
        nxt = next_page_url(page, section, base) if status == 200 else None
        entry["next_page_pattern"] = nxt
        if status == 200 and not nxt:     # no next-page link found: keep clues (links with numbers, "load more" buttons)
            entry["clues"] = sorted({h for h in re.findall(r'(?:href|data-url|data-href|data-next)="([^"]+)"', page)
                                     if re.search(r"page|[?&]p=|offset|load|more|ajax|api", h, re.I)})[:60]
            entry["buttons"] = re.findall(r">\s*((?:Зареди|Виж|Още|Покажи)[^<]{0,30})<", page)[:10]
        if nxt:
            for n in [2] + DEEPER:
                url = re.sub(r"([?&](?:page|p|pg)=|/page/|/)2(\b|/?$)", lambda m: f"{m.group(1)}{n}{m.group(2)}", nxt, count=1)
                status, p = get(url)
                links = article_links(p, section) if status == 200 else []
                entry["pages"].append({"n": n, "url": url, "status": status, "links": links,
                                       "note": "" if status == 200 else str(p)[:120]})
                if status != 200 or not links:
                    break
        report["sections"].append(entry)
        print(f"{section}: next page = {nxt}; " + ", ".join(f"page {p['n']}: {p['status']} {len(p['links'])} links"
                                                         for p in entry["pages"]))
    with open("probe_btv_pages.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
