import os, json, re, time, logging, requests
logging.basicConfig(level=logging.INFO); logger = logging.getLogger("t")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
ALLOW_PAID_AI = os.getenv("ALLOW_PAID_AI", "") == "1"
_GEM_MODELS = None
_GEM_DEAD = set()


class _AIResp:
    def __init__(self, payload, status=200):
        self._p, self.status_code = payload, status
        self.ok = status == 200
        self.text = json.dumps(payload)

    def json(self):
        return self._p

    def raise_for_status(self):
        if not self.ok:
            raise requests.HTTPError(f"AI unavailable ({self.status_code})")


def _gem_models():
    global _GEM_MODELS
    if _GEM_MODELS is not None:
        return _GEM_MODELS
    forced = os.getenv("GEMINI_MODEL", "").strip()
    if forced:
        _GEM_MODELS = [forced]
        return _GEM_MODELS
    try:
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                         params={"pageSize": 200, "key": GEMINI_API_KEY}, timeout=20)
        names = [m["name"].split("/", 1)[-1] for m in r.json().get("models", [])
                 if "generateContent" in (m.get("supportedGenerationMethods") or [])]
        bad = ("image", "tts", "audio", "live", "embedding", "thinking", "exp", "robotics", "computer", "native")
        fl = [n for n in names if "flash" in n and not any(x in n for x in bad)]
        ver = lambda n: float((re.search(r"gemini-(\d+(?:\.\d+)?)", n) or [0, 0])[1] or 0)
        rank = lambda n: (ver(n), "preview" not in n, "latest" not in n)
        lite = sorted([n for n in fl if "lite" in n], key=rank, reverse=True)
        full = sorted([n for n in fl if "lite" not in n], key=rank, reverse=True)
        _GEM_MODELS = (lite[:1] + full[:2]) or ["gemini-flash-lite-latest", "gemini-flash-latest"]
    except Exception as e:
        logger.warning(f"gemini models: {e}")
        _GEM_MODELS = ["gemini-flash-lite-latest", "gemini-flash-latest"]
    logger.info(f"🆓 AI gratuita: Gemini {_GEM_MODELS}")
    return _GEM_MODELS


def _anthropic_to_gemini(body):
    contents = []
    for m in body.get("messages", []):
        c = m.get("content")
        parts = []
        if isinstance(c, str):
            parts.append({"text": c})
        else:
            for b in c or []:
                if b.get("type") == "text":
                    parts.append({"text": b.get("text", "")})
                elif b.get("type") == "image" and (b.get("source") or {}).get("type") == "base64":
                    parts.append({"inline_data": {"mime_type": b["source"].get("media_type", "image/png"),
                                                  "data": b["source"].get("data", "")}})
        contents.append({"role": "model" if m.get("role") == "assistant" else "user", "parts": parts or [{"text": ""}]})
    out = {"contents": contents, "generationConfig": {"temperature": float(body.get("temperature", 0.5))}}
    sysp = body.get("system")
    if isinstance(sysp, list):
        sysp = "\n".join(x.get("text", "") for x in sysp if isinstance(x, dict))
    if sysp:
        out["systemInstruction"] = {"parts": [{"text": sysp}]}
    return out


def _gemini_messages(body, timeout):
    gb = _anthropic_to_gemini(body)
    for model in [m for m in _gem_models() if m not in _GEM_DEAD]:
        for attempt in range(2):
            try:
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                  params={"key": GEMINI_API_KEY}, json=gb, timeout=max(30, min(timeout or 60, 90)))
                if r.status_code == 200:
                    cand = (r.json().get("candidates") or [{}])[0]
                    txt = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", [])
                                  if not p.get("thought")).strip()
                    if txt:
                        return txt
                    break
                msg = r.text[:300]
                if r.status_code == 429 and ("quota" in msg.lower() or "PerDay" in msg):
                    _GEM_DEAD.add(model)
                    logger.warning(f"gemini {model}: quota giornaliera finita → modello successivo")
                    break
                if r.status_code in (429, 500, 503) and attempt == 0:
                    time.sleep(4 if r.status_code != 429 else 15)
                    continue
                logger.warning(f"gemini {model}: HTTP {r.status_code} {msg[:120]}")
                break
            except Exception as e:
                logger.warning(f"gemini {model}: {type(e).__name__}: {str(e)[:120]}")
                break
    return None


def _llm_post(url, headers=None, json=None, timeout=60, **kw):
    """Sostituisce requests.post verso api.anthropic.com/v1/messages (vedi sopra)."""
    body = json or {}
    if GEMINI_API_KEY:
        txt = _gemini_messages(body, timeout)
        if txt is not None:
            return _AIResp({"id": "gemini", "type": "message", "role": "assistant", "model": "gemini",
                            "content": [{"type": "text", "text": txt}], "stop_reason": "end_turn"})
        if not ALLOW_PAID_AI:
            logger.warning("AI gratuita non disponibile ora (quota/carico Gemini): Claude a pagamento spento")
            return _AIResp({"type": "error", "error": {"type": "free_ai_unavailable",
                                                     "message": "free AI unavailable"}}, status=503)
    return requests.post(url, headers=headers, json=json, timeout=timeout, **kw)

out=[]
t=time.time()
r=_llm_post("https://api.anthropic.com/v1/messages", headers={}, json={"model":"claude-sonnet-4-5","max_tokens":300,"system":"You are a concise market analyst.","messages":[{"role":"user","content":"In 2 sentences: what does price up + open interest down mean in futures?"}]}, timeout=40)
out.append(f"status {r.status_code} {time.time()-t:.1f}s: {r.json()}")
t=time.time()
r=_llm_post("https://api.anthropic.com/v1/messages", headers={}, json={"model":"claude-haiku-4-5","max_tokens":100,"messages":[{"role":"user","content":[{"type":"text","text":"Reply only: OK"}]}]}, timeout=20)
out.append(f"status {r.status_code} {time.time()-t:.1f}s: {r.json()['content'][0]['text']!r}")
os.makedirs("seo_out",exist_ok=True); open("seo_out/bot_llm.txt","w").write("\n".join(out)); print("\n".join(out))
