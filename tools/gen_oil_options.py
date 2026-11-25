#!/usr/bin/env python3
"""
gen_oil_options.py — XenosFinance daily Oil Options Monitor (2026-11-18)

What the options market says about crude oil, from free and legitimate data only:
  • OVX  — CBOE Crude Oil Volatility Index (implied volatility of oil options), Yahoo ^OVX
  • WTI  — front-month futures CL=F (Yahoo), for realised volatility and the WTI-equivalent levels
  • USO  — United States Oil Fund option chain (Yahoo): open interest, volume and implied
           volatility by strike. CME crude options (LO) are not used: CME forbids automated
           access, and QuikStrike has no API.

Every number shown is computed in code from those downloads. Nothing is estimated or filled in:
if a figure cannot be computed (missing quote, IV not valid), it is left out.

Day-over-day open-interest changes come from our own snapshots (oil-options/history.json),
so the first run has no OI change.

Output:
  oil-options/index.html   → https://xenosfinance.com/oil-options/
  oil-options/latest.json  → read by the Telegram bot (private preview → channel)
  oil-options/history.json → per-day OI snapshots by expiry and strike (rolling 30 days)
  sitemap.xml              → /oil-options/ entry
"""

import json
import math
import os
import sys
from datetime import date, datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)
import gen_analysis_pages as G  # noqa: E402

SITE = "https://xenosfinance.com"
OUT_DIR = os.path.join(ROOT, "oil-options")
HIST = os.path.join(OUT_DIR, "history.json")
KEEP_DAYS = 30
MAX_DTE = 75           # scadenze considerate per open interest e muri
MAX_EXPS = 6
IV_MIN, IV_MAX = 0.05, 3.0   # IV Yahoo fuori da questo intervallo = quotazione non valida


# ── download ────────────────────────────────────────────────────────────────
def daily_closes(ticker, period="1y"):
    """Chiusure giornaliere di sole sedute concluse. Il run è dopo la chiusura USA (≥ 21:20 UTC):
    la barra di oggi è completa e si usa; prima di quell'ora si escludono le barre di oggi."""
    import yfinance as yf
    df = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=False)
    if df is None or df.empty:
        return []
    now = datetime.now(timezone.utc)
    after_close = (now.hour, now.minute) >= (21, 20)
    today = now.date()
    out = [(i.date(), float(c)) for i, c in zip(df.index, df["Close"])
           if c == c and (i.date() < today or (after_close and i.date() == today))]
    return out


def chain_snapshot(today):
    """Catena opzioni USO per le scadenze entro MAX_DTE giorni."""
    import yfinance as yf
    tk = yf.Ticker("USO")
    exps = []
    for e in (tk.options or []):
        try:
            d = date.fromisoformat(e)
        except ValueError:
            continue
        dte = (d - today).days
        if 1 <= dte <= MAX_DTE:
            exps.append((e, dte))
    exps = exps[:MAX_EXPS]
    out = {}
    for e, dte in exps:
        try:
            oc = tk.option_chain(e)
        except Exception as ex:
            print(f"  ! chain {e}: {ex}")
            continue
        rows = {"dte": dte, "c": [], "p": []}
        for side, df in (("c", oc.calls), ("p", oc.puts)):
            for _, r in df.iterrows():
                k = float(r["strike"])
                oi = r.get("openInterest")
                vol = r.get("volume")
                iv = r.get("impliedVolatility")
                bid = r.get("bid")
                rows[side].append({
                    "k": k,
                    "oi": int(oi) if oi == oi and oi is not None else 0,
                    "vol": int(vol) if vol == vol and vol is not None else 0,
                    "iv": float(iv) if iv == iv and iv is not None else None,
                    "bid": float(bid) if bid == bid and bid is not None else 0.0,
                })
        out[e] = rows
    return out


# ── calcoli ─────────────────────────────────────────────────────────────────
def realised_vol(closes, n=20):
    px = [c for _, c in closes]
    if len(px) < n + 1:
        return None
    rets = [math.log(px[i] / px[i - 1]) for i in range(len(px) - n, len(px)) if px[i - 1] > 0]
    if len(rets) < n:
        return None
    m = sum(rets) / len(rets)
    var = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252) * 100


def percentile_rank(values, x):
    if not values:
        return None
    return 100.0 * sum(1 for v in values if v <= x) / len(values)


def iv_at(rows, target):
    """IV interpolata linearmente sullo strike target, solo quotazioni valide (bid>0, IV plausibile)."""
    pts = sorted((r["k"], r["iv"]) for r in rows
                 if r["iv"] is not None and IV_MIN <= r["iv"] <= IV_MAX and r["bid"] > 0)
    if len(pts) < 2:
        return None
    for (k1, v1), (k2, v2) in zip(pts, pts[1:]):
        if k1 <= target <= k2 and k2 > k1:
            return (v1 + (v2 - v1) * (target - k1) / (k2 - k1)) * 100
    return None          # target fuori dagli strike quotati: niente estrapolazione


def by_strike(chain):
    agg = {}
    for e, rows in chain.items():
        for side in ("c", "p"):
            for r in rows[side]:
                a = agg.setdefault(r["k"], {"c_oi": 0, "p_oi": 0, "c_vol": 0, "p_vol": 0})
                a[f"{side}_oi"] += r["oi"]
                a[f"{side}_vol"] += r["vol"]
    return agg


