import os
import threading
import random
import json
import logging
import asyncio  # Fixed: Added missing import for asyncio
from datetime import datetime, timedelta
import pytz
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant, FloodWait

# Setup logging for better debugging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Environment variables for the bot
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Bot configuration
BOT_USERNAME = "Video_hub_xbot"
ADMIN_ID = 7271198694
FORCE_CHANNEL = "@cnnetworkofficial"
VIDEO_CHANNEL_ID = -1003604209221

TIMEZONE = pytz.timezone("Asia/Kolkata")

# Limits and plans
FREE_DAILY_LIMIT = 5
SILVER_CREDITS, GOLD_CREDITS, PLATINUM_CREDITS = 15, 25, 40

PLAN_LIMITS = {
    "silver": 30,
    "gold": 50,
    "platinum": 10**9
}

# File paths for persistence
DATA_FILE = "bot_data.json"
LOG_FILE = "bot_log.txt"

# Global data structures
app = Client("video_hub", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

USERS = {}
PREMIUM = {}
FEEDBACK = {}  # Store user feedback

# Flask web server for Render
web = Flask(__name__)

@web.route("/")
def home():
    return "Bot Running Successfully!"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    web.run(host="0.0.0.0", port=port)

# Time utilities
def now():
    return datetime.now(TIMEZONE)

def today():
    return now().date()

# Data persistence functions
def load_data():
    global USERS, PREMIUM, FEEDBACK
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                USERS = {int(k): v for k, v in data.get("users", {}).items()}
                PREMIUM = {int(k): v for k, v in data.get("premium", {}).items()}
                FEEDBACK = {int(k): v for k, v in data.get("feedback", {}).items()}
                # Convert string dates back to datetime/date objects
                for u in USERS.values():
                    if isinstance(u.get("last_reset"), str):
                        u["last_reset"] = datetime.fromisoformat(u["last_reset"]).date()
                    if isinstance(u.get("joined"), str):
                        u["joined"] = datetime.fromisoformat(u["joined"])
                    u["seen_videos"] = set(u.get("seen_videos", []))
                    u["favorite_videos"] = u.get("favorite_videos", [])  # Favorites list
                for p in PREMIUM.values():
                    if isinstance(p.get("expiry"), str):
                        p["expiry"] = datetime.fromisoformat(p["expiry"])
        except Exception as e:
            logger.error(f"Error loading data: {e}")

def save_data():
    try:
        data = {
            "users": {
                k: {
                    **v,
                    "last_reset": v["last_reset"].isoformat(),
                    "joined": v["joined"].isoformat(),
                    "seen_videos": list(v["seen_videos"]),
                    "favorite_videos": v["favorite_videos"]
                } for k, v in USERS.items()
            },
            "premium": {k: {"plan": v["plan"], "expiry": v["expiry"].isoformat()} for k, v in PREMIUM.items()},
            "feedback": FEEDBACK
        }
        with open(DATA_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Error saving data: {e}")

# Logging function for actions
def log_action(action, uid=None, details=""):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"{now()} - {action} - User: {uid} - {details}\n")
        logger.info(f"{action} - User: {uid} - {details}")
    except Exception as e:
        logger.error(f"Logging error: {e}")

# User initialization
def load_user(uid):
    if uid not in USERS:
        USERS[uid] = {
            "videos_today": 0,
            "extra_videos_today": 0,
            "last_reset": today(),
            "credits": 0,
            "referrals": 0,
            "referred_by": None,
            "seen_videos": set(),
            "favorite_videos": [],
            "joined": now(),
            "notifications": True,
            "language": "en"
        }
        save_data()
        log_action("New User Registered", uid)

# Daily reset logic
def reset_daily(uid):
    u = USERS[uid]
    reset_happened = u["last_reset"] != today()
    if reset_happened:
        u["videos_today"] = 0
        u["extra_videos_today"] = 0
        u["last_reset"] = today()
        save_data()
        log_action("Daily Reset Performed", uid)
    return reset_happened

# Premium check
def is_premium(uid):
    if uid in PREMIUM and PREMIUM[uid]["expiry"] > now():
        return PREMIUM[uid]["plan"]
    PREMIUM.pop(uid, None)
    save_data()
    return None

# Auto-upgrade based on credits
def auto_upgrade(uid):
    u = USERS[uid]
    c = u["credits"]
    if c >= PLATINUM_CREDITS:
        plan = "platinum"
        cost = PLATINUM_CREDITS
    elif c >= GOLD_CREDITS:
        plan = "gold"
        cost = GOLD_CREDITS
    elif c >= SILVER_CREDITS:
        plan = "silver"
        cost = SILVER_CREDITS
    else:
        return None
    if uid in PREMIUM:
        PREMIUM[uid]["expiry"] += timedelta(days=7)
        if PREMIUM[uid]["plan"] != plan:
            PREMIUM[uid]["plan"] = plan
    else:
        PREMIUM[uid] = {"plan": plan, "expiry": now() + timedelta(days=7)}
    u["credits"] -= cost
    save_data()
    log_action("Auto-Upgrade Triggered", uid, f"To {plan}")
    return plan

# Limit reached message
def limit_reached_message(uid):
    u = USERS[uid]
    link = f"https://t.me/{BOT_USERNAME}?start={uid}"
    extra_available = max(0, u["credits"] * 2 - u["extra_videos_today"])
    extra_text = f"\n\nExtra Videos Available with Credits: 🎥 {extra_available}" if extra_available > 0 else ""
    msg = f"""🚫 DAILY LIMIT REACHED{extra_text}

━━━━━━━━━━━━━━━━━━
🎥 FREE USER LIMIT
━━━━━━━━━━━━━━━━━━
• 5 videos per day
• Reset at 12:00 AM IST

━━━━━━━━━━━━━━━━━━
🎁 CREDIT SYSTEM
━━━━━━━━━━━━━━━━━━
• 1 Referral = 1 Credit
• 1 Credit = 🎥 2 Videos

━━━━━━━━━━━━━━━━━━
🚀 AUTO UPGRADE SYSTEM
━━━━━━━━━━━━━━━━━━
• 🥈 Silver → 15 Credits
• 🥇 Gold → 25 Credits
• 👑 Platinum → 40 Credits

━━━━━━━━━━━━━━━━━━
🤝 REFER & EARN
━━━━━━━━━━━━━━━━━━
Your Referral Link:
{link}

Pro Tip: Share on social media for faster referrals!"""
    return msg

# Keyboard markups
MAIN_MENU = ReplyKeyboardMarkup([
    [KeyboardButton("🎬 Get Video"), KeyboardButton("❤️ Favorites")],
    [KeyboardButton("👤 Profile"), KeyboardButton("🤝 Refer & Earn")],
    [KeyboardButton("💎 Premium"), KeyboardButton("🏆 Leaderboard")],
    [KeyboardButton("🔔 Notifications"), KeyboardButton("❓ Help")],
    [KeyboardButton("📢 About Bot"), KeyboardButton("🗣 Feedback")],
    [KeyboardButton("🌐 Language")]
], resize_keyboard=True)

ADMIN_MENU = ReplyKeyboardMarkup([
    [KeyboardButton("🛠 Admin Panel")],
    [KeyboardButton("🎬 Get Video"), KeyboardButton("❤️ Favorites")],
    [KeyboardButton("👤 Profile"), KeyboardButton("🤝 Refer & Earn")],
    [KeyboardButton("💎 Premium"), KeyboardButton("🏆 Leaderboard")],
    [KeyboardButton("🔔 Notifications"), KeyboardButton("❓ Help")],
    [KeyboardButton("📢 About Bot"), KeyboardButton("🗣 Feedback")],
    [KeyboardButton("🌐 Language")]
], resize_keyboard=True)

UPGRADE_BUTTONS = InlineKeyboardMarkup([
    [InlineKeyboardButton("🤝 Refer & Earn", callback_data="open_refer")],
    [InlineKeyboardButton("💎 Premium", callback_data="open_premium")],
    [InlineKeyboardButton("🗣 Give Feedback", callback_data="open_feedback")]
])

LANGUAGE_BUTTONS = InlineKeyboardMarkup([
    [InlineKeyboardButton("English", callback_data="lang_en")],
    [InlineKeyboardButton("Hindi", callback_data="lang_hi")],
    [InlineKeyboardButton("Spanish", callback_data="lang_es")]
])

# Start command handler
@app.on_message(filters.command("start"))
async def start(_, m):
    uid = m.from_user.id
    load_user(uid)
    ref = None
    if len(m.command) > 1:
        try:
            ref = int(m.command[1])
            if ref == uid or USERS[uid]["referred_by"] is not None:
                ref = None
            else:
                USERS[uid]["referred_by"] = ref
        except ValueError:
            ref = None
    try:
        await app.get_chat_member(FORCE_CHANNEL, uid)
    except UserNotParticipant:
        await m.reply("🔒 Join our channel to use this bot",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Join Channel", url="https://t.me/cnnetworkofficial")],
                [InlineKeyboardButton("🔄 Refresh", callback_data="refresh")]
            ]))
        return
    # Handle referral
    if ref and USERS[uid]["referred_by"] != "counted":
        load_user(ref)
        USERS[ref]["credits"] += 1
        USERS[ref]["referrals"] += 1
        success_msg = "🎉 Referral Success!\n+1 Credit (2 Videos)"
        upgrade_plan = auto_upgrade(ref)
        if upgrade_plan:
            success_msg += f"\n\n🚀 AUTO-UPGRADED TO {upgrade_plan.upper()} PREMIUM!"
        if USERS[ref]["notifications"]:
            try:
                await app.send_message(ref, success_msg, reply_markup=MAIN_MENU if ref != ADMIN_ID else ADMIN_MENU)
            except FloodWait as e:
                await asyncio.sleep(e.value)  # Fixed: Use e.value for seconds
        USERS[uid]["referred_by"] = "counted"
        save_data()
    # Welcome message (elaborated as per design)
    username = m.from_user.first_name or "User"
    welcome_text = f"""👋 Welcome {username} to VIDEO HUB BOT – The Ultimate Video Entertainment Hub!

🎬 Discover VIDEO HUB:
Dive into a world of endless entertainment with VIDEO HUB, your go-to Telegram bot for private, high-quality videos! From hilarious memes and viral clips to educational tutorials, motivational speeches, and trending content – we've got something for everyone. All videos are sourced from our exclusive private channel, delivered randomly to surprise you every time. No more boring repeats – each video is fresh for you!

🚀 Why Choose VIDEO HUB? Key Uses & Features:
- **Personalized Video Streaming**: Request random videos tailored to your viewing history (no duplicates!).
- **Daily Video Allowance**: Free users get 5 videos/day; premium unlocks up to unlimited access.
- **Smart Credit System**: Earn credits via referrals and redeem for extra videos or auto-upgrades.
- **Referral Rewards Program**: Invite friends, earn credits, and climb the global leaderboard.
- **Auto-Upgrade Magic**: Collect credits to unlock premium tiers automatically – no payment needed!
- **Premium Subscriptions**: Paid plans for instant boosts with higher limits and exclusive perks.
- **Daily Auto-Reset**: Fresh limits every day at 12:00 AM IST – plan your binge sessions!
- **Content Protection**: Videos can't be forwarded, ensuring privacy and exclusivity.
- **Custom Notifications**: Stay updated on referrals, upgrades, resets, and personalized alerts.
- **Global Leaderboard**: Compete with users worldwide for top referrer spots and prizes.
- **User Profile Dashboard**: Track stats, favorites, and progress in one place.
- **Feedback Channel**: Share your thoughts to help us improve – your voice matters!
- **Multi-Language Support**: Choose your preferred language for a better experience (English, Hindi, Spanish).
- **Favorites List**: Save and revisit your favorite videos anytime.
- **Advanced Admin Tools**: For seamless management by @jioxt.

━━━━━━━━━━━━━━━━━━
✨ Free User Perks
━━━━━━━━━━━━━━━━━━
• 🎥 5 High-Quality Videos Daily – Enough for quick fun or learning breaks!
• ⏰ Reset Every Midnight IST – Come back tomorrow for more.
• Full access to referrals, profile, leaderboard, and more.

━━━━━━━━━━━━━━━━━━
💎 Premium Power-Up
━━━━━━━━━━━━━━━━━━
Elevate your experience with our value-packed plans:
• 🥈 Silver (₹69): 30 videos/day for 7 days – Perfect for casual viewers.
• 🥇 Gold (₹149): 50 videos/day for 7 days – Ideal for enthusiasts.
• 👑 Platinum (₹499): Unlimited videos for 7 days – For true video addicts!
Plus: Priority content, no ads, custom video requests. Custom plans? Chat with @jioxt!

━━━━━━━━━━━━━━━━━━
🎁 Credits & Referrals Explained
━━━━━━━━━━━━━━━━━━
• 1 Referral = 1 Credit = 2 Extra Videos.
• Credits are eternal – use for bonuses or auto-upgrades:
  - 15 Credits: Silver Unlock
  - 25 Credits: Gold Unlock
  - 40 Credits: Platinum Unlock
• Secure system: Only real new users count – no cheats!

━━━━━━━━━━━━━━━━━━
👨‍💻 Proudly Owned by @jioxt
━━━━━━━━━━━━━━━━━━
@jioxt is the visionary behind VIDEO HUB, ensuring top-notch content and support. For queries, payments, custom features, or collaborations, message @jioxt directly. We're here to make your video journey amazing!

Ready to dive in? Tap 🎬 Get Video now! 🍿
Explore the menu for more options. Happy watching!"""
    markup = ADMIN_MENU if uid == ADMIN_ID else MAIN_MENU
    await m.reply(welcome_text, reply_markup=markup)
    # Check auto-upgrade for current user
    upgrade_plan = auto_upgrade(uid)
    if upgrade_plan:
        await m.reply(f"🚀 AUTO-UPGRADED TO {upgrade_plan.upper()} PREMIUM!\nUnlock more videos and features for 7 days.", reply_markup=markup)

