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

All numbers computed in code. No AI.
"""

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)
import gen_analysis_pages as G  # noqa: E402

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
    20 sedute. Il volume del continuo (SI=F, HG=F) salta ai roll: argento risultava 262x."""
    import yfinance as yf
    syms = [f"{r['sym']}.{prod[2]}" for r in rows]
    try:
        df = yf.download(syms, period="3mo", interval="1d", group_by="ticker", progress=False, threads=True)
        tot = None
        for sy in syms:
            try:
                v = df[sy]["Volume"].fillna(0) if len(syms) > 1 else df["Volume"].fillna(0)
            except Exception:
                continue
            tot = v if tot is None else tot.add(v, fill_value=0)
        if tot is None:
            return None, None
        tot = [float(x) for x in tot if x and x > 0]
        if len(tot) >= 21:
            return tot[-1], sum(tot[-21:-1]) / 20
    except Exception as e:
        print(f"  ! volume {prod[0]}: {e}")
    return None, None


def kfmt(v):
    a = abs(v)
    s = f"{a / 1000:.1f}k" if a >= 1000 else f"{a:.0f}"
    return ("+" if v > 0 else "-" if v < 0 else "") + s


def quadrant(pchg, oichg):
    if pchg is None or oichg is None or oichg == 0:
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
    active = max(rows, key=lambda r: r["vol"])
    oi_tot = sum(r["oi"] for r in rows)
    vol_tot = sum(r["vol"] for r in rows)
    prev_map = {r["sym"]: r for r in (prev_rows or [])}
    oi_prev = sum(prev_map[r["sym"]]["oi"] for r in rows if r["sym"] in prev_map) if prev_map else None
    oi_chg = (oi_tot - oi_prev) if oi_prev else None
    ref = active  # price change measured on the most active month (avoids expiry noise)
    pchg = (ref["price"] / ref["prev"] - 1) * 100 if ref.get("prev") else None
    by_oi_chg = []
    if prev_map:
        for r in rows:
            p = prev_map.get(r["sym"])
            if p:
                by_oi_chg.append((r["oi"] - p["oi"], r["sym"]))
    top_oi = max(by_oi_chg, key=lambda t: abs(t[0])) if by_oi_chg else None
    m1, m2 = rows[0], rows[1]
    m6 = rows[5] if len(rows) > 5 else rows[-1]
    sp12 = m1["price"] - m2["price"]
    sp16 = m1["price"] - m6["price"]
    res = {
        "key": key, "name": name, "unit": unit, "dec": dec,
        "front": front["sym"], "active": active["sym"], "active_price": active["price"], "price_chg": pchg,
        "oi_total": oi_tot, "oi_chg": oi_chg, "vol_total": vol_tot,
        "vol_today": vol_now, "vol_avg20": vol_avg,
        "vol_ratio": (vol_now / vol_avg) if vol_now and vol_avg else None,
        "flow": quadrant(pchg, oi_chg), "top_oi_move": top_oi,
        "m1": m1["sym"], "m2": m2["sym"], "m6": m6["sym"],
        "spread_m1m2": sp12, "spread_m1m6": sp16,
        # gas naturale: curva stagionale (inverno > primavera) → struttura letta su M1–M2
        "structure": ("backwardation" if (sp12 if key == "ng" else sp16) > 0 else "contango"),
        "curve": [[r["sym"], r["price"], r["oi"], r["vol"]] for r in rows],
    }
    if prev_map and m1["sym"] in prev_map and m6["sym"] in prev_map:
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
                   f'fill="#243a5e"/>' for i, p in enumerate(pts))
    today = " ".join(f"{x(i):.1f},{y(p[1]):.1f}" for i, p in enumerate(pts))
    prev = " ".join(f"{x(i):.1f},{y(prev_map[p[0]]):.1f}" for i, p in enumerate(pts) if p[0] in prev_map)
    labels = "".join(f'<text x="{x(i):.1f}" y="{h}" fill="#5a7a9a" font-size="7" text-anchor="middle" '
                     f'font-family="IBM Plex Mono">{p[0][2:]}</text>' for i, p in enumerate(pts) if i % 2 == 0)
    return (f'<svg viewBox="0 0 {w} {h + 4}" width="100%" height="{h + 4}" role="img" aria-label="futures curve">{bars}'
            + (f'<polyline points="{prev}" fill="none" stroke="#5a7a9a" stroke-dasharray="3 3" stroke-width="1.2"/>' if prev else "")
            + f'<polyline points="{today}" fill="none" stroke="#3b82f6" stroke-width="1.8"/>{labels}</svg>')


def fp(v, dec):
    return f"{v:,.{dec}f}"


def telegram_html(res, day):
    import html as H
    lines = ["<b>XENOS WAVE · FUTURES FLOW</b>", f"<b>Session {day:%a %d %b} · open interest &amp; curve</b>", ""]
    tab = []
    for r in res:
        pc = f"{r['price_chg']:+.1f}%" if r["price_chg"] is not None else "  n/a"
        oc = kfmt(r["oi_chg"]) if r["oi_chg"] is not None else "n/a"
        vr = f"{r['vol_ratio']:.1f}x" if r["vol_ratio"] else " n/a"
        tab.append(f"{r['name'][:13]:<13} {pc:>6}  OI {oc:>7}  vol {vr:>4}")
    lines.append("<pre>" + H.escape("\n".join(tab)) + "</pre>")
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
    if cl and bz:
        curve.append(f"Brent–WTI {bz['curve'][0][1] - cl['curve'][0][1]:+.2f} (front months)")
    if ng:
        curve.append(f"NatGas {ng['m1']}-{ng['m2']} {ng['spread_m1m2']:+.3f} ({ng['structure']})")
    if curve:
        lines.append("<b>Curve</b>")
        lines += [H.escape(x) for x in curve]
    lines += ["", "Flow: price vs open-interest change (new longs / new shorts / short covering / liquidation).",
              f'Curves and contract detail: <a href="{SITE}/futures-flow">xenosfinance.com/futures-flow</a>']
    return "\n".join(lines)


