# XenosFinance Market Intelligence Agent

AI-powered financial market brief. RSS → Gemini AI → HTML → GitHub → xenosfinance.com/market-brief

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your keys
```

## Required env vars

```
GEMINI_API_KEY=...     # Google AI Studio
GITHUB_TOKEN=...       # GitHub personal access token (repo scope)
```

## Run

```bash
# Full pipeline (generates + publishes to GitHub)
GEMINI_API_KEY=xxx GITHUB_TOKEN=xxx PYTHONPATH=. python -B app/main.py

# Local test only (no GitHub publish)
GEMINI_API_KEY=xxx PYTHONPATH=. python -B app/main.py --no-publish

# Local test with browser preview
GEMINI_API_KEY=xxx PYTHONPATH=. python -B app/main.py --no-publish --serve
```

## Railway deploy (production)

Add these env vars in Railway → Settings → Variables:
- GEMINI_API_KEY
- GITHUB_TOKEN
- GITHUB_REPO=xenosfinance-prog/waves
- GITHUB_PATH=market-brief.html

Then add a cron job in Railway:
```
0 * * * *   PYTHONPATH=. python -B app/main.py
```
Runs every hour — generates brief and auto-publishes to xenosfinance.com/market-brief

## Pipeline steps

1. RSSCollector    — fetch 20 feeds in parallel
2. Deduplicator    — remove duplicates (Jaccard similarity)
3. Classifier      — category + sentiment per article
4. MarketAnalyzer  — aggregate stats, bull/bear %
5. GeminiWriter    — AI brief via gemini-2.5-flash (3 retries)
6. HTMLWriter      — full styled HTML (XenosFinance design)
7. GitHubPublisher — PUT to GitHub → Cloudflare Pages deploys automatically