def max_pain(rows):
    strikes = sorted({r["k"] for r in rows["c"]} | {r["k"] for r in rows["p"]})
    if not strikes:
        return None
    best, best_v = None, None
    for s in strikes:
        v = sum(r["oi"] * max(0.0, s - r["k"]) for r in rows["c"]) + \
            sum(r["oi"] * max(0.0, r["k"] - s) for r in rows["p"])
        if best_v is None or v < best_v:
            best, best_v = s, v
    return best


def compact(chain):
    """Snapshot per lo storico: {exp: {"c": {strike: oi}, "p": {...}}}"""
    return {e: {side: {f"{r['k']:g}": r["oi"] for r in rows[side] if r["oi"] > 0} for side in ("c", "p")}
            for e, rows in chain.items()}


def oi_changes(chain, prev):
    """Variazione di OI per strike (somma sulle scadenze presenti in entrambi gli snapshot)."""
    if not prev:
        return None
    ch = {}
    for e, rows in chain.items():
        pe = prev.get(e)
        if not pe:
            continue
        for side in ("c", "p"):
            old = pe.get(side, {})
            for r in rows[side]:
                d = r["oi"] - int(old.get(f"{r['k']:g}", 0))
                if d:
                    ch.setdefault((side, r["k"]), 0)
                    ch[(side, r["k"])] += d
    return ch


def analyse(today):
    ovx = daily_closes("^OVX")
    wti = daily_closes("CL=F")
    uso = daily_closes("USO", period="3mo")
    if len(ovx) < 30 or len(wti) < 30 or len(uso) < 5:
        raise RuntimeError(f"price history missing (OVX {len(ovx)}, WTI {len(wti)}, USO {len(uso)})")
    chain = chain_snapshot(today)
    if not chain:
        raise RuntimeError("USO option chain unavailable")

    # 2026-11-25: la seduta è quella della catena USO, non l'ultima barra OVX. Alle 21:30 UTC Yahoo
    # non ha ancora la barra OVX del giorno (indice CBOE pubblicato più tardi): il run del 24/11 era
    # etichettato "Monday 23" pur con la catena del 24. USO (titolo) ha la barra del giorno già al run.
    sess = max(uso[-1][0], ovx[-1][0])
    o_last, o_prev = ovx[-1][1], ovx[-2][1]
    o_1y = [c for _, c in ovx[-252:]]
    res = {"session": sess.isoformat(), "ovx_date": ovx[-1][0].isoformat(),
           "ovx": round(o_last, 2), "ovx_chg": round(o_last - o_prev, 2),
           "ovx_chg5": round(o_last - ovx[-6][1], 2) if len(ovx) >= 6 else None,
           "ovx_pct": round(percentile_rank(o_1y, o_last), 0),
           "ovx_hi": round(max(o_1y), 2), "ovx_lo": round(min(o_1y), 2)}
    rv = realised_vol(wti, 20)
    res["wti"] = round(wti[-1][1], 2)
    res["wti_date"] = wti[-1][0].isoformat()
    res["rv20"] = round(rv, 1) if rv is not None else None
    res["vrp"] = round(o_last - rv, 1) if rv is not None else None
    res["uso"] = round(uso[-1][1], 2)
    # rapporto WTI/USO dello stesso giorno: serve a tradurre gli strike USO in livelli WTI (≈)
    uso_d = dict(uso)
    k_day = next((d for d, _ in reversed(wti) if d in uso_d), None)
    res["ratio"] = round(dict(wti)[k_day] / uso_d[k_day], 4) if k_day else None
    res["ratio_date"] = k_day.isoformat() if k_day else None
    spot = res["uso"]

    # skew e ATM sulla scadenza più vicina a 30 giorni (almeno 7)
    cand = [(abs(r["dte"] - 30), e) for e, r in chain.items() if r["dte"] >= 7]
    if cand:
        e30 = min(cand)[1]
        r30 = chain[e30]
        atm_c, atm_p = iv_at(r30["c"], spot), iv_at(r30["p"], spot)
        put10, call10 = iv_at(r30["p"], spot * 0.90), iv_at(r30["c"], spot * 1.10)
        res["skew_exp"], res["skew_dte"] = e30, r30["dte"]
        res["atm_iv"] = round((atm_c + atm_p) / 2, 1) if atm_c is not None and atm_p is not None else None
        res["put10_iv"] = round(put10, 1) if put10 is not None else None
        res["call10_iv"] = round(call10, 1) if call10 is not None else None
        res["skew"] = round(put10 - call10, 1) if put10 is not None and call10 is not None else None

    agg = by_strike(chain)
    res["call_oi"] = sum(a["c_oi"] for a in agg.values())
    res["put_oi"] = sum(a["p_oi"] for a in agg.values())
    res["call_vol"] = sum(a["c_vol"] for a in agg.values())
    res["put_vol"] = sum(a["p_vol"] for a in agg.values())
    res["pc_oi"] = round(res["put_oi"] / res["call_oi"], 2) if res["call_oi"] else None
    res["pc_vol"] = round(res["put_vol"] / res["call_vol"], 2) if res["call_vol"] else None
    near = {k: a for k, a in agg.items() if 0.75 * spot <= k <= 1.25 * spot}
    above = {k: a for k, a in near.items() if k >= spot}
    below = {k: a for k, a in near.items() if k <= spot}
    if above:
        k = max(above, key=lambda x: above[x]["c_oi"])
        res["call_wall"], res["call_wall_oi"] = k, above[k]["c_oi"]
    if below:
        k = max(below, key=lambda x: below[x]["p_oi"])
        res["put_wall"], res["put_wall_oi"] = k, below[k]["p_oi"]
    big_e = max(chain, key=lambda e: sum(r["oi"] for s in ("c", "p") for r in chain[e][s]))
    res["mp_exp"] = big_e
    res["max_pain"] = max_pain(chain[big_e])
    res["exps"] = [{"exp": e, "dte": r["dte"], "c_oi": sum(x["oi"] for x in r["c"]),
                    "p_oi": sum(x["oi"] for x in r["p"])} for e, r in chain.items()]
    res["strikes"] = [{"k": k, **near[k]} for k in sorted(near)]

    # 2026-11-18: controllo di qualità. Fuori dall'orario USA Yahoo pubblica la catena con open
    # interest a zero e bid a zero (run delle 07:27 UTC: OI totale 170, IV non valide). Con dati
    # così non si pubblica niente: meglio nessun aggiornamento che numeri falsi.
    n_oi = sum(1 for a in agg.values() if a["c_oi"] > 0 or a["p_oi"] > 0)
    if res["call_oi"] + res["put_oi"] < 20000 or n_oi < 10:
        raise RuntimeError(f"option chain incomplete: total OI {res['call_oi'] + res['put_oi']}, "
                           f"{n_oi} strikes with OI — Yahoo has not published open interest")
    if res.get("atm_iv") is None and res.get("skew") is None:
        raise RuntimeError("no valid implied volatility in the chain (quotes without bid)")
    # attività anomala di oggi: volume ≥ 1.000 e ≥ 2× l'open interest dello strike
    unusual = []
    for e, rows in chain.items():
        for side in ("c", "p"):
            for r in rows[side]:
                if r["vol"] >= 1000 and r["vol"] >= 2 * max(r["oi"], 1):
                    unusual.append({"exp": e, "side": side, "k": r["k"], "vol": r["vol"], "oi": r["oi"]})
    res["unusual"] = sorted(unusual, key=lambda x: -x["vol"])[:5]
    return res, chain


