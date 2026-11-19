"""ews_engine.py — motore Elliott Wave del /ews (bot Telegram) usato dal sito.

GENERATO da xenosfinance-bot/bot.py con tools/sync_ews_engine.py: stesse funzioni del
/ews, copiate senza modifiche (tranne le etichette del timeframe), così sito e Telegram
contano le onde e disegnano il grafico nello stesso identico modo.
NON modificare a mano: correggere bot.py e rigenerare.
"""
import os, sys, json, logging, re, io, time, base64, hashlib
import numpy as np
import pandas as pd
import requests
from datetime import datetime, timedelta

logger = logging.getLogger("XenosWaves")

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import matplotlib.gridspec as gridspec
    import matplotlib.patheffects as mpe
    CHARTS_AVAILABLE = True
except Exception:
    CHARTS_AVAILABLE = False

# etichette del timeframe corrente (le imposta ew_server.py prima di ogni calcolo)
EWS_TF_TXT = "4H"
EWS_TF_CHART = "4h"

logger = logging.getLogger("XenosWaves")


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
    # 2026-10-25: per l'EW Morning Report (e /elliott DXY · DAX · SPX)
    "DXY":    {"name": "US Dollar Index",  "emoji": "💵", "yf": "DX-Y.NYB",  "cat": "index"},
    "DAX":    {"name": "DAX 40",           "emoji": "🇩🇪", "yf": "^GDAXI",   "cat": "equity"},
    "SPX":    {"name": "S&P 500 Index",    "emoji": "📊", "yf": "^GSPC",     "cat": "equity"},
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


CL_ROLL_BDAYS = 2


def _cl_front_contract(now=None):
    now = now or datetime.utcnow()
    codes = "FGHJKMNQUVXZ"
    def biz(d):
        return d.weekday() < 5 and not (d.month == 12 and d.day == 25) and not (d.month == 1 and d.day == 1)
    today = now.date()
    for k in range(1, 4):
        m0 = now.month - 1 + k
        cy, cm = now.year + m0 // 12, m0 % 12 + 1          # mese di consegna
        py, pm = (cy, cm - 1) if cm > 1 else (cy - 1, 12)   # mese precedente
        ref = datetime(py, pm, 25).date()
        while not biz(ref):
            ref -= timedelta(days=1)
        lt, n = ref, 0
        while n < 3:
            lt -= timedelta(days=1)
            if biz(lt):
                n += 1
        # 2026-10-20: roll negli ultimi giorni di vita del contratto (come Investing): il contratto in
        # scadenza è illiquido e prezza diverso; si passa al successivo CL_ROLL_BDAYS giorni lavorativi
        # prima dell'ultimo giorno di contrattazione (es. novembre: LTD 20/10 → dicembre dal 19/10).
        roll, n = lt, 0
        while n < CL_ROLL_BDAYS:
            roll -= timedelta(days=1)
            if biz(roll):
                n += 1
        if today <= roll:
            return f"CL{codes[cm - 1]}{str(cy)[-2:]}.NYM"
    return None


def yf_front(sym):
    """CL=F → contratto front month esplicito; ogni altro simbolo invariato."""
    if sym == "CL=F":
        try:
            return _cl_front_contract() or sym
        except Exception:
            return sym
    return sym


def _tv_anchor(yf):
    if yf.endswith("=F"):
        return "America/New_York", 18 * 60
    if yf.endswith("=X"):
        return "America/New_York", 17 * 60
    if yf in ("^NDX", "^DJI", "^GSPC", "SPY") or re.fullmatch(r"[A-Z]{1,5}(\.[A-Z])?", yf or ""):
        return "America/New_York", 9 * 60 + 30   # indici cash e azioni USA: sessione 09:30 New York
    if yf == "^GDAXI":
        return "Europe/Berlin", 9 * 60
    return None, 0


def resample_4h_tv(df1, yf):
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    tz, off = _tv_anchor(yf or "")
    if not tz:
        return df1.resample("4h", origin="epoch").agg(agg).dropna()
    idx = df1.index
    utc = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    loc = utc.tz_convert(tz).tz_localize(None)                     # ora locale della borsa
    sh = loc - pd.Timedelta(minutes=off)
    key_loc = sh.floor("4h") + pd.Timedelta(minutes=off)           # inizio candela, ora locale
    start_utc = (utc - (loc - key_loc)).tz_localize(None)          # inizio candela in UTC (naive come il resto)
    out = df1.groupby(start_utc).agg(agg).dropna()
    out.index.name = None
    return out


def fetch_data(symbol, days=365, interval="1d"):
    # FIX 2026-10: Yahoo non supporta interval="4h" (la richiesta falliva sempre →
    # pannello 4H e MTF 4H mai presenti). Scarico 1h e ricampiono su barre 4h UTC.
    if interval == "4h":
        df1 = fetch_data(symbol, days=days, interval="1h")
        if df1 is None or len(df1) == 0:
            return None
        df4 = resample_4h_tv(df1, MARKETS.get(symbol, {}).get("yf", ""))
        logger.info(f"✅ {symbol}: {len(df4)} bars (4h from 1h, TradingView session alignment)")
        return df4
    try:
        yf  = MARKETS[symbol]["yf"]
        end = int(datetime.now().timestamp())
        start = int((datetime.now() - timedelta(days=days)).timestamp())
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_front(yf)}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"},
                         params={"period1": start, "period2": end, "interval": interval}, timeout=15)
        d = r.json()
        # 2026-10-16: se il contratto WTI esplicito non risponde, si torna al continuo CL=F
        if yf_front(yf) != yf and not ((d.get("chart") or {}).get("result")):
            r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{yf}", headers={"User-Agent": "Mozilla/5.0"},
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


def identify_wave_degree(df):
    c = df["close"]
    r = (c.max()-c.min())/c.mean()*100
    if r>30:   return "Primary"
    elif r>15: return "Intermediate"
    elif r>7:  return "Minor"
    else:      return "Minute"


EW_ENGINE_RULES = {
    "w2":     (0.28, 0.786),
    "w3_ext": (1.0, 1.272, 1.618, 2.0, 2.618), "w3_tol": 0.15,
    "w4":     (0.15, 0.65),
    "b":      (0.236, 1.0),
}


EW_ENGINE_DEGREES = [("Minor", 4), ("Intermediate", 8), ("Primary", 16)]


EW_WAVE_LABELS = ["0", "1", "2", "3", "4", "5", "A", "B", "C"]


EW_W4_MIN_RETR = 0.236


EW_W4_MIN_TIME = 0.5


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
            # 2026-11-13: onda in corso oltre 4.236×W1 = grado sbagliato (la "1" è una sotto-onda)
            if not conf and ln(2, 3) > 4.236 * ln(0, 1):
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
            # 2026-11-13: una 5 in corso più lunga di 1.618×(0→3) non è una 5 di questo impulso
            # (test: "5" da 196 a 380 su un 0→3 di ~30 punti → conteggio rifiutato, si cerca il grado giusto)
            if not conf and ln(4, 5) > 1.618 * ln(0, 3):
                return False
            if conf:
                if not P[5] > P[3]:
                    return False
                if ln(2, 3) < ln(0, 1) and ln(2, 3) < ln(4, 5):
                    return False
        elif i == 6:
            if not P[6] < P[5]:
                return False
            # 2026-11-13: una "A" che ritraccia oltre l'inizio dell'impulso non è una correzione
            if P[6] < P[0]:
                return False
        elif i == 7:
            rb = (P[7] - P[6]) / (P[5] - P[6])
            if (not _ew_in(rb, R["b"])) if conf else (not 0 < rb < 1):
                return False
        elif i == 8:
            if not P[8] < P[7]:
                return False
            # 2026-11-13: C in corso oltre 2.618×A = struttura diversa (nuovo impulso)
            if ln(7, 8) > 2.618 * ln(5, 6):
                return False
    return True


def ew_engine_match(zz):
    end = len(zz) - 1
    for s in range(max(0, end - 8), end - 2):
        d = -1 if zz[s]["hi"] else 1
        if ew_engine_check([d * z["p"] for z in zz[s:]]):
            return s, d
    return None


def _ew_w4_too_early(zz, s, n_bars):
    """True se il conteggio trovato è "onda 4 in corso" ma il rimbalzo è ancora troppo piccolo
    (sotto EW_W4_MIN_RETR dell'onda 3) e troppo breve (sotto EW_W4_MIN_TIME della sua durata)."""
    pts = zz[s:]
    if len(pts) != 5:
        return False
    w3 = abs(pts[3]["p"] - pts[2]["p"])
    t3 = pts[3]["i"] - pts[2]["i"]
    if w3 <= 0 or t3 <= 0:
        return False
    retr = abs(pts[3]["p"] - pts[4]["p"]) / w3
    t4 = (n_bars - 1) - pts[3]["i"]
    return retr < EW_W4_MIN_RETR and t4 < EW_W4_MIN_TIME * t3


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


EW_TRI_MIN_LEG = 0.2


