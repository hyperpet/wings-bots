#!/usr/bin/env python3
"""
Wings — X (Twitter) Auto-Poster
Follows strictly: Instrucciones_Bot_Crypto_Twitter_FINAL.md
Scheduling is handled by main.py — this script just posts one tweet when called.
"""

import os
import json
import random
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import pytz
import tweepy
from openai import OpenAI

# ─── Logging ──────────────────────────────────────────────────────────────────
logger = logging.getLogger("wings.x")

# ─── Configuration ────────────────────────────────────────────────────────────
API_KEY             = os.environ.get("X_API_KEY", "tMkqzeKXyiqThV8relqr4Xa1h")
API_KEY_SECRET      = os.environ.get("X_API_KEY_SECRET", "Wchkdy8E2unkyzHNautGHbRWPiWJLqA3eUM5t8RqRZeaIGp8z8")
ACCESS_TOKEN        = os.environ.get("X_ACCESS_TOKEN", "2033548838124851200-LPpTaWOvxII1qjcVFi8EHQcNluZlSq")
ACCESS_TOKEN_SECRET = os.environ.get("X_ACCESS_TOKEN_SECRET", "t6p4XvsiLP6k9ZCEHlSBac0LsNeVDxPSC4b2vMS91uzT2")

BOT_TOKEN        = os.environ.get("TELEGRAM_BOT_TOKEN", "8203101684:AAE_RAR7CBhFy-N1CkVha1fF3vwfMf6nE8U")
TELEGRAM_CHANNEL = "@wingsscalls"

DATA_DIR   = os.environ.get("DATA_DIR", "/app/data")
STATE_FILE = os.path.join(DATA_DIR, "x_state.json")

EST = pytz.timezone("America/New_York")

# ─── State (narrative continuity) ─────────────────────────────────────────────
DEFAULT_STATE = {
    "ecosystem": "Solana",
    "conviction_tokens": ["$SOL", "$BRETT"],
    "btc_stance": "respects $BTC as store of value but heart is in altcoins",
    "entry_year": "2020",
    "biggest_mistake": "sold too early in the last cycle",
    "biggest_win": "held $SOL through the bear and multiplied capital significantly",
    "recent_tweets": [],
    "declared_positions": ["accumulating $SOL", "watching $BRETT"],
    "crosspost_counter": 0,
}

def load_state():
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_STATE.copy()

def save_state(state):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# ─── News Fetcher ─────────────────────────────────────────────────────────────
def fetch_crypto_news():
    feeds = [
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://cointelegraph.com/rss",
    ]
    headlines = []
    for url in feeds:
        try:
            r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:5]:
                title = item.findtext("title", "").strip()
                if title:
                    headlines.append(title)
            if headlines:
                logger.info(f"News fetched from {url}")
                break
        except Exception as e:
            logger.warning(f"News fetch failed ({url}): {e}")
    if not headlines:
        headlines = [
            "Bitcoin trading near key resistance levels",
            "Altcoin season speculation grows in crypto community",
            "DeFi protocols see increased activity",
        ]
    return headlines[:6]

# ─── Tweet Generator ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """you are a veteran crypto twitter operator with 150k+ followers. you've been in the market since 2020, survived a full bear market, and have real positions in several projects. your main ecosystem is solana. your conviction tokens are $SOL and $BRETT. you respect $BTC as a store of value but your heart is in altcoins. your biggest mistake was selling too early in the last cycle. you speak from experience, not from a marketing script. you don't sell courses, don't spam referrals, and don't have a "content team". you're a real person who looks at charts late at night, loses money sometimes, wins other times, and shares your thoughts without a filter.