# Callback for refresh
@app.on_callback_query(filters.regex("refresh"))
async def refresh_callback(_, cb):
    uid = cb.from_user.id
    try:
        await app.get_chat_member(FORCE_CHANNEL, uid)
        m = type("Message", (), {"from_user": cb.from_user, "chat": {"id": cb.message.chat.id}, "command": []})
        await start(_, m)
        await cb.message.delete()
    except UserNotParticipant:
        await cb.answer("Join the channel first!", show_alert=True)

# Callback for opening sections
@app.on_callback_query(filters.regex(r"open_(refer|premium|feedback)"))
async def open_section_callback(_, cb):
    uid = cb.from_user.id
    load_user(uid)
    reset_daily(uid)
    section = cb.matches[0].group(1)
    m = type("Message", (), {"from_user": cb.from_user, "chat": {"id": cb.message.chat.id}, "text": ""})
    if section == "refer":
        await refer(m)
    elif section == "premium":
        await premium(m)
    elif section == "feedback":
        await feedback(m)
    await cb.message.edit_reply_markup(None)

# Language callback
@app.on_callback_query(filters.regex(r"lang_(en|hi|es)"))
async def set_language(_, cb):
    uid = cb.from_user.id
    lang = cb.matches[0].group(1)
    USERS[uid]["language"] = lang
    await cb.answer(f"Language set to {lang.upper()}. Note: Full support coming soon!", show_alert=True)
    save_data()

