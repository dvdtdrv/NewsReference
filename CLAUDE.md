# NewsReference (Новинарски справочник)

Live site: https://newsreference.bg (since 21 Nov 2026; the old https://dvdtdrv.github.io/NewsReference/ forwards there) · Repo: dvdtdrv/NewsReference (public) ·
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
- **BTA** blocks programs; it allowed us in writing (31 Oct 2026; email + note kept by David, not in the repo) to read the feed at most
  once per 30 min -> `as_browser`, `gentle`. **bTV** allowed reading "from the browser" for this student project
  (1 Nov; email + note kept by David, not in the repo since 18 Nov). Commercial use, photos and attribution NOT covered: ask both again before
  the project earns money.
- **5 outlets refuse GitHub's servers** (bTV, Trud, Blitz, Marica: Cloudflare challenge 403; Bloomberg TV: its own
  403) -> read from David's PC (self-hosted runner) instead of bypassing. 21 Nov 2026: Dnes.bg and BG On Air answered
  GitHub 4/4 (probe-outlets.yml) and were moved back to GitHub (no `local`); BG On Air's article pages still refuse
  GitHub (403), so it is `photos_on_pc` (PC sends photos AND, since 21 Nov, does its deleted-articles check, like
  Euronews BG: link_check.due_articles treats photos_on_pc as PC). bTV answered GitHub 2 of 4 times: not moved.
  To re-test: run "Test PC outlets from GitHub" (probe-outlets.yml + probe_outlets.py, by hand only; reads each local
  feed + one article page). Nova works from GitHub (its feed was empty for a few hours on the night of 20-21 Nov).
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
  documents with personal ID numbers (ЕГН). No "(не сме го прочели)" notes on sources (David, 17 Nov: all 326 removed); a paywalled source
  ends in "(платен)" and the site shows it as a "платен достъп" tag. No meta-sentences about our own access problems.
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
- **Grouping misses paraphrases**: partly fixed 10 Nov by joining stories (matching.py); single articles in other words still stay out.
- **Few business outlets**, so business pieces rarely find a partner (only Bloomberg TV, Capital, Banker, partly
  Dnevnik).
- **Re-clustering can put one article into two archived stories** (5 of 245 in a test).
- **Club Z quotes show as ";"** (broken entities in its feed); not fixed yet.
- **Search index size**: ~850 bytes per record; Pages' 1 GB limit in about a year. Index only recent months or
  move search to a server before then.
- Old-titles note is hover-only (not tappable on phones).

