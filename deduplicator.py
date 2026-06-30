from typing import List
from collectors.base_collector import Article
from config.settings import SIMILARITY_THRESHOLD, MAX_ARTICLES_TOTAL
from utils.logger import get_logger

log = get_logger(__name__)


def _jaccard(a: str, b: str) -> float:
    """Fast token-level Jaccard similarity."""
    sa = set(a.lower().split())
    sb = set(b.lower().split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


class Deduplicator:
    def __init__(self, threshold: float = SIMILARITY_THRESHOLD, max_total: int = MAX_ARTICLES_TOTAL):
        self.threshold = threshold
        self.max_total = max_total

    def deduplicate(self, articles: List[Article]) -> List[Article]:
        # Sort newest first
        sorted_articles = sorted(
            articles,
            key=lambda a: a.published or __import__("datetime").datetime.min,
            reverse=True,
        )

        seen_urls: set = set()
        kept: List[Article] = []

        for article in sorted_articles:
            if len(kept) >= self.max_total:
                break

            # Exact URL dedup
            if article.url in seen_urls:
                continue
            seen_urls.add(article.url)

            # Fuzzy title dedup
            is_dup = False
            for existing in kept:
                sim = _jaccard(article.title, existing.title)
                if sim >= self.threshold:
                    is_dup = True
                    break

            if not is_dup:
                kept.append(article)

        log.info(f"Deduplicated: {len(articles)} → {len(kept)} articles")
        return kept
