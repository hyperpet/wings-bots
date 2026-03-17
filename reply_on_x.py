#!/usr/bin/env python3
"""
Wings — X (Twitter) Auto-Reply System
Follows strictly: Instrucciones_Bot_Crypto_Twitter_Replies.pdf
Finds recent posts from big CT accounts and replies authentically
Runs every 45-90 minutes during American/Western hours (6am-1am EST)
"""

import os, json, random, logging, subprocess
from datetime import datetime, timedelta
import pytz
import tweepy
from openai import OpenAI

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=os.environ.get("DATA_DIR", "/app/data") + "/x_reply_log.txt",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# ─── Configuration ────────────────────────────────────────────────────────────
API_KEY             = os.environ.get("X_API_KEY", "tMkqzeKXyiqThV8relqr4Xa1h")
API_KEY_SECRET      = os.environ.get("X_API_KEY_SECRET", "Wchkdy8E2unkyzHNautGHbRWPiWJLqA3eUM5t8RqRZeaIGp8z8")
ACCESS_TOKEN        = os.environ.get("X_ACCESS_TOKEN", "2033548838124851200-LPpTaWOvxII1qjcVFi8EHQcNluZlSq")
ACCESS_TOKEN_SECRET = os.environ.get("X_ACCESS_TOKEN_SECRET", "t6p4XvsiLP6k9ZCEHlSBac0LsNeVDxPSC4b2vMS91uzT2")

REPLIED_FILE        = os.environ.get("DATA_DIR", "/app/data") + "/x_replied_ids.json"
REPLY_STATE_FILE    = os.environ.get("DATA_DIR", "/app/data") + "/x_reply_state.json"

# Bearer Token (auto-generated from API Key + Secret, for reading public tweets)
import base64, requests as _requests

def get_bearer_token():
    """Generate Bearer Token from API Key + Secret for app-only auth (reading)."""
    credentials = base64.b64encode(f'{API_KEY}:{API_KEY_SECRET}'.encode()).decode()
    r = _requests.post(
        'https://api.twitter.com/oauth2/token',
        headers={'Authorization': f'Basic {credentials}', 'Content-Type': 'application/x-www-form-urlencoded'},
        data='grant_type=client_credentials',
        timeout=10,
    )
    r.raise_for_status()
    return r.json()['access_token']

EST = pytz.timezone("America/New_York")
POST_START_HOUR_EST = 6
POST_END_HOUR_EST   = 25  # 1am

# ─── Target Accounts (Big CT accounts to reply to) ────────────────────────────
# Mix of large CT accounts across different archetypes
TARGET_ACCOUNTS = [
    "CrashiusClay69",
    "ryandcrypto",
    "colethereum",
    "fxnction",
    "theshamdoo",
    "overdose_ai",
    "poe_real69",
    "inversebrah",
    "notthreadguy",
    "blknoiz06",
    "hsaka",
    "gainzy222",
    "CryptoHayes",
    "MustStopMurad",
    "DegenSpartan",
]

# ─── Replied IDs Tracker ──────────────────────────────────────────────────────
def load_replied_ids():
    if os.path.exists(REPLIED_FILE):
        with open(REPLIED_FILE) as f:
            return set(json.load(f))
    return set()

def save_replied_ids(ids):
    # Keep only last 500 to avoid bloat
    ids_list = list(ids)[-500:]
    with open(REPLIED_FILE, "w") as f:
        json.dump(ids_list, f)

# ─── Daily Reply Counter ──────────────────────────────────────────────────────
def load_reply_state():
    if os.path.exists(REPLY_STATE_FILE):
        with open(REPLY_STATE_FILE) as f:
            return json.load(f)
    return {"replies_today": 0, "day_reset": ""}

def save_reply_state(state):
    with open(REPLY_STATE_FILE, "w") as f:
        json.dump(state, f)

def get_today_str():
    return datetime.now(EST).strftime("%Y-%m-%d")

MAX_REPLIES_PER_DAY = random.randint(5, 12)  # 5-12 replies per day

