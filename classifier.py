import re
from typing import List
from collectors.base_collector import Article
from utils.logger import get_logger

log = get_logger(__name__)

# ── Keyword maps ──────────────────────────────────────────────────────────
CATEGORY_KEYWORDS = {
    "macro":       ["fed", "ecb", "boe", "inflation", "gdp", "cpi", "ppi", "interest rate",
                    "recession", "central bank", "fiscal", "monetary", "treasury", "yield",
                    "economy", "macro", "unemployment", "nfp", "fomc", "rate hike"],
    "equities":    ["stock", "shares", "equity", "s&p", "nasdaq", "dow", "earnings",
                    "ipo", "dividend", "buyback", "rally", "correction", "market cap",
                    "russell", "ftse", "dax", "nikkei", "sp500"],
    "commodities": ["oil", "gold", "silver", "copper", "wheat", "corn", "gas", "brent",
                    "wti", "opec", "crude", "commodity", "energy", "mining", "metal",
                    "platinum", "palladium", "lumber", "natural gas"],
    "crypto":      ["bitcoin", "ethereum", "crypto", "btc", "eth", "blockchain",
                    "defi", "nft", "altcoin", "stablecoin", "binance", "coinbase",
                    "solana", "xrp", "token", "digital asset", "web3"],
    "forex":       ["forex", "currency", "eur", "usd", "gbp", "jpy", "dollar",
                    "euro", "pound", "yen", "fx", "exchange rate", "parity",
                    "central bank", "rate decision", "intervention"],
    "geopolitics": ["war", "sanctions", "geopolit", "election", "nato", "china",
                    "russia", "ukraine", "middle east", "trade war", "tariff",
                    "diplomacy", "conflict", "military", "opec", "g7", "g20"],
}

SENTIMENT_BULLISH = ["surge", "rally", "gain", "rise", "jump", "soar", "record high",
                     "boom", "bullish", "upside", "outperform", "beat", "strong",
                     "growth", "recovery", "optimism", "positive"]
SENTIMENT_BEARISH = ["crash", "fall", "drop", "plunge", "decline", "slump", "recession",
                     "bearish", "downside", "miss", "weak", "concern", "fear", "risk",
                     "sell-off", "loss", "negative", "contraction", "warning"]

RELEVANCE_BOOST = ["market", "trading", "investor", "financial", "price", "analysis"]


def _score_text(text: str, keywords: List[str]) -> int:
    text_lower = text.lower()
    return sum(1 for kw in keywords if kw in text_lower)


class Classifier:
    def classify(self, articles: List[Article]) -> List[Article]:
        for a in articles:
            text = f"{a.title} {a.summary}".lower()

            # Re-classify category if needed (override RSS category with keyword match)
            best_cat   = a.category
            best_score = _score_text(text, CATEGORY_KEYWORDS.get(a.category, []))
            for cat, kws in CATEGORY_KEYWORDS.items():
                s = _score_text(text, kws)
                if s > best_score:
                    best_score = s
                    best_cat   = cat
            a.category = best_cat

            # Sentiment
            bull = _score_text(text, SENTIMENT_BULLISH)
            bear = _score_text(text, SENTIMENT_BEARISH)
            if bull > bear * 1.5:
                a.sentiment = "bullish"
            elif bear > bull * 1.5:
                a.sentiment = "bearish"
            elif bull > 0 and bear > 0:
                a.sentiment = "mixed"
            else:
                a.sentiment = "neutral"

            # Relevance score
            relevance = _score_text(text, RELEVANCE_BOOST)
            a.score = best_score + relevance * 0.5

        log.info(f"Classified {len(articles)} articles")
        return articles
