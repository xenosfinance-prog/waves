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
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import free_llm  # noqa: E402  (2026-10-26: Gemini gratuito al posto di Claude a pagamento)

MODEL = "gemini (free_llm)"   # 2026-10-26: niente più Claude a pagamento

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


def ai_read(kind, facts, n_sentences="4-5"):
    """kind: 'cot' | 'flow'. Ritorna (testo, None) oppure (None, motivo)."""
    if not free_llm.available():
        return None, "no GEMINI_API_KEY"
    what = ("the weekly CFTC Commitments of Traders positioning of speculative traders (managed money for "
            "commodities, leveraged funds for financial futures)" if kind == "cot" else
            "yesterday's futures session: price change against the change in total open interest, volume against "
            "its 20-day average, and the shape of the forward curves")
    prompt = f"""You are the head of a futures desk writing the short "Desk read" that opens a XenosFinance page about {what}.
Readers are traders and students: they see the tables below your text, so do not repeat every row — tell them what the numbers mean together.

FACTS (the only source you may use):
{json.dumps(facts, ensure_ascii=False, indent=0)}

Write {n_sentences} short sentences in English, one paragraph, MAXIMUM 120 words, plain text (no markdown, no bullet points, no headings).
Cover: the dominant theme, where positioning or flow is strongest, where it is crowded or fragile, and any divergence between price and positioning. Pick the 3-4 most important markets; do not try to mention all of them.

STRICT RULES:
- Every number you write must appear EXACTLY as written in the FACTS (same digits, same decimals). If a number is not in the FACTS, do not write it. Prefer fewer numbers.
- Do not compute new numbers (no sums, differences, averages or percentages of your own).
- Respect the direction words given in the FACTS exactly ("toward long", "toward short", "more short", "less long"...). A negative change on a net short position means the short got BIGGER, not smaller.
- A single-contract open-interest change is not part of the total change: never describe it as a share of the total.
- Use the words "crowded", "extended" or "extreme" only for markets the FACTS label that way.
- No news, no fundamentals, no forecasts of price targets, never tell the reader to buy or sell.
- Positioning is context, not a timing signal: say "risk of a squeeze" or "fragile", never "will rise/fall"."""
    try:
        raw = free_llm.generate(prompt, max_tokens=700)
        if not raw:
            return None, "AI unavailable (free quota)"
        txt = " ".join(raw.split()).strip()
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


def _dirword(net, chg):
    """Verso della variazione del netto, senza ambiguità sul segno."""
    if chg == 0:
        return "unchanged"
    prev = net - chg
    if prev > 0 > net:
        return "flipped from net long to net short"
    if prev < 0 < net:
        return "flipped from net short to net long"
    if net > 0 or (net == 0 and prev > 0):
        return "more long" if chg > 0 else "less long"
    return "less short" if chg > 0 else "more short"


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
             f"1-week change {_kfmt(r['chg'])} ({_dirword(r['net'], r['chg'])}); "
             f"4-week change {_kfmt(r['chg4'])} ({_dirword(r['net'], r['chg4'])}); "
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
            f += f"; net position moved {'toward long' if sg > 0 else 'toward short'} for {n} consecutive weeks"
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
def brent_wti(res):
    """2026-10-19: spread Brent–WTI sullo STESSO mese di consegna (il front month Brent è un mese avanti
    rispetto al WTI: confrontare i due front month mescolava due scadenze). -> (spread, 'Z26') o None."""
    cl = next((r for r in res if r["key"] == "cl"), None)
    bz = next((r for r in res if r["key"] == "bz"), None)
    if not cl or not bz or not cl.get("curve") or not bz.get("curve"):
        return None
    clm = {c[0][2:]: c[1] for c in cl["curve"]}
    for c in bz["curve"]:
        m = c[0][2:]
        if m in clm:
            return c[1] - clm[m], m
    return None