def build_page(res, prev_snap, day, now):
    title = "Futures Flow — Open Interest, Volume & Curves: Oil, Gas, Gold, Indices | XenosFinance"
    desc = (f"Daily futures flow for {day:%d %B %Y}: open interest and volume changes, positioning read and "
            "forward curves for WTI, Brent, natural gas, gold, silver, copper, S&P 500 and Nasdaq 100 futures.")
    b = ['<div class="crumb"><a href="/">Home</a> › Futures Flow</div>',
         "<h1>Futures Flow — Open Interest &amp; Curves</h1>",
         f'<div class="upd">Session {day:%A %d %B %Y} · Updated {now:%d %b %Y, %H:%M} UTC</div>',
         "<p>What changed in the futures market in the last session. Price change is set against the change in "
         "total open interest across listed months: rising price with rising open interest means new longs; "
         "falling price with rising open interest, new shorts; rising price with falling open interest, short "
         "covering; falling price with falling open interest, long liquidation. Volume is compared with its "
         "20-day average.</p>",
         "<h2>Overview</h2>",
         "<table><tr><th>Market</th><th>Most active</th><th>Price d/d</th><th>Open interest</th><th>OI d/d</th>"
         "<th>Volume vs 20d</th><th>Flow</th></tr>"]
    for r in res:
        cls = "up" if (r["price_chg"] or 0) > 0 else "dn" if (r["price_chg"] or 0) < 0 else ""
        pc = f"{r['price_chg']:+.2f}%" if r["price_chg"] is not None else "—"
        oc = kfmt(r["oi_chg"]) if r["oi_chg"] is not None else "—"
        vr = f"{r['vol_ratio']:.1f}x" if r["vol_ratio"] else "—"
        b.append(f"<tr><td>{esc(r['name'])}</td><td>{esc(r['active'])} {fp(r['active_price'], r['dec'])}</td>"
                 f'<td class="{cls}">{pc}</td><td>{r["oi_total"]:,}</td><td>{oc}</td><td>{vr}</td>'
                 f'<td class="m">{esc(r["flow"])}</td></tr>')
    b.append("</table>")
    b.append("<h2>Forward curves</h2>")
    b.append('<div class="grid">')
    for r in res:
        prev_rows = (prev_snap or {}).get(r["key"])
        extra = f"{r['m1']}–{r['m6']} {r['spread_m1m6']:+.{r['dec']}f} {r['unit']} · {r['structure']}"
        if r.get("top_oi_move"):
            extra += f" · largest OI change {r['top_oi_move'][1]} {kfmt(r['top_oi_move'][0])}"
        b.append(f'<div><p><b>{esc(r["name"])}</b> <span style="font-family:var(--mono);font-size:11px;color:var(--muted)">'
                 f'{esc(extra)}</span></p>{curve_svg(r, prev_rows)}</div>')
    b.append("</div>")
    b.append('<p style="font-family:var(--mono);font-size:10px;color:var(--muted);margin-top:12px">Curves: blue = '
             'latest settlement by contract month, dashed = previous session; bars = open interest by month. '
             'Source: exchange futures quotes via Yahoo Finance; open-interest history stored by XenosFinance.</p>')
    b.append('<div class="box"><p><b>Related</b></p><div class="cta"><a href="/cot">COT positioning</a>'
             '<a href="/analysis">Daily technical analysis</a><a href="https://t.me/xenoswavefinance">Telegram channel</a></div></div>')
    jsonld = [{"@context": "https://schema.org", "@type": "Article", "headline": title, "description": desc,
               "dateModified": now.isoformat(), "author": {"@type": "Organization", "name": "XenosFinance"},
               "publisher": {"@type": "Organization", "name": "XenosFinance"}, "mainEntityOfPage": f"{SITE}/futures-flow"}]
    return G.page_shell(title, desc, f"{SITE}/futures-flow", "\n".join(b), jsonld,
                        "futures open interest, oil futures curve, WTI spread, contango backwardation, futures volume",
                        active="/futures-flow")


def main():
    now = datetime.now(timezone.utc)
    today = now.date()
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
        snap[prod[0]] = rows
        vn, va = total_volume_stats(prod, rows)
        try:
            res.append(analyse(prod, rows, (prev_snap or {}).get(prod[0]), vn, va))
        except Exception as e:
            print(f"  ! skipped: {e}")
    if len(res) < 4:
        print("Too few products — aborting without changes.")
        return 1
    # session = last US trading day (the run is in the European morning)
    sess = today - timedelta(days=1)
    while sess.weekday() >= 5:
        sess -= timedelta(days=1)
    hist[today.isoformat()] = snap
    for d in sorted(hist)[:-KEEP_DAYS]:
        hist.pop(d, None)
    json.dump(hist, open(HIST, "w", encoding="utf-8"), separators=(",", ":"))
    open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8").write(build_page(res, prev_snap, sess, now))
    latest = {"session": sess.isoformat(), "generated": now.isoformat(), "has_oi_change": prev_snap is not None,
              "telegram_html": telegram_html(res, sess),
              "products": [{k: v for k, v in r.items() if k != "curve"} for r in res]}
    json.dump(latest, open(os.path.join(OUT_DIR, "latest.json"), "w", encoding="utf-8"), indent=1)
    G.update_sitemap([f"{SITE}/futures-flow"], today.isoformat())
    print(f"Done: {len(res)} products, session {sess}, OI change {'yes' if prev_snap else 'from next run'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
