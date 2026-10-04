#!/usr/bin/env python3
"""
gen_analysis_pages.py — XenosFinance daily analysis pages (SEO)

Genera pagine statiche indicizzabili da Google:
  analysis/index.html          → https://xenosfinance.com/analysis
  analysis/<slug>.html         → https://xenosfinance.com/analysis/<slug>
e aggiorna sitemap.xml.

Eseguito da GitHub Actions (.github/workflows/analysis-pages.yml) due volte
al giorno. Usa lo stesso motore di ew_server.py della dashboard
(_ta_compute), qui su H1 con contesto H4: TUTTI i numeri sono calcolati in
codice; l'AI (Claude) scrive solo il commento, con regole rigide (nessun
numero inventato). Se l'AI non risponde la pagina viene comunque generata
con la parte calcolata. Se il calcolo di uno strumento fallisce, la pagina
precedente resta invariata.

Env: ANTHROPIC_API_KEY (secret del repository).
"""

import json
import os
import re
import sys
import html
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import ew_server as E  # noqa: E402  (motore condiviso con la dashboard)

SITE = "https://xenosfinance.com"
OUT_DIR = os.path.join(ROOT, "analysis")
SITEMAP = os.path.join(ROOT, "sitemap.xml")
MODEL = "claude-sonnet-4-6"

INSTRUMENTS = [
    # slug, yfinance, display name, short label, decimals, group, search terms
    ("gold",            "GC=F",     "Gold",            "XAU/USD",  2, "Commodities", "gold price, XAU/USD"),
    ("silver",          "SI=F",     "Silver",          "XAG/USD",  3, "Commodities", "silver price, XAG/USD"),
    ("wti-crude-oil",   "CL=F",     "WTI Crude Oil",   "WTI",      2, "Commodities", "oil price, WTI crude, CL futures"),
    ("brent-crude-oil", "BZ=F",     "Brent Crude Oil", "Brent",    2, "Commodities", "Brent oil price, Brent crude"),
    ("natural-gas",     "NG=F",     "Natural Gas",     "NG",       3, "Commodities", "natural gas price, NG futures"),
    ("copper",          "HG=F",     "Copper",          "HG",       4, "Commodities", "copper price, HG futures"),
    ("eur-usd",         "EURUSD=X", "EUR/USD",         "EUR/USD",  5, "Forex",       "euro dollar, EURUSD"),
    ("gbp-usd",         "GBPUSD=X", "GBP/USD",         "GBP/USD",  5, "Forex",       "pound dollar, cable, GBPUSD"),
    ("usd-jpy",         "USDJPY=X", "USD/JPY",         "USD/JPY",  3, "Forex",       "dollar yen, USDJPY"),
    ("usd-chf",         "USDCHF=X", "USD/CHF",         "USD/CHF",  5, "Forex",       "dollar franc, USDCHF"),
    ("bitcoin",         "BTC-USD",  "Bitcoin",         "BTC/USD",  0, "Crypto",      "bitcoin price, BTC/USD"),
    ("ethereum",        "ETH-USD",  "Ethereum",        "ETH/USD",  2, "Crypto",      "ethereum price, ETH/USD"),
    ("sp500",           "^GSPC",    "S&P 500",         "SPX",      2, "Indices",     "S&P 500, SPX, US stocks"),
    ("nasdaq",          "^IXIC",    "Nasdaq Composite", "NASDAQ",  2, "Indices",     "Nasdaq, tech stocks"),
    ("dax",             "^GDAXI",   "DAX 40",          "DAX",      2, "Indices",     "DAX, German stocks"),
]

SCEN_NAME = {
    "long_pullback": "Bullish aggressive (pullback)",
    "long_breakout": "Bullish conservative (breakout)",
    "short_rejection": "Bearish aggressive (rejection)",
    "short_breakdown": "Bearish conservative (breakdown)",
}
MEMBER_NAME = {"prev_high": "Previous-day high", "prev_low": "Previous-day low",
               "swing_high": "Swing high", "swing_low": "Swing low", "ew_inv": "Elliott invalidation"}
REGIME = {"above_cloud": "above the cloud", "below_cloud": "below the cloud", "inside_cloud": "inside the cloud"}

# 2026-10: intestazione chiara (il bias è su 1H/4H, la pagina si aggiorna ogni giorno)
TF_LABEL = "Daily refresh · 1H/4H technical bias"

