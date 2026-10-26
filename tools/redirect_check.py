"""Controlla catene di redirect come le vede Google (usato solo dal workflow seo-check)."""
import re, requests, sys
from urllib.parse import urlparse
BASE = "https://xenosfinance.com"
UA = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"}
locs = re.findall(r"<loc>([^<]+)</loc>", open("sitemap.xml").read())
try:
    locs += re.findall(r"<loc>([^<]+)</loc>", requests.get(BASE + "/sitemap-setups.xml", headers=UA, timeout=20).text)
except Exception:
    pass
cands = set()
for u in locs:
    u = u.replace("&amp;", "&")
    cands.add(u)
    p = urlparse(u)
    path = p.path
    q = ("?" + p.query) if p.query else ""
    for host in ("http://xenosfinance.com", "https://www.xenosfinance.com", "http://www.xenosfinance.com"):
        cands.add(host + path + q)
    if path not in ("", "/"):
        if path.endswith("/"):
            cands.add(BASE + path.rstrip("/") + q)
            cands.add(BASE + path + "index.html" + q)
        else:
            cands.add(BASE + path + "/" + q)
            cands.add(BASE + path + ".html" + q)
for extra in ["/index.html", "/it/", "/ru/analysis/", "/analysis/index.html", "/cot/index.html", "/futures-flow/index.html",
              "/portfolio", "/portfolio.html", "/signals", "/signals.html", "/signalsarchive", "/blog/", "/feed/",
              "/XenosBlog.html", "/elliottwave.html", "/trade-setups/", "/topics/", "/setups", "/setups/"]:
    cands.add(BASE + extra)
rows, bad = [], []
for u in sorted(cands):
    chain, cur = [], u
    try:
        for _ in range(12):
            r = requests.get(cur, headers=UA, allow_redirects=False, timeout=20)
            chain.append(f"{r.status_code} {cur}")
            if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                nxt = requests.compat.urljoin(cur, r.headers["location"])
                if nxt in [c.split(" ", 1)[1] for c in chain]:
                    chain.append(f"LOOP -> {nxt}"); break
                cur = nxt
            else:
                break
        else:
            chain.append("TOO MANY REDIRECTS")
    except Exception as e:
        chain.append(f"ERR {e}")
    hops = sum(1 for c in chain if c[:3] in ("301", "302", "303", "307", "308"))
    final = chain[-1]
    problem = ("LOOP" in final or "TOO MANY" in final or final.startswith("ERR")
               or (final[:3] not in ("200",) and not final.startswith("LOOP")) or hops >= 3)
    line = " | ".join(chain)
    rows.append(line)
    if problem:
        bad.append(line)
open("seo_out/redirects_all.txt", "w").write("\n".join(rows))
open("seo_out/redirects_bad.txt", "w").write("\n".join(bad))
print(len(rows), "checked,", len(bad), "problems")