# Router for text messages
@app.on_message(filters.text & ~filters.command(""))
async def router(_, m):
    uid = m.from_user.id
    load_user(uid)
    reset_happened = reset_daily(uid)
    upgrade_plan = auto_upgrade(uid)
    text = m.text
    markup = ADMIN_MENU if uid == ADMIN_ID else MAIN_MENU  # Fixed: Defined markup here
    if reset_happened and USERS[uid]["notifications"]:
        reset_msg = """🌙 DAILY RESET COMPLETE!

Limits refreshed – enjoy fresh videos!
Credits intact. Start with 🎬 Get Video 🍿"""
        await m.reply(reset_msg, reply_markup=markup)
    if upgrade_plan:
        await m.reply(f"🚀 AUTO-UPGRADED TO {upgrade_plan.upper()}!\nMore videos await – happy viewing!", reply_markup=markup)
    if text == "🎬 Get Video":
        await send_video(m)
    elif text == "❤️ Favorites":
        await favorites(m)
    elif text == "👤 Profile":
        await profile(m)
    elif text == "🤝 Refer & Earn":
        await refer(m)
    elif text == "💎 Premium":
        await premium(m)
    elif text == "🏆 Leaderboard":
        await leaderboard_user(m)
    elif text == "🔔 Notifications":
        await toggle_notifications(m)
    elif text == "❓ Help":
        await help_command(m)
    elif text == "📢 About Bot":
        await about_bot(m)
    elif text == "🗣 Feedback":
        await feedback(m)
    elif text == "🌐 Language":
        await m.reply("Choose language:", reply_markup=LANGUAGE_BUTTONS)
    elif text == "🛠 Admin Panel" and uid == ADMIN_ID:
        await admin(m)

