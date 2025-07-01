"""
Realtime tracker for Cessna CitationJet ZS-CJI (ICAO-24 3e5671) ➜ Telegram.
Runs forever on Railway.

ENV VARS
  TG_TOKEN : BotFather token for @CJza_bot  
  TG_CHAT  : Numeric chat ID
OPTIONAL
  POLL_SEC : Seconds between queries (default 60)
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timezone

import async_timeout
from python_opensky import OpenSky
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Configuration
ICAO24   = "3e5671"  # ZS-CJI's hex code
POLL_SEC = int(os.getenv("POLL_SEC", "60"))
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT  = int(os.getenv("TG_CHAT", "0"))

if not TG_TOKEN or TG_CHAT == 0:
    raise SystemExit("❌ TG_TOKEN and TG_CHAT must be set as environment variables.")

# Initialize Application
app = (
    ApplicationBuilder()
    .token(TG_TOKEN)
    .post_init(lambda application: asyncio.create_task(on_startup(application)))
    .build()
)

# Store startup time and last known state
app.bot_data["start_time"] = time.time()
app.bot_data["last_state"] = None

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")


def fmt(v, unit="", mult=1.0, prec=0):
    """Format numeric values with fallback for None."""
    return f"{v*mult:.{prec}f}{unit}" if v is not None else "--"


def build_message(state):
    """Build formatted message with aircraft data."""
    # Altitude: prefer geometric, fallback to barometric
    alt = fmt(state.geometric_altitude, " m") if state.geometric_altitude else fmt(state.barometric_altitude, " m")
    vel = fmt(state.velocity, " kt", 1.943)
    lat = fmt(state.latitude, "", 1.0, 3)
    lon = fmt(state.longitude, "", 1.0, 3)
    head = fmt(state.true_track, "°")
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

    txt = (
        f"✈️ <b>ZS-CJI Live Position</b>\n"
        f"📍 <code>{lat}</code>, <code>{lon}</code>\n"
        f"🏔️ Alt {alt}   🏃 Spd {vel}   🧭 Hdg {head}\n"
        f"🕐 <i>{ts}</i>"
    )

    gmap = f"https://maps.google.com/?q={lat},{lon}"
    osky = f"https://opensky-network.org/aircraft-profile?icao24={ICAO24}"
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📍 View on Map", url=gmap),
        InlineKeyboardButton("🛩️ OpenSky Track", url=osky)
    ]])
    return txt, kb


async def on_startup(application):
    """Send startup confirmation and launch the background polling."""
    await application.bot.send_message(
        chat_id=TG_CHAT,
        text="✅ ZS-CJI Tracker Bot is now online and connected to Telegram!"
    )
    asyncio.create_task(main_loop())


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to /status with bot uptime and last known aircraft position."""
    uptime = time.time() - context.bot_data["start_time"]
    hrs, rem = divmod(int(uptime), 3600)
    mins, secs = divmod(rem, 60)
    last = context.bot_data["last_state"]
    if last:
        lat = f"{last.latitude:.3f}"
        lon = f"{last.longitude:.3f}"
        alt = f"{last.geometric_altitude:.0f} m" if last.geometric_altitude else "--"
        loc = f"📍 {lat}, {lon}  🏔️ {alt}"
    else:
        loc = "No aircraft data yet."
    text = (
        f"🤖 Bot Uptime: {hrs}h {mins}m {secs}s\n"
        f"🚀 Poll Interval: {POLL_SEC}s\n"
        f"🔄 Last Update: {loc}"
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)


async def main_loop():
    """Poll OpenSky for ZS-CJI and send updates to Telegram."""
    logging.info("🚀 ZS-CJI Tracker Bot starting polling loop...")
    async with OpenSky() as opensky:
        while True:
            try:
                async with async_timeout.timeout(10):
                    response = await opensky.get_states()
                # Filter for ZS-CJI
                states = [s for s in response.states if s.icao24.lower() == ICAO24.lower()] if response.states else []
                if states:
                    state = states[0]
                    app.bot_data["last_state"] = state
                    msg, kb = build_message(state)
                    await app.bot.send_message(
                        chat_id=TG_CHAT,
                        text=msg,
                        reply_markup=kb,
                        parse_mode=ParseMode.HTML
                    )
                    logging.info("✅ Position update sent.")
                else:
                    logging.info("⏸️ Aircraft not airborne; no update.")
            except Exception as e:
                logging.error(f"❌ Main loop error: {e}")
            await asyncio.sleep(POLL_SEC)


if __name__ == "__main__":
    # Register /status command
    app.add_handler(CommandHandler("status", status))
    # Start polling and idle
    app.run_polling()