# ─── Hours Check ─────────────────────────────────────────────────────────────
def is_posting_hours():
    now_est = datetime.now(EST)
    hour = now_est.hour + now_est.minute / 60
    # 6am to 1am EST
    return hour >= POST_START_HOUR_EST or hour < 1.0

# ─── Tweepy# ─── Tweepy Clients ────────────────────────────────────────────
def get_read_client():
    """App-only client using Bearer Token — for reading public tweets."""
    bearer = get_bearer_token()
    return tweepy.Client(bearer_token=bearer, wait_on_rate_limit=True)

def get_write_client():
    """OAuth 1.0a client — for posting replies as @wforwingss."""
    return tweepy.Client(
        consumer_key=API_KEY,
        consumer_secret=API_KEY_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET,
        wait_on_rate_limit=True,
    )

# ─── Fetch Recent Tweets from Target Accounts ─────────────────────────────────
def fetch_recent_tweets(client, replied_ids):
    """
    Fetch recent tweets from target accounts posted in the last 60 minutes.
    Returns a list of (tweet_id, author_username, tweet_text) tuples.
    """
    candidates = []
    cutoff = datetime.utcnow() - timedelta(minutes=90)
    
    # Shuffle accounts to vary which ones we check each run
    accounts = TARGET_ACCOUNTS.copy()
    random.shuffle(accounts)
    
    for username in accounts[:6]:  # Check 6 random accounts per run to save API credits
        try:
            # Get user ID first
            user_resp = client.get_user(username=username, user_fields=["public_metrics"])
            if not user_resp.data:
                continue
            user_id = user_resp.data.id
            followers = user_resp.data.public_metrics.get("followers_count", 0) if user_resp.data.public_metrics else 0
            
            # Get recent tweets
            tweets_resp = client.get_users_tweets(
                id=user_id,
                max_results=5,  # minimum allowed by API
                tweet_fields=["created_at", "public_metrics", "text"],
                exclude=["retweets", "replies"],
            )
            
            if not tweets_resp.data:
                continue
                
            for tweet in tweets_resp.data:
                tweet_id = str(tweet.id)
                
                # Skip if already replied
                if tweet_id in replied_ids:
                    continue
                
                # Skip if too old (> 90 minutes)
                if tweet.created_at and tweet.created_at.replace(tzinfo=None) < cutoff:
                    continue
                
                # Skip very short tweets (< 20 chars) — not worth replying to
                if len(tweet.text) < 20:
                    continue
                
                # Skip tweets that are already replies
                if tweet.text.startswith("@"):
                    continue
                
                # Calculate engagement score
                metrics = tweet.public_metrics or {}
                engagement = (
                    metrics.get("like_count", 0) * 1 +
                    metrics.get("retweet_count", 0) * 3 +
                    metrics.get("reply_count", 0) * 2
                )
                
                candidates.append({
                    "tweet_id": tweet_id,
                    "username": username,
                    "text": tweet.text,
                    "engagement": engagement,
                    "followers": followers,
                    "created_at": tweet.created_at,
                })
                
        except Exception as e:
            logging.warning(f"Failed to fetch tweets from @{username}: {e}")
            continue
    
    # Sort by engagement score (highest first)
    candidates.sort(key=lambda x: x["engagement"] + x["followers"] / 10000, reverse=True)
    return candidates

# ─── Classify Tweet Type ──────────────────────────────────────────────────────
def classify_tweet(text):
    """Classify the tweet to determine reply strategy."""
    text_lower = text.lower()
    
    # FUD about SOL or BRETT
    if any(w in text_lower for w in ["sol is dead", "solana is dead", "dump sol", "sell sol", "brett is", "solana failed"]):
        return "fud_on_bags"
    
    # Bearish/crash content
    if any(w in text_lower for w in ["crash", "dump", "bear", "down", "rekt", "panic", "sell", "bottom"]):
        return "bearish"
    
    # Bullish content
    if any(w in text_lower for w in ["pump", "moon", "ath", "bull", "buy", "accumulate", "up only"]):
        return "bullish"
    
    # Market truth / philosophical
    if any(w in text_lower for w in ["patience", "conviction", "hold", "cycle", "lesson", "truth", "reality"]):
        return "philosophical"
    
    # Loss / frustration
    if any(w in text_lower for w in ["lost", "loss", "down %", "rekt", "pain", "hurt", "frustrat"]):
        return "loss_empathy"
    
    # Ridiculous prediction or normie take
    if any(w in text_lower for w in ["guaranteed", "100%", "definitely", "will definitely", "trust me"]):
        return "ridiculous_prediction"
    
    return "general"

