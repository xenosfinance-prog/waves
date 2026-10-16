#!/usr/bin/env python3
"""
gen_cot.py — XenosFinance weekly COT positioning (2026-10-14)

Source: CFTC Commitments of Traders, public Socrata API (free, official).
  - Disaggregated (futures only, 72hh-3qpy): managed money — energy & metals
  - Traders in Financial Futures (futures only, gpe5-46if): leveraged funds +
    asset managers — equity indices, FX, Treasuries

Output:
  cot/index.html   → https://xenosfinance.com/cot   (static, indexable page)
  cot/latest.json  → read by the Telegram bot for the Monday channel post
  sitemap.xml      → /cot entry refreshed

All numbers are computed here from CFTC data and prices (Yahoo).
2026-10-16: "Desk read" summary (tools/desk_read.py): Claude rewrites ONLY the computed
figures, every number is checked against them; otherwise a rule-based summary is used.
Run by .github/workflows/cot-report.yml (Saturday, Monday fallback).
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, ROOT)
import gen_analysis_pages as G  # noqa: E402  page shell, CSS, sitemap (same look as /analysis)
import desk_read as D  # noqa: E402  Desk read (sintesi)

SITE = "https://xenosfinance.com"
OUT_DIR = os.path.join(ROOT, "cot")
API = "https://publicreporting.cftc.gov/resource/{ds}.json"
DS_DISAGG, DS_TFF = "72hh-3qpy", "gpe5-46if"
LOOKBACK_WEEKS = 156   # COT Index = position of the net within its 3-year range
CHART_WEEKS = 52

# key, CFTC code, dataset, display name, group, price ticker (Yahoo), primary trader group
MARKETS = [
    ("wti",    "067651", DS_DISAGG, "WTI Crude Oil", "Energy",     "CL=F", "mm"),
    ("natgas", "023651", DS_DISAGG, "Natural Gas",   "Energy",     "NG=F", "mm"),
    ("gold",   "088691", DS_DISAGG, "Gold",          "Metals",     "GC=F", "mm"),
    ("silver", "084691", DS_DISAGG, "Silver",        "Metals",     "SI=F", "mm"),
    ("copper", "085692", DS_DISAGG, "Copper",        "Metals",     "HG=F", "mm"),
    ("spx",    "13874A", DS_TFF,    "S&P 500",       "Indices",    "ES=F", "lev"),
    ("ndx",    "209742", DS_TFF,    "Nasdaq 100",    "Indices",    "NQ=F", "lev"),
    ("eur",    "099741", DS_TFF,    "Euro",          "Currencies", "6E=F", "lev"),
    ("jpy",    "097741", DS_TFF,    "Japanese Yen",  "Currencies", "6J=F", "lev"),
    ("gbp",    "096742", DS_TFF,    "British Pound", "Currencies", "6B=F", "lev"),
    ("ust10",  "043602", DS_TFF,    "US 10Y T-Note", "Rates",      "ZN=F", "lev"),
]
GROUP_LABEL = {"mm": "Managed money", "lev": "Leveraged funds"}
FIELDS = {
    "mm":   ("m_money_positions_long_all", "m_money_positions_short_all"),
    "lev":  ("lev_money_positions_long", "lev_money_positions_short"),
    "am":   ("asset_mgr_positions_long", "asset_mgr_positions_short"),
    "pm":   ("prod_merc_positions_long", "prod_merc_positions_short"),
    "swap": ("swap_positions_long_all", "swap__positions_short_all"),
}


def esc(t):
    return G.esc(t)


def _num(row, k):
    try:
        return float(row.get(k))
    except (TypeError, ValueError):
        return None


def fetch(code, ds):
    params = {"$where": f"cftc_contract_market_code='{code}'",
              "$order": "report_date_as_yyyy_mm_dd DESC", "$limit": LOOKBACK_WEEKS + 10}
    r = requests.get(API.format(ds=ds), params=params, timeout=40,
                     headers={"User-Agent": "XenosFinance COT (xenosfinance.com)"})
    r.raise_for_status()
    rows = r.json()
    out = []
    for x in rows:
        d = str(x.get("report_date_as_yyyy_mm_dd", ""))[:10]
        if d:
            out.append((d, x))
    out.sort(key=lambda t: t[0])
    # dedup by date (keep last)
    dd = {}
    for d, x in out:
        dd[d] = x
    return sorted(dd.items())


def net_series(rows, grp):
    lk, sk = FIELDS[grp]
    s = []
    for d, x in rows:
        lo, sh = _num(x, lk), _num(x, sk)
        if lo is not None and sh is not None:
            s.append((d, lo - sh, lo, sh, _num(x, "open_interest_all")))
    return s


def prices(tickers):
    import yfinance as yf
    out = {}
    for t in tickers:
        try:
            h = yf.Ticker(t).history(period="2y", interval="1d", auto_adjust=False)
            if h.empty:
                continue
            idx = [i.strftime("%Y-%m-%d") for i in h.index]
            out[t] = list(zip(idx, [float(v) for v in h["Close"]]))
        except Exception as e:
            print(f"  ! price {t}: {e}")
    return out


def px_on(series, day):
    """Close on or before `day` (report Tuesday)."""
    best = None
    for d, v in series or []:
        if d <= day:
            best = v
        else:
            break
    return best


def kfmt(v):
    a = abs(v)
    s = f"{a / 1e6:.2f}M" if a >= 1e6 else f"{a / 1000:.1f}k" if a >= 1000 else f"{a:.0f}"
    return ("+" if v > 0 else "-" if v < 0 else "") + s


def label_for(idx):
    if idx >= 90:
        return "Crowded long"
    if idx <= 10:
        return "Crowded short"
    if idx >= 80:
        return "Extended long"
    if idx <= 20:
        return "Extended short"
    return ""


def analyse(m, rows, px):
    key, code, ds, name, group, ticker, grp = m
    s = net_series(rows, grp)
    if len(s) < 30:
        raise ValueError(f"only {len(s)} weeks of data")
    hist = s[-LOOKBACK_WEEKS:]
    nets = [x[1] for x in hist]
    lo, hi = min(nets), max(nets)
    d, net, lng, sht, oi = s[-1]
    prev = s[-2][1]
    net4 = s[-5][1] if len(s) >= 5 else prev
    idx = (net - lo) / (hi - lo) * 100 if hi > lo else 50.0
    rng = hi - lo if hi > lo else 1.0
    p_now, p_prev = px_on(px.get(ticker), d), px_on(px.get(ticker), s[-2][0])
    p_chg = (p_now / p_prev - 1) * 100 if p_now and p_prev else None
    chg = net - prev
    div = ""
    if p_chg is not None and abs(chg) >= 0.05 * rng:
        if p_chg >= 1.0 and chg < 0:
            div = "Price up, funds cutting net length"
        elif p_chg <= -1.0 and chg > 0:
            div = "Price down, funds adding net length"
    res = {
        "key": key, "name": name, "group": group, "trader": GROUP_LABEL[grp], "date": d,
        "net": net, "long": lng, "short": sht, "oi": oi, "chg": chg, "chg4": net - net4,
        "net_pct_oi": (net / oi * 100) if oi else None, "cot_index": round(idx, 0), "flag": label_for(idx),
        "range_lo": lo, "range_hi": hi, "price": p_now, "price_chg": p_chg, "divergence": div,
        "chart": [[x[0], x[1], px_on(px.get(ticker), x[0])] for x in s[-CHART_WEEKS:]],
    }
    last = rows[-1][1]
    if ds == DS_TFF:
        lk, sk = FIELDS["am"]
        a1, a2 = _num(last, lk), _num(last, sk)
        if a1 is not None and a2 is not None:
            res["am_net"] = a1 - a2
    if key == "wti":  # oil detail: who is on the other side
        for g in ("pm", "swap"):
            lk, sk = FIELDS[g]
            a1, a2 = _num(last, lk), _num(last, sk)
            if a1 is not None and a2 is not None:
                res[f"{g}_net"] = a1 - a2
        if sht:
            res["mm_ls_ratio"] = lng / sht
    return res


def svg_chart(points, w=300, h=80):
    """Net position bars (green/red) + price line (blue) for the last 52 weeks."""
    nets = [p[1] for p in points]
    pxs = [p[2] for p in points if p[2]]
    if not nets:
        return ""
    n = len(nets)
    m = max(abs(v) for v in nets) or 1
    bw = w / n
    zero = h / 2
    bars = []
    for i, v in enumerate(nets):
        bh = abs(v) / m * (h / 2 - 2)
        y = zero - bh if v >= 0 else zero
        bars.append(f'<rect x="{i * bw:.1f}" y="{y:.1f}" width="{max(bw - 1, 1):.1f}" height="{bh:.1f}" '
                    f'fill="{"#34d399" if v >= 0 else "#f87171"}" opacity="0.55"/>')
    line = ""
    if len(pxs) >= 2:
        plo, phi = min(pxs), max(pxs)
        sp = (phi - plo) or 1
        pts = [f"{i * bw + bw / 2:.1f},{h - 4 - (p[2] - plo) / sp * (h - 8):.1f}"
               for i, p in enumerate(points) if p[2]]
        line = f'<polyline points="{" ".join(pts)}" fill="none" stroke="#3b82f6" stroke-width="1.6"/>'
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" preserveAspectRatio="none" role="img" '
            f'aria-label="52-week net positioning and price"><line x1="0" y1="{zero}" x2="{w}" y2="{zero}" '
            f'stroke="#243a5e"/>{"".join(bars)}{line}</svg>')


def telegram_html(res, report_date, release_date, desk=None):
    import html as H
    rows = []
    for grp_title, groups in (("COMMODITIES · managed money net", ("Energy", "Metals")),
                              ("FINANCIALS · leveraged funds net", ("Indices", "Currencies", "Rates"))):
        part = [r for r in res if r["group"] in groups]
        if not part:
            continue
        rows.append(grp_title)
        for r in part:
            arrow = "▲" if r["chg"] > 0 else "▼" if r["chg"] < 0 else "="
            rows.append(f"{r['name'][:13]:<13} {kfmt(r['net']):>8}  {arrow}{kfmt(r['chg']).lstrip('+-'):>6}  idx {int(r['cot_index']):>3}")
        rows.append("")
    ext = [r for r in res if r["flag"].startswith("Crowded")]
    divs = [r for r in res if r["divergence"]]
    lines = ["<b>XENOS WAVE · COT POSITIONING</b>",
             f"<b>Week to Tue {datetime.strptime(report_date, '%Y-%m-%d'):%d %b} · CFTC</b>", "",
             "<pre>" + H.escape("\n".join(rows).rstrip()) + "</pre>"]
    if desk:
        lines += ["<b>Desk read</b>", H.escape(desk), ""]
    if ext:
        lines.append("<b>Extremes</b> (3-year range)")
        lines += [f"• {H.escape(r['name'])}: {r['flag'].lower()} — COT index {int(r['cot_index'])}" for r in ext]
    if divs:
        lines.append("<b>Divergences</b>")
        lines += [f"• {H.escape(r['name'])}: {r['divergence'].lower()} ({r['price_chg']:+.1f}% w/w)" for r in divs]
    wti = next((r for r in res if r["key"] == "wti"), None)
    if wti and "pm_net" in wti:
        lines.append(f"<b>WTI detail</b>: producers {kfmt(wti['pm_net'])} · swap dealers {kfmt(wti.get('swap_net', 0))}"
                     + (f" · fund long/short {wti['mm_ls_ratio']:.2f}" if wti.get("mm_ls_ratio") else ""))
    lines += ["", "COT index: 0 = most short, 100 = most long of the last 3 years.",
              f'Full table and charts: <a href="{SITE}/cot">xenosfinance.com/cot</a>']
    return "\n".join(lines)


def build_page(res, report_date, release_date, now, desk=None):
    title = "COT Report — Futures Positioning: Oil, Gold, Indices, FX | XenosFinance"
    desc = (f"Weekly Commitments of Traders analysis (week to {report_date}): managed money and leveraged fund "
            "positioning in WTI, natural gas, gold, silver, copper, S&P 500, Nasdaq 100, euro, yen, pound and "
            "Treasuries, with 3-year COT index and extremes.")
    b = ['<div class="crumb"><a href="/">Home</a> › COT Positioning</div>',
         "<h1>COT Report — Futures Positioning</h1>",
         f'<div class="upd">Week to Tuesday {datetime.strptime(report_date, "%Y-%m-%d"):%d %B %Y} · '
         f'CFTC release {release_date} · Updated {now:%d %b %Y, %H:%M} UTC</div>',
         "<p>Positioning of speculative traders in the main futures markets, from the CFTC Commitments of Traders "
         "report. Commodities show <b>managed money</b> (hedge funds, CTAs); financial futures show <b>leveraged "
         "funds</b>. The COT index places this week's net position within its 3-year range: 0 is the most "
         "short, 100 the most long. Readings above 90 or below 10 mark crowded positioning, where the risk of a "
         "squeeze or a reversal rises.</p>"]
    if desk:
        b.append("<h2>Desk read</h2>")
        b.append(f"<p>{esc(desk)}</p>")
        b.append('<p style="font-family:var(--mono);font-size:10px;color:var(--muted)">Written from the figures in the tables below — no external data.</p>')
    ext = [r for r in res if r["flag"]]
    if ext:
        b.append('<div class="box"><p><b>Key reads this week</b></p>' + "".join(
            f"<p>{esc(r['name'])}: {esc(r['flag'].lower())} (COT index {int(r['cot_index'])})"
            + (f" — {esc(r['divergence'].lower())}" if r["divergence"] else "") + ".</p>" for r in ext) + "</div>")
    for groups, title_h, who in ((("Energy", "Metals"), "Commodities — managed money", "Managed money"),
                                 (("Indices", "Currencies", "Rates"), "Financial futures — leveraged funds", "Leveraged funds")):
        part = [r for r in res if r["group"] in groups]
        if not part:
            continue
        b.append(f"<h2>{esc(title_h)}</h2>")
        b.append("<table><tr><th>Market</th><th>Net</th><th>1 week</th><th>4 weeks</th><th>% of OI</th>"
                 "<th>COT index</th><th>Price w/w</th><th></th></tr>")
        for r in part:
            cls = "up" if r["chg"] > 0 else "dn" if r["chg"] < 0 else ""
            poi = "" if r["net_pct_oi"] is None else f"{r['net_pct_oi']:+.1f}%"
            pch = "" if r["price_chg"] is None else f"{r['price_chg']:+.1f}%"
            b.append(f"<tr><td>{esc(r['name'])}</td><td>{kfmt(r['net'])}</td>"
                     f'<td class="{cls}">{kfmt(r["chg"])}</td><td>{kfmt(r["chg4"])}</td>'
                     f"<td>{poi}</td><td><b>{int(r['cot_index'])}</b></td><td>{pch}</td>"
                     f'<td class="m">{esc(r["flag"])}</td></tr>')
        b.append("</table>")
        b.append('<div class="grid">')
        for r in part:
            extra = ""
            if "am_net" in r:
                extra = f" · asset managers {kfmt(r['am_net'])}"
            if r["key"] == "wti" and "pm_net" in r:
                extra = (f" · producers {kfmt(r['pm_net'])} · swap dealers {kfmt(r.get('swap_net', 0))}"
                         + (f" · fund L/S {r['mm_ls_ratio']:.2f}" if r.get("mm_ls_ratio") else ""))
            b.append(f'<div><p><b>{esc(r["name"])}</b> <span class="m" style="font-family:var(--mono);font-size:11px;'
                     f'color:var(--muted)">{esc(who)} {kfmt(r["net"])}{esc(extra)}</span></p>{svg_chart(r["chart"])}</div>')
        b.append("</div>")
    b.append('<p style="font-family:var(--mono);font-size:10px;color:var(--muted);margin-top:12px">Charts: bars = '
             'net position (52 weeks), blue line = futures price. Source: CFTC Commitments of Traders, futures only.</p>')
    b.append('<div class="box"><p><b>How to read it</b></p><p>Positioning is a context tool, not a timing signal: '
             'crowded trades can stay crowded for weeks. It becomes useful when an extreme meets a technical '
             'turning point — for example a completed Elliott Wave count at a support or resistance zone.</p>'
             '<div class="cta"><a href="/analysis">Daily technical analysis</a><a href="/elliottwave">Elliott Wave</a>'
             '<a href="https://t.me/xenoswavefinance">Telegram channel</a></div></div>')
    jsonld = [{"@context": "https://schema.org", "@type": "Article", "headline": title, "description": desc,
               "dateModified": now.isoformat(), "author": {"@type": "Organization", "name": "XenosFinance"},
               "publisher": {"@type": "Organization", "name": "XenosFinance"}, "mainEntityOfPage": f"{SITE}/cot"}]
    return G.page_shell(title, desc, f"{SITE}/cot", "\n".join(b), jsonld,
                        "COT report, commitments of traders, managed money, hedge fund positioning, oil positioning, "
                        "gold positioning, CFTC", active="/cot")


def main():
    now = datetime.now(timezone.utc)
    px = prices(sorted({m[5] for m in MARKETS}))
    res = []
    for m in MARKETS:
        print(f"→ {m[3]} ({m[1]})")
        try:
            rows = fetch(m[1], m[2])
            res.append(analyse(m, rows, px))
        except Exception as e:
            print(f"  ! skipped: {e}")
    if len(res) < 5:
        print("Too few markets — aborting without changes.")
        return 1
    report_date = max(r["date"] for r in res)
    res = [r for r in res if r["date"] == report_date] or res
    rel = datetime.strptime(report_date, "%Y-%m-%d") + timedelta(days=3)
    release_date = f"{rel:%d %b %Y}"
    desk, desk_src = D.build("cot", res)
    os.makedirs(OUT_DIR, exist_ok=True)
    open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8").write(build_page(res, report_date, release_date, now, desk))
    latest = {"report_date": report_date, "release_date": release_date, "generated": now.isoformat(),
              "desk_read": desk, "desk_read_source": desk_src,
              "telegram_html": telegram_html(res, report_date, release_date, desk),
              "markets": [{k: v for k, v in r.items() if k != "chart"} for r in res]}
    json.dump(latest, open(os.path.join(OUT_DIR, "latest.json"), "w", encoding="utf-8"), indent=1)
    G.update_sitemap([f"{SITE}/cot"], now.strftime("%Y-%m-%d"))
    print(f"Done: {len(res)} markets, week to {report_date}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
