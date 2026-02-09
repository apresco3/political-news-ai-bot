import feedparser
import pandas as pd
import os
import time
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime

# -------------------------
# SETUP
# -------------------------

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

RSS_FEEDS = {
    "Reuters Politics": "https://www.reuters.com/rssFeed/politicsNews"
}

CONFIDENCE_THRESHOLD = 70
LOG_FILE = "signals_log.csv"

seen_headlines = set()

# -------------------------
# AI CLASSIFICATION
# -------------------------

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

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    return response.choices[0].message.content


# -------------------------
# PARSE AI RESPONSE
# -------------------------

def parse_ai_response(text):
    data = {}
    for line in text.split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
    return data


# -------------------------
# TRADING LOGIC (PAPER ONLY)
# -------------------------

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


# -------------------------
# LOGGING
# -------------------------

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


# -------------------------
# MAIN LOOP
# -------------------------

def run_bot():
    print("Starting Political News AI Bot...")
    print("Checking for new headlines...\n")

    for source, url in RSS_FEEDS.items():
        feed = feedparser.parse(url)

        for entry in feed.entries[:5]:
            headline = entry.title

            if headline in seen_headlines:
                continue

            seen_headlines.add(headline)

            print(f"\nNEW HEADLINE ({source}):")
            print(headline)

            ai_text = classify_headline(headline)
            ai_data = parse_ai_response(ai_text)

            action = decide_action(ai_data)

            print("\nAI ANALYSIS:")
            for k, v in ai_data.items():
                print(f"{k}: {v}")

            print(f"\nFINAL DECISION: {action}")

            log_signal(headline, ai_data, action)

            time.sleep(2)  # polite delay to API

    print("\nRun complete.\n")


# -------------------------
# RUN
# -------------------------

if __name__ == "__main__":
    run_bot()
