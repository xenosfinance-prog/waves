#!/usr/bin/env python3
"""Rigenera ews_engine.py (motore + grafico del /ews) da xenosfinance-bot/bot.py.

2026-11-19: il sito (Live Analysis di elliottwave.html, endpoint /ews-chart di ew_server.py)
usa ESATTAMENTE le funzioni del /ews del bot. Questo script copia da bot.py, senza
riscriverle, tutte le funzioni e costanti necessarie a _ews_build (conteggio, piano target,
grafico). Le sole modifiche sono le etichette del timeframe, che nel bot sono fisse a 4H.

Uso:  python tools/sync_ews_engine.py /percorso/xenosfinance-bot/bot.py
"""
import ast
import sys
from pathlib import Path

ROOTS = ["_ews_build", "fetch_data", "resample_4h_tv", "MARKETS", "_ews_pf", "_ews_num",
         "_ews_chart", "EWS_BARS_DAYS", "EWS_BARS_DAYS_STOCKS", "EWS_STOCKS"]

# etichette del timeframe (nel bot sono sempre 4H)
REPLACE = [
    ("f\"{mkt.get('emoji', '')} <b>{mkt['name']}</b> · 4H · {datetime.utcnow():%d %b %Y}\"",
     "f\"{mkt.get('emoji', '')} <b>{mkt['name']}</b> · {EWS_TF_TXT} · {datetime.utcnow():%d %b %Y}\""),
    ("f\"{mkt['name']}  ·  4h  ·  XenosFinance\"",
     "f\"{mkt['name']}  ·  {EWS_TF_CHART}  ·  XenosFinance\""),
]

HEADER = '''"""ews_engine.py — motore Elliott Wave del /ews (bot Telegram) usato dal sito.

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

'''


def main(bot_path, out_path):
    src = Path(bot_path).read_text(encoding="utf-8")
    tree = ast.parse(src)
    lines = src.splitlines(keepends=True)
    defs, order = {}, []
    for node in tree.body:
        names = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [n.id for t in node.targets for n in ast.walk(t) if isinstance(n, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        for nm in names:
            defs.setdefault(nm, []).append(node)
        order.append(node)
    need, stack = set(), list(ROOTS)
    while stack:
        nm = stack.pop()
        for node in defs.get(nm, []):
            if id(node) in need:
                continue
            need.add(id(node))
            stack += [n.id for n in ast.walk(node) if isinstance(n, ast.Name) and n.id in defs]
    parts = []
    for node in order:
        if id(node) not in need:
            continue
        start = (node.decorator_list[0].lineno if getattr(node, "decorator_list", None) else node.lineno) - 1
        parts.append("".join(lines[start:node.end_lineno]))
    body = "\n\n".join(parts) + "\n"
    for a, b in REPLACE:
        if body.count(a) != 1:
            sys.exit(f"replace non trovato o multiplo ({body.count(a)}): {a[:70]}")
        body = body.replace(a, b)
    Path(out_path).write_text(HEADER + body, encoding="utf-8")
    print(f"ews_engine.py: {len(need)} blocchi da bot.py → {out_path}")


if __name__ == "__main__":
    here = Path(__file__).resolve().parent.parent
    main(sys.argv[1] if len(sys.argv) > 1 else "../xenosfinance-bot/bot.py", here / "ews_engine.py")
