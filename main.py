import os
import random
import asyncio
import threading
from datetime import datetime

from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import (
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

# ================= CONFIG =================
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_ID = 7271198694
FORCE_CHANNEL = "@cnnetworkofficial"
VIDEO_CHANNEL_ID = -1003604209221

FREE_LIMIT = 5
AUTO_DELETE_TIME = 300  # seconds
# =========================================

# ================= RENDER PORT FIX =================
web = Flask(__name__)

@web.route("/")
def home():
    return "Video Hub Bot Running"

def run_web():
    web.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

threading.Thread(target=run_web, daemon=True).start()
# ==================================================

app = Client(
    "video_hub_xbot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ================= DATABASE (IN MEMORY) =================
users = {}
# =======================================================

def today():
    return datetime.now().date()

def init_user(uid):
    if uid not in users:
        users[uid] = {
            "used": 0,
            "date": today(),
            "plan": "free"
        }

def reset_if_needed(uid):
    if users[uid]["date"] != today():
        users[uid]["used"] = 0
        users[uid]["date"] = today()

# ================= MENUS =================
MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["🎬 Get Video"],
        ["👤 Profile", "🤝 Refer & Earn"],
        ["💎 Premium"]
    ],
    resize_keyboard=True
)

def premium_button():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("💎 View Premium Plans", callback_data="premium")]]
    )
# ========================================

# ================= START =================
@app.on_message(filters.command("start"))
async def start(_, m):
    uid = m.from_user.id
    init_user(uid)

    try:
        await app.get_chat_member(FORCE_CHANNEL, uid)
    except:
        await m.reply(
            "🔒 Join the channel to use this bot",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Join Channel", url="https://t.me/cnnetworkofficial")],
                [InlineKeyboardButton("🔄 Refresh", callback_data="refresh")]
            ])
        )
        return

    await m.reply(
        f"👋 Welcome {m.from_user.first_name}",
        reply_markup=MAIN_MENU
    )

# ================= REFRESH =================
@app.on_callback_query(filters.regex("refresh"))
async def refresh(_, q):
    await start(_, q.message)

# ================= BUTTON ROUTER (MAIN FIX) =================
@app.on_message(filters.text & ~filters.command)
async def router(_, m):
    uid = m.from_user.id
    init_user(uid)
    reset_if_needed(uid)

    text = m.text.strip()

    if text == "🎬 Get Video":
        await send_video(m)

    elif text == "👤 Profile":
        await m.reply(
            f"👤 Profile\n\n"
            f"ID: `{uid}`\n"
            f"Plan: {users[uid]['plan'].upper()}\n"
            f"Used Today: {users[uid]['used']}/{FREE_LIMIT}",
            parse_mode="markdown"
        )

    elif text == "🤝 Refer & Earn":
        await m.reply(
            "🤝 Refer & Earn\n\n"
            "Invite friends & earn credits.\n"
            "Referral system coming next update."
        )

    elif text == "💎 Premium":
        await show_premium_message(m)

# ================= SEND VIDEO =================
async def send_video(m):
    uid = m.from_user.id
    user = users[uid]

    if user["plan"] == "free" and user["used"] >= FREE_LIMIT:
        await m.reply(
            "❌ Limit Reached!\n\n"
            "⏰ Reset at 12:00 AM IST\n\n"
            "💎 Upgrade to Premium for unlimited videos.",
            reply_markup=premium_button()
        )
        return

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
        caption="🎬 Enjoy your video\n\n🔰 @cnnetworkofficial",
        protect_content=True
    )

    if user["plan"] == "free":
        user["used"] += 1

    asyncio.create_task(auto_delete(sent.chat.id, sent.id))

async def auto_delete(chat_id, msg_id):
    await asyncio.sleep(AUTO_DELETE_TIME)
    try:
        await app.delete_messages(chat_id, msg_id)
    except:
        pass

# ================= PREMIUM =================
async def show_premium_message(m):
    await m.reply(
        "💎 Premium Plans\n\n"
        "🥈 Silver – ₹69\n"
        "• 30 videos/day\n\n"
        "🥇 Gold – ₹149\n"
        "• 50 videos/day\n\n"
        "💎 Platinum – ₹499\n"
        "• Unlimited videos\n\n"
        "📩 Contact @Jioxt"
    )

@app.on_callback_query(filters.regex("premium"))
async def premium_callback(_, q):
    await show_premium_message(q.message)

# ================= RUN =================
app.run()
