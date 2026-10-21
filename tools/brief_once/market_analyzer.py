from collections import Counter
from typing import List, Dict, Any, Optional
from base_collector import Article
from settings import CATEGORIES
from logger import get_logger
from divergence_scorer import compute_divergence_badge

log = get_logger(__name__)

OIL_KEYWORDS = ("oil", "wti", "brent", "crude", "opec", "petroleum", "barrel")


class MarketAnalyzer:
    def analyze(
        self,
        articles: List[Article],
        gemini_client=None,
        oil_price_data: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Compute aggregate market statistics from classified articles.

        gemini_client e oil_price_data sono opzionali: se non passati,
        il divergence score per l'oil viene semplicemente saltato
        (badge "unavailable"), il resto dell'analisi funziona come prima.
        """
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

        # Oil divergence score (dentro commodities, solo articoli oil-related)
        oil_divergence = self._compute_oil_divergence(
            by_category.get("commodities", []),
            gemini_client,
            oil_price_data,
        )
        if oil_divergence:
            cat_stats["commodities"]["oil_divergence"] = oil_divergence

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

    def _compute_oil_divergence(
        self,
        commodity_articles: List[Article],
        gemini_client,
        oil_price_data: Optional[Dict[str, float]],
    ) -> Optional[Dict[str, Any]]:
        """Filtra gli articoli oil-related dalla categoria commodities e calcola
        il divergence badge. Restituisce None se manca il client Gemini o non
        ci sono articoli rilevanti, invece di far fallire tutta l'analisi."""
        if gemini_client is None:
            return None

        oil_articles = [
            a for a in commodity_articles
            if any(kw in (a.title + " " + a.summary).lower() for kw in OIL_KEYWORDS)
        ]
        if not oil_articles:
            return None

        top_oil = sorted(oil_articles, key=lambda x: x.score, reverse=True)[:5]
        combined_text = " ".join(a.summary for a in top_oil)

        front = oil_price_data.get("front_month") if oil_price_data else None
        back = oil_price_data.get("back_month") if oil_price_data else None

        try:
            return compute_divergence_badge(
                article_text=combined_text,
                asset="oil",
                gemini_client=gemini_client,
                front_month_price=front,
                back_month_price=back,
            )
        except Exception as e:
            log.warning(f"Oil divergence score fallito: {e}")
            return None