## Next steps
0. Domain + hosting (agreed with David 18 Nov 2026). DONE 21 Nov ~01:20 Sofia: newsreference.bg is live (Cloudflare -> GitHub Pages),
   domain verified on GitHub, custom domain set in the repo (it needed one rebuild.yml run; the browser had cached GitHub's 404).
   www.newsreference.bg forwards to newsreference.bg. Checked: no cookies are set (keep it so: do NOT turn on Cloudflare's Bot Fight
   Mode, "Under Attack" or Turnstile without updating the cookie section of the legal page). Legal page hosting sentence now names
   Cloudflare (Последна промяна 21 ноември 2026). Cloudflare "Recommendations" asks for email records (SPF/DMARC "no mail"): optional.
   Paid server dropped for now (David, 20 Nov: too expensive; the 5 Cloudflare/Bloomberg outlets refuse any data centre anyway):
   site stays on free GitHub; the PC reads the 7 when it is on; David emails the outlets (universal text in the chat: NewsReferenceBot
   User-Agent skip rule / separate feed address / secret token; open about future commercial plans). bTV replied it allows reading
   but cannot change Cloudflare and suggested a click-the-check script: declined (never pass the challenge); a reply with the three
   options was drafted. Feed depth measured 20 Nov evening: Trud sitemap 175 items = 7 days, bTV 51 = ~8.5 h, Blitz 51 = ~6 h,
   Bloomberg TV 10 = ~3.5 h, Marica 10 = ~2 h, BG On Air 10 = ~2 h, Dnes.bg 10 = ~1 h (Dnes.bg rss.php?today now redirects to /rss/latest).
   Old plan steps for reference:
   a. newsreference.bg bought at Jump.bg 17 Nov (29.60 EUR/yr, renews 17.11.2027, owner David); registered 20 Nov; Jump.bg
      DNS servers set to Cloudflare's two on 20 Nov ~14:45 Sofia (waiting for .bg to publish it, then Cloudflare "Active").
   b. Cloudflare (David's free account, domain already added): records A @ -> 185.199.108-111.153, AAAA @ -> 2606:50c0:8000-8003::153,
      CNAME www -> dvdtdrv.github.io, all Proxied (orange) - all 9 added 18 Nov; SSL/TLS "Full" + "Always Use HTTPS"; then Jump.bg
      DNS servers -> Cloudflare's two: chip.ns.cloudflare.com, vida.ns.cloudflare.com (DNSSEC off at Jump.bg).
   c. GitHub account Settings -> Pages -> verified domain: TXT _github-pages-challenge-dvdtdrv added in Cloudflare 20 Nov; press
      Verify only after Cloudflare is Active. THEN repo Settings -> Pages -> custom domain newsreference.bg. Never before Cloudflare is
      Active: on 18 and 20 Nov it 301-redirected the whole site to the dead domain (after Remove, GitHub's CDN kept the redirect
      ~15 min; a rebuild.yml run cleared it). All site links are relative: no code change.
      Then update the legal page (hosting sentence), CLAUDE.md, and optionally strip GitHub/Fastly headers with a Cloudflare rule.
   d. Hetzner test (20 Nov, CPX02 Nuremberg 91.98.0.184, project NewsReferenceTest): cloud-init text (kept in the chat, not in the
      repo) checks the 7 feeds + BNR/Nova every 30 min for 48 h and shows a page at http://<ip>/. Lesson: in cloud-init runcmd never
      put ": " inside a command (YAML turns it into a mapping and the whole runcmd is skipped). First round 17:06 UTC: Dnes.bg and
      BG On Air OK; bTV, Trud, Blitz, Marica 403 = Cloudflare bot challenge ("Just a moment", cf-mitigated: challenge; same from
      Claude's workspace) -> any data-centre server, Bulgarian VPS too, will most likely get it; Bloomberg TV 403 from its own
      Apache (blocks Hetzner, answers Claude's workspace). Hetzner prices (Nov 2026, incl. 20% VAT): CPX02 1 GB 0.010 EUR/h,
      CPX22 4 GB ~19.79/mo; Cost-Optimized (CX/CAX) "limited availability". Pipeline needs ~2 GB peak (group_stories + AI model,
      measured 18 Nov), so 4 GB for the real server.
   e. If good: move the whole pipeline to the server, make the repo private (private repo = no free Actions minutes:
      ~27,000 min/month would cost ~150 $/month), point Cloudflare's records to the server. If some of the 7 still refuse:
      PC (or a Raspberry Pi at home) keeps reading them, or ask those outlets to allow the server's fixed IP (on Cloudflare
      sites the owner can add a WAF skip rule for one IP). Never try to pass the challenge. No residential proxies.
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
- `matching.py` + `places.json` + `requirements-ai.txt` (10 Nov): after the normal grouping, stories that are one
  event told in different words are joined (the Trakia crash of 10 Nov showed as ~25 stories). Rule: meaning >= 0.70
  (AI model paraphrase-multilingual-MiniLM-L12-v2, run on GitHub only; update.yml installs it and caches it) AND
  wording >= 0.30 AND started within 12 h (whole joined story within 24 h) AND a shared name/place AND no different
  Bulgarian places/motorways (places.json = EKATTE settlements). Weather forecasts join only for the same day.
  Without the model (David's PC, failed install) nothing is joined. Fingerprints: data/embeddings.json; every join:
  data/merge_log.json (14 days) - review it to tune. Tested 5-10 Nov: ~2-3 wrong joins per 50-90 (same place, e.g.
  two plane stories at Ben Gurion); rejected designs: "story memory" (snowballed), rare-names-only (blocked big
  events), cross-encoder reranker (missed most). Next: let Haiku confirm only the proposed joins.
  12 Nov: a joined story's title = the headline closest in meaning to all its articles (best_headline), not its
  largest part's title. Publish jobs in update.yml and rebuild.yml: timeout 15 min, not 5 (slow Pages publishes were cut off).
- `limits.py` (9 Nov): hard total time limit for one web request (`within(seconds, fn, ...)`), used by collect.py
  (photo pages 45 s, robots.txt 30 s, feeds 90 s) and link_check.py (40 s). Added after a stuck photo page made
  every update time out from ~06:30 to ~13:30 UTC on 9 Nov. update.yml's collect step has PYTHONUNBUFFERED=1 so
  the Actions log shows each outlet live.

- „Всички новини" (12 Nov): third tab on the front page, every article of the last 7 days newest first, no grouping,
  no photos (David chose the plain rows). build_site.py `feed_files()` writes site/feed/YYYY-MM-DD-HH.json (one file
  per UTC hour, rows [time, outlet, headline, link, story id, outlets in story, archive day]); the page lists the
  files in `feed_files` and loads them one by one (60 rows per „Покажи още новини"). Filters: one outlet, only
  articles outside stories. Each row says „в история с N медии" (opens the story) or „само тази медия".
  An article stamped later than the moment we first read it (BNR: ~1 h ahead on most) shows that moment instead.
  No new workflow step.

- Outlet names are clickable (12 Nov): in story cards and in „Всички новини" a click on the outlet's name opens the
  outlet window from „Медии" over the page (`outletLink` / `showOutlet` in site_template.html). Its data comes from
  site/outlets.json (written by build_site.py: outlet_info, outlet_totals, story_totals, outlet_recent), fetched on
  the first click. Closing (×, Esc, click outside, or the browser's Back) leaves the reader where they were.
  From „Всички новини" a story opens with „← Обратно към „Всички новини"" above it; Back returns to the same row.

- Refreshing without closing the app (12 Nov): „обновено в HH:MM ↻" next to „Истории" reloads the page; a dark
  pill „Има по-нови новини · Обнови" (top centre, bottom on phones) appears when site/version.json (written by
  build_site.py, the time of the last update) is newer than the open page. Checked every 5 min and when the app
  comes back to the front. Not on archive day pages.

- Legal page and footer (12 Nov): site/pravila.html (page mode "legal" in site_template.html; the text is in the
  template, section #legal): За нас и контакти (Давид Тодоров, newsreference.contact@gmail.com), Условия, Поверителност,
  Бисквитки, Авторски права и премахване, Корекции и право на отговор. Promises made there: removal requests answered
  in 72 h (photos or the whole outlet switched off without arguing), corrections in 7 days, replies published next to
  the claim, emails kept at most 3 years. Dark footer on every page links to it. Update „Последна промяна" when the
  text changes. No cookie banner: the site sets no cookies and loads nothing from third parties except outlet photos.
- Fonts are our own files (12 Nov): web/oswald-*.woff2, web/golos-text-*.woff2 (from @fontsource, OFL), @font-face in
  the template with {{BASE}}. Never load fonts or scripts from Google or other third parties (GDPR: LG München 2022).
- `no_photos.json` (12 Nov): list of outlet names (as in feeds.py) whose photos must not be shown; read by
  build_site.py and build_search.mjs; rebuild.yml also runs when it changes. Empty now.

- Party-name rule (14 Nov) in matching.py: if the only shared name is a political party's (PARTIES: first 6 letters,
  e.g. "прогре" = Прогресивна България), the meaning must be >= 0.80 (PARTY_MEANING). „Прогресивна България" had joined
  the personal-assistants law with the party's reply to Kaufland (0.72-0.74); right party-only joins were 0.74-0.90.
- `corrections.json` (14 Nov): hand corrections of SAVED stories, applied once each by group_stories.py
  `apply_corrections()` (done ones in data/corrections_done.json). Needed because saved stories never shrink, so a
  wrong join stays in the archive. Fields: name, why, day, story (id), headline (new title of what stays), move (links
  that become their own story on their own start day), move_headline, drop (links removed). Each part gets the id of
  its own first article. First use: the 11 Nov story mixing personal assistants (97 kept) and Kaufland reactions (27).
  Use it for reader/outlet correction requests about grouping (promised on the legal page).
- Outlet info #24 Darik (15 Nov): dariknews.bg = „Нет Инфо“ ЕАД (Nova / United Group), NOT Дарик радио or Darik.bg;
  feeds.py type changed radio -> online portal. Net Info's art. 7a declaration (06.07.2026) lists 15 ad contracts (2025)
  for all its sites; read with tesseract + bul.traineddata (raw.githubusercontent.com/tesseract-ocr/tessdata_fast).
  Net Info 2026 rate card PDF is gone (404), prices left out.
- Outlet info #25 Focus (15 Nov): full text received. NOT yet added because unverified from the workspace: the 15 public
  contracts (~489k EUR, sigma.midt.bg/contracts?bidder=206912758 answers 500) and the CIK list for 19.04.2026 (cik.bg 403);
  check both in David's PC browser. Disputes added 15 Nov: Darik + Vesti (2019 Net Info shareholder clash, Христо Христов's
  claim of editorial interference), Focus (2019 missing 1.5M лв, 2022 closure reports, Налджиев's 'deliberate bankruptcy' claim).
  News.bg: none found; added previous owner Красен Кралев (2013). Still unread (paywalled): Capital 30.05.2019 on Net Info.
- Outlet info #26 Vesti.bg (15 Nov): same publisher as Darik (Net Info); shared sections copied, plus budget payments from uic.bg (also added to Darik).
- Outlet info #27 News.bg (15 Nov): Уеб Медия Груп АД (public company), 73.45% Ню Уеб Маркет -> ... -> Некст Дженерейшън Консулт; no natural person named. CIK tariff lists not checked (cik.bg 403).
- Outlet info #28 BG On Air (15 Nov): same publisher as Dnes.bg (Инвестор.БГ); ownership/money/Химимпорт sections reused from Dnes.bg; no disputes of its own found. bgonair.bg/p/advertisement was readable from the workspace this time.
- Deep sweep 15 Nov (scandals, censorship, manipulation, foreign influence) for Darik, Vesti, Focus, News.bg, BG On Air: nothing new beyond
  the disputes already added. Checked: CEM annual reports 2022/2024, CEM election report 2024, RFE on the CSD Russia report, Club Z on China,
  StopFake, Actualno, Bivol on ТИМ (none names these outlets). Not readable: Capital (paywall), Marginalia, Banker 18.09.2019 (403).
- Known: 7 story ids appear on two archive days (existing before 14 Nov); not fixed yet.
- Headline-change table under „Медии" (21 Nov, David): the four kinds are own columns (Дребни / Обнов. / Живо / Съществ.,
  coloured headers, 0 faded); every header is a sort button (first click biggest first / names А-Я, again reversed; aria-sort);
  "малко данни" rows stay at the bottom; the old „По процент / По брой" buttons are gone. Phones show all columns: the
  table scrolls sideways with the outlet name sticky on the left.
- Spreading label (21 Nov, David chose only this of the "live" ideas): story-meta shows „↑ +N медии за последния час" (red
  outline, `--live` #B42318) when 2+ outlets first wrote about the story in the last hour, counted on the reader's clock
  (`liveFlag()` in site_template.html; an outlet whose clock runs ahead counts as "now"; if the story began within the hour
  its first outlet isn't counted). Not on archive pages. A „Ново" badge was tried and dropped by David. Concept mockup of the
  other ideas (live strip with ticker, „Днес в числа", lead story with „Мълчаха" box, „Кой пръв" timeline, „Как го озаглавиха",
  3-column grid) shown 21 Nov as screenshots only; nothing of it is built yet.
- First-screen graphics (21 Nov, David chose "the wheel first, switch to the map" from several concepts): build_site.py
  `hero_data()` (front page only, ~16 KB, key `hero`) from the last 24 h: outlets in wheel order (greedy: busiest first,
  then the one sharing most stories with the last two), each one's article count and last article time (min of published
  and collected), the top 260 outlet pairs by shared stories, articles per hour (24 bars), and towns named in stories
  (`geo_bg.json`: Bulgaria's border from Natural Earth via world-atlas, public domain, projected to 640x415, plus ~60 towns
  with x/y and regex word forms) with one story whose own headline names the town. site_template.html draws it all as
  inline SVG (no libraries): tabs „Медиите днес" (wheel; dark name = wrote in the last hour by the reader's clock; hover/
  focus lights its lines red and names its top partner; click opens the outlet window) / „Къде е новината" (map + top 4
  towns; click opens the story via showStory). The pulse sits under the stats. body.has-viz switches the intro to
  title|viz / text|viz; phones stack. rebuild.yml also runs when geo_bg.json changes. Town list can grow in geo_bg.json.
- `probe_outlets.py` + `.github/workflows/probe-outlets.yml` (21 Nov): by-hand test whether GitHub's servers can read the
  `local` outlets (feed + one article page); no timer, changes nothing. Use it when an outlet says it allowed NewsReferenceBot.
- Search engines (21 Nov): build_site.py writes site/sitemap.xml (6 main pages + every archive day, lastmod) and
  site/robots.txt (Allow all + Sitemap line; Cloudflare prepends its AI "content signals" comments). Every page gets
  `seo_head()`: its own <title>, description, canonical https://newsreference.bg/<page> (so Google ignores the old
  github.io address), Open Graph + twitter:card (image = icon-512.png for now; a 1200x630 share image would look better).
  SITE_URL in build_site.py. Google Search Console (Domain property, verified via Cloudflare TXT 21 Nov) and Bing (import
  from GSC) are David's; the front page was submitted for indexing 21 Nov 01:40; submit sitemap.xml there.

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
- Outlet info #29 Bloomberg TV (15-16 Nov): „Инвестор ТВ“ ЕООД (201523151), 100% Инвестор.БГ; Bloomberg L.P. = licence only. Own 2025 figures from the
  group report (revenue 2,524k, net loss 2,018k лв). Ownership chain, money-flow, Химимпорт and 2013 dispute reused from BG On Air. No disputes of its
  own found. Left out: CIK list 9.03.2026 (cik.bg 403), undated general rate card.
- Outlet info #30 Evrocom (16 Nov): Телевизия Евроком ООД (121761999), Илчев 51% / Златев 49% (register). Latest annual report in the register is 2022
  (filed 28.06.2025; scanned, rotated - read as image): revenue 2,094k, loss 415k лв. Media packages (ИРПС), own 2026 contract list (98,437.50 EUR),
  uic.bg budget payments. Disputes: 2019 Barekov's paid show dropped, 2020 prosecution/DANS/NAP checks of advertisers, 2026 final ruling (Халваджиян).
  Left out as unverified: SIGMA contracts (500), Finansi/CompanyBook/EMIS percentages, 1996 start date (eurocom.bg/za-nas 403; its PDFs open).
- Outlet info #31 Euronews BG (16 Nov): Телевизия Европа АД (115568068), sole owner Добрин Иванов (via ДИПИ ЕООД); Euronews SA = brand licence only.
  2023 report (scanned; tables read as images): revenue 1,577k, loss 4,941k, debts to owner's group 18,015k, equity -14,558k; 2022 audit qualified.
  Disputes: 2023 resignations / who controls the news (RFE, AEJ, CEM report, Stoimenova Jan 2024), 2020 FinCEN/Bivol on the owner. Extra: Direkt36 on
  who paid for Euronews (Orbán circle). Left out as unverified: CIK decision 4804-НС on the April 2026 exit poll (cik.bg 403), 99%/1% split and
  Finansi percentages (finansi 403), joint statement text (sbj JS check; old euronewsbulgaria.com link now redirects) - CEM's report quotes it.
- Outlet info #32 DW (16 Nov): public-law institution, no owner; law (DWG), 2024 accounts, 2025 management report, Evaluationsbericht 2025 (Bulgarian
  service figures, partners Dnevnik/Dnes/Nova/Fakti). Disputes: 2013 Бедров/Барух after the КТБ letter, 2022 Arabic service dismissals + Russia ban,
  2026 cuts (Greek service closed). Not readable: bundeshaushalt.de (503), ebu.ch (403), bghelsinki.org (403).
