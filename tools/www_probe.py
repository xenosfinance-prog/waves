import requests, re, json, time
ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"}
out = [time.strftime("%H:%M:%S UTC")]
def get(u):
    r = requests.get(u, headers=ua, timeout=25); return r
r = get("https://xenosfinance.com/futures-flow/")
h = r.text
out.append(f"futures-flow: {r.status_code} url={r.url} bytes={len(h)}")
out.append("title: " + (re.search(r"<title>(.*?)</title>", h, re.S).group(1) if "<title>" in h else "-"))
out.append("canonical: " + str(re.findall(r'rel="canonical" href="([^"]+)"', h)))
out.append("xf-page-i18n.js: " + str("xf-page-i18n.js" in h) + " · data-it count: " + str(h.count("data-it=")) + " · xf-title-it: " + str("xf-title-it" in h))
out.append("session mentions: " + str(sorted(set(re.findall(r"(?:Session|session)[^<]{0,40}?(\d{1,2} \w{3}|\d{4}-\d{2}-\d{2})", h)))[:5]))
out.append("NaN/None/undefined in page: " + str([w for w in ("NaN", ">None<", "undefined", "Traceback") if w in h]))
for path in ("/futures-flow/latest.json", "/futures-flow/history.json"):
    j = get("https://xenosfinance.com" + path)
    try:
        d = j.json()
        info = {k: d[k] for k in ("session", "generated") if isinstance(d, dict) and k in d} if isinstance(d, dict) else f"list len {len(d)}"
        if isinstance(d, dict) and "products" in d:
            info["products"] = [(p.get("name") or p.get("key"), p.get("chg_pct") or p.get("change_pct")) for p in d["products"]][:8]
        if isinstance(d, list): info = f"list len {len(d)} last={str(d[-1])[:200]}"
        if isinstance(d, dict) and "sessions" in d: info = f"sessions {len(d['sessions'])} last={str(d['sessions'][-1])[:200]}"
    except Exception as e:
        info = f"ERR {e} {j.text[:100]!r}"
    out.append(f"{path}: {j.status_code} {info}")
# link interni della pagina: tutti 200?
links = sorted(set(l for l in re.findall(r'href="(/[^"#?]*)"', h) if not l.endswith((".css", ".js", ".png", ".ico", ".json"))))
bad = []
for l in links:
    rr = requests.get("https://xenosfinance.com" + l, headers=ua, allow_redirects=False, timeout=20)
    if rr.status_code != 200: bad.append(f"{rr.status_code} {l} -> {rr.headers.get('location')}")
out.append(f"internal links {len(links)}, not-200: {bad}")
# testo italiano presente
it = re.findall(r'data-it="([^"]{20,120})', h)[:4]
out.append("IT samples: " + " | ".join(it))
open("seo_out/www_probe.txt", "w").write("\n".join(out)); print("\n".join(out))
