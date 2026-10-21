"""
eia_fundamentals.py — Fundamental score module per l'oil (WTI/Brent)
Si aggancia a market-intelligence-agent, chiamato da MarketAnalyzer.
"""

import os
import time
import requests
from datetime import datetime

EIA_API_KEY = os.environ.get("EIA_API_KEY")
EIA_BASE_URL = "https://api.eia.gov/v2"

# Serie EIA per scorte settimanali di greggio USA (esclusa riserva strategica)
CRUDE_STOCKS_SERIES = "PET.WCESTUS1.W"


def get_weekly_crude_stocks(weeks: int = 12) -> list[dict]:
    """
    Recupera le ultime N settimane di scorte di greggio USA.
    Restituisce lista ordinata dal più recente al più vecchio.
    """
    url = f"{EIA_BASE_URL}/petroleum/stoc/wstk/data/"
    params = {
        "api_key": EIA_API_KEY,
        "frequency": "weekly",
        "data[0]": "value",
        "facets[series][]": "WCESTUS1",
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": weeks,
    }
    # Un retry singolo con timeout più ampio: se il problema è un timeout/errore
    # di rete intermittente lato Railway (non riproducibile testando la stessa
    # chiave da un'altra rete), questo lo assorbe senza mascherare un errore reale
    # (es. api_key invalida, serie non trovata) che invece va a buon fine sempre
    # o fallisce sempre — in quel caso il retry fallirà di nuovo e l'eccezione
    # risalirà comunque, ora con traceback completo nei log (vedi divergence_scorer.py).
    last_exc = None
    for attempt in range(2):
        try:
            resp = requests.get(url, params=params, timeout=25)
            resp.raise_for_status()
            data = resp.json()["response"]["data"]
            return [{"date": d["period"], "value": float(d["value"])} for d in data]
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_exc = e
            if attempt == 0:
                time.sleep(3)
    raise last_exc


def compute_stock_surprise(weeks: int = 12) -> dict:
    """
    Confronta la variazione settimanale più recente contro la media
    delle variazioni delle N settimane precedenti (proxy di "stagionalità/consenso"
    senza dover integrare un'altra fonte per il consenso analisti).
    """
    stocks = get_weekly_crude_stocks(weeks=weeks + 1)
    if len(stocks) < weeks + 1:
        raise ValueError("Dati EIA insufficienti per calcolare la sorpresa")

    changes = []
    for i in range(len(stocks) - 1):
        change = stocks[i]["value"] - stocks[i + 1]["value"]
        changes.append(change)

    latest_change = changes[0]
    historical_avg = sum(changes[1:]) / len(changes[1:])
    historical_std = (
        sum((c - historical_avg) ** 2 for c in changes[1:]) / len(changes[1:])
    ) ** 0.5

    # z-score della variazione più recente rispetto allo storico
    z_score = (latest_change - historical_avg) / historical_std if historical_std > 0 else 0

    return {
        "latest_change_kbbl": round(latest_change, 1),
        "historical_avg_change_kbbl": round(historical_avg, 1),
        "z_score": round(z_score, 2),
        "as_of": stocks[0]["date"],
    }


def stock_surprise_to_score(z_score: float) -> float:
    """
    Converte lo z-score delle scorte in uno score -5/+5.
    Scorte che salgono più del previsto = bearish (score negativo).
    Scorte che scendono più del previsto = bullish (score positivo).
    Clippato a ±5, scalato in modo che z=2 (sorpresa forte) ≈ score massimo.
    """
    score = -z_score * 2.5
    return max(-5.0, min(5.0, round(score, 1)))


def get_curve_structure_score(front_month_price: float, back_month_price: float) -> float:
    """
    Backwardation (front > back) = bullish, contango (front < back) = bearish.
    front_month_price e back_month_price vanno passati da qualunque fonte prezzi
    tu già usi nel dashboard (Yahoo Finance, come da resto della piattaforma).
    """
    spread_pct = (front_month_price - back_month_price) / back_month_price * 100
    score = spread_pct * 3  # scala empirica: ±1.5% di spread ≈ score ±4.5
    return max(-5.0, min(5.0, round(score, 1)))


def compute_fundamental_score(front_month_price: float, back_month_price: float) -> dict:
    """
    Score fondamentale complessivo per l'oil: 60% scorte, 40% struttura curva.
    Output pronto da salvare insieme al narrative_score.
    """
    stock_data = compute_stock_surprise()
    stock_score = stock_surprise_to_score(stock_data["z_score"])
    curve_score = get_curve_structure_score(front_month_price, back_month_price)

    fundamental_score = round(stock_score * 0.6 + curve_score * 0.4, 1)

    return {
        "fundamental_score": fundamental_score,
        "stock_score": stock_score,
        "curve_score": curve_score,
        "stock_detail": stock_data,
        "computed_at": datetime.utcnow().isoformat(),
    }
