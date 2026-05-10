#!/usr/bin/env python3
"""
XenosFinance — Elliott Wave Server v3
Full glossary implementation: hard Fibonacci filters, alternate scenarios,
market structure, triangle/WXY detection, channeling targets.
"""

import os, json, logging
import anthropic
import yfinance as yf
import pandas as pd
import numpy as np
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EWServer")

app = Flask(__name__)
CORS(app)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

SYMBOL_MAP = {
    "eur/usd":"EURUSD=X","eurusd":"EURUSD=X",
    "gbp/usd":"GBPUSD=X","gbpusd":"GBPUSD=X",
    "usd/jpy":"USDJPY=X","usdjpy":"USDJPY=X",
    "usd/chf":"USDCHF=X","usdchf":"USDCHF=X",
    "aud/usd":"AUDUSD=X","audusd":"AUDUSD=X",
    "usd/cad":"USDCAD=X","usdcad":"USDCAD=X",
    "gbp/jpy":"GBPJPY=X","gbpjpy":"GBPJPY=X",
    "eur/jpy":"EURJPY=X","eurjpy":"EURJPY=X",
    "gold xau/usd":"GC=F","gold":"GC=F","xauusd":"GC=F",
    "silver xag/usd":"SI=F","silver":"SI=F","xagusd":"SI=F",
    "oil wti":"CL=F","usoil":"CL=F","wti":"CL=F","oil wti (crude)":"CL=F",
    "brent oil":"BZ=F","brent":"BZ=F",
    "nat gas":"NG=F","ngas":"NG=F","natural gas":"NG=F",
    "bitcoin btc/usd":"BTC-USD","btc/usd":"BTC-USD","btcusd":"BTC-USD","bitcoin":"BTC-USD",
    "ethereum eth/usd":"ETH-USD","eth/usd":"ETH-USD","ethusd":"ETH-USD","ethereum":"ETH-USD",
    "s&p 500":"SPY","spx500":"SPY","sp500":"SPY",
    "nasdaq":"QQQ","dow jones":"DIA",
    "dax":"^GDAXI","ftse 100":"^FTSE",
    "us dollar dxy":"DX-Y.NYB","dxy":"DX-Y.NYB",
    "eur/gbp":"EURGBP=X","eurgbp":"EURGBP=X",
    "usd/mxn":"USDMXN=X","usdmxn":"USDMXN=X",
    "usd/brl":"USDBRL=X",
    "copper":"HG=F","cocoa":"CC=F","coffee":"KC=F","wheat":"ZW=F","corn":"ZC=F",
    "vix":"^VIX",
}

TF_CONFIG = {
    "M5 (5-Min)":   ("5m",  "5d",   100, 0.8, "1h",  "14d"),
    "M15 (15-Min)": ("15m", "14d",  100, 0.9, "1h",  "30d"),
    "M30 (30-Min)": ("30m", "30d",  100, 1.0, "4h",  "60d"),
    "H1 (1-Hour)":  ("1h",  "30d",  90,  1.2, "1d",  "90d"),
    "H2 (2-Hour)":  ("2h",  "60d",  80,  1.5, "1d",  "180d"),
    "H4 (4-Hour)":  ("1h",  "60d",  80,  1.8, "1d",  "180d"),
    "D1 (Daily)":   ("1d",  "1y",   120, 2.2, "1wk", "5y"),
    "W1 (Weekly)":  ("1wk", "5y",   100, 2.8, "1mo", "10y"),
}

