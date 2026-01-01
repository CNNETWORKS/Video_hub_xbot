import os
import threading
import random
from datetime import datetime, timedelta
import pytz

from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

# ================= CONFIG =================
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

BOT_USERNAME = "Video_hub_xbot"
ADMIN_ID = 7271198694

FORCE_CHANNEL = "@cnnetworkofficial"
VIDEO_CHANNEL_ID = -1003604209221

TIMEZONE = pytz.timezone("Asia/Kolkata")

FREE_DAILY_LIMIT = 5

SILVER_CREDITS = 15
GOLD_CREDITS = 25
PLATINUM_CREDITS = 40

PLAN_LIMITS = {
    "silver": 30,
    "gold": 50,
    "platinum": 10**9
}

# ================= FLASK =================
web = Flask(__name__)

@web.route("/")
def home():
    return "Video Hub Bot Running"

def run_flask():
    web.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

# ================= PYROGRAM =================
app = Client(
    "video_hub",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ================= DATABASE =================
USERS = {}
PREMIUM = {}

def now():
    return datetime.now(TIMEZONE)

def today():
    return now().date()

def init_user(uid):
    if uid not in USERS:
        USERS[uid] = {
            "videos_today": 0,
            "last_reset": today(),
            "credits": 0,
            "referrals": 0,
            "referred_by": None,
            "seen_videos": set(),
            "joined": now()
        }

def reset_daily(uid):
    if USERS[uid]["last_reset"] != today():
        USERS[uid]["videos_today"] = 0
        USERS[uid]["last_reset"] = today()

def is_premium(uid):
    if uid in PREMIUM:
        if PREMIUM[uid]["expiry"] > now():
            return True
        del PREMIUM[uid]
    return False

def current_plan(uid):
    return PREMIUM[uid]["plan"] if is_premium(uid) else None

# ================= AUTO UPGRADE =================
def check_auto_upgrade(uid):
    credits = USERS[uid]["credits"]

    if credits >= PLATINUM_CREDITS:
        PREMIUM[uid] = {"plan": "platinum", "expiry": now() + timedelta(days=7)}
        USERS[uid]["credits"] -= PLATINUM_CREDITS
        return "platinum"

    if credits >= GOLD_CREDITS:
        PREMIUM[uid] = {"plan": "gold", "expiry": now() + timedelta(days=7)}
        USERS[uid]["credits"] -= GOLD_CREDITS
        return "gold"

    if credits >= SILVER_CREDITS:
        PREMIUM[uid] = {"plan": "silver", "expiry": now() + timedelta(days=7)}
        USERS[uid]["credits"] -= SILVER_CREDITS
        return "silver"

    return None

# ================= MENUS =================
MAIN_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🎬 Get Video")],
        [KeyboardButton("👤 Profile"), KeyboardButton("🤝 Refer & Earn")],
        [KeyboardButton("💎 Premium")]
    ],
    resize_keyboard=True
)

ADMIN_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🛠 Admin Panel")],
        [KeyboardButton("🎬 Get Video")],
        [KeyboardButton("👤 Profile"), KeyboardButton("🤝 Refer & Earn")],
        [KeyboardButton("💎 Premium")]
    ],
    resize_keyboard=True
)

def upgrade_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤝 Refer & Earn", callback_data="open_refer")],
        [InlineKeyboardButton("💎 Premium", callback_data="open_premium")]
    ])

# ================= START =================
@app.on_message(filters.command("start"))
async def start(_, m):
    uid = m.from_user.id
    init_user(uid)

    if len(m.command) > 1 and USERS[uid]["referred_by"] is None:
        ref = int(m.command[1])
        if ref != uid:
            USERS[uid]["referred_by"] = ref

    try:
        await app.get_chat_member(FORCE_CHANNEL, uid)
    except:
        await m.reply(
            "🔒 Join channel to continue",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Join Channel", url="https://t.me/cnnetworkofficial")],
                [InlineKeyboardButton("🔄 Refresh", callback_data="refresh")]
            ])
        )
        return

    referrer = USERS[uid]["referred_by"]
    if referrer and referrer in USERS and referrer != "counted":
        USERS[referrer]["referrals"] += 1
        USERS[referrer]["credits"] += 1
        USERS[uid]["referred_by"] = "counted"

        plan = check_auto_upgrade(referrer)

        msg = (
            "🎉 REFERRAL SUCCESS!\n\n"
            "You earned 🎁 1 Credit = 🎥 2 Videos\n\n"
            f"Total Credits: {USERS[referrer]['credits']}"
        )
        if plan:
            msg += f"\n\n🚀 AUTO-UPGRADED TO {plan.upper()}!"

        await app.send_message(referrer, msg)

    menu = ADMIN_MENU if uid == ADMIN_ID else MAIN_MENU
    await m.reply(
        "👋 Welcome to VIDEO HUB\n\n"
        "• Free: 5 videos/day\n"
        "• 1 Credit = 2 Videos\n"
        "• Refer friends to auto-unlock Premium",
        reply_markup=menu
    )

