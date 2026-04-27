#!/usr/bin/env python3
"""
XenosFinance — Elliott Wave Chart Server v2
ATR-based ZigZag + pivot quality scoring + MTF context + improved AI prompt
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
    "gold":"GC=F","xauusd":"GC=F",
    "silver":"SI=F","xagusd":"SI=F",
    "oil wti":"CL=F","usoil":"CL=F","wti":"CL=F",
    "nat gas":"NG=F","ngas":"NG=F",
    "btc/usd":"BTC-USD","btcusd":"BTC-USD","bitcoin":"BTC-USD",
    "eth/usd":"ETH-USD","ethusd":"ETH-USD",
    "s&p 500":"SPY","spx500":"SPY","sp500":"SPY",
    "nasdaq":"^IXIC","dax":"^GDAXI","ftse 100":"^FTSE",
}

# (interval, period, n_candles, atr_mult, parent_interval, parent_period)
TF_CONFIG = {
    "M5 (5-Min)":   ("5m",  "5d",   100, 0.8, "1h",  "14d"),
    "M15 (15-Min)": ("15m", "14d",  100, 0.9, "1h",  "30d"),
    "M30 (30-Min)": ("30m", "30d",  100, 1.0, "4h",  "60d"),
    "H1 (1-Hour)":  ("1h",  "30d",  90,  1.2, "1d",  "90d"),
    "H4 (4-Hour)":  ("1h",  "60d",  80,  1.8, "1d",  "180d"),
    "D1 (Daily)":   ("1d",  "2y",   120, 2.2, "1wk", "5y"),
    "W1 (Weekly)":  ("1wk", "5y",   100, 2.8, "1mo", "10y"),
}

# ── Data fetcher ───────────────────────────────────────────────────────────────
def fetch_candles(yf_sym, interval, period, n):
    df = yf.download(yf_sym, interval=interval, period=period,
                     progress=False, auto_adjust=True)
    if df.empty:
        raise ValueError(f"No data for {yf_sym}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna()
    if interval == "1h" and period == "60d":
        df = df.resample("4h").agg({"Open":"first","High":"max",
                                     "Low":"min","Close":"last","Volume":"sum"}).dropna()
    return df.tail(n)

# ── ATR ───────────────────────────────────────────────────────────────────────
def calc_atr(df, period=14):
    h, l, c = df["High"].values, df["Low"].values, df["Close"].values
    tr = np.maximum(h[1:]-l[1:], np.maximum(np.abs(h[1:]-c[:-1]), np.abs(l[1:]-c[:-1])))
    return float(np.mean(tr[-period:])) if len(tr) >= period else float(np.mean(tr))

# ── RSI ───────────────────────────────────────────────────────────────────────
def calc_rsi(closes, period=14):
    d = np.diff(closes)
    g, l = np.where(d>0,d,0), np.where(d<0,-d,0)
    ag, al = np.mean(g[-period:]), np.mean(l[-period:])
    return float(100.0 if al==0 else 100-(100/(1+ag/al)))

# ── ATR-based ZigZag ──────────────────────────────────────────────────────────
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
                direction = "up"; lli = 0; ll = lows[0]
            elif highs[0] - l > threshold:
                direction = "down"; lhi = 0; lh = highs[0]
            continue

        if direction == "up":
            if h >= lh: lh = h; lhi = i
            elif lh - l > threshold:
                pivots.append({"idx":lhi,"price":float(lh),"type":"high","date":dates[lhi]})
                direction = "down"; ll = l; lli = i
        else:
            if l <= ll: ll = l; lli = i
            elif h - ll > threshold:
                pivots.append({"idx":lli,"price":float(ll),"type":"low","date":dates[lli]})
                direction = "up"; lh = h; lhi = i

    # Add last pending pivot
    if direction == "up" and lhi > 0:
        pivots.append({"idx":lhi,"price":float(lh),"type":"high","date":dates[lhi]})
    elif direction == "down" and lli > 0:
        pivots.append({"idx":lli,"price":float(ll),"type":"low","date":dates[lli]})

    return pivots[-7:] if len(pivots) >= 3 else []

# ── Score pivots by significance ──────────────────────────────────────────────
def score_pivots(pivots, df):
    atr = calc_atr(df, 14)
    for i, p in enumerate(pivots):
        prev_p = pivots[i-1]["price"] if i > 0 else p["price"]
        next_p = pivots[i+1]["price"] if i < len(pivots)-1 else p["price"]
        move   = max(abs(p["price"]-prev_p), abs(p["price"]-next_p))
        p["significance"] = round(move/atr, 2)
    return pivots

# ── Technical indicators ──────────────────────────────────────────────────────
def get_indicators(df, dp):
    c  = df["Close"].values
    h  = df["High"].values
    l  = df["Low"].values
    rsi = calc_rsi(c, 14)
    atr = calc_atr(df, 14)
    e12 = pd.Series(c).ewm(span=12,adjust=False).mean().values
    e26 = pd.Series(c).ewm(span=26,adjust=False).mean().values
    ml  = e12[-1]-e26[-1]
    ms  = pd.Series(e12-e26).ewm(span=9,adjust=False).mean().values[-1]
    e20 = float(pd.Series(c).ewm(span=20,adjust=False).mean().values[-1])
    e50 = float(pd.Series(c).ewm(span=50,adjust=False).mean().values[-1])
    return {
        "rsi": round(rsi,1), "atr": round(atr,dp),
        "macd": round(float(ml),dp), "macd_hist": round(float(ml-ms),dp),
        "ema20": round(e20,dp), "ema50": round(e50,dp),
        "ema_trend": "UP" if e20>e50 else "DOWN",
        "range_high": round(float(np.max(h[-20:])),dp),
        "range_low":  round(float(np.min(l[-20:])),dp),
    }

# ── MTF context ───────────────────────────────────────────────────────────────
def get_mtf_context(yf_sym, p_iv, p_pd, dp):
    try:
        df = yf.download(yf_sym, interval=p_iv, period=p_pd,
                         progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna().tail(50)
        if df.empty: return "N/A"
        c   = df["Close"].values
        e20 = float(pd.Series(c).ewm(span=20,adjust=False).mean().values[-1])
        e50 = float(pd.Series(c).ewm(span=50,adjust=False).mean().values[-1])
        rsi = calc_rsi(c, 14)
        ph  = float(df["High"].values[-20:].max())
        pl  = float(df["Low"].values[-20:].min())
        trend = "UPTREND" if e20>e50 else "DOWNTREND"
        return (f"{trend} | EMA20={e20:.{dp}f} EMA50={e50:.{dp}f} | "
                f"RSI={rsi:.1f} | 20-bar range {pl:.{dp}f}-{ph:.{dp}f}")
    except Exception as e:
        logger.warning(f"MTF failed: {e}")
        return "N/A"

# ── AI wave labelling ─────────────────────────────────────────────────────────
def label_waves_with_ai(pivots, symbol, tf, live, dp, ind, mtf):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    ptext = "\n".join([
        f"Pivot {i}: idx={p['idx']}, price={p['price']:.{dp}f}, "
        f"type={p['type']}, date={str(p['date'])[:10]}, "
        f"significance={p.get('significance','?')}x ATR"
        for i,p in enumerate(pivots)
    ])

    prompt = f"""You are a professional Elliott Wave analyst.

