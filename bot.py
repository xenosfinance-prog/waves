#!/usr/bin/env python3 
# -*- coding: utf-8 -*-
import os, sys, json, logging, re, xml.etree.ElementTree as ET
import asyncio
import time
import base64, hashlib
import numpy as np
import pandas as pd
import requests
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ── Force UTF-8 I/O on Railway (no PYTHONIOENCODING set by default) ──────────
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("XenosWaves")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")
ANTHROPIC_API_KEY   = os.getenv("ANTHROPIC_API_KEY", "")
OWNER_ID = int(os.getenv("OWNER_TELEGRAM_ID", "0"))
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO  = os.getenv("GITHUB_REPO", "xenosfinance-prog/waves")
GITHUB_FILE  = "index.html"

SITE_NEWS   = "https://xenosfinance.com"
SITE_CHARTS = "https://xenosfinance.com/xenoswaves_charts"
SITE_FOOTER = (
    "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "📲 <a href=\"https://t.me/xenoswavefinance\"><b>Join XenosFinance</b></a> — Elliott Waves, analysis, macro and much more.\n"
    "🔔 <i>Enable notifications to stay updated.</i>\n"
    "⚠️ <i>Educational content — not investment advice.</i>"
)

SITE_KEYBOARD = {
    "inline_keyboard": [[
        {"text": "📊 Interactive Charts", "url": "https://xenosfinance.com/xenoswaves_charts"},
        {"text": "📰 Daily Brief",          "url": "https://xenosfinance.com"}
    ]]
}

MARKETS = {
    "EURUSD": {"name": "EUR/USD",          "emoji": "💶", "yf": "EURUSD=X",  "cat": "forex"},
    "GBPUSD": {"name": "GBP/USD",          "emoji": "💷", "yf": "GBPUSD=X",  "cat": "forex"},
    "USDJPY": {"name": "USD/JPY",          "emoji": "💴", "yf": "USDJPY=X",  "cat": "forex"},
    "AUDUSD": {"name": "AUD/USD",          "emoji": "🇦🇺", "yf": "AUDUSD=X", "cat": "forex"},
    "USDCHF": {"name": "USD/CHF",          "emoji": "🇨🇭", "yf": "USDCHF=X", "cat": "forex"},
    "USDCAD": {"name": "USD/CAD",          "emoji": "🇨🇦", "yf": "USDCAD=X", "cat": "forex"},
    "NZDUSD": {"name": "NZD/USD",          "emoji": "🇳🇿", "yf": "NZDUSD=X", "cat": "forex"},
    "GOLD":   {"name": "Gold",             "emoji": "🥇", "yf": "GC=F",      "cat": "commodities"},
    "SILVER": {"name": "Silver",           "emoji": "🥈", "yf": "SI=F",      "cat": "commodities"},
    "OIL":    {"name": "Crude Oil",        "emoji": "🛢",  "yf": "CL=F",     "cat": "commodities"},
    "NGAS":   {"name": "Natural Gas",      "emoji": "⛽", "yf": "NG=F",      "cat": "commodities"},
    "SPY":    {"name": "S&P 500",          "emoji": "📊", "yf": "SPY",       "cat": "equity"},
    "NASDAQ": {"name": "Nasdaq 100",       "emoji": "📈", "yf": "^NDX",      "cat": "equity"},
    "DJI":    {"name": "Dow Jones",        "emoji": "🇺🇸", "yf": "^DJI",     "cat": "equity"},
    "BTCUSD": {"name": "Bitcoin",          "emoji": "₿",  "yf": "BTC-USD",  "cat": "crypto"},
    "ETHUSD": {"name": "Ethereum",         "emoji": "💎", "yf": "ETH-USD",   "cat": "crypto"},
    "XRPUSD": {"name": "Ripple",           "emoji": "💧", "yf": "XRP-USD",   "cat": "crypto"},
    "SOLUSD": {"name": "Solana",           "emoji": "☀️", "yf": "SOL-USD",   "cat": "crypto"},
    "DOGEUSD":{"name": "Dogecoin",         "emoji": "🐶", "yf": "DOGE-USD",  "cat": "crypto"},
    "ZECUSD": {"name": "Zcash",            "emoji": "🔒", "yf": "ZEC-USD",   "cat": "crypto"},
    "AAPL":   {"name": "Apple",            "emoji": "🍎", "yf": "AAPL",      "cat": "bluechip"},
    "MSFT":   {"name": "Microsoft",        "emoji": "🪟", "yf": "MSFT",      "cat": "bluechip"},
    "JPM":    {"name": "JPMorgan",         "emoji": "🏦", "yf": "JPM",       "cat": "banks"},
    "V":      {"name": "Visa",             "emoji": "💳", "yf": "V",         "cat": "bluechip"},
    "UNH":    {"name": "UnitedHealth",     "emoji": "🏥", "yf": "UNH",       "cat": "bluechip"},
    "HD":     {"name": "Home Depot",       "emoji": "🏠", "yf": "HD",        "cat": "bluechip"},
    "MCD":    {"name": "McDonald's",       "emoji": "🍔", "yf": "MCD",       "cat": "bluechip"},
    "CAT":    {"name": "Caterpillar",      "emoji": "🚜", "yf": "CAT",       "cat": "bluechip"},
    "BA":     {"name": "Boeing",           "emoji": "✈️", "yf": "BA",        "cat": "bluechip"},
    "DIS":    {"name": "Walt Disney",      "emoji": "🏰", "yf": "DIS",       "cat": "bluechip"},
    "KO":     {"name": "Coca-Cola",        "emoji": "🥤", "yf": "KO",        "cat": "bluechip"},
    "WMT":    {"name": "Walmart",          "emoji": "🛒", "yf": "WMT",       "cat": "bluechip"},
    "JNJ":    {"name": "Johnson & Johnson","emoji": "💊", "yf": "JNJ",       "cat": "bluechip"},
    "PG":     {"name": "Procter & Gamble", "emoji": "🧴", "yf": "PG",        "cat": "bluechip"},
    "MMM":    {"name": "3M",               "emoji": "🔧", "yf": "MMM",       "cat": "bluechip"},
    "NVDA":   {"name": "Nvidia",           "emoji": "🎮", "yf": "NVDA",      "cat": "ai_tech"},
    "GOOGL":  {"name": "Alphabet",         "emoji": "🔍", "yf": "GOOGL",     "cat": "ai_tech"},
    "META":   {"name": "Meta",             "emoji": "👥", "yf": "META",      "cat": "ai_tech"},
    "AMZN":   {"name": "Amazon",           "emoji": "📦", "yf": "AMZN",      "cat": "ai_tech"},
    "TSLA":   {"name": "Tesla",            "emoji": "⚡", "yf": "TSLA",      "cat": "ai_tech"},
    "AMD":    {"name": "AMD",              "emoji": "💻", "yf": "AMD",       "cat": "ai_tech"},
    "ORCL":   {"name": "Oracle",           "emoji": "☁️", "yf": "ORCL",      "cat": "ai_tech"},
    "CRM":    {"name": "Salesforce",       "emoji": "💼", "yf": "CRM",       "cat": "ai_tech"},
    "PLTR":   {"name": "Palantir",         "emoji": "🔭", "yf": "PLTR",      "cat": "ai_tech"},
    "GS":     {"name": "Goldman Sachs",    "emoji": "💰", "yf": "GS",        "cat": "banks"},
    "BAC":    {"name": "Bank of America",  "emoji": "🏛️", "yf": "BAC",       "cat": "banks"},
    "WFC":    {"name": "Wells Fargo",      "emoji": "🐎", "yf": "WFC",       "cat": "banks"},
    "MS":     {"name": "Morgan Stanley",   "emoji": "📊", "yf": "MS",        "cat": "banks"},
    "C":      {"name": "Citigroup",        "emoji": "🌐", "yf": "C",         "cat": "banks"},
    "BLK":    {"name": "BlackRock",        "emoji": "🖤", "yf": "BLK",       "cat": "banks"},
    # ── FX CROSS ──────────────────────────────────────────────────
    "EURGBP": {"name": "EUR/GBP",  "emoji": "💶", "yf": "EURGBP=X",  "cat": "forex_cross"},
    "EURJPY": {"name": "EUR/JPY",  "emoji": "💶", "yf": "EURJPY=X",  "cat": "forex_cross"},
    "GBPJPY": {"name": "GBP/JPY",  "emoji": "💷", "yf": "GBPJPY=X",  "cat": "forex_cross"},
    "AUDJPY": {"name": "AUD/JPY",  "emoji": "🇦🇺","yf": "AUDJPY=X",  "cat": "forex_cross"},
    "CADJPY": {"name": "CAD/JPY",  "emoji": "🇨🇦","yf": "CADJPY=X",  "cat": "forex_cross"},
    "CHFJPY": {"name": "CHF/JPY",  "emoji": "🇨🇭","yf": "CHFJPY=X",  "cat": "forex_cross"},
    "EURAUD": {"name": "EUR/AUD",  "emoji": "💶", "yf": "EURAUD=X",  "cat": "forex_cross"},
    "EURCAD": {"name": "EUR/CAD",  "emoji": "💶", "yf": "EURCAD=X",  "cat": "forex_cross"},
    "EURCHF": {"name": "EUR/CHF",  "emoji": "💶", "yf": "EURCHF=X",  "cat": "forex_cross"},
    "GBPAUD": {"name": "GBP/AUD",  "emoji": "💷", "yf": "GBPAUD=X",  "cat": "forex_cross"},
    "GBPCAD": {"name": "GBP/CAD",  "emoji": "💷", "yf": "GBPCAD=X",  "cat": "forex_cross"},
    "AUDCAD": {"name": "AUD/CAD",  "emoji": "🇦🇺","yf": "AUDCAD=X",  "cat": "forex_cross"},
    "AUDCHF": {"name": "AUD/CHF",  "emoji": "🇦🇺","yf": "AUDCHF=X",  "cat": "forex_cross"},
    "NZDJPY": {"name": "NZD/JPY",  "emoji": "🇳🇿","yf": "NZDJPY=X",  "cat": "forex_cross"},
    "CADCHF": {"name": "CAD/CHF",  "emoji": "🇨🇦","yf": "CADCHF=X",  "cat": "forex_cross"},
}

ALIASES = {
    "EU":"EURUSD","GU":"GBPUSD","UJ":"USDJPY","AU":"AUDUSD",
    "UC":"USDCHF","UCHF":"USDCHF","NU":"NZDUSD","USDNZD":"NZDUSD",
    "XAU":"GOLD","XAUUSD":"GOLD","XAG":"SILVER","XAGUSD":"SILVER",
    "BTC":"BTCUSD","ETH":"ETHUSD","ETHEREUM":"ETHUSD","XRP":"XRPUSD","RIPPLE":"XRPUSD","SOL":"SOLUSD","SOLANA":"SOLUSD","DOGE":"DOGEUSD","DOGECOIN":"DOGEUSD","ZEC":"ZECUSD","ZCASH":"ZECUSD",
    "ES":"SPY","NQ":"NASDAQ","YM":"DJI","DOW":"DJI",
    "CL":"OIL","WTI":"OIL","GC":"GOLD","NG":"NGAS","GAS":"NGAS",
    "APPLE":"AAPL","MICROSOFT":"MSFT","NVIDIA":"NVDA","GOOGLE":"GOOGL",
    "ALPHABET":"GOOGL","AMAZON":"AMZN","FACEBOOK":"META","TESLA":"TSLA",
    "JPMORGAN":"JPM","JPMCHASE":"JPM","GOLDMAN":"GS","BOFA":"BAC",
    "WELLSFARGO":"WFC","MORGANSTANLEY":"MS","CITI":"C","CITIBANK":"C",
    "BLACKROCK":"BLK","MCDONALDS":"MCD","DISNEY":"DIS","COCACOLA":"KO",
    "BOEING":"BA","CATERPILLAR":"CAT","WALMART":"WMT","HOMEDEPOT":"HD",
    "PALANTIR":"PLTR","SALESFORCE":"CRM","ORACLE":"ORCL",
    # Cross aliases
    "EJ":"EURJPY","GJ":"GBPJPY","AJ":"AUDJPY","CJ":"CADJPY",
    "EG":"EURGBP","EA":"EURAUD","EC":"EURCAD","ECAD":"EURCAD",
}

SYMBOL_LIST = (
    "FX Major: EURUSD GBPUSD USDJPY AUDUSD USDCHF USDCAD NZDUSD | "
    "FX Cross: EURGBP EURJPY GBPJPY AUDJPY CADJPY CHFJPY EURAUD EURCAD EURCHF GBPAUD GBPCAD AUDCAD AUDCHF NZDJPY CADCHF | "
    "Commodities: GOLD SILVER OIL NGAS | "
    "Equity: SPY NASDAQ DJI | "
    "Crypto: BTCUSD ETHUSD XRPUSD SOLUSD DOGEUSD ZECUSD | "
    "Blue Chip: AAPL MSFT V UNH HD MCD CAT BA DIS KO WMT JNJ PG MMM | "
    "AI & Tech: NVDA GOOGL META AMZN TSLA AMD ORCL CRM PLTR | "
    "Banks: JPM GS BAC WFC MS C BLK"
)

GEOPOLITICS_FEEDS = [
    {"name": "Reuters World",   "url": "https://feeds.reuters.com/reuters/worldNews",    "emoji": "📡", "lang": "EN"},
    {"name": "Reuters Markets", "url": "https://feeds.reuters.com/reuters/businessNews", "emoji": "📡", "lang": "EN"},
    {"name": "Reuters Top",     "url": "https://feeds.reuters.com/reuters/topNews",      "emoji": "📡", "lang": "EN"},
    {"name": "AP News",         "url": "https://rsshub.app/apnews/topics/apf-topnews",   "emoji": "📰", "lang": "EN"},
    {"name": "Yahoo Finance",   "url": "https://finance.yahoo.com/rss/topstories",                    "emoji": "💹", "lang": "EN"},
]

GEOPOLITICS_KEYWORDS = [
    "war","conflict","sanctions","military","geopolit","energy","oil","nato",
    "russia","ukraine","china","iran","israel","middle east","opec","fed ",
    "federal reserve","inflation","recession","trade war","tariff","central bank",
    "guerra","conflitto","sanzioni","militare","energia","petrolio",
    "banca centrale","inflazione","recessione","trump","dollar","rate","interest",
    "economy","market","stock","bond","currency","treasury","gdp","jobs",
]

IMPACT_MAP = {
    "oil":       {"assets": ["OIL","NGAS","GOLD"],      "dir": "bullish"},
    "petrolio":  {"assets": ["OIL","NGAS","GOLD"],      "dir": "bullish"},
    "energy":    {"assets": ["OIL","NGAS"],              "dir": "bullish"},
    "russia":    {"assets": ["OIL","GOLD","EURUSD"],    "dir": "bearish"},
    "ukraine":   {"assets": ["OIL","GOLD","EURUSD"],    "dir": "bearish"},
    "china":     {"assets": ["SPY","NASDAQ","AUDUSD"],  "dir": "bearish"},
    "iran":      {"assets": ["OIL","GOLD"],              "dir": "bullish"},
    "israel":    {"assets": ["OIL","GOLD"],              "dir": "bullish"},
    "nato":      {"assets": ["GOLD","EURUSD"],           "dir": "mixed"},
    "sanctions": {"assets": ["GOLD","OIL","USDJPY"],    "dir": "bullish"},
    "sanzioni":  {"assets": ["GOLD","OIL"],              "dir": "bullish"},
    "fed":       {"assets": ["EURUSD","GOLD","SPY"],    "dir": "mixed"},
    "federal reserve": {"assets": ["EURUSD","GOLD","SPY"], "dir": "mixed"},
    "inflation": {"assets": ["GOLD","OIL"],              "dir": "bullish"},
    "recession": {"assets": ["GOLD","USDJPY","SPY"],    "dir": "mixed"},
    "tariff":    {"assets": ["SPY","NASDAQ","AUDUSD"],  "dir": "bearish"},
    "trade war": {"assets": ["SPY","GOLD","AUDUSD"],    "dir": "bearish"},
    "opec":      {"assets": ["OIL","NGAS"],              "dir": "bullish"},
    "trump":     {"assets": ["SPY","GOLD","USDJPY"],    "dir": "mixed"},
    "interest rate": {"assets": ["EURUSD","GOLD","SPY"], "dir": "mixed"},
    "rate hike": {"assets": ["EURUSD","GOLD","SPY"],    "dir": "bearish"},
    "rate cut":  {"assets": ["EURUSD","GOLD","SPY"],    "dir": "bullish"},
    "treasury":  {"assets": ["GOLD","USDJPY"],           "dir": "mixed"},
    "dollar":    {"assets": ["GOLD","EURUSD","OIL"],    "dir": "mixed"},
}

# ─── UTILITIES ────────────────────────────────────────────────────────────────
def strip_bold(text):
    return re.sub(r'\*\*(.+?)\*\*', r'\1', text) if text else text

def strip_html(text):
    if not text: return ""
    text = re.sub(r'<!\[CDATA\[', '', text)
    text = re.sub(r'\]\]>', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    for ent, ch in [('&amp;','&'),('&lt;','<'),('&gt;','>'),('&quot;','"'),('&#39;',"'"),('&nbsp;',' ')]:
        text = text.replace(ent, ch)
    text = re.sub(r'&#[0-9]+;', '', text)
    text = re.sub(r'&\w+;', '', text)
    return text.strip()

def safe_get_text(element):
    if element is None:
        return ""
    parts = []
    if element.text:
        parts.append(element.text)
    for child in element:
        if child.text:
            parts.append(child.text)
        if child.tail:
            parts.append(child.tail)
    if element.tail:
        parts.append(element.tail)
    return strip_html("".join(parts))

def split_message(text, max_len=4096):
    """Divide un testo lungo in parti da max_len caratteri, spezzando su newline."""
    if len(text) <= max_len:
        return [text]
    parts = []
    while len(text) > max_len:
        split_at = text.rfind('\n', 0, max_len)
        if split_at == -1:
            split_at = max_len
        parts.append(text[:split_at])
        text = text[split_at:].lstrip('\n')
    if text:
        parts.append(text)
    return parts

# ─── DATA FETCH ───────────────────────────────────────────────────────────────
def fetch_data(symbol, days=365, interval="1d"):
    # FIX 2026-10: Yahoo non supporta interval="4h" (la richiesta falliva sempre →
    # pannello 4H e MTF 4H mai presenti). Scarico 1h e ricampiono su barre 4h UTC.
    if interval == "4h":
        df1 = fetch_data(symbol, days=days, interval="1h")
        if df1 is None or len(df1) == 0:
            return None
        df4 = df1.resample("4h", origin="epoch").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
        logger.info(f"✅ {symbol}: {len(df4)} bars (4h from 1h)")
        return df4
    try:
        yf  = MARKETS[symbol]["yf"]
        end = int(datetime.now().timestamp())
        start = int((datetime.now() - timedelta(days=days)).timestamp())
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"},
                         params={"period1": start, "period2": end, "interval": interval}, timeout=15)
        d = r.json()
        res = d["chart"]["result"][0]
        q   = res["indicators"]["quote"][0]
        df  = pd.DataFrame({
            "open":   q["open"], "high":   q["high"],
            "low":    q["low"],  "close":  q["close"],
            "volume": q.get("volume", [0]*len(q["open"])),
        }, index=pd.to_datetime(res["timestamp"], unit="s"))
        df = df.dropna()
        # ── Freshness check: warn if last candle is stale ──
        if len(df) > 0:
            last_ts = df.index[-1]
            age_hours = (pd.Timestamp.now(tz="UTC") - last_ts.tz_localize("UTC") if last_ts.tzinfo is None else pd.Timestamp.now(tz="UTC") - last_ts).total_seconds() / 3600
            # For intraday intervals, flag if data is older than expected
            stale_threshold = {"1h": 4, "4h": 12, "5m": 1, "15m": 2, "30m": 3}.get(interval, 72)
            if age_hours > stale_threshold:
                logger.warning(f"⚠️ {symbol} ({interval}): last candle is {age_hours:.1f}h old — may be stale")
            # Also use regularMarketPrice from meta if available for last close
            meta = res.get("meta", {})
            live_price = float(meta.get("regularMarketPrice") or 0)
            if live_price > 0 and interval in ("1h", "5m", "15m"):
                df.iloc[-1, df.columns.get_loc("close")] = live_price
                # FIX 2026-10: high/low coerenti col prezzo live (prima il corpo poteva uscire dalle ombre)
                df.iloc[-1, df.columns.get_loc("high")] = max(float(df["high"].iloc[-1]), live_price)
                df.iloc[-1, df.columns.get_loc("low")]  = min(float(df["low"].iloc[-1]),  live_price)
        logger.info(f"✅ {symbol}: {len(df)} bars ({interval})")
        return df
    except Exception as e:
        logger.error(f"❌ {symbol}: {e}")
        return None

# ─── TECHNICAL INDICATORS ─────────────────────────────────────────────────────
def ema(s, span):    return s.ewm(span=span, adjust=False).mean()
def rsi(s, p=14):
    # FIX 2026-10-07: RSI di Wilder (come TradingView e come il pannello RSI del
    # grafico). Prima era la media semplice (Cutler): su USD/JPY Daily il testo
    # diceva RSI 70.8 "overbought" mentre il grafico mostrava 57.
    d = s.diff()
    g = d.clip(lower=0).ewm(alpha=1 / p, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(alpha=1 / p, adjust=False).mean()
    return 100 - (100 / (1 + g / l.replace(0, np.nan)))
def macd(s):
    e12, e26 = ema(s,12), ema(s,26)
    return e12-e26, ema(e12-e26, 9)
def atr(df, p=14):
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"]  - df["close"].shift()).abs()
    return pd.concat([hl,hc,lc], axis=1).max(axis=1).rolling(p).mean()
def bollinger(s, p=20):
    m = s.rolling(p).mean(); st = s.rolling(p).std()
    return m+2*st, m, m-2*st
def vwap_calc(df):
    tp = (df["high"]+df["low"]+df["close"])/3
    return (tp*df["volume"]).cumsum() / df["volume"].replace(0,np.nan).cumsum()
def pivot_points(df):
    p = df.iloc[-2]; P = (p["high"]+p["low"]+p["close"])/3
    return P, 2*P-p["low"], P+(p["high"]-p["low"]), 2*P-p["high"], P-(p["high"]-p["low"])
def fibonacci_levels(df, lb=100):
    h = df["high"].iloc[-lb:].max(); l = df["low"].iloc[-lb:].min(); d = h-l
    return {"0.0":h,"23.6":h-0.236*d,"38.2":h-0.382*d,"50.0":h-0.5*d,
            "61.8":h-0.618*d,"78.6":h-0.786*d,"100.0":l}


# ═══════════════════════════════════════════════════════════════════════════════
# ELLIOTT WAVE ENGINE v2.0
# ═══════════════════════════════════════════════════════════════════════════════

# ── CFD Elliott Wave Validator ────────────────────────────────────────────────
# Traduzione del framework CFD (Fluidodinamica) per validazione onde di Elliott.
# Usa Energia Cinetica e Reynolds Number sui dati reali di prezzo e volume.
#
# Reynolds > media*1.5 + KE alta   → Onda 3 confermata (massima energia)
# KE in calo vs 5 barre fa          → Onda 5 in esaurimento (divergenza)
# Reynolds < media*0.5              → Onda 4 stabilizzata (accumulo/scarico)
# Onde A/C richiedono KE sostenuta con Reynolds moderato-alto
# Onda B (rimbalzo correttivo): basso Reynolds, KE calante

def validate_elliott_with_cfd(wave_num: str, price_data: "pd.Series", volume_data: "pd.Series") -> dict:
    """
    Valida l'onda di Elliott corrente usando la fluidodinamica computazionale.
    Adattamento Python del framework CFD originale per bot Telegram.

    wave_num: stringa ('1','2','3','4','5','A','B','C','?')
    price_data:  pd.Series dei close (almeno 30 barre)
    volume_data: pd.Series dei volumi (può essere zero per forex → usa range H-L proxy)
    """
    import numpy as np

    n = min(20, len(price_data))
    prices  = price_data.iloc[-n:].astype(float)
    volumes = volume_data.iloc[-n:].astype(float)

    # Se volume è assente/zero (tipico forex), usa range H-L come proxy di liquidità
    # (già gestito upstream: df["volume"] = [0]*n per forex senza dati)
    vol_mean = float(volumes.mean())
    if vol_mean < 1e-6:
        # Proxy: usiamo la volatilità assoluta come surrogato del volume
        vol_proxy = float(prices.diff().abs().mean())
        vol_mean  = vol_proxy if vol_proxy > 1e-9 else 1.0
        volumes   = prices.diff().abs().fillna(vol_mean)

    # ── Velocità del prezzo ───────────────────────────────────────
    velocity_series = prices.diff().dropna()
    velocity        = float(velocity_series.iloc[-1])          # ultima variazione
    price_velocity  = float(velocity_series.mean())            # media direzionale
    price_speed     = float(velocity_series.abs().mean())      # media assoluta

    # ── Energia Cinetica: 0.5 × volume × velocity² ───────────────
    ke_series = 0.5 * volumes.iloc[1:] * (velocity_series ** 2)
    ke_current = float(ke_series.iloc[-1])
    ke_mean    = float(ke_series.mean()) if len(ke_series) > 0 else ke_current

    # Confronto KE con 5 barre fa (per rilevare esaurimento onda 5)
    ke_5ago = float(ke_series.iloc[-5]) if len(ke_series) >= 5 else ke_current

    # ── Viscosità: resistenza del mercato ────────────────────────
    # Volatilità % normalizzata per volume medio
    pct_vol   = float(prices.pct_change().std())
    viscosity = pct_vol / (vol_mean + 1e-9)

    # ── Reynolds Number: energia direzionale vs attrito ───────────
    reynolds_series = velocity_series.abs() / (viscosity + 1e-9)
    reynolds_current = float(reynolds_series.iloc[-1])
    reynolds_mean    = float(reynolds_series.mean()) if len(reynolds_series) > 0 else reynolds_current

    # ── Logica di validazione per onda ───────────────────────────
    validation = "WAIT"
    notes      = ""

    if wave_num == "3":
        # Onda 3: massima energia cinetica + massimo Reynolds
        if reynolds_current > reynolds_mean * 1.5 and ke_current > ke_mean:
            validation = "STRONG_CONFIRMATION"
            notes = "Reynolds peak + high KE: classic Wave 3 impulse structure"
        elif reynolds_current > reynolds_mean * 1.2:
            validation = "MODERATE_CONFIRMATION"
            notes = "Reynolds elevated but KE not yet at peak — early W3 or extension"
        else:
            validation = "WAIT"
            notes = "Insufficient thrust for Wave 3 — may be W1 or corrective"

    elif wave_num == "5":
        # Onda 5: KE in calo vs onda 3 (divergenza classica)
        if ke_current < ke_5ago * 0.85:
            validation = "WAVE_EXHAUSTION_WARNING"
            notes = f"KE declining ({ke_current:.4f} < {ke_5ago:.4f}): terminal wave — reduce exposure"
        elif ke_current < ke_mean * 0.9:
            validation = "WEAKENING_IMPULSE"
            notes = "KE below average: W5 may be truncated — tight trailing stops advised"
        else:
            validation = "MODERATE_CONFIRMATION"
            notes = "KE still elevated — W5 extension possible before reversal"

    elif wave_num == "4":
        # Onda 4: bassa energia, Reynolds basso (fase di accumulo/scarico)
        if reynolds_current < reynolds_mean * 0.5:
            validation = "CORRECTION_STABILIZED"
            notes = "Low Reynolds: market consolidating — W4 near completion, prepare W5 entry"
        elif reynolds_current < reynolds_mean * 0.8:
            validation = "CORRECTION_IN_PROGRESS"
            notes = "Reynolds moderately low — W4 correction ongoing"
        else:
            validation = "WAIT"
            notes = "Reynolds still high — correction may not be complete"

    elif wave_num == "2":
        # Onda 2: retrace profondo con bassa energia
        if reynolds_current < reynolds_mean * 0.7 and ke_current < ke_mean:
            validation = "CORRECTION_STABILIZED"
            notes = "Low energy retracement — W2 near completion, W3 setup forming"
        else:
            validation = "CORRECTION_IN_PROGRESS"
            notes = "Energy still present in correction — wait for Reynolds to drop"

    elif wave_num in ("A", "C"):
        # Onde impulsive correttive: servono KE e Reynolds sostenuti
        if reynolds_current > reynolds_mean and ke_current > ke_mean * 0.8:
            validation = "STRONG_CONFIRMATION"
            notes = f"Wave {wave_num}: impulsive corrective leg confirmed by CFD"
        else:
            validation = "MODERATE_CONFIRMATION"
            notes = f"Wave {wave_num}: correction underway but energy moderate"

    elif wave_num == "B":
        # Onda B: rimbalzo correttivo — bassa energia, Reynolds calante
        if reynolds_current < reynolds_mean * 0.8:
            validation = "BULL_TRAP_CONFIRMED"
            notes = "Low Reynolds bounce: classic Wave B bull trap — prepare short for C"
        else:
            validation = "WAIT"
            notes = "B wave energy too high — may still be impulsive, not corrective"

    elif wave_num == "1":
        # Onda 1: prima mossa, spesso non riconosciuta — Reynolds inizia a salire
        if reynolds_current > reynolds_mean and velocity > 0:
            validation = "IMPULSE_STARTING"
            notes = "Reynolds rising from low base — possible Wave 1 initiation"
        else:
            validation = "WAIT"
            notes = "Insufficient directional energy for W1 confirmation"

    else:
        validation = "WAIT"
        notes = "Wave count uncertain — CFD cannot confirm"

    flow_type = "TURBULENT/IMPULSIVE" if reynolds_current > reynolds_mean else "LAMINAR/CONGESTION"

    return {
        "wave":         wave_num,
        "cfd_status":   validation,
        "energy_flow":  round(ke_current, 6),
        "ke_mean":      round(ke_mean, 6),
        "reynolds":     round(reynolds_current, 2),
        "reynolds_mean":round(reynolds_mean, 2),
        "viscosity":    round(viscosity, 6),
        "flow_type":    flow_type,
        "notes":        notes,
    }



def detect_swings(series, window=5):
    highs, lows = [], []
    for i in range(window, len(series)-window):
        if series.iloc[i] == series.iloc[i-window:i+window+1].max():
            highs.append((i, float(series.iloc[i])))
        if series.iloc[i] == series.iloc[i-window:i+window+1].min():
            lows.append((i, float(series.iloc[i])))
    return highs, lows

def identify_wave_degree(df):
    c = df["close"]
    r = (c.max()-c.min())/c.mean()*100
    if r>30:   return "Primary"
    elif r>15: return "Intermediate"
    elif r>7:  return "Minor"
    else:      return "Minute"

def get_pivot_structure(series, window=10):
    highs, lows = detect_swings(series, window=window)
    all_pivots = (
        [{"type":"H","idx":i,"price":p} for i,p in highs] +
        [{"type":"L","idx":i,"price":p} for i,p in lows]
    )
    all_pivots.sort(key=lambda x: x["idx"])
    filtered = []
    for pv in all_pivots:
        if not filtered or filtered[-1]["type"] != pv["type"]:
            filtered.append(pv)
        else:
            if pv["type"]=="H" and pv["price"] > filtered[-1]["price"]:
                filtered[-1] = pv
            elif pv["type"]=="L" and pv["price"] < filtered[-1]["price"]:
                filtered[-1] = pv
    return filtered

def _fib_ret(start, end, ratio):
    return end - (end - start) * ratio

def _identify_corrective_pattern(pivots):
    """
    Classifies corrective patterns: Zigzag, Flat (Regular/Expanded/Running), Triangle.
    Uses wave ratios for accurate classification.
    """
    if len(pivots) < 4:
        return "Correction developing"
    recent = pivots[-6:] if len(pivots) >= 6 else pivots
    h_prices = [p["price"] for p in recent if p["type"] == "H"]
    l_prices  = [p["price"] for p in recent if p["type"] == "L"]
    if len(h_prices) < 2 or len(l_prices) < 2:
        return "Simple corrective structure"

    hd = h_prices[-1] < h_prices[-2]   # descending highs
    la = l_prices[-1] > l_prices[-2]   # ascending lows

    # Triangle family
    if hd and la:     return "Symmetric Triangle — pre-breakout compression"
    if hd and not la: return "Descending Triangle — bearish bias"
    if not hd and la: return "Ascending Triangle — bullish bias"

    # Flat / Zigzag classification via wave ratios
    wa = abs(h_prices[0] - l_prices[0])
    wb = abs(h_prices[-1] - h_prices[0]) if len(h_prices) >= 2 else 0
    wc_size = abs(l_prices[-1] - l_prices[0]) if len(l_prices) >= 2 else 0
    if wa > 0:
        b_ratio = wb / wa
        c_ratio = wc_size / wa
        if b_ratio > 1.05:
            return "Expanded Flat (3-3-5) — B exceeds wave A start"
        if c_ratio < 0.9 and b_ratio > 0.85:
            return "Running Flat (3-3-5) — trend strength"
        if 0.85 <= b_ratio <= 1.05:
            return "Regular Flat (3-3-5)"
    return "Zigzag (5-3-5) — sharp correction"


def _detect_diagonal(pivots, direction_up):
    """Detects Ending or Expanding Diagonal from pivot structure."""
    if len(pivots) < 6:
        return None
    recent   = pivots[-6:]
    h_prices = [p["price"] for p in recent if p["type"] == "H"]
    l_prices  = [p["price"] for p in recent if p["type"] == "L"]
    if len(h_prices) < 2 or len(l_prices) < 2:
        return None
    h_conv = h_prices[-1] < h_prices[0] if direction_up else h_prices[-1] > h_prices[0]
    l_conv = l_prices[-1] > l_prices[0] if direction_up else l_prices[-1] < l_prices[0]
    if h_conv and l_conv:
        return "Ending Diagonal (Terminal Wedge)"
    h_div = h_prices[-1] > h_prices[0] if direction_up else h_prices[-1] < h_prices[0]
    l_div = l_prices[-1] < l_prices[0] if direction_up else l_prices[-1] > l_prices[0]
    if h_div and l_div:
        return "Expanding Diagonal"
    return None


def _atr_sl(price, atr_val, direction_up, multiplier=1.5):
    """ATR-based stop loss capped at multiplier × ATR."""
    if direction_up:
        return price - atr_val * multiplier
    return price + atr_val * multiplier


def _validate_ew_rules(w1_start, w1_end, w3_end, p, direction_up, w1_size):
    """
    Enforces the 3 inviolable Elliott Wave rules as hard filters.
    Returns dict of violations found.
    """
    violations = {}
    if w3_end is not None and w1_size > 0:
        w3_size = abs(w3_end - w1_end)
        # Rule: Wave 3 cannot be shortest among W1, W3, W5 — we check W3 >= W1
        if w3_size < w1_size * 0.9:
            violations["w3_shortest"] = True
    # Rule: Wave 4 cannot enter Wave 1 territory
    if direction_up and p < w1_end:
        violations["w4_invades_w1"] = True
    elif not direction_up and p > w1_end:
        violations["w4_invades_w1"] = True
    # Rule: Wave 2 cannot retrace beyond Wave 1 start
    if direction_up and p < w1_start:
        violations["w2_beyond_start"] = True
    elif not direction_up and p > w1_start:
        violations["w2_beyond_start"] = True
    return violations


def count_elliott_waves_deepscan(df):
    """
    Elliott Wave engine v3.0
    Priority order:
    1. SL/TP realistic, ATR-calibrated per asset class
    2. MTF coherence checks
    3. Corrective pattern precision
    4. Hard EW rule enforcement
    """
    c    = df["close"]
    p    = float(c.iloc[-1])
    pv   = float(c.iloc[-2])
    rv   = float(rsi(c).iloc[-1])
    ml, sl_m = macd(c)
    mh   = float((ml - sl_m).iloc[-1])
    av   = float(atr(df).iloc[-1])
    s20  = float(c.rolling(20).mean().iloc[-1])
    s50  = float(c.rolling(50).mean().iloc[-1])
    s200 = float(c.rolling(200).mean().iloc[-1])

    # ── Pivot structures ──────────────────────────────────────────
    c200 = c.iloc[-200:] if len(c) >= 200 else c
    pivots = get_pivot_structure(c200, window=max(5, len(c200) // 20))
    h_pvts = [pv2 for pv2 in pivots if pv2["type"] == "H"]
    l_pvts = [pv2 for pv2 in pivots if pv2["type"] == "L"]

    c50 = c.iloc[-50:] if len(c) >= 50 else c
    pivots_recent = get_pivot_structure(c50, window=max(3, len(c50) // 10))
    h_rec = [pv2 for pv2 in pivots_recent if pv2["type"] == "H"]
    l_rec = [pv2 for pv2 in pivots_recent if pv2["type"] == "L"]

    # ── Wave 1 anchor ─────────────────────────────────────────────
    w1_start = float(l_pvts[0]["price"]) if l_pvts else float(c200.min())
    w1_end   = float(h_pvts[0]["price"]) if h_pvts else float(c200.max())
    if h_pvts and l_pvts and h_pvts[0]["idx"] < l_pvts[0]["idx"]:
        w1_start = float(h_pvts[0]["price"])
        w1_end   = float(l_pvts[0]["price"])
    w1_size      = abs(w1_end - w1_start)
    direction_up = w1_end > w1_start

    w3_end = None
    if direction_up and len(h_pvts) > 1:
        w3_end = float(h_pvts[1]["price"])
    elif not direction_up and len(l_pvts) > 1:
        w3_end = float(l_pvts[1]["price"])

    # ── Trend flags ───────────────────────────────────────────────
    trend_20  = p > float(c.iloc[-20])  if len(c) > 20  else True
    trend_50  = p > float(c.iloc[-50])  if len(c) > 50  else True
    trend_200 = p > float(c.iloc[-200]) if len(c) > 200 else True

    # ── Divergence detection ──────────────────────────────────────
    rsi_s    = rsi(c)
    rsi_pk20 = float(rsi_s.iloc[-20:-1].max()) if len(rsi_s) > 20 else rv
    p_pk20   = float(c.iloc[-20:-1].max())      if len(c) > 20    else p
    rsi_lw20 = float(rsi_s.iloc[-20:-1].min())  if len(rsi_s) > 20 else rv
    p_lw20   = float(c.iloc[-20:-1].min())       if len(c) > 20    else p
    bearish_div = (p >= p_pk20 * 0.998) and (rv < rsi_pk20 - 5)
    bullish_div = (p <= p_lw20 * 1.002) and (rv > rsi_lw20 + 5)

    # ── EW Rule validation ────────────────────────────────────────
    ew_violations = _validate_ew_rules(w1_start, w1_end, w3_end, p, direction_up, w1_size)

    # ══════════════════════════════════════════════════════════════
    # SCORING — each wave candidate scored independently
    # ══════════════════════════════════════════════════════════════
    score_w1 = 0
    if trend_20 and not trend_50:                   score_w1 += 2
    if not trend_200:                               score_w1 += 1
    if 38 < rv < 62:                                score_w1 += 1
    if mh > 0:                                      score_w1 += 1
    if p < s200 * 1.05:                             score_w1 += 1

    score_w2 = 0
    # Hard rule: W2 cannot retrace beyond W1 start
    w2_valid = (direction_up and w1_start < p < w1_end) or \
               (not direction_up and w1_end < p < w1_start)
    if w2_valid:                                    score_w2 += 3
    else:                                           score_w2 -= 5  # hard penalty
    if trend_200 and not trend_20:                  score_w2 += 2
    if rv < 50:                                     score_w2 += 1
    if mh < 0:                                      score_w2 += 1
    if w1_size > 0:
        ret_pct = abs(p - w1_end) / w1_size
        if 0.382 <= ret_pct <= 0.618:               score_w2 += 3  # ideal retracement
        elif 0.618 < ret_pct <= 0.786:              score_w2 += 1  # deep but valid
        elif ret_pct > 0.786:                       score_w2 -= 3  # approaching W1 start

    score_w3 = 0
    w3_ext = False
    if direction_up:
        if p > w1_end + w1_size * 1.0:             score_w3 += 2
        if p > w1_end + w1_size * 1.618:           score_w3 += 2
        if p > w1_end + w1_size * 2.618:           score_w3 += 1; w3_ext = True
    else:
        if p < w1_end - w1_size * 1.0:             score_w3 += 2
        if p < w1_end - w1_size * 1.618:           score_w3 += 2
        if p < w1_end - w1_size * 2.618:           score_w3 += 1; w3_ext = True
    if trend_20 and trend_50 and trend_200:         score_w3 += 2
    if rv > 55:                                     score_w3 += 1
    if mh > 0 and direction_up:                     score_w3 += 1
    if mh < 0 and not direction_up:                 score_w3 += 1
    # W3 cannot be shortest — penalize if W3 size < W1 size
    if w3_end and w1_size > 0:
        w3_size = abs(w3_end - w1_end)
        if w3_size < w1_size:                       score_w3 -= 4

    score_w4 = 0
    # Hard rule: W4 cannot enter W1 price territory
    w4_valid = (direction_up and p > w1_end) or \
               (not direction_up and p < w1_end)
    if w4_valid:                                    score_w4 += 3
    else:                                           score_w4 -= 6  # hard violation
    if trend_50 and trend_200 and not trend_20:     score_w4 += 2
    if 38 < rv < 65:                                score_w4 += 1
    if mh < 0:                                      score_w4 += 1
    if w3_end and w1_end:
        w3s = abs(w3_end - w1_end)
        if w3s > 0:
            r4 = abs(p - w3_end) / w3s
            if 0.236 <= r4 <= 0.382:                score_w4 += 3  # ideal W4 zone
            elif 0.382 < r4 <= 0.618:               score_w4 += 1
            elif r4 > 0.618:                        score_w4 -= 2
    # Alternance bonus: if W2 was sharp (Zigzag), W4 should be flat (Flat/Triangle)
    score_w4 += 1  # slight bonus as W4 is common after extended W3

    score_w5 = 0
    if trend_20 and trend_50 and trend_200:         score_w5 += 2
    if bearish_div and direction_up:                score_w5 += 3  # key W5 signal
    if bullish_div and not direction_up:            score_w5 += 3
    if rv > 65 and direction_up:                    score_w5 += 1  # overbought
    if rv < 35 and not direction_up:                score_w5 += 1  # oversold
    if mh > 0 and direction_up:                     score_w5 += 1
    _diag_pre = _detect_diagonal(pivots, direction_up)
    if _diag_pre and "Ending" in _diag_pre:         score_w5 += 2
    # W5 must be beyond W3 end
    if w3_end:
        if direction_up and p > w3_end:             score_w5 += 2
        elif not direction_up and p < w3_end:       score_w5 += 2
        else:                                       score_w5 -= 4

    score_wa = 0
    if trend_200 and not trend_50 and not trend_20: score_wa += 3
    if rv < 50:                                     score_wa += 1
    if mh < 0:                                      score_wa += 2
    if bearish_div and not direction_up:            score_wa += 1

    score_wb = 0
    if not trend_200 and trend_20:                  score_wb += 2
    if 48 < rv < 65:                                score_wb += 1
    if mh > 0 and not bearish_div:                  score_wb += 2

    score_wc = 0
    if not trend_200 and not trend_50:              score_wc += 2
    if rv < 45:                                     score_wc += 2
    if mh < 0:                                      score_wc += 1
    if bullish_div:                                 score_wc += 2

    # ══════════════════════════════════════════════════════════════
    # CANDIDATE SELECTION with hard rule enforcement
    # ══════════════════════════════════════════════════════════════
    candidates = []
    if score_w1 >= 3:                               candidates.append(("1", score_w1))
    if score_w2 >= 4 and w2_valid:                  candidates.append(("2", score_w2))
    if score_w3 >= 4:                               candidates.append(("3", score_w3))
    if score_w4 >= 4 and w4_valid:                  candidates.append(("4", score_w4))
    if score_w5 >= 4:                               candidates.append(("5", score_w5))
    if score_wa >= 4:                               candidates.append(("A", score_wa))
    if score_wb >= 3:                               candidates.append(("B", score_wb))
    if score_wc >= 3:                               candidates.append(("C", score_wc))

    if candidates:
        candidates.sort(key=lambda x: x[1], reverse=True)
        wn = candidates[0][0]
    else:
        wn = "?"

    # ══════════════════════════════════════════════════════════════
    # SL/TP CALCULATION — ATR-capped, asset-class aware
    # ATR multipliers by wave type:
    #   Impulsive (trend): SL = 1.0x ATR (tight, we're in the wave)
    #   Terminal W5:       SL = 1.5x ATR trailing
    #   Corrective entry:  SL = 1.2x ATR (beyond the correction extreme)
    #   ABC corrections:   SL = 1.0x ATR beyond pivot
    # ══════════════════════════════════════════════════════════════
    cp = None

    if wn == "1":
        wp  = "IMPULSIVE"
        wd  = "Wave ① — First Impulse"
        wc  = "Initial wave, often underestimated. Volume building, RSI rising from neutral."
        # SL just below the recent swing low, max 1.2x ATR
        raw_sl = float(l_rec[-1]["price"]) if l_rec else p - av * 1.2
        inv = max(raw_sl, p - av * 1.2) if direction_up else min(raw_sl, p + av * 1.2)
        nt  = p + w1_size * 1.0   if direction_up else p - w1_size * 1.0
        ct  = p + w1_size * 0.618 if direction_up else p - w1_size * 0.618
        action = "🟢 LONG — Entry now or on pullback to nearest support" if direction_up else "🔴 SHORT — Entry now or on bounce to nearest resistance"

    elif wn == "2":
        wp  = "CORRECTIVE"
        wd  = "Wave ② — Retracement (50–61.8% of W1)"
        wc  = "NEVER violates W1 start. Accumulation zone before the largest W3."
        cp  = _identify_corrective_pattern(pivots)
        # SL: just beyond W1 start, max 1.5x ATR
        raw_sl = w1_start - av * 0.1 if direction_up else w1_start + av * 0.1
        inv = max(raw_sl, p - av * 1.5) if direction_up else min(raw_sl, p + av * 1.5)
        entry_zone = _fib_ret(w1_start, w1_end, 0.618)
        nt  = w1_end + w1_size * 1.618 if direction_up else w1_end - w1_size * 1.618
        ct  = w1_end + w1_size * 1.0   if direction_up else w1_end - w1_size * 1.0
        action = f"🟢 LONG — Entry zone {entry_zone:.5f} (61.8% Fib W1), Stop below {inv:.5f}" if direction_up else f"🔴 SHORT — Entry zone {entry_zone:.5f} (61.8% Fib W1), Stop above {inv:.5f}"
        alt = f"W2: {cp.split(' ')[0]} — W4 should alternate (Flat/Triangle)"

    elif wn == "3":
        wp  = "IMPULSIVE"
        wd  = f"Wave ③ — {'EXTENDED ' if w3_ext else ''}Dominant Impulse"
        wc  = (("⚡ EXTENDED WAVE 3: exceeds 261.8% of W1. " if w3_ext else "") +
               "Never the shortest wave (inviolable rule). Maximum volume. Most profitable wave.")
        # SL: end of W1, but capped at 2x ATR to avoid absurd distances
        raw_sl = w1_end
        inv = max(raw_sl, p - av * 2.0) if direction_up else min(raw_sl, p + av * 2.0)
        nt  = w1_end + w1_size * (4.236 if w3_ext else 2.618) if direction_up else w1_end - w1_size * (4.236 if w3_ext else 2.618)
        ct  = w1_end + w1_size * 1.618 if direction_up else w1_end - w1_size * 1.618
        action = "🟢 LONG (trend) — Stay in trade, trailing stop below EMA21" if direction_up else "🔴 SHORT (trend) — Stay in trade, trailing stop above EMA21"
        alt = "N/A"

    elif wn == "4":
        wp  = "CORRECTIVE"
        wd  = "Wave ④ — Consolidation (23.6–38.2% Fib of W3)"
        wc  = "NEVER enters W1 territory (inviolable rule). Typical: Flat or Triangle. Alternates with W2."
        cp  = _identify_corrective_pattern(pivots)
        # SL: W1 end level, but max 1.5x ATR distance
        raw_sl = w1_end - av * 0.1 if direction_up else w1_end + av * 0.1
        inv = max(raw_sl, p - av * 1.5) if direction_up else min(raw_sl, p + av * 1.5)
        if w3_end:
            w3s = abs(w3_end - w1_end)
            nt  = w3_end + w3s * 0.618 if direction_up else w3_end - w3s * 0.618
            ct  = w3_end + w3s * 0.382 if direction_up else w3_end - w3s * 0.382
            ez4 = _fib_ret(w1_end, w3_end, 0.382)
        else:
            nt  = p + w1_size * 0.618 if direction_up else p - w1_size * 0.618
            ct  = p + w1_size * 0.382 if direction_up else p - w1_size * 0.382
            ez4 = p
        action = f"🟢 LONG — Entry on confirmed bounce at {ez4:.5f} (38.2% W3)" if direction_up else f"🔴 SHORT — Entry on confirmed bounce at {ez4:.5f} (38.2% W3)"
        alt = f"W4: {cp.split(' ')[0]} — alternation vs W2"

    elif wn == "5":
        wp  = "IMPULSIVE"
        diagonal = _detect_diagonal(pivots, direction_up)
        truncated = (direction_up and p < (w1_end + w1_size * 0.3)) or \
                    (not direction_up and p > (w1_end - w1_size * 0.3))
        wd  = "Wave ⑤ — Terminal Impulse"
        if truncated:  wd += " [TRUNCATED ⚠️]"
        if diagonal:   wd += f" [{diagonal}]"
        wc  = "⚠️ Bearish RSI divergence expected. End of impulsive cycle — expect ABC reversal."
        # SL: ATR trailing — 1.5x ATR, never a historical low
        inv = _atr_sl(p, av, direction_up, multiplier=1.5)
        nt  = p + w1_size * (0.382 if truncated else 0.618) if direction_up else p - w1_size * (0.382 if truncated else 0.618)
        ct  = p + w1_size * 0.382 if direction_up else p - w1_size * 0.382
        action = "⚠️ Terminal phase — trail stops, no new entries"
        alt = "N/A"

    elif wn == "A":
        wp  = "CORRECTIVE ABC"
        wd  = "Wave 🅐 — First Corrective Leg"
        wc  = "Internal impulse structure (5 sub-waves). Target: 38.2–61.8% of prior cycle."
        raw_sl = float(h_rec[-1]["price"]) if h_rec else p + av * 1.2
        # After bullish impulse → Wave A goes DOWN → SL above recent high
        # After bearish impulse → Wave A goes UP → SL below recent low
        inv = min(raw_sl, p + av * 1.2) if direction_up else max(float(l_rec[-1]["price"]) if l_rec else p - av * 1.2, p - av * 1.2)
        cycle_high = float(h_pvts[-1]["price"]) if h_pvts else float(c.max())
        cycle_low  = float(l_pvts[0]["price"])  if l_pvts else float(c.min())
        nt  = _fib_ret(cycle_high, cycle_low, 0.618) if direction_up else _fib_ret(cycle_low, cycle_high, 0.618)
        ct  = _fib_ret(cycle_high, cycle_low, 0.382) if direction_up else _fib_ret(cycle_low, cycle_high, 0.382)
        action = "🔴 SHORT — Distributive structure. Stop above recent high" if direction_up else "🟢 LONG — Corrective rally. Stop below recent low"

    elif wn == "B":
        wp  = "CORRECTIVE ABC"
        wd  = "Wave 🅑 — Corrective Bounce (Bull Trap)"
        wc  = "Volume declining vs prior cycle. Should not exceed wave A high. Prepare short for C."
        cp  = _identify_corrective_pattern(pivots)
        raw_sl = float(h_rec[-1]["price"]) if h_rec else p + av * 1.2
        inv = min(raw_sl, p + av * 1.5) if direction_up else max(float(l_rec[-1]["price"]) if l_rec else p - av * 1.5, p - av * 1.5)
        a_low  = float(l_rec[-1]["price"]) if l_rec else p - av * 2.0
        a_high = float(h_rec[-1]["price"]) if h_rec else p + av * 2.0
        nt  = _fib_ret(a_low, a_high, 0.618) if direction_up else _fib_ret(a_high, a_low, 0.618)
        ct  = _fib_ret(a_low, a_high, 0.5)   if direction_up else _fib_ret(a_high, a_low, 0.5)
        action = "⚠️ AVOID LONGS — Bull trap. Prepare SHORT for Wave C" if direction_up else "⚠️ AVOID SHORTS — Bear trap. Prepare LONG for Wave C"
        alt = f"B Pattern: {cp.split(' ')[0] if cp else 'N/A'}"

    elif wn == "C":
        wp  = "CORRECTIVE ABC"
        wd  = "Wave 🅒 — Final Bearish Leg (100–123.6% of A)"
        a_low  = float(l_rec[-1]["price"]) if l_rec else p - w1_size
        a_high = float(h_rec[-1]["price"]) if h_rec else p + w1_size
        a_size = abs(a_high - a_low)
        ct100  = a_low - a_size if not direction_up else a_high + a_size
        ct1236 = a_low - a_size * 1.236 if not direction_up else a_high + a_size * 1.236
        wc  = f"Internal impulse structure (5 sub-waves). Target: {ct100:.5f} (100%A) / {ct1236:.5f} (123.6%A)."
        raw_sl = float(h_rec[-1]["price"]) if h_rec else p + av * 1.2
        inv = min(raw_sl, p + av * 1.2) if direction_up else max(float(l_rec[-1]["price"]) if l_rec else p - av * 1.2, p - av * 1.2)
        nt  = ct1236
        ct  = ct100
        action = f"🔴 SHORT — Target {ct100:.5f} / {ct1236:.5f}. Stop above {inv:.5f}" if direction_up else f"🟢 LONG — Target {ct100:.5f} / {ct1236:.5f}. Stop below {inv:.5f}"
        alt = "N/A"

    else:
        wp  = "TRANSITION"
        wd  = "Transition Phase — Count Developing"
        wc  = "Structure not classifiable with confidence. Wait for key level breakout."
        inv = _atr_sl(p, av, True, 1.0)
        nt  = p + av * 2.0
        ct  = p + av * 1.0
        action = "⏳ WAIT — No confirmed setup. Wait for range breakout"
        alt = "Pending"

    # ── Post-processing ───────────────────────────────────────────
    diagonal  = _detect_diagonal(pivots, direction_up) if wn != "5" else locals().get("diagonal")
    truncated = locals().get("truncated", False)
    cp        = locals().get("cp", None)
    alt       = locals().get("alt", "N/A")

    # ── Bias strings ──────────────────────────────────────────────
    if wn in ["1", "3"]:    bi = "BULLISH" if direction_up else "BEARISH"
    elif wn == "5":          bi = "BULLISH (TERMINAL ⚠️)" if direction_up else "BEARISH (TERMINAL ⚠️)"
    elif wn == "2":          bi = "PULLBACK — LONG SETUP" if direction_up else "BOUNCE — SHORT SETUP"
    elif wn == "4":          bi = "PULLBACK — LONG SETUP" if direction_up else "BOUNCE — SHORT SETUP"
    elif wn == "A":          bi = "BEARISH" if direction_up else "BULLISH"
    elif wn == "B":          bi = "CORRECTIVE BOUNCE — SHORT SETUP" if direction_up else "CORRECTIVE DROP — LONG SETUP"
    elif wn == "C":          bi = "BEARISH (TERMINAL ⚠️)" if direction_up else "BULLISH (TERMINAL ⚠️)"
    else:                    bi = "NEUTRAL"

    # ── MTF coherence check ───────────────────────────────────────
    # Flag if bias contradicts trend alignment
    mtf_conflict = False
    if "BULL" in bi and not (trend_20 or trend_50):
        mtf_conflict = True
    if "BEAR" in bi and (trend_20 and trend_50):
        mtf_conflict = True

    # ── Confidence score ──────────────────────────────────────────
    degree = identify_wave_degree(df)
    conf_sigs = [p > s200, p > s50, p > s20, rv > 50, mh > 0, trend_20, trend_50]
    if "BULL" in bi:    conf = sum(conf_sigs) * 13
    elif "BEAR" in bi:  conf = (7 - sum(conf_sigs)) * 13
    else:               conf = 42
    if ew_violations:   conf -= 10 * len(ew_violations)
    if mtf_conflict:    conf -= 8
    conf = max(30, min(conf, 91))

    # ── Risk/Reward ───────────────────────────────────────────────
    risk   = abs(p - inv)
    reward = abs(nt - p)
    rr_val = round(reward / risk, 2) if risk > 0 else 0.0

    return {
        "wave_num": wn, "wave_phase": wp, "wave_desc": wd, "wave_char": wc,
        "action": action,
        "invalidation": inv, "next_target": nt, "conservative_target": ct,
        "corrective_pattern": cp, "extended": w3_ext if wn == "3" else False,
        "alternance": alt,
        "diagonal": diagonal, "truncated": truncated,
        "bearish_div": bearish_div, "bullish_div": bullish_div,
        "bias": bi, "confidence": conf, "degree": degree,
        "w1_start": w1_start, "w1_end": w1_end, "w1_size": w1_size,
        "w3_end": w3_end, "direction_up": direction_up,
        "pivots": pivots, "pivots_recent": pivots_recent,
        "risk_reward": rr_val,
        "ew_violations": ew_violations, "mtf_conflict": mtf_conflict,
        "cfd_validation": validate_elliott_with_cfd(wn, df["close"], df["volume"]),
    }



# ═══════════════════════════════════════════════════════════════════════════════
# XENOSFINANCE EW ENGINE (rule-validated) — stesso motore del sito (elliottwave.html)
# Sostituisce il vecchio scoring a indicatori (count_elliott_waves_deepscan).
# Regole: W2 28–78.6% · W3 su estensioni standard ±15%, mai la più corta ·
# W4 15–65% senza overlap con W1 · B 23.6–100% di A. 3 gradi di zigzag su high/low reali;
# vince la struttura valida più completa (min: W2 confermata, W3 in corso).
# ═══════════════════════════════════════════════════════════════════════════════
EW_ENGINE_RULES = {
    "w2":     (0.28, 0.786),
    "w3_ext": (1.0, 1.272, 1.618, 2.0, 2.618), "w3_tol": 0.15,
    "w4":     (0.15, 0.65),
    "b":      (0.236, 1.0),
}
EW_ENGINE_DEGREES = [("Minor", 4), ("Intermediate", 8), ("Primary", 16)]
EW_WAVE_LABELS = ["0", "1", "2", "3", "4", "5", "A", "B", "C"]


def _ew_in(x, r):
    return r[0] <= x <= r[1]


def _ew_near(x, arr, tol):
    return any(abs(x / e - 1) <= tol for e in arr)


def ew_engine_zigzag(highs, lows, length):
    """Pivot simmetrici (length barre a sx/dx) su high/low reali + tratto in corso fino all'ultima barra."""
    n = len(highs)
    piv = []
    for i in range(length, n - length):
        h, l = highs[i], lows[i]
        is_h = is_l = True
        for j in range(i - length, i + length + 1):
            if j == i:
                continue
            if highs[j] > h or (j < i and highs[j] == h):
                is_h = False
            if lows[j] < l or (j < i and lows[j] == l):
                is_l = False
            if not is_h and not is_l:
                break
        if is_h and is_l:
            continue
        if is_h:
            piv.append({"i": i, "p": h, "hi": True})
        if is_l:
            piv.append({"i": i, "p": l, "hi": False})
    zz = []
    for q in piv:
        if not zz:
            zz.append(q)
            continue
        last = zz[-1]
        if last["hi"] == q["hi"]:
            if (q["p"] > last["p"]) if q["hi"] else (q["p"] < last["p"]):
                zz[-1] = q
            continue
        if (q["p"] > last["p"]) if q["hi"] else (q["p"] < last["p"]):
            zz.append(q)
    if not zz:
        return zz
    # Inizio serie: estremo opposto prima del primo pivot come ancora
    first, anc = zz[0], None
    for k in range(0, first["i"]):
        va = lows[k] if first["hi"] else highs[k]
        if anc is None or ((va < anc["p"]) if first["hi"] else (va > anc["p"])):
            anc = {"i": k, "p": va, "hi": not first["hi"]}
    if anc and ((anc["p"] < first["p"]) if first["hi"] else (anc["p"] > first["p"])):
        zz.insert(0, anc)
    # Ultimo pivot spostato se il prezzo è andato oltre nella stessa direzione
    last = zz[-1]
    for k in range(last["i"] + 1, n):
        v0 = highs[k] if last["hi"] else lows[k]
        if (v0 > last["p"]) if last["hi"] else (v0 < last["p"]):
            last = {"i": k, "p": v0, "hi": last["hi"]}
            zz[-1] = last
    # Tratto in corso: estremo opposto dopo l'ultimo pivot
    best = None
    for k in range(last["i"] + 1, n):
        v = lows[k] if last["hi"] else highs[k]
        if best is None or ((v < best["p"]) if last["hi"] else (v > best["p"])):
            best = {"i": k, "p": v, "hi": not last["hi"]}
    if best:
        zz.append(best)
    return zz


def ew_engine_check(P):
    """P = prezzi normalizzati (trend sempre 'verso l'alto'); l'ultimo punto è provvisorio."""
    R = EW_ENGINE_RULES
    L = len(P) - 1
    ln = lambda a, b: abs(P[b] - P[a])
    for i in range(1, L + 1):
        conf = i < L
        if i == 1:
            if not P[1] > P[0]:
                return False
        elif i == 2:
            r2 = (P[1] - P[2]) / (P[1] - P[0])
            if (not _ew_in(r2, R["w2"])) if conf else (not 0 < r2 < 1):
                return False
        elif i == 3:
            if not P[3] > P[2]:
                return False
            if conf and (not P[3] > P[1] or not _ew_near(ln(2, 3) / ln(0, 1), R["w3_ext"], R["w3_tol"])):
                return False
        elif i == 4:
            r4 = (P[3] - P[4]) / (P[3] - P[2])
            if not P[4] > P[1]:
                return False
            if (not _ew_in(r4, R["w4"])) if conf else (not 0 < r4 < 1):
                return False
        elif i == 5:
            if not P[5] > P[4]:
                return False
            if conf:
                if not P[5] > P[3]:
                    return False
                if ln(2, 3) < ln(0, 1) and ln(2, 3) < ln(4, 5):
                    return False
        elif i == 6:
            if not P[6] < P[5]:
                return False
        elif i == 7:
            rb = (P[7] - P[6]) / (P[5] - P[6])
            if (not _ew_in(rb, R["b"])) if conf else (not 0 < rb < 1):
                return False
        elif i == 8:
            if not P[8] < P[7]:
                return False
    return True


def ew_engine_match(zz):
    end = len(zz) - 1
    for s in range(max(0, end - 8), end - 2):
        d = -1 if zz[s]["hi"] else 1
        if ew_engine_check([d * z["p"] for z in zz[s:]]):
            return s, d
    return None


def ew_engine_describe(s, d, zz, index, degree, length):
    pts = zz[s:]
    k = len(pts)
    p = [z["p"] for z in pts]
    wave = EW_WAVE_LABELS[k - 1]
    corrective = wave in ("A", "B", "C")
    wave_dir = d if wave in ("1", "3", "5", "B") else -d
    bias_dir = -d if corrective else d
    L = lambda a, b: abs(p[b] - p[a])
    lv = lambda base, sign, size, rs: [{"r": r, "v": base + sign * size * r} for r in rs]
    fibs, inval, basis = [], None, ""
    if wave == "3":
        fibs, inval, basis = lv(p[2], d, L(0, 1), [1, 1.618, 2.618]), p[2], "extension of wave 1 from end of wave 2"
    elif wave == "4":
        fibs, inval, basis = lv(p[3], -d, L(2, 3), [0.236, 0.382, 0.5]), p[1], "retracement of wave 3"
    elif wave == "5":
        fibs, inval, basis = lv(p[4], d, L(0, 1), [0.618, 1, 1.618]), p[4], "wave 1 length projected from end of wave 4"
    elif wave == "A":
        fibs, inval, basis = lv(p[5], -d, L(0, 5), [0.382, 0.5, 0.618]), p[5], "retracement of the whole 1-5 impulse"
    elif wave == "B":
        fibs, inval, basis = lv(p[6], d, L(5, 6), [0.382, 0.5, 0.618]), p[5], "retracement of wave A"
    elif wave == "C":
        fibs, inval, basis = lv(p[7], -d, L(5, 6), [0.618, 1, 1.618]), p[7], "wave A length projected from end of wave B"
    cur, tgt, reached = p[-1], None, False
    for f in fibs:
        if (f["v"] - cur) * wave_dir > 0:
            tgt = f
            break
    if tgt is None and fibs:
        tgt, reached = fibs[-1], True   # onda già oltre tutti i livelli: completamento probabile
    return {
        "degree": degree, "len": length, "k": k, "wave": wave,
        "trend": "bullish" if d > 0 else "bearish",
        "structure": "correction" if corrective else "impulse",
        "wave_up": wave_dir > 0, "bias_dir": bias_dir, "dir": d,
        "desc": (f"ABC correction of a {'bullish' if d > 0 else 'bearish'} impulse" if corrective
                 else f"{'Bullish' if d > 0 else 'Bearish'} impulse"),
        "pivots": [{"label": EW_WAVE_LABELS[n], "i": z["i"], "p": z["p"], "hi": z["hi"],
                    "time": str(index[z["i"]])[:16]} for n, z in enumerate(pts)],
        "fibs": fibs, "fib_basis": basis,
        "target": tgt["v"] if tgt else None, "target_ratio": tgt["r"] if tgt else None,
        "targets_reached": reached,
        "inval": inval,
    }


def ew_engine_run(df):
    highs = df["high"].astype(float).tolist()
    lows = df["low"].astype(float).tolist()
    degrees = []
    for name, length in EW_ENGINE_DEGREES:
        zz = ew_engine_zigzag(highs, lows, length)
        m = ew_engine_match(zz) if len(zz) >= 4 else None
        degrees.append(ew_engine_describe(m[0], m[1], zz, df.index, name, length) if m
                       else {"degree": name, "len": length, "none": True})
    # FIX 2026-10-07: il grado dipendeva solo dalla lunghezza dei pivot (4/8/16
    # barre), uguale su ogni timeframe → il 4H risultava "Intermediate" con il
    # Daily "Minor" (grado inferiore sopra a uno superiore). Ora il nome del
    # grado scala con il timeframe: Daily Minor/Intermediate/Primary, 4H
    # Minuette/Minute/Minor, 1H Subminuette/Minuette/Minute.
    _ladder = ["Subminuette", "Minuette", "Minute", "Minor", "Intermediate", "Primary"]
    try:
        _sec = pd.Series(df.index).diff().dt.total_seconds().median()
    except Exception:
        _sec = 86400
    _base = 3 if _sec >= 20 * 3600 else 1 if _sec >= 3 * 3600 else 0
    for _o in degrees:
        _step = [n for n, _ in EW_ENGINE_DEGREES].index(_o["degree"]) if _o["degree"] in [n for n, _ in EW_ENGINE_DEGREES] else 0
        _o["degree"] = _ladder[min(_base + _step, len(_ladder) - 1)]
    valid = sorted([o for o in degrees if not o.get("none")], key=lambda o: (-o["k"], -o["len"]))
    return {"primary": valid[0] if valid else None, "degrees": degrees}


def _ew_fmt(v):
    v = float(v)
    return f"{v:.5f}" if abs(v) < 10 else f"{v:.2f}"


def count_elliott_waves_engine(df):
    """
    Conteggio EW dal motore validato, restituito nello stesso formato di
    count_elliott_waves_deepscan (stesse chiavi) così il resto del bot non cambia.
    Chiavi nuove: engine, engine_degrees, trade_dir (+1 long / -1 short / 0), entry.
    """
    c = df["close"]
    p = float(c.iloc[-1])
    rv = float(rsi(c).iloc[-1])
    ml, sl_m = macd(c)
    mh = float((ml - sl_m).iloc[-1])
    av = float(atr(df).iloc[-1])
    s20 = float(c.rolling(20).mean().iloc[-1])
    s50 = float(c.rolling(50).mean().iloc[-1])
    s200 = float(c.rolling(200).mean().iloc[-1]) if len(c) >= 200 else float(c.mean())
    trend_20 = p > float(c.iloc[-20]) if len(c) > 20 else True
    trend_50 = p > float(c.iloc[-50]) if len(c) > 50 else True

    rsi_s = rsi(c)
    rsi_pk20 = float(rsi_s.iloc[-20:-1].max()) if len(rsi_s) > 20 else rv
    p_pk20 = float(c.iloc[-20:-1].max()) if len(c) > 20 else p
    rsi_lw20 = float(rsi_s.iloc[-20:-1].min()) if len(rsi_s) > 20 else rv
    p_lw20 = float(c.iloc[-20:-1].min()) if len(c) > 20 else p
    bearish_div = (p >= p_pk20 * 0.998) and (rv < rsi_pk20 - 5)
    bullish_div = (p <= p_lw20 * 1.002) and (rv > rsi_lw20 + 5)

    res = ew_engine_run(df)
    e = res["primary"]
    circ = {"1": "①", "2": "②", "3": "③", "4": "④", "5": "⑤", "A": "🅐", "B": "🅑", "C": "🅒"}
    extended = truncated = False
    w1s = w1e = w1z = 0.0
    w3e = None
    pivots = []

    if e is None:
        wn, wp = "?", "TRANSITION"
        wd = "Transition — no rule-valid wave count"
        wc = "No impulse or ABC structure passes the Fibonacci rules on any degree. Wait for structure."
        direction_up, trade_dir, entry = True, 0, p
        inv, nt, ct = p - av, p + av * 2.0, p + av
        action = "⏳ WAIT — No rule-valid wave count. No setup."
        bi = "NEUTRAL"
        degree = identify_wave_degree(df)
    else:
        wn = e["wave"]
        d = e["dir"]
        direction_up = d > 0
        pv = [x["p"] for x in e["pivots"]]
        fibs = e["fibs"]
        tgt = e["target"]
        degree = e["degree"]
        w1s, w1e = pv[0], pv[1]
        w1z = abs(w1e - w1s)
        w3e = pv[3] if len(pv) > 4 else None
        pivots = [{"type": "H" if x["hi"] else "L", "idx": x["i"], "price": x["p"]} for x in e["pivots"]]
        try:
            ti = [f["v"] for f in fibs].index(tgt)
            nxt = fibs[ti + 1]["v"] if ti + 1 < len(fibs) else tgt
        except ValueError:
            nxt = tgt
        inv = e["inval"]
        lvl_txt = ", ".join(f"{f['r']:g} = {_ew_fmt(f['v'])}" for f in fibs)
        side = lambda td: "🟢 LONG" if td > 0 else "🔴 SHORT"

        if wn in ("3", "5", "A", "C"):
            trade_dir = d if wn in ("3", "5") else -d
            entry, ct, nt = p, tgt, nxt
        elif wn == "4":
            trade_dir = d
            entry = tgt
            ct = pv[3]
            nt = entry + d * w1z
        else:  # B
            trade_dir = -d
            entry = tgt
            ct = pv[6]
            nt = entry - d * abs(pv[5] - pv[6])

        if wn == "3":
            extended = abs(pv[3] - pv[2]) / w1z > 2.618 if w1z > 0 else False
            wp = "IMPULSIVE"
            wd = f"Wave ③ — {'Extended ' if extended else ''}impulse in progress"
            action = f"{side(trade_dir)} — wave 3 in progress, target {_ew_fmt(ct)}, invalidation {_ew_fmt(inv)} (end of wave 2)"
            bi = "BULLISH" if direction_up else "BEARISH"
        elif wn == "4":
            wp = "CORRECTIVE"
            wd = "Wave ④ — corrective pullback in progress"
            action = f"{side(trade_dir)} — wait for wave 4 near {_ew_fmt(entry)}, invalidation {_ew_fmt(inv)} (wave 1 territory)"
            bi = "PULLBACK — LONG SETUP" if direction_up else "BOUNCE — SHORT SETUP"
        elif wn == "5":
            wp = "IMPULSIVE"
            wd = "Wave ⑤ — terminal impulse in progress"
            action = f"⚠️ Terminal wave — trail stops, no new entries. Projection {_ew_fmt(ct)}, invalidation {_ew_fmt(inv)}"
            bi = "BULLISH (TERMINAL ⚠️)" if direction_up else "BEARISH (TERMINAL ⚠️)"
        elif wn == "A":
            wp = "CORRECTIVE ABC"
            wd = "Wave 🅐 — first corrective leg in progress"
            action = f"{side(trade_dir)} — wave A in progress, target {_ew_fmt(ct)}, invalidation {_ew_fmt(inv)} (end of wave 5)"
            bi = "BEARISH" if direction_up else "BULLISH"
        elif wn == "B":
            wp = "CORRECTIVE ABC"
            wd = "Wave 🅑 — corrective counter-move in progress"
            action = f"{side(trade_dir)} — wait for wave B near {_ew_fmt(entry)} to trade wave C, invalidation {_ew_fmt(inv)}"
            bi = "CORRECTIVE BOUNCE — SHORT SETUP" if direction_up else "CORRECTIVE DROP — LONG SETUP"
        else:  # C
            wp = "CORRECTIVE ABC"
            wd = "Wave 🅒 — final corrective leg in progress"
            action = f"{side(trade_dir)} — wave C in progress, target {_ew_fmt(ct)}, invalidation {_ew_fmt(inv)} (end of wave B)"
            bi = "BEARISH (TERMINAL ⚠️)" if direction_up else "BULLISH (TERMINAL ⚠️)"
        wc = (f"Rule-validated count ({degree} degree, {e['desc']}). "
              f"Fibonacci ({e['fib_basis']}): {lvl_txt}.")
        if e.get("targets_reached"):
            # L'onda ha già superato tutti i livelli Fibonacci: niente nuovo ingresso
            if wn in ("4", "B"):
                entry = p
            else:
                trade_dir = 0
                bi = "NEUTRAL"
                action = (f"⏳ WAIT — wave {wn} has already exceeded all Fibonacci targets "
                          f"(last {_ew_fmt(tgt)}): completion likely, no new entry. Invalidation {_ew_fmt(inv)}")
                ct = nt = tgt
            wc += " All Fibonacci targets of the wave in progress already reached."

    mtf_conflict = ("BULL" in bi and not (trend_20 or trend_50)) or ("BEAR" in bi and (trend_20 and trend_50))
    conf_sigs = [p > s200, p > s50, p > s20, rv > 50, mh > 0, trend_20, trend_50]
    if trade_dir > 0:
        conf = sum(conf_sigs) * 13
    elif trade_dir < 0:
        conf = (7 - sum(conf_sigs)) * 13
    else:
        conf = 42
    if mtf_conflict:
        conf -= 8
    conf = max(30, min(conf, 91))

    risk = abs(entry - inv)
    rr_val = round(abs(ct - entry) / risk, 2) if risk > 0 else 0.0

    return {
        "wave_num": wn, "wave_phase": wp, "wave_desc": wd, "wave_char": wc,
        "action": action,
        "invalidation": inv, "next_target": nt, "conservative_target": ct,
        "corrective_pattern": None, "extended": extended, "alternance": "N/A",
        "diagonal": None, "truncated": truncated,
        "bearish_div": bearish_div, "bullish_div": bullish_div,
        "bias": bi, "confidence": conf, "degree": degree,
        "w1_start": w1s, "w1_end": w1e, "w1_size": w1z,
        "w3_end": w3e, "direction_up": direction_up,
        "pivots": pivots, "pivots_recent": pivots[-4:],
        "risk_reward": rr_val,
        "ew_violations": {}, "mtf_conflict": mtf_conflict,
        "cfd_validation": validate_elliott_with_cfd(wn, df["close"], df["volume"]),
        "engine": e, "engine_degrees": res["degrees"],
        "trade_dir": trade_dir, "entry": entry,
    }


def elliott_wave_analysis(df, df_4h=None, df_1h=None):
    if df is None or len(df) < 100: return None
    c  = df["close"]
    p  = float(c.iloc[-1])
    pv = float(c.iloc[-2])
    ch = ((p - pv) / pv) * 100
    rv  = float(rsi(c).iloc[-1])
    ml, sl_m = macd(c)
    mh  = float((ml - sl_m).iloc[-1])
    s20, s50, s200 = [float(c.rolling(x).mean().iloc[-1]) for x in [20, 50, 200]]
    e8, e21  = float(ema(c, 8).iloc[-1]), float(ema(c, 21).iloc[-1])
    av       = float(atr(df).iloc[-1])
    bbu, bbm, bbl = bollinger(c)
    bbu, bbm, bbl = float(bbu.iloc[-1]), float(bbm.iloc[-1]), float(bbl.iloc[-1])
    fib   = fibonacci_levels(df)
    P, R1, R2, S1, S2 = pivot_points(df)
    res   = float(df["high"].rolling(50).max().iloc[-1])
    sup   = float(df["low"].rolling(50).min().iloc[-1])

    ds    = count_elliott_waves_engine(df)
    wn    = ds["wave_num"];   wp  = ds["wave_phase"];   wd  = ds["wave_desc"]
    wc    = ds["wave_char"];  inv = ds["invalidation"];  nt  = ds["next_target"]
    ct    = ds["conservative_target"]
    cp    = ds["corrective_pattern"]; ext = ds["extended"]; alt = ds["alternance"]
    bd    = ds["bearish_div"]; bld = ds["bullish_div"]
    w1s   = ds["w1_start"];   w1e = ds["w1_end"]; w1z = ds["w1_size"]
    w3e   = ds.get("w3_end"); direction_up = ds.get("direction_up", True)
    diagonal = ds.get("diagonal"); truncated = ds.get("truncated", False)
    pivots = ds["pivots"];    pivots_recent = ds["pivots_recent"]
    bi    = ds["bias"];       conf = ds["confidence"]; degree = ds["degree"]
    rr    = ds["risk_reward"]; action = ds["action"]

    # Proiezione dal motore (livelli Fibonacci reali dell'onda in corso)
    eng = ds.get("engine")
    if eng and eng.get("target") is not None:
        pt = eng["target"]
        pl = f"{eng['target_ratio']:g} — {eng['fib_basis']}"
    else:
        pt = p + 1.5 * av
        pl = "1.5x ATR (no valid wave count)"

    mtf_4h = None
    if df_4h is not None and len(df_4h) >= 50:
        try:
            ds4 = count_elliott_waves_engine(df_4h)
            c4  = df_4h["close"]
            rv4 = float(rsi(c4).iloc[-1])
            ml4, sl4 = macd(c4)
            mh4 = float((ml4 - sl4).iloc[-1])
            mtf_4h = {
                "wave_num": ds4["wave_num"], "wave_phase": ds4["wave_phase"],
                "wave_desc": ds4["wave_desc"], "bias": ds4["bias"],
                "confidence": ds4["confidence"], "action": ds4["action"],
                "invalidation": ds4["invalidation"], "next_target": ds4["next_target"],
                "corrective_pattern": ds4["corrective_pattern"],
                "bearish_div": ds4["bearish_div"], "bullish_div": ds4["bullish_div"],
                "diagonal": ds4.get("diagonal"),
                "rsi": rv4, "macd_hist": mh4, "price": float(c4.iloc[-1]),
                "engine": ds4.get("engine"), "trade_dir": ds4.get("trade_dir", 0),
            }
        except Exception as e_4h:
            logger.warning(f"4H scan error: {e_4h}")

    mtf_1h = None
    if df_1h is not None and len(df_1h) >= 50:
        try:
            ds1 = count_elliott_waves_engine(df_1h)
            c1  = df_1h["close"]
            rv1 = float(rsi(c1).iloc[-1])
            ml1, sl1 = macd(c1)
            mh1 = float((ml1 - sl1).iloc[-1])
            av1 = float(atr(df_1h).iloc[-1])
            mtf_1h = {
                "wave_num": ds1["wave_num"], "wave_phase": ds1["wave_phase"],
                "wave_desc": ds1["wave_desc"], "bias": ds1["bias"],
                "confidence": ds1["confidence"], "action": ds1["action"],
                "invalidation": ds1["invalidation"], "next_target": ds1["next_target"],
                "corrective_pattern": ds1["corrective_pattern"],
                "bearish_div": ds1["bearish_div"], "bullish_div": ds1["bullish_div"],
                "diagonal": ds1.get("diagonal"),
                "rsi": rv1, "macd_hist": mh1, "atr": av1, "price": float(c1.iloc[-1]),
                "engine": ds1.get("engine"), "trade_dir": ds1.get("trade_dir", 0),
            }
        except Exception as e_1h:
            logger.warning(f"1H scan error: {e_1h}")

    return {
        "price": p, "chg": ch,
        "wave_num": wn, "wave_phase": wp, "wave_pos": wd, "wave_char": wc,
        "action": action,
        "degree": degree, "extended": ext, "alternance": alt, "corrective_pattern": cp,
        "diagonal": diagonal, "truncated": truncated,
        "bias": bi, "confidence": conf,
        "invalidation": inv, "next_target": nt, "conservative_target": ct,
        "risk_reward": rr, "proj_target": pt, "proj_label": pl,
        "fib_h": float(df["high"].iloc[-100:].max()), "fib_l": float(df["low"].iloc[-100:].min()),
        "fib_clusters": [], "bearish_div": bd, "bullish_div": bld,
        "rsi": rv, "macd_hist": mh, "sma20": s20, "sma50": s50, "sma200": s200,
        "ema8": e8, "ema21": e21, "atr": av,
        "bb_upper": bbu, "bb_middle": bbm, "bb_lower": bbl,
        "fib": fib, "resist": res, "support": sup,
        "pivot_P": P, "pivot_R1": R1, "pivot_R2": R2, "pivot_S1": S1, "pivot_S2": S2,
        "w1_start": w1s, "w1_end": w1e, "w1_size": w1z, "w3_end": w3e,
        "direction_up": direction_up,
        "pivots": pivots, "pivots_recent": pivots_recent,
        "t_up1": p + 1.5 * av, "t_up2": p + 2.5 * av,
        "t_dn1": p - 1.5 * av, "t_dn2": p - 2.5 * av,
        "mtf_4h": mtf_4h, "mtf_1h": mtf_1h,
        "engine": ds.get("engine"), "engine_degrees": ds.get("engine_degrees"),
        "trade_dir": ds.get("trade_dir", 0), "entry": ds.get("entry", p),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CHART GENERATION
# ═══════════════════════════════════════════════════════════════════════════════
import io
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import matplotlib.gridspec as gridspec
    from matplotlib.patches import FancyBboxPatch
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False
    logger.warning("⚠️ matplotlib non disponibile — grafici disabilitati")

DARK_BG   = '#0D1117'
DARK_PANEL= '#161B22'
GRID_COL  = '#21262D'
GREEN     = '#2ECC71'
RED       = '#E74C3C'
BLUE      = '#3498DB'
ORANGE    = '#F39C12'
PURPLE    = '#9B59B6'
WHITE     = '#E6EDF3'
GREY      = '#8B949E'
YELLOW    = '#F1C40F'

def _base_style():
    plt.rcParams.update({
        'figure.facecolor': DARK_BG,
        'axes.facecolor':   DARK_PANEL,
        'axes.edgecolor':   GRID_COL,
        'axes.labelcolor':  WHITE,
        'axes.titlecolor':  WHITE,
        'xtick.color':      GREY,
        'ytick.color':      GREY,
        'grid.color':       GRID_COL,
        'grid.linewidth':   0.5,
        'text.color':       WHITE,
        'legend.facecolor': DARK_PANEL,
        'legend.edgecolor': GRID_COL,
        'font.family':      'monospace',
        'font.size':        8,
    })

def _savefig_bytes(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor=DARK_BG, edgecolor='none')
    buf.seek(0)
    plt.close(fig)
    return buf

# ── EW chart (stile sito: navy, conteggio validato, onda in corso tratteggiata) ──
# FIX 2026-10: niente emoji nel grafico (DejaVu non ha ①②③🅐🌊 → uscivano quadratini),
# orario in UTC (prima diceva CET ma usava l'ora del server), onde reali disegnate.
EWC = {
    "bg": "#0f1724", "panel": "#111b2b", "grid": "#1e2a3d", "text": "#e2e8f0", "muted": "#8ba3c7",
    "up": "#34d399", "down": "#f87171", "target": "#60a5fa", "fib": "#64748b", "ema": "#f59e0b", "abc": "#f59e0b",
}


def _ew_pfmt(sym):
    return ".3f" if "JPY" in sym else _pf(sym)


def _ew_chart_panel(ax, df, eng, pf, label, compact=False, base_bars=90, max_bars=220):
    """Disegna candele + conteggio. Ritorna l'indice di partenza della finestra."""
    n = len(df)
    start = max(0, n - base_bars)
    if eng and eng.get("pivots"):
        start = min(start, max(0, eng["pivots"][0]["i"] - 5))
    start = max(start, n - max_bars, 0)
    seg = df.iloc[start:]
    m = len(seg)
    x = np.arange(m)
    o = seg["open"].values.astype(float); h = seg["high"].values.astype(float)
    l = seg["low"].values.astype(float); cl = seg["close"].values.astype(float)
    cols = np.where(cl >= o, EWC["up"], EWC["down"])
    lo, hi = float(np.nanmin(l)), float(np.nanmax(h))
    rng = (hi - lo) or abs(hi) * 0.01 or 1.0

    ax.set_facecolor(EWC["panel"])
    ax.grid(True, color=EWC["grid"], linewidth=0.5, alpha=0.8)
    for sp in ax.spines.values():
        sp.set_color(EWC["grid"])
    ax.tick_params(colors=EWC["muted"], labelsize=6.5 if compact else 7)
    ax.vlines(x, l, h, colors=cols, linewidth=0.7, alpha=0.9, zorder=2)
    ax.bar(x, np.maximum(np.abs(cl - o), rng * 0.0015), bottom=np.minimum(o, cl),
           color=cols, width=0.65, linewidth=0, zorder=3)
    ax.plot(x, ema(df["close"], 21).iloc[start:].values, color=EWC["ema"], lw=0.8, alpha=0.6, zorder=2)

    wcol = EWC["muted"]
    off_chart = []
    ylo, yhi = lo, hi

    def visible(y):
        return y is not None and lo - 0.35 * rng <= y <= hi + 0.35 * rng

    def hline(y, color, ls, lw, text):
        nonlocal ylo, yhi
        ax.axhline(y, color=color, ls=ls, lw=lw, alpha=0.9, zorder=1)
        ax.text(1.004, y, text, transform=ax.get_yaxis_transform(), color=color,
                fontsize=6 if compact else 6.8, va="center", ha="left", clip_on=False)
        ylo, yhi = min(ylo, y), max(yhi, y)

    if eng:
        wcol = EWC["up"] if eng["wave_up"] else EWC["down"]
        pts = [(pv["i"] - start, pv["p"], pv["label"], pv["hi"]) for pv in eng["pivots"] if pv["i"] >= start]
        if len(pts) >= 2:
            ax.plot([q[0] for q in pts[:-1]], [q[1] for q in pts[:-1]], color=EWC["text"], lw=1.5, alpha=0.85, zorder=4)
            ax.plot([pts[-2][0], pts[-1][0]], [pts[-2][1], pts[-1][1]], color=wcol, lw=1.8, ls=(0, (4, 3)), zorder=4)
            for xi, pr, lab, is_hi in pts[:-1]:
                if lab == "0":
                    continue
                corr = lab in ("A", "B", "C")
                ax.annotate(lab, (xi, pr), xytext=(0, 9 if is_hi else -9), textcoords="offset points",
                            ha="center", va="bottom" if is_hi else "top",
                            fontsize=6.5 if compact else 7.5, fontweight="bold",
                            color=EWC["abc"] if corr else EWC["text"], zorder=6,
                            bbox=dict(boxstyle="circle,pad=0.25", fc=EWC["bg"],
                                      ec=EWC["abc"] if corr else EWC["muted"], lw=0.8))
            xi, pr, lab, is_hi = pts[-1]
            txt = f"Wave ({lab})" + (" · ABC" if eng["structure"] == "correction" else "")
            ax.annotate(txt, (xi, pr), xytext=(-8, 24 if is_hi else -24), textcoords="offset points",
                        ha="right", va="center", fontsize=7 if compact else 8, fontweight="bold", color=wcol, zorder=7,
                        bbox=dict(boxstyle="round,pad=0.3", fc=EWC["bg"], ec=wcol, lw=1),
                        arrowprops=dict(arrowstyle="-|>", color=wcol, lw=1.2))
        if not compact:
            for f in eng["fibs"]:
                if f["r"] == eng["target_ratio"]:
                    continue
                if visible(f["v"]):
                    hline(f["v"], EWC["fib"], ":", 0.8, f"{f['r']:g}  {f['v']:{pf}}")
        _tname = "TGT" if compact else f"TARGET {eng['target_ratio']:g}"
        if eng.get("targets_reached"):
            _tname += " (reached)"
        for y, col, ls, name in ((eng["target"], EWC["target"], "--", _tname),
                                 (eng["inval"], EWC["down"], "--", "INV" if compact else "INVAL")):
            if y is None:
                continue
            if visible(y):
                hline(y, col, ls, 1.0, f"{name}  {y:{pf}}")
            else:
                off_chart.append(f"{name} {y:{pf}} (off-chart)")
        head = (f"{label}  ·  Wave {eng['wave']} in progress\n"
                f"{eng['desc']}  ·  {eng['degree']}")
    else:
        head = f"{label}  ·  No rule-valid count\nStructure developing — no setup"
    if off_chart:
        head += "\n" + "  ·  ".join(off_chart)

    last = float(cl[-1])
    ax.axhline(last, color=EWC["text"], lw=0.6, alpha=0.35, zorder=1)
    ax.text(1.004, last, f"{last:{pf}}", transform=ax.get_yaxis_transform(), color=EWC["bg"],
            fontsize=6.5 if compact else 7, fontweight="bold", va="center", ha="left", clip_on=False,
            bbox=dict(boxstyle="square,pad=0.2", fc=EWC["text"], ec="none"))
    ax.text(0.01, 0.98, head, transform=ax.transAxes, va="top", ha="left",
            fontsize=6.8 if compact else 8, fontweight="bold", color=wcol, zorder=8,
            bbox=dict(boxstyle="round,pad=0.35", fc=EWC["bg"], ec=wcol, lw=0.8, alpha=0.92))
    pad = (yhi - ylo) * 0.08
    ax.set_ylim(ylo - pad, yhi + pad)
    ax.set_xlim(-1, m + max(2, int(m * 0.03)))
    step = max(1, m // (4 if compact else 7))
    ticks = list(range(0, m, step))
    fmt = "%d %b" if label.startswith("DAILY") else "%d %b %H:%M"
    ax.set_xticks(ticks)
    ax.set_xticklabels([seg.index[i].strftime(fmt) for i in ticks], fontsize=6 if compact else 6.5)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:{pf}}"))
    return start


def chart_elliott(sym, df, ew, df_4h=None, df_1h=None):
    if not CHARTS_AVAILABLE or df is None or len(df) < 50 or not ew:
        return None
    try:
        mkt = MARKETS[sym]
        pf = _ew_pfmt(sym)
        e_d = ew.get("engine")
        e_4 = (ew.get("mtf_4h") or {}).get("engine")
        e_1 = (ew.get("mtf_1h") or {}).get("engine")
        lower = []
        if df_4h is not None and len(df_4h) >= 30:
            lower.append((df_4h, e_4, "4H"))
        if df_1h is not None and len(df_1h) >= 30:
            lower.append((df_1h, e_1, "1H"))

        plt.rcParams.update({"font.family": "monospace", "font.size": 7, "text.color": EWC["text"]})
        if lower:
            fig = plt.figure(figsize=(10, 11.5), facecolor=EWC["bg"])
            gs = gridspec.GridSpec(3, len(lower), height_ratios=[5.2, 1.0, 3.8], hspace=0.12, wspace=0.42,
                                   left=0.07, right=0.86, top=0.94, bottom=0.05)
        else:
            fig = plt.figure(figsize=(10, 7.5), facecolor=EWC["bg"])
            gs = gridspec.GridSpec(2, 1, height_ratios=[5.2, 1.0], hspace=0.08,
                                   left=0.07, right=0.86, top=0.92, bottom=0.07)

        ax_m = fig.add_subplot(gs[0, :])
        start = _ew_chart_panel(ax_m, df, e_d, pf, "DAILY", compact=False, base_bars=110, max_bars=240)
        plt.setp(ax_m.get_xticklabels(), visible=False)

        # RSI 14 (Wilder, come TradingView)
        ax_r = fig.add_subplot(gs[1, :], sharex=ax_m)
        dlt = df["close"].diff()
        g = dlt.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
        ls_ = (-dlt.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
        rsi_v = (100 - 100 / (1 + g / ls_.replace(0, np.nan))).iloc[start:].values
        xr = np.arange(len(rsi_v))
        ax_r.set_facecolor(EWC["panel"])
        for sp in ax_r.spines.values():
            sp.set_color(EWC["grid"])
        ax_r.plot(xr, rsi_v, color=EWC["target"], lw=0.9)
        for lvl, col in ((70, EWC["down"]), (30, EWC["up"])):
            ax_r.axhline(lvl, color=col, lw=0.6, ls="--", alpha=0.5)
        ax_r.set_ylim(0, 100)
        ax_r.set_yticks([30, 70])
        ax_r.tick_params(colors=EWC["muted"], labelsize=6.5)
        ax_r.grid(True, color=EWC["grid"], linewidth=0.5, alpha=0.8)
        ax_r.text(0.01, 0.82, "RSI 14", transform=ax_r.transAxes, color=EWC["muted"], fontsize=6.5)
        if len(rsi_v) and not np.isnan(rsi_v[-1]):
            ax_r.text(1.004, rsi_v[-1], f"{rsi_v[-1]:.0f}", transform=ax_r.get_yaxis_transform(),
                      color=EWC["target"], fontsize=6.5, va="center", clip_on=False)

        for col_i, (d_, e_, lab) in enumerate(lower):
            ax_l = fig.add_subplot(gs[2, col_i])
            _ew_chart_panel(ax_l, d_, e_, pf, lab, compact=True, base_bars=90, max_bars=160)

        fig.text(0.07, 0.975, f"ELLIOTT WAVE  ·  {mkt['name']}", fontsize=13, fontweight="bold",
                 color=EWC["text"], ha="left", va="center")
        fig.text(0.86, 0.975, datetime.utcnow().strftime("%d %b %Y  %H:%M UTC"), fontsize=8,
                 color=EWC["muted"], ha="right", va="center")
        fig.text(0.07, 0.012, "xenosfinance.com  ·  rule-validated count: W2 28–78.6% · W3 Fib ext ±15% · "
                              "W4 15–65% no overlap · B 23.6–100% of A", fontsize=6, color=EWC["muted"], ha="left")

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, facecolor=EWC["bg"], edgecolor="none")
        buf.seek(0)
        plt.close(fig)
        return buf
    except Exception as e:
        logger.error(f"chart_elliott {sym}: {e}", exc_info=True)
        try:
            plt.close("all")
        except Exception:
            pass
        return None



# ═══════════════════════════════════════════════════════════════════════════════
# GEOPOLITICS
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_geopolitics_news(max_items=10):
    all_items = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }

    for feed in GEOPOLITICS_FEEDS:
        try:
            logger.info(f"📡 Fetching feed: {feed['name']} — {feed['url']}")
            r = requests.get(feed["url"], headers=headers, timeout=20)
            if r.status_code != 200:
                logger.warning(f"⚠️ Feed {feed['name']}: HTTP {r.status_code}")
                continue

            content = r.content
            if content.startswith(b'\xef\xbb\xbf'):
                content = content[3:]

            try:
                root = ET.fromstring(content)
            except ET.ParseError as pe:
                try:
                    text = content.decode('utf-8', errors='replace')
                    text = re.sub(r'&(?!(amp|lt|gt|quot|apos|#\d+|#x[\da-fA-F]+);)', '&amp;', text)
                    root = ET.fromstring(text.encode('utf-8'))
                except Exception:
                    logger.error(f"❌ Feed {feed['name']}: XML parse error — {pe}")
                    continue

            ns = {"atom": "http://www.w3.org/2005/Atom"}
            items = root.findall(".//item")
            if not items:
                items = root.findall(".//atom:entry", ns)
            if not items:
                items = root.findall(".//entry")

            logger.info(f"✅ Feed {feed['name']}: {len(items)} items trovati")

            count = 0
            for item in items:
                if count >= 10:
                    break

                te = (item.find("title") or item.find("atom:title", ns) or
                      item.find("{http://www.w3.org/2005/Atom}title"))
                title = safe_get_text(te)
                if not title:
                    continue

                de = (item.find("description") or item.find("atom:summary", ns) or
                      item.find("{http://www.w3.org/2005/Atom}summary") or
                      item.find("atom:content", ns) or
                      item.find("{http://www.w3.org/2005/Atom}content") or
                      item.find("content"))
                desc = safe_get_text(de)

                le = (item.find("link") or item.find("atom:link", ns) or
                      item.find("{http://www.w3.org/2005/Atom}link"))
                if le is not None:
                    link = le.get("href") or (le.text or "").strip()
                else:
                    link = ""

                dte = (item.find("pubDate") or item.find("atom:updated", ns) or
                       item.find("{http://www.w3.org/2005/Atom}updated") or
                       item.find("atom:published", ns) or
                       item.find("{http://www.w3.org/2005/Atom}published"))
                date = (dte.text or "")[:30] if dte is not None else ""

                combined = (title + " " + desc).lower()
                is_geo = any(kw in combined for kw in GEOPOLITICS_KEYWORDS)

                if not is_geo:
                    count += 1
                    continue

                impacts = []
                seen = set()
                for kw, impact in IMPACT_MAP.items():
                    if kw in combined:
                        for asset in impact["assets"]:
                            if asset not in seen:
                                seen.add(asset)
                                impacts.append({"asset": asset, "dir": impact["dir"], "trigger": kw})

                all_items.append({
                    "source": feed["name"],
                    "emoji": feed["emoji"],
                    "title": title[:200],
                    "desc": desc[:300] if desc else "",
                    "link": link or "",
                    "date": date,
                    "impacts": impacts[:4]
                })
                count += 1

        except requests.exceptions.Timeout:
            logger.error(f"❌ Feed {feed['name']}: Timeout")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"❌ Feed {feed['name']}: Connessione fallita — {e}")
        except Exception as e:
            logger.error(f"❌ Feed {feed['name']}: {e}", exc_info=True)

    logger.info(f"📊 Geopolitics: {len(all_items)} news totali raccolte")

    if not all_items:
        logger.warning("⚠️ No geo news with keyword filter — retrying without filter")
        all_items = _fetch_news_no_filter(max_items)

    all_items.sort(key=lambda x: len(x["impacts"]), reverse=True)
    return all_items[:max_items]


def _fetch_news_no_filter(max_items=8):
    items_out = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    feeds_fallback = [
        {"name": "Reuters Top",   "url": "https://feeds.reuters.com/reuters/topNews",      "emoji": "📡"},
        {"name": "Al Jazeera",    "url": "https://www.aljazeera.com/xml/rss/all.xml",      "emoji": "🌐"},
        {"name": "Reuters Biz",   "url": "https://feeds.reuters.com/reuters/businessNews", "emoji": "📡"},
    ]
    for feed in feeds_fallback:
        try:
            r = requests.get(feed["url"], headers=headers, timeout=20)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:5]:
                te = item.find("title"); de = item.find("description"); le = item.find("link")
                title = safe_get_text(te)
                desc  = safe_get_text(de)
                link  = (le.text or "").strip() if le is not None else ""
                if not title:
                    continue
                combined = (title + " " + desc).lower()
                impacts = []
                seen = set()
                for kw, impact in IMPACT_MAP.items():
                    if kw in combined:
                        for asset in impact["assets"]:
                            if asset not in seen:
                                seen.add(asset)
                                impacts.append({"asset": asset, "dir": impact["dir"], "trigger": kw})
                items_out.append({
                    "source": feed["name"], "emoji": feed["emoji"],
                    "title": title[:200], "desc": desc[:300],
                    "link": link, "date": "", "impacts": impacts[:4]
                })
            if len(items_out) >= max_items:
                break
        except Exception as e:
            logger.error(f"Fallback feed {feed['name']}: {e}")
    return items_out[:max_items]


def fmt_geopolitics(items):
    now = datetime.now().strftime('%d %b %Y • %H:%M UTC')
    if not items:
        return (f"<b>🌍 GEOPOLITICAL MONITOR</b>\n{now}\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⚠️ Geopolitical news temporarily unavailable.\n"
                f"RSS feeds may be temporarily unavailable.\n\n"
                f"<i>XenosFinance Geopolitics Desk</i>")
    txt = (f"<b>🌍 GEOPOLITICAL MONITOR — MARKET IMPACT</b>\n{now}\n\n"
           f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
           f"<i>Sources: Reuters · CNBC · Al Jazeera · Yahoo Finance · AP News</i>\n\n"
           f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n")

    wi  = [i for i in items if i["impacts"]]
    nwi = [i for i in items if not i["impacts"]]

    if wi:
        txt += "<b>🔴 HIGH MARKET IMPACT NEWS</b>\n\n"
        for item in wi:
            txt += f"{item['emoji']} <b>[{item['source']}]</b>\n📰 <b>{item['title']}</b>\n"
            if item["desc"]:
                txt += f"<i>{item['desc'][:180]}...</i>\n"
            txt += "\n<b>📊 Expected impact:</b>\n"
            for imp in item["impacts"]:
                mkt = MARKETS.get(imp["asset"], {})
                di  = "📈" if imp["dir"] == "bullish" else "📉" if imp["dir"] == "bearish" else "↔️"
                dl  = "BULLISH" if imp["dir"] == "bullish" else "BEARISH" if imp["dir"] == "bearish" else "MIXED"
                txt += f"  {di} {mkt.get('emoji','•')} {mkt.get('name', imp['asset'])}: <b>{dl}</b>\n"
            if item["link"]:
                txt += f"\n🔗 <a href=\"{item['link']}\">Read article</a>\n"
            txt += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    if nwi:
        txt += "<b>📋 OTHER NEWS</b>\n\n"
        for item in nwi[:4]:
            txt += f"{item['emoji']} <b>[{item['source']}]</b> {item['title']}\n"
            if item["link"]:
                txt += f"🔗 <a href=\"{item['link']}\">Link</a>\n"
            txt += "\n"

    ai = {}
    for item in wi:
        for imp in item["impacts"]:
            a = imp["asset"]
            if a not in ai:
                ai[a] = {"bull": 0, "bear": 0, "mixed": 0}
            if imp["dir"] == "bullish":   ai[a]["bull"] += 1
            elif imp["dir"] == "bearish": ai[a]["bear"] += 1
            else:                          ai[a]["mixed"] += 1

    if ai:
        txt += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n<b>🎯 ASSET IMPACT SUMMARY</b>\n\n"
        for asset, counts in sorted(ai.items(), key=lambda x: x[1]["bull"]+x[1]["bear"], reverse=True):
            mkt = MARKETS.get(asset, {})
            ov  = ("📈 BULLISH Pressure" if counts["bull"] > counts["bear"] else
                   "📉 BEARISH Pressure" if counts["bear"] > counts["bull"] else "↔️ MIXED Signals")
            txt += f"{mkt.get('emoji','•')} <b>{mkt.get('name', asset)}:</b> {ov} ({counts['bull']}🟢 {counts['bear']}🔴)\n"

    txt += (f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ <i>Automated RSS-based analysis. Not investment advice.</i>\n\n"
            f"<i>XenosFinance Geopolitics Desk</i>" + SITE_FOOTER)
    return txt


# ─── CLAUDE AI ANALYSIS ───────────────────────────────────────────────────────
def _setup_levels(ew):
    """2026-10-07: livelli del setup (direzione, SL, TP, R/R) calcolati in UN
    solo punto e usati sia da /elliott sia da /ai. Prima /ai passava all'AI i
    livelli grezzi del motore (SL anche dal lato sbagliato o lontanissimo),
    mentre /elliott li correggeva: stesso asset, livelli diversi."""
    direction_up = ew.get("direction_up", True)
    wave_num     = ew.get("wave_num", "?")
    bias         = ew.get("bias", "")
    # Determine actual trade direction from bias, not just direction_up
    # Corrective waves A/C are bearish even in uptrend
    is_bearish = any(x in bias for x in ["BEAR", "SHORT", "CORR"])
    is_w5_term = "TERMINAL" in bias
    trade_dir  = ew.get("trade_dir")
    if trade_dir is not None:
        # FIX 2026-10: direzione dal motore. Prima A/C erano sempre "short" e
        # qualunque bias con "CORR" diventava short, anche dopo un impulso ribassista.
        if wave_num == "5":
            main_action = "trail / no new entries"
        elif trade_dir > 0:
            main_action = "long"
        elif trade_dir < 0:
            main_action = "short"
        else:
            main_action = "wait — no valid wave count"
    elif wave_num in ["A", "C"]:
        main_action = "short"
    elif wave_num == "5" or is_w5_term:
        main_action = "trail / no new entries"
    elif is_bearish:
        main_action = "short"
    else:
        main_action = "long"
    inv   = ew["invalidation"]
    price = ew["price"]
    atr_v = ew["atr"]

    # ── SL cap: max 1.5x ATR OR max 2% of price (whichever is smaller)
    # Prevents absurd SL like "buy Oil @91, SL @70" — intraday/swing only
    max_sl_dist = min(atr_v * 1.5, price * 0.02)
    min_sl_dist = atr_v * 0.3

    # Ensure tp1/tp2 are on the correct side of price
    tp1_raw = ew["next_target"]
    tp2_raw = ew["conservative_target"]
    if main_action == "long":
        # SL must be below price and within max_sl_dist
        if inv >= price or (price - inv) > max_sl_dist:
            inv = price - max(min_sl_dist, min(max_sl_dist, atr_v * 1.0))
        tp1 = max(tp1_raw, price + atr_v * 1.0)
        tp2 = max(tp2_raw, price + atr_v * 0.5)
        tp1 = min(tp1, price + atr_v * 3.0)
        tp2 = min(tp2, price + atr_v * 2.0)
    elif main_action == "short":
        # SL must be above price and within max_sl_dist
        if inv <= price or (inv - price) > max_sl_dist:
            inv = price + max(min_sl_dist, min(max_sl_dist, atr_v * 1.0))
        tp1 = min(tp1_raw, price - atr_v * 1.0)
        tp2 = min(tp2_raw, price - atr_v * 0.5)
        tp1 = max(tp1, price - atr_v * 3.0)
        tp2 = max(tp2, price - atr_v * 2.0)
    else:
        tp1 = tp1_raw
        tp2 = tp2_raw
    rr = round(abs(tp1 - price) / abs(inv - price), 1) if abs(inv - price) > 0 else ew["risk_reward"]
    return {"main_action": main_action, "wave_num": wave_num, "bias": bias,
            "inv": inv, "price": price, "atr_v": atr_v,
            "tp1": tp1, "tp2": tp2, "rr": rr, "entry": ew.get("entry", price)}


def claude_analysis_simple(name, ew, sym=None):
    """/ai — analisi quant breve (2026-10-07).
    Prima: livelli grezzi del motore (diversi da /elliott), tutti i prezzi a 5
    decimali (BTC 86000.00000), nessun conteggio del motore (l'AI poteva
    inventare un conteggio diverso da /elliott e dal sito) e una "probabilità
    %" inventata. Ora: stessi livelli di /elliott (_setup_levels), blocco
    livelli scritto dal codice, conteggio del motore come vincolo, probabilità
    = confidence del motore, max ~90 parole di commento."""
    if not ANTHROPIC_API_KEY:
        return None
    try:
        pfmt = _pf(sym) if sym else ".5f"
        lv = _setup_levels(ew)
        eng = ew.get("engine")
        eng_line = (f"EW ENGINE COUNT (authoritative, do NOT relabel): Daily {eng['degree']} degree, "
                    f"{eng['desc']}, wave {eng['wave']} in progress. "
                    + (f"Wave target {eng['target']:{pfmt}}. " if eng.get("target") else "")
                    + f"Count invalid {'below' if lv['main_action'] == 'long' else 'above'} {eng['inval']:{pfmt}} "
                    f"(the SL {lv['inv']:{pfmt}} is only a RISK STOP — breaking it does NOT invalidate the count).\n"
                    if eng else
                    "EW ENGINE COUNT: no rule-valid structure on Daily — do not assign wave labels.\n")
        prompt = f"""Analyze {name} for a trading channel, in ENGLISH.
PRICE: {ew['price']:{pfmt}} ({ew['chg']:+.2f}%)
{eng_line}BIAS: {ew['bias']} (engine confidence {ew['confidence']}%)
SETUP (fixed, shown separately to the reader): {lv['main_action']} | entry {lv['entry']:{pfmt}} | SL {lv['inv']:{pfmt}} | TP {lv['tp2']:{pfmt}} -> {lv['tp1']:{pfmt}} | R/R {lv['rr']:.1f}:1
RSI(14, Daily): {ew['rsi']:.1f} | MACD hist (Daily): {ew['macd_hist']:+.6f}
Bearish Divergence: {'YES' if ew['bearish_div'] else 'NO'} | Bullish: {'YES' if ew['bullish_div'] else 'NO'}
SMA 20/50/200: {ew['sma20']:{pfmt}}/{ew['sma50']:{pfmt}}/{ew['sma200']:{pfmt}}
ATR: {ew['atr']:{pfmt}} | Fib 38.2%: {ew['fib']['38.2']:{pfmt}} | 61.8%: {ew['fib']['61.8']:{pfmt}}

Write EXACTLY these 2 sections, nothing before or after:

\U0001f4ca Context
[2 short sentences: momentum (RSI/MACD/divergence) and trend (price vs SMA 20/50/200), and whether they support the {lv['main_action']} setup.]

\u26a0\ufe0f Risk
[1 sentence: the main risk to the setup and the level that would show it. If you mention the count, it is invalid only beyond the structural level above, never at the SL.]

RULES: MAXIMUM 90 words in total. Only cite levels listed above — no vague "clusters" or invented zones. Overbought means RSI >= 70 and oversold <= 30 only. Do NOT repeat entry/SL/TP numbers. Do NOT invent a probability — the confidence is {ew['confidence']}%. Use the engine count as given, never another one. NO asterisks, NO markdown, NO '#', NO title."""
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-5",
                "max_tokens": 350,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=60
        )
        res = r.json()
        if "content" in res and res["content"]:
            body = strip_bold(res["content"][0]["text"]).strip()
            body = re.sub(r"^#+\s*", "", body, flags=re.M)
            _i = body.find("\U0001f4ca")          # tutto ciò che precede la 1ª sezione (titoli) via
            if _i > 0: body = body[_i:]
            if lv["main_action"] in ("long", "short"):
                head = (f"\U0001f3af {lv['main_action'].upper()} setup · confidence {ew['confidence']}%\n"
                        f"Entry {lv['entry']:{pfmt}} · SL {lv['inv']:{pfmt}}\n"
                        f"TP {lv['tp2']:{pfmt}} → {lv['tp1']:{pfmt}} · R/R {lv['rr']:.1f}:1\n")
                if eng:   # stessa riga di /elliott: target e invalidazione del grafico
                    _tg = f"Wave target {eng['target']:{pfmt}} · " if eng.get("target") else ""
                    head += f"{_tg}Count invalid {'below' if lv['main_action'] == 'long' else 'above'} {eng['inval']:{pfmt}}\n"
                head += "\n"
            else:
                head = (f"\U0001f3af No new entry — {lv['main_action']}\n"
                        f"Invalidation {lv['inv']:{pfmt}}\n\n")
            return head + body
        logger.error(f"Claude /ai: no content — HTTP {r.status_code} — {str(res)[:300]}")
    except Exception as e:
        logger.error(f"Claude: {e}")
    return None


def claude_narrative_analysis(sym, ew, df):
    """
    Structured EW analysis: Major Takeaways / Main Scenario / Alternative / Analysis.
    Intraday/swing focus: H1, H4, Daily. Style: professional EW research service.
    """
    if not ANTHROPIC_API_KEY:
        return None
    try:
        mkt  = MARKETS[sym]
        name = mkt["name"]
        pfmt = _pf(sym)

        mtf_4h = ew.get("mtf_4h")
        mtf_1h = ew.get("mtf_1h")

        mtf_block = ""
        if mtf_4h:
            mtf_block += (f"4H: Wave {mtf_4h['wave_num']} {mtf_4h['wave_phase']} — "
                          f"Bias {mtf_4h['bias']} — RSI {mtf_4h['rsi']:.0f} — "
                          f"Action: {mtf_4h.get('action','')[:60]}\n")
        if mtf_1h:
            mtf_block += (f"1H: Wave {mtf_1h['wave_num']} {mtf_1h['wave_phase']} — "
                          f"Bias {mtf_1h['bias']} — RSI {mtf_1h['rsi']:.0f} — "
                          f"Action: {mtf_1h.get('action','')[:60]}\n")

        div_ctx = ""
        if ew.get("bearish_div"): div_ctx = "Bearish RSI divergence confirmed — exhaustion signal."
        if ew.get("bullish_div"): div_ctx = "Bullish RSI divergence confirmed — bearish pressure fading."

        special_ctx = ""
        if ew.get("extended"):           special_ctx += "Extended Wave 3 (>261.8% of W1). "
        if ew.get("diagonal"):           special_ctx += f"{ew['diagonal']}. "
        if ew.get("truncated"):          special_ctx += "Truncated Wave 5 — weak terminal impulse. "
        if ew.get("corrective_pattern"): special_ctx += f"Corrective pattern: {ew['corrective_pattern']}. "

        # ── VWAP / Volume Profile / Order Flow from df_1h ────────────────────
        _vwap_str = "N/A"; _vp_str = "N/A"; _of_str = "N/A"
        try:
            import numpy as _np
            if df is not None and len(df) >= 20:
                _c = df["close"].values.astype(float)
                _h = df["high"].values.astype(float)
                _l = df["low"].values.astype(float)
                _v = df["volume"].values.astype(float)
                _n = len(_c)
                _p = _c[-1]
                _pfmt2 = _pf(sym)
                # Yahoo doesn't report real traded volume for FX (and
                # sometimes raw indices) — the "volume" column comes back
                # all/mostly zero. VWAP/Volume Profile/Order Flow are
                # meaningless (or silently degrade into a disguised
                # price-only proxy) when computed on that, so skip them
                # entirely rather than publish precise-looking numbers
                # that aren't real volume analysis. Threshold: fewer than
                # half the bars having any reported volume is treated as
                # "no real volume data" for this instrument.
                _has_real_volume = (_v > 0).sum() >= (_n * 0.5)
                if not _has_real_volume:
                    raise ValueError("no real volume data for this instrument")
                # VWAP
                _tp = (_h + _l + _c) / 3
                _cv = (_np.cumsum(_v) + 1e-9)
                _vwap = float((_np.cumsum(_tp * _v)) [-1] / _cv[-1])
                _vwap_str = f"{_vwap:{_pfmt2}} ({'above' if _p > _vwap else 'below'})"
                # Volume Profile POC
                _use = min(60, _n)
                _pmin = float(_np.min(_l[-_use:])); _pmax = float(_np.max(_h[-_use:]))
                if _pmax > _pmin:
                    _bk = 30; _bsz = (_pmax - _pmin) / _bk
                    _bkts = _np.zeros(_bk)
                    for _i in range(_use):
                        _ix = min(int((_c[_n-_use+_i] - _pmin) / _bsz), _bk-1)
                        _bkts[_ix] += max(_v[_n-_use+_i], 1)
                    _poc_i = int(_np.argmax(_bkts))
                    _poc = _pmin + (_poc_i + 0.5) * _bsz
                    _tvol = _bkts.sum(); _va = _bkts[_poc_i]; _li, _hi = _poc_i, _poc_i
                    while _va < _tvol * 0.70:
                        _al = _bkts[_li-1] if _li > 0 else 0; _ah = _bkts[_hi+1] if _hi < _bk-1 else 0
                        if _ah >= _al and _hi < _bk-1: _hi += 1; _va += _ah
                        elif _li > 0: _li -= 1; _va += _al
                        else: break
                    _vah = _pmin + (_hi+1)*_bsz; _val = _pmin + _li*_bsz
                    _vp_str = (f"POC: {_poc:{_pfmt2}} | VAH: {_vah:{_pfmt2}} | VAL: {_val:{_pfmt2}}"
                               f" | Price {'ABOVE' if _p > _poc else 'BELOW'} POC"
                               f" | {'INSIDE' if _val <= _p <= _vah else 'OUTSIDE'} VA")
                # Order Flow Delta
                _use2 = min(20, _n)
                _dels = []
                for _i in range(_n-_use2, _n):
                    _rng = _h[_i] - _l[_i] + 1e-9
                    _dels.append(((_c[_i]-_l[_i])/_rng - (_h[_i]-_c[_i])/_rng) * max(_v[_i],1))
                _ofc = float(_np.sum(_dels))
                _of_bull = _ofc > 0
                _of_div = (_c[-1] > _c[-10]) != _of_bull if _n >= 10 else False
                _of_str = f"{'POSITIVE (buy aggression)' if _of_bull else 'NEGATIVE (sell aggression)'} | {'DELTA DIVERGENCE - momentum fading' if _of_div else 'No divergence'}"
        except Exception:
            pass

        _lv = _setup_levels(ew)
        main_action = _lv["main_action"]
        inv, price, atr_v = _lv["inv"], _lv["price"], _lv["atr_v"]
        tp1, tp2, rr = _lv["tp1"], _lv["tp2"], _lv["rr"]
        today = datetime.now().strftime("%d %b %Y")

        # Conteggio del motore (autoritativo): pivot reali, Fibonacci dell'onda, MTF
        eng = ew.get("engine")
        entry_px = ew.get("entry", price)
        if eng:
            _piv = "; ".join(f"({x['label']}) {x['p']:{pfmt}} on {x['time']}" + (" [in progress]" if n_ == len(eng['pivots']) - 1 else "")
                             for n_, x in enumerate(eng["pivots"]))
            _fib = ", ".join(f"{f['r']:g} = {f['v']:{pfmt}}" for f in eng["fibs"])
            _mtf_eng = []
            for _lab, _m in (("4H", mtf_4h), ("1H", mtf_1h)):
                _e = (_m or {}).get("engine")
                _mtf_eng.append(f"{_lab}: " + (f"wave {_e['wave']} in progress ({_e['desc']})" if _e else "no rule-valid count"))
            eng_block = (
                f"EW ENGINE COUNT (rule-validated, authoritative — do NOT relabel):\n"
                f"Daily {eng['degree']} degree, {eng['desc']}, wave {eng['wave']} in progress.\n"
                f"Pivots: {_piv}.\n"
                f"Fibonacci ({eng['fib_basis']}): {_fib}.\n"
                f"Structural invalidation: {eng['inval']:{pfmt}}. Setup entry: {entry_px:{pfmt}}.\n"
                f"{' | '.join(_mtf_eng)}\n"
            )
            fib_line = f"Wave Fibonacci levels: {_fib}\n"
        else:
            eng_block = "EW ENGINE COUNT: no rule-valid impulse/ABC structure on Daily — describe the structure as developing, no wave labels.\n"
            fib_line = (f"Fib 38.2%: {ew['fib']['38.2']:{pfmt}} | 50%: {ew['fib']['50.0']:{pfmt}} | 61.8%: {ew['fib']['61.8']:{pfmt}}\n")

        # Alternative scenario SL: if main SL breaks, next structural level
        # Capped at 2x ATR from price to avoid absurd levels
        alt_sl_dist = min(atr_v * 2.0, price * 0.03)
        if main_action == "long":
            alt_next_target = price - alt_sl_dist * 2
            alt_sl_note = f"below {price - alt_sl_dist:{pfmt}}"
        elif main_action == "short":
            alt_next_target = price + alt_sl_dist * 2
            alt_sl_note = f"above {price + alt_sl_dist:{pfmt}}"
        else:
            alt_next_target = price - atr_v * 2
            alt_sl_note = f"beyond {price - atr_v:{pfmt}}"

        prompt = (
            f"You are a senior Elliott Wave analyst at a professional trading research desk.\n"
            f"Write a structured intraday/swing EW analysis for {name} dated {today}.\n"
            f"Focus ONLY on H1, H4, and Daily timeframes — NO weekly or monthly references.\n\n"
            f"TECHNICAL DATA:\n"
            f"Price: {price:{pfmt}} ({ew['chg']:+.2f}%)\n"
            f"Daily: Wave {ew['wave_num']} — {ew['wave_pos']} (Degree: {ew['degree']})\n"
            f"{eng_block}"
            f"Bias: {ew['bias']} | Confidence: {ew['confidence']}%\n"
            f"{mtf_block}"
            f"RSI: {ew['rsi']:.1f} | MACD hist: {ew['macd_hist']:+.6f}\n"
            f"ATR (daily): {ew['atr']:{pfmt}}\n"
            f"SMA 20/50/200: {ew['sma20']:{pfmt}} / {ew['sma50']:{pfmt}} / {ew['sma200']:{pfmt}}\n"
            f"{fib_line}"
            f"Key support: {ew['support']:{pfmt}} | Key resistance: {ew['resist']:{pfmt}}\n"
            f"Main TP: {tp1:{pfmt}} | Conservative TP: {tp2:{pfmt}} | SL: {inv:{pfmt}} | R/R: {rr:.1f}:1\n"
            f"{div_ctx}\n{special_ctx}\n"
            f"VWAP Daily: {_vwap_str}\n"
            f"Volume Profile: {_vp_str}\n"
            f"Order Flow Delta: {_of_str}\n\n"
            # FIX 2026-10-07: analisi troppo lunghe (~450 parole, livelli ripetuti 3
            # volte, titolo/data/prezzo duplicati). I livelli ora sono un blocco
            # fisso scritto dal codice (sotto), l'AI scrive solo il ragionamento
            # in 3 sezioni brevi, max ~110 parole.
            f"OUTPUT FORMAT — EXACTLY these 3 section headers, nothing before or after:\n\n"
            f"\U0001f4c8 Scenario\n"
            f"[2 short sentences: the {main_action} idea in wave terms and the trigger that confirms it. "
            f"Do NOT repeat entry/SL/TP numbers — they are shown separately.]\n\n"
            f"\U0001f4c9 Invalidation\n"
            + (f"[1 sentence. {inv:{pfmt}} is the RISK STOP, not the count invalidation: a break of it means a deeper "
               f"pullback toward {eng['inval']:{pfmt}}; the count is invalid ONLY {'below' if main_action == 'long' else 'above'} "
               f"{eng['inval']:{pfmt}} (structural rule). Say exactly this, in your own words.]\n\n"
               if eng else
               f"[1 sentence: what a break of {inv:{pfmt}} means for the count and the next level near {alt_next_target:{pfmt}}. "
               f"No levels more than 2x ATR ({atr_v * 2:{pfmt}}) from price.]\n\n") +
            f"\U0001f50d Count\n"
            f"[2 short sentences: Daily wave in progress and where H4/H1 sit inside it, citing the engine pivots/Fibonacci.]\n\n"
            f"STRICT RULES:\n"
            f"- MAXIMUM 110 words in total. Short, dense sentences — a trader reads it in 20 seconds\n"
            f"- NO title, NO date, NO price header, NO 'Major Takeaways' — start directly with the first section header\n"
            f"- Professional English, tone like elliottwave.com EW research\n"
            f"- Use the EW ENGINE COUNT exactly as given: same wave labels, same pivots — never relabel or invent another count\n"
            f"- Only cite Fibonacci ratios and prices explicitly listed above — never invent levels or round numbers (e.g. 156.00)\n"
            f"- Current price is {price:{pfmt}}: never say price is above a level that is higher than {price:{pfmt}}, or below one that is lower\n"
            f"- Degrees: the lower timeframe is always a LOWER degree than Daily — call H4/H1 waves 'subwaves', never give them the Daily degree name\n"
            f"- NO asterisks, NO markdown, NO bullet points, NO '#'\n"
            f"- NO self-referential phrases\n"
            f"- H1/H4/Daily ONLY — no weekly/monthly\n"
        )

        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-5",
                # FIX 2026-09-22: il prompt sopra prometteva a Claude "4000
                # token disponibili" (probabile copia-incolla da un'altra
                # chiamata), ma qui il budget reale era 900 — un mismatch
                # che quasi garantiva un troncamento a metà, dato che Claude
                # scriveva puntando al budget promesso, non a quello vero.
                # Ora i due numeri combaciano, con margine reale per le 4
                # sezioni richieste (Major Takeaways, Main/Alt Scenario, Analysis).
                # 2026-10-07: testo breve (~110 parole) → 600 token bastano con margine
                "max_tokens": 600,
                "messages": [{"role": "user", "content": prompt}]
            },
            # FIX 2026-10: 40s erano troppo pochi per fino a 2000 token di output →
            # ReadTimeout → narrativa None → sul canale arrivava solo il grafico.
            timeout=120
        )
        res = r.json()
        if res.get("stop_reason") == "max_tokens":
            logger.warning("narrative AI: response truncated (max_tokens) — discarding incomplete narrative")
            return None
        if "content" in res and res["content"]:
            # 2026-10-07: blocco livelli fisso (numeri esatti del motore, mai
            # riscritti dall'AI) + ragionamento breve dell'AI.
            if main_action in ("long", "short"):
                lv = (f"\U0001f3af {main_action.upper()} setup\n"
                      f"Entry {entry_px:{pfmt}} · SL {inv:{pfmt}}\n"
                      f"TP {tp2:{pfmt}} → {tp1:{pfmt}} · R/R {rr:.1f}:1\n")
                # 2026-10-07: lo SL è uno stop di rischio (≤1.5 ATR) e i TP sono
                # limitati a 3 ATR: si mostrano anche target e invalidazione del
                # conteggio, gli stessi del grafico, così testo e chart coincidono.
                if eng:
                    _side = "below" if main_action == "long" else "above"
                    _tg = f"Wave target {eng['target']:{pfmt}} · " if eng.get("target") else ""
                    lv += f"{_tg}Count invalid {_side} {eng['inval']:{pfmt}}\n"
                lv += "\n"
            else:
                lv = (f"\U0001f3af No new entry — {main_action}\n"
                      f"Invalidation {inv:{pfmt}}\n\n")
            body = strip_bold(res["content"][0]["text"]).strip()
            body = re.sub(r"^#+\s*", "", body, flags=re.M)   # niente titoli markdown
            _i = body.find("\U0001f4c8")          # tutto ciò che precede la 1ª sezione (titoli) via
            if _i > 0: body = body[_i:]
            return lv + body
        logger.error(f"narrative AI: no content — HTTP {r.status_code} — {str(res)[:500]}")
    except Exception as e:
        logger.error(f"narrative: {type(e).__name__}: {e}")
    return None
def translate_news_it(items):
    """Traduce titoli e descrizioni delle notizie in russo professionale."""
    if not ANTHROPIC_API_KEY or not items:
        return items
    try:
        lines = []
        for i, it in enumerate(items):
            lines.append(f"{i}|TITLE|{it['title']}")
            if it.get('desc'):
                lines.append(f"{i}|DESC|{it['desc'][:250]}")
        batch = "\n".join(lines)
        prompt = (
            "Translate the following financial news headlines to professional English. "
            "Keep the exact format: NUMBER|TYPE|translated text. "
            "Translate only the text after the last |. Add nothing else.\n\n" + batch
        )
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-haiku-4-5",
                "max_tokens": 1200,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        res = r.json()
        if "content" not in res or not res["content"]:
            return items
        translated = items[:]
        for line in res["content"][0]["text"].strip().split("\n"):
            parts = line.split("|", 2)
            if len(parts) != 3: continue
            idx_s, typ, txt = parts
            try:
                idx_n = int(idx_s)
                if idx_n >= len(translated): continue
                if typ == "TITLE":
                    translated[idx_n] = {**translated[idx_n], "title": txt.strip()}
                elif typ == "DESC":
                    translated[idx_n] = {**translated[idx_n], "desc": txt.strip()}
            except ValueError:
                continue
        return translated
    except Exception as e:
        logger.warning(f"Traduzione fallita: {e}")
        return items


# ─── FORMAT HELPERS ───────────────────────────────────────────────────────────
def _pf(sym):
    # 2026-10-07: coppie JPY a 3 decimali (158.425, non 158.42500) e crypto a
    # basso prezzo a 4 (XRP 1.5042, non 1.50): ora i livelli li scrive il codice.
    if sym.endswith("JPY"):
        return ".3f"
    if sym in ["EURUSD","GBPUSD","AUDUSD","USDCHF","USDCAD","NZDUSD"]:
        return ".5f"
    if sym in ["XRPUSD","DOGEUSD","ADAUSD","XLMUSD"]:
        return ".4f"
    return ".2f"


def fmt_elliott(sym, ew):
    c    = MARKETS[sym]
    pfmt = _pf(sym)
    now_str = datetime.now().strftime('%d %b %Y  \u2022  %H:%M CET')
    a    = "\U0001f4c8" if ew["chg"] > 0 else "\U0001f4c9"

    wi_map = {"1":"\u2460","2":"\u2461","3":"\u2462","4":"\u2463","5":"\u2464",
              "A":"\U0001f170","B":"\U0001f171","C":"\U0001f172","?":"\u2753"}
    wi   = wi_map.get(ew['wave_num'], "\U0001f30a")
    pc   = {"IMPULSIVA":"\U0001f7e2","CORRETTIVA":"\U0001f534","CORRETTIVA ABC":"\U0001f7e0",
            "TRANSIZIONE":"\u26aa"}.get(ew['wave_phase'], "\u26aa")
    rr   = ew.get('risk_reward', 0)
    ri   = "\U0001f7e2" if rr >= 3 else "\U0001f7e1" if rr >= 2 else "\U0001f534"

    p_now = ew['price']
    inv   = ew['invalidation']
    nt    = ew['next_target']
    ct    = ew['conservative_target']
    atr_v = ew['atr']
    wn    = ew['wave_num']

    primary_bull = wn in ['1','2','3','4','5']
    w5_terminal  = wn == '5'

    if primary_bull:
        if wn in ['1','3','5']:
            entry = p_now
            tp1   = max(nt, ct, p_now + atr_v)          # always above entry
            tp2   = tp1 + abs(tp1 - entry) * 0.5         # further above tp1
            sl    = inv
        else:
            entry = ct
            tp1   = max(nt, entry + atr_v)               # always above entry
            tp2   = tp1 + abs(tp1 - entry) * 0.5
            sl    = inv
        alt_entry = inv - atr_v * 0.1
        alt_tp    = inv - atr_v * 2.5                    # below inv for short
        alt_sl    = p_now + atr_v * 0.5
    else:
        entry = p_now
        tp1   = min(nt, ct, p_now - atr_v)              # always below entry
        tp2   = tp1 - abs(entry - tp1) * 0.5             # further below tp1
        sl    = inv
        alt_entry = inv + atr_v * 0.1
        alt_tp    = inv + atr_v * 2                      # above inv for long
        alt_sl    = p_now - atr_v * 0.5

    alerts = []
    if ew.get('bearish_div'):   alerts.append("\u26a0\ufe0f Bearish RSI Divergence")
    if ew.get('bullish_div'):   alerts.append("\U0001f4a1 Bullish RSI Divergence")
    if ew.get('mtf_conflict'):  alerts.append("\u26a1 MTF Conflict \u2014 reduce size")
    violations = ew.get('ew_violations', {})
    vmap = {"w3_shortest":"W3 may be shortest","w4_invades_w1":"W4 invades W1","w2_beyond_start":"W2 beyond W1 start"}
    for v in violations:
        alerts.append("\U0001f6a8 " + vmap.get(v, v))
    if ew.get('extended'):     alerts.append("\u26a1 Extended Wave 3")
    if ew.get('truncated'):    alerts.append("\u26a1 W5 Truncated")
    if ew.get('diagonal'):     alerts.append("\U0001f4d0 " + ew['diagonal'])
    if ew.get('corrective_pattern') and wn in ['2','4','B']:
        alerts.append("\U0001f4ca " + ew['corrective_pattern'])

    alerts_lines = ["  " + x for x in alerts]
    alerts_str = ("\n" + "\n".join(alerts_lines) + "\n") if alerts_lines else ""

    def _mtf(tf_data, label):
        if not tf_data: return ""
        wn_ = tf_data.get('wave_num','?')
        bi_ = tf_data.get('bias','')
        rv_ = tf_data.get('rsi', 0)
        wi_ = wi_map.get(wn_, wn_)
        col = "\U0001f7e2" if "BULL" in bi_ else "\U0001f534" if "BEAR" in bi_ else "\U0001f7e1"
        div = " \u26a0\ufe0fdiv" if tf_data.get('bearish_div') else (" \U0001f4a1div" if tf_data.get('bullish_div') else "")
        return "  " + label + "  " + col + " Wave " + wi_ + "  RSI " + str(round(rv_)) + div + "\n"

    mtf_str = ""
    if ew.get('mtf_4h') or ew.get('mtf_1h'):
        mtf_str = _mtf(ew.get('mtf_4h'), "4H \u00b7") + _mtf(ew.get('mtf_1h'), "1H \u00b7")

    SEP = "\u2501" * 32
    FMT = "{:" + pfmt + "}"

    lines = []
    lines.append("<b>🌊 ELLIOTT WAVE  ·  " + c['emoji'] + " " + c['name'] + "</b>")
    lines.append("<i>" + now_str + "</i>")
    lines.append(SEP)
    lines.append("")
    lines.append("<b>I.  WAVE COUNT</b>")
    lines.append("Degree   <b>" + ew['degree'] + "</b>")
    lines.append("Position <b>Wave " + ew['wave_pos'] + "</b>  " + pc)
    lines.append("Bias     <b>" + ew['bias'] + "</b>  \u00b7  Confidence <b>" + "{:.0f}%".format(ew['confidence']) + "</b>")

    if mtf_str:
        lines.append("")
        lines.append("<b>Multi-Timeframe</b>")
        lines.append(mtf_str.rstrip())

    if alerts_str:
        lines.append("")
        lines.append("<b>Alerts</b>")
        lines.append(alerts_str.strip())

    lines.append("")
    lines.append(SEP)
    lines.append("")
    lines.append("<b>II.  TRADE SETUP</b>")

    if w5_terminal:
        lines.append("\u26a0\ufe0f <b>Terminal Wave \u2014 Manage Open Longs</b>")
        lines.append("Trail SL    <code>" + FMT.format(sl) + "</code>")
        lines.append("TP1         <code>" + FMT.format(tp1) + "</code>")
        lines.append("TP2         <code>" + FMT.format(tp2) + "</code>")
        lines.append("")
        lines.append("\U0001f4c9 <b>Reversal Setup</b>")
        lines.append("Short below <code>" + FMT.format(sl) + "</code>")
        lines.append("Target      <code>" + FMT.format(alt_tp) + "</code>  \u00b7  SL <code>" + FMT.format(alt_sl) + "</code>")
    elif primary_bull:
        lines.append("\U0001f4c8 <b>Primary \u2014 LONG</b>")
        lines.append("Entry       <code>" + FMT.format(entry) + "</code>")
        lines.append("TP1         <code>" + FMT.format(tp1) + "</code>")
        lines.append("TP2         <code>" + FMT.format(tp2) + "</code>")
        lines.append("Stop Loss   <code>" + FMT.format(sl) + "</code>")
        lines.append("")
        lines.append("\U0001f4c9 <b>Alternate \u2014 SHORT</b>")
        lines.append("Entry below <code>" + FMT.format(inv) + "</code>")
        lines.append("Target      <code>" + FMT.format(alt_tp) + "</code>  \u00b7  SL <code>" + FMT.format(alt_sl) + "</code>")
    else:
        lines.append("\U0001f4c9 <b>Primary \u2014 SHORT</b>")
        lines.append("Entry       <code>" + FMT.format(entry) + "</code>")
        lines.append("TP1         <code>" + FMT.format(tp1) + "</code>")
        lines.append("TP2         <code>" + FMT.format(tp2) + "</code>")
        lines.append("Stop Loss   <code>" + FMT.format(sl) + "</code>")
        lines.append("")
        lines.append("\U0001f4c8 <b>Alternate \u2014 LONG</b>")
        lines.append("Entry above <code>" + FMT.format(inv) + "</code>")
        lines.append("Target      <code>" + FMT.format(alt_tp) + "</code>  \u00b7  SL <code>" + FMT.format(alt_sl) + "</code>")

    lines.append("")
    lines.append("Invalidation  <code>" + FMT.format(inv) + "</code>")
    lines.append("Risk/Reward   " + ri + " <b>" + "{:.1f}".format(rr) + " : 1</b>")
    lines.append("")
    lines.append("<i>XenosFinance \u2014 Elliott Wave Desk</i>" + SITE_FOOTER)

    return "\n".join(lines)

def fmt_ai(sym, txt):
    # 2026-10-07: testo AI escapato (un "<" o "&" faceva rifiutare il messaggio
    # da Telegram), ora UTC reale (il server è in UTC: "CET" era sbagliato),
    # footer del canale come /elliott.
    import html as _html
    c = MARKETS[sym]
    return (f"<b>🤖 AI ANALYSIS — {c['emoji']} {c['name']}</b>\n"
            f"<i>{datetime.utcnow().strftime('%d %b %Y • %H:%M UTC')}</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n{_html.escape(txt, quote=False)}"
            + SITE_FOOTER)


# ─── TELEGRAM HELPERS ─────────────────────────────────────────────────────────
async def send_channel_photo(img_buf, caption=""):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID or img_buf is None: return False
    try:
        img_buf.seek(0)
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
            data={"chat_id": TELEGRAM_CHANNEL_ID, "parse_mode": "HTML",
                  "disable_web_page_preview": "true"},
            files={"photo": ("chart.png", img_buf, "image/png")},
            timeout=30
        )
        data = r.json()
        message_id = data.get("result", {}).get("message_id")
        if message_id:
            try:
                update_blog_tg_post(message_id)
            except Exception as e:
                logger.warning(f"blog tg photo update failed: {e}")
        return data.get("ok", False)
    except Exception as e:
        logger.error(f"send_photo: {e}"); return False

async def send_channel(t):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID: return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHANNEL_ID, "text": t, "parse_mode": "HTML",
                  "disable_web_page_preview": True, "reply_markup": json.dumps(SITE_KEYBOARD)},
            timeout=15
        )
        data = r.json()
        ok = data.get("ok", False)
        if not ok:
            logger.error(f"send_channel failed: {data}")
            return False
        # Update XenosBlog.html widget with latest post number
        message_id = data.get("result", {}).get("message_id")
        if message_id:
            try:
                update_blog_tg_post(message_id)
            except Exception as e:
                logger.warning(f"blog tg update failed: {e}")
        return message_id or True
    except Exception as e:
        logger.error(f"send: {e}"); return False

def update_blog_tg_post(message_id):
    """Update XenosBlog.html on GitHub — only replaces the telegram post number. Nothing else touched."""
    if not GITHUB_TOKEN:
        return
    import re as _re
    api = f"https://api.github.com/repos/{GITHUB_REPO}/contents/XenosBlog.html"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    r = requests.get(api, headers=headers, timeout=15)
    if r.status_code != 200:
        logger.warning(f"blog fetch failed: {r.status_code}")
        return
    data = r.json()
    sha = data.get("sha", "")
    content = base64.b64decode(data["content"]).decode("utf-8")

    # Replace ONLY the post number in data-telegram-post="xenosfin/XXXX"
    new_content = _re.sub(
        r'data-telegram-post="xenosfin/\d+"',
        f'data-telegram-post="xenosfin/{message_id}"',
        content
    )

    if new_content == content:
        logger.info("blog tg: no change needed")
        return

    encoded = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")
    payload = {
        "message": f"Update Telegram post widget → {message_id}",
        "content": encoded,
        "sha": sha,
        "committer": {"name": "XenosFinance Bot", "email": "bot@xenosfinance.com"}
    }
    r2 = requests.put(api, headers=headers, json=payload, timeout=30)
    if r2.status_code in [200, 201]:
        logger.info(f"✅ XenosBlog.html updated — Telegram post {message_id}")
    else:
        logger.error(f"❌ blog update failed: {r2.status_code}")


# ═══════════════════════════════════════════════════════════════════════════════
# TRADING IDEAS — GitHub JSON storage
# ═══════════════════════════════════════════════════════════════════════════════

TRADING_IDEAS_FILE = "trading_ideas/ideas.json"
TRADING_IDEAS_MAX  = 50
EW_SIGNALS_FILE    = "ew_signals/signals.json"
EW_SIGNALS_MAX     = 100

def _github_json_read(path):
    api = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    r = requests.get(api, headers=headers, timeout=15)
    if r.status_code == 404:
        return [], ""
    if r.status_code != 200:
        logger.warning(f"github read {path}: {r.status_code}")
        return None, None
    data = r.json()
    try:
        content = json.loads(base64.b64decode(data["content"]).decode("utf-8"))
    except Exception:
        content = []
    return content, data.get("sha", "")

def _strip_html(text: str) -> str:
    """Rimuove tag HTML Telegram e corregge double-encoding UTF-8."""
    import re
    text = re.sub(r'<[^>]+>', '', text or '')
    text = text.strip()
    # Fix double-encoded UTF-8 (Railway latin-1 issue)
    try:
        fixed = text.encode('latin-1').decode('utf-8')
        text = fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return text


def _github_json_write(path, content, sha, commit_msg):
    api = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    encoded = base64.b64encode(json.dumps(content, ensure_ascii=False, indent=2).encode("utf-8")).decode("utf-8")
    payload = {"message": commit_msg, "content": encoded, "committer": {"name": "XenosFinance Bot", "email": "bot@xenosfinance.com"}}
    if sha:
        payload["sha"] = sha
    r = requests.put(api, headers=headers, json=payload, timeout=30)
    if r.status_code in [200, 201]:
        logger.info(f"✅ github write OK: {path}")
        return True
    logger.error(f"❌ github write FAILED {path}: {r.status_code} — {r.text[:300]}")
    return False

def _github_image_upload(image_bytes, filename):
    path = f"trading_ideas/charts/{filename}"
    api  = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    r = requests.get(api, headers=headers, timeout=15)
    sha = r.json().get("sha", "") if r.status_code == 200 else ""
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    payload = {"message": f"Trading Idea chart: {filename}", "content": encoded, "committer": {"name": "XenosFinance Bot", "email": "bot@xenosfinance.com"}}
    if sha:
        payload["sha"] = sha
    r2 = requests.put(api, headers=headers, json=payload, timeout=30)
    if r2.status_code in [200, 201]:
        raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{path}"
        logger.info(f"✅ Chart uploaded: {raw_url}")
        return raw_url
    logger.error(f"image upload failed: {r2.status_code}")
    return None

def save_trading_idea(sym, ew, narrative, img_buf=None):
    if not GITHUB_TOKEN:
        logger.warning("⚠️ GITHUB_TOKEN mancante — Trading Idea non salvata")
        return False
    if not ew:
        return False
    import uuid as _uuid
    idea_id   = _uuid.uuid4().hex[:12]
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    mkt       = MARKETS.get(sym, {})
    image_url = None
    if img_buf is not None:
        try:
            img_buf.seek(0)
            image_bytes = img_buf.read()
            img_buf.seek(0)
            filename  = f"{sym}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{idea_id[:6]}.png"
            image_url = _github_image_upload(image_bytes, filename)
        except Exception as e:
            logger.warning(f"chart upload error: {e}")
    wi_map = {"1":"①","2":"②","3":"③","4":"④","5":"⑤","A":"🅐","B":"🅑","C":"🅒","?":"❓"}
    # Derive clean bias for Trading Ideas page
    raw_bias = ew.get("bias", "NEUTRAL")
    if "BULL" in raw_bias or "LONG" in raw_bias:
        clean_bias = "LONG"
    elif "BEAR" in raw_bias or "SHORT" in raw_bias:
        clean_bias = "SHORT"
    else:
        clean_bias = "NEUTRAL"
    price_now   = float(ew.get("price", 0))
    raw_target  = float(ew.get("next_target", 0))
    raw_inv     = float(ew.get("invalidation", 0))
    is_long     = clean_bias == "LONG"

    # Sanity check: target must be on the correct side of price
    # LONG: target > price, invalidation < price
    # SHORT: target < price, invalidation > price
    if price_now > 0 and raw_target > 0:
        target_ok = (raw_target > price_now) if is_long else (raw_target < price_now)
        if not target_ok:
            # Try conservative_target as fallback
            alt_target = float(ew.get("conservative_target", 0))
            alt_ok = (alt_target > price_now) if is_long else (alt_target < price_now)
            if alt_ok:
                raw_target = alt_target
                logger.warning(f"save_trading_idea {sym}: next_target {ew.get('next_target')} wrong side — using conservative_target {alt_target}")
            else:
                # Last resort: ATR-based target
                atr_v = float(ew.get("atr", price_now * 0.01))
                raw_target = price_now + atr_v * 2.0 if is_long else price_now - atr_v * 2.0
                logger.warning(f"save_trading_idea {sym}: both targets wrong side — using ATR fallback {raw_target:.5f}")

    if price_now > 0 and raw_inv > 0:
        inv_ok = (raw_inv < price_now) if is_long else (raw_inv > price_now)
        if not inv_ok:
            atr_v = float(ew.get("atr", price_now * 0.01))
            raw_inv = price_now - atr_v * 1.5 if is_long else price_now + atr_v * 1.5
            logger.warning(f"save_trading_idea {sym}: invalidation {ew.get('invalidation')} wrong side — using ATR fallback {raw_inv:.5f}")

    idea = {
        "id":           idea_id,
        "timestamp":    timestamp,
        "ticker":       sym,
        "name":         mkt.get("name", sym),
        "emoji":        mkt.get("emoji", "📊"),
        "timeframe":    "MTF",
        "wave_num":     ew.get("wave_num", "?"),
        "wave_icon":    wi_map.get(ew.get("wave_num","?"), "🌊"),
        "wave_phase":   ew.get("wave_phase", ""),
        "bias":         clean_bias,
        "confidence":   ew.get("confidence", 0),
        "price":        price_now,
        "target":       round(raw_target, 5),
        "invalidation": round(raw_inv, 5),
        "analysis":     _strip_html(narrative or ""),
        "image_url":    image_url or "",
    }
    ideas, sha = _github_json_read(EW_SIGNALS_FILE)
    if ideas is None:
        logger.warning("ew_signals/signals.json not found — creating new")
        ideas, sha = [], None
    ideas.insert(0, idea)
    if len(ideas) > EW_SIGNALS_MAX:
        ideas = ideas[:EW_SIGNALS_MAX]
    ok = _github_json_write(EW_SIGNALS_FILE, ideas, sha, f"EW Signal: {sym} Wave {ew.get('wave_num','?')} {timestamp}")
    if ok:
        logger.info(f"✅ EW Signal salvato: {sym} [{idea_id}]")
    return ok


async def send_long(text):
    """Invia un testo lungo spezzandolo in parti da max 4096 caratteri."""
    parts = split_message(text, max_len=4096)
    for part in parts:
        await send_channel(part)

async def check_auth(u):
    if u.effective_user.id != OWNER_ID:
        await u.message.reply_text("🚫 Access denied"); return False
    return True

def parse_symbol(args):
    if not args: return None
    s = args[0].upper().replace("/", "")
    s = ALIASES.get(s, s)
    return s if s in MARKETS else None


# ═══════════════════════════════════════════════════════════════════════════════
# DAILY NEWS BRIEF
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_news_for_brief(max_items=12):
    all_items = []
    feeds = [
        {"url": "https://finance.yahoo.com/rss/topstories",                        "name": "Yahoo Finance"},
        {"url": "https://finance.yahoo.com/rss/news",                              "name": "Yahoo News"},
        {"url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",          "name": "CNBC Markets"},
        {"url": "https://feeds.reuters.com/reuters/businessNews",        "name": "Reuters Markets"},
        {"url": "https://feeds.reuters.com/reuters/topNews",             "name": "Reuters Top"},
        {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml","name": "NYT Business"},
        {"url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml","name": "NYT World"},
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
        "Accept-Language": "en-US,en;q=0.9",
    }

    for feed in feeds:
        if len(all_items) >= max_items * 2:
            break
        try:
            r = requests.get(feed["url"], headers=headers, timeout=20)
            if r.status_code != 200:
                continue

            content = r.content
            if content.startswith(b'\xef\xbb\xbf'):
                content = content[3:]

            try:
                root = ET.fromstring(content)
            except ET.ParseError:
                try:
                    text = content.decode('utf-8', errors='replace')
                    text = re.sub(r'&(?!(amp|lt|gt|quot|apos|#\d+|#x[\da-fA-F]+);)', '&amp;', text)
                    root = ET.fromstring(text.encode('utf-8'))
                except Exception as e2:
                    continue

            items_xml = root.findall(".//item")
            for item in items_xml[:8]:
                te  = item.find("title")
                de  = item.find("description")
                dte = item.find("pubDate")
                title = safe_get_text(te)
                desc  = safe_get_text(de)
                date  = (dte.text or "")[:25] if dte is not None else ""

                link = ""
                le = item.find("link")
                if le is not None:
                    link = le.get("href", "") or (le.text or "").strip() or (le.tail or "").strip()
                if not link:
                    guid = item.find("guid")
                    if guid is not None and guid.text and guid.text.startswith("http"):
                        link = guid.text.strip()

                if not title:
                    continue

                impacts = []
                combined = (title + " " + desc).lower()
                for kw, imp in IMPACT_MAP.items():
                    if kw in combined:
                        for asset in imp["assets"][:2]:
                            impacts.append({"asset": asset, "dir": imp["dir"], "kw": kw})

                all_items.append({
                    "source": feed["name"], "title": title[:200],
                    "desc": desc[:300] if desc else "", "link": link,
                    "date": date, "impacts": impacts[:3]
                })

        except Exception as e:
            logger.error(f"❌ {feed['name']}: {e}")

        if len(all_items) >= max_items * 2:
            break

    all_items.sort(key=lambda x: len(x["impacts"]), reverse=True)

    seen_titles = set()
    deduped = []
    for item in all_items:
        key = item["title"][:60].lower()
        if key not in seen_titles:
            seen_titles.add(key)
            deduped.append(item)

    return deduped[:max_items]


def fetch_prices_for_brief():
    syms = {
        "OIL": "CL=F", "GOLD": "GC=F", "EURUSD": "EURUSD=X",
        "BTCUSD": "BTC-USD", "SPY": "SPY", "NASDAQ": "^IXIC",
        "USDJPY": "USDJPY=X", "NVDA": "NVDA", "NGAS": "NG=F"
    }
    prices = {}
    for name, yf_sym in syms.items():
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_sym}"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"},
                             params={"range": "5d", "interval": "5m"}, timeout=10)
            d = r.json()["chart"]["result"][0]
            closes = [x for x in d["indicators"]["quote"][0]["close"] if x is not None]
            if len(closes) < 2:
                raise ValueError("not enough data")
            p   = float(closes[-1])
            meta = d.get("meta", {})
            pv  = float(meta.get("previousClose") or meta.get("chartPreviousClose") or closes[-2])
            chg = ((p - pv) / pv) * 100
            prices[name] = {"p": p, "chg": chg}
        except Exception as e:
            logger.warning(f"⚠️ Price {name}: {e}")
            prices[name] = None
    return prices

def price_fmt(name, px):
    if not px: return ""
    sym_labels = {
        "OIL": "OIL", "GOLD": "GOLD", "EURUSD": "EUR/USD",
        "BTCUSD": "BTC", "SPY": "S&P 500", "NASDAQ": "NASDAQ",
        "USDJPY": "USD/JPY", "NVDA": "NVDA", "NGAS": "NAT GAS"
    }
    label = sym_labels.get(name, name)
    arrow = "▲" if px["chg"] >= 0 else "▼"
    cls   = "tick-up" if px["chg"] >= 0 else "tick-dn"
    if name in ["EURUSD", "USDJPY"]:   val = f"{px['p']:.4f}"
    elif name in ["BTCUSD", "NASDAQ"]: val = f"${px['p']:,.0f}"
    elif name in ["SPY", "NVDA"]:      val = f"${px['p']:.2f}"
    else:                               val = f"${px['p']:.2f}"
    return (f'<span class="tick"><span class="tick-sym">{label}</span>'
            f'<span class="{cls}">{val}</span>'
            f'<span class="{cls}">{arrow} {px["chg"]:+.2f}%</span></span>'
            f'<span class="tick-sep">|</span>')


def fetch_index_template():
    """Fetch the current index.html from GitHub to preserve layout."""
    try:
        api = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        r = requests.get(api, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return base64.b64decode(data["content"]).decode("utf-8"), data.get("sha", "")
    except Exception as e:
        logger.error(f"fetch_index_template error: {e}")
    return None, ""


def generate_news_html(news_items, prices):
    """
    Inject news into the correct index.html template using per-section markers.
    Markers: XENOS_ECO_START/END, XENOS_GEO_START/END, XENOS_AI_START/END, XENOS_STATUS, XENOS_TS
    Layout, CSS, JS, Macro Matrix, Economic Map are NEVER touched.
    """
    import re as _re
    now = datetime.now()
    time_str = now.strftime("%H:%M")
    ts = now.strftime("%Y%m%d%H%M%S")

    template, _ = fetch_index_template()

    if not template or "XENOS_ECO_START" not in template:
        logger.warning("⚠️ Template markers not found — skipping push to preserve layout")
        return None  # Return None = skip push entirely

    def tag_html(t):
        cls = "tag-bull" if t.get("dir") == "bull" else ("tag-geo" if t.get("dir") == "geo" else "tag-bear")
        arr = "▲" if t.get("dir") == "bull" else ("⚠" if t.get("dir") == "geo" else "▼")
        return f'<span class="news-tag {cls}">{arr} {t.get("asset","")}</span>'

    def detect_tags(title, desc):
        t = (title + " " + (desc or "")).lower()
        tags = []
        if "gold" in t and any(k in t for k in ["rise","gain","high","rally"]): tags.append({"l":"▲ Gold","c":"tag-bull"})
        if "gold" in t and any(k in t for k in ["fall","drop","low"]): tags.append({"l":"▼ Gold","c":"tag-bear"})
        if "oil" in t and any(k in t for k in ["rise","opec","cut"]): tags.append({"l":"▲ Oil","c":"tag-bull"})
        if "oil" in t and any(k in t for k in ["fall","oversupply"]): tags.append({"l":"▼ Oil","c":"tag-bear"})
        if any(k in t for k in ["rally","surge","bull"]): tags.append({"l":"▲ Mkt","c":"tag-bull"})
        if any(k in t for k in ["selloff","plunge","crash"]): tags.append({"l":"▼ Mkt","c":"tag-bear"})
        if any(k in t for k in ["war","conflict","sanction","military"]): tags.append({"l":"⚠ Geo","c":"tag-geo"})
        if any(k in t for k in ["rate","inflation","gdp","fed","ecb"]): tags.append({"l":"◈ Macro","c":"tag-macro"})
        return tags[:2]

    def item_html(a):
        tags = detect_tags(a.get("title",""), a.get("desc",""))
        tags_html = "".join(f'<span class="news-tag {t["c"]}">{t["l"]}</span>' for t in tags)
        lnk = a.get("link","")
        title = a.get("title","")
        desc = a.get("desc","")
        src = a.get("source","").upper()
        title_html = f'<a href="{lnk}" target="_blank" rel="noopener">{title}</a>' if lnk else title
        desc_html = f'<div class="news-desc">{desc[:180]}</div>' if desc else ""
        tags_wrap = f'<div class="news-tags">{tags_html}</div>' if tags_html else ""
        return (f'<div class="news-item">'
                f'<div class="news-src">{src} · {time_str} CET</div>'
                f'<div class="news-hl">{title_html}</div>'
                f'{desc_html}{tags_wrap}'
                f'</div>')

    ECO_KW = ["fed","rate","inflation","gdp","cpi","jobs","unemployment","earnings","recession","treasury","bond","yield","tariff","fiscal","monetary","bank","economic","economy","growth","trade","stock","market","nasdaq","oil price","gold price","crypto","bitcoin","trade war","energy","forecast","outlook"]
    GEO_KW = ["war","conflict","attack","military","troops","nato","ukraine","russia","china","israel","iran","middle east","taiwan","north korea","sanctions","coup","election","president","minister","summit","nuclear","missile","threat","border","embargo","opec","pipeline","geopolit"]

    def classify(title, summary):
        t = (title + " " + (summary or "")).lower()
        eco = sum(1 for k in ECO_KW if k in t)
        geo = sum(1 for k in GEO_KW if k in t)
        return "geo" if geo > eco + 1 else "eco"

    eco_items = [a for a in news_items if classify(a.get("title",""), a.get("desc","")) == "eco"]
    geo_items = [a for a in news_items if classify(a.get("title",""), a.get("desc","")) == "geo"]

    eco_html = "".join(item_html(a) for a in eco_items[:12]) if eco_items else '<div class="empty-row">No economic stories right now</div>'
    geo_html = "".join(item_html(a) for a in geo_items[:12]) if geo_items else '<div class="empty-row">No geopolitical stories right now</div>'

    # AI brief from prices
    price_lines = []
    for sym, label in [("GC=F","Gold"),("CL=F","Oil WTI"),("EURUSD","EUR/USD"),("BTC-USD","Bitcoin"),("SPY","S&P500")]:
        p = prices.get(sym) or prices.get(label) or {}
        if p.get("price"):
            chg = p.get("change_pct", 0)
            price_lines.append(f"{label}: {p['price']:.2f} ({chg:+.2f}%)")

    headlines = [a.get("title","") for a in news_items[:8]]
    ai_html = f'<div id="ai-brief" class="ai-text"><p style="color:var(--muted)">Brief generated {time_str} CET — {len(news_items)} stories loaded. Markets: {" · ".join(price_lines[:3])}</p></div>'

    # Inject into template
    result = _re.sub(r'<!-- XENOS_ECO_START -->.*?<!-- XENOS_ECO_END -->',
        f'<!-- XENOS_ECO_START -->\n{eco_html}\n<!-- XENOS_ECO_END -->', template, flags=_re.DOTALL)
    result = _re.sub(r'<!-- XENOS_GEO_START -->.*?<!-- XENOS_GEO_END -->',
        f'<!-- XENOS_GEO_START -->\n{geo_html}\n<!-- XENOS_GEO_END -->', result, flags=_re.DOTALL)
    result = _re.sub(r'<!-- XENOS_AI_START -->.*?<!-- XENOS_AI_END -->',
        f'<!-- XENOS_AI_START -->\n{ai_html}\n<!-- XENOS_AI_END -->', result, flags=_re.DOTALL)
    result = result.replace('<!-- XENOS_STATUS -->', f'✓ {len(news_items)} stories · {time_str} CET · Finnhub')
    result = _re.sub(r'content="XENOS_TS"', f'content="{ts}"', result)
    result = _re.sub(r'content="\d{14}"', f'content="{ts}"', result)

    logger.info(f"✅ Template injection OK — {len(eco_items)} eco, {len(geo_items)} geo stories injected")
    return result


def _generate_news_html_full(news_items, prices):
    """Legacy full-regen fallback. Only called if template markers are missing."""


def push_to_github(html_content):
    if not GITHUB_TOKEN:
        logger.warning("⚠️ GITHUB_TOKEN non configurato — skip push")
        return False
    try:
        api = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        }
        # Get current SHA (needed for update)
        r = requests.get(api, headers=headers, timeout=15)
        sha = r.json().get("sha", "") if r.status_code == 200 else ""
        encoded = base64.b64encode(html_content.encode("utf-8")).decode("utf-8")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload = {
            "message": f"Brief {now_str}",
            "content": encoded,
            "committer": {"name": "XenosFinance Bot", "email": "bot@xenosfinance.com"}
        }
        if sha:
            payload["sha"] = sha
        r2 = requests.put(api, headers=headers, json=payload, timeout=30)
        if r2.status_code in [200, 201]:
            commit_sha = r2.json().get("commit", {}).get("sha", "")[:8]
            logger.info(f"✅ GitHub aggiornato: {GITHUB_FILE} (commit {commit_sha})")
            return True
        else:
            logger.error(f"❌ GitHub push fallito: {r2.status_code} — {r2.text[:300]}")
            return False
    except Exception as e:
        logger.error(f"❌ GitHub push errore: {e}", exc_info=True)
        return False


# ─── COMMAND HANDLERS ─────────────────────────────────────────────────────────
async def cmd_start(u, c):
    # Deep link from the website's "Pay by card" button:
    # https://t.me/<bot>?start=paycard — open to everyone, not just the owner.
    if c.args and c.args[0].lower() == "paycard":
        await _paycard_request(u, c)
        return
    # 2026-10: pulsante "☕ Support XenosFinance" del sito → ?start=support
    if c.args and c.args[0].lower() == "support":
        await _support_request(u, c)
        return
    if not await check_auth(u): return
    await u.message.reply_text(
        "<b>📊 XENOSFINANCE</b>\n\n"
        "<b>TECHNICAL ANALYSIS:</b>\n"
        "/elliott SYMBOL — Elliott Wave v2 (Real Pivots)\n"
        "/ai SYMBOL — AI Analysis with Claude\n\n"
        "<b>MARKET OVERVIEW:</b>\n"
        "/outlook — Intraday market snapshot\n"
        "/premarket — 🌅 US Pre-Market brief + top movers\n\n"
        "<b>ASSET CLASS ANALYSIS:</b>\n"
        "/forex — FX majors | /crypto — BTC &amp; ETH\n"
        "/commodities — Gold, Silver, Oil, Gas\n"
        "/equity — S&amp;P 500, Nasdaq, Dow\n\n"
        "<b>ENERGY:</b>\n"
        "/eia — 🛢 EIA Weekly Petroleum Report → channel\n\n"
        "<b>GEOPOLITICS &amp; MACRO:</b>\n"
        "/geopolitics — Geopolitical news + market impact\n"
        "/news — 📰 Daily digest on xenosfinance.com\n\n"
        "/status — System status\n\n"
        "<i>FX: EURUSD GBPUSD USDJPY AUDUSD USDCHF USDCAD NZDUSD\n"
        "FX Crosses: EURGBP EURJPY GBPJPY AUDJPY CADJPY CHFJPY EURAUD EURCAD EURCHF GBPAUD GBPCAD AUDCAD AUDCHF NZDJPY CADCHF\n"
        "Comm: GOLD SILVER OIL NGAS | Idx: SPY NASDAQ DJI\n"
        "Crypto: BTCUSD ETHUSD XRPUSD SOLUSD DOGEUSD ZECUSD\n"
        "Blue Chip: AAPL MSFT V UNH HD MCD CAT BA DIS KO WMT JNJ PG MMM\n"
        "AI/Tech: NVDA GOOGL META AMZN TSLA AMD ORCL CRM PLTR\n"
        "Banks: JPM GS BAC WFC MS C BLK\n\n"
        "Alias: /quant = /ai | /geo = /geopolitics | /brief = /news</i>",
        parse_mode="HTML")

async def cmd_status(u, c):
    if not await check_auth(u): return
    ai = bool(ANTHROPIC_API_KEY)
    await u.message.reply_text(
        f"<b>🔧 SYSTEM STATUS</b>\n\n"
        f"✅ Elliott Wave Deep-Scan v2.0\n"
        f"✅ Pre-Market Brief | ✅ Geopolitical Monitor (multi-feed)\n"
        f"✅ Briefs FX/Crypto/Commodities/Equity\n"
        f"✅ EIA Weekly Petroleum Report (auto-post Wed/Thu + /eia)\n"
        f"✅ Daily Digest (Reuters + CNBC + Yahoo Finance + Al Jazeera)\n"
        f"{'✅' if ai else '⚠️'} AI Claude {'Active' if ai else '— API Key not configured'}\n"
        f"{'✅' if GITHUB_TOKEN else '⚠️'} GitHub {'Configured (' + GITHUB_REPO + ')' if GITHUB_TOKEN else 'Not configured'}\n"
        f"{'✅' if CHARTS_AVAILABLE else '⚠️'} Charts {'Active (matplotlib)' if CHARTS_AVAILABLE else 'Disabled'}\n\n"
        f"✅ Data: Yahoo Finance | ✅ News: Reuters + CNBC + Al Jazeera RSS",
        parse_mode="HTML")

# ── Bozze Reddit (2026-10-07) ────────────────────────────────────────────────
# La pubblicazione automatica su Reddit non è possibile: da novembre 2025 Reddit
# rilascia l'accesso API solo su approvazione e non a chi lo usa per promuoversi,
# e gli account che postano in automatico vengono bannati come spam. Il bot fa
# quindi tutto TRANNE il clic finale: dopo ogni pubblicazione (/elliott, /ai,
# report EIA) ti manda in privato la bozza già in markdown Reddit, il grafico da
# allegare e un pulsante che apre Reddit con titolo e testo già compilati.
REDDIT_DRAFTS = os.getenv("REDDIT_DRAFTS", "1") != "0"
REDDIT_SIGNATURE = ("\n\n---\n*Independent oil trader — Elliott Wave & macro. "
                    "No signals for sale, no brokers. Educational, not financial advice.*")


def _html_to_reddit(t):
    """HTML Telegram → markdown Reddit. Toglie footer canale, link e separatori."""
    import html as _h
    t = (t or "").replace(SITE_FOOTER, "")
    t = re.sub(r"<a [^>]*>(.*?)</a>", r"\1", t, flags=re.S)
    t = re.sub(r"</?b>", "**", t)
    t = re.sub(r"</?i>", "*", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = _h.unescape(t)
    t = re.sub(r"^━+\s*$", "", t, flags=re.M)
    t = re.sub(r"\n{3,}", "\n\n", t)
    # Reddit unisce le righe singole: doppio spazio a fine riga = a capo
    t = "\n".join((ln + "  ") if ln.strip() else ln for ln in t.strip().split("\n"))
    return t


def send_reddit_draft(title, body_md, img_bytes=None):
    """Manda al proprietario (privato) bozza Reddit + grafico + pulsante 'Apri su Reddit'."""
    if not REDDIT_DRAFTS or not TELEGRAM_BOT_TOKEN or not OWNER_ID:
        return False
    import html as _h
    from urllib.parse import quote
    body = body_md.strip() + REDDIT_SIGNATURE
    url = "https://www.reddit.com/submit?type=TEXT&title=" + quote(title[:290])
    full = url + "&text=" + quote(body)
    if len(full) <= 1900:      # limite pratico per un pulsante URL Telegram
        url = full
    api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    try:
        if img_bytes:
            requests.post(f"{api}/sendPhoto",
                          data={"chat_id": OWNER_ID,
                                "caption": "🟠 Reddit — immagine da allegare al post"},
                          files={"photo": ("chart.png", img_bytes, "image/png")}, timeout=30)
        kb = {"inline_keyboard": [[{"text": "📝 Apri su Reddit (titolo"
                                    + (" + testo" if url == full else "") + " già compilati)", "url": url}]]}
        msg = (f"🟠 <b>Bozza Reddit</b> — scegli il subreddit, allega l'immagine e pubblica.\n\n"
               f"<b>Titolo</b>\n<code>{_h.escape(title)}</code>\n\n"
               f"<b>Testo</b> (tocca per copiare)\n<pre>{_h.escape(body[:3400])}</pre>")
        r = requests.post(f"{api}/sendMessage",
                          json={"chat_id": OWNER_ID, "text": msg, "parse_mode": "HTML",
                                "disable_web_page_preview": True, "reply_markup": kb}, timeout=15)
        return r.json().get("ok", False)
    except Exception as e:
        logger.warning(f"reddit draft: {e}")
        return False


# ── /elliott e /ai: anteprima → pubblica/scarta (2026-10-07) ─────────────────
# Prima /elliott e /ai pubblicavano subito sul canale e salvavano in Trading
# Ideas. Ora testo e grafico arrivano prima SOLO in privato al proprietario,
# con due pulsanti: ✅ pubblica sul canale + salva in Trading Ideas, ❌ scarta.
# Stesso schema dell'anteprima MKO di /futures (bot_data + scadenza 6h).
SETUP_PREVIEW_TTL = 6 * 60 * 60

async def _setup_send_preview(u, c, kind, sym, messages, img, ew, narrative, label):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    img_bytes = None
    if img is not None:
        try:
            img.seek(0)
            img_bytes = img.read()
        except Exception as e_img:
            logger.warning(f"setup preview {sym}: chart read failed — {e_img}")
    key = "setup_" + hashlib.md5(f"{kind}{sym}{time.time()}".encode()).hexdigest()[:10]
    c.bot_data[key] = {"kind": kind, "sym": sym, "messages": messages, "img": img_bytes,
                       "ew": ew, "narrative": narrative, "label": label, "ts": time.time()}
    # Anteprima identica a ciò che andrà sul canale (HTML); se Telegram rifiuta
    # l'HTML lo vedi subito qui, prima di pubblicare.
    for msg in messages:
        try:
            await u.message.reply_text(msg, parse_mode="HTML", disable_web_page_preview=True)
        except Exception as e_msg:
            await u.message.reply_text(f"⚠️ Questo blocco non passa in HTML ({str(e_msg)[:80]}) — "
                                       f"sul canale fallirebbe.\n\n{msg[:3500]}")
    if img_bytes:
        await u.message.reply_photo(photo=io.BytesIO(img_bytes))
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Pubblica sul canale", callback_data=f"setup_pub:{key}"),
        InlineKeyboardButton("❌ Scarta", callback_data=f"setup_del:{key}"),
    ]])
    await u.message.reply_text(
        f"👆 <b>Anteprima — {label}</b>\n"
        f"{'Testo + grafico' if img_bytes else 'Solo testo (grafico non generato)'}. "
        f"Pubblico sul canale e salvo in Trading Ideas?",
        parse_mode="HTML", reply_markup=kb)

async def _cb_setup_preview(update, context):
    query = update.callback_query
    if query.from_user.id != OWNER_ID:
        await query.answer("🚫 Access denied", show_alert=True)
        return
    action, key = query.data.split(":", 1)
    cached = context.bot_data.get(key)
    if not cached or time.time() - cached.get("ts", 0) > SETUP_PREVIEW_TTL:
        context.bot_data.pop(key, None)
        await query.answer("⚠️ Anteprima scaduta — rigenera con /elliott o /ai", show_alert=True)
        await query.edit_message_reply_markup(reply_markup=None)
        return
    await query.edit_message_reply_markup(reply_markup=None)
    if action != "setup_pub":
        await query.answer("Scartato")
        await query.message.reply_text(f"🗑 Scartato: {cached['label']}")
        context.bot_data.pop(key, None)
        return
    await query.answer("📤 Invio al canale...")
    text_ok = True
    for msg in cached["messages"]:
        if not await send_channel(msg):
            text_ok = False
    img_ok = False
    img_buf = io.BytesIO(cached["img"]) if cached.get("img") else None
    if img_buf is not None:
        img_ok = await send_channel_photo(img_buf)
    idea_ok = False
    try:
        idea_ok = bool(save_trading_idea(cached["sym"], cached["ew"], cached["narrative"],
                                         img_buf=io.BytesIO(cached["img"]) if cached.get("img") else None))
    except Exception as e_save:
        logger.error(f"setup preview save idea {cached['sym']}: {e_save}", exc_info=True)
    # 2026-10-07: bozza Reddit pronta dopo la pubblicazione
    if text_ok:
        try:
            _ew = cached["ew"]
            _name = MARKETS[cached["sym"]]["name"]
            _dir = {1: "long", -1: "short"}.get(_ew.get("trade_dir"), "")
            _eng = _ew.get("engine") or {}
            _wave = f"wave {_eng.get('wave')}" if _eng.get("wave") else f"wave {_ew.get('wave_num', '?')}"
            if cached["kind"] == "elliott":
                _title = f"{_name} Elliott Wave: {_wave} {('— ' + _dir + ' setup') if _dir else ''} (levels + invalidation)"
            else:
                _title = f"{_name} technical read: {_dir + ' setup, ' if _dir else ''}momentum, trend and risk"
            _body = "\n\n".join(_html_to_reddit(m_) for m_ in cached["messages"])
            send_reddit_draft(re.sub(r"\s+", " ", _title).strip(), _body, cached.get("img"))
            _bs = bluesky_setup_text(cached["kind"], cached["sym"], _ew)
            if _bs:
                bluesky_post(_bs, cached.get("img"), alt=f"{_name} Elliott Wave chart, Daily/H4/H1")
        except Exception as e_rd:
            logger.warning(f"reddit draft (setup): {e_rd}")
    await query.message.reply_text(
        f"{'✅ Testo inviato' if text_ok else '❌ Testo NON inviato (vedi log Railway)'} · "
        f"{'✅ Grafico inviato' if img_ok else ('⚠️ Grafico non inviato' if img_buf else '— nessun grafico')}\n"
        f"{'📌 Salvato in Trading Ideas' if idea_ok else '⚠️ Trading Ideas non aggiornato (vedi log)'}"
    )
    context.bot_data.pop(key, None)


async def cmd_elliott(u, c):
    if not await check_auth(u): return
    s = parse_symbol(c.args)
    if not s:
        await u.message.reply_text(f"❌ Usage: /elliott EURUSD\n\n{SYMBOL_LIST}"); return
    m = await u.message.reply_text(f"🌊 MTF Elliott Wave analysis {MARKETS[s]['name']}...")
    try:
        df    = fetch_data(s, days=365, interval="1d")
        df_4h = fetch_data(s, days=60,  interval="4h")
        df_1h = fetch_data(s, days=10,  interval="1h")
        ew = elliott_wave_analysis(df, df_4h=df_4h, df_1h=df_1h)
        if not ew:
            await m.edit_text("❌ Data unavailable"); return
        # ── 1. Prima manda il testo narrativo ──
        # FIX 2026-10: il testo non arrivava ma il bot diceva "sent":
        #  - narrativa AI non escapata in HTML (un "<" o "&" → Telegram rifiuta il messaggio)
        #  - nessun controllo su lunghezza (>4096) né sull'esito di send_channel
        #  - se l'AI falliva, il testo veniva saltato in silenzio
        # Ora: escape HTML, split in parti, fallback con il riepilogo del motore, esito reale.
        import html as _html
        narrative = claude_narrative_analysis(s, ew, df)
        pf_ = _pf(s)
        if not narrative:
            logger.warning(f"elliott {s}: AI narrative unavailable — sending engine summary instead")
            narrative = (
                f"{ew.get('wave_pos', '')}\n"
                f"Bias: {ew.get('bias', '')}\n\n"
                f"{ew.get('action', '')}\n\n"
                f"{ew.get('wave_char', '')}"
            )
        now_str = datetime.utcnow().strftime("%d %b %Y • %H:%M UTC")
        wi_map = {"1":"①","2":"②","3":"③","4":"④","5":"⑤","A":"🅐","B":"🅑","C":"🅒","?":"❓"}
        wi = wi_map.get(ew["wave_num"], "🌊")
        head = (
            f"<b>📝 ANALYSIS — {MARKETS[s]['emoji']} {MARKETS[s]['name']} · Wave {wi}</b>\n"
            f"<i>{now_str}</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        # 2026-10-07: tolto il secondo disclaimer — SITE_FOOTER ne ha già uno
        tail = SITE_FOOTER
        body_parts = split_message(_html.escape(narrative, quote=False), max_len=3500)
        messages = [
            (head if n_ == 0 else "") + part + (tail if n_ == len(body_parts) - 1 else "")
            for n_, part in enumerate(body_parts)
        ]
        img = None
        if CHARTS_AVAILABLE:
            img = chart_elliott(s, df, ew, df_4h=df_4h, df_1h=df_1h)
        # FIX 2026-10-07: niente più invio diretto al canale — anteprima privata
        # con ✅ Pubblica / ❌ Scarta (canale + Trading Ideas solo dopo conferma).
        await _setup_send_preview(u, c, "elliott", s, messages, img, ew, narrative,
                                  f"Elliott {MARKETS[s]['name']} · Wave {ew.get('wave_num', '?')}")
        await m.edit_text("👀 Anteprima pronta qui sotto — controlla e scegli se pubblicare")
    except Exception as e:
        logger.error(f"elliott: {e}", exc_info=True)
        await m.edit_text(f"❌ Error: {str(e)[:100]}")

async def cmd_ai(u, c):
    if not await check_auth(u): return
    s = parse_symbol(c.args)
    if not s:
        await u.message.reply_text(f"❌ Usage: /ai EURUSD\n\n{SYMBOL_LIST}"); return
    if not ANTHROPIC_API_KEY:
        await u.message.reply_text("⚠️ Configure ANTHROPIC_API_KEY!"); return
    m = await u.message.reply_text(f"🤖 AI analysis {MARKETS[s]['name']}...")
    try:
        df    = fetch_data(s, days=365, interval="1d")
        df_4h = fetch_data(s, days=60,  interval="4h")
        df_1h = fetch_data(s, days=10,  interval="1h")
        ew = elliott_wave_analysis(df, df_4h=df_4h, df_1h=df_1h)
        if not ew:
            await m.edit_text("❌ Data unavailable"); return
        ai = claude_analysis_simple(MARKETS[s]["name"], ew, sym=s)
        if not ai:
            await m.edit_text("❌ AI unavailable"); return
        img = None
        if CHARTS_AVAILABLE:
            img = chart_elliott(s, df, ew, df_4h=df_4h, df_1h=df_1h)
        # FIX 2026-10-07: anteprima privata prima di pubblicare (vedi /elliott)
        await _setup_send_preview(u, c, "ai", s, [fmt_ai(s, ai)], img, ew, ai,
                                  f"AI {MARKETS[s]['name']}")
        await m.edit_text("👀 Anteprima pronta qui sotto — controlla e scegli se pubblicare")
    except Exception as e:
        logger.error(f"ai: {e}", exc_info=True)
        await m.edit_text(f"❌ Error: {str(e)[:100]}")


# ═══════════════════════════════════════════════════════════════════════════════
# PREMARKET USA
# ═══════════════════════════════════════════════════════════════════════════════

PREMARKET_SYMBOLS = {
    "SPY":     {"name": "S&P 500",      "emoji": "📊", "yf": "SPY",       "group": "futures"},
    "NASDAQ":  {"name": "Nasdaq 100",   "emoji": "📈", "yf": "^NDX",      "group": "futures"},
    "DJI":     {"name": "Dow Jones",    "emoji": "🇺🇸", "yf": "^DJI",    "group": "futures"},
    "GOLD":    {"name": "Gold",         "emoji": "🥇", "yf": "GC=F",      "group": "macro"},
    "OIL":     {"name": "WTI Crude",    "emoji": "🛢",  "yf": "CL=F",     "group": "macro"},
    "SILVER":  {"name": "Silver",       "emoji": "🥈", "yf": "SI=F",      "group": "macro"},
    "NGAS":    {"name": "Natural Gas",  "emoji": "⛽", "yf": "NG=F",      "group": "macro"},
    "BTCUSD":  {"name": "Bitcoin",      "emoji": "₿",  "yf": "BTC-USD",   "group": "crypto"},
    "ETHUSD":  {"name": "Ethereum",     "emoji": "💎", "yf": "ETH-USD",   "group": "crypto"},
    "XRPUSD":  {"name": "Ripple",       "emoji": "💧", "yf": "XRP-USD",   "group": "crypto"},
    "SOLUSD":  {"name": "Solana",       "emoji": "☀️", "yf": "SOL-USD",  "group": "crypto"},
    "DOGEUSD": {"name": "Dogecoin",     "emoji": "🐕", "yf": "DOGE-USD",  "group": "crypto"},
    "EURUSD":  {"name": "EUR/USD",      "emoji": "💶", "yf": "EURUSD=X",  "group": "forex"},
    "GBPUSD":  {"name": "GBP/USD",      "emoji": "💷", "yf": "GBPUSD=X",  "group": "forex"},
    "USDJPY":  {"name": "USD/JPY",      "emoji": "💴", "yf": "USDJPY=X",  "group": "forex"},
    "USDCAD":  {"name": "USD/CAD",      "emoji": "🇨🇦", "yf": "USDCAD=X","group": "forex"},
    "AUDUSD":  {"name": "AUD/USD",      "emoji": "🇦🇺", "yf": "AUDUSD=X","group": "forex"},
    "USDCHF":  {"name": "USD/CHF",      "emoji": "🇨🇭", "yf": "USDCHF=X","group": "forex"},
    "DAX":     {"name": "DAX",          "emoji": "🇩🇪", "yf": "^GDAXI",  "group": "europe"},
    "FTSE":    {"name": "FTSE 100",     "emoji": "🇬🇧", "yf": "^FTSE",   "group": "europe"},
    "CAC":     {"name": "CAC 40",       "emoji": "🇫🇷", "yf": "^FCHI",   "group": "europe"},
    "NVDA":    {"name": "Nvidia",       "emoji": "🎮", "yf": "NVDA",      "group": "movers"},
    "AAPL":    {"name": "Apple",        "emoji": "🍎", "yf": "AAPL",      "group": "movers"},
    "TSLA":    {"name": "Tesla",        "emoji": "⚡", "yf": "TSLA",      "group": "movers"},
    "META":    {"name": "Meta",         "emoji": "👥", "yf": "META",      "group": "movers"},
    "AMZN":    {"name": "Amazon",       "emoji": "📦", "yf": "AMZN",      "group": "movers"},
}

def fetch_premarket_quote(yf_ticker):
    """Fetch prezzo live da Yahoo Finance — priorità a regularMarketPrice dal meta."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
    }
    # Priorità: 1d/5m per massima freschezza, poi fallback
    for params in [
        {"range": "1d",  "interval": "5m"},
        {"range": "5d",  "interval": "1h"},
        {"range": "1mo", "interval": "1d"},
    ]:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_ticker}"
            r = requests.get(url, headers=headers, params={**params, "_": int(datetime.now().timestamp())}, timeout=10)
            if not r.ok:
                continue
            d = r.json()
            res = d["chart"]["result"][0]
            meta = res.get("meta", {})
            # regularMarketPrice è sempre il prezzo più aggiornato disponibile
            last = float(meta.get("regularMarketPrice") or 0)
            prev = float(meta.get("chartPreviousClose") or meta.get("previousClose") or 0)
            if last <= 0:
                q = res["indicators"]["quote"][0]
                closes = [x for x in (q.get("close") or []) if x is not None]
                if len(closes) < 2:
                    continue
                last = closes[-1]
                prev = closes[-2]
            if last <= 0:
                continue
            if prev <= 0:
                prev = last
            chg = ((last - prev) / prev) * 100 if prev else 0
            return {"price": last, "prev": prev, "chg": chg}
        except Exception as e:
            logger.warning(f"premarket fetch {yf_ticker} ({params}): {e}")
            continue
    return None

def fetch_recent_news_for_premarket(max_items=6):
    feeds = [
        "https://finance.yahoo.com/rss/topstories",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://feeds.reuters.com/reuters/topNews",
        "https://www.aljazeera.com/xml/rss/all.xml",
    ]
    items = []
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/rss+xml, */*"}
    for feed_url in feeds:
        try:
            r = requests.get(feed_url, headers=headers, timeout=15)
            root = ET.fromstring(r.content)
            for item in root.findall(".//item"):
                title = (item.findtext("title") or "").strip()
                desc  = (item.findtext("description") or "").strip()
                if title:
                    items.append({"title": title, "desc": desc[:200]})
                if len(items) >= max_items:
                    break
        except Exception as e:
            logger.warning(f"news premarket: {e}")
        if len(items) >= max_items:
            break
    return items[:max_items]

def _mkt_str(sym, market_data):
    """Helper: formatta prezzo e variazione per un simbolo."""
    d = market_data.get(sym)
    if not d: return "N/D"
    p   = d["price"]
    chg = d["chg"]
    pfmt = ".0f" if p > 1000 else ".2f" if p > 10 else ".4f"
    sign = "+" if chg >= 0 else ""
    return f"{p:{pfmt}} ({sign}{chg:.2f}%)"



def _run_site_update() -> tuple[bool, str]:
    """
    Shared logic for cmd_updatesite (manual) and _scheduled_updatesite
    (automatic, every 4h) — one implementation, no duplication.
    Returns (success, message).
    """
    news   = fetch_news_for_brief(max_items=12)
    prices = fetch_prices_for_brief()
    html = generate_news_html(news, prices)
    if html is None:
        return False, "generate_news_html returned None — template missing markers, push skipped"
    ok = push_to_github(html)
    if ok:
        return True, "Site updated"
    return False, "GitHub push failed — check GITHUB_TOKEN in logs"


async def cmd_updatesite(u, c):
    if not await check_auth(u): return
    m = await u.message.reply_text("🔄 Updating xenosfinance.com...")
    try:
        ok, msg = _run_site_update()
        if ok:
            await m.edit_text(
                "✅ <b>Site updated!</b>\n\nWait 1–2 minutes for Cloudflare Pages deploy.",
                parse_mode="HTML"
            )
        else:
            await m.edit_text(f"❌ {msg}")
    except Exception as e:
        logger.error(f"updatesite: {e}", exc_info=True)
        await m.edit_text(f"❌ Error: {str(e)[:150]}")


async def _scheduled_updatesite(context: ContextTypes.DEFAULT_TYPE):
    """JobQueue — refreshes the homepage news/prices sections every 4h.
    Silent (no Telegram message) — logs only, same as other background jobs."""
    logger.info("[UpdateSite] Running scheduled homepage refresh...")
    try:
        ok, msg = _run_site_update()
        logger.info(f"[UpdateSite] {'OK' if ok else 'FAILED'} — {msg}")
    except Exception as e:
        logger.error(f"[UpdateSite] Scheduled job error: {e}", exc_info=True)


# ═══════════════════════════════════════════════════════════════════════════════
# INTRADAY SIGNAL ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def intraday_technical_analysis(sym):
    """
    Analisi tecnica intraday su H1 + H4 per generare segnali forex.
    Nessun Elliott Wave — puro price action, momentum e livelli chiave.
    """
    try:
        df_h4 = fetch_data(sym, days=60, interval="4h")
        df_h1 = fetch_data(sym, days=10, interval="1h")
        if df_h1 is None or len(df_h1) < 20:
            return None
        if df_h4 is None or len(df_h4) < 10:
            df_h4 = None

        # ── Prezzi correnti ──
        c1  = df_h1["close"]
        p   = float(c1.iloc[-1])
        pv  = float(c1.iloc[-2])
        chg = ((p - pv) / pv) * 100

        # ── EMA ──
        e8  = float(ema(c1, 8).iloc[-1])
        e21 = float(ema(c1, 21).iloc[-1])
        e50 = float(ema(c1, 50).iloc[-1])

        # ── RSI H1 ──
        rv1 = float(rsi(c1).iloc[-1])

        # ── MACD H1 ──
        ml1, sl1 = macd(c1)
        mh1 = float((ml1 - sl1).iloc[-1])
        mh1_prev = float((ml1 - sl1).iloc[-2])
        macd_cross_bull = mh1 > 0 and mh1_prev <= 0
        macd_cross_bear = mh1 < 0 and mh1_prev >= 0

        # ── ATR H1 ──
        av1 = float(atr(df_h1).iloc[-1])

        # ── Supporti e Resistenze H1 (ultimi 48 candles) ──
        h1_48  = df_h1.iloc[-48:]
        recent_high = float(h1_48["high"].max())
        recent_low  = float(h1_48["low"].min())
        # Swing highs/lows significativi
        highs_sw, lows_sw = detect_swings(c1.iloc[-48:], window=3)
        key_res = sorted(set([recent_high] + [p for _, p in highs_sw[-3:]]), reverse=True)
        key_sup = sorted(set([recent_low]  + [p for _, p in lows_sw[-3:]]), reverse=False)
        nearest_res = next((r for r in key_res if r > p + av1 * 0.1), p + av1 * 2)
        nearest_sup = next((s for s in key_sup if s < p - av1 * 0.1), p - av1 * 2)

        # ── H4 context (bias direzionale) ──
        h4_bias = "NEUTRAL"
        h4_rsi  = None
        h4_trend = None
        if df_h4 is not None:
            c4   = df_h4["close"]
            e21_h4 = float(ema(c4, 21).iloc[-1])
            e50_h4 = float(ema(c4, 50).iloc[-1])
            rv4  = float(rsi(c4).iloc[-1])
            h4_rsi = rv4
            if c4.iloc[-1] > e21_h4 and e21_h4 > e50_h4:
                h4_bias = "BULLISH"
                h4_trend = f"H4: prezzo sopra EMA21 ({e21_h4:.5f}) e EMA50 ({e50_h4:.5f})"
            elif c4.iloc[-1] < e21_h4 and e21_h4 < e50_h4:
                h4_bias = "BEARISH"
                h4_trend = f"H4: prezzo sotto EMA21 ({e21_h4:.5f}) e EMA50 ({e50_h4:.5f})"
            else:
                h4_trend = f"H4: struttura mista — EMA21 {e21_h4:.5f}"

        # ── Candlestick patterns H1 (ultimi 3 candles) ──
        patterns = []
        if len(df_h1) >= 3:
            c_now  = df_h1.iloc[-1]
            c_prev = df_h1.iloc[-2]
            c_pp   = df_h1.iloc[-3]
            body_now  = abs(c_now["close"]  - c_now["open"])
            body_prev = abs(c_prev["close"] - c_prev["open"])
            rng_now   = c_now["high"] - c_now["low"]
            # Pin bar bullish
            if (c_now["close"] > c_now["open"] and
                (c_now["open"] - c_now["low"]) > body_now * 1.5 and
                (c_now["high"] - c_now["close"]) < body_now * 0.5):
                patterns.append("Pin Bar Bullish")
            # Pin bar bearish
            if (c_now["close"] < c_now["open"] and
                (c_now["high"] - c_now["open"]) > body_now * 1.5 and
                (c_now["close"] - c_now["low"]) < body_now * 0.5):
                patterns.append("Pin Bar Bearish")
            # Engulfing bullish
            if (c_now["close"] > c_now["open"] and
                c_prev["close"] < c_prev["open"] and
                c_now["close"] > c_prev["open"] and
                c_now["open"] < c_prev["close"]):
                patterns.append("Engulfing Bullish")
            # Engulfing bearish
            if (c_now["close"] < c_now["open"] and
                c_prev["close"] > c_prev["open"] and
                c_now["close"] < c_prev["open"] and
                c_now["open"] > c_prev["close"]):
                patterns.append("Engulfing Bearish")
            # Inside bar
            if (c_now["high"] < c_prev["high"] and c_now["low"] > c_prev["low"]):
                patterns.append("Inside Bar (compressione)")

        # ── Bollinger Bands H1 ──
        bb_u, bb_m, bb_l = bollinger(c1)
        bb_upper = float(bb_u.iloc[-1])
        bb_lower = float(bb_l.iloc[-1])
        bb_mid   = float(bb_m.iloc[-1])
        bb_squeeze = (bb_upper - bb_lower) < av1 * 2.5

        # ── Session context ──
        now_h = datetime.now().hour
        if 7 <= now_h < 10:
            session = "Apertura Londra"
        elif 13 <= now_h < 17:
            session = "Overlap Londra-New York"
        elif 17 <= now_h < 22:
            session = "Sessione New York"
        else:
            session = "Sessione Asia/Fuori orario"

        # ── VWAP H1 ──────────────────────────────────────────────────────────
        vwap_val = float(vwap_calc(df_h1).iloc[-1]) if df_h1["volume"].sum() > 0 else p
        above_vwap = p > vwap_val

        # ── Volume Profile H1 (POC / Value Area) ─────────────────────────────
        vp_poc = p; vp_vah = p; vp_val_level = p
        vp_above_poc = False; vp_in_va = False
        try:
            c_arr = df_h1["close"].values.astype(float)
            h_arr = df_h1["high"].values.astype(float)
            l_arr = df_h1["low"].values.astype(float)
            v_arr = df_h1["volume"].values.astype(float)
            n_bars = len(c_arr)
            use_n = min(60, n_bars)
            p_min = float(np.min(l_arr[-use_n:]))
            p_max = float(np.max(h_arr[-use_n:]))
            if p_max > p_min:
                n_bkts = 30
                bk_sz  = (p_max - p_min) / n_bkts
                bkts   = np.zeros(n_bkts)
                for i in range(use_n):
                    idx = int((c_arr[n_bars - use_n + i] - p_min) / bk_sz)
                    idx = min(idx, n_bkts - 1)
                    bkts[idx] += v_arr[n_bars - use_n + i] if v_arr[n_bars - use_n + i] > 0 else 1
                poc_idx = int(np.argmax(bkts))
                vp_poc  = p_min + (poc_idx + 0.5) * bk_sz
                total_vol = bkts.sum(); target_vol = total_vol * 0.70
                va_vol = bkts[poc_idx]; lo_i, hi_i = poc_idx, poc_idx
                while va_vol < target_vol:
                    add_lo = bkts[lo_i - 1] if lo_i > 0 else 0
                    add_hi = bkts[hi_i + 1] if hi_i < n_bkts - 1 else 0
                    if add_hi >= add_lo and hi_i < n_bkts - 1:
                        hi_i += 1; va_vol += add_hi
                    elif lo_i > 0:
                        lo_i -= 1; va_vol += add_lo
                    else:
                        break
                vp_vah = p_min + (hi_i + 1) * bk_sz
                vp_val_level = p_min + lo_i * bk_sz
                vp_above_poc = p > vp_poc
                vp_in_va     = vp_val_level <= p <= vp_vah
        except Exception:
            pass

        # ── Order Flow Delta H1 ───────────────────────────────────────────────
        of_cum_delta = 0.0; of_delta_bull = False; of_divergence = False
        try:
            c_arr = df_h1["close"].values.astype(float)
            h_arr = df_h1["high"].values.astype(float)
            l_arr = df_h1["low"].values.astype(float)
            v_arr = df_h1["volume"].values.astype(float)
            n_bars = len(c_arr)
            use_n  = min(20, n_bars)
            deltas = []
            for i in range(n_bars - use_n, n_bars):
                rng = h_arr[i] - l_arr[i] + 1e-9
                buy_r  = (c_arr[i] - l_arr[i]) / rng
                sell_r = (h_arr[i] - c_arr[i]) / rng
                vol_i  = v_arr[i] if v_arr[i] > 0 else 1
                deltas.append((buy_r - sell_r) * vol_i)
            of_cum_delta  = float(np.sum(deltas))
            of_delta_bull = of_cum_delta > 0
            price_dir     = c_arr[-1] > c_arr[-10] if n_bars >= 10 else True
            of_divergence = price_dir != of_delta_bull
        except Exception:
            pass

        return {
            "sym": sym, "price": p, "chg": chg,
            "ema8": e8, "ema21": e21, "ema50": e50,
            "rsi_h1": rv1, "macd_h1": mh1, "macd_prev": mh1_prev,
            "macd_cross_bull": macd_cross_bull, "macd_cross_bear": macd_cross_bear,
            "atr": av1,
            "nearest_res": nearest_res, "nearest_sup": nearest_sup,
            "recent_high": recent_high, "recent_low": recent_low,
            "h4_bias": h4_bias, "h4_rsi": h4_rsi, "h4_trend": h4_trend,
            "patterns": patterns,
            "bb_upper": bb_upper, "bb_lower": bb_lower, "bb_mid": bb_mid,
            "bb_squeeze": bb_squeeze, "session": session,
            "cfd": validate_elliott_with_cfd("?", df_h1["close"], df_h1["volume"]),
            # ── NEW: AMT / Volume Profile / VWAP / Order Flow ──
            "vwap": vwap_val, "above_vwap": above_vwap,
            "vp_poc": vp_poc, "vp_vah": vp_vah, "vp_val": vp_val_level,
            "vp_above_poc": vp_above_poc, "vp_in_va": vp_in_va,
            "of_cum_delta": of_cum_delta, "of_delta_bull": of_delta_bull,
            "of_divergence": of_divergence,
        }
    except Exception as e:
        logger.error(f"intraday_ta {sym}: {e}", exc_info=True)
        return None


def generate_signal_ai(sym, ta):
    """Genera segnale intraday nel template XenosFinance via Claude."""
    if not ANTHROPIC_API_KEY or not ta:
        return None

    mkt  = MARKETS[sym]
    name = mkt["name"]
    pfmt = _pf(sym)
    now_str = datetime.now().strftime("%d %b %Y • %H:%M CET")

    pattern_str = ", ".join(ta["patterns"]) if ta["patterns"] else "Nessun pattern candele confermato"
    h4_str = ta["h4_trend"] or "H4 unavailable"
    h4_rsi_str = f"{ta['h4_rsi']:.1f}" if ta['h4_rsi'] is not None else "N/D"

    # ── AMT / VP / OF strings ─────────────────────────────────────────────────
    vwap_val = ta.get('vwap', ta['price'])
    vwap_str = f"{vwap_val:{pfmt}} ({'above' if ta.get('above_vwap') else 'below'})"
    vp_poc   = ta.get('vp_poc', ta['price'])
    vp_str   = (f"POC: {vp_poc:{pfmt}} | VAH: {ta.get('vp_vah', vp_poc):{pfmt}} | VAL: {ta.get('vp_val', vp_poc):{pfmt}}"
                f" | Price {'ABOVE' if ta.get('vp_above_poc') else 'BELOW'} POC"
                f" | {'INSIDE' if ta.get('vp_in_va') else 'OUTSIDE'} Value Area")
    of_dir   = "POSITIVE (buy aggression)" if ta.get('of_delta_bull') else "NEGATIVE (sell aggression)"
    of_div   = "DELTA DIVERGENCE - momentum fading" if ta.get('of_divergence') else "No divergence"

    prompt = f"""You are a senior institutional FX trader. Analyze the following technical data for {name} and identify ONE intraday trade setup (educational analysis).

TECHNICAL DATA -- {now_str}
Price: {ta['price']:{pfmt}}
Change: {ta['chg']:+.2f}%
Session: {ta['session']}

H1 INDICATORS:
EMA 8: {ta['ema8']:{pfmt}} | EMA 21: {ta['ema21']:{pfmt}} | EMA 50: {ta['ema50']:{pfmt}}
RSI H1: {ta['rsi_h1']:.1f}
MACD Histogram: {ta['macd_h1']:+.6f} (prev: {ta['macd_prev']:+.6f})
MACD Cross Bull: {ta['macd_cross_bull']} | Bear: {ta['macd_cross_bear']}
ATR H1: {ta['atr']:{pfmt}}
BB Upper: {ta['bb_upper']:{pfmt}} | Mid: {ta['bb_mid']:{pfmt}} | Lower: {ta['bb_lower']:{pfmt}}
BB Squeeze: {ta['bb_squeeze']}

KEY LEVELS H1:
Nearest Resistance: {ta['nearest_res']:{pfmt}}
Nearest Support:    {ta['nearest_sup']:{pfmt}}
48H High: {ta['recent_high']:{pfmt}} | 48H Low: {ta['recent_low']:{pfmt}}

H4 CONTEXT:
Bias: {ta['h4_bias']}
{h4_str}
RSI H4: {h4_rsi_str}

CANDLE PATTERNS H1: {pattern_str}

AUCTION MARKET THEORY / INSTITUTIONAL LAYERS:
VWAP H1:          {vwap_str}
Volume Profile:   {vp_str}
Order Flow Delta: {of_dir} | {of_div}

AMT RULES (apply these to direction and levels):
- Price ABOVE VWAP = institutional buying zone -- favor LONG unless overbought
- Price BELOW VWAP = institutional selling zone -- favor SHORT unless oversold
- Price ABOVE POC + OUTSIDE Value Area = breakout, HIGH conviction
- Price INSIDE Value Area = congestion, LOWER conviction -- downgrade confidence
- Order Flow DIVERGENCE = momentum fading -- use CONFIDENCE: LOW
- POC is a key magnet: use as TP target or SL reference where applicable

INSTRUCTIONS:
- ALWAYS generate a signal -- if setup is weak use CONFIDENCE: LOW
- Prioritize VWAP + Volume Profile confluence with EMA/RSI for direction

RSI COHERENCE RULES (mandatory):
  RSI H1 < 35 (oversold)   = LONG only. Never SHORT when oversold.
  RSI H1 > 65 (overbought) = SHORT only. Never LONG when overbought.
  RSI H1 35-65 (neutral)   = Follow VWAP + EMA + H4 bias.

H4 BIAS ALIGNMENT (mandatory):
  H4 BULLISH = prefer LONG. SHORT only if RSI H1 > 70 AND price at BB Upper.
  H4 BEARISH = prefer SHORT. LONG only if RSI H1 < 30 AND price at BB Lower.
  SETUP description must always be consistent with DIRECTION.

- SL: beyond swing high/low or BB band -- 0.5x to 2.0x ATR. Consider POC as magnet.
- TP1: 1.0x to 1.5x ATR. If POC is between entry and TP1, use POC as TP1.
- TP2: 2.0x to 3.0x ATR
- Only reply NO_SIGNAL if price data is clearly corrupt (all zeros)

Reply EXACTLY in this format (nothing else, no intro):

DIRECTION: LONG or SHORT
ENTRY: [exact price]
SL: [exact price]
TP1: [exact price]
TP2: [exact price]
TIMEFRAME: H1
SETUP: [5-8 words describing the setup]
RR: [ratio, e.g. 1:2.1]
INVALIDATION: [5-8 words]
CONFIDENCE: [HIGH / MEDIUM / LOW]
NOTE: [max 1 sentence -- mention VWAP/POC context if relevant]"""

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": "claude-sonnet-4-5", "max_tokens": 400,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=30
        )
        res = r.json()
        if "content" in res and res["content"]:
            return res["content"][0]["text"].strip()
    except Exception as e:
        logger.error(f"signal AI {sym}: {e}")
    return None


def fmt_signal(sym, ta, ai_response):
    """Formatta il segnale nel template XenosFinance."""
    mkt    = MARKETS[sym]
    pfmt   = _pf(sym)
    now_str = datetime.now().strftime("%d %b %Y • %H:%M CET")

    if not ai_response or ai_response.strip().startswith("NO_SIGNAL"):
        return (
            f"⚪ <b>NO SETUP — {mkt['emoji']} {mkt['name']}</b>\n"
            f"<i>{now_str}</i>\n\n"
            f"No clear setup at this moment.\n"
            f"RSI H1: {ta['rsi_h1']:.0f} | H4 Bias: {ta['h4_bias']} | Sessione: {ta['session']}\n\n"
            f"<i>XenosFinance Trading Desk</i>" + SITE_FOOTER
        )

    # Parsa la risposta AI
    lines = ai_response.strip().split("\n")
    parsed = {}
    for line in lines:
        if ":" in line:
            k, v = line.split(":", 1)
            parsed[k.strip()] = v.strip()

    direction = parsed.get("DIRECTION", "?")
    entry     = parsed.get("ENTRY", "?")
    sl        = parsed.get("SL", "?")
    tp1       = parsed.get("TP1", "?")
    tp2       = parsed.get("TP2", "?")
    tf        = parsed.get("TIMEFRAME", "H1")
    setup     = parsed.get("SETUP", "?")
    rr        = parsed.get("RR", "?")
    inv       = parsed.get("INVALIDATION", "?")
    conf      = parsed.get("CONFIDENCE", "MEDIUM")
    note      = parsed.get("NOTE", "")

    dir_emoji = "🟢" if direction == "LONG" else "🔴"
    conf_emoji = "🔥" if conf == "HIGH" else "⚡" if conf == "MEDIUM" else "⚠️"

    txt = (
        f"<b>📊 FOREX INTRADAY SETUP</b>\n"
        f"<i>{now_str}</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Pair:</b> {mkt['emoji']} {mkt['name']}\n"
        f"<b>Direction:</b> {dir_emoji} <b>{direction}</b>\n\n"
        f"<b>Entry:</b> <code>{entry}</code>\n"
        f"<b>Stop Loss:</b> <code>{sl}</code>\n\n"
        f"<b>Take Profit:</b>\n"
        f"  TP1: <code>{tp1}</code>\n"
        f"  TP2: <code>{tp2}</code>\n\n"
        f"<b>Timeframe:</b> {tf}\n"
        f"<b>Setup:</b> {setup}\n"
        f"<b>Risk/Reward:</b> {rr}\n"
        f"<b>Confidence:</b> {conf_emoji} {conf}\n\n"
        f"<b>Invalidation:</b>\n"
        f"<i>{inv}</i>\n"
    )
    if note:
        txt += f"\n💬 <i>{note}</i>\n"
    txt += (
        f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>XenosFinance Trading Desk</i>" + SITE_FOOTER
    )
    return txt


def _save_signal_to_site(sym, ta, ai_response):
    """Salva il segnale AI in signals_cfd/ su GitHub per esporlo sul sito."""
    if not ai_response or ai_response.strip().startswith("NO_SIGNAL"):
        return
    if not GITHUB_TOKEN:
        logger.warning("_save_signal_to_site: GITHUB_TOKEN mancante")
        return

    mkt = MARKETS.get(sym, {})
    lines = ai_response.strip().split("\n")
    parsed = {}
    for line in lines:
        if ":" in line:
            k, v = line.split(":", 1)
            parsed[k.strip()] = v.strip()

    direction = parsed.get("DIRECTION", "").upper()
    dir_mapped = "BUY" if direction == "LONG" else "SELL" if direction == "SHORT" else direction
    try: entry = float(parsed.get("ENTRY", 0))
    except: entry = 0
    try: sl = float(parsed.get("SL", 0))
    except: sl = 0
    try: tp = float(parsed.get("TP1", 0))  # usa TP1 come TP principale
    except: tp = 0
    try: tp2 = float(parsed.get("TP2", 0))
    except: tp2 = 0
    tf      = parsed.get("TIMEFRAME", ta.get("tf", "H1"))
    setup   = parsed.get("SETUP", "AI Signal")
    rr      = parsed.get("RR", "—")
    inv     = parsed.get("INVALIDATION", "—")
    conf_txt= parsed.get("CONFIDENCE", "MEDIUM")
    note    = parsed.get("NOTE", "")
    conf_map= {"HIGH": 85, "MEDIUM": 70, "LOW": 55}
    confidence = conf_map.get(conf_txt.upper(), 70)

    now  = datetime.utcnow()
    ts   = now.strftime("%Y%m%d_%H%M%S")
    pair = mkt.get("name", sym).replace("/", "").replace(" ", "_").upper()
    filename = f"signal_{pair}_{ts}.json"
    path     = f"signals_cfd/{filename}"

    signal = {
        "pair":           mkt.get("name", sym),
        "direction":      dir_mapped,
        "entry":          entry,
        "sl":             sl,
        "tp":             tp,
        "tp2":            tp2,
        "rr":             rr,
        "timeframe":      tf,
        "confidence":     confidence,
        "pattern":        setup,
        "pattern_desc":   setup,
        "ew_context":     note or "—",
        "market_context": f"RSI H1: {ta.get('rsi_h1', '—')} | H4 Bias: {ta.get('h4_bias', '—')}",
        "key_levels":     f"Entry: {entry} | SL: {sl} | TP1: {tp} | TP2: {tp2}",
        "invalidation":   inv,
        "tags":           ["ai", sym.lower(), dir_mapped.lower(), tf.lower()],
        "source":         "AI",
        "outcome":        "open",
        "saved_at":       now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timestamp":      now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    ok = _github_json_write(path, signal, None, f"AI Signal: {pair} {dir_mapped} @ {entry}")
    if ok:
        logger.info(f"✅ Signal saved to site: {path}")
    else:
        logger.warning(f"⚠️ Signal NOT saved to site: {path}")


async def cmd_signal(u, c):
    """Segnale intraday Forex AI-generated su H1+H4. Uso: /signal EURUSD"""
    if not await check_auth(u): return
    s = parse_symbol(c.args)
    if not s:
        # Mostra lista FX disponibili
        fx_list = [k for k, v in MARKETS.items() if v.get("cat") in ("forex", "forex_cross")]
        pairs = " | ".join(fx_list)
        await u.message.reply_text(
            f"❌ Usa: /signal EURUSD\n\n"
            f"<b>FX Major:</b> EURUSD GBPUSD USDJPY AUDUSD USDCHF USDCAD NZDUSD\n\n"
            f"<b>FX Cross:</b> EURGBP EURJPY GBPJPY AUDJPY CADJPY CHFJPY\n"
            f"EURAUD EURCAD EURCHF GBPAUD GBPCAD AUDCAD AUDCHF NZDJPY CADCHF",
            parse_mode="HTML"
        )
        return

    mkt = MARKETS[s]
    if mkt.get("cat") not in ("forex", "forex_cross"):
        await u.message.reply_text(f"❌ {mkt['name']} non è un cross FX — usa solo coppie Forex.")
        return

    m = await u.message.reply_text(f"📊 Intraday analysis {mkt['name']}...")
    try:
        await m.edit_text(f"📊 Loading H1 + H4 data for {mkt['name']}...")
        ta = intraday_technical_analysis(s)
        if not ta:
            await m.edit_text("❌ Data unavailable"); return

        await m.edit_text(f"🤖 Generating AI setup for {mkt['name']}...")
        ai_resp = generate_signal_ai(s, ta)

        signal_txt = fmt_signal(s, ta, ai_resp)
        await send_channel(signal_txt)

        # Salva su GitHub → appare in signals_cfd/ sul sito
        _save_signal_to_site(s, ta, ai_resp)

        await m.edit_text(f"✅ Setup {mkt['name']} sent to channel!")

    except Exception as e:
        logger.error(f"signal: {e}", exc_info=True)
        await m.edit_text(f"❌ Error: {str(e)[:100]}")


# ── /pub — Pubblica segnale manuale in signals_cfd/ ──────────────────────────
async def cmd_pub(u, c):
    """
    Pubblica un segnale CFD manuale sul sito.
    Uso: /pub PAIR DIRECTION ENTRY SL:xxx TP:xxx [TF:xxx] [nota libera]
    Esempio: /pub EURUSD BUY 1.0845 SL:1.0800 TP:1.0920 TF:H4 Wave 3 in progress
    """
    if not await check_auth(u): return

    args = c.args
    USAGE = (
        "Uso: /pub PAIR DIREZIONE ENTRY SL:xxx TP:xxx [TF:xxx] [nota]\n"
        "Esempio: /pub EURUSD BUY 1.0845 SL:1.0800 TP:1.0920 TF:H4 Wave 3 in progress"
    )

    if not args or len(args) < 4:
        await u.message.reply_text(f"❌ Argomenti insufficienti.\n{USAGE}")
        return

    pair      = args[0].upper()
    direction = args[1].upper()
    if direction not in ("BUY", "SELL"):
        await u.message.reply_text(f"❌ Direzione deve essere BUY o SELL.\n{USAGE}")
        return

    try:
        entry = float(args[2])
    except ValueError:
        await u.message.reply_text(f"❌ Entry non valido: {args[2]}\n{USAGE}")
        return

    sl = tp = None
    tf = "H4"
    notes_parts = []

    for tok in args[3:]:
        t = tok.upper()
        if t.startswith("SL:"):
            try: sl = float(tok[3:])
            except: pass
        elif t.startswith("TP:"):
            try: tp = float(tok[3:])
            except: pass
        elif t.startswith("TF:"):
            tf = tok[3:].upper()
        else:
            notes_parts.append(tok)

    if sl is None or tp is None:
        await u.message.reply_text(f"❌ SL e TP obbligatori.\n{USAGE}")
        return

    # Calcola R:R
    risk   = abs(entry - sl)
    reward = abs(tp - entry)
    rr     = f"1:{round(reward/risk, 1)}" if risk > 0 else "—"

    # Calcola confidence base su R:R
    rr_val = reward / risk if risk > 0 else 1
    confidence = min(95, max(55, int(50 + rr_val * 15)))

    note = " ".join(notes_parts).strip()
    now  = datetime.utcnow()
    ts   = now.strftime("%Y%m%d_%H%M%S")
    filename = f"manual_{pair}_{ts}.json"
    path     = f"signals_cfd/{filename}"

    signal = {
        "pair":          pair,
        "direction":     direction,
        "entry":         entry,
        "sl":            sl,
        "tp":            tp,
        "rr":            rr,
        "timeframe":     tf,
        "confidence":    confidence,
        "pattern":       "Manual Setup",
        "pattern_desc":  note or "Trade setup published by analyst.",
        "ew_context":    note or "—",
        "market_context": note or "—",
        "key_levels":    f"Entry: {entry} | SL: {sl} | TP: {tp}",
        "invalidation":  f"Close beyond SL {sl}",
        "tags":          ["manual", pair.lower(), direction.lower(), tf.lower()],
        "source":        "MANUAL",
        "outcome":       "open",
        "saved_at":      now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timestamp":     now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    ok = _github_json_write(path, signal, None, f"Manual signal: {pair} {direction} @ {entry}")
    if not ok:
        await u.message.reply_text("❌ Errore salvataggio su GitHub. Controlla GITHUB_TOKEN.")
        return

    # Notifica canale
    emoji = "🟢" if direction == "BUY" else "🔴"
    msg = (
        f"{emoji} TRADE SETUP — {pair}\n"
        f"Direction: {direction}\n"
        f"Entry: {entry}\n"
        f"SL: {sl}\n"
        f"TP: {tp}\n"
        f"R:R: {rr}\n"
        f"TF: {tf}\n"
        + (f"Note: {note}\n" if note else "")
        + f"\nLive trade setups: xenosfinance.com/trading-signals\n⚠️ Educational content — not investment advice."
    )
    await send_channel(msg)
    await u.message.reply_text(f"✅ Segnale {pair} {direction} pubblicato sul sito e inviato al canale.")


async def cmd_geopolitics(u, c):
    # FIX: rimosso il corpo duplicato che causava il doppio messaggio
    if not await check_auth(u): return
    m = await u.message.reply_text("🌍 Fetching geopolitical news Reuters/CNBC/Al Jazeera/AP...")
    try:
        items = fetch_geopolitics_news(max_items=10)
        txt   = fmt_geopolitics(items)
        # FIX: usa send_long per gestire messaggi > 4096 caratteri
        parts = split_message(txt, max_len=4096)
        for part in parts:
            await send_channel(part)
        await m.edit_text(f"✅ Geopolitical monitor sent! ({len(items)} stories)")
    except Exception as e:
        logger.error(f"geo: {e}", exc_info=True)
        await m.edit_text(f"❌ Error: {str(e)[:100]}")

async def cmd_news(u, c):
    if not await check_auth(u): return
    m = await u.message.reply_text("📰 Generating daily digest...")
    try:
        await u.message.reply_text("⏳ Fetching news Reuters + CNBC + Yahoo Finance...")
        news   = fetch_news_for_brief(max_items=12)
        prices = fetch_prices_for_brief()

        html = generate_news_html(news, prices)
        if html is None:
            await m.edit_text('❌ Template markers missing on GitHub — push index.html first', parse_mode='HTML')
            return
        await m.edit_text("⏳ Publishing to xenosfinance.com...")
        ok   = push_to_github(html)

        now     = datetime.now()
        days_it = ["Lunedì","Martedì","Mercoledì","Giovedì","Venerdì","Sabato","Domenica"]
        day_str = f"{days_it[now.weekday()]} {now.day} {['Gen','Feb','Mar','Apr','Mag','Giu','Lug','Ago','Set','Ott','Nov','Dic'][now.month-1]} {now.year}"
        top3    = news[:3]
        rest    = news[3:8]

        def pline(key, label, fmt=".2f"):
            p = prices.get(key)
            if not p: return ""
            arr = "▲" if p["chg"] >= 0 else "▼"
            col = "+" if p["chg"] >= 0 else ""
            val = f"{p['p']:.4f}" if key in ["EURUSD","USDJPY"] else (f"${p['p']:,.0f}" if key == "BTCUSD" else f"${p['p']:.2f}")
            return f"<code>{label:8}</code> {val}  {arr} {col}{p['chg']:.2f}%\n"

        price_block = (
            pline("SPY",    "S&P 500") +
            pline("NASDAQ", "Nasdaq ") +
            pline("GOLD",   "Gold   ") +
            pline("OIL",    "Oil WTI") +
            pline("EURUSD", "EUR/USD") +
            pline("BTCUSD", "Bitcoin")
        ).strip()

        def build_story(item, idx_n):
            title  = item["title"]
            desc   = item.get("desc","")
            source = item.get("source","").replace("Yahoo Finance","YF").replace("CNBC Markets","CNBC").replace("CNBC Business","CNBC")
            imp_str = ""
            for imp in item.get("impacts", [])[:2]:
                mkt   = MARKETS.get(imp["asset"], {})
                arrow = "▲" if imp["dir"] == "bullish" else "▼" if imp["dir"] == "bearish" else "↔"
                imp_str += f" {arrow}<i>{mkt.get('name', imp['asset'])}</i>"
            if len(title) > 100: title = title[:97] + "…"
            context = ""
            if desc and len(desc) > 30:
                sentences = desc.replace("...","").split(".")
                first = sentences[0].strip() if sentences else ""
                if first and len(first) > 20:
                    context = f"\n<i>└ {first[:150]}</i>"
            line = f"<b>{idx_n}. {title}</b>"
            if imp_str: line += f"\n   {imp_str.strip()}"
            if context: line += context
            return line

        def get_events_today():
            # Fetch real calendar from ForexFactory via Worker
            today_iso = now.strftime("%Y-%m-%d")
            WORKER = "https://xenos-ai-proxy.xenosfinance.workers.dev"
            try:
                r = requests.post(
                    WORKER,
                    json={"type": "forexfactory", "week": "thisweek"},
                    timeout=10
                )
                if r.ok:
                    data = r.json()
                    raw_events = data.get("events", [])
                    # Filter for today only, high/medium impact
                    today_events = []
                    for ev in raw_events:
                        ev_date = (ev.get("time") or "")[:10]
                        if ev_date != today_iso:
                            continue
                        impact = ev.get("impact", "low")
                        if impact not in ("high", "medium"):
                            continue
                        country = ev.get("country", "")
                        event_name = ev.get("event", "")
                        # Format time from ISO to CET
                        try:
                            from datetime import timezone, timedelta
                            t = datetime.fromisoformat(ev["time"].replace("Z", "+00:00"))
                            cet = t + timedelta(hours=1)
                            time_str = cet.strftime("%H:%M")
                        except:
                            time_str = "--:--"
                        flag = {"USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧",
                                "JPY": "🇯🇵", "CHF": "🇨🇭", "AUD": "🇦🇺",
                                "CAD": "🇨🇦", "NZD": "🇳🇿", "CNY": "🇨🇳"}.get(country, "🌐")
                        imp_icon = "🔴" if impact == "high" else "🟡"
                        today_events.append(f"{flag} {imp_icon} {event_name} ({time_str} CET)")
                    if today_events:
                        return today_events
            except Exception as e:
                pass
            # Fallback: generic message if no data
            return ["📊 No major scheduled events today — check xenosfinance.com/calendar"]

        events     = get_events_today()
        events_str = "\n".join(f"  • {e}" for e in events)

        preview  = f"<b>📰 DAILY BRIEF — {day_str}</b>\n"
        preview += f"<i>XenosFinance Market Intelligence · {now.strftime('%H:%M')} CET</i>\n"
        preview += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        if price_block:
            preview += f"<b>📊 MARKET SNAPSHOT</b>\n{price_block}\n\n"
        preview += "<b>🔥 TOP STORIES</b>\n\n"
        if top3:
            for i, item in enumerate(top3, 1):
                preview += build_story(item, i) + "\n\n"
        else:
            preview += "⚠️ No news available.\n\n"
        if rest:
            preview += "<b>📌 MORE NEWS</b>\n"
            for item in rest[:4]:
                src = item.get("source","").replace("Yahoo Finance","YF").replace("CNBC Markets","CNBC")
                lnk = item.get("link","#")
                preview += f"• <a href='{lnk}'>{item['title'][:90]}</a> <i>[{src}]</i>\n"
            preview += "\n"
        preview += f"<b>🗓 WATCH TODAY</b>\n{events_str}\n\n"
        preview += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        preview += f"📖 <a href='https://xenosfinance.com'><b>Full digest → xenosfinance.com</b></a>\n"
        preview += f"<i>XenosFinance · {len(news)} stories analyzed</i>"

        await send_channel(preview)
        status = ("✅ Digest published on xenosfinance.com!" if ok
                  else "✅ Digest sent to channel (GitHub not configured or error)")
        await m.edit_text(status)

    except Exception as e:
        logger.error(f"news: {e}", exc_info=True)
        await m.edit_text(f"❌ Error: {str(e)[:100]}")


async def cmd_outlook(u, c):
    """Global Markets Intraday Brief — FX, Equity, Commodities, Crypto in russo."""
    if not await check_auth(u): return
    m = await u.message.reply_text("📊 Generating market brief...")
    try:
        import concurrent.futures

        # ── Fetch tutti i dati necessari ──
        symbols_needed = {
            # FX majors
            "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
            "AUDUSD": "AUDUSD=X", "USDCHF": "USDCHF=X", "USDCAD": "USDCAD=X",
            "NZDUSD": "NZDUSD=X",
            # Equity indices
            "SPX": "^GSPC", "NDX": "^NDX", "SPY": "SPY", "NASDAQ": "^IXIC", "DJI": "^DJI",
            "DAX": "^GDAXI", "FTSE": "^FTSE", "CAC": "^FCHI", "NKY": "^N225",
            # Commodities
            "GOLD": "GC=F", "OIL": "CL=F", "SILVER": "SI=F", "NGAS": "NG=F",
            # Crypto
            "BTC": "BTC-USD", "ETH": "ETH-USD",
            "XRP": "XRP-USD", "SOL": "SOL-USD", "DOGE": "DOGE-USD", "ZEC": "ZEC-USD",
        }

        def fetch_q(sym, yf_ticker):
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_ticker}"
                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"},
                                 params={"range": "1d", "interval": "5m"}, timeout=10)
                d = r.json()["chart"]["result"][0]
                meta = d.get("meta", {})
                # Use regularMarketPrice — always the live/latest price
                last = float(meta.get("regularMarketPrice") or 0)
                prev = float(meta.get("chartPreviousClose") or meta.get("previousClose") or 0)
                if last <= 0:
                    q = d["indicators"]["quote"][0]
                    closes = [x for x in q["close"] if x is not None]
                    if len(closes) < 1: return None
                    last = closes[-1]
                if last <= 0: return None
                if prev <= 0: prev = last
                chg = ((last - prev) / prev) * 100
                return {"price": last, "chg": chg}
            except: return None

        data = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:
            fut = {sym: ex.submit(fetch_q, sym, yf) for sym, yf in symbols_needed.items()}
            for sym, f in fut.items():
                try: data[sym] = f.result(timeout=12)
                except: data[sym] = None

        now = datetime.now()
        hour = now.hour
        if 0 <= hour < 9:       session = "Asian Session"
        elif 9 <= hour < 13:    session = "European Session"
        elif 13 <= hour < 17:   session = "Europe-New York Overlap"
        elif 17 <= hour < 22:   session = "New York Session"
        else:                   session = "After Hours"

        now_str = now.strftime("%d %b %Y • %H:%M CET")

        await m.edit_text("🤖 Generating AI brief...")

        # ── Prepare data for prompt ──
        def fmt_d(d, dec=2, prefix=""):
            if not d: return "N/D"
            return f"{prefix}{d['price']:.{dec}f} ({d['chg']:+.2f}%)"

        fx_block = f"""EUR/USD: {fmt_d(data.get('EURUSD'), 4)}
GBP/USD: {fmt_d(data.get('GBPUSD'), 4)}
USD/JPY: {fmt_d(data.get('USDJPY'), 4)}
AUD/USD: {fmt_d(data.get('AUDUSD'), 4)}
USD/CHF: {fmt_d(data.get('USDCHF'), 4)}
USD/CAD: {fmt_d(data.get('USDCAD'), 4)}
NZD/USD: {fmt_d(data.get('NZDUSD'), 4)}"""

        eq_block = f"""S&P 500: {fmt_d(data.get('SPX'), 2)}
Nasdaq 100: {fmt_d(data.get('NDX'), 0)}
Dow Jones: {fmt_d(data.get('DJI'), 0)}
DAX: {fmt_d(data.get('DAX'), 0)}
FTSE 100: {fmt_d(data.get('FTSE'), 0)}
CAC 40: {fmt_d(data.get('CAC'), 0)}
Nikkei 225: {fmt_d(data.get('NKY'), 0)}"""

        comm_block = f"""Gold: {fmt_d(data.get('GOLD'), 2, '$')}
WTI Crude: {fmt_d(data.get('OIL'), 2, '$')}
Silver: {fmt_d(data.get('SILVER'), 2, '$')}
Natural Gas: {fmt_d(data.get('NGAS'), 3, '$')}"""

        crypto_block = f"""Bitcoin: {fmt_d(data.get('BTC'), 0, '$')}
Ethereum: {fmt_d(data.get('ETH'), 2, '$')}
Ripple (XRP): {fmt_d(data.get('XRP'), 4, '$')}
Solana: {fmt_d(data.get('SOL'), 2, '$')}
Dogecoin: {fmt_d(data.get('DOGE'), 4, '$')}
Zcash: {fmt_d(data.get('ZEC'), 2, '$')}"""

        prompt = f"""You are a senior macro strategist at XenosFinance.
You are a senior macro analyst at XenosFinance. Write a brief, complete markets overview.
Date: {now_str} | Session: {session}

LIVE DATA:
FOREX: {fx_block}
EQUITY: {eq_block}
COMMODITIES: {comm_block}
CRYPTO: {crypto_block}

FORMAT — write each section exactly as shown, in this order:

🌍 MACRO TONE
[1 sentence: risk-on/off + main catalyst]

📊 FX RANKING [strongest→weakest, 1 line each: EUR +0.3% — brief reason]

💱 KEY PAIRS [3 pairs: EURUSD 1.1605 | Bias: LONG | Watch: 1.1580]

📈 INDICES [4 indices: Nikkei 69318 +4.9% — 1 note]

🛢️ COMMODITIES [Gold + Oil + Silver — price change + 1 driver each]

₿ CRYPTO [BTC + ETH — price + 1-line outlook each]

🎯 TRADE IDEAS
LONG: 2 ideas (asset | entry zone | reason)
SHORT: 2 ideas (asset | entry zone | reason)

📅 KEY EVENTS TODAY [max 3 — Event | Time CET | Impact]

RULES: Use exact prices from data — copy every number exactly as given, never rescale or correct a value. No asterisks. No markdown. No empty sections.
Write all sections fully. Max 350 words total."""

        result = None
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": "claude-sonnet-4-5", "max_tokens": 1200,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=60
            )
            res = r.json()
            # FIX 2026-09-22: max_tokens era 700 per un prompt che chiede 7
            # sezioni diverse (FX ranking, coppie, indici, commodities,
            # crypto, trade ideas, eventi) in "max 350 parole" — un'istruzione
            # che Claude spesso supera cercando di scrivere ogni sezione per
            # intero come richiesto altrove nel prompt. Il testo, essendo
            # semplice (non JSON), non falliva mai il parsing quando tagliato
            # a metà — veniva pubblicato così com'è, a metà frase. Ora un
            # troncamento blocca la pubblicazione invece di mandarla rotta.
            if res.get("stop_reason") == "max_tokens":
                logger.warning("outlook AI: response truncated (max_tokens) — not publishing incomplete content")
                result = None
            elif "content" in res and res["content"]:
                result = strip_bold(res["content"][0]["text"])
        except Exception as e:
            logger.error(f"outlook AI: {e}")

        if not result:
            await m.edit_text("❌ AI unavailable"); return

        header = (
            f"📊 <b>GLOBAL MARKETS BRIEF</b>\n"
            f"<i>{now_str} · {session}</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        footer = (
            f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ <i>Not investment advice.</i>\n"
            f"<i>XenosFinance Macro Desk</i>" + SITE_FOOTER
        )
        full = header + result + footer
        parts = split_message(full, max_len=4096)
        for part in parts:
            await send_channel(part)
        try:
            await m.edit_text("✅ Inviato al canale!")
        except Exception:
            pass
        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            import hashlib as _hl
            _ck = "outlook_" + _hl.md5(str(datetime.now()).encode()).hexdigest()[:8]
            c.bot_data[_ck] = {"text": result, "label": "Global Markets Brief", "now_str": now_str}
            _kb = InlineKeyboardMarkup([[InlineKeyboardButton("📝 Pubblica su XenosBlog", callback_data=f"pub_brief:{_ck}")]])
            await u.message.reply_text("Pubblica sul blog?", reply_markup=_kb)
        except Exception as _ekb:
            logger.warning(f"blog btn outlook: {_ekb}")

    except Exception as e:
        logger.error(f"outlook: {e}", exc_info=True)
        await m.edit_text(f"❌ Error: {str(e)[:100]}")


async def cmd_premarket(u, c):
    """US Pre-Market News & Analysis — top movers, earnings, macro catalysts before NYSE open."""
    if not await check_auth(u): return
    if not ANTHROPIC_API_KEY:
        await u.message.reply_text("⚠️ Configure ANTHROPIC_API_KEY!"); return

    m = await u.message.reply_text("📊 Fetching US pre-market data & news...")
    try:
        import concurrent.futures

        # Fetch key US pre-market symbols
        pm_symbols = {
            "SPY":  "SPY",    "NASDAQ": "^IXIC",  "DJI":   "^DJI",
            "ES":   "ES=F",   "NQ":    "NQ=F",    "YM":    "YM=F",
            "VIX":  "^VIX",   "NVDA":  "NVDA",    "AAPL":  "AAPL",
            "MSFT": "MSFT",   "META":  "META",     "AMZN":  "AMZN",
            "TSLA": "TSLA",   "GOOGL": "GOOGL",    "AMD":   "AMD",
            "JPM":  "JPM",    "GS":    "GS",       "GOLD":  "GC=F",
            "OIL":  "CL=F",   "BTCUSD":"BTC-USD",  "USDJPY":"USDJPY=X",
            "EURUSD":"EURUSD=X",
        }

        def fetch_q(yf_ticker):
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_ticker}"
                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"},
                                 params={"range": "1d", "interval": "5m"}, timeout=10)
                d = r.json()["chart"]["result"][0]
                meta = d.get("meta", {})
                last = float(meta.get("regularMarketPrice") or 0)
                prev = float(meta.get("chartPreviousClose") or meta.get("previousClose") or 0)
                if last <= 0:
                    cls = [x for x in d["indicators"]["quote"][0]["close"] if x is not None]
                    if not cls: return None
                    last = cls[-1]
                if last <= 0: return None
                if prev <= 0: prev = last
                chg = ((last - prev) / prev) * 100
                return {"price": last, "chg": chg}
            except: return None

        data = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:
            futs = {sym: ex.submit(fetch_q, yf) for sym, yf in pm_symbols.items()}
            for sym, f in futs.items():
                try: data[sym] = f.result(timeout=12)
                except: data[sym] = None

        # Fetch pre-market news
        news = fetch_recent_news_for_premarket(max_items=10)

        await m.edit_text("🤖 Generating AI pre-market brief...")

        now     = datetime.now()
        now_str = now.strftime("%d %b %Y • %H:%M CET")

        def fmt_q(sym, dec=2, prefix="$"):
            d = data.get(sym)
            if not d: return "N/D"
            fmt = f".{dec}f"
            return f"{prefix}{d['price']:{fmt}} ({d['chg']:+.2f}%)"

        futures_block = f"""S&P 500 Futures (ES): {fmt_q('ES', 2, '')}
Nasdaq 100 Futures (NQ): {fmt_q('NQ', 0, '')}
Dow Jones Futures (YM): {fmt_q('YM', 0, '')}
VIX: {fmt_q('VIX', 2, '')}"""

        movers_block = f"""NVDA: {fmt_q('NVDA')} | AAPL: {fmt_q('AAPL')} | MSFT: {fmt_q('MSFT')}
META: {fmt_q('META')} | AMZN: {fmt_q('AMZN')} | TSLA: {fmt_q('TSLA')}
GOOGL: {fmt_q('GOOGL')} | AMD: {fmt_q('AMD')}
JPM: {fmt_q('JPM')} | GS: {fmt_q('GS')}"""

        macro_block = f"""Gold: {fmt_q('GOLD')} | Oil WTI: {fmt_q('OIL')}
Bitcoin: {fmt_q('BTCUSD', 0)} | EUR/USD: {fmt_q('EURUSD', 4, '')} | USD/JPY: {fmt_q('USDJPY', 4, '')}"""

        news_block = "\n".join([f"  - {n['title']}" for n in news[:8]]) or "  No news available"

        prompt = f"""You are a senior US equity strategist at XenosFinance.
You are a US equity strategist at XenosFinance. Write a concise pre-market brief.
Date: {now_str}

LIVE DATA:
Futures: {futures_block}
Movers: {movers_block}
Macro: {macro_block}
News: {news_block}

FORMAT — complete every section:

🌅 SNAPSHOT [1 sentence: futures tone + key driver]

📊 FUTURES [S&P | Nasdaq | Dow — price + % + key level]

🎯 TOP MOVERS [4 stocks: AAPL +2.1% — catalyst — key level]

🏦 SECTOR THEME [1 sentence: what leads/lags today]

📰 CATALYSTS [3 items: Event | Time ET | Impact]

⚠️ RISKS [2 lines max]

RULES: Exact prices — copy every number exactly as given, never rescale or correct a value. No asterisks. No markdown. Max 220 words. Complete every section."""

        result = None
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": "claude-sonnet-4-5", "max_tokens": 700,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=60
            )
            res = r.json()
            if "content" in res and res["content"]:
                result = strip_bold(res["content"][0]["text"])
        except Exception as e:
            logger.error(f"premarket AI: {e}")

        if not result:
            await m.edit_text("❌ AI unavailable"); return

        header = (
            f"<b>🌅 US PRE-MARKET BRIEF</b>\n"
            f"<i>{now_str}</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        footer = (
            f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ <i>Not investment advice.</i>\n"
            f"<i>XenosFinance — US Equity Desk</i>" + SITE_FOOTER
        )
        full = header + result + footer
        for part in split_message(full, max_len=4096):
            await send_channel(part)
        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            import hashlib as _hl
            _ck = "premarket_" + _hl.md5(str(datetime.now()).encode()).hexdigest()[:8]
            c.bot_data[_ck] = {"text": result, "label": "Pre-Market Brief", "now_str": now_str}
            _kb = InlineKeyboardMarkup([[InlineKeyboardButton("📝 Pubblica su XenosBlog", callback_data=f"pub_brief:{_ck}")]])
            await u.message.reply_text("Pubblica sul blog?", reply_markup=_kb)
        except Exception as _ekb:
            logger.warning(f"blog btn premarket: {_ekb}")
            await m.edit_text("✅ Sent to channel!")

    except Exception as e:
        logger.error(f"premarket: {e}", exc_info=True)
        await m.edit_text(f"❌ Error: {str(e)[:100]}")


async def cmd_forex(u, c):
    if not await check_auth(u): return
    m = await u.message.reply_text("\U0001f4b1 Generating FX brief...")
    try:
        import concurrent.futures
        fx_symbols = {
            "EURUSD":"EURUSD=X","GBPUSD":"GBPUSD=X","USDJPY":"USDJPY=X",
            "AUDUSD":"AUDUSD=X","USDCHF":"USDCHF=X","USDCAD":"USDCAD=X",
            "NZDUSD":"NZDUSD=X",
            "EURJPY":"EURJPY=X","GBPJPY":"GBPJPY=X","AUDJPY":"AUDJPY=X",
            "CADJPY":"CADJPY=X","CHFJPY":"CHFJPY=X","NZDJPY":"NZDJPY=X",
            "EURGBP":"EURGBP=X","EURAUD":"EURAUD=X","EURCAD":"EURCAD=X","EURCHF":"EURCHF=X",
            "GBPAUD":"GBPAUD=X","GBPCAD":"GBPCAD=X",
            "AUDCAD":"AUDCAD=X","AUDCHF":"AUDCHF=X","CADCHF":"CADCHF=X",
        }
        def _fq(yf_ticker):
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_ticker}"
                r2 = requests.get(url, headers={"User-Agent":"Mozilla/5.0"},
                                  params={"range":"5d","interval":"1d"}, timeout=10)
                d = r2.json()["chart"]["result"][0]
                cls = [x for x in d["indicators"]["quote"][0]["close"] if x is not None]
                if len(cls) < 2: return None
                prev, last = cls[-2], cls[-1]
                chg = ((last-prev)/prev)*100
                wch = ((last-cls[0])/cls[0])*100
                return {"p":last,"ch":chg,"wch":wch}
            except: return None
        data = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
            futs = {s: ex.submit(_fq, y) for s,y in fx_symbols.items()}
            for s, f in futs.items():
                try: data[s] = f.result(timeout=12)
                except: data[s] = None

        now = datetime.now()
        now_str = now.strftime("%d %b %Y \u2022 %H:%M CET")

        def fl(sym, label):
            d = data.get(sym)
            if not d: return f"{label}: N/D"
            return f"{label}: {d['p']:.4f} ({d['ch']:+.2f}% intraday | {d['wch']:+.2f}% sett)"

        majors = "\n".join([fl("EURUSD","EUR/USD"),fl("GBPUSD","GBP/USD"),fl("USDJPY","USD/JPY"),
                             fl("AUDUSD","AUD/USD"),fl("USDCHF","USD/CHF"),fl("USDCAD","USD/CAD"),fl("NZDUSD","NZD/USD")])
        jpy_cx = "\n".join([fl("EURJPY","EUR/JPY"),fl("GBPJPY","GBP/JPY"),fl("AUDJPY","AUD/JPY"),
                             fl("CADJPY","CAD/JPY"),fl("CHFJPY","CHF/JPY"),fl("NZDJPY","NZD/JPY")])
        eur_cx = "\n".join([fl("EURGBP","EUR/GBP"),fl("EURAUD","EUR/AUD"),fl("EURCAD","EUR/CAD"),fl("EURCHF","EUR/CHF")])
        oth_cx = "\n".join([fl("GBPAUD","GBP/AUD"),fl("GBPCAD","GBP/CAD"),fl("AUDCAD","AUD/CAD"),
                             fl("AUDCHF","AUD/CHF"),fl("CADCHF","CAD/CHF")])

        usd_proxy = []
        for sym, sign in [("EURUSD",-1),("GBPUSD",-1),("USDJPY",1),("AUDUSD",-1),("USDCHF",1),("USDCAD",1),("NZDUSD",-1)]:
            d = data.get(sym)
            if d: usd_proxy.append(d["ch"]*sign)
        usd_str = sum(usd_proxy)/len(usd_proxy) if usd_proxy else 0
        usd_label = "DOLLARO FORTE" if usd_str > 0.1 else "DOLLARO DEBOLE" if usd_str < -0.1 else "DOLLARO NEUTRALE"

        hour = now.hour
        if 0 <= hour < 9:     session = "Asian Session"
        elif 9 <= hour < 13:  session = "European Session"
        elif 13 <= hour < 17: session = "Europe-New York Overlap"
        elif 17 <= hour < 22: session = "New York Session"
        else:                 session = "After Hours"

        prompt = (
            f"You are the chief FX strategist at XenosFinance.\n"
            f"Write a COMPLETE but CONCISE FX brief. Date: {now_str} | Session: {session}\n\n"
            f"LIVE FX DATA:\n{majors}\n{jpy_cx}\n{eur_cx}\n{oth_cx}\n"
            f"USD Strength: {usd_str:+.3f} ({usd_label})\n\n"
            "FORMAT — complete every section:\\n\\n"
            "📊 FX THEME [1 sentence: dominant driver]\\n\\n"
            "💪 CURRENCY RANKING [all 8: EUR +0.3% — reason | 1 line each]\\n\\n"
            "💱 KEY PAIRS [4 pairs: EURUSD 1.1605 +0.3% | LONG | S:1.1580 R:1.1650]\\n\\n"
            "🔄 CROSS PAIRS [2 crosses — same format]\\n\\n"
            "🎯 TRADE IDEAS\\n"
            "LONG: 2 (pair | entry | SL | TP | reason)\\n"
            "SHORT: 2 (pair | entry | SL | TP | reason)\\n\\n"
            "⚠️ RISKS [2 lines max]\\n\\n"
            "RULES: Exact prices — copy every number exactly as given, never rescale or correct a value. No asterisks. No markdown.\\n"
            "Max 280 words. Write every section — do not stop early."
        )
        await m.edit_text("\U0001f916 AI is writing FX brief...")
        result = None
        if ANTHROPIC_API_KEY:
            try:
                rr = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
                    json={"model":"claude-sonnet-4-5","max_tokens":700,
                          "messages":[{"role":"user","content":prompt}]},
                    timeout=45
                )
                res = rr.json()
                if "content" in res and res["content"]:
                    result = strip_bold(res["content"][0]["text"])
            except Exception as e:
                logger.error(f"forex AI: {e}")
        if not result:
            await m.edit_text("\u274c AI unavailable"); return
        header = f"<b>\U0001f4b1 FX MARKETS BRIEF</b>\n<i>{now_str} \u00b7 {session}</i>\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
        footer = f"\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\u26a0\ufe0f <i>Not investment advice.</i>\n<i>XenosFinance FX Desk</i>" + SITE_FOOTER
        full = header + result + footer
        for part in split_message(full, max_len=4096):
            await send_channel(part)
        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            import hashlib as _hl
            _ck = "forex_" + _hl.md5(str(datetime.now()).encode()).hexdigest()[:8]
            c.bot_data[_ck] = {"text": result, "label": "FX Brief", "now_str": now_str}
            _kb = InlineKeyboardMarkup([[InlineKeyboardButton("📝 Pubblica su XenosBlog", callback_data=f"pub_brief:{_ck}")]])
            await u.message.reply_text("Pubblica sul blog?", reply_markup=_kb)
        except Exception as _ekb:
            logger.warning(f"blog btn forex: {_ekb}")
            await m.edit_text("✅ Sent to channel!")
    except Exception as e:
        logger.error(f"forex: {e}", exc_info=True)
        await m.edit_text(f"\u274c Error: {str(e)[:100]}")

# ── 2. SOSTITUISCI cmd_crypto ─────────────────────────────────────────────────
async def cmd_crypto(u, c):
    if not await check_auth(u): return
    m = await u.message.reply_text("\u20bf Generating crypto brief...")
    try:
        import concurrent.futures
        crypto_symbols = {
            "BTC":"BTC-USD","ETH":"ETH-USD","BNB":"BNB-USD","XRP":"XRP-USD",
            "SOL":"SOL-USD","ADA":"ADA-USD","AVAX":"AVAX-USD","DOT":"DOT-USD",
            "LINK":"LINK-USD","MATIC":"MATIC-USD","DOGE":"DOGE-USD","ZEC":"ZEC-USD",
        }
        def _fq(yf_ticker):
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_ticker}"
                r2 = requests.get(url, headers={"User-Agent":"Mozilla/5.0"},
                                  params={"range":"7d","interval":"1d"}, timeout=10)
                d = r2.json()["chart"]["result"][0]
                cls = [x for x in d["indicators"]["quote"][0]["close"] if x is not None]
                if len(cls) < 2: return None
                prev, last = cls[-2], cls[-1]
                chg = ((last-prev)/prev)*100
                wch = ((last-cls[0])/cls[0])*100
                return {"p":last,"ch":chg,"wch":wch}
            except: return None
        data = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
            futs = {s: ex.submit(_fq, y) for s,y in crypto_symbols.items()}
            for s, f in futs.items():
                try: data[s] = f.result(timeout=12)
                except: data[s] = None

        now = datetime.now()
        now_str = now.strftime("%d %b %Y \u2022 %H:%M CET")

        def cl(sym, label):
            d = data.get(sym)
            if not d: return f"{label}: N/D"
            fmt = ".0f" if d["p"] > 100 else ".4f" if d["p"] < 1 else ".2f"
            return f"{label}: ${d['p']:{fmt}} ({d['ch']:+.2f}% 24h | {d['wch']:+.2f}% 7d)"

        l1 = "\n".join([cl("BTC","Bitcoin BTC"),cl("ETH","Ethereum ETH"),cl("BNB","BNB")])
        l2 = "\n".join([cl("XRP","Ripple XRP"),cl("SOL","Solana"),cl("ADA","Cardano"),cl("AVAX","Avalanche"),cl("DOT","Polkadot")])
        l3 = "\n".join([cl("LINK","Chainlink"),cl("MATIC","Polygon MATIC"),cl("DOGE","Dogecoin"),cl("ZEC","Zcash")])

        btc_d = data.get("BTC"); eth_d = data.get("ETH")
        btc_chg = btc_d["ch"] if btc_d else 0
        eth_btc = ""
        if btc_d and eth_d:
            ratio = eth_d["ch"] - btc_d["ch"]
            eth_btc = f"ETH/BTC spread 24h: {ratio:+.2f}% ({'ETH outperforms' if ratio > 0.5 else 'BTC outperforms' if ratio < -0.5 else 'alta correlazione'})"

        prompt = (
            "You are the chief crypto strategist at XenosFinance.\n"
            f"Write a COMPLETE but CONCISE crypto brief. Date: {now_str}\n\n"
            f"LIVE CRYPTO DATA:\n{l1}\n{l2}\n{l3}\n{eth_btc}\n"
            f"BTC Sentiment: {'BULLISH' if btc_chg > 1 else 'BEARISH' if btc_chg < -1 else 'NEUTRAL'}\n\n"
            "STRUCTURE (complete every section):\n\n"
            "₿ CRYPTO SUMMARY [2 sentences: overall tone + dominant narrative]\n\n"
            "📊 ASSET RANKING [Top 6 assets, strongest→weakest, format: BTC $105K +2.1% — one-line note]\n\n"
            "🔵 BITCOIN [price, trend, key levels, 1 key catalyst — 3 lines max]\n\n"
            "🔷 ETHEREUM [price, ETH/BTC ratio, DeFi context — 2 lines max]\n\n"
            "🚀 TOP ALT [1 standout altcoin — name, price, reason — 1 line]\n\n"
            "🎯 TRADE IDEAS\n"
            "LONG: 2 setups (asset — reason — entry — SL — TP)\n"
            "SHORT/AVOID: 1 setup (asset — reason)\n\n"
            "⚠️ RISKS [2 risks — 1 line each]\n\n"
            "RULES: Exact prices — copy every number exactly as given, never rescale or correct a value. No asterisks. No markdown. No filler.\n"
            "Target: 300 words maximum. All sections must be complete."
        )
        await m.edit_text("\U0001f916 AI is writing crypto brief...")
        result = None
        if ANTHROPIC_API_KEY:
            try:
                rr = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
                    json={"model":"claude-sonnet-4-5","max_tokens":700,
                          "messages":[{"role":"user","content":prompt}]},
                    timeout=45
                )
                res = rr.json()
                if "content" in res and res["content"]:
                    result = strip_bold(res["content"][0]["text"])
            except Exception as e:
                logger.error(f"crypto AI: {e}")
        if not result:
            await m.edit_text("\u274c AI unavailable"); return
        header = f"<b>\u20bf CRYPTO MARKETS BRIEF</b>\n<i>{now_str}</i>\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
        footer = f"\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\u26a0\ufe0f <i>Not investment advice.</i>\n<i>XenosFinance Crypto Desk</i>" + SITE_FOOTER
        full = header + result + footer
        for part in split_message(full, max_len=4096):
            await send_channel(part)
        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            import hashlib as _hl
            _ck = "crypto_" + _hl.md5(str(datetime.now()).encode()).hexdigest()[:8]
            c.bot_data[_ck] = {"text": result, "label": "Crypto Brief", "now_str": now_str}
            _kb = InlineKeyboardMarkup([[InlineKeyboardButton("📝 Pubblica su XenosBlog", callback_data=f"pub_brief:{_ck}")]])
            await u.message.reply_text("Pubblica sul blog?", reply_markup=_kb)
        except Exception as _ekb:
            logger.warning(f"blog btn crypto: {_ekb}")
            await m.edit_text("✅ Sent to channel!")
    except Exception as e:
        logger.error(f"crypto: {e}", exc_info=True)
        await m.edit_text(f"\u274c Error: {str(e)[:100]}")

# ── 3. SOSTITUISCI cmd_commodities ───────────────────────────────────────────
async def cmd_commodities(u, c):
    if not await check_auth(u): return
    m = await u.message.reply_text("\U0001f6e2\ufe0f Generating commodities brief...")
    try:
        import concurrent.futures
        comm_symbols = {
            "GOLD":"GC=F","SILVER":"SI=F","OIL":"CL=F","BRENT":"BZ=F",
            "NGAS":"NG=F","COPPER":"HG=F","WHEAT":"ZW=F","CORN":"ZC=F",
            "SOYBEANS":"ZS=F","PLATINUM":"PL=F","PALLADIUM":"PA=F",
        }
        def _fq(yf_ticker):
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_ticker}"
                r2 = requests.get(url, headers={"User-Agent":"Mozilla/5.0"},
                                  params={"range":"5d","interval":"1d"}, timeout=10)
                d = r2.json()["chart"]["result"][0]
                cls = [x for x in d["indicators"]["quote"][0]["close"] if x is not None]
                if len(cls) < 2: return None
                prev, last = cls[-2], cls[-1]
                chg = ((last-prev)/prev)*100
                wch = ((last-cls[0])/cls[0])*100
                return {"p":last,"ch":chg,"wch":wch}
            except: return None
        data = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
            futs = {s: ex.submit(_fq, y) for s,y in comm_symbols.items()}
            for s, f in futs.items():
                try: data[s] = f.result(timeout=12)
                except: data[s] = None

        now = datetime.now()
        now_str = now.strftime("%d %b %Y \u2022 %H:%M CET")

        def cl(sym, label, unit=""):
            d = data.get(sym)
            if not d: return f"{label}: N/D"
            return f"{label}: ${d['p']:.2f}{unit} ({d['ch']:+.2f}% intraday | {d['wch']:+.2f}% sett)"

        metals = "\n".join([cl("GOLD","Gold XAU","/oz"),cl("SILVER","Silver XAG","/oz"),
                             cl("PLATINUM","Platinum","/oz"),cl("PALLADIUM","Palladium","/oz"),cl("COPPER","Copper","/lb")])
        energy = "\n".join([cl("OIL","Oil WTI","/bbl"),cl("BRENT","Brent","/bbl"),cl("NGAS","Natural gas","/MMBtu")])
        agri  = "\n".join([cl("WHEAT","Wheat","/bu"),cl("CORN","Corn","/bu"),cl("SOYBEANS","Soybeans","/bu")])

        oil_d = data.get("OIL"); brent_d = data.get("BRENT")
        spread_str = ""
        if oil_d and brent_d:
            spread_str = f"Spread Brent-WTI: ${brent_d['p']-oil_d['p']:.2f}/bbl"

        prompt = (
            "You are the chief commodities strategist at XenosFinance.\n"
            f"Write a COMPLETE but CONCISE commodities brief. Date: {now_str}\n\n"
            f"LIVE DATA:\nPRECIOUS METALS:\n{metals}\nENERGY:\n{energy}\n{spread_str}\nAGRICULTURE:\n{agri}\n\n"
            "STRUCTURE (complete every section):\n\n"
            "🛢️ COMMODITIES SUMMARY [2 sentences: dominant theme + macro driver]\n\n"
            "🥇 PRECIOUS METALS [Gold + Silver + Platinum — format: Gold $3350 +0.8% | Bias: LONG | Key: $3300/$3400]\n\n"
            "⚡ ENERGY [WTI + Brent + spread + NatGas — format: WTI $80.5 -1.2% | Bias: NEUTRAL | Key: $79/$83]\n\n"
            "🌾 AGRICULTURE [2-3 key names — format: Wheat $580 +0.5% — one-line note]\n\n"
            "🎯 TRADE IDEAS\n"
            "LONG: 2 setups (commodity — reason — entry — SL — TP)\n"
            "SHORT: 1 setup (commodity — reason — entry — SL — TP)\n\n"
            "⚠️ RISKS [2 risks — 1 line each]\n\n"
            "RULES: Exact prices — copy every number exactly as given, never rescale or correct a value. No asterisks. No markdown. No filler.\n"
            "Target: 300 words maximum. All sections must be complete."
        )
        await m.edit_text("\U0001f916 AI is writing commodities brief...")
        result = None
        if ANTHROPIC_API_KEY:
            try:
                rr = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
                    json={"model":"claude-sonnet-4-5","max_tokens":700,
                          "messages":[{"role":"user","content":prompt}]},
                    timeout=45
                )
                res = rr.json()
                if "content" in res and res["content"]:
                    result = strip_bold(res["content"][0]["text"])
            except Exception as e:
                logger.error(f"comm AI: {e}")
        if not result:
            await m.edit_text("\u274c AI unavailable"); return
        header = f"<b>\U0001f6e2\ufe0f COMMODITIES MARKETS BRIEF</b>\n<i>{now_str}</i>\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
        footer = f"\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\u26a0\ufe0f <i>Not investment advice.</i>\n<i>XenosFinance Commodities Desk</i>" + SITE_FOOTER
        full = header + result + footer
        for part in split_message(full, max_len=4096):
            await send_channel(part)
        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            import hashlib as _hl
            _ck = "commod_" + _hl.md5(str(datetime.now()).encode()).hexdigest()[:8]
            c.bot_data[_ck] = {"text": result, "label": "Commodities Brief", "now_str": now_str}
            _kb = InlineKeyboardMarkup([[InlineKeyboardButton("📝 Pubblica su XenosBlog", callback_data=f"pub_brief:{_ck}")]])
            await u.message.reply_text("Pubblica sul blog?", reply_markup=_kb)
        except Exception as _ekb:
            logger.warning(f"blog btn commod: {_ekb}")
            await m.edit_text("✅ Sent to channel!")
    except Exception as e:
        logger.error(f"comm: {e}", exc_info=True)
        await m.edit_text(f"\u274c Error: {str(e)[:100]}")

# ── 4. SOSTITUISCI cmd_equity ─────────────────────────────────────────────────
async def cmd_equity(u, c):
    if not await check_auth(u): return
    m = await u.message.reply_text("\U0001f4ca Generating equity brief...")
    try:
        import concurrent.futures
        eq_symbols = {
            # FIX 2026-10: S&P 500 veniva dall'ETF SPY (~1/10 dell'indice) e l'AI lo
            # "correggeva" inventando un valore; Nasdaq era il Composite, non il Nasdaq 100
            # di TradingView (NAS100/NQ). Ora indici veri: ^GSPC e ^NDX (+ Composite a parte).
            "SPX":"^GSPC","NDX":"^NDX","SPY":"SPY","NASDAQ":"^IXIC","DJI":"^DJI","RUT":"^RUT","VIX":"^VIX",
            "DAX":"^GDAXI","FTSE":"^FTSE","CAC":"^FCHI","MIB":"FTSEMIB.MI","IBEX":"^IBEX",
            "NKY":"^N225","HSI":"^HSI","CSI300":"000300.SS",
            "NVDA":"NVDA","AAPL":"AAPL","MSFT":"MSFT","META":"META",
            "AMZN":"AMZN","TSLA":"TSLA","GOOGL":"GOOGL",
        }
        def _fq(yf_ticker):
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_ticker}"
                r2 = requests.get(url, headers={"User-Agent":"Mozilla/5.0"},
                                  params={"range":"5d","interval":"1d"}, timeout=10)
                d = r2.json()["chart"]["result"][0]
                cls = [x for x in d["indicators"]["quote"][0]["close"] if x is not None]
                if len(cls) < 2: return None
                prev, last = cls[-2], cls[-1]
                chg = ((last-prev)/prev)*100
                wch = ((last-cls[0])/cls[0])*100
                return {"p":last,"ch":chg,"wch":wch}
            except: return None
        data = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
            futs = {s: ex.submit(_fq, y) for s,y in eq_symbols.items()}
            for s, f in futs.items():
                try: data[s] = f.result(timeout=12)
                except: data[s] = None

        now = datetime.now()
        now_str = now.strftime("%d %b %Y \u2022 %H:%M CET")

        def el(sym, label, dec=2, pfx=""):
            d = data.get(sym)
            if not d: return f"{label}: N/D"
            return f"{label}: {pfx}{d['p']:,.{dec}f} ({d['ch']:+.2f}% oggi | {d['wch']:+.2f}% sett)"

        us_block  = "\n".join([el("SPX","S&P 500",2),el("NDX","Nasdaq 100",0),el("NASDAQ","Nasdaq Composite",0),el("DJI","Dow Jones",0),el("RUT","Russell 2000",2)])
        vix_d = data.get("VIX")
        vix_str = ""
        if vix_d:
            vl = vix_d["p"]
            vix_str = f"VIX: {vl:.2f} — {'PAURA' if vl>25 else 'ELEVATA' if vl>20 else 'NORMALE' if vl>15 else 'BASSA'}"
        eu_block  = "\n".join([el("DAX","DAX (DE)",0),el("FTSE","FTSE 100 (UK)",0),el("CAC","CAC 40 (FR)",0),el("MIB","FTSE MIB (IT)",0),el("IBEX","IBEX 35 (ES)",0)])
        asia_block= "\n".join([el("NKY","Nikkei 225",0),el("HSI","Hang Seng",0),el("CSI300","CSI 300",0)])
        tech_block= "\n".join([el("NVDA","Nvidia",2,"$"),el("AAPL","Apple",2,"$"),el("MSFT","Microsoft",2,"$"),
                                el("META","Meta",2,"$"),el("AMZN","Amazon",2,"$"),el("TSLA","Tesla",2,"$"),el("GOOGL","Alphabet",2,"$")])

        spy_d = data.get("SPX") or data.get("SPY"); ndq_d = data.get("NDX") or data.get("NASDAQ")
        avg_us = ((spy_d["ch"] if spy_d else 0)+(ndq_d["ch"] if ndq_d else 0))/2
        regime = "RISK ON" if avg_us > 0.5 else "RISK OFF" if avg_us < -0.5 else "TRANSITIONAL"

        hour = now.hour
        if 9 <= hour < 13:    session = "European session"
        elif 13 <= hour < 17: session = "Europe-New York handover"
        elif 17 <= hour < 22: session = "New York session"
        else:                 session = "Asia / Pre-market"

        prompt = (
            f"You are the chief global equity strategist at XenosFinance.\n"
            f"Write a COMPLETE but CONCISE equity brief. Date: {now_str} | Session: {session}\n\n"
            f"LIVE DATA:\nUSA:\n{us_block}\n{vix_str}\nEUROPE:\n{eu_block}\nASIA:\n{asia_block}\nMEGA CAP TECH:\n{tech_block}\n"
            f"Regime: {regime}\n\n"
            "STRUCTURE (complete every section):\n\n"
            "📈 EQUITY SUMMARY [2 sentences: risk regime + session driver]\n\n"
            "🌍 INDEX RANKING [6 indices, best→worst — format: Nikkei 69318 +4.9% — one-line note]\n\n"
            "🇺🇸 US MARKET [S&P + Nasdaq + Dow — key levels, bias, 1 catalyst each — 3 lines max]\n\n"
            "🇪🇺 EUROPE [DAX + FTSE + CAC — 1 line each with level, change, note]\n\n"
            "💻 TECH FOCUS [2 mega caps: price, change, catalyst — 2 lines]\n\n"
            "🎯 TRADE IDEAS\n"
            "LONG: 2 setups (index/stock — reason — entry — SL — TP)\n"
            "SHORT/AVOID: 1 setup (reason)\n\n"
            "⚠️ RISKS [2 risks — 1 line each]\n\n"
            "RULES: Exact prices — copy every number exactly as given, never rescale or correct a value. No asterisks. No markdown. No filler.\n"
            "Target: 300 words maximum. All sections must be complete."
        )
        await m.edit_text("\U0001f916 AI is writing equity brief...")
        result = None
        if ANTHROPIC_API_KEY:
            try:
                rr = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
                    json={"model":"claude-sonnet-4-5","max_tokens":700,
                          "messages":[{"role":"user","content":prompt}]},
                    timeout=45
                )
                res = rr.json()
                if "content" in res and res["content"]:
                    result = strip_bold(res["content"][0]["text"])
            except Exception as e:
                logger.error(f"equity AI: {e}")
        if not result:
            await m.edit_text("\u274c AI unavailable"); return
        header = f"<b>\U0001f4ca EQUITY MARKETS BRIEF</b>\n<i>{now_str} \u00b7 {session}</i>\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
        footer = f"\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\u26a0\ufe0f <i>Not investment advice.</i>\n<i>XenosFinance Equity Desk</i>" + SITE_FOOTER
        full = header + result + footer
        for part in split_message(full, max_len=4096):
            await send_channel(part)
        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            import hashlib as _hl
            _ck = "equity_" + _hl.md5(str(datetime.now()).encode()).hexdigest()[:8]
            c.bot_data[_ck] = {"text": result, "label": "Equity Brief", "now_str": now_str}
            _kb = InlineKeyboardMarkup([[InlineKeyboardButton("📝 Pubblica su XenosBlog", callback_data=f"pub_brief:{_ck}")]])
            await u.message.reply_text("Pubblica sul blog?", reply_markup=_kb)
        except Exception as _ekb:
            logger.warning(f"blog btn equity: {_ekb}")
            await m.edit_text("✅ Sent to channel!")
    except Exception as e:
        logger.error(f"equity: {e}", exc_info=True)
        await m.edit_text(f"\u274c Error: {str(e)[:100]}")
# ─── SCHEDULER ────────────────────────────────────────────────────────────────


# ─── MAIN ─────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
# XENOS MKO ENGINE — Institutional Futures Signal System v1.0
# Multi-asset: Crypto (Binance) + Commodities + FX (Yahoo Finance fallback)
# Layers: Ichimoku · VWAP · Order Book Imbalance · OI Delta · ATR Levels
# Output: Telegram push (auto-scan) + /futures command (manual)
# ══════════════════════════════════════════════════════════════════════════════

try:
    import ccxt
    CCXT_AVAILABLE = True
except ImportError:
    ccxt = None
    CCXT_AVAILABLE = False
    logger.warning("⚠️ ccxt not available — MKO crypto data via Yahoo Finance only")

from threading import Thread

# ── Asset universe ────────────────────────────────────────────────────────────
MKO_ASSETS = {
    # Crypto — Binance Futures (dati completi: candle + orderbook + OI)
    "BTCUSDT":  {"name": "Bitcoin",      "emoji": "₿",  "type": "crypto",     "ccxt": "BTC/USDT",  "yf": "BTC-USD",  "decimals": 0},
    "ETHUSDT":  {"name": "Ethereum",     "emoji": "💎", "type": "crypto",     "ccxt": "ETH/USDT",  "yf": "ETH-USD",  "decimals": 2},
    "SOLUSDT":  {"name": "Solana",       "emoji": "☀️", "type": "crypto",     "ccxt": "SOL/USDT",  "yf": "SOL-USD",  "decimals": 3},
    "BNBUSDT":  {"name": "BNB",          "emoji": "🔶", "type": "crypto",     "ccxt": "BNB/USDT",  "yf": "BNB-USD",  "decimals": 2},
    "XRPUSDT":  {"name": "Ripple",       "emoji": "💧", "type": "crypto",     "ccxt": "XRP/USDT",  "yf": "XRP-USD",  "decimals": 4},
    # Commodities — Yahoo Finance (GC=F, CL=F, SI=F, NG=F)
    "GOLD":     {"name": "Gold",         "emoji": "🥇", "type": "commodity",  "ccxt": None,         "yf": "GC=F",     "decimals": 2},
    "OIL":      {"name": "Crude Oil",    "emoji": "🛢", "type": "commodity",  "ccxt": None,         "yf": "CL=F",     "decimals": 2},
    "SILVER":   {"name": "Silver",       "emoji": "🥈", "type": "commodity",  "ccxt": None,         "yf": "SI=F",     "decimals": 3},
    "NGAS":     {"name": "Natural Gas",  "emoji": "⛽", "type": "commodity",  "ccxt": None,         "yf": "NG=F",     "decimals": 3},
    # FX Majors — Yahoo Finance
    "EURUSD":   {"name": "EUR/USD",      "emoji": "💶", "type": "fx",         "ccxt": None,         "yf": "EURUSD=X", "decimals": 4},
    "GBPUSD":   {"name": "GBP/USD",      "emoji": "💷", "type": "fx",         "ccxt": None,         "yf": "GBPUSD=X", "decimals": 4},
    "USDJPY":   {"name": "USD/JPY",      "emoji": "💴", "type": "fx",         "ccxt": None,         "yf": "USDJPY=X", "decimals": 2},
    # XAUUSD removed — duplicate of GOLD (both use GC=F)
    # US Equities — Yahoo Finance (top liquid stocks)
    "NVDA":     {"name": "NVIDIA",       "emoji": "🟢", "type": "equity",     "ccxt": None,         "yf": "NVDA",     "decimals": 2},
    "AAPL":     {"name": "Apple",        "emoji": "🍎", "type": "equity",     "ccxt": None,         "yf": "AAPL",     "decimals": 2},
    "TSLA":     {"name": "Tesla",        "emoji": "⚡", "type": "equity",     "ccxt": None,         "yf": "TSLA",     "decimals": 2},
    "META":     {"name": "Meta",         "emoji": "📘", "type": "equity",     "ccxt": None,         "yf": "META",     "decimals": 2},
    "AMZN":     {"name": "Amazon",       "emoji": "📦", "type": "equity",     "ccxt": None,         "yf": "AMZN",     "decimals": 2},
    "MSFT":     {"name": "Microsoft",    "emoji": "🪟", "type": "equity",     "ccxt": None,         "yf": "MSFT",     "decimals": 2},
    "SPY":      {"name": "S&P 500 ETF",  "emoji": "📊", "type": "equity",     "ccxt": None,         "yf": "SPY",      "decimals": 2},
    "QQQ":      {"name": "Nasdaq ETF",   "emoji": "💻", "type": "equity",     "ccxt": None,         "yf": "QQQ",      "decimals": 2},
}

# Binance Futures exchange (rate limited, no API key needed for public data)
_binance = None
def _get_binance():
    global _binance
    if not CCXT_AVAILABLE:
        return None
    if _binance is None:
        _binance = ccxt.binance({
            'options': {'defaultType': 'future'},
            'enableRateLimit': True,
        })
    return _binance

# ── Score thresholds ──────────────────────────────────────────────────────────
MKO_SCORE_STRONG  = 7   # ≥7/10 → STRONG signal, push to channel
MKO_SCORE_VALID   = 5   # ≥5/10 → valid signal, shown on /futures
MKO_MIN_RR        = 1.8 # minimum R:R to publish

# ── Auto-scan interval (minutes) ─────────────────────────────────────────────
MKO_SCAN_INTERVAL = 60  # ogni ora

# ── State: last OI values for delta calculation ───────────────────────────────
_oi_prev = {}


# ── Data layer: fetch OHLCV from Binance or Yahoo Finance ────────────────────
def mko_fetch_ohlcv(sym: str, asset: dict, tf="1h", limit=120) -> pd.DataFrame | None:
    """Returns DataFrame with columns: ts open high low close volume"""
    if asset["type"] == "crypto" and asset["ccxt"] and CCXT_AVAILABLE:
        try:
            ex = _get_binance()
            if ex is None:
                raise RuntimeError("ccxt unavailable")
            raw = ex.fetch_ohlcv(asset["ccxt"], timeframe=tf, limit=limit)
            df = pd.DataFrame(raw, columns=["ts","open","high","low","close","volume"])
            df[["open","high","low","close","volume"]] = df[["open","high","low","close","volume"]].astype(float)
            return df
        except Exception as e:
            logger.warning(f"MKO Binance OHLCV {sym}: {e}")
    # Fallback: Yahoo Finance (usato per commodities e FX)
    try:
        import yfinance as yf
        ticker = yf.Ticker(asset["yf"])
        hist = ticker.history(period="10d", interval=tf if tf in ["1h","1d"] else "1h")
        if hist.empty or len(hist) < 30:
            return None
        df = hist.reset_index()
        df = df.rename(columns={"Open":"open","High":"high","Low":"low","Close":"close","Volume":"volume"})
        df["ts"] = df.iloc[:,0].astype(np.int64) // 10**6
        df = df[["ts","open","high","low","close","volume"]].astype(float)
        return df.tail(limit).reset_index(drop=True)
    except Exception as e:
        logger.warning(f"MKO YF OHLCV {sym}: {e}")
        return None


# ── Data layer: order book imbalance (Binance only) ──────────────────────────
def mko_orderbook_imbalance(sym: str, asset: dict, depth=20) -> float | None:
    """Returns imbalance in [-1, +1]. Positive = buyer pressure."""
    if asset["type"] != "crypto" or not asset["ccxt"] or not CCXT_AVAILABLE:
        return None
    try:
        ex = _get_binance()
        if ex is None:
            return None
        ob = ex.fetch_order_book(asset["ccxt"], limit=depth)
        bids = sum(b[1] for b in ob["bids"][:depth])
        asks = sum(a[1] for a in ob["asks"][:depth])
        denom = bids + asks
        if denom == 0:
            return 0.0
        return (bids - asks) / denom
    except Exception as e:
        logger.warning(f"MKO OB {sym}: {e}")
        return None


# ── Data layer: Open Interest + delta ────────────────────────────────────────
def mko_open_interest(sym: str, asset: dict) -> dict | None:
    """Returns dict with oi, oi_prev, oi_delta_pct"""
    if asset["type"] != "crypto" or not asset["ccxt"] or not CCXT_AVAILABLE:
        return None
    try:
        ex = _get_binance()
        if ex is None:
            return None
        raw_sym = asset["ccxt"].replace("/","")
        data = ex.fapiPublicGetOpenInterest({"symbol": raw_sym})
        oi = float(data["openInterest"])
        prev = _oi_prev.get(sym)
        _oi_prev[sym] = oi
        delta_pct = ((oi - prev) / prev * 100) if prev and prev > 0 else 0.0
        return {"oi": oi, "oi_prev": prev, "oi_delta_pct": delta_pct}
    except Exception as e:
        logger.warning(f"MKO OI {sym}: {e}")
        return None


# ── Indicator engine ──────────────────────────────────────────────────────────
def mko_indicators(df: pd.DataFrame) -> dict:
    """
    Calcola tutti gli indicatori su df OHLCV.
    Returns dict con tutti i valori necessari per lo scoring.
    """
    c = df["close"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    v = df["volume"].values.astype(float)
    n = len(c)
    price = c[-1]

    # Yahoo doesn't report real traded volume for FX (fx-type assets here
    # have ccxt=None, so they fall back to Yahoo) — "volume" comes back
    # all/mostly zero. VWAP, Volume Profile and Order Flow Delta below are
    # meaningless when computed on that, and previously degraded silently
    # into values that always read as bearish (price > 0-fallback-VWAP is
    # never true, zero delta is never bullish) — a systematic, silent bias
    # in the scoring for fx-type assets specifically. Gated behind this
    # flag instead: those three indicators stay None/unset when volume
    # isn't real, and mko_score() skips them entirely rather than always
    # counting a bear point.
    has_real_volume = bool((v > 0).sum() >= max(1, n * 0.5))

    # ── EMA ──────────────────────────────────────────────────────
    def ema(arr, p):
        if len(arr) < p:
            return arr[-1]
        k = 2 / (p + 1)
        e = float(np.mean(arr[:p]))
        for x in arr[p:]:
            e = x * k + e * (1 - k)
        return e

    ema20  = ema(c, 20)
    ema50  = ema(c, 50)
    ema200 = ema(c, min(200, n-1))

    # ── ATR ──────────────────────────────────────────────────────
    trs = [max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1])) for i in range(1, n)]
    atr = float(np.mean(trs[-14:])) if len(trs) >= 14 else float(np.mean(trs))

    # ── RSI ──────────────────────────────────────────────────────
    diffs = np.diff(c[-16:])
    gains = diffs[diffs > 0].sum()
    losses = -diffs[diffs < 0].sum()
    rsi = 100 - 100 / (1 + gains / (losses + 1e-9))

    # ── Stoch RSI ────────────────────────────────────────────────
    rsi_series = []
    for i in range(14, n):
        d = np.diff(c[i-14:i+1])
        g = d[d>0].sum(); lo = -d[d<0].sum()
        rsi_series.append(100 - 100/(1+g/(lo+1e-9)))
    stoch_rsi = None
    if len(rsi_series) >= 14:
        sl = rsi_series[-14:]
        mn, mx = min(sl), max(sl)
        stoch_rsi = (rsi_series[-1] - mn) / (mx - mn + 1e-9) * 100

    # ── VWAP ─────────────────────────────────────────────────────
    vwap = None
    if has_real_volume:
        tp = (h + l + c) / 3
        cum_vol = np.cumsum(v)
        cum_tpv = np.cumsum(tp * v)
        vwap = float(cum_tpv[-1] / cum_vol[-1]) if cum_vol[-1] > 0 else price

    # ── Bollinger Bands ──────────────────────────────────────────
    bb_slice = c[-20:]
    bb_mid   = float(np.mean(bb_slice))
    bb_std   = float(np.std(bb_slice))
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    bb_width = (bb_upper - bb_lower) / (bb_mid + 1e-9)

    # ── MACD ─────────────────────────────────────────────────────
    macd_line   = ema(c, 12) - ema(c, 26)
    signal_line = ema(c[-9:], 9) if n >= 9 else macd_line
    macd_hist   = macd_line - signal_line

    # ── Ichimoku ─────────────────────────────────────────────────
    ichi = {}
    if n >= 52:
        tenkan  = (max(h[-9:])  + min(l[-9:]))  / 2
        kijun   = (max(h[-26:]) + min(l[-26:])) / 2
        senkou_a = (tenkan + kijun) / 2
        senkou_b = (max(h[-52:]) + min(l[-52:])) / 2
        ichi = {
            "tenkan": tenkan, "kijun": kijun,
            "senkou_a": senkou_a, "senkou_b": senkou_b,
            "above_cloud": price > max(senkou_a, senkou_b),
            "below_cloud": price < min(senkou_a, senkou_b),
            "tk_cross_bull": tenkan > kijun,
            "cloud_bull": senkou_a > senkou_b,
        }

    # ── Volume analysis ──────────────────────────────────────────
    vol_mean20 = float(np.mean(v[-20:])) if n >= 20 else float(np.mean(v))
    vol_mean5  = float(np.mean(v[-5:]))  if n >= 5  else float(np.mean(v))
    vol_expanding = vol_mean5 > vol_mean20 * 1.15
    vol_climax    = v[-1] > vol_mean20 * 2.0

    # ── Swing highs/lows ─────────────────────────────────────────
    swing_highs = [i for i in range(4, n-4) if h[i] == max(h[i-4:i+5])]
    swing_lows  = [i for i in range(4, n-4) if l[i] == min(l[i-4:i+5])]
    last_sh = h[swing_highs[-1]] if swing_highs else max(h[-20:])
    last_sl = l[swing_lows[-1]]  if swing_lows  else min(l[-20:])

    # ── Volume Profile (POC + Value Area) ────────────────────────────
    # Divide price range into 30 buckets, find highest volume node (POC)
    vp_poc = None
    vp_vah = None
    vp_val = None
    vp_above_poc = False
    vp_in_value_area = False
    try:
        if n >= 20 and has_real_volume:
            price_min = float(np.min(l[-60:])) if n >= 60 else float(np.min(l))
            price_max = float(np.max(h[-60:])) if n >= 60 else float(np.max(h))
            if price_max > price_min:
                n_buckets = 30
                bucket_size = (price_max - price_min) / n_buckets
                buckets = np.zeros(n_buckets)
                use_len = min(60, n)
                for i in range(use_len):
                    idx = int((c[n - use_len + i] - price_min) / bucket_size)
                    idx = min(idx, n_buckets - 1)
                    buckets[idx] += v[n - use_len + i]
                poc_idx = int(np.argmax(buckets))
                vp_poc = price_min + (poc_idx + 0.5) * bucket_size
                # Value Area: 70% of total volume around POC
                total_vol = buckets.sum()
                target_vol = total_vol * 0.70
                va_vol = buckets[poc_idx]
                lo_idx, hi_idx = poc_idx, poc_idx
                while va_vol < target_vol:
                    add_lo = buckets[lo_idx - 1] if lo_idx > 0 else 0
                    add_hi = buckets[hi_idx + 1] if hi_idx < n_buckets - 1 else 0
                    if add_hi >= add_lo and hi_idx < n_buckets - 1:
                        hi_idx += 1; va_vol += add_hi
                    elif lo_idx > 0:
                        lo_idx -= 1; va_vol += add_lo
                    else:
                        break
                vp_vah = price_min + (hi_idx + 1) * bucket_size  # Value Area High
                vp_val = price_min + lo_idx * bucket_size          # Value Area Low
                vp_above_poc     = price > vp_poc
                vp_in_value_area = vp_val <= price <= vp_vah
    except Exception:
        pass

    # ── Order Flow Delta ──────────────────────────────────────────────
    # Approximation: bullish candles → buy volume, bearish → sell volume
    # Cumulative delta over last 20 bars; delta divergence vs price
    of_delta      = 0.0
    of_cum_delta  = None
    of_delta_bull = False
    of_divergence = False  # price up but delta down (or vice versa) = divergence
    try:
        if n >= 20 and has_real_volume:
            deltas = []
            for i in range(n - 20, n):
                candle_range = h[i] - l[i] + 1e-9
                # Estimate buy/sell vol by candle close position
                buy_ratio  = (c[i] - l[i]) / candle_range
                sell_ratio = (h[i] - c[i]) / candle_range
                d = (buy_ratio - sell_ratio) * v[i]
                deltas.append(d)
            of_cum_delta  = float(np.sum(deltas))
            of_delta      = float(deltas[-1])
            of_delta_bull = of_cum_delta > 0
            # Divergence: last 10 bars — price direction vs delta direction
            price_dir = c[-1] > c[-10] if n >= 10 else False
            delta_dir = of_cum_delta > 0
            of_divergence = (price_dir != delta_dir)
    except Exception:
        pass

    return {
        "price": price, "atr": atr, "rsi": rsi, "stoch_rsi": stoch_rsi,
        "ema20": ema20, "ema50": ema50, "ema200": ema200,
        "vwap": vwap, "above_vwap": (price > vwap) if has_real_volume else None,
        "bb_upper": bb_upper, "bb_lower": bb_lower, "bb_mid": bb_mid, "bb_width": bb_width,
        "macd_hist": macd_hist, "macd_bull": macd_hist > 0,
        "ichimoku": ichi,
        "vol_expanding": vol_expanding, "vol_climax": vol_climax, "vol_ratio": vol_mean5 / (vol_mean20 + 1e-9),
        "last_sh": last_sh, "last_sl": last_sl,
        "trend_up":   ema20 > ema50 and price > ema20,
        "trend_down": ema20 < ema50 and price < ema20,
        # Volume Profile
        "vp_poc": vp_poc, "vp_vah": vp_vah, "vp_val": vp_val,
        "vp_above_poc": vp_above_poc, "vp_in_value_area": vp_in_value_area,
        # Order Flow Delta
        "of_cum_delta": of_cum_delta, "of_delta_bull": of_delta_bull,
        "of_divergence": of_divergence, "of_delta": of_delta,
        "has_real_volume": has_real_volume,
    }


# ── Scoring engine ────────────────────────────────────────────────────────────
def mko_score(ind: dict, ob_imbalance: float | None, oi_data: dict | None) -> dict:
    """
    10-point scoring system. Each confirmed condition = 1 point.
    Returns: score (0-10), direction ('BUY'|'SELL'|None), breakdown list.
    Requires at least 5 points + consistent direction to generate signal.
    """
    bull_pts = []
    bear_pts = []

    ichi = ind.get("ichimoku", {})

    # ── Layer 1: Ichimoku (2 pts max) ────────────────────────────
    if ichi:
        if ichi.get("above_cloud") and ichi.get("tk_cross_bull"):
            bull_pts.append("Ichimoku: above cloud + TK cross ↑")
        elif ichi.get("above_cloud"):
            bull_pts.append("Ichimoku: price above cloud")
        if ichi.get("below_cloud") and not ichi.get("tk_cross_bull"):
            bear_pts.append("Ichimoku: below cloud + TK cross ↓")
        elif ichi.get("below_cloud"):
            bear_pts.append("Ichimoku: price below cloud")
        if ichi.get("cloud_bull") and ichi.get("above_cloud"):
            bull_pts.append("Ichimoku: bullish cloud (A>B)")
        elif not ichi.get("cloud_bull") and ichi.get("below_cloud"):
            bear_pts.append("Ichimoku: bearish cloud (B>A)")

    # ── Layer 2: VWAP (1 pt) ─────────────────────────────────────
    if ind.get("above_vwap") is not None:
        if ind["above_vwap"]:
            bull_pts.append("VWAP: price above — institutional buying zone")
        else:
            bear_pts.append("VWAP: price below — institutional selling zone")

    # ── Layer 3: EMA trend (1 pt) ────────────────────────────────
    if ind["trend_up"]:
        bull_pts.append("EMA20 > EMA50: uptrend confirmed")
    elif ind["trend_down"]:
        bear_pts.append("EMA20 < EMA50: downtrend confirmed")

    # ── Layer 4: EMA200 macro filter (1 pt) ──────────────────────
    if ind["price"] > ind["ema200"]:
        bull_pts.append("EMA200: macro bullish (price > 200)")
    else:
        bear_pts.append("EMA200: macro bearish (price < 200)")

    # ── Layer 5: RSI (1 pt normally, 2 pts at extremes) ───────────
    # FIX 2026-09: two corrections to the original version:
    #  1. Extreme readings (deep oversold/overbought) carry MORE
    #     weight than a normal layer, not a hard veto — direction is
    #     still decided by all 10 layers together (majority vote). A
    #     strongly contradicting RSI (e.g. 71+ against a would-be
    #     LONG) now has more say in that vote than a flat 1 point.
    #  2. The "neutral" 35-65 band is no longer always counted as
    #     bullish regardless of where in that range it sits — RSI 42
    #     and falling is NOT the same signal as RSI 63 and rising.
    #     Split at the 50 midline instead: above 50 reads as bullish
    #     momentum building, below 50 as bearish momentum building —
    #     standard RSI reading, and it also closes a gap in the old
    #     ranges (35-40 previously matched neither branch and
    #     contributed nothing to either side).
    rsi = ind["rsi"]
    if rsi >= 80:
        bear_pts.append(f"RSI: {rsi:.0f} — extreme overbought")
        bear_pts.append(f"RSI: {rsi:.0f} — extreme overbought, extra confirmation weight")
    elif rsi > 65:
        bear_pts.append(f"RSI: {rsi:.0f} — overbought distribution")
        bear_pts.append(f"RSI: {rsi:.0f} — overbought, extra confirmation weight")
    elif rsi >= 50:
        bull_pts.append(f"RSI: {rsi:.0f} — above midline, bullish momentum building")
    elif rsi >= 35:
        bear_pts.append(f"RSI: {rsi:.0f} — below midline, bearish momentum building")
    else:  # rsi < 35
        bull_pts.append(f"RSI: {rsi:.0f} — oversold, reversal watch")
        bull_pts.append(f"RSI: {rsi:.0f} — oversold extreme, extra confirmation weight")

    # ── Layer 6: MACD (1 pt) ─────────────────────────────────────
    if ind["macd_bull"]:
        bull_pts.append("MACD: histogram positive — bullish momentum")
    else:
        bear_pts.append("MACD: histogram negative — bearish momentum")

    # ── Layer 7: Order Book Imbalance (1 pt, crypto only) ────────
    ob_str = None
    if ob_imbalance is not None:
        ob_pct = ob_imbalance * 100
        if ob_imbalance > 0.12:
            bull_pts.append(f"Order Book: +{ob_pct:.1f}% buyer pressure (depth 20)")
            ob_str = f"+{ob_pct:.1f}% BUYERS"
        elif ob_imbalance < -0.12:
            bear_pts.append(f"Order Book: {ob_pct:.1f}% seller pressure (depth 20)")
            ob_str = f"{ob_pct:.1f}% SELLERS"

    # ── Layer 8: Open Interest delta (1 pt, crypto only) ─────────
    oi_str = None
    if oi_data:
        delta = oi_data.get("oi_delta_pct", 0)
        if abs(delta) > 0.3:  # OI cambiato di almeno 0.3%
            if delta > 0 and ind["trend_up"]:
                bull_pts.append(f"OI: +{delta:.2f}% — new longs opening (bullish)")
                oi_str = f"↑{delta:.2f}% (longs)"
            elif delta > 0 and ind["trend_down"]:
                bear_pts.append(f"OI: +{delta:.2f}% — new shorts opening (bearish)")
                oi_str = f"↑{delta:.2f}% (shorts)"
            elif delta < 0:
                # OI cala = chiusura posizioni → segnale ambiguo, non punteggiato

                oi_str = f"↓{abs(delta):.2f}% (closing)"

    # ── Layer 9: Volume (1 pt) ───────────────────────────────────
    if ind["vol_expanding"]:
        if ind["trend_up"]:
            bull_pts.append(f"Volume: expanding {ind['vol_ratio']:.1f}x avg — trend confirmed")
        elif ind["trend_down"]:
            bear_pts.append(f"Volume: expanding {ind['vol_ratio']:.1f}x avg — trend confirmed")

    # ── Layer 10: Volume Profile / POC (1 pt) ────────────────────
    vp_poc = ind.get("vp_poc")
    if vp_poc:
        dec_poc = max(2, len(str(round(vp_poc, 6)).split(".")[-1].rstrip("0") or "0"))
        poc_fmt = f"{vp_poc:.{dec_poc}f}"
        if ind.get("vp_above_poc") and ind.get("trend_up"):
            bull_pts.append(f"Vol Profile: price above POC {poc_fmt} — institutional acceptance zone")
        elif not ind.get("vp_above_poc") and ind.get("trend_down"):
            bear_pts.append(f"Vol Profile: price below POC {poc_fmt} — sellers in control")
        if not ind.get("vp_in_value_area"):
            if ind.get("vp_above_poc"):
                bull_pts.append("Vol Profile: price above Value Area — breakout with volume conviction")
            else:
                bear_pts.append("Vol Profile: price below Value Area — breakdown with volume conviction")

    # ── Layer 11: Order Flow Delta (1 pt) ────────────────────────
    if ind.get("of_cum_delta") is not None:
        if ind["of_delta_bull"] and ind.get("trend_up"):
            bull_pts.append("Order Flow: cumulative delta positive — buy-side aggression confirmed")
        elif not ind["of_delta_bull"] and ind.get("trend_down"):
            bear_pts.append("Order Flow: cumulative delta negative — sell-side aggression confirmed")

    # ── Determine direction and score ────────────────────────────
    bull_score = len(bull_pts)
    bear_score = len(bear_pts)

    # FIX 2026-09-23: FX never produced a STRONG signal. FX comes from
    # Yahoo (no real volume) and has no order book / OI, so 7 of the
    # scoring layers (VWAP, Volume, Vol Profile x2, Order Flow, OB, OI)
    # can never fire — max reachable was ~6 raw points, permanently
    # below MKO_SCORE_STRONG (7). The raw count is now scaled to /10 on
    # the layers actually AVAILABLE for that asset, but only when fewer
    # than 10 are available — crypto/commodities/equities (10+ layers)
    # keep exactly the same scoring as before.
    layers_available = 6  # Ichimoku(2) + EMA trend + EMA200 + RSI + MACD
    if ind.get("has_real_volume"):
        layers_available += 5  # VWAP + Volume + Vol Profile(2) + Order Flow
    if ob_imbalance is not None:
        layers_available += 1
    if oi_data:
        layers_available += 1

    def _to_score(raw: int) -> int:
        if layers_available >= 10:
            return min(10, raw)
        return min(10, int(raw * 10 / layers_available))  # floor: FX needs 5/6 aligned layers for 8/10

    if bull_score >= bear_score + 2:
        direction = "BUY"
        score = _to_score(bull_score)
        breakdown = bull_pts
    elif bear_score >= bull_score + 2:
        direction = "SELL"
        score = _to_score(bear_score)
        breakdown = bear_pts
    else:
        direction = None
        score = 0
        breakdown = []

    return {
        "direction": direction,
        "score": score,
        "layers_available": layers_available,
        "breakdown": breakdown,
        "ob_str": ob_str,
        "oi_str": oi_str,
        "bull_score": bull_score,
        "bear_score": bear_score,
    }


# ── Level calculator: Entry / SL / TP ────────────────────────────────────────
def mko_levels(ind: dict, direction: str) -> dict:
    """
    Calcola Entry, Stop Loss e Take Profit basati su ATR e struttura di mercato.
    SL: dietro ultimo swing (con buffer ATR) — mai > 2.5x ATR
    TP1: 1.8 R:R | TP2: 3.0 R:R (Fibonacci projection)
    """
    price = ind["price"]
    atr   = ind["atr"]

    if direction == "BUY":
        # SL: sotto ultimo swing low o EMA50, con buffer
        raw_sl = min(ind["last_sl"], ind["ema50"]) - atr * 0.3
        sl = max(raw_sl, price - atr * 2.5)  # cap: non > 2.5 ATR
        risk = price - sl
        entry = price
        tp1 = price + risk * 1.8
        tp2 = price + risk * 3.0
    else:  # SELL
        raw_sl = max(ind["last_sh"], ind["ema50"]) + atr * 0.3
        sl = min(raw_sl, price + atr * 2.5)
        risk = sl - price
        entry = price
        tp1 = price - risk * 1.8
        tp2 = price - risk * 3.0

    rr1 = abs(tp1 - entry) / abs(sl - entry) if sl != entry else 0

    return {"entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2, "rr1": rr1, "risk": risk}


# ── Claude AI commentary ──────────────────────────────────────────────────────
def mko_claude_commentary(sym: str, asset: dict, ind: dict, scoring: dict,
                           levels: dict, ob_imbalance, oi_data) -> str:
    """
    Chiede a Claude un commento istituzionale breve (max 180 parole).
    Stile: Bloomberg terminal note — niente emoji, plain text professionale.
    """
    if not ANTHROPIC_API_KEY:
        return ""

    ichi = ind.get("ichimoku", {})
    oi_str = f"OI delta: {oi_data['oi_delta_pct']:+.2f}%" if oi_data else "OI: N/A"
    ob_str = f"Order book imbalance: {ob_imbalance*100:+.1f}%" if ob_imbalance is not None else "OB: N/A"
    vwap_val = ind.get("vwap")
    vwap_str = (
        f"{vwap_val:.{asset['decimals']}f} ({'above' if ind.get('above_vwap') else 'below'})"
        if vwap_val is not None else "VWAP: N/A (no real volume data for this instrument)"
    )

    # Volume Profile
    vp_poc = ind.get("vp_poc")
    vp_str = (
        f"Vol Profile POC: {vp_poc:.{asset['decimals']}f} | VAH: {ind.get('vp_vah', vp_poc):.{asset['decimals']}f} | VAL: {ind.get('vp_val', vp_poc):.{asset['decimals']}f} | Price {'above' if ind.get('vp_above_poc') else 'below'} POC | {'Inside' if ind.get('vp_in_value_area') else 'Outside'} Value Area"
        if vp_poc else "Vol Profile: N/A"
    )

    # Order Flow
    of_cum = ind.get("of_cum_delta")
    of_str = (
        f"Order Flow delta: {'positive (buy aggression)' if ind.get('of_delta_bull') else 'negative (sell aggression)'}"
        + (" | DELTA DIVERGENCE DETECTED" if ind.get("of_divergence") else "")
        if of_cum is not None else "Order Flow: N/A"
    )

    prompt = f"""You are a senior futures desk analyst at a tier-1 investment bank.
Write a concise institutional commentary (120-180 words, NO bullet points, plain paragraphs) for this trade setup.

ASSET: {asset['name']} ({sym})
DIRECTION: {scoring['direction']}
SCORE: {scoring['score']}/10 — Confirmed signals: {', '.join(scoring['breakdown'][:4])}

MARKET STRUCTURE:
  Price: {ind['price']:.{asset['decimals']}f} | ATR: {ind['atr']:.{asset['decimals']}f}
  EMA20/50/200: {ind['ema20']:.{asset['decimals']}f} / {ind['ema50']:.{asset['decimals']}f} / {ind['ema200']:.{asset['decimals']}f}
  RSI: {ind['rsi']:.1f} | MACD hist: {ind['macd_hist']:+.{asset['decimals']}f}
  VWAP: {vwap_str}
  Ichimoku: {'above cloud, TK bull' if ichi.get('above_cloud') and ichi.get('tk_cross_bull') else 'below cloud' if ichi.get('below_cloud') else 'in cloud'}
  {ob_str} | {oi_str}
  {vp_str}
  {of_str}

LEVELS:
  Entry: {levels['entry']:.{asset['decimals']}f}
  Stop Loss: {levels['sl']:.{asset['decimals']}f}
  TP1: {levels['tp1']:.{asset['decimals']}f} (R:R 1:{levels['rr1']:.1f})
  TP2: {levels['tp2']:.{asset['decimals']}f}

Focus on: why this setup has institutional conviction, key invalidation factors,
and the primary catalyst for the move. Reference Volume Profile and Order Flow where relevant.
No markdown, no asterisks, plain text only."""

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5",
                "max_tokens": 350,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=20,
        )
        res = r.json()
        if "content" in res and res["content"]:
            return strip_bold(res["content"][0]["text"].strip())
    except Exception as e:
        logger.error(f"MKO Claude {sym}: {e}")
    return ""


# ── Signal formatter ──────────────────────────────────────────────────────────
def mko_format_signal(sym: str, asset: dict, ind: dict,
                       scoring: dict, levels: dict,
                       ob_imbalance, oi_data, commentary: str) -> str:
    """Formatta il segnale MKO — plain text professionale stile desk analyst."""

    dec       = asset["decimals"]
    p         = ind["price"]
    dir_arrow = "▲" if scoring["direction"] == "BUY" else "▼"
    dir_label = "LONG" if scoring["direction"] == "BUY" else "SHORT"
    score_bar = "█" * scoring["score"] + "░" * (10 - scoring["score"])

    # Score label
    if scoring["score"] >= 8:
        score_label = "STRONG CONVICTION"
    elif scoring["score"] >= 6:
        score_label = "HIGH PROBABILITY"
    else:
        score_label = "VALID SETUP"

    # Market state
    trend_str = "Bullish Continuation" if ind["trend_up"] else "Bearish Continuation" if ind["trend_down"] else "Ranging"
    mom_str   = "Rising" if ind["macd_bull"] else "Declining"
    atr_pct   = (ind["atr"] / p) * 100
    vol_str   = "High" if atr_pct > 2 else "Moderate" if atr_pct > 1 else "Low"
    sent_str  = ("Risk-ON" if ind["above_vwap"] and ind["trend_up"]
                 else "Risk-OFF" if ind["above_vwap"] is False and ind["trend_down"]
                 else "Neutral")

    # Ichimoku
    ichi     = ind.get("ichimoku", {})
    ichi_str = "Above cloud + TK cross ↑" if ichi.get("above_cloud") and ichi.get("tk_cross_bull") else                "Above cloud" if ichi.get("above_cloud") else                "Below cloud + TK cross ↓" if ichi.get("below_cloud") else                "Below cloud" if ichi.get("below_cloud") else "Inside cloud"
    cloud_str = "Bullish structure (A>B)" if ichi.get("cloud_bull") else "Bearish structure (B>A)"

    # OI / OB lines
    oi_line = ""
    if oi_data:
        delta  = oi_data["oi_delta_pct"]
        arrow  = "↑" if delta > 0 else "↓"
        oi_line = f"OI          {arrow}{abs(delta):.2f}% — {'new positions opening' if abs(delta) > 0.5 else 'stable'}"
    ob_line = ""
    if ob_imbalance is not None:
        pct    = ob_imbalance * 100
        label  = "BUYER PRESSURE" if pct > 0 else "SELLER PRESSURE"
        ob_line = f"Order Book  {pct:+.1f}% {label}"

    # Volume Profile block
    vp_line = ""
    vp_poc = ind.get("vp_poc")
    if vp_poc:
        vp_vah = ind.get("vp_vah", vp_poc)
        vp_val = ind.get("vp_val", vp_poc)
        poc_pos = "above" if ind.get("vp_above_poc") else "below"
        va_pos  = "inside" if ind.get("vp_in_value_area") else ("above VA" if ind.get("vp_above_poc") else "below VA")
        vp_line = (
            f"\nVOLUME PROFILE\n"
            f"POC         {vp_poc:.{dec}f}  (price {poc_pos})\n"
            f"Value Area  {vp_val:.{dec}f} – {vp_vah:.{dec}f}  [{va_pos}]\n"
        )

    # Order Flow Delta block
    of_line = ""
    of_cum = ind.get("of_cum_delta")
    if of_cum is not None:
        of_dir    = "Positive (buy-side)" if ind.get("of_delta_bull") else "Negative (sell-side)"
        of_align  = "✓ Aligned" if (ind.get("of_delta_bull") == (dir_label == "LONG")) else "✗ Diverging"
        of_div    = "  ⚠ Delta divergence — momentum may be fading" if ind.get("of_divergence") else ""
        of_line = (
            f"\nORDER FLOW\n"
            f"Delta       {of_dir}\n"
            f"Alignment   {of_align} with {dir_label}{of_div}\n"
        )

    # Confirmed signals checkmarks
    signals_str = "\n".join(f"✓ {b}" for b in scoring["breakdown"][:5])

    # Trade management
    sl_dist = abs(levels["sl"] - p)
    tp1_dist = abs(levels["tp1"] - p)
    be_note = f"Break-even above TP1" if dir_label == "LONG" else "Break-even below TP1"

    # Commentary block
    ai_block = f"\n\nAI ANALYSIS\n{commentary}" if commentary else ""

    msg = (
        f"XENOS MKO · {sym} · {dir_arrow} {dir_label}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Score: {scoring['score']}/10 {score_bar}\n"
        f"{score_label}\n\n"
        f"MARKET STATE\n"
        f"Trend       {trend_str}\n"
        f"MACD Momentum {mom_str}\n"
        f"Volatility  {vol_str}\n"
        f"Sentiment   {sent_str}\n\n"
    )

    if commentary:
        # Show commentary as SCENARIO section
        msg += f"SCENARIO\n{commentary}\n\n"

    msg += (
        f"SETUP LEVELS\n"
        f"Entry       {p:.{dec}f}\n"
        f"Stop Loss   {levels['sl']:.{dec}f}  ({abs(levels['sl']-p)/ind['atr']:.1f}x ATR)\n"
        f"Target 1    {levels['tp1']:.{dec}f}  R:R 1:{levels['rr1']:.1f}\n"
        f"Target 2    {levels['tp2']:.{dec}f}  R:R 1:{abs(levels['tp2']-p)/abs(levels['sl']-p):.1f}\n\n"
        f"TRADE MANAGEMENT\n"
        f"• {be_note}\n"
        f"• Momentum confirmation above TP1\n"
        f"• Invalidation beyond {levels['sl']:.{dec}f}\n\n"
        f"TECHNICAL CONFLUENCE\n"
        f"RSI         {ind['rsi']:.0f} — {'bullish momentum' if 45 < ind['rsi'] < 65 else 'oversold' if ind['rsi'] < 35 else 'overbought' if ind['rsi'] > 70 else 'neutral'}\n"
        f"VWAP        {'Price ' + ('above' if ind['above_vwap'] else 'below') + (' ✓' if ind['above_vwap'] == (dir_label == 'LONG') else ' ✗') if ind.get('above_vwap') is not None else 'N/A (no real volume data)'}\n"
        f"Ichimoku    {ichi_str}\n"
        f"Trend       EMA20 {'>' if ind['ema20'] > ind['ema50'] else '<'} EMA50\n"
        f"Cloud       {cloud_str}\n"
    )

    if ob_line:
        msg += f"{ob_line}\n"
    if oi_line:
        msg += f"{oi_line}\n"
    if vp_line:
        msg += vp_line
    if of_line:
        msg += of_line

    msg += (
        f"\nCONFIRMED FACTORS\n"
        f"{signals_str}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        f"{SITE_FOOTER}"
    )

    return msg


# ── Core analysis function ────────────────────────────────────────────────────
def mko_analyze(sym: str, tf="1h") -> dict | None:
    """
    Full pipeline for one asset.
    Returns result dict or None if no valid signal.
    """
    asset = MKO_ASSETS.get(sym)
    if not asset:
        return None

    df = mko_fetch_ohlcv(sym, asset, tf=tf)
    if df is None or len(df) < 60:
        logger.warning(f"MKO: insufficient data for {sym}")
        return None

    ind     = mko_indicators(df)
    ob_imb  = mko_orderbook_imbalance(sym, asset)
    oi_data = mko_open_interest(sym, asset)
    scoring = mko_score(ind, ob_imb, oi_data)

    if scoring["direction"] is None or scoring["score"] < MKO_SCORE_VALID:
        return None

    levels = mko_levels(ind, scoring["direction"])
    if levels["rr1"] < MKO_MIN_RR:
        logger.info(f"MKO {sym}: R:R {levels['rr1']:.1f} below minimum {MKO_MIN_RR} — skip")
        return None

    if scoring["score"] >= 8:
        commentary = mko_claude_commentary(sym, asset, ind, scoring, levels, ob_imb, oi_data)
    else:
        direction  = scoring["direction"]
        trend_str  = "bullish" if ind.get("trend_up") else "bearish"
        vp_poc     = ind.get("vp_poc")
        poc_str    = f" POC at {vp_poc:.{asset['decimals']}f}." if vp_poc else ""
        commentary = (
            f"{asset.get('name', sym)} shows a {trend_str} setup with score {scoring['score']}/10.{poc_str} "
            f"Key levels confirmed by VWAP, EMA stack and momentum indicators. "
            f"{'Long' if direction == 'BUY' else 'Short'} bias with defined risk parameters."
        )
    message = mko_format_signal(sym, asset, ind, scoring, levels, ob_imb, oi_data, commentary)

    return {
        "sym": sym, "asset": asset, "score": scoring["score"],
        "direction": scoring["direction"], "levels": levels,
        "message": message, "ind": ind, "commentary": commentary,
    }


# ── MKO chart generator ───────────────────────────────────────────────────────
def _mko_chart(sym: str, asset: dict, df: pd.DataFrame, levels: dict, direction: str) -> bytes | None:
    """
    Genera un chart candlestick 1H per un segnale MKO.
    Restituisce i bytes PNG, oppure None se matplotlib non è disponibile.
    """
    if not CHARTS_AVAILABLE or df is None or len(df) < 30:
        return None
    try:
        import io
        _base_style()

        data = df.tail(72).reset_index(drop=True)
        x    = range(len(data))

        sl   = levels.get("sl",  0)
        tp1  = levels.get("tp1", 0)
        tp2  = levels.get("tp2", 0)
        entry_price = levels.get("entry", df["close"].iloc[-1])

        dec  = asset.get("decimals", 2)
        pfmt = f".{dec}f"
        name = asset.get("name", sym)
        emoji = asset.get("emoji", "")

        fig = plt.figure(figsize=(10, 6), facecolor=DARK_BG)
        fig.suptitle(
            f'MKO SETUP — {emoji} {name}  ·  {direction}  ·  {datetime.utcnow().strftime("%d %b %Y %H:%M UTC")}',
            color=WHITE, fontsize=10, fontweight="bold", y=0.98
        )

        gs  = gridspec.GridSpec(2, 1, height_ratios=[5, 1.5], hspace=0.06)
        ax1 = fig.add_subplot(gs[0])
        ax2 = fig.add_subplot(gs[1], sharex=ax1)

        # ── Candlestick ──
        for i, row in data.iterrows():
            col = GREEN if row["close"] >= row["open"] else RED
            bot = min(row["open"], row["close"])
            top = max(row["open"], row["close"])
            ax1.bar(i, top - bot, bottom=bot, color=col, width=0.7, alpha=0.85)
            ax1.plot([i, i], [row["low"],  bot],        color=col, linewidth=0.7, alpha=0.85)
            ax1.plot([i, i], [top, row["high"]],        color=col, linewidth=0.7, alpha=0.85)

        # ── MAs ──
        c_ser = data["close"]
        sma20 = c_ser.rolling(20).mean().values
        sma50 = c_ser.rolling(50).mean().values
        ax1.plot(x, sma20, color=BLUE,   linewidth=1.0, label="SMA20", alpha=0.85)
        ax1.plot(x, sma50, color=ORANGE, linewidth=1.0, label="SMA50", alpha=0.85)

        # ── Levels ──
        dir_color = GREEN if direction == "LONG" else RED
        if sl   > 0: ax1.axhline(sl,   color=RED,        linewidth=1.2, linestyle="--", alpha=0.9,  label=f"SL {sl:{pfmt}}")
        if tp1  > 0: ax1.axhline(tp1,  color=GREEN,      linewidth=1.2, linestyle="--", alpha=0.9,  label=f"TP1 {tp1:{pfmt}}")
        if tp2  > 0 and tp2 != tp1:
                     ax1.axhline(tp2,  color=BLUE,        linewidth=0.9, linestyle=":",  alpha=0.7,  label=f"TP2 {tp2:{pfmt}}")
        if entry_price > 0:
                     ax1.axhline(entry_price, color=WHITE, linewidth=0.8, linestyle="-", alpha=0.45, label=f"Entry {entry_price:{pfmt}}")

        # ── Score badge (top-left) ──
        score_txt = f"MKO Score: {levels.get('score', '?')}/10  ·  R:R {levels.get('rr1', 0):.1f}x"
        ax1.text(0.01, 0.97, score_txt, transform=ax1.transAxes,
                 color=dir_color, fontsize=8, va="top", ha="left",
                 bbox=dict(facecolor=DARK_BG, alpha=0.7, edgecolor="none", pad=3))

        ax1.legend(fontsize=7, loc="upper right", framealpha=0.5,
                   facecolor=DARK_BG, edgecolor="#333", labelcolor=WHITE)
        ax1.set_facecolor(DARK_BG)
        ax1.tick_params(colors=WHITE, labelsize=7)
        ax1.spines[:].set_color("#1e3050")
        plt.setp(ax1.get_xticklabels(), visible=False)

        # ── Volume ──
        vol = data["volume"].values
        vcols = [GREEN if data["close"].iloc[i] >= data["open"].iloc[i] else RED for i in range(len(data))]
        ax2.bar(x, vol, color=vcols, alpha=0.6, width=0.7)
        ax2.set_facecolor(DARK_BG)
        ax2.tick_params(colors=WHITE, labelsize=6)
        ax2.spines[:].set_color("#1e3050")
        ax2.set_ylabel("Vol", color=WHITE, fontsize=6)

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                    facecolor=DARK_BG, edgecolor="none")
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        logger.warning(f"_mko_chart {sym}: {e}")
        try:
            plt.close("all")
        except Exception:
            pass
        return None


# ── Auto-scan: background thread ──────────────────────────────────────────────
def _mko_push_idea(sym: str, result: dict) -> bool:
    """
    Salva un segnale MKO su trading_ideas/ideas.json (GitHub).
    Riusa la stessa struttura di push_trading_idea().
    """
    import uuid
    asset     = result["asset"]
    levels    = result["levels"]
    ind       = result["ind"]
    direction = result["direction"]  # "LONG" | "SHORT"
    score     = result["score"]

    idea_id   = str(uuid.uuid4())
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # Mappa category MKO → categoria Trading Ideas
    cat_map = {"crypto": "crypto", "commodity": "commodities", "fx": "forex"}
    category = cat_map.get(asset.get("type", ""), "indices")

    # Confidence: score MKO è su 10, portiamo a %
    confidence = int(result["score"] * 10)

    # ── Genera chart MKO ──────────────────────────────────────────────────────
    image_url = ""
    try:
        df_chart = mko_fetch_ohlcv(sym, asset, tf="1h", limit=120)
        if df_chart is not None and len(df_chart) >= 30:
            # Aggiungi score al dict levels per il badge nel chart
            levels_chart = dict(levels)
            levels_chart["score"] = score
            chart_bytes = _mko_chart(sym, asset, df_chart, levels_chart, direction)
            if chart_bytes:
                filename  = f"mko_{sym}_{idea_id[:8]}.png"
                image_url = _github_image_upload(chart_bytes, filename) or ""
    except Exception as e:
        logger.warning(f"MKO chart generation failed for {sym}: {e}")

    price_now  = round(ind.get("price", levels.get("entry", 0)), asset.get("decimals", 2))
    tp1_raw    = levels.get("tp1", 0)
    sl_raw     = levels.get("sl", 0)
    dec        = asset.get("decimals", 2)
    is_long_mk = direction == "BUY"

    # Sanity check: tp1 must be on correct side of price
    if price_now > 0 and tp1_raw > 0:
        tp_ok = (tp1_raw > price_now) if is_long_mk else (tp1_raw < price_now)
        if not tp_ok:
            tp1_raw = levels.get("tp2", tp1_raw)  # try tp2
            tp_ok2 = (tp1_raw > price_now) if is_long_mk else (tp1_raw < price_now)
            if not tp_ok2:
                atr_v = ind.get("atr", price_now * 0.01)
                tp1_raw = price_now + atr_v * 1.8 if is_long_mk else price_now - atr_v * 1.8
                logger.warning(f"_mko_push_idea {sym}: tp1 wrong side — ATR fallback {tp1_raw:.{dec}f}")

    if price_now > 0 and sl_raw > 0:
        sl_ok = (sl_raw < price_now) if is_long_mk else (sl_raw > price_now)
        if not sl_ok:
            atr_v = ind.get("atr", price_now * 0.01)
            sl_raw = price_now - atr_v * 1.5 if is_long_mk else price_now + atr_v * 1.5
            logger.warning(f"_mko_push_idea {sym}: sl wrong side — ATR fallback {sl_raw:.{dec}f}")

    # Estrai commentary (testo puro della SCENARIO section) da result
    raw_message = result.get("message", "")
    commentary  = result.get("commentary", "")   # passato direttamente se disponibile

    # Se commentary non è nel result, estrailo dal message (dopo "SCENARIO\n")
    if not commentary and "SCENARIO\n" in raw_message:
        try:
            commentary = raw_message.split("SCENARIO\n", 1)[1].split("\n\nSETUP LEVELS")[0].split("\n\nSIGNAL LEVELS")[0].strip()
        except Exception:
            commentary = ""

    # Market state dal result o dai parametri ind/scoring già calcolati
    ind_r    = result.get("ind", {})
    score_r  = result.get("score", score)
    dir_r    = result.get("direction", direction)
    trend_str  = "Bullish Continuation" if ind_r.get("trend_up") else "Bearish Continuation" if ind_r.get("trend_down") else "Ranging"
    mom_str    = "Rising" if ind_r.get("macd_bull") else "Declining"
    p_r        = ind_r.get("price", price_now)
    atr_pct    = (ind_r.get("atr", p_r * 0.01) / p_r) * 100 if p_r else 1
    vol_str    = "High" if atr_pct > 2 else "Moderate" if atr_pct > 1 else "Low"
    sent_str   = ("Risk-ON" if ind_r.get("above_vwap") and ind_r.get("trend_up")
                  else "Risk-OFF" if ind_r.get("above_vwap") is False and ind_r.get("trend_down")
                  else "Neutral")
    score_label = "STRONG CONVICTION" if score_r >= 8 else "HIGH PROBABILITY" if score_r >= 6 else "VALID SETUP"

    # Scenario title: prima riga del commentary (spesso è il titolo in caps)
    scenario_title = ""
    if commentary:
        first_line = commentary.split("\n")[0].strip()
        if first_line.isupper() or (len(first_line) < 80 and first_line == first_line.upper()):
            scenario_title = first_line
            commentary_body = "\n".join(commentary.split("\n")[1:]).strip()
        else:
            scenario_title = f"{asset.get('name', sym).upper()} {dir_r} SETUP - INSTITUTIONAL COMMENTARY"
            commentary_body = commentary
    else:
        commentary_body = ""

    idea = {
        "id":           idea_id,
        "timestamp":    timestamp,
        "ticker":       sym,
        "name":         asset.get("name", sym),
        "emoji":        asset.get("emoji", "📊"),
        "timeframe":    "1H",
        "bias":         direction,
        "confidence":   confidence,
        "price":        price_now,
        "target":       round(tp1_raw, dec),
        "invalidation": round(sl_raw, dec),
        "analysis":     _strip_html(commentary_body or raw_message),
        "narrative":    _strip_html(commentary_body or raw_message),
        "scenario_title": scenario_title,
        "market_state": {
            "trend":      trend_str,
            "momentum":   mom_str,
            "volatility": vol_str,
            "sentiment":  sent_str,
        },
        "score_label":  score_label,
        "image_url":    image_url,
        "source":       "MKO",
        "rr":           round(levels.get("rr1", 0), 2),
        "score":        score,
        "tg_url":       result.get("tg_url", ""),
    }

    ideas, sha = _github_json_read(TRADING_IDEAS_FILE)
    if ideas is None:
        logger.error("MKO push idea: impossibile leggere ideas.json")
        return False
    ideas.insert(0, idea)
    if len(ideas) > TRADING_IDEAS_MAX:
        ideas = ideas[:TRADING_IDEAS_MAX]
    ok = _github_json_write(TRADING_IDEAS_FILE, ideas, sha, f"MKO Signal: {sym} {direction} score={score} {timestamp}")
    if ok:
        logger.info(f"✅ MKO idea salvata su GitHub: {sym} {direction} image={'✓' if image_url else '✗'}")
    return ok


# Dedup cache: {sym: timestamp} — per-symbol cooldown (indipendente dalla direction)
_mko_sent: dict = {}
MKO_DEDUP_TTL = 24 * 60 * 60  # 24h cooldown per asset (A+B combinati)

# Daily cap: {YYYY-MM-DD: count} — max segnali per giorno solare
_mko_daily_count: dict = {}
MKO_DAILY_CAP = 5  # max 5 segnali al giorno in totale

# ── Persistent dedup helpers (GitHub JSON) ────────────────────────────────────
MKO_DEDUP_FILE = "data/mko_dedup.json"

def _mko_dedup_load() -> dict:
    """Carica cache dedup da GitHub. In caso di file mancante, ricostruisce da ideas.json."""
    try:
        data, _ = _github_json_read(MKO_DEDUP_FILE)
        if isinstance(data, dict) and data:
            logger.info(f"MKO dedup loaded from file: {len(data)} entries")
            return data
    except Exception:
        pass

    # Fallback: ricostruisce dedup dagli ultimi segnali MKO in ideas.json
    logger.info("MKO dedup file vuoto/mancante — bootstrap da ideas.json")
    cache = {}
    try:
        ideas, _ = _github_json_read(TRADING_IDEAS_FILE)
        if isinstance(ideas, list):
            cutoff = time.time() - MKO_DEDUP_TTL
            for idea in ideas:
                if idea.get("source") != "MKO":
                    continue
                ts_str = idea.get("timestamp", "")
                try:
                    ts = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(
                        tzinfo=__import__('datetime').timezone.utc).timestamp()
                except Exception:
                    continue
                if ts < cutoff:
                    continue
                key = idea['ticker']  # per-symbol cooldown, direction-agnostic
                # Tieni il più recente per ogni key
                if key not in cache or ts > cache[key]:
                    cache[key] = ts
            logger.info(f"MKO dedup bootstrap: {len(cache)} entries da ideas.json")
    except Exception as e:
        logger.warning(f"MKO dedup bootstrap failed: {e}")
    return cache

def _mko_dedup_save(cache: dict):
    """Salva cache dedup su GitHub, eliminando le entry scadute (>48h)."""
    try:
        cutoff = time.time() - 48 * 3600
        pruned = {k: v for k, v in cache.items() if v > cutoff}
        _, sha = _github_json_read(MKO_DEDUP_FILE)
        _github_json_write(MKO_DEDUP_FILE, pruned, sha, "MKO dedup update")
    except Exception as e:
        logger.warning(f"MKO dedup save: {e}")

def _mko_is_market_open(asset: dict) -> bool:
    """
    Ritorna True se il mercato dell'asset è aperto adesso.
    - equity (NYSE): lunedì-venerdì 13:30-20:00 UTC (pre-market escluso)
    - fx: chiude venerdì 21:00 UTC, riapre domenica 22:00 UTC
    - commodity (oro/argento/petrolio, CME Globex): chiude venerdì 21:00 UTC,
      riapre domenica 22:00 UTC, pausa giornaliera 21:00-22:00 UTC nei feriali
    - crypto: sempre aperto nei giorni feriali, disabilitata nel weekend
    """
    asset_type = asset.get("type", "")
    now_utc = datetime.utcnow()
    weekday = now_utc.weekday()  # 0=lunedì, 6=domenica
    hour    = now_utc.hour
    minute  = now_utc.minute
    h_min   = hour + minute / 60.0

    if asset_type == "crypto":
        return weekday < 5  # crypto disabilitata sabato (5) e domenica (6)

    if asset_type == "equity":
        if weekday >= 5:
            return False  # NYSE chiuso nel weekend
        # NYSE: 09:30-16:00 ET = 13:30-20:00 UTC (ora legale US)
        return 13.5 <= h_min < 20.0

    if asset_type in ("fx", "commodity"):
        # Mercato chiuso da venerdì 21:00 UTC a domenica 22:00 UTC (nessuna eccezione)
        if weekday == 4 and h_min >= 21.0:   # venerdì dopo le 21 UTC
            return False
        if weekday == 5:                     # tutto sabato: chiuso
            return False
        if weekday == 6 and h_min < 22.0:    # domenica prima delle 22 UTC: chiuso
            return False
        if asset_type == "commodity" and weekday < 5 and 21.0 <= h_min < 22.0:
            return False  # pausa giornaliera CME Globex nei feriali
        return True

    return True  # default: aperto

async def mko_auto_scan():
    """
    Scansione automatica ogni MKO_SCAN_INTERVAL minuti.
    - Pubblica solo score >= MKO_SCORE_STRONG
    - Dedup persistente su GitHub (sopravvive ai riavvii Railway)
    - Filtro ore di mercato: equity solo NYSE open, fx/commodity solo giorni lavorativi
    - Max 3 segnali per ciclo
    """
    await asyncio.sleep(30)
    logger.info("🔍 MKO Auto-scan started")

    # Carica dedup persistente all'avvio
    global _mko_sent
    _mko_sent = _mko_dedup_load()
    logger.info(f"MKO dedup loaded: {len(_mko_sent)} entries")

    while True:
        try:
            logger.info("MKO: scanning all assets...")
            found = 0
            MAX_SIGNALS_PER_SCAN = 3  # quality > quantity
            now = time.time()
            today_str = datetime.utcnow().strftime("%Y-%m-%d")
            dedup_dirty = False

            # Conta segnali già inviati oggi
            signals_today = _mko_daily_count.get(today_str, 0)
            if signals_today >= MKO_DAILY_CAP:
                logger.info(f"MKO: daily cap {MKO_DAILY_CAP} raggiunto per {today_str} — scan saltato")
                await asyncio.sleep(MKO_SCAN_INTERVAL * 60)
                continue

            for sym, asset in MKO_ASSETS.items():
                try:
                    # ── Filtro ore di mercato ─────────────────────────────────
                    if not _mko_is_market_open(asset):
                        logger.info(f"MKO SKIP (market closed): {sym} ({asset.get('type')})")
                        continue

                    result = mko_analyze(sym)
                    if not result or result["score"] < MKO_SCORE_STRONG:
                        continue

                    # ── Dedup check A: per-symbol cooldown 24h ────────────────
                    # Chiave SOLO sul simbolo, indipendente dalla direction
                    # Evita che un asset spammi sia BUY che SELL nella stessa giornata
                    key = sym
                    last_sent = _mko_sent.get(key, 0)
                    elapsed_h = (now - last_sent) / 3600
                    if now - last_sent < MKO_DEDUP_TTL:
                        logger.info(f"MKO SKIP (cooldown {elapsed_h:.1f}h/{MKO_DEDUP_TTL/3600:.0f}h): {sym}")
                        continue

                    # ── Dedup check B: daily cap globale ─────────────────────
                    signals_today = _mko_daily_count.get(today_str, 0)
                    if signals_today >= MKO_DAILY_CAP:
                        logger.info(f"MKO: daily cap {MKO_DAILY_CAP} raggiunto — stop scan")
                        break

                    if found >= MAX_SIGNALS_PER_SCAN:
                        logger.info(f"MKO: cap {MAX_SIGNALS_PER_SCAN} raggiunto — stop scan")
                        break

                    logger.info(f"MKO SIGNAL: {sym} {result['direction']} score={result['score']}")
                    msg_id = await send_channel(result["message"])
                    _mko_sent[key] = now           # per-symbol cooldown
                    _mko_daily_count[today_str] = _mko_daily_count.get(today_str, 0) + 1
                    dedup_dirty = True
                    found += 1

                    try:
                        tg_url = f"https://t.me/xenoswavefinance/{msg_id}" if isinstance(msg_id, int) else ""
                        result["tg_url"] = tg_url
                        await asyncio.get_event_loop().run_in_executor(None, _mko_push_idea, sym, result)
                    except Exception as e_push:
                        logger.error(f"❌ MKO push idea FAILED {sym}: {e_push}", exc_info=True)

                    await asyncio.sleep(3)

                except Exception as e:
                    logger.warning(f"MKO scan {sym}: {e}")
                await asyncio.sleep(1)

            # Salva dedup su GitHub solo se ci sono nuovi segnali
            if dedup_dirty:
                await asyncio.get_event_loop().run_in_executor(None, _mko_dedup_save, _mko_sent)

            logger.info(f"MKO scan complete — {found} signals published (today total: {_mko_daily_count.get(today_str, 0)}/{MKO_DAILY_CAP})")

        except Exception as e:
            logger.error(f"MKO auto-scan error: {e}")

        await asyncio.sleep(MKO_SCAN_INTERVAL * 60)


# ── MKO preview → approve/discard before publishing ──────────────────────────
# FIX 2026-09-23: /futures used to push every signal straight to the
# channel. Now each signal is sent to the owner as a preview with two
# buttons; only ✅ publishes it to @xenoswavefinance. The auto-scan loop
# (mko_auto_scan) is unchanged.
MKO_PREVIEW_TTL = 6 * 60 * 60  # preview buttons expire after 6h

async def _mko_send_preview(u, c, result: dict):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    key = "mko_" + hashlib.md5(f"{result.get('sym','')}{time.time()}".encode()).hexdigest()[:10]
    c.bot_data[key] = {"message": result["message"], "ts": time.time(),
                       "sym": result.get("sym"), "result": result,
                       "label": f"{result['asset']['name']} {result['direction']} {result['score']}/10"}
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Pubblica sul canale", callback_data=f"mko_pub:{key}"),
        InlineKeyboardButton("❌ Scarta", callback_data=f"mko_del:{key}"),
    ]])
    await u.message.reply_text(result["message"], parse_mode="HTML",
                               disable_web_page_preview=True, reply_markup=kb)

async def _cb_mko_preview(update, context):
    query = update.callback_query
    if query.from_user.id != OWNER_ID:
        await query.answer("🚫 Access denied", show_alert=True)
        return
    action, key = query.data.split(":", 1)
    cached = context.bot_data.get(key)
    if not cached or time.time() - cached.get("ts", 0) > MKO_PREVIEW_TTL:
        context.bot_data.pop(key, None)
        await query.answer("⚠️ Anteprima scaduta — rigenera con /futures", show_alert=True)
        await query.edit_message_reply_markup(reply_markup=None)
        return
    await query.edit_message_reply_markup(reply_markup=None)
    if action == "mko_pub":
        await query.answer("📤 Invio al canale...")
        msg_id = await send_channel(cached["message"])
        if not msg_id:
            await query.message.reply_text("❌ Invio fallito — controlla i log Railway.")
            context.bot_data.pop(key, None)
            return
        # Same post-publish path as mko_auto_scan: save the idea to
        # trading_ideas/ideas.json (site + broker-engine's MKOSignalSource
        # reads it from there → eligible for MT5 if the symbol is allowed)
        # and set the 24h per-asset cooldown so the auto-scan doesn't
        # re-post the same asset.
        sym = cached.get("sym")
        idea_ok = False
        if sym and cached.get("result"):
            try:
                res = cached["result"]
                res["tg_url"] = f"https://t.me/xenoswavefinance/{msg_id}" if isinstance(msg_id, int) else ""
                idea_ok = await asyncio.get_event_loop().run_in_executor(None, _mko_push_idea, sym, res)
                _mko_sent[sym] = time.time()
                await asyncio.get_event_loop().run_in_executor(None, _mko_dedup_save, _mko_sent)
            except Exception as e_push:
                logger.error(f"MKO preview push idea FAILED {sym}: {e_push}", exc_info=True)
        await query.message.reply_text(
            f"✅ Pubblicato: {cached['label']}" + ("\n📌 Salvato in Trading Ideas" if idea_ok else "\n⚠️ Trading Ideas non aggiornato (vedi log)")
        )
    else:
        await query.answer("Scartato")
        await query.message.reply_text(f"🗑 Scartato: {cached['label']}")
    context.bot_data.pop(key, None)


# ── /futures command ──────────────────────────────────────────────────────────
async def cmd_futures(u, c):
    """
    /futures — scansiona tutti gli asset MKO e mostra segnali validi (score ≥ 5).
    /futures BTC — analizza solo Bitcoin.
    /futures scan — full scan, mostra anche i segnali sotto STRONG.
    Ogni segnale arriva in anteprima con ✅ Pubblica / ❌ Scarta.
    """
    if not await check_auth(u): return

    args = c.args or []
    single_sym = None
    force_scan = False

    if args:
        arg = args[0].upper()
        if arg == "SCAN":
            force_scan = True
        else:
            # Match parziale: BTC → BTCUSDT, GOLD → GOLD, ecc.
            for k in MKO_ASSETS:
                if k.startswith(arg) or k == arg:
                    single_sym = k
                    break
            if not single_sym:
                await u.message.reply_text(
                    f"❌ Asset non trovato: <code>{arg}</code>\n\n"
                    f"<b>Crypto:</b> BTC ETH SOL BNB XRP ADA AVAX DOGE DOT LINK\n"
                    f"<b>Commodities:</b> GOLD SILVER OIL BRENT NGAS COPPER WHEAT CORN PLATINUM\n"
                    f"<b>FX Majors:</b> EURUSD GBPUSD USDJPY AUDUSD USDCHF USDCAD NZDUSD\n"
                    f"<b>FX Crosses:</b> EURJPY GBPJPY AUDJPY CADJPY EURGBP EURAUD EURCAD\n"
                    f"<b>Indices:</b> SPY QQQ DAX FTSE NKY\n"
                    f"<b>Stocks:</b> NVDA AAPL MSFT META TSLA AMZN GOOGL\n\n"
                    f"<i>Uso: /futures | /futures NVDA | /futures scan</i>",
                    parse_mode="HTML"
                )
                return

    # Single asset
    if single_sym:
        asset = MKO_ASSETS[single_sym]
        m = await u.message.reply_text(
            f"🔍 Analyzing {asset['name']} (Ichimoku + VWAP + OB + OI)..."
        )
        try:
            result = mko_analyze(single_sym)
            if not result:
                await m.edit_text(
                    f"⏳ <b>{asset['name']}</b> — No valid setup.\n"
                    f"<i>Score below threshold or R:R insufficient. Market in consolidation.</i>",
                    parse_mode="HTML"
                )
            else:
                await m.edit_text(
                    f"👁 {asset['name']} — {result['direction']}, score {result['score']}/10. Anteprima qui sotto:"
                )
                await _mko_send_preview(u, c, result)
        except Exception as e:
            logger.error(f"futures single {single_sym}: {e}", exc_info=True)
            await m.edit_text(f"❌ Error: {str(e)[:120]}")
        return

    # Full scan
    m = await u.message.reply_text(
        f"🔍 MKO Full Scan — {len(MKO_ASSETS)} assets (1H timeframe)...\n"
        f"<i>Layers: Ichimoku · VWAP · EMA · RSI · MACD · OB · OI · Volume</i>",
        parse_mode="HTML"
    )
    results = []
    for sym in MKO_ASSETS:
        try:
            res = mko_analyze(sym)
            if res:
                results.append(res)
        except Exception as e:
            logger.warning(f"futures scan {sym}: {e}")

    if not results:
        await m.edit_text(
            "⏳ <b>No valid setups found</b>\n"
            "<i>All assets below score threshold. Markets in consolidation — no high-probability entries available.</i>",
            parse_mode="HTML"
        )
        return

    # Sort by score desc
    results.sort(key=lambda x: x["score"], reverse=True)

    # Summary message first
    lines = []
    for r in results:
        arrow = "▲" if r["direction"] == "BUY" else "▼"
        score_bar = "█" * r["score"] + "░" * (10 - r["score"])
        lines.append(
            f"{r['asset']['emoji']} <b>{r['asset']['name']}</b>  {arrow} {r['direction']}  "
            f"[{score_bar}] {r['score']}/10"
        )

    summary = (
        f"📊 <b>XENOS MKO SCAN — {len(results)} setup{'s' if len(results)>1 else ''}</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        + "\n".join(lines) +
        f"\n<code>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        f"<i>Anteprime qui sotto — scegli cosa pubblicare.</i>"
    )
    await m.edit_text(summary, parse_mode="HTML")

    # Preview each signal (nothing goes to the channel without ✅)
    for r in results:
        if force_scan or r["score"] >= MKO_SCORE_VALID:
            try:
                await _mko_send_preview(u, c, r)
            except Exception as e_prev:
                logger.warning(f"MKO preview {r['asset']['name']}: {e_prev}")
            await asyncio.sleep(1)


# ══════════════════════════════════════════════════════════════════════════════
# END MKO ENGINE
# ══════════════════════════════════════════════════════════════════════════════
# ── Blog image generator (replica di generateArticleImage del browser) ────────
def _generate_blog_image(title: str, category: str, market: str) -> bytes | None:
    """Genera un'immagine 1200x630 per gli articoli del blog, stile XenosFinance."""
    if not CHARTS_AVAILABLE:
        return None
    try:
        import io, textwrap
        _base_style()
        W, H = 12.0, 6.3  # inches @ 100dpi = 1200x630px

        themes = {
            "forex":       {"bg": "#050d1a", "a": "#3b82f6", "a2": "#60a5fa", "label": "FOREX",        "icon": "₣"},
            "commodities": {"bg": "#120a00", "a": "#f59e0b", "a2": "#fbbf24", "label": "COMMODITIES",  "icon": "◈"},
            "equity":      {"bg": "#001a0e", "a": "#10b981", "a2": "#34d399", "label": "EQUITY",       "icon": "▲"},
            "crypto":      {"bg": "#0d0520", "a": "#8b5cf6", "a2": "#a78bfa", "label": "CRYPTO",       "icon": "₿"},
            "macro":       {"bg": "#1a0505", "a": "#ef4444", "a2": "#f87171", "label": "MACRO",        "icon": "◉"},
            "multi":       {"bg": "#050d1a", "a": "#3b82f6", "a2": "#60a5fa", "label": "GLOBAL",       "icon": "◈"},
        }
        mk  = (market or "multi").lower()
        th  = themes.get(mk, themes["multi"])
        cat = (category or th["label"]).upper()

        fig = plt.figure(figsize=(W, H), facecolor=th["bg"])
        ax  = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, 1200); ax.set_ylim(0, 630)
        ax.set_facecolor(th["bg"])
        ax.axis("off")

        # ── Grid lines ──
        from matplotlib.patches import Rectangle
        import numpy as np
        for y in range(0, 631, 60):
            ax.plot([0, 1200], [y, y], color=th["a"]+"28", linewidth=0.5, alpha=0.3)
        for x in range(0, 1201, 80):
            ax.plot([x, x], [0, 630], color=th["a"]+"28", linewidth=0.5, alpha=0.3)

        # ── Market decoration (right side) ──
        cx, cy = 820, 315
        if mk == "commodities":
            bars = [(.3,.7,.85,.15),(.65,.4,.75,.3),(.35,.8,.9,.1),(.75,.55,.88,.45),
                    (.5,.85,.95,.4),(.8,.6,.9,.5),(.55,.9,1.,.45),(.85,.7,.95,.6)]
            bw, gap, bh = 44, 16, 260
            for i, (o, c2, h2, l2) in enumerate(bars):
                x0 = cx - 180 + i*(bw+gap)
                up = c2 > o
                col = "#10b981" if up else "#ef4444"
                ax.plot([x0+bw/2, x0+bw/2], [cy-130+l2*260, cy-130+h2*260], color=col, lw=2, alpha=0.4)
                y0 = cy - 130 + min(o, c2)*260
                ax.add_patch(Rectangle((x0, y0), bw, max(abs(c2-o)*260, 4),
                                       color=col, alpha=0.35))
        elif mk in ("equity", "macro", "forex", "multi"):
            pts = [0.5,0.58,0.52,0.65,0.55,0.70,0.62,0.75,0.68,0.80,0.72,0.78,0.74]
            xs  = [cx - 220 + i/(len(pts)-1)*480 for i in range(len(pts))]
            ys  = [cy - 110 + p*220 for p in pts]
            ax.plot(xs, ys, color=th["a"], linewidth=3, alpha=0.5)
            ax.fill_between(xs, [cy-110]*len(xs), ys, color=th["a"], alpha=0.08)
        elif mk == "crypto":
            for i in range(7):
                angle = i/6 * 2*3.14159
                rx = cx + np.cos(angle)*130; ry = cy + np.sin(angle)*130
                angles2 = [j/6*2*3.14159 for j in range(7)]
                hx = [rx + np.cos(a)*40 for a in angles2]
                hy = [ry + np.sin(a)*40 for a in angles2]
                ax.plot(hx+[hx[0]], hy+[hy[0]], color=th["a2"], lw=1.5, alpha=0.2)

        # ── Left accent strip ──
        ax.add_patch(Rectangle((0, 0), 6, 630, color=th["a"], alpha=1.0))

        # ── Category label ──
        ax.text(44, 574, f"// {cat}", color=th["a2"], fontsize=13,
                fontfamily="monospace", fontweight="bold", va="top")
        ax.plot([44, 440], [560, 560], color=th["a"], linewidth=2, alpha=0.7)

        # ── Title (word-wrap) ──
        short = title[:108] + "…" if len(title) > 110 else title
        wrapped = textwrap.fill(short, width=38)
        lines_t = wrapped.split("\n")[:3]
        fs = 42 if len(lines_t) == 1 else 34 if len(lines_t) == 2 else 28
        for i, line in enumerate(lines_t):
            ax.text(44, 500 - i*(fs*1.35), line, color="#ffffff",
                    fontsize=fs, fontweight="bold", va="top")

        # ── Ghost watermark icon ──
        ax.text(1160, 120, th["icon"], color=th["a"], fontsize=220,
                fontweight="bold", ha="right", va="bottom", alpha=0.04)

        # ── Bottom branding bar ──
        ax.add_patch(Rectangle((0, 0), 1200, 48, color="#080e1a", alpha=0.95))
        ax.text(44,  24, "XENOS",       color=th["a"],   fontsize=14, fontfamily="monospace", fontweight="bold", va="center")
        ax.text(105, 24, "FINANCE",     color="#c8d8ea", fontsize=14, fontfamily="monospace", fontweight="bold", va="center")
        ax.text(210, 24, "· AI MARKET INTELLIGENCE", color="#3a5575", fontsize=11, fontfamily="monospace", va="center")
        from datetime import datetime as _dt
        ax.text(1160, 24, _dt.utcnow().strftime("%d %b %Y").upper(),
                color="#2a4060", fontsize=11, fontfamily="monospace", ha="right", va="center")

        buf = io.BytesIO()
        plt.savefig(buf, format="jpeg", dpi=100, bbox_inches="tight",
                    facecolor=th["bg"], edgecolor="none", pil_kwargs={"quality": 93})
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        logger.warning(f"_generate_blog_image: {e}")
        try: plt.close("all")
        except: pass
        return None


# ── Blog publish: tutti i brief ───────────────────────────────────────────────
BLOG_ARTICLES_FILE = "articles/index.json"

def _publish_brief_to_blog(text: str, label: str, now_str: str) -> bool:
    """Pubblica qualsiasi brief del bot come articolo su XenosBlog con immagine."""
    if not GITHUB_TOKEN:
        logger.warning("_publish_brief_to_blog: GITHUB_TOKEN mancante")
        return False
    try:
        import uuid as _uuid, re as _re, math as _math, base64 as _b64, json as _json

        slug     = f"brief-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{_uuid.uuid4().hex[:6]}"
        now_iso  = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        date_lbl = datetime.utcnow().strftime("%d %b %Y")

        # Categoria basata sul label
        cat_map = {
            "FX":         ("FX Markets · AI Analysis",        "forex"),
            "Forex":      ("FX Markets · AI Analysis",        "forex"),
            "Crypto":     ("Crypto Markets · AI Analysis",    "crypto"),
            "Commodities":("Commodities · AI Analysis",       "commodities"),
            "Equity":     ("Global Equities · AI Analysis",   "equity"),
            "Pre-Market": ("US Pre-Market · AI Analysis",     "equity"),
            "Wrap":       ("Market Wrap · AI Analysis",       "macro"),
            "Global":     ("Market Outlook · AI Macro",       "macro"),
            "Brief":      ("Market Outlook · AI Macro",       "macro"),
        }
        cat_label, cat_market = "Market Brief · AI Analysis", "macro"
        for key, (cl, cm) in cat_map.items():
            if key.lower() in label.lower():
                cat_label, cat_market = cl, cm
                break

        # Pulisci il testo da tag HTML Telegram e separatori
        clean = _re.sub(r"<[^>]+>", "", text)
        clean = _re.sub("━+|─+", "", clean).strip()
        lines = clean.splitlines()

        # Cerca sezioni basandosi su righe con emoji tipiche
        section_emoji = ["📊","💱","💰","📈","🛢","₿","🎯","📅","🌅","🏦","⚠️","🔭","🌆","🌍","⚡","🌏"]
        sections, current_heading, current_lines = [], None, []
        for line in lines:
            line = line.strip()
            if not line: continue
            is_sec = any(line.startswith(e) for e in section_emoji) and len(line) < 100
            if is_sec:
                if current_heading and current_lines:
                    sections.append({"heading": current_heading,
                                     "content": "\n".join(current_lines).strip()})
                current_heading = line; current_lines = []
            else:
                current_lines.append(line)
        if current_heading and current_lines:
            sections.append({"heading": current_heading,
                             "content": "\n".join(current_lines).strip()})

        if not sections:
            chunk = max(1, len(clean)//3)
            sections = [
                {"heading": "Overview",  "content": clean[:chunk].strip()},
                {"heading": "Analysis",  "content": clean[chunk:chunk*2].strip()},
                {"heading": "Outlook",   "content": clean[chunk*2:].strip()},
            ]

        intro      = sections[0]["content"] if sections else clean[:800]
        word_count = len(clean.split())
        read_time  = f"{max(2, _math.ceil(word_count/200))} min read"
        sentences  = [s.strip() for s in _re.split(r"[.!?]", clean) if len(s.strip()) > 40]
        quote      = sentences[0][:200] if sentences else label
        _excerpt_src = (sections[0]["content"] if sections else clean)[:400]
        excerpt    = _excerpt_src[:120].strip() + "..."
        title_art  = f"{label} — {date_lbl}"

        # ── Genera immagine ──
        image_url = None
        try:
            img_bytes = _generate_blog_image(title_art, cat_label, cat_market)
            if img_bytes:
                api_base2 = f"https://api.github.com/repos/{GITHUB_REPO}/contents"
                hdrs2 = {"Authorization": f"token {GITHUB_TOKEN}",
                         "Accept": "application/vnd.github.v3+json"}
                img_path = f"articles/{slug}-img.jpg"
                img_b64  = _b64.b64encode(img_bytes).decode()
                ri = requests.put(f"{api_base2}/{img_path}", headers=hdrs2,
                                  json={"message": f"Image: {title_art}",
                                        "content": img_b64, "branch": "main"}, timeout=20)
                if ri.status_code in (200, 201):
                    image_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/{img_path}"
                    logger.info(f"✅ Blog image uploaded: {image_url}")
        except Exception as e_img:
            logger.warning(f"blog image gen failed: {e_img}")

        article = {
            "slug": slug, "title": title_art,
            "intro": intro, "sections": sections,
            "quote": quote,
            "conclusion": sections[-1]["content"] if sections else "",
            "excerpt": excerpt,
            "categoryLabel": cat_label,
            "market": cat_market, "tech": "ai", "lang": "EN",
            "readTime": read_time, "publishedAt": now_iso,
            "imageUrl": image_url, "source": "bot_brief",
        }

        api_base = f"https://api.github.com/repos/{GITHUB_REPO}/contents"
        hdrs = {"Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"}

        art_b64 = _b64.b64encode(_json.dumps(article, ensure_ascii=False, indent=2).encode()).decode()
        r1 = requests.put(f"{api_base}/articles/{slug}.json", headers=hdrs,
                          json={"message": f"Blog: {title_art}",
                                "content": art_b64, "branch": "main"}, timeout=15)
        if r1.status_code not in (200, 201):
            logger.error(f"_publish_brief_to_blog article: {r1.status_code}")
            return False

        idx_url = f"{api_base}/articles/index.json"
        r2 = requests.get(idx_url, headers=hdrs, timeout=10)
        idx_sha, existing = None, []
        if r2.status_code == 200:
            idx_sha  = r2.json().get("sha")
            existing = _json.loads(_b64.b64decode(r2.json()["content"]).decode())

        entry = {"slug": slug, "title": title_art, "excerpt": excerpt,
                 "category": cat_label, "market": cat_market,
                 "tech": "ai", "lang": "EN", "readTime": read_time,
                 "publishedAt": now_iso, "imageUrl": image_url}
        existing.insert(0, entry)
        idx_b64 = _b64.b64encode(_json.dumps(existing, ensure_ascii=False, indent=2).encode()).decode()
        idx_payload = {"message": f"Index: {title_art}", "content": idx_b64, "branch": "main"}
        if idx_sha: idx_payload["sha"] = idx_sha
        r3 = requests.put(idx_url, headers=hdrs, json=idx_payload, timeout=15)
        if r3.status_code not in (200, 201):
            logger.error(f"_publish_brief_to_blog index: {r3.status_code}")
            return False

        logger.info(f"✅ Brief pubblicato su blog: {slug} ({label})")
        return True
    except Exception as e:
        logger.error(f"_publish_brief_to_blog: {e}", exc_info=True)
        return False


async def _cb_publish_brief(update, context):
    """Callback unificato per tutti i pulsanti 'Pubblica su Blog'."""
    query = update.callback_query
    await query.answer("📝 Pubblicazione in corso...")
    data = query.data
    logger.info(f"_cb_publish_brief: {data}")
    if not data.startswith("pub_brief:"):
        return
    cache_key = data.split(":", 1)[1]
    cached    = context.bot_data.get(cache_key)
    if not cached:
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("⚠️ Dati scaduti — genera di nuovo il brief.")
        return
    await query.edit_message_reply_markup(reply_markup=None)
    msg = await query.message.reply_text("📝 Pubblicazione su XenosBlog (con immagine)...")
    ok  = _publish_brief_to_blog(
        cached.get("text", ""),
        cached.get("label", "Market Brief"),
        cached.get("now_str", "")
    )
    await msg.edit_text(
        "✅ Pubblicato su XenosBlog!\n🌐 xenosfinance.com/XenosBlog" if ok
        else "❌ Errore pubblicazione — controlla i log Railway."
    )
    context.bot_data.pop(cache_key, None)


# ═══════════════════════════════════════════════════════════════════════════════
# DAILY EDUCATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

_ED_TOPICS = {
    "technical": [
        "Support & Resistance", "Trend Lines", "Breakout & Fake Breakout",
        "Pivot Points", "Volume Analysis", "Momentum", "Candlestick Patterns",
        "RSI Divergences", "MACD Crossovers", "Moving Averages",
        "Market Structure", "Consolidation & Range", "Pullback in Trend",
        "Volatility Expansion", "Swing Trading Setup", "Scalping Techniques",
        "Trend Following", "Mean Reversion", "Order Blocks", "Fair Value Gaps",
        "Bollinger Bands", "Fibonacci Retracements", "Elliott Wave Basics",
        "Chart Patterns (H&S, Triangles)", "Gap Trading", "ATR & Volatility Sizing",
        "Multi-Timeframe Analysis", "Session Highs & Lows", "VWAP Trading",
        "Ichimoku Cloud Basics"
    ],
    "fundamental": [
        "Inflation & CPI", "Interest Rates & Fed", "NFP Report",
        "GDP & Recession", "Soft vs Hard Landing", "Oil & Geopolitics",
        "Gold as Safe Haven", "DXY Dollar Index", "Bond Yields",
        "Earnings Season", "Central Bank Policies", "Liquidity Cycles",
        "ECB Policy", "Global Macro Cycle", "PMI & Manufacturing Data",
        "Trade Balance & Tariffs", "Currency Intervention", "Commodity Supercycles",
        "Crypto Regulation & ETFs", "Sector Rotation", "Yield Curve Signals",
        "Housing Market Data", "Retail Sales Impact", "OPEC+ Decisions"
    ],
    "psychology": [
        "Fear & Greed", "Revenge Trading", "FOMO", "Patience & Discipline",
        "Emotional Control", "Trading Routine", "Consistency", "Loss Management",
        "Overconfidence", "Trading Journal", "Analysis Paralysis",
        "Confirmation Bias", "Sunk Cost Fallacy", "Trading Burnout",
        "Building a Trading Edge", "Dealing with Drawdowns"
    ],
    "risk": [
        "Capital Preservation", "Risk Per Trade", "Portfolio Exposure",
        "Stop Loss Discipline", "Max Drawdown", "Money Management",
        "Correlation Risk", "Diversification", "Position Sizing Models",
        "Risk-Reward Ratios", "Black Swan Events", "Hedging Strategies",
        "Scaling In & Out", "News Event Risk"
    ],
    "leverage": [
        "Leverage Basics", "Margin Call", "Free vs Used Margin",
        "Liquidation Risk", "Position Sizing", "Overexposure",
        "CFD vs Futures Margin", "Funding Costs", "Cross vs Isolated Margin",
        "Leverage in Crypto Perpetuals", "Margin Requirements by Broker"
    ],
    "terminology": [
        "Bull & Bear Market", "Liquidity & Spread", "Slippage", "Hedging",
        "Options & Futures", "ETF Mechanics", "Market Maker", "Institutional Flow",
        "Long/Short Squeeze", "Open Interest", "Contango & Backwardation",
        "Yield Curve", "Risk-on / Risk-off", "Order Types Explained",
        "Bid-Ask Spread Mechanics", "Dark Pool Trading", "Circuit Breakers",
        "Rollover & Swap Rates"
    ],
    "advanced": [
        "COT Report", "Gamma Exposure", "Options Flow", "Liquidity Grabs",
        "Smart Money Concepts", "Intermarket Analysis", "Yield Curve Inversion",
        "Dollar Liquidity", "Central Bank Balance Sheets", "Dark Pools",
        "Delta-Neutral Strategies", "Volatility Skew", "Order Flow Analysis",
        "Market Maker Hedging", "Basis Trading", "Carry Trade Mechanics"
    ]
}

# Rotating sector focus so real market examples cover every instrument
# class over time, not just whatever the AI defaults to.
_ED_SECTORS = [
    "Forex (majors & crosses)", "Cryptocurrency", "Commodities (Gold, Oil, Silver, Nat Gas)",
    "Equities / Single Stocks", "Stock Indices (S&P 500, Nasdaq, DAX...)",
    "Bonds & Interest Rates", "Options & Derivatives"
]

_ED_SYSTEM = (
    "You are a professional educational trading assistant for a premium financial Telegram channel.\n"
    "Generate DAILY EDUCATIONAL CONTENT for traders (beginners and intermediate level).\n\n"
    "STYLE RULES:\n"
    "- Professional desk analyst tone\n"
    "- Clear, direct, engaging language\n"
    "- Short sentences, readable on mobile\n"
    "- No excessive disclaimers, no hype\n"
    "- Use bullet points with dashes\n"
    "- NO asterisks, NO markdown, NO special formatting characters\n"
    "- Plain readable text only — every character must display as-is\n\n"
    "OUTPUT STRUCTURE — use this exact layout:\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "📚 DAILY MARKET EDUCATION\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "[SECTION 1]\n[SECTION 2]\n[SECTION 3 - 3 Daily Tips]\n[SECTION 4 - Risk reminder]\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "Educational purpose only\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "Each section: catchy title with emoji, clear explanation, real market example, practical tips, "
    "PRO TIP or SMART MONEY RULE at the end.\n"
    "Target length: 400-600 words total. Be concise and direct.\n"
    "CRITICAL: NEVER use *asterisks* or _underscores_ or any markdown syntax. Plain text only."
)

_ED_MAIN_CATS = ["technical", "fundamental", "psychology", "leverage", "terminology", "advanced"]


def _ed_get_topics(date):
    """Returns topics for the given date, rotating through the FULL topic
    pool with no gaps.

    IMPORTANT: topic selection must advance by 1 each time a category
    recurs — NOT by the raw day-of-year. Stepping by the same amount as
    the category-cycle length (previously 6, matching len(_ED_MAIN_CATS))
    only reaches gcd(6, len(topics)) of the topics whenever that length
    shares a common factor with 6 (true for every even-length list) —
    silently skipping half the curated topics forever. Using the
    occurrence count instead guarantees every topic in every category is
    eventually used, and using a deterministic per-category offset
    (instead of Python's hash(), which is randomized per process run)
    keeps the rotation stable across bot restarts/redeploys.
    """
    day       = date.timetuple().tm_yday
    n_cats    = len(_ED_MAIN_CATS)
    pri_cat   = _ED_MAIN_CATS[day % n_cats]
    sec_cat   = _ED_MAIN_CATS[(day + 1) % n_cats]

    pri_occurrence = day // n_cats
    sec_occurrence = (day + 1) // n_cats
    pri_offset = sum(ord(c) for c in pri_cat)
    sec_offset = sum(ord(c) for c in sec_cat)

    pri_top   = _ED_TOPICS[pri_cat][(pri_occurrence + pri_offset) % len(_ED_TOPICS[pri_cat])]
    sec_top   = _ED_TOPICS[sec_cat][(sec_occurrence + sec_offset) % len(_ED_TOPICS[sec_cat])]
    risk_top  = _ED_TOPICS["risk"][day % len(_ED_TOPICS["risk"])]
    sector    = _ED_SECTORS[day % len(_ED_SECTORS)]
    return pri_cat, pri_top, sec_cat, sec_top, risk_top, sector


def _generate_daily_education(date=None):
    """Calls Claude API and returns the daily education text."""
    if date is None:
        date = datetime.now().date()
    pri_cat, pri_top, sec_cat, sec_top, risk_top, sector = _ed_get_topics(date)
    user_msg = (
        f"Generate today's DAILY EDUCATIONAL CONTENT for {date.strftime('%A %d %B %Y')}.\n\n"
        f"SECTION 1 — {pri_cat.upper()}: Topic = \"{pri_top}\"\n"
        f"SECTION 2 — {sec_cat.upper()}: Topic = \"{sec_top}\"\n"
        f"SECTION 3 — DAILY TRADING TIPS: 3 practical tips relevant to current market conditions\n"
        f"SECTION 4 — RISK MANAGEMENT: Topic = \"{risk_top}\"\n\n"
        f"TODAY'S SECTOR FOCUS: {sector}\n"
        f"Every real market example across all sections should be drawn from this sector "
        f"specifically (not forex by default) unless a section's topic is inherently about "
        f"another asset class — vary the instruments you reference (e.g. specific pairs, "
        f"coins, tickers, or contracts within {sector}) rather than reusing the same one.\n\n"
        f"Make it engaging and professional. Include real market examples where possible.\n"
        f"Keep formatting clean for Telegram — plain dashes for bullets."
    )
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-sonnet-4-5",
            "max_tokens": 2000,
            "system": _ED_SYSTEM,
            "messages": [{"role": "user", "content": user_msg}]
        },
        timeout=60
    )
    res = r.json()
    if "content" in res and res["content"]:
        return res["content"][0]["text"]
    raise RuntimeError(f"Education API error: {res}")


def _ed_save_to_github(content, date):
    """Saves post to GitHub daily_education/YYYY-MM-DD.json and updates index."""
    if not GITHUB_TOKEN:
        logger.warning("[Education] No GITHUB_TOKEN — skipping GitHub save")
        return False
    date_str = date.strftime("%Y-%m-%d")
    api_base = f"https://api.github.com/repos/{GITHUB_REPO}/contents"
    hdrs     = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

    # 1. Save post file
    payload   = {
        "date": date_str,
        "day_name": date.strftime("%A"),
        "content": content,
        "generated_at": datetime.utcnow().isoformat() + "Z"
    }
    post_b64  = base64.b64encode(json.dumps(payload, ensure_ascii=False, indent=2).encode()).decode()
    file_path = f"daily_education/{date_str}.json"
    file_url  = f"{api_base}/{file_path}"

    existing_sha = None
    r_check = requests.get(file_url, headers=hdrs, timeout=10)
    if r_check.status_code == 200:
        existing_sha = r_check.json().get("sha")

    put_body = {"message": f"Daily education {date_str}", "content": post_b64, "branch": "main"}
    if existing_sha:
        put_body["sha"] = existing_sha
    r1 = requests.put(file_url, headers=hdrs, json=put_body, timeout=15)
    if r1.status_code not in (200, 201):
        logger.error(f"[Education] save error {r1.status_code}: {r1.text[:200]}")
        return False

    # 2. Update index
    idx_url = f"{api_base}/daily_education/index.json"
    r_idx   = requests.get(idx_url, headers=hdrs, timeout=10)
    idx_sha, index_data = None, {"posts": []}
    if r_idx.status_code == 200:
        idx_sha    = r_idx.json().get("sha")
        index_data = json.loads(base64.b64decode(r_idx.json()["content"]).decode())

    existing_dates = {p["date"] for p in index_data.get("posts", [])}
    if date_str not in existing_dates:
        index_data.setdefault("posts", []).insert(0, {
            "date": date_str,
            "day_name": date.strftime("%A"),
            "file": file_path
        })
        index_data["posts"] = index_data["posts"][:90]

    idx_b64  = base64.b64encode(json.dumps(index_data, ensure_ascii=False, indent=2).encode()).decode()
    idx_body = {"message": f"Education index {date_str}", "content": idx_b64, "branch": "main"}
    if idx_sha:
        idx_body["sha"] = idx_sha
    r2 = requests.put(idx_url, headers=hdrs, json=idx_body, timeout=15)
    if r2.status_code not in (200, 201):
        logger.error(f"[Education] index error {r2.status_code}")
        return False

    logger.info(f"[Education] Saved {date_str} to GitHub OK")
    return True


async def cmd_daily_education(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/daily_education — manual trigger, owner only."""
    if update.effective_user.id != OWNER_ID:
        return
    await update.message.reply_text("⏳ Generating daily education content...")
    try:
        today   = datetime.now().date()
        content = _generate_daily_education(today)
        for part in split_message(content, 4000):
            await context.bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=part)
        ok = _ed_save_to_github(content, today)
        await update.message.reply_text(
            "✅ Daily education posted to channel and saved to GitHub!" if ok
            else "✅ Posted to channel. GitHub save failed — check logs."
        )
    except Exception as e:
        logger.error(f"cmd_daily_education: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Error: {e}")


async def _scheduled_daily_education(context: ContextTypes.DEFAULT_TYPE):
    """JobQueue — runs daily at 09:00 CET (08:00 UTC)."""
    logger.info("[Education] Running scheduled daily education job...")
    try:
        today   = datetime.now().date()
        content = _generate_daily_education(today)
        for part in split_message(content, 4000):
            await context.bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=part)
        ok = _ed_save_to_github(content, today)
        logger.info(f"[Education] Done for {today}. GitHub: {'OK' if ok else 'FAILED'}")
    except Exception as e:
        logger.error(f"[Education] Scheduled job error: {e}", exc_info=True)



# ── WEEKLY TRADING PLAN ───────────────────────────────────────────────────────

def _fetch_live_price(symbol: str) -> str:
    """Fetcha il prezzo live da Yahoo Finance per il weekly plan."""
    try:
        yf_sym = MARKETS.get(symbol, {}).get("yf")
        if not yf_sym:
            return "N/A"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_sym}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"},
                         params={"range": "1d", "interval": "1m"}, timeout=10)
        d = r.json()
        meta = d["chart"]["result"][0]["meta"]
        price = float(meta.get("regularMarketPrice") or meta.get("previousClose") or 0)
        if price <= 0:
            return "N/A"
        # Formatta decimali per asset
        if symbol in ("EURUSD", "EURGBP"):
            return f"{price:.4f}"
        elif symbol in ("OIL", "NGAS"):
            return f"{price:.2f}"
        elif symbol == "BTCUSD":
            return f"{price:,.0f}"
        elif symbol == "GOLD":
            return f"{price:.1f}"
        else:
            return f"{price:.2f}"
    except Exception as e:
        logger.warning(f"_fetch_live_price {symbol}: {e}")
        return "N/A"

def _strip_markdown(text: str) -> str:
    """Rimuove asterischi e altri marcatori markdown dal testo."""
    import re
    text = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,2}(.*?)_{1,2}", r"\1", text)
    text = re.sub(r"`{1,3}(.*?)`{1,3}", r"\1", text)
    text = re.sub(r"^#{1,4}\s*", "", text, flags=re.MULTILINE)
    return text.strip()



# ═══════════════════════════════════════════════════════════════════════════════
# CARD PAYMENT REQUESTS (Premium) — ADDED 2026-09-23
# The card payment link is never published on the website. Visitors tap
# "Pay by card" → open this bot with ?start=paycard → the owner gets the
# request with ✅/❌ buttons → on ✅ the bot sends that user the link,
# read from the CARD_PAY_LINK env var on Railway (not in code, not on GitHub).
# Any later message from that user (e.g. the payment receipt) is relayed to
# the owner; the owner answers by REPLYING to the relayed message.
# ═══════════════════════════════════════════════════════════════════════════════

def _user_label(user) -> str:
    name = " ".join(x for x in [user.first_name, user.last_name] if x) or "Unknown"
    handle = f"@{user.username}" if user.username else "no username"
    return f"{name} ({handle} · id {user.id})"


async def _paycard_request(u, c):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    user = u.effective_user
    await u.message.reply_text(
        "💳 <b>XenosFinance Premium — card payment</b>\n\n"
        "Thanks, your request has been received. You'll get your secure "
        "payment link here in this chat shortly.\n\n"
        "<b>Plans:</b> Monthly 9 USD · Yearly 99 USD\n\n"
        "<i>Questions? Just write here.</i>",
        parse_mode="HTML",
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Send payment link", callback_data=f"paycard_send:{user.id}"),
        InlineKeyboardButton("❌ Decline", callback_data=f"paycard_no:{user.id}"),
    ]])
    await c.bot.send_message(
        OWNER_ID,
        f"💳 Card payment request\n{_user_label(user)}",
        reply_markup=kb,
    )


async def _support_request(u, c):
    """Contributo libero dal pulsante ☕ Support del sito: stesso link carta (CARD_PAY_LINK), importo a scelta."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    user = u.effective_user
    await u.message.reply_text(
        "☕ <b>Support XenosFinance</b>\n\n"
        "Thank you! XenosFinance is independent — no sponsors, no brokers, no ads. "
        "Your contribution helps cover market data, servers and AI costs.\n\n"
        "You'll get a secure card payment link here in this chat shortly — "
        "any amount is welcome.\n\n"
        "<i>Questions? Just write here.</i>",
        parse_mode="HTML",
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Send payment link", callback_data=f"support_send:{user.id}"),
        InlineKeyboardButton("❌ Decline", callback_data=f"support_no:{user.id}"),
    ]])
    await c.bot.send_message(
        OWNER_ID,
        f"☕ Support (contribution) request\n{_user_label(user)}",
        reply_markup=kb,
    )


async def _cb_support(update, context):
    query = update.callback_query
    if query.from_user.id != OWNER_ID:
        await query.answer("🚫 Access denied", show_alert=True)
        return
    action, uid = query.data.split(":", 1)
    uid = int(uid)
    if action == "support_send":
        link = os.getenv("CARD_PAY_LINK", "").strip()
        if not link:
            await query.answer("Set CARD_PAY_LINK on Railway first", show_alert=True)
            return
        try:
            await context.bot.send_message(
                uid,
                "☕ <b>Support XenosFinance</b>\n\n"
                f"Your secure payment link:\n{link}\n\n"
                "Enter any amount you like on the payment page. Thank you for supporting "
                "independent market research!\n\n"
                "<i>This link is personal — please don't share it.</i>",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            await query.answer("Link sent")
            await query.edit_message_text(query.message.text + "\n\n✅ Link sent")
        except Exception as e:
            await query.answer(f"Send failed: {str(e)[:120]}", show_alert=True)
    else:
        try:
            await context.bot.send_message(
                uid,
                "Card contributions aren't available at the moment — thank you anyway! "
                "Reply here if you need anything.",
            )
        except Exception:
            pass
        await query.answer("Declined")
        await query.edit_message_text(query.message.text + "\n\n❌ Declined")


async def _cb_paycard(update, context):
    query = update.callback_query
    if query.from_user.id != OWNER_ID:
        await query.answer("🚫 Access denied", show_alert=True)
        return
    action, uid = query.data.split(":", 1)
    uid = int(uid)
    if action == "paycard_send":
        link = os.getenv("CARD_PAY_LINK", "").strip()
        if not link:
            await query.answer("Set CARD_PAY_LINK on Railway first", show_alert=True)
            return
        try:
            await context.bot.send_message(
                uid,
                "💳 <b>XenosFinance Premium — card payment</b>\n\n"
                f"Your secure payment link:\n{link}\n\n"
                "<b>Plans:</b> Monthly 9 USD · Yearly 99 USD — enter the amount on the payment page.\n\n"
                "After paying, send the payment receipt (a screenshot is fine) here in this chat. "
                "You'll receive your Premium access code within 24 hours.\n\n"
                "<i>This link is personal — please don't share it.</i>",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            await query.answer("Link sent")
            await query.edit_message_text(query.message.text + "\n\n✅ Link sent")
        except Exception as e:
            await query.answer(f"Send failed: {str(e)[:120]}", show_alert=True)
    else:
        try:
            await context.bot.send_message(
                uid,
                "Card payment isn't available at the moment. You can pay with USDC on Base at "
                "xenosfinance.com/premium, or reply here if you need help.",
            )
        except Exception:
            pass
        await query.answer("Declined")
        await query.edit_message_text(query.message.text + "\n\n❌ Declined")


async def _relay_user_message(u, c):
    """Non-owner private messages (receipts, questions) → forwarded to the owner."""
    user = u.effective_user
    relay = c.bot_data.setdefault("relay_map", {})
    header = await c.bot.send_message(OWNER_ID, f"📩 {_user_label(user)}\n↩️ Reply to this message to answer.")
    relay[header.message_id] = user.id
    try:
        fwd = await u.message.forward(OWNER_ID)
    except Exception:
        fwd = await c.bot.copy_message(OWNER_ID, u.effective_chat.id, u.message.message_id)
    relay[getattr(fwd, "message_id", fwd)] = user.id
    await u.message.reply_text("✅ Received — we'll get back to you here shortly.")


async def _owner_reply_relay(u, c):
    """Owner replies to a relayed message → copied to that user."""
    reply_to = u.message.reply_to_message
    uid = c.bot_data.get("relay_map", {}).get(reply_to.message_id) if reply_to else None
    if not uid:
        return  # not a reply to a relayed message — ignore
    try:
        await c.bot.copy_message(uid, u.effective_chat.id, u.message.message_id)
        await u.message.reply_text("↩️ Sent")
    except Exception as e:
        await u.message.reply_text(f"❌ Couldn't deliver: {str(e)[:120]}")


# ═══════════════════════════════════════════════════════════════════════════════
# EIA WEEKLY PETROLEUM REPORT — post automatico sul canale (2026-10)
# Dati ufficiali U.S. EIA via Worker (type:'eia_wpsr'): variazioni settimanali di
# crude, benzina, distillati, Cushing, SPR; produzione, raffinerie, import/export;
# confronto con la media a 5 anni della stessa settimana + forecast ForexFactory.
# Il job controlla ogni 10 minuti il mercoledì e il giovedì (festività USA)
# 14:00–20:00 UTC e posta appena esce una settimana nuova. Lo stato (ultima
# settimana pubblicata) è salvato su GitHub → niente doppioni dopo un riavvio.
# /eia = pubblica subito il report corrente (manuale).
# ═══════════════════════════════════════════════════════════════════════════════
EIA_WORKER_URL = "https://xenos-ai-proxy.xenosfinance.workers.dev"
EIA_STATE_FILE = "data/eia_wpsr_last.json"


def eia_fetch_report():
    r = requests.post(EIA_WORKER_URL, json={"type": "eia_wpsr"}, timeout=45)
    d = r.json()
    if d.get("error"):
        raise RuntimeError(d["error"])
    if not d.get("stats", {}).get("crude"):
        raise RuntimeError("EIA report: crude data missing")
    return d


def _eia_parse_m(v):
    """'-1.6M' / '850K' → milioni di barili (float) o None."""
    try:
        t = str(v or "").strip().upper().replace(",", "")
        if not t or t in ("—", "-"):
            return None
        mult = 1.0
        if t.endswith("M"):
            t = t[:-1]
        elif t.endswith("K"):
            t, mult = t[:-1], 0.001
        elif t.endswith("B"):
            t, mult = t[:-1], 1000.0
        return float(t) * mult
    except Exception:
        return None


def eia_fetch_forecast():
    """Forecast ForexFactory della settimana (solo crude, l'unico con consenso affidabile)."""
    try:
        r = requests.post(EIA_WORKER_URL, json={"type": "forexfactory", "week": "thisweek"}, timeout=20)
        for ev in r.json().get("events", []):
            title = str(ev.get("event", "")).lower()
            if ev.get("country") == "USD" and "crude oil inventories" in title and "cushing" not in title:
                return _eia_parse_m(ev.get("estimate"))
    except Exception as e:
        logger.warning(f"EIA forecast: {e}")
    return None


def _eia_m(x, plus=True):
    """migliaia di barili → stringa in milioni (es. -3.2M)."""
    v = x / 1000.0
    return (f"{v:+.1f}M" if plus else f"{v:.1f}M")


def eia_xenos_read(rep, fc):
    """
    XENOS READ — lettura del desk, deterministica (nessuna AI, nessun numero inventato).
    Crude: scorecard su 6 fattori → bias + conviction + driver.
    Prodotti e gas: variazione vs media 5 anni della stessa settimana.
    """
    st = rep["stats"]
    cr = st["crude"]
    M = lambda k: st[k]["change"] / 1000.0 if st.get(k) else None
    A = lambda k: (st[k].get("change_5y_avg") or 0) / 1000.0 if st.get(k) else None
    score, drivers = 0, []

    def add(pts, txt):
        nonlocal score
        score += pts
        drivers.append(("✅ " if pts > 0 else "❌ " if pts < 0 else "▫️ ") + txt)

    # 1) Sorpresa crude vs forecast (o vs stagionalità) — peso doppio
    chg = M("crude")
    ref = fc if fc is not None else A("crude")
    ref_name = "consensus" if fc is not None else "5y seasonal"
    sur = chg - ref
    if sur <= -2.0:
        add(2, f"Crude {chg:+.1f}M vs {ref_name} {ref:+.1f}M — big draw surprise ({sur:+.1f}M)")
    elif sur <= -0.8:
        add(1, f"Crude {chg:+.1f}M vs {ref_name} {ref:+.1f}M — tighter than expected")
    elif sur >= 2.0:
        add(-2, f"Crude {chg:+.1f}M vs {ref_name} {ref:+.1f}M — big build surprise ({sur:+.1f}M)")
    elif sur >= 0.8:
        add(-1, f"Crude {chg:+.1f}M vs {ref_name} {ref:+.1f}M — looser than expected")
    else:
        add(0, f"Crude {chg:+.1f}M in line with {ref_name} ({ref:+.1f}M)")

    # 2) Cushing (hub di consegna WTI)
    cu = M("cushing")
    if cu is not None:
        if cu <= -0.4:
            add(1, f"Cushing {cu:+.1f}M — tightening at the WTI delivery hub")
        elif cu >= 0.4:
            add(-1, f"Cushing {cu:+.1f}M — stocks building at the WTI hub")

    # 3) Livello scorte vs media 5 anni (contesto strutturale)
    v5 = cr.get("vs_5y_pct")
    if v5 is not None:
        if v5 <= -3:
            add(1, f"Crude stocks {v5:+.1f}% vs 5y average — structurally tight")
        elif v5 >= 3:
            add(-1, f"Crude stocks {v5:+.1f}% vs 5y average — structurally comfortable")

    # 4) Raffinerie: più lavorazioni = più domanda di crude
    ru = st.get("refutil")
    if ru:
        if ru["change"] >= 0.8:
            add(1, f"Refinery runs {ru['value']:.1f}% ({ru['change']:+.1f} pp) — stronger crude demand")
        elif ru["change"] <= -0.8:
            add(-1, f"Refinery runs {ru['value']:.1f}% ({ru['change']:+.1f} pp) — weaker crude demand")

    # 5) Produzione USA
    pr = st.get("production")
    if pr:
        dp = pr["change"] / 1000.0
        if dp >= 0.10:
            add(-1, f"US output {pr['value'] / 1000:.2f} mb/d ({dp:+.2f}) — supply rising")
        elif dp <= -0.10:
            add(1, f"US output {pr['value'] / 1000:.2f} mb/d ({dp:+.2f}) — supply easing")

    # 6) Complesso petrolifero totale vs stagionalità
    ks = [k for k in ("crude", "gasoline", "distillate") if st.get(k)]
    tot, tot5 = sum(M(k) for k in ks), sum(A(k) for k in ks)
    if tot - tot5 <= -2.0:
        add(1, f"Total crude + products {tot:+.1f}M vs seasonal {tot5:+.1f}M — complex-wide draw")
    elif tot - tot5 >= 2.0:
        add(-1, f"Total crude + products {tot:+.1f}M vs seasonal {tot5:+.1f}M — complex-wide build")

    def bias(sc):
        if sc >= 3:  return "🟢 <b>BULLISH</b>"
        if sc >= 1:  return "🟢 <b>MILDLY BULLISH</b>"
        if sc <= -3: return "🔴 <b>BEARISH</b>"
        if sc <= -1: return "🔴 <b>MILDLY BEARISH</b>"
        return "⚪ <b>NEUTRAL</b>"
    conv = "High" if abs(score) >= 4 else "Medium" if abs(score) >= 2 else "Low"

    # Prodotti: variazione vs stagionalità
    def prod(k, name):
        if not st.get(k):
            return None, 0
        d = M(k) - A(k)
        if d <= -1.5:
            return f"{name} 🟢 bullish ({M(k):+.1f}M vs seasonal {A(k):+.1f}M)", 1
        if d >= 1.5:
            return f"{name} 🔴 bearish ({M(k):+.1f}M vs seasonal {A(k):+.1f}M)", -1
        return f"{name} ⚪ neutral ({M(k):+.1f}M vs seasonal {A(k):+.1f}M)", 0
    g_txt, g_sc = prod("gasoline", "Gasoline (RBOB)")
    d_txt, d_sc = prod("distillate", "Distillates (ULSD)")

    out = ["", "<b>🧭 XENOS READ</b>",
           f"<b>WTI / Crude:</b> {bias(score)} · conviction {conv} (score {score:+d})"]
    out += [f"  {x}" for x in drivers]
    prods = [x for x in (g_txt, d_txt) if x]
    if prods:
        out += ["", "<b>Products:</b>"] + [f"  • {x}" for x in prods]

    ng_line = None
    ng = st.get("natgas")
    if ng and rep.get("natgas_week_ending") == rep["week_ending"] and ng.get("change_5y_avg") is not None:
        dg = ng["change"] - ng["change_5y_avg"]
        tag = "🟢 bullish" if dg <= -10 else "🔴 bearish" if dg >= 10 else "⚪ neutral"
        ng_line = (f"<b>Natural gas:</b> {tag} — storage {ng['change']:+.0f} Bcf vs 5y avg "
                   f"{ng['change_5y_avg']:+.0f} Bcf ({dg:+.0f} Bcf)")
        out += ["", ng_line]

    # Takeaway da desk
    psc = g_sc + d_sc
    if score >= 1 and psc >= 1:
        tk = "Tightness across crude and products — supportive for WTI/Brent; dips likely bought while the draw trend holds."
    elif score <= -1 and psc <= -1:
        tk = "Builds across crude and products — headwind for WTI/Brent; rallies vulnerable until balances tighten."
    elif score <= 0 and psc >= 1:
        tk = "Product-led tightness with soft crude balances — supportive for refining margins (crack spreads) more than for flat-price crude."
    elif score >= 1 and psc <= -1:
        tk = "Crude tightening but products building — refiners may cut runs; upside in crude needs product demand to confirm."
    elif score >= 1:
        tk = "Crude balances tightening — mild support for WTI; watch Cushing and refinery runs next week."
    elif score <= -1:
        tk = "Crude balances loosening — mild pressure on WTI; watch exports and runs for a reversal."
    else:
        tk = "Balanced report — no clear inventory signal; price action likely driven by macro and OPEC+ headlines."
    out += ["", f"<b>Takeaway:</b> {tk}"]
    return out


def eia_build_message(rep, fc):
    st = rep["stats"]
    we = datetime.strptime(rep["week_ending"], "%Y-%m-%d").strftime("%d %b %Y")
    cr = st["crude"]
    lines = [
        "<b>🛢 EIA WEEKLY PETROLEUM REPORT</b>",
        f"<i>Week ending {we} · Source: U.S. Energy Information Administration</i>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "<b>Inventories — change w/w</b>",
    ]
    for k, label in (("crude", "Crude (ex SPR)"), ("gasoline", "Gasoline"),
                     ("distillate", "Distillates"), ("cushing", "Cushing"), ("spr", "SPR")):
        s = st.get(k)
        if not s:
            continue
        extra = []
        if s.get("change_5y_avg") is not None:
            extra.append(f"5y avg {_eia_m(s['change_5y_avg'])}")
        if k == "crude" and fc is not None:
            extra.append(f"forecast {fc:+.1f}M")
        lines.append(f"• {label}: <b>{_eia_m(s['change'])}</b>" + (f"  ({' · '.join(extra)})" if extra else ""))

    total = sum((st[k]["change"] for k in ("crude", "gasoline", "distillate") if st.get(k))) / 1000.0
    lines.append(f"• Total crude + products: <b>{total:+.1f}M</b> ({'draw' if total < 0 else 'build'})")

    lines += ["", "<b>Levels</b>"]
    lv = f"• Crude stocks: <b>{cr['value'] / 1000:.1f}M bbl</b>"
    if cr.get("vs_5y_pct") is not None:
        lv += f"  ({cr['vs_5y_pct']:+.1f}% vs 5y avg)"
    lines.append(lv)
    if st.get("cushing"):
        lines.append(f"• Cushing: <b>{st['cushing']['value'] / 1000:.1f}M bbl</b>")

    sup = []
    if st.get("production"):
        p = st["production"]
        sup.append(f"• US production: <b>{p['value'] / 1000:.2f} mb/d</b> ({(p['change']) / 1000:+.2f})")
    if st.get("refutil"):
        ru = st["refutil"]
        sup.append(f"• Refinery utilization: <b>{ru['value']:.1f}%</b> ({ru['change']:+.1f} pp)")
    if st.get("imports") and st.get("exports"):
        sup.append(f"• Crude imports / exports: <b>{st['imports']['value'] / 1000:.2f}</b> / "
                   f"<b>{st['exports']['value'] / 1000:.2f} mb/d</b>")
    if sup:
        lines += ["", "<b>Supply</b>"] + sup

    lines += eia_xenos_read(rep, fc)

    lines += ["", "<i>XenosFinance — Energy Desk</i>"]   # disclaimer già in SITE_FOOTER
    return "\n".join(lines) + SITE_FOOTER


def eia_build_chart(rep):
    if not CHARTS_AVAILABLE:
        return None
    try:
        st, hist = rep["stats"], rep.get("crude_history") or []
        plt.rcParams.update({"font.family": "monospace", "font.size": 7, "text.color": EWC["text"]})
        fig = plt.figure(figsize=(10, 8.2), facecolor=EWC["bg"])
        gs = gridspec.GridSpec(2, 1, height_ratios=[3.2, 2.0], hspace=0.32,
                               left=0.08, right=0.91, top=0.91, bottom=0.07)

        # 1) Scorte crude 52 settimane vs banda 5 anni
        ax = fig.add_subplot(gs[0])
        ax.set_facecolor(EWC["panel"])
        for sp in ax.spines.values():
            sp.set_color(EWC["grid"])
        ax.grid(True, color=EWC["grid"], linewidth=0.5)
        ax.tick_params(colors=EWC["muted"], labelsize=7)
        x = np.arange(len(hist))
        val = np.array([h["value"] / 1000 for h in hist], dtype=float)
        mn = np.array([h["min5"] / 1000 if h.get("min5") else np.nan for h in hist], dtype=float)
        mx = np.array([h["max5"] / 1000 if h.get("max5") else np.nan for h in hist], dtype=float)
        av = np.array([h["avg5"] / 1000 if h.get("avg5") else np.nan for h in hist], dtype=float)
        ax.fill_between(x, mn, mx, color=EWC["muted"], alpha=0.18, linewidth=0, label="5-year range")
        ax.plot(x, av, color=EWC["muted"], lw=1.0, ls="--", label="5-year average")
        ax.plot(x, val, color=EWC["target"], lw=2.0, label="Crude stocks (ex SPR)")
        ax.scatter([x[-1]], [val[-1]], color=EWC["target"], s=24, zorder=5)
        ax.text(1.0, val[-1], f" {val[-1]:.1f}M", transform=ax.get_yaxis_transform(), color=EWC["target"],
                fontsize=7.5, fontweight="bold", va="center", ha="left", clip_on=False)
        step = max(1, len(hist) // 8)
        ax.set_xticks(list(range(0, len(hist), step)))
        ax.set_xticklabels([datetime.strptime(hist[i]["period"], "%Y-%m-%d").strftime("%b %y")
                            for i in range(0, len(hist), step)], fontsize=6.5)
        ax.set_ylabel("Million barrels", color=EWC["muted"], fontsize=7)
        ax.legend(loc="upper left", fontsize=6.5, facecolor=EWC["bg"], edgecolor=EWC["grid"], labelcolor=EWC["text"])
        ax.set_title("US commercial crude inventories — 52 weeks vs 5-year range", color=EWC["text"],
                     fontsize=9, loc="left", pad=6)

        # 2) Variazioni della settimana vs media 5 anni stessa settimana
        bx = fig.add_subplot(gs[1])
        bx.set_facecolor(EWC["panel"])
        for sp in bx.spines.values():
            sp.set_color(EWC["grid"])
        bx.grid(True, axis="y", color=EWC["grid"], linewidth=0.5)
        bx.tick_params(colors=EWC["muted"], labelsize=7)
        keys = [k for k in ("crude", "gasoline", "distillate", "cushing") if st.get(k)]
        labels = {"crude": "Crude", "gasoline": "Gasoline", "distillate": "Distillates", "cushing": "Cushing"}
        chg = [st[k]["change"] / 1000 for k in keys]
        avg = [(st[k].get("change_5y_avg") or 0) / 1000 for k in keys]
        xb = np.arange(len(keys))
        bars = bx.bar(xb, chg, width=0.5, color=[EWC["up"] if v < 0 else EWC["down"] for v in chg], zorder=3)
        bx.scatter(xb, avg, marker="_", s=900, color=EWC["text"], linewidths=2, zorder=4, label="5-year avg, same week")
        for b, v in zip(bars, chg):
            bx.text(b.get_x() + b.get_width() / 2, v, f"{v:+.1f}M", ha="center",
                    va="bottom" if v >= 0 else "top", color=EWC["text"], fontsize=7.5, fontweight="bold")
        bx.axhline(0, color=EWC["muted"], lw=0.8)
        bx.set_xticks(xb)
        bx.set_xticklabels([labels[k] for k in keys], fontsize=8)
        lo, hi = min(chg + avg + [0]), max(chg + avg + [0])
        pad = (hi - lo) * 0.25 or 1
        bx.set_ylim(lo - pad, hi + pad)
        bx.legend(loc="best", fontsize=6.5, facecolor=EWC["bg"], edgecolor=EWC["grid"], labelcolor=EWC["text"])
        bx.set_title("Weekly change (green = draw, red = build)", color=EWC["text"], fontsize=9, loc="left", pad=6)

        we = datetime.strptime(rep["week_ending"], "%Y-%m-%d").strftime("%d %b %Y")
        fig.text(0.08, 0.965, "EIA WEEKLY PETROLEUM REPORT", fontsize=13, fontweight="bold",
                 color=EWC["text"], ha="left", va="center")
        fig.text(0.91, 0.965, f"Week ending {we}", fontsize=8, color=EWC["muted"], ha="right", va="center")
        fig.text(0.08, 0.015, "xenosfinance.com  ·  Source: U.S. Energy Information Administration (EIA)",
                 fontsize=6, color=EWC["muted"], ha="left")
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, facecolor=EWC["bg"], edgecolor="none")
        buf.seek(0)
        plt.close(fig)
        return buf
    except Exception as e:
        logger.error(f"eia chart: {e}", exc_info=True)
        try:
            plt.close("all")
        except Exception:
            pass
        return None


async def eia_publish_if_new(force=False):
    """Pubblica il report se c'è una settimana nuova (o sempre, con force). Ritorna un esito leggibile."""
    loop = asyncio.get_event_loop()
    try:
        rep = await loop.run_in_executor(None, eia_fetch_report)
    except Exception as e:
        logger.warning(f"EIA report fetch: {e}")
        return f"❌ EIA data unavailable: {e}"
    week = rep["week_ending"]
    state, sha = await loop.run_in_executor(None, _github_json_read, EIA_STATE_FILE)
    last = state.get("last_week") if isinstance(state, dict) else None
    age_days = (datetime.utcnow().date() - datetime.strptime(week, "%Y-%m-%d").date()).days
    if not force:
        if week == last:
            return f"ℹ️ Week ending {week} already published"
        if age_days > 7:
            return f"ℹ️ Latest EIA week ({week}) is not new — waiting for the next release"
    fc = await loop.run_in_executor(None, eia_fetch_forecast)
    msg = eia_build_message(rep, fc)
    img = await loop.run_in_executor(None, eia_build_chart, rep)
    photo_ok = await send_channel_photo(img) if img else False
    text_ok = await send_channel(msg)
    if text_ok:
        # 2026-10-07: bozza Reddit del report EIA (il contenuto più forte per r/oil e simili)
        try:
            _we = datetime.strptime(week, "%Y-%m-%d").strftime("%b %d")
            _chg = rep["stats"]["crude"]["change"] / 1000.0
            _title = (f"EIA weekly: US crude {'draw' if _chg < 0 else 'build'} of {abs(_chg):.1f}M bbl "
                      f"(week ending {_we}) — inventories, refinery runs and what it means")
            _img_b = None
            if img:
                try:
                    img.seek(0); _img_b = img.read()
                except Exception:
                    _img_b = None
            await loop.run_in_executor(None, send_reddit_draft, _title, _html_to_reddit(msg), _img_b)
            # Bluesky: versione breve (≤300 caratteri) + grafico
            _st = rep["stats"]
            _bs = f"🛢 EIA weekly (w/e {_we}): US crude {_chg:+.1f}M bbl"
            if fc is not None:
                _bs += f" (fcst {fc:+.1f}M)"
            for _k, _lab in (("gasoline", "gasoline"), ("distillate", "distillates"), ("cushing", "Cushing")):
                if _st.get(_k):
                    _bs += f", {_lab} {_st[_k]['change'] / 1000.0:+.1f}M"
            if _st.get("refutil"):
                _bs += f". Refinery util {_st['refutil']['value']:.1f}%"
            _bs += ".\n#oil #crude #EIA"
            await loop.run_in_executor(None, bluesky_post, _bs, _img_b, "EIA weekly petroleum inventories chart")
        except Exception as e_rd:
            logger.warning(f"reddit draft (EIA): {e_rd}")
        await loop.run_in_executor(None, _github_json_write, EIA_STATE_FILE,
                                   {"last_week": week, "posted_at": datetime.utcnow().isoformat() + "Z"},
                                   sha if sha is not None else "", f"EIA WPSR posted {week}")
    return (f"{'✅' if text_ok else '❌'} EIA report week ending {week} · text {'sent' if text_ok else 'NOT sent'}"
            f" · chart {'sent' if photo_ok else 'not sent'}")


async def _scheduled_eia_check(context):
    now = datetime.utcnow()
    # Mercoledì (2) e giovedì (3), 14:00–20:00 UTC: copre l'uscita delle 10:30 ET,
    # con o senza ora legale, e lo slittamento al giovedì nelle settimane con festività USA.
    if now.weekday() not in (2, 3) or not (14 <= now.hour < 20):
        return
    res = await eia_publish_if_new()
    if not res.startswith("ℹ️"):
        logger.info(f"EIA auto-post: {res}")


async def cmd_eia(u, c):
    """/eia — pubblica subito sul canale il report EIA della settimana corrente."""
    if not await check_auth(u): return
    m = await u.message.reply_text("🛢 Fetching EIA weekly petroleum data...")
    res = await eia_publish_if_new(force=True)
    await m.edit_text(res)


# ═══════════════════════════════════════════════════════════════════════════════
# 2026-10-07 — DISTRIBUZIONE: Bluesky (automatico) + Week ahead (bozza Reddit)
# ═══════════════════════════════════════════════════════════════════════════════
# Bluesky permette la pubblicazione automatica via API (account bot ammessi se
# dichiarati). Si attiva impostando su Railway BLUESKY_HANDLE (es.
# xenosfinance.bsky.social) e BLUESKY_APP_PASSWORD (Bluesky → Settings →
# Privacy and security → App passwords). Senza le due variabili non fa nulla.
import pytz   # già usato dal JobQueue (requirements)
BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE", "")
BLUESKY_APP_PASSWORD = os.getenv("BLUESKY_APP_PASSWORD", "")
BLUESKY_PDS = os.getenv("BLUESKY_PDS", "https://bsky.social")
SITE_IDEAS_URL = "https://xenosfinance.com/trading-ideas"
_bsky_sess = {"jwt": None, "did": None, "ts": 0}


def _bsky_login():
    if not (BLUESKY_HANDLE and BLUESKY_APP_PASSWORD):
        return None
    if _bsky_sess["jwt"] and time.time() - _bsky_sess["ts"] < 50 * 60:
        return _bsky_sess
    r = requests.post(f"{BLUESKY_PDS}/xrpc/com.atproto.server.createSession",
                      json={"identifier": BLUESKY_HANDLE, "password": BLUESKY_APP_PASSWORD}, timeout=20)
    d = r.json()
    if "accessJwt" not in d:
        logger.warning(f"bluesky login failed: {str(d)[:200]}")
        return None
    _bsky_sess.update(jwt=d["accessJwt"], did=d["did"], ts=time.time())
    return _bsky_sess


def _bsky_facets(text):
    """Link (xenosfinance.com/…) e hashtag cliccabili: offset in BYTE UTF-8."""
    facets = []
    b = text.encode("utf-8")
    for m in re.finditer(r"(https?://)?xenosfinance\.com(/[\w\-/]*)?", text):
        s = len(text[:m.start()].encode("utf-8")); e = s + len(m.group(0).encode("utf-8"))
        uri = m.group(0) if m.group(0).startswith("http") else "https://" + m.group(0)
        facets.append({"index": {"byteStart": s, "byteEnd": e},
                       "features": [{"$type": "app.bsky.richtext.facet#link", "uri": uri}]})
    for m in re.finditer(r"(?<!\w)#([A-Za-z][A-Za-z0-9_]{1,40})", text):
        s = len(text[:m.start()].encode("utf-8")); e = s + len(m.group(0).encode("utf-8"))
        facets.append({"index": {"byteStart": s, "byteEnd": e},
                       "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": m.group(1)}]})
    return facets if b else []


def bluesky_post(text, img_bytes=None, alt="Chart"):
    """Pubblica un post su Bluesky (max 300 caratteri, immagine opzionale). Mai eccezioni."""
    try:
        s = _bsky_login()
        if not s:
            return False
        if len(text) > 300:
            text = text[:297].rstrip() + "…"
        hdr = {"Authorization": f"Bearer {s['jwt']}"}
        record = {"$type": "app.bsky.feed.post", "text": text, "langs": ["en"],
                  "createdAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"}
        f = _bsky_facets(text)
        if f:
            record["facets"] = f
        if img_bytes:
            data, mime = img_bytes, "image/png"
            if len(data) > 950_000:          # limite blob Bluesky ~1 MB → JPEG
                try:
                    from PIL import Image as _Im
                    im = _Im.open(io.BytesIO(data)).convert("RGB")
                    buf = io.BytesIO(); im.save(buf, "JPEG", quality=85, optimize=True)
                    data, mime = buf.getvalue(), "image/jpeg"
                except Exception as e_c:
                    logger.warning(f"bluesky image compress: {e_c}")
                    data = None
            if data:
                up = requests.post(f"{BLUESKY_PDS}/xrpc/com.atproto.repo.uploadBlob",
                                   headers={**hdr, "Content-Type": mime}, data=data, timeout=40).json()
                if "blob" in up:
                    record["embed"] = {"$type": "app.bsky.embed.images",
                                       "images": [{"alt": alt[:300], "image": up["blob"]}]}
        r = requests.post(f"{BLUESKY_PDS}/xrpc/com.atproto.repo.createRecord", headers=hdr,
                          json={"repo": s["did"], "collection": "app.bsky.feed.post", "record": record},
                          timeout=20)
        ok = r.status_code == 200
        if not ok:
            logger.warning(f"bluesky post failed: {r.status_code} {r.text[:200]}")
        return ok
    except Exception as e:
        logger.warning(f"bluesky post: {e}")
        return False


def bluesky_setup_text(kind, sym, ew):
    """Testo breve (≤300) per un setup /elliott o /ai, stessi livelli del canale."""
    try:
        pf = _pf(sym)
        lv = _setup_levels(ew)
        eng = ew.get("engine") or {}
        name = MARKETS[sym]["name"]
        wave = f" · wave {eng['wave']}" if eng.get("wave") else ""
        tag = "#ElliottWave" if kind == "elliott" else "#TechnicalAnalysis"
        if lv["main_action"] in ("long", "short"):
            body = (f"{name}{wave} · {lv['main_action'].upper()} setup\n"
                    f"Entry {lv['entry']:{pf}} · SL {lv['inv']:{pf}}\n"
                    f"TP {lv['tp2']:{pf}} → {lv['tp1']:{pf}}")
            if eng.get("inval") is not None:
                body += f"\nCount invalid {'below' if lv['main_action'] == 'long' else 'above'} {eng['inval']:{pf}}"
        else:
            body = f"{name}{wave} · no new entry ({lv['main_action']})\nInvalidation {lv['inv']:{pf}}"
        return f"{body}\n\nFull analysis: xenosfinance.com/trading-ideas\n{tag} #trading"
    except Exception as e:
        logger.warning(f"bluesky setup text: {e}")
        return None


# ── Week ahead ──────────────────────────────────────────────────────────────
FF_THISWEEK_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
WEEKAHEAD_CCY = ("USD", "EUR", "GBP", "JPY", "CAD", "CNY", "AUD", "CHF")


def weekahead_events():
    """Eventi ad alto impatto della settimana. Chiamata la DOMENICA: per
    ForexFactory la settimana inizia di domenica, quindi 'thisweek' è quella
    che sta per iniziare. Ritorna lista di dict ordinati per orario (UTC)."""
    r = requests.get(FF_THISWEEK_URL, headers={"User-Agent": "Mozilla/5.0 XenosFinanceBot"}, timeout=20)
    r.raise_for_status()
    out = []
    for ev in r.json():
        if (ev.get("impact") or "").lower() != "high":
            continue
        if ev.get("country") not in WEEKAHEAD_CCY:
            continue
        try:
            dt = datetime.fromisoformat(ev["date"]).astimezone(pytz.UTC)
        except Exception:
            continue
        out.append({"dt": dt, "ccy": ev["country"], "title": ev.get("title", ""),
                    "forecast": ev.get("forecast") or "", "previous": ev.get("previous") or ""})
    # Il report EIA del greggio non è "high" su FF ma per noi è centrale
    for ev in r.json():
        if "crude oil inventories" in (ev.get("title") or "").lower() and ev.get("country") == "USD":
            try:
                dt = datetime.fromisoformat(ev["date"]).astimezone(pytz.UTC)
                if not any(o["title"] == ev["title"] and o["dt"] == dt for o in out):
                    out.append({"dt": dt, "ccy": "USD", "title": "EIA " + ev["title"],
                                "forecast": ev.get("forecast") or "", "previous": ev.get("previous") or ""})
            except Exception:
                pass
    return sorted(out, key=lambda o: o["dt"])


def weekahead_watch_ai(events):
    """3 frasi: cosa guardare per petrolio, oro, dollaro. None se AI non disponibile."""
    if not ANTHROPIC_API_KEY or not events:
        return None
    lst = "\n".join(f"{e['dt']:%a %H:%M} UTC · {e['ccy']} · {e['title']}"
                    + (f" (fcst {e['forecast']}, prev {e['previous']})" if e['forecast'] or e['previous'] else "")
                    for e in events[:25])
    prompt = ("You are an independent oil trader writing for Reddit. Based ONLY on these high-impact "
              f"events for the coming week:\n{lst}\n\nWrite exactly 3 short sentences, one each for "
              "crude oil, gold and the US dollar: which event matters most and why. No hype, no predictions "
              "of direction, no markdown, no title. Max 70 words total.")
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
                          headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                                   "content-type": "application/json"},
                          json={"model": "claude-sonnet-4-5", "max_tokens": 250,
                                "messages": [{"role": "user", "content": prompt}]}, timeout=60)
        res = r.json()
        if res.get("content"):
            return strip_bold(res["content"][0]["text"]).strip()
    except Exception as e:
        logger.warning(f"weekahead ai: {e}")
    return None


def weekahead_build():
    ev = weekahead_events()
    if not ev:
        return None
    et = pytz.timezone("America/New_York")
    first = ev[0]["dt"].astimezone(et)
    title = f"Week ahead ({first:%b %d}): the high-impact releases that matter for oil, gold and the dollar"
    lines, day = [], None
    for e in ev:
        loc = e["dt"].astimezone(et)
        d = loc.strftime("%A %b %d")
        if d != day:
            lines.append(f"\n**{d}**  ")
            day = d
        extra = ""
        if e["forecast"] or e["previous"]:
            extra = f" — fcst {e['forecast'] or 'n/a'}, prev {e['previous'] or 'n/a'}"
        lines.append(f"- {loc:%H:%M} ET · {e['ccy']} · {e['title']}{extra}")
    body = "Times in ET. High-impact releases only, plus the EIA crude report.\n" + "\n".join(lines)
    watch = weekahead_watch_ai(ev)
    if watch:
        body += f"\n\n**What I'm watching**  \n{watch}"
    # Bluesky: i 5 eventi principali
    top = [e for e in ev if not e["title"].startswith("EIA")][:4] + [e for e in ev if e["title"].startswith("EIA")][:1]
    top = sorted(top, key=lambda o: o["dt"])
    bs = "Week ahead — key releases (ET):\n" + "\n".join(
        f"{e['dt'].astimezone(et):%a %H:%M} {e['ccy']} {e['title'][:34]}" for e in top)
    bs += "\n#forex #oil #macro"
    return title, body, bs


async def _scheduled_weekahead(context):
    now = datetime.utcnow()
    if now.weekday() != 6:          # solo domenica
        return
    loop = asyncio.get_event_loop()
    try:
        res = await loop.run_in_executor(None, weekahead_build)
    except Exception as e:
        logger.warning(f"weekahead: {e}")
        return
    if not res:
        return
    title, body, bs = res
    await loop.run_in_executor(None, send_reddit_draft, title, body, None)
    await loop.run_in_executor(None, bluesky_post, bs, None)


async def cmd_weekahead(u, c):
    """/weekahead — bozza Reddit della settimana (in privato). Nessuna pubblicazione."""
    if not await check_auth(u): return
    m = await u.message.reply_text("🗓 Preparing week ahead...")
    loop = asyncio.get_event_loop()
    try:
        res = await loop.run_in_executor(None, weekahead_build)
    except Exception as e:
        await m.edit_text(f"❌ Calendar unavailable: {e}"); return
    if not res:
        await m.edit_text("ℹ️ No high-impact events found"); return
    await loop.run_in_executor(None, send_reddit_draft, res[0], res[1], None)
    await m.edit_text("✅ Week ahead draft sent (Reddit). Bluesky posts it automatically on Sunday.")


def main():
    logger.info("="*60)
    logger.info("XENOSFINANCE — Financial Intelligence Bot v3.1")
    logger.info("="*60)
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ Manca TELEGRAM_BOT_TOKEN"); return
    if OWNER_ID == 0:
        logger.error("❌ Manca OWNER_TELEGRAM_ID"); return
    logger.info(f"✅ Owner ID: {OWNER_ID}")
    logger.info(f"✅ AI Claude: {'Active' if ANTHROPIC_API_KEY else 'Not configured'}")
    logger.info("✅ Elliott Wave Deep-Scan v2.0")
    logger.info("✅ Geopolitics: Reuters + CNBC + Al Jazeera + Yahoo Finance + AP News")
    logger.info(f"✅ Daily News Brief: {'GitHub (' + GITHUB_REPO + ')' if GITHUB_TOKEN else 'GitHub not configured'}")
    logger.info(f"✅ Charts: {'Active (matplotlib)' if CHARTS_AVAILABLE else 'Disabled'}")
    logger.info("="*60)

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",       cmd_start))
    app.add_handler(CommandHandler("menu",        cmd_start))
    app.add_handler(CommandHandler("status",      cmd_status))
    app.add_handler(CommandHandler("elliott",     cmd_elliott))
    app.add_handler(CommandHandler("ai",          cmd_ai))
    app.add_handler(CommandHandler("quant",       cmd_ai))
    app.add_handler(CommandHandler("signal",      cmd_signal))
    app.add_handler(CommandHandler("geopolitics", cmd_geopolitics))
    app.add_handler(CommandHandler("geo",         cmd_geopolitics))
    app.add_handler(CommandHandler("outlook",     cmd_outlook))
    app.add_handler(CommandHandler("premarket",   cmd_premarket))
    from telegram.ext import CallbackQueryHandler as _CQH
    app.add_handler(_CQH(_cb_publish_brief, pattern=r"^pub_brief:"))
    app.add_handler(_CQH(_cb_mko_preview, pattern=r"^mko_(pub|del):"))
    app.add_handler(_CQH(_cb_setup_preview, pattern=r"^setup_(pub|del):"))
    app.add_handler(_CQH(_cb_paycard, pattern=r"^paycard_(send|no):\d+$"))
    app.add_handler(_CQH(_cb_support, pattern=r"^support_(send|no):\d+$"))
    from telegram.ext import MessageHandler as _MH, filters as _F
    app.add_handler(_MH(_F.ChatType.PRIVATE & ~_F.User(OWNER_ID) & ~_F.COMMAND, _relay_user_message))
    app.add_handler(_MH(_F.ChatType.PRIVATE & _F.User(OWNER_ID) & _F.REPLY & ~_F.COMMAND, _owner_reply_relay))
    app.add_handler(CommandHandler("forex",       cmd_forex))
    app.add_handler(CommandHandler("crypto",      cmd_crypto))
    app.add_handler(CommandHandler("commodities", cmd_commodities))
    app.add_handler(CommandHandler("equity",      cmd_equity))
    app.add_handler(CommandHandler("updatesite",  cmd_updatesite))
    app.add_handler(CommandHandler("news",        cmd_news))
    app.add_handler(CommandHandler("brief",       cmd_news))
    app.add_handler(CommandHandler("futures",          cmd_futures))
    app.add_handler(CommandHandler("mko",              cmd_futures))
    app.add_handler(CommandHandler("daily_education",  cmd_daily_education))
    app.add_handler(CommandHandler("pub",             cmd_pub))
    app.add_handler(CommandHandler("eia",             cmd_eia))
    app.add_handler(CommandHandler("weekahead",       cmd_weekahead))

    logger.info("🚀 Bot started — waiting for commands...")
    logger.info(f"✅ MKO Engine: {len(MKO_ASSETS)} assets, auto-scan every {MKO_SCAN_INTERVAL}min, push threshold {MKO_SCORE_STRONG}/10, cooldown {MKO_DEDUP_TTL//3600}h/asset, daily cap {MKO_DAILY_CAP}")

    async def _post_init(application):
        asyncio.ensure_future(mko_auto_scan())
        if application.job_queue is not None:
            import datetime as _dt2, pytz as _pytz
            application.job_queue.run_daily(
                _scheduled_daily_education,
                time=_dt2.time(8, 0, tzinfo=_pytz.UTC),
                name="daily_education"
            )
            logger.info("✅ Daily Education: scheduled job active (09:00 CET)")
            application.job_queue.run_repeating(
                _scheduled_updatesite,
                interval=4 * 3600,
                first=120,
                name="updatesite"
            )
            logger.info("✅ Site update: scheduled job active (every 4h)")
            application.job_queue.run_repeating(
                _scheduled_eia_check,
                interval=600,
                first=90,
                name="eia_wpsr"
            )
            logger.info("✅ EIA weekly petroleum report: auto-post active (Wed/Thu 14-20 UTC, every 10 min)")
            # 2026-10-07: week ahead (domenica 17:00 UTC); il giorno viene
            # controllato dentro la funzione (job giornaliero).
            application.job_queue.run_daily(_scheduled_weekahead, time=_dt2.time(17, 0, tzinfo=_pytz.UTC), name="weekahead")
            logger.info(f"✅ Week ahead (Sun 17:00 UTC) draft active · Bluesky: "
                        f"{'ON as ' + BLUESKY_HANDLE if BLUESKY_HANDLE and BLUESKY_APP_PASSWORD else 'off (set BLUESKY_HANDLE + BLUESKY_APP_PASSWORD)'}")
        else:
            logger.warning("⚠️ Daily Education: JobQueue not available. Add python-telegram-bot[job-queue] to requirements.txt. Manual /daily_education still works.")

    app.post_init = _post_init
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
