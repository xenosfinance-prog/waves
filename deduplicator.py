from datetime import datetime
from typing import List, Set

from collectors.base_collector import Article
from config.settings import SIMILARITY_THRESHOLD, MAX_ARTICLES_TOTAL
from utils.logger import get_logger

log = get_logger(__name__)


def _jaccard(a: str, b: str) -> float:
    """
    Compute token-level Jaccard similarity between two strings.
    """
    sa = set(a.lower().split())
    sb = set(b.lower().split())

    if not sa or not sb:
        return 0.0

    return len(sa & sb) / len(sa | sb)


class Deduplicator:
    """
    Remove duplicate articles using:
    1. Exact URL matching
    2. Fuzzy title matching (Jaccard similarity)
    """

    def __init__(
        self,
        threshold: float = SIMILARITY_THRESHOLD,
        max_total: int = MAX_ARTICLES_TOTAL,
    ):
        self.threshold = threshold
        self.max_total = max_total

    def deduplicate(self, articles: List[Article]) -> List[Article]:
        """
        Deduplicate articles and return the newest unique ones.
        """

        sorted_articles = sorted(
            articles,
            key=lambda article: article.published or datetime.min,
            reverse=True,
        )

        seen_urls: Set[str] = set()
        kept: List[Article] = []

        for article in sorted_articles:

            if len(kept) >= self.max_total:
                break

            if not article.url:
                continue

            if article.url in seen_urls:
                continue

            seen_urls.add(article.url)

            duplicate = any(
                _jaccard(article.title, existing.title) >= self.threshold
                for existing in kept
            )

            if not duplicate:
                kept.append(article)

        log.info(
            "Deduplicated: %d → %d articles",
            len(articles),
            len(kept),
        )

        return kept
