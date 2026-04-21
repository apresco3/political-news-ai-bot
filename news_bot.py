import feedparser
import pandas as pd
import os
import time
import argparse
import calendar
import csv
import email.utils
import re
import urllib.request
import shutil
from urllib.parse import urlparse, quote
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key and OpenAI else None

RSS_FEEDS = {
    "Reuters Politics (Google News)": (
        "https://news.google.com/rss/search?"
        "q=site:reuters.com+politics&hl=en-US&gl=US&ceid=US:en"
    ),
    "AP Politics (Google News)": (
        "https://news.google.com/rss/search?"
        "q=site:apnews.com+politics&hl=en-US&gl=US&ceid=US:en"
    ),
    "Federal Reserve - All Press Releases": "https://www.federalreserve.gov/feeds/press_all.xml",
    "Federal Reserve - Monetary Policy": "https://www.federalreserve.gov/feeds/press_monetary.xml",
    "SEC Press Releases": "https://www.sec.gov/news/pressreleases.rss",
    "Treasury Press Releases (Google News)": (
        "https://news.google.com/rss/search?"
        "q=site:home.treasury.gov/news/press-releases&hl=en-US&gl=US&ceid=US:en"
    ),
    "White House Actions (Google News)": (
        "https://news.google.com/rss/search?"
        "q=site:whitehouse.gov/presidential-actions&hl=en-US&gl=US&ceid=US:en"
    ),
    "USTR Trade Policy (Google News)": (
        "https://news.google.com/rss/search?"
        "q=site:ustr.gov+press+release+trade&hl=en-US&gl=US&ceid=US:en"
    ),
    "NPR Politics": "https://feeds.npr.org/1014/rss.xml",
    "NPR Economy": "https://feeds.npr.org/1006/rss.xml",
    "Politico White House": "https://rss.politico.com/white-house.xml",
    "Politico Defense": "https://rss.politico.com/defense.xml",
    "Politico Energy": "https://rss.politico.com/energy.xml",
    "CNBC Politics": "https://www.cnbc.com/id/10000113/device/rss/rss.html",
    "CNBC Economy": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "BBC World": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "BBC Business": "https://feeds.bbci.co.uk/news/business/rss.xml",
    "Al Jazeera News": "https://www.aljazeera.com/xml/rss/all.xml",
    "Guardian US Politics": "https://www.theguardian.com/us-news/us-politics/rss",
    "Guardian World": "https://www.theguardian.com/world/rss",
    "NYT DealBook": "https://rss.nytimes.com/services/xml/rss/nyt/Dealbook.xml",
    "NYT Business": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"
}

CONFIDENCE_THRESHOLD = 70
LOG_FILE = "signals_log.csv"
SEEN_FILE = "seen_headlines.txt"
EASTERN = timezone(timedelta(hours=-5), "ET")
TIME_FORMAT = "%Y-%m-%d %H:%M:%S ET"
LOG_COLUMNS = [
    "Time",
    "Published",
    "Source",
    "Headline",
    "Link",
    "MarketRelevant",
    "Category",
    "Sentiment",
    "Confidence",
    "Action",
    "Explanation"
]

def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for h in sorted(seen):
            f.write(h.replace("\n", " ").strip() + "\n")

seen_headlines = load_seen()

