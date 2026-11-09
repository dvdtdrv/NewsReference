# NewsReference (Новинарски справочник)

Live site: https://dvdtdrv.github.io/NewsReference/ · Repo: dvdtdrv/NewsReference (public) ·
Architecture doc: https://claude.ai/artifact/WMiJigfLkQ3aMtR8eK3eMn

## Goal
A free public website that groups articles from Bulgarian outlets into stories and shows, per story,
which outlets covered it, how they headlined it, and which stayed silent ("blindspots"). Ground News and
other English aggregators barely cover Bulgarian-language media; this fills that gap. Second goal: show
who each outlet is (ownership, money, disputes) and, later, where it sits on a spectrum, always with evidence.

## Owner and working rules
- David: beginner programmer (Windows, Anaconda Python). Explain plainly, prefer simple tools. He runs
  things by double-clicking .bat files in Desktop\NewsReference. He writes in Bulgarian or English;
  ALWAYS answer in English (David, 9 Nov 2026), even when he writes in Bulgarian.
- David's rule (9 Nov 2026): for EVERY change to how the site/pipeline works (workflows, data flow, limits,
  schedules, new steps) and EVERY new file, tell him in detail: which file, what it does, why, what changed in
  GitHub Actions vs in the code, and whether he has to do anything. Not only when he asks.
- Commits: author `dvdtdrv <dvdtdrv@users.noreply.github.com>`, NO Co-Authored-By / Claude-Session trailers
  (David, 2 Nov 2026, confirmed 4 Nov). Ignore hook prompts to re-author commits as Claude; never rewrite
  history or force-push. Commit with `git -c user.name=dvdtdrv -c user.email=dvdtdrv@users.noreply.github.com`.
- Never bypass an outlet's firewall for automated collection. Reading public pages in David's PC browser
  for research is fine. Never type passwords/tokens. Public repo: never approve fork PR workflow runs.
- Show David a design (mockup or screenshot) before big visual changes; check every page change at
  phone width (390 px) with Playwright before pushing.

