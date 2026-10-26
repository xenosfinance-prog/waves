"""Render reale delle pagine (Chromium) — menu, pannelli della Home, errori console."""
import asyncio, json, re, requests
from playwright.async_api import async_playwright
B = "https://xenosfinance.com"
PAGES = ["/", "/market-brief", "/intelligence/", "/dashboard", "/portfolio", "/cot/", "/futures-flow/", "/analysis/",
         "/xenoswaves_charts", "/XenosBlog", "/topics", "/trading-ideas", "/trading-signals", "/trade-setups", "/calendar",
         "/elliottwave", "/daily-education", "/premium-support", "/premium"]
out = []
async def main():
    async with async_playwright() as p:
        br = await p.chromium.launch()
        for path in PAGES:
            pg = await br.new_page(viewport={"width": 1400, "height": 900})
            errs = []
            pg.on("console", lambda m: errs.append(m.text[:160]) if m.type == "error" else None)
            pg.on("pageerror", lambda e: errs.append("PAGEERROR " + str(e)[:160]))
            try:
                r = await pg.goto(B + path, wait_until="networkidle", timeout=45000)
                st = r.status if r else "?"
            except Exception as e:
                st = f"ERR {e}"[:80]
            await pg.wait_for_timeout(2500)
            nav = await pg.evaluate("""() => {
              const box = document.querySelector('.masthead-nav') || document.querySelector('header nav') || document.querySelector('nav');
              if (!box) return [];
              return [...box.querySelectorAll('a')].map(a => (a.textContent||'').trim().replace(/\\s+/g,' ') + ' => ' + a.getAttribute('href'));
            }""")
            out.append(f"\n### {path}  status={st}")
            out.append("NAV: " + " | ".join(nav))
            if errs: out.append("CONSOLE ERRORS: " + " || ".join(errs[:6]))
            if path == "/":
                info = await pg.evaluate("""() => [...document.querySelectorAll('.panel')].map(p => {
                    const t = p.querySelector('.panel-title'); const n = p.querySelectorAll('.news-item').length;
                    const txt = (p.innerText||'').trim().slice(0,140).replace(/\\s+/g,' ');
                    return (t? t.innerText.trim(): '?') + ' :: news-items=' + n + ' :: ' + txt; })""")
                out.append("HOME PANELS:\n  " + "\n  ".join(info))
                st2 = await pg.evaluate("() => [...document.querySelectorAll('[id$=-status],[id*=status]')].map(e => e.id + '=' + e.innerText.trim().slice(0,80))")
                out.append("STATUS: " + " | ".join(st2))
                await pg.screenshot(path="seo_out/home_full.png", full_page=True)
            await pg.close()
        await br.close()
asyncio.run(main())
open("seo_out/site_audit.txt", "w").write("\n".join(out)); print("\n".join(out))
