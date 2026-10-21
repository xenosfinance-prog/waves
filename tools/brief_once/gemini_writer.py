import os
import time
from typing import List, Dict, Any
from base_collector import Article
from settings import GEMINI_API_KEY, GEMINI_MODEL, MAX_ARTICLES_ANALYSIS
from logger import get_logger

log = get_logger(__name__)

MAX_RETRIES  = 3
RETRY_DELAY  = 8  # base seconds; actual wait grows exponentially per attempt (Gemini 503s are usually transient load spikes, not permanent failures — worth waiting longer before giving up)
RETRY_MAX_DELAY = 60  # cap so a single run can't hang indefinitely

# When the primary model (GEMINI_MODEL) is persistently 503-ing — a known,
# widely-reported Google-side capacity issue that can last hours for a
# specific model — fall back to alternate models rather than failing the
# whole run. Each gets its own (shorter) retry budget.
# 2026-10-06: gemini-2.0-flash spento dal 1 giugno 2026 (inutile in coda);
# gemini-2.5-flash spento dal 16 ottobre 2026 → sostituto ufficiale
# gemini-3.5-flash messo PRIMA. 2.5-flash resta solo finché esiste: dopo lo
# spegnimento risponde 404 e viene saltato subito (vedi _is_model_gone).
# gemini-3.1-flash-lite = ultima spiaggia, pool di capacità separato.
FALLBACK_MODELS = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-3.1-flash-lite"]

# 2026-10-06: timeout per singola chiamata. Il 06/10 un tentativo su
# gemini-flash-latest è rimasto appeso 4 min 20 s prima del 503: senza
# timeout una richiesta bloccata ritarda (o blocca) tutta la run e i
# fallback non partono. Override da Railway: GEMINI_TIMEOUT_SECONDS.
REQUEST_TIMEOUT_SECONDS = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "60"))


def _is_model_gone(err: Exception) -> bool:
    """404 / NOT_FOUND = modello spento o inesistente: ritentare non serve,
    si passa subito al fallback successivo invece di sprecare il backoff."""
    msg = str(err)
    return "404" in msg or "NOT_FOUND" in msg


def _build_prompt(articles: List[Article], market_data: Dict[str, Any]) -> str:
    overall  = market_data["overall_label"]
    bull     = market_data["bull_pct"]
    bear     = market_data["bear_pct"]
    total    = market_data["total_articles"]

    # Category breakdown summary
    cat_summary = []
    for cat, stats in market_data["cat_stats"].items():
        if stats["count"] > 0:
            cat_summary.append(
                f"  - {cat.upper()}: {stats['count']} articles, sentiment={stats['sentiment']}"
            )

    # Top articles for Gemini
    top = sorted(articles, key=lambda a: a.score, reverse=True)[:MAX_ARTICLES_ANALYSIS]
    news_lines = []
    for i, a in enumerate(top, 1):
        pub = a.published.strftime("%H:%M UTC") if a.published else ""
        news_lines.append(
            f"{i}. [{a.category.upper()}] [{a.sentiment.upper()}] {a.source} {pub}\n"
            f"   HEADLINE: {a.title}\n"
            f"   SUMMARY: {a.summary[:250]}"
        )

    prompt = f"""You are a senior financial analyst at XenosFinance, a professional trading intelligence platform.

MARKET DATA SNAPSHOT:
- Overall Sentiment: {overall}
- Bullish signals: {bull:.0f}% | Bearish signals: {bear:.0f}%
- Total articles analyzed: {total}

CATEGORY BREAKDOWN:
{chr(10).join(cat_summary)}

TOP {len(top)} NEWS ARTICLES:
{chr(10).join(news_lines)}

---
TASK: Write a professional daily market intelligence brief for traders.

Use EXACTLY these section headers (with ## prefix):

## EXECUTIVE SUMMARY
Write 2-3 sentences summarizing the overall market tone and the single most important theme today.

## MACRO & CENTRAL BANKS
Key macro data releases, central bank signals, interest rate developments, bond market moves.

## EQUITIES
S&P 500, Nasdaq, European and Asian indices. Key sector moves. Earnings catalysts.

## COMMODITIES & ENERGY
Crude oil (WTI/Brent), gold, silver, natural gas. Supply/demand drivers. OPEC developments.

## CRYPTO
Bitcoin, Ethereum, altcoin market. Key on-chain or macro drivers.

## FOREX & RATES
US Dollar index, major pairs (EUR/USD, GBP/USD, USD/JPY). Treasury yields. FX volatility.

## GEOPOLITICAL RISK
Geopolitical events with direct market impact. Trade tensions, sanctions, elections.

## MARKET OUTLOOK
What to watch in the next 24-48 hours. Key risk events, data releases, technical levels.

RULES:
- Professional and concise. No filler sentences.
- Each section: 3-5 sentences maximum.
- Use specific asset names, numbers and percentages when available from the news.
- Do NOT use markdown bold (**text**) or italic (*text*).
- Do NOT add any intro or outro outside the sections.
- Write in present tense.
"""
    return prompt


