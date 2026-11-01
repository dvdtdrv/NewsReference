"""
The outlets the project reads, and how to read each one.

Each outlet has:
  name     - how we show it on the site
  domain   - the website's address
  type     - rough category, used later for grouping outlets
  feed     - the RSS feed address, OR
  sitemap  - a "news sitemap" address (a list of new articles with headlines) for outlets without a feed
  gentle   - True for sites that limit automated traffic: read at most once per run, and wait when told to
  as_browser - introduce ourselves as a web browser. ONLY with the outlet's written permission
               (kept in the permissions folder).

Found with check_feeds.py and probe_missing.py on 31 Oct 2026.
"""

OUTLETS = [
    # --- Public / state media ---
    # BTA blocks programs, but gave written permission on 31 Oct 2026 to read the feed with our
    # program in any way, at most once every 30 minutes (see permissions/BTA.md). So for BTA only,
    # the program introduces itself as a browser.
    {"name": "BTA", "domain": "bta.bg", "type": "news agency",
     "feed": "https://www.bta.bg/bg/rss/free", "gentle": True, "as_browser": True},
    {"name": "BNT", "domain": "bntnews.bg", "type": "public TV",
     "feed": "http://news.bnt.bg/bg/rss/news.xml"},
    # BNR's news moved to bnrnews.bg, which has a feed (found 1 Nov 2026)
    {"name": "BNR", "domain": "bnrnews.bg", "type": "public radio",
     "feed": "https://bnrnews.bg/api/rss/main"},

    # --- Commercial TV ---
    {"name": "bTV Novinite", "domain": "btvnovinite.bg", "type": "commercial TV",
     "feed": "https://btvnovinite.bg/lbin/v3/rss.php"},
    {"name": "Nova", "domain": "nova.bg", "type": "commercial TV",
     "feed": "https://nova.bg/rss/latest"},

    # --- Newspapers and online media ---
    {"name": "Dnevnik", "domain": "dnevnik.bg", "type": "online daily",
     "feed": "https://www.dnevnik.bg/rss/"},
    {"name": "Capital", "domain": "capital.bg", "type": "weekly / business",
     "feed": "https://www.capital.bg/rss/"},
    {"name": "Mediapool", "domain": "mediapool.bg", "type": "online, politics",
     "feed": "https://www.mediapool.bg/rss"},
    {"name": "Standart", "domain": "standartnews.com", "type": "daily",
     "feed": "https://www.standartnews.com/rss?p=1"},
    {"name": "24 Chasa", "domain": "24chasa.bg", "type": "mass daily",
     "feed": "https://www.24chasa.bg/rss"},
    {"name": "Trud", "domain": "trud.bg", "type": "mass daily",
     "sitemap": "https://trud.bg/sitemaps/sitemap_latest.xml"},
    {"name": "Sega", "domain": "segabg.com", "type": "daily",
     "feed": "https://www.segabg.com/rss"},
    {"name": "Club Z", "domain": "clubz.bg", "type": "online",
     "feed": "https://www.clubz.bg/rss"},
    {"name": "Dnes.bg", "domain": "dnes.bg", "type": "online portal",
     "feed": "https://www.dnes.bg/rss.php?today"},
    {"name": "Actualno", "domain": "actualno.com", "type": "online portal",
     "feed": "https://www.actualno.com/rss"},
    {"name": "Fakti", "domain": "fakti.bg", "type": "online portal",
     "feed": "https://fakti.bg/feed"},
    {"name": "Offnews", "domain": "offnews.bg", "type": "online portal",
     "sitemap": "https://offnews.bg/xml/sitemap.php?type=news"},
    {"name": "Blitz", "domain": "blitz.bg", "type": "online portal",
     "feed": "https://blitz.bg/rss"},
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
    {"name": "Darik", "domain": "dariknews.bg", "type": "radio",
     "feed": "https://dariknews.bg/rss.php"},
    {"name": "Focus", "domain": "focus-news.net", "type": "news agency",
     "feed": "https://www.focus-news.net/rss.php"},
    {"name": "Vesti.bg", "domain": "vesti.bg", "type": "online portal",
     "feed": "https://www.vesti.bg/rss"},
    # News.bg has no feed or sitemap; we read its "latest news" page (robots.txt allows it)
    {"name": "News.bg", "domain": "news.bg", "type": "online portal",
     "page": "https://news.bg/latest"},
    {"name": "BG On Air", "domain": "bgonair.bg", "type": "commercial TV",
     "feed": "https://www.bgonair.bg/rss/news"},
    {"name": "Bloomberg TV", "domain": "bloombergtv.bg", "type": "business TV",
     "feed": "https://www.bloombergtv.bg/rss/news"},
    {"name": "Evrocom", "domain": "eurocom.bg", "type": "commercial TV",
     "feed": "https://eurocom.bg/feed/"},
    {"name": "Euronews BG", "domain": "euronews.bg", "type": "international",
     "feed": "https://euronews.bg/feed/"},
    # DW's Bulgarian service has no Bulgarian feed; its news sitemap lists headlines, times and photos
    {"name": "DW", "domain": "dw.com", "type": "international",
     "sitemap": "https://www.dw.com/bg/news-sitemap.xml"},
    {"name": "Boulevard Bulgaria", "domain": "boulevardbulgaria.bg", "type": "online",
     "feed": "https://boulevardbulgaria.bg/feed.atom"},
    {"name": "Svobodna Tochka", "domain": "svobodnatochka.bg", "type": "online",
     "feed": "https://svobodnatochka.bg/feed/"},
    {"name": "Marica", "domain": "marica.bg", "type": "regional",
     "feed": "https://www.marica.bg/rss"},
    {"name": "Moreto.net", "domain": "moreto.net", "type": "regional",
     "feed": "https://www.moreto.net/rss/lastnews.xml"},
]

# Outlets we'd like but can't read yet. The website lists these so nobody
# mistakes "not tracked" for "didn't cover the story".
UNTRACKED = []   # BNR, Novini.bg and Dir.bg were here until 1 Nov 2026; all three are tracked now

# Left out for now: English-language outlets (Novinite, The Sofia Globe).
# The grouping compares Bulgarian text, so English headlines would never match.