def to_wti(res, k):
    return round(k * res["ratio"], 2) if res.get("ratio") and k is not None else None


# ── testo (solo dai numeri calcolati) ───────────────────────────────────────
def _ord(x):
    n = int(round(x))
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def desk_read(res):
    """Ritorna (righe EN, righe IT, bottom line EN, bottom line IT)."""
    en, it = [], []
    o, p = res["ovx"], res["ovx_pct"]
    lvl_en = "elevated" if p >= 75 else "low" if p <= 25 else "middle of its range"
    lvl_it = "elevata" if p >= 75 else "bassa" if p <= 25 else "a metà del range"
    en.append(f"Crude implied volatility (OVX) at {o:.2f}, {res['ovx_chg']:+.2f} on the day, "
              f"{_ord(p)} percentile of the past year — {lvl_en}.")
    it.append(f"Volatilità implicita del petrolio (OVX) a {o:.2f}, {res['ovx_chg']:+.2f} nella seduta, "
              f"{p:.0f}° percentile dell'ultimo anno — {lvl_it}.")
    if res.get("vrp") is not None:
        v, rv = res["vrp"], res["rv20"]
        if v >= 5:
            en.append(f"Options price more movement than oil has delivered: OVX {v:+.1f} pts over 20-day realised "
                      f"volatility ({rv:.1f}%) — event risk is being paid for.")
            it.append(f"Le opzioni prezzano più movimento di quello che il petrolio ha fatto: OVX {v:+.1f} punti "
                      f"sopra la volatilità realizzata a 20 giorni ({rv:.1f}%) — il mercato paga il rischio evento.")
        elif v <= -3:
            en.append(f"Options are cheap against actual movement: OVX {v:+.1f} pts vs 20-day realised "
                      f"volatility ({rv:.1f}%) — protection is underpriced.")
            it.append(f"Le opzioni costano poco rispetto al movimento reale: OVX {v:+.1f} punti rispetto alla "
                      f"volatilità realizzata a 20 giorni ({rv:.1f}%) — la protezione è sottoprezzata.")
        else:
            en.append(f"Implied and realised volatility are aligned (OVX {v:+.1f} pts vs 20-day realised {rv:.1f}%).")
            it.append(f"Volatilità implicita e realizzata allineate (OVX {v:+.1f} punti vs realizzata a 20 giorni {rv:.1f}%).")
    if res.get("skew") is not None:
        s, pi, ci = res["skew"], res["put10_iv"], res["call10_iv"]
        if s >= 3:
            en.append(f"Skew to the downside: 10% OTM puts at {pi:.1f}% IV vs calls at {ci:.1f}% ({s:+.1f} pts) — "
                      "more demand for protection against a drop.")
            it.append(f"Skew al ribasso: put 10% OTM a {pi:.1f}% di IV contro call a {ci:.1f}% ({s:+.1f} punti) — "
                      "più domanda di protezione contro un calo.")
        elif s <= -3:
            en.append(f"Skew to the upside: 10% OTM calls at {ci:.1f}% IV vs puts at {pi:.1f}% ({-s:.1f} pts richer) — "
                      "the market is paying for a supply-driven spike.")
            it.append(f"Skew al rialzo: call 10% OTM a {ci:.1f}% di IV contro put a {pi:.1f}% (più care di {-s:.1f} punti) — "
                      "il mercato paga per coprirsi da uno spike di offerta.")
        elif s <= -1.5:
            en.append(f"Calls richer than puts: 10% OTM calls at {ci:.1f}% IV vs puts at {pi:.1f}% ({-s:.1f} pts) — "
                      "more is paid for upside protection than for downside.")
            it.append(f"Call più care delle put: call 10% OTM a {ci:.1f}% di IV contro put a {pi:.1f}% ({-s:.1f} punti) — "
                      "si paga di più la protezione dal rialzo che dal ribasso.")
        elif s >= 1.5:
            en.append(f"Puts richer than calls: 10% OTM puts at {pi:.1f}% IV vs calls at {ci:.1f}% ({s:.1f} pts) — "
                      "more is paid for downside protection.")
            it.append(f"Put più care delle call: put 10% OTM a {pi:.1f}% di IV contro call a {ci:.1f}% ({s:.1f} punti) — "
                      "si paga di più la protezione dal ribasso.")
        else:
            en.append(f"Balanced skew: 10% OTM puts {pi:.1f}% vs calls {ci:.1f}% IV ({s:+.1f} pts).")
            it.append(f"Skew equilibrato: put 10% OTM {pi:.1f}% contro call {ci:.1f}% di IV ({s:+.1f} punti).")
    if res.get("call_wall") and res.get("put_wall"):
        cw, pw = res["call_wall"], res["put_wall"]
        cww, pww = to_wti(res, cw), to_wti(res, pw)
        wt_en = f" (≈ WTI {pww:.1f}–{cww:.1f})" if cww and pww else ""
        en.append(f"Largest put open interest at USO {pw:g}, largest call open interest at USO {cw:g}{wt_en}: "
                  "the range where options positioning is concentrated.")
        it.append(f"Massimo open interest sulle put a USO {pw:g}, sulle call a USO {cw:g}{wt_en}: "
                  "il range in cui è concentrato il posizionamento in opzioni.")
    if res.get("pc_oi") is not None:
        pc = res["pc_oi"]
        en.append(f"Put/call ratio {pc:.2f} on open interest"
                  + (f", {res['pc_vol']:.2f} on volume." if res.get("pc_vol") is not None else "."))
        it.append(f"Rapporto put/call {pc:.2f} sull'open interest"
                  + (f", {res['pc_vol']:.2f} sui volumi." if res.get("pc_vol") is not None else "."))
    # sintesi
    skew, vrp = res.get("skew"), res.get("vrp")
    sk = skew if skew is not None else 0
    un = res.get("unusual") or []
    calls_un = [u for u in un if u["side"] == "c"]
    puts_un = [u for u in un if u["side"] == "p"]
    if vrp is not None and vrp <= -3 and sk <= -1.5:
        bl = ("Volatility is cheap but calls are bid: the market underprices movement while paying for upside protection"
              + (" — unusual call buying confirms it." if calls_un and len(calls_un) >= len(puts_un) else "."),
              "Volatilità a buon mercato ma call richieste: il mercato sottoprezza il movimento mentre paga la protezione dal rialzo"
              + (" — gli acquisti anomali di call lo confermano." if calls_un and len(calls_un) >= len(puts_un) else "."))
    elif vrp is not None and vrp <= -3 and sk >= 1.5:
        bl = ("Volatility is cheap but puts are bid: movement is underpriced while downside protection is in demand"
              + (" — unusual put buying confirms it." if puts_un and len(puts_un) > len(calls_un) else "."),
              "Volatilità a buon mercato ma put richieste: il movimento è sottoprezzato mentre si cerca protezione dal ribasso"
              + (" — gli acquisti anomali di put lo confermano." if puts_un and len(puts_un) > len(calls_un) else "."))
    elif sk <= -3 and (vrp or 0) >= 3:
        bl = ("Options are positioned for upside risk in crude: calls bid and implied volatility above realised.",
              "Le opzioni sono posizionate per un rischio al rialzo sul petrolio: call richieste e volatilità implicita sopra la realizzata.")
    elif sk >= 3 and (vrp or 0) >= 3:
        bl = ("Options are positioned for downside risk in crude: puts bid and implied volatility above realised.",
              "Le opzioni sono posizionate per un rischio al ribasso sul petrolio: put richieste e volatilità implicita sopra la realizzata.")
    elif vrp is not None and vrp <= -3:
        bl = ("Complacent options market: volatility is cheap relative to how oil is actually moving.",
              "Mercato delle opzioni compiacente: la volatilità costa poco rispetto a come si muove davvero il petrolio.")
    else:
        bl = ("No strong directional signal from the options market.",
              "Nessun segnale direzionale forte dal mercato delle opzioni.")
    return en, it, bl[0], bl[1]


