import asyncio, random, time
from datetime import datetime, timedelta
import pytz
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from PIL import Image, ImageDraw, ImageFont

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

BOT_USERNAME = "Video_hub_xbot"

ADMIN_ID = 7271198694
ADMIN_USERNAME = "@Jioxt"

FORCE_CHANNEL = "@cnnetworkofficial"
FORCE_CHANNEL_ID = -1001693340041
VIDEO_GROUP_ID = -1003453185774

IST = pytz.timezone("Asia/Kolkata")

FREE_LIMIT = 5
PLANS = {
    "free": 5,
    "silver": 30,
    "gold": 50,
    "platinum": 999999
}

REF_UPGRADE = {
    10: ("silver", 3),
    25: ("gold", 7),
    50: ("platinum", 7)
}

app = Client("video_hub", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

users = {}
videos = []
banned = set()
rate_limit = {}

# ---------------- UTILS ---------------- #

def now():
    return datetime.now(IST)

def next_reset():
    t = now().replace(hour=0, minute=0, second=0)
    if now() >= t:
        t += timedelta(days=1)
    return t

def joined(client, uid):
    try:
        client.get_chat_member(FORCE_CHANNEL_ID, uid)
        return True
    except:
        return False

def init_user(uid):
    if uid not in users:
        users[uid] = {
            "used": 0,
            "credits": 0,
            "plan": "free",
            "expiry": None,
            "ref": set(),
            "last_bonus": None,
            "reset": next_reset()
        }

def reset_if_needed(uid):
    if now() >= users[uid]["reset"]:
        users[uid]["used"] = 0
        users[uid]["reset"] = next_reset()

def is_premium(uid):
    if users[uid]["plan"] == "free":
        return False
    if users[uid]["expiry"] and now() > users[uid]["expiry"]:
        users[uid]["plan"] = "free"
        users[uid]["expiry"] = None
        return False
    return True

def limit(uid):
    return PLANS[users[uid]["plan"]]

def cooldown(uid):
    if uid in rate_limit and time.time() - rate_limit[uid] < 4:
        return True
    rate_limit[uid] = time.time()
    return False

# ---------------- VIDEO COLLECT ---------------- #

@app.on_message(filters.chat(VIDEO_GROUP_ID) & filters.video)
def collect(_, m):
    videos.append(m.id)

# ---------------- START ---------------- #

@app.on_message(filters.command("start"))
def start(c, m):
    uid = m.from_user.id
    if uid in banned:
        return

    init_user(uid)

    if len(m.command) > 1:
        ref = int(m.command[1])
        if ref != uid:
            init_user(ref)
            if uid not in users[ref]["ref"]:
                users[ref]["ref"].add(uid)
                users[ref]["credits"] += 1
                c.send_message(
                    ref,
                    "🎉 New referral joined!\n💳 +1 credit added"
                )

    if not joined(c, uid):
        m.reply(
            "🔒 Join channel to use bot",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Join Channel", url="https://t.me/cnnetworkofficial")],
                [InlineKeyboardButton("🔄 Refresh", callback_data="refresh")]
            ])
        )
        return

    m.reply(
        f"👋 Welcome **{m.from_user.first_name}**\n\nChoose an option:",
        reply_markup=main_menu(uid)
    )

def main_menu(uid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Get Video", callback_data="video")],
        [InlineKeyboardButton("👤 Profile", callback_data="profile")],
        [InlineKeyboardButton("🤝 Refer & Earn", callback_data="refer")],
        [InlineKeyboardButton("💎 Premium", callback_data="premium")],
        [InlineKeyboardButton("🛠 Admin Panel", callback_data="admin")] if uid == ADMIN_ID else []
    ])

# ---------------- CALLBACKS ---------------- #

@app.on_callback_query()
def cb(c, q):
    uid = q.from_user.id
    if uid in banned:
        return

    init_user(uid)
    reset_if_needed(uid)

    if cooldown(uid):
        q.answer("⏳ Slow down!", show_alert=True)
        return

    if q.data == "refresh":
        start(c, q.message)

    elif q.data == "video":
        if not videos:
            q.message.reply("⚠️ No videos available")
            return

        lim = limit(uid)

        if users[uid]["used"] < lim or is_premium(uid):
            users[uid]["used"] += 1
        elif users[uid]["credits"] > 0:
            users[uid]["credits"] -= 1
        else:
            q.message.reply(
                f"❌ Limit reached\n⏰ Reset at 12:00 AM IST"
            )
            return

        loading = c.send_animation(
            uid,
            "https://media.giphy.com/media/3oEjI6SIIHBdRxXI40/giphy.gif"
        )

        vid = random.choice(videos)
        msg = c.forward_messages(
            uid,
            VIDEO_GROUP_ID,
            vid,
            protect_content=True
        )

        c.send_message(uid, "@cnnetworkofficial")
        asyncio.sleep(300)
        msg.delete()
        loading.delete()

    elif q.data == "refer":
        q.message.reply(
            f"👥 Referrals: {len(users[uid]['ref'])}\n"
            f"💳 Credits: {users[uid]['credits']}\n\n"
            f"🔗 https://t.me/{BOT_USERNAME}?start={uid}"
        )

    elif q.data == "premium":
        q.message.reply(
            "💎 Premium Plans\n\n"
            "🥈 Silver ₹69 – 30/day\n"
            "🥇 Gold ₹149 – 50/day\n"
            "💎 Platinum ₹499 – Unlimited\n\n"
            "🌟 Special Plan?\nContact @Jioxt"
        )

    elif q.data == "profile":
        q.message.reply(
            f"👤 {q.from_user.first_name}\n"
            f"💎 Plan: {users[uid]['plan'].title()}\n"
            f"🎥 Used: {users[uid]['used']} / {limit(uid)}\n"
            f"💳 Credits: {users[uid]['credits']}\n"
            f"⏰ Reset: 12 AM IST"
        )

    elif q.data == "admin" and uid == ADMIN_ID:
        q.message.reply(
            "🛠 Admin Panel",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Stats", callback_data="stats")],
                [InlineKeyboardButton("🏆 Leaderboard", callback_data="leader")]
            ])
        )

    elif q.data == "stats" and uid == ADMIN_ID:
        q.message.reply(
            f"👥 Users: {len(users)}\n"
            f"🎬 Videos: {len(videos)}"
        )

    elif q.data == "leader":
        top = sorted(users.items(), key=lambda x: len(x[1]["ref"]), reverse=True)[:10]
        txt = "🏆 Top Referrers\n\n"
        for i, (u, d) in enumerate(top, 1):
            txt += f"{i}. {u} – {len(d['ref'])}\n"
        q.message.reply(txt)

app.run()