# ─── Generate Reply ───────────────────────────────────────────────────────────
REPLY_SYSTEM_PROMPT = """you are a veteran crypto twitter operator with 150k+ followers. your style is 100% lowercase, no periods at the end, no hashtags, using ct slang (degen, jeet, bags, wagmi, ngmi, alpha, trenches, rekt, diamond hands, paper hands). you are cynical, direct and sometimes sarcastic. you are NOT a friendly ai bot.

REPLY RULES — NO EXCEPTIONS:
1. everything lowercase. UPPERCASE only for extreme emphasis
2. no periods at end. minimal punctuation
3. NEVER hashtags
4. max 1 emoji per reply. only: 💀 👀 🤝 😭 🎯. NEVER: 🚀 🔥 💎 🙌
5. NEVER say "great post", "so true", "i agree", "thanks for sharing"
6. NEVER use links
7. reply must be SHORTER than the original post. max 15-20 words usually
8. sound like a human reacting impulsively from their phone
9. use ct abbreviations: u, ur, rn, tbh, ngl, imo, fr, bc, nfa"""

def generate_reply(tweet_text, username, tweet_type):
    client = OpenAI()
    
    type_instructions = {
        "fud_on_bags": "someone is fudding $SOL or $BRETT. respond with absolute conviction, dismissive of the criticism. NOT defensive. examples: 'more for me then. keep fading it' or 'been hearing this since $SOL was $10'",
        "bearish": "someone is posting about a crash or dump. respond with calm veteran energy. show you've seen this before. examples: 'just another tuesday in crypto' or 'generational buying opportunity and people are panicking'",
        "bullish": "someone is bullish. add a cynical veteran perspective, not just agreement. examples: 'everyone's a genius in a bull market' or 'the timeline isn't ready for what's coming'",
        "philosophical": "someone shared a market truth or philosophical take. validate cynically with your own veteran perspective. add something they didn't say",
        "loss_empathy": "someone shared a loss or frustration. show degen camaraderie. examples: 'we've all paid that tuition fee. survive and advance' or 'i'm down too. holding the line'",
        "ridiculous_prediction": "someone made an overconfident prediction. dry sarcasm. examples: 'this gotta be the funniest shit i've seen all week' or 'ser that's a terrible entry point'",
        "general": "make a sharp, cynical or witty observation that adds value or perspective. not generic agreement",
    }
    
    prompt = f"""POST ORIGINAL:
Author: @{username}
Text: "{tweet_text}"
Tweet type: {tweet_type}

TASK: {type_instructions.get(tweet_type, type_instructions['general'])}

Generate exactly 1 reply. Output ONLY the reply text, nothing else. No quotes, no labels.
Keep it under 20 words if possible. Make it feel like an impulsive human reaction."""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": REPLY_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        max_tokens=80,
        temperature=1.0,
    )
    
    reply = response.choices[0].message.content.strip()
    if reply.startswith('"') and reply.endswith('"'):
        reply = reply[1:-1]
    return reply

# ─── Post Reply ───────────────────────────────────────────────────────────────
def post_reply(client, reply_text, tweet_id):
    response = client.create_tweet(
        text=reply_text,
        in_reply_to_tweet_id=tweet_id,
    )
    return response.data["id"]

