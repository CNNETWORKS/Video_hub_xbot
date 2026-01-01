import os
import asyncio
import random
import time
import threading
from datetime import datetime, timedelta

from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import (
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

# ================== CONFIG ==================
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_ID = 7271198694
FORCE_CHANNEL = "@cnnetworkofficial"
VIDEO_CHANNEL_ID = -1003604209221

FREE_DAILY_LIMIT = 5
AUTO_DELETE_SECONDS = 300  # 5 minutes
# ============================================

# ================== DUMMY WEB SERVER (RENDER FIX) ==================
web = Flask(__name__)

@web.route("/")
def home():
    return "Video Hub Bot is running"

def run_web():
    web.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

threading.Thread(target=run_web, daemon=True).start()
# ==================================================================

app = Client(
    "video_hub",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ================== IN-MEMORY DATABASE ==================
users = {}
# users[user_id] = {
#   free_used, last_reset, plan, premium_expiry
# }
# ========================================================

def now():
    return datetime.now()

def reset_if_needed(uid):
    u = users[uid]
    if now().date() != u["last_reset"]:
        u["free_used"] = 0
        u["last_reset"] = now().date()

# ================== KEYBOARDS ==================
MAIN_MENU = ReplyKeyboardMarkup(
    [["🎬 Get Video"], ["👤 Profile", "🤝 Refer & Earn"], ["💎 Premium"]],
    resize_keyboard=True
)

def premium_button():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💎 View Premium Plans", callback_data="show_premium")]
    ])
# ===============================================

# ================== START ==================
@app.on_message(filters.command("start"))
async def start(_, m):
    uid = m.from_user.id

    if uid not in users:
        users[uid] = {
            "free_used": 0,
            "last_reset": now().date(),
            "plan": "free",
            "premium_expiry": None
        }

    try:
        member = await app.get_chat_member(FORCE_CHANNEL, uid)
    except:
        await m.reply(
            "🔒 Join the channel to use this bot",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{FORCE_CHANNEL[1:]}")],
                [InlineKeyboardButton("🔄 Refresh", callback_data="refresh")]
            ])
        )
        return

    await m.reply(
        f"👋 Welcome {m.from_user.first_name}",
        reply_markup=MAIN_MENU
    )

# ================== REFRESH ==================
@app.on_callback_query(filters.regex("refresh"))
async def refresh(_, q):
    await start(_, q.message)

# ================== GET VIDEO ==================
@app.on_message(filters.regex("Get Video"))
async def get_video(_, m):
    uid = m.from_user.id
    reset_if_needed(uid)

    u = users[uid]

    # PREMIUM CHECK
    if u["plan"] == "free" and u["free_used"] >= FREE_DAILY_LIMIT:
        await m.reply(
            f"❌ Limit Reached!\n\n"
            f"⏰ Reset at 12:00 AM IST\n\n"
            f"🎬 Free: 5 videos/day\n"
            f"💎 Premium: Unlimited",
            reply_markup=premium_button()
        )
        return

    # FETCH VIDEOS
    videos = []
    async for msg in app.get_chat_history(VIDEO_CHANNEL_ID, limit=50):
        if msg.video:
            videos.append(msg)

    if not videos:
        await m.reply("⚠️ No videos available")
        return

    video = random.choice(videos)

    sent = await app.copy_message(
        chat_id=m.chat.id,
        from_chat_id=VIDEO_CHANNEL_ID,
        message_id=video.id,
        caption="🎬 Enjoy\n\n🔰 @cnnetworkofficial",
        protect_content=True
    )

    if u["plan"] == "free":
        u["free_used"] += 1

    # AUTO DELETE
    asyncio.create_task(auto_delete(sent.chat.id, sent.id))

async def auto_delete(chat_id, msg_id):
    await asyncio.sleep(AUTO_DELETE_SECONDS)
    try:
        await app.delete_messages(chat_id, msg_id)
    except:
        pass

# ================== PROFILE ==================
@app.on_message(filters.regex("Profile"))
async def profile(_, m):
    u = users[m.from_user.id]
    await m.reply(
        f"👤 *Profile*\n\n"
        f"ID: `{m.from_user.id}`\n"
        f"Plan: {u['plan'].upper()}\n"
        f"Used Today: {u['free_used']}/{FREE_DAILY_LIMIT}",
        parse_mode="markdown"
    )

# ================== PREMIUM ==================
@app.on_message(filters.regex("Premium"))
async def premium(_, m):
    await m.reply(
        "💎 *Premium Plans*\n\n"
        "🥈 Silver – ₹69 (30/day)\n"
        "🥇 Gold – ₹149 (50/day)\n"
        "💎 Platinum – ₹499 (Unlimited)\n\n"
        "📩 Contact @Jioxt",
        parse_mode="markdown"
    )

@app.on_callback_query(filters.regex("show_premium"))
async def show_premium(_, q):
    await premium(_, q.message)

# ================== ADMIN GIVE PREMIUM ==================
@app.on_message(filters.command("addpremium") & filters.user(ADMIN_ID))
async def add_premium(_, m):
    try:
        _, uid, days = m.text.split()
        uid = int(uid)
        days = int(days)

        users[uid]["plan"] = "premium"
        users[uid]["premium_expiry"] = now() + timedelta(days=days)

        await m.reply("✅ Premium granted")
        await app.send_message(uid, "🎉 Premium activated!")
    except:
        await m.reply("Usage: /addpremium user_id days")

# ================== RUN ==================
app.run()