@app.on_callback_query(filters.regex("refresh"))
async def refresh(_, q):
    await start(_, q.message)

# ================= ROUTER =================
@app.on_message(filters.text & ~filters.regex("^/"))
async def router(_, m):
    uid = m.from_user.id
    init_user(uid)
    reset_daily(uid)

    if m.text == "🎬 Get Video":
        await send_video(m)
    elif m.text == "👤 Profile":
        await profile(m)
    elif m.text == "🤝 Refer & Earn":
        await refer(m)
    elif m.text == "💎 Premium":
        await premium(m)
    elif m.text == "🛠 Admin Panel" and uid == ADMIN_ID:
        await admin_panel(m)

# ================= VIDEO =================
async def send_video(m):
    uid = m.from_user.id
    user = USERS[uid]

    if is_premium(uid):
        limit = PLAN_LIMITS[current_plan(uid)]
        if user["videos_today"] >= limit:
            await m.reply("🚫 Premium daily limit reached")
            return
    else:
        if user["videos_today"] >= FREE_DAILY_LIMIT:
            await m.reply(
                f"🚫 DAILY LIMIT REACHED\n\n"
                f"Referral Link:\nhttps://t.me/{BOT_USERNAME}?start={uid}",
                reply_markup=upgrade_buttons()
            )
            return

    videos = []
    async for msg in app.get_chat_history(VIDEO_CHANNEL_ID, limit=200):
        if msg.video and msg.id not in user["seen_videos"]:
            videos.append(msg)

    if not videos:
        await m.reply("⚠️ No new videos available.")
        return

    v = random.choice(videos)
    user["seen_videos"].add(v.id)

    await app.copy_message(
        m.chat.id,
        VIDEO_CHANNEL_ID,
        v.id,
        protect_content=True
    )

    user["videos_today"] += 1

# ================= PROFILE =================
async def profile(m):
    u = USERS[m.from_user.id]
    await m.reply(
        f"👤 PROFILE\n\n"
        f"Credits: {u['credits']} (🎥 {u['credits']*2})\n"
        f"Referrals: {u['referrals']}\n"
        f"Premium: {'Yes' if is_premium(m.from_user.id) else 'No'}"
    )

# ================= REFER =================
async def refer(m):
    uid = m.from_user.id
    await m.reply(
        f"🤝 REFER & EARN\n\n"
        f"1 Referral = 1 Credit = 2 Videos\n\n"
        f"Auto-upgrade:\n"
        f"Silver: {SILVER_CREDITS}\n"
        f"Gold: {GOLD_CREDITS}\n"
        f"Platinum: {PLATINUM_CREDITS}\n\n"
        f"Your Link:\nhttps://t.me/{BOT_USERNAME}?start={uid}"
    )

# ================= PREMIUM =================
async def premium(m):
    await m.reply(
        "💎 PREMIUM PLANS\n\n"
        "Silver ₹69 (30/day)\n"
        "Gold ₹149 (50/day)\n"
        "Platinum ₹499 (Unlimited)\n\n"
        "Contact @jioxt"
    )

@app.on_callback_query(filters.regex("open_premium"))
async def cb_premium(_, q):
    await premium(q.message)

@app.on_callback_query(filters.regex("open_refer"))
async def cb_refer(_, q):
    await refer(q.message)

# ================= ADMIN =================
async def admin_panel(m):
    await m.reply(
        "/addpremium user_id plan days\n"
        "/broadcast message\n"
        "/stats"
    )

@app.on_message(filters.command("addpremium") & filters.user(ADMIN_ID))
async def add_premium(_, m):
    _, uid, plan, days = m.text.split()
    PREMIUM[int(uid)] = {
        "plan": plan.lower(),
        "expiry": now() + timedelta(days=int(days))
    }
    await m.reply("✅ Premium added")

@app.on_message(filters.command("broadcast") & filters.user(ADMIN_ID))
async def broadcast(_, m):
    msg = m.text.replace("/broadcast", "").strip()
    for uid in USERS:
        try:
            await app.send_message(uid, msg)
        except:
            pass
    await m.reply("📢 Broadcast sent")

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats(_, m):
    await m.reply(
        f"Users: {len(USERS)}\nPremium: {len(PREMIUM)}"
    )

# ================= RUN =================
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    app.run()
