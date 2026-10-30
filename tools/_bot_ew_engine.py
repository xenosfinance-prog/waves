import logging
logger=logging.getLogger('ewbot')
import os, sys, json, logging, re, xml.etree.ElementTree as ET
import asyncio
import time
import base64, hashlib
import numpy as np
import pandas as pd
import requests
from datetime import datetime, timedelta
import io
from threading import Thread
import difflib as _difflib
import re as _re
import pytz
MARKETS = {'EURUSD': {'name': 'EUR/USD', 'emoji': '💶', 'yf': 'EURUSD=X', 'cat': 'forex'}, 'GBPUSD': {'name': 'GBP/USD', 'emoji': '💷', 'yf': 'GBPUSD=X', 'cat': 'forex'}, 'USDJPY': {'name': 'USD/JPY', 'emoji': '💴', 'yf': 'USDJPY=X', 'cat': 'forex'}, 'AUDUSD': {'name': 'AUD/USD', 'emoji': '🇦🇺', 'yf': 'AUDUSD=X', 'cat': 'forex'}, 'USDCHF': {'name': 'USD/CHF', 'emoji': '🇨🇭', 'yf': 'USDCHF=X', 'cat': 'forex'}, 'USDCAD': {'name': 'USD/CAD', 'emoji': '🇨🇦', 'yf': 'USDCAD=X', 'cat': 'forex'}, 'NZDUSD': {'name': 'NZD/USD', 'emoji': '🇳🇿', 'yf': 'NZDUSD=X', 'cat': 'forex'}, 'GOLD': {'name': 'Gold', 'emoji': '🥇', 'yf': 'GC=F', 'cat': 'commodities'}, 'SILVER': {'name': 'Silver', 'emoji': '🥈', 'yf': 'SI=F', 'cat': 'commodities'}, 'OIL': {'name': 'Crude Oil', 'emoji': '🛢', 'yf': 'CL=F', 'cat': 'commodities'}, 'NGAS': {'name': 'Natural Gas', 'emoji': '⛽', 'yf': 'NG=F', 'cat': 'commodities'}, 'SPY': {'name': 'S&P 500', 'emoji': '📊', 'yf': 'SPY', 'cat': 'equity'}, 'NASDAQ': {'name': 'Nasdaq 100', 'emoji': '📈', 'yf': '^NDX', 'cat': 'equity'}, 'DJI': {'name': 'Dow Jones', 'emoji': '🇺🇸', 'yf': '^DJI', 'cat': 'equity'}, 'DXY': {'name': 'US Dollar Index', 'emoji': '💵', 'yf': 'DX-Y.NYB', 'cat': 'index'}, 'DAX': {'name': 'DAX 40', 'emoji': '🇩🇪', 'yf': '^GDAXI', 'cat': 'equity'}, 'SPX': {'name': 'S&P 500 Index', 'emoji': '📊', 'yf': '^GSPC', 'cat': 'equity'}, 'BTCUSD': {'name': 'Bitcoin', 'emoji': '₿', 'yf': 'BTC-USD', 'cat': 'crypto'}, 'ETHUSD': {'name': 'Ethereum', 'emoji': '💎', 'yf': 'ETH-USD', 'cat': 'crypto'}, 'XRPUSD': {'name': 'Ripple', 'emoji': '💧', 'yf': 'XRP-USD', 'cat': 'crypto'}, 'SOLUSD': {'name': 'Solana', 'emoji': '☀️', 'yf': 'SOL-USD', 'cat': 'crypto'}, 'DOGEUSD': {'name': 'Dogecoin', 'emoji': '🐶', 'yf': 'DOGE-USD', 'cat': 'crypto'}, 'ZECUSD': {'name': 'Zcash', 'emoji': '🔒', 'yf': 'ZEC-USD', 'cat': 'crypto'}, 'AAPL': {'name': 'Apple', 'emoji': '🍎', 'yf': 'AAPL', 'cat': 'bluechip'}, 'MSFT': {'name': 'Microsoft', 'emoji': '🪟', 'yf': 'MSFT', 'cat': 'bluechip'}, 'JPM': {'name': 'JPMorgan', 'emoji': '🏦', 'yf': 'JPM', 'cat': 'banks'}, 'V': {'name': 'Visa', 'emoji': '💳', 'yf': 'V', 'cat': 'bluechip'}, 'UNH': {'name': 'UnitedHealth', 'emoji': '🏥', 'yf': 'UNH', 'cat': 'bluechip'}, 'HD': {'name': 'Home Depot', 'emoji': '🏠', 'yf': 'HD', 'cat': 'bluechip'}, 'MCD': {'name': "McDonald's", 'emoji': '🍔', 'yf': 'MCD', 'cat': 'bluechip'}, 'CAT': {'name': 'Caterpillar', 'emoji': '🚜', 'yf': 'CAT', 'cat': 'bluechip'}, 'BA': {'name': 'Boeing', 'emoji': '✈️', 'yf': 'BA', 'cat': 'bluechip'}, 'DIS': {'name': 'Walt Disney', 'emoji': '🏰', 'yf': 'DIS', 'cat': 'bluechip'}, 'KO': {'name': 'Coca-Cola', 'emoji': '🥤', 'yf': 'KO', 'cat': 'bluechip'}, 'WMT': {'name': 'Walmart', 'emoji': '🛒', 'yf': 'WMT', 'cat': 'bluechip'}, 'JNJ': {'name': 'Johnson & Johnson', 'emoji': '💊', 'yf': 'JNJ', 'cat': 'bluechip'}, 'PG': {'name': 'Procter & Gamble', 'emoji': '🧴', 'yf': 'PG', 'cat': 'bluechip'}, 'MMM': {'name': '3M', 'emoji': '🔧', 'yf': 'MMM', 'cat': 'bluechip'}, 'NVDA': {'name': 'Nvidia', 'emoji': '🎮', 'yf': 'NVDA', 'cat': 'ai_tech'}, 'GOOGL': {'name': 'Alphabet', 'emoji': '🔍', 'yf': 'GOOGL', 'cat': 'ai_tech'}, 'META': {'name': 'Meta', 'emoji': '👥', 'yf': 'META', 'cat': 'ai_tech'}, 'AMZN': {'name': 'Amazon', 'emoji': '📦', 'yf': 'AMZN', 'cat': 'ai_tech'}, 'TSLA': {'name': 'Tesla', 'emoji': '⚡', 'yf': 'TSLA', 'cat': 'ai_tech'}, 'AMD': {'name': 'AMD', 'emoji': '💻', 'yf': 'AMD', 'cat': 'ai_tech'}, 'ORCL': {'name': 'Oracle', 'emoji': '☁️', 'yf': 'ORCL', 'cat': 'ai_tech'}, 'CRM': {'name': 'Salesforce', 'emoji': '💼', 'yf': 'CRM', 'cat': 'ai_tech'}, 'PLTR': {'name': 'Palantir', 'emoji': '🔭', 'yf': 'PLTR', 'cat': 'ai_tech'}, 'GS': {'name': 'Goldman Sachs', 'emoji': '💰', 'yf': 'GS', 'cat': 'banks'}, 'BAC': {'name': 'Bank of America', 'emoji': '🏛️', 'yf': 'BAC', 'cat': 'banks'}, 'WFC': {'name': 'Wells Fargo', 'emoji': '🐎', 'yf': 'WFC', 'cat': 'banks'}, 'MS': {'name': 'Morgan Stanley', 'emoji': '📊', 'yf': 'MS', 'cat': 'banks'}, 'C': {'name': 'Citigroup', 'emoji': '🌐', 'yf': 'C', 'cat': 'banks'}, 'BLK': {'name': 'BlackRock', 'emoji': '🖤', 'yf': 'BLK', 'cat': 'banks'}, 'EURGBP': {'name': 'EUR/GBP', 'emoji': '💶', 'yf': 'EURGBP=X', 'cat': 'forex_cross'}, 'EURJPY': {'name': 'EUR/JPY', 'emoji': '💶', 'yf': 'EURJPY=X', 'cat': 'forex_cross'}, 'GBPJPY': {'name': 'GBP/JPY', 'emoji': '💷', 'yf': 'GBPJPY=X', 'cat': 'forex_cross'}, 'AUDJPY': {'name': 'AUD/JPY', 'emoji': '🇦🇺', 'yf': 'AUDJPY=X', 'cat': 'forex_cross'}, 'CADJPY': {'name': 'CAD/JPY', 'emoji': '🇨🇦', 'yf': 'CADJPY=X', 'cat': 'forex_cross'}, 'CHFJPY': {'name': 'CHF/JPY', 'emoji': '🇨🇭', 'yf': 'CHFJPY=X', 'cat': 'forex_cross'}, 'EURAUD': {'name': 'EUR/AUD', 'emoji': '💶', 'yf': 'EURAUD=X', 'cat': 'forex_cross'}, 'EURCAD': {'name': 'EUR/CAD', 'emoji': '💶', 'yf': 'EURCAD=X', 'cat': 'forex_cross'}, 'EURCHF': {'name': 'EUR/CHF', 'emoji': '💶', 'yf': 'EURCHF=X', 'cat': 'forex_cross'}, 'GBPAUD': {'name': 'GBP/AUD', 'emoji': '💷', 'yf': 'GBPAUD=X', 'cat': 'forex_cross'}, 'GBPCAD': {'name': 'GBP/CAD', 'emoji': '💷', 'yf': 'GBPCAD=X', 'cat': 'forex_cross'}, 'AUDCAD': {'name': 'AUD/CAD', 'emoji': '🇦🇺', 'yf': 'AUDCAD=X', 'cat': 'forex_cross'}, 'AUDCHF': {'name': 'AUD/CHF', 'emoji': '🇦🇺', 'yf': 'AUDCHF=X', 'cat': 'forex_cross'}, 'NZDJPY': {'name': 'NZD/JPY', 'emoji': '🇳🇿', 'yf': 'NZDJPY=X', 'cat': 'forex_cross'}, 'CADCHF': {'name': 'CAD/CHF', 'emoji': '🇨🇦', 'yf': 'CADCHF=X', 'cat': 'forex_cross'}}
CL_ROLL_BDAYS = 2