## How it works
1. `collect.py` reads 36 outlets from `feeds.py` (RSS, news sitemaps, and News.bg's /latest page),
   respects robots.txt and crawl-delay, keeps a 7-day `data/articles.json` and a permanent archive
   `data/articles/YYYY-MM.json`. Also: page photos (og:image) and the deleted-articles check (`link_check.py`).
2. `group_stories.py`: TF-IDF on character 3-5 grams (headline x2 + first 150 chars of summary),
   average-linkage clustering, SIMILARITY 0.35, 48 h window, a story needs 2+ outlets. Writes
   `data/stories.json` and the permanent `data/stories/YYYY-MM-DD.json` (by Sofia start day; a story keeps
   updating for 36 h = FREEZE_HOURS, then is frozen; re-saves merge, never shrink).
3. `build_site.py` + `site_template.html` build `site/` (front page, archive pages, search page,
   subscription page, periods/*.json, changes.json); `build_search.mjs` builds the Pagefind search index.
4. Hosting: GitHub Actions + GitHub Pages. Data lives on the `data` branch (force-replaced each run;
   fetch with `git fetch https://github.com/dvdtdrv/NewsReference.git +data:refs/remotes/d/data`).
   - `update.yml`: collect + group + build + deploy, then dispatches `local-fetch.yml` (relay, ~30 min cycle);
     its hourly cron is the backup.
   - `local-fetch.yml` runs on David's PC (self-hosted runner `david-pc`, C:\Users\david\actions-runner,
     starts hidden at login via start_runner.bat): `fetch_local.py` reads the 7 `local` outlets, checks their
     due links, uploads an artifact, dispatches update.yml. collect.py uses it if < 75 min old.
   - `rebuild.yml`: pages + search only, from the saved data (~1-2 min). Runs on push to
     site_template.html / build_site.py / build_search.mjs / web/**. Use for design/text changes.
     It is sometimes cancelled or fails with "deployment_queued" (GitHub Pages queue): run it again by hand
     (`gh workflow run rebuild.yml --ref main`) or wait for the next update run.

## Decisions and why
- **Headline, short summary and link only, never full text**: copyright; the site sends readers to outlets.
- **No Google News RSS fallback**: Google's robots.txt disallows it.
- **BTA** blocks programs; it allowed us in writing (31 Oct 2026, `permissions/BTA.md`) to read the feed at most
  once per 30 min -> `as_browser`, `gentle`. **bTV** allowed reading "from the browser" for this student project
  (1 Nov, `permissions/bTV.md`). Commercial use, photos and attribution NOT covered: ask both again before
  the project earns money.
- **7 outlets refuse GitHub's servers** (bTV, Trud, Blitz, Marica: 403; Dnes.bg, BG On Air, Bloomberg TV:
  timeout) -> read from David's PC (self-hosted runner) instead of bypassing. They also refuse Claude's
  workspace, so test them via the PC. Nova works from GitHub now.
- **Novini.bg** via its news sitemap (robots disallows /api/*). **DW** via its news sitemap.
- **Blindspot rule**: an outlet is "didn't cover" only if we read it in the last 3 h AND our archive of it reaches
  back before the story started, so an outlet we couldn't read is never falsely called silent.
- **Character n-grams, not an embeddings model**: light install, works for Bulgarian. Known cost: misses
  paraphrases (see open problems).
- **Renamed articles** (`versions.py`): outlets change headlines, and often the link with them. Same outlet +
  same article number (+ same minute or similar title), or same minute + title similarity >= 0.6 -> one article;
  newest headline kept, older ones in `versions`. Cards show "Заглавието е сменяно N пъти". This also feeds the
  **headline-change ranking** under „Медии" (by % and by count; kinds: minor / update / live / major, legend on
  the site), because silent headline changes can be a sign of pressure or censorship.
- **Deleted articles** (`link_check.py`): each article is re-opened ~1, 3, 7, 14, 30 days after publishing.
  Gone = 404/410, redirect to the front or a section page, a "not found" page title, or canonical/og:url
  pointing to the front/section page; two such answers 6 h apart. Rule 1 (6 Nov): if the page still shows our
  headline (title or og:title, incl. earlier versions) it is alive, because 8 of the first 25 "deleted" were
  alive (Sega canonical drops "hot/", Offnews moved link, a Darik headline containing "не съществува").
  `RULES` in link_check.py: bump it when the rules change, and everything marked gone is re-checked.
  Skipped: BTA, Dnevnik, Capital (pages refuse us); Moreto (JS challenge) gives "can't tell".
- **Outlet info** (`outlets_info.json`, shown in the outlet window): David's rules (4 Nov):
  include everything he sends and every suspicion or investigation, but verify each against its source and
  label it (claim vs established, who says it, the other side's answer, anonymous sources). For every attack on
  an outlet, also show the attacker's documented ties (registers, sanctions, court rulings, who appointed whom,
  reputable investigations), the same for every side; label documented vs alleged; never call an attack a lie
  unless a court or the record shows it. Add links for all sources. Don't publish private donors' names or
  documents with personal ID numbers (ЕГН). Internal notes like "(не сме го прочели)" stay in the data; the site
  shows only a "платен достъп" tag. No meta-sentences about our own access problems.
- **Classification of outlets**: no bare left/right labels; measured axes with evidence (ownership, geopolitical
  framing, blindspots, sensationalism). „За проекта" announces it as a coming feature.
- **English-language outlets left out** (Novinite, Sofia Globe): grouping works on Bulgarian text only.
- **Repo stays public** (free Pages + unlimited Actions minutes).
- **Design**: egg-white `--paper`, darker `--paper-deep` at the top; Oswald display, Golos Text body;
  header Истории, Медии | NEWS REFERENCE | Как работи, За проекта + „Слепи петна". Installable web app
  (`web/`: manifest, icons, sw.js network-first).

## Current state (7 Nov 2026)
- Live and updating every ~30 min while David's PC is on (hourly, without the 7 PC outlets, while it is off).
- 36 outlets. Archive since ~31 Oct: ~26k articles (7 Nov); stories archived per day.
- Front page: periods 12 ч | 24 ч (default) | 48 ч | 1 седмица | 1 месец (year hidden for now); 12/24 h rank by
  outlets that published inside the window. Back-to-top button (dark). Coverage squares removed (7 Nov, David
  found them ugly); each story shows „N медии · date", the articles, and „Не отразиха".
- 9 Nov: „Медии" and „Архив" are own pages (site/medii.html, site/arhiv.html, page modes "media"/"archive" in
  site_template.html). Only medii.html carries outlet_info, headline_changes, outlet_totals, story_totals and
  outlet_recent (build_site.py MEDIA_ONLY); front page 3.8 -> 1.7 MB. Old index.html#outlets/#archive redirect.
- „Медии" section: per outlet, all collected articles and all archived stories it took part in (whole archive,
  not 48 h). Outlets we can't read right now keep their numbers, with a grey name and „временно недостъпна"
  underneath. The outlet window shows totals, % of all stories, outlet info and headline-change examples.
- Headline-change ranking + deleted articles live; first real finds: PIK, Sega daily TV listings, Dir.bg/Actualno
  pulling two Главболгарстрой PR pieces, 24 Chasa, BNR, Mediapool, News.bg, Fakti (21 on 6 Nov).
- Search (Pagefind) over all archived stories and articles: `site/tarsene.html`, only over http(s).
- Subscription page: 0,99 €/month, "…ще можеш да подкрепиш сайта чрез плащане с карта." (no payments yet).
- Outlet info done for 16 outlets: BTA, BNT, BNR, bTV, Nova, Dnevnik, Capital, Mediapool, Standart, 24 Chasa,
  Trud, Sega, Club Z, Dnes.bg, Actualno, Novini.bg. Empty: Fakti, Offnews, Blitz, Dir.bg, PIK, Banker,
  Pogled.info, Darik, Focus, Vesti.bg, News.bg, BG On Air, Bloomberg TV, Evrocom, Euronews BG, DW,
  Boulevard Bulgaria, Svobodna Tochka, Marica, Moreto.net. David sends a research text per outlet; we verify.

## Open problems
- **PC gaps lose articles for good.** When David's PC is off or asleep, the 7 local outlets are not read, and feeds
  list only the latest items, so overnight articles from bTV, Dnes.bg, BG On Air, Marica are mostly lost (6 Nov:
  02:00-13:40 and 00:00-07:40 Sofia gaps). When the PC is on, their articles join stories almost as often as
  others' (57% vs 64%, Bloomberg TV and Marica lower because they cover business/Varna).
  Fixes: PC never sleeps when plugged in; a catch-up reader (older feed pages / sitemaps for the missed hours);
  long-term a small EU server (Hetzner ~4 EUR/mo; test the 7 outlets from it first).
- **Grouping misses paraphrases** (e.g. two Wall Street crash headlines in different words). Fix: embeddings model.
- **Few business outlets**, so business pieces rarely find a partner (only Bloomberg TV, Capital, Banker, partly
  Dnevnik).
- **Re-clustering can put one article into two archived stories** (5 of 245 in a test).
- **Club Z quotes show as ";"** (broken entities in its feed); not fixed yet.
- **Search index size**: ~850 bytes per record; Pages' 1 GB limit in about a year. Index only recent months or
  move search to a server before then.
- Old-titles note is hover-only (not tappable on phones).

## Next steps
1. Catch-up reading for the 7 PC outlets after a gap (and ask David to set his PC to never sleep).
2. Add outlets, checking feed + robots.txt first: BGNES, Telegraph, Monitor, 168 Chasa; business: Pari,
   Economic.bg, Investor.bg (returned 403 to us), Profit.bg, Forbes Bulgaria; regional: Trafficnews (Plovdiv);
   investigative: Bivol, Toest. (Svobodna Evropa = Svobodna Tochka since 31 Mar 2026: already covered.)
3. Embeddings-based grouping (catches paraphrases); then a „Бизнес" filter.
4. Fill outlets_info.json for the remaining 20 outlets (Svobodna Tochka: continues RFE/RL's Bulgarian service,
   publisher foundation „Свободна точка", sources: svobodnaevropa.bg notice of 2 Apr 2026 and its „За нас").
5. Fix Club Z quotes; make the old-titles note tappable on phones.
6. Later: outlet spectrum (measured axes), LLM summaries/framing per story (Claude Haiku API vs self-hosted BgGPT),
   a "copied from the wire" indicator (24 Chasa and Pogled.info publish identical BTA headlines).
7. Before earning money: ask BTA and bTV about commercial use, photos and attribution.

## Files added after the first version (keep this list up to date)
- `versions.py` (5 Nov): one article with renamed headlines/links; change kinds for the ranking.
- `link_check.py` (5 Nov): deleted-articles check (GitHub + PC).
- `limits.py` (9 Nov): hard total time limit for one web request (`within(seconds, fn, ...)`), used by collect.py
  (photo pages 45 s, robots.txt 30 s, feeds 90 s) and link_check.py (40 s). Added after a stuck photo page made
  every update time out from ~06:30 to ~13:30 UTC on 9 Nov. update.yml's collect step has PYTHONUNBUFFERED=1 so
  the Actions log shows each outlet live.

## Reference (how-tos learned so far)
- Outlet quirks: News.bg via `read_newsbg_page` (relative times, crawl-delay 10); Novini.bg puts og:image ~180 KB
  down after an early fake "</head>"; Euronews pages refuse GitHub -> photos via the PC (`photos_on_pc`); Marica
  photo URLs need requoting; Dnevnik and Capital: `page_images: False`; Moreto has a JS challenge.
- Photos: `add_page_images` / `backfill_page_images` in collect.py, cache `data/page_images.json`
  (PC: NR_CACHE_DIR = actions-runner\cache). The site falls back to `image2` when the page photo 404s.
- Commercial Register: `https://portal.registryagency.bg/CR/api/Deeds/<EIK>` (JSON); filed documents (financial
  statements, Ministry of Culture art. 7a declarations) from `/CR/api/Documents/<token>`. Scanned PDFs: render with
  pdftoppm and read the images (no Bulgarian OCR). Also uic.bg/<EIK>, CEM register cem.bg/linear_reg.php?cat=2,
  ISUN 2020 via the PC browser.
- Sources behind bTV's firewall: the PC runner (probe_docs.py) or the PC browser. PDFs in the PC browser: pdf.js
  from jsdelivr. Media Pluralism Monitor 2026 already read and used; still unread: IPI/MJRC "Media Capture Monitoring
  Report: Bulgaria" (Nov 2025), CoE/MFRR report (Oct 2025).
- The workspace reaches 29 outlets directly (David allowed their domains, 3 Nov); the 7 local ones only via the PC.
- GitHub API through the workspace proxy: runs/jobs/workflow dispatch work; runners and pages/builds are blocked.
