import requests, time
out = [time.strftime("%H:%M:%S UTC")]
ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"
for u in ("https://www.xenosfinance.com/", "https://www.xenosfinance.com/analysis/", "http://www.xenosfinance.com/cot/",
          "https://www.xenosfinance.com/XenosBlog?slug=article-1777981266856", "https://www.xenosfinance.com/setups/",
          "https://xenosfinance.com/", "https://xenosfinance.com/analysis/"):
    chain, cur = [], u
    for _ in range(6):
        r = requests.get(cur, headers={"User-Agent": ua}, allow_redirects=False, timeout=20)
        t = r.text[:600]
        title = t.split("<title>")[1].split("</title>")[0] if "<title>" in t else ""
        chain.append(f"{r.status_code} {cur}" + (f" [{title[:50]}]" if r.status_code == 200 or r.status_code >= 400 else ""))
        if r.status_code in (301, 302, 307, 308):
            cur = requests.compat.urljoin(cur, r.headers["location"])
        else:
            break
    out.append(" -> ".join(chain))
open("seo_out/www_probe.txt", "w").write("\n".join(out)); print("\n".join(out))
