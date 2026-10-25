#!/usr/bin/env python3
"""
XenosFinance — traduzione italiana pre-generata dei contenuti salvati (2026-10-25).

Cosa fa
  Per ogni articolo del blog (articles/*.json) e ogni lezione di Daily Education
  (daily_education/*.json) crea la versione italiana in:
      i18n/it/articles/<slug>.json          (stessa struttura dell'originale)
      i18n/it/articles/index.json           (titoli/estratti per la griglia)
      i18n/it/daily_education/<data>.json
  Il sito, con la lingua IT attiva, legge questi file: niente traduzione al
  volo, niente attese, qualità costante.

Costo: zero.
  1) GEMINI_API_KEY presente (secret del repo) → Gemini, piano gratuito.
  2) Altrimenti, o se Gemini fallisce → Google Translate pubblico (gratuito).

Fedeltà
  - Ogni numero del testo inglese (prezzi, livelli, percentuali, date) deve
    ricomparire identico nel testo italiano, altrimenti quel campo viene
    rifatto con l'altro traduttore; se fallisce anche quello resta in inglese.
  - I tag HTML (<br>, <b>…) devono restare tutti.
  - Un file viene ritradotto solo se l'originale inglese cambia (_src_hash).

Uso:  python tools/translate_content.py [--max 40] [--only articles|education]
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "i18n", "it")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODELS = [m for m in [os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"), "gemini-2.5-flash-lite"] if m]
GEMINI_PAUSE = float(os.environ.get("GEMINI_PAUSE", "7"))   # piano free: ~10 richieste/minuto
UA = "Mozilla/5.0 (XenosFinance translator)"

ARTICLE_TEXT_KEYS = ["title", "excerpt", "intro", "conclusion", "quote", "categoryLabel", "category"]
IT_LANG_VALUES = {"it", "italiano", "italian"}

GLOSSARY = (
    "Keep these trading terms in English exactly as written: stop loss, take profit, bias, setup, "
    "trade setup, smart money, risk-on, risk-off, breakout, pullback, swing, trend, range, spread, "
    "call, put, straddle, iron condor, VWAP, COT, CFD, ETF, futures, Pre-Market, PRO TIP, SMART MONEY RULE, "
    "TIP 1/2/3 labels. Elliott Wave → 'Onde di Elliott' (wave = onda, impulse = impulso, "
    "corrective = correttiva). Crude oil = petrolio greggio, inventories = scorte, draw = calo delle scorte, "
    "build = aumento delle scorte, yield = rendimento, rate cut = taglio dei tassi."
)

# ── utilità ────────────────────────────────────────────────────────────────

def log(*a):
    msg = " ".join(str(x) for x in a)
    print(msg, flush=True)
    # 2026-10-25: errori e riepilogo anche come annotazioni di GitHub Actions (visibili dall'API)
    if os.environ.get("GITHUB_ACTIONS") and re.search(r"✗|gemini|gtx|Troppi|Tradotti in questo run|Traduttore:", msg):
        kind = "notice" if ("Tradotti in questo run" in msg or "Traduttore:" in msg) else "warning"
        print(f"::{kind}::" + msg.replace("\n", " ")[:900], flush=True)


def src_hash(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


NUM_RE = re.compile(r"\d+(?:[.,:]\d+)*")
TAG_RE = re.compile(r"<[^>]+>")


def numbers(s):
    return {re.sub(r"[.,:]", "", n) for n in NUM_RE.findall(s or "")}


def faithful(src, dst):
    """Il testo tradotto conserva tutti i numeri e tutti i tag HTML?"""
    if not dst or not dst.strip():
        return False
    if not numbers(src) <= numbers(dst):
        return False
    if sorted(t.lower() for t in TAG_RE.findall(src)) != sorted(t.lower() for t in TAG_RE.findall(dst)):
        return False
    return True


def needs_translation(s):
    return isinstance(s, str) and bool(re.search(r"[A-Za-z]{2,}", s))


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


# ── traduttori ─────────────────────────────────────────────────────────────

class GeminiQuotaExhausted(Exception):
    pass


_gemini_model_idx = 0
_gemini_disabled = not GEMINI_KEY


def gemini_translate(fields):
    """fields: {id: testo_en} → {id: testo_it}. Una sola richiesta per documento."""
    global _gemini_model_idx, _gemini_disabled
    if _gemini_disabled:
        return {}
    prompt = (
        "You are a senior financial translator for a professional trading website. "
        "Translate every value of the JSON object below from English to Italian.\n"
        "Rules:\n"
        "- Faithful, natural professional Italian as written by an Italian trader/analyst. Do not add, "
        "remove, summarise or comment anything.\n"
        "- Keep EVERY number exactly as written in the source, including decimal points "
        "(write 3.1 not 3,1; 1.0850 not 1,0850), prices, levels, percentages, dates' digits.\n"
        "- Keep tickers and symbols unchanged (WTI, EUR/USD, NAS100, S&P 500, BTC, EIA, API, OPEC+, Fed, ECB, CPI, NFP).\n"
        "- Keep all HTML tags (<br>, <b>…) and all line breaks, emojis, bullet markers ('- ', '•'), "
        "separator lines (━━━) and *asterisk* emphasis exactly in place.\n"
        f"- {GLOSSARY}\n"
        "Return ONLY a JSON object with exactly the same keys.\n\n"
        + json.dumps(fields, ensure_ascii=False)
    )
    body = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json",
                             "thinkingConfig": {"thinkingBudget": 0}},
    }).encode("utf-8")
    while _gemini_model_idx < len(GEMINI_MODELS):
        model = GEMINI_MODELS[_gemini_model_idx]
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key="
               + urllib.parse.quote(GEMINI_KEY))
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=180) as r:
                    data = json.loads(r.read().decode("utf-8"))
                time.sleep(GEMINI_PAUSE)
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                out = json.loads(text)
                return {k: v for k, v in out.items() if k in fields and isinstance(v, str)}
            except urllib.error.HTTPError as e:
                msg = e.read().decode("utf-8", "ignore")[:300]
                if e.code == 429:
                    if "PerDay" in msg or "per day" in msg.lower() or attempt == 2:
                        log(f"  gemini {model}: quota esaurita → modello successivo")
                        break
                    time.sleep(30)
                    continue
                if e.code in (500, 502, 503, 504):
                    time.sleep(10 * (attempt + 1))
                    continue
                log(f"  gemini {model}: HTTP {e.code} {msg}")
                if e.code in (400, 401, 403):
                    _gemini_disabled = True
                    return {}
                return {}
            except Exception as e:  # risposta non JSON, timeout, ecc.
                log(f"  gemini {model}: {type(e).__name__}: {str(e)[:150]}")
                time.sleep(5)
        _gemini_model_idx += 1
    _gemini_disabled = True
    log("  gemini: nessun modello disponibile in questo run → Google Translate")
    return {}


def _gtx_call(text):
    url = ("https://translate.googleapis.com/translate_a/single?client=gtx&dt=t&sl=en&tl=it&q="
           + urllib.parse.quote(text))
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
            time.sleep(0.8)
            return "".join(p[0] for p in (data[0] or []) if p and p[0])
        except Exception as e:
            time.sleep(3 * (attempt + 1))
            last = e
    raise RuntimeError(f"gtx: {last}")


def _gtx_chunks(text, limit=1800):
    out, cur = [], None
    for line in text.split("\n"):
        if cur is None:
            cur = line
        elif len(cur) + 1 + len(line) > limit:
            out.append(cur)
            cur = line
        else:
            cur = cur + "\n" + line
    out.append(cur or "")
    return out


def gtx_translate(text):
    """Google Translate gratuito. Protegge tag HTML e a capo: traduce solo i pezzi di testo."""
    parts = re.split(r"(<[^>]+>|\n)", text)
    idx = [i for i, p in enumerate(parts) if p and p not in ("\n",) and not TAG_RE.fullmatch(p) and needs_translation(p)]
    if not idx:
        return text
    pieces = [parts[i].strip() for i in idx]
    joined = "\n".join(pieces)
    translated = []
    for ch in _gtx_chunks(joined):
        translated.append(_gtx_call(ch) if ch.strip() else ch)
    lines = "\n".join(translated).split("\n")
    if len(lines) != len(pieces):                    # allineamento perso → pezzo per pezzo
        lines = [_gtx_call(p) for p in pieces]
    for i, t in zip(idx, lines):
        lead = parts[i][: len(parts[i]) - len(parts[i].lstrip())]
        trail = parts[i][len(parts[i].rstrip()):]
        parts[i] = lead + t.strip() + trail
    return fix_terms("".join(parts))


FIX_IT = [
    (r"\bpregiudizi?o? (rialzista|ribassista|neutrale|neutro)", r"bias \1"),
    (r"\bpregiudizio\b", "bias"),
    (r"\bdenaro intelligente\b", "smart money"),
    (r"\bsoldi intelligenti\b", "smart money"),
    (r"\bonde di Elliot\b", "onde di Elliott"),
    (r"\bOnde di Elliot\b", "Onde di Elliott"),
]


def fix_terms(s):
    for a, b in FIX_IT:
        s = re.sub(a, b, s, flags=re.I)
    return s


def translate_fields(fields):
    """Traduce un dizionario {id: testo}. Ritorna (risultato, traduttore usato)."""
    todo = {k: v for k, v in fields.items() if needs_translation(v)}
    result = {k: v for k, v in fields.items()}
    used = set()
    if todo:
        g = gemini_translate(todo)
        for k, v in g.items():
            if faithful(todo[k], v):
                result[k] = v
                used.add("gemini")
        missing = [k for k in todo if not (k in g and faithful(todo[k], g[k]))]
        if g and missing:
            # secondo tentativo Gemini solo sui campi scartati
            g2 = gemini_translate({k: todo[k] for k in missing})
            for k, v in g2.items():
                if faithful(todo[k], v):
                    result[k] = v
            missing = [k for k in missing if not (k in g2 and faithful(todo[k], g2[k]))]
        for k in missing:
            try:
                v = gtx_translate(todo[k])
            except Exception as e:
                # errore di rete: NON si salva il file, si riprova al prossimo run
                raise RuntimeError(f"traduttore non raggiungibile ({k}): {e}")
            if faithful(todo[k], v):
                result[k] = v
                used.add("google")
            else:
                result[k] = todo[k]          # meglio inglese che un numero sbagliato
                used.add("en-kept")
                log(f"  campo {k}: traduzione non fedele → resta in inglese")
    return result, "+".join(sorted(used)) or "none"


# ── contenuti ──────────────────────────────────────────────────────────────

def article_fields(a):
    f = {}
    for k in ARTICLE_TEXT_KEYS:
        if isinstance(a.get(k), str) and a[k]:
            f[k] = a[k]
    for i, s in enumerate(a.get("sections") or []):
        if not isinstance(s, dict):
            continue
        for k in ("heading", "heading2", "content"):
            if isinstance(s.get(k), str) and s[k]:
                f[f"sections.{i}.{k}"] = s[k]
    for i, b in enumerate(a.get("bullets") or []):
        if isinstance(b, str) and b:
            f[f"bullets.{i}"] = b
    for i, kl in enumerate(a.get("keyLevels") or []):
        if isinstance(kl, dict) and isinstance(kl.get("label"), str) and kl["label"]:
            f[f"keyLevels.{i}.label"] = kl["label"]
    return f


def apply_article_fields(a, tr):
    out = json.loads(json.dumps(a))
    for k, v in tr.items():
        p = k.split(".")
        if len(p) == 1:
            out[k] = v
        elif p[0] == "sections":
            out["sections"][int(p[1])][p[2]] = v
        elif p[0] == "bullets":
            out["bullets"][int(p[1])] = v
        elif p[0] == "keyLevels":
            out["keyLevels"][int(p[1])]["label"] = v
    return out


def article_jobs():
    idx_path = os.path.join(ROOT, "articles", "index.json")
    order = []
    try:
        order = [x.get("slug") for x in read_json(idx_path) if x.get("slug")]
    except Exception:
        pass
    files = {os.path.basename(p)[:-5]: p for p in glob.glob(os.path.join(ROOT, "articles", "*.json"))
             if not p.endswith("index.json")}
    seen = [s for s in order if s in files]
    rest = sorted((s for s in files if s not in set(seen)), reverse=True)
    return [(s, files[s]) for s in seen + rest]


def education_jobs():
    files = sorted(glob.glob(os.path.join(ROOT, "daily_education", "*.json")), reverse=True)
    return [(os.path.basename(p)[:-5], p) for p in files if not p.endswith("index.json")]


def process_article(slug, path):
    a = read_json(path)
    h = src_hash(a)
    dst = os.path.join(OUT, "articles", slug + ".json")
    if os.path.exists(dst):
        try:
            if read_json(dst).get("_src_hash") == h:
                return False
        except Exception:
            pass
    if str(a.get("lang", "")).lower() in IT_LANG_VALUES:
        out = json.loads(json.dumps(a))
        used = "source-it"
    else:
        tr, used = translate_fields(article_fields(a))
        out = apply_article_fields(a, tr)
    out["lang"] = "it"
    out["_src_hash"] = h
    out["_translator"] = used
    write_json(dst, out)
    log(f"  ✓ articolo {slug} [{used}]")
    return True


def process_education(key, path):
    d = read_json(path)
    h = src_hash(d)
    dst = os.path.join(OUT, "daily_education", key + ".json")
    if os.path.exists(dst):
        try:
            if read_json(dst).get("_src_hash") == h:
                return False
        except Exception:
            pass
    tr, used = translate_fields({"content": d.get("content", "")})
    out = dict(d)
    out["content"] = tr["content"]
    out["_src_hash"] = h
    out["_translator"] = used
    write_json(dst, out)
    log(f"  ✓ education {key} [{used}]")
    return True


def rebuild_article_index():
    """Indice IT per la griglia del blog: titolo/estratto/categoria tradotti."""
    try:
        src = read_json(os.path.join(ROOT, "articles", "index.json"))
    except Exception:
        return
    out = {}
    for x in src:
        slug = x.get("slug")
        p = os.path.join(OUT, "articles", f"{slug}.json")
        if not slug or not os.path.exists(p):
            continue
        try:
            a = read_json(p)
        except Exception:
            continue
        excerpt = a.get("excerpt") or ""
        out[slug] = {
            "title": a.get("title") or x.get("title", ""),
            "excerpt": excerpt,
            "category": a.get("categoryLabel") or a.get("category") or x.get("category", ""),
        }
    write_json(os.path.join(OUT, "articles", "index.json"), out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=int(os.environ.get("TRANSLATE_MAX", "40")),
                    help="documenti massimi tradotti per esecuzione")
    ap.add_argument("--only", choices=["articles", "education"], default=None)
    args = ap.parse_args()

    log(f"Traduttore: {'Gemini (' + GEMINI_MODELS[0] + ') + Google fallback' if GEMINI_KEY else 'Google Translate (nessuna GEMINI_API_KEY)'}")
    jobs = []
    if args.only in (None, "articles"):
        jobs += [("a", s, p) for s, p in article_jobs()]
    if args.only in (None, "education"):
        jobs += [("e", s, p) for s, p in education_jobs()]
    # i più recenti prima, alternando blog ed education
    arts = [j for j in jobs if j[0] == "a"]
    edus = [j for j in jobs if j[0] == "e"]
    mixed = []
    for i in range(max(len(arts), len(edus))):
        if i < len(arts):
            mixed.append(arts[i])
        if i < len(edus):
            mixed.append(edus[i])

    done = 0
    fails = 0
    for kind, key, path in mixed:
        if done >= args.max:
            break
        try:
            changed = process_article(key, path) if kind == "a" else process_education(key, path)
        except Exception as e:
            log(f"  ✗ {key}: {type(e).__name__}: {e}")
            fails += 1
            if fails >= 3:
                log("Troppi errori consecutivi: stop, si riprova al prossimo run.")
                break
            continue
        fails = 0
        if changed:
            done += 1
    rebuild_article_index()
    pending = 0
    for kind, key, path in mixed:
        dst = os.path.join(OUT, "articles" if kind == "a" else "daily_education", key + ".json")
        if not os.path.exists(dst):
            pending += 1
    log(f"Tradotti in questo run: {done} · ancora da tradurre: {pending}")


if __name__ == "__main__":
    sys.exit(main())
