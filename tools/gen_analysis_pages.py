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
import urllib.parse as _up  # noqa: E402
import urllib.request as _ur  # noqa: E402


class E:  # noqa: N801
    """2026-11-24: il motore (ew_server.py) è in un repo privato e gira su Railway.
    Stesso calcolo di prima (H1 + contesto H4 + Elliott H4), letto da /analysis-data."""
    URL = os.environ.get("EW_SERVER_URL", "https://waves-production-ddbf.up.railway.app")

    @staticmethod
    def _ta_compute(yf, dec, **_):
        q = _up.urlencode({"yf": yf, "dec": dec})
        last = None
        for _i in range(3):
            try:
                with _ur.urlopen(f"{E.URL}/analysis-data?{q}", timeout=240) as r:
                    d = json.loads(r.read().decode("utf-8"))
                if "error" in d:
                    raise ValueError(d["error"])
                return d
            except Exception as e:  # noqa: BLE001
                last = e
        raise ValueError(f"engine: {last}")


import free_llm  # noqa: E402  (2026-10-26: commento AI gratuito con Gemini)

SITE = "https://xenosfinance.com"
OUT_DIR = os.path.join(ROOT, "analysis")
SITEMAP = os.path.join(ROOT, "sitemap.xml")
MODEL = "gemini (free_llm)"   # 2026-10-26: niente più Claude a pagamento

