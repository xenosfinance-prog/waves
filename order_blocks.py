"""
order_blocks.py — Order Block (Smart Money Concepts) con regole OGGETTIVE.

2026-10-30. Usato da ew_server.py per:
  - /order-block-signal   segnale live per il broker-engine
  - /order-block-backtest backtest su dati reali Yahoo (stesso feed del sistema)

Regole (identiche in live e backtest, nessun lookahead):
  1. Swing high/low a frattale: pivot con K candele per lato, CONFERMATO solo
     K candele dopo (prima non si conosce).
  2. BOS: una candela CHIUDE oltre l'ultimo swing confermato e non ancora rotto.
  3. Gamba d'impulso: dal minimo (long) / massimo (short) tra lo swing rotto e
     la candela di BOS. Ampiezza >= DISP_ATR × ATR(14)  → displacement.
  4. FVG: almeno un fair value gap nella gamba (low[j+1] > high[j-1] long,
     high[j+1] < low[j-1] short).
  5. Order block = ultima candela di colore opposto (ribassista per il long)
     entro le OB_LOOKBACK candele che precedono l'estremo della gamba.
     Zona = [min dei minimi da OB a estremo, massimo della candela OB] (long).
  6. Filtro trend opzionale: long solo con chiusura > SMA200, short solo sotto.
  7. Valido solo al PRIMO ritorno (non mitigato), entro MAX_WAIT candele.
  Ingresso al bordo della zona (top per il long), stop oltre la zona di
  STOP_ATR × ATR, target a RR × rischio.
"""

import numpy as np
import pandas as pd

K = 3               # candele per lato del frattale
DISP_ATR = 2.0      # ampiezza minima dell'impulso in ATR
OB_LOOKBACK = 3     # candele prima dell'estremo in cui cercare l'OB
STOP_ATR = 0.1      # margine dello stop oltre la zona
MAX_WAIT = 48       # candele massime di attesa del ritorno in zona
MAX_HOLD = 120      # candele massime in posizione (backtest)


def _atr(df, n=14):
    h, l, c = df["High"].values, df["Low"].values, df["Close"].values
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).rolling(n, min_periods=n).mean().values


def find_zones(df, trend_filter=True, rr=2.0):
    """Tutte le zone OB create nella serie. Ogni zona porta l'indice della
    candela di BOS (`created`): da lì in poi è nota, mai prima."""
    o, h, l, c = (df[x].values.astype(float) for x in ("Open", "High", "Low", "Close"))
    n = len(c)
    atr = _atr(df)
    sma200 = pd.Series(c).rolling(200, min_periods=200).mean().values
    zones = []
    sh = sl = None            # ultimo swing confermato: (prezzo, indice, rotto?)
    for i in range(2 * K, n):
        p = i - K             # pivot che si conferma alla candela i
        if h[p] >= h[p - K:p].max() and h[p] > h[p + 1:i + 1].max():
            sh = [h[p], p, False]
        if l[p] <= l[p - K:p].min() and l[p] < l[p + 1:i + 1].min():
            sl = [l[p], p, False]
        if np.isnan(atr[i]):
            continue

        # ── BOS rialzista → order block bullish
        if sh is not None and not sh[2] and c[i] > sh[0]:
            sh[2] = True
            seg = range(sh[1], i + 1)
            leg = min(seg, key=lambda j: l[j])
            ob = next((j for j in range(leg, max(leg - OB_LOOKBACK, 0) - 1, -1) if c[j] < o[j]), None)
            fvg = any(l[j + 1] > h[j - 1] for j in range(max(leg, 1), i))
            trend_ok = (not trend_filter) or (not np.isnan(sma200[i]) and c[i] > sma200[i])
            if ob is not None and fvg and trend_ok and (c[i] - l[leg]) >= DISP_ATR * atr[i]:
                top, bottom = h[ob], l[ob:leg + 1].min()
                stop = bottom - STOP_ATR * atr[i]
                zones.append({"side": "long", "created": i, "ob": ob, "top": top, "bottom": bottom,
                              "entry": top, "stop": stop, "tp": top + rr * (top - stop)})

        # ── BOS ribassista → order block bearish
        if sl is not None and not sl[2] and c[i] < sl[0]:
            sl[2] = True
            seg = range(sl[1], i + 1)
            leg = max(seg, key=lambda j: h[j])
            ob = next((j for j in range(leg, max(leg - OB_LOOKBACK, 0) - 1, -1) if c[j] > o[j]), None)
            fvg = any(h[j + 1] < l[j - 1] for j in range(max(leg, 1), i))
            trend_ok = (not trend_filter) or (not np.isnan(sma200[i]) and c[i] < sma200[i])
            if ob is not None and fvg and trend_ok and (h[leg] - c[i]) >= DISP_ATR * atr[i]:
                bottom, top = l[ob], h[ob:leg + 1].max()
                stop = top + STOP_ATR * atr[i]
                zones.append({"side": "short", "created": i, "ob": ob, "top": top, "bottom": bottom,
                              "entry": bottom, "stop": stop, "tp": bottom - rr * (stop - bottom)})
    return zones