def ew_engine_triangle(zz, index, degree, length):
    n = len(zz)
    best = None
    for npts, phase in ((7, "thrust"), (6, "E")):
        s = n - npts
        if s < 1:
            continue
        pts = zz[s:]
        d = 1 if pts[0]["hi"] else -1            # P0 massimo → triangolo dentro un trend rialzista
        q = [d * z["p"] for z in pts]
        qprev = d * zz[s - 1]["p"]
        la = q[0] - q[1]
        if la <= 0 or (q[0] - qprev) <= la:      # onda precedente più ampia di A
            continue
        if not (q[2] < q[0] and q[4] < q[2] and q[3] > q[1] and q[5] > q[3]):
            continue                              # massimi ↓, minimi ↑ (E non oltre C)
        legs = [q[2] - q[1], q[2] - q[3], q[4] - q[3], q[4] - q[5]]
        if min(legs) < EW_TRI_MIN_LEG * la:
            continue
        p = [z["p"] for z in pts]
        if phase == "thrust":
            if not q[6] > q[4] - 0.25 * legs[3]:  # la spinta deve almeno avvicinarsi al massimo di D
                continue
            base = p[5]
            fibs = [{"r": r, "v": base + d * la * r} for r in (0.618, 1.0, 1.272)]
            cur = p[6]
            tgt = next((f for f in fibs if (f["v"] - cur) * d > 0), fibs[-1])
            reached = (fibs[-1]["v"] - cur) * d <= 0
            labels = ["0", "A", "B", "C", "D", "E", "5"]
            out = {"wave": "5", "wave_up": d > 0, "inval": p[5], "target": tgt["v"], "target_ratio": tgt["r"],
                   "targets_reached": reached, "fibs": fibs, "entry": cur,
                   "fib_basis": "widest part of the triangle (wave A) projected from the end of wave E",
                   "desc": f"Thrust out of a contracting triangle ({'bullish' if d > 0 else 'bearish'} trend)"}
        else:
            # E in corso: zona di fine E = 61.8–78.6% di D; poi spinta = A dalla fine di E
            ez = [{"r": r, "v": p[4] - d * legs[2] * r} for r in (0.618, 0.786)]
            entry = ez[0]["v"] if (q[5] > d * ez[0]["v"]) else p[5]
            tgt_v = entry + d * la
            labels = ["0", "A", "B", "C", "D", "E"]
            out = {"wave": "E", "wave_up": d < 0, "inval": p[3], "target": tgt_v, "target_ratio": 1.0,
                   "targets_reached": False, "fibs": ez, "entry": entry,
                   "fib_basis": "widest part of the triangle (wave A) projected from the end of wave E",
                   "desc": f"Contracting triangle, wave E in progress ({'bullish' if d > 0 else 'bearish'} trend)"}
        out.update({
            "la": la, "d_level": p[4], "e_level": p[5], "e_leg": legs[3],
            "degree": degree, "len": length, "k": len(pts), "trend": "bullish" if d > 0 else "bearish",
            "structure": "triangle", "triangle": True, "bias_dir": d, "dir": d,
            "pivots": [{"label": labels[i], "i": z["i"], "p": z["p"], "hi": z["hi"], "time": str(index[z["i"]])[:16]}
                       for i, z in enumerate(pts)],
        })
        best = out
        break
    return best


def ew_engine_run(df):
    highs = df["high"].astype(float).tolist()
    lows = df["low"].astype(float).tolist()
    degrees = []
    triangles = []
    for name, length in EW_ENGINE_DEGREES:
        zz = ew_engine_zigzag(highs, lows, length)
        m = ew_engine_match(zz) if len(zz) >= 4 else None
        zc = zz
        if m and _ew_w4_too_early(zz, m[0], len(highs)):
            # rimbalzo ancora piccolo: si conta senza il tratto in corso → la 3 resta in corso
            m2 = ew_engine_match(zz[:-1]) if len(zz) >= 5 else None
            if m2:
                zc, m = zz[:-1], m2
        degrees.append(ew_engine_describe(m[0], m[1], zc, df.index, name, length) if m
                       else {"degree": name, "len": length, "none": True})
        try:
            t = ew_engine_triangle(zz, df.index, name, length) if len(zz) >= 7 else None
            if t:
                triangles.append(t)
        except Exception as e_tri:
            logger.warning(f"triangle scan {name}: {e_tri}")
    # FIX 2026-10-07: il grado dipendeva solo dalla lunghezza dei pivot (4/8/16
    # barre), uguale su ogni timeframe → il 4H risultava "Intermediate" con il
    # Daily "Minor" (grado inferiore sopra a uno superiore). Ora il nome del
    # grado scala con il timeframe: Daily Minor/Intermediate/Primary, 4H
    # Minuette/Minute/Minor, 1H Subminuette/Minuette/Minute.
    _ladder = ["Subminuette", "Minuette", "Minute", "Minor", "Intermediate", "Primary"]
    try:
        # 2026-10-29: quantile 20% invece della mediana — sul 4H azionario metà degli intervalli
        # sono gap notturni da 20h e la mediana lo faceva sembrare Daily (grado "Primary")
        _sec = pd.Series(df.index).diff().dt.total_seconds().dropna().quantile(0.2)
    except Exception:
        _sec = 86400
    _base = 3 if _sec >= 20 * 3600 else 1 if _sec >= 3 * 3600 else 0
    for _o in degrees + triangles:
        _step = [n for n, _ in EW_ENGINE_DEGREES].index(_o["degree"]) if _o["degree"] in [n for n, _ in EW_ENGINE_DEGREES] else 0
        _o["degree"] = _ladder[min(_base + _step, len(_ladder) - 1)]
    valid = sorted([o for o in degrees if not o.get("none")], key=lambda o: (-o["k"], -o["len"]))
    # 2026-10-25: triangolo preferito quando nessun impulso/ABC è valido, oppure quando il conteggio
    # "valido" nasce DENTRO il triangolo (un falso 1-2-3 fatto con le gambe C-D-E): lì la struttura
    # più ampia è il triangolo. In tutti gli altri casi i conteggi restano quelli di prima.
    # Tra i triangoli: preferita la spinta già partita, poi il grado più ampio.
    tri = sorted(triangles, key=lambda o: (o["wave"] != "5", -o["len"]))
    primary = valid[0] if valid else None
    if tri and (primary is None or primary["pivots"][0]["i"] >= tri[0]["pivots"][1]["i"]):
        primary = tri[0]
    return {"primary": primary, "degrees": degrees, "triangle": tri[0] if tri else None}


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
    elif e.get("triangle"):
        # 2026-10-25: triangolo contrattivo (vedi ew_engine_triangle)
        wn = e["wave"]
        d = e["dir"]
        direction_up = d > 0
        degree = e["degree"]
        pv = [x["p"] for x in e["pivots"]]
        pivots = [{"type": "H" if x["hi"] else "L", "idx": x["i"], "price": x["p"]} for x in e["pivots"]]
        w1s, w1e = pv[0], pv[1]
        w1z = abs(w1e - w1s)
        inv = e["inval"]
        side = "🟢 LONG" if d > 0 else "🔴 SHORT"
        trade_dir = d
        if wn == "5":
            entry, ct = p, e["target"]
            nt = e["fibs"][-1]["v"]
            wp = "IMPULSIVE"
            wd = "Wave ⑤ — thrust out of a contracting triangle"
            action = (f"{side} — triangle complete, thrust in progress, target {_ew_fmt(ct)} "
                      f"(widest part of the triangle), invalidation {_ew_fmt(inv)} (end of wave E)")
            bi = "BULLISH" if direction_up else "BEARISH"
            if e.get("targets_reached"):
                trade_dir, bi = 0, "NEUTRAL"
                action = (f"⏳ WAIT — the thrust has already reached the triangle targets (last {_ew_fmt(ct)}): "
                          f"no new entry. Invalidation {_ew_fmt(inv)}")
        elif (p - e["e_level"]) * d > 0.382 * e["e_leg"]:
            # il prezzo si è già allontanato dalla fine di E nella direzione della spinta
            entry = p
            ct = nt = e["e_level"] + d * e["la"]
            wp = "CORRECTIVE TRIANGLE"
            wd = "Wave E of a contracting triangle — likely complete, thrust starting"
            action = (f"{side} — wave E likely complete at {_ew_fmt(e['e_level'])}, thrust starting: "
                      f"confirmation on a break of {_ew_fmt(e['d_level'])} (end of wave D), target {_ew_fmt(ct)}, "
                      f"invalidation {_ew_fmt(inv)} (end of wave C)")
            bi = "TRIANGLE — LONG SETUP" if direction_up else "TRIANGLE — SHORT SETUP"
            e["target"] = ct
        else:
            entry, ct = e["entry"], e["target"]
            nt = ct
            wp = "CORRECTIVE TRIANGLE"
            wd = "Wave E of a contracting triangle — last leg before the thrust"
            action = (f"{side} — wait for wave E to end near {_ew_fmt(entry)}, then trade the thrust: "
                      f"target {_ew_fmt(ct)}, invalidation {_ew_fmt(inv)} (end of wave C)")
            bi = "TRIANGLE — LONG SETUP" if direction_up else "TRIANGLE — SHORT SETUP"
        wc = (f"Contracting triangle A-B-C-D-E ({degree} degree): lower highs and higher lows, each leg shorter "
              f"than the previous. Thrust target = widest part of the triangle (wave A) projected from the end of wave E.")
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
                _mn = _ew_mature_note(e, wn, _ew_fmt)
                action = ("⏳ WAIT — " + ". ".join(_mn) + "." if _mn else
                          f"⏳ WAIT — wave {wn} has already passed its last Fibonacci level ({_ew_fmt(tgt)}). "
                          f"Invalidation {_ew_fmt(inv)}")
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


def _ew_pfmt(sym):
    return ".3f" if "JPY" in sym else _pf(sym)


EWP = {
    "bg": "#0f1724", "panel": "#0f1724", "grid": "#18243a", "text": "#e2eaf4", "muted": "#7f93b0",
    "c_up_edge": "#cbd5e1", "c_dn": "#7c8ba1", "wick": "#8b9bb3",
    "imp": "#60a5fa", "corr": "#f87171", "imp2": "#93c5fd", "corr2": "#fca5a5",
    "inval": "#ef4444", "target": "#2563eb", "path": "#60a5fa", "fib": "#94a3b8", "tri": "#f87171",
}


_EWP_ROMAN = {"1": "i", "2": "ii", "3": "iii", "4": "iv", "5": "v"}


