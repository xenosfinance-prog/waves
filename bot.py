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
    "📲 <a href=\"https://t.me/xenosfin\"><b>Join XenosFinance</b></a> — Elliott Waves, analysis, macro and much more.\n"
    "🔔 <i>Enable notifications to stay updated.</i>"
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
    "NASDAQ": {"name": "Nasdaq",           "emoji": "📈", "yf": "^IXIC",     "cat": "equity"},
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
        logger.info(f"✅ {symbol}: {len(df)} bars ({interval})")
        return df
    except Exception as e:
        logger.error(f"❌ {symbol}: {e}")
        return None

# ─── TECHNICAL INDICATORS ─────────────────────────────────────────────────────
def ema(s, span):    return s.ewm(span=span, adjust=False).mean()
def rsi(s, p=14):
    d = s.diff()
    g = d.clip(lower=0).rolling(p).mean()
    l = (-d.clip(upper=0)).rolling(p).mean()
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

    ds    = count_elliott_waves_deepscan(df)
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

    if wn == "3":
        pt = w1e + w1z * (2.618 if ext else 1.618)
        pl = f"{'261.8%' if ext else '161.8%'} estensione W1"
    elif wn == "5":
        pt = w1e + w1z * 0.618
        pl = "61.8% di W1"
    elif wn == "C":
        pt = ct
        pl = "100-123.6% di Onda A"
    elif wn in ["2","4"]:
        pt = ct
        pl = f"{'61.8%' if wn=='2' else '38.2%'} Fibonacci"
    else:
        pt = p + 1.5 * av
        pl = "1.5x ATR"

    mtf_4h = None
    if df_4h is not None and len(df_4h) >= 50:
        try:
            ds4 = count_elliott_waves_deepscan(df_4h)
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
            }
        except Exception as e_4h:
            logger.warning(f"4H scan error: {e_4h}")

    mtf_1h = None
    if df_1h is not None and len(df_1h) >= 50:
        try:
            ds1 = count_elliott_waves_deepscan(df_1h)
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

