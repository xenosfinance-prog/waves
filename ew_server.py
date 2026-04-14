#!/usr/bin/env python3
"""
XenosFinance — Elliott Wave Chart Server
Runs as a separate service on Railway alongside bot.py.
Endpoint: POST /ew-chart
Returns: HTML page with Plotly candlestick + EW wave overlay
"""

import os
import json
import logging
import anthropic
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EWServer")

app = Flask(__name__)
CORS(app)  # Allow all origins

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── Symbol map ─────────────────────────────────────────────────────────────────
SYMBOL_MAP = {
    "eur/usd": "EURUSD=X", "eurusd": "EURUSD=X",
    "gbp/usd": "GBPUSD=X", "gbpusd": "GBPUSD=X",
    "usd/jpy": "USDJPY=X", "usdjpy": "USDJPY=X",
    "gold":    "GC=F",     "xauusd": "GC=F",
    "silver":  "SI=F",     "xagusd": "SI=F",
    "oil wti": "CL=F",     "usoil":  "CL=F",
    "nat gas": "NG=F",
    "btc/usd": "BTC-USD",  "btcusd": "BTC-USD",
    "eth/usd": "ETH-USD",  "ethusd": "ETH-USD",
    "s&p 500": "SPY",      "spx500": "SPY",
    "nasdaq":  "^IXIC",
    "dax":     "^GDAXI",
    "ftse 100":"^FTSE",
}

TF_MAP = {
    "H1 (1-Hour)":  ("1h",  "14d"),
    "H4 (4-Hour)":  ("1h",  "60d"),
    "D1 (Daily)":   ("1d",  "1y"),
    "W1 (Weekly)":  ("1wk", "3y"),
}

# ── Candle fetcher ─────────────────────────────────────────────────────────────
def fetch_candles(yf_symbol: str, interval: str, period: str) -> pd.DataFrame:
    df = yf.download(yf_symbol, interval=interval, period=period, progress=False, auto_adjust=True)
    if df.empty:
        raise ValueError(f"No data for {yf_symbol}")
    df = df.dropna()
    # Aggregate to H4 if needed
    if interval == "1h" and period == "60d":
        df = df.resample("4h").agg({
            "Open":  "first",
            "High":  "max",
            "Low":   "min",
            "Close": "last",
            "Volume":"sum"
        }).dropna()
    return df.tail(80)

# ── Swing pivot detection ──────────────────────────────────────────────────────
def find_pivots(df: pd.DataFrame, window: int = 5) -> list:
    highs = df["High"].values
    lows  = df["Low"].values
    dates = df.index.tolist()
    raw = []

    for i in range(window, len(df) - window):
        is_high = all(highs[i] > highs[i-j] for j in range(1, window+1)) and \
                  all(highs[i] > highs[i+j] for j in range(1, window+1))
        is_low  = all(lows[i]  < lows[i-j]  for j in range(1, window+1)) and \
                  all(lows[i]  < lows[i+j]  for j in range(1, window+1))
        if is_high:
            raw.append({"idx": i, "price": float(highs[i]), "type": "high", "date": dates[i]})
        if is_low:
            raw.append({"idx": i, "price": float(lows[i]),  "type": "low",  "date": dates[i]})

    # Enforce alternation — keep most extreme of consecutive same-type
    alt = []
    for p in sorted(raw, key=lambda x: x["idx"]):
        if not alt or alt[-1]["type"] != p["type"]:
            alt.append(p)
        elif p["type"] == "high" and p["price"] > alt[-1]["price"]:
            alt[-1] = p
        elif p["type"] == "low" and p["price"] < alt[-1]["price"]:
            alt[-1] = p

    return alt[-7:]  # last 7 pivots max

