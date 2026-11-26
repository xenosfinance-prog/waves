#!/usr/bin/env python3
"""
gen_oil_hub.py — pagina /analysis/oil-market (2026-11-01)

Hub del petrolio per la SEO: tutto ciò che XenosFinance calcola sul greggio in
un'unica pagina indicizzabile, rigenerata insieme alle pagine /analysis (sei
volte al giorno, GitHub Actions). Solo dati reali:
  - WTI e Brent: prezzo, bias, supporti/resistenze, Elliott 4H → dagli stessi
    calcoli delle pagine /analysis (passati da gen_analysis_pages.py)
  - spread Brent–WTI: chiusure giornaliere dei futures (Yahoo), ultimi 6 mesi
  - curva dei futures e flussi: futures-flow/latest.json (CME)
  - scorte EIA: data/eia_wpsr_last.json (salvato dal bot quando pubblica il
    report, con il consenso della settimana) oppure il Worker EIA; lettura del
    desk con le STESSE regole del bot (eia_xenos_read in bot.py)
  - posizionamento: cot/latest.json (CFTC)
  - calendario: /ff-calendar del server waves (ForexFactory)
Se un blocco non ha dati, il blocco non compare: nessun numero inventato.
Un errore qui non ferma mai le pagine /analysis (chiamato in try/except).
"""

import json
import os
import re
from datetime import datetime, timezone

import requests

import page_i18n as PI

L = PI.L
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://xenosfinance.com"
URL = f"{SITE}/analysis/oil-market"
EIA_WORKER_URL = "https://xenos-ai-proxy.xenosfinance.workers.dev"
FF_URL = "https://waves-production-ddbf.up.railway.app/ff-calendar?weeks=thisweek,nextweek"


def _esc(t):
    import html
    return html.escape(str(t if t is not None else ""), quote=True)


def _f(v, dec=2, plus=False):
    if v is None:
        return "—"
    return (f"{v:+,.{dec}f}" if plus else f"{v:,.{dec}f}")


def _ord(x):
    n = int(round(x))
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def _load(rel):
    try:
        return json.load(open(os.path.join(ROOT, rel), encoding="utf-8"))
    except Exception:
        return None


# ───────────────────────── dati ─────────────────────────
def spread_history(E):
    """Chiusure giornaliere WTI e Brent, serie CONTINUE front-month di entrambi → [(data, spread)].
    Non fetch_candles: per CL=F usa il contratto esplicito (es. CLZ26), e mesi fa quel contratto era
    un mese lontano, sotto il front in backwardation → spread storico gonfiato (+$10–15)."""
    def closes(sym):
        df = E.yf.download(sym, interval="1d", period="6mo", progress=False, auto_adjust=True)
        if E.pd.api.types.is_list_like(df.columns) and getattr(df.columns, "nlevels", 1) > 1:
            df.columns = df.columns.get_level_values(0)
        return {str(i)[:10]: float(v) for i, v in df["Close"].dropna().items()}
    a, b = closes("CL=F"), closes("BZ=F")
    days = sorted(set(a) & set(b))
    return [(d, b[d] - a[d]) for d in days]


def eia_report():
    """(rep, forecast, fonte). Preferito il file salvato dal bot (stesso consenso del post Telegram)."""
    st = _load("data/eia_wpsr_last.json") or {}
    if isinstance(st.get("rep"), dict) and st["rep"].get("stats", {}).get("crude"):
        return st["rep"], st.get("forecast"), "bot"
    try:
        r = requests.post(EIA_WORKER_URL, json={"type": "eia_wpsr"}, timeout=45)
        d = r.json()
        if d.get("stats", {}).get("crude"):
            return d, None, "worker"
    except Exception as e:
        print(f"  ! oil hub: EIA worker: {e}")
    return None, None, None


def oil_calendar(now):
    """Eventi del petrolio (scorte, OPEC) da ora in avanti, settimana corrente e prossima."""
    try:
        evs = requests.get(FF_URL, timeout=25).json().get("events", [])
    except Exception as e:
        print(f"  ! oil hub: calendar: {e}")
        return []
    out = []
    for ev in evs:
        title = str(ev.get("event", ""))
        if not re.search(r"crude|oil|opec|petroleum|gasoline|distillate", title, re.I):
            continue
        try:
            t = datetime.fromisoformat(str(ev.get("time")).replace("Z", "+00:00"))
        except Exception:
            continue
        if t.astimezone(timezone.utc) < now.replace(hour=0, minute=0, second=0, microsecond=0):
            continue
        out.append((t, title, ev.get("country", ""), ev.get("impact", ""),
                    ev.get("estimate") or ev.get("forecast") or "", ev.get("prev") or ev.get("previous") or "",
                    ev.get("actual") or ""))
    out.sort(key=lambda x: x[0])
    return out[:10]


