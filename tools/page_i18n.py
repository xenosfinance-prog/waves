#!/usr/bin/env python3
"""
page_i18n.py — versione italiana delle pagine statiche COT e Futures Flow (2026-10-25)

Le pagine restano in inglese nell'HTML (SEO invariata). Ogni testo traducibile è
avvolto in  <span data-it="…testo italiano…">testo inglese</span>; con la lingua IT
attiva sul sito (localStorage 'xenos_lang', la stessa del selettore delle altre
pagine) un piccolo script sostituisce il testo. Nessuna richiesta esterna dal
browser, nessuna attesa.

Da dove viene l'italiano:
  - testi fissi (titoli, intestazioni, spiegazioni, etichette, motivi del bias):
    scritti qui a mano → traduzione esatta;
  - testi variabili (Desk read, Oil desk, conclusione Bias): tradotti in fase di
    generazione con tools/translate_content.py (Gemini free / Google, gratis) e
    con il controllo che ogni numero resti identico. Se la traduzione non è
    fedele o non riesce, quel paragrafo resta in inglese.
"""

import html as _html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _attr(s):
    return _html.escape(s, quote=True)


def L(en_html, it_html, tag="span", cls=""):
    """Testo bilingue: EN nell'HTML, IT in data-it (sostituito dallo script se lingua IT)."""
    if not it_html or it_html == en_html:
        return en_html
    c = f' class="{cls}"' if cls else ""
    return f'<{tag}{c} data-it="{_attr(it_html)}">{en_html}</{tag}>'


# ── vocabolario fisso ──────────────────────────────────────────────────────

MARKET_IT = {
    "WTI Crude Oil": "Petrolio WTI", "Brent (NYMEX)": "Brent (NYMEX)", "Natural Gas": "Gas naturale",
    "Gold": "Oro", "Silver": "Argento", "Copper": "Rame", "S&P 500": "S&P 500", "Nasdaq 100": "Nasdaq 100",
    "Euro": "Euro", "Japanese Yen": "Yen giapponese", "British Pound": "Sterlina britannica",
    "US 10Y T-Note": "T-Note USA 10 anni",
}
FLAG_IT = {"Crowded long": "Long affollato", "Crowded short": "Short affollato",
           "Extended long": "Long esteso", "Extended short": "Short esteso", "": ""}
DIV_IT = {"Price up, funds cutting net length": "Prezzo in salita, fondi che riducono il net long",
          "Price down, funds adding net length": "Prezzo in discesa, fondi che aumentano il net long", "": ""}
BIAS_IT = {"Bullish": "Rialzista", "Mildly bullish": "Moderatamente rialzista", "Neutral": "Neutrale",
           "Mildly bearish": "Moderatamente ribassista", "Bearish": "Ribassista"}
FLOW_IT = {"New longs": "Nuovi long", "New shorts": "Nuovi short", "Short covering": "Ricopertura short",
           "Long liquidation": "Liquidazione long", "": ""}
STRUCT_IT = {"backwardation": "backwardation", "contango": "contango"}
WHO_IT = {"Managed money": "Managed money", "Leveraged funds": "Leveraged funds"}

MONTHS_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
             "settembre", "ottobre", "novembre", "dicembre"]
MONTHS_IT_SHORT = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]
DAYS_IT = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]


def d_long(dt):          # 20 ottobre 2026
    return f"{dt.day} {MONTHS_IT[dt.month - 1]} {dt.year}"


def d_day_long(dt):      # martedì 20 ottobre 2026
    return f"{DAYS_IT[dt.weekday()]} {d_long(dt)}"


def d_short_time(dt):    # 25 ott 2026, 06:30
    return f"{dt.day} {MONTHS_IT_SHORT[dt.month - 1]} {dt.year}, {dt:%H:%M}"


def release_it(release_date):
    """'23 Oct 2026' → '23 ott 2026'."""
    en = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    for i, m in enumerate(en):
        release_date = re.sub(rf"\b{m}\b", MONTHS_IT_SHORT[i], release_date)
    return release_date


