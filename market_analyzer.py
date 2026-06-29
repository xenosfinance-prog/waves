from collections import Counter
from typing import List, Dict, Any
from collectors.base_collector import Article
from config.settings import CATEGORIES
from utils.logger import get_logger

log = get_logger(__name__)


class MarketAnalyzer:
    def analyze(self, articles: List[Article]) -> Dict[str, Any]:
        """Compute aggregate market statistics from classified articles."""
        by_category: Dict[str, List[Article]] = {c: [] for c in CATEGORIES}

        for a in articles:
            cat = a.category if a.category in by_category else "macro"
            by_category[cat].append(a)

        # Overall sentiment
        sentiments = [a.sentiment for a in articles]
        sent_count = Counter(sentiments)
        total = len(articles) or 1
        bull_pct = sent_count["bullish"] / total * 100
        bear_pct = sent_count["bearish"] / total * 100

        if bull_pct > 55:
            overall_sentiment = "risk-on"
            overall_label     = "RISK-ON 🟢"
        elif bear_pct > 55:
            overall_sentiment = "risk-off"
            overall_label     = "RISK-OFF 🔴"
        else:
            overall_sentiment = "mixed"
            overall_label     = "MIXED 🟡"

        # Top sources
        sources = Counter(a.source for a in articles)

        # Per-category stats
        cat_stats: Dict[str, Dict] = {}
        for cat, arts in by_category.items():
            if not arts:
                cat_stats[cat] = {"count": 0, "sentiment": "neutral", "top": []}
                continue
            s = Counter(a.sentiment for a in arts)
            total_cat = len(arts)
            if s["bullish"] / total_cat > 0.5:
                cat_sent = "bullish"
            elif s["bearish"] / total_cat > 0.5:
                cat_sent = "bearish"
            else:
                cat_sent = "mixed"
            top = sorted(arts, key=lambda x: x.score, reverse=True)[:5]
            cat_stats[cat] = {
                "count":     total_cat,
                "sentiment": cat_sent,
                "top":       top,
            }

        log.info(
            f"Market analysis: {overall_label} | "
            f"bull={bull_pct:.0f}% bear={bear_pct:.0f}%"
        )

        return {
            "total_articles":     len(articles),
            "overall_sentiment":  overall_sentiment,
            "overall_label":      overall_label,
            "bull_pct":           bull_pct,
            "bear_pct":           bear_pct,
            "sent_count":         dict(sent_count),
            "by_category":        by_category,
            "cat_stats":          cat_stats,
            "top_sources":        sources.most_common(5),
        }