class GeminiWriter:
    def __init__(self):
        self.client = None
        self._init_client()

    def _init_client(self):
        if not GEMINI_API_KEY:
            log.warning("GEMINI_API_KEY not set — AI analysis will be skipped")
            return
        try:
            from google import genai
            from google.genai import types
            # timeout in MILLISECONDI per l'SDK google-genai
            self.client = genai.Client(
                api_key=GEMINI_API_KEY,
                http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_SECONDS * 1000),
            )
            log.info(f"Gemini client ready ({GEMINI_MODEL}, timeout {REQUEST_TIMEOUT_SECONDS}s)")
        except ImportError:
            log.error("google-genai not installed. Run: pip install google-genai")
        except Exception as e:
            log.error(f"Gemini init failed: {e}")

    def generate(self, articles: List[Article], market_data: Dict[str, Any]) -> str:
        if not self.client:
            log.error("Gemini client not configured (missing/invalid API key) — signalling failure to caller (no publish)")
            return None

        prompt = _build_prompt(articles, market_data)
        log.info(f"Prompt: {len(prompt)} chars | Articles: {min(len(articles), MAX_ARTICLES_ANALYSIS)}")

        # Try the configured model first, then fall back to alternates if it
        # keeps failing — a persistent 503 usually means THAT model's
        # capacity is exhausted, not that Gemini as a whole is down.
        models_to_try = [GEMINI_MODEL] + [m for m in FALLBACK_MODELS if m != GEMINI_MODEL]

        for model_name in models_to_try:
            text = self._try_model(model_name, prompt)
            if text:
                return text
            log.warning(f"Model {model_name} exhausted its retries — trying next fallback" if model_name != models_to_try[-1] else f"Model {model_name} exhausted its retries — no more fallbacks")

        log.error("All Gemini models failed — signalling failure to caller (no publish)")
        return None

    def _try_model(self, model_name: str, prompt: str) -> str:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                log.info(f"Gemini request ({model_name}) attempt {attempt}/{MAX_RETRIES}...")
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )

                # Safe text extraction
                text = ""
                if hasattr(response, "text") and response.text:
                    text = response.text.strip()
                elif hasattr(response, "candidates") and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, "content") and candidate.content:
                        parts = candidate.content.parts or []
                        text = " ".join(p.text for p in parts if hasattr(p, "text")).strip()

                if not text:
                    raise ValueError("Empty response from Gemini")

                # Validate: must have at least some sections
                if "##" not in text:
                    log.warning("Response missing section headers — retrying")
                    raise ValueError("Response missing ## section headers")

                log.info(f"✓ Gemini response ({model_name}): {len(text)} chars")
                return text

            except Exception as e:
                log.warning(f"[{model_name}] Attempt {attempt} failed: {e}")
                if _is_model_gone(e):
                    log.warning(f"[{model_name}] model not available (404/NOT_FOUND) — skipping retries")
                    return None
                if attempt < MAX_RETRIES:
                    delay = min(RETRY_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
                    log.info(f"Retrying in {delay}s...")
                    time.sleep(delay)

        return None

    def _fallback_brief(self, market_data: Dict[str, Any]) -> str:
        """Kept for callers that explicitly want a degraded-but-labeled brief
        (e.g. an internal admin preview). NEVER auto-invoked by generate()
        anymore — a total Gemini failure now returns None so the pipeline
        can skip publishing instead of shipping raw, unedited headlines to
        users as if they were AI analysis."""
        cats = []
        for cat, stats in market_data.get("cat_stats", {}).items():
            if stats.get("count", 0) > 0:
                top = stats.get("top", [])
                headline = top[0].title if top else "No headlines"
                cats.append(f"## {cat.upper()}\n{headline}")

        return (
            f"## EXECUTIVE SUMMARY\n"
            f"Market sentiment is {market_data['overall_label']}. "
            f"Bullish signals: {market_data['bull_pct']:.0f}%. "
            f"Bearish signals: {market_data['bear_pct']:.0f}%. "
            f"Total articles analyzed: {market_data['total_articles']}.\n\n"
            + "\n\n".join(cats) +
            "\n\n## MARKET OUTLOOK\n"
            "AI brief temporarily unavailable. Monitor key economic releases and central bank communications."
        )
