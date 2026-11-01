# NewsReference

A website that groups Bulgarian news coverage of the same event, so you can see
which outlets covered a story and which stayed silent.

## Run it

Double-click **`run_all.bat`**. It does three steps:

1. `collect.py` reads all 20 outlets, adds new articles, and saves every article permanently by month.
2. `group_stories.py` groups the last 48 hours into stories, and saves every story permanently by day.
3. `build_site.py` builds `site\index.html` and one archive page per day.

Run it every so often; each run adds to the archive. Later, GitHub will run it every 30 minutes.

## Files

| File | What it is |
| --- | --- |
| `feeds.py` | The outlets and how to read each (feed or news sitemap). Edit to add/remove outlets. |
| `collect.py` | Step 1: collects new articles. |
| `group_stories.py` | Step 2: groups articles into stories, lists who didn't cover each. |
| `build_site.py` | Step 3: builds the website pages from the stories. |
| `site_template.html` | The design of the page. Change the look here, never in `site\`. |
| `data\articles.json` | Articles from the last 7 days (used for grouping). |
| `data\articles\YYYY-MM.json` | **Every article ever collected**, one file per month. Never deleted. |
| `data\stories.json` | Stories from the last 48 hours (the front page). |
| `data\stories\YYYY-MM-DD.json` | **Every story**, saved by the day it started. Never deleted. |
| `data\outlet_status.json` | How each outlet did on the last run. |
| `site\index.html` | The website's front page. |
| `site\archive\YYYY-MM-DD.html` | One archive page per day. |
| `check_feeds.py`, `probe_missing.py` | Diagnostic tools used to find the feeds. |
| `CLAUDE.md` | Project brief for Claude Code. |

## Web app

The `web` folder holds what makes the site installable on phones: `manifest.webmanifest`
(name, colours, icons), the icons, and `sw.js` (keeps the last opened pages available offline).
`build_site.py` copies them into `site\`. On a phone: open the site, then
"Add to Home screen" (Android) or Share → "Add to Home Screen" (iPhone).

## On GitHub

`.github/workflows/update.yml` runs the three steps on GitHub every 30 minutes and publishes `site/`
with GitHub Pages. The archive (`data/`) is kept on a separate branch called `data`, which always holds
only the latest snapshot. `seed/` is a copy of the archive from 31 Oct 2026 that the very first
GitHub run starts from. The `data/` and `site/` folders on your PC are not uploaded (see `.gitignore`).

## Fair blindspots

An outlet is only listed as "didn't cover" a story if it was read in the last 3 hours
and our archive for it goes back to before the story started. In the first day of running,
fast outlets (bTV, Fakti) only show their last few hours, so blindspot lists get more
reliable as the archive builds up.