# Send video handler
async def send_video(m):
    uid = m.from_user.id
    load_user(uid)
    reset_daily(uid)
    plan = is_premium(uid)
    u = USERS[uid]
    markup = ADMIN_MENU if uid == ADMIN_ID else MAIN_MENU  # Fixed: Defined markup
    if plan:
        daily_limit = PLAN_LIMITS[plan]
        if u["videos_today"] >= daily_limit:
            await m.reply("🚫 Premium limit reached. Wait for reset or upgrade higher!", reply_markup=markup)
            return
        using_extra = False
    else:
        daily_limit = FREE_DAILY_LIMIT
        if u["videos_today"] >= daily_limit:
            using_extra = True
            next_extra = u["extra_videos_today"] + 1
            if next_extra > u["credits"] * 2:
                await m.reply(limit_reached_message(uid), reply_markup=UPGRADE_BUTTONS)
                return
        else:
            using_extra = False
    # Fetch available videos
    vids = []
    async for msg_ in app.get_chat_history(VIDEO_CHANNEL_ID, limit=1000):
        if msg_.video and msg_.id not in u["seen_videos"]:
            vids.append(msg_)
    if not vids:
        await m.reply("No new videos yet. Adding soon – stay tuned!", reply_markup=markup)
        return
    v = random.choice(vids)
    u["seen_videos"].add(v.id)
    if using_extra:
        u["extra_videos_today"] += 1
        if u["extra_videos_today"] % 2 == 0:
            u["credits"] -= 1
            if u["credits"] < 0:
                u["credits"] = 0
            if u["notifications"]:
                await m.reply("📉 Credit used. Refer for more!", reply_markup=markup)
    else:
        u["videos_today"] += 1
    await app.copy_message(m.chat.id, VIDEO_CHANNEL_ID, v.id, protect_content=True)
    total_today = u["videos_today"] + u["extra_videos_today"]
    await m.reply(f"🍿 Video delivered! Enjoy.\nToday: {total_today}\nFavorite it? Reply /favorite {v.id}", reply_markup=markup)
    save_data()
    log_action("Video Sent", uid, str(v.id))

