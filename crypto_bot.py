
import logging
import requests
import os
import json
from datetime import datetime
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio

# ─────────────────────────────────────────
#  KONFIGURASI
# ─────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8663484684:AAH0kJ0TgpYAaG6NMzxJ0-OKWwg4T0pnNX4")
GROUP_ID  = os.environ.get("GROUP_ID", "-1003714160870")

JADWAL = [
    {"jam": 0,  "menit": 0, "label": "🕖 Update 07:00 WIB"},
    {"jam": 4,  "menit": 0, "label": "🕚 Update 11:00 WIB"},
    {"jam": 8,  "menit": 0, "label": "🕒 Update 15:00 WIB"},
    {"jam": 12, "menit": 0, "label": "🕖 Update 19:00 WIB"},
    {"jam": 16, "menit": 0, "label": "🕚 Update 23:00 WIB"},
    {"jam": 20, "menit": 0, "label": "🕒 Update 03:00 WIB"},
]

# Semua jam dalam UTC (WIB - 7)
# 20:00 WIB = 13:00 UTC → leaderboard harian
# 07:00 WIB = 00:00 UTC → rekap mingguan & bulanan
# ─────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ──────────────── STORAGE ───────────────────
# 3 file terpisah: harian, mingguan, bulanan
FILE_HARIAN   = "data_harian.json"
FILE_MINGGUAN = "data_mingguan.json"
FILE_BULANAN  = "data_bulanan.json"

def load_data(filepath: str) -> dict:
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_data(filepath: str, data: dict):
    with open(filepath, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def tambah_pesan(user_id: str, nama: str, username: str):
    """Catat pesan ke semua 3 periode sekaligus"""
    for filepath in [FILE_HARIAN, FILE_MINGGUAN, FILE_BULANAN]:
        data = load_data(filepath)
        if user_id not in data:
            data[user_id] = {"nama": nama, "username": username, "pesan": 0}
        data[user_id]["pesan"]    += 1
        data[user_id]["nama"]      = nama
        data[user_id]["username"]  = username
        save_data(filepath, data)

def reset_data(filepath: str):
    save_data(filepath, {})
    logging.info(f"🔄 Reset: {filepath}")

# ──────────────── FORMAT LEADERBOARD ───────────────────

def format_leaderboard(filepath: str, judul: str, periode: str) -> str:
    data = load_data(filepath)
    now  = datetime.now().strftime("%d %b %Y")
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

    if not data:
        return (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{judul}\n"
            f"📅 {periode}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Belum ada aktivitas tercatat.\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

    sorted_members = sorted(data.items(), key=lambda x: x[1]["pesan"], reverse=True)
    top5 = sorted_members[:5]

    rows = ""
    for i, (uid, info) in enumerate(top5):
        username = f"@{info['username']}" if info["username"] else info["nama"]
        pesan    = info["pesan"]
        rows += f"{medals[i]} {username} — `{pesan} pesan`\n"

    # Hitung total pesan & total member aktif
    total_pesan   = sum(v["pesan"] for v in data.values())
    total_member  = len(data)

    msg = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{judul}\n"
        f"📅 {periode}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{rows}\n"
        f"📊 Total pesan  : `{total_pesan}`\n"
        f"👥 Member aktif : `{total_member} orang`\n\n"
        f"💬 _Terus semangat berdiskusi!_ 🚀\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    return msg

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

# ──────────────── FORMAT PESAN HARGA ───────────────────

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

    return (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 *{label_waktu}*\n"
        f"🕐 {now}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{btc_block}"
        f"{fg_block}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"_Data: CoinGecko & Alternative.me_"
    )

# ──────────────── SCHEDULER JOBS ───────────────────

async def kirim_update(bot: Bot, label: str):
    msg = format_message(label)
    try:
        await bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode="Markdown")
        logging.info(f"✅ Harga terkirim: {label}")
    except Exception as e:
        logging.error(f"Gagal kirim harga: {e}")

async def kirim_leaderboard_harian(bot: Bot):
    """Setiap hari jam 20:00 WIB"""
    now    = datetime.now()
    periode = now.strftime("%d %b %Y")
    msg    = format_leaderboard(FILE_HARIAN, "🏆 *Leaderboard Harian*", periode)
    try:
        await bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode="Markdown")
        logging.info("✅ Leaderboard harian terkirim")
        reset_data(FILE_HARIAN)
    except Exception as e:
        logging.error(f"Gagal kirim leaderboard harian: {e}")

async def kirim_leaderboard_mingguan(bot: Bot):
    """Setiap Senin jam 07:00 WIB"""
    now     = datetime.now()
    # Hitung rentang minggu lalu (Senin - Minggu)
    from datetime import timedelta
    senin   = (now - timedelta(days=7)).strftime("%d %b")
    minggu  = (now - timedelta(days=1)).strftime("%d %b %Y")
    periode = f"{senin} – {minggu}"
    msg     = format_leaderboard(FILE_MINGGUAN, "📅 *Rekap Mingguan*", periode)
    try:
        await bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode="Markdown")
        logging.info("✅ Leaderboard mingguan terkirim")
        reset_data(FILE_MINGGUAN)
    except Exception as e:
        logging.error(f"Gagal kirim leaderboard mingguan: {e}")

