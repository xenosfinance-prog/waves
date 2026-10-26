import requests, socket
out = []
for host in ("www.xenosfinance.com", "xenosfinance.com"):
    try:
        out.append(f"DNS {host}: {socket.gethostbyname_ex(host)}")
    except Exception as e:
        out.append(f"DNS {host}: ERR {e}")
for ua in ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36",
           "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"):
    for u in ("https://www.xenosfinance.com/", "https://www.xenosfinance.com/analysis/", "http://www.xenosfinance.com/",
              "https://xenosfinance.com/", "http://xenosfinance.com/analysis/"):
        try:
            r = requests.get(u, headers={"User-Agent": ua}, allow_redirects=False, timeout=20)
            h = {k: v for k, v in r.headers.items() if k.lower() in ("location", "server", "cf-ray", "cf-mitigated", "content-type")}
            out.append(f"[{ua[:20]}] {r.status_code} {u} {h} BODY: {r.text[:160]!r}")
        except Exception as e:
            out.append(f"[{ua[:20]}] ERR {u} {e}")
open("seo_out/www_probe.txt", "w").write("\n".join(out))
print("\n".join(out))
