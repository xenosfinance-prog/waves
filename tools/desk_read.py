#!/usr/bin/env python3
"""
desk_read.py — sintesi "Desk read" per le pagine COT e Futures Flow (2026-10-16)

Due livelli, entrambi SOLO sui numeri già calcolati dai generatori:
  1. rule_*  → sintesi deterministica scritta in codice (sempre disponibile)
  2. ai_read → Claude riformula gli stessi fatti in prosa da desk

Garanzia "niente numeri inventati": ogni numero presente nel testo dell'AI deve
comparire, identico, nella lista dei fatti passata al modello. Se anche un solo
numero non torna (o l'AI non risponde) si pubblica la sintesi deterministica.
"""

import json
import os
import re

MODEL = "claude-sonnet-4-6"

# numeri di contesto ammessi anche se non presenti nei fatti (es. "3-year range", "20-day average")
_CONTEXT_NUMS = {"0", "1", "2", "3", "4", "5", "6", "10", "20", "52", "90", "100"}
_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _norm(tok):
    return tok.replace(",", "")


def numbers_in(text):
    return {_norm(m.group(0)) for m in _NUM_RE.finditer(text)}


def numbers_ok(text, facts):
    allowed = numbers_in("\n".join(facts)) | _CONTEXT_NUMS
    bad = sorted(n for n in numbers_in(text) if n not in allowed)
    return not bad, bad


def ai_read(kind, facts, n_sentences="4-6"):
    """kind: 'cot' | 'flow'. Ritorna (testo, None) oppure (None, motivo)."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return None, "no ANTHROPIC_API_KEY"
    what = ("the weekly CFTC Commitments of Traders positioning of speculative traders (managed money for "
            "commodities, leveraged funds for financial futures)" if kind == "cot" else
            "yesterday's futures session: price change against the change in total open interest, volume against "
            "its 20-day average, and the shape of the forward curves")
    prompt = f"""You are the head of a futures desk writing the short "Desk read" that opens a XenosFinance page about {what}.
Readers are traders and students: they see the tables below your text, so do not repeat every row — tell them what the numbers mean together.

FACTS (the only source you may use):
{json.dumps(facts, ensure_ascii=False, indent=0)}

Write {n_sentences} sentences in English, one paragraph, plain text (no markdown, no bullet points, no headings).
Cover: the dominant theme, where positioning or flow is strongest, where it is crowded or fragile, and any divergence between price and positioning.

STRICT RULES:
- Every number you write must appear EXACTLY as written in the FACTS (same digits, same decimals). If a number is not in the FACTS, do not write it. Prefer fewer numbers.
- Do not compute new numbers (no sums, differences, averages or percentages of your own).
- No news, no fundamentals, no forecasts of price targets, never tell the reader to buy or sell.
- Positioning is context, not a timing signal: say "risk of a squeeze" or "fragile", never "will rise/fall"."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(model=MODEL, max_tokens=700, messages=[{"role": "user", "content": prompt}])
        txt = " ".join(msg.content[0].text.split()).strip()
    except Exception as e:
        return None, f"AI error: {e}"
    if len(txt) < 80:
        return None, "AI text too short"
    ok, bad = numbers_ok(txt, facts)
    if not ok:
        return None, f"AI used numbers not in the facts: {bad}"
    return txt, None


# ───────────────────────── COT ─────────────────────────
def _kfmt(v):
    a = abs(v)
    s = f"{a / 1e6:.2f}M" if a >= 1e6 else f"{a / 1000:.1f}k" if a >= 1000 else f"{a:.0f}"
    return ("+" if v > 0 else "-" if v < 0 else "") + s


def _streak(chart):
    """Settimane consecutive di variazione del netto nello stesso verso (dalla più recente)."""
    nets = [p[1] for p in chart or []]
    if len(nets) < 3:
        return 0, 0
    d = [nets[i] - nets[i - 1] for i in range(1, len(nets))]
    sign = 1 if d[-1] > 0 else -1 if d[-1] < 0 else 0
    if sign == 0:
        return 0, 0
    n = 0
    for x in reversed(d):
        if (x > 0 and sign > 0) or (x < 0 and sign < 0):
            n += 1
        else:
            break
    return n, sign


