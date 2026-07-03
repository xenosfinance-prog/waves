import os
import re
from datetime import datetime, timezone
from typing import List, Dict, Any

from base_collector import Article
from settings import CATEGORY_LABELS, OUTPUT_PATH
from helpers import format_dt, sentiment_emoji
from logger import get_logger

log = get_logger(__name__)

SENTIMENT_COLORS = {
    "bullish":  "#22c55e",
    "bearish":  "#ef4444",
    "neutral":  "#8892a4",
    "mixed":    "#f0c040",
    "risk-on":  "#22c55e",
    "risk-off": "#ef4444",
}


def _md_to_html(text: str) -> str:
    """Convert simple markdown to HTML for Gemini output."""
    lines = text.split("\n")
    out   = []
    for line in lines:
        line = line.rstrip()
        if line.startswith("## "):
            out.append(f'<h3 class="brief-section-title">{line[3:]}</h3>')
        elif line.startswith("# "):
            out.append(f'<h2 class="brief-title">{line[2:]}</h2>')
        elif line.startswith("- "):
            out.append(f'<li>{line[2:]}</li>')
        elif line == "":
            out.append("<br>")
        else:
            out.append(f'<p class="brief-p">{line}</p>')
    return "\n".join(out)


def _sentiment_bar(bull: float, bear: float) -> str:
    neut = max(0, 100 - bull - bear)
    return f"""
    <div class="sent-bar-wrap">
      <div class="sent-bar-label">
        <span style="color:#22c55e">▲ {bull:.0f}% Bullish</span>
        <span style="color:#8892a4">● {neut:.0f}% Neutral</span>
        <span style="color:#ef4444">▼ {bear:.0f}% Bearish</span>
      </div>
      <div class="sent-bar">
        <div class="sent-bull" style="width:{bull:.0f}%"></div>
        <div class="sent-neut" style="width:{neut:.0f}%"></div>
        <div class="sent-bear" style="width:{bear:.0f}%"></div>
      </div>
    </div>"""


def _article_card(a: Article) -> str:
    color   = SENTIMENT_COLORS.get(a.sentiment, "#8892a4")
    emoji   = sentiment_emoji(a.sentiment)
    pub     = format_dt(a.published)
    cat_lbl = CATEGORY_LABELS.get(a.category, a.category)
    return f"""
    <div class="article-card">
      <div class="article-meta">
        <span class="article-cat">{cat_lbl}</span>
        <span class="article-source">{a.source}</span>
        <span class="article-date">{pub}</span>
        <span class="article-sent" style="color:{color}">{emoji} {a.sentiment}</span>
      </div>
      <a class="article-title" href="{a.url}" target="_blank" rel="noopener">{a.title}</a>
      <p class="article-summary">{a.summary}</p>
    </div>"""


def _category_section(cat: str, stats: Dict, all_articles: List[Article]) -> str:
    label   = CATEGORY_LABELS.get(cat, cat)
    arts    = [a for a in all_articles if a.category == cat]
    if not arts:
        return ""
    color   = SENTIMENT_COLORS.get(stats["sentiment"], "#8892a4")
    emoji   = sentiment_emoji(stats["sentiment"])
    cards   = "\n".join(_article_card(a) for a in
                        sorted(arts, key=lambda x: x.score, reverse=True)[:8])
    return f"""
    <section class="cat-section" id="cat-{cat}">
      <div class="cat-header">
        <span class="cat-label">{label}</span>
        <span class="cat-sentiment" style="color:{color}">{emoji} {stats['sentiment'].upper()}</span>
        <span class="cat-count">{stats['count']} articles</span>
      </div>
      <div class="articles-grid">
        {cards}
      </div>
    </section>"""


class HTMLWriter:
    def write(
        self,
        articles:    List[Article],
        market_data: Dict[str, Any],
        ai_brief:    str,
        output_path: str = OUTPUT_PATH,
    ) -> str:
        now    = datetime.now(timezone.utc)
        ts_str = now.strftime("%A, %d %B %Y — %H:%M UTC")

        # Sentiment bar
        sent_bar = _sentiment_bar(market_data["bull_pct"], market_data["bear_pct"])

        # AI brief html
        ai_html = _md_to_html(ai_brief)

        # Category sections
        cat_sections = "\n".join(
            _category_section(cat, market_data["cat_stats"].get(cat, {"count": 0, "sentiment": "neutral"}), articles)
            for cat in ["macro", "equities", "commodities", "crypto", "forex", "geopolitics"]
        )

        # Category nav tabs
        cat_tabs = "\n".join(
            f'<a class="cat-tab" href="#cat-{cat}">{CATEGORY_LABELS[cat]}</a>'
            for cat in ["macro", "equities", "commodities", "crypto", "forex", "geopolitics"]
        )

        overall_color = SENTIMENT_COLORS.get(market_data["overall_sentiment"], "#8892a4")

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>XenosFinance · Market Intelligence Brief</title>
<meta name="description" content="AI-powered daily financial market intelligence brief — Macro, Equities, Commodities, Crypto, Forex. Powered by XenosFinance.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;800&family=IBM+Plex+Mono:wght@400;500&family=PT+Serif:ital,wght@0,400;1,400&display=swap" rel="stylesheet">
<style>
:root {{
  --bg:     #0a1020;
  --bg2:    #0f1828;
  --bg3:    #162035;
  --border: #1e2d45;
  --ink:    #d8e8f8;
  --ink2:   #b0c4d8;
  --muted:  #6878a0;
  --gold:   #3b82f6;
  --gold2:  #60a5fa;
  --green:  #22c55e;
  --red:    #ef4444;
  --yellow: #f0c040;
  --mono:   'IBM Plex Mono', monospace;
  --serif:  'PT Serif', Georgia, serif;
  --head:   'Playfair Display', Georgia, serif;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  background: var(--bg);
  color: var(--ink);
  font-family: var(--serif);
  font-size: 14px;
  line-height: 1.7;
}}
a {{ color: var(--gold2); text-decoration: none; }}
a:hover {{ color: var(--ink); }}