# ─── Schedule Next Run ────────────────────────────────────────────────────────
def schedule_next_run():
    """Schedule next reply run in 45-90 minutes, only during posting hours."""
    now_utc = datetime.utcnow()
    now_est = datetime.now(EST)
    
    # Random interval between 45 and 90 minutes
    interval_minutes = random.randint(45, 90)
    next_utc = now_utc + timedelta(minutes=interval_minutes)
    next_est = now_est + timedelta(minutes=interval_minutes)
    
    # If next run would be outside posting hours, schedule for next morning
    next_hour = next_est.hour + next_est.minute / 60
    if next_hour < POST_START_HOUR_EST or (next_hour >= 1.0 and next_hour < POST_START_HOUR_EST):
        # Schedule for 6am EST tomorrow
        tomorrow = now_est.replace(hour=0, minute=0, second=0) + timedelta(days=1)
        next_est = tomorrow.replace(hour=POST_START_HOUR_EST, minute=random.randint(10, 45))
        next_utc = next_est.astimezone(pytz.utc).replace(tzinfo=None)
        logging.info(f"Outside hours. Next reply run tomorrow at {next_est.strftime('%H:%M')} EST")
    else:
        logging.info(f"Next reply run in {interval_minutes}min at {next_est.strftime('%H:%M')} EST")
    
    cron_line = f"{next_utc.minute} {next_utc.hour} {next_utc.day} {next_utc.month} * python3 /home/ubuntu/wings/reply_on_x.py >> /home/ubuntu/wings/x_reply_cron.log 2>&1"
    
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = result.stdout if result.returncode == 0 else ""
    lines = [l for l in existing.splitlines() if "reply_on_x.py" not in l]
    lines.append(cron_line)
    new_crontab = "\n".join(lines) + "\n"
    subprocess.run(["crontab", "-"], input=new_crontab, text=True)
    logging.info(f"Reply cron updated: {cron_line}")

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    # Check posting hours
    if not is_posting_hours():
        logging.info("Outside American/Western posting hours. Skipping reply run.")
        schedule_next_run()
        return
    
    # Load state
    reply_state = load_reply_state()
    today = get_today_str()
    
    # Reset daily counter
    if reply_state.get("day_reset") != today:
        reply_state["replies_today"] = 0
        reply_state["day_reset"] = today
        # Pick new daily target
        reply_state["daily_target"] = random.randint(5, 12)
    
    daily_target = reply_state.get("daily_target", 8)
    replies_today = reply_state.get("replies_today", 0)
    
    if replies_today >= daily_target:
        logging.info(f"Already made {replies_today} replies today (target: {daily_target}). Skipping.")
        schedule_next_run()
        save_reply_state(reply_state)
        return
    
    replied_ids = load_replied_ids()
    read_client = get_read_client()
    write_client = get_write_client()
    
    # Fetch recent tweets from target accounts
    logging.info("Fetching recent tweets from target CT accounts...")
    candidates = fetch_recent_tweets(read_client, replied_ids)
    
    if not candidates:
        logging.info("No suitable tweets found to reply to this run.")
        schedule_next_run()
        return
    
    logging.info(f"Found {len(candidates)} candidate tweets to reply to.")
    
    # Pick 1-2 tweets to reply to this run (don't spam)
    num_replies_this_run = random.randint(1, 2)
    selected = candidates[:num_replies_this_run]
    
    for candidate in selected:
        tweet_id = candidate["tweet_id"]
        username = candidate["username"]
        tweet_text = candidate["text"]
        
        # Classify and generate reply
        tweet_type = classify_tweet(tweet_text)
        logging.info(f"Replying to @{username} [{tweet_type}]: {tweet_text[:80]}...")
        
        try:
            reply_text = generate_reply(tweet_text, username, tweet_type)
            logging.info(f"Generated reply: {reply_text}")
            
            # Post the reply using write client (OAuth)
            reply_id = post_reply(write_client, reply_text, tweet_id)
            reply_url = f"https://x.com/wforwingss/status/{reply_id}"
            logging.info(f"Reply posted: {reply_url}")
            
            # Mark as replied
            replied_ids.add(tweet_id)
            reply_state["replies_today"] = replies_today + 1
            replies_today += 1
            
        except Exception as e:
            logging.error(f"Failed to reply to tweet {tweet_id}: {e}")
    
    save_replied_ids(replied_ids)
    save_reply_state(reply_state)
    schedule_next_run()

if __name__ == "__main__":
    main()
