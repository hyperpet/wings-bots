#!/usr/bin/env python3
"""
Wings — X (Twitter) Auto-Poster
Follows strictly: Instrucciones_Bot_Crypto_Twitter_FINAL.md
3-7 posts per day, irregular schedule, CT veteran persona
"""

import os, json, random, logging, subprocess
from datetime import datetime, timedelta
import pytz
import tweepy
import requests
import xml.etree.ElementTree as ET
from openai import OpenAI

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=os.environ.get("DATA_DIR", "/app/data") + "/x_post_log.txt",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# ─── Configuration ────────────────────────────────────────────────────────────
API_KEY             = os.environ.get("X_API_KEY", "tMkqzeKXyiqThV8relqr4Xa1h")
API_KEY_SECRET      = os.environ.get("X_API_KEY_SECRET", "Wchkdy8E2unkyzHNautGHbRWPiWJLqA3eUM5t8RqRZeaIGp8z8")
ACCESS_TOKEN        = os.environ.get("X_ACCESS_TOKEN", "2033548838124851200-LPpTaWOvxII1qjcVFi8EHQcNluZlSq")
ACCESS_TOKEN_SECRET = os.environ.get("X_ACCESS_TOKEN_SECRET", "t6p4XvsiLP6k9ZCEHlSBac0LsNeVDxPSC4b2vMS91uzT2")

BOT_TOKEN           = os.environ.get("TELEGRAM_BOT_TOKEN", "8203101684:AAE_RAR7CBhFy-N1CkVha1fF3vwfMf6nE8U")
TELEGRAM_CHANNEL    = "@wingsscalls"

STATE_FILE          = os.environ.get("DATA_DIR", "/app/data") + "/x_state.json"
LAST_POST_FILE      = os.environ.get("DATA_DIR", "/app/data") + "/x_last_post.txt"

EST = pytz.timezone("America/New_York")

# ─── Narrative State ──────────────────────────────────────────────────────────
DEFAULT_STATE = {
    "ecosystem": "Solana",
    "conviction_tokens": ["$SOL", "$BRETT"],
    "btc_stance": "respects $BTC as store of value but heart is in altcoins",
    "entry_year": "2020",
    "biggest_mistake": "sold too early in the last cycle",
    "biggest_win": "held $SOL through the bear and multiplied capital significantly",
    "recent_tweets": [],
    "declared_positions": ["accumulating $SOL", "watching $BRETT"],
    "posts_today": 0,
    "posts_target_today": 0,
    "day_reset": ""
}

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return DEFAULT_STATE.copy()

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# ─── Time Guard ───────────────────────────────────────────────────────────────
MIN_HOURS_BETWEEN_POSTS = 1.5  # minimum 1.5h between individual tweets

def get_last_post_time():
    if os.path.exists(LAST_POST_FILE):
        with open(LAST_POST_FILE) as f:
            ts = f.read().strip()
            if ts:
                return datetime.fromisoformat(ts)
    return None

def set_last_post_time():
    with open(LAST_POST_FILE, "w") as f:
        f.write(datetime.utcnow().isoformat())

def hours_since_last_post():
    last = get_last_post_time()
    if last is None:
        return 999
    return (datetime.utcnow() - last).total_seconds() / 3600

# ─── Daily Post Counter ───────────────────────────────────────────────────────
def get_today_str():
    return datetime.now(EST).strftime("%Y-%m-%d")

def reset_daily_if_needed(state):
    today = get_today_str()
    if state.get("day_reset") != today:
        state["posts_today"] = 0
        state["posts_target_today"] = random.randint(3, 7)
        state["day_reset"] = today
        logging.info(f"New day: target {state['posts_target_today']} posts today")
    return state

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
                logging.info(f"News from {url}")
                break
        except Exception as e:
            logging.warning(f"News fetch failed ({url}): {e}")
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
    # Remove surrounding quotes if present
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
    """Cross-post every ~2 X posts to Telegram"""
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
    requests.post(url, json={"chat_id": TELEGRAM_CHANNEL, "text": msg}, timeout=10)
    logging.info(f"Cross-posted to Telegram: {tweet_url}")

# ─── Schedule Next Post ───────────────────────────────────────────────────────
# ─── American/Western Hours Definition ───────────────────────────────────────
# Posts only during: 6:00 AM - 1:00 AM EST (next day)
# This covers: US East, US West, UK evening, Western Europe evening
# Avoids: Asian morning hours (2am-6am EST = 3pm-7pm Asia)
POST_START_HOUR_EST = 6    # 6:00 AM EST
POST_END_HOUR_EST   = 25   # 1:00 AM EST next day (hour 25 = 1am)

