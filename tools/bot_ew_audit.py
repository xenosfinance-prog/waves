#!/usr/bin/env python3
"""bot_ew_audit.py (2026-10-30) — audit del motore Elliott del BOT (/ews, /elliott) su dati reali.
Usa una copia estratta del motore (tools/_bot_ew_engine.py, solo audit). Per ogni mercato EWS:
  B1 prezzo dal lato giusto dell'invalidazione      B2 target nella direzione del trade
  B3 "reached": livello davvero toccato dai massimi/minimi reali dell'onda in corso
  B4 geometria del conteggio (regole Elliott sui pivot etichettati)
  B5 bias coerente con l'onda                       + testo completo del caso richiesto
"""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bot_ew_engine as B

FOCUS = sys.argv[1:] or ["WMT"]


def geometry(eng):
    pv = {p["label"]: p["p"] for p in eng["pivots"]}
    d = eng["dir"]
    g = lambda k: d * pv[k]
    errs = []
    if eng.get("triangle"):
        return errs
    labs = [p["label"] for p in eng["pivots"]]
    if "1" in pv and not g("1") > g("0"): errs.append("W1 not beyond W0")
    if "2" in pv and not g("2") > g("0"): errs.append("W2 beyond W0 (rule 1)")
    if "3" in pv and labs.index("3") < len(labs) - 1 and not g("3") > g("1"): errs.append("W3 not beyond W1")
    if "4" in pv and not g("4") > g("1"): errs.append("W4 overlaps W1 (rule 3)")
    return errs


def main():
    bad = 0
    for sym in B.EWS_SYMBOLS:
        days = B.EWS_BARS_DAYS_STOCKS if sym in B.EWS_STOCKS else B.EWS_BARS_DAYS
        r = B.fetch_data(sym, days, "1h")
        if r is None or not len(r):
            print(f"{sym:7s} no data"); continue
        df4 = B.resample_4h_tv(r, B.MARKETS[sym]["yf"])
        if len(df4) < 60:
            print(f"{sym:7s} too few bars"); continue
        ds = B.count_elliott_waves_engine(df4)
        eng = ds.get("engine")
        last = float(df4["close"].iloc[-1])
        if not eng:
            print(f"{sym:7s} no count"); continue
        wn, td, inv = ds["wave_num"], ds.get("trade_dir", 0), ds.get("invalidation")
        pf = B._ews_pf(sym)
        n = len(df4)
        st = max(min(max(0, n - 70), max(0, eng["pivots"][0]["i"] - 6)), n - 300, 0)
        rng = float(df4["high"].iloc[st:].max() - df4["low"].iloc[st:].min()) or abs(last) * 0.01
        ext = B._ew_wave_extreme(df4, eng, td) if wn in ("3", "5", "A", "C") else None
        plan = B._ew_target_plan(eng, B._ewp_setup_from(ds), last, rng, pf, extreme=ext)
        v = []
        if td and inv is not None and ((td > 0 and last <= inv) or (td < 0 and last >= inv)):
            v.append(f"B1 last {last} beyond invalidation {inv}")
        for t_, lab in plan["targets"]:
            if (t_ - last) * td <= 0: v.append(f"B2 target {t_:.2f} not in trade direction")
        if plan.get("reached"):
            lvl = plan["reached"][0]
            i0 = eng["pivots"][-2]["i"]
            seg = df4.iloc[i0:]
            real = float(seg["high"].max()) if td > 0 else float(seg["low"].min())
            if (real - lvl) * td < 0:
                v.append(f"B3 'reached' {lvl:.2f} but wave extreme is {real:.2f}")
        v += [f"B4 {e}" for e in geometry(eng)]
        if not eng.get("triangle") and td:
            exp = {"1": 1, "3": 1, "5": 1, "2": 1, "4": 1, "A": -1, "B": -1, "C": -1}.get(wn)
            if exp is not None and td != exp * eng["dir"] and "TERMINAL" not in str(ds.get("bias", "")):
                v.append(f"B5 bias {td:+d} vs wave {wn} of a {'bull' if eng['dir']>0 else 'bear'} structure")
        bad += len(v)
        print(f"{sym:7s} wave {wn:2s} {eng['degree']:11s} td={td:+d} last={last:.2f} inv={inv}"
              + "".join(f"\n        ✗ {x}" for x in v))
        if sym in FOCUS:
            waiting = wn in ("4", "B")
            k0 = 2 if plan["reached"] else 1
            notes = B._ews_trade_plan(ds, eng, plan, df4, last, td, pf, wn, waiting, k0)
            dn = B._ews_desk_note(df4, ds, td, pf) if td else ""
            print("    pivots:", ", ".join(f"{p['label']}={p['p']:.2f}@{p['time']}" for p in eng["pivots"]))
            print(f"    wave extreme since last confirmed pivot: {ext}   fibs: {[round(f['v'],2) for f in eng.get('fibs', [])]}")
            print(f"    plan: reached={plan.get('reached')} targets={plan['targets']} basis={plan['basis']}")
            print(f"    desk notes: {notes} | {dn}")
            print("    last 6 bars:\n" + df4.tail(6).round(2).to_string())
    print(f"\nTOTAL violations: {bad}")


if __name__ == "__main__":
    main()