- Outlet info #33 Boulevard Bulgaria (16 Nov): Публитикс Медиа ЕООД (201501023); founder Асен Григоров died May 2025, his wife Сибина Григорова is owner,
  manager and managing editor since 10.06.2025. 2023 report: revenue 835k, profit 91k лв. Political contracts 2026 only with Гюров-Кандев IC (2,989 EUR,
  PDF), ПП, ДБ (their PDFs 404). No disputes found. Left out as unverified: America for Bulgaria grant 38,330 лв (us4bg.org JS check - check in David's
  browser), Finansi percentages.
- Outlet info #34 Svobodna Tochka (16 Nov): foundation (208740798, public benefit, registered 20.03.2026, 30 EUR initial contribution); director Иван Бедров,
  second representative Ваксберг -> Делчева on 09.11.2026 (uic.bg history). Donor-funded, donors and sums not published. No disputes found; Bedrov's
  remark on early pressure attempts (kultura.bg interview) and the 2013 DW episode are in the independence section.
- Outlet info #35 Marica (16 Nov): ИК Марица ЕООД (115350662) <- Пресгрупа Утро ЕООД (117017845, since 20.01.2015) <- BG Privatinvest GmbH (Austria);
  Грозев + Хабсбург named by Club Z / Akcent / Dotbg, not visible in the register. Earlier owner ГМ Прес (КТБ credits, 2012-2015). НАП liens on the shares
  2020-21 and 2022-23; latest report filed is 2022. Disputes: Russian attacks on Grozev (ФАН 2021, wanted 2022), 2018 unsupported Peevski claim.
  NOT verified, left out (check in David's PC browser): Indzhov's study figures (590k / 436k лв; uni-vt.bg TLS error + robots), SBJ 12.06.2026 (JS check),
  SIGMA contracts with Община Пловдив (~208k EUR), North Data (429), marica.bg/reklama; register document downloads returned 500 on 16 Nov
  (2022 report and the 2019 art. 7a declaration not read - retry).
- Outlet info #36 Moreto.net (16 Nov): two companies - Морето ООД (148107340; Стефанов 50% / Петрова 50%) and Морето Нет ЕООД (208626887, registered
  29.12.2025, Петрова 100%; issues the 2026 election tariff and contracts, 10,605.54 EUR). НАП lien on Stefanov's share 02.12.2025 (uic.bg history).
  No disputes found. Not verified (JS check / robots): contacts and terms pages, audience figures, ВАС decision 6315/2026 on the moreto.bg trademark.