def cot_facts(res):
    facts = []
    for r in res:
        side = "net long" if r["net"] > 0 else "net short" if r["net"] < 0 else "flat"
        n, sg = _streak(r.get("chart"))
        f = (f"{r['name']} ({r['group']}): {r['trader'].lower()} {side} {_kfmt(r['net'])} contracts; "
             f"1-week change {_kfmt(r['chg'])}; 4-week change {_kfmt(r['chg4'])}; "
             f"COT index {int(r['cot_index'])} (0 = most short, 100 = most long of the 3-year range)")
        if r.get("net_pct_oi") is not None:
            f += f"; net = {r['net_pct_oi']:+.1f}% of open interest"
        if r.get("price_chg") is not None:
            f += f"; futures price {r['price_chg']:+.1f}% over the report week"
        if r.get("flag"):
            f += f"; positioning: {r['flag'].lower()}"
        if r.get("divergence"):
            f += f"; divergence: {r['divergence'].lower()}"
        if n >= 2:
            f += f"; net position {'increased' if sg > 0 else 'decreased'} for {n} consecutive weeks"
        if r["key"] == "wti" and "pm_net" in r:
            f += f"; producers/merchants net {_kfmt(r['pm_net'])}, swap dealers net {_kfmt(r.get('swap_net', 0))}"
        facts.append(f)
    return facts


def rule_cot(res):
    """Sintesi deterministica COT: solo numeri presi dai risultati."""
    s = []
    rng = lambda r: (r["range_hi"] - r["range_lo"]) or 1
    movers = sorted(res, key=lambda r: abs(r["chg"]) / rng(r), reverse=True)[:2]
    if movers:
        s.append("Largest weekly shifts relative to their 3-year range: " + "; ".join(
            f"{r['name']} ({r['trader'].lower()} net {'raised' if r['chg'] > 0 else 'cut'} by {_kfmt(abs(r['chg']))} "
            f"to {_kfmt(r['net'])})" for r in movers) + ".")
    crowded = [r for r in res if r["flag"]]
    if crowded:
        s.append("Stretched positioning: " + "; ".join(
            f"{r['name']} {r['flag'].lower()} (COT index {int(r['cot_index'])})" for r in crowded)
            + " — crowded trades raise the risk of a squeeze if price turns against them.")
    else:
        s.append("No market is at a positioning extreme this week (all COT indexes between 20 and 80).")
    divs = [r for r in res if r["divergence"]]
    if divs:
        s.append("Price and positioning diverge in " + "; ".join(
            f"{r['name']} ({r['divergence'].lower()}, price {r['price_chg']:+.1f}%)" for r in divs)
            + ": the move is not backed by new speculative positions.")
    streaks = []
    for r in res:
        n, sg = _streak(r.get("chart"))
        if n >= 3:
            streaks.append(f"{r['name']} ({'adding' if sg > 0 else 'cutting'} net length for {n} weeks)")
    if streaks:
        s.append("Persistent trends in positioning: " + "; ".join(streaks[:4]) + ".")
    wti = next((r for r in res if r["key"] == "wti"), None)
    if wti:
        side = "long" if wti["net"] > 0 else "short"
        s.append(f"WTI: managed money net {side} {_kfmt(wti['net'])}, COT index {int(wti['cot_index'])}"
                 + (f", producers/merchants net {_kfmt(wti['pm_net'])}" if "pm_net" in wti else "") + ".")
    return " ".join(s)


