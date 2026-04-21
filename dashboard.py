import argparse
import csv
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

LOG_FILE = "signals_log.csv"
BACKUP_LOG_FILE = "signals_log.csv.bak"
HOST = "127.0.0.1"
PORT = 8765
EASTERN = timezone(timedelta(hours=-5), "ET")
TIME_FORMAT = "%Y-%m-%d %H:%M:%S ET"


def active_log_file():
    if os.path.exists(LOG_FILE):
        return LOG_FILE
    if os.path.exists(BACKUP_LOG_FILE):
        return BACKUP_LOG_FILE
    return LOG_FILE


def read_signals(limit=200):
    path = active_log_file()
    if not os.path.exists(path):
        return []

    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    rows.sort(key=signal_sort_timestamp, reverse=True)
    cleaned = []
    seen_headlines = set()
    for row in rows:
        row = {key: (value or "").strip() for key, value in row.items()}
        dedupe_key = normalize_headline(row.get("Headline", ""))
        if dedupe_key in seen_headlines:
            continue
        seen_headlines.add(dedupe_key)
        try:
            row["ConfidenceNumeric"] = int(float(row.get("Confidence", 0) or 0))
        except ValueError:
            row["ConfidenceNumeric"] = 0
        row["Published"] = format_eastern_display(row.get("Published", ""), legacy_tz=timezone.utc)
        row["Time"] = format_eastern_display(row.get("Time", ""), legacy_tz=EASTERN)
        cleaned.append(row)
        if len(cleaned) >= limit:
            break
    return cleaned


def build_summary(rows):
    total = len(rows)
    actions = [row for row in rows if row.get("Action", "").startswith(("BUY", "SELL", "RISK"))]
    no_actions = total - len(actions)
    relevant = [row for row in rows if row.get("MarketRelevant", "").lower() == "yes"]
    avg_confidence = round(sum(row["ConfidenceNumeric"] for row in rows) / total, 1) if total else 0
    high_confidence_actions = [
        row for row in actions
        if row["ConfidenceNumeric"] >= 70
    ]

    by_category = {}
    for row in rows:
        category = row.get("Category") or "Unknown"
        by_category[category] = by_category.get(category, 0) + 1

    return {
        "total": total,
        "actions": len(actions),
        "noActions": no_actions,
        "noActionRate": round((no_actions / total) * 100, 1) if total else 0,
        "marketRelevant": len(relevant),
        "avgConfidence": avg_confidence,
        "highConfidenceActions": len(high_confidence_actions),
        "byCategory": by_category,
        "logFile": active_log_file(),
        "updatedAt": datetime.now(EASTERN).strftime(TIME_FORMAT),
    }


def bot_python():
    venv_python = os.path.join("venv", "bin", "python")
    if os.path.exists(venv_python):
        return venv_python
    return sys.executable


