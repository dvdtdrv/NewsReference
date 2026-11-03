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

## Photos (2 Nov 2026)
- Probe (probe_images.py, run on the PC via probe-images.yml) showed og:image on article pages for 33 of 35
  outlets; feeds had none for BNT, BNR, Mediapool, Offnews, Novini.bg, Euronews, Marica, Moreto, few for PIK,
  Svobodna Tochka, and Evrocom's were a Facebook icon. Many feed photos are small crops (Banker 150x150).
- collect.py `add_page_images`: for NEW articles (and photo-less ones < 48 h old) read the page head
  (<= 250 KB), take og:image (else twitter:image), max 20 page reads per outlet per run, robots + crawl-delay.
  Answers remembered in data/page_images.json (PC: NR_CACHE_DIR = actions-runner\cache). Feed photo stays
  as fallback. `good_image` drops svg/gif and file names like logo/icon/avatar/default/placeholder.
- Older articles: `backfill_page_images` upgrades up to 40 per outlet per run (12 outlets in parallel, 6 min cap),
  newest first; build_site.py and build_search.mjs show the remembered page photo for any link (incl. frozen stories).
- 3 Nov: Novini.bg puts og:image ~180 KB down, after an early fake "</head>": reader now reads until og:image
  (max 250 KB). Cache v2 dropped old "" answers once. Photo URLs are requoted (Marica: spaces, Cyrillic).
  Euronews pages refuse GitHub -> `photos_on_pc`: fetch_local.py sends {link: photo} in local_articles.json "photos".
  Site tries `image2` (feed photo kept as `image_feed`) when the page photo 404s (Fakti, Mediapool delete some).
- Skipped: BTA (permission covers the feed only), Dnevnik + Capital (`page_images: False`, pages 403 us).

## Outlet info (3-4 Nov 2026)
- outlets_info.json per outlet: owner, founded, sources [{label,url}], disputes [{date,title,summary,sources}],
  extra [{title,text,items?,sources}] (money, advertisers, election contracts...). Shown in the outlet window.
- David's rule (4 Nov): include EVERYTHING he sends and every suspicion, investigation or accusation found, but verify
  each against its source and label it (claim vs established, who says it, the other side's answer, anonymous sources).
- Done: BTA, BNT, BNR, bTV. Sources behind bTV's firewall are fetched via the PC runner (probe_docs.py) or the PC browser.
- 4 Nov: Media Pluralism Monitor 2026 (CMPF/EUI, Bulgaria) read in full via the PC browser (pdf.js from jsdelivr inside
  the cadmus.eui.eu tab; PDF at /server/api/core/bitstreams/<id>/content). Its findings, each checked against the cited
  source, were added to bTV, Nova (first 3 disputes), BNT, BNR and BTA. Still unread: IPI/MJRC "Media Capture Monitoring
  Report: Bulgaria" (Nov 2025) and the CoE/MFRR report (Oct 2025). Nova's owner/founded still empty (next outlet).

## Search (2 Nov 2026)
- Header magnifier -> `site/tarsene.html` (template `data.page == "search"`, body.compact: no sliding stage).
  Tabs Истории | Статии with counts, sort Най-подходящи | Най-нови; address keeps ?q=&t=article&s=new.
- `build_search.mjs` (Pagefind 1.5.2 via package.json, Node API custom records) indexes ALL archived stories
  (headline + article titles; meta href archive/DAY.html#s-ID) and articles (title + first 200 chars of summary;
  meta: outlet, published, image, story link). Filters type/outlet, sort date. Output site/pagefind/.
- Story bands have id="s-<id>"; archive page with that hash renders down to it, scrolls and flashes it.
- Works only over http(s), not file://. sw.js (cache v2) does not cache /pagefind/.
- Size: ~850 bytes per record (6.8 MB for 8k records); ~75k articles/month -> Pages 1 GB limit in about a year.
  Before then: index only recent months, or move search to a server.

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
- 3 Nov 2026: David allowed the outlet domains (incl. www.*) for Claude's cloud workspace (claude.ai Settings ->
  Capabilities). From the workspace 29 outlets answer; the same 7 `local` ones refuse it (403/reset), so test those via the PC.
- Later option for 24/7 without the PC: small EU server (Hetzner ~4 EUR/mo); test the 7 outlets first.
- English outlets (Novinite, Sofia Globe) left out: grouping is Bulgarian text only. Sofia Globe feed dead since Jul 2025.
- Outlet classification: David (2 Nov 2026) wants the site to show where each outlet sits on a spectrum
  ("За проекта" now says so, as a coming feature). Earlier plan was no left/right labels; Measured axes: ownership (cited records), geopolitical framing,
  blindspots, sensationalism. Always show evidence.
- Relay (3 Nov): GitHub's cron ran only ~hourly, so update.yml ends by dispatching local-fetch.yml with wait=27-min-spent;
  the PC waits, reads, uploads, then dispatches update.yml -> ~30 min cycle. local-fetch has no cron (queued requests
  wait for the PC); update.yml cron is an hourly backup. local-fetch concurrency cancel-in-progress keeps one relay.
- Quick rebuild (3 Nov): rebuild.yml rebuilds pages + search from the saved data branch and deploys (~1-2 min);
  runs on push to site_template.html/build_site.py/build_search.mjs/web/** or by hand. Use it for design/text changes.
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
