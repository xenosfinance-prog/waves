"""
free_llm.py — testi AI a costo zero (2026-10-26)

Tutte le pipeline del sito (Daily Analysis, COT, Futures Flow) e il server Elliott
Wave usano questo modulo invece di chiamare Claude a pagamento:

  1. Gemini, piano gratuito (GEMINI_API_KEY). Si sceglie il Flash più recente
     disponibile per la chiave, con il Flash-Lite come riserva.
  2. Claude a pagamento SOLO se la variabile ALLOW_PAID_AI=1 (spenta di serie).
  3. Altrimenti None: chi chiama pubblica la versione scritta dal codice
     (ogni pipeline ne ha già una), quindi nessuna pagina resta vuota.

Solo libreria standard (urllib): nessuna dipendenza nuova.
"""

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

_MODELS = None
_DEAD = set()       # modelli con quota esaurita in questo processo: non si riprovano
LAST_ERRORS = []   # diagnostica: ultimi errori (modello, codice, messaggio)
_BAD = ("image", "tts", "audio", "live", "embedding", "thinking", "exp", "robotics", "computer", "native")


def _gkey():
    return os.environ.get("GEMINI_API_KEY", "").strip()


def available():
    return bool(_gkey()) or (os.environ.get("ALLOW_PAID_AI") == "1" and bool(os.environ.get("ANTHROPIC_API_KEY")))


def _ver(name):
    m = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
    return float(m.group(1)) if m else 0.0


def models():
    """Flash più recenti disponibili per la chiave (stabili prima delle preview) + un Flash-Lite."""
    global _MODELS
    if _MODELS is not None:
        return _MODELS
    forced = os.environ.get("GEMINI_MODEL", "").strip()
    if forced:
        _MODELS = [forced]
        return _MODELS
    try:
        url = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200&key=" + urllib.parse.quote(_gkey())
        with urllib.request.urlopen(urllib.request.Request(url), timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
        names = [m["name"].split("/", 1)[-1] for m in data.get("models", [])
                 if "generateContent" in (m.get("supportedGenerationMethods") or [])]
        flash = [n for n in names if "flash" in n and not any(x in n for x in _BAD)]
        rank = lambda n: (_ver(n), "preview" not in n, "latest" not in n)
        full = sorted([n for n in flash if "lite" not in n], key=rank, reverse=True)
        lite = sorted([n for n in flash if "lite" in n], key=rank, reverse=True)
        # Flash-Lite per primo: quota gratuita separata da quella usata dalle traduzioni (Flash),
        # più richieste al giorno e meno spesso sovraccarico; il Flash resta come riserva
        _MODELS = (lite[:1] + full[:2]) or ["gemini-flash-lite-latest", "gemini-flash-latest"]
    except Exception:
        _MODELS = ["gemini-flash-lite-latest", "gemini-flash-latest"]
    return _MODELS


def _gemini_call(model, contents, system, max_tokens, json_mode, timeout, thinking_off=False):
    cfg = {"temperature": 0.4}
    if json_mode:
        cfg["responseMimeType"] = "application/json"
    if thinking_off:
        cfg["thinkingConfig"] = {"thinkingBudget": 0}
    body = {"contents": contents, "generationConfig": cfg}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key="
           + urllib.parse.quote(_gkey()))
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    parts = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    txt = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    return txt or None


def gemini(contents, system=None, max_tokens=1200, json_mode=False, timeout=60):
    """contents in formato Gemini. Ritorna il testo o None."""
    if not _gkey():
        return None
    for model in [m for m in models() if m not in _DEAD]:
        thinking_off = False
        for attempt in range(2):
            try:
                txt = _gemini_call(model, contents, system, max_tokens, json_mode, timeout, thinking_off)
                if txt:
                    return txt
                break
            except urllib.error.HTTPError as e:
                msg = ""
                try:
                    msg = e.read().decode("utf-8", "ignore")[:300]
                except Exception:
                    pass
                LAST_ERRORS.append((model, e.code, msg[:200]))
                if e.code == 429:
                    if "PerDay" in msg or "per day" in msg.lower() or "quota" in msg.lower():
                        _DEAD.add(model)              # quota del giorno finita: modello successivo, per sempre
                        break
                    if attempt < 1:
                        time.sleep(15)                # limite al minuto
                        continue
                if e.code in (500, 503) and attempt < 1:
                    time.sleep(4)
                    continue
                break                              # 404 / quota del giorno finita → modello successivo
            except Exception as e:
                LAST_ERRORS.append((model, type(e).__name__, str(e)[:200]))
                break                             # timeout: modello successivo
    return None


def _claude_paid(prompt, system, max_tokens, model="claude-haiku-4-5"):
    if os.environ.get("ALLOW_PAID_AI") != "1" or not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        body = {"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]}
        if system:
            body["system"] = system
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json",
                                              "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                                              "anthropic-version": "2023-06-01"})
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read().decode("utf-8"))
        return "".join(b.get("text", "") for b in data.get("content", [])).strip() or None
    except Exception:
        return None


def generate(prompt, max_tokens=1200, json_mode=False, system=None):
    """Testo AI gratuito (Gemini); Claude a pagamento solo con ALLOW_PAID_AI=1; altrimenti None."""
    txt = gemini([{"role": "user", "parts": [{"text": prompt}]}], system=system,
                 max_tokens=max_tokens, json_mode=json_mode)
    if txt:
        return txt
    return _claude_paid(prompt, system, max_tokens)
