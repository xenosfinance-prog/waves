#!/usr/bin/env python3
"""
gen_futures_flow.py — XenosFinance daily Futures Flow (2026-10-14)

CME data is not scraped (CME blocks automated access and its Terms of Use
forbid it). Source: Yahoo Finance per-contract futures quotes (price, volume,
open interest of each listed month: CLX26.NYM, CLZ26.NYM, ...).

Every run stores a snapshot in futures-flow/history.json (rolling 90 days), so
day-over-day open-interest changes come from our own history.

Output:
  futures-flow/index.html   → https://xenosfinance.com/futures-flow
  futures-flow/latest.json  → read by the Telegram bot for the daily channel post
  futures-flow/history.json → per-day snapshots (OI, volume, settle per contract)
  sitemap.xml          → /futures-flow entry

All numbers computed in code.
2026-10-16: "Desk read" summary (tools/desk_read.py): Claude rewrites ONLY the computed
figures, every number is checked against them; otherwise a rule-based summary is used.
2026-10-16: FIX price d/d and volume — the run is at 05:30 UTC, when Yahoo already has a
partial daily bar for the new session (volumes read 0.01-0.16x, price change = overnight
move). Both now use only completed sessions (bars dated before today UTC).
"""

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)
import gen_analysis_pages as G  # noqa: E402
import desk_read as D  # noqa: E402  Desk read (sintesi)

SITE = "https://xenosfinance.com"
OUT_DIR = os.path.join(ROOT, "futures-flow")
HIST = os.path.join(OUT_DIR, "history.json")
MONTHS = "FGHJKMNQUVXZ"
KEEP_DAYS = 90

# key, root, exchange suffix, name, continuous ticker, months ahead to scan, decimals, unit
PRODUCTS = [
    ("cl", "CL", "NYM", "WTI Crude Oil", "CL=F", 14, 2, "$/bbl"),
    ("bz", "BZ", "NYM", "Brent (NYMEX)", "BZ=F", 8, 2, "$/bbl"),
    ("ng", "NG", "NYM", "Natural Gas", "NG=F", 14, 3, "$/MMBtu"),
    ("gc", "GC", "CMX", "Gold", "GC=F", 14, 1, "$/oz"),
    ("si", "SI", "CMX", "Silver", "SI=F", 14, 3, "$/oz"),
    ("hg", "HG", "CMX", "Copper", "HG=F", 14, 4, "$/lb"),
    ("es", "ES", "CME", "S&P 500", "ES=F", 12, 2, "pts"),
    ("nq", "NQ", "CME", "Nasdaq 100", "NQ=F", 12, 2, "pts"),
]


def esc(t):
    return G.esc(t)


def contract_symbols(root, ex, n, today):
    out = []
    for i in range(n):
        m0 = today.month - 1 + i
        yy, mm = today.year + m0 // 12, m0 % 12 + 1
        out.append((f"{yy}-{mm:02d}", f"{root}{MONTHS[mm - 1]}{str(yy)[2:]}.{ex}"))
    return out


def snapshot(prod, today):
    import yfinance as yf
    key, root, ex, name, cont, n, dec, unit = prod
    rows = []
    for ym, sym in contract_symbols(root, ex, n, today):
        try:
            inf = yf.Ticker(sym).info or {}
        except Exception as e:
            print(f"  ! {sym}: {e}")
            continue
        px = inf.get("regularMarketPrice") or inf.get("previousClose")
        if not px:
            continue
        rows.append({"ym": ym, "sym": sym.split(".")[0], "price": float(px),
                     "prev": float(inf["regularMarketPreviousClose"]) if inf.get("regularMarketPreviousClose") else None,
                     "vol": int(inf.get("volume") or 0), "oi": int(inf.get("openInterest") or 0)})
    return rows