# ─────────── lettura EIA: STESSE regole di eia_xenos_read (bot.py) ───────────
def eia_read(rep, fc):
    st = rep["stats"]
    cr = st["crude"]
    M = lambda k: st[k]["change"] / 1000.0 if st.get(k) else None
    A = lambda k: (st[k].get("change_5y_avg") or 0) / 1000.0 if st.get(k) else None
    score, drivers = 0, []

    def add(pts, txt):
        nonlocal score
        score += pts
        drivers.append((pts, txt))

    chg = M("crude")
    ref = fc if fc is not None else A("crude")
    ref_name = "consensus" if fc is not None else "5y seasonal"
    sur = chg - ref
    if sur <= -2.0:
        add(2, f"Crude {chg:+.1f}M vs {ref_name} {ref:+.1f}M — big draw surprise ({sur:+.1f}M)")
    elif sur <= -0.8:
        add(1, f"Crude {chg:+.1f}M vs {ref_name} {ref:+.1f}M — tighter than expected")
    elif sur >= 2.0:
        add(-2, f"Crude {chg:+.1f}M vs {ref_name} {ref:+.1f}M — big build surprise ({sur:+.1f}M)")
    elif sur >= 0.8:
        add(-1, f"Crude {chg:+.1f}M vs {ref_name} {ref:+.1f}M — looser than expected")
    else:
        add(0, f"Crude {chg:+.1f}M vs {ref_name} {ref:+.1f}M — in line")
    cu = st.get("cushing")
    if cu:
        c = cu["change"] / 1000.0
        if c <= -0.5:
            add(1, f"Cushing {c:+.1f}M — draw at the WTI delivery hub")
        elif c >= 0.5:
            add(-1, f"Cushing {c:+.1f}M — build at the WTI delivery hub")
    v5 = cr.get("vs_5y_pct")
    if v5 is not None:
        if v5 <= -3:
            add(1, f"Crude stocks {v5:+.1f}% vs 5y average — structurally tight")
        elif v5 >= 3:
            add(-1, f"Crude stocks {v5:+.1f}% vs 5y average — structurally comfortable")
    ru = st.get("refutil")
    if ru:
        if ru["change"] >= 0.8:
            add(1, f"Refinery runs {ru['value']:.1f}% ({ru['change']:+.1f} pp) — stronger crude demand")
        elif ru["change"] <= -0.8:
            add(-1, f"Refinery runs {ru['value']:.1f}% ({ru['change']:+.1f} pp) — weaker crude demand")
    pr = st.get("production")
    if pr:
        dp = pr["change"] / 1000.0
        if dp >= 0.10:
            add(-1, f"US output {pr['value'] / 1000:.2f} mb/d ({dp:+.2f}) — supply rising")
        elif dp <= -0.10:
            add(1, f"US output {pr['value'] / 1000:.2f} mb/d ({dp:+.2f}) — supply easing")
    ks = [k for k in ("crude", "gasoline", "distillate") if st.get(k)]
    tot, tot5 = sum(M(k) for k in ks), sum(A(k) for k in ks)
    if tot - tot5 <= -2.0:
        add(1, f"Total crude + products {tot:+.1f}M vs seasonal {tot5:+.1f}M — complex-wide draw")
    elif tot - tot5 >= 2.0:
        add(-1, f"Total crude + products {tot:+.1f}M vs seasonal {tot5:+.1f}M — complex-wide build")
    bias = ("bullish", "Bullish") if score >= 3 else ("bullish", "Mildly bullish") if score >= 1 else \
           ("bearish", "Bearish") if score <= -3 else ("bearish", "Mildly bearish") if score <= -1 else ("neutral", "Neutral")
    conv = "High" if abs(score) >= 4 else "Medium" if abs(score) >= 2 else "Low"

    def prod(k):
        if not st.get(k):
            return 0
        d = M(k) - A(k)
        return 1 if d <= -1.5 else -1 if d >= 1.5 else 0
    psc = prod("gasoline") + prod("distillate")
    if score >= 1 and psc >= 1:
        tk = "Tightness across crude and products — supportive for WTI/Brent; dips likely bought while the draw trend holds."
    elif score <= -1 and psc <= -1:
        tk = "Builds across crude and products — headwind for WTI/Brent; rallies vulnerable until balances tighten."
    elif score <= 0 and psc >= 1:
        tk = "Product-led tightness with soft crude balances — supportive for refining margins (crack spreads) more than for flat-price crude."
    elif score >= 1 and psc <= -1:
        tk = "Crude tightening but products building — refiners may cut runs; upside in crude needs product demand to confirm."
    elif score >= 1:
        tk = "Crude balances tightening — mild support for WTI; watch Cushing and refinery runs next week."
    elif score <= -1:
        tk = "Crude balances loosening — mild pressure on WTI; watch exports and runs for a reversal."
    else:
        tk = "Balanced report — no clear inventory signal; price action likely driven by macro and OPEC+ headlines."
    return {"score": score, "bias": bias, "conv": conv, "drivers": drivers, "takeaway": tk}


