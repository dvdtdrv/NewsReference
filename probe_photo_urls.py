"""
Test: do these outlets' photo addresses load when shown on our site?
Asks each photo address (from image_test_urls.json) three ways: with no "Referer" (what our pages send),
as if from our site, and as if from the outlet's own site. Writes probe_photo_urls.json.
Run with:   python probe_photo_urls.py OUTPUT.json
"""
import json, sys
from urllib.parse import urlparse, quote
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"

def ask(url, referer):
    h = {"User-Agent": UA, "Accept": "image/avif,image/webp,image/*,*/*;q=0.8"}
    if referer:
        h["Referer"] = referer
    try:
        r = requests.get(url, headers=h, timeout=20, stream=True, allow_redirects=True)
        first = next(r.iter_content(64), b"")
        return {"status": r.status_code, "type": r.headers.get("Content-Type", ""), "final": r.url[:120], "start": first[:12].hex()}
    except Exception as e:
        return {"error": str(e)[:150]}

def main():
    urls = json.load(open("image_test_urls.json", encoding="utf-8"))
    out = {}
    for outlet, kinds in urls.items():
        for kind, items in kinds.items():
            for u in items:
                site = f"{urlparse(u).scheme}://{urlparse(u).netloc}/"
                out.setdefault(outlet, []).append({"kind": kind, "url": u,
                    "no_referer": ask(u, None), "from_our_site": ask(u, "https://dvdtdrv.github.io/"),
                    "from_outlet": ask(u, site)})
    json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