# ── AI wave labelling ──────────────────────────────────────────────────────────
def label_waves_with_ai(pivots: list, symbol: str, tf: str, live_price: float, dp: int) -> dict:
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    pivot_text = "\n".join([
        f"Pivot {i}: idx={p['idx']}, price={p['price']:.{dp}f}, type={p['type']}, date={str(p['date'])[:10]}"
        for i, p in enumerate(pivots)
    ])

    prompt = f"""You are a professional Elliott Wave analyst.

The following swing pivots have been mathematically detected from real {symbol} {tf} price data.
These are REAL alternating swing highs and lows.

DETECTED PIVOTS:
{pivot_text}

Current live price: {live_price:.{dp}f}

YOUR TASK: Assign Elliott Wave labels to these pivots.

STRICT RULES:
1. Use ALL pivots listed — do not skip any
2. For IMPULSE (5 pivots): labels must be 1,2,3,4,5 in chronological order
3. For CORRECTIVE (3 pivots): labels must be A,B,C in chronological order  
4. idx, price, type must be EXACTLY as shown — do not change them
5. EW rules: wave 2 cannot go beyond wave 0/start, wave 3 cannot be shortest, wave 4 cannot enter wave 1 territory
6. "signal": LONG if last wave points up, SHORT if points down, WAIT if unclear
7. "invalidation": the price level that invalidates the count
8. "tp1": conservative target, "tp2": extended target

Respond ONLY with valid JSON, no markdown:
{{
  "pattern": "Impulse",
  "trend": "UP",
  "current_wave": "5",
  "degree": "Minor",
  "confidence": 78,
  "wave_points": [
    {{"label":"1","idx":5,"price":1.0820,"type":"low"}},
    {{"label":"2","idx":18,"price":1.0950,"type":"high"}},
    {{"label":"3","idx":26,"price":1.0865,"type":"low"}},
    {{"label":"4","idx":48,"price":1.1120,"type":"high"}},
    {{"label":"5","idx":57,"price":1.1010,"type":"low"}}
  ],
  "invalidation": 1.0819,
  "tp1": 1.1250,
  "tp2": 1.1380,
  "signal": "LONG",
  "narrative": "3 sentences: wave structure, key risk, levels to watch. Plain text only."
}}"""

    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = msg.content[0].text.strip()
    # Strip markdown if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())

