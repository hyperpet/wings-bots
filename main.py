#!/usr/bin/env python3
"""
Wings Bot - Main Runner for Railway
Runs all bots in a continuous loop with proper scheduling.
No cron needed - this process stays alive 24/7.
"""

import time
import threading
import logging
import os
from datetime import datetime, timezone
import pytz

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("wings.main")

EST = pytz.timezone("America/New_York")


def run_telegram_bot():
    """Run the Telegram bot every hour."""
    import post_to_channel
    while True:
        try:
            logger.info("=== Running Telegram bot ===")
            post_to_channel.main()
        except Exception as e:
            logger.error(f"Telegram bot error: {e}")
        logger.info("Telegram bot sleeping 60 minutes...")
        time.sleep(3600)  # check every hour


def run_x_bot():
    """Run the X poster every hour (offset 30 min from Telegram)."""
    time.sleep(1800)  # start 30 min after Telegram
    import post_to_x
    while True:
        try:
            logger.info("=== Running X poster ===")
            post_to_x.main()
        except Exception as e:
            logger.error(f"X poster error: {e}")
        logger.info("X poster sleeping 60 minutes...")
        time.sleep(3600)


def run_x_replies():
    """Run the X reply bot every 2 hours (offset 1h from start)."""
    time.sleep(3600)  # start 1 hour after launch
    import reply_on_x
    while True:
        try:
            logger.info("=== Running X reply bot ===")
            reply_on_x.main()
        except Exception as e:
            logger.error(f"X reply bot error: {e}")
        logger.info("X reply bot sleeping 2 hours...")
        time.sleep(7200)


if __name__ == "__main__":
    logger.info("Wings Bot starting on Railway...")
    logger.info(f"Current time UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")

    # Start all bots in separate threads
    threads = [
        threading.Thread(target=run_telegram_bot, name="TelegramBot", daemon=True),
        threading.Thread(target=run_x_bot, name="XPoster", daemon=True),
        threading.Thread(target=run_x_replies, name="XReplies", daemon=True),
    ]

    for t in threads:
        t.start()
        logger.info(f"Started thread: {t.name}")

    # Keep main thread alive
    while True:
        now = datetime.now(timezone.utc)
        logger.info(f"Wings Bot alive — {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        time.sleep(3600)  # heartbeat every hour