# 2026-10: spread Brent–WTI (calcolato in main quando ci sono entrambi i prezzi)
SPREAD = None


def market_closed(now, group):
    """Forex, materie prime e indici chiusi nel weekend (ven 21:00 UTC → dom 22:00 UTC). Crypto sempre aperte."""
    if group == "Crypto":
        return False
    wd, h = now.weekday(), now.hour
    return wd == 5 or (wd == 6 and h < 22) or (wd == 4 and h >= 21)


def spread_html():
    """Riga sullo spread Brent–WTI: spiega perché i due benchmark possono avere bias diversi sull'1H."""
    if not SPREAD:
        return ""
    v = SPREAD
    side = "Brent premium" if v >= 0 else "WTI premium"
    return (f'<p class="spread">Brent–WTI spread: <b>${abs(v):.2f}</b> ({side}). '
            "The two benchmarks usually move together, but on 1-hour charts they can show different biases "
            "while the spread is widening or narrowing.</p>")


def esc(t):
    return html.escape(str(t if t is not None else ""), quote=True)


def fmt(v, dec):
    if v is None:
        return "—"
    return f"{v:,.{dec}f}" if dec <= 2 and abs(v) >= 1000 else f"{v:.{dec}f}"


def zone_txt(z, dec):
    return fmt(z["low"], dec) if z["low"] == z["high"] else f"{fmt(z['low'], dec)}–{fmt(z['high'], dec)}"


# ───────────────────────── AI commentary ─────────────────────────
def ai_commentary(name, data):
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return None
    prompt = f"""You are a senior technical analyst at an institutional desk writing the daily analysis page for XenosFinance, a market analysis and trading education platform.
Instrument: {name} — 1-hour chart with 4-hour context. All data below is ALREADY CALCULATED by our engine:

{json.dumps(data, ensure_ascii=False)}

Write in English. Return ONLY minified JSON, no fences:
{{"headline":"<max 10 words, journalistic, describes today's technical picture>","summary":"<60-80 words: price, recent move, where it sits vs the key zones, overall bias>","trend":"<50-70 words: moving averages, SuperTrend, 4-hour Ichimoku context>","momentum":"<40-60 words: RSI, MACD, volume if given>","structure":"<40-60 words: last swing, Fibonacci levels, Elliott wave position if given>","outlook":"<60-80 words: what confirms the bullish case and the bearish case using the trigger levels, which scenarios have favourable risk/reward>"}}

STRICT RULES:
- Use ONLY numbers present in the data. Never invent prices, percentages or levels; never recompute risk/reward.
- The bias is already decided ({data['bias']['direction']}, confidence {data['bias']['confidence']}): stay consistent with it.
- If "elliott" is null, do not mention Elliott waves. If volume_ratio is null, do not mention volume.
- Educational technical analysis only: no news, no fundamentals, never tell the reader to buy or sell."""
    try:
        client = E.anthropic.Anthropic(api_key=key)
        msg = client.messages.create(model=MODEL, max_tokens=1200,
                                     messages=[{"role": "user", "content": prompt}])
        txt = msg.content[0].text.strip().replace("```json", "").replace("```", "").strip()
        a, b = txt.find("{"), txt.rfind("}")
        out = json.loads(txt[a:b + 1])
        return out if out.get("summary") else None
    except Exception as e:
        print(f"  ! AI commentary failed: {e}")
        return None