def _cl_front_contract(now=None):
    now = now or datetime.utcnow()
    codes = 'FGHJKMNQUVXZ'

    def biz(d):
        return d.weekday() < 5 and (not (d.month == 12 and d.day == 25)) and (not (d.month == 1 and d.day == 1))
    today = now.date()
    for k in range(1, 4):
        m0 = now.month - 1 + k
        cy, cm = (now.year + m0 // 12, m0 % 12 + 1)
        py, pm = (cy, cm - 1) if cm > 1 else (cy - 1, 12)
        ref = datetime(py, pm, 25).date()
        while not biz(ref):
            ref -= timedelta(days=1)
        lt, n = (ref, 0)
        while n < 3:
            lt -= timedelta(days=1)
            if biz(lt):
                n += 1
        roll, n = (lt, 0)
        while n < CL_ROLL_BDAYS:
            roll -= timedelta(days=1)
            if biz(roll):
                n += 1
        if today <= roll:
            return f'CL{codes[cm - 1]}{str(cy)[-2:]}.NYM'
    return None

def yf_front(sym):
    """CL=F → contratto front month esplicito; ogni altro simbolo invariato."""
    if sym == 'CL=F':
        try:
            return _cl_front_contract() or sym
        except Exception:
            return sym
    return sym

def _tv_anchor(yf):
    if yf.endswith('=F'):
        return ('America/New_York', 18 * 60)
    if yf.endswith('=X'):
        return ('America/New_York', 17 * 60)
    if yf in ('^NDX', '^DJI', '^GSPC', 'SPY') or re.fullmatch('[A-Z]{1,5}(\\.[A-Z])?', yf or ''):
        return ('America/New_York', 9 * 60 + 30)
    if yf == '^GDAXI':
        return ('Europe/Berlin', 9 * 60)
    return (None, 0)

def resample_4h_tv(df1, yf):
    agg = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
    tz, off = _tv_anchor(yf or '')
    if not tz:
        return df1.resample('4h', origin='epoch').agg(agg).dropna()
    idx = df1.index
    utc = idx.tz_localize('UTC') if idx.tz is None else idx.tz_convert('UTC')
    loc = utc.tz_convert(tz).tz_localize(None)
    sh = loc - pd.Timedelta(minutes=off)
    key_loc = sh.floor('4h') + pd.Timedelta(minutes=off)
    start_utc = (utc - (loc - key_loc)).tz_localize(None)
    out = df1.groupby(start_utc).agg(agg).dropna()
    out.index.name = None
    return out

def fetch_data(symbol, days=365, interval='1d'):
    if interval == '4h':
        df1 = fetch_data(symbol, days=days, interval='1h')
        if df1 is None or len(df1) == 0:
            return None
        df4 = resample_4h_tv(df1, MARKETS.get(symbol, {}).get('yf', ''))
        logger.info(f'✅ {symbol}: {len(df4)} bars (4h from 1h, TradingView session alignment)')
        return df4
    try:
        yf = MARKETS[symbol]['yf']
        end = int(datetime.now().timestamp())
        start = int((datetime.now() - timedelta(days=days)).timestamp())
        url = f'https://query1.finance.yahoo.com/v8/finance/chart/{yf_front(yf)}'
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, params={'period1': start, 'period2': end, 'interval': interval}, timeout=15)
        d = r.json()
        if yf_front(yf) != yf and (not (d.get('chart') or {}).get('result')):
            r = requests.get(f'https://query1.finance.yahoo.com/v8/finance/chart/{yf}', headers={'User-Agent': 'Mozilla/5.0'}, params={'period1': start, 'period2': end, 'interval': interval}, timeout=15)
            d = r.json()
        res = d['chart']['result'][0]
        q = res['indicators']['quote'][0]
        df = pd.DataFrame({'open': q['open'], 'high': q['high'], 'low': q['low'], 'close': q['close'], 'volume': q.get('volume', [0] * len(q['open']))}, index=pd.to_datetime(res['timestamp'], unit='s'))
        df = df.dropna()
        if len(df) > 0:
            last_ts = df.index[-1]
            age_hours = (pd.Timestamp.now(tz='UTC') - last_ts.tz_localize('UTC') if last_ts.tzinfo is None else pd.Timestamp.now(tz='UTC') - last_ts).total_seconds() / 3600
            stale_threshold = {'1h': 4, '4h': 12, '5m': 1, '15m': 2, '30m': 3}.get(interval, 72)
            if age_hours > stale_threshold:
                logger.warning(f'⚠️ {symbol} ({interval}): last candle is {age_hours:.1f}h old — may be stale')
            meta = res.get('meta', {})
            live_price = float(meta.get('regularMarketPrice') or 0)
            if live_price > 0 and interval in ('1h', '5m', '15m'):
                df.iloc[-1, df.columns.get_loc('close')] = live_price
                df.iloc[-1, df.columns.get_loc('high')] = max(float(df['high'].iloc[-1]), live_price)
                df.iloc[-1, df.columns.get_loc('low')] = min(float(df['low'].iloc[-1]), live_price)
        logger.info(f'✅ {symbol}: {len(df)} bars ({interval})')
        return df
    except Exception as e:
        logger.error(f'❌ {symbol}: {e}')
        return None

def ema(s, span):
    return s.ewm(span=span, adjust=False).mean()

