"""One-off: pubblica il Market Brief del mattino del 21/10/2026 da GitHub Actions
(Railway aveva build/deploy in pausa). Stessa pipeline del servizio
market-intelligence-agent; il testo AI usa Claude se Gemini non è configurato.
Da eliminare dopo l'esecuzione."""
import os, sys, json, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# GITHUB_PATH è una variabile riservata di GitHub Actions (file temporaneo del
# runner): il publisher la leggeva come percorso del brief → 422 "path cannot
# start with a slash". Qui va forzata prima di importare il publisher.
os.environ["GITHUB_PATH"] = "market-brief.html"
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
import github_publisher as gp
_orig_publish = gp.GitHubPublisher.publish
def _strict_publish(self, html_path):
    ok = _orig_publish(self, html_path)
    print("GitHub publish result:", ok, "| token set:", bool(self.token), "| repo:", self.repo)
    if not ok:
        sys.exit("publish failed")
    return ok
gp.GitHubPublisher.publish = _strict_publish
print("GEMINI key set:", bool(os.getenv("GEMINI_API_KEY")), "| ANTHROPIC key set:", bool(os.getenv("ANTHROPIC_API_KEY")))
res = MarketIntelligencePipeline(output_path="site/market-brief.html", publish=True).run()
if not res:
    sys.exit("pipeline failed")
print("published:", res)
