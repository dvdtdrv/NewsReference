"""
Test: download a few public documents from outlets that refuse GitHub and Claude's servers
(e.g. bTV's published election contracts), so they can be checked. Saves them to OUTPUT_DIR.
Run with:   python probe_docs.py OUTPUT_DIR
"""
import os, sys, requests
import collect

URLS = [
    "https://bravo.btv.bg/docs/%D0%A2%D0%B0%D0%B1%D0%BB%D0%B8%D1%86%D0%B0%20-%20%D0%B4%D0%BE%D0%B3%D0%BE%D0%B2%D0%BE%D1%80%D0%B8_2910.pdf",
    "https://web.static.btv.bg/Digital%20Sales%20Policy_2026_BG_EN.pdf",
    "https://web.static.btv.bg/izbori2026/BMG%20Sales%20Policy%20Elections%20October%202026.pdf",
]

def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for i, u in enumerate(URLS):
        try:
            r = requests.get(u, headers=collect.BROWSER_HEADERS, timeout=60)
            path = os.path.join(out, f"doc{i}.pdf")
            with open(path, "wb") as f:
                f.write(r.content)
            print(r.status_code, len(r.content), u)
        except Exception as e:
            print("ERR", u, e)

if __name__ == "__main__":
    main()
