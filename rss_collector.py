import feedparser
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Dict

from collectors.base_collector import BaseCollector, Article
from config.settings import MAX_ARTICLES_PER_FEED, FETCH_TIMEOUT_SEC
from utils.helpers import clean_text, truncate
from utils.logger import get_logger

log = get_logger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; XenosFinance-MarketAgent/1.0)",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


def _parse_date(entry) -> datetime:
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                import time
                return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
            except Exception:
                pass
    # fallback: try published string
    pub = getattr(entry, "published", None)
    if pub:
        try:
            return parsedate_to_datetime(pub)
        except Exception:
            pass
    return datetime.now(timezone.utc)


def _fetch_feed(feed_cfg: Dict, max_articles: int) -> List[Article]:
    url      = feed_cfg["url"]
    category = feed_cfg["category"]
    source   = feed_cfg["source"]
    articles = []

    try:
        req  = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SEC)
        raw  = resp.read()
        feed = feedparser.parse(raw)

        for entry in feed.entries[:max_articles]:
            title = clean_text(getattr(entry, "title", ""))
            if not title:
                continue

            link    = getattr(entry, "link", "") or getattr(entry, "id", "")
            summary = truncate(
                clean_text(
                    getattr(entry, "summary", "")
                    or getattr(entry, "description", "")
                    or getattr(entry, "content", [{}])[0].get("value", "")
                ),
                max_chars=400,
            )
            pub = _parse_date(entry)

            articles.append(Article(
                title=title,
                url=link,
                summary=summary,
                source=source,
                category=category,
                published=pub,
                raw_text=f"{title}. {summary}",
            ))

        log.info(f"✓ {source}: {len(articles)} articles")
    except Exception as e:
        log.warning(f"✗ {source} ({url[:50]}): {e}")

    return articles


class RSSCollector(BaseCollector):
    def __init__(self, feeds: List[Dict], max_per_feed: int = MAX_ARTICLES_PER_FEED):
        self.feeds       = feeds
        self.max_per_feed = max_per_feed

    def collect(self) -> List[Article]:
        all_articles: List[Article] = []
        log.info(f"Fetching {len(self.feeds)} RSS feeds…")

        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {
                ex.submit(_fetch_feed, feed, self.max_per_feed): feed
                for feed in self.feeds
            }
            for fut in as_completed(futures):
                try:
                    all_articles.extend(fut.result())
                except Exception as e:
                    log.warning(f"Feed error: {e}")

        log.info(f"Total collected: {len(all_articles)} articles")
        return all_articles