def flow_facts(res):
    facts = []
    for r in res:
        f = f"{r['name']}: most active {r['active']}"
        if r.get("price_chg") is not None:
            f += f"; price {r['price_chg']:+.2f}% on the session"
        if r.get("oi_chg"):   # 0 = open interest non aggiornato dalla fonte: non è un dato
            pct = r["oi_chg"] / (r["oi_total"] - r["oi_chg"]) * 100 if r["oi_total"] - r["oi_chg"] else None
            f += f"; total open interest across all months {_kfmt(r['oi_chg'])} contracts" + (f" ({pct:+.1f}%)" if pct is not None else "")
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
            f += (f"; largest single-contract open-interest change: {r['top_oi_move'][1]} {_kfmt(r['top_oi_move'][0])} "
                  "(single months include rolling between months; only the total is the net flow)")
        if r.get("rolling"):   # 2026-11-17: settimana di scadenza
            f += (f"; expiry roll: {', '.join(r['rolling'])} is expiring and open interest is moving to {r['m1']}, "
                  f"which is used as the reference month; the open-interest change reflects the roll and is not a "
                  f"directional flow")
        facts.append(f)
    bw = brent_wti(res)
    if bw:
        facts.append(f"Brent (NYMEX) minus WTI, same delivery month {bw[1]}: {bw[0]:+.2f} $/bbl")
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
    rolls = [r for r in res if r.get("flow") == "Expiry roll"]
    if rolls:   # 2026-11-17
        s.append("Expiry roll under way, open-interest change not directional: " + ", ".join(
            f"{r['name']} ({', '.join(r['rolling'])} → {r['m1']})" for r in rolls) + ".")
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


# ───────────────────────── OIL DESK (WTI & Brent) ─────────────────────────
# 2026-10-19: blocco fisso sul petrolio in COT e Futures Flow, qualunque sia il tema della settimana.
_OIL_KEYS = {"cot": ("wti", "brent"), "flow": ("cl", "bz")}


def oil_facts(kind, res):
    oil = [r for r in res if r["key"] in _OIL_KEYS[kind]]
    if not oil:
        return []
    facts = cot_facts(oil) if kind == "cot" else flow_facts(oil)
    if kind == "cot":
        w = next((r for r in oil if r["key"] == "wti"), None)
        if w and w.get("mm_ls_ratio"):
            facts.append(f"WTI managed money long/short ratio {w['mm_ls_ratio']:.2f}")
    else:
        for r in oil:
            facts.append(f"{r['name']}: {r['m1']}-{r['m2']} spread {r['spread_m1m2']:+.{r['dec']}f} {r['unit']} (front month minus second month)")
    return facts


def ai_oil(kind, facts):
    if not free_llm.available() or not facts:
        return None, "no key or no oil data"
    what = ("CFTC Commitments of Traders positioning (managed money; producers/merchants and swap dealers are the commercial side)"
            if kind == "cot" else "yesterday's futures session: price vs total open interest, volume vs its 20-day average, and the forward curve")
    prompt = f"""You run the oil desk at XenosFinance and write the short "Oil desk" note on WTI and Brent for {what}.

FACTS (the only source you may use):
{json.dumps(facts, ensure_ascii=False, indent=0)}

Write 2-3 short sentences in English, one paragraph, MAXIMUM 75 words, plain text. Talk only about WTI and Brent: speculative positioning or flow, how strong or fragile it is, and the curve or commercial structure when the FACTS give it.

STRICT RULES:
- Every number you write must appear EXACTLY as written in the FACTS. Do not compute new numbers.
- Respect the direction words in the FACTS exactly ("more long", "less long", "more short"...).
- A single-contract open-interest change is not part of the total change.
- If the FACTS give no open-interest change for a market, do not mention open interest for it at all.
- Do not start with a title or heading.
- Use "crowded", "extended" or "extreme" only if the FACTS say so.
- No news, no fundamentals, no price targets, never tell the reader to buy or sell."""
    try:
        raw = free_llm.generate(prompt, max_tokens=400)
        if not raw:
            return None, "AI unavailable (free quota)"
        txt = " ".join(raw.split()).strip()
    except Exception as e:
        return None, f"AI error: {e}"
    import re as _re   # il modello a volte ripete il titolo del blocco
    txt = _re.sub(r"^\s*\**\s*oil desk[^a-z0-9]*(?:wti\s*(?:&|and)\s*brent)?\s*\**[:\-—\s]*", "", txt, flags=_re.I).strip()
    if len(txt) < 60:
        return None, "AI text too short"
    ok, bad = numbers_ok(txt, facts)
    if not ok:
        return None, f"AI used numbers not in the facts: {bad}"
    return txt, None