- 16 Nov: outlet info now filled for all 36 outlets. 17 Nov: the PC-browser checks are done and added (see below).
- Deeper sweep 17 Nov (David: scandals, lawsuits, convictions were not really investigated). Method that worked: СЕМ's published penalty orders
  (cem.bg/controlsbg/13, 14 pages, 272 PDFs, 2015-2026) downloaded to the scratchpad and parsed (pdftotext; EIK after "срещу", fine after "НАЛАГАМ").
  Counts: bTV 44 (323k лв), Nova 57 (372k), BNT 18, BNR 16, Evrocom 8 (39k), Телевизия Европа 8 (27k, all before the Euronews rebrand),
  Инвестор.БГ 2 (6k), Инвестор ТВ 0, Дарик радио 8 (not our Darik). Added as dispute entries to Evrocom, Euronews BG, BG On Air, bTV, Nova;
  BNT/BNR not added yet. ЦИК decisions can be found by title through bta.bg "oficial-messages" (text paywalled): 552/554/556-ЕП of 18.07.2019
  against Инвестор.БГ. Svobodna Tochka: Борис Митов's final conviction (ВКС 16.07.2025, Mediapool articles of 2018).
  Still nothing found for Bloomberg TV, Boulevard Bulgaria, Moreto.net, Marica (as a defendant). Court databases vks.bg and legalacts.justice.bg
  do not open from the workspace (proxy / robots) - two ВКС acts mentioning Марица are unread; check in David's PC browser.