def run_refresh():
    result = subprocess.run(
        [bot_python(), "news_bot.py", "--max-entries", "5"],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    return {
        "returnCode": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
    }


def normalize_headline(text):
    value = (text or "").lower()
    value = re.sub(
        r"\s+[-|]\s+(reuters|ap news|associated press|nyt|new york times|politico|npr|cnbc)\s*$",
        "",
        value,
    )
    value = re.sub(r"[^a-z0-9\s]", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def signal_sort_timestamp(row):
    for field, legacy_tz in (("Published", timezone.utc), ("Time", EASTERN)):
        parsed = parse_datetime(row.get(field, ""), legacy_tz=legacy_tz)
        if parsed:
            return parsed.timestamp()
    return 0


def parse_datetime(value, legacy_tz=EASTERN):
    value = (value or "").strip()
    if not value:
        return None

    formats = [
        "%Y-%m-%d %H:%M:%S ET",
        "%Y-%m-%d %H:%M:%S",
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
    ]
    for fmt in formats:
        try:
            parsed = datetime.strptime(value, fmt)
            if parsed.tzinfo is None and re.search(r"\s(GMT|UTC)$", value, re.IGNORECASE):
                parsed = parsed.replace(tzinfo=timezone.utc)
            return ensure_eastern(parsed, legacy_tz=legacy_tz)
        except ValueError:
            pass

    try:
        return ensure_eastern(datetime.fromisoformat(value.replace("Z", "+00:00")), legacy_tz=legacy_tz)
    except ValueError:
        return None


def ensure_eastern(value, legacy_tz=EASTERN):
    if value.tzinfo is None:
        value = value.replace(tzinfo=legacy_tz)
    return value.astimezone(EASTERN)


def format_eastern_display(value, legacy_tz=EASTERN):
    parsed = parse_datetime(value, legacy_tz=legacy_tz)
    if not parsed:
        return value
    return parsed.strftime(TIME_FORMAT)


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Political News AI Dashboard</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #1d242f;
      --muted: #5f6875;
      --line: #d8dde6;
      --surface: #ffffff;
      --band: #f5f7f9;
      --green: #1f7a4d;
      --red: #b13b3b;
      --blue: #245f91;
      --amber: #9a6a12;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--band);
    }
    header {
      background: #17202c;
      color: white;
      padding: 22px clamp(16px, 4vw, 44px);
      border-bottom: 4px solid #d5aa44;
    }
    header h1 {
      margin: 0 0 8px;
      font-size: clamp(1.6rem, 3vw, 2.4rem);
      line-height: 1.08;
      letter-spacing: 0;
    }
    header p {
      max-width: 980px;
      margin: 0;
      color: #dbe3ec;
      font-size: 1rem;
      line-height: 1.5;
    }
    main {
      width: min(1180px, calc(100% - 28px));
      margin: 18px auto 40px;
    }
    .toolbar {
      display: grid;
      grid-template-columns: 1fr auto auto auto;
      gap: 10px;
      align-items: center;
      margin-bottom: 14px;
    }
    input, select, button {
      min-height: 40px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: white;
      color: var(--ink);
      font: inherit;
    }
    input, select { padding: 0 12px; }
    .sort-note {
      color: var(--muted);
      font-size: .9rem;
      white-space: nowrap;
    }
    button {
      cursor: pointer;
      padding: 0 14px;
      font-weight: 650;
    }
    button.selected {
      background: #d5aa44;
      border-color: #b98b1d;
      color: #17202c;
    }
    button.primary {
      background: #245f91;
      border-color: #245f91;
      color: white;
    }
    .summary {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 18px;
    }
    .metric {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      min-height: 86px;
    }
    .metric span {
      display: block;
      color: var(--muted);
      font-size: .82rem;
      margin-bottom: 8px;
    }
    .metric strong {
      display: block;
      font-size: 1.65rem;
      line-height: 1;
    }
    .layout {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 330px;
      gap: 16px;
      align-items: start;
    }
    .feed {
      display: grid;
      gap: 10px;
    }
    .signal {
      background: var(--surface);
      border: 1px solid var(--line);
      border-left: 6px solid #8894a5;
      border-radius: 8px;
      padding: 15px;
    }
    .signal.action { border-left-color: var(--green); }
    .signal.risk { border-left-color: var(--red); }
    .signal.no-action { border-left-color: var(--muted); }
    .signal h2 {
      margin: 0 0 8px;
      font-size: 1.05rem;
      line-height: 1.35;
      letter-spacing: 0;
    }
    .meta, .chips, .trade-row {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      align-items: center;
    }
    .meta {
      color: var(--muted);
      font-size: .86rem;
      margin-bottom: 10px;
    }
    .chip {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 9px;
      background: #f8fafc;
      font-size: .82rem;
      line-height: 1.2;
    }
    .chip.relevant { border-color: #9bc7ae; color: var(--green); }
    .chip.negative { border-color: #e3a7a7; color: var(--red); }
    .chip.positive { border-color: #91bba4; color: var(--green); }
    .chip.neutral { border-color: #b7c2d1; color: var(--blue); }
    .explanation {
      color: #313946;
      line-height: 1.5;
      margin: 10px 0 12px;
    }
    .trade-row button {
      min-height: 34px;
      padding: 0 10px;
      font-size: .86rem;
    }
    aside {
      display: grid;
      gap: 12px;
    }
    .panel {
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }
    .panel h2 {
      margin: 0 0 12px;
      font-size: 1rem;
      letter-spacing: 0;
    }
    .holding, .category-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      padding: 8px 0;
      border-top: 1px solid #eef1f5;
      font-size: .92rem;
    }
    .holding span {
      min-width: 0;
      overflow-wrap: anywhere;
    }
    .holding-actions {
      display: flex;
      align-items: center;
      gap: 8px;
      flex: 0 0 auto;
    }
    .remove-trade {
      min-height: 28px;
      padding: 0 8px;
      color: #b13b3b;
      border-color: #e3a7a7;
      background: #fff8f8;
      font-size: .78rem;
    }
    .status {
      color: var(--muted);
      font-size: .9rem;
      min-height: 22px;
      margin: 8px 0 0;
    }
    a { color: #245f91; }
    @media (max-width: 860px) {
      .toolbar, .summary, .layout {
        grid-template-columns: 1fr;
      }
      .toolbar button, .toolbar select { width: 100%; }
      .sort-note { white-space: normal; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Political News AI Dashboard</h1>
    <p>Live RSS classifications, cautious guardrail outcomes, and local paper-trading decisions for evaluating how the system reacts to political news.</p>
  </header>
  <main>
    <section class="toolbar" aria-label="Dashboard controls">
      <input id="search" type="search" placeholder="Search headlines, categories, explanations">
      <select id="filter">
        <option value="all">All signals</option>
        <option value="action">Paper-trade actions</option>
        <option value="no-action">No action outcomes</option>
        <option value="relevant">Market relevant</option>
      </select>
      <button id="refresh" class="primary">Refresh Feeds</button>
      <button id="reload">Reload CSV</button>
      <span class="sort-note">Newest first</span>
    </section>
    <section class="summary" id="summary"></section>
    <section class="layout">
      <div class="feed" id="feed"></div>
      <aside>
        <section class="panel">
          <h2>Paper Portfolio</h2>
          <div id="portfolio"></div>
        </section>
        <section class="panel">
          <h2>Evaluation Snapshot</h2>
          <div id="evaluation"></div>
          <p class="status" id="status"></p>
        </section>
      </aside>
    </section>
  </main>
  <script>
    const state = { rows: [], summary: {}, trades: JSON.parse(localStorage.getItem("paperTrades") || "[]") };
    const tradeChoices = ["BULLISH EQUITIES", "BEARISH BONDS", "RISK OFF", "WATCH"];
    const tradeLabels = {
      "BULLISH EQUITIES": "Bullish Equities",
      "BEARISH BONDS": "Bearish Bonds",
      "RISK OFF": "Risk Off",
      "WATCH": "Watch"
    };
    const legacyTradeMap = {
      "BUY": "BULLISH EQUITIES",
      "SELL": "BEARISH BONDS"
    };
    const feed = document.getElementById("feed");
    const statusEl = document.getElementById("status");

    function escapeHtml(value) {
      return String(value || "").replace(/[&<>"']/g, char => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
      }[char]));
    }

    function signalClass(row) {
      const action = row.Action || "";
      if (action.startsWith("RISK")) return "risk";
      if (action.startsWith("BUY") || action.startsWith("SELL")) return "action";
      return "no-action";
    }

    function rowId(row) {
      return btoa(unescape(encodeURIComponent(`${row.Time}|${row.Headline}`))).replace(/=+$/, "");
    }

    function selectedTradeFor(id) {
      return state.trades.find(trade => trade.id === id);
    }

    function migrateStoredTrades() {
      let changed = false;
      state.trades = state.trades.map(trade => {
        const mappedChoice = legacyTradeMap[trade.choice] || trade.choice;
        if (mappedChoice !== trade.choice) {
          changed = true;
          trade = { ...trade, choice: mappedChoice };
        }
        if (trade.id) return trade;
        const row = state.rows.find(item => item.Headline === trade.headline);
        if (!row) return trade;
        changed = true;
        return { ...trade, id: rowId(row) };
      });

      const byId = new Map();
      const withoutId = [];
      state.trades.forEach(trade => {
        if (!trade.id) {
          withoutId.push(trade);
          return;
        }
        byId.set(trade.id, trade);
      });

      const migrated = [...withoutId, ...byId.values()];
      if (changed || migrated.length !== state.trades.length) {
        state.trades = migrated;
        localStorage.setItem("paperTrades", JSON.stringify(state.trades));
      }
    }

    function renderSummary() {
      const s = state.summary;
      document.getElementById("summary").innerHTML = [
        ["Signals", s.total || 0],
        ["Paper Actions", s.actions || 0],
        ["No Action Rate", `${s.noActionRate || 0}%`],
        ["Avg Confidence", s.avgConfidence || 0],
        ["High-Conf Actions", s.highConfidenceActions || 0],
      ].map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`).join("");
    }

    function renderFeed() {
      const query = document.getElementById("search").value.toLowerCase();
      const filter = document.getElementById("filter").value;
      const rows = state.rows.filter(row => {
        const haystack = Object.values(row).join(" ").toLowerCase();
        const matchesQuery = !query || haystack.includes(query);
        const cls = signalClass(row);
        const matchesFilter =
          filter === "all" ||
          (filter === "action" && cls !== "no-action") ||
          (filter === "no-action" && cls === "no-action") ||
          (filter === "relevant" && String(row.MarketRelevant).toLowerCase() === "yes");
        return matchesQuery && matchesFilter;
      });

      feed.innerHTML = rows.map(row => {
        const id = rowId(row);
        const link = row.Link ? `<a href="${escapeHtml(row.Link)}" target="_blank" rel="noreferrer">Open source</a>` : "No link";
        return `<article class="signal ${signalClass(row)}">
          <h2>${escapeHtml(row.Headline)}</h2>
          <div class="meta">
            <span>${escapeHtml(row.Source || "Unknown source")}</span>
            <span>${escapeHtml(row.Published || row.Time || "")}</span>
            <span>${link}</span>
          </div>
          <div class="chips">
            <span class="chip relevant">${escapeHtml(row.MarketRelevant || "Unknown relevance")}</span>
            <span class="chip">${escapeHtml(row.Category || "Uncategorized")}</span>
            <span class="chip ${String(row.Sentiment || "").toLowerCase()}">${escapeHtml(row.Sentiment || "Unknown")}</span>
            <span class="chip">${escapeHtml(row.Confidence || "0")} confidence</span>
            <span class="chip">${escapeHtml(row.Action || "NO ACTION")}</span>
          </div>
          <p class="explanation">${escapeHtml(row.Explanation)}</p>
          <div class="trade-row">
            ${tradeChoices.map(choice => {
              const selected = selectedTradeFor(id)?.choice === choice ? " selected" : "";
              return `<button class="${selected}" data-trade="${choice}" data-id="${id}">${tradeLabels[choice]}</button>`;
            }).join("")}
          </div>
        </article>`;
      }).join("") || `<section class="panel"><h2>No matching signals</h2><p class="status">Run the bot or change the filters.</p></section>`;
    }

    function renderPortfolio() {
      const counts = state.trades.reduce((acc, trade) => {
        const label = tradeLabels[trade.choice] || trade.choice;
        acc[label] = (acc[label] || 0) + 1;
        return acc;
      }, {});
      const latest = state.trades
        .map((trade, index) => ({ ...trade, index }))
        .slice(-6)
        .reverse();
      document.getElementById("portfolio").innerHTML =
        Object.keys(counts).length
          ? Object.entries(counts).map(([key, value]) => `<div class="holding"><span>${key}</span><strong>${value}</strong></div>`).join("")
          : `<p class="status">No paper decisions recorded in this browser.</p>`;
      document.getElementById("portfolio").innerHTML += latest.map(trade =>
        `<div class="holding">
          <span>${escapeHtml(trade.headline)}</span>
          <div class="holding-actions">
            <strong>${tradeLabels[trade.choice] || trade.choice}</strong>
            <button class="remove-trade" data-remove-index="${trade.index}">Remove</button>
          </div>
        </div>`
      ).join("");
    }

    function renderEvaluation() {
      const categories = state.summary.byCategory || {};
      const rows = Object.entries(categories).sort((a, b) => b[1] - a[1]);
      document.getElementById("evaluation").innerHTML = rows.map(([name, count]) =>
        `<div class="category-row"><span>${escapeHtml(name)}</span><strong>${count}</strong></div>`
      ).join("") || `<p class="status">No classification data yet.</p>`;
      statusEl.textContent = `Reading ${state.summary.logFile || "signals_log.csv"}; updated ${state.summary.updatedAt || ""}`;
    }

    async function loadData() {
      const response = await fetch("/api/signals");
      const data = await response.json();
      state.rows = data.rows;
      state.summary = data.summary;
      migrateStoredTrades();
      renderSummary();
      renderFeed();
      renderPortfolio();
      renderEvaluation();
    }

    document.getElementById("search").addEventListener("input", renderFeed);
    document.getElementById("filter").addEventListener("change", renderFeed);
    document.getElementById("reload").addEventListener("click", loadData);
    document.getElementById("refresh").addEventListener("click", async () => {
      statusEl.textContent = "Refreshing RSS feeds and classifications...";
      const response = await fetch("/api/refresh", { method: "POST" });
      const result = await response.json();
      statusEl.textContent = result.returnCode === 0 ? "Feed refresh complete." : "Feed refresh returned an error. Check terminal output.";
      await loadData();
    });
    feed.addEventListener("click", event => {
      const button = event.target.closest("button[data-trade]");
      if (!button) return;
      const row = state.rows.find(item => rowId(item) === button.dataset.id);
      state.trades = state.trades.filter(trade => trade.id !== button.dataset.id);
      state.trades.push({
        id: button.dataset.id,
        choice: button.dataset.trade,
        headline: row ? row.Headline : "Unknown headline",
        time: new Date().toISOString()
      });
      localStorage.setItem("paperTrades", JSON.stringify(state.trades));
      renderFeed();
      renderPortfolio();
    });
    document.getElementById("portfolio").addEventListener("click", event => {
      const button = event.target.closest("button[data-remove-index]");
      if (!button) return;
      const removeIndex = Number(button.dataset.removeIndex);
      state.trades = state.trades.filter((trade, index) => index !== removeIndex);
      localStorage.setItem("paperTrades", JSON.stringify(state.trades));
      renderFeed();
      renderPortfolio();
    });

    loadData();
    setInterval(loadData, 30000);
  </script>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/signals":
            rows = read_signals()
            self.send_json({"rows": rows, "summary": build_summary(rows)})
            return
        self.send_json({"error": "Not found"}, status=404)

    def do_HEAD(self):
        path = urlparse(self.path).path
        if path == "/":
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return
        if path == "/api/signals":
            rows = read_signals()
            body = json.dumps({"rows": rows, "summary": build_summary(rows)}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return
        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/refresh":
            self.send_json(run_refresh())
            return
        self.send_json({"error": "Not found"}, status=404)

    def log_message(self, format, *args):
        return


def main():
    parser = argparse.ArgumentParser(description="Run the Political News AI dashboard.")
    parser.add_argument("--host", default=HOST, help="Host/interface to bind")
    parser.add_argument("--port", type=int, default=PORT, help="Port to bind")
    args = parser.parse_args()

    HTTPServer.allow_reuse_address = True
    server = None
    selected_port = args.port
    for candidate_port in range(args.port, args.port + 50):
        try:
            server = HTTPServer((args.host, candidate_port), DashboardHandler)
            selected_port = candidate_port
            break
        except OSError as e:
            if getattr(e, "errno", None) != 48:
                raise

    if server is None:
        raise OSError(f"No open port found from {args.port} to {args.port + 49}.")

    if selected_port != args.port:
        print(f"Port {args.port} was busy; using {selected_port} instead.")
    print(f"Dashboard running at http://{args.host}:{selected_port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")


if __name__ == "__main__":
    main()
