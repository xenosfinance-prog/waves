import re
import unicodedata
from datetime import datetime, timezone
from typing import Optional


def clean_text(text: str) -> str:
    """Strip HTML tags, normalize whitespace, clean unicode."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def truncate(text: str, max_chars: int = 300) -> str:
    text = clean_text(text)
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def format_dt(dt: Optional[datetime]) -> str:
    if not dt:
        return "—"
    try:
        return dt.strftime("%d %b %Y %H:%M UTC")
    except Exception:
        return str(dt)


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")[:60]


def sentiment_emoji(sentiment: str) -> str:
    mapping = {
        "bullish":  "🟢",
        "bearish":  "🔴",
        "neutral":  "⚪",
        "mixed":    "🟡",
        "risk-on":  "🟢",
        "risk-off": "🔴",
    }
    return mapping.get(sentiment.lower(), "⚪")