SYMBOL: {symbol} | TF: {tf} | LIVE PRICE: {live:.{dp}f}

PARENT TF CONTEXT: {mtf}

INDICATORS:
RSI(14)={ind['rsi']} {'[OVERBOUGHT]' if ind['rsi']>70 else '[OVERSOLD]' if ind['rsi']<30 else '[NEUTRAL]'}
MACD={ind['macd']:.{dp}f} | Histogram={ind['macd_hist']:.{dp}f} {'[BULL MOMENTUM]' if ind['macd_hist']>0 else '[BEAR MOMENTUM]'}
EMA20={ind['ema20']:.{dp}f} | EMA50={ind['ema50']:.{dp}f} | EMA Bias={ind['ema_trend']}
ATR(14)={ind['atr']:.{dp}f}

ATR-ZIGZAG PIVOTS (each reversed by >{ind['atr']:.{dp}f}):
{ptext}

RULES:
1. Label pivots: IMPULSE=5-wave (1,2,3,4,5) | CORRECTIVE=3-wave (A,B,C)
2. EW validation:
   - W2 cannot retrace beyond W0
   - W3 must be longest impulse wave
   - W4 cannot overlap W1 (except diagonal)
   - If RSI diverges at W5 high/low → confidence -20
3. Use parent TF bias to confirm direction
4. SIGNAL must match wave:
   - Impulse UP waves 1-4: LONG | W5+RSI_div: WAIT
   - Impulse DOWN waves 1-4: SHORT | W5+RSI_div: WAIT
   - ABC bear (post-uptrend): WAIT(A), SHORT(B top), WAIT(C)
   - ABC bull (post-downtrend): WAIT(A), LONG(B low), WAIT(C)
5. key_levels.tp1 and tp2 MUST be in signal direction vs {live:.{dp}f}

