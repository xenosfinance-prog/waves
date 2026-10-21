"""One-off: pubblica il Market Brief del mattino del 21/10/2026 da GitHub Actions
(Railway aveva build/deploy in pausa). Stessa pipeline del servizio
market-intelligence-agent; il testo AI usa Claude se Gemini non è configurato.
Da eliminare dopo l'esecuzione."""
import os, sys, json, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gemini_writer as gw


def _claude_generate(self, articles, market_data):
    prompt = gw._build_prompt(articles, market_data)
    body = json.dumps({"model": "claude-sonnet-4-6", "max_tokens": 4000,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
        "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read().decode())
    text = "".join(b.get("text", "") for b in data.get("content", [])).strip()
    if "##" not in text:
        print("Claude reply without ## sections:", text[:300])
        return None
    print(f"Claude brief: {len(text)} chars")
    return text


if not os.getenv("GEMINI_API_KEY"):
    gw.GeminiWriter.generate = _claude_generate

from pipeline import MarketIntelligencePipeline
res = MarketIntelligencePipeline(output_path="site/market-brief.html", publish=True).run()
if not res:
    sys.exit("pipeline failed")
print("published:", res)