def rsi(s, p=14):
    d = s.diff()
    g = d.clip(lower=0).ewm(alpha=1 / p, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(alpha=1 / p, adjust=False).mean()
    return 100 - 100 / (1 + g / l.replace(0, np.nan))

def macd(s):
    e12, e26 = (ema(s, 12), ema(s, 26))
    return (e12 - e26, ema(e12 - e26, 9))

def atr(df, p=14):
    hl = df['high'] - df['low']
    hc = (df['high'] - df['close'].shift()).abs()
    lc = (df['low'] - df['close'].shift()).abs()
    return pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(p).mean()

def validate_elliott_with_cfd(wave_num: str, price_data: 'pd.Series', volume_data: 'pd.Series') -> dict:
    """
    Valida l'onda di Elliott corrente usando la fluidodinamica computazionale.
    Adattamento Python del framework CFD originale per bot Telegram.

    wave_num: stringa ('1','2','3','4','5','A','B','C','?')
    price_data:  pd.Series dei close (almeno 30 barre)
    volume_data: pd.Series dei volumi (può essere zero per forex → usa range H-L proxy)
    """
    import numpy as np
    n = min(20, len(price_data))
    prices = price_data.iloc[-n:].astype(float)
    volumes = volume_data.iloc[-n:].astype(float)
    vol_mean = float(volumes.mean())
    if vol_mean < 1e-06:
        vol_proxy = float(prices.diff().abs().mean())
        vol_mean = vol_proxy if vol_proxy > 1e-09 else 1.0
        volumes = prices.diff().abs().fillna(vol_mean)
    velocity_series = prices.diff().dropna()
    velocity = float(velocity_series.iloc[-1])
    price_velocity = float(velocity_series.mean())
    price_speed = float(velocity_series.abs().mean())
    ke_series = 0.5 * volumes.iloc[1:] * velocity_series ** 2
    ke_current = float(ke_series.iloc[-1])
    ke_mean = float(ke_series.mean()) if len(ke_series) > 0 else ke_current
    ke_5ago = float(ke_series.iloc[-5]) if len(ke_series) >= 5 else ke_current
    pct_vol = float(prices.pct_change().std())
    viscosity = pct_vol / (vol_mean + 1e-09)
    reynolds_series = velocity_series.abs() / (viscosity + 1e-09)
    reynolds_current = float(reynolds_series.iloc[-1])
    reynolds_mean = float(reynolds_series.mean()) if len(reynolds_series) > 0 else reynolds_current
    validation = 'WAIT'
    notes = ''
    if wave_num == '3':
        if reynolds_current > reynolds_mean * 1.5 and ke_current > ke_mean:
            validation = 'STRONG_CONFIRMATION'
            notes = 'Reynolds peak + high KE: classic Wave 3 impulse structure'
        elif reynolds_current > reynolds_mean * 1.2:
            validation = 'MODERATE_CONFIRMATION'
            notes = 'Reynolds elevated but KE not yet at peak — early W3 or extension'
        else:
            validation = 'WAIT'
            notes = 'Insufficient thrust for Wave 3 — may be W1 or corrective'
    elif wave_num == '5':
        if ke_current < ke_5ago * 0.85:
            validation = 'WAVE_EXHAUSTION_WARNING'
            notes = f'KE declining ({ke_current:.4f} < {ke_5ago:.4f}): terminal wave — reduce exposure'
        elif ke_current < ke_mean * 0.9:
            validation = 'WEAKENING_IMPULSE'
            notes = 'KE below average: W5 may be truncated — tight trailing stops advised'
        else:
            validation = 'MODERATE_CONFIRMATION'
            notes = 'KE still elevated — W5 extension possible before reversal'
    elif wave_num == '4':
        if reynolds_current < reynolds_mean * 0.5:
            validation = 'CORRECTION_STABILIZED'
            notes = 'Low Reynolds: market consolidating — W4 near completion, prepare W5 entry'
        elif reynolds_current < reynolds_mean * 0.8:
            validation = 'CORRECTION_IN_PROGRESS'
            notes = 'Reynolds moderately low — W4 correction ongoing'
        else:
            validation = 'WAIT'
            notes = 'Reynolds still high — correction may not be complete'
    elif wave_num == '2':
        if reynolds_current < reynolds_mean * 0.7 and ke_current < ke_mean:
            validation = 'CORRECTION_STABILIZED'
            notes = 'Low energy retracement — W2 near completion, W3 setup forming'
        else:
            validation = 'CORRECTION_IN_PROGRESS'
            notes = 'Energy still present in correction — wait for Reynolds to drop'
    elif wave_num in ('A', 'C'):
        if reynolds_current > reynolds_mean and ke_current > ke_mean * 0.8:
            validation = 'STRONG_CONFIRMATION'
            notes = f'Wave {wave_num}: impulsive corrective leg confirmed by CFD'
        else:
            validation = 'MODERATE_CONFIRMATION'
            notes = f'Wave {wave_num}: correction underway but energy moderate'
    elif wave_num == 'B':
        if reynolds_current < reynolds_mean * 0.8:
            validation = 'BULL_TRAP_CONFIRMED'
            notes = 'Low Reynolds bounce: classic Wave B bull trap — prepare short for C'
        else:
            validation = 'WAIT'
            notes = 'B wave energy too high — may still be impulsive, not corrective'
    elif wave_num == '1':
        if reynolds_current > reynolds_mean and velocity > 0:
            validation = 'IMPULSE_STARTING'
            notes = 'Reynolds rising from low base — possible Wave 1 initiation'
        else:
            validation = 'WAIT'
            notes = 'Insufficient directional energy for W1 confirmation'
    else:
        validation = 'WAIT'
        notes = 'Wave count uncertain — CFD cannot confirm'
    flow_type = 'TURBULENT/IMPULSIVE' if reynolds_current > reynolds_mean else 'LAMINAR/CONGESTION'
    return {'wave': wave_num, 'cfd_status': validation, 'energy_flow': round(ke_current, 6), 'ke_mean': round(ke_mean, 6), 'reynolds': round(reynolds_current, 2), 'reynolds_mean': round(reynolds_mean, 2), 'viscosity': round(viscosity, 6), 'flow_type': flow_type, 'notes': notes}

def identify_wave_degree(df):
    c = df['close']
    r = (c.max() - c.min()) / c.mean() * 100
    if r > 30:
        return 'Primary'
    elif r > 15:
        return 'Intermediate'
    elif r > 7:
        return 'Minor'
    else:
        return 'Minute'
EW_ENGINE_RULES = {'w2': (0.28, 0.786), 'w3_ext': (1.0, 1.272, 1.618, 2.0, 2.618), 'w3_tol': 0.15, 'w4': (0.15, 0.65), 'b': (0.236, 1.0)}
EW_ENGINE_DEGREES = [('Minor', 4), ('Intermediate', 8), ('Primary', 16)]
EW_WAVE_LABELS = ['0', '1', '2', '3', '4', '5', 'A', 'B', 'C']

def _ew_in(x, r):
    return r[0] <= x <= r[1]

def _ew_near(x, arr, tol):
    return any((abs(x / e - 1) <= tol for e in arr))

def ew_engine_zigzag(highs, lows, length):
    """Pivot simmetrici (length barre a sx/dx) su high/low reali + tratto in corso fino all'ultima barra."""
    n = len(highs)
    piv = []
    for i in range(length, n - length):
        h, l = (highs[i], lows[i])
        is_h = is_l = True
        for j in range(i - length, i + length + 1):
            if j == i:
                continue
            if highs[j] > h or (j < i and highs[j] == h):
                is_h = False
            if lows[j] < l or (j < i and lows[j] == l):
                is_l = False
            if not is_h and (not is_l):
                break
        if is_h and is_l:
            continue
        if is_h:
            piv.append({'i': i, 'p': h, 'hi': True})
        if is_l:
            piv.append({'i': i, 'p': l, 'hi': False})
    zz = []
    for q in piv:
        if not zz:
            zz.append(q)
            continue
        last = zz[-1]
        if last['hi'] == q['hi']:
            if q['p'] > last['p'] if q['hi'] else q['p'] < last['p']:
                zz[-1] = q
            continue
        if q['p'] > last['p'] if q['hi'] else q['p'] < last['p']:
            zz.append(q)
    if not zz:
        return zz
    first, anc = (zz[0], None)
    for k in range(0, first['i']):
        va = lows[k] if first['hi'] else highs[k]
        if anc is None or (va < anc['p'] if first['hi'] else va > anc['p']):
            anc = {'i': k, 'p': va, 'hi': not first['hi']}
    if anc and (anc['p'] < first['p'] if first['hi'] else anc['p'] > first['p']):
        zz.insert(0, anc)
    last = zz[-1]
    for k in range(last['i'] + 1, n):
        v0 = highs[k] if last['hi'] else lows[k]
        if v0 > last['p'] if last['hi'] else v0 < last['p']:
            last = {'i': k, 'p': v0, 'hi': last['hi']}
            zz[-1] = last
    best = None
    for k in range(last['i'] + 1, n):
        v = lows[k] if last['hi'] else highs[k]
        if best is None or (v < best['p'] if last['hi'] else v > best['p']):
            best = {'i': k, 'p': v, 'hi': not last['hi']}
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
            if not _ew_in(r2, R['w2']) if conf else not 0 < r2 < 1:
                return False
        elif i == 3:
            if not P[3] > P[2]:
                return False
            if conf and (not P[3] > P[1] or not _ew_near(ln(2, 3) / ln(0, 1), R['w3_ext'], R['w3_tol'])):
                return False
        elif i == 4:
            r4 = (P[3] - P[4]) / (P[3] - P[2])
            if not P[4] > P[1]:
                return False
            if not _ew_in(r4, R['w4']) if conf else not 0 < r4 < 1:
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
            if not _ew_in(rb, R['b']) if conf else not 0 < rb < 1:
                return False
        elif i == 8:
            if not P[8] < P[7]:
                return False
    return True

def ew_engine_match(zz):
    end = len(zz) - 1
    for s in range(max(0, end - 8), end - 2):
        d = -1 if zz[s]['hi'] else 1
        if ew_engine_check([d * z['p'] for z in zz[s:]]):
            return (s, d)
    return None

def ew_engine_describe(s, d, zz, index, degree, length):
    pts = zz[s:]
    k = len(pts)
    p = [z['p'] for z in pts]
    wave = EW_WAVE_LABELS[k - 1]
    corrective = wave in ('A', 'B', 'C')
    wave_dir = d if wave in ('1', '3', '5', 'B') else -d
    bias_dir = -d if corrective else d
    L = lambda a, b: abs(p[b] - p[a])
    lv = lambda base, sign, size, rs: [{'r': r, 'v': base + sign * size * r} for r in rs]
    fibs, inval, basis = ([], None, '')
    if wave == '3':
        fibs, inval, basis = (lv(p[2], d, L(0, 1), [1, 1.618, 2.618]), p[2], 'extension of wave 1 from end of wave 2')
    elif wave == '4':
        fibs, inval, basis = (lv(p[3], -d, L(2, 3), [0.236, 0.382, 0.5]), p[1], 'retracement of wave 3')
    elif wave == '5':
        fibs, inval, basis = (lv(p[4], d, L(0, 1), [0.618, 1, 1.618]), p[4], 'wave 1 length projected from end of wave 4')
    elif wave == 'A':
        fibs, inval, basis = (lv(p[5], -d, L(0, 5), [0.382, 0.5, 0.618]), p[5], 'retracement of the whole 1-5 impulse')
    elif wave == 'B':
        fibs, inval, basis = (lv(p[6], d, L(5, 6), [0.382, 0.5, 0.618]), p[5], 'retracement of wave A')
    elif wave == 'C':
        fibs, inval, basis = (lv(p[7], -d, L(5, 6), [0.618, 1, 1.618]), p[7], 'wave A length projected from end of wave B')
    cur, tgt, reached = (p[-1], None, False)
    for f in fibs:
        if (f['v'] - cur) * wave_dir > 0:
            tgt = f
            break
    if tgt is None and fibs:
        tgt, reached = (fibs[-1], True)
    return {'degree': degree, 'len': length, 'k': k, 'wave': wave, 'trend': 'bullish' if d > 0 else 'bearish', 'structure': 'correction' if corrective else 'impulse', 'wave_up': wave_dir > 0, 'bias_dir': bias_dir, 'dir': d, 'desc': f"ABC correction of a {('bullish' if d > 0 else 'bearish')} impulse" if corrective else f"{('Bullish' if d > 0 else 'Bearish')} impulse", 'pivots': [{'label': EW_WAVE_LABELS[n], 'i': z['i'], 'p': z['p'], 'hi': z['hi'], 'time': str(index[z['i']])[:16]} for n, z in enumerate(pts)], 'fibs': fibs, 'fib_basis': basis, 'target': tgt['v'] if tgt else None, 'target_ratio': tgt['r'] if tgt else None, 'targets_reached': reached, 'inval': inval}
EW_TRI_MIN_LEG = 0.2

def ew_engine_triangle(zz, index, degree, length):
    n = len(zz)
    best = None
    for npts, phase in ((7, 'thrust'), (6, 'E')):
        s = n - npts
        if s < 1:
            continue
        pts = zz[s:]
        d = 1 if pts[0]['hi'] else -1
        q = [d * z['p'] for z in pts]
        qprev = d * zz[s - 1]['p']
        la = q[0] - q[1]
        if la <= 0 or q[0] - qprev <= la:
            continue
        if not (q[2] < q[0] and q[4] < q[2] and (q[3] > q[1]) and (q[5] > q[3])):
            continue
        legs = [q[2] - q[1], q[2] - q[3], q[4] - q[3], q[4] - q[5]]
        if min(legs) < EW_TRI_MIN_LEG * la:
            continue
        p = [z['p'] for z in pts]
        if phase == 'thrust':
            if not q[6] > q[4] - 0.25 * legs[3]:
                continue
            base = p[5]
            fibs = [{'r': r, 'v': base + d * la * r} for r in (0.618, 1.0, 1.272)]
            cur = p[6]
            tgt = next((f for f in fibs if (f['v'] - cur) * d > 0), fibs[-1])
            reached = (fibs[-1]['v'] - cur) * d <= 0
            labels = ['0', 'A', 'B', 'C', 'D', 'E', '5']
            out = {'wave': '5', 'wave_up': d > 0, 'inval': p[5], 'target': tgt['v'], 'target_ratio': tgt['r'], 'targets_reached': reached, 'fibs': fibs, 'entry': cur, 'fib_basis': 'widest part of the triangle (wave A) projected from the end of wave E', 'desc': f"Thrust out of a contracting triangle ({('bullish' if d > 0 else 'bearish')} trend)"}
        else:
            ez = [{'r': r, 'v': p[4] - d * legs[2] * r} for r in (0.618, 0.786)]
            entry = ez[0]['v'] if q[5] > d * ez[0]['v'] else p[5]
            tgt_v = entry + d * la
            labels = ['0', 'A', 'B', 'C', 'D', 'E']
            out = {'wave': 'E', 'wave_up': d < 0, 'inval': p[3], 'target': tgt_v, 'target_ratio': 1.0, 'targets_reached': False, 'fibs': ez, 'entry': entry, 'fib_basis': 'widest part of the triangle (wave A) projected from the end of wave E', 'desc': f"Contracting triangle, wave E in progress ({('bullish' if d > 0 else 'bearish')} trend)"}
        out.update({'la': la, 'd_level': p[4], 'e_level': p[5], 'e_leg': legs[3], 'degree': degree, 'len': length, 'k': len(pts), 'trend': 'bullish' if d > 0 else 'bearish', 'structure': 'triangle', 'triangle': True, 'bias_dir': d, 'dir': d, 'pivots': [{'label': labels[i], 'i': z['i'], 'p': z['p'], 'hi': z['hi'], 'time': str(index[z['i']])[:16]} for i, z in enumerate(pts)]})
        best = out
        break
    return best

def ew_engine_run(df):
    highs = df['high'].astype(float).tolist()
    lows = df['low'].astype(float).tolist()
    degrees = []
    triangles = []
    for name, length in EW_ENGINE_DEGREES:
        zz = ew_engine_zigzag(highs, lows, length)
        m = ew_engine_match(zz) if len(zz) >= 4 else None
        degrees.append(ew_engine_describe(m[0], m[1], zz, df.index, name, length) if m else {'degree': name, 'len': length, 'none': True})
        try:
            t = ew_engine_triangle(zz, df.index, name, length) if len(zz) >= 7 else None
            if t:
                triangles.append(t)
        except Exception as e_tri:
            logger.warning(f'triangle scan {name}: {e_tri}')
    _ladder = ['Subminuette', 'Minuette', 'Minute', 'Minor', 'Intermediate', 'Primary']
    try:
        _sec = pd.Series(df.index).diff().dt.total_seconds().dropna().quantile(0.2)
    except Exception:
        _sec = 86400
    _base = 3 if _sec >= 20 * 3600 else 1 if _sec >= 3 * 3600 else 0
    for _o in degrees + triangles:
        _step = [n for n, _ in EW_ENGINE_DEGREES].index(_o['degree']) if _o['degree'] in [n for n, _ in EW_ENGINE_DEGREES] else 0
        _o['degree'] = _ladder[min(_base + _step, len(_ladder) - 1)]
    valid = sorted([o for o in degrees if not o.get('none')], key=lambda o: (-o['k'], -o['len']))
    tri = sorted(triangles, key=lambda o: (o['wave'] != '5', -o['len']))
    primary = valid[0] if valid else None
    if tri and (primary is None or primary['pivots'][0]['i'] >= tri[0]['pivots'][1]['i']):
        primary = tri[0]
    return {'primary': primary, 'degrees': degrees, 'triangle': tri[0] if tri else None}

def _ew_fmt(v):
    v = float(v)
    return f'{v:.5f}' if abs(v) < 10 else f'{v:.2f}'

def count_elliott_waves_engine(df):
    """
    Conteggio EW dal motore validato, restituito nello stesso formato di
    count_elliott_waves_deepscan (stesse chiavi) così il resto del bot non cambia.
    Chiavi nuove: engine, engine_degrees, trade_dir (+1 long / -1 short / 0), entry.
    """
    c = df['close']
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
    bearish_div = p >= p_pk20 * 0.998 and rv < rsi_pk20 - 5
    bullish_div = p <= p_lw20 * 1.002 and rv > rsi_lw20 + 5
    res = ew_engine_run(df)
    e = res['primary']
    circ = {'1': '①', '2': '②', '3': '③', '4': '④', '5': '⑤', 'A': '🅐', 'B': '🅑', 'C': '🅒'}
    extended = truncated = False
    w1s = w1e = w1z = 0.0
    w3e = None
    pivots = []
    if e is None:
        wn, wp = ('?', 'TRANSITION')
        wd = 'Transition — no rule-valid wave count'
        wc = 'No impulse or ABC structure passes the Fibonacci rules on any degree. Wait for structure.'
        direction_up, trade_dir, entry = (True, 0, p)
        inv, nt, ct = (p - av, p + av * 2.0, p + av)
        action = '⏳ WAIT — No rule-valid wave count. No setup.'
        bi = 'NEUTRAL'
        degree = identify_wave_degree(df)
    elif e.get('triangle'):
        wn = e['wave']
        d = e['dir']
        direction_up = d > 0
        degree = e['degree']
        pv = [x['p'] for x in e['pivots']]
        pivots = [{'type': 'H' if x['hi'] else 'L', 'idx': x['i'], 'price': x['p']} for x in e['pivots']]
        w1s, w1e = (pv[0], pv[1])
        w1z = abs(w1e - w1s)
        inv = e['inval']
        side = '🟢 LONG' if d > 0 else '🔴 SHORT'
        trade_dir = d
        if wn == '5':
            entry, ct = (p, e['target'])
            nt = e['fibs'][-1]['v']
            wp = 'IMPULSIVE'
            wd = 'Wave ⑤ — thrust out of a contracting triangle'
            action = f'{side} — triangle complete, thrust in progress, target {_ew_fmt(ct)} (widest part of the triangle), invalidation {_ew_fmt(inv)} (end of wave E)'
            bi = 'BULLISH' if direction_up else 'BEARISH'
            if e.get('targets_reached'):
                trade_dir, bi = (0, 'NEUTRAL')
                action = f'⏳ WAIT — the thrust has already reached the triangle targets (last {_ew_fmt(ct)}): no new entry. Invalidation {_ew_fmt(inv)}'
        elif (p - e['e_level']) * d > 0.382 * e['e_leg']:
            entry = p
            ct = nt = e['e_level'] + d * e['la']
            wp = 'CORRECTIVE TRIANGLE'
            wd = 'Wave E of a contracting triangle — likely complete, thrust starting'
            action = f"{side} — wave E likely complete at {_ew_fmt(e['e_level'])}, thrust starting: confirmation on a break of {_ew_fmt(e['d_level'])} (end of wave D), target {_ew_fmt(ct)}, invalidation {_ew_fmt(inv)} (end of wave C)"
            bi = 'TRIANGLE — LONG SETUP' if direction_up else 'TRIANGLE — SHORT SETUP'
            e['target'] = ct
        else:
            entry, ct = (e['entry'], e['target'])
            nt = ct
            wp = 'CORRECTIVE TRIANGLE'
            wd = 'Wave E of a contracting triangle — last leg before the thrust'
            action = f'{side} — wait for wave E to end near {_ew_fmt(entry)}, then trade the thrust: target {_ew_fmt(ct)}, invalidation {_ew_fmt(inv)} (end of wave C)'
            bi = 'TRIANGLE — LONG SETUP' if direction_up else 'TRIANGLE — SHORT SETUP'
        wc = f'Contracting triangle A-B-C-D-E ({degree} degree): lower highs and higher lows, each leg shorter than the previous. Thrust target = widest part of the triangle (wave A) projected from the end of wave E.'
    else:
        wn = e['wave']
        d = e['dir']
        direction_up = d > 0
        pv = [x['p'] for x in e['pivots']]
        fibs = e['fibs']
        tgt = e['target']
        degree = e['degree']
        w1s, w1e = (pv[0], pv[1])
        w1z = abs(w1e - w1s)
        w3e = pv[3] if len(pv) > 4 else None
        pivots = [{'type': 'H' if x['hi'] else 'L', 'idx': x['i'], 'price': x['p']} for x in e['pivots']]
        try:
            ti = [f['v'] for f in fibs].index(tgt)
            nxt = fibs[ti + 1]['v'] if ti + 1 < len(fibs) else tgt
        except ValueError:
            nxt = tgt
        inv = e['inval']
        lvl_txt = ', '.join((f"{f['r']:g} = {_ew_fmt(f['v'])}" for f in fibs))
        side = lambda td: '🟢 LONG' if td > 0 else '🔴 SHORT'
        if wn in ('3', '5', 'A', 'C'):
            trade_dir = d if wn in ('3', '5') else -d
            entry, ct, nt = (p, tgt, nxt)
        elif wn == '4':
            trade_dir = d
            entry = tgt
            ct = pv[3]
            nt = entry + d * w1z
        else:
            trade_dir = -d
            entry = tgt
            ct = pv[6]
            nt = entry - d * abs(pv[5] - pv[6])
        if wn == '3':
            extended = abs(pv[3] - pv[2]) / w1z > 2.618 if w1z > 0 else False
            wp = 'IMPULSIVE'
            wd = f"Wave ③ — {('Extended ' if extended else '')}impulse in progress"
            action = f'{side(trade_dir)} — wave 3 in progress, target {_ew_fmt(ct)}, invalidation {_ew_fmt(inv)} (end of wave 2)'
            bi = 'BULLISH' if direction_up else 'BEARISH'
        elif wn == '4':
            wp = 'CORRECTIVE'
            wd = 'Wave ④ — corrective pullback in progress'
            action = f'{side(trade_dir)} — wait for wave 4 near {_ew_fmt(entry)}, invalidation {_ew_fmt(inv)} (wave 1 territory)'
            bi = 'PULLBACK — LONG SETUP' if direction_up else 'BOUNCE — SHORT SETUP'
        elif wn == '5':
            wp = 'IMPULSIVE'
            wd = 'Wave ⑤ — terminal impulse in progress'
            action = f'⚠️ Terminal wave — trail stops, no new entries. Projection {_ew_fmt(ct)}, invalidation {_ew_fmt(inv)}'
            bi = 'BULLISH (TERMINAL ⚠️)' if direction_up else 'BEARISH (TERMINAL ⚠️)'
        elif wn == 'A':
            wp = 'CORRECTIVE ABC'
            wd = 'Wave 🅐 — first corrective leg in progress'
            action = f'{side(trade_dir)} — wave A in progress, target {_ew_fmt(ct)}, invalidation {_ew_fmt(inv)} (end of wave 5)'
            bi = 'BEARISH' if direction_up else 'BULLISH'
        elif wn == 'B':
            wp = 'CORRECTIVE ABC'
            wd = 'Wave 🅑 — corrective counter-move in progress'
            action = f'{side(trade_dir)} — wait for wave B near {_ew_fmt(entry)} to trade wave C, invalidation {_ew_fmt(inv)}'
            bi = 'CORRECTIVE BOUNCE — SHORT SETUP' if direction_up else 'CORRECTIVE DROP — LONG SETUP'
        else:
            wp = 'CORRECTIVE ABC'
            wd = 'Wave 🅒 — final corrective leg in progress'
            action = f'{side(trade_dir)} — wave C in progress, target {_ew_fmt(ct)}, invalidation {_ew_fmt(inv)} (end of wave B)'
            bi = 'BEARISH (TERMINAL ⚠️)' if direction_up else 'BULLISH (TERMINAL ⚠️)'
        wc = f"Rule-validated count ({degree} degree, {e['desc']}). Fibonacci ({e['fib_basis']}): {lvl_txt}."
        if e.get('targets_reached'):
            if wn in ('4', 'B'):
                entry = p
            else:
                trade_dir = 0
                bi = 'NEUTRAL'
                _mn = _ew_mature_note(e, wn, _ew_fmt)
                action = '⏳ WAIT — ' + '. '.join(_mn) + '.' if _mn else f'⏳ WAIT — wave {wn} has already passed its last Fibonacci level ({_ew_fmt(tgt)}). Invalidation {_ew_fmt(inv)}'
                ct = nt = tgt
            wc += ' All Fibonacci targets of the wave in progress already reached.'
    mtf_conflict = 'BULL' in bi and (not (trend_20 or trend_50)) or ('BEAR' in bi and (trend_20 and trend_50))
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
    return {'wave_num': wn, 'wave_phase': wp, 'wave_desc': wd, 'wave_char': wc, 'action': action, 'invalidation': inv, 'next_target': nt, 'conservative_target': ct, 'corrective_pattern': None, 'extended': extended, 'alternance': 'N/A', 'diagonal': None, 'truncated': truncated, 'bearish_div': bearish_div, 'bullish_div': bullish_div, 'bias': bi, 'confidence': conf, 'degree': degree, 'w1_start': w1s, 'w1_end': w1e, 'w1_size': w1z, 'w3_end': w3e, 'direction_up': direction_up, 'pivots': pivots, 'pivots_recent': pivots[-4:], 'risk_reward': rr_val, 'ew_violations': {}, 'mtf_conflict': mtf_conflict, 'cfd_validation': validate_elliott_with_cfd(wn, df['close'], df['volume']), 'engine': e, 'engine_degrees': res['degrees'], 'trade_dir': trade_dir, 'entry': entry}

def _ew_pfmt(sym):
    return '.3f' if 'JPY' in sym else _pf(sym)

def _ew_mature_note(eng, wn, fmt):
    """2026-10-29: nota chiara quando l'onda in corso ha già superato tutti i livelli Fibonacci.
    Dice cosa è successo, cosa NON fare e quale livello reale conferma la svolta. fmt = formattatore prezzi."""
    fibs = (eng or {}).get('fibs') or []
    pv = {x['label']: x['p'] for x in (eng or {}).get('pivots', [])}
    up = bool((eng or {}).get('wave_up'))
    if not fibs:
        return []
    f = fibs[-1]
    lvl, r = (fmt(f['v']), _ew_fr(f['r']))
    no_new = 'no new longs' if up else 'no new shorts'
    back = 'below' if up else 'above'
    if wn == '3':
        out = [f'Wave 3 is already beyond its last projection ({r}×W1 at {lvl}): extended move, too late to chase', 'better entry on the wave 4 pullback']
        if '2' in pv:
            out.append(f"the count holds while price stays {('above' if up else 'below')} {fmt(pv['2'])} (end of wave 2)")
        return out
    if wn == '5':
        out = [f'Wave 5 is already beyond its last projection ({r}×W1 at {lvl}): the impulse can end at any time', f'{no_new} here — protect profits']
        if '4' in pv:
            out.append(f"a break back {back} {fmt(pv['4'])} (end of wave 4) would confirm the {('top' if up else 'low')} is in")
        return out
    if wn == 'A':
        return [f'Wave A has already retraced {r} of the whole impulse ({lvl}): the first corrective leg is mature', 'no chasing — wait for the wave B bounce to position for wave C']
    if wn == 'C':
        out = [f'Wave C has already reached {r}×A ({lvl}): the correction can end at any time', f'{no_new} here']
        if 'B' in pv:
            out.append(f"a break back {back} {fmt(pv['B'])} (end of wave B) would confirm the correction is over")
        return out
    if wn in ('4', 'B'):
        base = 'wave 3' if wn == '4' else 'wave A'
        return [f'Wave {wn} has reached the {r} retracement of {base} ({lvl}), the usual end zone for this correction']
    return []

def _ew_fr(r):
    return '1.0' if abs(r - 1) < 1e-09 else f'{r:g}'

def _ew_target_plan(eng, setup, last, rng, pf='.2f', extreme=None):
    """2026-10-26: UNICA fonte dei target per testo e grafico, ognuno col suo criterio Fibonacci esatto.
    Ritorna {"targets": [(valore, etichetta)], "basis": str, "entry_note": str, "inv_note": str}."""
    out = {'targets': [], 'basis': '', 'entry_note': '', 'inv_note': '', 'reached': None}
    if not eng:
        return out
    st = setup or {}
    td = st.get('td', 0) or 0
    ref = last if extreme is None else max(last, extreme) if td > 0 else min(last, extreme)
    wave = st.get('wave') or eng.get('wave')
    entry = st.get('entry')
    fibs = eng.get('fibs') or []
    pv = {x['label']: x['p'] for x in eng.get('pivots', [])}
    num = lambda v: format(float(v), ',' + pf)
    tri = bool(eng.get('triangle'))
    out['inv_note'] = ({'5': 'end of wave E', 'E': 'end of wave C'} if tri else {'3': 'end of wave 2', '4': 'end of wave 1 — no overlap', '5': 'end of wave 4', 'A': 'end of wave 5', 'B': 'start of wave A', 'C': 'end of wave B'}).get(wave, '')

    def match_fib(v):
        return next((f for f in fibs if v is not None and abs(f['v'] - v) <= max(abs(v) * 1e-09, 1e-12)), None)
    t = []
    if td != 0:
        if tri and wave == '5':
            t = [(f['v'], f"{_ew_fr(f['r'])}× triangle width") for f in fibs if (f['v'] - ref) * td > 0]
            out['basis'] = f"triangle width projected from the end of wave E ({num(pv['E'])})"
        elif tri:
            ct = st.get('ct')
            if ct is not None:
                t = [(ct, '1.0× triangle width')]
            mf = match_fib(entry)
            if mf and abs(entry - last) > rng * 0.01:
                out['entry_note'] = f"{_ew_fr(mf['r'])} retracement of wave D"
            out['basis'] = 'triangle width projected from the end of wave E'
        elif wave == '3':
            t = [(f['v'], f"W3 = {_ew_fr(f['r'])}×W1") for f in fibs if (f['v'] - ref) * td > 0]
            out['basis'] = f"wave 1 projected from the end of wave 2 ({num(pv['2'])})"
        elif wave == '5':
            t = [(f['v'], f"W5 = {_ew_fr(f['r'])}×W1") for f in fibs if (f['v'] - ref) * td > 0]
            out['basis'] = f"wave 1 projected from the end of wave 4 ({num(pv['4'])})"
        elif wave == 'A':
            t = [(f['v'], f"{_ew_fr(f['r'])} retr. of 1–5") for f in fibs if (f['v'] - ref) * td > 0]
            out['basis'] = f"retracement of waves 1–5 ({num(pv['0'])} → {num(pv['5'])})"
        elif wave == 'C':
            t = [(f['v'], f"C = {_ew_fr(f['r'])}×A") for f in fibs if (f['v'] - ref) * td > 0]
            out['basis'] = f"wave A projected from the end of wave B ({num(pv['B'])})"
        elif wave == '4':
            if st.get('ct') is not None:
                t.append((st['ct'], 'end of wave 3'))
            if st.get('nt') is not None:
                t.append((st['nt'], 'W5 = 1.0×W1'))
            mf = match_fib(entry)
            out['entry_note'] = f"{_ew_fr(mf['r'])} retracement of wave 3" if mf else 'end of wave 4'
            out['basis'] = 'wave 5 after the entry zone'
        elif wave == 'B':
            if st.get('ct') is not None:
                t.append((st['ct'], 'end of wave A'))
            if st.get('nt') is not None:
                t.append((st['nt'], 'C = 1.0×A'))
            mf = match_fib(entry)
            out['entry_note'] = f"{_ew_fr(mf['r'])} retracement of wave A" if mf else 'end of wave B'
            out['basis'] = 'wave C after the entry zone'
        if wave in ('4', 'B') and len(t) > 1:
            t.sort(key=lambda x: (x[0] - ref) * td)
        if not t and st.get('ct') is not None and (wave not in ('4', 'B')) and (not tri):
            t = [(st['ct'], '')]
        if td != 0 and wave in ('3', '5', 'A', 'C') and (not (tri and wave != '5')):
            lab_of = {'3': 'W3 = {}×W1', '5': 'W5 = {}×W1', 'A': '{} retr. of 1–5', 'C': 'C = {}×A'}
            done = [f for f in fibs if (f['v'] - ref) * td <= 0 and (wave == 'A' or f['r'] >= 1)]
            if done:
                f = done[-1]
                lab = f"{_ew_fr(f['r'])}× triangle width" if tri else lab_of[wave].format(_ew_fr(f['r']))
                out['reached'] = (f['v'], lab)
    seen, clean = ([], [])
    for v, lab in t:
        if (v - ref) * td <= 0 or any((abs(v - s_) <= rng * 0.01 for s_ in seen)):
            continue
        if clean and abs(v - last) > rng * 1.0:
            continue
        seen.append(v)
        clean.append((v, lab))
    out['targets'] = clean[:3]
    return out

def _ew_wave_extreme(df, eng, td):
    """Massimo (td>0) o minimo (td<0) toccato dall'onda in corso, dall'ultimo pivot confermato a oggi."""
    try:
        i0 = eng['pivots'][-2]['i']
        seg = df.iloc[i0:]
        return float(seg['high'].max()) if td > 0 else float(seg['low'].min())
    except Exception:
        return None

def _ewp_setup_from(ds):
    """setup per _ew_pro_panel da un risultato di count_elliott_waves_engine / elliott_wave_analysis."""
    if not ds:
        return {}
    return {'td': ds.get('trade_dir', 0), 'entry': ds.get('entry'), 'ct': ds.get('conservative_target'), 'nt': ds.get('next_target'), 'inv': ds.get('invalidation'), 'wave': ds.get('wave_num')}

def _pf(sym):
    if sym.endswith('JPY'):
        return '.3f'
    if sym in ['EURUSD', 'GBPUSD', 'AUDUSD', 'USDCHF', 'USDCAD', 'NZDUSD']:
        return '.5f'
    if sym in ['XRPUSD', 'DOGEUSD', 'ADAUSD', 'XLMUSD']:
        return '.4f'
    return '.2f'
HORIZON_TXT = {'mko': 'Short-term · H1 entry, H4 trend · hours to a few days', 'elliott': 'Swing · Daily count, 4H/1H timing · days to weeks', 'ai': 'Swing · Daily count, 4H/1H timing · days to weeks', 'ews': 'Swing · 4H count · several days to 2-3 weeks'}
EWS_STOCKS = ['AAPL', 'AMZN', 'BA', 'CAT', 'CRM', 'DIS', 'GOOGL', 'GS', 'HD', 'JNJ', 'JPM', 'KO', 'MCD', 'MMM', 'MSFT', 'NVDA', 'PG', 'UNH', 'V', 'WMT']
EWS_BARS_DAYS = 60
EWS_BARS_DAYS_STOCKS = 150

def _ews_pf(sym):
    return '.3f' if sym == 'DXY' else _ew_pfmt(sym)

def _ews_num(v, pf):
    try:
        return format(float(v), ',' + pf)
    except Exception:
        return '—'

def _ews_desk_note(df4, ds, td, pf):
    """2026-10-25: nota operativa breve dagli indicatori 4H (RSI, EMA21, MACD, divergenze, ATR),
    letta nel contesto dello scenario EW. Calcolata in codice, massimo 2 frasi, niente AI."""
    try:
        c = df4['close'].astype(float)
        last = float(c.iloc[-1])
        r = float(rsi(c).iloc[-1])
        e21 = float(ema(c, 21).iloc[-1])
        av = float(atr(df4).iloc[-1]) or abs(last) * 0.005
        ml, sl_ = macd(c)
        hist = ml - sl_
        h_now, h_prev = (float(hist.iloc[-1]), float(hist.iloc[-4]))
        stretch = (last - e21) / av
        wn = ds.get('wave_num')
        late = wn in ('5', 'C') or 'TERMINAL' in str(ds.get('bias', ''))
        notes = []
        if late and (r >= 70 and td > 0 or (r <= 30 and td < 0)):
            notes.append(f"RSI {r:.0f} {('overbought' if td > 0 else 'oversold')} in a terminal wave: exhaustion risk — protect profits, no new {('longs' if td > 0 else 'shorts')}")
        elif r <= 30:
            notes.append(f'RSI {r:.0f} oversold: possible pullback toward {_ews_num(e21, pf)} (EMA21) before the next leg lower — better to sell rallies than to chase the move' if td < 0 else f'RSI {r:.0f} oversold into the pullback: supports buying near the end of the correction, not before')
        elif r >= 70:
            notes.append(f'RSI {r:.0f} overbought: possible pullback toward {_ews_num(e21, pf)} (EMA21) before continuation — better to buy dips than to chase the move' if td > 0 else f'RSI {r:.0f} overbought into the bounce: supports selling near the end of the correction, not before')
        if td < 0 and ds.get('bullish_div'):
            notes.append('bullish RSI divergence: downside momentum is fading — tighten risk')
        elif td > 0 and ds.get('bearish_div'):
            notes.append('bearish RSI divergence: upside momentum is fading — tighten risk')
        if len(notes) < 2 and 30 < r < 70 and (abs(stretch) >= 2.0) and (stretch * td > 0):
            notes.append(f'price is {abs(stretch):.1f} ATR away from EMA21: stretched, entries on a retracement are safer')
        if len(notes) < 2 and td != 0:
            rising = h_now > h_prev
            if (td > 0) == rising:
                notes.append('MACD momentum is building in the direction of the scenario')
            elif late:
                notes.append('MACD momentum is fading — typical of a maturing terminal wave')
            elif wn in ('4', 'B', 'E'):
                notes.append(f"MACD is moving with the {('pullback' if td > 0 else 'bounce')}, as expected in wave {wn}: a MACD turn back {('up' if td > 0 else 'down')} in the entry zone is the timing signal")
            else:
                notes.append('MACD momentum is fading against the scenario — wait for confirmation')
        if not notes:
            return ''
        txt = '; '.join(notes[:2])
        return txt[0].upper() + txt[1:] + '.'
    except Exception as e:
        logger.warning(f'EWS desk note: {e}')
        return ''

def _ews_trade_plan(ds, eng, plan, df4, last, td, pf, wn, waiting, k0):
    """2026-10-26: piano operativo dalla posizione tecnica. Tutti i livelli vengono dal conteggio
    e dai dati reali (pivot, Fibonacci, EMA21, trendline 2-4): niente frasi generiche."""
    if td == 0 or not eng:
        return []
    num = lambda v: _ews_num(v, pf)
    pv = {x['label']: x for x in eng.get('pivots', [])}
    inv = ds.get('invalidation')
    side = 'long' if td > 0 else 'short'
    buy_sell = 'buy' if td > 0 else 'sell'
    beyond = 'below' if td > 0 else 'above'
    n = len(df4)
    out = []
    try:
        e21 = float(ema(df4['close'].astype(float), 21).iloc[-1])
    except Exception:
        e21 = None

    def line_at(a, b):
        """valore oggi della retta per due pivot (a, b)."""
        if a not in pv or b not in pv or pv[b]['i'] == pv[a]['i']:
            return None
        sl = (pv[b]['p'] - pv[a]['p']) / (pv[b]['i'] - pv[a]['i'])
        return pv[b]['p'] + sl * (n - 1 - pv[b]['i'])
    tg = plan.get('targets') or []
    if eng.get('triangle'):
        if wn == 'E' and 'likely complete' not in ds.get('wave_desc', ''):
            out.append(f"Wait for wave E to end near {num(ds.get('entry'))}: {side} only on a break of {num(eng.get('d_level'))} (end of wave D), stop {beyond} {num(inv)}")
        elif wn == 'E':
            out.append(f"Breakout trigger: {num(eng.get('d_level'))} (end of wave D) — {side} on the break, stop {beyond} {num(inv)}")
        else:
            out.append(f"Thrust out of the triangle: trail the stop {beyond} the end of wave E ({num(pv['E']['p'])}); thrusts are fast and often end the larger move")
        return out
    if waiting:
        entry = ds.get('entry')
        brk = pv.get('3' if wn == '4' else 'A', {}).get('p')
        rr = ''
        if entry is not None and inv is not None and tg and (abs(inv - entry) > 0):
            rr = f', R:R ≈ 1:{abs(tg[-1][0] - entry) / abs(inv - entry):.1f} to T{k0 + len(tg) - 1}'
        word = 'Pullback' if td > 0 else 'Bounce'
        if entry is not None and (entry - last) * td < 0:
            out.append(f"{word} still under way toward {num(entry)} ({plan.get('entry_note') or 'entry zone'}): {buy_sell} there on a {('bullish' if td > 0 else 'bearish')} reversal candle, stop {beyond} {num(inv)}{rr}")
        else:
            out.append(f"Price is in the entry zone: {side} only after a {('bullish' if td > 0 else 'bearish')} reversal candle, stop {beyond} {num(inv)}{rr}")
        if brk is not None:
            out.append(f"A break of {num(brk)} (end of wave {('3' if wn == '4' else 'A')}) confirms wave {('5' if wn == '4' else 'C')} is under way — no chasing the breakout, wait for the retest")
        return out
    if plan.get('reached') and wn in ('5', 'C'):
        rv, rlab = plan['reached']
        out.append(f'T1 reached ({rlab}): the wave can complete at any time — no new {side}s, protect profits' + (f'; T{k0} only on an extension' if tg else ''))
    elif plan.get('reached'):
        out.append('T1 reached: move the stop to break-even and trail it' + (f', next T{k0}' if tg else ''))
    elif tg:
        try:
            _atr = float(atr(df4).iloc[-1])
            _gap = abs(tg[0][0] - last)
            if _atr > 0 and _gap <= 0.5 * _atr:
                out.append(f'T{k0} is only {num(_gap)} away ({_gap / _atr:.1f} ATR): little room left, no new entries at market')
        except Exception:
            pass
    if wn == '3':
        ext = _ew_wave_extreme(df4, eng, td)
        p1 = pv['1']['p']
        past1 = ext is not None and (ext - p1) * td > 0
        if past1 and (last - p1) * td < 0:
            return [f"Price is back {('below' if td > 0 else 'above')} the end of wave 1 ({num(p1)}): the impulse count is in doubt — stand aside until it recovers {num(p1)}; the count fails at {num(inv)}"]
        if e21 is not None and (not out):
            if (e21 - last) * td < 0 and (inv is None or (e21 - inv) * td > 0):
                out.append(f"Trend leg: {buy_sell} pullbacks toward the EMA21 ({num(e21)}), stop {beyond} the end of wave 2 ({num(pv['2']['p'])})")
            else:
                out.append(f"Price is at the EMA21 ({num(e21)}): {side} only on a {('bullish' if td > 0 else 'bearish')} reversal candle, stop {beyond} {num(inv)}")
        if not past1:
            out.append(f'Wave 3 is confirmed only on a break of {num(p1)} (end of wave 1) — that is the breakout trigger')
        else:
            out.append(f"When wave 3 ends, wave 4 must hold {('above' if td > 0 else 'below')} {num(p1)} (end of wave 1, no overlap)")
    elif wn == '5':
        tl = line_at('2', '4')
        if tl is not None and (last - tl) * td > 0:
            out.append(f'A break of the 2–4 trendline ({num(tl)}) would signal wave 5 complete and a correction of the whole move — exit {side}s there')
    elif wn == 'A':
        out.append(f"First leg of the correction: after T1 expect a wave B {('bounce' if td < 0 else 'pullback')} — better to {buy_sell} the B {('rally' if td < 0 else 'dip')} than to chase wave A")
    elif wn == 'C':
        tl = line_at('5', 'B')
        if tl is not None and (last - tl) * td > 0:
            out.append(f'A break back through {num(tl)} (5–B trendline) would signal wave C complete — exit {side}s there')
    return out
EWS_SYMBOLS = ['DXY', 'EURUSD', 'GBPUSD', 'AUDUSD', 'USDCAD', 'USDCHF', 'USDJPY', 'EURGBP', 'EURAUD', 'EURJPY', 'GBPJPY', 'GBPAUD', 'GOLD', 'SILVER', 'OIL', 'NGAS', 'DAX', 'DJI', 'NASDAQ', 'SPX', 'BTCUSD']
EWS_SYMBOLS = EWS_SYMBOLS + EWS_STOCKS