# ───────────────────────── grafici SVG (dati reali) ─────────────────────────
def svg_line(points, w=900, h=240, pad=(46, 14, 26, 10), fmt=lambda v: f"{v:.2f}", band=None, ref=None,
             label="", unit=""):
    """Linea singola con eventuale banda (min/max) e riferimento tratteggiato; crosshair al passaggio."""
    if len(points) < 2:
        return ""
    xs = list(range(len(points)))
    vals = [v for _, v in points]
    allv = vals + ([x for lo, hi in band for x in (lo, hi) if x is not None] if band else []) + \
           ([x for x in ref if x is not None] if ref else [])
    lo, hi = min(allv), max(allv)
    span = (hi - lo) or 1.0
    lo, hi = lo - span * 0.06, hi + span * 0.06
    L_, R_, B_, T_ = pad
    X = lambda i: L_ + (w - L_ - R_) * i / (len(points) - 1)
    Y = lambda v: T_ + (h - T_ - B_) * (1 - (v - lo) / (hi - lo))
    g = []
    for k in range(5):                                   # griglia recessiva
        v = lo + (hi - lo) * k / 4
        g.append(f'<line x1="{L_}" x2="{w - R_}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="#2e4570" stroke-width="1"/>'
                 f'<text x="{L_ - 6}" y="{Y(v) + 3:.1f}" text-anchor="end">{_esc(fmt(v))}</text>')
    for i in sorted({0, len(points) // 3, 2 * len(points) // 3, len(points) - 1}):
        d = datetime.strptime(points[i][0][:10], "%Y-%m-%d")
        g.append(f'<text x="{X(i):.1f}" y="{h - 6}" text-anchor="middle">{d:%d %b %y}</text>')
    if band:
        up = [(X(i), Y(b[1])) for i, b in enumerate(band) if b[0] is not None and b[1] is not None]
        dn = [(X(i), Y(b[0])) for i, b in enumerate(band) if b[0] is not None and b[1] is not None]
        if up:
            path = " ".join(f"{x:.1f},{y:.1f}" for x, y in up + dn[::-1])
            g.append(f'<polygon points="{path}" fill="#8aa2bb" fill-opacity="0.18"/>')
    if ref:
        pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(ref) if v is not None)
        g.append(f'<polyline points="{pts}" fill="none" stroke="#8aa2bb" stroke-width="1.5" stroke-dasharray="4 4"/>')
    if lo < 0 < hi:
        g.append(f'<line x1="{L_}" x2="{w - R_}" y1="{Y(0):.1f}" y2="{Y(0):.1f}" stroke="#8aa2bb" stroke-width="1"/>')
    line = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(vals))
    g.append(f'<polyline points="{line}" fill="none" stroke="#3b82f6" stroke-width="2" stroke-linejoin="round"/>')
    g.append(f'<circle cx="{X(len(vals) - 1):.1f}" cy="{Y(vals[-1]):.1f}" r="4" fill="#3b82f6" stroke="#1a273d" stroke-width="2"/>')
    data = json.dumps([[p[0][:10], round(p[1], 2)] + ([round(band[i][0], 1) if band[i][0] is not None else None,
                       round(band[i][1], 1) if band[i][1] is not None else None] if band else [])
                       for i, p in enumerate(points)], separators=(",", ":"))
    return (f'<figure class="chart" data-pts=\'{_esc(data)}\' data-unit="{_esc(unit)}" data-label="{_esc(label)}" '
            f'data-l="{L_}" data-r="{R_}" data-w="{w}">'
            f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{_esc(label)}" preserveAspectRatio="none">'
            + "".join(g) + f'<line class="xh" x1="0" x2="0" y1="{T_}" y2="{h - B_}" stroke="#c8d7e6" stroke-width="1" '
            f'visibility="hidden"/></svg><div class="tip" hidden></div></figure>')


CHART_JS = """<script>
document.querySelectorAll('figure.chart').forEach(function(f){
  var pts=JSON.parse(f.dataset.pts),svg=f.querySelector('svg'),xh=f.querySelector('.xh'),tip=f.querySelector('.tip');
  var L=+f.dataset.l,R=+f.dataset.r,W=+f.dataset.w,u=f.dataset.unit;
  function mv(e){var r=svg.getBoundingClientRect(),x=(e.clientX-r.left)/r.width*W;
    var i=Math.round((x-L)/(W-L-R)*(pts.length-1));if(i<0||i>=pts.length){out();return;}
    var px=L+(W-L-R)*i/(pts.length-1);xh.setAttribute('x1',px);xh.setAttribute('x2',px);xh.setAttribute('visibility','visible');
    var p=pts[i],t=p[0]+' · '+p[1]+u+(p.length>3&&p[2]!=null?' · 5y range '+p[2]+'–'+p[3]+u:'');
    tip.textContent=t;tip.hidden=false;tip.style.left=Math.min(Math.max(px/W*r.width-80,0),r.width-200)+'px';}
  function out(){xh.setAttribute('visibility','hidden');tip.hidden=true;}
  svg.addEventListener('mousemove',mv);svg.addEventListener('mouseleave',out);
  svg.addEventListener('touchstart',function(e){mv(e.touches[0]);},{passive:true});
});
</script>"""