/* ── Masthead ── */
.masthead {{
  background: var(--bg2);
  border-bottom: 1px solid var(--border);
  padding: 0 24px;
}}
.masthead-top {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 2px;
  color: var(--muted);
  text-transform: uppercase;
  border-bottom: 1px solid var(--border);
}}
.masthead-center {{
  text-align: center;
  padding: 24px 0 20px;
}}
.masthead-eyebrow {{
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 4px;
  color: var(--gold2);
  text-transform: uppercase;
  margin-bottom: 8px;
}}
.masthead-name {{
  font-family: var(--head);
  font-size: clamp(32px, 5vw, 64px);
  font-weight: 800;
  letter-spacing: -1px;
  color: var(--ink);
  line-height: 1;
}}
.masthead-name span {{ color: var(--gold2); }}
.masthead-sub {{
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 3px;
  color: var(--muted);
  text-transform: uppercase;
  margin-top: 8px;
}}
.masthead-nav {{
  display: flex;
  justify-content: center;
  gap: 0;
  border-top: 1px solid var(--border);
  flex-wrap: wrap;
}}
.nav-btn {{
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--muted);
  padding: 10px 16px;
  border-right: 1px solid var(--border);
  transition: color 0.2s;
}}
.nav-btn:hover {{ color: var(--gold2); }}
.nav-btn.active {{ color: var(--gold2); border-bottom: 2px solid var(--gold2); }}

/* ── Layout ── */
.wrap {{ max-width: 1200px; margin: 0 auto; padding: 0 20px 60px; }}

