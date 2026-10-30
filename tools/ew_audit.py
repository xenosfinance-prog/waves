#!/usr/bin/env python3
"""
ew_audit.py — controllo di coerenza del motore Elliott su dati reali (2026-10-30).

Per ogni strumento delle pagine /analysis e ogni timeframe del sito esegue la
STESSA pipeline di /ew-chart (candele, zigzag, analyze_structure,
get_wave_position) e verifica le regole che ogni conteggio pubblicato deve
rispettare:

  R1 prezzo dal lato giusto dell'invalidazione (stop) rispetto ai target
  R2 ingresso dal lato giusto dello stop
  R3 conteggio attuale: dopo l'ultimo pivot etichettato al massimo 1 pivot
     (l'estremo provvisorio dell'onda in corso)
  R4 tipo dell'alternativo coerente con i suoi dati (impulse/abc)
  R5 onda A: prezzo tra W0 e W5 dell'impulso
  W1 avviso: prezzo già oltre il target finale (tp2)

Uso:  python tools/ew_audit.py [percorso_ew_server.py ...]
Con più file confronta le versioni (es. prima/dopo una modifica).
Esce con codice 1 se la versione ULTIMA ha violazioni R1-R5.
"""

import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SYMBOLS = ["GC=F", "SI=F", "CL=F", "BZ=F", "NG=F", "HG=F", "EURUSD=X", "GBPUSD=X", "USDJPY=X",
           "USDCHF=X", "BTC-USD", "ETH-USD", "^NDX", "^GDAXI", "^GSPC", "^FTSE"]
TFS = ["M30 (30-Min)", "H1 (1-Hour)", "H4 (4-Hour)", "D1 (Daily)"]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def last_labelled(cand):
    d = cand["data"]
    if cand["type"] == "impulse":
        ws = [d.get(k) for k in ("W0", "W1", "W2", "W3", "W4", "W5") if d.get(k)]
    else:
        ws = [d.get(k) for k in ("WA", "WB", "WC") if d.get(k)]
    return ws[-1] if ws else None


def check(E, df_cache, sym, tf):
    iv, pd_, n, mult, _p, _pp = E.TF_CONFIG[tf]
    key = (sym, iv, pd_, n, tf == "H4 (4-Hour)")
    if key not in df_cache:
        df_cache[key] = E.fetch_candles(sym, iv, pd_, n, tf == "H4 (4-Hour)")
    df = df_cache[key]
    pivots = E.find_pivots_zigzag(df, atr_mult=mult)
    if len(pivots) < 3:
        pivots = E.find_pivots_zigzag(df, atr_mult=mult * 0.65)
    live = float(df["Close"].iloc[-1])
    dp = 2 if live > 10 else 5
    atr = E.calc_atr(df, 14)
    primary, alternate, _t, _m = E.analyze_structure(pivots, live)
    out, viol, warn = {}, [], []
    for role, cand in (("primary", primary), ("alternate", alternate)):
        if not cand:
            out[role] = "-"
            continue
        d = cand["data"]
        real_type = "impulse" if "W0" in d else "abc"
        if cand["type"] != real_type:
            viol.append(f"R4 {role} labelled {cand['type']} but data is {real_type}")
            out[role] = f"type-mismatch({cand['type']}/{real_type})"
            continue
        try:
            wn, desc, _s, kl = E.get_wave_position(cand, live, dp, atr)
        except Exception as e:
            viol.append(f"ERR {role}: {type(e).__name__} {e}")
            out[role] = "error"
            continue
        out[role] = f"{wn}"
        if wn == "?":
            continue
        lp = last_labelled(cand)
        if lp is not None and lp in pivots:
            after = len(pivots) - 1 - pivots.index(lp)
            if after > 1:
                viol.append(f"R3 {role} wave {wn}: {after} pivots after the last labelled one (stale count)")
        stop, tp1, tp2 = kl.get("stop_loss"), kl.get("tp1"), kl.get("tp2")
        entry = kl.get("entry", live)
        if stop is not None and tp1 is not None:
            long_side = tp1 > stop
            if (long_side and live <= stop) or (not long_side and live >= stop):
                viol.append(f"R1 {role} wave {wn}: live {live:.{dp}f} beyond invalidation {stop}")
            if (long_side and not (stop < entry)) or (not long_side and not (stop > entry)):
                viol.append(f"R2 {role} wave {wn}: entry {entry} on the wrong side of the stop {stop}")
            if (long_side and live > tp1) or (not long_side and live < tp1):
                warn.append(f"W2 {role} wave {wn}: live {live:.{dp}f} already beyond first target {tp1}")
            if tp2 is not None and ((long_side and live > tp2) or (not long_side and live < tp2)):
                warn.append(f"W1 {role} wave {wn}: live {live:.{dp}f} already beyond final target {tp2}")
        if wn == "A" and real_type == "impulse":
            lo, hi = sorted((d["W0"]["price"], d["W5"]["price"]))
            if not (lo <= live <= hi):
                viol.append(f"R5 {role} wave A: live {live:.{dp}f} outside W0–W5 [{lo:.{dp}f}, {hi:.{dp}f}]")
    return out, viol, warn, live


def main():
    paths = sys.argv[1:] or [os.path.join(ROOT, "ew_server.py")]
    mods = [load(p, f"ew_mod_{i}") for i, p in enumerate(paths)]
    cache = {}
    totals = [[0, 0, 0] for _ in mods]   # conteggi pubblicabili, violazioni, avvisi
    for sym in SYMBOLS:
        for tf in TFS:
            cells = []
            for i, E in enumerate(mods):
                try:
                    out, viol, warn, live = check(E, cache, sym, tf)
                except Exception as e:
                    cells.append(f"FETCH/ERR {type(e).__name__}: {str(e)[:80]}")
                    continue
                totals[i][0] += sum(1 for v in out.values() if v not in ("-", "?", "error"))
                totals[i][1] += len(viol)
                totals[i][2] += len(warn)
                cells.append(f"P={out.get('primary')} A={out.get('alternate')} live={live:.5g}"
                             + "".join(f"\n      ✗ {v}" for v in viol)
                             + "".join(f"\n      ! {w}" for w in warn))
            print(f"{sym:9s} {tf:13s}")
            for i, c in enumerate(cells):
                print(f"   [v{i}] {c}")
    print("\nTOTALS (counts shown / violations R1-R5 / warnings):")
    for i, (p, t) in enumerate(zip(paths, totals)):
        print(f"   [v{i}] {os.path.basename(p)}: {t[0]} / {t[1]} / {t[2]}")
    sys.exit(1 if totals[-1][1] else 0)


if __name__ == "__main__":
    main()