async def kirim_leaderboard_bulanan(bot: Bot):
    """Setiap tanggal 1 jam 07:00 WIB"""
    now     = datetime.now()
    # Nama bulan yang baru saja selesai
    from datetime import timedelta
    bulan_lalu = (now - timedelta(days=1)).strftime("%B %Y")
    msg     = format_leaderboard(FILE_BULANAN, "📆 *Rekap Bulanan*", bulan_lalu)
    try:
        await bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode="Markdown")
        logging.info("✅ Leaderboard bulanan terkirim")
        reset_data(FILE_BULANAN)
    except Exception as e:
        logging.error(f"Gagal kirim leaderboard bulanan: {e}")

# ──────────────── MESSAGE TRACKER ───────────────────

async def track_pesan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if user and not user.is_bot:
        user_id  = str(user.id)
        nama     = user.first_name or ""
        if user.last_name:
            nama += f" {user.last_name}"
        username = user.username or ""
        tambah_pesan(user_id, nama, username)

# ──────────────── COMMAND HANDLERS ───────────────────

async def cmd_start(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Halo! Saya *BlockStation Crypto Bot*\n\n"
        "Perintah yang tersedia:\n"
        "• /btc — Harga BTC sekarang\n"
        "• /fg — Fear & Greed Index\n"
        "• /top — Leaderboard hari ini\n"
        "• /topweek — Rekap minggu ini\n"
        "• /topmonth — Rekap bulan ini\n"
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

async def cmd_top(update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now().strftime("%d %b %Y")
    msg = format_leaderboard(FILE_HARIAN, "🏆 *Leaderboard Harian*", now)
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_topweek(update, context: ContextTypes.DEFAULT_TYPE):
    from datetime import timedelta
    now    = datetime.now()
    senin  = (now - timedelta(days=now.weekday())).strftime("%d %b")
    hari_ini = now.strftime("%d %b %Y")
    periode = f"{senin} – {hari_ini}"
    msg    = format_leaderboard(FILE_MINGGUAN, "📅 *Rekap Minggu Ini*", periode)
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_topmonth(update, context: ContextTypes.DEFAULT_TYPE):
    periode = datetime.now().strftime("%B %Y")
    msg     = format_leaderboard(FILE_BULANAN, "📆 *Rekap Bulan Ini*", periode)
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_info(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *BlockStation Crypto Bot*\n\n"
        "📡 Sumber data: CoinGecko, Alternative.me\n\n"
        "⏰ Update harga otomatis:\n"
        "   • 07:00 | 11:00 | 15:00 WIB\n"
        "   • 19:00 | 23:00 | 03:00 WIB\n\n"
        "🏆 Leaderboard otomatis:\n"
        "   • Harian  — setiap 20:00 WIB\n"
        "   • Mingguan — setiap Senin 07:00 WIB\n"
        "   • Bulanan  — setiap tgl 1, 07:00 WIB\n\n"
        "🛠 Made with python-telegram-bot",
        parse_mode="Markdown"
    )

# ──────────────── WELCOME NEW MEMBER ───────────────────

async def welcome_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        nama     = member.first_name or ""
        if member.last_name:
            nama += f" {member.last_name}"
        username = f"@{member.username}" if member.username else nama
        btc      = get_btc_price()
        harga_info = f"\n\n💰 *BTC saat ini:* `${btc['usd']:,.2f}` ({btc['change24h']:+.2f}%)" if btc else ""
        msg = (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎉 *Selamat Datang!*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Halo {username}! 👋\n"
            f"Selamat bergabung di *BlockStation* 🚀\n\n"
            f"📌 *Yang bisa kamu temukan di sini:*\n"
            f"   • Update harga BTC setiap 4 jam\n"
            f"   • Fear & Greed Index harian\n"
            f"   • 🏆 Leaderboard harian, mingguan & bulanan\n"
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

    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("btc",       cmd_btc))
    app.add_handler(CommandHandler("fg",        cmd_fg))
    app.add_handler(CommandHandler("top",       cmd_top))
    app.add_handler(CommandHandler("topweek",   cmd_topweek))
    app.add_handler(CommandHandler("topmonth",  cmd_topmonth))
    app.add_handler(CommandHandler("info",      cmd_info))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_member))
    app.add_handler(MessageHandler(filters.TEXT & filters.Chat(int(GROUP_ID)), track_pesan))

    scheduler = AsyncIOScheduler(timezone="UTC")

    # Update harga 6x sehari
    for jadwal in JADWAL:
        scheduler.add_job(kirim_update, trigger="cron",
            hour=jadwal["jam"], minute=jadwal["menit"],
            args=[app.bot, jadwal["label"]])

    # Leaderboard harian — 20:00 WIB = 13:00 UTC
    scheduler.add_job(kirim_leaderboard_harian, trigger="cron",
        hour=13, minute=0, args=[app.bot])

    # Leaderboard mingguan — Senin 07:00 WIB = 00:00 UTC
    scheduler.add_job(kirim_leaderboard_mingguan, trigger="cron",
        day_of_week="mon", hour=0, minute=0, args=[app.bot])

    # Leaderboard bulanan — tanggal 1, 07:00 WIB = 00:00 UTC
    scheduler.add_job(kirim_leaderboard_bulanan, trigger="cron",
        day=1, hour=0, minute=0, args=[app.bot])

    scheduler.start()
    logging.info("✅ Bot aktif | Harian + Mingguan + Bulanan scheduler berjalan...")

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
