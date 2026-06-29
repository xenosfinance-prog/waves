import os

# ── API Keys ──────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ── Gemini Model ──────────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-2.5-flash"

# ── RSS Feeds ─────────────────────────────────────────────────────────────
RSS_FEEDS = [
    # Macro / Economy
    {"url": "https://feeds.content.dowjones.io/public/rss/mw_marketpulse",   "category": "macro",    "source": "MarketWatch"},
    {"url": "https://feeds.content.dowjones.io/public/rss/mw_topstories",    "category": "macro",    "source": "MarketWatch"},
    {"url": "https://feeds.bbci.co.uk/news/business/rss.xml",                "category": "macro",    "source": "BBC Business"},
    {"url": "https://www.ft.com/rss/home/uk",                                "category": "macro",    "source": "FT"},
    # Equities
    {"url": "https://feeds.content.dowjones.io/public/rss/mw_stocks",        "category": "equities", "source": "MarketWatch"},
    {"url": "https://seekingalpha.com/market_currents.xml",                   "category": "equities", "source": "SeekingAlpha"},
    # Commodities / Energy
    {"url": "https://oilprice.com/rss/main",                                  "category": "commodities", "source": "OilPrice"},
    {"url": "https://www.mining.com/feed/",                                   "category": "commodities", "source": "Mining.com"},
    # Crypto
    {"url": "https://cointelegraph.com/rss",                                  "category": "crypto",   "source": "CoinTelegraph"},
    {"url": "https://coindesk.com/arc/outboundfeeds/rss/",                   "category": "crypto",   "source": "CoinDesk"},
    # Forex / Central Banks
    {"url": "https://www.forexlive.com/feed/news",                            "category": "forex",    "source": "ForexLive"},
    {"url": "https://www.dailyfx.com/feeds/all",                              "category": "forex",    "source": "DailyFX"},
    # Geopolitics
    {"url": "https://feeds.reuters.com/Reuters/worldNews",                    "category": "geopolitics", "source": "Reuters"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",        "category": "geopolitics", "source": "NYT World"},
]

# ── Output ────────────────────────────────────────────────────────────────
OUTPUT_PATH = "site/market-brief.html"

# ── Pipeline settings ─────────────────────────────────────────────────────
MAX_ARTICLES_PER_FEED = 10
MAX_ARTICLES_TOTAL    = 60   # after dedup
MAX_ARTICLES_ANALYSIS = 30   # top N sent to Gemini
FETCH_TIMEOUT_SEC     = 10
SIMILARITY_THRESHOLD  = 0.75 # for deduplication

# ── Categories ────────────────────────────────────────────────────────────
CATEGORIES = ["macro", "equities", "commodities", "crypto", "forex", "geopolitics"]

CATEGORY_LABELS = {
    "macro":       "🌐 Macro & Economy",
    "equities":    "📈 Equities",
    "commodities": "🛢️ Commodities & Energy",
    "crypto":      "₿ Crypto",
    "forex":       "💱 Forex & Central Banks",
    "geopolitics": "🌍 Geopolitics",
}
