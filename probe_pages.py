"""
Test: where in an article page does the sharing photo (og:image) appear, as our program sees the page?
Run with:   python probe_pages.py OUTPUT.json
"""
import json, sys
import requests
import collect

LINKS = [
    "https://novini.bg/article/2026110311430837925",
    "https://novini.bg/article/2026110312051563355",
    "https://novini.bg/article/2026110311175427945",
    "https://novini.bg/article/2026110311593317482",
    "https://novini.bg/article/2026110311483751605"
]

def main():
    out = []
    for link in LINKS:
        try:
            r = requests.get(link, headers=collect.HEADERS, timeout=30)
            t = r.text
            out.append({"link": link, "status": r.status_code, "length": len(r.content),
                        "og_at": t.find("og:image"), "head_end_at": t.lower().find("</head>"),
                        "found_by_collector": collect.page_image(link, collect.HEADERS)})
        except Exception as e:
            out.append({"link": link, "error": str(e)[:200]})
    json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