# Favorites handler
async def favorites(m):
    uid = m.from_user.id
    u = USERS[uid]
    markup = ADMIN_MENU if uid == ADMIN_ID else MAIN_MENU  # Fixed: Defined markup
    if not u["favorite_videos"]:
        await m.reply("No favorites yet. Favorite videos by replying /favorite <id> after receiving one.", reply_markup=markup)
        return
    msg = "❤️ Your Favorites:\n"
    for vid in u["favorite_videos"][:10]:  # Limit to 10 for brevity
        msg += f"- Video ID: {vid}\n"
    if len(u["favorite_videos"]) > 10:
        msg += f"... and {len(u['favorite_videos']) - 10} more."
    await m.reply(msg, reply_markup=markup)
    await m.reply("Want to re-watch? Reply /rewatch <id>")

# Add favorite command
@app.on_message(filters.command("favorite"))
async def add_favorite(_, m):
    uid = m.from_user.id
    if len(m.command) < 2:
        await m.reply("Usage: /favorite <video_id>")
        return
    try:
        vid = int(m.command[1])
        if vid in USERS[uid]["seen_videos"] and vid not in USERS[uid]["favorite_videos"]:
            USERS[uid]["favorite_videos"].append(vid)
            await m.reply("❤️ Added to favorites!")
            save_data()
        else:
            await m.reply("Invalid or already favorited.")
    except ValueError:
        await m.reply("Invalid video ID.")

# Rewatch favorite command
@app.on_message(filters.command("rewatch"))
async def rewatch_favorite(_, m):
    uid = m.from_user.id
    if len(m.command) < 2:
        await m.reply("Usage: /rewatch <video_id>")
        return
    try:
        vid = int(m.command[1])
        if vid in USERS[uid]["favorite_videos"]:
            await app.copy_message(m.chat.id, VIDEO_CHANNEL_ID, vid, protect_content=True)
            await m.reply("🍿 Re-watching favorite!")
        else:
            await m.reply("Not in favorites.")
    except ValueError:
        await m.reply("Invalid video ID.")

