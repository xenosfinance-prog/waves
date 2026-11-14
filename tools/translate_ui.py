#!/usr/bin/env python3
"""
XenosFinance — dizionari dell'interfaccia per le lingue aggiuntive (2026-11-14).

Le etichette del sito (menu, pulsanti, titoli: chiavi data-i18n) stanno in
i18n.js per EN e IT. Per ES, RU e UK questo script crea:
    i18n/ui/<lingua>.json   dizionario + hash dell'inglese di ogni chiave
    i18n/ui/<lingua>.js     lo stesso dizionario, caricato da i18n-engine.js
Ritraduce solo le chiavi nuove o il cui testo inglese è cambiato.

Costo zero: stessi traduttori di translate_content.py (Gemini piano gratuito,
poi Google Translate pubblico) con gli stessi controlli di fedeltà (numeri e
tag HTML identici). Se una chiave non si traduce resta l'inglese.

Uso:  python tools/translate_ui.py [--lang es|ru|uk]   (richiede node per leggere i18n.js)
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import translate_content as TC  # noqa: E402

ROOT = TC.ROOT
UI_DIR = os.path.join(ROOT, "i18n", "ui")
UI_LANGS = ["es", "ru", "uk"]
BATCH = 50
PH_RE = re.compile(r"\{[^}]*\}|%[sd]|\$\{[^}]*\}")


def english_dict():
    js = (
        "global.window=global;global.document={addEventListener(){},querySelectorAll(){return[]},"
        "getElementById(){return null},readyState:'complete'};"
        "global.localStorage={getItem(){return null},setItem(){}};"
        "const fs=require('fs');let src=fs.readFileSync(process.argv[1],'utf8');"
        "src=src.replace(/^\\s*(const|let|var)\\s+XENOS_I18N\\s*=/m,'global.XENOS_I18N=');"
        "try{eval(src)}catch(e){}"
        "process.stdout.write(JSON.stringify(global.XENOS_I18N.en))"
    )
    out = subprocess.run(["node", "-e", js, os.path.join(ROOT, "i18n.js")],
                         capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    return {k: v for k, v in d.items() if isinstance(v, str)}


def h(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def load(lang):
    p = os.path.join(UI_DIR, lang + ".json")
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        return d.get("dict", {}), d.get("src", {})
    except Exception:
        return {}, {}


def save(lang, dct, src):
    os.makedirs(UI_DIR, exist_ok=True)
    TC.write_json(os.path.join(UI_DIR, lang + ".json"), {"lang": lang, "dict": dct, "src": src})
    body = json.dumps(dct, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    js = ("/* XenosFinance UI — " + lang + " (generato da tools/translate_ui.py, non modificare a mano) */\n"
          "(window.XF_I18N_EXTRA = window.XF_I18N_EXTRA || {})['" + lang + "'] = " + body + ";\n")
    with open(os.path.join(UI_DIR, lang + ".js"), "w", encoding="utf-8") as f:
        f.write(js)


def placeholders_ok(src, dst):
    return sorted(PH_RE.findall(src)) == sorted(PH_RE.findall(dst))


def run_lang(lang, en):
    TC.set_lang(lang)
    dct, src = load(lang)
    # chiavi tolte dall'inglese → via anche qui
    for k in list(dct):
        if k not in en:
            dct.pop(k, None)
            src.pop(k, None)
    todo = [k for k, v in en.items() if src.get(k) != h(v) and TC.needs_translation(v)]
    for k, v in en.items():                      # solo numeri/simboli: copiati così come sono
        if not TC.needs_translation(v):
            dct[k], src[k] = v, h(v)
    TC.log(f"[{lang}] chiavi da tradurre: {len(todo)} su {len(en)}")
    done = 0
    for i in range(0, len(todo), BATCH):
        part = {k: en[k] for k in todo[i:i + BATCH]}
        try:
            tr, used = TC.translate_fields(part)
        except Exception as e:
            TC.log(f"  ✗ [{lang}] blocco {i // BATCH + 1}: {e}")
            break
        for k, v in tr.items():
            if not placeholders_ok(part[k], v):
                continue
            dct[k] = v
            if v != part[k]:                     # uguale all'inglese: si ritenta al prossimo run
                src[k] = h(part[k])
                done += 1
        save(lang, dct, src)                     # salvataggio a ogni blocco
        TC.log(f"  ✓ [{lang}] blocco {i // BATCH + 1} [{used}]")
    save(lang, dct, src)
    TC.log(f"[{lang}] tradotte in questo run: {done} · totale: {len(dct)}/{len(en)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=UI_LANGS, default=None)
    args = ap.parse_args()
    if TC.GEMINI_KEY:
        TC.GEMINI_MODELS[:] = TC.discover_gemini_models()
    en = english_dict()
    for lang in ([args.lang] if args.lang else UI_LANGS):
        run_lang(lang, en)


if __name__ == "__main__":
    sys.exit(main())
