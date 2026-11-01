#!/usr/bin/env python3
"""Prova dell'hub petrolio su dati reali (solo branch di audit): calcola WTI e Brent come le
pagine /analysis e scrive tools/oil_hub_preview.html. Non tocca analysis/ né la sitemap."""
import os, sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_analysis_pages as G
import gen_oil_hub as OH

now = datetime.now(timezone.utc)
built = []
for inst in G.INSTRUMENTS:
    if inst[0] in ("wti-crude-oil", "brent-crude-oil"):
        d = G.E._ta_compute(inst[1], inst[4], interval="1h", period="60d", htf_rule="4h", ew_tf="H4 (4-Hour)")
        built.append((inst, d, None))
G.RELATED.update(G.related_articles())
html = OH.build(G, built, now)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "oil_hub_preview.html")
open(out, "w", encoding="utf-8").write(html or "NO PAGE")
print("written", out, len(html or ""))