# ───────────────────────── HTML ─────────────────────────
CSS = """:root{--bg:#0f1724;--bg2:#131f2e;--bg3:#172032;--ink:#e2eaf4;--ink2:#b8cce0;--muted:#5a7a9a;--border:#1e3050;--border2:#243a5e;--red2:#f87171;--green2:#34d399;--gold:#3b82f6;--mono:'IBM Plex Mono',monospace;--serif:'Playfair Display',Georgia,serif;--body:'PT Serif',Georgia,serif;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--ink);font-family:var(--body);line-height:1.7;}
a{color:var(--gold);text-decoration:none;} a:hover{text-decoration:underline;}
.top{border-bottom:3px double var(--gold);text-align:center;padding:22px 20px 14px;}
.brand{font-family:var(--serif);font-size:34px;font-weight:900;letter-spacing:-1px;text-transform:uppercase;color:var(--ink);}
.brand span{color:var(--gold);}
.tag{font-family:var(--mono);font-size:9px;letter-spacing:4px;color:var(--muted);text-transform:uppercase;margin-top:4px;}
nav{display:flex;flex-wrap:wrap;justify-content:center;border-bottom:1px solid var(--border);background:var(--bg2);}
nav a{font-family:var(--mono);font-size:10px;letter-spacing:2px;text-transform:uppercase;padding:11px 18px;color:var(--muted);}
nav a.on,nav a:hover{color:var(--gold);text-decoration:none;}
main{max-width:980px;margin:0 auto;padding:26px 22px 60px;}
.crumb{font-family:var(--mono);font-size:10px;color:var(--muted);letter-spacing:1px;margin-bottom:14px;}
h1{font-family:var(--serif);font-size:34px;line-height:1.2;margin-bottom:6px;}
.upd{font-family:var(--mono);font-size:10px;color:var(--muted);letter-spacing:1px;margin-bottom:16px;}
.headline{font-family:var(--serif);font-size:21px;color:var(--ink2);margin:8px 0 14px;font-style:italic;}
.px{font-family:var(--mono);font-size:13px;margin-bottom:10px;}
.up{color:var(--green2);} .dn{color:var(--red2);}
.bias{display:inline-flex;gap:10px;align-items:center;font-family:var(--mono);font-size:10px;letter-spacing:2px;text-transform:uppercase;margin-bottom:6px;}
.bias b{padding:3px 10px;border:1px solid currentColor;font-weight:500;}
.bias.bullish b{color:var(--green2);} .bias.bearish b{color:var(--red2);} .bias.neutral b{color:#facc15;}
.bias span{color:var(--muted);}
h2{font-family:var(--mono);font-size:11px;letter-spacing:3px;text-transform:uppercase;color:var(--gold);margin:30px 0 10px;border-bottom:1px solid var(--border);padding-bottom:6px;}
p{color:var(--ink2);margin-bottom:10px;font-size:15px;}
table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:12px;margin:6px 0 4px;}
th{text-align:left;font-size:9px;letter-spacing:2px;text-transform:uppercase;color:var(--muted);font-weight:normal;padding:6px 8px;border-bottom:1px solid var(--border2);}
td{padding:8px;border-bottom:1px solid var(--border);color:var(--ink);}
td.m{color:var(--muted);font-size:11px;}
.q{font-size:9px;letter-spacing:1px;text-transform:uppercase;padding:1px 6px;border:1px solid currentColor;}
.q.good{color:var(--green2);} .q.ok{color:#facc15;} .q.poor{color:var(--red2);}
tr.poor td{color:var(--muted);}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:22px;}
.trig{font-family:var(--mono);font-size:12px;margin:6px 0;}
.box{border:1px solid var(--border2);background:var(--bg2);padding:16px 18px;margin-top:26px;}
.box p{font-size:14px;}
.cta a{display:inline-block;margin:6px 10px 0 0;font-family:var(--mono);font-size:11px;letter-spacing:1px;padding:9px 16px;border:1px solid var(--gold);color:var(--ink);}
.rel{display:flex;flex-wrap:wrap;gap:8px;}
.rel a{font-family:var(--mono);font-size:11px;border:1px solid var(--border2);padding:6px 10px;color:var(--ink2);}
.faq h3{font-family:var(--body);font-size:16px;color:var(--ink);margin:14px 0 4px;}
.disc{font-family:var(--mono);font-size:10px;color:var(--muted);line-height:1.6;margin-top:34px;border-top:1px solid var(--border);padding-top:14px;}
@media(max-width:720px){h1{font-size:26px;}.grid{grid-template-columns:1fr;}table{font-size:11px;}th,td{padding:5px;}}"""


def page_shell(title, desc, canonical, body, jsonld, keywords):
    ld = "\n".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in jsonld)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="keywords" content="{esc(keywords)}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="article">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="XenosFinance">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
