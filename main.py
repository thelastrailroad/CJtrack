"""
Realtime ZS-CJI flight summary ➜ Telegram using Flightradar24 API

ENV VARS
  TG_TOKEN   : Your Telegram Bot API token
  TG_CHAT    : Numeric chat ID
  FR24_TOKEN : Your Flightradar24 API Bearer token
OPTIONAL
  POLL_SEC   : Seconds between queries (default 60)
"""

import logging
import os
from datetime import datetime, timedelta, timezone

import aiohttp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import Conflict
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, JobQueue

# --- Configuration ------------------------------------------------------------

POLL_SEC     = int(os.getenv("POLL_SEC", "60"))
TG_TOKEN     = os.getenv("TG_TOKEN")
TG_CHAT      = int(os.getenv("TG_CHAT", "0"))
FR24_TOKEN   = os.getenv("FR24_TOKEN")
REGISTRATION = "ZS-CJI"

if not (TG_TOKEN and TG_CHAT and FR24_TOKEN):
    raise SystemExit("❌ Set TG_TOKEN, TG_CHAT, and FR24_TOKEN environment variables.")

# --- Logging ------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# --- Telegram Application ----------------------------------------------------

app = ApplicationBuilder().token(TG_TOKEN).build()
app.bot_data["last_summary"] = None

# --- Error Handler ------------------------------------------------------------

async def ignore_conflict(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if isinstance(context.error, Conflict):
        logging.warning("🔄 Ignored Conflict error: another getUpdates session is active")
    else:
        raise context.error

app.add_error_handler(ignore_conflict)

# --- FlightRadar24 Fetch Logic -----------------------------------------------

async def fetch_summary() -> dict | None:
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
    # Use empty string if field is missing or null
    flight_no = summary.get("flight") or "N/A"
    takeoff   = summary.get("datetime_takeoff") or "N/A"
    landed    = summary.get("datetime_landed") or "N/A"
    hex_code  = summary.get("hex") or "N/A"

    text = (
        f"✈️ <b>ZS-CJI Flight Summary</b>\n"
        f"• Flight No: <code>{flight_no}</code>\n"
        f"• Take-off : <code>{takeoff}</code>\n"
        f"• Landed   : <code>{landed}</code>\n"
        f"• Hex Code : <code>{hex_code}</code>"
    )

    # Only build URL if flight_no is not "N/A"
    if flight_no != "N/A":
        url = f"https://www.flightradar24.com/data/flights/{flight_no.lower()}"
        kb  = InlineKeyboardMarkup([[InlineKeyboardButton("View on FR24", url=url)]])
    else:
        kb = InlineKeyboardMarkup([])

    return text, kb

# --- Job Callback -------------------------------------------------------------

async def polling_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    summary = await fetch_summary()
    if summary and summary != context.bot_data["last_summary"]:
        msg, kb = build_message(summary)
        await context.bot.send_message(
            chat_id=TG_CHAT,
            text=msg,
            reply_markup=kb,
            parse_mode="HTML"
        )
        context.bot_data["last_summary"] = summary
        logging.info("✅ New summary sent.")
    else:
        logging.info("⏸️ No new summary.")

# --- /status Command Handler -------------------------------------------------

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    last = context.bot_data.get("last_summary")
    if last:
        takeoff = last.get("datetime_takeoff") or "N/A"
        landed  = last.get("datetime_landed") or "N/A"
        text = f"🛰 Last summary:\n• Take-off: {takeoff}\n• Landed: {landed}"
    else:
        text = "⚠️ No flight summary fetched yet."
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

# --- Application Setup -------------------------------------------------------

# Register /status command
app.add_handler(CommandHandler("status", status))

# Schedule polling_job
job_queue: JobQueue = app.job_queue
job_queue.run_repeating(polling_job, interval=POLL_SEC, first=0)

# --- Run Bot -----------------------------------------------------------------

if __name__ == "__main__":
    logging.info("🚀 Starting Telegram bot with FlightRadar24 polling...")
    app.run_polling(drop_pending_updates=True)
