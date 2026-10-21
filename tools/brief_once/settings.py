import os

# ─────────────────────────────────────────────
# OUTPUT
# ─────────────────────────────────────────────
OUTPUT_PATH = os.getenv("OUTPUT_PATH", "site/market-brief.html")

# ─────────────────────────────────────────────
# RSS COLLECTION
# ─────────────────────────────────────────────
MAX_ARTICLES_PER_FEED = int(os.getenv("MAX_ARTICLES_PER_FEED", "15"))
FETCH_TIMEOUT_SEC     = int(os.getenv("FETCH_TIMEOUT_SEC", "10"))

RSS_FEEDS = [
    # ── Macro / Central Banks ──
    {"url": "https://www.investing.com/rss/news_285.rss",           "category": "macro",        "source": "Investing.com"},
    {"url": "https://feeds.marketwatch.com/marketwatch/topstories/", "category": "macro",        "source": "MarketWatch"},
    {"url": "https://www.cnbc.com/id/10000664/device/rss/rss.html", "category": "macro",        "source": "CNBC Economy"},

    # ── Equities ──
    {"url": "https://www.investing.com/rss/news_25.rss",            "category": "equities",     "source": "Investing.com Stocks"},
    {"url": "https://feeds.marketwatch.com/marketwatch/marketpulse/", "category": "equities",   "source": "MarketWatch Pulse"},
    {"url": "https://www.cnbc.com/id/10001147/device/rss/rss.html", "category": "equities",     "source": "CNBC Markets"},

    # ── Commodities & Energy ──
    {"url": "https://oilprice.com/rss/main",                        "category": "commodities",  "source": "OilPrice.com"},
    {"url": "https://www.investing.com/rss/news_11.rss",            "category": "commodities",  "source": "Investing.com Commodities"},

    # ── Crypto ──
    {"url": "https://www.coindesk.com/arc/outboundfeeds/rss/",      "category": "crypto",       "source": "CoinDesk"},
    {"url": "https://cointelegraph.com/rss",                        "category": "crypto",       "source": "Cointelegraph"},

    # ── Forex & Rates ──
    {"url": "https://www.investing.com/rss/news_1.rss",             "category": "forex",        "source": "Investing.com Forex"},
    {"url": "https://www.forexlive.com/feed/news",                  "category": "forex",        "source": "ForexLive"},

    # ── Geopolitical Risk ──
    {"url": "https://www.investing.com/rss/news_301.rss",           "category": "geopolitics", "source": "Investing.com Politics"},
    {"url": "https://www.aljazeera.com/xml/rss/all.xml",            "category": "geopolitics", "source": "Al Jazeera"},
]

# ─────────────────────────────────────────────
# DEDUPLICATION
# ─────────────────────────────────────────────
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.85"))
MAX_ARTICLES_TOTAL    = int(os.getenv("MAX_ARTICLES_TOTAL", "100"))

# ─────────────────────────────────────────────
# CLASSIFICATION CATEGORIES
# Devono combaciare con quanto assegna classifier.py
# e con le sezioni usate in gemini_writer.py
# ─────────────────────────────────────────────
CATEGORIES = ["macro", "equities", "commodities", "crypto", "forex", "geopolitics"]

CATEGORY_LABELS = {
    "macro":        "Macro & Central Banks",
    "equities":     "Equities",
    "commodities":  "Commodities & Energy",
    "crypto":       "Crypto",
    "forex":        "Forex & Rates",
    "geopolitics": "Geopolitical Risk",
}

# ─────────────────────────────────────────────
# GEMINI AI
# ─────────────────────────────────────────────
GEMINI_API_KEY         = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL           = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
MAX_ARTICLES_ANALYSIS  = int(os.getenv("MAX_ARTICLES_ANALYSIS", "30"))