def classify_headline(headline):
    prompt = f"""
You are classifying political news for market relevance.

Headline:
"{headline}"

Rules:
- Be cautious. If the headline is vague, local-only, personality-driven, or lacks a clear market channel, mark it not market relevant or assign low confidence.
- Do not force a paper-trading signal from weak political news.
- Prefer "No" and lower confidence when there is no clear impact on rates, fiscal policy, regulation, trade, sanctions, conflict, energy, or broad risk sentiment.

Return your answer in EXACTLY this format:
MarketRelevant: Yes or No
Category: MonetaryPolicy, FiscalPolicy, Regulation, Geopolitics, Other
Sentiment: Positive, Negative, Neutral
Confidence: 0-100
Explanation: One sentence explanation
"""

    if not client:
        print("OPENAI_API_KEY not configured; using local heuristic classifier.")
        return classify_headline_locally(headline)

    try:
        print("Sending OpenAI request...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        print("OpenAI response model:", response.model)
        return response.choices[0].message.content
    except Exception as e:
        print(f"[OpenAI ERROR] {e}")
        print("Falling back to local heuristic classifier.")
        return classify_headline_locally(headline)

def classify_headline_locally(headline):
    """Small deterministic fallback so the project can run as an MVP without API access."""
    text = headline.lower()

    category_rules = [
        ("MonetaryPolicy", ["fed", "federal reserve", "interest rate", "inflation", "cpi", "jobs report", "treasury", "bond", "yield"]),
        ("FiscalPolicy", ["budget", "tax", "tariff", "spending", "stimulus", "debt ceiling", "shutdown", "deficit"]),
        ("Regulation", ["regulation", "regulator", "antitrust", "sec", "ftc", "doj", "bank rule", "crypto", "ai rule"]),
        ("Geopolitics", ["war", "sanction", "iran", "china", "russia", "ukraine", "taiwan", "oil", "opec", "missile", "border"]),
    ]
    negative_words = ["war", "sanction", "tariff", "shutdown", "conflict", "probe", "ban", "crackdown", "inflation", "missile", "default"]
    positive_words = ["deal", "ceasefire", "cuts taxes", "tax cut", "stimulus", "agreement", "eases", "growth", "approves"]

    category = "Other"
    matched_terms = []
    for candidate, terms in category_rules:
        matched_terms = [term for term in terms if term in text]
        if matched_terms:
            category = candidate
            break

    if any(word in text for word in negative_words):
        sentiment = "Negative"
    elif any(word in text for word in positive_words):
        sentiment = "Positive"
    else:
        sentiment = "Neutral"

    if category == "Other":
        relevant = "No"
        confidence = 35
        explanation = "No clear market transmission channel was detected, so the safe interpretation is no action."
    elif sentiment == "Neutral":
        relevant = "Yes"
        confidence = 60
        explanation = f"The headline mentions {category} but does not give a clear positive or negative market direction."
    else:
        relevant = "Yes"
        confidence = 75
        explanation = f"The headline contains {category} terms that may affect market expectations, but this remains a cautious paper signal."

    return "\n".join([
        f"MarketRelevant: {relevant}",
        f"Category: {category}",
        f"Sentiment: {sentiment}",
        f"Confidence: {confidence}",
        f"Explanation: {explanation}",
    ])

def parse_ai_response(text):
    data = {}
    for line in text.split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
    return data

def decide_action(ai_data):
    try:
        confidence = int(ai_data.get("Confidence", 0))
        relevant = ai_data.get("MarketRelevant", "No").strip().lower()

        if relevant != "yes":
            return "NO ACTION (Not market relevant)"

        if confidence < CONFIDENCE_THRESHOLD:
            return "NO ACTION (Low confidence)"

        category = ai_data.get("Category")
        sentiment = ai_data.get("Sentiment")

        if category == "MonetaryPolicy" and sentiment == "Negative":
            return "SELL BONDS (Paper Trade)"

        if category == "FiscalPolicy" and sentiment == "Positive":
            return "BUY EQUITIES (Paper Trade)"

        if category == "Geopolitics" and sentiment == "Negative":
            return "RISK OFF (Paper Trade)"

        return "NO ACTION (Rule mismatch)"

    except Exception as e:
        return f"NO ACTION (Error: {e})"

def log_signal(headline, link, published, source, ai_data, action):
    row = {
        "Time": format_eastern(datetime.now(EASTERN)),
        "Published": published,
        "Source": source,
        "Headline": headline,
        "Link": link,
        "MarketRelevant": ai_data.get("MarketRelevant"),
        "Category": ai_data.get("Category"),
        "Sentiment": ai_data.get("Sentiment"),
        "Confidence": ai_data.get("Confidence"),
        "Action": action,
        "Explanation": ai_data.get("Explanation")
    }

    df_new = pd.DataFrame([row]).reindex(columns=LOG_COLUMNS)

    if os.path.exists(LOG_FILE):
        try:
            df_old = pd.read_csv(LOG_FILE)
        except Exception:
            df_old = pd.DataFrame(columns=LOG_COLUMNS)
    else:
        df_old = pd.DataFrame(columns=LOG_COLUMNS)

    for col in LOG_COLUMNS:
        if col not in df_old.columns:
            df_old[col] = ""
    df_old = df_old[LOG_COLUMNS]

    df_all = pd.concat([df_old, df_new], ignore_index=True)
    if os.path.exists(LOG_FILE):
        shutil.copyfile(LOG_FILE, f"{LOG_FILE}.bak")
    df_all.to_csv(LOG_FILE, index=False, quoting=csv.QUOTE_ALL)

def format_published(entry):
    published = getattr(entry, "published", "") or getattr(entry, "updated", "")
    published_parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if published_parsed:
        try:
            published_utc = datetime.fromtimestamp(calendar.timegm(published_parsed), tz=timezone.utc)
            return format_eastern(published_utc)
        except Exception:
            pass
    if published:
        try:
            parsed = email.utils.parsedate_to_datetime(published)
            return format_eastern(parsed)
        except Exception:
            pass
    return published or ""

def format_eastern(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=EASTERN)
    return value.astimezone(EASTERN).strftime(TIME_FORMAT)

def parse_feed(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
        return feedparser.parse(data)
    except Exception:
        return feedparser.parse(url)

def resolve_final_url(url):
    if not url:
        return ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.geturl()
    except Exception:
        return url

def source_from_url(url):
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return ""
    if "reuters.com" in host:
        return "Reuters"
    if "nytimes.com" in host:
        return "NYT"
    if "apnews.com" in host:
        return "AP News"
    if "npr.org" in host:
        return "NPR"
    if "politico.com" in host:
        return "Politico"
    if "cnbc.com" in host:
        return "CNBC"
    if "federalreserve.gov" in host:
        return "Federal Reserve"
    if "sec.gov" in host:
        return "SEC"
    if "treasury.gov" in host:
        return "Treasury"
    if "whitehouse.gov" in host:
        return "White House"
    if "ustr.gov" in host:
        return "USTR"
    if "bbc.co.uk" in host or "bbc.com" in host:
        return "BBC"
    if "aljazeera.com" in host:
        return "Al Jazeera"
    if "theguardian.com" in host:
        return "The Guardian"
    if host:
        return host.replace("www.", "")
    return ""

def entry_source_name(entry, fallback_source, link):
    entry_source = getattr(entry, "source", None)
    if entry_source and getattr(entry_source, "title", ""):
        return entry_source.title
    inferred = source_from_url(link)
    return inferred or fallback_source

def run_bot(max_entries=5):
    print("Starting Political News AI Bot...")
    print("Checking for new headlines...\n")
    processed = 0

    for source, url in RSS_FEEDS.items():
        print(f"Fetching feed: {source}")
        feed = parse_feed(url)

        # Diagnostics so you can see what's happening
        status = getattr(feed, "status", "unknown")
        bozo = getattr(feed, "bozo", False)
        entries_count = len(feed.entries)

        print(f"[Feed status] status={status} entries={entries_count} bozo={bozo}")

        if bozo:
            print("bozo_exception:", getattr(feed, "bozo_exception", None))

        if entries_count == 0:
            print("No headlines found for this feed.\n")
            continue

        for entry in feed.entries[:max_entries]:
            headline = entry.title.strip()
            dedupe_key = normalize_headline(headline)

            if not dedupe_key:
                continue

            if headline in seen_headlines or dedupe_key in seen_headlines:
                continue

            seen_headlines.add(dedupe_key)

            print(f"\nNEW HEADLINE ({source}):")
            print(headline)

            ai_text = classify_headline(headline)
            if not ai_text:
                print("AI classification failed.")
                continue

            ai_data = parse_ai_response(ai_text)
            action = decide_action(ai_data)

            print("\nAI ANALYSIS:")
            for k, v in ai_data.items():
                print(f"{k}: {v}")

            print(f"\nFINAL DECISION: {action}")

            link = getattr(entry, "link", "")
            published = format_published(entry)
            source_name = entry_source_name(entry, source, link)
            log_signal(headline, link, published, source_name, ai_data, action)
            processed += 1

            time.sleep(2)

    save_seen(seen_headlines)
    print(f"\nRun complete. Processed {processed} new headlines.\n")
    return processed

def run_loop(interval_seconds=300, max_entries=5):
    print(f"Loop mode enabled. Checking feeds every {interval_seconds} seconds.")
    while True:
        run_bot(max_entries=max_entries)
        print(f"Sleeping for {interval_seconds} seconds. Press Ctrl+C to stop.")
        time.sleep(interval_seconds)

def normalize_headline(text):
    t = (text or "").lower()
    t = re.sub(
        r"\s+[-|]\s+(reuters|ap news|associated press|nyt|new york times|politico|npr|cnbc)\s*$",
        "",
        t,
    )
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def fetch_reuters_link_from_google(headline):
    query = quote(f'{headline} site:reuters.com')
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    feed = parse_feed(url)
    if not feed.entries:
        return ""
    entry = feed.entries[0]
    raw_link = getattr(entry, "link", "")
    if not raw_link:
        return ""
    try:
        req = urllib.request.Request(raw_link, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            final_url = resp.geturl()
        if "reuters.com" in final_url:
            return final_url
    except Exception:
        pass
    return raw_link

def migrate_links(max_rows=100):
    if not os.path.exists(LOG_FILE):
        print("No signals_log.csv found.")
        return
    try:
        df = pd.read_csv(LOG_FILE)
    except Exception as e:
        print(f"Failed to read log: {e}")
        return
    if df.empty:
        print("Log is empty.")
        return
    if "Link" not in df.columns:
        df["Link"] = ""
    updated = 0
    for idx, row in df.iterrows():
        if updated >= max_rows:
            break
        link = str(row.get("Link", "")).strip()
        if link:
            continue
        headline = str(row.get("Headline", "")).strip()
        if not headline:
            continue
        resolved = fetch_reuters_link_from_google(headline)
        if resolved:
            df.at[idx, "Link"] = resolved
            updated += 1
    if updated:
        if os.path.exists(LOG_FILE):
            shutil.copyfile(LOG_FILE, f"{LOG_FILE}.bak")
        df.to_csv(LOG_FILE, index=False, quoting=csv.QUOTE_ALL)
    print(f"Link migration complete. Updated {updated} rows.")

def fetch_meta_from_google(headline):
    query = quote(f'"{headline}"')
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    feed = parse_feed(url)
    if not feed.entries:
        return {}
    entry = feed.entries[0]
    raw_link = getattr(entry, "link", "")
    final_link = resolve_final_url(raw_link)
    published = format_published(entry)
    source = ""
    entry_source = getattr(entry, "source", None)
    if entry_source and getattr(entry_source, "title", ""):
        source = entry_source.title
    if not source:
        source = source_from_url(final_link)
    return {
        "Link": final_link or raw_link,
        "Published": published,
        "Source": source
    }

def migrate_metadata(max_rows=100, sleep_seconds=0.5):
    if not os.path.exists(LOG_FILE):
        print("No signals_log.csv found.")
        return
    try:
        df = pd.read_csv(LOG_FILE)
    except Exception as e:
        print(f"Failed to read log: {e}")
        return
    if df.empty:
        print("Log is empty.")
        return
    if "Link" not in df.columns:
        df["Link"] = ""
    if "Published" not in df.columns:
        df["Published"] = ""
    if "Source" not in df.columns:
        df["Source"] = ""

    updated = 0
    for idx, row in df.iterrows():
        if updated >= max_rows:
            break
        link = str(row.get("Link", "")).strip()
        published = str(row.get("Published", "")).strip()
        source = str(row.get("Source", "")).strip()
        if link and published and source:
            continue
        headline = str(row.get("Headline", "")).strip()
        if not headline:
            continue
        meta = fetch_meta_from_google(headline)
        if not meta:
            continue
        if not link and meta.get("Link"):
            df.at[idx, "Link"] = meta["Link"]
        if not published and meta.get("Published"):
            df.at[idx, "Published"] = meta["Published"]
        if not source and meta.get("Source"):
            df.at[idx, "Source"] = meta["Source"]
        updated += 1
        time.sleep(sleep_seconds)

    if updated:
        if os.path.exists(LOG_FILE):
            shutil.copyfile(LOG_FILE, f"{LOG_FILE}.bak")
        df.to_csv(LOG_FILE, index=False, quoting=csv.QUOTE_ALL)
    print(f"Metadata migration complete. Updated {updated} rows.")

def reset_log():
    df = pd.DataFrame(columns=LOG_COLUMNS)
    if os.path.exists(LOG_FILE):
        shutil.copyfile(LOG_FILE, f"{LOG_FILE}.bak")
    df.to_csv(LOG_FILE, index=False, quoting=csv.QUOTE_ALL)
    print("signals_log.csv reset with headers.")

def reset_seen():
    if os.path.exists(SEEN_FILE):
        shutil.copyfile(SEEN_FILE, f"{SEEN_FILE}.bak")
        os.remove(SEEN_FILE)
    print("seen_headlines.txt reset.")

def main():
    parser = argparse.ArgumentParser(description="Political News Bot")
    parser.add_argument("--migrate-links", action="store_true", help="Backfill missing links in signals_log.csv")
    parser.add_argument("--migrate-meta", action="store_true", help="Backfill missing links/published/source in signals_log.csv")
    parser.add_argument("--reset-log", action="store_true", help="Reset signals_log.csv (backs up first)")
    parser.add_argument("--reset-seen", action="store_true", help="Reset seen_headlines.txt (backs up first)")
    parser.add_argument("--loop", action="store_true", help="Continuously poll RSS feeds")
    parser.add_argument("--interval", type=int, default=300, help="Seconds between loop runs")
    parser.add_argument("--max-entries", type=int, default=5, help="Max entries to inspect per feed")
    args = parser.parse_args()

    if args.reset_seen:
        reset_seen()
    elif args.reset_log:
        reset_log()
    elif args.migrate_meta:
        migrate_metadata()
    elif args.migrate_links:
        migrate_links()
    elif args.loop:
        run_loop(interval_seconds=args.interval, max_entries=args.max_entries)
    else:
        run_bot(max_entries=args.max_entries)


if __name__ == "__main__":
    main()