- 17 Nov, read in David's PC browser (built-in browser) and added: SIGMA contracts (Focus 489k EUR, Evrocom 76k, Marica 208k with Plovdiv),
  CIK tariff list for 19.04.2026 (cik.bg/bg/ns19.04.2026/media_tarif; Euronews not on it), CIK 4804-НС (Euronews exit poll before 20:00),
  CIK 2019 decisions vs Инвестор.БГ (276/277 violations; 552/554/556 = 2000+1000+2000 лв), Boulevard's America for Bulgaria grant (38,330 лв),
  Moreto terms/contacts/ad page and the ВАС 6315/2026 trademark case (won by Морето ООД), Indzhov's study (uni-vt.bg PDF, pp. 44-49),
  SBJ 12.06.2026, North Data (BG Privatinvest terminated 19.10.2022 but still owner in the BG register - open question), Marica's register
  documents (2019 art. 7a declaration names Grozev + Habsburg; 2022 report). Court finds: ВКС 206/07.12.2023 (PIK + Селевкиди, 10,000 лв,
  bTV presenter) cites Sofia Appeals 984/2021 against "ИК Марица ООД" (8,000 лв, not read itself). Two other acts were unrelated.
  How-tos: PDFs in the PC browser - fetch the bytes in page JS, then pdf.js via dynamic import from jsdelivr (works on uni-vt.bg and
  legalacts, blocked by CSP on the register portal); register documents: fetch /CR/api/Documents/<token> from a portal page, then show
  them with a blob URL in an <embed> and read by screenshots (they are scans). vks.bg, legalacts, cik.bg, sigma.midt.bg open fine there.
