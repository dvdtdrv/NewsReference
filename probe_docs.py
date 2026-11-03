"""
Test: download a few public documents from outlets that refuse GitHub and Claude's servers
(e.g. bTV's published election contracts), so they can be checked. Saves them to OUTPUT_DIR.
Run with:   python probe_docs.py OUTPUT_DIR
"""
import os, sys, requests
import collect

URLS = [
    "https://www.baca.bg/wp-content/uploads/2026/08/BACA_Media_Market_2026.pdf.pdf",
    "https://mediaconnection.bg/download/report/107",
]

def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for i, u in enumerate(URLS):
        try:
            r = requests.get(u, headers=collect.BROWSER_HEADERS, timeout=60)
            path = os.path.join(out, f"more{i}.pdf")
            with open(path, "wb") as f:
                f.write(r.content)
            print(r.status_code, len(r.content), u)
        except Exception as e:
            print("ERR", u, e)

if __name__ == "__main__":
    main()