/* ── Sentiment Hero ── */
.sentiment-hero {{
  text-align: center;
  padding: 36px 20px 28px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 32px;
}}
.sentiment-label {{
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 4px;
  color: var(--muted);
  text-transform: uppercase;
  margin-bottom: 10px;
}}
.sentiment-value {{
  font-family: var(--head);
  font-size: 48px;
  font-weight: 800;
  line-height: 1;
  margin-bottom: 8px;
}}
.sentiment-stats {{
  font-family: var(--mono);
  font-size: 10px;
  color: var(--muted);
  margin-bottom: 20px;
  letter-spacing: 1px;
}}
.sent-bar-wrap {{ max-width: 500px; margin: 0 auto; }}
.sent-bar-label {{
  display: flex;
  justify-content: space-between;
  font-family: var(--mono);
  font-size: 9px;
  margin-bottom: 6px;
}}
.sent-bar {{
  display: flex;
  height: 6px;
  border-radius: 3px;
  overflow: hidden;
  background: var(--bg3);
}}
.sent-bull {{ background: #22c55e; }}
.sent-neut {{ background: #334155; }}
.sent-bear {{ background: #ef4444; }}

/* ── AI Brief ── */
.ai-section {{
  background: var(--bg2);
  border: 1px solid var(--border);
  padding: 28px 32px;
  margin-bottom: 40px;
}}
.ai-header {{
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}}
.ai-badge {{
  font-family: var(--mono);
  font-size: 8px;
  letter-spacing: 3px;
  text-transform: uppercase;
  background: rgba(59,130,246,0.15);
  color: var(--gold2);
  border: 1px solid rgba(59,130,246,0.3);
  padding: 3px 10px;
}}
.ai-title {{
  font-family: var(--head);
  font-size: 20px;
  font-weight: 700;
}}
.brief-section-title {{
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: var(--gold2);
  margin: 20px 0 8px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}}
.brief-p {{
  color: var(--ink2);
  font-size: 13px;
  line-height: 1.75;
  margin-bottom: 4px;
}}

/* ── Category Nav ── */
.cat-nav {{
  display: flex;
  gap: 0;
  border: 1px solid var(--border);
  margin-bottom: 32px;
  overflow-x: auto;
}}
.cat-tab {{
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--muted);
  padding: 10px 14px;
  white-space: nowrap;
  border-right: 1px solid var(--border);
  transition: all 0.2s;
}}
.cat-tab:hover {{ color: var(--gold2); background: var(--bg2); }}

/* ── Category Section ── */
.cat-section {{ margin-bottom: 48px; }}
.cat-header {{
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}}
.cat-label {{
  font-family: var(--head);
  font-size: 20px;
  font-weight: 700;
}}
.cat-sentiment {{
  font-family: var(--mono);
  font-size: 9px;
  letter-spacing: 2px;
  text-transform: uppercase;
}}
.cat-count {{
  font-family: var(--mono);
  font-size: 9px;
  color: var(--muted);
  margin-left: auto;
}}

/* ── Article Cards ── */
.articles-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 1px;
  background: var(--border);
}}
.article-card {{
  background: var(--bg2);
  padding: 16px;
  transition: background 0.2s;
}}
.article-card:hover {{ background: var(--bg3); }}
.article-meta {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}}
.article-cat {{
  font-family: var(--mono);
  font-size: 8px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--gold2);
}}
.article-source {{
  font-family: var(--mono);
  font-size: 8px;
  color: var(--muted);
}}
.article-date {{
  font-family: var(--mono);
  font-size: 8px;
  color: var(--muted);
  margin-left: auto;
}}
.article-sent {{
  font-family: var(--mono);
  font-size: 8px;
  letter-spacing: 1px;
  text-transform: uppercase;
}}
.article-title {{
  display: block;
  font-family: var(--head);
  font-size: 15px;
  font-weight: 700;
  color: var(--ink);
  line-height: 1.35;
  margin-bottom: 8px;
  transition: color 0.2s;
}}
.article-title:hover {{ color: var(--gold2); }}
.article-summary {{
  font-size: 12px;
  color: var(--ink2);
  line-height: 1.65;
}}

/* ── Footer ── */
.page-footer {{
  border-top: 1px solid var(--border);
  padding: 16px 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: var(--mono);
  font-size: 9px;
  color: var(--muted);
  letter-spacing: 1px;
  margin-top: 40px;
}}
.footer-links {{ display: flex; gap: 20px; }}
.footer-links a {{ color: var(--muted); }}
.footer-links a:hover {{ color: var(--gold2); }}

@media (max-width: 640px) {{
  .articles-grid {{ grid-template-columns: 1fr; }}
  .cat-header {{ flex-wrap: wrap; }}
  .sentiment-value {{ font-size: 32px; }}
  .ai-section {{ padding: 16px; }}
}}
</style>
</head>
<body>

<!-- Masthead -->
<div class="masthead">
  <div class="masthead-top">
    <span>XenosFinance · Market Intelligence</span>
    <span>{ts_str}</span>
    <span>AI-Powered Brief</span>
  </div>
  <div class="masthead-center">
    <div class="masthead-eyebrow">Financial Intelligence · Global Markets</div>
    <div class="masthead-name">XENOS<span>FINANCE</span></div>
    <div class="masthead-sub">Market Intelligence Brief · Powered by AI</div>
  </div>
  <nav class="masthead-nav">
    <a class="nav-btn" href="https://xenosfinance.com">📰 News</a>
    <a class="nav-btn active" href="https://xenosfinance.com/market-brief">🤖 Market Brief</a>
    <a class="nav-btn" href="https://xenosfinance.com/dashboard">📊 Dashboard</a>
    <a class="nav-btn" href="https://xenosfinance.com/xenoswaves_charts">◈ Charts</a>
    <a class="nav-btn" href="https://xenosfinance.com/XenosBlog">✦ AI Blog</a>
    <a class="nav-btn" href="https://xenosfinance.com/trading-signals">📡 Live Signals</a>
    <a class="nav-btn" href="https://xenosfinance.com/calendar">🗓 Calendar</a>
    <a class="nav-btn" href="https://xenosfinance.com/premium-support">✦ Premium</a>
  </nav>
</div>

<div class="wrap">

  <!-- Sentiment Hero -->
  <div class="sentiment-hero">
    <div class="sentiment-label">Overall Market Sentiment</div>
    <div class="sentiment-value" style="color:{overall_color}">{market_data['overall_label']}</div>
    <div class="sentiment-stats">
      {market_data['total_articles']} articles analyzed · {ts_str}
    </div>
    {sent_bar}
  </div>

  <!-- AI Brief -->
  <section class="ai-section">
    <div class="ai-header">
      <span class="ai-badge">✦ AI Analysis</span>
      <span class="ai-title">Market Intelligence Brief</span>
    </div>
    <div class="ai-content">
      {ai_html}
    </div>
  </section>

  <!-- Category Navigation -->
  <nav class="cat-nav">
    {cat_tabs}
  </nav>

  <!-- Category Sections -->
  {cat_sections}

  <!-- Footer -->
  <footer class="page-footer">
    <span>© XenosFinance 2026</span>
    <div class="footer-links">
      <a href="https://xenosfinance.com">Home</a>
      <a href="https://xenosfinance.com/dashboard">Dashboard</a>
      <a href="https://t.me/xenosfin" target="_blank">Telegram</a>
      <a href="https://xenosfinance.com/premium-support">Premium</a>
    </div>
    <span>⚠ Not investment advice</span>
  </footer>

</div>
</body>
</html>"""

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        log.info(f"HTML written → {output_path} ({len(html):,} chars)")
        return output_path