def _ewp_tag(ax, y, text, fc, tc="#ffffff", fs=7.0):
    """Cartellino sull'asse destro (stile TradingView)."""
    ax.text(1.003, y, f" {text} ", transform=ax.get_yaxis_transform(), color=tc, fontsize=fs,
            fontweight="bold", va="center", ha="left", clip_on=False, zorder=12,
            bbox=dict(boxstyle="square,pad=0.25", fc=fc, ec="none"))


def _ewp_minor(degrees, eng):
    """Grado minore da disegnare insieme al principale: il conteggio valido di grado più piccolo
    che non coincide con quello principale e che parte dopo l'inizio del conteggio principale."""
    if not degrees or not eng or eng.get("triangle"):
        return None
    main_idx = {pv["i"] for pv in eng["pivots"]}
    cands = [o for o in degrees if not o.get("none") and o.get("len", 0) < eng.get("len", 0)
             and o["pivots"] and o["pivots"][0]["i"] >= eng["pivots"][0]["i"]
             and not {pv["i"] for pv in o["pivots"]} <= main_idx]
    if eng.get("wave") in ("2", "4", "B") and len(eng["pivots"]) >= 2:
        # 2026-10-29: dentro un'onda correttiva in corso un i-ii impulsivo contraddice il conteggio
        leg0 = eng["pivots"][-2]["i"]
        cands = [o for o in cands if o["pivots"][0]["i"] < leg0 or o.get("structure") == "correction"]
    return min(cands, key=lambda o: o["len"]) if cands else None


def _ewp_abc(df, i0, i1, p0, p1):
    """2026-10-26: suddivisione a-b-c di un'onda correttiva completata (onde 2, 4, B) dai prezzi reali.
    i0/p0 = inizio della correzione (pivot), i1/p1 = fine. Cerca a (primo estremo nella direzione della
    correzione), b (rimbalzo contrario 23.6–90% di a) e c = fine dell'onda (oltre a, o vicino ad a nei flat).
    Ritorna [(ia, pa), (ib, pb)] oppure None se dentro l'onda non c'è una struttura a-b-c leggibile."""
    try:
        if i1 - i0 < 6:
            return None
        dn = p1 < p0                                   # correzione verso il basso?
        hi = df["high"].values.astype(float)
        lo = df["low"].values.astype(float)
        size = abs(p0 - p1)
        best, best_sc = None, 0.0
        for ia in range(i0 + 2, i1 - 3):
            pa = lo[ia] if dn else hi[ia]
            seg_a = lo[i0 + 1:ia + 1] if dn else hi[i0 + 1:ia + 1]
            if (dn and pa > seg_a.min()) or (not dn and pa < seg_a.max()):
                continue                               # a = estremo della prima gamba
            rng_b = range(ia + 2, i1 - 1)
            if not len(rng_b):
                continue
            ib = max(rng_b, key=lambda k: hi[k]) if dn else min(rng_b, key=lambda k: lo[k])
            pb = hi[ib] if dn else lo[ib]
            leg_a = abs(p0 - pa)
            if leg_a < 0.3 * size or ib - ia < 2 or i1 - ib < 2:
                continue
            retr = abs(pb - pa) / leg_a
            if not 0.236 <= retr <= 0.9:
                continue
            # c deve arrivare almeno vicino ad a (zigzag: oltre; flat: ±10% della gamba a)
            if (dn and p1 > pa + 0.1 * leg_a) or (not dn and p1 < pa - 0.1 * leg_a):
                continue
            # nessun prezzo oltre la fine dell'onda dentro la correzione
            mid = lo[i0 + 1:i1] if dn else hi[i0 + 1:i1]
            if (dn and mid.min() < p1 - 1e-12) or (not dn and mid.max() > p1 + 1e-12):
                return None
            sc = abs(pb - pa) * min(ib - ia, i1 - ib)
            if sc > best_sc:
                best, best_sc = [(ia, pa), (ib, pb)], sc
        return best
    except Exception:
        return None


def _ewp_i_ii(df, i0, p0, up):
    """2026-10-26: prime due onde (i, ii) dell'onda motrice in corso (3 o 5), dai prezzi reali:
    i = primo massimo (minimo) significativo, ii = ritracciamento 38.2–90% che non torna oltre l'inizio,
    poi il prezzo deve aver già superato i (iii in corso). Ritorna [(ia, pa), (ib, pb)] oppure None."""
    try:
        hi = df["high"].values.astype(float)
        lo = df["low"].values.astype(float)
        n = len(df)
        if n - i0 < 8:
            return None
        best, best_sc = None, 0.0
        for ia in range(i0 + 2, n - 4):
            pa = hi[ia] if up else lo[ia]
            seg = hi[i0 + 1:ia + 1] if up else lo[i0 + 1:ia + 1]
            if (up and pa < seg.max()) or (not up and pa > seg.min()):
                continue
            # fine di ii: estremo opposto prima che il prezzo superi i
            j = ia + 1
            while j < n and ((hi[j] <= pa) if up else (lo[j] >= pa)):
                j += 1
            if j >= n or j - ia < 3:
                continue                              # i non ancora superato → niente iii
            win = range(ia + 1, j)
            ib = min(win, key=lambda k: lo[k]) if up else max(win, key=lambda k: hi[k])
            pb = lo[ib] if up else hi[ib]
            leg = abs(pa - p0)
            if leg <= 0:
                continue
            retr = abs(pa - pb) / leg
            if not 0.382 <= retr <= 0.9 or ib - ia < 1 or j - ib < 1:
                continue
            sc = leg * retr * min(ia - i0, ib - ia)
            if sc > best_sc:
                best, best_sc = [(ia, pa), (ib, pb)], sc
        return best
    except Exception:
        return None


