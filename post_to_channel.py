#!/usr/bin/env python3
"""
Wings Calls - Telegram Bot (v3)
Instrucciones: Instrucciones_Bot_Telegram_Crypto.pdf
- Identidad híbrida: Degen Caller + Analista Técnico + Hermano Mayor + Insider
- Sistema de clusters para calls (4 mensajes en ~30 min)
- 5 tipos de mensajes con frecuencias correctas
- Formato estricto: minúsculas, sin hashtags, saltos de línea, emojis estratégicos
- Manejo de crisis si un call sale mal
- Mínimo 12h entre posts normales (clusters no cuentan como posts separados)
"""

import os
import json
import random
import requests
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from openai import OpenAI

# ─── Configuration ────────────────────────────────────────────────────────────
BOT_TOKEN          = os.environ.get("TELEGRAM_BOT_TOKEN", "8203101684:AAE_RAR7CBhFy-N1CkVha1fF3vwfMf6nE8U")
CHANNEL_ID         = "@wingsscalls"
LOG_FILE           = os.environ.get("DATA_DIR", "/app/data") + "/post_log.txt"
SCRIPT_PATH        = os.path.abspath(__file__)
LAST_POST_FILE     = os.environ.get("DATA_DIR", "/app/data") + "/last_post_time.txt"
ACTIVE_CALL_FILE   = os.environ.get("DATA_DIR", "/app/data") + "/active_call.json"
MIN_HOURS          = 12

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ─── OpenAI ───────────────────────────────────────────────────────────────────
client = OpenAI()

# ─── System Prompt Base ───────────────────────────────────────────────────────
SYSTEM_PROMPT = """eres el admin de un canal de telegram crypto muy respetado llamado Wings Calls.
tu audiencia confía en ti porque eres auténtico, transparente y rentable.
no eres un bot corporativo ni un influencer falso. eres un degen veterano que sobrevive en las trincheras de solana y ethereum.

tu identidad tiene 4 facetas que rotas naturalmente:
1. DEGEN CALLER: compartes operaciones de alto riesgo en tiempo real con convicción absoluta
2. ANALISTA TÉCNICO: das contexto de mercado (BTC/SOL) para justificar operaciones
3. HERMANO MAYOR: muestras vulnerabilidad, reflexiones sobre la vida y el mercado
4. INSIDER: actúas como si entendieras las narrativas antes que la masa

reglas de escritura ESTRICTAS:
- todo en minúsculas SIEMPRE (excepto tickers como $BTC, $SOL, $ETH)
- sin puntos finales en las oraciones
- saltos de línea frecuentes entre ideas cortas (cada idea = su propia línea)
- lenguaje informal: "u" en vez de "you", "ur" en vez de "your", "rn" en vez de "right now", "im" sin apóstrofe
- emojis estratégicos pero no excesivos: 🔥 para calls/pumps, 🗿 cuando el mercado sangra, 👀 como teaser, 🤝 camaradería
- tono de camaradería: "fellas", "chat", "fam", "brother"
- CERO hashtags (es señal de bot de spam en telegram)
- CERO bloques de texto densos (nadie lee párrafos largos en telegram)
- CERO formalidad financiera ("nfa" en vez de "not financial advice")
- CERO links acortados

diccionario que debes dominar:
- trenches: el mercado de memecoins de baja capitalización
- ape/aped: comprar agresivamente
- jeet: alguien que vende por pánico o ganancias mínimas
- moonbag: porción pequeña de tokens que guardas por si se multiplica
- nuke/nuking: caída drástica de precio
- send it: grito de guerra para que el precio suba
- cook/cooking: cuando un gráfico se ve prometedor
- HTF: higher time frame
- chop: mercado lateral sin dirección

escribe en inglés."""