# ── Plotly chart builder ───────────────────────────────────────────────────────
def build_plotly_chart(df: pd.DataFrame, ai_result: dict, symbol: str, tf: str, dp: int) -> str:
    dates  = df.index.tolist()
    is_bull = ai_result.get("trend") == "UP"
    wave_pts = ai_result.get("wave_points", [])
    kl = ai_result
    signal  = ai_result.get("signal", "WAIT")
    live_price = float(df["Close"].iloc[-1])

    # Wave colors
    IMPULSE_COLOR  = "#3b82f6"   # blue
    CORRECTIVE_COLOR = "#f59e0b" # amber

    # Determine color per segment
    impulse_labels = {"1","3","5"} if ai_result.get("pattern") == "Impulse" else set()
    corrective_labels = {"2","4","A","C"}

    # ── Candlestick ────────────────────────────────────────────────────────────
    candle = go.Candlestick(
        x=dates,
        open=df["Open"].values,
        high=df["High"].values,
        low=df["Low"].values,
        close=df["Close"].values,
        name=symbol,
        increasing=dict(line=dict(color="#10b981"), fillcolor="rgba(16,185,129,0.7)"),
        decreasing=dict(line=dict(color="#ef4444"), fillcolor="rgba(239,68,68,0.7)"),
        whiskerwidth=0.3,
        showlegend=False,
    )

    # ── Wave zigzag ────────────────────────────────────────────────────────────
    wave_x = [dates[p["idx"]] for p in wave_pts if p["idx"] < len(dates)]
    wave_y = [p["price"] for p in wave_pts if p["idx"] < len(dates)]
    wave_labels_text = [f"({p['label']})" for p in wave_pts if p["idx"] < len(dates)]

    zigzag = go.Scatter(
        x=wave_x,
        y=wave_y,
        mode="lines+markers+text",
        name="Elliott Wave",
        line=dict(color=IMPULSE_COLOR if is_bull else CORRECTIVE_COLOR, width=2.5),
        marker=dict(
            size=10,
            color=[IMPULSE_COLOR if p["label"] in {"1","3","5"} else CORRECTIVE_COLOR for p in wave_pts if p["idx"] < len(dates)],
            line=dict(color="#0f1724", width=2),
        ),
        text=wave_labels_text,
        textposition=["top center" if p["type"] == "high" else "bottom center" for p in wave_pts if p["idx"] < len(dates)],
        textfont=dict(size=14, color=IMPULSE_COLOR if is_bull else CORRECTIVE_COLOR, family="Arial Black"),
        hovertemplate="Wave %{text}<br>%{y}<extra></extra>",
        showlegend=False,
    )

    # ── Horizontal level lines ─────────────────────────────────────────────────
    sl  = kl.get("invalidation")
    tp1 = kl.get("tp1")
    tp2 = kl.get("tp2")

    shapes = []
    level_annotations = []

    def add_level(price, color, label):
        if not price:
            return
        shapes.append(dict(
            type="line", x0=dates[0], x1=dates[-1], y0=price, y1=price,
            line=dict(color=color, width=1, dash="dash"), opacity=0.6
        ))
        level_annotations.append(dict(
            x=dates[-1], y=price, xanchor="left", text=f" {label} {price:.{dp}f}",
            font=dict(color=color, size=10, family="IBM Plex Mono"),
            showarrow=False, xref="x", yref="y"
        ))

    add_level(live_price, "#00d4ff", "NOW")
    add_level(sl,         "#ef4444", "SL ")
    add_level(tp1,        "#10b981", "TP1")
    add_level(tp2,        "#059669", "TP2")

    # ── Wave label annotations ─────────────────────────────────────────────────
    wave_annotations = []
    for p in wave_pts:
        if p["idx"] >= len(dates):
            continue
        is_high = p["type"] == "high"
        col = IMPULSE_COLOR if p["label"] in {"1","3","5"} else CORRECTIVE_COLOR
        wave_annotations.append(dict(
            x=dates[p["idx"]],
            y=p["price"],
            xref="x", yref="y",
            text=f"<b>({p['label']})</b>",
            showarrow=True,
            arrowhead=0,
            arrowcolor=col,
            arrowwidth=1.5,
            ax=0,
            ay=-30 if is_high else 30,
            font=dict(size=14, color=col, family="Arial Black"),
            bgcolor="rgba(9,15,26,0.85)",
            bordercolor=col,
            borderwidth=1,
            borderpad=4,
        ))

    # ── Layout ─────────────────────────────────────────────────────────────────
    sig_color = "#00e676" if signal == "LONG" else "#ff3d5a" if signal == "SHORT" else "#f59e0b"
    sig_text  = "▲ LONG" if signal == "LONG" else "▼ SHORT" if signal == "SHORT" else "◆ WAIT"
    trend_color = "#34d399" if is_bull else "#f87171"
    trend_text  = "▲ TREND UP" if is_bull else "▼ TREND DOWN"

    layout = go.Layout(
        paper_bgcolor="#0d1520",
        plot_bgcolor="#090f1a",
        font=dict(family="IBM Plex Mono, monospace", color="#c8d8ea", size=11),
        margin=dict(l=60, r=120, t=50, b=40),
        xaxis=dict(
            rangeslider=dict(visible=False),
            gridcolor="#1a2a40", gridwidth=0.5,
            linecolor="#1e3050",
            tickfont=dict(size=9, color="#4a6a8a"),
            type="date",
        ),
        yaxis=dict(
            gridcolor="#1a2a40", gridwidth=0.5,
            linecolor="#1e3050",
            tickfont=dict(size=9, color="#4a6a8a"),
            tickformat=f".{dp}f",
            side="left",
        ),
        showlegend=False,
        shapes=shapes,
        annotations=wave_annotations + level_annotations + [
            dict(x=0.01, y=0.99, xref="paper", yref="paper",
                 text=f"<b><span style='color:#3b82f6'>XENOS</span>FINANCE</b>  ·  {symbol}  ·  {tf}",
                 font=dict(size=12, family="IBM Plex Mono"), showarrow=False,
                 align="left", bgcolor="rgba(9,15,26,0.7)", borderpad=6),
            dict(x=0.5, y=0.99, xref="paper", yref="paper",
                 text=f"<b><span style='color:{trend_color}'>{trend_text}</span></b>",
                 font=dict(size=11), showarrow=False, align="center"),
            dict(x=0.99, y=0.99, xref="paper", yref="paper",
                 text=f"<b><span style='color:{sig_color}'>{sig_text}</span></b>",
                 font=dict(size=12), showarrow=False, align="right"),
        ],
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#0d1520", bordercolor="#1e3050",
            font=dict(family="IBM Plex Mono", size=11, color="#c8d8ea")
        ),
        dragmode="pan",
        height=480,
    )

    fig = go.Figure(data=[candle, zigzag], layout=layout)

    # Return full HTML with config
    html = fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        config=dict(
            responsive=True,
            displaylogo=False,
            scrollZoom=True,
            modeBarButtonsToRemove=["autoScale2d", "lasso2d", "select2d"],
        )
    )
    return html