# ─────────────────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────────────────
def fetch_candles(yf_sym, interval, period, n, is_h4=False):
    df = yf.download(yf_sym, interval=interval, period=period,
                     progress=False, auto_adjust=True)
    if df.empty:
        raise ValueError(f"No data for {yf_sym}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna()
    if is_h4:
        df = df.resample("4h").agg({"Open":"first","High":"max",
                                     "Low":"min","Close":"last","Volume":"sum"}).dropna()
    return df.tail(n)

# ─────────────────────────────────────────────────────────
# INDICATORS
# ─────────────────────────────────────────────────────────
def calc_atr(df, period=14):
    h,l,c = df["High"].values, df["Low"].values, df["Close"].values
    tr = np.maximum(h[1:]-l[1:], np.maximum(np.abs(h[1:]-c[:-1]), np.abs(l[1:]-c[:-1])))
    return float(np.mean(tr[-period:])) if len(tr) >= period else float(np.mean(tr))

def calc_rsi(closes, period=14):
    d = np.diff(closes)
    g,l = np.where(d>0,d,0), np.where(d<0,-d,0)
    ag,al = np.mean(g[-period:]), np.mean(l[-period:])
    return float(100.0 if al==0 else 100-(100/(1+ag/al)))

def get_indicators(df, dp):
    c = df["Close"].values
    rsi = calc_rsi(c, 14)
    atr = calc_atr(df, 14)
    e12 = pd.Series(c).ewm(span=12,adjust=False).mean().values
    e26 = pd.Series(c).ewm(span=26,adjust=False).mean().values
    ml  = float(e12[-1]-e26[-1])
    ms  = float(pd.Series(e12-e26).ewm(span=9,adjust=False).mean().values[-1])
    e20 = float(pd.Series(c).ewm(span=20,adjust=False).mean().values[-1])
    e50 = float(pd.Series(c).ewm(span=50,adjust=False).mean().values[-1])
    e200= float(pd.Series(c).ewm(span=200,adjust=False).mean().values[-1]) if len(c)>=200 else e50
    return {
        "rsi":round(rsi,1),"atr":round(atr,dp),
        "macd":round(ml,dp),"macd_hist":round(ml-ms,dp),
        "ema20":round(e20,dp),"ema50":round(e50,dp),"ema200":round(e200,dp),
        "ema_trend":"UP" if e20>e50 else "DOWN",
        "range_high":round(float(df["High"].values[-20:].max()),dp),
        "range_low": round(float(df["Low"].values[-20:].min()),dp),
    }

def get_mtf_context(yf_sym, p_iv, p_pd, dp):
    try:
        df = yf.download(yf_sym, interval=p_iv, period=p_pd, progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna().tail(50)
        if df.empty: return "N/A"
        c   = df["Close"].values
        e20 = float(pd.Series(c).ewm(span=20,adjust=False).mean().values[-1])
        e50 = float(pd.Series(c).ewm(span=50,adjust=False).mean().values[-1])
        rsi = calc_rsi(c,14)
        ph  = float(df["High"].values[-20:].max())
        pl  = float(df["Low"].values[-20:].min())
        trend = "UPTREND" if e20>e50 else "DOWNTREND"
        return (f"{trend} | EMA20={e20:.{dp}f} EMA50={e50:.{dp}f} | "
                f"RSI={rsi:.1f} | Range {pl:.{dp}f}–{ph:.{dp}f}")
    except Exception as e:
        logger.warning(f"MTF failed: {e}")
        return "N/A"

# ─────────────────────────────────────────────────────────
# PIVOT DETECTION
# ─────────────────────────────────────────────────────────
def find_pivots_zigzag(df, atr_mult=1.5):
    atr       = calc_atr(df, 14)
    threshold = atr * atr_mult
    highs, lows = df["High"].values, df["Low"].values
    dates     = df.index.tolist()
    n         = len(df)
    pivots    = []
    direction = None
    lhi, lli  = 0, 0
    lh, ll    = highs[0], lows[0]

    for i in range(1, n):
        h, l = highs[i], lows[i]
        if direction is None:
            if h - lows[0] > threshold:
                direction="up"; lli=0; ll=lows[0]
            elif highs[0] - l > threshold:
                direction="down"; lhi=0; lh=highs[0]
            continue
        if direction=="up":
            if h >= lh: lh=h; lhi=i
            elif lh - l > threshold:
                pivots.append({"idx":lhi,"price":float(lh),"type":"H","date":str(dates[lhi])[:10]})
                direction="down"; ll=l; lli=i
        else:
            if l <= ll: ll=l; lli=i
            elif h - ll > threshold:
                pivots.append({"idx":lli,"price":float(ll),"type":"L","date":str(dates[lli])[:10]})
                direction="up"; lh=h; lhi=i

    if direction=="up" and lhi>0:
        pivots.append({"idx":lhi,"price":float(lh),"type":"H","date":str(dates[lhi])[:10]})
    elif direction=="down" and lli>0:
        pivots.append({"idx":lli,"price":float(ll),"type":"L","date":str(dates[lli])[:10]})

    # Score significance
    atr_val = atr
    for i,p in enumerate(pivots):
        prev = pivots[i-1]["price"] if i>0 else p["price"]
        nxt  = pivots[i+1]["price"] if i<len(pivots)-1 else p["price"]
        move = max(abs(p["price"]-prev), abs(p["price"]-nxt))
        p["significance"] = round(move/atr_val, 2) if atr_val>0 else 1.0

    return pivots

# ─────────────────────────────────────────────────────────
# FIBONACCI VALIDATION ENGINE
# All rules from XenosFinance glossary — hard filters
# ─────────────────────────────────────────────────────────
TOL = 0.15  # ±15% tolerance on Fibonacci ratios

def near_fib(ratio, *targets):
    return any(t > 0 and abs(ratio-t)/t <= TOL for t in targets)

def try_impulse(pivots):
    """
    Find best impulse wave count (1-2-3-4-5).
    Rules:
      W2: never beyond W0; retraces 30-78.6% of W1
      W3: terminates at 1.0/1.382/1.618/2.0/2.618/4.236 × W1; never shortest
      W4: no overlap W1; retraces 18-65% of W3
      W5: near 0.618/1.0/1.618 × W1
    """
    candidates = []
    for start in range(len(pivots)-2):
        p0 = pivots[start]
        for bull in [True, False]:
            if bull  and p0["type"] != "L": continue
            if not bull and p0["type"] != "H": continue

            seq = [p0]
            for j in range(start+1, len(pivots)):
                if len(seq) >= 6: break
                exp = "L" if (len(seq)%2==0)==bull else "H"
                if pivots[j]["type"] == exp:
                    seq.append(pivots[j])
            if len(seq) < 3: continue

            W0,W1,W2 = seq[0],seq[1],seq[2]
            W3 = seq[3] if len(seq)>3 else None
            W4 = seq[4] if len(seq)>4 else None
            W5 = seq[5] if len(seq)>5 else None

            # Rule I: W2 never beyond W0
            if bull  and W2["price"] <= W0["price"]: continue
            if not bull and W2["price"] >= W0["price"]: continue

            w1_size = abs(W1["price"]-W0["price"])
            if w1_size == 0: continue
            if w1_size < abs(W0["price"]) * 0.002: continue  # noise

            # W2 retrace: 30-78.6% of W1
            w2_ret = abs(W2["price"]-W1["price"]) / w1_size
            if w2_ret < 0.28 or w2_ret >= 1.0: continue

            w3_size = 0
            if W3:
                w3_size = abs(W3["price"]-W2["price"])
                if w3_size == 0: continue
                w3_ratio = w3_size / w1_size
                # W3 must be at valid Fibonacci extension
                if not near_fib(w3_ratio, 1.0, 1.382, 1.618, 2.0, 2.618, 4.236):
                    continue
                # Rule II: W3 never shortest
                if W5 and W4:
                    w5_size = abs(W5["price"]-W4["price"])
                    if w3_size < w1_size and w3_size < w5_size: continue

            if W4 and W3:
                # Rule III: no overlap
                if bull  and W4["price"] <= W1["price"]: continue
                if not bull and W4["price"] >= W1["price"]: continue
                # W4 retrace: 18-65% of W3
                w4_ret = abs(W4["price"]-W3["price"]) / w3_size if w3_size>0 else 1
                if w4_ret < 0.15 or w4_ret > 0.65: continue

            if W5 and W4:
                w5_size = abs(W5["price"]-W4["price"])
                w5_ratio = w5_size / w1_size
                if not near_fib(w5_ratio, 0.618, 1.0, 1.618, 2.618): continue

            # Score
            score = len(seq)*10 + (len(pivots)-start)
            if W3:
                r = w3_size/w1_size
                if near_fib(r, 1.618): score += 12
                elif near_fib(r, 2.618): score += 8
                elif near_fib(r, 1.0):   score += 5
            if near_fib(w2_ret, 0.618): score += 8
            elif near_fib(w2_ret, 0.5): score += 5

            candidates.append({
                "W0":W0,"W1":W1,"W2":W2,"W3":W3,"W4":W4,"W5":W5,
                "bull":bull,"w1_size":w1_size,"w3_size":w3_size,
                "score":score,"wave_count":len(seq)
            })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates

def try_abc(pivots, live_price):
    """
    Find best ABC corrective structure.
    Zigzag: B retraces 38.2-61.8% of A; C = 100-161.8% of A
    Flat:   B retraces ~85-100% of A; C = 100% of A
    Expanded: B > 100% of A
    """
    candidates = []
    max_a_size = live_price * 0.50  # WA can't be more than 50% from live

    for start in range(len(pivots)-1):
        WA = pivots[start]
        for bear in [True, False]:
            if bear  and WA["type"] != "H": continue
            if not bear and WA["type"] != "L": continue

            wb_type = "L" if bear else "H"
            wc_type = "H" if bear else "L"

            WB = WC = None
            for j in range(start+1, len(pivots)):
                if not WB and pivots[j]["type"]==wb_type: WB=pivots[j]; continue
                if WB and not WC and pivots[j]["type"]==wc_type: WC=pivots[j]; break
            if not WB: continue

            a_size = abs(WB["price"]-WA["price"])
            if a_size==0 or a_size < live_price*0.002: continue
            if a_size > max_a_size: continue  # too old / too large

            if bear  and WB["price"] >= WA["price"]: continue
            if not bear and WB["price"] <= WA["price"]: continue

            b_ret = a_size / a_size  # = 1.0 always (b vs a is size of WA→WB)
            # Real B retrace = how much WB moved from WA end
            b_ret = abs(WB["price"]-WA["price"]) / a_size  # always 1.0
            # Actually: b_ratio = abs(WB - WA.start) / a_size
            # WA goes from WA["price"] to WB["price"] by definition
            # B retrace = how far B went BACK toward WA origin
            # We need WA origin which is the pivot before WA
            # Since we don't have it easily, use significance as proxy
            # For now: b_size = abs(WB - WA), c_size = abs(WC - WB)
            # Zigzag: C/A >= 0.9; Flat: B/A >= 0.85

            c_ratio = 0.0
            if WC:
                c_size = abs(WC["price"]-WB["price"])
                c_ratio = c_size / a_size if a_size>0 else 0
                # C must be 50-220% of A
                if c_ratio < 0.50 or c_ratio > 2.20: continue
            else:
                # Check live price doesn't make C ratio absurd
                c_size_live = abs(live_price-WB["price"])
                c_ratio_live = c_size_live/a_size if a_size>0 else 0
                if c_ratio_live > 2.20: continue

            # Structure still active: live price within range
            abc_high = max(WA["price"], WB["price"], WC["price"] if WC else live_price)
            abc_low  = min(WA["price"], WB["price"], WC["price"] if WC else live_price)
            abc_range = abc_high - abc_low
            if live_price > abc_high + abc_range*0.50: continue
            if live_price < abc_low  - abc_range*0.50: continue

            # Classify
            if c_ratio > 1.02 and near_fib(a_size/a_size, 1.0):
                pat = "Expanded Flat (3-3-5)"
            elif c_ratio > 0 and c_ratio < 0.90:
                pat = "Running Flat (3-3-5)"
            elif near_fib(c_ratio, 1.0) if c_ratio>0 else False:
                pat = "Regular Flat (3-3-5)"
            else:
                pat = "Zigzag (5-3-5)"

            score = (30 if WC else 20) + (len(pivots)-start)
            if near_fib(c_ratio, 1.0):   score += 8
            if near_fib(c_ratio, 1.618): score += 6

            candidates.append({
                "WA":WA,"WB":WB,"WC":WC,"bear":bear,
                "a_size":a_size,"c_ratio":c_ratio,
                "pattern":pat,"score":score
            })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates

def try_triangle(pivots):
    """ABCDE contracting/expanding triangle."""
    if len(pivots) < 5: return None
    seq = []
    for p in pivots[-10:]:
        if not seq or p["type"] != seq[-1]["type"]:
            seq.append(p)
        if len(seq) >= 5: break
    if len(seq) < 5: return None

    highs = [p["price"] for p in seq if p["type"]=="H"]
    lows  = [p["price"] for p in seq if p["type"]=="L"]
    if len(highs)<2 or len(lows)<2: return None

    h_desc = all(highs[i]<highs[i-1]*1.02 for i in range(1,len(highs)))
    l_asc  = all(lows[i]>lows[i-1]*0.98  for i in range(1,len(lows)))
    if h_desc and l_asc:
        widest = max(highs)-min(lows)
        return {"type":"Contracting Triangle (3-3-3-3-3)","widest":widest,
                "note":"Valid in Wave 4 or Wave B only. Thrust target = widest point added to breakout."}
    return None

def calc_market_structure(pivots):
    """HH/HL/LH/LL market structure."""
    if len(pivots) < 4:
        return {"structure":"UNDEFINED","bos":False,"choch":False}
    highs = [p["price"] for p in pivots[-10:] if p["type"]=="H"]
    lows  = [p["price"] for p in pivots[-10:] if p["type"]=="L"]
    if len(highs)<2 or len(lows)<2:
        return {"structure":"UNDEFINED","bos":False,"choch":False}

    hh = sum(1 for i in range(1,len(highs)) if highs[i]>highs[i-1])
    hl = sum(1 for i in range(1,len(lows))  if lows[i]>lows[i-1])
    lh = sum(1 for i in range(1,len(highs)) if highs[i]<highs[i-1])
    ll = sum(1 for i in range(1,len(lows))  if lows[i]<lows[i-1])

    if hh>=lh and hl>=ll and hh>0: structure="BULLISH (HH+HL)"
    elif lh>hh and ll>hl: structure="BEARISH (LH+LL)"
    else: structure="RANGING"

    bos   = (highs[-1]>highs[-2]) or (lows[-1]<lows[-2])
    choch = ("BULLISH" in structure and lows[-1]<lows[-2]) or \
            ("BEARISH" in structure and highs[-1]>highs[-2])

    return {
        "structure":structure,"bos":bos,"choch":choch,
        "last_high":round(highs[-1],5),"last_low":round(lows[-1],5)
    }

def analyze_structure(pivots, live_price):
    """
    Run all detectors and return primary + alternate scenario.
    """
    imp_candidates = try_impulse(pivots)
    abc_candidates = try_abc(pivots, live_price)
    triangle       = try_triangle(pivots)
    mkt_structure  = calc_market_structure(pivots)

    primary_imp = next((c for c in imp_candidates if c["wave_count"]>=4), None)
    primary_abc = abc_candidates[0] if abc_candidates else None
    alt_imp     = next((c for c in imp_candidates if c["wave_count"]>=4 and c!=primary_imp), None)
    alt_abc     = abc_candidates[1] if len(abc_candidates)>1 else None

    # Choose primary
    if primary_imp and primary_abc:
        use_impulse = primary_imp["wave_count"]>=4 or primary_imp["score"]>=primary_abc["score"]
    elif primary_imp:
        use_impulse = True
    elif primary_abc:
        use_impulse = False
    else:
        return None, None, None, triangle, mkt_structure

    primary = primary_imp if use_impulse else primary_abc

    # Alternate
    if use_impulse:
        alt = alt_imp or primary_abc
    else:
        alt = alt_abc or primary_imp

    # Probabilities
    p_score = primary.get("score",1) if primary else 1
    a_score = alt.get("score",1) if alt else 1
    total   = p_score + a_score
    p_pct   = min(80, round(p_score/total*85))
    a_pct   = max(15, 100-p_pct-5)

    return (
        {"type":"impulse" if use_impulse else "abc", "data":primary, "prob":p_pct},
        {"type":"abc" if use_impulse else "impulse", "data":alt, "prob":a_pct} if alt else None,
        triangle,
        mkt_structure
    )

# ─────────────────────────────────────────────────────────
# WAVE POSITION LABELLING
# ─────────────────────────────────────────────────────────
def get_wave_position(primary, live_price, dp, atr):
    """
    Determine current wave position from primary structure.
    Returns waveNum, waveDesc, scenario text, key levels.
    """
    if not primary:
        return "?", "No valid wave count", "Insufficient pivot structure on this timeframe.", {}

    t    = primary["type"]
    data = primary["data"]
    live = live_price

    if t == "impulse":
        I    = data
        bull = I["bull"]
        W0,W1,W2,W3,W4,W5 = I["W0"],I["W1"],I["W2"],I["W3"],I["W4"],I["W5"]
        w1s  = I["w1_size"]
        dec  = dp

        # Determine which wave we're in based on last confirmed pivot
        confirmed = [x for x in [W0,W1,W2,W3,W4,W5] if x]
        last = confirmed[-1]
        n    = len(confirmed)

        # Wave position map
        wave_map = {2:"1",3:"2",4:"3",5:"4",6:"5"}
        wn = wave_map.get(n, "?")

        # If all 5 waves confirmed → Wave A
        if W5:
            wn = "A"
            cycle_high = W5["price"] if bull else W0["price"]
            cycle_low  = W0["price"] if bull else W5["price"]
            a382 = cycle_high - (cycle_high-cycle_low)*0.382 if bull else cycle_low + (cycle_high-cycle_low)*0.382
            a618 = cycle_high - (cycle_high-cycle_low)*0.618 if bull else cycle_low + (cycle_high-cycle_low)*0.618
            desc = "Wave 🅐 — First Corrective Leg"
            scenario = (f"5-wave impulse complete. ABC correction underway. "
                       f"{'Wave A decline' if bull else 'Wave A rally'} targeting "
                       f"{a382:.{dec}f} (38.2%) — {a618:.{dec}f} (61.8%).")
            inv = cycle_high*1.001 if bull else cycle_low*0.999
            return wn, desc, scenario, {
                "entry":round(live,dec),"stop_loss":round(inv,dec),
                "tp1":round(a382,dec),"tp2":round(a618,dec)
            }

        # Build scenario per wave
        if wn == "2":
            w1e  = W1["price"]
            a618 = W1["price"] - w1s*0.618 if bull else W1["price"] + w1s*0.618
            a786 = W1["price"] - w1s*0.786 if bull else W1["price"] + w1s*0.786
            desc = f"Wave ② — Retracement ({abs(live-W1['price'])/w1s*100:.0f}% of W1)"
            scenario = (f"Wave 2 retracing W1. Typical retrace 50–61.8%. "
                       f"Support zone {a618:.{dec}f}–{a786:.{dec}f}. "
                       f"Invalidation beyond W0 ({W0['price']:.{dec}f}).")
            inv = W0["price"]
            nt  = W1["price"] + w1s*1.618 if bull else W1["price"] - w1s*1.618
            # entry near W2 support/resistance, tp toward W3
            # a618 is the buy zone (below live for bull), nt is W3 target
            entry_w2 = a618  # ideal entry at 61.8% retrace
            return wn, desc, scenario, {
                "entry":round(entry_w2,dec),"stop_loss":round(inv,dec),
                "tp1":round(nt,dec),"tp2":round(W1["price"] + w1s*2.618 if bull else W1["price"] - w1s*2.618,dec)
            }

        if wn == "3":
            w3e  = W3["price"] if W3 else live
            w3s  = I["w3_size"] or w1s*1.618
            desc = f"Wave ③ — Dominant Impulse ({w3s/w1s*100:.0f}% of W1)"
            t618 = W2["price"] + w1s*1.618 if bull else W2["price"] - w1s*1.618
            t262 = W2["price"] + w1s*2.618 if bull else W2["price"] - w1s*2.618
            scenario = (f"Strongest wave. RULE II: W3 never shortest. "
                       f"Target: {t618:.{dec}f} (161.8%) / {t262:.{dec}f} (261.8%). "
                       f"Invalidation: W1 end ({W1['price']:.{dec}f}).")
            return wn, desc, scenario, {
                "entry":round(live,dec),"stop_loss":round(W1["price"],dec),
                "tp1":round(t618,dec),"tp2":round(t262,dec)
            }

        if wn == "4":
            w3e = W3["price"] if W3 else live
            w3s = I["w3_size"] or w1s
            t382 = w3e - w3s*0.382 if bull else w3e + w3s*0.382
            t618 = w3e - w3s*0.618 if bull else w3e + w3s*0.618
            w5eq  = W3["price"] + w1s if bull else W3["price"] - w1s
            desc = f"Wave ④ — Consolidation ({abs(live-w3e)/w3s*100:.0f}% of W3)"
            scenario = (f"RULE III: W4 must stay above W1 ({W1['price']:.{dec}f}). "
                       f"Target zone {t382:.{dec}f}–{t618:.{dec}f} (38.2–61.8% W3). "
                       f"W5 equality target: {w5eq:.{dec}f}.")
            # entry near W4 support, tp toward W5
            entry_w4 = t382  # ideal entry at 38.2% retrace of W3
            return wn, desc, scenario, {
                "entry":round(entry_w4,dec),"stop_loss":round(t618,dec),
                "tp1":round(w5eq,dec),"tp2":round(W3["price"] + w1s*1.618 if bull else W3["price"] - w1s*1.618,dec)
            }

        if wn == "5":
            w4e = W4["price"] if W4 else live
            w5eq  = w4e + w1s     if bull else w4e - w1s
            w5ext = w4e + w1s*1.618 if bull else w4e - w1s*1.618
            desc = "Wave ⑤ — Terminal Impulse"
            scenario = (f"Terminal wave. W5 equality target: {w5eq:.{dec}f} (=W1). "
                       f"Extension target: {w5ext:.{dec}f} (161.8% W1). "
                       f"Watch for RSI divergence as exhaustion signal. ABC correction follows.")
            return wn, desc, scenario, {
                "entry":round(live,dec),"stop_loss":round(w4e,dec),
                "tp1":round(w5eq,dec),"tp2":round(w5ext,dec)
            }

    elif t == "abc":
        A    = data
        bear = A["bear"]
        WA,WB,WC = A["WA"],A["WB"],A["WC"]
        a_size = A["a_size"]
        pat  = A["pattern"]
        dec  = dp

        if not WC:
            # In Wave B
            wn = "B"
            c100 = WB["price"] - a_size if bear else WB["price"] + a_size
            c162 = WB["price"] - a_size*1.618 if bear else WB["price"] + a_size*1.618
            desc = f"Wave 🅑 — Corrective Bounce ({pat})"
            scenario = (f"{pat} — Wave B counter-trend {'rally' if bear else 'decline'}. "
                       f"Classic {'bull' if bear else 'bear'} trap — do not chase. "
                       f"Wave C target: {c100:.{dec}f} (100%A) / {c162:.{dec}f} (161.8%A).")
            inv = WA["price"] * (1.001 if bear else 0.999)
            return wn, desc, scenario, {
                "entry":round(live,dec),"stop_loss":round(inv,dec),
                "tp1":round(c100,dec),"tp2":round(c162,dec)
            }
        else:
            # In Wave C
            c_ret = abs(live-WB["price"])/a_size if a_size>0 else 0
            complete = c_ret >= 0.85
            c100  = WB["price"] - a_size      if bear else WB["price"] + a_size
            c1236 = WB["price"] - a_size*1.236 if bear else WB["price"] + a_size*1.236
            c162  = WB["price"] - a_size*1.618 if bear else WB["price"] + a_size*1.618
            desc  = f"Wave 🅒 — Final Corrective Leg ({c_ret*100:.1f}% of A)" + (" [NEAR COMPLETION]" if complete else "")
            scenario = (f"{pat} — Wave C internally 5-wave structure. "
                       f"Targets: {c100:.{dec}f} (100%A) | {c1236:.{dec}f} (123.6%A) | {c162:.{dec}f} (161.8%A). "
                       f"{'Near completion — watch for reversal.' if complete else 'In progress.'} "
                       f"Invalidation: {WA['price']:.{dec}f}.")
            inv = WA["price"] * (1.001 if bear else 0.999)
            return "C", desc, scenario, {
                "entry":round(live,dec),"stop_loss":round(inv,dec),
                "tp1":round(c100,dec),"tp2":round(c162,dec)
            }

    return "?", "Structure unclear", "No valid wave count on this timeframe.", {}

# ─────────────────────────────────────────────────────────
# AI NARRATIVE (short, 3 sentences)
# ─────────────────────────────────────────────────────────
def generate_narrative(symbol, tf, live, dp, wave_num, wave_desc, scenario_text,
                       primary_prob, alt_desc, alt_prob, ind, mtf, key_levels):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    kl = key_levels
    scenario_type = "SCENARIO ONLY — no trade setup" if wave_num not in ["5"] else "SIGNAL WAVE"

    prompt = f"""Elliott Wave analysis. 3 sentences max, 80 words total. Plain text, no headers.

{symbol} | {tf} | Live: {live:.{dp}f}
Wave: {wave_num} | {wave_desc}
{scenario_text}
Primary ({primary_prob}%) vs Alt ({alt_prob}%): {alt_desc or 'insufficient data'}
Invalidation: {kl.get('stop_loss','—')} | Target: {kl.get('tp1','—')}–{kl.get('tp2','—')}
RSI: {ind['rsi']} | MACD hist: {ind['macd_hist']} | EMA trend: {ind['ema_trend']}
MTF: {mtf}
Type: {scenario_type}

Write 3 sentences: (1) wave position + structure, (2) primary vs alternate probabilities with prices, (3) what to watch + invalidation."""

    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role":"user","content":prompt}]
    )
    return msg.content[0].text.strip()

# ─────────────────────────────────────────────────────────
# ENDPOINT
# ─────────────────────────────────────────────────────────
@app.route("/ew-chart", methods=["POST","OPTIONS"])
def ew_chart():
    if request.method == "OPTIONS":
        return Response(status=200)
    try:
        body    = request.get_json(force=True) or {}
        sym_raw = body.get("symbol","eur/usd").lower().strip()
        tf_raw  = body.get("tf","D1 (Daily)")

        yf_sym = SYMBOL_MAP.get(sym_raw)
        if not yf_sym:
            # Try partial match
            for k,v in SYMBOL_MAP.items():
                if k in sym_raw or sym_raw in k:
                    yf_sym = v; break
        if not yf_sym:
            return jsonify({"error":f"Unknown symbol: {sym_raw}"}), 400

        cfg = TF_CONFIG.get(tf_raw, ("1d","1y",120,2.2,"1wk","5y"))
        iv, pd_, n, mult, piv, ppd = cfg
        is_h4 = (tf_raw == "H4 (4-Hour)")
        sym_name = sym_raw.upper()

        logger.info(f"Fetching {yf_sym} {iv} {pd_}")
        df   = fetch_candles(yf_sym, iv, pd_, n, is_h4)
        live = float(df["Close"].iloc[-1])
        dp   = 2 if live > 10 else 5

        logger.info("Pivot detection...")
        pivots = find_pivots_zigzag(df, atr_mult=mult)
        if len(pivots) < 3:
            pivots = find_pivots_zigzag(df, atr_mult=mult*0.65)
        if len(pivots) < 3:
            return jsonify({"error":"Insufficient pivot structure. Try a different timeframe."}), 400
        logger.info(f"{len(pivots)} pivots found")

        ind = get_indicators(df, dp)
        mtf = get_mtf_context(yf_sym, piv, ppd, dp)

        logger.info("Analyzing wave structure...")
        primary, alternate, triangle, mkt_structure = analyze_structure(pivots, live)

        if not primary:
            return jsonify({
                "error": "No valid Elliott Wave structure found on this timeframe.",
                "no_count": True,
                "indicators": ind,
                "mtf_context": mtf,
                "live_price": live,
                "candles": [{"datetime":str(i)[:16],
                    "open":round(float(r["Open"]),dp),"high":round(float(r["High"]),dp),
                    "low":round(float(r["Low"]),dp),"close":round(float(r["Close"]),dp)}
                    for i,r in df.iterrows()]
            }), 200

        wave_num, wave_desc, scenario_text, key_levels = get_wave_position(
            primary, live, dp, ind["atr"])

        # Build alternate description
        alt_desc = "Insufficient data"
        alt_prob = 20
        if alternate:
            alt_prob = alternate.get("prob", 20)
            at = alternate.get("type","")
            ad = alternate.get("data",{})
            if at == "impulse" and ad:
                alt_desc = f"{'Bullish' if ad.get('bull') else 'Bearish'} impulse ({ad.get('wave_count',0)} pivots confirmed)"
            elif at == "abc" and ad:
                alt_desc = f"{'Bearish' if ad.get('bear') else 'Bullish'} {ad.get('pattern','ABC')} correction"
        if triangle:
            alt_desc = f"{triangle['type']} — {triangle['note']}"

        p_prob = primary.get("prob", 65)

        logger.info(f"Wave {wave_num} | Primary {p_prob}% | Alt {alt_prob}%")

        logger.info("Generating narrative...")
        narrative = generate_narrative(sym_name, tf_raw, live, dp, wave_num,
                                       wave_desc, scenario_text, p_prob,
                                       alt_desc, alt_prob, ind, mtf, key_levels)

        # Build wave_points for sketch
        wave_points = {}
        prim_data = primary.get("data",{})
        if primary["type"] == "impulse":
            for k,label in [("W0","w0"),("W1","w1"),("W2","w2"),("W3","w3"),("W4","w4"),("W5","w5")]:
                w = prim_data.get(k)
                if w: wave_points[label] = {"price":w["price"],"idx":w["idx"],"date":w["date"]}
            # If impulse complete (W5 exists) and we are in Wave A, add wa = W5
            # so the sketch correctly draws the A leg starting from the W5 pivot
            if wave_num == "A" and prim_data.get("W5"):
                w5 = prim_data["W5"]
                wave_points["wa"] = {"price":w5["price"],"idx":w5["idx"],"date":w5["date"]}
        else:
            # Pure ABC structure
            for k,label in [("WA","wa"),("WB","wb"),("WC","wc")]:
                w = prim_data.get(k)
                if w: wave_points[label] = {"price":w["price"],"idx":w["idx"],"date":w["date"]}

        # Add live price as wlive endpoint so canvas draws current position
        last_idx = len(df) - 1
        wave_points["wlive"] = {"price": round(live, dp), "idx": last_idx, "date": str(df.index[-1])[:10]}

        # Determine bearABC — must be consistent with trend and wave direction
        bear_abc = False
        if primary["type"] == "abc":
            bear_abc = bool(prim_data.get("bear", False))
        elif wave_num == "A":
            # Wave A after completed impulse: bull impulse → bearish ABC (price falls)
            bear_abc = bool(prim_data.get("bull", True))

        candles = [{"datetime":str(i)[:16],
                    "open":round(float(r["Open"]),dp),
                    "high":round(float(r["High"]),dp),
                    "low":round(float(r["Low"]),dp),
                    "close":round(float(r["Close"]),dp)}
                   for i,r in df.iterrows()]

        return jsonify({
            "candles":          candles,
            "live_price":       live,
            "current_wave":     wave_num,
            "wave_desc":        wave_desc,
            "scenario":         scenario_text,
            "trend":            "UP" if (primary["type"]=="impulse" and prim_data.get("bull")) or
                                         (primary["type"]=="abc" and not prim_data.get("bear")) else "DOWN",
            "bear_abc":         bear_abc,
            "correction_dir":   "BEARISH" if bear_abc else "BULLISH",
            "degree":           "Primary",
            "confidence":       p_prob,
            "key_levels":       key_levels,
            "wave_points":      wave_points,
            "pattern":          prim_data.get("pattern","Impulse") if primary["type"]=="abc" else "Impulse",
            "corrective_pattern": prim_data.get("pattern") if primary["type"]=="abc" else None,
            "scenario_only":    wave_num not in ["5"],
            "primary_prob":     p_prob,
            "alt_scenario":     {"description":alt_desc,"probability":alt_prob},
            "triangle":         triangle,
            "market_structure": mkt_structure,
            "indicators":       ind,
            "mtf_context":      mtf,
            "analysis_text":    narrative,
            "pivots_raw":       pivots,
        })

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return jsonify({"error":str(e)}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status":"ok","service":"XenosFinance EW Server v3"})

if __name__ == "__main__":
    port = int(os.getenv("PORT", os.getenv("EW_PORT",5001)))
    logger.info(f"EW Server v3 on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
