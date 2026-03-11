"""
===========================================
  Telegram Crypto Bot — BlockStation
  Fitur: Harga BTC, Berita Real-time + AI Insight, Kuis, Leaderboard
  By: Claude | Stack: python-telegram-bot + Gemini AI
===========================================
"""

import logging
import requests
import feedparser
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
BOT_TOKEN    = os.environ.get("BOT_TOKEN",    "8663484684:AAH0kJ0TgpYAaG6NMzxJ0-OKWwg4T0pnNX4")
GROUP_ID     = os.environ.get("GROUP_ID",     "-1003714160870")
GEMINI_KEY   = os.environ.get("GEMINI_API_KEY","AIzaSyAZ6YlOppU2zfHMco3EMOzddMq3vTQYIjI")

JADWAL = [
    {"jam": 0,  "menit": 0, "label": "🕖 Update 07:00 WIB"},
    {"jam": 4,  "menit": 0, "label": "🕚 Update 11:00 WIB"},
    {"jam": 8,  "menit": 0, "label": "🕒 Update 15:00 WIB"},
    {"jam": 12, "menit": 0, "label": "🕖 Update 19:00 WIB"},
    {"jam": 16, "menit": 0, "label": "🕚 Update 23:00 WIB"},
    {"jam": 20, "menit": 0, "label": "🕒 Update 03:00 WIB"},
]

POIN_BENAR = 3
POIN_SALAH = 5