def changes_list(res, ch):
    if ch is None:
        return None
    top = sorted(((abs(v), side, k, v) for (side, k), v in ch.items() if abs(v) >= 500), reverse=True)[:6]
    return [{"side": side, "k": k, "chg": v, "wti": to_wti(res, k)} for _, side, k, v in top]


# ── output ──────────────────────────────────────────────────────────────────
def fk(v):
    return f"{v:,}".replace(",", ",")


def oi_svg(res, w=760, h=230):
    rows = res["strikes"]
    if len(rows) < 3:
        return ""
    mx = max(max(r["c_oi"], r["p_oi"]) for r in rows) or 1
    pad, mid = 40, h / 2
    bw = (w - 2 * pad) / len(rows)
    k0, k1 = rows[0]["k"], rows[-1]["k"]
    x = lambda k: pad + (k - k0) / ((k1 - k0) or 1) * (w - 2 * pad - bw) + bw / 2
    out = [f'<svg viewBox="0 0 {w} {h + 22}" width="100%" role="img" aria-label="USO options open interest by strike" '
           f'style="background:var(--bg2,#131f2e);border:1px solid var(--border,#1e3050)">']
    for r in rows:
        cx = x(r["k"])
        hc = r["c_oi"] / mx * (mid - 14)
        hp = r["p_oi"] / mx * (mid - 14)
        out.append(f'<rect x="{cx - bw * 0.4:.1f}" y="{mid - hc:.1f}" width="{bw * 0.8:.1f}" height="{hc:.1f}" fill="#10b981" opacity=".85"/>')
        out.append(f'<rect x="{cx - bw * 0.4:.1f}" y="{mid:.1f}" width="{bw * 0.8:.1f}" height="{hp:.1f}" fill="#ef4444" opacity=".85"/>')
    out.append(f'<line x1="{pad}" x2="{w - pad}" y1="{mid}" y2="{mid}" stroke="#7f9ab5" stroke-width=".6"/>')
    sx = x(min(max(res["uso"], k0), k1))
    out.append(f'<line x1="{sx:.1f}" x2="{sx:.1f}" y1="6" y2="{h - 6}" stroke="#facc15" stroke-dasharray="4 3"/>')
    out.append(f'<text x="{sx + 4:.1f}" y="16" fill="#facc15" font-size="10" font-family="monospace">USO {res["uso"]:g}</text>')
    step = max(1, len(rows) // 10)
    for r in rows[::step]:
        out.append(f'<text x="{x(r["k"]):.1f}" y="{h + 14}" fill="#7f9ab5" font-size="9" font-family="monospace" '
                   f'text-anchor="middle">{r["k"]:g}</text>')
    out.append(f'<text x="{pad}" y="14" fill="#10b981" font-size="10" font-family="monospace">calls</text>')
    out.append(f'<text x="{pad}" y="{h - 4}" fill="#ef4444" font-size="10" font-family="monospace">puts</text>')
    out.append("</svg>")
    return "".join(out)


def _dmy(iso):
    try:
        return datetime.strptime(str(iso)[:10], "%Y-%m-%d").strftime("%d %b").lstrip("0")
    except Exception:
        return str(iso)


def telegram_html(res, day, en, bl, chg):
    """2026-11-19: post riscritto — prezzo WTI in testa, una sezione per tema, niente doppioni,
    strike sempre tradotti in WTI. Il bot inserisce la vista Elliott (riga "Elliott Wave")
    prima del Bottom line e la collega allo strike anomalo se coincide con l'invalidazione."""
    import html as H
    e = H.escape
    L = ["<b>XENOS WAVE · OIL OPTIONS MONITOR</b>",
         f"<b>Close {day:%a %d %b} · what options price for crude</b>", ""]
    head = f"<b>WTI {res['wti']:.2f}</b>" if res.get("wti") else ""
    head += (" · " if head else "") + f"OVX {res['ovx']:.1f} ({res['ovx_chg']:+.2f}, {_ord(res['ovx_pct'])} pct 1y)"
    L += [head, ""]
    if res.get("vrp") is not None:
        v, rv = res["vrp"], res["rv20"]
        if v <= -3:
            t = f"OVX {res['ovx']:.1f} vs 20-day realised {rv:.1f}% → options cheap by {-v:.1f} pts. Protection is underpriced."
        elif v >= 5:
            t = f"OVX {res['ovx']:.1f} vs 20-day realised {rv:.1f}% → options rich by {v:.1f} pts. Event risk is being paid for."
        else:
            t = f"OVX {res['ovx']:.1f} vs 20-day realised {rv:.1f}% → implied and realised aligned ({v:+.1f} pts)."
        L.append(f"<b>Volatility:</b> {e(t)}")
    if res.get("skew") is not None:
        sk, pi, ci = res["skew"], res["put10_iv"], res["call10_iv"]
        if sk <= -1.5:
            t = (f"calls richer than puts ({ci:.1f}% vs {pi:.1f}% IV, 10% OTM). "
                 "The market pays more for upside protection than for downside.")
        elif sk >= 1.5:
            t = (f"puts richer than calls ({pi:.1f}% vs {ci:.1f}% IV, 10% OTM). "
                 "The market pays more for downside protection.")
        else:
            t = f"balanced (puts {pi:.1f}% vs calls {ci:.1f}% IV, 10% OTM)."
        L += ["", f"<b>Skew:</b> {e(t)}"]
    un = res.get("unusual") or []
    if un:
        u = un[0]
        uw = to_wti(res, u["k"])
        mult = u["vol"] / max(u["oi"], 1)
        side = "calls" if u["side"] == "c" else "puts"
        t = (f"{u['vol']:,} USO {u['k']:g} {side}" + (f" (≈ WTI {uw:.1f})" if uw else "")
             + f" expiring {_dmy(u['exp'])} traded against {u['oi']:,} open"
             + (f", {mult:.0f}× the open interest." if mult >= 3 else "."))
        same = [x for x in un if x["side"] == u["side"]]
        if len(un) >= 3 and len(same) == len(un):
            ks = [to_wti(res, x["k"]) for x in un]
            if all(ks):
                t += f" All {len(un)} unusual strikes are {side}, WTI ≈{min(ks):.1f}–{max(ks):.1f}."
        L += ["", f"<b>The signal:</b> {e(t)}"]
    pos = []
    if res.get("put_wall") and res.get("call_wall"):
        pw, cw = to_wti(res, res["put_wall"]), to_wti(res, res["call_wall"])
        if pw and cw:
            pos.append(f"open interest concentrated between WTI ≈{pw:.0f} (puts) and ≈{cw:.0f} (calls).")
    if res.get("pc_oi") is not None:
        pos.append(f"Put/call {res['pc_oi']:.2f} OI" + (f" · {res['pc_vol']:.2f} volume." if res.get("pc_vol") is not None else "."))
    if pos:
        L += ["", "<b>Positioning:</b> " + e(" ".join(pos))]
    if chg:
        bits = []
        for c in chg[:3]:
            bits.append(f"{'calls' if c['side'] == 'c' else 'puts'} {c['k']:g} {c['chg']:+,}"
                        + (f" (≈ WTI {c['wti']:.1f})" if c.get("wti") else ""))
        L += ["", "<b>Biggest OI changes:</b> " + e("; ".join(bits)) + "."]
    L += ["", f"<b>Bottom line:</b> {e(bl)}", "",
          "<i>Data: CBOE OVX, NYMEX WTI front month, USO options.</i>",
          # 2026-11-20: ?d=<sessione> → URL nuovo ogni giorno, così Telegram non riusa l'anteprima
          # in cache del giorno prima (titolo/descrizione con la data vecchia)
          f'Charts: <a href="{SITE}/oil-options/?d={res["session"]}">xenosfinance.com/oil-options</a>']
    return "\n".join(L)


def build_page(res, day, now, en, it, bl, bl_it, chg):
    import page_i18n as PI
    Lg = PI.L
    esc = G.esc
    title = "Oil Options Monitor — Crude Implied Volatility, Skew & Open Interest | XenosFinance"
    title_it = "Oil Options Monitor — Volatilità implicita, skew e open interest sul petrolio | XenosFinance"
    desc = (f"What the options market prices for crude oil on {day:%d %B %Y}: OVX implied volatility vs realised, "
            "put/call skew, open-interest walls and unusual activity in USO options, with WTI-equivalent levels.")
    note = 'style="font-family:var(--mono);font-size:10px;color:var(--muted)"'
    # 2026-11-25: se Yahoo non ha ancora la barra OVX della seduta, lo dichiariamo
    ovx_note_en = ovx_note_it = ""
    if res.get("ovx_date") and res["ovx_date"] != res["session"]:
        od = date.fromisoformat(res["ovx_date"])
        ovx_note_en = f" · OVX: {od:%d %b} close (latest published)"
        ovx_note_it = f" · OVX: chiusura {od.day} {PI.MONTHS_IT_SHORT[od.month - 1]} (ultima pubblicata)"
    b = ['<div class="crumb"><a href="/">Home</a> › Oil Options</div>',
         f"<h1>{Lg('Oil Options Monitor', 'Oil Options Monitor — opzioni sul petrolio')}</h1>",
         '<div class="upd">' + Lg(f'Session {day:%A %d %B %Y} · Updated {now:%d %b %Y, %H:%M} UTC' + ovx_note_en,
                                  f'Seduta di {PI.d_day_long(day)} · aggiornato {PI.d_short_time(now)} UTC' + ovx_note_it) + '</div>',
         "<p>" + Lg(
             "What the options market is pricing for crude oil: how much movement it expects (implied volatility), "
             "whether it fears a drop or a spike more (skew), and where positions are concentrated (open interest "
             "by strike). Implied volatility comes from the CBOE OVX index; positioning from the USO option chain, "
             "translated into WTI-equivalent levels.",
             "Cosa prezza il mercato delle opzioni sul petrolio: quanto movimento si aspetta (volatilità implicita), "
             "se teme di più un calo o uno spike (skew) e dove sono concentrate le posizioni (open interest per "
             "strike). La volatilità implicita viene dall'indice CBOE OVX; il posizionamento dalla catena opzioni "
             "di USO, tradotto in livelli equivalenti WTI.") + "</p>",
         "<h2>Desk read</h2>"]
    for e_, i_ in zip(en, it):
        b.append(f"<p>{Lg(esc(e_), esc(i_))}</p>")
    b.append(f"<p><b>Bottom line:</b> {Lg(esc(bl), esc(bl_it))}</p>")
    b.append(f'<p {note}>' + Lg("Written by rules from the figures on this page — no external data, no estimates.",
                                "Scritto con regole fisse dai dati di questa pagina — nessun dato esterno, nessuna stima.") + "</p>")

    b += [f"<h2>{Lg('Volatility', 'Volatilità')}</h2>", "<table>",
          f"<tr><th>{Lg('Measure', 'Misura')}</th><th>{Lg('Value', 'Valore')}</th><th>{Lg('Note', 'Nota')}</th></tr>",
          f"<tr><td>OVX</td><td>{res['ovx']:.2f}</td><td>{res['ovx_chg']:+.2f} d/d"
          + (f" · {res['ovx_chg5']:+.2f} 5d" if res.get("ovx_chg5") is not None else "")
          + f" · {Lg('1-year range', 'range 1 anno')} {res['ovx_lo']:.2f}–{res['ovx_hi']:.2f}</td></tr>",
          f"<tr><td>{Lg('OVX percentile (1y)', 'Percentile OVX (1 anno)')}</td><td>{res['ovx_pct']:.0f}</td><td></td></tr>"]
    if res.get("rv20") is not None:
        b.append(f"<tr><td>{Lg('WTI realised vol, 20 days', 'Volatilità realizzata WTI, 20 giorni')}</td>"
                 f"<td>{res['rv20']:.1f}%</td><td>WTI {res['wti']:.2f} ({esc(res['wti_date'])})</td></tr>")
        b.append(f"<tr><td>{Lg('Implied premium (OVX − realised)', 'Premio implicito (OVX − realizzata)')}</td>"
                 f"<td>{res['vrp']:+.1f}</td><td></td></tr>")
    if res.get("atm_iv") is not None or res.get("skew") is not None:
        b.append(f"<tr><td>{Lg('USO ATM implied vol', 'Vol implicita ATM USO')} ({esc(res.get('skew_exp', ''))}, {res.get('skew_dte', '')}d)</td>"
                 f"<td>{res['atm_iv']:.1f}%</td><td></td></tr>" if res.get("atm_iv") is not None else "")
    if res.get("skew") is not None:
        b.append(f"<tr><td>{Lg('Skew: 10% OTM put − call IV', 'Skew: IV put − call 10% OTM')}</td><td>{res['skew']:+.1f}</td>"
                 f"<td>put {res['put10_iv']:.1f}% · call {res['call10_iv']:.1f}%</td></tr>")
    b.append("</table>")

    b += [f"<h2>{Lg('Open interest by strike (USO)', 'Open interest per strike (USO)')}</h2>", oi_svg(res),
          f'<p {note}>' + Lg(f"Sum of the expiries within {MAX_DTE} days. Green = call open interest, red = put open interest, "
                             "yellow line = last USO close.",
                             f"Somma delle scadenze entro {MAX_DTE} giorni. Verde = open interest call, rosso = open interest "
                             "put, linea gialla = ultima chiusura USO.") + "</p>",
          "<table>",
          f"<tr><th>{Lg('Level', 'Livello')}</th><th>USO</th><th>{Lg('≈ WTI', '≈ WTI')}</th><th>Open interest</th></tr>"]
    if res.get("call_wall"):
        b.append(f"<tr><td>{Lg('Call wall (max call OI above price)', 'Muro call (max OI call sopra il prezzo)')}</td>"
                 f"<td>{res['call_wall']:g}</td><td>{to_wti(res, res['call_wall']) or '—'}</td><td>{res['call_wall_oi']:,}</td></tr>")
    if res.get("put_wall"):
        b.append(f"<tr><td>{Lg('Put wall (max put OI below price)', 'Muro put (max OI put sotto il prezzo)')}</td>"
                 f"<td>{res['put_wall']:g}</td><td>{to_wti(res, res['put_wall']) or '—'}</td><td>{res['put_wall_oi']:,}</td></tr>")
    if res.get("max_pain") is not None:
        b.append(f"<tr><td>{Lg('Max pain', 'Max pain')} ({esc(res['mp_exp'])})</td><td>{res['max_pain']:g}</td>"
                 f"<td>{to_wti(res, res['max_pain']) or '—'}</td><td></td></tr>")
    b.append(f"<tr><td>{Lg('Put/call ratio', 'Rapporto put/call')}</td><td colspan=\"3\">OI {res['pc_oi']} · "
             f"{Lg('volume', 'volumi')} {res['pc_vol']} · calls {res['call_oi']:,} / puts {res['put_oi']:,}</td></tr>"
             if res.get("pc_oi") is not None else "")
    b.append("</table>")

    b += [f"<h2>{Lg('Open-interest changes', 'Variazioni di open interest')}</h2>"]
    if chg is None:
        b.append("<p>" + Lg("Day-over-day changes start from the next session (first snapshot stored today).",
                            "Le variazioni giorno su giorno partono dalla prossima seduta (primo snapshot salvato oggi).") + "</p>")
    elif not chg:
        b.append("<p>" + Lg("No strike changed by 500 contracts or more.",
                            "Nessuno strike è cambiato di 500 contratti o più.") + "</p>")
    else:
        b.append(f"<table><tr><th>{Lg('Type', 'Tipo')}</th><th>Strike USO</th><th>≈ WTI</th><th>{Lg('OI change', 'Variazione OI')}</th></tr>")
        for c in chg:
            b.append(f"<tr><td>{'Call' if c['side'] == 'c' else 'Put'}</td><td>{c['k']:g}</td><td>{c['wti'] or '—'}</td>"
                     f"<td class=\"{'up' if c['chg'] > 0 else 'dn'}\">{c['chg']:+,}</td></tr>")
        b.append("</table>")
    if res.get("unusual"):
        b += [f"<h2>{Lg('Unusual volume', 'Volumi anomali')}</h2>",
              f"<table><tr><th>{Lg('Type', 'Tipo')}</th><th>{Lg('Expiry', 'Scadenza')}</th><th>Strike</th>"
              f"<th>{Lg('Volume', 'Volume')}</th><th>Open interest</th></tr>"]
        for u in res["unusual"]:
            b.append(f"<tr><td>{'Call' if u['side'] == 'c' else 'Put'}</td><td>{esc(u['exp'])}</td><td>{u['k']:g}</td>"
                     f"<td>{u['vol']:,}</td><td>{u['oi']:,}</td></tr>")
        b.append("</table>")
        b.append(f'<p {note}>' + Lg("Volume of at least 1,000 contracts and at least twice the open interest of the strike.",
                                    "Volume di almeno 1.000 contratti e almeno il doppio dell'open interest dello strike.") + "</p>")

    b += [f"<h2>{Lg('How to read it', 'Come leggerlo')}</h2>",
          "<p>" + Lg("OVX is the 30-day implied volatility of oil options: the higher it is, the bigger the move the market "
                     "is paying to protect against. Compared with realised volatility it shows whether options are expensive "
                     "(event risk priced) or cheap. Skew compares out-of-the-money puts and calls: puts richer means fear of a "
                     "drop, calls richer means fear of a supply spike. Open-interest walls are strikes where many contracts "
                     "are open — levels that often act as magnets or barriers, above all close to expiry.",
                     "L'OVX è la volatilità implicita a 30 giorni delle opzioni sul petrolio: più è alto, più è ampio il "
                     "movimento da cui il mercato paga per proteggersi. Confrontato con la volatilità realizzata dice se le "
                     "opzioni sono care (rischio evento prezzato) o economiche. Lo skew confronta put e call fuori dal "
                     "denaro: put più care significa timore di un calo, call più care timore di uno spike di offerta. I muri "
                     "di open interest sono strike con molti contratti aperti — livelli che spesso fanno da magnete o da "
                     "barriera, soprattutto vicino alla scadenza.") + "</p>",
          f'<p {note}>' + Lg(
              f"Sources: CBOE OVX and NYMEX WTI front month (CL=F) daily closes, USO option chain — via Yahoo Finance. "
              f"WTI-equivalent levels = USO strike × WTI/USO close ratio of {res.get('ratio_date') or '—'} "
              f"({res.get('ratio') or '—'}); approximate because USO holds a mix of contract months. "
              "Not investment advice.",
              f"Fonti: chiusure giornaliere CBOE OVX e WTI front month NYMEX (CL=F), catena opzioni USO — tramite Yahoo "
              f"Finance. Livelli equivalenti WTI = strike USO × rapporto WTI/USO del {res.get('ratio_date') or '—'} "
              f"({res.get('ratio') or '—'}); approssimati perché USO detiene un mix di scadenze. Non è consulenza "
              "finanziaria.") + "</p>",
          f'<div class="box"><p><b>{Lg("Related", "Correlati")}</b></p><div class="cta">'
          f'<a href="/futures-flow/">Futures Flow</a><a href="/cot/">{Lg("COT positioning", "Posizionamento COT")}</a>'
          f'<a href="https://t.me/xenoswavefinance">{Lg("Telegram channel", "Canale Telegram")}</a></div></div>']
    jsonld = [{"@context": "https://schema.org", "@type": "Article", "headline": title, "description": desc,
               "dateModified": now.isoformat(),
               "author": {"@type": "Person", "@id": f"{SITE}/about#founder", "name": "Manolis Evlogimenos", "url": f"{SITE}/about"},
               "publisher": {"@type": "Organization", "name": "XenosFinance"}, "mainEntityOfPage": f"{SITE}/oil-options/"}]
    return G.page_shell(title, desc, f"{SITE}/oil-options/", "\n".join(x for x in b if x), jsonld,
                        "crude oil options, OVX, oil implied volatility, oil skew, USO options open interest, WTI options",
                        active="/oil-options/", it_title=title_it)


def main():
    now = datetime.now(timezone.utc)
    today = now.date()
    if today.weekday() >= 5 and os.environ.get("FORCE_OILOPT") != "1":
        print("Weekend — no US options session.")
        return 0
    os.makedirs(OUT_DIR, exist_ok=True)
    hist = {}
    if os.path.exists(HIST):
        try:
            hist = json.load(open(HIST, encoding="utf-8"))
        except Exception:
            hist = {}
    res, chain = analyse(today)
    day = date.fromisoformat(res["session"])
    prev_day = max((d for d in hist if d < res["session"]), default=None)
    ch = oi_changes(chain, hist.get(prev_day) if prev_day else None)
    chg = changes_list(res, ch)
    hist[res["session"]] = compact(chain)
    for d in sorted(hist)[:-KEEP_DAYS]:
        hist.pop(d, None)
    json.dump(hist, open(HIST, "w", encoding="utf-8"), separators=(",", ":"))
    en, it, bl, bl_it = desk_read(res)
    open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8").write(
        build_page(res, day, now, en, it, bl, bl_it, chg))
    latest = {"session": res["session"], "generated": now.isoformat(), "has_oi_change": chg is not None,
              "prev_session": prev_day, "desk_read": en, "bottom_line": bl,
              "telegram_html": telegram_html(res, day, en, bl, chg), "data": res, "oi_changes": chg}
    json.dump(latest, open(os.path.join(OUT_DIR, "latest.json"), "w", encoding="utf-8"), indent=1, default=str)
    G.update_sitemap([f"{SITE}/oil-options/"], today.isoformat())
    print(f"Done: session {res['session']}, OVX {res['ovx']}, {len(chain)} expiries, "
          f"OI change {'yes' if chg is not None else 'from next run'}")
    print(json.dumps({k: v for k, v in res.items() if k not in ('strikes', 'exps')}, default=str)[:1500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