JSON ONLY (no markdown):
{{
  "pattern":"Impulse",
  "trend":"UP",
  "current_wave":"3",
  "degree":"Minor",
  "confidence":75,
  "wave_points":[
    {{"label":"1","idx":0,"price":0.0,"type":"low"}},
    {{"label":"2","idx":0,"price":0.0,"type":"high"}},
    {{"label":"3","idx":0,"price":0.0,"type":"low"}}
  ],
  "key_levels":{{"entry":{live:.{dp}f},"stop_loss":0.0,"tp1":0.0,"tp2":0.0}},
  "signal":"LONG",
  "analysis_text":"5-7 sentences: wave position, EW rules, RSI/MACD context, MTF alignment, trade rationale, key risk."
}}"""

    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role":"user","content":prompt}]
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]
    result = json.loads(raw.strip())

    # ── Coherence validation ──────────────────────────────────────────────────
    pattern = result.get("pattern","").lower()
    cw      = str(result.get("current_wave","")).upper()
    trend   = result.get("trend","UP")
    signal  = result.get("signal","WAIT")
    kl      = result.get("key_levels",{})
    tp1     = float(kl.get("tp1",0) or 0)
    tp2     = float(kl.get("tp2",0) or 0)

    if "corrective" in pattern or cw in ["A","B","C"]:
        if trend=="DOWN" and signal=="LONG":
            result["signal"] = "WAIT"; signal = "WAIT"
        elif trend=="UP" and signal=="SHORT":
            result["signal"] = "WAIT"; signal = "WAIT"

    if signal=="LONG":
        if tp1 <= live: result["key_levels"]["tp1"] = round(live*1.008,dp)
        if tp2 <= live: result["key_levels"]["tp2"] = round(live*1.018,dp)
    elif signal=="SHORT":
        if tp1 >= live: result["key_levels"]["tp1"] = round(live*0.992,dp)
        if tp2 >= live: result["key_levels"]["tp2"] = round(live*0.982,dp)

    return result

# ── Endpoint ──────────────────────────────────────────────────────────────────
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
            return jsonify({"error":f"Unknown symbol: {sym_raw}"}), 400

        cfg = TF_CONFIG.get(tf_raw, ("1d","2y",120,2.2,"1wk","5y"))
        iv, pd_, n, mult, piv, ppd = cfg
        sym_name = sym_raw.upper()

        logger.info(f"Fetching {yf_sym} {iv} {pd_}")
        df   = fetch_candles(yf_sym, iv, pd_, n)
        live = float(df["Close"].iloc[-1])
        dp   = 2 if live > 10 else 5

        logger.info("ZigZag pivot detection...")
        pivots = find_pivots_zigzag(df, atr_mult=mult)
        if len(pivots) < 3:
            logger.warning("Reducing ATR threshold...")
            pivots = find_pivots_zigzag(df, atr_mult=mult*0.6)
        if len(pivots) < 3:
            return jsonify({"error":"Insufficient pivot structure. Try a different timeframe."}), 400

        pivots = score_pivots(pivots, df)
        logger.info(f"{len(pivots)} pivots found")

        ind = get_indicators(df, dp)

        logger.info("Fetching MTF context...")
        mtf = get_mtf_context(yf_sym, piv, ppd, dp)

        logger.info("AI labelling...")
        ai  = label_waves_with_ai(pivots, sym_name, tf_raw, live, dp, ind, mtf)
        kl  = ai.get("key_levels", {})

        candles = [{"datetime":str(i)[:16],
                    "open":round(float(r["Open"]),dp),
                    "high":round(float(r["High"]),dp),
                    "low":round(float(r["Low"]),dp),
                    "close":round(float(r["Close"]),dp)}
                   for i,r in df.iterrows()]

        return jsonify({
            "candles":      candles,
            "pattern":      ai.get("pattern"),
            "trend":        ai.get("trend"),
            "current_wave": ai.get("current_wave"),
            "degree":       ai.get("degree"),
            "confidence":   ai.get("confidence"),
            "signal":       ai.get("signal"),
            "key_levels":   kl,
            "live_price":   live,
            "analysis_text":ai.get("analysis_text",""),
            "wave_points":  ai.get("wave_points",[]),
            "indicators":   ind,
            "mtf_context":  mtf,
        })

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return jsonify({"error":str(e)}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status":"ok","service":"XenosFinance EW Server v2"})

if __name__ == "__main__":
    port = int(os.getenv("PORT", os.getenv("EW_PORT",5001)))
    logger.info(f"EW Server v2 starting on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