EXTRA_CSS = """<style>
figure.chart{position:relative;margin:10px 0 4px;border:1px solid var(--border);background:var(--bg2);padding:6px 4px 0;}
figure.chart svg{width:100%;height:240px;display:block;font-family:var(--mono);font-size:10px;fill:#8aa2bb;}
figure.chart .tip{position:absolute;top:6px;background:#1a273d;border:1px solid var(--border2);color:var(--ink);font-family:var(--mono);
  font-size:11px;padding:4px 8px;white-space:nowrap;pointer-events:none;}
.legend{font-family:var(--mono);font-size:10px;color:var(--muted);margin:4px 0 12px;}
.legend i{display:inline-block;width:14px;height:2px;vertical-align:middle;margin:0 4px 0 12px;background:#3b82f6;}
.legend i.band{height:8px;background:rgba(138,162,187,.35);} .legend i.ref{background:none;border-top:2px dashed #8aa2bb;}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:8px 0 6px;}
.kpi{border:1px solid var(--border);background:var(--bg2);padding:10px 12px;}
.kpi .k{font-family:var(--mono);font-size:9px;letter-spacing:2px;text-transform:uppercase;color:var(--muted);}
.kpi .v{font-family:var(--mono);font-size:18px;color:var(--ink);margin-top:2px;}
.kpi .s{font-family:var(--mono);font-size:10px;color:var(--muted);}
.drv{list-style:none;font-family:var(--mono);font-size:12px;margin:6px 0 10px;}
.drv li{padding:3px 0;color:var(--ink2);} .drv li b{display:inline-block;width:18px;}
.src{font-family:var(--mono);font-size:10px;color:var(--muted);margin:2px 0 6px;}
.guide h3{font-family:var(--body);font-size:17px;color:var(--ink);margin:16px 0 4px;}
</style>"""


