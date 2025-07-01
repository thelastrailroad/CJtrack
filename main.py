"""
Realtime ZS-CJI flight summary ➜ Telegram using Flightradar24 API

ENV VARS
  TG_TOKEN   : Telegram BotFather token (@CJza_bot)
  TG_CHAT    : Numeric chat ID
  FR24_TOKEN : Flightradar24 API Bearer token
OPTIONAL
  POLL_SEC   : Seconds between queries (default 60)
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone

import aiohttp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Configuration
POLL_SEC    = int(os.getenv("POLL_SEC", "60"))
TG_TOKEN    = os.getenv("TG_TOKEN")
TG_CHAT     = int(os.getenv("TG_CHAT", "0"))
FR24_TOKEN  = os.getenv("FR24_TOKEN")
REGISTRATION = "ZS-CJI"

if not TG_TOKEN or TG_CHAT == 0 or not FR24_TOKEN:
    raise SystemExit("❌ TG_TOKEN, TG_CHAT, and FR24_TOKEN must be set as environment variables.")

# Build the Telegram application
app = ApplicationBuilder().token(TG_TOKEN).build()
app.bot_data["last_summary"] = None


async def fetch_summary() -> dict | None:
    """
    Fetch latest flight summary for ZS-CJI from Flightradar24 Light endpoint.
    """
    now = datetime.now(timezone.utc)
    frm = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
    to  = now.strftime("%Y-%m-%dT%H:%M:%S")

    url = "https://fr24api.flightradar24.com/api/flight-summary/light"
    headers = {
        "Authorization": f"Bearer {FR24_TOKEN}",
        "Accept": "application/json",
        "Accept-Version": "v1",
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
    """
    Build a formatted Telegram message and inline buttons.
    """
    takeoff = summary.get("datetime_takeoff", "N/A")
    landed  = summary.get("datetime_landed", "N/A")
    flight  = summary.get("flight", "")
    hex_    = summary.get("hex", "")

    text = (
        f"✈️ <b>ZS-CJI Flight Summary</b>\n"
        f"• Flight No: <code>{flight}</code>\n"
        f"• Take-off: <code>{takeoff}</code>\n"
        f"• Landed:   <code>{landed}</code>\n"
        f"• Hex:      <code>{hex_}</code>"
    )

    url = f"https://www.flightradar24.com/data/flights/{flight.lower()}"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("View on FR24", url=url)]])
    return text, kb


async def main_loop():
    """
    Periodically fetch and send flight summary updates.
    """
    while True:
        try:
            summary = await fetch_summary()
            if summary and summary != app.bot_data["last_summary"]:
                msg, kb = build_message(summary)
                await app.bot.send_message(
                    chat_id=TG_CHAT,
                    text=msg,
                    reply_markup=kb,
                    parse_mode=ParseMode.HTML
                )
                app.bot_data["last_summary"] = summary
        except Exception as e:
            # Log or notify on errors if desired
            print("Error fetching or sending summary:", e)
        await asyncio.sleep(POLL_SEC)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Reply to /status with last fetched summary or notice.
    """
    last = context.bot_data.get("last_summary")
    if last:
        takeoff = last.get("datetime_takeoff", "N/A")
        landed  = last.get("datetime_landed", "N/A")
        text = f"🛰 Last summary:\nTake-off: {takeoff}\nLanded: {landed}"
    else:
        text = "⚠️ No flight summary fetched yet."
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)


if __name__ == "__main__":
    # Register /status handler
    app.add_handler(CommandHandler("status", status))
    # Start background polling
    asyncio.create_task(main_loop())
    # Run the bot
    app.run_polling()
