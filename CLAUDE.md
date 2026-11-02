# Project brief: NewsReference

## Goal
A free public website that groups articles from Bulgarian outlets into stories and shows,
per story: which outlets covered it, how each framed it, and which stayed silent (blindspots).
English aggregators like Ground News barely cover Bulgarian-language media; this fills that gap.

## Owner
David, beginner programmer (Windows, Anaconda Python). Explain code plainly; prefer simple tools.
He runs things by double-clicking .bat files in Desktop\NewsReference.
Commits: author dvdtdrv <dvdtdrv@users.noreply.github.com>, NO Co-Authored-By / Claude-Session trailers
(David asked, 2 Nov 2026: commits should show as his own).

## Pipeline (working, tested 31 Oct 2026)
1. `collect.py`: reads 20 outlets from `feeds.py` (18 RSS feeds, 2 news sitemaps: Trud, Offnews),
   respects robots.txt, appends new articles to `data/articles.json` (7-day archive, deduped by link
   and by outlet+title). BTA is `gentle`: one request per run; on HTTP 429 it waits the Retry-After
   time, stored in `data/state.json`.
2. `group_stories.py`: TF-IDF on character 3-5 grams of headline (x2) + first 150 chars of summary,
   average-linkage agglomerative clustering, similarity threshold 0.35, 48 h window, story = 2+ outlets.
   Tested on 614 real headlines: 82 stories, top groups clean. Writes `data/stories.json`.
   No embeddings model yet (heavier install); revisit if grouping misses paraphrases.
3. Blindspot rule: outlet listed in `not_covered` only if read in last 3 h AND its archive reaches back
   before the story's first article. Untracked outlets (BNR, Novini.bg, Dir.bg) are listed separately.

## Archive (added 31 Oct 2026)
- `collect.py` also syncs every article into `data/articles/YYYY-MM.json` (by published month, kept forever).
- `group_stories.py` saves stories into `data/stories/YYYY-MM-DD.json` by Sofia start day. A story is
  updated while its first article is < 36 h old (FREEZE_HOURS), then frozen. Re-saves merge with the stored
  copy (union of articles), so the 48 h window cutting old articles never shrinks an archived story.
  First run archives everything in the window.
- Known gap: re-clustering a day later can put an article into two archived stories (5 of 245 in a test).
- `build_site.py` writes `site/index.html` + `site/archive/YYYY-MM-DD.html`; template switches to a date view
  when `data.archive_date` is set; `data.base` is "../" on archive pages.
- Site design: egg-white `--paper`, darker `--paper-deep` at the top fading to paper on scroll; Oswald display,
  Golos Text body; header = Истории, Медии | NEWS REFERENCE | Как работи, За проекта + "Слепи петна" button.

## Outlets added 1 Nov 2026
- BNR: news moved to bnrnews.bg; feed https://bnrnews.bg/api/rss/main (robots allows).
- Novini.bg: feed exists at /api/rss but robots.txt disallows /api/* -> we use the news sitemap
  https://novini.bg/sitemap/news/1.xml (200 latest, headlines, no photos).
- Dir.bg: feed https://dir.bg/feeds/rss (robots allows all; includes photos).
- Now 23 outlets, UNTRACKED is empty.
- Later on 1 Nov, 13 more (asked for by David): Darik, Focus, Vesti.bg, BG On Air, Bloomberg TV, Evrocom,
  Euronews BG, Boulevard Bulgaria, Svobodna Tochka, Marica, Moreto.net (all RSS); DW via
  https://www.dw.com/bg/news-sitemap.xml; News.bg via its https://news.bg/latest page (`page` method,
  `read_newsbg_page` in collect.py; relative times like "преди 2 часа", robots crawl-delay 10). 36 outlets.

## Web app (1 Nov 2026)
- `web/` holds manifest.webmanifest, icons (drawn in Oswald 500, NEWS/REFERENCE on #E6DFCC) and sw.js
  (network-first for same-origin pages, falls back to cache offline). build_site.py copies web/* into site/
  and replaces {{BASE}} in the template head ("" or "../" for archive pages). Tested: no installability
  errors, works offline. The service worker registers only on https (GitHub Pages).

## Decisions
- Never store or show full article text: headline, short summary, link only.
- Google News RSS fallback is NOT allowed (Google's robots.txt disallows it).
- BTA: blocks programs (429 on the first request; browsers work). On 31 Oct 2026 BTA replied in writing that
  our program may read the feed in any way, at most once per 30 min (text in `permissions/BTA.md`).
  So BTA is `as_browser` in feeds.py (browser User-Agent, BTA only). Commercial use, photos and attribution
  were not covered: ask BTA again before the project earns money.
- bTV: refused GitHub's servers (403). On 1 Nov 2026 bTV replied that we may read its coverage "from the
  browser" for this student project (`permissions/bTV.md`) -> `as_browser` for bTV. Same caveats as BTA.
- GitHub Actions cannot reach 8 outlets (bTV, Trud, Blitz, Marica: 403; Dnes.bg, BG On Air, Bloomberg TV:
  timeout; Nova: empty). They work from David's PC. Do not bypass; options: permission, self-hosted runner, EU server.
- Self-hosted runner (live 2 Nov 2026): David's PC (`david-pc`, C:\Users\david\actions-runner) runs
  local-fetch.yml at :02/:32 -> fetch_local.py reads the 7 `local` outlets -> artifact; update.yml (:07/:37)
  downloads it, collect.py uses it if < 75 min old, else status "waiting". Runner starts hidden at login
  (start_runner.bat / stop_runner.bat). Public repo: never approve fork PR workflow runs.
- Repo stays public for now (free Pages + unlimited minutes). If going private later: second public repo for
  the built site only (free), or GitHub Pro; private minutes (~2000/mo) need hourly runs or self-hosted.
- Later option for 24/7 without the PC: small EU server (Hetzner ~4 EUR/mo); test the 7 outlets first.
- English outlets (Novinite, Sofia Globe) left out: grouping is Bulgarian text only. Sofia Globe feed dead since Jul 2025.
- Outlet classification: no left/right labels. Measured axes: ownership (cited records), geopolitical framing,
  blindspots, sensationalism. Always show evidence.
- Hosting (live): GitHub Actions runs collect + group every 30 min and commits `data/stories.json`;
  GitHub Pages serves a static site that reads it.
- Design: done with Claude as a clickable mockup first, then turned into the real static page.
- Architecture doc: https://claude.ai/artifact/WMiJigfLkQ3aMtR8eK3eMn

## Ideas noticed
- 24 Chasa and Pogled.info publish word-for-word identical headlines (likely BTA wire copy):
  a "copied from the wire" indicator could be a feature.

## Next
- [ ] Run `run_all.bat` a few times; check BTA recovers.
- [ ] Design the front page (story cards, coverage bar, not-covered list).
- [ ] GitHub repo + Actions schedule + Pages.
- [ ] Later: LLM summaries and framing per outlet (open choice: Claude Haiku API vs self-hosted BgGPT).
