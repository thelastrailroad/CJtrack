"""
Realtime ZS-CJI flight summary ➜ Telegram using Flightradar24 API

ENV VARS
  TG_TOKEN   : Your Telegram BotFather token
  TG_CHAT    : Numeric chat ID
  FR24_TOKEN : Your Flightradar24 API Bearer token
OPTIONAL
  POLL_SEC   : Seconds between queries (default 60)
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import aiohttp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Configuration
POLL_SEC     = int(os.getenv("POLL_SEC", "60"))
TG_TOKEN     = os.getenv("TG_TOKEN")
TG_CHAT      = int(os.getenv("TG_CHAT", "0"))
FR24_TOKEN   = os.getenv("FR24_TOKEN")
REGISTRATION = "ZS-CJI"

if not (TG_TOKEN and TG_CHAT and FR24_TOKEN):
    raise SystemExit("❌ Set TG_TOKEN, TG_CHAT, and FR24_TOKEN environment variables.")

# Build the Telegram application, scheduling on_startup inside its loop
app = (
    ApplicationBuilder()
    .token(TG_TOKEN)
    .post_init(lambda application: asyncio.create_task(main_loop()))
    .build()
)

# Keep last summary in memory
app.bot_data["last_summary"] = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


async def fetch_summary() -> dict | None:
    """Fetch the latest flight summary for REGISTRATION."""
    now = datetime.now(timezone.utc)
    frm = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
    to  = now.strftime("%Y-%m-%dT%H:%M:%S")

    url = "https://fr24api.flightradar24.com/api/flight-summary/light"
    headers = {
        "Authorization": f"Bearer {FR24_TOKEN}",
        "Accept": "application/json",
        "Accept-Version": "v1"
    }
    params = {
        "registrations": REGISTRATION,
        "flight_datetime_from": frm,
        "flight_datetime_to": to,
        "limit": 1,
        "sort": "desc"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params, timeout=10) as resp:
            resp.raise_for_status()
            data = await resp.json()
    flights = data.get("data", [])
    return flights[0] if flights else None


def build_message(summary: dict) -> tuple[str, InlineKeyboardMarkup]:
    """Construct the Telegram message and inline keyboard."""
    flight_no = summary.get("flight", "N/A")
    takeoff   = summary.get("datetime_takeoff", "N/A")
    landed    = summary.get("datetime_landed", "N/A")
    hex_code  = summary.get("hex", "")

    text = (
        f"✈️ <b>ZS-CJI Flight Summary</b>\n"
        f"• Flight No: <code>{flight_no}</code>\n"
        f"• Take-off : <code>{takeoff}</code>\n"
        f"• Landed   : <code>{landed}</code>\n"
        f"• Hex Code : <code>{hex_code}</code>"
    )

    url = f"https://www.flightradar24.com/data/flights/{flight_no.lower()}"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("View on FR24", url=url)]])
    return text, kb


async def main_loop():
    """Background task: fetch and send new summaries every POLL_SEC seconds."""
    logging.info("🚀 Starting Flightradar24 polling loop...")
    while True:
        try:
            summary = await fetch_summary()
            if summary and summary != app.bot_data["last_summary"]:
                msg, kb = build_message(summary)
                await app.bot.send_message(
                    chat_id=TG_CHAT,
                    text=msg,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
                app.bot_data["last_summary"] = summary
                logging.info("✅ New summary sent.")
            else:
                logging.info("⏸️ No new summary.")
        except Exception as e:
            logging.error(f"❌ Error fetching/sending summary: {e}")
        await asyncio.sleep(POLL_SEC)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status — report last fetched summary."""
    last = context.bot_data.get("last_summary")
    if last:
        takeoff = last.get("datetime_takeoff", "N/A")
        landed  = last.get("datetime_landed", "N/A")
        text = f"🛰 Last summary:\n• Take-off: {takeoff}\n• Landed: {landed}"
    else:
        text = "⚠️ No flight summary fetched yet."
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)


if __name__ == "__main__":
    # Register the /status command
    app.add_handler(CommandHandler("status", status))
    # Start polling Telegram (and keep the application running)
    app.run_polling()