def rule_oil(kind, res):
    s = []
    for r in res:
        if r["key"] not in _OIL_KEYS[kind]:
            continue
        if kind == "cot":
            side = "long" if r["net"] > 0 else "short"
            t = (f"{r['name']}: managed money net {side} {_kfmt(r['net'])}, 1-week change {_kfmt(r['chg'])} "
                 f"({_dirword(r['net'], r['chg'])}), COT index {int(r['cot_index'])}")
            if "pm_net" in r:
                t += f"; producers/merchants net {_kfmt(r['pm_net'])}, swap dealers net {_kfmt(r.get('swap_net', 0))}"
            if r.get("mm_ls_ratio"):
                t += f"; fund long/short {r['mm_ls_ratio']:.2f}"
        else:
            t = f"{r['name']} ({r['active']})"
            if r.get("price_chg") is not None:
                t += f" {r['price_chg']:+.2f}%"
            if r.get("oi_chg"):
                t += f", total open interest {_kfmt(r['oi_chg'])}"
            if r.get("flow"):
                t += f" ({r['flow'].lower()})"
            if r.get("vol_ratio"):
                t += f", volume {r['vol_ratio']:.1f}x the 20-day average"
            t += (f"; curve in {r['structure']}, {r['m1']}-{r['m2']} {r['spread_m1m2']:+.{r['dec']}f}, "
                  f"{r['m1']}-{r['m6']} {r['spread_m1m6']:+.{r['dec']}f} {r['unit']}")
            if r.get("spread_m1m6_chg") is not None:
                t += f" ({r['spread_m1m6_chg']:+.{r['dec']}f} vs previous session)"
        s.append(t + ".")
    if kind == "flow":
        bw = brent_wti(res)
        if bw:
            s.append(f"Brent (NYMEX) minus WTI, same delivery month {bw[1]}: {bw[0]:+.2f} $/bbl.")
    return " ".join(s)


def build_oil(kind, res):
    """Ritorna (testo, fonte) del blocco Oil desk; ('', 'none') se mancano WTI e Brent."""
    facts = oil_facts(kind, res)
    if not facts:
        return "", "none"
    txt, why = ai_oil(kind, facts)
    if txt:
        print(f"  Oil desk: AI ({len(txt)} chars)")
        return txt, "ai"
    print(f"  Oil desk: rule-based ({why})")
    return rule_oil(kind, res), "rules"


def build(kind, res):
    """Ritorna (testo, fonte) dove fonte = 'ai' oppure 'rules'."""
    facts = cot_facts(res) if kind == "cot" else flow_facts(res)
    txt, why = ai_read(kind, facts)
    if txt:
        print(f"  Desk read: AI ({len(txt)} chars)")
        return txt, "ai"
    print(f"  Desk read: rule-based ({why})")
    return (rule_cot(res) if kind == "cot" else rule_flow(res)), "rules"


# ───────────────────────── BIAS & TREND READ ─────────────────────────
# 2026-10-19: conclusione finale — cosa dicono le posizioni sul possibile trend.
# Il BIAS è calcolato in codice con regole fisse sui dati già calcolati (niente AI nel punteggio);
# l'AI scrive solo la conclusione in prosa, con lo stesso controllo dei numeri.
# Orizzonte: COT = settimane (posizionamento dei fondi), Futures Flow = breve termine (1 seduta).

def _sg(v):
    return 1 if v and v > 0 else -1 if v and v < 0 else 0


def _bias_label(score):
    if score >= 4:
        return "Bullish"
    if score >= 2:
        return "Mildly bullish"
    if score <= -4:
        return "Bearish"
    if score <= -2:
        return "Mildly bearish"
    return "Neutral"


def bias_cot(r):
    """Punteggio di bias (settimane) per un mercato COT → (score, label, motivi[(segno, testo)])."""
    score, why = 0, []
    s1, s4 = _sg(r["chg"]), _sg(r["chg4"])
    if s4:
        score += s4
        why.append((s4, f"funds moved {'toward long' if s4 > 0 else 'toward short'} over 4 weeks"))
    if s1:
        score += s1
        if s1 != s4:
            why.append((s1, f"last week funds turned {'toward long' if s1 > 0 else 'toward short'}"))
    n, sg = _streak(r.get("chart"))
    if n >= 3:
        score += sg
        why.append((sg, f"{n} straight weeks {'toward long' if sg > 0 else 'toward short'}"))
    pc = r.get("price_chg")
    if r.get("divergence"):
        score -= s1
        why.append((-s1, "price and positioning diverge — the move lacks new speculative positions"))
    elif pc is not None and s1 and _sg(pc) == s1 and abs(pc) >= 0.5:
        score += s1
        why.append((s1, "price confirms the positioning change"))
    idx = int(r["cot_index"])
    if idx >= 90:
        score -= 2
        why.append((-1, f"crowded long (COT index {idx}): trend mature, reversal risk"))
    elif idx <= 10:
        score += 2
        why.append((1, f"crowded short (COT index {idx}): short-squeeze risk"))
    elif idx >= 80:
        score -= 1
        why.append((-1, f"extended long (COT index {idx})"))
    elif idx <= 20:
        score += 1
        why.append((1, f"extended short (COT index {idx})"))
    return score, _bias_label(score), why


