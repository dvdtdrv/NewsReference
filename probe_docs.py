"""
Test: download a few public documents from outlets that refuse GitHub and Claude's servers
(e.g. bTV's published election contracts), so they can be checked. Saves them to OUTPUT_DIR.
Run with:   python probe_docs.py OUTPUT_DIR
"""
import os, sys, requests
import collect

URLS = [
    "https://cadmus.eui.eu/bitstreams/f233f694-c9c6-4b6d-87fa-98f9cc27b6d1/download",
    "https://cadmus.eui.eu/bitstreams/b8901241-08c8-4b54-9709-f3a16f6476e0/download",
]

def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for i, u in enumerate(URLS):
        try:
            r = requests.get(u, headers=collect.BROWSER_HEADERS, timeout=60)
            path = os.path.join(out, f"mpm2026_{i}.pdf")
            with open(path, "wb") as f:
                f.write(r.content)
            print(r.status_code, len(r.content), u)
        except Exception as e:
            print("ERR", u, e)

if __name__ == "__main__":
    main()