# motivi del bias (desk_read.bias_cot / bias_flow) → italiano esatto
_LONG_SHORT = {"toward long": "verso il long", "toward short": "verso lo short"}
WHY_RULES = [
    (r"^funds moved (toward long|toward short) over 4 weeks$",
     lambda m: f"fondi spostati {_LONG_SHORT[m[1]]} nelle ultime 4 settimane"),
    (r"^last week funds turned (toward long|toward short)$",
     lambda m: f"nell'ultima settimana i fondi hanno girato {_LONG_SHORT[m[1]]}"),
    (r"^(\d+) straight weeks (toward long|toward short)$",
     lambda m: f"{m[1]} settimane consecutive {_LONG_SHORT[m[2]]}"),
    (r"^price and positioning diverge — the move lacks new speculative positions$",
     lambda m: "prezzo e posizionamento divergono — al movimento mancano nuove posizioni speculative"),
    (r"^price confirms the positioning change$", lambda m: "il prezzo conferma la variazione di posizionamento"),
    (r"^crowded long \(COT index (\d+)\): trend mature, reversal risk$",
     lambda m: f"long affollato (COT index {m[1]}): trend maturo, rischio di inversione"),
    (r"^crowded short \(COT index (\d+)\): short-squeeze risk$",
     lambda m: f"short affollato (COT index {m[1]}): rischio di short squeeze"),
    (r"^extended long \(COT index (\d+)\)$", lambda m: f"long esteso (COT index {m[1]})"),
    (r"^extended short \(COT index (\d+)\)$", lambda m: f"short esteso (COT index {m[1]})"),
    (r"^new longs \(fresh positions\)$", lambda m: "nuovi long (posizioni fresche)"),
    (r"^new shorts \(fresh positions\)$", lambda m: "nuovi short (posizioni fresche)"),
    (r"^short covering \(positions closing, less durable\)$",
     lambda m: "ricopertura short (posizioni in chiusura, meno durevole)"),
    (r"^long liquidation \(positions closing, less durable\)$",
     lambda m: "liquidazione long (posizioni in chiusura, meno durevole)"),
    (r"^price (up|down) without an open-interest reading$",
     lambda m: f"prezzo {'in salita' if m[1] == 'up' else 'in discesa'} senza dato di open interest"),
    (r"^volume ([\d.]+)x the 20-day average \(conviction\)$",
     lambda m: f"volume {m[1]}x la media a 20 sedute (convinzione)"),
    (r"^light volume ([\d.]+)x the 20-day average$",
     lambda m: f"volume debole, {m[1]}x la media a 20 sedute"),
    (r"^curve in (backwardation|contango)$", lambda m: f"curva in {m[1]}"),
    (r"^backwardation steepening$", lambda m: "backwardation in aumento"),
    (r"^curve weakening \(spread narrowing\)$", lambda m: "curva in indebolimento (spread in restringimento)"),
    (r"^no clear signal$", lambda m: "nessun segnale chiaro"),
]


def why_it(s):
    for pat, fn in WHY_RULES:
        m = re.match(pat, s)
        if m:
            return fn(m)
    return None   # motivo nuovo non in elenco → resta in inglese


def market(name, esc):
    return L(esc(name), esc(MARKET_IT.get(name, name)))


# ── testi variabili: traduzione in fase di generazione ─────────────────────

def translate_texts(texts):
    """Lista di testi EN → lista di testi IT (None dove la traduzione non è fedele o fallisce)."""
    texts = [t or "" for t in texts]
    if not any(texts):
        return [None] * len(texts)
    try:
        import translate_content as TC
        fields = {str(i): t for i, t in enumerate(texts) if t}
        out, used = TC.translate_fields(fields)
        print(f"  Traduzione IT testi variabili: {used}")
        res = []
        for i, t in enumerate(texts):
            v = out.get(str(i))
            res.append(v if t and v and v != t else None)
        return res
    except Exception as e:
        print(f"  ! traduzione IT non disponibile: {e}")
        return [None] * len(texts)