def total_volume_stats(prod, rows):
    """FIX 2026-10-14: volume TOTALE della curva (somma dei mesi quotati) vs la sua media a
    20 sedute. Il volume del continuo (SI=F, HG=F) salta ai roll: argento risultava 262x.
    2026-11-17: ritorna anche, per OGNI contratto, chiusura e volume dell'ultima seduta conclusa
    e la chiusura della seduta prima → (vol_now, vol_avg, {sym: (close, prev_close, volume)})."""
    import yfinance as yf
    syms = [f"{r['sym']}.{prod[2]}" for r in rows]
    last = {}
    try:
        df = yf.download(syms, period="3mo", interval="1d", group_by="ticker", progress=False, threads=True)
        today = datetime.now(timezone.utc).date()
        tot = None
        for sy in syms:
            try:
                sub = df[sy] if len(syms) > 1 else df
                sub = sub[[i.date() < today for i in sub.index]]   # solo sedute concluse
                v = sub["Volume"].fillna(0)
                c = sub["Close"].dropna()
                c = c[c > 0]
                if len(c) >= 2:
                    last[sy.split(".")[0]] = (float(c.iloc[-1]), float(c.iloc[-2]),
                                              int(v.loc[c.index[-1]]) if c.index[-1] in v.index else 0)
            except Exception:
                continue
            tot = v if tot is None else tot.add(v, fill_value=0)
        if tot is None:
            return None, None, last
        tot = [float(x) for x in tot if x and x > 0]
        if len(tot) >= 21:
            return tot[-1], sum(tot[-21:-1]) / 20, last
    except Exception as e:
        print(f"  ! volume {prod[0]}: {e}")
    return None, None, last


