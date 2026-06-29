import time
from typing import List, Dict, Any
from collectors.base_collector import Article
from config.settings import GEMINI_API_KEY, GEMINI_MODEL, MAX_ARTICLES_ANALYSIS
from utils.logger import get_logger

log = get_logger(__name__)

MAX_RETRIES  = 3
RETRY_DELAY  = 5  # seconds between retries


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
            self.client = genai.Client(api_key=GEMINI_API_KEY)
            log.info(f"Gemini client ready ({GEMINI_MODEL})")
        except ImportError:
            log.error("google-genai not installed. Run: pip install google-genai")
        except Exception as e:
            log.error(f"Gemini init failed: {e}")

    def generate(self, articles: List[Article], market_data: Dict[str, Any]) -> str:
        if not self.client:
            log.warning("Gemini not available — using fallback")
            return self._fallback_brief(market_data)

        prompt = _build_prompt(articles, market_data)
        log.info(f"Prompt: {len(prompt)} chars | Articles: {min(len(articles), MAX_ARTICLES_ANALYSIS)}")

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                log.info(f"Gemini request attempt {attempt}/{MAX_RETRIES}...")
                response = self.client.models.generate_content(
                    model=GEMINI_MODEL,
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

                log.info(f"✓ Gemini response: {len(text)} chars")
                return text

            except Exception as e:
                log.warning(f"Attempt {attempt} failed: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    log.error("All Gemini attempts failed — using fallback")
                    return self._fallback_brief(market_data)

        return self._fallback_brief(market_data)

    def _fallback_brief(self, market_data: Dict[str, Any]) -> str:
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
