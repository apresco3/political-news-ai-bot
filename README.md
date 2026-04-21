# Political News AI Bot

Real-time AI system that:
- pulls political and market-policy headlines from Reuters, AP, NPR, Politico, CNBC, and NYT RSS feeds
- classifies market relevance using LLMs
- applies guardrails
- outputs paper trading signals

## Stack
- Python
- OpenAI API
- RSS feeds
- pandas

## Run locally

pip install -r requirements.txt

python news_bot.py

If you do not have an `OPENAI_API_KEY` in `.env`, the bot still runs with a
small local heuristic classifier. The heuristic is only for MVP demos and class
evaluation; use OpenAI classifications for better analysis.

## Run the dashboard

Start the local web dashboard:

python dashboard.py

Then open:

http://127.0.0.1:8765

If the dashboard says that port is busy and chooses a different port, open the
URL printed in the terminal.

If that port is busy, choose another one:

python dashboard.py --port 8766

The dashboard reads `signals_log.csv` when it exists. If the active log has not
been created yet, it falls back to `signals_log.csv.bak` so the interface can be
previewed with existing sample data.

If a local `venv/bin/python` exists, the dashboard uses it when the Refresh Feeds
button runs `news_bot.py`.

Dashboard features:
- Live signal table with source links, categories, sentiment, confidence, and guardrail outcome
- Search and filters for market-relevant stories, paper-trade actions, and no-action outcomes
- Evaluation snapshot showing no-action rate, confidence, and category distribution
- Browser-local paper-trading decisions for Buy, Sell, Risk Off, and Watch
- Refresh button that runs `news_bot.py` once and reloads the CSV

## Run continuously

Poll RSS feeds every five minutes:

python news_bot.py --loop --interval 300

Inspect fewer or more entries per feed:

python news_bot.py --max-entries 10

## Current RSS sources

- Reuters Politics
- AP Politics
- Federal Reserve All Press Releases
- Federal Reserve Monetary Policy
- SEC Press Releases
- Treasury Press Releases
- White House Presidential Actions
- USTR Trade Policy
- NPR Politics
- NPR Economy
- Politico White House
- Politico Defense
- Politico Energy
- CNBC Politics
- CNBC Economy
- BBC World
- BBC Business
- Al Jazeera News
- Guardian US Politics
- Guardian World
- NYT DealBook
- NYT Business

Reuters, AP, Treasury, White House, and USTR are read through Google News RSS
source-scoped searches where direct RSS endpoints were unavailable or less
reliable during local testing.

## Backfill missing links

If you have older rows without links, run:

python news_bot.py --migrate-links

You only need to run it once unless you have new historical rows without links.

## Backfill missing metadata (link/published/source)

If you want older rows to show real publish time and source, run:

python news_bot.py --migrate-meta

## Reset log (if corrupted)

If your CSV is corrupted (columns shifted), run:

python news_bot.py --reset-log

## Reset seen headlines

If you reset the log and want to reprocess headlines, run:

python news_bot.py --reset-seen

For demo prep, you can also clear only the seen-headlines dedupe file while
leaving the signal CSV alone:

python clear_seen_sources.py
