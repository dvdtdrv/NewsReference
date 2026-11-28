# NewsReference (Новинарски справочник)

Free public site that groups articles from 36 Bulgarian outlets into stories and shows, per story, who covered it,
how they headlined it, and who stayed silent ("blindspots"); plus who each outlet is (ownership, money, disputes).
Live: https://newsreference.bg (Cloudflare -> GitHub Pages) · Repo: dvdtdrv/NewsReference (public, stays public: free
Pages + Actions) · Architecture doc: https://claude.ai/artifact/WMiJigfLkQ3aMtR8eK3eMn · Full history of every decision and lesson: `docs/HISTORY.md` (search it before re-deciding something).

## Working with David (always)
- David is a beginner (Windows, Anaconda Python, runs .bat files by double-clicking). Explain plainly.
- ALWAYS answer in English, even when he writes in Bulgarian. The site itself is in Bulgarian.
- For EVERY change to how the site/pipeline works and EVERY new file, tell him: which file, what it does, why,
  what changed in GitHub Actions vs in the code, and whether he has to do anything.
- Show a mock-up or screenshot before any visible design change and let him choose; he often picks from 2-5 options.
- Before pushing a page change, check it with Playwright at 390 px (phone) AND on a computer width, in Chromium AND
  WebKit (Safari bugs show only in WebKit). After editing phone CSS, also check the story cards.
- Commits: author `dvdtdrv <dvdtdrv@users.noreply.github.com>`, NO Co-Authored-By / Claude-Session trailers.
  `git -c user.name=dvdtdrv -c user.email=dvdtdrv@users.noreply.github.com commit ...`. Never rewrite history or
  force-push main. Push only what David agreed to.
- After a change: add a short dated line to the right section here (or to docs/HISTORY.md if it is detail).
- `sync_from_github.bat` does `git reset --hard origin/main`: it wipes uncommitted edits in this folder. Commit
  and push before David runs it. It replaces itself while running, so its last steps sit in one ( ) block, and
  .gitattributes gives all .bat files Windows line endings (an LF .bat printed "'igin' is not recognized", 23 Nov).

## Where Claude Code runs (since 23 Nov 2026)
Either way the repo on GitHub is the source of truth: work on main's latest code, commit, push; Actions deploy.
- In the cloud (claude.ai/code): fresh clone; web requests come from a cloud server and only reach the sites allowed in
  that environment's network settings (outlet sites must be allowed there). The 5 `local` outlets refuse cloud servers.
  The PC, its runner and its files are not reachable from there unless the session is linked to the PC.
- On David's PC (folder Desktop\NewsReference, a clone of the repo; pushing needs his GitHub login, e.g. GitHub Desktop):
  - At the start of each session run `git pull` yourself (it keeps local edits; the sync .bat wipes them). David
    doesn't need to run sync_from_github.bat routinely; the runner uses its own copy of the code.
  - Python: `%USERPROFILE%\anaconda3\python.exe` (else `python`), with `PYTHONIOENCODING=utf-8`. Node is needed for
    Pagefind/Playwright; Playwright browsers may need `npx playwright install chromium webkit` the first time.
  - Every web request made here comes from David's HOME connection, the same one outlets can block (BG On Air did).
    Fetch outlet pages slowly and only when needed; never loop over many article pages from here.
  - The self-hosted runner (C:\Users\david\actions-runner) runs on this same PC: don't stop it or edit its folder.
  - The AI model for matching.py did not install on this PC, so a local group_stories.py run joins nothing and its
    stories differ from the live site. Real data comes from the `data` branch, not from local runs; don't push data.
  - `run_all.bat` (collect + group + build locally) is old and writes local data only; GitHub is the real pipeline.

## Hard rules
- Headline, short summary, link and the outlet's photo only; never full article text (copyright).
- Never bypass an outlet's firewall: never pass a Cloudflare/JS challenge, no proxies, no other IPs, no fake
  browsers beyond what an outlet allowed. Respect robots.txt and crawl-delay. Reading public pages in David's
  browser for research is fine.