# ── menu, tagline e disclaimer comuni (page_shell) ─────────────────────────

NAV_IT = {"Home": "Home", "Dashboard": "Dashboard", "Daily Analysis": "Analisi giornaliera",
          "COT Positioning": "Posizionamento COT", "Futures Flow": "Futures Flow", "Calendar": "Calendario",
          "Elliott Wave": "Onde di Elliott", "Trade Setups": "Trade Setups", "Premium": "Premium",
          "Market Brief": "Brief di mercato", "Intelligence": "Intelligence", "Blog": "Blog", "Topics": "Temi",
          "Charts": "Grafici", "Trading Ideas": "Idee di trading", "Live Setups": "Setup live",
          "Education": "Formazione"}

TAG_IT = "Analisi di mercato &amp; formazione al trading"
DISC_IT = ("Contenuto solo educativo. Questa analisi è generata algoritmicamente da dati di mercato pubblici a "
           "scopo di analisi di mercato e formazione al trading e non costituisce consulenza finanziaria né una "
           "raccomandazione ad acquistare o vendere alcuno strumento finanziario. Il trading comporta un rischio "
           "significativo di perdita. © XenosFinance")


# ── pagine /analysis ───────────────────────────────────────────────────────

INSTRUMENT_IT = {"Gold": "Oro", "Silver": "Argento", "WTI Crude Oil": "Petrolio WTI",
                 "Brent Crude Oil": "Petrolio Brent", "Natural Gas": "Gas naturale", "Copper": "Rame",
                 "Bitcoin": "Bitcoin", "Ethereum": "Ethereum", "S&P 500": "S&P 500", "Nasdaq 100": "Nasdaq 100",
                 "DAX 40": "DAX 40"}
GROUP_IT = {"Commodities": "Materie prime", "Forex": "Forex", "Crypto": "Crypto", "Indices": "Indici"}
SCEN_IT = {"long_pullback": "Rialzista aggressivo (pullback)", "long_breakout": "Rialzista conservativo (breakout)",
           "short_rejection": "Ribassista aggressivo (rifiuto)", "short_breakdown": "Ribassista conservativo (rottura)"}
MEMBER_IT = {"prev_high": "Massimo del giorno prima", "prev_low": "Minimo del giorno prima",
             "swing_high": "Swing high", "swing_low": "Swing low", "ew_inv": "Invalidazione Elliott"}
REGIME_IT = {"above_cloud": "sopra la nuvola", "below_cloud": "sotto la nuvola", "inside_cloud": "dentro la nuvola"}
QL_IT = {"good": "buono", "ok": "accettabile", "poor": "sfavorevole"}
DIR_IT = {"bullish": "Rialzista", "bearish": "Ribassista", "neutral": "Neutrale"}
CONF_IT = {"high": "alta", "medium": "media", "low": "bassa"}

_EW = [
    (r"First Corrective Leg", "Prima gamba correttiva"),
    (r"Retracement", "Ritracciamento"),
    (r"Dominant Impulse", "Impulso dominante"),
    (r"Consolidation", "Consolidamento"),
    (r"Terminal Impulse", "Impulso terminale"),
    (r"Corrective Bounce", "Rimbalzo correttivo"),
    (r"Final Corrective Leg", "Gamba correttiva finale"),
    (r"\[NEAR COMPLETION\]", "[VICINA AL COMPLETAMENTO]"),
    (r"No valid wave count", "Nessun conteggio d'onda valido"),
    (r"% of (W\d|A)\)", r"% di \1)"),
    (r"^Wave ", "Onda "),
]


def ew_desc_it(desc):
    out = desc or ""
    for a, b in _EW:
        out = re.sub(a, b, out)
    return out


def iname(name):
    return INSTRUMENT_IT.get(name, name)