def _first_touch(z, h, l, start, end):
    """Indice della prima candela in [start, end) che tocca la zona, o None."""
    for t in range(start, end):
        if (z["side"] == "long" and l[t] <= z["entry"]) or (z["side"] == "short" and h[t] >= z["entry"]):
            return t
    return None


def live_signal(df, trend_filter=True, rr=2.0):
    """Segnale se l'ULTIMA candela è il primo ritorno in una zona attiva e la
    zona non è stata violata (chiusura oltre lo stop). None altrimenti."""
    h, l, c = df["High"].values, df["Low"].values, df["Close"].values
    last = len(c) - 1
    best = None
    for z in find_zones(df, trend_filter, rr):
        if z["created"] >= last or last - z["created"] > MAX_WAIT:
            continue
        if _first_touch(z, h, l, z["created"] + 1, last) is not None:
            continue                                   # già mitigata
        if _first_touch(z, h, l, last, last + 1) is None:
            continue                                   # non ancora in zona
        if (z["side"] == "long" and c[last] <= z["stop"]) or (z["side"] == "short" and c[last] >= z["stop"]):
            continue                                   # zona violata
        if best is None or z["created"] > best["created"]:
            best = z
    return best


def backtest(df, trend_filter=True, rr=2.0, cost=0.0):
    """Una posizione alla volta. Stessa candela con stop e target = perdita
    (conservativo). Target non valutato sulla candela d'ingresso. Costo
    (spread) sottratto in R su ogni trade. Restituisce la lista dei trade."""
    o, h, l, c = (df[x].values.astype(float) for x in ("Open", "High", "Low", "Close"))
    n = len(c)
    trades, busy_until = [], -1
    for z in find_zones(df, trend_filter, rr):
        t = _first_touch(z, h, l, z["created"] + 1, min(z["created"] + 1 + MAX_WAIT, n))
        if t is None or t <= busy_until:
            continue
        long_ = z["side"] == "long"
        entry = min(o[t], z["entry"]) if long_ else max(o[t], z["entry"])   # gap dentro la zona
        risk = (entry - z["stop"]) if long_ else (z["stop"] - entry)
        if risk <= 0:
            continue
        stop, tp = z["stop"], z["tp"]
        r, exit_t = None, None
        if (long_ and l[t] <= stop) or (not long_ and h[t] >= stop):
            r, exit_t = -1.0, t
        else:
            for u in range(t + 1, min(t + 1 + MAX_HOLD, n)):
                if (long_ and l[u] <= stop) or (not long_ and h[u] >= stop):
                    r, exit_t = -1.0, u
                    break
                if (long_ and h[u] >= tp) or (not long_ and l[u] <= tp):
                    r, exit_t = abs(tp - entry) / risk, u
                    break
            if r is None:
                exit_t = min(t + MAX_HOLD, n - 1)
                r = ((c[exit_t] - entry) if long_ else (entry - c[exit_t])) / risk
        trades.append({"t": t, "side": z["side"], "r": r - cost / risk})
        busy_until = exit_t
    return trades


def stats(trades):
    if not trades:
        return {"n": 0}
    r = np.array([t["r"] for t in trades])
    wins, losses = r[r > 0].sum(), -r[r < 0].sum()
    eq = np.cumsum(r)
    dd = float((np.maximum.accumulate(eq) - eq).max()) if len(eq) else 0.0
    return {"n": int(len(r)), "win": round(float((r > 0).mean() * 100), 1),
            "exp_r": round(float(r.mean()), 3), "total_r": round(float(r.sum()), 1),
            "pf": round(float(wins / losses), 2) if losses > 0 else None, "max_dd_r": round(dd, 1)}
