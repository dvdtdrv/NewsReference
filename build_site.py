"""
Step 3: build the website pages from the latest stories and the archive.

Takes site_template.html and writes:
  site/index.html               the front page: stories from the last 48 hours
  site/abonament.html           the subscription page
  site/archive/YYYY-MM-DD.html  one page per day in the archive (data/stories/YYYY-MM-DD.json)
  site/manifest.webmanifest, sw.js, icons   copied from web/, so phones can install the site as an app

The stories are put inside each page itself, so the pages work straight from your folder:
double-click site/index.html to open the site.

Run with:   python build_site.py
"""

import json
import os
import shutil

from feeds import UNTRACKED

TEMPLATE = "site_template.html"
OUT_DIR = "site"
WEB_DIR = "web"   # manifest, icons and offline helper that make the site installable on phones
DAYS_DIR = os.path.join("data", "stories")
KEEP = ("outlet", "title", "link", "published", "image")


def slim(stories):
    """Keep only what the page uses, so it loads fast."""
    for s in stories:
        s["articles"] = [{k: a.get(k, "") for k in KEEP} for a in s["articles"]]
    return stories


def archive_days():
    """The days in the archive, newest first, with how many stories each has."""
    if not os.path.isdir(DAYS_DIR):
        return []
    days = []
    for name in sorted(os.listdir(DAYS_DIR), reverse=True):
        if name.endswith(".json"):
            with open(os.path.join(DAYS_DIR, name), encoding="utf-8") as f:
                days.append({"date": name[:-5], "count": len(json.load(f)["stories"])})
    return days


def render(data, template, fragment_only=False):
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")  # a headline containing "</script>" must not end the script
    page = template.replace("/*__DATA__*/", payload).replace("{{BASE}}", data.get("base", ""))
    if fragment_only:
        return page
    # wrap in a full HTML document: title, fonts and styles go in <head>, the rest in <body>
    head, body = page.split("<!--body-->", 1)
    return (
        '<!doctype html>\n<html lang="bg">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        f"{head}</head>\n<body>{body}</body>\n</html>\n"
    )


def front_page_data():
    with open(os.path.join("data", "stories.json"), encoding="utf-8") as f:
        data = json.load(f)
    slim(data["stories"])
    data["archive_days"] = archive_days()
    data["base"] = ""
    return data


def build(fragment_only=False):
    """The front page as one HTML string (used for the preview)."""
    with open(TEMPLATE, encoding="utf-8") as f:
        return render(front_page_data(), f.read(), fragment_only)


def main():
    with open(TEMPLATE, encoding="utf-8") as f:
        template = f.read()
    os.makedirs(os.path.join(OUT_DIR, "archive"), exist_ok=True)

    # web app files (manifest, icons, offline helper) are copied as they are
    for name in os.listdir(WEB_DIR):
        shutil.copyfile(os.path.join(WEB_DIR, name), os.path.join(OUT_DIR, name))

    front = front_page_data()
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(render(front, template))

    # the subscription page: same template and data, shown in "support" mode
    with open(os.path.join(OUT_DIR, "abonament.html"), "w", encoding="utf-8") as f:
        f.write(render({**front, "page": "support"}, template))

    days = front["archive_days"]
    for day in days:
        with open(os.path.join(DAYS_DIR, f"{day['date']}.json"), encoding="utf-8") as f:
            saved = json.load(f)
        data = {
            "generated_at": saved["updated_at"],
            "archive_date": day["date"],
            "tracked_outlets": saved.get("tracked_outlets", []),
            "untracked_outlets": UNTRACKED,
            "stories": slim(saved["stories"]),
            "archive_days": days,
            "base": "../",
        }
        with open(os.path.join(OUT_DIR, "archive", f"{day['date']}.html"), "w", encoding="utf-8") as f:
            f.write(render(data, template))

    print(f"Website built: site\\index.html and {len(days)} archive pages in site\\archive\\  "
          "(double-click site\\index.html to open)")


if __name__ == "__main__":
    main()