def _ew_pro_panel(ax, df, eng, degrees, pf, setup, compact=False, base_bars=70, max_bars=300):
    """Disegna il pannello. setup = {"td","entry","ct","nt","inv","wave"} dal motore. Ritorna lo start."""
    n = len(df)
    start = max(0, n - base_bars)
    if eng and eng.get("pivots"):
        start = min(start, max(0, eng["pivots"][0]["i"] - 6))
    start = max(start, n - max_bars, 0)
    seg = df.iloc[start:]
    m = len(seg)
    x = np.arange(m)
    o = seg["open"].values.astype(float); h = seg["high"].values.astype(float)
    l = seg["low"].values.astype(float); cl = seg["close"].values.astype(float)
    lo, hi = float(np.nanmin(l)), float(np.nanmax(h))
    rng = (hi - lo) or abs(hi) * 0.01 or 1.0
    last = float(cl[-1])
    # 2026-10-25: caratteri più grandi — su telefono l'immagine viene rimpicciolita
    fs_major, fs_minor, fs_lvl = (7.5, 6.6, 6.6) if compact else (11.0, 9.5, 9.0)

    ax.set_facecolor(EWP["panel"])
    ax.grid(True, color=EWP["grid"], linewidth=0.5)
    for sp in ax.spines.values():
        sp.set_color(EWP["grid"])
    ax.tick_params(colors=EWP["muted"], labelsize=6.6 if compact else 8.5)
    ax.yaxis.tick_right()
    # candele monocromatiche: rialzo vuota, ribasso piena
    ax.vlines(x, l, h, colors=EWP["wick"], linewidth=0.6, zorder=2)
    body_lo, body_h = np.minimum(o, cl), np.maximum(np.abs(cl - o), rng * 0.0012)
    up = cl >= o
    ax.bar(x[up], body_h[up], bottom=body_lo[up], width=0.62, color=EWP["bg"], edgecolor=EWP["c_up_edge"],
           linewidth=0.6, zorder=3)
    ax.bar(x[~up], body_h[~up], bottom=body_lo[~up], width=0.62, color=EWP["c_dn"], edgecolor=EWP["c_dn"],
           linewidth=0.6, zorder=3)

    ylo, yhi = lo, hi
    occupied = {}
    tags = []          # cartellini sull'asse destro: disegnati alla fine, senza sovrapposizioni
    tag_notes = {}     # indice in tags -> (nota sotto il cartellino, colore)

    _stroke = [mpe.withStroke(linewidth=3.2, foreground=EWP["panel"])]
    near = max(2, int(m * 0.025))       # barre entro cui due etichette sullo stesso lato si toccano

    def put_label(xi, pr, is_hi, text, color, major, dashed=False):
        # 2026-10-29: impilamento per altezza reale (cerchio ≈ 2× il testo) e per lato, controllando
        # anche le barre vicine: niente "c" sopra il cerchio dell'onda 2, niente etichette accavallate
        k = int(round(xi))
        h_lab = (fs_major * 1.65) if major else (fs_minor * 1.35)
        used = max([occupied.get((k + d, is_hi), 0.0) for d in range(-near, near + 1)] + [0.0])
        off0 = 7.0 + used
        occupied[(k, is_hi)] = used + h_lab + 2.0
        off = off0 * (1 if is_hi else -1)
        dx, ha = 0.0, "center"
        if not major and used > 0:
            # 2026-11-13: sotto-etichetta in collisione con un cerchio maggiore → accanto al pivot
            # (a destra, alla quota del punto) invece di impilarla lontano dal minimo/massimo a cui si riferisce
            occupied[(k, is_hi)] = used
            # lato opposto all'etichetta che occupa lo spazio (es. "a" dell'onda 2 → a sinistra del cerchio "2")
            dd = max(range(-near, near + 1), key=lambda d: (occupied.get((k + d, is_hi), 0.0) if d else 0.0, -abs(d)))
            sgn = -1 if dd > 0 else 1
            dx, ha, off = sgn * fs_minor * 0.7, ("right" if sgn < 0 else "left"), 3.0 * (1 if is_hi else -1)
        kw = dict(ha=ha, va="bottom" if is_hi else "top", fontsize=fs_major if major else fs_minor,
                  color=color, zorder=11, fontweight="bold" if major else "normal")
        if major:
            kw["bbox"] = dict(boxstyle="circle,pad=0.18", fc=EWP["panel"], ec=color, lw=0.9,
                              ls=(0, (2, 2)) if dashed else "-", alpha=1.0)
        else:   # contorno nel colore di fondo: leggibile sopra le linee senza "buchi" nei livelli
            kw["path_effects"] = _stroke
            # 2026-11-13: riquadro col colore del pannello — una linea di livello (es. INV vicino
            # al minimo della ii) non attraversa più la lettera (Walmart 4H: "ii" sopra la linea rossa)
            kw["bbox"] = dict(boxstyle="round,pad=0.12", fc=EWP["panel"], ec="none", alpha=0.92)
        ax.annotate(text, (xi, pr), xytext=(dx, off), textcoords="offset points", **kw)

    if eng:
        tri = eng.get("triangle")
        pts = [(pv["i"] - start, pv["p"], pv["label"], pv["hi"]) for pv in eng["pivots"] if pv["i"] >= start]
        # grado maggiore: le onde completate (l'ultima è in corso → la racconta la freccia)
        # (eccezione: la E di un triangolo si etichetta sempre — è il punto da cui parte la spinta)
        for xi, pr, lab, is_hi in (pts if (tri and pts and pts[-1][2] == "E") else pts[:-1]):
            if lab == "0":
                # 2026-11-10: origine del conteggio segnata (prima mancava: non si capiva da dove partisse l'onda 1)
                if not compact:
                    put_label(xi, pr, is_hi, "0", EWP["imp"], True)
                continue
            corr = lab in ("A", "B", "C", "D", "E")
            put_label(xi, pr, is_hi, lab, EWP["corr"] if corr else EWP["imp"], True)
        if tri and len(pts) >= 6:
            tp = {q[2]: (q[0], q[1]) for q in pts}
            for a_, b_ in (("A", "C"), ("B", "D")):
                if a_ in tp and b_ in tp and tp[b_][0] != tp[a_][0]:
                    (x1, y1), (x2, y2) = tp[a_], tp[b_]
                    sl = (y2 - y1) / (x2 - x1)
                    xe = min(m - 1, max(tp.get("E", (x2, 0))[0] + 6, x2 + 6))
                    ax.plot([x1, xe], [y1, y1 + sl * (xe - x1)], color=EWP["tri"], lw=1.0, zorder=4)
        # grado minore (suddivisione dell'onda più recente)
        mn = _ewp_minor(degrees, eng)
        # 2026-10-26: correzioni completate (2, 4, B) disegnate come zigzag a-b-c
        if not tri:
            piv = eng["pivots"]
            mn_idx = {q["i"] for q in (mn["pivots"] if mn else [])}
            for k in range(1, len(piv) - 1):
                if piv[k]["label"] not in ("2", "4", "B"):
                    continue
                i0, i1 = piv[k - 1]["i"], piv[k]["i"]
                if i0 < start or any(i0 < q < i1 for q in mn_idx):
                    continue
                abc = _ewp_abc(df, i0, i1, piv[k - 1]["p"], piv[k]["p"])
                if not abc:
                    continue
                (ia, pa), (ib, pb) = abc
                dn = piv[k]["p"] < piv[k - 1]["p"]
                xs = [i0 - start, ia - start, ib - start, i1 - start]
                ys = [piv[k - 1]["p"], pa, pb, piv[k]["p"]]
                ax.plot(xs, ys, color=EWP["corr2"], lw=0.9, alpha=0.85, zorder=6)
                put_label(ia - start, pa, not dn, "a", EWP["corr2"], False)
                put_label(ib - start, pb, dn, "b", EWP["corr2"], False)
                # 2026-11-10: la "c" coincide con il cerchio dell'onda maggiore → accanto al cerchio,
                # non impilata sotto (sembrava staccata dal prezzo)
                # 2026-11-13: se la "a" è vicina al cerchio, la "c" va a destra (Caterpillar: "c" sopra la "a")
                c_r = abs(ia - i1) <= 2 * near
                ax.annotate("c", (i1 - start, piv[k]["p"]), xytext=((fs_major * 1.25) * (1 if c_r else -1), -7 if dn else 7),
                            textcoords="offset points", ha="left" if c_r else "right", va="top" if dn else "bottom",
                            fontsize=fs_minor, color=EWP["corr2"], zorder=11, path_effects=_stroke)
            # onda motrice in corso (3 o 5): i e ii già formate, iii in corso
            if not mn and piv[-1]["label"] in ("3", "5") and len(piv) >= 2:
                i0, p0 = piv[-2]["i"], piv[-2]["p"]
                up = piv[-1]["p"] > p0
                if i0 >= start:
                    w = _ewp_i_ii(df, i0, p0, up)
                    if w:
                        (ia, pa), (ib, pb) = w
                        ax.plot([i0 - start, ia - start, ib - start], [p0, pa, pb], color=EWP["imp2"], lw=0.9,
                                alpha=0.85, zorder=6)
                        put_label(ia - start, pa, up, "i", EWP["imp2"], False)
                        put_label(ib - start, pb, not up, "ii", EWP["imp2"], False)
        if mn:
            for pv in mn["pivots"][:-1]:
                if pv["i"] < start or pv["label"] == "0":
                    continue
                lab = pv["label"]
                corr = lab in ("A", "B", "C")
                txt = lab.lower() if corr else _EWP_ROMAN.get(lab, lab)
                put_label(pv["i"] - start, pv["p"], pv["hi"], txt, EWP["corr2"] if corr else EWP["imp2"], False)

        # ── livelli ──
        st = setup or {}
        td = st.get("td", 0) or 0
        wave = st.get("wave") or eng.get("wave")
        inv = st.get("inv", eng.get("inval"))
        x_end = m - 1 + max(12, int(m * 0.24))      # spazio "futuro" a destra per scenario ed etichette
        ext0 = x_end - (m - 1)
        plan = _ew_panel_plan(df, eng, st, pf, base_bars, max_bars)
        if inv is not None:
            inv_x = next((q[0] for q in pts if abs(q[1] - inv) <= abs(inv) * 1e-9), max(0, m - 1 - int(m * 0.35)))
            ax.hlines(inv, inv_x, x_end, colors=EWP["inval"], linewidth=1.0, zorder=5)
            tags.append((inv, f"INV {inv:{pf}}" if not compact else f"{inv:{pf}}", EWP["inval"], "#ffffff", fs_lvl))
            ylo, yhi = min(ylo, inv), max(yhi, inv)
            if not compact and plan.get("inv_note"):
                # 2026-10-29: perché è quello il livello (es. "end of wave 2"), sotto il cartellino
                tag_notes[len(tags) - 1] = (plan["inv_note"].split(" — ")[0], EWP["corr2"])

        zone = list(eng.get("fibs") or []) if (td != 0 and wave in ("4", "B", "E")) else []
        targets = [v for v, _ in plan["targets"]]
        tlabels = [lab for _, lab in plan["targets"]]
        if compact:
            targets = targets[:1]
        k0 = 1
        if plan["reached"]:
            k0 = 2      # il T1 raggiunto è nel testo; sul grafico niente linea vicino al prezzo
        for k_, v in enumerate(targets, k0):
            ax.hlines(v, m - 1 + ext0 * 0.55, x_end, colors=EWP["target"], linewidth=1.0, zorder=5)
            tags.append((v, f"T{k_} {v:{pf}}" if not compact else f"{v:{pf}}", EWP["target"], "#ffffff", fs_lvl))
            ylo, yhi = min(ylo, v), max(yhi, v)
            lab_ = tlabels[k_ - k0] if k_ - k0 < len(tlabels) else ""
            if not compact and lab_:
                # 2026-10-29: criterio Fibonacci del target sotto il cartellino (es. "1.618×W1")
                tag_notes[len(tags) - 1] = (lab_.split("= ")[-1], EWP["imp2"])
        if not compact:
            for f in zone:
                v = f["v"]
                x0 = m - 1 + ext0 * 0.05
                ax.hlines(v, x0, x_end, colors=EWP["fib"], linewidth=0.8, linestyles=(0, (3, 3)), zorder=4)
                ax.text(x_end, v, f"{f['r']:g} ", color=EWP["muted"], fontsize=fs_lvl - 1,
                        ha="right", va="bottom", zorder=9)
                ylo, yhi = min(ylo, v), max(yhi, v)

        # ── percorso dello scenario ──
        if td != 0 and targets:
            ext = x_end - (m - 1)
            # onda 5 (terminale): la freccia punta all'uguaglianza W5 = W1, non all'estensione
            goal = targets[min(1, len(targets) - 1)] if wave not in ("4", "B", "E", "5") else targets[0]
            entry = st.get("entry")
            if wave in ("4", "B", "E") and entry is not None and abs(entry - last) > rng * 0.01:
                path = [(m - 1, last), (m - 1 + ext * 0.22, entry), (m - 1 + ext * 0.5, goal)]
            else:
                path = [(m - 1, last), (m - 1 + ext * 0.5, goal)]
            ax.plot([p_[0] for p_ in path], [p_[1] for p_ in path],
                    color=EWP["path"], lw=1.6, zorder=10, solid_capstyle="round")
            ax.annotate("", xy=path[-1], xytext=(path[-1][0] - (path[-1][0] - path[-2][0]) * 0.12,
                                                  path[-1][1] - (path[-1][1] - path[-2][1]) * 0.12),
                        arrowprops=dict(arrowstyle="-|>", color=EWP["path"], lw=1.6, mutation_scale=12), zorder=10)
            if not compact and not eng.get("triangle"):
                nxt = {"4": "5", "B": "C"}.get(wave, wave)
                if nxt:
                    goes_up = path[-1][1] > path[-2][1]
                    put_label(path[-1][0], path[-1][1], goes_up, nxt,
                              EWP["corr"] if nxt in ("A", "B", "C") else EWP["imp"], True, dashed=True)
        ax.set_xlim(-1, x_end + 1)
    else:
        ax.set_xlim(-1, m + max(4, int(m * 0.05)))

    # prezzo attuale
    ax.axhline(last, color=EWP["text"], lw=0.5, alpha=0.25, zorder=1)
    tags.append((last, f"{last:{pf}}", "#e2eaf4", EWP["bg"], 6.8 if compact else 9.0))
    pad = (yhi - ylo) * 0.08
    ax.set_ylim(ylo - pad, yhi + pad * 1.6)
    # cartellini: se due livelli sono vicini (es. prezzo e invalidazione) si distanziano in verticale
    y0, y1 = ax.get_ylim()
    gap = (y1 - y0) * (0.045 if not compact else 0.06)
    gap_n = (y1 - y0) * 0.075       # cartellino + nota sotto
    placed = []
    order = sorted(range(len(tags)), key=lambda i_: tags[i_][0])
    note_ys = []
    for i_ in order:
        y, text, fc, tc, fsz = tags[i_]
        note = tag_notes.get(i_)
        # la nota sta sotto il cartellino: serve più spazio rispetto al cartellino più in basso
        yy = y if not placed else max(y, placed[-1] + (gap_n if note else gap))
        placed.append(yy)
        _ewp_tag(ax, yy, text, fc, tc=tc, fs=fsz)
        if note:
            note_ys.append(yy - gap * 0.75)
            ax.annotate(note[0], (1.006, yy), xycoords=ax.get_yaxis_transform(), xytext=(0, -9),
                        textcoords="offset points", color=note[1], fontsize=fsz - 1.8, ha="left", va="top",
                        annotation_clip=False, zorder=12)
    # scala prezzi a destra, ma senza numeri dietro/vicino ai cartellini
    _yt = [t_ for t_ in ax.get_yticks() if y0 < t_ < y1]
    ax.set_yticks(_yt)
    ax.set_yticklabels(["" if any(abs(t_ - p_) < gap * 0.9 for p_ in placed + note_ys) else f"{t_:{pf}}" for t_ in _yt])
    ax.tick_params(axis="y", length=0)
    step = max(1, m // (4 if compact else 7))
    ticks = list(range(0, m, step))
    ax.set_xticks(ticks)
    ax.set_xticklabels([seg.index[i].strftime("%d %b") for i in ticks], fontsize=6.3 if compact else 8.3)
    return start


def _ew_mature_note(eng, wn, fmt):
    """2026-10-29: nota chiara quando l'onda in corso ha già superato tutti i livelli Fibonacci.
    Dice cosa è successo, cosa NON fare e quale livello reale conferma la svolta. fmt = formattatore prezzi."""
    fibs = (eng or {}).get("fibs") or []
    pv = {x["label"]: x["p"] for x in (eng or {}).get("pivots", [])}
    up = bool((eng or {}).get("wave_up"))
    if not fibs:
        return []
    f = fibs[-1]
    lvl, r = fmt(f["v"]), _ew_fr(f["r"])
    no_new = "no new longs" if up else "no new shorts"
    back = "below" if up else "above"
    if wn == "3":
        out = [f"Wave 3 is already beyond its last projection ({r}×W1 at {lvl}): extended move, too late to chase",
               "better entry on the wave 4 pullback"]
        if "2" in pv:
            out.append(f"the count holds while price stays {'above' if up else 'below'} {fmt(pv['2'])} (end of wave 2)")
        return out
    if wn == "5":
        out = [f"Wave 5 is already beyond its last projection ({r}×W1 at {lvl}): the impulse can end at any time",
               f"{no_new} here — protect profits"]
        if "4" in pv:
            out.append(f"a break back {back} {fmt(pv['4'])} (end of wave 4) would confirm the "
                       f"{'top' if up else 'low'} is in")
        return out
    if wn == "A":
        return [f"Wave A has already retraced {r} of the whole impulse ({lvl}): the first corrective leg is mature",
                "no chasing — wait for the wave B bounce to position for wave C"]
    if wn == "C":
        out = [f"Wave C has already reached {r}×A ({lvl}): the correction can end at any time", f"{no_new} here"]
        if "B" in pv:
            out.append(f"a break back {back} {fmt(pv['B'])} (end of wave B) would confirm the correction is over")
        return out
    if wn in ("4", "B"):
        base = "wave 3" if wn == "4" else "wave A"
        return [f"Wave {wn} has reached the {r} retracement of {base} ({lvl}), the usual end zone for this correction"]
    return []


def _ew_fr(r):
    return "1.0" if abs(r - 1) < 1e-9 else f"{r:g}"


def _ew_target_plan(eng, setup, last, rng, pf=".2f", extreme=None):
    """2026-10-26: UNICA fonte dei target per testo e grafico, ognuno col suo criterio Fibonacci esatto.
    Ritorna {"targets": [(valore, etichetta)], "basis": str, "entry_note": str, "inv_note": str}."""
    out = {"targets": [], "basis": "", "entry_note": "", "inv_note": "", "reached": None}
    # 2026-10-26: "raggiunto" si misura sull'estremo dell'onda in corso (massimo/minimo toccato),
    # non sull'ultima chiusura: un target toccato e poi abbandonato resta raggiunto.
    if not eng:
        return out
    st = setup or {}
    td = st.get("td", 0) or 0
    ref = last if extreme is None else (max(last, extreme) if td > 0 else min(last, extreme))
    wave = st.get("wave") or eng.get("wave")
    entry = st.get("entry")
    fibs = eng.get("fibs") or []
    pv = {x["label"]: x["p"] for x in eng.get("pivots", [])}
    num = lambda v: format(float(v), "," + pf)
    tri = bool(eng.get("triangle"))
    # perché il livello di invalidazione è quello
    out["inv_note"] = ({"5": "end of wave E", "E": "end of wave C"} if tri else
                       {"3": "end of wave 2", "4": "end of wave 1 — no overlap", "5": "end of wave 4",
                        "A": "end of wave 5", "B": "start of wave A", "C": "end of wave B"}).get(wave, "")

    def match_fib(v):
        return next((f for f in fibs if v is not None and abs(f["v"] - v) <= max(abs(v) * 1e-9, 1e-12)), None)

    t = []
    if td != 0:
        if tri and wave == "5":
            t = [(f["v"], f"{_ew_fr(f['r'])}× triangle width") for f in fibs if (f["v"] - ref) * td > 0]
            out["basis"] = f"triangle width projected from the end of wave E ({num(pv['E'])})"
        elif tri:   # onda E in corso / appena finita: la spinta
            ct = st.get("ct")
            if ct is not None:
                t = [(ct, "1.0× triangle width")]
            mf = match_fib(entry)
            if mf and abs(entry - last) > rng * 0.01:
                out["entry_note"] = f"{_ew_fr(mf['r'])} retracement of wave D"
            out["basis"] = "triangle width projected from the end of wave E"
        elif wave == "3":
            t = [(f["v"], f"W3 = {_ew_fr(f['r'])}×W1") for f in fibs if (f["v"] - ref) * td > 0]
            out["basis"] = f"wave 1 projected from the end of wave 2 ({num(pv['2'])})"
        elif wave == "5":
            t = [(f["v"], f"W5 = {_ew_fr(f['r'])}×W1") for f in fibs if (f["v"] - ref) * td > 0]
            out["basis"] = f"wave 1 projected from the end of wave 4 ({num(pv['4'])})"
            # 2026-11-13: una 5 normale supera l'estremo della 3. Con una W1 corta i target ×W1 cadevano
            # sotto il massimo della 3 (Walmart 4H: T1 128.81 con W3 a ~131.8 → 5 "troncata").
            # Tengo solo i target oltre la 3 e aggiungo le proiezioni 0.618/1.0 × (0→3) dalla fine della 4.
            if all(k in pv for k in ("0", "3", "4")):
                w3x, span = float(pv["3"]), abs(float(pv["3"]) - float(pv["0"]))
                below = [x for x in t if (x[0] - w3x) * td <= 0]
                if below:
                    extra = [(float(pv["4"]) + td * r_ * span, f"W5 = {_ew_fr(r_)}×(0→3)") for r_ in (0.618, 1.0)]
                    t = sorted([x for x in t if (x[0] - w3x) * td > 0] + [x for x in extra if (x[0] - w3x) * td > 0],
                               key=lambda x: (x[0] - ref) * td)
                    out["basis"] = (f"from the end of wave 4 ({num(pv['4'])}) · wave 5 must clear the wave 3 "
                                    f"{'high' if td > 0 else 'low'} ({num(w3x)}), below it = truncated fifth")
        elif wave == "A":
            t = [(f["v"], f"{_ew_fr(f['r'])} retr. of 1–5") for f in fibs if (f["v"] - ref) * td > 0]
            out["basis"] = f"retracement of waves 1–5 ({num(pv['0'])} → {num(pv['5'])})"
        elif wave == "C":
            t = [(f["v"], f"C = {_ew_fr(f['r'])}×A") for f in fibs if (f["v"] - ref) * td > 0]
            out["basis"] = f"wave A projected from the end of wave B ({num(pv['B'])})"
        elif wave == "4":
            if st.get("ct") is not None:
                t.append((st["ct"], "end of wave 3"))
            if st.get("nt") is not None:
                t.append((st["nt"], "W5 = 1.0×W1"))
            mf = match_fib(entry)
            out["entry_note"] = f"{_ew_fr(mf['r'])} retracement of wave 3" if mf else "end of wave 4"
            out["basis"] = "wave 5 after the entry zone"
        elif wave == "B":
            if st.get("ct") is not None:
                t.append((st["ct"], "end of wave A"))
            if st.get("nt") is not None:
                t.append((st["nt"], "C = 1.0×A"))
            mf = match_fib(entry)
            out["entry_note"] = f"{_ew_fr(mf['r'])} retracement of wave A" if mf else "end of wave B"
            out["basis"] = "wave C after the entry zone"
        if wave in ("4", "B") and len(t) > 1:
            # 2026-10-29: T1 = il target più vicino al prezzo (prima uscivano invertiti, es. JPM T1 325 / T2 327)
            t.sort(key=lambda x: (x[0] - ref) * td)
        if not t and st.get("ct") is not None and wave not in ("4", "B") and not tri:
            t = [(st["ct"], "")]
        # 2026-10-26: l'ultimo livello Fibonacci già superato resta in lista come "reached"
        # (niente rinumerazione: chi legge vede che il #1 è stato preso)
        if td != 0 and wave in ("3", "5", "A", "C") and not (tri and wave != "5"):
            lab_of = {"3": "W3 = {}×W1", "5": "W5 = {}×W1", "A": "{} retr. of 1–5", "C": "C = {}×A"}
            done = [f for f in fibs if (f["v"] - ref) * td <= 0 and (wave == "A" or f["r"] >= 1)]
            if done:
                f = done[-1]
                lab = (f"{_ew_fr(f['r'])}× triangle width" if tri else lab_of[wave].format(_ew_fr(f["r"])))
                out["reached"] = (f["v"], lab)
    # solo livelli nella direzione del trade, senza doppioni; oltre il primo, entro ~1 range visibile
    seen, clean = [], []
    for v, lab in t:
        if (v - ref) * td <= 0 or any(abs(v - s_) <= rng * 0.01 for s_ in seen):
            continue
        if clean and abs(v - last) > rng * 1.0:
            continue
        seen.append(v)
        clean.append((v, lab))
    out["targets"] = clean[:3]
    return out


def _ew_wave_extreme(df, eng, td):
    """Massimo (td>0) o minimo (td<0) toccato dall'onda in corso, dall'ultimo pivot confermato a oggi."""
    try:
        i0 = eng["pivots"][-2]["i"]
        seg = df.iloc[i0:]
        return float(seg["high"].max()) if td > 0 else float(seg["low"].min())
    except Exception:
        return None


def _ew_panel_plan(df, eng, setup, pf, base_bars=70, max_bars=300):
    """2026-10-26: target del grafico calcolati fuori dal grafico, con la STESSA finestra del pannello:
    testo (/elliott, /ai, /ews) e grafico mostrano sempre gli stessi numeri."""
    if df is None or not len(df) or not eng:
        return {"targets": [], "basis": "", "entry_note": "", "inv_note": "", "reached": None}
    n = len(df)
    start = max(0, n - base_bars)
    if eng.get("pivots"):
        start = min(start, max(0, eng["pivots"][0]["i"] - 6))
    start = max(start, n - max_bars, 0)
    seg = df.iloc[start:]
    lo, hi = float(np.nanmin(seg["low"].values.astype(float))), float(np.nanmax(seg["high"].values.astype(float)))
    rng = (hi - lo) or abs(hi) * 0.01 or 1.0
    last = float(seg["close"].values.astype(float)[-1])
    st = setup or {}
    td = st.get("td", 0) or 0
    wave = st.get("wave") or eng.get("wave")
    return _ew_target_plan(eng, st, last, rng, pf,
                           extreme=_ew_wave_extreme(df, eng, td) if wave in ("3", "5", "A", "C") else None)


def _ewp_setup_from(ds):
    """setup per _ew_pro_panel da un risultato di count_elliott_waves_engine / elliott_wave_analysis."""
    if not ds:
        return {}
    return {"td": ds.get("trade_dir", 0), "entry": ds.get("entry"), "ct": ds.get("conservative_target"),
            "nt": ds.get("next_target"), "inv": ds.get("invalidation"), "wave": ds.get("wave_num")}


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


HORIZON_TXT = {
    "mko":     "Short-term · H1 entry, H4 trend · hours to a few days",
    "elliott": "Swing · Daily count, 4H/1H timing · days to weeks",
    "ai":      "Swing · Daily count, 4H/1H timing · days to weeks",
    "ews":     "Swing · 4H count · several days to 2-3 weeks",
}


EWS_STOCKS = ["AAPL", "AMZN", "BA", "CAT", "CRM", "DIS", "GOOGL", "GS", "HD", "JNJ",
              "JPM", "KO", "MCD", "MMM", "MSFT", "NVDA", "PG", "UNH", "V", "WMT"]


EWS_BARS_DAYS = 60                       # 60 giorni di 1H → ~360 barre 4H


EWS_BARS_DAYS_STOCKS = 150               # azioni: solo sessione regolare (2 barre 4H/giorno) → ~200 barre 4H


def _ews_pf(sym):
    return ".3f" if sym == "DXY" else _ew_pfmt(sym)


def _ews_num(v, pf):
    try:
        return format(float(v), "," + pf)
    except Exception:
        return "—"


def _ews_desk_note(df4, ds, td, pf):
    """2026-10-25: nota operativa breve dagli indicatori 4H (RSI, EMA21, MACD, divergenze, ATR),
    letta nel contesto dello scenario EW. Calcolata in codice, massimo 2 frasi, niente AI."""
    try:
        c = df4["close"].astype(float)
        last = float(c.iloc[-1])
        r = float(rsi(c).iloc[-1])
        e21 = float(ema(c, 21).iloc[-1])
        av = float(atr(df4).iloc[-1]) or abs(last) * 0.005
        ml, sl_ = macd(c)
        hist = (ml - sl_)
        h_now, h_prev = float(hist.iloc[-1]), float(hist.iloc[-4])
        stretch = (last - e21) / av
        wn = ds.get("wave_num")
        late = wn in ("5", "C") or "TERMINAL" in str(ds.get("bias", ""))
        notes = []
        # 0) 2026-11-13: divergenza RSI contro lo scenario PER PRIMA — il grafico la disegna, la nota
        #    non può ignorarla (Nvidia 4H: "Bullish divergence" sul grafico, assente dal testo)
        if td < 0 and ds.get("bullish_div"):
            notes.append("bullish RSI divergence on the chart: downside momentum is fading"
                         + (" — wave 3 may be close to its end, a wave 4 bounce is the next risk" if wn == "3" else "")
                         + "; tighten risk, no new shorts at these lows")
        elif td > 0 and ds.get("bearish_div"):
            notes.append("bearish RSI divergence on the chart: upside momentum is fading"
                         + (" — wave 3 may be close to its end, a wave 4 pullback is the next risk" if wn == "3" else "")
                         + "; tighten risk, no new longs at these highs")
        # 0b) 2026-11-13: rimbalzo già in corso dall'estremo dell'onda motrice — il prezzo non è più
        #     all'estremo, la correzione successiva (4 / B / nuovo ciclo) può essere già partita
        #     (Caterpillar 4H: onda 3 a 555 = 1.96×W1, prezzo risalito a 599, nota "momentum is building")
        eng = ds.get("engine") or {}
        pvs = eng.get("pivots") or []
        if not notes and wn in ("3", "5", "C") and len(pvs) >= 2:
            ext, st0 = float(pvs[-1]["p"]), float(pvs[-2]["p"])
            leg = abs(ext - st0)
            back = (last - ext) * (-td)          # quanto il prezzo è tornato indietro dall'estremo
            if leg > 0 and back >= 2 * av and back / leg >= 0.10:
                nxt = {"3": "wave 4", "5": "the correction of the whole impulse", "C": "a new move"}[wn]
                side = "low" if td < 0 else "high"
                notes.append(f"price is {back / leg * 100:.0f}% off the wave {wn} {side} ({_ews_num(ext, pf)}): "
                             f"{nxt} may already be under way — wave {wn} continues only on a new {side} "
                             f"{'below' if td < 0 else 'above'} {_ews_num(ext, pf)}, "
                             f"no new {'shorts' if td < 0 else 'longs'} on this {'bounce' if td < 0 else 'pullback'} before a reversal")
        # 1) RSI agli estremi (in un'onda terminale = rischio di esaurimento, non "compra il ribasso")
        if late and ((r >= 70 and td > 0) or (r <= 30 and td < 0)):
            notes.append(f"RSI {r:.0f} {'overbought' if td > 0 else 'oversold'} in a terminal wave: exhaustion risk "
                         f"— protect profits, no new {'longs' if td > 0 else 'shorts'}")
        elif r <= 30:
            notes.append(f"RSI {r:.0f} oversold: possible pullback toward {_ews_num(e21, pf)} (EMA21) before the next leg lower "
                         "— better to sell rallies than to chase the move" if td < 0 else
                         f"RSI {r:.0f} oversold into the pullback: supports buying near the end of the correction, not before")
        elif r >= 70:
            notes.append(f"RSI {r:.0f} overbought: possible pullback toward {_ews_num(e21, pf)} (EMA21) before continuation "
                         "— better to buy dips than to chase the move" if td > 0 else
                         f"RSI {r:.0f} overbought into the bounce: supports selling near the end of the correction, not before")
        # 3) prezzo tirato lontano dalla media
        if len(notes) < 2 and 30 < r < 70 and abs(stretch) >= 2.0 and (stretch * td > 0):
            notes.append(f"price is {abs(stretch):.1f} ATR away from EMA21: stretched, entries on a retracement are safer")
        # 4) momentum letto sull'RSI — 2026-11-13: il grafico mostra l'RSI, non il MACD: la nota parla
        #    dell'indicatore che il lettore vede (valore e direzione sulle ultime 3 candele 4H)
        if len(notes) < 2 and td != 0:
            r_prev = float(rsi(c).iloc[-4])
            rising = r > r_prev
            zone = "above 50" if r >= 50 else "below 50"
            if (td > 0) == rising and ((r >= 50) == (td > 0)):
                notes.append(f"RSI {r:.0f} {'rising' if rising else 'falling'} {zone}: momentum is building in the direction of the scenario")
            elif (td > 0) == rising:
                # 2026-11-13: RSI che gira nel verso giusto ma ancora dal lato opposto di 50 non è momentum
                # confermato (3M 4H: "RSI 56 falling above 50: momentum is building" in uno scenario ribassista)
                notes.append(f"RSI {r:.0f} turning {'up' if td > 0 else 'lower'} but still {zone}: "
                             f"{'bullish' if td > 0 else 'bearish'} momentum is confirmed only on a move {'above' if td > 0 else 'below'} 50")
            elif late:
                notes.append(f"RSI {r:.0f} {'falling' if td > 0 else 'rising'} while price extends: momentum is fading, typical of a maturing terminal wave")
            elif wn in ("4", "B", "E"):
                notes.append(f"RSI {r:.0f} is moving with the {'pullback' if td > 0 else 'bounce'}, as expected in wave {wn}: "
                             f"an RSI turn back {'up' if td > 0 else 'down'} in the entry zone is the timing signal")
            else:
                notes.append(f"RSI {r:.0f} {'falling' if td > 0 else 'rising'} against the scenario — wait for confirmation")
        if not notes:
            return ""
        txt = "; ".join(notes[:2])
        return txt[0].upper() + txt[1:] + "."
    except Exception as e:
        logger.warning(f"EWS desk note: {e}")
        return ""


def _ews_build(sym, df4):
    """Conta le onde sul 4H e prepara grafico + testo (df4 già scaricato)."""
    ds = count_elliott_waves_engine(df4)
    eng = ds.get("engine")
    mkt = MARKETS[sym]
    pf = _ews_pf(sym)
    last = float(df4["close"].iloc[-1])
    td = ds.get("trade_dir", 0)
    bias = "🟢 Bullish" if td > 0 else "🔴 Bearish" if td < 0 else "⚪ Neutral — wait"
    if td != 0 and "TERMINAL" in str(ds.get("bias", "")):
        bias += " — terminal wave, late in the move"
    out = {"sym": sym, "name": mkt["name"], "emoji": mkt.get("emoji", "📊"), "eng": eng, "ds": ds,
           "last": last, "bias": bias, "td": td, "img": None, "text": ""}
    if not eng:
        return out
    wn = ds["wave_num"]
    tgt, inv = ds.get("conservative_target"), ds.get("invalidation")
    import html as _hn
    bias_txt = ("🟢 Bullish" if td > 0 else "🔴 Bearish" if td < 0 else "⚪ Neutral — wait")
    if td != 0 and "TERMINAL" in str(ds.get("bias", "")):
        bias_txt += " · terminal wave"
    count_txt = (f"<b>{ds['wave_desc']}</b>\n{eng['trend'].capitalize()} trend · {eng['degree']} degree" if eng.get("triangle")
                 else f"<b>Wave {wn} in progress</b>\n{eng['desc']} · {eng['degree']} degree")
    lines = [
        "<b>XENOS WAVE · ELLIOTT WAVE</b>",
        f"{mkt.get('emoji', '')} <b>{mkt['name']}</b> · {EWS_TF_TXT} · {datetime.utcnow():%d %b %Y}",
        f"<i>⏱ {HORIZON_TXT['ews']}</i>",
        "",
        count_txt,
        f"<b>Bias:</b> {bias_txt}",
    ]
    # target, ingresso e invalidazione con il criterio esatto — stessi valori del grafico
    _n = len(df4)
    _st = max(min(max(0, _n - 70), max(0, eng["pivots"][0]["i"] - 6)), _n - 300, 0)   # stessa finestra del grafico
    rng_ = float(df4["high"].iloc[_st:].max() - df4["low"].iloc[_st:].min()) or abs(last) * 0.01
    plan = _ew_target_plan(eng, _ewp_setup_from(ds), last, rng_, pf,
                           extreme=_ew_wave_extreme(df4, eng, td) if wn in ("3", "5", "A", "C") else None)
    waiting = wn in ("4", "B") or (wn == "E" and "likely complete" not in ds.get("wave_desc", ""))
    out["targets"] = [float(v) for v, _ in plan["targets"]]          # 2026-11-18: per gli Active Setups
    out["entry"] = ds.get("entry") if waiting else None
    lines.append("")
    if wn == "E" and td != 0 and "likely complete" in ds.get("wave_desc", ""):
        lines.append(f"<b>Trigger:</b> break of {_ews_num(eng.get('d_level'), pf)} (end of wave D)")
    elif waiting and td != 0:
        lines.append(f"<b>Entry zone:</b> {_ews_num(ds.get('entry'), pf)} · "
                     + (plan["entry_note"] or f"end of wave {wn}"))
    k0 = 2 if plan["reached"] else 1
    if (plan["targets"] or plan["reached"]) and td != 0:
        lines.append("<b>Targets</b>" + (f" — {plan['basis']}" if plan["basis"] else ""))
        if plan["reached"]:
            lines.append(f"  ✅ T1  {_ews_num(plan['reached'][0], pf)}  ·  {plan['reached'][1]}  ·  reached")
        for i_, (v, lab) in enumerate(plan["targets"], k0):
            lines.append(f"  🎯 T{i_}  {_ews_num(v, pf)}" + (f"  ·  {lab}" if lab else ""))
    if inv is not None:
        lines.append(f"<b>Invalidation:</b> {_ews_num(inv, pf)}" + (f" · {plan['inv_note']}" if plan["inv_note"] else ""))
    lines.append(f"<b>Last:</b> {_ews_num(last, pf)}")

    # nota da desk: piano operativo sulla posizione tecnica (ingresso, stop, R:R, trigger di
    # breakout/pullback, segnale di fine onda) + al massimo una lettura degli indicatori
    notes = _ews_trade_plan(ds, eng, plan, df4, last, td, pf, wn, waiting, k0)
    dn = _ews_desk_note(df4, ds, td, pf) if td != 0 else ""
    if dn:
        notes += [x.strip().rstrip(".") for x in dn.split(";") if x.strip()][:1]
    if eng.get("targets_reached"):
        _mn = _ew_mature_note(eng, wn, lambda v: _ews_num(v, pf))
        if _mn:
            # onda 4/B: la nota di maturità + il piano (ingresso solo su inversione, stop, R:R)
            notes = _mn + (notes[:1] if wn in ("4", "B") else [])
    if notes and notes[0].startswith("Price is back"):
        lines = [("<b>Bias:</b> ⚪ Count in doubt — stand aside" if x.startswith("<b>Bias:</b>") else x) for x in lines]
        notes = notes[:1]
    if notes:
        txt = ". ".join(n_[0].upper() + n_[1:] for n_ in notes[:3]) + "."
        lines += ["", f"📝 <b>Desk note</b>\n{_hn.escape(txt, quote=False)}"]
    out["text"] = "\n".join(lines)
    if len(out["text"]) > 1000:          # limite didascalia Telegram (1024): via la riga del criterio Fibonacci
        out["text"] = "\n".join(x.split(" — ")[0] if x.startswith("<b>Targets</b>") else x for x in lines)
    out["img"] = _ews_chart(sym, df4, eng, ds, pf)
    return out


def _ews_trade_plan(ds, eng, plan, df4, last, td, pf, wn, waiting, k0):
    """2026-10-26: piano operativo dalla posizione tecnica. Tutti i livelli vengono dal conteggio
    e dai dati reali (pivot, Fibonacci, EMA21, trendline 2-4): niente frasi generiche."""
    if td == 0 or not eng:
        return []
    num = lambda v: _ews_num(v, pf)
    pv = {x["label"]: x for x in eng.get("pivots", [])}
    inv = ds.get("invalidation")
    side = "long" if td > 0 else "short"
    buy_sell = "buy" if td > 0 else "sell"
    beyond = "below" if td > 0 else "above"          # lato dello stop
    n = len(df4)
    out = []
    try:
        e21 = float(ema(df4["close"].astype(float), 21).iloc[-1])
    except Exception:
        e21 = None

    def line_at(a, b):
        """valore oggi della retta per due pivot (a, b)."""
        if a not in pv or b not in pv or pv[b]["i"] == pv[a]["i"]:
            return None
        sl = (pv[b]["p"] - pv[a]["p"]) / (pv[b]["i"] - pv[a]["i"])
        return pv[b]["p"] + sl * (n - 1 - pv[b]["i"])

    tg = plan.get("targets") or []
    if eng.get("triangle"):
        if wn == "E" and "likely complete" not in ds.get("wave_desc", ""):
            out.append(f"Wait for wave E to end near {num(ds.get('entry'))}: {side} only on a break of "
                       f"{num(eng.get('d_level'))} (end of wave D), stop {beyond} {num(inv)}")
        elif wn == "E":
            out.append(f"Breakout trigger: {num(eng.get('d_level'))} (end of wave D) — {side} on the break, "
                       f"stop {beyond} {num(inv)}")
        else:
            out.append(f"Thrust out of the triangle: trail the stop {beyond} the end of wave E ({num(pv['E']['p'])}); "
                       "thrusts are fast and often end the larger move")
        return out

    if waiting:                                   # onda 4 o B: si aspetta il pullback/rimbalzo
        entry = ds.get("entry")
        brk = pv.get("3" if wn == "4" else "A", {}).get("p")
        rr = ""
        if entry is not None and inv is not None and tg and abs(inv - entry) > 0:
            rr = f", R:R ≈ 1:{abs(tg[-1][0] - entry) / abs(inv - entry):.1f} to T{k0 + len(tg) - 1}"
        word = "Pullback" if td > 0 else "Bounce"
        if entry is not None and (entry - last) * td < 0:
            out.append(f"{word} still under way toward {num(entry)} ({plan.get('entry_note') or 'entry zone'}): "
                       f"{buy_sell} there on a {'bullish' if td > 0 else 'bearish'} reversal candle, stop {beyond} "
                       f"{num(inv)}{rr}")
        else:
            out.append(f"Price is in the entry zone: {side} only after a {'bullish' if td > 0 else 'bearish'} "
                       f"reversal candle, stop {beyond} {num(inv)}{rr}")
        if brk is not None:
            out.append(f"A break of {num(brk)} (end of wave {'3' if wn == '4' else 'A'}) confirms wave "
                       f"{'5' if wn == '4' else 'C'} is under way — no chasing the breakout, wait for the retest")
        return out

    if plan.get("reached") and wn in ("5", "C"):
        rv, rlab = plan["reached"]
        out.append(f"T1 reached ({rlab}): the wave can complete at any time — no new {side}s, protect profits"
                   + (f"; T{k0} only on an extension" if tg else ""))
    elif plan.get("reached"):
        out.append("T1 reached: move the stop to break-even and trail it" + (f", next T{k0}" if tg else ""))
    elif tg:
        try:
            _atr = float(atr(df4).iloc[-1])
            _gap = abs(tg[0][0] - last)
            if _atr > 0 and _gap <= 0.5 * _atr:
                out.append(f"T{k0} is only {num(_gap)} away ({_gap / _atr:.1f} ATR): little room left, "
                           "no new entries at market")
        except Exception:
            pass

    if wn == "3":
        ext = _ew_wave_extreme(df4, eng, td)
        p1 = pv["1"]["p"]
        past1 = ext is not None and (ext - p1) * td > 0
        if past1 and (last - p1) * td < 0:
            # wave 3 aveva superato l'onda 1 ma il prezzo ci è tornato dentro: conteggio in dubbio
            return [f"Price is back {'below' if td > 0 else 'above'} the end of wave 1 ({num(p1)}): the impulse "
                    f"count is in doubt — stand aside until it recovers {num(p1)}; the count fails at {num(inv)}"]
        if e21 is not None and not out:
            if (e21 - last) * td < 0 and (inv is None or (e21 - inv) * td > 0):
                out.append(f"Trend leg: {buy_sell} pullbacks toward the EMA21 ({num(e21)}), stop {beyond} the end of "
                           f"wave 2 ({num(pv['2']['p'])})")
            else:
                out.append(f"Price is at the EMA21 ({num(e21)}): {side} only on a "
                           f"{'bullish' if td > 0 else 'bearish'} reversal candle, stop {beyond} {num(inv)}")
        if not past1:
            out.append(f"Wave 3 is confirmed only on a break of {num(p1)} (end of wave 1) — that is the breakout trigger")
        else:
            out.append(f"When wave 3 ends, wave 4 must hold {'above' if td > 0 else 'below'} {num(p1)} "
                       "(end of wave 1, no overlap)")
    elif wn == "5":
        tl = line_at("2", "4")
        if tl is not None and (last - tl) * td > 0:
            out.append(f"A break of the 2–4 trendline ({num(tl)}) would signal wave 5 complete and a correction "
                       f"of the whole move — exit {side}s there")
    elif wn == "A":
        out.append(f"First leg of the correction: after T1 expect a wave B {'bounce' if td < 0 else 'pullback'} "
                   f"— better to {buy_sell} the B {'rally' if td < 0 else 'dip'} than to chase wave A")
    elif wn == "C":
        tl = line_at("5", "B")
        if tl is not None and (last - tl) * td > 0:
            out.append(f"A break back through {num(tl)} (5–B trendline) would signal wave C complete — "
                       f"exit {side}s there")
    return out


def _ewp_rsi_panel(ax_r, ax_p, df, start, ds):
    """RSI 14 (Wilder) + 70/30 + divergenza evidenziata su prezzo e RSI, se il motore la segnala."""
    c = df["close"].astype(float)
    rs = rsi(c)
    seg = rs.iloc[start:].values
    x = np.arange(len(seg))
    ax_r.set_facecolor(EWP["panel"])
    for sp in ax_r.spines.values():
        sp.set_color(EWP["grid"])
    ax_r.grid(True, color=EWP["grid"], linewidth=0.5)
    ax_r.yaxis.tick_right()
    ax_r.tick_params(colors=EWP["muted"], labelsize=8)
    ax_r.axhspan(70, 100, color=EWP["corr"], alpha=0.07, zorder=1)
    ax_r.axhspan(0, 30, color=EWP["imp"], alpha=0.07, zorder=1)
    for lvl in (70, 30):
        ax_r.axhline(lvl, color=EWP["muted"], lw=0.6, ls=(0, (3, 3)), zorder=2)
    ax_r.plot(x, seg, color="#a78bfa", lw=1.2, zorder=3)
    ax_r.set_ylim(0, 100)
    ax_r.set_yticks([30, 70])
    ax_r.text(0.005, 0.86, "RSI 14", transform=ax_r.transAxes, color=EWP["muted"], fontsize=8.5, zorder=5)
    last_r = float(seg[-1]) if len(seg) and not np.isnan(seg[-1]) else None
    if last_r is not None:
        _ewp_tag(ax_r, last_r, f"{last_r:.0f}", "#a78bfa", fs=8.5)
        # 2026-10-29: niente "30"/"70" nascosti a metà dietro il cartellino del valore
        ax_r.set_yticklabels(["" if abs(t_ - last_r) < 9 else str(t_) for t_ in (30, 70)])
    # divergenza: stesso criterio del motore (ultima barra vs estremo delle 20 barre precedenti)
    for kind in ("bearish_div", "bullish_div"):
        if not ds.get(kind) or len(c) < 22:
            continue
        win = c.iloc[-20:-1]
        j = int(np.argmax(win.values)) if kind == "bearish_div" else int(np.argmin(win.values))
        i0 = len(c) - 20 + j - start
        i1 = len(c) - 1 - start
        if i0 < 0:
            continue
        col = EWP["corr"] if kind == "bearish_div" else "#34d399"
        ax_p.plot([i0, i1], [float(win.iloc[j]), float(c.iloc[-1])], color=col, lw=1.4, zorder=11)
        r0, r1 = float(rs.iloc[start + i0]), float(rs.iloc[-1])
        ax_r.plot([i0, i1], [r0, r1], color=col, lw=1.4, zorder=6)
        # 2026-10-29: scritta sopra (bearish) o sotto (bullish) il tratto, con contorno: non taglia la linea 70/30
        bear = kind == "bearish_div"
        ty = min(97, max(r0, r1) + 6) if bear else max(3, min(r0, r1) - 6)
        ax_r.text((i0 + i1) / 2, ty, "Bearish divergence" if bear else "Bullish divergence",
                  color=col, fontsize=8, ha="center", va="bottom" if bear else "top", zorder=7,
                  path_effects=[mpe.withStroke(linewidth=3, foreground=EWP["panel"])])
    m = len(seg)
    step = max(1, m // 7)
    ticks = list(range(0, m, step))
    ax_r.set_xticks(ticks)
    ax_r.set_xticklabels([df.index[start + i].strftime("%d %b") for i in ticks], fontsize=8.3)


def _ews_chart(sym, df4, eng, ds, pf):
    """Grafico 4H in stile report professionale (vedi _ew_pro_panel)."""
    if not CHARTS_AVAILABLE:
        return None
    try:
        plt.rcParams.update({"font.family": "monospace", "font.size": 7, "text.color": EWP["text"]})
        # 2026-10-26: pannello RSI sotto il prezzo — mostra ciò che la Desk note scrive
        # (ipercomprato/ipervenduto, divergenze). Stesso RSI di Wilder usato per la nota.
        fig = plt.figure(figsize=(8.6, 7.6), facecolor=EWP["bg"])
        ax = fig.add_axes([0.03, 0.27, 0.81, 0.635])
        start = _ew_pro_panel(ax, df4, eng, ds.get("engine_degrees"), pf, _ewp_setup_from(ds),
                              compact=False, base_bars=70, max_bars=300)
        plt.setp(ax.get_xticklabels(), visible=False)
        ax_r = fig.add_axes([0.03, 0.08, 0.81, 0.17], sharex=ax)
        _ewp_rsi_panel(ax_r, ax, df4, start, ds)
        mkt = MARKETS[sym]
        fig.text(0.03, 0.955, f"{mkt['name']}  ·  {EWS_TF_CHART}  ·  XenosFinance", fontsize=12, fontweight="bold",
                 color=EWP["text"], ha="left", va="center")
        fig.text(0.84, 0.955, datetime.utcnow().strftime("%d %b %Y  %H:%M UTC"), fontsize=8.5,
                 color=EWP["muted"], ha="right", va="center")
        # 2026-10-29: sottotitolo con lo scenario, così il grafico si legge anche senza didascalia
        td_ = ds.get("trade_dir", 0) or 0
        wn_ = ds.get("wave_num")
        if eng and eng.get("triangle"):
            sub = str(ds.get("wave_desc") or "Triangle")
        elif wn_:
            sub = f"Wave {wn_} in progress"
            if eng and eng.get("degree"):
                sub += f" · {eng['degree']} degree"
        else:
            sub = ""
        bias_ = "Bullish scenario" if td_ > 0 else "Bearish scenario" if td_ < 0 else "Neutral — wait"
        fig.text(0.03, 0.924, (sub + "  ·  " if sub else "") + bias_, fontsize=9,
                 color=EWP["imp"] if td_ > 0 else EWP["corr"] if td_ < 0 else EWP["muted"], ha="left", va="center")
        fig.text(0.03, 0.025, "XENOSFINANCE", fontsize=10, fontweight="bold", color="#2a3a55", ha="left")
        fig.text(0.84, 0.025, "Elliott Wave scenario · probabilities, not certainties",
                 fontsize=7.5, color=EWP["muted"], ha="right")
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=190, facecolor=EWP["bg"], edgecolor="none")
        plt.close(fig)
        return buf.getvalue()
    except Exception as e:
        logger.error(f"EWS chart {sym}: {e}", exc_info=True)
        try:
            plt.close("all")
        except Exception:
            pass
        return None

