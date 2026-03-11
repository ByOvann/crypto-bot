"""
===========================================
  Telegram Crypto Bot — BTC + Fear & Greed
  By: Claude | Stack: python-telegram-bot
===========================================
SETUP:
  pip install python-telegram-bot apscheduler requests

JALANKAN:
  python crypto_bot.py
"""

import logging
import requests
from datetime import datetime
from telegram import Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio

# ─────────────────────────────────────────
#  KONFIGURASI — ISI DI SINI
# ─────────────────────────────────────────
BOT_TOKEN = "8663484684:AAH0kJ0TgpYAaG6NMzxJ0-OKWwg4T0pnNX4"
GROUP_ID  = "-1003714160870"

# Jadwal kirim otomatis (format 24 jam, WIB = UTC+7)
# Railway server pakai UTC, jadi jam WIB dikurangi 7
# WIB 07:00 = UTC 00:00 | WIB 11:00 = UTC 04:00 | dst
JADWAL = [
    {"jam": 0,  "menit": 0, "label": "🕖 Update 07:00 WIB"},
    {"jam": 4,  "menit": 0, "label": "🕚 Update 11:00 WIB"},
    {"jam": 8,  "menit": 0, "label": "🕒 Update 15:00 WIB"},
    {"jam": 12, "menit": 0, "label": "🕖 Update 19:00 WIB"},
    {"jam": 16, "menit": 0, "label": "🕚 Update 23:00 WIB"},
    {"jam": 20, "menit": 0, "label": "🕒 Update 03:00 WIB"},
]
# ─────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ──────────────── API FUNCTIONS ───────────────────

def get_btc_price():
    """Ambil harga BTC dari CoinGecko (gratis, tanpa API key)"""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": "bitcoin",
            "vs_currencies": "usd,idr",
            "include_24hr_change": "true",
            "include_24hr_vol": "true",
            "include_market_cap": "true"
        }
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()["bitcoin"]
        return {
            "usd":       data["usd"],
            "idr":       data["idr"],
            "change24h": data["usd_24h_change"],
            "vol24h":    data["usd_24h_vol"],
            "mcap":      data["usd_market_cap"],
        }
    except Exception as e:
        logging.error(f"Error get BTC price: {e}")
        return None

def get_fear_greed():
    """Ambil Fear & Greed Index dari alternative.me"""
    try:
        r = requests.get("https://api.alternative.me/fng/", timeout=10)
        r.raise_for_status()
        data = r.json()["data"][0]
        return {
            "value":       int(data["value"]),
            "label":       data["value_classification"],
            "time_update": data["time_until_update"]
        }
    except Exception as e:
        logging.error(f"Error get Fear & Greed: {e}")
        return None

# ──────────────── FORMAT PESAN ───────────────────

def format_message(label_waktu: str) -> str:
    btc = get_btc_price()
    fg  = get_fear_greed()
    now = datetime.now().strftime("%d %b %Y | %H:%M WIB")

    # emoji perubahan harga
    if btc:
        change = btc["change24h"]
        arrow  = "🟢" if change >= 0 else "🔴"
        sign   = "+" if change >= 0 else ""
        btc_block = (
            f"💰 *Bitcoin (BTC)*\n"
            f"   USD  : `${btc['usd']:,.2f}`\n"
            f"   IDR  : `Rp {btc['idr']:,.0f}`\n"
            f"   24h  : {arrow} `{sign}{change:.2f}%`\n"
            f"   Vol  : `${btc['vol24h']/1e9:.2f}B`\n"
            f"   MCap : `${btc['mcap']/1e12:.3f}T`"
        )
    else:
        btc_block = "❌ Gagal mengambil data BTC"

    # fear & greed emoji
    if fg:
        score = fg["value"]
        if   score <= 24: fg_emoji = "😱"
        elif score <= 44: fg_emoji = "😟"
        elif score <= 54: fg_emoji = "😐"
        elif score <= 74: fg_emoji = "😊"
        else:             fg_emoji = "🤑"

        fg_block = (
            f"\n📊 *Fear & Greed Index*\n"
            f"   {fg_emoji} `{score}/100` — {fg['label']}"
        )
    else:
        fg_block = "\n❌ Gagal mengambil Fear & Greed"

    msg = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 *{label_waktu}*\n"
        f"🕐 {now}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{btc_block}"
        f"{fg_block}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"_Data: CoinGecko & Alternative.me_"
    )
    return msg

# ──────────────── SCHEDULER JOB ───────────────────

async def kirim_update(bot: Bot, label: str):
    msg = format_message(label)
    try:
        await bot.send_message(
            chat_id=GROUP_ID,
            text=msg,
            parse_mode="Markdown"
        )
        logging.info(f"✅ Pesan terkirim: {label}")
    except Exception as e:
        logging.error(f"Gagal kirim pesan: {e}")

# ──────────────── COMMAND HANDLERS ───────────────────

async def cmd_start(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Halo! Saya *Crypto Bot*\n\n"
        "Perintah yang tersedia:\n"
        "• /btc — Harga BTC sekarang\n"
        "• /fg — Fear & Greed Index\n"
        "• /info — Info bot",
        parse_mode="Markdown"
    )

async def cmd_btc(update, context: ContextTypes.DEFAULT_TYPE):
    msg = format_message("Update Manual")
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_fg(update, context: ContextTypes.DEFAULT_TYPE):
    fg = get_fear_greed()
    if fg:
        score = fg["value"]
        if   score <= 24: emoji = "😱 Extreme Fear"
        elif score <= 44: emoji = "😟 Fear"
        elif score <= 54: emoji = "😐 Neutral"
        elif score <= 74: emoji = "😊 Greed"
        else:             emoji = "🤑 Extreme Greed"

        msg = (
            f"📊 *Fear & Greed Index*\n\n"
            f"Score : `{score}/100`\n"
            f"Status: {emoji}\n\n"
            f"_Diperbarui setiap hari_"
        )
    else:
        msg = "❌ Gagal mengambil data Fear & Greed"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_info(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Crypto Bot Info*\n\n"
        "📡 Sumber data: CoinGecko, Alternative.me\n"
        "⏰ Update otomatis:\n"
        "   • 08:00 WIB — Market Asia\n"
        "   • 15:00 WIB — Market Eropa\n"
        "   • 21:30 WIB — Market Amerika\n\n"
        "🛠 Made with python-telegram-bot",
        parse_mode="Markdown"
    )

# ──────────────── MAIN ───────────────────

async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Daftarkan commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("btc",   cmd_btc))
    app.add_handler(CommandHandler("fg",    cmd_fg))
    app.add_handler(CommandHandler("info",  cmd_info))

    # Setup scheduler
    scheduler = AsyncIOScheduler(timezone="UTC")
    for jadwal in JADWAL:
        scheduler.add_job(
            kirim_update,
            trigger="cron",
            hour=jadwal["jam"],
            minute=jadwal["menit"],
            args=[app.bot, jadwal["label"]]
        )
    scheduler.start()
    logging.info("✅ Bot aktif | Scheduler berjalan...")

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    # Jaga bot tetap berjalan
    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