# ─── Fetch Crypto News ────────────────────────────────────────────────────────
def fetch_crypto_news() -> str:
    """Fetch top crypto headlines from multiple sources."""
    # Source 1: CoinDesk RSS
    try:
        resp = requests.get("https://www.coindesk.com/arc/outboundfeeds/rss/",
                            timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")[:8]
        headlines = [item.findtext("title", "").strip() for item in items if item.findtext("title")]
        if headlines:
            logger.info("News: CoinDesk RSS")
            return "\n".join(f"- {h}" for h in headlines)
    except Exception as e:
        logger.warning(f"CoinDesk failed: {e}")

    # Source 2: CryptoPanic
    try:
        resp = requests.get("https://cryptopanic.com/api/free/v1/posts/?auth_token=free&public=true&kind=news", timeout=10)
        results = resp.json().get("results", [])[:8]
        headlines = [item["title"] for item in results if item.get("title")]
        if headlines:
            logger.info("News: CryptoPanic")
            return "\n".join(f"- {h}" for h in headlines)
    except Exception as e:
        logger.warning(f"CryptoPanic failed: {e}")

    # Source 3: Cointelegraph RSS
    try:
        resp = requests.get("https://cointelegraph.com/rss",
                            timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")[:8]
        headlines = [item.findtext("title", "").strip() for item in items if item.findtext("title")]
        if headlines:
            logger.info("News: Cointelegraph RSS")
            return "\n".join(f"- {h}" for h in headlines)
    except Exception as e:
        logger.warning(f"Cointelegraph failed: {e}")

    logger.warning("All news sources failed, using fallback")
    return "- Bitcoin holding above $70k\n- Solana ecosystem growing fast\n- Memecoins showing risk-on sentiment\n- Crypto market cap at $2.6T"

# ─── Fetch Real Tokens from DexScreener ─────────────────────────────────────
def fetch_real_solana_gems() -> list:
    """
    Fetch recently created Solana tokens from DexScreener with real data.
    Filters for promising gems based on:
    - Created in last 6 hours
    - Volume > $10k
    - Buy/sell ratio > 2x (more buyers than sellers)
    - Liquidity > $5k
    - Market cap < $5M (low cap = more upside)
    Returns list of token dicts with real data.
    """
    gems = []
    try:
        # Get latest token profiles (recently boosted/created on Solana)
        resp = requests.get(
            "https://api.dexscreener.com/token-profiles/latest/v1",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        if resp.status_code != 200:
            logger.warning(f"DexScreener profiles failed: {resp.status_code}")
            return []

        profiles = [p for p in resp.json() if p.get("chainId") == "solana"]
        logger.info(f"DexScreener: {len(profiles)} Solana profiles found")

        # For each profile, get detailed pair data
        for profile in profiles[:20]:  # Check top 20
            ca = profile.get("tokenAddress", "")
            if not ca:
                continue
            try:
                detail_resp = requests.get(
                    f"https://api.dexscreener.com/tokens/v1/solana/{ca}",
                    timeout=8
                )
                if detail_resp.status_code != 200:
                    continue
                pairs = detail_resp.json()
                if not pairs:
                    continue

                pair = pairs[0]  # Main pair
                name = pair.get("baseToken", {}).get("name", "")
                symbol = pair.get("baseToken", {}).get("symbol", "")
                price_usd = float(pair.get("priceUsd") or 0)
                volume_h24 = float(pair.get("volume", {}).get("h24") or 0)
                price_change_h1 = float(pair.get("priceChange", {}).get("h1") or 0)
                price_change_h6 = float(pair.get("priceChange", {}).get("h6") or 0)
                liquidity = float(pair.get("liquidity", {}).get("usd") or 0)
                market_cap = float(pair.get("marketCap") or 0)
                buys_h1 = int(pair.get("txns", {}).get("h1", {}).get("buys") or 0)
                sells_h1 = int(pair.get("txns", {}).get("h1", {}).get("sells") or 1)
                created_at_ms = pair.get("pairCreatedAt") or 0
                created_at = datetime.utcfromtimestamp(created_at_ms / 1000) if created_at_ms else None
                age_hours = (datetime.utcnow() - created_at).total_seconds() / 3600 if created_at else 999

                buy_sell_ratio = buys_h1 / max(sells_h1, 1)

                # Filter criteria for a promising gem
                if (
                    age_hours <= 6 and
                    volume_h24 >= 10000 and
                    liquidity >= 5000 and
                    buy_sell_ratio >= 2.0 and
                    (market_cap == 0 or market_cap <= 5_000_000) and
                    name and symbol
                ):
                    gems.append({
                        "name": name,
                        "symbol": symbol,
                        "ca": ca,
                        "price_usd": price_usd,
                        "volume_h24": volume_h24,
                        "price_change_h1": price_change_h1,
                        "price_change_h6": price_change_h6,
                        "liquidity": liquidity,
                        "market_cap": market_cap,
                        "buy_sell_ratio": buy_sell_ratio,
                        "age_hours": round(age_hours, 1),
                        "description": profile.get("description", ""),
                        "dex_url": f"https://dexscreener.com/solana/{ca}"
                    })
                    logger.info(f"Gem found: {symbol} | MC: ${market_cap:,.0f} | Vol: ${volume_h24:,.0f} | B/S: {buy_sell_ratio:.1f}x")

            except Exception as e:
                logger.warning(f"Error fetching pair {ca}: {e}")
                continue

    except Exception as e:
        logger.error(f"DexScreener fetch error: {e}")

    return gems

# ─── Message Generators ───────────────────────────────────────────────────────

def generate_gm(news: str) -> str:
    """Generate a GM/opening message to measure audience sentiment."""
    prompt = f"""today's crypto news:
{news}

write a short GM message to open the day in the telegram channel.
examples of tone: "gm gm gm / how are the trenches today chat", "morning fellas / market looking spicy rn 🔥", "gm / who survived last night"
rules: all lowercase, no final periods, 1-3 lines max, use saltos de línea between ideas, feel natural not scripted"""

    return _call_gpt(prompt, max_tokens=80)


def generate_market_update(news: str) -> str:
    """Generate a BTC/SOL market update with technical analysis tone."""
    coin = random.choice(["BTC", "SOL"])
    prompt = f"""today's crypto news:
{news}

write a market update about ${coin} for the telegram channel.
rules:
- all lowercase, no final periods
- each idea on its own line (use line breaks)
- mention key levels (e.g. "needs to hold 70k", "looking for 82 bounce")
- use terms like HTF, liquidity, chop, nuke naturally
- tone: analytical but degen
- 4-6 lines max
- end with something like "watching closely" or "lets see how this plays out" """

    return _call_gpt(prompt, max_tokens=150)


def generate_call(news: str) -> dict:
    """
    Generate a memecoin call using REAL tokens from DexScreener.
    Falls back to market update if no gems found.
    """
    gems = fetch_real_solana_gems()

    if not gems:
        logger.warning("No real gems found on DexScreener. Skipping call, posting market update instead.")
        return {"text": generate_market_update(news), "ticker": None, "ca": None, "fallback": True}

    # Pick the best gem (highest buy/sell ratio among top volume)
    gem = sorted(gems, key=lambda x: x["buy_sell_ratio"] * x["volume_h24"], reverse=True)[0]

    ticker = f"${gem['symbol']}"
    ca = gem["ca"]
    name = gem["name"]
    mc_str = f"${gem['market_cap']:,.0f}" if gem["market_cap"] > 0 else "very low cap"
    vol_str = f"${gem['volume_h24']:,.0f}"
    change_str = f"+{gem['price_change_h1']:.0f}%" if gem["price_change_h1"] > 0 else f"{gem['price_change_h1']:.0f}%"
    bs_ratio = f"{gem['buy_sell_ratio']:.1f}x"
    age_str = f"{gem['age_hours']}h old"
    description = gem.get("description", "")

    prompt = f"""write a memecoin call for the telegram channel based on this REAL token:

token name: {name}
ticker: {ticker}
contract: {ca}
market cap: {mc_str}
volume last 24h: {vol_str}
price change last 1h: {change_str}
buy/sell ratio last 1h: {bs_ratio} (way more buyers than sellers)
age: {age_str}
description: {description}

structure (EXACTLY this format, no extra lines):
line 1: 1 sentence explaining why this token looks interesting RIGHT NOW based on the data above (lowercase, natural, reference the momentum/narrative)
line 2: your conviction ("im in", "looks primed", "aped a bag", "low cap gem", "cooking")
line 3: just the ticker: {ticker}
line 4: CA: {ca}
line 5: "nfa dyor" or "nfa dont ape what u cant lose"

rules: all lowercase, no hashtags, feel like a real degen sharing a find, not a bot. max 5 lines."""

    text = _call_gpt(prompt, max_tokens=130)
    # Ensure CA is always shown in its original case (GPT sometimes lowercases it)
    if ca.lower() in text.lower():
        import re
        text = re.sub(re.escape(ca), ca, text, flags=re.IGNORECASE)
    logger.info(f"Real gem call: {ticker} | CA: {ca} | MC: {mc_str} | Vol: {vol_str} | B/S: {bs_ratio}")
    return {"text": text, "ticker": ticker, "ca": ca, "fallback": False, "gem_data": gem}


def generate_call_update(update_type: str, ticker: str) -> str:
    """Generate a cluster update message after a call."""
    updates = {
        "chart_check": [
            f"chart looks primed\n{ticker} holding well 👀",
            f"still watching {ticker}\ngraph cooking rn",
            f"{ticker} not moving yet but setup still valid\npatience",
        ],
        "first_target": [
            f"2x from entry on {ticker}\nsecure ur initials fellas",
            f"first target hit on {ticker} 🔥\nlet the rest ride",
            f"{ticker} moving\nwho got in early chat",
        ],
        "final_update": [
            f"fully out of {ticker}\nnice trade fellas 🤝",
            f"holding a moonbag on {ticker}\nrest is profit",
            f"took profits on {ticker}\nonto the next one",
        ],
    }
    return random.choice(updates.get(update_type, updates["chart_check"]))


def generate_vulnerability(news: str) -> str:
    """Generate a vulnerability/community message (Hermano Mayor archetype)."""
    prompt = f"""today's crypto news:
{news}

write a vulnerability/community message for the telegram channel.
rules:
- all lowercase, no final periods
- tone: hermano mayor, estoico, empático
- talk about surviving the market, taking breaks, protecting mental health
- use "fellas" or "chat" at least once
- 3-4 lines max, each idea on its own line
- can reference market conditions from the news"""

    return _call_gpt(prompt, max_tokens=100)


def generate_crisis_message(ticker: str, reason: str = "rugged") -> str:
    """Generate a crisis message when a call goes bad."""
    messages = {
        "rugged": f"dev rugged on {ticker}\ntook an L here\nonto the next one",
        "nuke": f"{ticker} nuked hard\nstopped out\nmarket is brutal today, protecting capital",
        "slow": f"{ticker} not moving as expected\ncutting it\nnever risk more than u can afford to lose fellas",
    }
    return messages.get(reason, messages["rugged"])


def _call_gpt(prompt: str, max_tokens: int = 150) -> str:
    """Call OpenAI GPT with the system prompt and return the response."""
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=1.1,
        )
        text = response.choices[0].message.content.strip()
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]
        return text
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return "market moving rn\nwatching closely"


# ─── Send Message ─────────────────────────────────────────────────────────────
def send_message(text: str) -> bool:
    """Send a message to the Telegram channel."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text}
    try:
        resp = requests.post(url, json=payload, timeout=30)
        data = resp.json()
        if data.get("ok"):
            logger.info(f"Sent msg ID: {data['result']['message_id']} | {text[:60]}")
            return True
        else:
            logger.error(f"Telegram error: {data}")
            return False
    except Exception as e:
        logger.error(f"Request error: {e}")
        return False


# ─── Cluster: Full Call Sequence ──────────────────────────────────────────────
def run_call_cluster(news: str):
    """
    Execute a full call cluster:
    Minute 0:  Send the call with CA
    Minute 15: Chart check update
    Minute 25: First target update
    Minute 35: Final update / moonbag
    """
    logger.info("Starting call cluster...")
    call_data = generate_call(news)

    # Message 1: The Call
    send_message(call_data["text"])
    logger.info(f"Call sent: {call_data['ticker']}")

    # Save active call state
    with open(ACTIVE_CALL_FILE, "w") as f:
        json.dump({"ticker": call_data["ticker"], "started": datetime.utcnow().isoformat()}, f)

    # Message 2: Chart check (15 min later)
    time.sleep(15 * 60)
    update1 = generate_call_update("chart_check", call_data["ticker"])
    send_message(update1)

    # Message 3: First target (10 more minutes)
    time.sleep(10 * 60)
    update2 = generate_call_update("first_target", call_data["ticker"])
    send_message(update2)

    # Message 4: Final update (10 more minutes)
    time.sleep(10 * 60)
    update3 = generate_call_update("final_update", call_data["ticker"])
    send_message(update3)

    # Clear active call
    if os.path.exists(ACTIVE_CALL_FILE):
        os.remove(ACTIVE_CALL_FILE)

    logger.info(f"Call cluster complete for {call_data['ticker']}")


# ─── Message Type Selector ────────────────────────────────────────────────────
def select_message_type() -> str:
    """
    Select message type based on document frequencies:
    - GM: 1x/day (only if no GM sent today)
    - Market Update: 2-3x/week → ~35% of non-GM posts
    - Call: 1-2x/day → ~30% of posts
    - Price Update: only after a call (handled in cluster)
    - Vulnerability: 1x/week → ~10% of posts
    """
    # Check if GM was already sent today
    gm_sent_today = False
    if os.path.exists(LAST_POST_FILE):
        try:
            with open(LAST_POST_FILE, "r") as f:
                data = json.load(f)
            last_gm = data.get("last_gm_date", "")
            if last_gm == datetime.utcnow().strftime("%Y-%m-%d"):
                gm_sent_today = True
        except Exception:
            pass

    roll = random.random()

    if not gm_sent_today and roll < 0.20:
        return "gm"
    elif roll < 0.50:
        return "call"
    elif roll < 0.80:
        return "market_update"
    else:
        return "vulnerability"


# ─── Time Guard ───────────────────────────────────────────────────────────────
def check_min_interval() -> bool:
    """Returns True if at least 12h have passed since the last main post."""
    if not os.path.exists(LAST_POST_FILE):
        return True
    try:
        with open(LAST_POST_FILE, "r") as f:
            data = json.load(f)
        last_ts = data.get("timestamp", 0)
        elapsed = (datetime.utcnow().timestamp() - last_ts) / 3600
        if elapsed < MIN_HOURS:
            logger.warning(f"Too soon: {elapsed:.1f}h since last post (min {MIN_HOURS}h). Skipping.")
            return False
        return True
    except Exception:
        return True


def save_post_time(msg_type: str):
    """Save the current UTC timestamp and message type."""
    data = {}
    if os.path.exists(LAST_POST_FILE):
        try:
            with open(LAST_POST_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            pass

    data["timestamp"] = datetime.utcnow().timestamp()
    data["last_type"] = msg_type
    if msg_type == "gm":
        data["last_gm_date"] = datetime.utcnow().strftime("%Y-%m-%d")

    with open(LAST_POST_FILE, "w") as f:
        json.dump(data, f)


# Scheduling is handled by main.py — no cron needed here


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    logger.info(f"=== Post triggered at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC ===")

    # 1. Fetch news
    news = fetch_crypto_news()
    logger.info(f"News fetched: {news[:150]}...")

    # 3. Select message type and generate content
    msg_type = select_message_type()
    logger.info(f"Message type selected: {msg_type}")

    if msg_type == "gm":
        text = generate_gm(news)
        success = send_message(text)
        if success:
            save_post_time("gm")

    elif msg_type == "market_update":
        text = generate_market_update(news)
        success = send_message(text)
        if success:
            save_post_time("market_update")

    elif msg_type == "call":
        # Calls run as a cluster (4 messages over ~35 minutes)
        # We save post time before cluster to prevent double-posting
        save_post_time("call")
        run_call_cluster(news)

    elif msg_type == "vulnerability":
        text = generate_vulnerability(news)
        success = send_message(text)
        if success:
            save_post_time("vulnerability")

    # Scheduling is handled by main.py


if __name__ == "__main__":
    main()
