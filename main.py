import os
import threading
import random
from datetime import datetime, timedelta
from flask import Flask

from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

ADMIN_ID = 7271198694
VIDEO_CHANNEL_ID = -1003604209221

FREE_DAILY_LIMIT = 5

# ================== FLASK (RENDER NEEDS THIS) ==================
web = Flask(__name__)

@web.route("/")
def home():
    return "✅ Video Hub Bot is running"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web.run(host="0.0.0.0", port=port)

# ================== PYROGRAM BOT ==================
app = Client(
    "video_hub",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ================== STORAGE ==================
USERS = {}
PREMIUM = {}

# ================== HELPERS ==================
def now():
    return datetime.now()

def init_user(uid):
    if uid not in USERS:
        USERS[uid] = {
            "videos": 0,
            "reset": now(),
            "joined": now(),
            "referrals": 0
        }

def reset_limit(uid):
    if (now() - USERS[uid]["reset"]).days >= 1:
        USERS[uid]["videos"] = 0
        USERS[uid]["reset"] = now()

def is_premium(uid):
    return uid in PREMIUM and PREMIUM[uid] > now()

# ================== KEYBOARDS ==================
MAIN_KB = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🎬 Get Video")],
        [KeyboardButton("👤 Profile"), KeyboardButton("🤝 Refer & Earn")],
        [KeyboardButton("💎 Premium")]
    ],
    resize_keyboard=True
)

ADMIN_KB = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🛠 Admin Panel")],
        [KeyboardButton("🎬 Get Video")],
        [KeyboardButton("👤 Profile"), KeyboardButton("🤝 Refer & Earn")],
        [KeyboardButton("💎 Premium")]
    ],
    resize_keyboard=True
)

# ================== START ==================
@app.on_message(filters.command("start"))
async def start(_, m):
    uid = m.from_user.id
    init_user(uid)

    kb = ADMIN_KB if uid == ADMIN_ID else MAIN_KB

    await m.reply(
        f"👋 Welcome **{m.from_user.first_name}**\n\n"
        "🎬 Get random videos\n"
        "🤝 Refer & earn\n"
        "💎 Upgrade for unlimited access",
        reply_markup=kb
    )

# ================== ROUTER (FIXED) ==================
@app.on_message(filters.text & ~filters.regex("^/"))
async def router(_, m):
    uid = m.from_user.id
    init_user(uid)
    reset_limit(uid)

    text = m.text.strip()

    if text == "🎬 Get Video":
        await send_video(m)

    elif text == "👤 Profile":
        await profile(m)

    elif text == "🤝 Refer & Earn":
        await refer(m)

    elif text == "💎 Premium":
        await premium(m)

    elif text == "🛠 Admin Panel" and uid == ADMIN_ID:
        await admin_panel(m)

# ================== VIDEO ==================
async def send_video(m):
    uid = m.from_user.id

    if not is_premium(uid):
        if USERS[uid]["videos"] >= FREE_DAILY_LIMIT:
            await m.reply(
                "🚫 **Limit Reached**\n\n"
                "Free users: 5/day\n"
                "Upgrade to Premium 💎"
            )
            return

    USERS[uid]["videos"] += 1

    await app.copy_message(
        chat_id=m.chat.id,
        from_chat_id=VIDEO_CHANNEL_ID,
        message_id=random.randint(1, 50)
    )

# ================== PROFILE ==================
async def profile(m):
    uid = m.from_user.id
    user = USERS[uid]

    await m.reply(
        f"👤 **Your Profile**\n\n"
        f"🆔 ID: `{uid}`\n"
        f"🎬 Videos today: {user['videos']}\n"
        f"🤝 Referrals: {user['referrals']}\n"
        f"💎 Premium: {'Yes' if is_premium(uid) else 'No'}\n"
        f"📅 Joined: {user['joined'].strftime('%d-%m-%Y')}"
    )

# ================== REFER ==================
async def refer(m):
    uid = m.from_user.id
    me = await app.get_me()
    await m.reply(
        f"🤝 **Refer & Earn**\n\n"
        f"Invite friends:\n"
        f"https://t.me/{me.username}?start={uid}"
    )

# ================== PREMIUM ==================
async def premium(m):
    await m.reply(
        "💎 **Premium Plans**\n\n"
        "🥈 Silver – ₹69 (30/day)\n"
        "🥇 Gold – ₹149 (50/day)\n"
        "👑 Platinum – ₹499 (Unlimited)\n\n"
        "📩 Contact: @jioxt"
    )

# ================== ADMIN ==================
async def admin_panel(m):
    await m.reply(
        "🛠 **Admin Panel**\n\n"
        "/addpremium user_id days\n"
        "/removepremium user_id\n"
        "/stats"
    )

@app.on_message(filters.command("addpremium") & filters.user(ADMIN_ID))
async def add_premium(_, m):
    _, uid, days = m.text.split()
    PREMIUM[int(uid)] = now() + timedelta(days=int(days))
    await m.reply("✅ Premium added")

@app.on_message(filters.command("removepremium") & filters.user(ADMIN_ID))
async def remove_premium(_, m):
    _, uid = m.text.split()
    PREMIUM.pop(int(uid), None)
    await m.reply("❌ Premium removed")

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats(_, m):
    await m.reply(
        f"📊 **Stats**\n\n"
        f"Users: {len(USERS)}\n"
        f"Premium: {len(PREMIUM)}"
    )

# ================== RUN BOTH ==================
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    app.run()