# ── Main endpoint ──────────────────────────────────────────────────────────────
@app.route("/ew-chart", methods=["POST", "OPTIONS"])
def ew_chart():
    if request.method == "OPTIONS":
        return Response(status=200)

    try:
        body       = request.get_json(force=True) or {}
        symbol_raw = body.get("symbol", "eur/usd").lower().strip()
        tf_raw     = body.get("tf", "D1 (Daily)")

        yf_sym = SYMBOL_MAP.get(symbol_raw)
        if not yf_sym:
            return jsonify({"error": f"Unknown symbol: {symbol_raw}"}), 400

        interval, period = TF_MAP.get(tf_raw, ("1d", "1y"))
        symbol_name = symbol_raw.upper()

        # 1. Fetch candles
        logger.info(f"Fetching candles: {yf_sym} {interval} {period}")
        df = fetch_candles(yf_sym, interval, period)

        live_price = float(df["Close"].iloc[-1])
        dp = 2 if live_price > 100 else 5

        # 2. Find pivots mathematically
        logger.info("Finding swing pivots...")
        pivots = find_pivots(df, window=5)
        if len(pivots) < 3:
            return jsonify({"error": "Not enough pivot structure. Try a different timeframe."}), 400

        # 3. AI labels the pivots
        logger.info("AI labelling waves...")
        ai_result = label_waves_with_ai(pivots, symbol_name, tf_raw, live_price, dp)

        # 4. Build Plotly chart
        logger.info("Building Plotly chart...")
        chart_html = build_plotly_chart(df, ai_result, symbol_name, tf_raw, dp)

        return jsonify({
            "chart_html":   chart_html,
            "pattern":      ai_result.get("pattern"),
            "trend":        ai_result.get("trend"),
            "current_wave": ai_result.get("current_wave"),
            "degree":       ai_result.get("degree"),
            "confidence":   ai_result.get("confidence"),
            "signal":       ai_result.get("signal"),
            "invalidation": ai_result.get("invalidation"),
            "tp1":          ai_result.get("tp1"),
            "tp2":          ai_result.get("tp2"),
            "live_price":   live_price,
            "narrative":    ai_result.get("narrative", ""),
            "wave_points":  ai_result.get("wave_points", []),
        })

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "XenosFinance EW Server"})

if __name__ == "__main__":
    port = int(os.getenv("PORT", os.getenv("EW_PORT", 5001)))
    logger.info(f"Starting EW Server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
