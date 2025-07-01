"""
Realtime tracker for Cessna CitationJet ZS-CJI (ICAO-24 3e5671) ➜ Telegram.
Runs forever on Railway.

ENV VARS
  TG_TOKEN : BotFather token for @CJza_bot  
  TG_CHAT  : Numeric chat ID
OPTIONAL
  POLL_SEC : Seconds between queries (default 60)
"""

import asyncio, logging, os
from datetime import datetime, timezone

from python_opensky import OpenSky
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

# Configuration
ICAO24   = "3e5671"  # ZS-CJI's hex code
POLL_SEC = int(os.getenv("POLL_SEC", "60"))
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT  = int(os.getenv("TG_CHAT", "0"))

if not TG_TOKEN or TG_CHAT == 0:
    raise SystemExit("❌ TG_TOKEN and TG_CHAT must be set as environment variables.")

# Initialize APIs
bot = Bot(TG_TOKEN)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

def fmt(v, unit="", mult=1.0, prec=0):
    """Format values with fallback for None"""
    return f"{v*mult:.{prec}f}{unit}" if v is not None else "--"

def build_message(state):
    """Build formatted message with aircraft data"""
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

    # Create interactive buttons
    gmap = f"https://maps.google.com/?q={lat},{lon}"
    osky = f"https://opensky-network.org/aircraft-profile?icao24={ICAO24}"
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📍 View on Map", url=gmap),
        InlineKeyboardButton("🛩️ OpenSky Track", url=osky)
    ]])
    return txt, kb

async def main_loop():
    """Main bot loop - polls OpenSky and sends updates"""
    logging.info("🚀 ZS-CJI Tracker Bot starting...")
    
    async with OpenSky() as opensky:
        while True:
            try:
                # Updated API call for python-opensky 0.2.0
                response = await opensky.get_states(icao24=ICAO24)
                
                if response and response.states:
                    msg, kb = build_message(response.states[0])
                    await bot.send_message(
                        chat_id=TG_CHAT,
                        text=msg,
                        reply_markup=kb,
                        parse_mode=ParseMode.HTML
                    )
                    logging.info("✅ Position update sent to Telegram")
                else:
                    logging.info("⏸️ Aircraft not airborne - no update sent")
                    
            except Exception as e:
                logging.error(f"❌ Error in main loop: {e}")
                
            await asyncio.sleep(POLL_SEC)

if __name__ == "__main__":
    asyncio.run(main_loop())