# ───────────────────────── pagina ─────────────────────────
def build(G, built, now):
    """G = modulo gen_analysis_pages (page_shell, fmt, zone_txt, RELATED, market_closed). Ritorna HTML o None."""
    E = G.E
    by = {inst[0]: (inst, d) for inst, d, ai in built}
    if "wti-crude-oil" not in by or "brent-crude-oil" not in by:
        print("  ! oil hub: WTI/Brent not computed — page not rebuilt")
        return None
    date_h = now.strftime("%d %B %Y")
    b = [EXTRA_CSS,
         f'<div class="crumb"><a href="/">Home</a> › <a href="/analysis/">{L("Daily Analysis", "Analisi giornaliera")}</a> › '
         f'{L("Crude Oil Market", "Mercato del petrolio")}</div>',
         f"<h1>{L('Crude Oil Market Today: WTI &amp; Brent', 'Mercato del petrolio oggi: WTI e Brent')}</h1>",
         f'<div class="upd">{L("Updated", "Aggiornato")} {now:%d %b %Y %H:%M} UTC · '
         f'{L("prices, inventories, positioning and futures curve in one page", "prezzi, scorte, posizionamento e curva dei futures in una pagina")}</div>']
    if G.market_closed(now, "Commodities"):
        b.append('<div class="stale">' + L("Markets closed — prices are as of Friday's close.",
                                            "Mercati chiusi — i prezzi sono alla chiusura di venerdì.") + "</div>")
    b.append("<p>" + L(
        "The XenosFinance energy desk page for crude oil: the technical picture of both benchmarks, the Brent–WTI spread, "
        "the shape of the futures curve, the latest U.S. EIA inventory report with our desk read, and how speculators are "
        "positioned in the CFTC Commitments of Traders. Every number comes from market data or official releases.",
        "La pagina del desk energia di XenosFinance sul greggio: quadro tecnico dei due benchmark, spread Brent–WTI, "
        "forma della curva dei futures, ultimo report EIA sulle scorte USA con la lettura del desk e posizionamento degli "
        "speculatori nel Commitments of Traders della CFTC. Ogni numero viene da dati di mercato o pubblicazioni ufficiali.") + "</p>")

    # 1) quadro tecnico
    rows = []
    for slug, label in (("wti-crude-oil", "WTI"), ("brent-crude-oil", "Brent")):
        inst, d = by[slug]
        dec = inst[4]
        sup, res = d["zones"]["supports"], d["zones"]["resistances"]
        ch = d.get("change_pct_day")
        dirw = d["bias"]["direction"]
        cls = {"bullish": "up", "bearish": "dn"}.get(dirw, "")
        ew = d.get("elliott") or {}
        ew_txt = (f"W{ew['wave']} · inv {G.fmt(ew['invalidation'], dec)}" if ew.get("wave") and ew.get("invalidation") is not None
                  else (f"W{ew['wave']}" if ew.get("wave") else "—"))
        rows.append(f'<tr><td><a href="/analysis/{slug}">{label}</a></td><td>{G.fmt(d["live"], dec)}</td>'
                    f'<td class="{"up" if (ch or 0) > 0 else "dn" if (ch or 0) < 0 else ""}">{_f(ch, 2, True)}%</td>'
                    f'<td class="{cls}">{L(dirw.capitalize(), PI.DIR_IT.get(dirw, dirw))}</td>'
                    f'<td>{G.zone_txt(sup[0], dec) if sup else "—"}</td><td>{G.zone_txt(res[0], dec) if res else "—"}</td>'
                    f'<td>{_esc(ew_txt)}</td></tr>')
    b.append(f"<h2>{L('WTI &amp; Brent — technical picture', 'WTI e Brent — quadro tecnico')}</h2>")
    b.append(f"<table><tr><th>{L('Benchmark', 'Benchmark')}</th><th>{L('Price', 'Prezzo')}</th><th>{L('Day', 'Giorno')}</th>"
             f"<th>{L('Bias 1H/4H', 'Bias 1H/4H')}</th><th>{L('Support', 'Supporto')}</th><th>{L('Resistance', 'Resistenza')}</th>"
             f"<th>Elliott 4H</th></tr>{''.join(rows)}</table>")
    b.append('<p class="src">' + L("Full levels, Elliott Wave count and trade scenarios: ", "Livelli completi, conteggio di Elliott e scenari: ")
             + '<a href="/analysis/wti-crude-oil">WTI</a> · <a href="/analysis/brent-crude-oil">Brent</a></p>')

    # 2) spread Brent–WTI
    try:
        hist = spread_history(E)
    except Exception as e:
        print(f"  ! oil hub: spread history: {e}")
        hist = []
    if len(hist) >= 20:
        now_sp = hist[-1][1]
        last3 = [v for _, v in hist[-63:]]
        avg3, lo3, hi3 = sum(last3) / len(last3), min(last3), max(last3)
        pct = sum(1 for v in last3 if v <= now_sp) / len(last3) * 100
        b.append(f"<h2>{L('Brent–WTI spread', 'Spread Brent–WTI')}</h2>")
        b.append('<div class="kpis">'
                 f'<div class="kpi"><div class="k">{L("Spread now", "Spread ora")}</div><div class="v">${now_sp:.2f}</div>'
                 f'<div class="s">{L("Brent premium" if now_sp >= 0 else "WTI premium", "premio Brent" if now_sp >= 0 else "premio WTI")} · {hist[-1][0]}</div></div>'
                 f'<div class="kpi"><div class="k">{L("3-month average", "Media 3 mesi")}</div><div class="v">${avg3:.2f}</div>'
                 f'<div class="s">{L("daily closes", "chiusure giornaliere")}</div></div>'
                 f'<div class="kpi"><div class="k">{L("3-month range", "Range 3 mesi")}</div><div class="v">${lo3:.2f}–{hi3:.2f}</div>'
                 f'<div class="s">{L(f"now at the {_ord(pct)} percentile", f"ora al {pct:.0f}° percentile")}</div></div></div>')
        b.append(svg_line(hist, fmt=lambda v: f"{v:.1f}", label="Brent–WTI spread, daily close ($/bbl)", unit=" $/bbl"))
        b.append('<div class="legend"><i></i>' + L("Brent minus WTI, front-month futures, daily close ($/bbl)",
                                                   "Brent meno WTI, futures front month, chiusura giornaliera ($/bbl)") + "</div>")
        b.append("<p>" + L(
            "Brent is the seaborne benchmark priced off North Sea crude; WTI is delivered inland at Cushing, Oklahoma. "
            "A wider spread usually reflects ample U.S. supply or tight global seaborne markets; a narrower spread reflects "
            "tighter U.S. balances or strong U.S. export demand. When the spread moves, the two benchmarks can show different "
            "short-term biases.",
            "Il Brent è il benchmark del greggio via mare, legato al Mare del Nord; il WTI è consegnato nell'entroterra a "
            "Cushing, in Oklahoma. Uno spread più ampio riflette di solito un'offerta USA abbondante o un mercato marittimo "
            "globale teso; uno spread più stretto riflette bilanci USA più tesi o una forte domanda di export USA. Quando lo "
            "spread si muove, i due benchmark possono mostrare bias di breve diversi.") + "</p>")

    # 3) curva dei futures e flussi (CME)
    fl = _load("futures-flow/latest.json") or {}
    prods = {p.get("key"): p for p in fl.get("products", [])}
    if prods.get("cl") or prods.get("bz"):
        b.append(f"<h2>{L('Oil futures forward curve &amp; flows', 'Curva forward dei futures sul petrolio e flussi')}</h2>")  # 2026-11-08 SEO: ricerca "oil price forward curve" (pos. ~10)
        b.append(f"<table><tr><th>{L('Contract', 'Contratto')}</th><th>{L('Settle', 'Settle')}</th><th>{L('Day', 'Giorno')}</th>"
                 f"<th>{L('Structure', 'Struttura')}</th><th>M1–M2</th><th>M1–M6</th><th>{L('Open interest', 'Open interest')}</th>"
                 f"<th>{L('Flow', 'Flusso')}</th></tr>")
        for k, nm in (("cl", "WTI"), ("bz", "Brent")):
            p = prods.get(k)
            if not p:
                continue
            stc = p.get("structure") or "—"
            stc_it = {"backwardation": "backwardation", "contango": "contango"}.get(stc, stc)
            # 2026-11-13: riga sul FRONT MONTH (M1), lo stesso contratto da cui partono gli spread M1–M2 / M1–M6.
            # Prima mostrava il contratto più scambiato (es. BZG27 = M2) → settle ~$2.5 sotto il front e il prezzo
            # live, e spread in tabella riferiti a un contratto diverso da quello mostrato.
            cur = p.get("curve") or []
            m1s = p.get("m1") or (cur[0][0] if cur else p.get("active", ""))
            m1p = next((r[1] for r in cur if r[0] == m1s), None)
            if m1p is None:
                m1s, m1p = p.get("active", ""), p.get("active_price")
            dchg = p.get("price_chg") if m1s == p.get("active") else p.get("m1_chg")
            b.append(f"<tr><td>{nm} {_esc(m1s)}</td><td>{_f(m1p)}</td>"
                     f"<td class=\"{'up' if (dchg or 0) > 0 else 'dn'}\">{_f(dchg, 2, True)}{'%' if dchg is not None else ''}</td>"
                     f"<td>{L(_esc(stc), _esc(stc_it))}</td><td>{_f(p.get('spread_m1m2'), 2, True)}</td>"
                     f"<td>{_f(p.get('spread_m1m6'), 2, True)}</td><td>{_f(p.get('oi_chg'), 0, True)}</td>"
                     f"<td>{_esc(p.get('flow') or '—')}</td></tr>")
        b.append("</table>")
        _ct = " · ".join(f"{nm} M1 {_esc(prods[k].get('m1', ''))} / M2 {_esc(prods[k].get('m2', ''))} / M6 {_esc(prods[k].get('m6', ''))}"
                         for k, nm in (("cl", "WTI"), ("bz", "Brent")) if prods.get(k))
        if _ct:
            b.append(f'<p class="src">{L("Front month (M1) settlement; spreads against", "Settlement del primo mese (M1); spread rispetto a")} {_ct}</p>')
        b.append(f'<p class="src">CME · {L("session", "sessione")} {_esc(fl.get("session", ""))} · '
                 f'<a href="/futures-flow/">{L("Full Futures Flow report", "Report Futures Flow completo")}</a></p>')
        if fl.get("oil_read"):
            b.append(f"<p>{_esc(fl['oil_read'])}</p>")
        b.append("<p>" + L(
            "Backwardation (nearby contracts above deferred ones) signals prompt tightness: buyers pay up for barrels now. "
            "Contango (nearby below deferred) signals ample supply and pays for storage.",
            "Backwardation (contratti vicini sopra quelli lontani) segnala tensione immediata: chi compra paga di più per i "
            "barili subito. Contango (vicini sotto i lontani) segnala offerta abbondante e remunera lo stoccaggio.") + "</p>")

    # 4) scorte EIA
    rep, fc, src = eia_report()
    if rep:
        st = rep["stats"]
        we = rep.get("week_ending", "")
        rd = eia_read(rep, fc)
        b.append(f"<h2>{L('EIA weekly inventories', 'Scorte settimanali EIA')}</h2>")
        b.append(f'<p class="src">U.S. Energy Information Administration · {L("week ending", "settimana al")} {_esc(we)}'
                 + (f' · {L("consensus", "consenso")} crude {fc:+.1f}M' if fc is not None else "") + "</p>")
        b.append(f"<table><tr><th>{L('Inventory', 'Scorte')}</th><th>{L('Change w/w', 'Variazione sett.')}</th>"
                 f"<th>{L('5y avg change', 'Media 5 anni')}</th><th>{L('Level', 'Livello')}</th></tr>")
        for k, en, it in (("crude", "Crude (ex SPR)", "Greggio (escl. SPR)"), ("gasoline", "Gasoline", "Benzina"),
                          ("distillate", "Distillates", "Distillati"), ("cushing", "Cushing", "Cushing"), ("spr", "SPR", "SPR")):
            s = st.get(k)
            if not s:
                continue
            c5 = s.get("change_5y_avg")
            c5_txt = f"{c5 / 1000:+.1f}M" if c5 is not None else "—"
            lvl_txt = f"{s['value'] / 1000:.1f}M bbl" if s.get("value") else "—"
            cls_c = "dn" if s["change"] > 0 else "up"
            b.append(f'<tr><td>{L(en, it)}</td><td class="{cls_c}">{s["change"] / 1000:+.1f}M</td>'
                     f"<td>{c5_txt}</td><td>{lvl_txt}</td></tr>")
        b.append("</table>")
        sup = []
        if st.get("production"):
            p = st["production"]
            sup.append(f'<div class="kpi"><div class="k">{L("US production", "Produzione USA")}</div>'
                       f'<div class="v">{p["value"] / 1000:.2f} mb/d</div><div class="s">{p["change"] / 1000:+.2f} w/w</div></div>')
        if st.get("refutil"):
            ru = st["refutil"]
            sup.append(f'<div class="kpi"><div class="k">{L("Refinery utilization", "Utilizzo raffinerie")}</div>'
                       f'<div class="v">{ru["value"]:.1f}%</div><div class="s">{ru["change"]:+.1f} pp</div></div>')
        if st.get("imports") and st.get("exports"):
            sup.append(f'<div class="kpi"><div class="k">{L("Crude imports / exports", "Import / export greggio")}</div>'
                       f'<div class="v">{st["imports"]["value"] / 1000:.2f} / {st["exports"]["value"] / 1000:.2f}</div>'
                       f'<div class="s">mb/d</div></div>')
        if st["crude"].get("vs_5y_pct") is not None:
            sup.append(f'<div class="kpi"><div class="k">{L("Crude vs 5y average", "Greggio vs media 5 anni")}</div>'
                       f'<div class="v">{st["crude"]["vs_5y_pct"]:+.1f}%</div><div class="s">{L("stock level", "livello scorte")}</div></div>')
        if sup:
            b.append('<div class="kpis">' + "".join(sup) + "</div>")
        hist = rep.get("crude_history") or []
        if len(hist) >= 10:
            pts = [(h["period"], round(h["value"] / 1000, 1)) for h in hist]
            band = [((h.get("min5") or 0) / 1000 or None, (h.get("max5") or 0) / 1000 or None) for h in hist]
            ref = [(h.get("avg5") or 0) / 1000 or None for h in hist]
            b.append(svg_line(pts, fmt=lambda v: f"{v:.0f}", band=band, ref=ref,
                              label="US commercial crude stocks vs 5-year range (million barrels)", unit="M"))
            b.append('<div class="legend"><i></i>' + L("Crude stocks ex SPR (M bbl)", "Scorte greggio escl. SPR (M bbl)")
                     + '<i class="band"></i>' + L("5-year range", "Range 5 anni") + '<i class="ref"></i>'
                     + L("5-year average", "Media 5 anni") + "</div>")
        cls = {"bullish": "up", "bearish": "dn"}.get(rd["bias"][0], "")
        b.append('<div class="box">'
                 f'<p><b>{L("Xenos read", "Lettura Xenos")}:</b> <span class="{cls}">{_esc(rd["bias"][1])}</span> · '
                 f'{L("conviction", "convinzione")} {_esc(rd["conv"])} ({L("score", "punteggio")} {rd["score"]:+d})</p>'
                 '<ul class="drv">' + "".join(
                     f'<li><b class="{"up" if p > 0 else "dn" if p < 0 else ""}">{"+" if p > 0 else "−" if p < 0 else "·"}</b>{_esc(t)}</li>'
                     for p, t in rd["drivers"]) + "</ul>"
                 f"<p><b>{L('Takeaway', 'In sintesi')}:</b> {_esc(rd['takeaway'])}</p></div>")

    # 5) COT
    cot = _load("cot/latest.json") or {}
    mk = {m.get("key"): m for m in cot.get("markets", [])}
    if mk.get("wti") or mk.get("brent"):
        b.append(f"<h2>{L('Positioning — CFTC Commitments of Traders', 'Posizionamento — CFTC Commitments of Traders')}</h2>")
        b.append(f"<table><tr><th>{L('Market', 'Mercato')}</th><th>{L('Managed money net', 'Managed money netto')}</th>"
                 f"<th>{L('1 week', '1 settimana')}</th><th>{L('4 weeks', '4 settimane')}</th><th>COT index</th>"
                 f"<th>{L('Price w/w', 'Prezzo sett.')}</th></tr>")
        for k, nm in (("wti", "WTI"), ("brent", "Brent")):
            m = mk.get(k)
            if not m:
                continue
            b.append(f"<tr><td>{nm}</td><td>{_f(m.get('net'), 0, True)}</td><td>{_f(m.get('chg'), 0, True)}</td>"
                     f"<td>{_f(m.get('chg4'), 0, True)}</td><td>{_f(m.get('cot_index'), 0)}</td>"
                     f"<td>{_f(m.get('price_chg'), 1, True)}%</td></tr>")
        b.append("</table>")
        b.append(f'<p class="src">CFTC · {L("positions as of", "posizioni al")} {_esc(cot.get("report_date", ""))}, '
                 f'{L("released", "pubblicato")} {_esc(cot.get("release_date", ""))} · '
                 f'<a href="/cot/">{L("Full COT report", "Report COT completo")}</a></p>')
        if cot.get("oil_read"):
            b.append(f"<p>{_esc(cot['oil_read'])}</p>")
        b.append("<p>" + L(
            "COT index: where today's managed-money net position sits in its range of the last three years (0 = most short, "
            "100 = most long). Extremes often mark crowded trades.",
            "COT index: dove si trova oggi la posizione netta dei managed money nel suo range degli ultimi tre anni "
            "(0 = massimo short, 100 = massimo long). Gli estremi segnalano spesso posizioni affollate.") + "</p>")

    # 6) calendario
    cal = oil_calendar(now)
    if cal:
        import zoneinfo
        rome = zoneinfo.ZoneInfo("Europe/Rome")
        b.append(f"<h2>{L('Oil calendar', 'Calendario petrolio')}</h2><table><tr><th>{L('When (CET)', 'Quando (CET)')}</th>"
                 f"<th>{L('Event', 'Evento')}</th><th>{L('Forecast', 'Previsione')}</th><th>{L('Previous', 'Precedente')}</th>"
                 f"<th>{L('Actual', 'Effettivo')}</th></tr>")
        for t, title, ctry, imp, fc_, pv, act in cal:
            b.append(f"<tr><td>{t.astimezone(rome):%a %d %b %H:%M}</td><td>{_esc(ctry)} {_esc(title)}</td>"
                     f"<td>{_esc(fc_ or '—')}</td><td>{_esc(pv or '—')}</td><td>{_esc(act or '—')}</td></tr>")
        b.append("</table>")

    # 7) guida
    b.append(f"<h2>{L('How to read the oil market', 'Come leggere il mercato del petrolio')}</h2><div class=\"guide\">")
    for en_h, it_h, en_p, it_p in (
        ("WTI and Brent", "WTI e Brent",
         "WTI (NYMEX, delivered at Cushing) is the U.S. benchmark; Brent (ICE, North Sea) prices most of the world's "
         "seaborne crude. They trend together, but local supply, pipelines, shipping and export flows move the spread.",
         "Il WTI (NYMEX, consegna a Cushing) è il benchmark USA; il Brent (ICE, Mare del Nord) prezza la maggior parte del "
         "greggio trasportato via mare nel mondo. Hanno lo stesso trend, ma offerta locale, oleodotti, trasporto marittimo "
         "ed export muovono lo spread."),
        ("The weekly inventory cycle", "Il ciclo settimanale delle scorte",
         "The API publishes its estimate on Tuesday at 16:30 ET; the official EIA Weekly Petroleum Status Report follows on "
         "Wednesday at 10:30 ET (16:30 CET), one day later in weeks with a U.S. holiday. Markets react to the surprise versus "
         "consensus, to Cushing, and to products (gasoline, distillates) as a read on demand.",
         "L'API pubblica la sua stima il martedì alle 16:30 ET; il report ufficiale EIA (Weekly Petroleum Status Report) "
         "esce il mercoledì alle 10:30 ET (16:30 in Italia), un giorno dopo nelle settimane con festività USA. Il mercato "
         "reagisce alla sorpresa rispetto al consenso, a Cushing e ai prodotti (benzina, distillati) come misura della domanda."),
        ("Positioning", "Posizionamento",
         "The CFTC Commitments of Traders reports positions as of Tuesday and is released on Friday at 15:30 ET. Managed money "
         "(funds) is the speculative flow; producers and swap dealers hedge physical exposure.",
         "Il Commitments of Traders della CFTC riporta le posizioni al martedì ed è pubblicato il venerdì alle 15:30 ET. I "
         "managed money (fondi) sono il flusso speculativo; produttori e swap dealer coprono esposizioni fisiche."),
        ("The futures curve", "La curva dei futures",
         "The spread between the front month and later months is a real-time gauge of physical tightness. A curve moving "
         "deeper into backwardation while inventories draw confirms a tight market; a flattening curve with builds warns "
         "the opposite.",
         "Lo spread tra il primo mese e i mesi successivi misura in tempo reale la tensione fisica. Una curva che va più in "
         "backwardation mentre le scorte calano conferma un mercato teso; una curva che si appiattisce con scorte in aumento "
         "segnala il contrario.")):
        b.append(f"<h3>{L(en_h, it_h)}</h3><p>{L(en_p, it_p)}</p>")
    b.append("</div>")

    # 8) collegamenti
    links = [("/analysis/wti-crude-oil", "WTI technical analysis", "Analisi tecnica WTI"),
             ("/analysis/brent-crude-oil", "Brent technical analysis", "Analisi tecnica Brent"),
             ("/analysis/natural-gas", "Natural gas analysis", "Analisi gas naturale"),
             ("/cot/", "COT positioning", "Posizionamento COT"), ("/futures-flow/", "Futures Flow", "Futures Flow"),
             ("/elliottwave", "Elliott Wave", "Onde di Elliott"),
             ("/topics/oil-market", "Oil market news &amp; articles", "Notizie e articoli sul petrolio")]
    b.append(f"<h2>{L('Related', 'Collegati')}</h2><div class=\"rel\">"
             + "".join(f'<a href="{h}">{L(en, it)}</a>' for h, en, it in links) + "</div>")
    arts = (getattr(G, "RELATED", {}) or {}).get("wti-crude-oil") or []
    if arts:
        b.append(f"<h2>{L('Latest oil articles', 'Ultimi articoli sul petrolio')}</h2><div class=\"rel\">"
                 + "".join(f'<a href="/XenosBlog?slug={_esc(s)}">{L(_esc(t), _esc(ti) if ti else "")}</a>'
                           for s, t, ti, _d in arts) + "</div>")
    b.append(CHART_JS)

    wti, brent = by["wti-crude-oil"][1], by["brent-crude-oil"][1]
    title = "Crude Oil Market Today — WTI & Brent, Futures Forward Curve, EIA Inventories | XenosFinance"
    title_it = "Petrolio oggi — WTI e Brent, curva forward dei futures, scorte EIA | XenosFinance"
    desc = (f"Crude oil market on {date_h}: WTI {G.fmt(wti['live'], 2)} ({wti['bias']['direction']} bias), "
            f"Brent {G.fmt(brent['live'], 2)}, Brent–WTI spread, futures curve, latest EIA inventories with desk read "
            f"and CFTC positioning.")
    jsonld = [{"@context": "https://schema.org", "@type": "WebPage", "name": title, "description": desc, "url": URL,
               "dateModified": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
               "publisher": {"@type": "Organization", "name": "XenosFinance", "url": SITE},
               "about": [{"@type": "Thing", "name": "Crude oil"}, {"@type": "Thing", "name": "WTI"},
                         {"@type": "Thing", "name": "Brent crude"}]},
              {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                  {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE},
                  {"@type": "ListItem", "position": 2, "name": "Daily Analysis", "item": f"{SITE}/analysis/"},
                  {"@type": "ListItem", "position": 3, "name": "Crude Oil Market", "item": URL}]}]
    kw = ("crude oil market today, oil price analysis, WTI analysis, Brent analysis, Brent WTI spread, EIA crude inventories, "
          "oil inventories this week, crude oil COT, oil futures curve backwardation")
    return G.page_shell(title, desc, URL, "\n".join(b), jsonld, kw, active="/analysis/", it_title=title_it)