_FLOW_PTS = {"New longs": 2, "Short covering": 1, "New shorts": -2, "Long liquidation": -1}


def bias_flow(r):
    """Punteggio di bias (breve termine, 1 seduta) per un prodotto Futures Flow → (score, label, motivi)."""
    score, why = 0, []
    fl = r.get("flow") or ""
    pts = _FLOW_PTS.get(fl, 0)
    pc = r.get("price_chg")
    if pts:
        score += pts
        why.append((_sg(pts), fl.lower() + (" (fresh positions)" if abs(pts) == 2 else " (positions closing, less durable)")))
    elif pc is not None and abs(pc) >= 0.5:
        score += _sg(pc)
        why.append((_sg(pc), f"price {'up' if pc > 0 else 'down'} without an open-interest reading"))
    vr = r.get("vol_ratio")
    dirn = _sg(score)
    if vr and dirn:
        if vr >= 1.2:
            score += dirn
            why.append((dirn, f"volume {vr:.1f}x the 20-day average (conviction)"))
        elif vr < 0.7:
            score -= dirn
            why.append((-dirn, f"light volume {vr:.1f}x the 20-day average"))
    if r["key"] in ("cl", "bz"):   # struttura della curva: segnale reale solo sul petrolio
        cs = 1 if r["structure"] == "backwardation" else -1
        score += cs
        why.append((cs, f"curve in {r['structure']}"))
        ch = r.get("spread_m1m6_chg")
        if ch is not None and abs(ch) >= 0.1:
            score += _sg(ch)
            why.append((_sg(ch), "backwardation steepening" if ch > 0 else "curve weakening (spread narrowing)"))
    return score, _bias_label(score), why


def bias_rows(kind, res):
    fn = bias_cot if kind == "cot" else bias_flow
    okeys = _OIL_KEYS[kind]
    rows = []
    for r in res:
        sc, lab, why = fn(r)
        d = _sg(sc)
        why = [t for g, t in why if d and g == d] + [t for g, t in why if not (d and g == d)]  # prima i motivi a favore
        rows.append({"key": r["key"], "name": r["name"], "score": sc, "bias": lab, "why": why})
    rows.sort(key=lambda x: (x["key"] not in okeys,))   # petrolio sempre in cima
    return rows


def bias_facts(kind, rows):
    hz = "medium term (weeks, from fund positioning)" if kind == "cot" else "short term (from the last session's flow)"
    facts = [f"Horizon of this bias: {hz}"]
    for b in rows:
        facts.append(f"{b['name']}: bias {b['bias'].lower()}" + (f" — {'; '.join(b['why'])}" if b["why"] else ""))
    return facts


def ai_bias(kind, facts):
    if not free_llm.available() or not facts:
        return None, "no key or no data"
    prompt = f"""You run the futures desk at XenosFinance and write the closing "Bias & trend read" of a page about {'CFTC COT positioning' if kind == 'cot' else "yesterday's futures flow (open interest, volume, curve)"}.
The bias of each market is ALREADY computed from the data and given below: explain what it means for a possible trend. Do not change any bias.

FACTS (the only source you may use):
{json.dumps(facts, ensure_ascii=False, indent=0)}

Write 4-5 short sentences in English, one paragraph, MAXIMUM 120 words, plain text, no headings.
Start with WTI and Brent (always), then the 2-3 other markets with the clearest bias. For each, say whether the positioning supports the current trend, warns of exhaustion/reversal (crowded), or is too weak to back the move. Close with the overall picture across markets.

STRICT RULES:
- Use exactly the bias words given (bullish, mildly bullish, neutral, mildly bearish, bearish).
- Every number you write must appear EXACTLY as written in the FACTS. Prefer no numbers at all.
- Positioning is context, not a timing signal: say "supports", "warns of", "risk of a squeeze", never "will rise/fall".
- No news, no fundamentals, no price targets, never tell the reader to buy or sell."""
    try:
        raw = free_llm.generate(prompt, max_tokens=600)
        if not raw:
            return None, "AI unavailable (free quota)"
        txt = " ".join(raw.split()).strip()
    except Exception as e:
        return None, f"AI error: {e}"
    txt = re.sub(r"^\s*\**\s*bias\s*(?:&|and)\s*trend read\s*\**[:\-—\s]*", "", txt, flags=re.I).strip()
    if len(txt) < 80:
        return None, "AI text too short"
    ok, bad = numbers_ok(txt, facts)
    if not ok:
        return None, f"AI used numbers not in the facts: {bad}"
    return txt, None