<link rel="icon" type="image/x-icon" href="/favicon.ico">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
<link rel="apple-touch-icon" sizes="192x192" href="/favicon-192.png">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=PT+Serif:ital,wght@0,400;0,700;1,400&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS}</style>
{ld}
</head>
<body>
<header class="top"><div class="brand">Xenos<span>Finance</span></div><div class="tag">Market analysis &amp; trading education</div></header>
<nav><a href="/">Home</a><a href="/dashboard">Dashboard</a><a href="/analysis" class="on">Daily Analysis</a><a href="/calendar">Calendar</a><a href="/elliottwave">Elliott Wave</a><a href="/trading-signals">Trade Setups</a><a href="/premium">Premium</a></nav>
<main>
{body}
<div class="disc">Educational content only. This analysis is generated algorithmically from public market data for market analysis and trading education purposes and does not constitute investment advice or a recommendation to buy or sell any financial instrument. Trading involves a significant risk of loss. © XenosFinance</div>
</main>
</body>
</html>
"""


def build_instrument_page(inst, d, ai, now, all_rows):
    slug, yf, name, short, dec, group, terms = inst
    f = lambda v: fmt(v, dec)
    url = f"{SITE}/analysis/{slug}"
    date_h = now.strftime("%d %B %Y")
    dirw = d["bias"]["direction"]
    bias_word = {"bullish": "Bullish", "bearish": "Bearish", "neutral": "Neutral"}[dirw]
    chg = d.get("change_pct_day")
    sup = d["zones"]["supports"]
    res = d["zones"]["resistances"]

    title = f"{name} Technical Analysis Today — Levels, Bias & Scenarios ({short}) | XenosFinance"
    s1 = zone_txt(sup[0], dec) if sup else None
    r1 = zone_txt(res[0], dec) if res else None
    desc = (f"{name} ({short}) technical analysis for {date_h}: {bias_word.lower()} bias on the 1-hour chart"
            + (f", support {s1}" if s1 else "") + (f", resistance {r1}" if r1 else "")
            + ". Confluence zones, Elliott Wave, trade scenarios with risk/reward.")

    b = [f'<div class="crumb"><a href="/">Home</a> › <a href="/analysis">Daily Analysis</a> › {esc(name)}</div>',
         f"<h1>{esc(name)} Technical Analysis Today</h1>",
         f'<div class="upd">Updated {now.strftime("%d %b %Y, %H:%M")} UTC · {TF_LABEL} · {esc(group)}</div>']
    if market_closed(now, group):
        b.append('<div class="upd">Market closed — data as of Friday close</div>')
    if slug in ("wti-crude-oil", "brent-crude-oil"):
        b.append(spread_html())
    if ai and ai.get("headline"):
        b.append(f'<div class="headline">{esc(ai["headline"])}</div>')
    b.append(f'<div class="px">{esc(short)} <b>{f(d["live"])}</b>'
             + (f' <span class="{"up" if chg >= 0 else "dn"}">{chg:+.2f}%</span>' if chg is not None else "")
             + f' · ATR(14) {f(d["atr"])}</div>')
    b.append(f'<div class="bias {dirw}"><span>Bias</span><b>{bias_word}</b><span>Confidence {d["bias"]["confidence"]} · score {d["bias"]["score"]:+d}/7</span></div>')

    if ai:
        b.append("<h2>Summary</h2>")
        b.append(f"<p>{esc(ai.get('summary', ''))}</p>")

    # Zone
    def zrows(zs):
        if not zs:
            return '<tr><td colspan="3" class="m">No level within range</td></tr>'
        return "".join(f'<tr><td>{zone_txt(z, dec)}</td><td class="m">{esc(" + ".join(MEMBER_NAME.get(m, m) for m in z["members"]))}</td><td>{"●" * min(z["strength"], 4)}</td></tr>' for z in zs)
    b.append("<h2>Key levels — confluence zones</h2>")
    b.append("<p>Zones where several technical levels cluster together (moving averages, SuperTrend, Fibonacci retracements, previous-day range, swing points). More converging levels mean a more relevant zone.</p>")
    b.append('<div class="grid"><div><table><tr><th>Resistance</th><th>Levels</th><th>Strength</th></tr>' + zrows(res)
             + '</table></div><div><table><tr><th>Support</th><th>Levels</th><th>Strength</th></tr>' + zrows(sup) + "</table></div></div>")

    # Trend & momentum
    ind = d["indicators"]
    b.append("<h2>Trend</h2>")
    if ai and ai.get("trend"):
        b.append(f"<p>{esc(ai['trend'])}</p>")
    h1c = d.get("h1")
    b.append("<table><tr><th>Indicator</th><th>Value</th><th>Reading</th></tr>"
             f'<tr><td>SMA 20</td><td>{f(ind["sma20"])}</td><td class="m">{"price above" if ind["sma20"] and d["live"] > ind["sma20"] else "price below"}</td></tr>'
             f'<tr><td>SMA 50</td><td>{f(ind["sma50"])}</td><td class="m">{"price above" if ind["sma50"] and d["live"] > ind["sma50"] else "price below"}</td></tr>'
             f'<tr><td>SMA 200</td><td>{f(ind["sma200"])}</td><td class="m">{"price above" if ind["sma200"] and d["live"] > ind["sma200"] else "price below"}</td></tr>'
             f'<tr><td>SuperTrend (10,3)</td><td>{f(ind["supertrend"])}</td><td class="m">{"bullish" if ind["supertrend_dir"] == "up" else "bearish"}</td></tr>'
             + (f'<tr><td>Ichimoku 4H</td><td>{REGIME.get(h1c["regime"], h1c["regime"])}</td><td class="m">{h1c["bull_score"]}/4 bullish · {h1c["bear_score"]}/4 bearish</td></tr>' if h1c else "")
             + "</table>")
    b.append("<h2>Momentum</h2>")
    if ai and ai.get("momentum"):
        b.append(f"<p>{esc(ai['momentum'])}</p>")
    b.append("<table><tr><th>Indicator</th><th>Value</th></tr>"
             f'<tr><td>RSI (14)</td><td>{ind["rsi"]}</td></tr>'
             f'<tr><td>MACD / signal</td><td>{ind["macd"]} / {ind["macd_signal"]}</td></tr>'
             + (f'<tr><td>Volume vs 40-bar average</td><td>×{ind["volume_ratio"]}</td></tr>' if ind.get("volume_ratio") else "")
             + "</table>")

    # Struttura
    b.append("<h2>Structure — swing, Fibonacci and Elliott Wave</h2>")
    if ai and ai.get("structure"):
        b.append(f"<p>{esc(ai['structure'])}</p>")
    rows = ""
    if d.get("swing"):
        sw = d["swing"]
        rows += f'<tr><td>Last swing</td><td>{f(sw["from"])} → {f(sw["to"])} ({sw["dir"]})</td></tr>'
    for k, v in (d.get("fib") or {}).items():
        rows += f"<tr><td>Fibonacci {k}%</td><td>{f(v)}</td></tr>"
    if d.get("elliott"):
        ew = d["elliott"]
        rows += f'<tr><td>Elliott Wave</td><td>{esc(ew["desc"])}</td></tr>'
        if ew.get("invalidation") is not None:
            rows += f'<tr><td>Elliott invalidation</td><td>{f(ew["invalidation"])}</td></tr>'
        tps = [f(t) for t in (ew.get("tp1"), ew.get("tp2")) if t is not None]
        if tps:
            rows += f'<tr><td>Elliott targets</td><td>{" · ".join(tps)}</td></tr>'
    pdv = d.get("prev_day") or {}
    if pdv.get("high") is not None and pdv.get("low") is not None:
        rows += f'<tr><td>Previous-day range</td><td>{f(pdv["low"])} – {f(pdv["high"])}</td></tr>'
    if rows:
        b.append(f"<table><tr><th>Element</th><th>Level</th></tr>{rows}</table>")

    # Scenari
    if d.get("scenarios"):
        b.append("<h2>Trade scenarios</h2>")
        b.append("<p>Educational scenarios built from the confluence zones. Entry, stop and target are calculated by our engine; risk/reward is computed from the published numbers, and scenarios with an unfavourable ratio are flagged rather than presented as opportunities.</p>")
        t = "<table><tr><th>Scenario</th><th>Entry</th><th>Stop</th><th>Target</th><th>R:R</th><th>Quality</th></tr>"
        for sc in d["scenarios"]:
            ql = {"good": "good", "ok": "acceptable", "poor": "unfavourable"}[sc["quality"]]
            t += (f'<tr class="{sc["quality"]}"><td>{SCEN_NAME.get(sc["key"], sc["key"])}</td><td>{f(sc["entry"])}</td>'
                  f'<td>{f(sc["stop"])}</td><td>{f(sc["target"])}</td><td>{sc["rr"]:.2f}:1</td><td><span class="q {sc["quality"]}">{ql}</span></td></tr>')
        b.append(t + "</table>")

    b.append("<h2>Outlook and confirmation</h2>")
    if ai and ai.get("outlook"):
        b.append(f"<p>{esc(ai['outlook'])}</p>")
    tr = d.get("trigger") or {}
    if tr.get("bull") is not None:
        b.append(f'<div class="trig up">▲ Bullish confirmation: hourly close above {f(tr["bull"])}</div>')
    if tr.get("bear") is not None:
        b.append(f'<div class="trig dn">▼ Bearish confirmation: hourly close below {f(tr["bear"])}</div>')

    # FAQ deterministica (numeri dal motore, nessun testo AI)
    faq = [
        (f"What is the {name} trend today?",
         f"On the 1-hour chart our engine reads a {bias_word.lower()} bias with {d['bias']['confidence']} confidence (score {d['bias']['score']:+d}/7), "
         f"based on moving averages, MACD, RSI, SuperTrend and the 4-hour Ichimoku context. {name} trades at {f(d['live'])}."),
        (f"What are the key support levels for {name}?",
         ("The nearest support zones are " + ", ".join(zone_txt(z, dec) for z in sup) + ".") if sup else "No support zone is currently within range of the price."),
        (f"What are the key resistance levels for {name}?",
         ("The nearest resistance zones are " + ", ".join(zone_txt(z, dec) for z in res) + ".") if res else "No resistance zone is currently within range of the price."),
        (f"What would confirm a move in {name}?",
         " ".join(x for x in [
             f"An hourly close above {f(tr['bull'])} would confirm the bullish case." if tr.get("bull") is not None else "",
             f"An hourly close below {f(tr['bear'])} would confirm the bearish case." if tr.get("bear") is not None else ""] if x)
         or "Wait for a decisive hourly close outside the nearest confluence zones."),
    ]
    b.append('<h2>FAQ</h2><div class="faq">' + "".join(f"<h3>{esc(q)}</h3><p>{esc(a)}</p>" for q, a in faq) + "</div>")

    b.append('<div class="box"><p><b>Live intraday analysis.</b> For a 15-minute read updated every candle, open the '
             '<a href="/dashboard">XenosFinance dashboard</a> and click any instrument. Daily briefs and Elliott Wave studies are published on our '
             '<a href="https://t.me/xenoswavefinance">Telegram channel</a>.</p><div class="cta"><a href="/dashboard">Open the dashboard</a><a href="/premium">Premium tools</a></div></div>')

    others = [r for r in all_rows if r[0] != slug]
    b.append("<h2>Other daily analyses</h2><div class=\"rel\">" + "".join(f'<a href="/analysis/{r[0]}">{esc(r[2])}</a>' for r in others) + "</div>")

    iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    jsonld = [
        {"@context": "https://schema.org", "@type": "Article", "headline": f"{name} Technical Analysis Today",
         "description": desc, "datePublished": iso, "dateModified": iso, "mainEntityOfPage": url,
         "author": {"@type": "Organization", "name": "XenosFinance", "url": SITE},
         "publisher": {"@type": "Organization", "name": "XenosFinance", "logo": {"@type": "ImageObject", "url": f"{SITE}/favicon-192.png"}}},
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE},
            {"@type": "ListItem", "position": 2, "name": "Daily Analysis", "item": f"{SITE}/analysis"},
            {"@type": "ListItem", "position": 3, "name": name, "item": url}]},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]},
    ]
    kw = f"{name} technical analysis, {name} analysis today, {terms}, {short} support resistance, {short} forecast levels, Elliott Wave {name}"
    return page_shell(title, desc, url, "\n".join(b), jsonld, kw)


def build_index(rows, now):
    url = f"{SITE}/analysis"
    title = "Daily Technical Analysis — Gold, Oil, Forex, Crypto & Indices | XenosFinance"
    desc = "Daily technical analysis for Gold, Oil, Forex, Bitcoin and stock indices: bias, confluence zones, Elliott Wave and trade scenarios with risk/reward. Updated twice a day."
    b = ['<div class="crumb"><a href="/">Home</a> › Daily Analysis</div>',
         "<h1>Daily Technical Analysis</h1>",
         f'<div class="upd">Updated {now.strftime("%d %b %Y, %H:%M")} UTC · {TF_LABEL}</div>',
         ('<div class="upd">Market closed — Forex, Commodities and Indices show data as of Friday close; Crypto is live.</div>'
          if market_closed(now, "Forex") else ""),
         "<p>Every analysis is built by the XenosFinance engine on real market data: moving averages, SuperTrend, MACD, RSI, Fibonacci, "
         "Ichimoku and an Elliott Wave count combine into confluence zones and trade scenarios with calculated risk/reward. "
         "Pages are refreshed twice a day for market analysis and trading education.</p>"]
    groups = []
    for r in rows:
        if r[5] not in groups:
            groups.append(r[5])
    for g in groups:
        b.append(f"<h2>{esc(g)}</h2><table><tr><th>Instrument</th><th>Price</th><th>Bias</th><th>Nearest support</th><th>Nearest resistance</th></tr>")
        for slug, name, short, dec, bias, price, s1, r1 in [(r[0], r[2], r[3], r[4], r[6], r[7], r[8], r[9]) for r in rows if r[5] == g]:
            cls = {"bullish": "up", "bearish": "dn"}.get(bias, "")
            b.append(f'<tr><td><a href="/analysis/{slug}">{esc(name)}</a></td><td>{esc(price)}</td>'
                     f'<td class="{cls}">{esc(bias.capitalize() if bias else "—")}</td><td>{esc(s1 or "—")}</td><td>{esc(r1 or "—")}</td></tr>')
        b.append("</table>")
        if g == "Commodities":
            b.append(spread_html())
    jsonld = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": "Daily Technical Analysis",
               "description": desc, "url": url, "dateModified": now.strftime("%Y-%m-%dT%H:%M:%SZ")}]
    return page_shell(title, desc, url, "\n".join(b), jsonld,
                      "daily technical analysis, gold technical analysis, oil technical analysis, forex technical analysis, bitcoin technical analysis, Elliott Wave analysis")


# ───────────────────────── sitemap ─────────────────────────
def update_sitemap(urls, day):
    if not os.path.exists(SITEMAP):
        print("  ! sitemap.xml not found — skipped")
        return
    s = open(SITEMAP, encoding="utf-8").read()
    for u in urls:
        loc = f"<loc>{u}</loc>"
        if loc in s:
            s = re.sub(re.escape(loc) + r"(\s*)<lastmod>[^<]*</lastmod>",
                       lambda m: f"{loc}{m.group(1)}<lastmod>{day}</lastmod>", s, count=1)
        else:
            entry = (f"  <url>\n    {loc}\n    <lastmod>{day}</lastmod>\n"
                     f"    <changefreq>daily</changefreq>\n    <priority>{'0.8' if u.endswith('/analysis') else '0.7'}</priority>\n  </url>\n")
            s = s.replace("</urlset>", entry + "</urlset>")
    open(SITEMAP, "w", encoding="utf-8").write(s)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    now = datetime.now(timezone.utc)
    rows, built = [], []
    for inst in INSTRUMENTS:
        slug, yf, name, short, dec, group, _ = inst
        print(f"→ {name} ({yf})")
        try:
            d = E._ta_compute(yf, dec, interval="1h", period="60d", htf_rule="4h")
        except Exception as e:
            print(f"  ! compute failed, keeping previous page: {e}")
            continue
        ai = ai_commentary(name, d)
        sup, res = d["zones"]["supports"], d["zones"]["resistances"]
        rows.append((slug, yf, name, short, dec, group, d["bias"]["direction"], fmt(d["live"], dec),
                     zone_txt(sup[0], dec) if sup else None, zone_txt(res[0], dec) if res else None))
        built.append((inst, d, ai))
    if not built:
        print("Nothing built — aborting without changes.")
        return 1
    global SPREAD
    px = {inst[0]: d.get("live") for inst, d, ai in built}
    if px.get("wti-crude-oil") and px.get("brent-crude-oil"):
        SPREAD = float(px["brent-crude-oil"]) - float(px["wti-crude-oil"])
        print(f"  Brent–WTI spread: {SPREAD:+.2f}")
    for inst, d, ai in built:
        path = os.path.join(OUT_DIR, f"{inst[0]}.html")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(build_instrument_page(inst, d, ai, now, rows))
        print(f"  ✓ analysis/{inst[0]}.html  (AI: {'yes' if ai else 'no'})")
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(build_index(rows, now))
    update_sitemap([f"{SITE}/analysis"] + [f"{SITE}/analysis/{r[0]}" for r in rows], now.strftime("%Y-%m-%d"))
    print(f"Done: {len(built)} pages + index, sitemap updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