RSS_SOURCES = [
    {"name": "CoinDesk",         "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
    {"name": "CoinTelegraph",    "url": "https://cointelegraph.com/rss"},
    {"name": "Decrypt",          "url": "https://decrypt.co/feed"},
    {"name": "Bitcoin Magazine", "url": "https://bitcoinmagazine.com/feed"},
    {"name": "CryptoSlate",      "url": "https://cryptoslate.com/feed/"},
]

FILE_HARIAN      = "data_harian.json"
FILE_MINGGUAN    = "data_mingguan.json"
FILE_BULANAN     = "data_bulanan.json"
FILE_KUIS        = "data_kuis.json"
FILE_BERITA_SENT = "berita_sent.json"

def now_wib():
    return datetime.now() + timedelta(hours=7)

# ─────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ──────────────── GEMINI AI INSIGHT ───────────────────

def get_gemini_insight(judul: str, sumber: str) -> str:
    """Generate insight singkat dari judul berita pakai Gemini"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
        prompt = (
            f"Kamu adalah analis crypto. Berdasarkan judul berita ini:\n"
            f"\"{judul}\"\n\n"
            f"Tulis insight singkat dalam Bahasa Indonesia, maksimal 2 kalimat:\n"
            f"1. Jelaskan inti beritanya secara singkat\n"
            f"2. Apa dampak atau artinya bagi market crypto\n\n"
            f"Gaya bahasa: santai tapi informatif. Jangan mulai dengan kata 'Berita ini'."
        )
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        result = r.json()
        text = result["candidates"][0]["content"]["parts"][0]["text"]
        return text.strip()
    except Exception as e:
        logging.error(f"Gemini error: {e}")
        return None

# ──────────────── STORAGE ───────────────────

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
    for filepath in [FILE_HARIAN, FILE_MINGGUAN, FILE_BULANAN]:
        data = load_data(filepath)
        if user_id not in data:
            data[user_id] = {"nama": nama, "username": username, "pesan": 0, "poin": 0}
        if "poin" not in data[user_id]:
            data[user_id]["poin"] = 0
        data[user_id]["poin"]     = max(0, data[user_id]["poin"] + delta)
        data[user_id]["nama"]     = nama
        data[user_id]["username"] = username
        save_data(filepath, data)

# ──────────────── FORMAT LEADERBOARD ───────────────────

def format_leaderboard(filepath: str, judul: str, periode: str) -> str:
    data   = load_data(filepath)
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

    if not data:
        return (
            f"━━━━━━━━━━━━━━━━━━━━\n{judul}\n📅 {periode}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\nBelum ada aktivitas tercatat.\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

    sorted_members = sorted(
        data.items(),
        key=lambda x: (x[1].get("poin", 0), x[1]["pesan"]),
        reverse=True
    )
    rows = ""
    for i, (uid, info) in enumerate(sorted_members[:5]):
        username = f"@{info['username']}" if info["username"] else info["nama"]
        rows += f"{medals[i]} {username} — `{info['pesan']} pesan` | `{info.get('poin', 0)} poin`\n"

    total_pesan  = sum(v["pesan"] for v in data.values())
    total_member = len(data)

    return (
        f"━━━━━━━━━━━━━━━━━━━━\n{judul}\n📅 {periode}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n{rows}\n"
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

# ──────────────── BERITA REAL-TIME ───────────────────

def fetch_rss_news(max_per_source: int = 3) -> list:
    semua_berita = []
    for src in RSS_SOURCES:
        try:
            feed = feedparser.parse(src["url"])
            for entry in feed.entries[:max_per_source]:
                semua_berita.append({
                    "id":     entry.get("id") or entry.get("link", ""),
                    "judul":  entry.get("title", "No title"),
                    "url":    entry.get("link", ""),
                    "sumber": src["name"],
                    "waktu":  entry.get("published", "")
                })
        except Exception as e:
            logging.error(f"Error RSS {src['name']}: {e}")
    return semua_berita

async def cek_dan_kirim_berita(bot: Bot):
    sent        = load_data(FILE_BERITA_SENT)
    berita_list = fetch_rss_news(max_per_source=5)
    berita_baru = []

    for b in berita_list:
        if b["id"] not in sent:
            berita_baru.append(b)
            sent[b["id"]] = now_wib().strftime("%Y-%m-%d %H:%M")

    if not berita_baru:
        return

    berita_baru = berita_baru[:3]

    if len(sent) > 500:
        keys = list(sent.keys())
        for k in keys[:-500]:
            del sent[k]
    save_data(FILE_BERITA_SENT, sent)

    now = now_wib().strftime("%H:%M WIB")
    for b in berita_baru:
        # Generate insight dari Gemini
        insight = get_gemini_insight(b["judul"], b["sumber"])
        insight_block = f"\n\n💡 *Insight:*\n_{insight}_" if insight else ""

        msg = (
            f"📰 *{b['sumber']}* — {now}\n\n"
            f"*{b['judul']}*"
            f"{insight_block}\n\n"
            f"🔗 {b['url']}"
        )
        try:
            await bot.send_message(
                chat_id=GROUP_ID,
                text=msg,
                parse_mode="Markdown",
                disable_web_page_preview=False
            )
            await asyncio.sleep(2)  # jeda agar tidak flood + beri waktu Gemini
        except Exception as e:
            logging.error(f"Gagal kirim berita: {e}")

    logging.info(f"✅ {len(berita_baru)} berita baru terkirim")

# ──────────────── FORMAT PESAN HARGA ───────────────────

def format_message(label_waktu: str) -> str:
    btc = get_btc_price()
    fg  = get_fear_greed()
    now = now_wib().strftime("%d %b %Y | %H:%M WIB")

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

# ──────────────── KUIS BTC ───────────────────

def buat_opsi_range(harga: float) -> tuple:
    import random
    step  = 1000
    base  = int(harga / step) * step
    benar = f"${base:,} – ${base + step:,}"
    offsets = [-2, -1, 1, 2]
    random.shuffle(offsets)
    salah = [f"${base + (o*step):,} – ${base + (o*step) + step:,}" for o in offsets[:3]]
    semua = [benar] + salah
    random.shuffle(semua)
    return semua, benar

async def kirim_kuis(bot: Bot):
    btc = get_btc_price()
    if not btc:
        return
    opsi, jawaban_benar = buat_opsi_range(btc["usd"])
    save_data(FILE_KUIS, {
        "jawaban_benar":   jawaban_benar,
        "harga_saat_kuis": btc["usd"],
        "sudah_jawab":     {},
        "waktu":           now_wib().strftime("%d %b %Y %H:%M")
    })
    keyboard     = [[InlineKeyboardButton(o, callback_data=f"kuis:{o}")] for o in opsi]
    reply_markup = InlineKeyboardMarkup(keyboard)
    now = now_wib().strftime("%d %b %Y | %H:%M WIB")
    msg = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 *Kuis Harian — Tebak Harga BTC!*\n🕐 {now}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Harga BTC sekarang: `${btc['usd']:,.0f}`\n\n"
        f"❓ *Harga BTC 1 jam lagi ada di range mana?*\n\n"
        f"✅ Benar: `+{POIN_BENAR} poin`\n"
        f"❌ Salah: `-{POIN_SALAH} poin`\n\n"
        f"⏰ _Jawaban ditutup dalam 1 jam_"
    )
    try:
        await bot.send_message(chat_id=GROUP_ID, text=msg,
            parse_mode="Markdown", reply_markup=reply_markup)
        logging.info("✅ Kuis terkirim")
    except Exception as e:
        logging.error(f"Gagal kirim kuis: {e}")

async def tutup_kuis(bot: Bot):
    kuis = load_data(FILE_KUIS)
    if not kuis or "jawaban_benar" not in kuis:
        return
    jawaban_benar = kuis["jawaban_benar"]
    sudah_jawab   = kuis.get("sudah_jawab", {})
    harga_check   = get_btc_price()
    harga_aktual  = f"${harga_check['usd']:,.0f}" if harga_check else "N/A"

    benar_list, salah_list = [], []
    for uid, info in sudah_jawab.items():
        tag = f"@{info['username']}" if info["username"] else info["nama"]
        if info["pilihan"] == jawaban_benar:
            update_poin(uid, info["nama"], info["username"], +POIN_BENAR)
            benar_list.append(tag)
        else:
            update_poin(uid, info["nama"], info["username"], -POIN_SALAH)
            salah_list.append(tag)

    msg = (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 *Hasil Kuis BTC!*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Jawaban benar: `{jawaban_benar}`\n"
        f"Harga aktual : `{harga_aktual}`\n\n"
        f"✅ Benar (+{POIN_BENAR} poin):\n{', '.join(benar_list) or '_Tidak ada_'}\n\n"
        f"❌ Salah (-{POIN_SALAH} poin):\n{', '.join(salah_list) or '_Tidak ada_'}\n\n"
        f"🏆 Cek poin kamu: ketik `top`\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    try:
        await bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode="Markdown")
        logging.info("✅ Hasil kuis terkirim")
        reset_data(FILE_KUIS)
    except Exception as e:
        logging.error(f"Gagal kirim hasil kuis: {e}")

async def callback_kuis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not query.data.startswith("kuis:"):
        return
    pilihan  = query.data.replace("kuis:", "")
    user     = query.from_user
    user_id  = str(user.id)
    nama     = (user.first_name or "") + (f" {user.last_name}" if user.last_name else "")
    username = user.username or ""

    kuis = load_data(FILE_KUIS)
    if not kuis or "jawaban_benar" not in kuis:
        await query.answer("⏰ Kuis sudah ditutup!", show_alert=True)
        return
    if user_id in kuis.get("sudah_jawab", {}):
        await query.answer("⚠️ Kamu sudah menjawab!", show_alert=True)
        return

    kuis.setdefault("sudah_jawab", {})[user_id] = {
        "nama": nama, "username": username, "pilihan": pilihan
    }
    save_data(FILE_KUIS, kuis)
    await query.answer(f"✅ Jawaban: {pilihan} tercatat!", show_alert=True)

# ──────────────── SCHEDULER JOBS ───────────────────

async def kirim_update(bot: Bot, label: str):
    try:
        await bot.send_message(chat_id=GROUP_ID, text=format_message(label), parse_mode="Markdown")
        logging.info(f"✅ Harga terkirim: {label}")
    except Exception as e:
        logging.error(f"Gagal kirim harga: {e}")

async def kirim_leaderboard_harian(bot: Bot):
    msg = format_leaderboard(FILE_HARIAN, "🏆 *Leaderboard Harian*", now_wib().strftime("%d %b %Y"))
    try:
        await bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode="Markdown")
        reset_data(FILE_HARIAN)
    except Exception as e:
        logging.error(f"Gagal kirim leaderboard harian: {e}")

async def kirim_leaderboard_mingguan(bot: Bot):
    now    = now_wib()
    senin  = (now - timedelta(days=7)).strftime("%d %b")
    minggu = (now - timedelta(days=1)).strftime("%d %b %Y")
    msg    = format_leaderboard(FILE_MINGGUAN, "📅 *Rekap Mingguan*", f"{senin} – {minggu}")
    try:
        await bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode="Markdown")
        reset_data(FILE_MINGGUAN)
    except Exception as e:
        logging.error(f"Gagal kirim leaderboard mingguan: {e}")

async def kirim_leaderboard_bulanan(bot: Bot):
    bulan_lalu = (now_wib() - timedelta(days=1)).strftime("%B %Y")
    msg = format_leaderboard(FILE_BULANAN, "📆 *Rekap Bulanan*", bulan_lalu)
    try:
        await bot.send_message(chat_id=GROUP_ID, text=msg, parse_mode="Markdown")
        reset_data(FILE_BULANAN)
    except Exception as e:
        logging.error(f"Gagal kirim leaderboard bulanan: {e}")

# ──────────────── HANDLE PESAN ───────────────────

async def handle_pesan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not user or user.is_bot:
        return
    user_id  = str(user.id)
    nama     = (user.first_name or "") + (f" {user.last_name}" if user.last_name else "")
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
    elif teks in ["berita", "news"]:
        await update.message.reply_text("⏳ Mengambil berita + insight AI, sebentar...")
        berita_list = fetch_rss_news(max_per_source=3)[:3]
        if berita_list:
            for b in berita_list:
                insight = get_gemini_insight(b["judul"], b["sumber"])
                insight_block = f"\n\n💡 *Insight:*\n_{insight}_" if insight else ""
                msg = (
                    f"📰 *{b['sumber']}*\n\n"
                    f"*{b['judul']}*"
                    f"{insight_block}\n\n"
                    f"🔗 {b['url']}"
                )
                await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=False)
                await asyncio.sleep(1)
        else:
            await update.message.reply_text("❌ Berita tidak tersedia saat ini.")
    elif teks == "top":
        await update.message.reply_text(
            format_leaderboard(FILE_HARIAN, "🏆 *Leaderboard Harian*", now_wib().strftime("%d %b %Y")),
            parse_mode="Markdown")
    elif teks == "topweek":
        now     = now_wib()
        senin   = (now - timedelta(days=now.weekday())).strftime("%d %b")
        hari_ini = now.strftime("%d %b %Y")
        await update.message.reply_text(
            format_leaderboard(FILE_MINGGUAN, "📅 *Rekap Minggu Ini*", f"{senin} – {hari_ini}"),
            parse_mode="Markdown")
    elif teks == "topmonth":
        await update.message.reply_text(
            format_leaderboard(FILE_BULANAN, "📆 *Rekap Bulan Ini*", now_wib().strftime("%B %Y")),
            parse_mode="Markdown")

# ──────────────── COMMAND HANDLERS ───────────────────

async def cmd_start(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Halo! Saya *BlockStation Crypto Bot*\n\n"
        "📊 *Data & Harga*\n"
        "• btc / /btc — Harga BTC sekarang\n"
        "• fg / /fg — Fear & Greed Index\n\n"
        "📰 *Berita*\n"
        "• berita / /news — Berita + AI insight\n"
        "• _(otomatis real-time setiap 5 menit)_\n\n"
        "🏆 *Leaderboard*\n"
        "• top / /top — Hari ini\n"
        "• topweek / /topweek — Minggu ini\n"
        "• topmonth / /topmonth — Bulan ini\n\n"
        "🎯 *Kuis* — otomatis jam 20:00 WIB\n"
        "• Benar: +3 poin | Salah: -5 poin\n\n"
        "• /info — Info lengkap jadwal bot",
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
    await update.message.reply_text("⏳ Mengambil berita + insight AI, sebentar...")
    berita_list = fetch_rss_news(max_per_source=3)[:3]
    if berita_list:
        for b in berita_list:
            insight = get_gemini_insight(b["judul"], b["sumber"])
            insight_block = f"\n\n💡 *Insight:*\n_{insight}_" if insight else ""
            msg = (
                f"📰 *{b['sumber']}*\n\n"
                f"*{b['judul']}*"
                f"{insight_block}\n\n"
                f"🔗 {b['url']}"
            )
            await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=False)
            await asyncio.sleep(1)
    else:
        await update.message.reply_text("❌ Berita tidak tersedia saat ini.")

async def cmd_top(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        format_leaderboard(FILE_HARIAN, "🏆 *Leaderboard Harian*", now_wib().strftime("%d %b %Y")),
        parse_mode="Markdown")

async def cmd_topweek(update, context: ContextTypes.DEFAULT_TYPE):
    now     = now_wib()
    senin   = (now - timedelta(days=now.weekday())).strftime("%d %b")
    hari_ini = now.strftime("%d %b %Y")
    await update.message.reply_text(
        format_leaderboard(FILE_MINGGUAN, "📅 *Rekap Minggu Ini*", f"{senin} – {hari_ini}"),
        parse_mode="Markdown")

async def cmd_topmonth(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        format_leaderboard(FILE_BULANAN, "📆 *Rekap Bulan Ini*", now_wib().strftime("%B %Y")),
        parse_mode="Markdown")

async def cmd_info(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *BlockStation Crypto Bot*\n\n"
        "📡 Sumber data:\n"
        "   • Harga: CoinGecko\n"
        "   • Sentiment: Alternative.me\n"
        "   • Berita: CoinDesk, CoinTelegraph,\n"
        "     Decrypt, Bitcoin Magazine, CryptoSlate\n"
        "   • AI Insight: Gemini (Google)\n\n"
        "⏰ Jadwal otomatis:\n"
        "   • Berita real-time — setiap 5 menit\n"
        "   • Harga — 07:00|11:00|15:00|19:00|23:00|03:00\n"
        "   • Kuis  — 20:00 WIB\n"
        "   • Hasil kuis — 21:00 WIB\n"
        "   • Leaderboard harian — 20:05 WIB\n"
        "   • Rekap mingguan — Senin 07:00 WIB\n"
        "   • Rekap bulanan  — Tgl 1, 07:00 WIB\n\n"
        "🛠 Made with python-telegram-bot + Gemini AI",
        parse_mode="Markdown"
    )

# ──────────────── WELCOME NEW MEMBER ───────────────────

async def welcome_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        nama     = (member.first_name or "") + (f" {member.last_name}" if member.last_name else "")
        username = f"@{member.username}" if member.username else nama
        btc      = get_btc_price()
        harga_info = f"\n\n💰 *BTC saat ini:* `${btc['usd']:,.2f}` ({btc['change24h']:+.2f}%)" if btc else ""
        msg = (
            f"━━━━━━━━━━━━━━━━━━━━\n🎉 *Selamat Datang!*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Halo {username}! 👋\n"
            f"Selamat bergabung di *BlockStation* 🚀\n\n"
            f"📌 *Yang bisa kamu temukan di sini:*\n"
            f"   • 📊 Update harga BTC setiap 4 jam\n"
            f"   • 📰 Berita crypto + AI insight real-time\n"
            f"   • 🎯 Kuis tebak harga BTC tiap malam\n"
            f"   • 🏆 Leaderboard harian, mingguan & bulanan"
            f"{harga_info}\n\n"
            f"💬 Ketik /start untuk lihat semua fitur\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

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

    for jadwal in JADWAL:
        scheduler.add_job(kirim_update, trigger="cron",
            hour=jadwal["jam"], minute=jadwal["menit"], args=[app.bot, jadwal["label"]])

    scheduler.add_job(cek_dan_kirim_berita,       trigger="interval", minutes=5, args=[app.bot])
    scheduler.add_job(kirim_kuis,                 trigger="cron", hour=13, minute=0,  args=[app.bot])
    scheduler.add_job(tutup_kuis,                 trigger="cron", hour=14, minute=0,  args=[app.bot])
    scheduler.add_job(kirim_leaderboard_harian,   trigger="cron", hour=13, minute=5,  args=[app.bot])
    scheduler.add_job(kirim_leaderboard_mingguan, trigger="cron",
        day_of_week="mon", hour=0, minute=1, args=[app.bot])
    scheduler.add_job(kirim_leaderboard_bulanan,  trigger="cron",
        day=1, hour=0, minute=2, args=[app.bot])

    scheduler.start()
    logging.info("✅ Bot aktif | Berita + Gemini AI Insight berjalan...")

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
