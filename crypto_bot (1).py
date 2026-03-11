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
import os
from datetime import datetime
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio

# ─────────────────────────────────────────
#  KONFIGURASI
# ─────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "ISI_TOKEN_BOT_KAMU")
GROUP_ID  = os.environ.get("GROUP_ID",  "ISI_GROUP_ID_KAMU")

# Jadwal kirim otomatis (UTC = WIB - 7)
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
    try:
        r = requests.get("https://api.alternative.me/fng/", timeout=10)
        r.raise_for_status()
        data = r.json()["data"][0]
        return {
            "value": int(data["value"]),
            "label": data["value_classification"],
        }
    except Exception as e:
        logging.error(f"Error get Fear & Greed: {e}")
        return None

# ──────────────── FORMAT PESAN ───────────────────

def format_message(label_waktu: str) -> str:
    btc = get_btc_price()
    fg  = get_fear_greed()
    now = datetime.now().strftime("%d %b %Y | %H:%M WIB")

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
        "👋 Halo! Saya *BlockStation Crypto Bot*\n\n"
        "Perintah yang tersedia:\n"
        "• /btc — Harga BTC sekarang\n"
        "• /fg — Fear & Greed Index\n"
        "• /info — Info bot & jadwal",
        parse_mode="Markdown"
    )

async def cmd_btc(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Mengambil data, sebentar...")
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
        "🤖 *BlockStation Crypto Bot*\n\n"
        "📡 Sumber data: CoinGecko, Alternative.me\n\n"
        "⏰ Update otomatis:\n"
        "   • 07:00 WIB\n"
        "   • 11:00 WIB\n"
        "   • 15:00 WIB\n"
        "   • 19:00 WIB\n"
        "   • 23:00 WIB\n"
        "   • 03:00 WIB\n\n"
        "🛠 Made with python-telegram-bot",
        parse_mode="Markdown"
    )

# ──────────────── WELCOME NEW MEMBER ───────────────────

async def welcome_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue

        nama = member.first_name
        if member.last_name:
            nama += f" {member.last_name}"
        username = f"@{member.username}" if member.username else nama

        btc = get_btc_price()
        if btc:
            harga_info = f"\n\n💰 *BTC saat ini:* `${btc['usd']:,.2f}` ({btc['change24h']:+.2f}%)"
        else:
            harga_info = ""

        msg = (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎉 *Selamat Datang!*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Halo {username}! 👋\n"
            f"Selamat bergabung di *BlockStation* 🚀\n\n"
            f"📌 *Yang bisa kamu temukan di sini:*\n"
            f"   • Update harga BTC setiap 4 jam\n"
            f"   • Fear & Greed Index harian\n"
            f"   • Diskusi & info terkini seputar crypto"
            f"{harga_info}\n\n"
            f"💬 Ketik /start untuk lihat fitur bot\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        await update.message.reply_text(msg, parse_mode="Markdown")
        logging.info(f"✅ Welcome terkirim untuk: {nama}")

# ──────────────── MAIN ───────────────────

async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("btc",   cmd_btc))
    app.add_handler(CommandHandler("fg",    cmd_fg))
    app.add_handler(CommandHandler("info",  cmd_info))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_member))

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

    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