# Profile handler
async def profile(m):
    uid = m.from_user.id
    u = USERS[uid]
    plan = is_premium(uid)
    prem_str = plan.upper() if plan else "No"
    if plan:
        expiry = PREMIUM[uid]["expiry"].strftime("%d-%m-%Y %H:%M")
        prem_str += f" (Expires: {expiry})"
    videos_from_credits = u["credits"] * 2
    total_today = u["videos_today"] + u["extra_videos_today"]
    joined_str = u["joined"].strftime("%d-%m-%Y")
    notif_str = "Enabled" if u["notifications"] else "Disabled"
    lang_str = u["language"].upper()
    daily_remaining = PLAN_LIMITS.get(plan, FREE_DAILY_LIMIT) - u["videos_today"]
    extra_remaining = videos_from_credits - u["extra_videos_today"]
    favorites_count = len(u["favorite_videos"])
    markup = ADMIN_MENU if uid == ADMIN_ID else MAIN_MENU  # Fixed: Defined markup
    msg = f"""👤 PROFILE DASHBOARD

━━━━━━━━━━━━━━━━━━
Videos Today: {total_today} (Remaining: {max(0, daily_remaining)})
Extra Remaining: {max(0, extra_remaining)}
Credits: {u['credits']} (🎥 {videos_from_credits})
Referrals: {u['referrals']}
Favorites: {favorites_count}
Premium: {prem_str}
Joined: {joined_str}
Notifications: {notif_str}
Language: {lang_str}

━━━━━━━━━━━━━━━━━━
Tip: Favorite videos to build your collection!"""
    await m.reply(msg, reply_markup=markup)

# Refer handler
async def refer(m):
    uid = m.from_user.id
    link = f"https://t.me/{BOT_USERNAME}?start={uid}"
    markup = ADMIN_MENU if uid == ADMIN_ID else MAIN_MENU  # Fixed: Defined markup
    msg = f"""🤝 REFER & EARN REWARDS

Invite friends to VIDEO HUB and reap benefits!
• 1 Referral = 1 Credit = 2 Extra Videos

Guide:
- Share link.
- New user joins channel.
- Genuine only – no fakes.

Upgrades:
• 🥈 Silver: 15 Credits
• 🥇 Gold: 25 Credits
• 👑 Platinum: 40 Credits

Link: {link}

Pro Tip: Post in groups for max referrals!"""
    await m.reply(msg, reply_markup=markup)

# Premium handler
async def premium(m):
    markup = ADMIN_MENU if m.from_user.id == ADMIN_ID else MAIN_MENU  # Fixed: Defined markup
    msg = """💎 PREMIUM UNLOCKS

Boost your access:
• 🥈 Silver ₹69: 30/day, 7 days
• 🥇 Gold ₹149: 50/day, 7 days
• 👑 Platinum ₹499: Unlimited, 7 days

Perks: Priority, customs.

Contact @jioxt for payment!"""
    await m.reply(msg, reply_markup=markup)

# Leaderboard handler
async def leaderboard_user(m):
    ref_list = sorted(USERS.items(), key=lambda x: x[1]["referrals"], reverse=True)[:10]
    msg = "🏆 LEADERBOARD TOP 10\n"
    for i, (uid, u) in enumerate(ref_list, 1):
        try:
            user = await app.get_users(uid)
            username = user.first_name or f"User {uid}"
            msg += f"{i}. {username}: {u['referrals']}\n"
        except:
            msg += f"{i}. User {uid}: {u['referrals']}\n"
    pos = next((i+1 for i, (k,v) in enumerate(sorted(USERS.items(), key=lambda x: x[1]["referrals"], reverse=True)) if k == m.from_user.id), "N/A")
    msg += f"\nYour Rank: {pos}"
    markup = ADMIN_MENU if m.from_user.id == ADMIN_ID else MAIN_MENU  # Fixed: Defined markup
    await m.reply(msg, reply_markup=markup)

# Toggle notifications
async def toggle_notifications(m):
    uid = m.from_user.id
    USERS[uid]["notifications"] = not USERS[uid]["notifications"]
    status = "enabled" if USERS[uid]["notifications"] else "disabled"
    markup = ADMIN_MENU if uid == ADMIN_ID else MAIN_MENU  # Fixed: Defined markup
    await m.reply(f"🔔 Notifications {status}.", reply_markup=markup)
    save_data()

