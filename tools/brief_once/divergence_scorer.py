"""
divergence_scorer.py — Combina narrative_score (Gemini) e fundamental_score (EIA)
in un badge di divergenza. Chiamato da MarketAnalyzer per l'oil.
"""

import json
import time
import logging
from datetime import datetime

from settings import GEMINI_MODEL
from eia_fundamentals import compute_fundamental_score

logger = logging.getLogger(__name__)

DIVERGENCE_THRESHOLDS = {
    "aligned": 2.0,
    "medium": 4.0,
    # oltre 4.0 = "high"
}

NARRATIVE_RETRIES = 3
NARRATIVE_RETRY_DELAY = 5  # seconds, exponential (5s, 10s, 20s) — stesso spirito
                            # del retry di gemini_writer.py per il brief principale


def get_narrative_score(article_text: str, asset: str, gemini_client) -> dict | None:
    """
    Chiede a Gemini uno score strutturato separato dal testo narrativo del brief.
    Usa la stessa interfaccia client.models.generate_content() di GeminiWriter.
    Restituisce None se la chiamata fallisce (dopo i retry) o il JSON non è
    parsabile, invece di far crashare il pipeline.
    """
    prompt = f"""Analizza il sentiment di mercato per {asset} nel seguente testo.
Rispondi SOLO con JSON, nessun altro testo:
{{"score": <intero da -5 a 5, -5 molto bearish, +5 molto bullish>, "confidence": <0-1>}}

Testo: {article_text}"""

    delay = NARRATIVE_RETRY_DELAY
    last_error = None
    for attempt in range(1, NARRATIVE_RETRIES + 1):
        try:
            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )

            # Stessa estrazione sicura del testo usata in gemini_writer.py
            text = ""
            if hasattr(response, "text") and response.text:
                text = response.text.strip()
            elif hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "content") and candidate.content:
                    parts = candidate.content.parts or []
                    text = " ".join(p.text for p in parts if hasattr(p, "text")).strip()

            if not text:
                raise ValueError("Risposta vuota da Gemini")

            text = text.replace("```json", "").replace("```", "").strip()
            return json.loads(text)
        except Exception as e:
            last_error = e
            if attempt < NARRATIVE_RETRIES:
                time.sleep(delay)
                delay *= 2
    logger.warning(f"narrative_score fallito per {asset} dopo {NARRATIVE_RETRIES} tentativi: {last_error}")
    return None


def classify_divergence(diff: float) -> str:
    abs_diff = abs(diff)
    if abs_diff < DIVERGENCE_THRESHOLDS["aligned"]:
        return "aligned"
    elif abs_diff < DIVERGENCE_THRESHOLDS["medium"]:
        return "medium"
    return "high"


def compute_divergence_badge(
    article_text: str,
    asset: str,
    gemini_client,
    front_month_price: float | None = None,
    back_month_price: float | None = None,
) -> dict:
    """
    Output finale da salvare nel JSON che trading-ideas.html legge per il badge.
    Se un pezzo manca (narrative o fundamental), il badge risulta "unavailable"
    invece di mostrare dati parziali/fuorvianti — ma i due punteggi vengono
    SEMPRE tentati entrambi, indipendentemente l'uno dall'altro: un fallimento
    di Gemini (narrative) non deve più impedire il tentativo EIA (fundamental),
    e viceversa. Prima, se narrative falliva, la funzione usciva subito senza
    nemmeno provare l'EIA — motivo per cui negli ultimi giorni fundamental_score
    risultava null anche in run dove l'EIA probabilmente avrebbe funzionato.
    """
    result = {
        "asset": asset,
        "narrative_score": None,
        "fundamental_score": None,
        "divergence": None,
        "badge": "unavailable",
        "computed_at": datetime.utcnow().isoformat(),
    }

    narrative = get_narrative_score(article_text, asset, gemini_client)
    if narrative is not None:
        result["narrative_score"] = narrative.get("score")

    try:
        if front_month_price is not None and back_month_price is not None:
            fundamental = compute_fundamental_score(front_month_price, back_month_price)
        else:
            # fallback: solo score scorte, niente curva, se non hai ancora i prezzi futures
            from eia_fundamentals import compute_stock_surprise, stock_surprise_to_score
            stock_data = compute_stock_surprise()
            fundamental = {"fundamental_score": stock_surprise_to_score(stock_data["z_score"])}
        result["fundamental_score"] = fundamental["fundamental_score"]
    except Exception:
        # logger.exception include il traceback completo nei log Railway
        # (prima si vedeva solo str(e), spesso troppo generico per capire
        # se è timeout, connessione rifiutata dalla rete Railway, o altro)
        logger.exception(f"fundamental_score fallito per {asset}")

    # Divergenza/badge richiedono davvero entrambi i punteggi — questo non cambia,
    # ma ora ogni singolo score arriva nel JSON pubblicato anche se l'altro manca,
    # invece di sparire entrambi insieme per colpa di un solo provider giù.
    if result["narrative_score"] is not None and result["fundamental_score"] is not None:
        diff = result["narrative_score"] - result["fundamental_score"]
        result["divergence"] = round(diff, 1)
        result["badge"] = classify_divergence(diff)

    return result