def _bday_back(d, n):
    """n giorni lavorativi (lun–ven) prima di d. Festività ignorate: errore massimo 1 giorno."""
    while n > 0:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def last_trade_day(key, ym):
    """2026-11-17: ultimo giorno di negoziazione (regole CME) per i prodotti energia; None per gli altri.
    CL: 3 giorni lavorativi prima del 25 del mese precedente la consegna (se il 25 non è lavorativo, si parte
    dal giorno lavorativo precedente). NG: 3 giorni lavorativi prima del primo giorno del mese di consegna.
    BZ (Brent NYMEX): ultimo giorno lavorativo del secondo mese prima della consegna."""
    y, m = int(ym[:4]), int(ym[5:7])
    if key == "cl":
        py, pm = (y, m - 1) if m > 1 else (y - 1, 12)
        d = date(py, pm, 25)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        return _bday_back(d, 3)
    if key == "ng":
        return _bday_back(date(y, m, 1), 3)
    if key == "bz":
        py, pm = (y, m - 2) if m > 2 else (y - 1, m + 10)
        d = date(py + (pm // 12), pm % 12 + 1, 1) - timedelta(days=1)   # ultimo giorno del mese pm
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        return d
    return None


ROLL_DAYS = 10


def kfmt(v):
    a = abs(v)
    s = f"{a / 1000:.1f}k" if a >= 1000 else f"{a:.0f}"
    return ("+" if v > 0 else "-" if v < 0 else "") + s


OI_MIN_PCT = 0.5   # 2026-11-17: sotto lo 0.5% dell'OI totale la variazione è rumore/roll, non un flusso


def quadrant(pchg, oichg, oi_tot=None):
    if pchg is None or oichg is None or oichg == 0:
        return ""
    # 2026-11-17: il 16/11 oro (−1.6k, −0.4%) e rame (−0.9k, −0.3%) erano "long liquidation" mentre
    # l'OI si stava solo spostando da dicembre ai mesi successivi (Z26 −11.3k / −8.9k)
    if oi_tot and abs(oichg) / max(oi_tot - oichg, 1) * 100 < OI_MIN_PCT:
        return ""
    if pchg > 0 and oichg > 0:
        return "New longs"
    if pchg < 0 and oichg > 0:
        return "New shorts"
    if pchg > 0 and oichg < 0:
        return "Short covering"
    return "Long liquidation"


def analyse(prod, rows, prev_rows, vol_now, vol_avg):
    key, root, ex, name, cont, n, dec, unit = prod
    rows = [r for r in rows if r["oi"] > 0 or r["vol"] > 0]
    if len(rows) < 2:
        raise ValueError("not enough live contracts")
    front = rows[0]
    # 2026-11-17: SETTIMANA DI SCADENZA. Il 16/11 il front WTI era CLZ26 (scade il 20/11) con 134k di
    # OI contro i 266k di CLF27: il mercato era già passato a gennaio, ma curva e spread venivano
    # misurati sul contratto in scadenza e il -29k di OI su CLZ26 (posizioni chiuse/rollate per la
    # scadenza) diventava "long liquidation". Regola standard: il mese di riferimento (M1) è il primo
    # con open interest non inferiore al successivo (al massimo 2 salti: es. oro Nov → Dic).
    # Energia: si salta il front SOLO se scade entro ROLL_DAYS giorni E ha già meno OI del mese dopo
    # (il Brent NYMEX ha più OI sui mesi successivi anche lontano dalla scadenza: col solo OI saltava
    # BZF27, che scade il 30/11). Metalli/indici: mese di consegna con poco OI (es. oro Nov) → si salta.
    today_ = datetime.now(timezone.utc).date()
    i0 = 0
    while i0 < 2 and i0 + 1 < len(rows) and rows[i0]["oi"] < rows[i0 + 1]["oi"]:
        ltd = last_trade_day(key, rows[i0]["ym"])
        if ltd is not None and (ltd - today_).days > ROLL_DAYS:
            break
        i0 += 1
    rolling = [r["sym"] for r in rows[:i0]]
    active = max(rows, key=lambda r: r["vol"])
    oi_tot = sum(r["oi"] for r in rows)
    vol_tot = sum(r["vol"] for r in rows)
    prev_map = {r["sym"]: r for r in (prev_rows or [])}
    oi_prev = sum(prev_map[r["sym"]]["oi"] for r in rows if r["sym"] in prev_map) if prev_map else None
    oi_chg = (oi_tot - oi_prev) if oi_prev else None
    ref = active  # price change measured on the most active month (avoids expiry noise)
    pchg = None
    try:  # 2026-10-14: ultime due chiusure giornaliere reali (previousClose di Yahoo a volte è vecchio)
        import yfinance as yf
        h = yf.Ticker(f"{ref['sym']}.{prod[2]}").history(period="10d", interval="1d")
        today = datetime.now(timezone.utc).date()
        h = h[[i.date() < today for i in h.index]]          # solo sedute concluse (niente barra parziale)
        c = [float(x) for x in h["Close"] if x and x > 0]
        if len(c) >= 2:
            pchg = (c[-1] / c[-2] - 1) * 100
    except Exception as e:
        print(f"  ! closes {ref['sym']}: {e}")
    # (nessun fallback su price/previousClose di .info: a quell'ora è il movimento overnight, non la seduta)
    # 2026-11-13: anche la variazione del FRONT MONTH (M1), per le tabelle che mostrano M1 e gli spread M1–Mx
    m1_chg = pchg if rows[i0]["sym"] == ref["sym"] else None
    if m1_chg is None:
        try:
            import yfinance as yf
            h1 = yf.Ticker(f"{rows[i0]['sym']}.{prod[2]}").history(period="10d", interval="1d")
            today = datetime.now(timezone.utc).date()
            h1 = h1[[i.date() < today for i in h1.index]]
            c1 = [float(x) for x in h1["Close"] if x and x > 0]
            if len(c1) >= 2:
                m1_chg = (c1[-1] / c1[-2] - 1) * 100
        except Exception as e:
            print(f"  ! closes {rows[i0]['sym']}: {e}")
    by_oi_chg = []
    if prev_map:
        for r in rows:
            p = prev_map.get(r["sym"])
            if p:
                by_oi_chg.append((r["oi"] - p["oi"], r["sym"]))
    top_oi = max(by_oi_chg, key=lambda t: abs(t[0])) if by_oi_chg else None
    m1 = rows[i0]
    m2 = rows[i0 + 1] if i0 + 1 < len(rows) else rows[-1]
    m6 = rows[i0 + 5] if len(rows) > i0 + 5 else rows[-1]
    sp12 = m1["price"] - m2["price"]
    sp16 = m1["price"] - m6["price"]
    flow = quadrant(pchg, oi_chg, oi_tot)
    # il movimento di OI più grande è sul contratto in scadenza → è il roll, non un flusso direzionale
    if rolling and top_oi and top_oi[1] in rolling:
        flow = "Expiry roll"
    res = {
        "key": key, "name": name, "unit": unit, "dec": dec,
        "front": front["sym"], "active": active["sym"], "active_price": active["price"], "price_chg": pchg,
        "oi_total": oi_tot, "oi_chg": oi_chg, "vol_total": vol_tot,
        "vol_today": vol_now, "vol_avg20": vol_avg,
        "vol_ratio": (vol_now / vol_avg) if vol_now and vol_avg else None,
        "flow": flow, "top_oi_move": top_oi, "rolling": rolling,
        "m1": m1["sym"], "m2": m2["sym"], "m6": m6["sym"],
        "spread_m1m2": sp12, "spread_m1m6": sp16,
        "m1_price": m1["price"], "m1_chg": m1_chg,
        # gas naturale: curva stagionale (inverno > primavera) → struttura letta su M1–M2
        "structure": ("backwardation" if (sp12 if key == "ng" else sp16) > 0 else "contango"),
        "curve": [[r["sym"], r["price"], r["oi"], r["vol"]] for r in rows],
    }
    # 2026-11-17: variazione dello spread sulle due ULTIME CHIUSURE di ciascun contratto (stessa fonte,
    # stessi orari); lo snapshot del giorno prima resta solo come ripiego
    if m1.get("prev_close") and m6.get("prev_close"):
        res["spread_m1m6_chg"] = sp16 - (m1["prev_close"] - m6["prev_close"])
    elif prev_map and m1["sym"] in prev_map and m6["sym"] in prev_map:
        res["spread_m1m6_chg"] = sp16 - (prev_map[m1["sym"]]["price"] - prev_map[m6["sym"]]["price"])
    return res


def curve_svg(res, prev_rows, w=320, h=90):
    pts = res["curve"]
    prev_map = {r["sym"]: r["price"] for r in (prev_rows or [])}
    vals = [p[1] for p in pts] + [prev_map[p[0]] for p in pts if p[0] in prev_map]
    lo, hi = min(vals), max(vals)
    sp = (hi - lo) or 1
    n = len(pts)
    x = lambda i: 8 + i * (w - 16) / max(n - 1, 1)
    y = lambda v: h - 10 - (v - lo) / sp * (h - 22)
    oimax = max(p[2] for p in pts) or 1
    bars = "".join(f'<rect x="{x(i) - 5:.1f}" y="{h - 4 - p[2] / oimax * 26:.1f}" width="10" height="{p[2] / oimax * 26:.1f}" '
                   f'fill="#355281"/>' for i, p in enumerate(pts))
    today = " ".join(f"{x(i):.1f},{y(p[1]):.1f}" for i, p in enumerate(pts))
    prev = " ".join(f"{x(i):.1f},{y(prev_map[p[0]]):.1f}" for i, p in enumerate(pts) if p[0] in prev_map)
    labels = "".join(f'<text x="{x(i):.1f}" y="{h}" fill="#c8d7e6" font-size="8" text-anchor="middle" '
                     f'font-family="IBM Plex Mono">{p[0][2:]}</text>' for i, p in enumerate(pts) if i % 2 == 0)
    return (f'<svg viewBox="0 0 {w} {h + 4}" width="100%" height="{h + 4}" role="img" aria-label="futures curve">{bars}'
            + (f'<polyline points="{prev}" fill="none" stroke="#8aa2bb" stroke-dasharray="3 3" stroke-width="1.2"/>' if prev else "")
            + f'<polyline points="{today}" fill="none" stroke="#3b82f6" stroke-width="1.8"/>{labels}</svg>')


def fp(v, dec):
    return f"{v:,.{dec}f}"


def telegram_html(res, day, desk=None, oil=None, bias=None):
    import html as H
    lines = ["<b>XENOS WAVE · FUTURES FLOW</b>", f"<b>Session {day:%a %d %b} · open interest &amp; curve</b>", ""]
    tab = []
    for r in res:
        pc = f"{r['price_chg']:+.1f}%" if r["price_chg"] is not None else "  n/a"
        oc = kfmt(r["oi_chg"]) if r["oi_chg"] is not None else "n/a"
        vr = f"{r['vol_ratio']:.1f}x" if r["vol_ratio"] else " n/a"
        tab.append(f"{r['name'][:13]:<13} {pc:>6}  OI {oc:>7}  vol {vr:>4}")
    lines.append("<pre>" + H.escape("\n".join(tab)) + "</pre>")
    if desk:
        lines += ["<b>Desk read</b>", H.escape(desk), ""]
    if oil:
        lines += ["<b>Oil desk — WTI &amp; Brent</b>", H.escape(oil), ""]
    flows = [r for r in res if r["flow"]]
    if flows:
        lines.append("<b>Positioning read</b>")
        lines += [f"• {H.escape(r['name'])}: {r['flow'].lower()}" for r in flows]
    hot = [r for r in res if r["vol_ratio"] and r["vol_ratio"] >= 1.5]
    if hot:
        lines.append("<b>Heavy volume</b>: " + " · ".join(f"{H.escape(r['name'])} {r['vol_ratio']:.1f}x 20d avg" for r in hot))
    cl = next((r for r in res if r["key"] == "cl"), None)
    bz = next((r for r in res if r["key"] == "bz"), None)
    ng = next((r for r in res if r["key"] == "ng"), None)
    curve = []
    if cl:
        c = (f"WTI {cl['m1']}-{cl['m2']} {cl['spread_m1m2']:+.2f} · {cl['m1']}-{cl['m6']} {cl['spread_m1m6']:+.2f} ({cl['structure']}"
             + (f", {cl['spread_m1m6_chg']:+.2f} d/d" if cl.get("spread_m1m6_chg") is not None else "") + ")")
        curve.append(c)
    bw = D.brent_wti(res)   # 2026-10-19: stesso mese di consegna, non i due front month
    if bw:
        curve.append(f"Brent–WTI {bw[0]:+.2f} ({bw[1]} contracts)")
    if ng:
        curve.append(f"NatGas {ng['m1']}-{ng['m2']} {ng['spread_m1m2']:+.3f} ({ng['structure']})")
    if curve:
        lines.append("<b>Curve</b>")
        lines += [H.escape(x) for x in curve]
    if bias:   # 2026-10-19: conclusione finale — bias e trend
        lines += [""] + D.bias_telegram(bias[0], bias[1])
    lines += ["", "Flow: price vs open-interest change (new longs / new shorts / short covering / liquidation).",
              f'Curves and contract detail: <a href="{SITE}/futures-flow/">xenosfinance.com/futures-flow</a>']
    return "\n".join(lines)


def build_page(res, prev_snap, day, now, desk=None, oil=None, bias=None, it=None):
    """2026-10-25: pagina bilingue — HTML in inglese (SEO), italiano in data-it (tools/page_i18n.py)."""
    import page_i18n as PI
    L, it = PI.L, (it or {})
    # 2026-11-26: Bing — "wti crude oil forward curve contango backwardation" in pos. 4 con 0 clic:
    # titolo e descrizione dicono subito lo stato della curva WTI del giorno
    _cl = next((r for r in res if r.get("key") == "cl"), None)
    _st = _cl.get("structure") if _cl else None
    title = ("WTI Forward Curve: Contango or Backwardation? Oil, Gas, Gold Futures Flow | XenosFinance")
    title_it = "Curva forward WTI: contango o backwardation? Futures flow petrolio, gas, oro | XenosFinance"
    desc = ((f"WTI crude oil forward curve on {day:%d %B %Y}: {_st} (M1–M6 spread {_cl['spread_m1m6']:+.2f} {_cl['unit']}). "
             if _st else f"WTI crude oil forward curve on {day:%d %B %Y}. ") +
            "Open interest, volume and curves for WTI, Brent, natural gas, gold, silver, copper, S&P 500 and Nasdaq 100 futures.")
    mono_note = 'style="font-family:var(--mono);font-size:10px;color:var(--muted)"'
    b = ['<div class="crumb"><a href="/">Home</a> › Futures Flow</div>',
         f"<h1>{L('Futures Flow — Open Interest &amp; Curves', 'Futures Flow — Open interest e curve')}</h1>",
         '<div class="upd">' + L(f'Session {day:%A %d %B %Y} · Updated {now:%d %b %Y, %H:%M} UTC',
                                 f'Seduta di {PI.d_day_long(day)} · aggiornato {PI.d_short_time(now)} UTC') + '</div>',
         "<p>" + L(
             "What changed in the futures market in the last session. Price change is set against the change in "
             "total open interest across listed months: rising price with rising open interest means new longs; "
             "falling price with rising open interest, new shorts; rising price with falling open interest, short "
             "covering; falling price with falling open interest, long liquidation. Volume is compared with its "
             "20-day average.",
             "Cosa è cambiato sul mercato dei futures nell'ultima seduta. La variazione di prezzo viene confrontata "
             "con la variazione dell'open interest totale su tutte le scadenze quotate: prezzo in salita con open "
             "interest in aumento indica nuovi long; prezzo in discesa con open interest in aumento, nuovi short; "
             "prezzo in salita con open interest in calo, ricopertura degli short; prezzo in discesa con open "
             "interest in calo, liquidazione dei long. Il volume è confrontato con la sua media a 20 sedute.") + "</p>"]
    if desk:
        b += ["<h2>Desk read</h2>", f"<p>{L(esc(desk), esc(it['desk']) if it.get('desk') else '')}</p>",
              f'<p {mono_note}>' + L("Written from the figures in the tables below — no external data.",
                                      "Scritto dai dati delle tabelle qui sotto — nessun dato esterno.") + '</p>']
    if oil:
        b += [f"<h2>{L('Oil desk — WTI &amp; Brent', 'Desk petrolio — WTI e Brent')}</h2>",
              f"<p>{L(esc(oil), esc(it['oil']) if it.get('oil') else '')}</p>",
              f'<p {mono_note}>' + L("WTI and Brent are always covered here, whatever the theme of the week.",
                                      "WTI e Brent sono sempre trattati qui, qualunque sia il tema della settimana.") + '</p>']
    b += [f"<h2>{L('Overview', 'Panoramica')}</h2>",
          f"<table><tr><th>{L('Market', 'Mercato')}</th><th>{L('Most active', 'Più attivo')}</th>"
          f"<th>{L('Price d/d', 'Prezzo g/g')}</th><th>Open interest</th><th>{L('OI d/d', 'OI g/g')}</th>"
          f"<th>{L('Volume vs 20d', 'Volume vs 20g')}</th><th>{L('Flow', 'Flusso')}</th></tr>"]
    for r in res:
        cls = "up" if (r["price_chg"] or 0) > 0 else "dn" if (r["price_chg"] or 0) < 0 else ""
        pc = f"{r['price_chg']:+.2f}%" if r["price_chg"] is not None else "—"
        oc = kfmt(r["oi_chg"]) if r["oi_chg"] is not None else "—"
        vr = f"{r['vol_ratio']:.1f}x" if r["vol_ratio"] else "—"
        b.append(f"<tr><td>{PI.market(r['name'], esc)}</td><td>{esc(r['active'])} {fp(r['active_price'], r['dec'])}</td>"
                 f'<td class="{cls}">{pc}</td><td>{r["oi_total"]:,}</td><td>{oc}</td><td>{vr}</td>'
                 f'<td class="m">{L(esc(r["flow"]), esc(PI.FLOW_IT.get(r["flow"], "")))}</td></tr>')
    b.append("</table>")
    b.append(f"<h2>{L('Forward curves', 'Curve forward')}</h2>")
    b.append('<div class="grid">')
    for r in res:
        prev_rows = (prev_snap or {}).get(r["key"])
        # 2026-11-02: valori in giallo (prima tutto grigio, poco leggibile)
        Y = lambda v: f'<b style="color:#facc15;font-weight:500">{esc(v)}</b>'
        sp_txt = f"{r['spread_m1m6']:+.{r['dec']}f} {r['unit']}"
        extra = f"{esc(r['m1'])}–{esc(r['m6'])} " + Y(sp_txt) + f" · {esc(r['structure'])}"
        extra_it = extra
        if r.get("top_oi_move"):
            mv = f"{esc(r['top_oi_move'][1])} " + Y(kfmt(r['top_oi_move'][0]))
            extra += f" · largest OI change {mv}"
            extra_it += f" · maggiore variazione di OI {mv}"
        b.append(f'<div><p><b>{PI.market(r["name"], esc)}</b> <span style="font-family:var(--mono);font-size:11px;color:var(--muted)">'
                 f'{L(extra, extra_it)}</span></p>{curve_svg(r, prev_rows)}</div>')
    b.append("</div>")
    b.append('<p style="font-family:var(--mono);font-size:10px;color:var(--muted);margin-top:12px">' + L(
        "Curves: blue = latest settlement by contract month, dashed = previous session; bars = open interest by month. "
        "Open-interest history stored by XenosFinance.",
        "Curve: blu = ultimo settlement per scadenza, tratteggio = seduta precedente; barre = open interest per "
        "scadenza. Storico dell'open interest registrato da XenosFinance.") + '</p>')
    if bias:   # 2026-10-19: conclusione finale — bias e trend
        b += D.bias_html("flow", bias[0], bias[1], esc, it.get("bias"))
    b.append(f'<div class="box"><p><b>{L("Related", "Correlati")}</b></p><div class="cta">'
             f'<a href="/cot/">{L("COT positioning", "Posizionamento COT")}</a>'
             f'<a href="/analysis/">{L("Daily technical analysis", "Analisi tecnica giornaliera")}</a>'
             f'<a href="https://t.me/xenoswavefinance">{L("Telegram channel", "Canale Telegram")}</a></div></div>')
    jsonld = [{"@context": "https://schema.org", "@type": "Article", "headline": title, "description": desc,
               "dateModified": now.isoformat(), "author": {"@type": "Organization", "name": "XenosFinance"},
               "publisher": {"@type": "Organization", "name": "XenosFinance"}, "mainEntityOfPage": f"{SITE}/futures-flow/"}]
    return G.page_shell(title, desc, f"{SITE}/futures-flow/", "\n".join(b), jsonld,
                        "futures open interest, oil futures curve, WTI spread, contango backwardation, futures volume",
                        active="/futures-flow/", it_title=title_it)


def main():
    now = datetime.now(timezone.utc)
    today = now.date()
    # 2026-10-19: domenica e lunedì mattina non c'è una seduta nuova rispetto allo snapshot del sabato
    # (OI invariato → variazioni 0 e lettura falsata). Un avvio manuale in quei giorni non cambia niente.
    if today.weekday() in (6, 0) and os.environ.get("FORCE_FLOW") != "1":
        print("No new session since Saturday's snapshot (Sunday/Monday) — nothing to do.")
        return 0
    os.makedirs(OUT_DIR, exist_ok=True)
    hist = {}
    if os.path.exists(HIST):
        try:
            hist = json.load(open(HIST, encoding="utf-8"))
        except Exception:
            hist = {}
    snap, res = {}, []
    prev_day = max((d for d in hist if d < today.isoformat()), default=None)
    prev_snap = hist.get(prev_day) if prev_day else None
    for prod in PRODUCTS:
        print(f"→ {prod[3]}")
        rows = snapshot(prod, today)
        if not rows:
            print("  ! no contracts")
            continue
        vn, va, last = total_volume_stats(prod, rows)
        # 2026-11-17: FIX prezzi. Alle 05:30 UTC "regularMarketPrice" di Yahoo è già la quotazione
        # overnight della seduta nuova: il 17/11 la pagina "Session Monday 16 November" mostrava CLZ26
        # 84.98 (prezzo di martedì notte) invece della chiusura di lunedì 85.72, e gli spread mescolavano
        # mesi quotati overnight e mesi fermi all'ultima chiusura. Ora prezzo e volume di ogni contratto
        # sono quelli dell'ultima seduta conclusa (la stessa usata per la variazione %).
        for r in rows:
            if r["sym"] in last:
                r["price"], r["prev_close"], r["vol"] = last[r["sym"]]
        snap[prod[0]] = rows
        try:
            res.append(analyse(prod, rows, (prev_snap or {}).get(prod[0]), vn, va))
        except Exception as e:
            print(f"  ! skipped: {e}")
    if len(res) < 4:
        print("Too few products — aborting without changes.")
        return 1
    # 2026-11-17: Yahoo non aggiorna sempre l'open interest: lo snapshot di sabato 14/11 aveva l'OI
    # IDENTICO a quello di venerdì 13/11 per tutti i prodotti. In quel caso la variazione di OI di oggi
    # copre due sedute, mentre la variazione di prezzo ne copre una: va detto nel testo.
    oi_sessions = 1
    if prev_day:
        older = max((d for d in hist if d < prev_day), default=None)
        if older:
            same = sum(1 for k in (prev_snap or {})
                       if sum(r["oi"] for r in prev_snap[k]) == sum(r["oi"] for r in hist[older].get(k, [])))
            if prev_snap and same >= len(prev_snap) - 1:
                oi_sessions = 2
    for r in res:
        r["oi_sessions"] = oi_sessions
    # session = last US trading day (the run is in the European morning)
    sess = today - timedelta(days=1)
    while sess.weekday() >= 5:
        sess -= timedelta(days=1)
    hist[today.isoformat()] = snap
    for d in sorted(hist)[:-KEEP_DAYS]:
        hist.pop(d, None)
    json.dump(hist, open(HIST, "w", encoding="utf-8"), separators=(",", ":"))
    desk, desk_src = D.build("flow", res)
    oil, oil_src = D.build_oil("flow", res)
    b_rows, b_txt, b_src = D.build_bias("flow", res)
    bias = (b_rows, b_txt)
    # 2026-10-25: versione italiana dei testi variabili (gratis, numeri controllati)
    import page_i18n as PI
    t_desk, t_oil, t_bias = PI.translate_texts([desk, oil, b_txt])
    it = {"desk": t_desk, "oil": t_oil, "bias": t_bias}
    open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8").write(build_page(res, prev_snap, sess, now, desk, oil, bias, it))
    latest = {"session": sess.isoformat(), "generated": now.isoformat(), "has_oi_change": prev_snap is not None,
              "oi_sessions": oi_sessions,
              "desk_read": desk, "desk_read_source": desk_src, "oil_read": oil, "oil_read_source": oil_src,
              "bias_read": b_txt, "bias_read_source": b_src, "bias": b_rows,
              "telegram_html": telegram_html(res, sess, desk, oil, bias),
              "products": [{k: v for k, v in r.items() if k != "curve"} for r in res]}
    json.dump(latest, open(os.path.join(OUT_DIR, "latest.json"), "w", encoding="utf-8"), indent=1)
    G.update_sitemap([f"{SITE}/futures-flow/"], today.isoformat())
    print(f"Done: {len(res)} products, session {sess}, OI change {'yes' if prev_snap else 'from next run'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