# Help handler
async def help_command(m):
    markup = ADMIN_MENU if m.from_user.id == ADMIN_ID else MAIN_MENU  # Fixed: Defined markup
    msg = """❓ FULL HELP GUIDE

- 🎬 Get Video: Random video.
- ❤️ Favorites: View/save.
- 👤 Profile: Stats.
- 🤝 Refer: Link.
- 💎 Premium: Plans.
- 🏆 Leaderboard: Ranks.
- 🔔 Notifications: Toggle.
- 📢 About: Info.
- 🗣 Feedback: Share thoughts.
- 🌐 Language: Select.

Support: @jioxt"""
    await m.reply(msg, reply_markup=markup)

# About handler
async def about_bot(m):
    markup = ADMIN_MENU if m.from_user.id == ADMIN_ID else MAIN_MENU  # Fixed: Defined markup
    msg = """📢 VIDEO HUB INFO

Premier video bot by @jioxt.
Exclusive content, secure.
Join @cnnetworkofficial.
Feedback welcome!"""
    await m.reply(msg, reply_markup=markup)

# Feedback handler
async def feedback(m):
    markup = ADMIN_MENU if m.from_user.id == ADMIN_ID else MAIN_MENU  # Fixed: Defined markup
    await m.reply("🗣 Share feedback: Reply with your message.", reply_markup=markup)

# Receive feedback (reply handler)
@app.on_message(filters.reply & filters.text)
async def receive_feedback(_, m):
    if "Share feedback" in m.reply_to_message.text:
        uid = m.from_user.id
        fb = m.text
        FEEDBACK[uid] = fb
        await m.reply("Thanks for feedback!")
        try:
            await app.send_message(ADMIN_ID, f"Feedback from {uid}: {fb}")
        except:
            pass
        save_data()
        log_action("Feedback Received", uid, fb[:50] + "..." if len(fb) > 50 else fb)

# Admin panel
async def admin(m):
    markup = ADMIN_MENU  # Fixed: Defined markup
    msg = """🛠 ADMIN COMMANDS

/addpremium <uid> <plan> <days>
/removepremium <uid>
/addcredits <uid> <credits>
/broadcast <msg>
/stats
/leaderboard
/userinfo <uid>
/viewfeedback
/viewlogs"""
    await m.reply(msg, reply_markup=markup)

# Admin commands
@app.on_message(filters.command("addpremium") & filters.user(ADMIN_ID))
async def addprem(_, m):
    try:
        parts = m.text.split()
        uid = int(parts[1])
        plan = parts[2].lower()
        days = int(parts[3])
        if plan not in PLAN_LIMITS:
            await m.reply("Invalid plan.")
            return
        if uid in PREMIUM:
            PREMIUM[uid]["expiry"] += timedelta(days=days)
            if PREMIUM[uid]["plan"] != plan:
                PREMIUM[uid]["plan"] = plan
        else:
            PREMIUM[uid] = {"plan": plan, "expiry": now() + timedelta(days=days)}
        load_user(uid)
        await m.reply(f"Premium added: {plan} {days} days to {uid}")
        if USERS[uid]["notifications"]:
            await app.send_message(uid, f"🎉 Premium {plan.upper()} for {days} days!")
        save_data()
        log_action("Add Premium", uid, f"{plan} {days}")
    except:
        await m.reply("Usage: /addpremium <uid> <plan> <days>")

@app.on_message(filters.command("removepremium") & filters.user(ADMIN_ID))
async def removeprem(_, m):
    try:
        uid = int(m.text.split()[1])
        PREMIUM.pop(uid, None)
        await m.reply(f"Premium removed {uid}")
        if uid in USERS and USERS[uid]["notifications"]:
            await app.send_message(uid, "Premium removed.")
        save_data()
        log_action("Remove Premium", uid)
    except:
        await m.reply("Usage: /removepremium <uid>")

@app.on_message(filters.command("addcredits") & filters.user(ADMIN_ID))
async def addcredits(_, m):
    try:
        parts = m.text.split()
        uid = int(parts[1])
        credits = int(parts[2])
        load_user(uid)
        USERS[uid]["credits"] += credits
        await m.reply(f"Added {credits} to {uid}")
        if USERS[uid]["notifications"]:
            await app.send_message(uid, f"+{credits} Credits!")
        auto_upgrade(uid)
        save_data()
        log_action("Add Credits", uid, credits)
    except:
        await m.reply("Usage: /addcredits <uid> <credits>")