- Be gentle with David's home connection (BG On Air blocked it on 21 Nov after ~230 fast page loads):
  link_check PC_PER_OUTLET 40, PC_PAUSE 5 s, GIVE_UP 3. Don't raise these.
- Never type passwords or tokens. Never approve workflow runs from fork pull requests.
- No cookies, no third-party fonts/scripts (fonts are our own files in web/). Don't turn on Cloudflare Bot Fight
  Mode / Under Attack / Turnstile (they set cookies; the legal page promises none).
- Outlet spectrum / left-right classification is ON HOLD (David, 21 Nov): nothing about it on the site without asking.
- Outlet info (`outlets_info.json`): verify every claim against its source and link it; label claim vs established,
  who says it, the other side's answer; for each attacker also show their documented ties; never call an attack a
  lie unless a court/record shows it; no private donors' names, no documents with ЕГН; paywalled sources end in
  "(платен)"; no notes about our own access problems. Read scanned figures twice, zoomed. "facts" rows = audited
  figures only; update text and facts together when a new annual report appears.
- No Google News RSS (robots disallows). English-language outlets are left out (grouping is Bulgarian-only).
- Permissions: BTA allowed its feed at most once per 30 min (31 Oct); bTV allowed reading for this student project
  (1 Nov). Neither covers commercial use, photos or attribution: ask both again before the site earns money.

