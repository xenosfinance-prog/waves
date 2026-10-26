import requests, socket, time
out = [time.strftime("%H:%M:%S UTC")]
for host in ("www.xenosfinance.com", "xenosfinance.com"):
    try: out.append(f"DNS {host}: {socket.gethostbyname_ex(host)}")
    except Exception as e: out.append(f"DNS {host}: ERR {e}")
ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"
for u in ("https://xenosfinance.com/", "https://xenosfinance.com/analysis/", "https://xenosfinance.com/cot/",
          "https://www.xenosfinance.com/", "https://www.xenosfinance.com/analysis/", "http://www.xenosfinance.com/analysis/"):
    r = requests.get(u, headers={"User-Agent": ua}, allow_redirects=False, timeout=20)
    h = {k: v for k, v in r.headers.items() if k.lower() in ("location", "server", "cf-mitigated", "x-github-request-id")}
    t = r.text[:400]
    title = t.split("<title>")[1].split("</title>")[0] if "<title>" in t else t[:80]
    out.append(f"{r.status_code} {u} {h} title={title!r}")
open("seo_out/www_probe.txt", "w").write("\n".join(out)); print("\n".join(out))
