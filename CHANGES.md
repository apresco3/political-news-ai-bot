## Update Template

Copy this block and append it for each new change batch:

```md
## YYYY-MM-DD

### Summary
- Short description of what changed.

### Files
- `path/to/file1`
- `path/to/file2`

### Infra impact
- New resources / modified resources / removed resources.

### Deploy notes
- Commands run and any caveats.
```

### Summary
- Renamed manual paper-trade choices to Bullish Equities, Bearish Bonds, Risk Off, and Watch, with migration for older Buy/Sell browser-local choices.
- Added all requested additional RSS sources: Federal Reserve press releases/monetary policy, SEC press releases, Treasury, White House actions, USTR trade policy, BBC World/Business, Al Jazeera, and Guardian US Politics/World.
- Corrected legacy timestamp conversion so old timezone-less `Published` values are treated as feed/UTC time and display as ET, while old scrape `Time` values remain local ET.
- Standardized backend and dashboard timestamps to Eastern Time, including an `ET` suffix for scraped time, published time, dashboard update time, sorting, and display.
- Sorted dashboard news articles by publish date/time descending, with scrape time as a fallback when published time is missing.
- Expanded RSS coverage beyond Reuters and NYT with AP Politics, NPR Politics/Economy, Politico White House/Defense/Energy, and CNBC Politics/Economy feeds.
- Replaced unreliable direct Reuters/AP politics RSS endpoints with source-scoped Google News RSS searches after local availability checks showed the Reuters host failed DNS and the AP endpoint returned 404.
- Added normalized headline deduplication in the backend and dashboard so repeated stories with source suffix or punctuation differences do not show up twice.
- Fixed dashboard removal for legacy paper-trade entries saved before trade IDs existed, and added automatic migration/deduplication of browser-local paper-trade state.
- Updated dashboard paper-trading controls so each headline can have only one selected decision at a time, selected actions are highlighted, and saved paper-trade items can be removed.
- Added `clear_seen_sources.py`, a demo helper that clears the seen-headlines dedupe file so the bot can scrape current RSS items from scratch without deleting the signal log.
- Added an MVP local dashboard for viewing classified political news, guardrail outcomes, evaluation metrics, source links, and browser-local paper-trading decisions.
- Added a continuous polling mode to the news bot with configurable interval and entries-per-feed.
- Added a cautious offline heuristic classifier so the project can run locally for demos even when `OPENAI_API_KEY` is missing or the OpenAI request fails.
- Tightened the LLM classification prompt to prefer low confidence or no action for ambiguous headlines.
- Updated local run instructions for the dashboard, loop mode, and demo fallback behavior.

### Files
- `news_bot.py`
- `dashboard.py`
- `clear_seen_sources.py`
- `README.md`
- `CHANGES.md`
- `requirements.txt`

### Infra impact
- No new hosted resources.
- Dashboard uses Python's standard-library HTTP server, defaults to `127.0.0.1:8765`, supports `--port`, and automatically chooses the next open port if the requested port is busy.
- Paper-trading decisions are stored in browser `localStorage`; classifications continue to use `signals_log.csv`.

### Deploy notes
- Install dependencies with `pip install -r requirements.txt`.
- Run backend once with `python news_bot.py`.
- Run continuous ingestion with `python news_bot.py --loop --interval 300`.
- Run dashboard with `python dashboard.py`, then open `http://127.0.0.1:8765`.
- Caveat: the local heuristic classifier is intentionally simple and should be described as a fallback/demo mode, not equivalent to the LLM path.
