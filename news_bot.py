import feedparser
import pandas as pd
import os
import time
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("Missing OPENAI_API_KEY in .env")

client = OpenAI(api_key=api_key)

# Use Google News RSS to reliably get Reuters politics headlines
RSS_FEEDS = {
    "Reuters Politics (via Google News)": (
        "https://news.google.com/rss/search?"
        "q=site:reuters.com+politics&hl=en-US&gl=US&ceid=US:en"
    )
}

CONFIDENCE_THRESHOLD = 70
LOG_FILE = "signals_log.csv"
SEEN_FILE = "seen_headlines.txt"

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

Return your answer in EXACTLY this format:
MarketRelevant: Yes or No
Category: MonetaryPolicy, FiscalPolicy, Regulation, Geopolitics, Other
Sentiment: Positive, Negative, Neutral
Confidence: 0-100
Explanation: One sentence explanation
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[OpenAI ERROR] {e}")
        return ""

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
        relevant = ai_data.get("MarketRelevant", "No")

        if relevant != "Yes":
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

def log_signal(headline, ai_data, action):
    row = {
        "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Headline": headline,
        "MarketRelevant": ai_data.get("MarketRelevant"),
        "Category": ai_data.get("Category"),
        "Sentiment": ai_data.get("Sentiment"),
        "Confidence": ai_data.get("Confidence"),
        "Action": action,
        "Explanation": ai_data.get("Explanation")
    }

    df = pd.DataFrame([row])

    if not os.path.exists(LOG_FILE):
        df.to_csv(LOG_FILE, index=False)
    else:
        df.to_csv(LOG_FILE, mode="a", header=False, index=False)

def run_bot():
    print("Starting Political News AI Bot...")
    print("Checking for new headlines...\n")

    for source, url in RSS_FEEDS.items():
        print(f"Fetching feed: {source}")
        feed = feedparser.parse(url)

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

        for entry in feed.entries[:5]:
            headline = entry.title.strip()

            if headline in seen_headlines:
                continue

            seen_headlines.add(headline)

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

            log_signal(headline, ai_data, action)

            time.sleep(2)

    save_seen(seen_headlines)
    print("\nRun complete.\n")


if __name__ == "__main__":
    run_bot()
