"""
The outlets the project reads, and how to read each one.

Each outlet has:
  name     - how we show it on the site
  domain   - the website's address
  type     - rough category, used later for grouping outlets
  feed     - the RSS feed address, OR
  sitemap  - a "news sitemap" address (a list of new articles with headlines) for outlets without a feed
  gentle   - True for sites that limit automated traffic: read at most once per run, and wait when told to
  local    - True for outlets that refuse GitHub's servers but work from David's PC: they are read on
             the PC by fetch_local.py (workflow local-fetch.yml), and GitHub's run picks up the result
  photos_on_pc - GitHub reads the feed, but the article pages (photos) refuse GitHub: David's PC fetches them
  page_images - False for outlets whose article pages refuse us (403): keep the feed's photo
  as_browser - introduce ourselves as a web browser. ONLY with the outlet's written permission
               (kept in the permissions folder).
  catchup  - (local outlets) where the PC reads back what it missed while it was off (catchup.py, 23 Nov 2026):
             {"sitemap": address, "headlines": True if the sitemap itself has the headlines}
  semicolon_quotes - the feed turns quotation marks into ";" (Club Z): collect.py puts them back

Found with check_feeds.py and probe_missing.py on 31 Oct 2026.
"""

OUTLETS = [
    # --- Public / state media ---
    # BTA blocks programs, but gave written permission on 31 Oct 2026 to read the feed with our
    # program in any way, at most once every 30 minutes (the email is kept by David, outside the repository). So for BTA only,
    # the program introduces itself as a browser.
    {"name": "BTA", "domain": "bta.bg", "type": "news agency",
     "feed": "https://www.bta.bg/bg/rss/free", "gentle": True, "as_browser": True},
    {"name": "BNT", "domain": "bntnews.bg", "type": "public TV",
     "feed": "https://news.bnt.bg/bg/rss/news.xml"},
    # BNR's news moved to bnrnews.bg, which has a feed (found 1 Nov 2026)
    {"name": "BNR", "domain": "bnrnews.bg", "type": "public radio",
     "feed": "https://bnrnews.bg/api/rss/main"},

    # --- Commercial TV ---
    # bTV gave written permission on 1 Nov 2026 to read its coverage through a browser for this
    # project (the email is kept by David, outside the repository), so the program introduces itself as a browser for bTV only.
    {"name": "bTV Novinite", "local": True, "domain": "btvnovinite.bg", "type": "commercial TV",
     "feed": "https://btvnovinite.bg/lbin/v3/rss.php", "as_browser": True,
     "catchup": {"sitemap": "https://btvnovinite.bg/lbin/v3/sitemap.php", "headlines": False,
                 # its sitemap lists only ~30 links: after a gap also these section pages (probe_btv_pages.py, 23 Nov)
                 "sections": ["https://btvnovinite.bg/bulgaria/", "https://btvnovinite.bg/svetut/",
                              "https://btvnovinite.bg/predavania/"]}},
    {"name": "Nova", "domain": "nova.bg", "type": "commercial TV",
     "feed": "https://nova.bg/rss/latest"},

    # --- Newspapers and online media ---
    {"name": "Dnevnik", "domain": "dnevnik.bg", "type": "online daily",
     "feed": "https://www.dnevnik.bg/rss/", "page_images": False},
    {"name": "Capital", "domain": "capital.bg", "type": "weekly / business",
     "feed": "https://www.capital.bg/rss/", "page_images": False},
    {"name": "Mediapool", "domain": "mediapool.bg", "type": "online, politics",
     "feed": "https://www.mediapool.bg/rss"},
    {"name": "Standart", "domain": "standartnews.com", "type": "daily",
     "feed": "https://www.standartnews.com/rss?p=1"},
    {"name": "24 Chasa", "domain": "24chasa.bg", "type": "mass daily",
     "feed": "https://www.24chasa.bg/rss"},
    {"name": "Trud", "local": True, "domain": "trud.bg", "type": "mass daily",
     "sitemap": "https://trud.bg/sitemaps/sitemap_latest.xml"},
    {"name": "Sega", "domain": "segabg.com", "type": "daily",
     "feed": "https://www.segabg.com/rss"},
    # Club Z's feed turns every quotation mark into ";" (";Нова надежда;" where its page says "Нова надежда"):
    # collect.py puts the quotes back (fix_semicolon_quotes), 23 Nov 2026
    {"name": "Club Z", "domain": "clubz.bg", "type": "online",
     "feed": "https://www.clubz.bg/rss", "semicolon_quotes": True},
    # Dnes.bg and BG On Air refused GitHub until ~Nov 2026; on 21 Nov 2026 both answered GitHub every time
    # (probe-outlets.yml), so GitHub reads them again, day and night. rss.php?today now redirects to /rss/latest.
    {"name": "Dnes.bg", "domain": "dnes.bg", "type": "online portal",
     "feed": "https://www.dnes.bg/rss/latest"},
    {"name": "Actualno", "domain": "actualno.com", "type": "online portal",
     "feed": "https://www.actualno.com/rss"},
    {"name": "Fakti", "domain": "fakti.bg", "type": "online portal",
     "feed": "https://fakti.bg/feed"},
    {"name": "Offnews", "domain": "offnews.bg", "type": "online portal",
     "sitemap": "https://offnews.bg/xml/sitemap.php?type=news"},
    {"name": "Blitz", "local": True, "domain": "blitz.bg", "type": "online portal",
     "feed": "https://blitz.bg/rss",
     "catchup": {"sitemap": "https://blitz.bg/sitemap/google-news.xml", "headlines": True}},
    # Novini.bg's feed is under /api/, which its robots.txt forbids, so we read its news sitemap instead
    {"name": "Novini.bg", "domain": "novini.bg", "type": "online portal",
     "sitemap": "https://novini.bg/sitemap/news/1.xml"},
    {"name": "Dir.bg", "domain": "dir.bg", "type": "online portal",
     "feed": "https://dir.bg/feeds/rss"},
    {"name": "PIK", "domain": "pik.bg", "type": "online portal",
     "feed": "https://www.pik.bg/feed.xml"},
    {"name": "Banker", "domain": "banker.bg", "type": "business",
     "feed": "https://www.banker.bg/rss"},
    {"name": "Pogled.info", "domain": "pogled.info", "type": "online",
     "feed": "https://pogled.info/rss"},

    # --- Added 1 Nov 2026 (found with probe_missing.py and checked in a browser) ---
    {"name": "Darik", "domain": "dariknews.bg", "type": "online portal",   # Net Info, not the radio (15 Nov 2026)
     "feed": "https://dariknews.bg/rss.php"},
    {"name": "Focus", "domain": "focus-news.net", "type": "news agency",
     "feed": "https://www.focus-news.net/rss.php"},
    {"name": "Vesti.bg", "domain": "vesti.bg", "type": "online portal",
     "feed": "https://www.vesti.bg/rss"},
    # News.bg has no feed or sitemap; we read its "latest news" page (robots.txt allows it)
    {"name": "News.bg", "domain": "news.bg", "type": "online portal",
     "page": "https://news.bg/latest"},
    # BG On Air: its feed answers GitHub, but its article pages still refuse GitHub (403), so the PC
    # sends the photos and does the deleted-articles check (photos_on_pc), like Euronews BG
    {"name": "BG On Air", "domain": "bgonair.bg", "type": "commercial TV",
     "feed": "https://www.bgonair.bg/rss/news", "photos_on_pc": True},
    {"name": "Bloomberg TV", "local": True, "domain": "bloombergtv.bg", "type": "business TV",
     "feed": "https://www.bloombergtv.bg/rss/news",
     "catchup": {"sitemap": "https://www.bloombergtv.bg/sitemap/sitemap-1.xml", "headlines": False}},
    {"name": "Evrocom", "domain": "eurocom.bg", "type": "commercial TV",
     "feed": "https://eurocom.bg/feed/"},
    {"name": "Euronews BG", "domain": "euronews.bg", "type": "international",
     "feed": "https://euronews.bg/feed/", "photos_on_pc": True},
    # DW's Bulgarian service has no Bulgarian feed; its news sitemap lists headlines, times and photos
    {"name": "DW", "domain": "dw.com", "type": "international",
     "sitemap": "https://www.dw.com/bg/news-sitemap.xml"},
    {"name": "Boulevard Bulgaria", "domain": "boulevardbulgaria.bg", "type": "online",
     "feed": "https://boulevardbulgaria.bg/feed.atom"},
    {"name": "Svobodna Tochka", "domain": "svobodnatochka.bg", "type": "online",
     "feed": "https://svobodnatochka.bg/feed/"},
    {"name": "Marica", "local": True, "domain": "marica.bg", "type": "regional",
     "feed": "https://www.marica.bg/rss",
     "catchup": {"sitemap": "https://www.marica.bg/storage/google-news-sitemap.xml", "headlines": True,
                 "hours": 72}},   # its sitemap reaches ~3 days (David, 23 Nov 2026)
    {"name": "Moreto.net", "domain": "moreto.net", "type": "regional",
     "feed": "https://www.moreto.net/rss/lastnews.xml"},
]

# Outlets we'd like but can't read yet. The website lists these so nobody
# mistakes "not tracked" for "didn't cover the story".
UNTRACKED = []   # BNR, Novini.bg and Dir.bg were here until 1 Nov 2026; all three are tracked now

# Left out for now: English-language outlets (Novinite, The Sofia Globe).
# The grouping compares Bulgarian text, so English headlines would never match.