INSTRUMENTS = [
    # slug, yfinance, display name, short label, decimals, group, search terms
    ("gold",            "GC=F",     "Gold",            "XAU/USD",  2, "Commodities", "gold price, XAU/USD"),
    ("silver",          "SI=F",     "Silver",          "XAG/USD",  3, "Commodities", "silver price, XAG/USD"),
    ("wti-crude-oil",   "CL=F",     "WTI Crude Oil",   "WTI",      2, "Commodities", "oil price, WTI crude, CL futures"),
    ("brent-crude-oil", "BZ=F",     "Brent Crude Oil", "Brent",    2, "Commodities", "Brent oil price, Brent crude"),
    ("natural-gas",     "NG=F",     "Natural Gas",     "NG",       3, "Commodities", "natural gas price, NG futures"),
    ("copper",          "HG=F",     "Copper",          "HG",       4, "Commodities", "copper price, HG futures"),
    # 2026-11-26: tutti gli strumenti della dashboard hanno la loro pagina "Technical Analysis Today"
    ("platinum",        "PL=F",     "Platinum",        "XPT/USD",  2, "Commodities", "platinum price, XPT/USD, PL futures"),
    ("palladium",       "PA=F",     "Palladium",       "XPD/USD",  2, "Commodities", "palladium price, XPD/USD, PA futures"),
    ("wheat",           "ZW=F",     "Wheat",           "ZW",       2, "Commodities", "wheat price, wheat futures, ZW"),
    ("corn",            "ZC=F",     "Corn",            "ZC",       2, "Commodities", "corn price, corn futures, ZC"),
    ("soybeans",        "ZS=F",     "Soybeans",        "ZS",       2, "Commodities", "soybean price, soybean futures, ZS"),
    ("coffee",          "KC=F",     "Coffee",          "KC",       2, "Commodities", "coffee price, arabica coffee futures, KC"),
    ("sugar",           "SB=F",     "Sugar",           "SB",       2, "Commodities", "sugar price, sugar No.11 futures, SB"),
    ("cotton",          "CT=F",     "Cotton",          "CT",       2, "Commodities", "cotton price, cotton futures, CT"),
    ("eur-usd",         "EURUSD=X", "EUR/USD",         "EUR/USD",  5, "Forex",       "euro dollar, EURUSD"),
    ("gbp-usd",         "GBPUSD=X", "GBP/USD",         "GBP/USD",  5, "Forex",       "pound dollar, cable, GBPUSD"),
    ("usd-jpy",         "USDJPY=X", "USD/JPY",         "USD/JPY",  3, "Forex",       "dollar yen, USDJPY"),
    ("usd-chf",         "USDCHF=X", "USD/CHF",         "USD/CHF",  5, "Forex",       "dollar franc, USDCHF"),
    ("bitcoin",         "BTC-USD",  "Bitcoin",         "BTC/USD",  0, "Crypto",      "bitcoin price, BTC/USD"),
    ("ethereum",        "ETH-USD",  "Ethereum",        "ETH/USD",  2, "Crypto",      "ethereum price, ETH/USD"),
    ("sp500",           "^GSPC",    "S&P 500",         "SPX",      2, "Indices",     "S&P 500, SPX, US stocks"),
    ("nasdaq",          "^NDX",     "Nasdaq 100",      "NAS100",   2, "Indices",     "Nasdaq 100, NAS100, tech stocks"),
    ("dax",             "^GDAXI",   "DAX 40",          "DAX",      2, "Indices",     "DAX, German stocks"),
    ("ftse-100",        "^FTSE",    "FTSE 100",        "UK100",    2, "Indices",     "FTSE 100, UK stocks, UK100"),
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
TF_LABEL = "Commentary updated through the EU & US sessions · levels live · 1H/4H technical bias"
TF_LABEL_IT = "Commento aggiornato durante le sessioni EU e USA · livelli live · bias tecnico 1H/4H"

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
    import page_i18n as PI
    v = SPREAD
    side = "Brent premium" if v >= 0 else "WTI premium"
    side_it = "premio del Brent" if v >= 0 else "premio del WTI"
    en = (f"Brent–WTI spread: <b>${abs(v):.2f}</b> ({side}). "
          "The two benchmarks usually move together, but on 1-hour charts they can show different biases "
          "while the spread is widening or narrowing.")
    it = (f"Spread Brent–WTI: <b>${abs(v):.2f}</b> ({side_it}). "
          "I due benchmark di solito si muovono insieme, ma sui grafici a 1 ora possono mostrare bias diversi "
          "mentre lo spread si allarga o si restringe.")
    # 2026-11-01: collegamento all'hub del petrolio (SEO: link interno dalle pagine WTI/Brent e dall'indice)
    hub = PI.L("Full oil market view: spread history, futures curve, EIA inventories and COT positioning",
               "Quadro completo del petrolio: storico dello spread, curva dei futures, scorte EIA e posizionamento COT")
    return f'<p class="spread">{PI.L(en, it)} <a href="/analysis/oil-market">{hub} →</a></p>'


def esc(t):
    return html.escape(str(t if t is not None else ""), quote=True)


def fmt(v, dec):
    if v is None:
        return "—"
    return f"{v:,.{dec}f}" if dec <= 2 and abs(v) >= 1000 else f"{v:.{dec}f}"


def zone_txt(z, dec):
    return fmt(z["low"], dec) if z["low"] == z["high"] else f"{fmt(z['low'], dec)}–{fmt(z['high'], dec)}"


# ───────────────────────── AI commentary ─────────────────────────
# 2026-11-19: soglie di "movimento forte" per classe (USD/JPY +0.33% titolato "Surges").
_STRONG_THR = {"Forex": 1.0, "Indices": 1.5, "Commodities": 2.0, "Crypto": 4.0}
_STRONG_RE = re.compile(r"\b(surg(?:es|ing|ed)?|soar(?:s|ing|ed)?|plung(?:es|ing|ed)?|crash(?:es|ing|ed)?|"
                        r"rocket(?:s|ing|ed)?|tumbl(?:es|ing|ed)?|slump(?:s|ing|ed)?|skyrocket(?:s|ing|ed)?|"
                        r"explod(?:es|ing|ed)?|collaps(?:es|ing|ed)?)\b", re.I)
_CUR_GROUP = {"g": "Forex"}


def _strong_thr(data):
    return _STRONG_THR.get(_CUR_GROUP["g"], 1.5)


def _fix_ai(ai, d, group, name, dec=5):
    """Controlli deterministici sul testo AI: verbo del titolo proporzionato al movimento,
    onda citata nel titolo ⇒ onda e invalidazione anche nel sommario."""
    if not ai:
        return ai
    hl = str(ai.get("headline") or "")
    chg = d.get("change_pct_day")
    thr = _STRONG_THR.get(group, 1.5)
    if hl and _STRONG_RE.search(hl) and (chg is None or abs(chg) < thr):
        mild = {"surg": "Edges Up", "soar": "Edges Up", "rocket": "Edges Up", "skyrocket": "Edges Up",
                "explod": "Edges Up", "plung": "Slips", "crash": "Slips", "tumbl": "Slips", "slump": "Slips",
                "collaps": "Slips"}

        def _rep(m):
            w = m.group(0).lower()
            for k, v in mild.items():
                if w.startswith(k):
                    return v                       # direzione del verbo originale, solo più misurata
            return m.group(0)
        new = _STRONG_RE.sub(_rep, hl)
        print(f"  ~ headline toned down ({chg}% < {thr}%): {hl!r} → {new!r}")
        ai["headline"] = hl = new
    ew = d.get("elliott")
    if hl and re.search(r"\bwave\b", hl, re.I):
        if not ew:
            ai["headline"] = re.sub(r"\s*(as|with|in|on)?\s*(the\s+)?(elliott\s+)?wave\s*\w*(\s+\w+){0,2}\s*(extends|builds|unfolds|continues)?\s*(higher|lower)?",
                                    "", hl, flags=re.I).strip(" ,:-") or f"{name} Technical Picture"
            print(f"  ~ headline wave removed (no EW count): {ai['headline']!r}")
        else:
            summ = str(ai.get("summary") or "")
            if not re.search(rf"\bwave\s*{re.escape(str(ew.get('wave')))}\b", summ, re.I):
                inv = ew.get("invalidation")
                live = d.get("live")
                side = "above" if inv is not None and live is not None and inv < live else "below"
                add = f" On the 4-hour chart the Elliott count is in wave {ew.get('wave')}"
                add += f", valid while price holds {side} {fmt(inv, dec)}." if inv is not None else "."
                ai["summary"] = summ.rstrip() + add
                print(f"  ~ summary: added wave {ew.get('wave')} line")
    return ai


def ai_commentary(name, data):
    if not free_llm.available():
        return None
    prompt = f"""You are a senior technical analyst at an institutional desk writing the daily analysis page for XenosFinance, a market analysis and trading education platform.
Instrument: {name} — 1-hour chart with 4-hour context. Swing and Fibonacci levels are on the 1-hour chart; the Elliott wave count ("elliott") is on the 4-hour chart — always say "on the 4-hour chart" when you mention it. All data below is ALREADY CALCULATED by our engine:

{json.dumps(data, ensure_ascii=False)}

Write in English. Return ONLY minified JSON, no fences:
{{"headline":"<max 10 words, journalistic, describes today's technical picture>","summary":"<60-80 words: price, recent move, where it sits vs the key zones, overall bias>","trend":"<50-70 words: moving averages, SuperTrend, 4-hour Ichimoku context>","momentum":"<40-60 words: RSI, MACD, volume if given>","structure":"<40-60 words: last swing, Fibonacci levels, Elliott wave position if given>","outlook":"<60-80 words: what confirms the bullish case and the bearish case using the trigger levels, which scenarios have favourable risk/reward>"}}

STRICT RULES:
- Use ONLY numbers present in the data. Never invent prices, percentages or levels; never recompute risk/reward.
- The bias is already decided ({data['bias']['direction']}, confidence {data['bias']['confidence']}): stay consistent with it.
- If "elliott" is null, do not mention Elliott waves. If volume_ratio is null, do not mention volume.
- Write like a desk analyst, not like software: never quote internal engine fields or scores (no "bear score", "bull score", "score 4/7", "confidence medium", field names). Describe what they mean instead (e.g. "all four 4-hour Ichimoku conditions point lower").
- No filler phrases ("challenging the immediate structure", "it remains to be seen"): every sentence must say something concrete about price and levels.
- Headline verbs must match the size of today's move (change_pct_day): words like "surges", "soars", "plunges", "crashes", "rockets", "tumbles", "slumps" only for a large move (at least {_strong_thr(data)}% on this instrument); otherwise use measured words ("edges higher", "presses resistance", "holds support", "slips").
- If the headline mentions an Elliott wave, the summary must state that wave on the 4-hour chart and its invalidation level from "elliott".
- Educational technical analysis only: no news, no fundamentals, never tell the reader to buy or sell."""
    try:
        raw = free_llm.generate(prompt, max_tokens=1200, json_mode=True)
        if not raw:
            print("  ! AI commentary: free quota unavailable — page without commentary")
            return None
        txt = raw.strip().replace("```json", "").replace("```", "").strip()
        a, b = txt.find("{"), txt.rfind("}")
        out = json.loads(txt[a:b + 1])
        # 2026-10-26: ogni numero del commento deve esistere nei dati del motore; una sezione con
        # numeri inventati viene tolta (meglio una sezione in meno che un livello sbagliato)
        allowed = {n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", json.dumps(data))}
        allowed |= {"1", "2", "3", "4", "5", "7", "14", "20", "50", "100", "200", "0"}
        for k in list(out.keys()):
            v = out.get(k)
            if isinstance(v, str):
                bad = [n for n in re.findall(r"\d[\d,]*(?:\.\d+)?", v) if n.replace(",", "") not in allowed]
                if bad:
                    print(f"  ! AI section '{k}' dropped: numbers not in data {bad[:4]}")
                    out[k] = ""
        return out if out.get("summary") else None
    except Exception as e:
        print(f"  ! AI commentary failed: {e}")
        return None


# ───────────────────────── HTML ─────────────────────────
CSS = """:root{--bg:#1a273d;--bg2:#1e3149;--bg3:#24324d;--ink:#edf2f8;--ink2:#c8d7e6;--muted:#8aa2bb;--border:#2e4570;--border2:#355281;--red2:#f87171;--green2:#34d399;--gold:#3b82f6;--mono:'IBM Plex Mono',monospace;--serif:'Playfair Display',Georgia,serif;--body:'Inter',system-ui,sans-serif;}
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
.stale{border:1px solid #f59e0b;background:rgba(245,158,11,0.08);color:#fbbf24;font-family:var(--mono);font-size:12px;line-height:1.6;padding:10px 14px;margin:10px 0;}
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
@media(max-width:720px){h1{font-size:26px;}.grid{grid-template-columns:1fr;}table{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch;font-size:10.5px;}table>tbody,table>thead{display:table;width:100%;}th{letter-spacing:.5px;padding:5px 4px;}td{padding:6px 4px;}td.m{font-size:10px;}}"""


NAV = [("/", "Home"), ("/market-brief", "Market Brief"), ("/intelligence/", "Intelligence"), ("/dashboard", "Dashboard"),
       ("/analysis/", "Daily Analysis"), ("/cot/", "COT Positioning"), ("/futures-flow/", "Futures Flow"), ("/oil-options/", "Oil Options"),
       ("/xenoswaves_charts", "Charts"), ("/workstation", "Workstation"), ("/XenosBlog", "Blog"), ("/trading-ideas", "Trading Ideas"),
       ("/live-setups", "Live Setups"), ("/calendar", "Calendar"), ("/elliottwave", "Elliott Wave"),
       ("/daily-education", "Education"), ("/premium", "Premium")]   # 2026-10-28: + Charts, Ideas, Setups, Education   # 2026-10-26: stessi servizi del menu principale del sito


def page_shell(title, desc, canonical, body, jsonld, keywords, active="/analysis/", it_title=None):
    ld = "\n".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in jsonld)
    nav = "".join('<a href="%s"%s>%s</a>' % (h, ' class="on"' if h == active else "", t) for h, t in NAV)
    # 2026-10-25: versione italiana. Tutte le pagine hanno le bandierine EN/IT
    # (/xf-page-i18n.js); menu, tagline e disclaimer sono bilingui. Il contenuto
    # è in italiano dove il generatore fornisce data-it (it_title = titolo IT).
    import page_i18n as PI
    nav = "".join('<a href="%s"%s>%s</a>' % (h, ' class="on"' if h == active else "", PI.L(t, PI.NAV_IT.get(t, t)))
                  for h, t in NAV)
    tag = PI.L("Market analysis &amp; trading education", PI.TAG_IT)
    disc = PI.L(DISC_EN, PI.DISC_IT)
    js = '<script src="/xf-page-i18n.js?v=1" defer></script>\n'
    js += '<script src="/tg-banner.js?v=1" defer></script>\n'  # 2026-10-27: banner canale Telegram
    meta_it = ""
    if it_title:
        meta_it = f'<meta name="xf-title-it" content="{esc(it_title)}">\n'
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
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS}</style>
{meta_it}{ld}
</head>
<body>
<header class="top"><div class="brand">Xenos<span>Finance</span></div><div class="tag">{tag}</div></header>
<nav>{nav}</nav>
<main>
{body}
<div class="disc">{disc}</div>
</main>
{js}</body>
</html>
"""


DISC_EN = ("Educational content only. This analysis is generated algorithmically from public market data for market "
           "analysis and trading education purposes and does not constitute investment advice or a recommendation to "
           "buy or sell any financial instrument. Trading involves a significant risk of loss. © XenosFinance")


def build_instrument_page(inst, d, ai, now, all_rows):
    """2026-10-25: pagina bilingue — HTML in inglese (SEO), italiano in data-it (tools/page_i18n.py).
    ai["_it"] = commento AI tradotto (stesse chiavi), se la traduzione è riuscita."""
    import page_i18n as PI
    L = PI.L
    slug, yf, name, short, dec, group, terms = inst
    name_it = PI.iname(name)
    f = lambda v: fmt(v, dec)
    url = f"{SITE}/analysis/{slug}"
    date_h = now.strftime("%d %B %Y")
    dirw = d["bias"]["direction"]
    bias_word = {"bullish": "Bullish", "bearish": "Bearish", "neutral": "Neutral"}[dirw]
    conf = d["bias"]["confidence"]
    conf_it = PI.CONF_IT.get(conf, conf)
    chg = d.get("change_pct_day")
    sup = d["zones"]["supports"]
    res = d["zones"]["resistances"]
    ai_it = (ai or {}).get("_it") or {}

    def ai_p(key):
        return f"<p>{L(esc(ai.get(key, '')), esc(ai_it[key]) if ai_it.get(key) else '')}</p>"

    # 2026-11-08 SEO (Search Console): le ricerche reali sono "… technical analysis today" e "… support and resistance levels"
    # 2026-11-13 CTR (Search Console: 2% di clic sulle impressioni): data e prezzo nel titolo —
    # per le ricerche "… today" il risultato mostra che l'analisi è di oggi e con il prezzo reale
    day_s = f"{now.day} {now.strftime('%b')}"
    px_s = fmt(d.get("live"), dec) if d.get("live") is not None else ""
    title = (f"{name} Technical Analysis Today ({day_s}) — {short}" + (f" at {px_s}" if px_s else "")
             + " · Support & Resistance | XenosFinance")
    title_it = (f"{name_it} analisi tecnica oggi ({now.day} {PI.MONTHS_IT_SHORT[now.month - 1]}) — {short}"
                + (f" a {px_s}" if px_s else "") + " · supporti e resistenze | XenosFinance")
    s1 = zone_txt(sup[0], dec) if sup else None
    r1 = zone_txt(res[0], dec) if res else None
    desc = (f"{name} ({short}) technical analysis for {date_h}: {bias_word.lower()} bias on the 1-hour chart"
            + (f", support {s1}" if s1 else "") + (f", resistance {r1}" if r1 else "")
            + ". Elliott Wave and trade scenarios.")   # 2026-11-26: ~160 car., oltre Google taglia

    b = [f'<div class="crumb"><a href="/">Home</a> › <a href="/analysis/">{L("Daily Analysis", "Analisi giornaliera")}</a> › '
         f'{L(esc(name), esc(name_it))}</div>',
         f"<h1>{L(esc(name) + ' Technical Analysis Today', esc(name_it) + ' — analisi tecnica di oggi')}</h1>",
         '<div id="lv-upd" hidden></div>',   # 2026-10-28: niente scritte su aggiornamenti/orari
         # 2026-10-16: configurazione per /analysis/live.js (numeri aggiornati dal vivo)
         f'<div id="lv-cfg" hidden data-yf="{esc(yf)}" data-dec="{dec}" data-short="{esc(short)}" data-name="{esc(name)}"'
         # 2026-10-28: fotografia al momento del commento — live.js avvisa se i numeri live la superano
         f' data-bias="{dirw}" data-px="{d["live"]}" data-atr="{d["atr"]}"'
         f' data-inv="{(d.get("elliott") or {}).get("invalidation") or ""}" data-built="{now.strftime("%H:%M")}"></div>',
]
    if market_closed(now, group):
        b.append('<div class="upd">' + L("Market closed — data as of Friday close",
                                          "Mercato chiuso — dati alla chiusura di venerdì") + '</div>')
    if slug in ("wti-crude-oil", "brent-crude-oil"):
        b.append(spread_html())
    if ai and ai.get("headline"):
        b.append(f'<div class="headline">{L(esc(ai["headline"]), esc(ai_it["headline"]) if ai_it.get("headline") else "")}</div>')
    b.append(f'<div class="px" id="lv-px">{esc(short)} <b>{f(d["live"])}</b>'
             + (f' <span class="{"up" if chg >= 0 else "dn"}">{chg:+.2f}%</span>' if chg is not None else "")
             + f' · ATR(14) {f(d["atr"])}</div>')
    b.append(f'<div class="bias {dirw}" id="lv-bias"><span>Bias</span><b>{L(bias_word, PI.DIR_IT[dirw])}</b><span>'
             + L(f'Confidence {conf} · score {d["bias"]["score"]:+d}/7',
                 f'Affidabilità {conf_it} · punteggio {d["bias"]["score"]:+d}/7') + '</span></div>')

    if ai:
        b.append(f"<h2>{L('Summary', 'Sintesi')}</h2>")
        b.append(ai_p("summary"))

    # Zone
    def zrows(zs):
        if not zs:
            return f'<tr><td colspan="3" class="m">{L("No level within range", "Nessun livello nel range")}</td></tr>'
        return "".join(
            f'<tr><td>{zone_txt(z, dec)}</td><td class="m">'
            + L(esc(" + ".join(MEMBER_NAME.get(m, m) for m in z["members"])),
                esc(" + ".join(PI.MEMBER_IT.get(m, MEMBER_NAME.get(m, m)) for m in z["members"])))
            + f'</td><td>{"●" * min(z["strength"], 4)}</td></tr>' for z in zs)
    th_r = f"<tr><th>{L('Resistance', 'Resistenza')}</th><th>{L('Levels', 'Livelli')}</th><th>{L('Strength', 'Forza')}</th></tr>"
    th_s = f"<tr><th>{L('Support', 'Supporto')}</th><th>{L('Levels', 'Livelli')}</th><th>{L('Strength', 'Forza')}</th></tr>"
    b.append(f"<h2>{L(esc(name) + ' support and resistance levels — confluence zones', esc(name_it) + ': supporti e resistenze — zone di confluenza')}</h2>")
    b.append("<p>" + L(
        "Zones where several technical levels cluster together (moving averages, SuperTrend, Fibonacci retracements, "
        "previous-day range, swing points). More converging levels mean a more relevant zone.",
        "Zone in cui si concentrano più livelli tecnici (medie mobili, SuperTrend, ritracciamenti di Fibonacci, range "
        "del giorno precedente, punti di swing). Più livelli convergono, più la zona è rilevante.") + "</p>")
    b.append('<div class="grid" id="lv-zones"><div><table>' + th_r + zrows(res)
             + '</table></div><div><table>' + th_s + zrows(sup) + "</table></div></div>")

    # Trend & momentum
    ind = d["indicators"]
    b.append(f"<h2>{L('Trend', 'Trend')}</h2>")
    if ai and ai.get("trend"):
        b.append(ai_p("trend"))
    h1c = d.get("h1")
    above = L("price above", "prezzo sopra")
    below = L("price below", "prezzo sotto")
    pos = lambda v: above if v and d["live"] > v else below
    ich_row = ""
    if h1c:
        ich_en = f"{h1c['bull_score']}/4 bullish · {h1c['bear_score']}/4 bearish"
        ich_it = f"{h1c['bull_score']}/4 rialzista · {h1c['bear_score']}/4 ribassista"
        ich_row = (f'<tr><td>Ichimoku 4H</td><td>{L(REGIME.get(h1c["regime"], h1c["regime"]), PI.REGIME_IT.get(h1c["regime"], ""))}</td>'
                   f'<td class="m">{L(ich_en, ich_it)}</td></tr>')
    th3 = f"<tr><th>{L('Indicator', 'Indicatore')}</th><th>{L('Value', 'Valore')}</th><th>{L('Reading', 'Lettura')}</th></tr>"
    b.append('<div id="lv-trend"><table>' + th3 +
             f'<tr><td>SMA 20</td><td>{f(ind["sma20"])}</td><td class="m">{pos(ind["sma20"])}</td></tr>'
             f'<tr><td>SMA 50</td><td>{f(ind["sma50"])}</td><td class="m">{pos(ind["sma50"])}</td></tr>'
             f'<tr><td>SMA 200</td><td>{f(ind["sma200"])}</td><td class="m">{pos(ind["sma200"])}</td></tr>'
             f'<tr><td>SuperTrend (10,3)</td><td>{f(ind["supertrend"])}</td><td class="m">'
             + (L("bullish", "rialzista") if ind["supertrend_dir"] == "up" else L("bearish", "ribassista")) + '</td></tr>'
             + ich_row
             + "</table></div>")
    b.append(f"<h2>{L('Momentum — RSI &amp; MACD', 'Momentum — RSI e MACD')}</h2>")
    if ai and ai.get("momentum"):
        b.append(ai_p("momentum"))
    th2 = f"<tr><th>{L('Indicator', 'Indicatore')}</th><th>{L('Value', 'Valore')}</th></tr>"
    b.append('<div id="lv-mom"><table>' + th2 +
             f'<tr><td>RSI (14)</td><td>{ind["rsi"]}</td></tr>'
             f'<tr><td>{L("MACD / signal", "MACD / segnale")}</td><td>{ind["macd"]} / {ind["macd_signal"]}</td></tr>'
             + (f'<tr><td>{L("Volume vs 40-bar average", "Volume vs media 40 barre")}</td><td>×{ind["volume_ratio"]}</td></tr>'
                if ind.get("volume_ratio") else "")
             + "</table></div>")

    # Struttura
    b.append(f"<h2>{L('Structure — swing, Fibonacci and Elliott Wave', 'Struttura — swing, Fibonacci e onde di Elliott')}</h2>")
    if ai and ai.get("structure"):
        b.append(ai_p("structure"))
    rows = ""
    if d.get("swing"):
        sw = d["swing"]
        dir_it = "rialzo" if sw["dir"] == "up" else "ribasso"
        rows += (f'<tr><td>{L("Last swing (1H)", "Ultimo swing (1H)")}</td><td>{f(sw["from"])} → {f(sw["to"])} '
                 f'({L(esc(sw["dir"]), dir_it)})</td></tr>')
    for k, v in (d.get("fib") or {}).items():
        rows += f"<tr><td>Fibonacci {k}% (1H)</td><td>{f(v)}</td></tr>"
    if d.get("elliott"):
        ew = d["elliott"]
        rows += f'<tr><td>{L("Elliott Wave (4H)", "Onda di Elliott (4H)")}</td><td>{L(esc(ew["desc"]), esc(PI.ew_desc_it(ew["desc"])))}</td></tr>'
        if ew.get("invalidation") is not None:
            rows += f'<tr><td>{L("Elliott invalidation (4H)", "Invalidazione Elliott (4H)")}</td><td>{f(ew["invalidation"])}</td></tr>'
        tps = [f(t) for t in (ew.get("tp1"), ew.get("tp2")) if t is not None]
        if tps:
            rows += f'<tr><td>{L("Elliott targets (4H)", "Target Elliott (4H)")}</td><td>{" · ".join(tps)}</td></tr>'
    pdv = d.get("prev_day") or {}
    if pdv.get("high") is not None and pdv.get("low") is not None:
        rows += f'<tr><td>{L("Previous-day range", "Range del giorno precedente")}</td><td>{f(pdv["low"])} – {f(pdv["high"])}</td></tr>'
    b.append('<div id="lv-struct">' + (f"<table><tr><th>{L('Element', 'Elemento')}</th><th>{L('Level', 'Livello')}</th></tr>{rows}</table>"
                                       if rows else "") + "</div>")

    # Scenari
    b.append(f"<h2>{L('Trade scenarios', 'Scenari operativi')}</h2>")
    b.append("<p>" + L(
        "Educational scenarios built from the confluence zones. Entry, stop and target are calculated by our engine; "
        "risk/reward is computed from the published numbers, and scenarios with an unfavourable ratio are flagged rather "
        "than presented as opportunities.",
        "Scenari a scopo educativo costruiti sulle zone di confluenza. Entry, stop e target sono calcolati dal nostro "
        "motore; il rapporto rischio/rendimento è calcolato sui numeri pubblicati, e gli scenari con un rapporto "
        "sfavorevole vengono segnalati invece di essere presentati come opportunità.") + "</p>")
    if d.get("scenarios"):
        t = (f"<table><tr><th>{L('Scenario', 'Scenario')}</th><th>Entry</th><th>Stop</th><th>Target</th><th>R:R</th>"
             f"<th>{L('Quality', 'Qualità')}</th></tr>")
        for sc in d["scenarios"]:
            ql = {"good": "good", "ok": "acceptable", "poor": "unfavourable"}[sc["quality"]]
            t += (f'<tr class="{sc["quality"]}"><td>{L(SCEN_NAME.get(sc["key"], sc["key"]), PI.SCEN_IT.get(sc["key"], ""))}</td>'
                  f'<td>{f(sc["entry"])}</td><td>{f(sc["stop"])}</td><td>{f(sc["target"])}</td><td>{sc["rr"]:.2f}:1</td>'
                  f'<td><span class="q {sc["quality"]}">{L(ql, PI.QL_IT[sc["quality"]])}</span></td></tr>')
        b.append('<div id="lv-scen">' + t + "</table></div>")
    else:
        b.append('<div id="lv-scen"><p>' + L("No scenario with valid levels at the moment.",
                                              "Al momento nessuno scenario con livelli validi.") + '</p></div>')

    b.append(f"<h2>{L('Outlook and confirmation', 'Prospettive e conferme')}</h2>")
    if ai and ai.get("outlook"):
        b.append(ai_p("outlook"))
    tr = d.get("trigger") or {}
    trg = ""
    if tr.get("bull") is not None:
        trg += '<div class="trig up">▲ ' + L(f"Bullish confirmation: hourly close above {f(tr['bull'])}",
                                              f"Conferma rialzista: chiusura oraria sopra {f(tr['bull'])}") + '</div>'
    if tr.get("bear") is not None:
        trg += '<div class="trig dn">▼ ' + L(f"Bearish confirmation: hourly close below {f(tr['bear'])}",
                                              f"Conferma ribassista: chiusura oraria sotto {f(tr['bear'])}") + '</div>'
    b.append(f'<div id="lv-trig">{trg}</div>')

    # FAQ deterministica (numeri dal motore, nessun testo AI)
    faq = [
        (f"What is the {name} trend today?",
         # 2026-11-19: niente punteggio interno ("score -7/7") nel testo pubblico — se ne descrive il significato
         f"On the 1-hour chart the bias is {bias_word.lower()}: {abs(d['bias']['score'])} of 7 trend and momentum signals "
         f"point {'lower' if d['bias']['score'] < 0 else 'higher' if d['bias']['score'] > 0 else 'nowhere in particular'} "
         f"(moving averages, MACD, RSI, SuperTrend and the 4-hour Ichimoku context). {name} trades at {f(d['live'])}."),
        # 2026-11-19 (Search Console): domande con le parole delle ricerche reali — "gold support levels",
        # "silver support and resistance levels", "gold price support level" — e la data del giorno.
        (f"What are the {name} support levels today?",
         (f"{name} support levels today ({day_s}): " + ", ".join(zone_txt(z, dec) for z in sup) + ".") if sup else "No support zone is currently within range of the price."),
        (f"What are the {name} resistance levels today?",
         (f"{name} resistance levels today ({day_s}): " + ", ".join(zone_txt(z, dec) for z in res) + ".") if res else "No resistance zone is currently within range of the price."),
        (f"What would confirm a move in {name}?",
         " ".join(x for x in [
             f"An hourly close above {f(tr['bull'])} would confirm the bullish case." if tr.get("bull") is not None else "",
             f"An hourly close below {f(tr['bear'])} would confirm the bearish case." if tr.get("bear") is not None else ""] if x)
         or "Wait for a decisive hourly close outside the nearest confluence zones."),
    ]
    faq_it = [
        (f"{name_it}: qual è il trend oggi?",
         f"Sul grafico a 1 ora il nostro motore legge un bias {PI.DIR_IT[dirw].lower()} con affidabilità {conf_it} "
         f"(punteggio {d['bias']['score']:+d}/7), basato su medie mobili, MACD, RSI, SuperTrend e il contesto Ichimoku a 4 ore. "
         f"{name_it} quota {f(d['live'])}."),
        (f"{name_it}: quali sono i supporti chiave?",
         ("Le zone di supporto più vicine sono " + ", ".join(zone_txt(z, dec) for z in sup) + ".") if sup
         else "Al momento nessuna zona di supporto è nel range del prezzo."),
        (f"{name_it}: quali sono le resistenze chiave?",
         ("Le zone di resistenza più vicine sono " + ", ".join(zone_txt(z, dec) for z in res) + ".") if res
         else "Al momento nessuna zona di resistenza è nel range del prezzo."),
        (f"{name_it}: cosa confermerebbe un movimento?",
         " ".join(x for x in [
             f"Una chiusura oraria sopra {f(tr['bull'])} confermerebbe lo scenario rialzista." if tr.get("bull") is not None else "",
             f"Una chiusura oraria sotto {f(tr['bear'])} confermerebbe lo scenario ribassista." if tr.get("bear") is not None else ""] if x)
         or "Attendere una chiusura oraria decisa fuori dalle zone di confluenza più vicine."),
    ]
    b.append('<h2>FAQ</h2><div class="faq">' + "".join(
        f"<h3>{L(esc(q), esc(qi))}</h3><p>{L(esc(a), esc(ai_))}</p>" for (q, a), (qi, ai_) in zip(faq, faq_it)) + "</div>")

    b.append('<div class="box"><p>' + L(
        '<b>Live intraday analysis.</b> For a 15-minute read updated every candle, open the '
        '<a href="/dashboard">XenosFinance dashboard</a> and click any instrument. Daily briefs and Elliott Wave studies are published on our '
        '<a href="https://t.me/xenoswavefinance">Telegram channel</a>.',
        '<b>Analisi intraday dal vivo.</b> Per una lettura a 15 minuti aggiornata a ogni candela, apri la '
        '<a href="/dashboard">dashboard di XenosFinance</a> e clicca su uno strumento. Brief giornalieri e studi sulle onde di Elliott '
        'sono pubblicati sul nostro <a href="https://t.me/xenoswavefinance">canale Telegram</a>.')
        + f'</p><div class="cta"><a href="/dashboard">{L("Open the dashboard", "Apri la dashboard")}</a>'
          f'<a href="/premium">{L("Premium tools", "Strumenti Premium")}</a></div></div>')

    # 2026-10-25: ultimi articoli del blog su questo strumento (link interni, SEO)
    rel = RELATED.get(slug) or []
    if rel:
        b.append(f"<h2>{L('Latest articles on ' + esc(name), 'Ultimi articoli su ' + esc(name_it))}</h2><div class=\"faq\">"
                 + "".join(f'<p><a href="/XenosBlog?slug={esc(s_)}">{L(esc(t_), esc(ti_) if ti_ else "")}</a>'
                           f' <span class="m" style="font-family:var(--mono);font-size:10px;color:var(--muted)">{esc(d_)}</span></p>'
                           for s_, t_, ti_, d_ in rel) + "</div>")

    others = [r for r in all_rows if r[0] != slug]
    b.append(f"<h2>{L('Other daily analyses', 'Altre analisi giornaliere')}</h2><div class=\"rel\">"
             + "".join(f'<a href="/analysis/{r[0]}">{L(esc(r[2]), esc(PI.iname(r[2])))}</a>' for r in others) + "</div>")

    iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    jsonld = [
        {"@context": "https://schema.org", "@type": "Article", "headline": f"{name} Technical Analysis Today",
         "description": desc, "datePublished": iso, "dateModified": iso, "mainEntityOfPage": url,
         "author": {"@type": "Organization", "name": "XenosFinance", "url": SITE},
         "publisher": {"@type": "Organization", "name": "XenosFinance", "logo": {"@type": "ImageObject", "url": f"{SITE}/favicon-192.png"}}},
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE},
            {"@type": "ListItem", "position": 2, "name": "Daily Analysis", "item": f"{SITE}/analysis/"},
            {"@type": "ListItem", "position": 3, "name": name, "item": url}]},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]},
    ]
    kw = f"{name} technical analysis, {name} analysis today, {terms}, {short} support resistance, {short} forecast levels, Elliott Wave {name}"
    b.append('<script src="/analysis/live.js?v=3" defer></script>')
    return page_shell(title, desc, url, "\n".join(b), jsonld, kw, it_title=title_it)


def build_index(rows, now):
    import page_i18n as PI
    L = PI.L
    url = f"{SITE}/analysis/"
    title = "Daily Technical Analysis — Gold, Oil, Forex, Crypto & Indices | XenosFinance"
    title_it = "Analisi tecnica giornaliera — oro, petrolio, forex, crypto e indici | XenosFinance"
    desc = "Daily technical analysis for Gold, Oil, Forex, Bitcoin and stock indices: bias, confluence zones, Elliott Wave and trade scenarios with risk/reward. Levels updated live."
    b = [f'<div class="crumb"><a href="/">Home</a> › {L("Daily Analysis", "Analisi giornaliera")}</div>',
         f"<h1>{L('Daily Technical Analysis', 'Analisi tecnica giornaliera')}</h1>",
         '<div id="lv-upd" hidden></div>',
         ('<div class="upd">' + L("Market closed — Forex, Commodities and Indices show data as of Friday close; Crypto is live.",
                                  "Mercati chiusi — Forex, materie prime e indici mostrano i dati alla chiusura di venerdì; "
                                  "le crypto sono live.") + '</div>'
          if market_closed(now, "Forex") else ""),
         "<p>" + L(
             "Every analysis is built by the XenosFinance engine on real market data: moving averages, SuperTrend, MACD, RSI, Fibonacci, "
             "Ichimoku and an Elliott Wave count combine into confluence zones and trade scenarios with calculated risk/reward. "
             "Prices, levels and scenarios are live.",
             "Ogni analisi è costruita dal motore di XenosFinance su dati di mercato reali: medie mobili, SuperTrend, MACD, RSI, "
             "Fibonacci, Ichimoku e un conteggio delle onde di Elliott si combinano in zone di confluenza e scenari operativi con "
             "rischio/rendimento calcolato. Prezzi, livelli e scenari sono live.") + "</p>"]
    groups = []
    for r in rows:
        if r[5] not in groups:
            groups.append(r[5])
    for g in groups:
        b.append(f"<h2>{L(esc(g), esc(PI.GROUP_IT.get(g, g)))}</h2><table><tr><th>{L('Instrument', 'Strumento')}</th>"
                 f"<th>{L('Price', 'Prezzo')}</th><th>Bias</th><th>{L('Nearest support', 'Supporto più vicino')}</th>"
                 f"<th>{L('Nearest resistance', 'Resistenza più vicina')}</th></tr>")
        for slug, yf, name, short, dec, bias, price, s1, r1 in [(r[0], r[1], r[2], r[3], r[4], r[6], r[7], r[8], r[9]) for r in rows if r[5] == g]:
            cls = {"bullish": "up", "bearish": "dn"}.get(bias, "")
            bias_en = bias.capitalize() if bias else "—"
            b.append(f'<tr class="lv-row" data-yf="{esc(yf)}" data-dec="{dec}"><td><a href="/analysis/{slug}">'
                     f'{L(esc(name), esc(PI.iname(name)))}</a></td><td class="lv-price">{esc(price)}</td>'
                     f'<td class="lv-b {cls}">{L(esc(bias_en), esc(PI.DIR_IT.get(bias, "")))}</td>'
                     f'<td class="lv-s1">{esc(s1 or "—")}</td><td class="lv-r1">{esc(r1 or "—")}</td></tr>')
        b.append("</table>")
        if g == "Commodities":
            b.append(spread_html())
    b.append('<script src="/analysis/live.js?v=3" defer></script>')
    jsonld = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": "Daily Technical Analysis",
               "description": desc, "url": url, "dateModified": now.strftime("%Y-%m-%dT%H:%M:%SZ")}]
    return page_shell(title, desc, url, "\n".join(b), jsonld,
                      "daily technical analysis, gold technical analysis, oil technical analysis, forex technical analysis, bitcoin technical analysis, Elliott Wave analysis",
                      it_title=title_it)


# ───────────────────── articoli del blog collegati (2026-10-25, SEO) ─────────────────────
# Stesse regole di functions/XenosBlog.js (articolo → analisi). Qui al contrario:
# per ogni strumento, gli ultimi articoli del blog che ne parlano → link interni
# dalle pagine /analysis agli articoli (e il blog linka già le analisi).
_REL_RULES = [
    (r"\b(wti|crude|oil|eia|opec\+?|petroleum|gasoline|distillates?|refiner\w*|barrels?)\b", ["wti-crude-oil", "brent-crude-oil"]),
    (r"\bbrent\b", ["brent-crude-oil", "wti-crude-oil"]),
    (r"\b(natural gas|natgas|lng|henry hub)\b", ["natural-gas"]),
    (r"\b(gold|xau|bullion)\b", ["gold"]),
    (r"\b(silver|xag)\b", ["silver"]),
    (r"\bcopper\b", ["copper"]),
    (r"\b(bitcoin|btc)\b", ["bitcoin"]),
    (r"\b(ethereum|eth)\b", ["ethereum"]),
    (r"\bcrypto\w*", ["bitcoin", "ethereum"]),
    (r"\b(eur/?usd|euro|ecb)\b", ["eur-usd"]),
    (r"\b(gbp/?usd|pound|sterling|boe|bank of england)\b", ["gbp-usd"]),
    (r"\b(usd/?jpy|yen|boj|bank of japan)\b", ["usd-jpy"]),
    (r"\b(usd/?chf|swiss franc|snb)\b", ["usd-chf"]),
    (r"\b(nasdaq|ndx|nas100|tech stocks|megacap|mega-cap|semiconductor\w*)\b", ["nasdaq"]),
    (r"(s&p|\bspx\b|\bspy\b|wall street|\bequit\w*|\bstocks?\b|\bpre-market\b|\bearnings\b)", ["sp500", "nasdaq"]),
    (r"\b(dax|german\w*|bund|european (stocks|equities))\b", ["dax"]),
    (r"\b(dollar|dxy|fed|fomc|forex|\bfx\b|treasur\w*|yields?)\b", ["eur-usd", "usd-jpy"]),
]


def _article_instruments(a):
    txt = " ".join(str(a.get(k) or "") for k in ("title", "category", "categoryLabel", "excerpt")).lower()
    out = []
    for rx, pages in _REL_RULES:
        if re.search(rx, txt):
            for p in pages:
                if p not in out:
                    out.append(p)
        if len(out) >= 4:
            break
    return out[:4]


def related_articles(limit=5):
    """slug strumento → [(slug articolo, titolo EN, titolo IT|None, data)] più recenti."""
    try:
        idx = json.load(open(os.path.join(ROOT, "articles", "index.json"), encoding="utf-8"))
    except Exception:
        return {}
    try:
        it = json.load(open(os.path.join(ROOT, "i18n", "it", "articles", "index.json"), encoding="utf-8"))
    except Exception:
        it = {}
    idx = sorted([a for a in idx if a.get("slug") and a.get("title")],
                 key=lambda a: str(a.get("publishedAt") or ""), reverse=True)
    out = {}
    for a in idx:
        for p in _article_instruments(a):
            lst = out.setdefault(p, [])
            if len(lst) < limit:
                lst.append((a["slug"], a["title"], (it.get(a["slug"]) or {}).get("title"), str(a.get("publishedAt") or "")[:10]))
    return out


RELATED = {}


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
                     f"    <changefreq>daily</changefreq>\n    <priority>{'0.8' if u.endswith('/analysis/') else '0.7'}</priority>\n  </url>\n")
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
            # 2026-10-30: Elliott sul 4 ore, identico alla pagina Elliott del sito (/ew-chart H4)
            d = E._ta_compute(yf, dec, interval="1h", period="60d", htf_rule="4h", ew_tf="H4 (4-Hour)")
        except Exception as e:
            print(f"  ! compute failed, keeping previous page: {e}")
            continue
        _CUR_GROUP["g"] = group
        ai = _fix_ai(ai_commentary(name, d), d, group, name, dec)
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
    # 2026-10-25: commento AI in italiano — tutti gli strumenti in una sola richiesta (Gemini free),
    # con il controllo che ogni numero resti identico; se fallisce, il commento resta in inglese.
    try:
        import page_i18n as PI
        keys = ("headline", "summary", "trend", "momentum", "structure", "outlook")
        idx = [(i, k) for i, (inst, d, ai) in enumerate(built) if ai for k in keys if ai.get(k)]
        tr_out = PI.translate_texts([built[i][2][k] for i, k in idx])
        for (i, k), v in zip(idx, tr_out):
            if v:
                built[i][2].setdefault("_it", {})[k] = v
    except Exception as e:
        print(f"  ! traduzione IT commento AI: {e}")
    RELATED.update(related_articles())
    for inst, d, ai in built:
        path = os.path.join(OUT_DIR, f"{inst[0]}.html")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(build_instrument_page(inst, d, ai, now, rows))
        print(f"  ✓ analysis/{inst[0]}.html  (AI: {'yes' if ai else 'no'})")
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(build_index(rows, now))
    extra = []
    # 2026-11-01: hub del petrolio — un errore qui non tocca le altre pagine
    try:
        import gen_oil_hub as OH
        hub = OH.build(sys.modules[__name__], built, now)
        if hub:
            with open(os.path.join(OUT_DIR, "oil-market.html"), "w", encoding="utf-8") as fh:
                fh.write(hub)
            extra.append(f"{SITE}/analysis/oil-market")
            print("  ✓ analysis/oil-market.html")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"  ! oil hub failed (other pages unaffected): {e}")
    update_sitemap([f"{SITE}/analysis/"] + [f"{SITE}/analysis/{r[0]}" for r in rows] + extra, now.strftime("%Y-%m-%d"))
    print(f"Done: {len(built)} pages + index, sitemap updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