## How it works
1. `collect.py` reads the outlets in `feeds.py` (RSS, news sitemaps, News.bg's /latest page) -> 7-day
   `data/articles.json` + permanent `data/articles/YYYY-MM.json`; page photos (og:image, cache data/page_images.json).
   `versions.py` merges renamed articles (headline history -> "Заглавието е сменяно N пъти" + the headline-change
   ranking under „Медии"). `limits.py` = hard time limit per web request.
2. `link_check.py` re-opens each article ~3 h, 12 h, 1.5, 3, 7, 14, 30 days after publishing: deleted articles (two
   "gone" answers 6 h apart; a page still showing our headline is alive; bump `RULES` when rules change) and, via
   `headline_watch.py`, silent headline changes (confirmed only when the next look shows it too). BTA, Dnevnik,
   Capital pages are never opened.
3. `group_stories.py`: TF-IDF on character 3-5 grams, average linkage, SIMILARITY 0.35, 48 h window, 2+ outlets per
   story -> `data/stories.json` + `data/stories/YYYY-MM-DD.json` (Sofia start day; updates for 36 h, then frozen; saved
   stories never shrink). `matching.py` then joins stories that are one event in other words (AI model
   paraphrase-multilingual-MiniLM-L12-v2, GitHub only; rules: meaning >= 0.70, party-only names >= 0.80, wording >= 0.30,
   12 h, shared name/place, no conflicting places from `places.json`; log in data/merge_log.json).
   `corrections.json` = hand fixes of saved stories (applied once each).
4. `build_site.py` + `site_template.html` (all CSS + JS of every page) -> `site/`: front page (index), medii.html,
   arhiv.html + archive days, tarsene.html (Pagefind search, `build_search.mjs`), pravila.html (legal), support page,
   outlets.json, feed/*.json („Всички новини": one file per hour + feed/o-NAME.json per outlet, 23 Nov: picking DW
   took 38 s, now 0.2 s), periods/*.json, sitemap.xml, robots.txt. `no_photos.json` = outlets
   whose photos must not be shown. `SMALLER_PHOTOS` (24 Nov) asks 6 outlets' own image servers for a smaller copy
   of the same photo (Vesti.bg, BNR, BNT, PIK, Novini.bg, Euronews BG); the full one stays as image2 (fallback). `geo_bg.json` = map + towns for the first-screen graphics. Heavy data
   (outlet info, totals, headline changes) goes only to medii.html/outlets.json (`MEDIA_ONLY`), keeping the front page
   light. The front page holds only the 40 stories of its first view (most covered, 24 h); the other 48 h stories are in
   stories-48h.json, loaded in the background (23 Nov: 2.7 MB -> 0.65 MB; `split_front_stories` must count like
   `periodItems` in the template). `SITE_URL` gives each page its canonical address. `seed/` = starting data for a first run on an empty branch.
5. Data lives on the `data` branch (force-replaced each run):
   `git fetch https://github.com/dvdtdrv/NewsReference.git +data:refs/remotes/d/data`.
6. Blindspot rule: an outlet is listed under „Не отразиха" only if we read it in the last 3 h AND our archive of it
   reaches back before the story began, so an outlet we couldn't read is never falsely called silent.
7. Headline-change kinds (minor / update / live / major, `versions.change_kind`) feed the ranking under „Медии" with a
   legend on the site; silent changes can signal pressure, so precision beats speed (two looks before recording).

### Workflows (.github/workflows)
- `update.yml`: collect + group + build + deploy (~every 30 min: started by the PC relay; hourly cron at :37 as backup).
- `local-fetch.yml`: runs on David's PC (self-hosted runner `david-pc`, C:\Users\david\actions-runner, starts hidden at
  login via start_runner.bat). `fetch_local.py` reads the `local` outlets (bTV, Trud, Blitz, Marica: Cloudflare challenge;
  Bloomberg TV: own 403 - they refuse GitHub's servers), their due link checks and the photos/link checks of
  `photos_on_pc` outlets (BG On Air, Euronews BG), uploads an artifact, dispatches update.yml. Used if < 75 min old.
  When the PC is off, the feeds are too short to cover the gap: `catchup.py` (23 Nov) reads back the last 24 h each
  round (Marica 72 h, its sitemap reaches ~3 days): Marica + Blitz from their Google News sitemaps (headlines included, 1 request); bTV + Bloomberg TV from sitemaps
  without headlines, opening <= 10 missed article pages per outlet per round, 5 s apart, only links not in GitHub's
  data/known_local.json. Read-back articles are only added, never counted as renames. Trud's sitemap already reaches ~4 days.
  bTV's sitemap lists only ~30 links: after a PC gap > 2 h it also reads pages 1-3 of its sections (България, Светът,
  Предавания; probe_btv_pages.py showed they page back ~1 day per 1-2 pages). Deep catch-up once by hand: run
  local-fetch.yml with deep = 1 (7 days, section pages stop by date, <= 100 article pages per outlet); an outlet stops after 5 pages without a usable headline/date. While a round works (after its wait), a hidden helper started by local-fetch.yml asks Windows
  not to sleep until the job ends (24 Nov: deep runs were cut off, "runner lost communication", once right after
  fetch_local.py ended); it can't wake a sleeping PC.
  A deep run has its own concurrency group, so regular rounds wait for it instead of cancelling it (24 Nov). Articles older
  than ~36-48 h reach the archive, „Всички новини" and search, but not their (frozen) stories.
- `rebuild.yml`: pages + search only from saved data (~1-2 min); runs on push to site_template.html, build_site.py,
  build_search.mjs, outlets_info.json, web/**, geo_bg.json, no_photos.json. If it fails with "deployment_queued":
  `gh workflow run rebuild.yml --ref main`.
- By hand only: `probe-outlets.yml` (can GitHub read the local outlets now?), `probe-catchup.yml` (PC, 23 Nov: how far
  back can each local outlet's robots-named sitemaps / feed page 2 reach? `probe_catchup.py`, <= 8 requests per outlet), `headline-audit.yml` (PC: opens every
  archived page of ONE outlet once, uploads a report, changes nothing; `recheck.json` makes chosen links due once),
  `probe-images.yml`.

### Testing a page change locally
Get the data branch into `data/`, run `python build_site.py`, serve `site/` (`python -m http.server 8765`), check with
Playwright (Chromium + WebKit; devices 'iPhone 15 Pro', 'iPhone SE'; computer 1280x720 and 1920x960). Search works only
over http(s), not file://.

## Design (current)
- Colours: egg-white `--paper`, darker `--paper-deep` on top, `--muted #5C5965`, `--live #B42318`. Content width
  `--max: 1340px` (23 Nov; 1240 had too much margin on 1920 px screens, 1440 too little).
- Fonts (own files, OFL, web/README.md), with BULGARIAN letter shapes since 24 Nov (philologists: the old ones were
  Russian-only; David chose option A): Sofia Sans Extra Condensed (labels/numbers, was Oswald), Sofia Sans (body, was
  Golos Text), Roboto Serif narrow (big page titles „Една новина." + grey italic „Всички медии.", was Noto Serif Display),
  Source Serif 4 SemiBold (story headlines, was Noto Serif), Kalam Light (footer motto „Jesus Christ is the greatest of
  all time."; Light since 28 Nov). Footer bottom line: just „© 2026 News Reference" (28 Nov, David; the
  „headlines and photos belong to the outlets" note stays on „За проекта" and pravila.html). Weights matched to the old stroke thickness, size-adjust to the old letter heights.
  Big numbers use proportional digits (David, 24 Nov: the equal-width ones sat too far apart). Any new font must have
  Bulgarian forms (GSUB locl cyrl:BGR, or Bulgarian by default like Sofia Sans).
- Header on computers (> 860 px): Медии, Архив | NEWS REFERENCE | search, „Подкрепи" pill. „За проекта" lives in the footer.
- Front page first screen: title, stats (медии / истории in the whole archive / статии, numbers like 73 028), the pulse
  (articles per hour, 24 h), tabs „Медиите днес" (outlet wheel) / „Къде е новината" (map). Sizes follow window height;
  `body.hero-tall` turns off the sliding stage when it doesn't fit.
- Stories on computers: one sliding row of all articles with ‹ › buttons, rounded photos, „Всички N статии" opens the grid,
  the order menu („От първата / последната статия") jumps the row back to its start (24 Nov),
  „Не отразиха" list, „↑ +N медии за последния час" when 2+ outlets joined in the last hour.
- Phones (<= 480 px): article list (84 px photo left), one-line title, „Какво е това? +" button, „В числа" and pulse boxes,
  „Не отразиха +" opens on tap. Installed app: pull down to reload. Own rounded menus (`makeMenu`) replace <select>.
- The outlet window (click any outlet name) shows totals, „Накратко" facts, outlet info with folded sources.
- „Медии", headline-change legend: the two notes under „Как се класифицира една смяна" are folded behind a round
  „!" next to the heading (28 Nov).

## Domain, hosting, accounts
- newsreference.bg: bought at Jump.bg (David owns it), renews 17.11.2027 (29.60 EUR/yr). DNS at Cloudflare (David's
  free account; nameservers chip/vida.ns.cloudflare.com): A/AAAA to GitHub Pages, www CNAME, all proxied, SSL Full +
  Always HTTPS. Custom domain set in the repo's Pages settings; the old github.io address forwards. Never remove the
  custom domain while Cloudflare is not Active (it once redirected the whole site to a dead address).
- Google Search Console (Domain property) and Bing are David's.
- Support page: 0,99 EUR/month promised, no payments built yet (ask BTA/bTV first, see Hard rules).

## Open problems
- PC off/asleep = lost articles from the PC outlets (71% of the time 3-23 Nov). Catch-up reading (23 Nov) recovers the last
  24 h after the PC wakes; longer gaps still lose the oldest part. Other fixes: PC never sleeps; outlets allowing
  `NewsReferenceBot` (David emailed them; bTV allows reading but can't change Cloudflare - its click-the-check suggestion
  was declined). Paid server dropped (cost; data centres get the same challenge).
- Grouping misses paraphrased single articles; few business outlets.
- Re-clustering can put one article into two archived stories; 7 story ids are on two archive days.
- Club Z quotes show as ";". „Заглавието е сменяно" note is hover-only (not tappable on phones).
- Search index grows ~850 B/record: Pages' 1 GB limit in about a year.

## Waiting for David's decision
- Phone wheel: 4a ranked list or 4b bigger wheel with top 12 named; smaller back-to-top button; tappable headline note.
- A 1200x630 share image (social previews use the app icon now). Submit sitemap.xml in Google Search Console.
- Ad videos (Desktop\NR - advertisement\NR_advertisement; 10 vertical videos, code in 2_video_code, make_videos.bat):
  music still open (David may pick a track). Ads never use outlets' photos or footage.
  24 Nov: new promo video planned (David sends materials). `.claude/settings.json` enables the Lemo-Opuscar plugin
  (lemomo-ai/lemo-opuscar: films made in code; films we make are ours, commercial use OK; needs ffmpeg 7+).
  25 Nov: promo „Искал ли си да бъдеш тук…" (David's own nature clips in private repo dvdtdrv/nr-promo + city ->
  flood of real headline cards WITH outlet photos (David decided 25 Nov: allowed as snapshots of the site; was "never")
  -> the site animated on a phone -> logo). 58.3 s, 1080x1920, text + no-text versions; David records the Bulgarian
  voice. Music: Vivaldi Summer i (0-21.6 s) + Summer iii Presto + Spring i, John Harrison with Wichita State Univ.
  Chamber Players (archive.org, CC BY-SA 3.0: credit in the post; Spotify can't be used). Lemo-Opuscar styles rejected.
  25 Nov v4 (59.8 s): Rila/sea/lake -> train fields („тук." on the first card) -> storm on Summer i's climax -> Spring:
  live pulse wave, turning wheel, map taps, Коцев story scroll, Медии (BNT window + headline-change ranking), search.
  Everything (code, captures, music, David's clips, all MP4s v1-v4) is in dvdtdrv/nr-promo; README has voice timings,
  build.sh rebuilds it. David still records the voice.
- BG On Air email if it keeps blocking his home connection.

## Next steps
1. Watch catch-up reading (23 Nov) for a few days: outlet_status notes say "catch-up: N ...".
2. More outlets (check feed + robots first): BGNES, Telegraph, Monitor, 168 Chasa; business: Pari, Economic.bg,
   Investor.bg, Profit.bg, Forbes Bulgaria; Trafficnews (Plovdiv); Bivol, Toest.
3. Better grouping (embeddings for single articles; Haiku to confirm proposed joins), then a „Бизнес" filter.
4. Fix Club Z quotes; tappable old-titles note.
5. Later (ask first): LLM summaries per story, "copied from the wire" indicator, outlet spectrum (on hold).
6. Before earning money: ask BTA and bTV about commercial use, photos, attribution.

## Useful references
- Commercial Register: `https://portal.registryagency.bg/CR/api/Deeds/<EIK>` (JSON), documents `/CR/api/Documents/<token>`
  (often scans: render pages and read them; Bulgarian OCR: tesseract + bul.traineddata). Also uic.bg/<EIK>, cem.bg,
  СЕМ penalty orders (cem.bg/controlsbg/13), sigma.midt.bg contracts, cik.bg. Some open only in David's own browser.
- Outlet quirks (News.bg relative times + crawl-delay 10, Novini.bg late og:image, Marica photo URLs, Moreto JS
  challenge and windows-1251, Fakti's og:image sometimes missing -> feed photo): see docs/HISTORY.md "Reference".
- Contact on the site: newsreference.contact@gmail.com. Legal page promises: removals in 72 h, corrections in 7 days,
  replies published next to the claim; update „Последна промяна" when its text changes.
