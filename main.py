"""
Realtime tracker for Cessna CitationJet ZS-CJI (ICAO-24 3e5671) ➜ Telegram.
Uses direct OpenSky API calls to avoid dependency issues.
"""

import asyncio, logging, os
from datetime import datetime, timezone
import aiohttp

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

async def get_aircraft_data():
    """Fetch aircraft data directly from OpenSky REST API"""
    url = f"https://opensky-network.org/api/states/all?icao24={ICAO24}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('states') and len(data['states']) > 0:
                        return data['states'][0]  # First aircraft state
        return None
    except Exception as e:
        logging.error(f"OpenSky API error: {e}")
        return None

def build_message(state_data):
    """Build formatted message with aircraft data from raw API response"""
    # OpenSky API returns array: [icao24, callsign, origin_country, time_position, 
    # last_contact, longitude, latitude, baro_altitude, on_ground, velocity, 
    # true_track, vertical_rate, sensors, geo_altitude, squawk, spi, position_source]
    
    if not state_data or len(state_data) < 14:
        return None, None
        
    longitude = state_data[5]
    latitude = state_data[6]
    baro_altitude = state_data[7]
    geo_altitude = state_data[13]
    velocity = state_data[9]
    true_track = state_data[10]
    
    alt = fmt(geo_altitude, " m") if geo_altitude else fmt(baro_altitude, " m")
    vel = fmt(velocity, " kt", 1.943)
    lat = fmt(latitude, "", 1.0, 3)
    lon = fmt(longitude, "", 1.0, 3)
    head = fmt(true_track, "°")
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
    
    while True:
        try:
            state_data = await get_aircraft_data()
            
            if state_data:
                msg, kb = build_message(state_data)
                if msg:
                    await bot.send_message(
                        chat_id=TG_CHAT,
                        text=msg,
                        reply_markup=kb,
                        parse_mode=ParseMode.HTML
                    )
                    logging.info("✅ Position update sent to Telegram")
                else:
                    logging.info("⏸️ Invalid aircraft data received")
            else:
                logging.info("⏸️ Aircraft not airborne - no update sent")
                
        except Exception as e:
            logging.error(f"❌ Error in main loop: {e}")
            
        await asyncio.sleep(POLL_SEC)

if __name__ == "__main__":
    asyncio.run(main_loop())