def rule_bias(kind, rows):
    okeys = _OIL_KEYS[kind]
    s = []
    for b in [x for x in rows if x["key"] in okeys]:
        s.append(f"{b['name']}: {b['bias'].lower()}" + (f" — {'; '.join(b['why'][:2])}" if b["why"] else "") + ".")
    others = sorted([x for x in rows if x["key"] not in okeys and x["bias"] != "Neutral"],
                    key=lambda x: abs(x["score"]), reverse=True)[:3]
    for b in others:
        s.append(f"{b['name']}: {b['bias'].lower()}" + (f" — {b['why'][0]}" if b["why"] else "") + ".")
    up = sum(1 for x in rows if x["score"] >= 2)
    dn = sum(1 for x in rows if x["score"] <= -2)
    mk = lambda n, v: f"{n} market {v}s" if n == 1 else f"{n} markets {v}"
    s.append(f"Overall: {mk(up, 'lean')} bullish, {mk(dn, 'lean')} bearish, the rest neutral.")
    return " ".join(s)


def build_bias(kind, res):
    """Ritorna (righe_bias, testo, fonte). Le righe hanno sempre il bias calcolato in codice."""
    rows = bias_rows(kind, res)
    txt, why = ai_bias(kind, bias_facts(kind, rows))
    if txt:
        print(f"  Bias read: AI ({len(txt)} chars)")
        return rows, txt, "ai"
    print(f"  Bias read: rule-based ({why})")
    return rows, rule_bias(kind, rows), "rules"


def bias_html(kind, rows, text, esc, text_it=None):
    """Sezione finale della pagina: tabella bias + conclusione.
    2026-10-25: versione italiana (data-it, vedi tools/page_i18n.py); text_it = conclusione tradotta."""
    import page_i18n as PI
    L = PI.L
    hz = ("Medium-term bias (weeks) from speculative positioning." if kind == "cot" else
          "Short-term bias (next sessions) from the last session's flow and, for oil, the curve.")
    hz_it = ("Bias di medio periodo (settimane) dal posizionamento speculativo." if kind == "cot" else
             "Bias di breve periodo (prossime sedute) dal flusso dell'ultima seduta e, per il petrolio, dalla curva.")
    cls = lambda b: "up" if "ullish" in b else "dn" if "earish" in b else ""
    h = [f"<h2>{L('Bias &amp; trend read', 'Bias e lettura del trend')}</h2>",
         f"<p>{L(esc(text), esc(text_it) if text_it else '')}</p>",
         f"<table><tr><th>{L('Market', 'Mercato')}</th><th>Bias</th><th>{L('Why', 'Motivi')}</th></tr>"]
    for b in rows:
        why_en = "; ".join(b["why"]) or "no clear signal"
        parts_it = [PI.why_it(w) for w in (b["why"] or ["no clear signal"])]
        why_html = L(esc(why_en), esc("; ".join(parts_it)) if all(parts_it) else "")
        h.append(f'<tr><td>{PI.market(b["name"], esc)}</td><td class="{cls(b["bias"])}"><b>'
                 f'{L(esc(b["bias"]), esc(PI.BIAS_IT.get(b["bias"], "")))}</b></td>'
                 f'<td class="m">{why_html}</td></tr>')
    h.append("</table>")
    foot_en = (f"{hz} Bias is computed in code from the figures on this page with fixed rules (direction and "
               "persistence of positioning, price confirmation, crowding" + (", curve" if kind == "flow" else "")
               + "). Context, not a trade signal.")
    foot_it = (f"{hz_it} Il bias è calcolato in codice dai dati di questa pagina con regole fisse (direzione e "
               "persistenza del posizionamento, conferma del prezzo, affollamento" + (", curva" if kind == "flow" else "")
               + "). È contesto, non un segnale operativo.")
    h.append(f'<p style="font-family:var(--mono);font-size:10px;color:var(--muted)">{L(foot_en, foot_it)}</p>')
    return h


def bias_telegram(rows, text):
    import html as H
    arrow = lambda b: "▲" if "ullish" in b else "▼" if "earish" in b else "•"
    tab = "\n".join(f"{b['name'][:13]:<13} {arrow(b['bias'])} {b['bias']}" for b in rows)
    return ["<b>Bias &amp; trend read</b>", "<pre>" + H.escape(tab) + "</pre>", H.escape(text)]