def chart_elliott(sym, df, ew, df_4h=None, df_1h=None):
    if not CHARTS_AVAILABLE or df is None or len(df) < 50: return None
    _base_style()
    mkt  = MARKETS[sym]
    pfmt = '.5f' if sym in ['EURUSD','GBPUSD','USDJPY','AUDUSD','USDCHF','USDCAD','NZDUSD'] else '.2f'
    p    = ew['price']

    has_4h = df_4h is not None and len(df_4h) >= 30
    has_1h = df_1h is not None and len(df_1h) >= 30
    n_tf   = 1 + int(has_4h) + int(has_1h)

    fig = plt.figure(figsize=(7 * n_tf, 12), facecolor=DARK_BG)
    fig.suptitle(
        f'🌊 ELLIOTT WAVE MTF — {mkt["emoji"]} {mkt["name"]}  |  {datetime.now().strftime("%d %b %Y %H:%M CET")}',
        color=WHITE, fontsize=11, fontweight='bold', y=0.98
    )

    tf_configs = [{"df": df.iloc[-80:].copy(), "label": "DAILY"}]
    if has_4h: tf_configs.append({"df": df_4h.iloc[-96:].copy(), "label": "4H"})
    if has_1h: tf_configs.append({"df": df_1h.iloc[-72:].copy(), "label": "1H"})

    gs = gridspec.GridSpec(3, n_tf, height_ratios=[6, 1.8, 1.8], hspace=0.06, wspace=0.3)

    def _draw_tf(col_idx, cfg, ew_data):
        data  = cfg["df"]
        label = cfg["label"]
        x     = range(len(data))
        c_ser = data['close']

        ax1 = fig.add_subplot(gs[0, col_idx])
        ax2 = fig.add_subplot(gs[1, col_idx], sharex=ax1)
        ax3 = fig.add_subplot(gs[2, col_idx], sharex=ax1)

        for i, (idx, row) in enumerate(data.iterrows()):
            col   = GREEN if row['close'] >= row['open'] else RED
            bot   = min(row['open'], row['close'])
            top   = max(row['open'], row['close'])
            ax1.bar(i, top - bot, bottom=bot, color=col, width=0.7, alpha=0.85)
            ax1.plot([i, i], [row['low'],  bot], color=col, linewidth=0.7, alpha=0.85)
            ax1.plot([i, i], [top, row['high']], color=col, linewidth=0.7, alpha=0.85)

        sma20v  = c_ser.rolling(20).mean().values
        sma50v  = c_ser.rolling(50).mean().values
        ema21v  = c_ser.ewm(span=21, adjust=False).mean().values
        ax1.plot(x, sma20v,  color=BLUE,   linewidth=1.0, label='SMA20',  alpha=0.85)
        ax1.plot(x, sma50v,  color=ORANGE, linewidth=1.0, label='SMA50',  alpha=0.85)
        ax1.plot(x, ema21v,  color=YELLOW, linewidth=0.8, label='EMA21',  alpha=0.7, linestyle='--')

        if ew_data:
            inv_l = ew_data.get('invalidation', 0)
            tgt_l = ew_data.get('next_target',  0)
            ct_l  = ew_data.get('conservative_target', 0)
            pr_l  = ew_data.get('price', 0)
            fib_d = ew_data.get('fib', {}) if col_idx == 0 else {}

            if inv_l > 0: ax1.axhline(inv_l, color=RED,   linewidth=1.2, linestyle='--', alpha=0.85, label=f'SL {inv_l:{pfmt}}')
            if tgt_l > 0: ax1.axhline(tgt_l, color=GREEN, linewidth=1.2, linestyle='--', alpha=0.85, label=f'TP {tgt_l:{pfmt}}')
            if ct_l > 0 and ct_l != tgt_l:
                ax1.axhline(ct_l, color=BLUE, linewidth=0.9, linestyle=':', alpha=0.7, label=f'TP2 {ct_l:{pfmt}}')

            for key, (fc, fa) in [('38.2',(ORANGE,0.5)),('50.0',(YELLOW,0.4)),('61.8',(PURPLE,0.55))]:
                if key in fib_d and fib_d[key] > 0:
                    ax1.axhline(fib_d[key], color=fc, linewidth=0.7, linestyle=':', alpha=fa)
                    ax1.text(len(x)-1, fib_d[key], f' {key}%', color=fc, fontsize=5.5, va='center', alpha=0.85)

            if pr_l > 0:
                ax1.axhline(pr_l, color=WHITE, linewidth=0.7, linestyle='-', alpha=0.45)
                ax1.text(len(x)-1, pr_l, f' {pr_l:{pfmt}}', color=WHITE, fontsize=6.5, va='center', fontweight='bold')

            wi_map = {'1':'①','2':'②','3':'③','4':'④','5':'⑤','A':'🅐','B':'🅑','C':'🅒','?':'?'}
            wn_d   = ew_data.get('wave_num','?')
            wp_d   = ew_data.get('wave_phase','')
            bi_d   = ew_data.get('bias','')
            wi     = wi_map.get(wn_d, wn_d)
            wclr   = GREEN if wp_d == 'IMPULSIVA' else RED if 'CORR' in wp_d else ORANGE
            conf_d = ew_data.get('confidence', 0)
            diag_d = ew_data.get('diagonal')
            diag_txt = f" | {diag_d.split(' ')[0]}" if diag_d else ""
            ax1.text(0.02, 0.97,
                     f"Onda {wi}  {wp_d[:8]}{diag_txt}\n{bi_d[:22]}  {conf_d:.0f}%",
                     transform=ax1.transAxes, color=wclr, fontsize=7, fontweight='bold', va='top',
                     bbox=dict(boxstyle='round,pad=0.25', facecolor=DARK_PANEL, alpha=0.82, edgecolor=wclr))

        ax1.set_title(label, color=GREY, fontsize=9, fontweight='bold', pad=4)
        ax1.legend(loc='lower left', fontsize=5.5, ncol=3, framealpha=0.55)
        ax1.set_ylabel('Price' if col_idx == 0 else '', color=WHITE, fontsize=7)
        ax1.grid(True, alpha=0.25)
        plt.setp(ax1.get_xticklabels(), visible=False)

        rsi_vals = []
        for i in range(len(data)):
            sl = c_ser.iloc[:i+1]
            if len(sl) >= 14:
                d_ = sl.diff()
                g_ = d_.clip(lower=0).rolling(14).mean().iloc[-1]
                l_ = (-d_.clip(upper=0)).rolling(14).mean().iloc[-1]
                rv_ = 100 - (100 / (1 + g_ / l_)) if l_ > 0 else 50
            else:
                rv_ = 50
            rsi_vals.append(rv_)
        ax2.plot(x, rsi_vals, color=BLUE, linewidth=1.0)
        ax2.axhline(70, color=RED,   linewidth=0.7, linestyle='--', alpha=0.55)
        ax2.axhline(30, color=GREEN, linewidth=0.7, linestyle='--', alpha=0.55)
        ax2.axhline(50, color=GREY,  linewidth=0.4, linestyle=':',  alpha=0.35)
        ax2.fill_between(x, rsi_vals, 70, where=[v > 70 for v in rsi_vals], alpha=0.18, color=RED)
        ax2.fill_between(x, rsi_vals, 30, where=[v < 30 for v in rsi_vals], alpha=0.18, color=GREEN)
        ax2.set_ylim(0, 100)
        ax2.set_ylabel('RSI' if col_idx == 0 else '', color=WHITE, fontsize=6.5)
        ax2.text(len(x)-1, rsi_vals[-1], f' {rsi_vals[-1]:.0f}', color=BLUE, fontsize=6.5, va='center')
        ax2.grid(True, alpha=0.22)
        plt.setp(ax2.get_xticklabels(), visible=False)

        e12 = c_ser.ewm(span=12, adjust=False).mean()
        e26 = c_ser.ewm(span=26, adjust=False).mean()
        ml_v  = e12 - e26
        sig_v = ml_v.ewm(span=9, adjust=False).mean()
        hist  = ml_v - sig_v
        ax3.bar(x, hist.values, color=[GREEN if v >= 0 else RED for v in hist], alpha=0.65, width=0.8)
        ax3.plot(x, ml_v.values,  color=BLUE,   linewidth=0.9, label='M')
        ax3.plot(x, sig_v.values, color=ORANGE,  linewidth=0.9, label='S')
        ax3.axhline(0, color=GREY, linewidth=0.4)
        ax3.set_ylabel('MACD' if col_idx == 0 else '', color=WHITE, fontsize=6.5)
        ax3.legend(loc='lower left', fontsize=5.5, framealpha=0.45)
        ax3.grid(True, alpha=0.22)

        tick_step = max(1, len(data) // 6)
        tick_pos  = list(range(0, len(data), tick_step))
        ax3.set_xticks(tick_pos)
        ax3.set_xticklabels(
            [data.index[i].strftime('%d/%m' if label != 'DAILY' else '%d %b') for i in tick_pos],
            rotation=30, ha='right', fontsize=5.5
        )

    _draw_tf(0, tf_configs[0], ew)
    if has_4h:
        ew4 = dict(ew.get('mtf_4h') or {}); ew4['fib'] = {}; ew4['conservative_target'] = 0
        _draw_tf(1, tf_configs[1], ew4)
    if has_1h:
        ew1 = dict(ew.get('mtf_1h') or {}); ew1['fib'] = {}; ew1['conservative_target'] = 0
        _draw_tf(2, tf_configs[2], ew1)

    plt.tight_layout(rect=[0, 0, 1, 0.97], pad=0.4)
    return _savefig_bytes(fig)


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
def claude_analysis_simple(name, ew):
    if not ANTHROPIC_API_KEY:
        return None
    try:
        prompt = f"""Analyze {name} with this data in ENGLISH:
PRICE: {ew['price']:.5f} ({ew['chg']:+.2f}%)
ELLIOTT WAVE: {ew['wave_pos']} (Degree: {ew['degree']}) | BIAS: {ew['bias']} ({ew['confidence']}%)
RSI: {ew['rsi']:.1f} | MACD: {ew['macd_hist']:+.6f}
Bearish Divergence: {'YES' if ew['bearish_div'] else 'NO'} | Bullish: {'YES' if ew['bullish_div'] else 'NO'}
SMA 20/50/200: {ew['sma20']:.5f}/{ew['sma50']:.5f}/{ew['sma200']:.5f}
ATR: {ew['atr']:.5f} | Fib 38.2%: {ew['fib']['38.2']:.5f} | 61.8%: {ew['fib']['61.8']:.5f}
Stop Loss: {ew['invalidation']:.5f} | Target: {ew['next_target']:.5f} | R/R: {ew['risk_reward']:.1f}:1

IMPORTANT: Always write in ENGLISH. NO asterisks. Plain text only.
Institutional analysis max 250 words: multi-timeframe technical context,
entry/target/stop based on EW and Fibonacci levels, scenario probability %, risk factors."""
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-5",
                "max_tokens": 600,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        res = r.json()
        if "content" in res and res["content"]:
            return strip_bold(res["content"][0]["text"])
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

        direction_up = ew.get("direction_up", True)
        wave_num     = ew.get("wave_num", "?")
        bias         = ew.get("bias", "")
        # Determine actual trade direction from bias, not just direction_up
        # Corrective waves A/C are bearish even in uptrend
        is_bearish = any(x in bias for x in ["BEAR", "SHORT", "CORR"])
        is_w5_term = "TERMINAL" in bias
        if wave_num in ["A", "C"]:
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
        today = datetime.now().strftime("%d %b %Y")

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
            f"Bias: {ew['bias']} | Confidence: {ew['confidence']}%\n"
            f"{mtf_block}"
            f"RSI: {ew['rsi']:.1f} | MACD hist: {ew['macd_hist']:+.6f}\n"
            f"ATR (daily): {ew['atr']:{pfmt}}\n"
            f"SMA 20/50/200: {ew['sma20']:{pfmt}} / {ew['sma50']:{pfmt}} / {ew['sma200']:{pfmt}}\n"
            f"Fib 38.2%: {ew['fib']['38.2']:{pfmt}} | 50%: {ew['fib']['50.0']:{pfmt}} | 61.8%: {ew['fib']['61.8']:{pfmt}}\n"
            f"Key support: {ew['support']:{pfmt}} | Key resistance: {ew['resist']:{pfmt}}\n"
            f"Main TP: {tp1:{pfmt}} | Conservative TP: {tp2:{pfmt}} | SL: {inv:{pfmt}} | R/R: {rr:.1f}:1\n"
            f"{div_ctx}\n{special_ctx}\n\n"
            f"OUTPUT FORMAT — use EXACTLY these 4 section headers:\n\n"
            f"\U0001f3af Major Takeaways\n"
            f"- Main scenario: [one sentence — {main_action} signal, entry near {price:{pfmt}}, target range {tp2:{pfmt}}–{tp1:{pfmt}}, SL at {inv:{pfmt}}]\n"
            f"- Alternative scenario: [one sentence — what happens if {inv:{pfmt}} breaks, next structural target near {alt_next_target:{pfmt}}]\n\n"
            f"\U0001f4c8 Main Scenario\n"
            f"[2-3 sentences. The {main_action} setup: entry near {price:{pfmt}}, TP targets {tp1:{pfmt}} and {tp2:{pfmt}}, SL at {inv:{pfmt}}. "
            f"State the buy/sell signal trigger. R/R = {rr:.1f}:1.]\n\n"
            f"\U0001f4c9 Alternative Scenario\n"
            f"[1-2 sentences. If {inv:{pfmt}} is breached, describe the wave structure that follows. "
            f"Next structural target near {alt_next_target:{pfmt}}. "
            f"IMPORTANT: do NOT use price levels more than 2x ATR ({atr_v * 2:{pfmt}}) away from current price — "
            f"this is an intraday/swing analysis, not a multi-week forecast.]\n\n"
            f"\U0001f50d Analysis\n"
            f"[3-4 sentences: (1) what wave structure is developing on Daily based on H4/H1 sub-waves, "
            f"(2) which sub-wave is currently forming and at what stage, "
            f"(3) why {inv:{pfmt}} is the critical structural level. "
            f"Reference specific timeframes H1/H4/Daily. Be precise about wave degrees and sub-wave labels.]\n\n"
            f"STRICT RULES:\n"
            f"- Professional English, tone like elliottwave.com or FXStreet EW research\n"
            f"- Use EXACT price levels from the data provided above\n"
            f"- SL and TP levels must stay within ATR-based ranges — NEVER invent distant historical levels\n"
            f"- NO asterisks, NO markdown, NO bullet points except in Major Takeaways\n"
            f"- NO self-referential phrases\n"
            f"- H1/H4/Daily ONLY — no weekly/monthly\n"
            f"- Max 320 words total"
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
                "max_tokens": 900,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=40
        )
        res = r.json()
        if "content" in res and res["content"]:
            return strip_bold(res["content"][0]["text"])
    except Exception as e:
        logger.error(f"narrative: {e}")
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
    return ".5f" if sym in ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCHF","USDCAD","NZDUSD"] else ".2f"


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
    c = MARKETS[sym]
    return (f"<b>🤖 AI ANALYSIS — {c['emoji']} {c['name']}</b>\n"
            f"{datetime.now().strftime('%d %b %Y • %H:%M CET')}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n{txt}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n<i>XenosFinance AI Desk</i>")


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
    ideas, sha = _github_json_read(TRADING_IDEAS_FILE)
    if ideas is None:
        logger.error("❌ Impossibile leggere trading_ideas/ideas.json")
        return False
    ideas.insert(0, idea)
    if len(ideas) > TRADING_IDEAS_MAX:
        ideas = ideas[:TRADING_IDEAS_MAX]
    ok = _github_json_write(TRADING_IDEAS_FILE, ideas, sha, f"Trading Idea: {sym} Wave {ew.get('wave_num','?')} {timestamp}")
    if ok:
        logger.info(f"✅ Trading Idea salvata: {sym} [{idea_id}]")
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
    if not await check_auth(u): return
    await u.message.reply_text(
        "<b>📊 XENOSFINANCE</b>\n\n"
        "<b>TECHNICAL ANALYSIS:</b>\n"
        "/elliott SYMBOL — Elliott Wave v2 (Real Pivots)\n"
        "/ai SYMBOL — AI Analysis with Claude\n\n"
        "<b>MARKET OVERVIEW:</b>\n"
        "/outlook — Intraday market snapshot\n"
        "/wrap — Morning/Afternoon Wrap 800+ words\n"
        "/premarket — 🌅 US Pre-Market brief + top movers\n\n"
        "<b>ASSET CLASS ANALYSIS:</b>\n"
        "/forex — FX majors | /crypto — BTC &amp; ETH\n"
        "/commodities — Gold, Silver, Oil, Gas\n"
        "/equity — S&amp;P 500, Nasdaq, Dow\n\n"
        "<b>GEOPOLITICS &amp; MACRO:</b>\n"
        "/geopolitics — Geopolitical news + market impact\n"
        "/news — 📰 Daily digest on xenosfinance.com\n\n"
        "/status — System status\n\n"
        "<i>FX: EURUSD GBPUSD USDJPY AUDUSD USDCHF USDCAD NZDUSD\n"
        "Comm: GOLD SILVER OIL NGAS | Idx: SPY NASDAQ DJI\n"
        "Crypto: BTCUSD ETHUSD\n"
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
        f"✅ Daily Digest (Reuters + CNBC + Yahoo Finance + Al Jazeera)\n"
        f"{'✅' if ai else '⚠️'} AI Claude {'Active' if ai else '— API Key not configured'}\n"
        f"{'✅' if GITHUB_TOKEN else '⚠️'} GitHub {'Configured (' + GITHUB_REPO + ')' if GITHUB_TOKEN else 'Not configured'}\n"
        f"{'✅' if CHARTS_AVAILABLE else '⚠️'} Charts {'Active (matplotlib)' if CHARTS_AVAILABLE else 'Disabled'}\n\n"
        f"✅ Data: Yahoo Finance | ✅ News: Reuters + CNBC + Al Jazeera RSS",
        parse_mode="HTML")

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
        narrative = claude_narrative_analysis(s, ew, df)
        if narrative:
            now_str = datetime.now().strftime("%d %b %Y • %H:%M CET")
            wi_map = {"1":"①","2":"②","3":"③","4":"④","5":"⑤","A":"🅐","B":"🅑","C":"🅒","?":"❓"}
            wi = wi_map.get(ew["wave_num"], "🌊")
            nav_msg = (
                f"<b>📝 ANALYSIS — {MARKETS[s]['emoji']} {MARKETS[s]['name']} · Wave {wi}</b>\n"
                f"<i>{now_str}</i>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{narrative}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ <i>Not investment advice.</i>\n"
                f"<i>XenosFinance — Elliott Wave Desk</i>"
                + SITE_FOOTER
            )
            await send_channel(nav_msg)
        # ── 2. Poi manda il grafico ──
        img = None
        if CHARTS_AVAILABLE:
            img = chart_elliott(s, df, ew, df_4h=df_4h, df_1h=df_1h)
            if img:
                await send_channel_photo(img)
        # ── 3. Salva Trading Idea su GitHub ──
        save_trading_idea(s, ew, narrative, img_buf=img)
        await m.edit_text("✅ MTF analysis + chart + editorial sent to channel!")
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
        ai = claude_analysis_simple(MARKETS[s]["name"], ew)
        if not ai:
            await m.edit_text("❌ AI unavailable"); return
        await send_channel(fmt_ai(s, ai))
        img = None
        if CHARTS_AVAILABLE:
            img = chart_elliott(s, df, ew, df_4h=df_4h, df_1h=df_1h)
            if img:
                await send_channel_photo(img)
        # Salva Trading Idea su GitHub
        save_trading_idea(s, ew, ai, img_buf=img)
        await m.edit_text("✅ AI analysis + MTF chart sent to channel!")
    except Exception as e:
        logger.error(f"ai: {e}", exc_info=True)
        await m.edit_text(f"❌ Error: {str(e)[:100]}")


