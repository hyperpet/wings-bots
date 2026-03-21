#!/usr/bin/env python3
"""
Wings Bot - Main Runner for Railway
Runs all bots 24/7 with proper human-like scheduling.
- Telegram: 1 post per day, random time, min 12h between posts
- X: 3-7 posts per day, random times, 6am-1am EST only
- X Replies: every 2h during EST hours (after account warms up)
"""

import time
import random
import logging
import os
from datetime import datetime, timedelta
import pytz

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("wings.main")

EST = pytz.timezone("America/New_York")
UTC = pytz.utc

# ─── Telegram Scheduler ──────────────────────────────────────────────────────
def run_telegram_bot():
    """
    Telegram bot: posts 1 time per day at a random time.
    Occasionally skips a day (15% chance) to simulate human behavior.
    Minimum 12h between posts always enforced.
    """
    import post_to_channel

    last_post_time = None  # Track in memory (no file dependency)

    while True:
        now_utc = datetime.now(UTC)

        # Check if minimum 12h have passed since last post
        if last_post_time is not None:
            hours_since = (now_utc - last_post_time).total_seconds() / 3600
            if hours_since < 12:
                sleep_secs = (12 - hours_since) * 3600 + random.randint(0, 3600)
                logger.info(f"[Telegram] Too soon ({hours_since:.1f}h since last). Sleeping {sleep_secs/3600:.1f}h")
                time.sleep(sleep_secs)
                continue

        # Decide whether to post now or wait
        # Random wait between 12-24h from last post (or from start if first post)
        if last_post_time is None:
            # First post: wait a random time between 1-6 hours after startup
            wait_hours = random.uniform(1, 6)
        else:
            # Subsequent posts: 15% chance of silent day (36-48h), else 12-24h
            if random.random() < 0.15:
                wait_hours = random.uniform(36, 48)
                logger.info(f"[Telegram] Silent period chosen: {wait_hours:.1f}h")
            else:
                wait_hours = random.uniform(12, 24)

        next_post_time = (last_post_time or now_utc) + timedelta(hours=wait_hours)
        wait_secs = max(0, (next_post_time - datetime.now(UTC)).total_seconds())

        logger.info(f"[Telegram] Next post in {wait_secs/3600:.1f}h at {next_post_time.strftime('%Y-%m-%d %H:%M UTC')}")
        time.sleep(wait_secs)

        # Post
        try:
            logger.info("[Telegram] === Posting now ===")
            post_to_channel.main()
            last_post_time = datetime.now(UTC)
            logger.info(f"[Telegram] Post done at {last_post_time.strftime('%Y-%m-%d %H:%M UTC')}")
        except Exception as e:
            logger.error(f"[Telegram] Error: {e}")
            # On error, wait 30 min and retry
            time.sleep(1800)


# ─── X Posts Scheduler ───────────────────────────────────────────────────────
def run_x_bot():
    """
    X poster: 3-7 posts per day, only during 6am-1am EST.
    Posts are spread randomly throughout the day.
    """
    time.sleep(600)  # Start 10 min after Telegram to avoid simultaneous startup
    import post_to_x

    while True:
        now_est = datetime.now(EST)
        hour_est = now_est.hour

        # Only post between 6am and 1am EST (hour 6 to 24)
        if hour_est < 6:
            # Sleep until 6am EST
            wake_time = now_est.replace(hour=6, minute=random.randint(0, 59), second=0)
            if wake_time < now_est:
                wake_time += timedelta(days=1)
            sleep_secs = (wake_time - now_est).total_seconds()
            logger.info(f"[X] Outside posting hours. Sleeping until {wake_time.strftime('%H:%M EST')}")
            time.sleep(sleep_secs)
            continue

        # Decide how many posts today (3-7)
        posts_today = random.randint(3, 7)
        logger.info(f"[X] Planning {posts_today} posts today")

        # Generate random posting times spread across 6am-1am EST (19 hours)
        available_minutes = list(range(6 * 60, 25 * 60))  # 6am to 1am = 360 to 1500 min
        post_minutes = sorted(random.sample(available_minutes, min(posts_today, len(available_minutes))))

        for post_minute in post_minutes:
            target_hour = post_minute // 60
            target_min = post_minute % 60

            now_est = datetime.now(EST)
            target_time = now_est.replace(hour=target_hour % 24, minute=target_min, second=0, microsecond=0)

            # Skip if this time has already passed today
            if target_time <= now_est:
                continue

            wait_secs = (target_time - now_est).total_seconds()
            # Add small random jitter (±15 min) to feel more human
            wait_secs += random.randint(-900, 900)
            wait_secs = max(60, wait_secs)

            logger.info(f"[X] Next post at {target_time.strftime('%H:%M EST')} (waiting {wait_secs/3600:.1f}h)")
            time.sleep(wait_secs)

            try:
                logger.info("[X] === Posting now ===")
                post_to_x.main()
                logger.info(f"[X] Post done at {datetime.now(EST).strftime('%H:%M EST')}")
            except Exception as e:
                logger.error(f"[X] Error: {e}")

        # Sleep until next day 6am EST
        now_est = datetime.now(EST)
        next_day_6am = (now_est + timedelta(days=1)).replace(hour=6, minute=random.randint(0, 30), second=0)
        sleep_secs = (next_day_6am - now_est).total_seconds()
        logger.info(f"[X] Day done. Sleeping until tomorrow {next_day_6am.strftime('%H:%M EST')}")
        time.sleep(max(60, sleep_secs))


# ─── X Replies Scheduler ─────────────────────────────────────────────────────
def run_x_replies():
    """
    X reply bot: runs every 2h during EST hours.
    Currently in warm-up mode — will activate after ~1 week.
    """
    time.sleep(1200)  # Start 20 min after main bots

    import reply_on_x

    while True:
        now_est = datetime.now(EST)
        hour_est = now_est.hour

        # Only reply during 8am-11pm EST
        if hour_est < 8 or hour_est >= 23:
            sleep_secs = random.randint(3600, 7200)
            logger.info(f"[X Replies] Outside hours. Sleeping {sleep_secs/3600:.1f}h")
            time.sleep(sleep_secs)
            continue

        try:
            logger.info("[X Replies] === Running reply check ===")
            reply_on_x.main()
        except Exception as e:
            logger.error(f"[X Replies] Error: {e}")

        # Wait 2-3h before next reply check
        sleep_secs = random.randint(7200, 10800)
        logger.info(f"[X Replies] Sleeping {sleep_secs/3600:.1f}h until next reply check")
        time.sleep(sleep_secs)


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import threading

    logger.info("=" * 60)
    logger.info("Wings Bot starting on Railway...")
    logger.info(f"UTC:  {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"EST:  {datetime.now(EST).strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    threads = [
        threading.Thread(target=run_telegram_bot, name="TelegramBot", daemon=True),
        threading.Thread(target=run_x_bot, name="XPoster", daemon=True),
        threading.Thread(target=run_x_replies, name="XReplies", daemon=True),
    ]

    for t in threads:
        t.start()
        logger.info(f"Started thread: {t.name}")

    # Keep main thread alive with heartbeat
    while True:
        now = datetime.now(UTC)
        logger.info(f"[Heartbeat] Wings Bot alive — {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        time.sleep(3600)
