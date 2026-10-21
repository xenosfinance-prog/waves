#!/usr/bin/env python3
import sys
import os

# Ensure /app is in path so flat imports work
sys.path.insert(0, '/app')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
from datetime import datetime, timedelta

# 2026-10-21: due edizioni al giorno, alle 10:30 e alle 17:00 ora ITALIANA.
# Il cron di Railway è solo in UTC e l'ora italiana cambia con l'ora legale,
# quindi il cron gira agli orari UTC di entrambe le stagioni
# ("0,30 8-11,15-17 * * *") e qui si parte solo se a Roma è uno degli orari
# voluti. Orari configurabili con la env BRIEF_TIMES_ROME (es. "10:30,17:00").
BRIEF_TIMES_ROME = os.environ.get("BRIEF_TIMES_ROME", "10:30,17:00")
# 2026-10-21 (2): il 21/10 il cron di Railway non è partito alle 10:30 (nessuna
# esecuzione registrata). Ora ogni edizione ha una finestra di recupero di 2 ore:
# il cron gira ogni 30 minuti nella finestra e pubblica alla PRIMA esecuzione
# riuscita; le successive vedono che l'edizione è già su GitHub e saltano.
WINDOW_MINUTES = int(os.environ.get("BRIEF_WINDOW_MINUTES", "120"))


def _rome_now() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Rome")).replace(tzinfo=None)
    except Exception:
        # Fallback senza tzdata: regola UE dell'ora legale (ultima domenica di
        # marzo → ultima domenica di ottobre, cambio alle 01:00 UTC).
        utc = datetime.utcnow()
        def last_sunday(month):
            d = datetime(utc.year, month, 31 if month in (3, 10) else 30, 1, 0)
            return d - timedelta(days=(d.weekday() + 1) % 7)
        dst = last_sunday(3) <= utc < last_sunday(10)
        return utc + timedelta(hours=2 if dst else 1)


def _scheduled_slot():
    """(orario HH:MM, minuti trascorsi dall'orario) dell'edizione in finestra, o None."""
    now = _rome_now()
    for slot in [t.strip() for t in BRIEF_TIMES_ROME.split(",") if t.strip()]:
        try:
            hh, mm = (int(x) for x in slot.split(":"))
        except ValueError:
            continue
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if timedelta(0) <= now - target < timedelta(minutes=WINDOW_MINUTES):
            return slot, (now - target).total_seconds() / 60.0
    return None


def _already_published(minutes_since_slot: float):
    """True se market-brief.html è stato aggiornato su GitHub dopo l'orario
    dell'edizione; None se GitHub non risponde (stato sconosciuto)."""
    import json, urllib.request
    token = os.getenv("GITHUB_TOKEN", "")
    repo = os.getenv("GITHUB_REPO", "xenosfinance-prog/waves")
    path = os.getenv("GITHUB_PATH", "market-brief.html")
    branch = os.getenv("GITHUB_BRANCH", "main")
    since = (datetime.utcnow() - timedelta(minutes=minutes_since_slot)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"https://api.github.com/repos/{repo}/commits?path={path}&sha={branch}&since={since}&per_page=1"
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "XenosFinance-MarketAgent/1.0"}
    if token:
        headers["Authorization"] = f"token {token}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as r:
            return len(json.loads(r.read().decode("utf-8"))) > 0
    except Exception as e:
        print(f"GitHub check failed ({e}) — assuming not published yet")
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", "-o", default="site/market-brief.html")
    parser.add_argument("--no-publish", action="store_true")
    parser.add_argument("--force", action="store_true", help="ignora gli orari, esegui subito")
    args = parser.parse_args()

    if not args.force and os.environ.get("BRIEF_FORCE_RUN", "").strip() != "1":
        found = _scheduled_slot()
        if found is None:
            print(f"Not a brief time in Rome ({_rome_now():%H:%M}, scheduled {BRIEF_TIMES_ROME}) — skipping.")
            return
        slot, elapsed = found
        if _already_published(elapsed):
            print(f"Brief edition {slot} already published — skipping.")
            return
        print(f"Brief edition {slot} (Rome time, {elapsed:.0f} min after schedule)")

    from pipeline import MarketIntelligencePipeline

    publish  = not args.no_publish
    pipeline = MarketIntelligencePipeline(output_path=args.output, publish=publish)
    result   = pipeline.run()

    if not result:
        print("Pipeline failed.", file=sys.stderr)
        sys.exit(1)

    print(f"\n✓ Done: {result}")
    if not publish:
        print("  (GitHub publish skipped)")

if __name__ == "__main__":
    main()