# ═══════════════════════════════════════════════════════════════════════════════
# PREMARKET USA
# ═══════════════════════════════════════════════════════════════════════════════

PREMARKET_SYMBOLS = {
    "SPY":     {"name": "S&P 500",      "emoji": "📊", "yf": "SPY",       "group": "futures"},
    "NASDAQ":  {"name": "Nasdaq 100",   "emoji": "📈", "yf": "^IXIC",     "group": "futures"},
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



async def cmd_updatesite(u, c):
    if not await check_auth(u): return
    m = await u.message.reply_text("🔄 Updating xenosfinance.com...")
    try:
        news   = fetch_news_for_brief(max_items=12)
        prices = fetch_prices_for_brief()
        html = generate_news_html(news, prices)
        if html is None:
            logger.error('❌ generate_news_html returned None — template missing markers, push skipped')
            return
        ok   = push_to_github(html)
        if ok:
            await m.edit_text(
                "✅ <b>Site updated!</b>\n\nWait 1–2 minutes for GitHub Pages deploy.",
                parse_mode="HTML"
            )
        else:
            await m.edit_text("❌ GitHub push failed — check GITHUB_TOKEN in logs")
    except Exception as e:
        logger.error(f"updatesite: {e}", exc_info=True)
        await m.edit_text(f"❌ Error: {str(e)[:150]}")


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

    prompt = f"""You are a senior institutional FX trader. Analyze the following technical data for {name} and generate ONE intraday trading signal.

TECHNICAL DATA — {now_str}
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

INSTRUCTIONS:
- ALWAYS generate a signal — if the setup is weak use CONFIDENCE: LOW
- Determine direction from EMA alignment, MACD, RSI and H4 bias
- SL: place just beyond the nearest swing high/low or BB band — use 0.5x to 2.0x ATR as guide
- TP1: 1.0x to 1.5x ATR from entry
- TP2: 2.0x to 3.0x ATR from entry
- Only reply NO_SIGNAL if price data is clearly corrupt (all zeros or identical values)

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
NOTE: [max 1 sentence of context]"""

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
            f"⚪ <b>NO SIGNAL — {mkt['emoji']} {mkt['name']}</b>\n"
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
        f"<b>📊 FOREX INTRADAY SIGNAL</b>\n"
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

        await m.edit_text(f"🤖 Generating AI signal for {mkt['name']}...")
        ai_resp = generate_signal_ai(s, ta)

        signal_txt = fmt_signal(s, ta, ai_resp)
        await send_channel(signal_txt)
        await m.edit_text(f"✅ Signal {mkt['name']} sent to channel!")

    except Exception as e:
        logger.error(f"signal: {e}", exc_info=True)
        await m.edit_text(f"❌ Error: {str(e)[:100]}")


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
            "SPY": "SPY", "NASDAQ": "^IXIC", "DJI": "^DJI",
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

        eq_block = f"""S&P 500: {fmt_d(data.get('SPY'), 2, '$')}
Nasdaq: {fmt_d(data.get('NASDAQ'), 0)}
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

        prompt = f"""You are the chief macro strategist at a major institutional investment bank.
Generate a COMPLETE institutional market briefing for the "{session}" session.
Date: {now_str}

DATI LIVE:
=== FOREX ===
{fx_block}

=== EQUITY ===
{eq_block}

=== COMMODITIES ===
{comm_block}

=== CRYPTO ===
{crypto_block}

Write the briefing IN ENGLISH, professional institutional style. EXACT structure:

🌍 Global Market Briefing — {session}
[1 introductory paragraph on global sentiment, macro context, session drivers]

📊 FOREX — Currency Strength
[Currency ranking from strongest to weakest with intraday %, flow analysis]

💱 Key Currency Pairs
[3-4 key pairs with bias and technical context — 2-3 lines each]

💰 FX Flows & Positioning
[3-4 bullets on flows, positioning, hedges]

📈 EQUITIES — Indices
[Index ranking with performance, sector analysis, US vs Europe sentiment]

🛢️ COMMODITIES
[Gold, Oil, Silver, Gas — key levels, bias, fundamental drivers]

₿ CRYPTO
[BTC: exact price, 24h change, key support/resistance, sentiment
ETH: exact price, 24h change, ETH/BTC ratio, outlook
XRP, SOL, DOGE: brief note on top mover with exact price]

🎯 Intraday Trade Ideas
📈 LONG — [3-4 ideas with pair/asset and brief rationale]
📉 SHORT — [3-4 ideas with pair/asset and brief rationale]

📅 Today's Macro Drivers
[Macro data, Fed/ECB events, yields — to monitor]

MANDATORY RULES:
- Everything in professional English
- Use EXACT prices from the data
- NO asterisks, NO ** markdown
- Investment bank authoritative tone
- Maximum 500 words — cover all sections completely"""

        result = None
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": "claude-sonnet-4-5", "max_tokens": 1500,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=60
            )
            res = r.json()
            if "content" in res and res["content"]:
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
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            import hashlib as _hl
            _ck = "outlook_" + _hl.md5(str(datetime.now()).encode()).hexdigest()[:8]
            c.bot_data[_ck] = {"text": result, "label": "Global Markets Brief", "now_str": now_str}
            _kb = InlineKeyboardMarkup([[InlineKeyboardButton("📝 Pubblica su XenosBlog", callback_data=f"pub_brief:{_ck}")]])
            await m.edit_text(f"✅ Inviato al canale! Pubblica sul blog?", reply_markup=_kb)
        except Exception as _ekb:
            logger.warning(f"blog btn outlook: {_ekb}")
            await m.edit_text("✅ Sent to channel!")

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

        futures_block = f"""S&P 500 Futures (SPY): {fmt_q('SPY')}
Nasdaq Futures: {fmt_q('NASDAQ', 0, '')}
Dow Jones Futures: {fmt_q('DJI', 0, '')}
VIX: {fmt_q('VIX', 2, '')}"""

        movers_block = f"""NVDA: {fmt_q('NVDA')} | AAPL: {fmt_q('AAPL')} | MSFT: {fmt_q('MSFT')}
META: {fmt_q('META')} | AMZN: {fmt_q('AMZN')} | TSLA: {fmt_q('TSLA')}
GOOGL: {fmt_q('GOOGL')} | AMD: {fmt_q('AMD')}
JPM: {fmt_q('JPM')} | GS: {fmt_q('GS')}"""

        macro_block = f"""Gold: {fmt_q('GOLD')} | Oil WTI: {fmt_q('OIL')}
Bitcoin: {fmt_q('BTCUSD', 0)} | EUR/USD: {fmt_q('EURUSD', 4, '')} | USD/JPY: {fmt_q('USDJPY', 4, '')}"""

        news_block = "\n".join([f"  - {n['title']}" for n in news[:8]]) or "  No news available"

        prompt = f"""You are a senior US equity strategist at an institutional trading desk.
Write a professional PRE-MARKET BRIEF for the US session on {now_str}.

FUTURES & INDICES:
{futures_block}

TOP MOVERS (pre-market):
{movers_block}

MACRO:
{macro_block}

OVERNIGHT NEWS:
{news_block}

MANDATORY STRUCTURE — professional English, max 260 words:

🌅 Pre-Market Overview — {now_str}
[2-3 paragraphs: overall futures sentiment, overnight drivers from Asia/Europe, key macro backdrop]

📊 Index Futures Analysis
[S&P 500, Nasdaq, Dow — exact levels, key support/resistance, what to watch at open]

🎯 Top Pre-Market Movers
[5-6 stocks with specific % moves, catalyst (earnings/upgrade/news), trading implication]

🏦 Sector Rotation & Theme
[Which sectors are leading/lagging pre-market, AI/tech vs defensives, financials]

📰 Key Catalysts Today
[Earnings releases, macro data, Fed speakers, geopolitical events — exact times ET]

⚠️ Risk Factors
[2-3 specific risks that could change the open scenario]

RULES: Professional English institutional tone. EXACT prices from data. NO asterisks. NO markdown. Max 260 words."""

        result = None
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": "claude-sonnet-4-5", "max_tokens": 1000,
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
            await m.edit_text(f"✅ Inviato al canale! Pubblica sul blog?", reply_markup=_kb)
        except Exception as _ekb:
            logger.warning(f"blog btn premarket: {_ekb}")
            await m.edit_text("✅ Sent to channel!")

    except Exception as e:
        logger.error(f"premarket: {e}", exc_info=True)
        await m.edit_text(f"❌ Error: {str(e)[:100]}")


async def cmd_forex(u, c):
    if not await check_auth(u): return
    m = await u.message.reply_text("\U0001f4b1 \u0413\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u044f FX-\u0431\u0440\u0438\u0444\u0430...")
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
            f"You are the chief FX strategist at a major investment bank.\n"
            f"Write a professional editorial FX BRIEF IN ENGLISH. Date: {now_str} | Session: {session}\n\n"
            f"LIVE FX DATA:\n\n=== FX MAJOR ===\n{majors}\n\n=== JPY CROSSES ===\n{jpy_cx}\n\n=== EUR CROSSES ===\n{eur_cx}\n\n=== OTHER CROSSES ===\n{oth_cx}\n\n"
            f"USD Strength intraday: {usd_str:+.3f} ({usd_label})\n\n"
            "MANDATORY STRUCTURE — max 280 words, style: Bloomberg/Reuters FX:\n\n"
            f"Headline: Global FX Overview — {session}\n"
            "[dominant macro narrative driving the dollar, risk sentiment]\n\n"
            "Section Currency Strength: ranking from strongest to weakest with intraday % and flow analysis\n\n"
            "Section FX Majors — key pairs: analysis of all 7 majors with levels and bias (2-3 lines each)\n\n"
            "Section FX Crosses — rotation: 4-5 most significant JPY/EUR/GBP crosses\n\n"
            "Section Flows and Positioning: carry trade, hedging, seasonal factors (3-4 bullets)\n\n"
            "Section Trade Ideas intraday:\nLONG: [3 pairs with rationale]\nSHORT: [3 pairs with rationale]\n\n"
            "Section Macro Drivers today: data, central banks, events\n\n"
            "Section Risks: 2-3 specific risks\n\n"
            "RULES: professional English Bloomberg/Reuters style, EXACT prices from data, NO asterisks NO markdown, min 550 words"
        )
        await m.edit_text("\U0001f916 AI \u043f\u0438\u0448\u0435\u0442 FX-\u0431\u0440\u0438\u0444...")
        result = None
        if ANTHROPIC_API_KEY:
            try:
                rr = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
                    json={"model":"claude-sonnet-4-5","max_tokens":1100,
                          "messages":[{"role":"user","content":prompt}]},
                    timeout=60
                )
                res = rr.json()
                if "content" in res and res["content"]:
                    result = strip_bold(res["content"][0]["text"])
            except Exception as e:
                logger.error(f"forex AI: {e}")
        if not result:
            await m.edit_text("\u274c AI \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d"); return
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
            await m.edit_text(f"✅ Inviato al canale! Pubblica sul blog?", reply_markup=_kb)
        except Exception as _ekb:
            logger.warning(f"blog btn forex: {_ekb}")
            await m.edit_text("✅ Sent to channel!")
    except Exception as e:
        logger.error(f"forex: {e}", exc_info=True)
        await m.edit_text(f"\u274c \u041e\u0448\u0438\u0431\u043a\u0430: {str(e)[:100]}")

# ── 2. SOSTITUISCI cmd_crypto ─────────────────────────────────────────────────
async def cmd_crypto(u, c):
    if not await check_auth(u): return
    m = await u.message.reply_text("\u20bf \u0413\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u044f \u043a\u0440\u0438\u043f\u0442\u043e-\u0431\u0440\u0438\u0444\u0430...")
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
            "You are the chief crypto strategist at an institutional hedge fund specializing in digital assets.\n"
            f"Write a professional editorial CRYPTO BRIEF IN ENGLISH. Date: {now_str}\n\n"
            f"LIVE CRYPTO DATA:\n\n=== LAYER 1 BLUE CHIP ===\n{l1}\n\n=== ALTCOINS L1/L2 ===\n{l2}\n\n=== OTHERS ===\n{l3}\n\n{eth_btc}\n"
            f"BTC Sentiment: {'BULL >1%' if btc_chg > 1 else 'BEAR <-1%' if btc_chg < -1 else 'NEUTRAL'}\n\n"
            "MANDATORY STRUCTURE — max 260 words, style: Bloomberg Crypto / CoinDesk institutional:\n\n"
            "Headline: Crypto Markets — Session Overview\n"
            "[overall sentiment, BTC dominance, institutional flows, correlation with TradFi]\n\n"
            "Section Bitcoin — dominant narrative: detailed BTC analysis with levels\n\n"
            "Section Ethereum and DeFi: ETH vs BTC, staking, Layer 2\n\n"
            "Section Altcoins — capital rotation: L1s (SOL/ADA/AVAX), XRP, meme coins\n\n"
            "Section On-chain and Sentiment: fear/greed, funding rates, liquidations\n\n"
            "Section Trade Ideas:\nLONG: [3 assets with rationale]\nSHORT/AVOID: [2-3 with rationale]\n\n"
            "Section Risks: 2-3 key risks\n\n"
            "RULES: professional English Bloomberg Crypto, EXACT prices, NO asterisks, NO markdown, max 260 words"
        )
        await m.edit_text("\U0001f916 AI \u043f\u0438\u0448\u0435\u0442 \u043a\u0440\u0438\u043f\u0442\u043e-\u0431\u0440\u0438\u0444...")
        result = None
        if ANTHROPIC_API_KEY:
            try:
                rr = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
                    json={"model":"claude-sonnet-4-5","max_tokens":1000,
                          "messages":[{"role":"user","content":prompt}]},
                    timeout=60
                )
                res = rr.json()
                if "content" in res and res["content"]:
                    result = strip_bold(res["content"][0]["text"])
            except Exception as e:
                logger.error(f"crypto AI: {e}")
        if not result:
            await m.edit_text("\u274c AI \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d"); return
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
            await m.edit_text(f"✅ Inviato al canale! Pubblica sul blog?", reply_markup=_kb)
        except Exception as _ekb:
            logger.warning(f"blog btn crypto: {_ekb}")
            await m.edit_text("✅ Sent to channel!")
    except Exception as e:
        logger.error(f"crypto: {e}", exc_info=True)
        await m.edit_text(f"\u274c \u041e\u0448\u0438\u0431\u043a\u0430: {str(e)[:100]}")

# ── 3. SOSTITUISCI cmd_commodities ───────────────────────────────────────────
async def cmd_commodities(u, c):
    if not await check_auth(u): return
    m = await u.message.reply_text("\U0001f6e2\ufe0f \u0413\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u044f \u0431\u0440\u0438\u0444\u0430 \u043f\u043e \u0441\u044b\u0440\u044c\u0435\u0432\u044b\u043c \u0440\u044b\u043d\u043a\u0430\u043c...")
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

        metals = "\n".join([cl("GOLD","\u0417\u043e\u043b\u043e\u0442\u043e XAU","/oz"),cl("SILVER","\u0421\u0435\u0440\u0435\u0431\u0440\u043e XAG","/oz"),
                             cl("PLATINUM","\u041f\u043b\u0430\u0442\u0438\u043d\u0430","/oz"),cl("PALLADIUM","\u041f\u0430\u043b\u043b\u0430\u0434\u0438\u0439","/oz"),cl("COPPER","\u041c\u0435\u0434\u044c","/lb")])
        energy = "\n".join([cl("OIL","\u041d\u0435\u0444\u0442\u044c WTI","/bbl"),cl("BRENT","Brent","/bbl"),cl("NGAS","\u041f\u0440\u0438\u0440\u043e\u0434\u043d\u044b\u0439 \u0433\u0430\u0437","/MMBtu")])
        agri  = "\n".join([cl("WHEAT","\u041f\u0448\u0435\u043d\u0438\u0446\u0430","/bu"),cl("CORN","\u041a\u0443\u043a\u0443\u0440\u0443\u0437\u0430","/bu"),cl("SOYBEANS","\u0421\u043e\u044f","/bu")])

        oil_d = data.get("OIL"); brent_d = data.get("BRENT")
        spread_str = ""
        if oil_d and brent_d:
            spread_str = f"Spread Brent-WTI: ${brent_d['p']-oil_d['p']:.2f}/bbl"

        prompt = (
            "You are the chief commodities strategist at a major investment bank.\n"
            f"Write a professional editorial COMMODITIES BRIEF IN ENGLISH. Date: {now_str}\n\n"
            f"LIVE COMMODITIES DATA:\n\n=== PRECIOUS METALS ===\n{metals}\n\n=== ENERGY ===\n{energy}\n{spread_str}\n\n=== AGRICULTURE ===\n{agri}\n\n"
            "MANDATORY STRUCTURE — max 260 words, style: Goldman Sachs Commodities Research:\n\n"
            "Headline: Commodities Markets — Session Overview\n"
            "[macro context: commodities supercycle, dollar impact, risk sentiment]\n\n"
            "Section Precious Metals: Gold (real rates, CB, safe haven), Silver, Platinum/Palladium, Copper (growth barometer)\n\n"
            "Section Energy: WTI and Brent (supply/demand, OPEC+, geopolitics), Brent-WTI spread, Natural Gas\n\n"
            "Section Agriculture: wheat, corn, soy — climate, exports\n\n"
            "Section Trade Ideas:\nLONG: [3 assets]\nSHORT/HEDGE: [2-3 assets]\n\n"
            "Section Key Risks: 2-3 key risks\n\n"
            "RULES: professional English Goldman Sachs / JPMorgan Commodities style, EXACT prices, NO asterisks, NO markdown, max 260 words"
        )
        await m.edit_text("\U0001f916 AI \u043f\u0438\u0448\u0435\u0442 commodities-\u0431\u0440\u0438\u0444...")
        result = None
        if ANTHROPIC_API_KEY:
            try:
                rr = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
                    json={"model":"claude-sonnet-4-5","max_tokens":1000,
                          "messages":[{"role":"user","content":prompt}]},
                    timeout=60
                )
                res = rr.json()
                if "content" in res and res["content"]:
                    result = strip_bold(res["content"][0]["text"])
            except Exception as e:
                logger.error(f"comm AI: {e}")
        if not result:
            await m.edit_text("\u274c AI \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d"); return
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
            await m.edit_text(f"✅ Inviato al canale! Pubblica sul blog?", reply_markup=_kb)
        except Exception as _ekb:
            logger.warning(f"blog btn commod: {_ekb}")
            await m.edit_text("✅ Sent to channel!")
    except Exception as e:
        logger.error(f"comm: {e}", exc_info=True)
        await m.edit_text(f"\u274c \u041e\u0448\u0438\u0431\u043a\u0430: {str(e)[:100]}")

# ── 4. SOSTITUISCI cmd_equity ─────────────────────────────────────────────────
async def cmd_equity(u, c):
    if not await check_auth(u): return
    m = await u.message.reply_text("\U0001f4ca \u0413\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u044f equity-\u0431\u0440\u0438\u0444\u0430...")
    try:
        import concurrent.futures
        eq_symbols = {
            "SPY":"SPY","NASDAQ":"^IXIC","DJI":"^DJI","RUT":"^RUT","VIX":"^VIX",
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

        us_block  = "\n".join([el("SPY","S&P 500",2,"$"),el("NASDAQ","Nasdaq",0),el("DJI","Dow Jones",0),el("RUT","Russell 2000",2,"$")])
        vix_d = data.get("VIX")
        vix_str = ""
        if vix_d:
            vl = vix_d["p"]
            vix_str = f"VIX: {vl:.2f} — {'PAURA' if vl>25 else 'ELEVATA' if vl>20 else 'NORMALE' if vl>15 else 'BASSA'}"
        eu_block  = "\n".join([el("DAX","DAX (DE)",0),el("FTSE","FTSE 100 (UK)",0),el("CAC","CAC 40 (FR)",0),el("MIB","FTSE MIB (IT)",0),el("IBEX","IBEX 35 (ES)",0)])
        asia_block= "\n".join([el("NKY","Nikkei 225",0),el("HSI","Hang Seng",0),el("CSI300","CSI 300",0)])
        tech_block= "\n".join([el("NVDA","Nvidia",2,"$"),el("AAPL","Apple",2,"$"),el("MSFT","Microsoft",2,"$"),
                                el("META","Meta",2,"$"),el("AMZN","Amazon",2,"$"),el("TSLA","Tesla",2,"$"),el("GOOGL","Alphabet",2,"$")])

        spy_d = data.get("SPY"); ndq_d = data.get("NASDAQ")
        avg_us = ((spy_d["ch"] if spy_d else 0)+(ndq_d["ch"] if ndq_d else 0))/2
        regime = "\u0420\u0418\u0421\u041a \u0412\u041a\u041b\u042e\u0427\u0401\u041d" if avg_us > 0.5 else "\u0423\u0425\u041e\u0414 \u041e\u0422 \u0420\u0418\u0421\u041a\u0410" if avg_us < -0.5 else "\u041f\u0415\u0420\u0415\u0425\u041e\u0414\u041d\u042b\u0419"

        hour = now.hour
        if 9 <= hour < 13:    session = "\u0415\u0432\u0440\u043e\u043f\u0435\u0439\u0441\u043a\u0430\u044f \u0441\u0435\u0441\u0441\u0438\u044f"
        elif 13 <= hour < 17: session = "\u041f\u0435\u0440\u0435\u0441\u0435\u0447\u0435\u043d\u0438\u0435 \u0415\u0432\u0440\u043e\u043f\u0430-\u041d\u044c\u044e-\u0419\u043e\u0440\u043a"
        elif 17 <= hour < 22: session = "\u0421\u0435\u0441\u0441\u0438\u044f \u041d\u044c\u044e-\u0419\u043e\u0440\u043a"
        else:                 session = "\u0410\u0437\u0438\u0430 / Pre-market"

        prompt = (
            f"You are the chief global equity strategist at a major investment bank.\n"
            f"Write a professional editorial EQUITY BRIEF IN ENGLISH. Date: {now_str} | Session: {session}\n\n"
            f"LIVE EQUITY DATA:\n\n=== USA ===\n{us_block}\n{vix_str}\n\n=== EUROPE ===\n{eu_block}\n\n=== ASIA ===\n{asia_block}\n\n=== MEGA CAP TECH ===\n{tech_block}\n\n"
            f"Regime: {regime} (S&P/Nasdaq avg: {avg_us:+.2f}%)\n\n"
            "MANDATORY STRUCTURE — max 280 words, style: Morgan Stanley / Goldman Sachs Equity Research:\n\n"
            f"Headline: Global Equities — Session Overview\n"
            "[global risk sentiment, what is driving markets — Fed, macro, geopolitics, earnings]\n\n"
            "Section USA — S&P 500, Nasdaq, Dow: breadth, leaders/laggards, Russell 2000, VIX\n\n"
            "Section Europe — DAX, FTSE, CAC, MIB: European divergence, ECB, sector rotation\n\n"
            "Section Asia — Nikkei, HSI, CSI300: Japan (JPY), China (stimulus)\n\n"
            "Section Mega-Cap Tech — AI trade: NVDA, AAPL, MSFT, META, AMZN, TSLA\n\n"
            "Section Sector Rotation: Growth vs Value, Tech vs Financials vs Energy vs Defensives\n\n"
            "Section Trade Ideas:\nLONG: [3 ideas with rationale]\nSHORT/HEDGE: [2-3 ideas]\n\n"
            "Section Key Risks: 3 specific risks\n\n"
            "RULES: professional English Goldman Sachs / MS equity note, EXACT prices, NO asterisks, NO markdown, max 280 words"
        )
        await m.edit_text("\U0001f916 AI \u043f\u0438\u0448\u0435\u0442 equity-\u0431\u0440\u0438\u0444...")
        result = None
        if ANTHROPIC_API_KEY:
            try:
                rr = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
                    json={"model":"claude-sonnet-4-5","max_tokens":1100,
                          "messages":[{"role":"user","content":prompt}]},
                    timeout=60
                )
                res = rr.json()
                if "content" in res and res["content"]:
                    result = strip_bold(res["content"][0]["text"])
            except Exception as e:
                logger.error(f"equity AI: {e}")
        if not result:
            await m.edit_text("\u274c AI \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d"); return
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
            await m.edit_text(f"✅ Inviato al canale! Pubblica sul blog?", reply_markup=_kb)
        except Exception as _ekb:
            logger.warning(f"blog btn equity: {_ekb}")
            await m.edit_text("✅ Sent to channel!")
    except Exception as e:
        logger.error(f"equity: {e}", exc_info=True)
        await m.edit_text(f"\u274c \u041e\u0448\u0438\u0431\u043a\u0430: {str(e)[:100]}")
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
MKO_SCORE_STRONG  = 6   # ≥6/10 → STRONG signal, push to channel
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

    return {
        "price": price, "atr": atr, "rsi": rsi, "stoch_rsi": stoch_rsi,
        "ema20": ema20, "ema50": ema50, "ema200": ema200,
        "vwap": vwap, "above_vwap": price > vwap,
        "bb_upper": bb_upper, "bb_lower": bb_lower, "bb_mid": bb_mid, "bb_width": bb_width,
        "macd_hist": macd_hist, "macd_bull": macd_hist > 0,
        "ichimoku": ichi,
        "vol_expanding": vol_expanding, "vol_climax": vol_climax, "vol_ratio": vol_mean5 / (vol_mean20 + 1e-9),
        "last_sh": last_sh, "last_sl": last_sl,
        "trend_up":   ema20 > ema50 and price > ema20,
        "trend_down": ema20 < ema50 and price < ema20,
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

    # ── Layer 5: RSI (1 pt) ──────────────────────────────────────
    rsi = ind["rsi"]
    if 40 < rsi < 65:
        bull_pts.append(f"RSI: {rsi:.0f} — momentum zone (40-65)")
    elif rsi < 35:
        bull_pts.append(f"RSI: {rsi:.0f} — oversold, reversal watch")
    elif rsi > 65 and rsi < 80:
        bear_pts.append(f"RSI: {rsi:.0f} — overbought distribution")
    elif rsi >= 80:
        bear_pts.append(f"RSI: {rsi:.0f} — extreme overbought")

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

    # ── Determine direction and score ────────────────────────────
    bull_score = len(bull_pts)
    bear_score = len(bear_pts)

    if bull_score >= bear_score + 2:
        direction = "BUY"
        score = min(10, bull_score)
        breakdown = bull_pts
    elif bear_score >= bull_score + 2:
        direction = "SELL"
        score = min(10, bear_score)
        breakdown = bear_pts
    else:
        direction = None
        score = 0
        breakdown = []

    return {
        "direction": direction,
        "score": score,
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

    prompt = f"""You are a senior futures desk analyst at a tier-1 investment bank.
Write a concise institutional commentary (120-180 words, NO bullet points, plain paragraphs) for this trade setup.

ASSET: {asset['name']} ({sym})
DIRECTION: {scoring['direction']}
SCORE: {scoring['score']}/10 — Confirmed signals: {', '.join(scoring['breakdown'][:4])}

MARKET STRUCTURE:
  Price: {ind['price']:.{asset['decimals']}f} | ATR: {ind['atr']:.{asset['decimals']}f}
  EMA20/50/200: {ind['ema20']:.{asset['decimals']}f} / {ind['ema50']:.{asset['decimals']}f} / {ind['ema200']:.{asset['decimals']}f}
  RSI: {ind['rsi']:.1f} | MACD hist: {ind['macd_hist']:+.{asset['decimals']}f}
  VWAP: {ind['vwap']:.{asset['decimals']}f} ({'above' if ind['above_vwap'] else 'below'})
  Ichimoku: {'above cloud, TK bull' if ichi.get('above_cloud') and ichi.get('tk_cross_bull') else 'below cloud' if ichi.get('below_cloud') else 'in cloud'}
  {ob_str} | {oi_str}

LEVELS:
  Entry: {levels['entry']:.{asset['decimals']}f}
  Stop Loss: {levels['sl']:.{asset['decimals']}f}
  TP1: {levels['tp1']:.{asset['decimals']}f} (R:R 1:{levels['rr1']:.1f})
  TP2: {levels['tp2']:.{asset['decimals']}f}

Focus on: why this setup has institutional conviction, key invalidation factors,
and the primary catalyst for the move. No markdown, no asterisks, plain text only."""

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-5",
                "max_tokens": 350,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=25,
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
    sent_str  = "Risk-ON" if ind["above_vwap"] and ind["trend_up"] else "Risk-OFF" if not ind["above_vwap"] and ind["trend_down"] else "Neutral"

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
        f"Momentum    {mom_str}\n"
        f"Volatility  {vol_str}\n"
        f"Sentiment   {sent_str}\n\n"
    )

    if commentary:
        # Show commentary as SCENARIO section
        msg += f"SCENARIO\n{commentary}\n\n"

    msg += (
        f"SIGNAL LEVELS\n"
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
        f"VWAP        Price {'above' if ind['above_vwap'] else 'below'} {'✓' if ind['above_vwap'] == (dir_label == 'LONG') else '✗'}\n"
        f"Ichimoku    {ichi_str}\n"
        f"Trend       EMA20 {'>' if ind['ema20'] > ind['ema50'] else '<'} EMA50\n"
        f"Cloud       {cloud_str}\n"
    )

    if ob_line:
        msg += f"{ob_line}\n"
    if oi_line:
        msg += f"{oi_line}\n"

    msg += (
        f"\nCONFIRMED SIGNALS\n"
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

    commentary = mko_claude_commentary(sym, asset, ind, scoring, levels, ob_imb, oi_data)
    message    = mko_format_signal(sym, asset, ind, scoring, levels, ob_imb, oi_data, commentary)

    return {
        "sym": sym, "asset": asset, "score": scoring["score"],
        "direction": scoring["direction"], "levels": levels,
        "message": message, "ind": ind,
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
            f'MKO SIGNAL — {emoji} {name}  ·  {direction}  ·  {datetime.utcnow().strftime("%d %b %Y %H:%M UTC")}',
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

    idea = {
        "id":           idea_id,
        "timestamp":    timestamp,
        "ticker":       sym,
        "name":         asset.get("name", sym),
        "emoji":        asset.get("emoji", "📊"),
        "timeframe":    "1H",
        "wave_num":     "?",
        "wave_icon":    "🌊",
        "wave_phase":   "MKO Signal",
        "bias":         direction,
        "confidence":   confidence,
        "price":        price_now,
        "target":       round(tp1_raw, dec),
        "invalidation": round(sl_raw, dec),
        "analysis":     _strip_html(result.get("message", ""))[:500],
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


# Dedup cache: {sym_direction: timestamp} — evita segnali duplicati entro 4h
_mko_sent: dict = {}
MKO_DEDUP_TTL = 12 * 60 * 60  # 12 ore in secondi — stesso segnale non ripetuto per 12h

async def mko_auto_scan():
    """
    Scansione automatica ogni MKO_SCAN_INTERVAL minuti.
    Pubblica sul canale solo i segnali con score >= MKO_SCORE_STRONG.
    Stesso segnale (sym+direction) non viene ripubblicato entro 24 ore.
    """
    await asyncio.sleep(30)  # attendi avvio bot
    logger.info("🔍 MKO Auto-scan started")

    while True:
        try:
            logger.info("MKO: scanning all assets...")
            found = 0
            MAX_SIGNALS_PER_SCAN = 5  # max segnali per ciclo — evita flooding
            now = time.time()  # use real unix timestamp for persistent dedup
            for sym in MKO_ASSETS:
                try:
                    result = mko_analyze(sym)
                    if result and result["score"] >= MKO_SCORE_STRONG:
                        key = f"{sym}_{result['direction']}"
                        last_sent = _mko_sent.get(key, 0)
                        if now - last_sent < MKO_DEDUP_TTL:
                            logger.info(f"MKO SKIP (dedup): {sym} {result['direction']} — già inviato {(now-last_sent)/3600:.1f}h fa")
                            continue
                        if found >= MAX_SIGNALS_PER_SCAN:
                            logger.info(f"MKO: max signals per scan reached ({MAX_SIGNALS_PER_SCAN}) — stopping")
                            break
                        logger.info(f"MKO SIGNAL: {sym} {result['direction']} score={result['score']}")
                        msg_id = await send_channel(result["message"])
                        _mko_sent[key] = now
                        found += 1
                        # Salva anche su Trading Ideas (GitHub) con link Telegram
                        try:
                            tg_url = f"https://t.me/xenosfin/{msg_id}" if isinstance(msg_id, int) else ""
                            result["tg_url"] = tg_url
                            await asyncio.get_event_loop().run_in_executor(None, _mko_push_idea, sym, result)
                        except Exception as e_push:
                            logger.error(f"❌ MKO push idea FAILED {sym}: {e_push}", exc_info=True)
                        await asyncio.sleep(3)  # anti-flood
                except Exception as e:
                    logger.warning(f"MKO scan {sym}: {e}")
                await asyncio.sleep(1)  # rate limit tra asset
            logger.info(f"MKO scan complete — {found} signals published")
        except Exception as e:
            logger.error(f"MKO auto-scan error: {e}")

        await asyncio.sleep(MKO_SCAN_INTERVAL * 60)


# ── /futures command ──────────────────────────────────────────────────────────
async def cmd_futures(u, c):
    """
    /futures — scansiona tutti gli asset MKO e mostra segnali validi (score ≥ 5).
    /futures BTC — analizza solo Bitcoin.
    /futures scan — forza full scan e pubblica i STRONG sul canale.
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
                await send_channel(result["message"])
                await m.edit_text(
                    f"✅ {asset['name']} signal sent ({result['direction']}, score {result['score']}/10)"
                )
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
        f"📊 <b>XENOS MKO SCAN — {len(results)} signal{'s' if len(results)>1 else ''}</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        + "\n".join(lines) +
        f"\n<code>━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        f"<i>Publishing full signals to channel...</i>"
    )
    await m.edit_text(summary, parse_mode="HTML")

    # Publish each signal to channel
    for r in results:
        if force_scan or r["score"] >= MKO_SCORE_STRONG:
            await send_channel(r["message"])
            await asyncio.sleep(2)
        elif r["score"] >= MKO_SCORE_VALID:
            # Score valido ma non strong: invia solo all'owner in DM
            try:
                await u.message.reply_text(
                    f"<i>Score {r['score']}/10 — sent to channel (valid setup)</i>",
                    parse_mode="HTML"
                )
                await send_channel(r["message"])
            except Exception:
                pass
            await asyncio.sleep(2)


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

        intro      = sections[0]["content"][:400] if sections else clean[:400]
        word_count = len(clean.split())
        read_time  = f"{max(2, _math.ceil(word_count/200))} min read"
        sentences  = [s.strip() for s in _re.split(r"[.!?]", clean) if len(s.strip()) > 40]
        quote      = sentences[0][:200] if sentences else label
        excerpt    = intro[:120].strip() + "..."
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
            "conclusion": sections[-1]["content"][:300] if sections else "",
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
        "Trend Following", "Mean Reversion", "Order Blocks", "Fair Value Gaps"
    ],
    "fundamental": [
        "Inflation & CPI", "Interest Rates & Fed", "NFP Report",
        "GDP & Recession", "Soft vs Hard Landing", "Oil & Geopolitics",
        "Gold as Safe Haven", "DXY Dollar Index", "Bond Yields",
        "Earnings Season", "Central Bank Policies", "Liquidity Cycles",
        "ECB Policy", "Global Macro Cycle"
    ],
    "psychology": [
        "Fear & Greed", "Revenge Trading", "FOMO", "Patience & Discipline",
        "Emotional Control", "Trading Routine", "Consistency", "Loss Management",
        "Overconfidence", "Trading Journal"
    ],
    "risk": [
        "Capital Preservation", "Risk Per Trade", "Portfolio Exposure",
        "Stop Loss Discipline", "Max Drawdown", "Money Management",
        "Correlation Risk", "Diversification"
    ],
    "leverage": [
        "Leverage Basics", "Margin Call", "Free vs Used Margin",
        "Liquidation Risk", "Position Sizing", "Overexposure",
        "CFD vs Futures Margin", "Funding Costs"
    ],
    "terminology": [
        "Bull & Bear Market", "Liquidity & Spread", "Slippage", "Hedging",
        "Options & Futures", "ETF Mechanics", "Market Maker", "Institutional Flow",
        "Long/Short Squeeze", "Open Interest", "Contango & Backwardation",
        "Yield Curve", "Risk-on / Risk-off"
    ],
    "advanced": [
        "COT Report", "Gamma Exposure", "Options Flow", "Liquidity Grabs",
        "Smart Money Concepts", "Intermarket Analysis", "Yield Curve Inversion",
        "Dollar Liquidity", "Central Bank Balance Sheets", "Dark Pools"
    ]
}

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
    """Returns topics for the given date, rotating automatically."""
    day       = date.timetuple().tm_yday
    pri_cat   = _ED_MAIN_CATS[day % len(_ED_MAIN_CATS)]
    sec_cat   = _ED_MAIN_CATS[(day + 1) % len(_ED_MAIN_CATS)]
    pri_top   = _ED_TOPICS[pri_cat][(day + hash(pri_cat))   % len(_ED_TOPICS[pri_cat])]
    sec_top   = _ED_TOPICS[sec_cat][(day + hash(sec_cat))   % len(_ED_TOPICS[sec_cat])]
    risk_top  = _ED_TOPICS["risk"][day % len(_ED_TOPICS["risk"])]
    return pri_cat, pri_top, sec_cat, sec_top, risk_top