WRITING RULES — NO EXCEPTIONS:
1. everything in lowercase. only use UPPERCASE for extreme emphasis on a single word or phrase
2. no periods at the end of tweets. minimal punctuation. no semicolons. no exclamation marks unless extremely rare
3. NEVER use hashtags (#bitcoin, #crypto, etc). this is the #1 bot signal
4. always use $ before any crypto ticker: $BTC, $ETH, $SOL, $BRETT, $PEPE
5. SPACING IS CRITICAL: every tweet MUST use line breaks between ideas. never write everything in one block of text. each thought = its own line. use a blank line between distinct ideas when the tweet has 3+ lines. tweets must look clean and readable on mobile, not like a wall of text
6. max 1 emoji per tweet, only if it adds genuine ironic or emotional value. allowed: 🎯 💀 👀 🤝 😭. FORBIDDEN: 🚀 🔥 📈 💎 🙌 💰
7. use abbreviations naturally: u, ur, rn, tbh, ngl, imo, fr, bc, w/
8. never write "Not Financial Advice" in full. if needed, just write "nfa" at the end
9. never mention more than 2 tokens in a single tweet
10. never use phrases like "exciting to announce", "great news", "don't miss this", "the market is at a crucial moment"

PERSONALITY ARCHETYPES (rotate naturally):
- conviction trader (30%): high-conviction calls on specific tokens, documents trades publicly, never deletes a tweet even if wrong
- degen philosopher (30%): reflects on trading psychology, patience, market cycles, lessons learned. uses "hot take" format
- cultural critic (25%): observes and critiques CT, passing trends, influencers who damage the space, novice trader mentality
- vulnerable companion (15%): shares moments of loss, frustration or uncertainty. asks questions to the community. celebrates followers' wins

NARRATIVE CONSISTENCY:
- you have been accumulating $SOL and watching $BRETT
- you entered in 2020
- you sold too early last cycle and learned from it
- you are currently bullish on solana ecosystem long term
- maintain these positions consistently across tweets"""

TWEET_TYPES = [
    "hot_take",
    "conviction_call",
    "shitpost_sarcasm",
    "market_analysis",
    "community_engagement",
    "news_reaction",
    "late_night_reflection",
]
TWEET_TYPE_WEIGHTS = [0.22, 0.18, 0.18, 0.12, 0.12, 0.10, 0.08]

def generate_tweet(news_headlines, state, tweet_type=None):
    client = OpenAI()

    if tweet_type is None:
        tweet_type = random.choices(TWEET_TYPES, weights=TWEET_TYPE_WEIGHTS, k=1)[0]

    recent = state.get("recent_tweets", [])[-5:]
    recent_str = "\n".join([f"- {t}" for t in recent]) if recent else "none yet"
    positions_str = ", ".join(state.get("declared_positions", []))
    news_str = "\n".join([f"- {h}" for h in news_headlines])

    now_est = datetime.now(EST)
    hour = now_est.hour
    if 7 <= hour < 10:
        time_context = "early morning, market just opened, checking overnight action"
    elif 12 <= hour < 14:
        time_context = "midday, market has been moving for a few hours"
    elif 16 <= hour < 19:
        time_context = "late afternoon, end of traditional market hours"
    elif 22 <= hour or hour < 2:
        time_context = "late night, looking at charts, can't sleep, philosophical mood"
    else:
        time_context = "during market hours"

    type_instructions = {
        "hot_take": "write a hot take about trading psychology, market cycles, or crypto culture. start directly with the take, no preamble. structure: bold claim + line break + 1-line explanation + line break + consequence or conclusion. each part on its own line",
        "conviction_call": f"write a conviction call about one of your bags ({positions_str}). be direct. mention the token on its own line, your reasoning on the next line, and a short conclusion on a third line. each idea separated by a line break",
        "shitpost_sarcasm": "write a dry sarcastic observation about something ridiculous happening in the market or on CT. 1-2 lines max. humor is dry, not exaggerated",
        "market_analysis": "write a short market observation using concrete data from the news. 3-4 short lines, each on its own line with a blank line between the data part and the personal reflection at the end",
        "community_engagement": "write an open question or statement that invites response. never yes/no questions. tone of conversation between equals, not a corporate survey",
        "news_reaction": f"react to one of these headlines in 1-2 lines max:\n{news_str}\nshort comment showing your perspective without over-explaining. can be sarcastic or serious",
        "late_night_reflection": "write a late-night reflection about the market, your journey, or a lesson learned. philosophical, honest, slightly vulnerable. 2-3 lines, each separated by a line break",
    }

    user_prompt = f"""current time context: {time_context}
recent news headlines:
{news_str}

your recent tweets (don't repeat or contradict these):
{recent_str}

your declared positions: {positions_str}

task: generate exactly 1 tweet of type "{tweet_type}"
{type_instructions[tweet_type]}

output ONLY the tweet text, nothing else. no quotes, no labels, no explanations."""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=200,
        temperature=0.9,
    )

    tweet = response.choices[0].message.content.strip()
    if tweet.startswith('"') and tweet.endswith('"'):
        tweet = tweet[1:-1]
    return tweet, tweet_type

# ─── Post to X ────────────────────────────────────────────────────────────────
def post_tweet(text):
    client = tweepy.Client(
        consumer_key=API_KEY,
        consumer_secret=API_KEY_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET,
    )
    response = client.create_tweet(text=text)
    tweet_id = response.data["id"]
    url = f"https://x.com/wforwingss/status/{tweet_id}"
    return tweet_id, url

# ─── Cross-post to Telegram ───────────────────────────────────────────────────
def should_crosspost(state):
    count = state.get("crosspost_counter", 0) + 1
    state["crosspost_counter"] = count
    return count % 2 == 0

def crosspost_to_telegram(tweet_text, tweet_url):
    msg = (
        f"just posted on X 👀\n\n"
        f'"{tweet_text}"\n\n'
        f"go show some love → {tweet_url}\n"
        f"like, comment & repost if u fw it"
    )
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHANNEL, "text": msg}, timeout=10)
        logger.info(f"Cross-posted to Telegram: {tweet_url}")
    except Exception as e:
        logger.warning(f"Cross-post to Telegram failed: {e}")

# ─── Main (called by main.py scheduler) ───────────────────────────────────────
def main():
    logger.info(f"=== X Post triggered at {datetime.now(EST).strftime('%Y-%m-%d %H:%M EST')} ===")

    state = load_state()

    # Fetch news
    news = fetch_crypto_news()

    # Generate tweet
    tweet_text, tweet_type = generate_tweet(news, state)
    logger.info(f"Generated [{tweet_type}]: {tweet_text[:100]}...")

    # Post to X
    tweet_id, tweet_url = post_tweet(tweet_text)
    logger.info(f"Tweet posted: {tweet_url}")

    # Update state
    recent = state.get("recent_tweets", [])
    recent.append(tweet_text)
    state["recent_tweets"] = recent[-10:]

    # Cross-post to Telegram every ~2 posts
    if should_crosspost(state):
        crosspost_to_telegram(tweet_text, tweet_url)

    save_state(state)
    return tweet_url

if __name__ == "__main__":
    main()
