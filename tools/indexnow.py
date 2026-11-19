#!/usr/bin/env python3
"""
XenosFinance — IndexNow (2026-11-14, SEO / AI search).

Avvisa Bing (e gli altri motori IndexNow: Yandex, Seznam, Naver…) delle pagine
nuove o aggiornate, così vengono indicizzate in ore invece che in settimane.
ChatGPT Search e Copilot si appoggiano all'indice di Bing.

Gratuito, nessun account: la "chiave" è il file /<KEY>.txt nella root del sito.

Uso:
  python tools/indexnow.py --since "2 hours 15 minutes ago"   # file cambiati nei commit recenti
  python tools/indexnow.py --all                               # tutte le pagine principali (primo invio)
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://xenosfinance.com"
HOST = "xenosfinance.com"
ENDPOINT = "https://api.indexnow.org/indexnow"
LANGS = ("it", "es", "ru", "uk")

STATIC = ["/", "/dashboard", "/calendar", "/elliottwave", "/XenosBlog", "/daily-education", "/analysis/",
          "/analysis/oil-market", "/cot/", "/futures-flow/", "/oil-options/", "/intelligence/", "/market-brief",
          "/trading-ideas", "/live-setups", "/xenoswaves_charts", "/topics", "/premium", "/llms.txt"]


def key():
    keys = [os.path.basename(p)[:-4] for p in glob.glob(os.path.join(ROOT, "*.txt"))
            if re.fullmatch(r"[0-9a-f]{32}", os.path.basename(p)[:-4])]
    if not keys:
        sys.exit("chiave IndexNow non trovata (file <32 hex>.txt nella root)")
    return keys[0]


def url_for(path):
    """Percorso di un file del repo → URL pubblico (None se non è una pagina)."""
    p = path.replace("\\", "/")
    m = re.fullmatch(r"articles/([A-Za-z0-9_-]+)\.json", p)
    if m and m.group(1) != "index":
        return f"{SITE}/XenosBlog?slug={m.group(1)}"
    m = re.fullmatch(r"daily_education/(\d{4}-\d{2}-\d{2})\.json", p)
    if m:
        return f"{SITE}/daily-education?d={m.group(1)}"
    m = re.fullmatch(r"i18n/(it|es|ru|uk)/articles/([A-Za-z0-9_-]+)\.json", p)
    if m and m.group(2) != "index":
        return f"{SITE}/XenosBlog?slug={m.group(2)}&lang={m.group(1)}"
    m = re.fullmatch(r"i18n/(it|es|ru|uk)/daily_education/(\d{4}-\d{2}-\d{2})\.json", p)
    if m:
        return f"{SITE}/daily-education?d={m.group(2)}&lang={m.group(1)}"
    m = re.fullmatch(r"analysis/([a-z0-9-]+)\.html", p)
    if m:
        return f"{SITE}/analysis/" if m.group(1) == "index" else f"{SITE}/analysis/{m.group(1)}"
    for d in ("cot", "futures-flow", "intelligence"):
        if p == f"{d}/index.html":
            return f"{SITE}/{d}/"
    if p == "llms.txt":
        return f"{SITE}/llms.txt"
    if p == "index.html":
        return f"{SITE}/"
    m = re.fullmatch(r"([A-Za-z0-9_-]+)\.html", p)
    if m and m.group(1) not in ("XenosBlogAdmin", "signals", "signalsarchive", "portfolio",
                                "stripe-frontend-snippet", "elliottwave-newbie", "elliottwave-pro"):
        return f"{SITE}/{m.group(1)}"
    return None


def changed_since(since):
    out = subprocess.run(["git", "-C", ROOT, "log", f"--since={since}", "--name-only", "--pretty=format:"],
                         capture_output=True, text=True, check=True).stdout
    return sorted({f.strip() for f in out.splitlines() if f.strip()})


def all_urls():
    urls = [SITE + p for p in STATIC]
    files = glob.glob(os.path.join(ROOT, "analysis", "*.html"))
    files += glob.glob(os.path.join(ROOT, "articles", "*.json"))
    files += glob.glob(os.path.join(ROOT, "daily_education", "*.json"))
    for f in files:
        u = url_for(os.path.relpath(f, ROOT))
        if u:
            urls.append(u)
    return urls


def submit(urls):
    urls = list(dict.fromkeys(urls))
    if not urls:
        print("Nessuna pagina nuova da segnalare.")
        return
    k = key()
    for i in range(0, len(urls), 9000):
        part = urls[i:i + 9000]
        body = json.dumps({"host": HOST, "key": k, "keyLocation": f"{SITE}/{k}.txt", "urlList": part}).encode()
        req = urllib.request.Request(ENDPOINT, data=body, headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                print(f"IndexNow: {len(part)} URL inviati → HTTP {r.status}")
        except urllib.error.HTTPError as e:
            # 200/202 = ok; 403 = chiave non ancora raggiungibile sul sito; 422 = URL non del dominio; 429 = troppe richieste
            print(f"::warning::IndexNow HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:200]}")
    for u in urls[:15]:
        print("  ", u)
    if len(urls) > 15:
        print(f"   … e altri {len(urls) - 15}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=None)
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if a.all:
        submit(all_urls())
    else:
        files = changed_since(a.since or "2 hours 15 minutes ago")
        submit([u for u in (url_for(f) for f in files) if u])


if __name__ == "__main__":
    main()