def _generate_daily_education(date=None):
    """Calls Claude API and returns the daily education text."""
    if date is None:
        date = datetime.now().date()
    pri_cat, pri_top, sec_cat, sec_top, risk_top = _ed_get_topics(date)
    user_msg = (
        f"Generate today's DAILY EDUCATIONAL CONTENT for {date.strftime('%A %d %B %Y')}.\n\n"
        f"SECTION 1 — {pri_cat.upper()}: Topic = \"{pri_top}\"\n"
        f"SECTION 2 — {sec_cat.upper()}: Topic = \"{sec_top}\"\n"
        f"SECTION 3 — DAILY TRADING TIPS: 3 practical tips relevant to current market conditions\n"
        f"SECTION 4 — RISK MANAGEMENT: Topic = \"{risk_top}\"\n\n"
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

async def _generate_weekly_trading_plan(context=None):
    """Genera il Weekly Trading Plan ogni lunedì alle 06:00 CET."""
    import datetime as _dt
    logger.info("📊 Weekly Trading Plan: generating...")

    if not ANTHROPIC_API_KEY:
        logger.warning("⚠️ Weekly Trading Plan: ANTHROPIC_API_KEY mancante"); return

    try:
        import anthropic as _ac
        client = _ac.Anthropic(api_key=ANTHROPIC_API_KEY)

        now = _dt.datetime.utcnow()
        week_start = now - _dt.timedelta(days=now.weekday())
        week_end   = week_start + _dt.timedelta(days=4)
        week_str   = f"{week_start.strftime('%d %b')} – {week_end.strftime('%d %b %Y')}"
        issue_num  = now.isocalendar()[1]

        prompt = f"""You are the XenosFinance senior analyst. Generate a professional Weekly Trading Plan for the week of {week_str}.

Search your knowledge for the most recent macro context and produce:

1. MACRO OUTLOOK (3-4 sentences: dominant macro themes, central bank stance, geopolitical risks)
2. ASSET ANALYSIS for each: WTI Crude Oil, Gold, EUR/USD, EUR/GBP, S&P 500, Bitcoin
   Per asset: EW structure, key support/resistance, directional bias, entry zone, SL, TP, R:R
3. ECONOMIC CALENDAR: top 5 high-impact events this week with expected market impact
4. EDITOR VIEW: 2-3 sentences of your personal directional conviction

Format with clear section headers. Professional institutional tone. Max 800 words."""

        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}]
        )
        plan_text = msg.content[0].text if msg.content else ""
        if not plan_text:
            logger.warning("Weekly Trading Plan: risposta AI vuota"); return

        logger.info("✅ Weekly Trading Plan generated")

        # ── Push to GitHub ────────────────────────────────────────────────────
        if GITHUB_TOKEN:
            import json as _json, base64 as _b64
            plan_data = {
                "week": week_str,
                "issue": f"Vol. {issue_num}, {now.year}",
                "generated": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "text": plan_text
            }
            path = "weekly_plan/latest.json"
            ideas, sha = _github_json_read(path)
            if ideas is None:
                sha = ""
            encoded = _b64.b64encode(_json.dumps(plan_data, ensure_ascii=False, indent=2).encode("utf-8")).decode("utf-8")
            import requests as _req
            api = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"
            headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
            payload = {"message": f"Weekly Trading Plan: {week_str}", "content": encoded, "committer": {"name": "XenosBot", "email": "bot@xenosfinance.com"}}
            if sha:
                payload["sha"] = sha
            r = _req.put(api, headers=headers, json=payload, timeout=30)
            if r.status_code in [200, 201]:
                logger.info("✅ Weekly Trading Plan pushed to GitHub")
            else:
                logger.error(f"❌ GitHub push failed: {r.status_code} {r.text[:200]}")

        # ── Send to Telegram channel ──────────────────────────────────────────
        truncated = plan_text[:3800]
        msg_text = f"📊 <b>XenosFinance Weekly Trading Plan</b>\nWeek of {week_str} · Edition #XF-WTP-{now.year}-{issue_num}\n\n{truncated}"
        await send_channel(msg_text)
        logger.info("✅ Weekly Trading Plan sent to Telegram")

    except Exception as e:
        logger.error(f"❌ Weekly Trading Plan error: {e}", exc_info=True)


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
    app.add_handler(CommandHandler("weeklyplan",        lambda u,c: asyncio.ensure_future(_generate_weekly_trading_plan())))

    logger.info("🚀 Bot started — waiting for commands...")
    logger.info(f"✅ MKO Engine: {len(MKO_ASSETS)} assets, auto-scan every {MKO_SCAN_INTERVAL}min, push threshold {MKO_SCORE_STRONG}/10")

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
            # Weekly Trading Plan — ogni lunedì alle 05:00 UTC (06:00 CET)
            application.job_queue.run_daily(
                _generate_weekly_trading_plan,
                time=_dt2.time(5, 0, tzinfo=_pytz.UTC),
                days=(0,),  # 0 = Monday
                name="weekly_trading_plan"
            )
            logger.info("✅ Weekly Trading Plan: scheduled every Monday 06:00 CET")
        else:
            logger.warning("⚠️ Daily Education: JobQueue not available. Add python-telegram-bot[job-queue] to requirements.txt. Manual /daily_education still works.")

    app.post_init = _post_init
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