def schedule_next(state):
    """
    Schedule next post based on how many posts remain for today.
    Uses irregular intervals to simulate human behavior.
    Posts are ONLY distributed during American/Western hours (6am - 1am EST).
    """
    posts_done = state.get("posts_today", 0)
    posts_target = state.get("posts_target_today", 4)
    posts_remaining = posts_target - posts_done

    now_est = datetime.now(EST)
    now_utc = datetime.utcnow()
    current_hour_decimal = now_est.hour + now_est.minute / 60

    if posts_remaining <= 0:
        # Done for today — schedule first post of tomorrow at a random time 6am-10am EST
        tomorrow_est = now_est.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        rand_hour = random.randint(POST_START_HOUR_EST, 10)
        rand_min = random.randint(0, 59)
        next_est = tomorrow_est.replace(hour=rand_hour, minute=rand_min)
        # Reset daily counter for tomorrow
        state["posts_today"] = 0
        state["posts_target_today"] = random.randint(3, 7)
        state["day_reset"] = (now_est + timedelta(days=1)).strftime("%Y-%m-%d")
        interval_hours = (next_est - now_est).total_seconds() / 3600
        logging.info(f"Done for today ({posts_done} posts). Next post tomorrow at {next_est.strftime('%H:%M')} EST")
    else:
        # If we're outside posting hours, wait until 6am EST
        if current_hour_decimal < POST_START_HOUR_EST:
            # It's before 6am EST — wait until 6am + random minutes
            next_est = now_est.replace(hour=POST_START_HOUR_EST, minute=random.randint(0, 45), second=0)
            interval_hours = (next_est - now_est).total_seconds() / 3600
            logging.info(f"Outside posting hours. Waiting until {next_est.strftime('%H:%M')} EST")
        elif current_hour_decimal >= POST_END_HOUR_EST - 24:  # after 1am
            # After 1am — schedule for tomorrow morning
            tomorrow_est = now_est.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            next_est = tomorrow_est.replace(hour=POST_START_HOUR_EST, minute=random.randint(0, 45))
            interval_hours = (next_est - now_est).total_seconds() / 3600
            logging.info(f"Past 1am EST. Scheduling for tomorrow at {next_est.strftime('%H:%M')} EST")
        else:
            # Within posting hours — spread remaining posts across the rest of the day
            # Remaining hours until 1am EST
            hours_left = max(POST_END_HOUR_EST - current_hour_decimal, 1.5)
            base_interval = hours_left / max(posts_remaining, 1)
            # Add randomness: ±40% variation
            variation = base_interval * 0.4
            interval_hours = base_interval + random.uniform(-variation, variation)
            interval_hours = max(1.5, min(interval_hours, 8))  # between 1.5h and 8h
            next_est = now_est + timedelta(hours=interval_hours)
            logging.info(f"Next post in {interval_hours:.1f}h at {next_est.strftime('%H:%M')} EST ({posts_remaining-1} more after that today)")

    # Convert to UTC for cron
    next_utc = now_utc + timedelta(hours=interval_hours)
    
    cron_min = next_utc.minute
    cron_hour = next_utc.hour
    cron_day = next_utc.day
    cron_month = next_utc.month

    cron_line = f"{cron_min} {cron_hour} {cron_day} {cron_month} * python3 /home/ubuntu/wings/post_to_x.py >> /home/ubuntu/wings/x_cron_output.log 2>&1"

    # Update crontab
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = result.stdout if result.returncode == 0 else ""
    lines = [l for l in existing.splitlines() if "post_to_x.py" not in l]
    lines.append(cron_line)
    new_crontab = "\n".join(lines) + "\n"
    subprocess.run(["crontab", "-"], input=new_crontab, text=True)
    logging.info(f"Cron updated: {cron_line}")

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    # Time guard
    hours_since = hours_since_last_post()
    if hours_since < MIN_HOURS_BETWEEN_POSTS:
        logging.info(f"Too soon to post. Only {hours_since:.1f}h since last post (min {MIN_HOURS_BETWEEN_POSTS}h). Skipping.")
        return

    state = load_state()
    state = reset_daily_if_needed(state)

    posts_done = state.get("posts_today", 0)
    posts_target = state.get("posts_target_today", 4)

    if posts_done >= posts_target:
        logging.info(f"Already posted {posts_done}/{posts_target} times today. Done.")
        schedule_next(state)
        save_state(state)
        return

    # Fetch news
    news = fetch_crypto_news()

    # Generate tweet
    tweet_text, tweet_type = generate_tweet(news, state)
    logging.info(f"Generated [{tweet_type}]: {tweet_text}")

    # Post to X
    try:
        tweet_id, tweet_url = post_tweet(tweet_text)
        logging.info(f"Tweet posted. ID: {tweet_id} | URL: {tweet_url}")

        # Update state
        state["posts_today"] = posts_done + 1
        recent = state.get("recent_tweets", [])
        recent.append(tweet_text)
        state["recent_tweets"] = recent[-10:]  # keep last 10
        set_last_post_time()

        # Cross-post to Telegram every ~2 X posts
        if should_crosspost(state):
            try:
                crosspost_to_telegram(tweet_text, tweet_url)
            except Exception as e:
                logging.warning(f"Cross-post to Telegram failed: {e}")

    except Exception as e:
        logging.error(f"Failed to post tweet: {e}")

    # Schedule next post
    schedule_next(state)
    save_state(state)

if __name__ == "__main__":
    main()
