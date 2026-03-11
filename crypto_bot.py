"""
===========================================
  Telegram Crypto Bot — BlockStation
  Fitur: Harga BTC, Leaderboard, Berita, Kuis
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
import json
from datetime import datetime, timedelta
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler,
                           CallbackQueryHandler, filters, ContextTypes)
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

POIN_BENAR = 3
POIN_SALAH = 5   # dikurangi
# ─────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ──────────────── STORAGE ───────────────────
FILE_HARIAN   = "data_harian.json"
FILE_MINGGUAN = "data_mingguan.json"
FILE_BULANAN  = "data_bulanan.json"
FILE_KUIS     = "data_kuis.json"   # jawaban kuis aktif saat ini

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

def reset_data(filepath: str):
    save_data(filepath, {})
    logging.info(f"🔄 Reset: {filepath}")

def tambah_pesan(user_id: str, nama: str, username: str):
    for filepath in [FILE_HARIAN, FILE_MINGGUAN, FILE_BULANAN]:
        data = load_data(filepath)
        if user_id not in data:
            data[user_id] = {"nama": nama, "username": username, "pesan": 0, "poin": 0}
        data[user_id]["pesan"]   += 1
        data[user_id]["nama"]     = nama
        data[user_id]["username"] = username
        if "poin" not in data[user_id]:
            data[user_id]["poin"] = 0
        save_data(filepath, data)

def update_poin(user_id: str, nama: str, username: str, delta: int):
    """Tambah atau kurangi poin di semua periode"""
    for filepath in [FILE_HARIAN, FILE_MINGGUAN, FILE_BULANAN]:
        data = load_data(filepath)
        if user_id not in data:
            data[user_id] = {"nama": nama, "username": username, "pesan": 0, "poin": 0}
        if "poin" not in data[user_id]:
            data[user_id]["poin"] = 0
        data[user_id]["poin"] = max(0, data[user_id]["poin"] + delta)
        data[user_id]["nama"]     = nama
        data[user_id]["username"] = username
        save_data(filepath, data)

# ──────────────── FORMAT LEADERBOARD ───────────────────

def format_leaderboard(filepath: str, judul: str, periode: str) -> str:
    data   = load_data(filepath)
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

    if not data:
        return (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{judul}\n📅 {periode}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Belum ada aktivitas tercatat.\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

    sorted_members = sorted(
        data.items(),
        key=lambda x: (x[1].get("poin", 0), x[1]["pesan"]),
        reverse=True
    )
    top5  = sorted_members[:5]
    rows  = ""
    for i, (uid, info) in enumerate(top5):
        username = f"@{info['username']}" if info["username"] else info["nama"]
        pesan    = info["pesan"]
        poin     = info.get("poin", 0)
        rows += f"{medals[i]} {username} — `{pesan} pesan` | `{poin} poin`\n"

    total_pesan  = sum(v["pesan"] for v in data.values())
    total_member = len(data)

    return (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{judul}\n📅 {periode}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{rows}\n"
        f"📊 Total pesan  : `{total_pesan}`\n"
        f"👥 Member aktif : `{total_member} orang`\n\n"
        f"💬 _Terus semangat berdiskusi!_ 🚀\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

# ──────────────── API FUNCTIONS ───────────────────

def get_btc_price():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price", params={
            "ids": "bitcoin", "vs_currencies": "usd,idr",
            "include_24hr_change": "true", "include_24hr_vol": "true",
            "include_market_cap": "true"
        }, timeout=10)
        r.raise_for_status()
        d = r.json()["bitcoin"]
        return {"usd": d["usd"], "idr": d["idr"], "change24h": d["usd_24h_change"],
                "vol24h": d["usd_24h_vol"], "mcap": d["usd_market_cap"]}
    except Exception as e:
        logging.error(f"Error get BTC: {e}")
        return None

def get_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/", timeout=10)
        r.raise_for_status()
        d = r.json()["data"][0]
        return {"value": int(d["value"]), "label": d["value_classification"]}
    except Exception as e:
        logging.error(f"Error get FG: {e}")
        return None

def get_crypto_news():
    """Ambil berita crypto terbaru dari CryptoPanic API (gratis)"""
    try:
        r = requests.get(
            "https://cryptopanic.com/api/v1/posts/",
            params={"auth_token": "free", "public": "true", "kind": "news", "currencies": "BTC"},
            timeout=10
        )
        r.raise_for_status()
        results = r.json().get("results", [])[:5]  # ambil 5 berita teratas
        return results
    except Exception as e:
        logging.error(f"Error get news: {e}")
        return []

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
        fg_block = f"\n📊 *Fear & Greed Index*\n   {fg_emoji} `{score}/100` — {fg['label']}"
    else:
        fg_block = "\n❌ Gagal mengambil Fear & Greed"

    return (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 *{label_waktu}*\n🕐 {now}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{btc_block}{fg_block}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"_Data: CoinGecko & Alternative.me_"
    )

# ──────────────── BERITA CRYPTO ───────────────────

def format_berita() -> str:
    news  = get_crypto_news()
    now   = datetime.now().strftime("%d %b %Y | %H:%M WIB")

    if not news:
        return (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📰 *Berita Crypto Pagi Ini*\n🕐 {now}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"❌ Berita tidak tersedia saat ini.\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

    baris = ""
    for i, item in enumerate(news, 1):
        judul = item.get("title", "No title")
        url   = item.get("url", "")
        src   = item.get("source", {}).get("title", "Unknown")
        baris += f"{i}. [{judul}]({url})\n   _— {src}_\n\n"

    return (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📰 *Berita Crypto Pagi Ini*\n🕐 {now}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{baris}"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"_Sumber: CryptoPanic_"
    )

# ──────────────── KUIS BTC ───────────────────

def buat_opsi_range(harga: float) -> list:
    """Buat 4 pilihan range harga, salah satunya adalah jawaban benar"""
    import random
    step   = 1000  # range per opsi $1000
    base   = int(harga / step) * step
    benar  = f"${base:,} – ${base + step:,}"

    # Buat 3 opsi salah (range berbeda)
    offsets = [-2, -1, 1, 2]
    random.shuffle(offsets)
    salah = [f"${base + (o * step):,} – ${base + (o * step) + step:,}" for o in offsets[:3]]

    semua = [benar] + salah
    random.shuffle(semua)
    return semua, benar

async def kirim_kuis(bot: Bot):
    """Kirim kuis tebak range harga BTC jam 20:00 WIB"""
    btc = get_btc_price()
    if not btc:
        return

    harga_sekarang = btc["usd"]
    opsi, jawaban_benar = buat_opsi_range(harga_sekarang)

    # Simpan jawaban benar & siapa saja yang sudah jawab
    kuis_data = {
        "jawaban_benar": jawaban_benar,
        "harga_saat_kuis": harga_sekarang,
        "sudah_jawab": {},   # {user_id: pilihan_mereka}
        "waktu": datetime.now().strftime("%d %b %Y %H:%M")
    }
    save_data(FILE_KUIS, kuis_data)

    # Buat tombol inline
    keyboard = [[InlineKeyboardButton(o, callback_data=f"kuis:{o}")] for o in opsi]
    reply_markup = InlineKeyboardMarkup(keyboard)

    now = datetime.now().strftime("%d %b %Y | %H:%M WIB")
    msg = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 *Kuis Harian — Tebak Harga BTC!*\n"
        f"🕐 {now}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Harga BTC sekarang: `${harga_sekarang:,.0f}`\n\n"
        f"❓ *Menurut kamu, harga BTC 1 jam lagi akan berada di range mana?*\n\n"
        f"✅ Benar: `+{POIN_BENAR} poin`\n"
        f"❌ Salah: `-{POIN_SALAH} poin`\n\n"
        f"⏰ _Jawaban ditutup dalam 1 jam_"
    )

    try:
        await bot.send_message(
            chat_id=GROUP_ID,
            text=msg,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        logging.info("✅ Kuis terkirim")
    except Exception as e:
        logging.error(f"Gagal kirim kuis: {e}")

async def tutup_kuis(bot: Bot):
    """Tutup kuis 1 jam setelah dibuka, cek jawaban & update poin"""
    kuis = load_data(FILE_KUIS)
    if not kuis or "jawaban_benar" not in kuis:
        return

    jawaban_benar = kuis["jawaban_benar"]
    sudah_jawab   = kuis.get("sudah_jawab", {})
    harga_check   = get_btc_price()
    harga_aktual  = f"${harga_check['usd']:,.0f}" if harga_check else "N/A"

    benar_list = []
    salah_list = []

    for uid, info in sudah_jawab.items():
        nama     = info["nama"]
        username = info["username"]
        pilihan  = info["pilihan"]

        if pilihan == jawaban_benar:
            update_poin(uid, nama, username, +POIN_BENAR)
            tag = f"@{username}" if username else nama
            benar_list.append(tag)
        else:
            update_poin(uid, nama, username, -POIN_SALAH)
            tag = f"@{username}" if username else nama
            salah_list.append(tag)

    benar_str = ", ".join(benar_list) if benar_list else "_Tidak ada_"
    salah_str = ", ".join(salah_list) if salah_list else "_Tidak ada_"

    msg = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 *Hasil Kuis BTC!*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Jawaban benar: `{jawaban_benar}`\n"
        f"Harga aktual : `{harga_aktual}`\n\n"
        f"✅ Benar (+{POIN_BENAR} poin):\n{benar_str}\n\n"
        f"❌ Salah (-{POIN_SALAH} poin):\n{salah_str}\n\n"
        f"🏆 Cek poin kamu: ketik `top`\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    try:
        await bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode="Markdown")
        logging.info("✅ Hasil kuis terkirim")
        reset_data(FILE_KUIS)
    except Exception as e:
        logging.error(f"Gagal kirim hasil kuis: {e}")

# ──────────────── CALLBACK KUIS (tombol jawaban) ───────────────────

async def callback_kuis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not query.data.startswith("kuis:"):
        return

    pilihan  = query.data.replace("kuis:", "")
    user     = query.from_user
    user_id  = str(user.id)
    nama     = user.first_name or ""
    if user.last_name:
        nama += f" {user.last_name}"
    username = user.username or ""

    kuis = load_data(FILE_KUIS)
    if not kuis or "jawaban_benar" not in kuis:
        await query.answer("⏰ Kuis sudah ditutup!", show_alert=True)
        return

    sudah_jawab = kuis.get("sudah_jawab", {})
    if user_id in sudah_jawab:
        await query.answer("⚠️ Kamu sudah menjawab kuis ini!", show_alert=True)
        return

    # Simpan jawaban
    sudah_jawab[user_id] = {"nama": nama, "username": username, "pilihan": pilihan}
    kuis["sudah_jawab"] = sudah_jawab
    save_data(FILE_KUIS, kuis)

    tag = f"@{username}" if username else nama
    await query.answer(f"✅ Jawaban kamu: {pilihan} tercatat!", show_alert=True)
    logging.info(f"📝 {tag} menjawab: {pilihan}")

# ──────────────── SCHEDULER JOBS ───────────────────

async def kirim_update(bot: Bot, label: str):
    try:
        await bot.send_message(chat_id=GROUP_ID, text=format_message(label), parse_mode="Markdown")
        logging.info(f"✅ Harga terkirim: {label}")
    except Exception as e:
        logging.error(f"Gagal kirim harga: {e}")

async def kirim_berita(bot: Bot):
    try:
        await bot.send_message(
            chat_id=GROUP_ID,
            text=format_berita(),
            parse_mode="Markdown",
            disable_web_page_preview=False  # tampilkan preview link
        )
        logging.info("✅ Berita terkirim")
    except Exception as e:
        logging.error(f"Gagal kirim berita: {e}")

async def kirim_leaderboard_harian(bot: Bot):
    periode = datetime.now().strftime("%d %b %Y")
    msg = format_leaderboard(FILE_HARIAN, "🏆 *Leaderboard Harian*", periode)
    try:
        await bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode="Markdown")
        logging.info("✅ Leaderboard harian terkirim")
        reset_data(FILE_HARIAN)
    except Exception as e:
        logging.error(f"Gagal kirim leaderboard harian: {e}")

async def kirim_leaderboard_mingguan(bot: Bot):
    now    = datetime.now()
    senin  = (now - timedelta(days=7)).strftime("%d %b")
    minggu = (now - timedelta(days=1)).strftime("%d %b %Y")
    msg = format_leaderboard(FILE_MINGGUAN, "📅 *Rekap Mingguan*", f"{senin} – {minggu}")
    try:
        await bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode="Markdown")
        logging.info("✅ Leaderboard mingguan terkirim")
        reset_data(FILE_MINGGUAN)
    except Exception as e:
        logging.error(f"Gagal kirim leaderboard mingguan: {e}")

async def kirim_leaderboard_bulanan(bot: Bot):
    bulan_lalu = (datetime.now() - timedelta(days=1)).strftime("%B %Y")
    msg = format_leaderboard(FILE_BULANAN, "📆 *Rekap Bulanan*", bulan_lalu)
    try:
        await bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode="Markdown")
        logging.info("✅ Leaderboard bulanan terkirim")
        reset_data(FILE_BULANAN)
    except Exception as e:
        logging.error(f"Gagal kirim leaderboard bulanan: {e}")

# ──────────────── HANDLE PESAN (tracker + keyword) ───────────────────

async def handle_pesan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not user or user.is_bot:
        return

    user_id  = str(user.id)
    nama     = user.first_name or ""
    if user.last_name:
        nama += f" {user.last_name}"
    username = user.username or ""
    tambah_pesan(user_id, nama, username)

    teks = update.message.text.strip().lower()

    if teks == "btc":
        await update.message.reply_text("⏳ Mengambil data, sebentar...")
        await update.message.reply_text(format_message("Update Manual"), parse_mode="Markdown")

    elif teks == "fg":
        fg = get_fear_greed()
        if fg:
            score = fg["value"]
            if   score <= 24: emoji = "😱 Extreme Fear"
            elif score <= 44: emoji = "😟 Fear"
            elif score <= 54: emoji = "😐 Neutral"
            elif score <= 74: emoji = "😊 Greed"
            else:             emoji = "🤑 Extreme Greed"
            msg = f"📊 *Fear & Greed Index*\n\nScore : `{score}/100`\nStatus: {emoji}\n\n_Diperbarui setiap hari_"
        else:
            msg = "❌ Gagal mengambil data"
        await update.message.reply_text(msg, parse_mode="Markdown")

    elif teks == "news" or teks == "berita":
        await update.message.reply_text("⏳ Mengambil berita terbaru...")
        await update.message.reply_text(format_berita(), parse_mode="Markdown", disable_web_page_preview=False)

    elif teks == "top":
        await update.message.reply_text(
            format_leaderboard(FILE_HARIAN, "🏆 *Leaderboard Harian*", datetime.now().strftime("%d %b %Y")),
            parse_mode="Markdown"
        )
    elif teks == "topweek":
        now     = datetime.now()
        senin   = (now - timedelta(days=now.weekday())).strftime("%d %b")
        hari_ini = now.strftime("%d %b %Y")
        await update.message.reply_text(
            format_leaderboard(FILE_MINGGUAN, "📅 *Rekap Minggu Ini*", f"{senin} – {hari_ini}"),
            parse_mode="Markdown"
        )
    elif teks == "topmonth":
        await update.message.reply_text(
            format_leaderboard(FILE_BULANAN, "📆 *Rekap Bulan Ini*", datetime.now().strftime("%B %Y")),
            parse_mode="Markdown"
        )

# ──────────────── COMMAND HANDLERS ───────────────────

async def cmd_start(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Halo! Saya *BlockStation Crypto Bot*\n\n"
        "Ketik langsung atau pakai /perintah:\n\n"
        "📊 *Data & Harga*\n"
        "• btc / /btc — Harga BTC sekarang\n"
        "• fg / /fg — Fear & Greed Index\n"
        "• berita / /news — Berita crypto terbaru\n\n"
        "🏆 *Leaderboard*\n"
        "• top / /top — Leaderboard hari ini\n"
        "• topweek / /topweek — Rekap minggu ini\n"
        "• topmonth / /topmonth — Rekap bulan ini\n\n"
        "🎯 *Kuis*\n"
        "• Kuis harga BTC otomatis jam 20:00 WIB\n"
        "• Benar: +3 poin | Salah: -5 poin\n\n"
        "• /info — Info lengkap bot",
        parse_mode="Markdown"
    )

async def cmd_btc(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Mengambil data, sebentar...")
    await update.message.reply_text(format_message("Update Manual"), parse_mode="Markdown")

async def cmd_fg(update, context: ContextTypes.DEFAULT_TYPE):
    fg = get_fear_greed()
    if fg:
        score = fg["value"]
        if   score <= 24: emoji = "😱 Extreme Fear"
        elif score <= 44: emoji = "😟 Fear"
        elif score <= 54: emoji = "😐 Neutral"
        elif score <= 74: emoji = "😊 Greed"
        else:             emoji = "🤑 Extreme Greed"
        msg = f"📊 *Fear & Greed Index*\n\nScore : `{score}/100`\nStatus: {emoji}\n\n_Diperbarui setiap hari_"
    else:
        msg = "❌ Gagal mengambil data"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_news(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Mengambil berita terbaru...")
    await update.message.reply_text(format_berita(), parse_mode="Markdown", disable_web_page_preview=False)

async def cmd_top(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        format_leaderboard(FILE_HARIAN, "🏆 *Leaderboard Harian*", datetime.now().strftime("%d %b %Y")),
        parse_mode="Markdown"
    )

async def cmd_topweek(update, context: ContextTypes.DEFAULT_TYPE):
    now     = datetime.now()
    senin   = (now - timedelta(days=now.weekday())).strftime("%d %b")
    hari_ini = now.strftime("%d %b %Y")
    await update.message.reply_text(
        format_leaderboard(FILE_MINGGUAN, "📅 *Rekap Minggu Ini*", f"{senin} – {hari_ini}"),
        parse_mode="Markdown"
    )

async def cmd_topmonth(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        format_leaderboard(FILE_BULANAN, "📆 *Rekap Bulan Ini*", datetime.now().strftime("%B %Y")),
        parse_mode="Markdown"
    )

async def cmd_info(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *BlockStation Crypto Bot*\n\n"
        "📡 Sumber data: CoinGecko, Alternative.me, CryptoPanic\n\n"
        "⏰ Jadwal otomatis:\n"
        "   • 07:00 WIB — Berita crypto + Update harga\n"
        "   • 11:00 | 15:00 | 19:00 | 23:00 | 03:00 — Update harga\n"
        "   • 20:00 WIB — Kuis tebak harga BTC\n"
        "   • 21:00 WIB — Hasil kuis + update poin\n"
        "   • 20:00 WIB — Leaderboard harian\n"
        "   • Senin 07:00 WIB — Rekap mingguan\n"
        "   • Tgl 1, 07:00 WIB — Rekap bulanan\n\n"
        "🎯 Sistem poin kuis:\n"
        "   • Benar: +3 poin\n"
        "   • Salah: -5 poin\n\n"
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
            f"   • 📰 Berita crypto terbaru setiap pagi\n"
            f"   • 🎯 Kuis tebak harga BTC setiap malam\n"
            f"   • 🏆 Leaderboard harian, mingguan & bulanan\n"
            f"   • Diskusi & info terkini seputar crypto"
            f"{harga_info}\n\n"
            f"💬 Ketik /start untuk lihat semua fitur\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
        logging.info(f"✅ Welcome terkirim untuk: {nama}")

# ──────────────── MAIN ───────────────────

async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("btc",      cmd_btc))
    app.add_handler(CommandHandler("fg",       cmd_fg))
    app.add_handler(CommandHandler("news",     cmd_news))
    app.add_handler(CommandHandler("top",      cmd_top))
    app.add_handler(CommandHandler("topweek",  cmd_topweek))
    app.add_handler(CommandHandler("topmonth", cmd_topmonth))
    app.add_handler(CommandHandler("info",     cmd_info))
    app.add_handler(CallbackQueryHandler(callback_kuis, pattern="^kuis:"))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_member))
    app.add_handler(MessageHandler(filters.TEXT & filters.Chat(int(GROUP_ID)), handle_pesan))

    scheduler = AsyncIOScheduler(timezone="UTC")

    # Update harga 6x sehari
    for jadwal in JADWAL:
        scheduler.add_job(kirim_update, trigger="cron",
            hour=jadwal["jam"], minute=jadwal["menit"], args=[app.bot, jadwal["label"]])

    # Berita pagi jam 07:00 WIB = 00:00 UTC
    scheduler.add_job(kirim_berita, trigger="cron", hour=0, minute=0, args=[app.bot])

    # Kuis jam 20:00 WIB = 13:00 UTC
    scheduler.add_job(kirim_kuis, trigger="cron", hour=13, minute=0, args=[app.bot])

    # Tutup kuis & umumkan hasil 1 jam kemudian = 14:00 UTC
    scheduler.add_job(tutup_kuis, trigger="cron", hour=14, minute=0, args=[app.bot])

    # Leaderboard harian jam 20:00 WIB setelah kuis = 13:05 UTC
    scheduler.add_job(kirim_leaderboard_harian, trigger="cron", hour=13, minute=5, args=[app.bot])

    # Rekap mingguan — Senin 07:00 WIB = 00:00 UTC
    scheduler.add_job(kirim_leaderboard_mingguan, trigger="cron",
        day_of_week="mon", hour=0, minute=1, args=[app.bot])

    # Rekap bulanan — tanggal 1 jam 07:00 WIB = 00:00 UTC
    scheduler.add_job(kirim_leaderboard_bulanan, trigger="cron",
        day=1, hour=0, minute=2, args=[app.bot])

    scheduler.start()
    logging.info("✅ Bot aktif | Semua scheduler berjalan...")

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