# ───────────────────────── FUTURES FLOW ─────────────────────────
def flow_facts(res):
    facts = []
    for r in res:
        f = f"{r['name']}: most active {r['active']}"
        if r.get("price_chg") is not None:
            f += f"; price {r['price_chg']:+.2f}% on the session"
        if r.get("oi_chg") is not None:
            pct = r["oi_chg"] / (r["oi_total"] - r["oi_chg"]) * 100 if r["oi_total"] - r["oi_chg"] else None
            f += f"; total open interest {_kfmt(r['oi_chg'])} contracts" + (f" ({pct:+.1f}%)" if pct is not None else "")
        if r.get("vol_ratio"):
            f += f"; volume {r['vol_ratio']:.1f}x its 20-day average"
        if r.get("flow"):
            f += f"; flow read: {r['flow'].lower()}"
        sp = r["spread_m1m2"] if r["key"] == "ng" else r["spread_m1m6"]
        lab = f"{r['m1']}-{r['m2']}" if r["key"] == "ng" else f"{r['m1']}-{r['m6']}"
        f += f"; curve {r['structure']}, {lab} spread {sp:+.{r['dec']}f} {r['unit']}"
        if r.get("spread_m1m6_chg") is not None and r["key"] != "ng":
            f += f" ({r['spread_m1m6_chg']:+.{r['dec']}f} vs previous session)"
        if r.get("top_oi_move"):
            f += f"; largest open-interest change in {r['top_oi_move'][1]} ({_kfmt(r['top_oi_move'][0])})"
        facts.append(f)
    cl = next((r for r in res if r["key"] == "cl"), None)
    bz = next((r for r in res if r["key"] == "bz"), None)
    if cl and bz:
        facts.append(f"Brent (NYMEX) minus WTI, front months: {bz['curve'][0][1] - cl['curve'][0][1]:+.2f} $/bbl")
    return facts


def rule_flow(res):
    s = []
    by = {}
    for r in res:
        if r.get("flow"):
            by.setdefault(r["flow"], []).append(r["name"])
    if by:
        new = len(by.get("New longs", [])) + len(by.get("New shorts", []))
        close = len(by.get("Short covering", [])) + len(by.get("Long liquidation", []))
        theme = ("fresh positions were opened" if new > close else
                 "the session was driven by positions being closed" if close > new else
                 "new positions and closures were balanced")
        s.append(f"Overall {theme}: " + "; ".join(f"{k.lower()} in {', '.join(v)}" for k, v in by.items()) + ".")
    strong = [r for r in res if r.get("oi_chg") and r["oi_chg"] > 0 and r.get("vol_ratio") and r["vol_ratio"] >= 1.2]
    if strong:
        s.append("Moves with conviction (open interest and volume both up): " + "; ".join(
            f"{r['name']} (OI {_kfmt(r['oi_chg'])}, volume {r['vol_ratio']:.1f}x)" for r in strong) + ".")
    fragile = [r for r in res if r.get("flow") in ("Short covering", "Long liquidation")]
    if fragile:
        s.append("Moves driven by closing positions, typically less durable: " + ", ".join(r["name"] for r in fragile) + ".")
    quiet = [r for r in res if r.get("vol_ratio") and r["vol_ratio"] < 0.7]
    if quiet:
        s.append("Light participation (volume below 0.7x the 20-day average) in " + ", ".join(r["name"] for r in quiet) + ".")
    cl = next((r for r in res if r["key"] == "cl"), None)
    if cl:
        t = f"WTI curve in {cl['structure']}, {cl['m1']}-{cl['m6']} spread {cl['spread_m1m6']:+.2f} $/bbl"
        if cl.get("spread_m1m6_chg") is not None:
            t += f" ({cl['spread_m1m6_chg']:+.2f} vs previous session)"
        s.append(t + ".")
    return " ".join(s)


def build(kind, res):
    """Ritorna (testo, fonte) dove fonte = 'ai' oppure 'rules'."""
    facts = cot_facts(res) if kind == "cot" else flow_facts(res)
    txt, why = ai_read(kind, facts)
    if txt:
        print(f"  Desk read: AI ({len(txt)} chars)")
        return txt, "ai"
    print(f"  Desk read: rule-based ({why})")
    return (rule_cot(res) if kind == "cot" else rule_flow(res)), "rules"