@app.on_message(filters.command("broadcast") & filters.user(ADMIN_ID))
async def bc(_, m):
    msg = m.text.replace("/broadcast", "").strip()
    if not msg:
        await m.reply("Usage: /broadcast <msg>")
        return
    sent = 0
    for uid in list(USERS.keys()):
        try:
            markup = MAIN_MENU if uid != ADMIN_ID else ADMIN_MENU
            await app.send_message(uid, msg, reply_markup=markup)
            sent += 1
        except:
            pass
    await m.reply(f"Sent to {sent} users")
    log_action("Broadcast", details=msg[:50] + "..." if len(msg) > 50 else msg)

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats(_, m):
    user_count = len(USERS)
    prem_count = sum(1 for uid in USERS if is_premium(uid))
    total_videos = sum(u["videos_today"] + u["extra_videos_today"] for u in USERS.values())
    total_credits = sum(u["credits"] for u in USERS.values())
    total_referrals = sum(u["referrals"] for u in USERS.values())
    total_favorites = sum(len(u["favorite_videos"]) for u in USERS.values())
    msg = f"📊 STATS\nUsers: {user_count}\nPremium: {prem_count}\nVideos Today: {total_videos}\nCredits: {total_credits}\nReferrals: {total_referrals}\nFavorites: {total_favorites}"
    await m.reply(msg)

@app.on_message(filters.command("leaderboard") & filters.user(ADMIN_ID))
async def leaderboard(_, m):
    ref_list = sorted(USERS.items(), key=lambda x: x[1]["referrals"], reverse=True)[:10]
    msg = "🏆 ADMIN LEADERBOARD\n"
    for i, (uid, u) in enumerate(ref_list, 1):
        try:
            user = await app.get_users(uid)
            username = user.first_name or f"User {uid}"
            msg += f"{i}. {username} ({uid}): {u['referrals']}\n"
        except:
            msg += f"{i}. User {uid}: {u['referrals']}\n"
    await m.reply(msg)

@app.on_message(filters.command("userinfo") & filters.user(ADMIN_ID))
async def userinfo(_, m):
    try:
        uid = int(m.text.split()[1])
        if uid not in USERS:
            await m.reply("User not found.")
            return
        u = USERS[uid]
        plan = is_premium(uid)
        prem_str = plan.upper() if plan else "No"
        if plan:
            expiry = PREMIUM[uid]["expiry"].strftime("%d-%m-%Y %H:%M")
            prem_str += f" ({expiry})"
        videos_from_credits = u["credits"] * 2
        total_today = u["videos_today"] + u["extra_videos_today"]
        joined_str = u["joined"].strftime("%d-%m-%Y")
        notif_str = "Enabled" if u["notifications"] else "Disabled"
        lang_str = u["language"].upper()
        favorites = len(u["favorite_videos"])
        try:
            user = await app.get_users(uid)
            username = user.first_name or "Unknown"
        except:
            username = "Unknown"
        msg = f"👤 {uid} ({username})\nVideos Today: {total_today}\nCredits: {u['credits']} ({videos_from_credits})\nReferrals: {u['referrals']}\nFavorites: {favorites}\nPremium: {prem_str}\nJoined: {joined_str}\nNotifications: {notif_str}\nLanguage: {lang_str}\nSeen: {len(u['seen_videos'])}"
        await m.reply(msg)
    except:
        await m.reply("Usage: /userinfo <uid>")

@app.on_message(filters.command("viewfeedback") & filters.user(ADMIN_ID))
async def view_feedback(_, m):
    if not FEEDBACK:
        await m.reply("No feedback yet.")
        return
    msg = "🗣 FEEDBACKS\n"
    for uid, fb in list(FEEDBACK.items())[-10:]:  # Last 10
        msg += f"User {uid}: {fb}\n"
    await m.reply(msg)

@app.on_message(filters.command("viewlogs") & filters.user(ADMIN_ID))
async def view_logs(_, m):
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            logs = f.read()[-2000:]  # Last 2000 chars
        await m.reply(f"Recent Logs:\n{logs}")
    else:
        await m.reply("No logs.")

# Main execution
if __name__ == "__main__":
    load_data()
    threading.Thread(target=run_flask, daemon=True).start()
    app.run()
