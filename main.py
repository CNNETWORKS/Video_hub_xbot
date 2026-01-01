import os
import threading
import random
import json
from datetime import datetime, timedelta
import pytz
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

BOT_USERNAME = "Video_hub_xbot"
ADMIN_ID = 7271198694
FORCE_CHANNEL = "@cnnetworkofficial"
VIDEO_CHANNEL_ID = -1003604209221

TIMEZONE = pytz.timezone("Asia/Kolkata")

FREE_DAILY_LIMIT = 5
SILVER_CREDITS, GOLD_CREDITS, PLATINUM_CREDITS = 15, 25, 40

PLAN_LIMITS = {
    "silver": 30,
    "gold": 50,
    "platinum": 10**9
}

DATA_FILE = "bot_data.json"

app = Client("video_hub", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

USERS = {}
PREMIUM = {}

web = Flask(__name__)
@web.route("/")
def home():
    return "Bot Running"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    web.run(host="0.0.0.0", port=port)

def now():
    return datetime.now(TIMEZONE)

def today():
    return now().date()

def load_data():
    global USERS, PREMIUM
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            USERS = {int(k): v for k, v in data.get("users", {}).items()}
            PREMIUM = {int(k): v for k, v in data.get("premium", {}).items()}
            # Convert dates
            for u in USERS.values():
                u["last_reset"] = datetime.fromisoformat(u["last_reset"]).date() if isinstance(u["last_reset"], str) else u["last_reset"]
                u["joined"] = datetime.fromisoformat(u["joined"]) if isinstance(u["joined"], str) else u["joined"]
                u["seen_videos"] = set(u["seen_videos"])
            for p in PREMIUM.values():
                p["expiry"] = datetime.fromisoformat(p["expiry"]) if isinstance(p["expiry"], str) else p["expiry"]

def save_data():
    data = {
        "users": {k: {**v, "last_reset": v["last_reset"].isoformat(), "joined": v["joined"].isoformat(), "seen_videos": list(v["seen_videos"])} for k, v in USERS.items()},
        "premium": {k: {**v, "expiry": v["expiry"].isoformat()} for k, v in PREMIUM.items()}
    }
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

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
            "joined": now(),
            "notifications": True  # New: User can toggle notifications
        }
        save_data()

def reset_daily(uid):
    u = USERS[uid]
    reset_happened = u["last_reset"] != today()
    if reset_happened:
        u["videos_today"] = 0
        u["extra_videos_today"] = 0
        u["last_reset"] = today()
        save_data()
    return reset_happened

def is_premium(uid):
    if uid in PREMIUM and PREMIUM[uid]["expiry"] > now():
        return PREMIUM[uid]["plan"]
    PREMIUM.pop(uid, None)
    save_data()
    return None

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
    return plan

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
{link}"""
    return msg

MAIN_MENU = ReplyKeyboardMarkup([
    [KeyboardButton("🎬 Get Video")],
    [KeyboardButton("👤 Profile"), KeyboardButton("🤝 Refer & Earn")],
    [KeyboardButton("💎 Premium"), KeyboardButton("🏆 Leaderboard")],
    [KeyboardButton("🔔 Notifications"), KeyboardButton("❓ Help")],
    [KeyboardButton("📢 About Bot")]
], resize_keyboard=True)

ADMIN_MENU = ReplyKeyboardMarkup([
    [KeyboardButton("🛠 Admin Panel")],
    [KeyboardButton("🎬 Get Video")],
    [KeyboardButton("👤 Profile"), KeyboardButton("🤝 Refer & Earn")],
    [KeyboardButton("💎 Premium"), KeyboardButton("🏆 Leaderboard")],
    [KeyboardButton("🔔 Notifications"), KeyboardButton("❓ Help")],
    [KeyboardButton("📢 About Bot")]
], resize_keyboard=True)

UPGRADE_BUTTONS = InlineKeyboardMarkup([
    [InlineKeyboardButton("🤝 Refer & Earn", callback_data="open_refer")],
    [InlineKeyboardButton("💎 Premium", callback_data="open_premium")]
])

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
    # Joined channel
    if ref and USERS[uid]["referred_by"] != "counted":
        load_user(ref)
        USERS[ref]["credits"] += 1
        USERS[ref]["referrals"] += 1
        success_msg = "🎉 Referral Success!\n+1 Credit (2 Videos)"
        upgrade_plan = auto_upgrade(ref)
        if upgrade_plan:
            success_msg += f"\n\n🚀 AUTO-UPGRADED TO {upgrade_plan.upper()} PREMIUM!"
        if USERS[ref]["notifications"]:
            await app.send_message(ref, success_msg, reply_markup=MAIN_MENU if ref != ADMIN_ID else ADMIN_MENU)
        USERS[uid]["referred_by"] = "counted"
        save_data()
    # Elaborate welcome message
    username = m.from_user.first_name or "User"
    welcome_text = f"""👋 Welcome {username} to VIDEO HUB BOT!

🎬 What is VIDEO HUB?
VIDEO HUB is your ultimate private and protected video platform on Telegram! Designed for entertainment enthusiasts, this bot delivers high-quality, exclusive videos directly to your chat. Whether you're looking for fun clips, educational content, motivational videos, or trending reels, VIDEO HUB has it all – sourced from our private channel and delivered randomly to keep things exciting and fresh every time!

🚀 Uses & Features:
- **Random Video Delivery**: Get a new, unseen video each time you request one – no repeats for the same user!
- **Daily Limits with Flexibility**: As a free user, enjoy 5 videos per day. Premium users get more – up to unlimited!
- **Credit System for Extra Access**: Earn credits through referrals and use them for bonus videos beyond your daily limit (1 credit = 2 extra videos).
- **Auto-Upgrade System**: Accumulate credits to automatically unlock premium tiers without paying – perfect for active referrers!
- **Referral Program**: Share your link, earn credits, and climb the leaderboard.
- **Premium Plans**: Paid options for instant upgrades with higher limits.
- **Daily Reset**: Limits refresh every day at 12:00 AM IST, so you can start fresh.
- **Protected Content**: Videos are sent with forwarding disabled to keep them private.
- **Notifications**: Get alerts for referrals, upgrades, resets, and more (toggleable).
- **Leaderboard**: See top referrers and compete for the top spots.
- **Profile Stats**: Track your videos watched, credits, referrals, and premium status.
- **Help & About**: Quick guides and bot info at your fingertips.
- **Admin Tools**: For the owner to manage users, broadcast updates, and view stats.

━━━━━━━━━━━━━━━━━━
✨ WHAT YOU GET AS A FREE USER
━━━━━━━━━━━━━━━━━━
• 🎥 5 videos every day – perfect for casual viewing!
• ⏰ Automatic reset at 12:00 AM IST, so you never miss out on daily entertainment.
• Access to all basic features like profile, referrals, and leaderboard.

━━━━━━━━━━━━━━━━━━
💎 ABOUT PREMIUM
━━━━━━━━━━━━━━━━━━
Upgrade to premium for unlimited fun! Our plans are affordable and packed with value:
• 🥈 Silver – ₹69: 30 videos/day for 7 days – ideal for moderate users.
• 🥇 Gold – ₹149: 50 videos/day for 7 days – great for binge-watchers.
• 👑 Platinum – ₹499: Unlimited videos for 7 days – the ultimate experience!
Custom plans available too! Contact the owner @jioxt for payments, activations, or questions. Premium users also get priority support and early access to new features.

━━━━━━━━━━━━━━━━━━
🎁 ABOUT CREDITS & REFERRALS
━━━━━━━━━━━━━━━━━━
• Earn 1 Credit per successful referral (new user who joins the channel via your link).
• 1 Credit = 🎥 2 Extra Videos – use them after your daily limit.
• Credits never expire and can be used for auto-upgrades:
  - 15 Credits → 🥈 Silver (7 days)
  - 25 Credits → 🥇 Gold (7 days)
  - 40 Credits → 👑 Platinum (7 days)
• Anti-fake system: Only genuine new referrals count – no self-referrals or duplicates.

━━━━━━━━━━━━━━━━━━
👨‍💻 Owned & Managed by @jioxt
━━━━━━━━━━━━━━━━━━
@jioxt is the creator and admin of VIDEO HUB. For any support, custom requests, premium activations, or feedback, reach out directly. We're committed to providing a safe, fun, and engaging video experience!

Tap 🎬 Get Video to start watching 🍿
Or explore the menu for more!"""
    markup = ADMIN_MENU if uid == ADMIN_ID else MAIN_MENU
    await m.reply(welcome_text, reply_markup=markup)
    # Check auto-upgrade for current user
    upgrade_plan = auto_upgrade(uid)
    if upgrade_plan:
        await m.reply(f"🚀 AUTO-UPGRADED TO {upgrade_plan.upper()} PREMIUM!\nEnjoy unlimited access for 7 days.", reply_markup=markup)

@app.on_callback_query(filters.regex("refresh"))
async def refresh_callback(_, cb):
    uid = cb.from_user.id
    try:
        await app.get_chat_member(FORCE_CHANNEL, uid)
        # Trigger start logic
        m = type("Message", (), {"from_user": cb.from_user, "chat": {"id": cb.message.chat.id}, "command": []})
        await start(_, m)
        await cb.message.delete()
    except UserNotParticipant:
        await cb.answer("Please join the channel first!", show_alert=True)

@app.on_callback_query(filters.regex(r"open_(refer|premium)"))
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
    await cb.message.edit_reply_markup(None)

@app.on_message(filters.text & ~filters.command(""))
async def router(_, m):
    uid = m.from_user.id
    load_user(uid)
    reset_happened = reset_daily(uid)
    upgrade_plan = auto_upgrade(uid)
    text = m.text
    markup = ADMIN_MENU if uid == ADMIN_ID else MAIN_MENU
    if reset_happened:
        reset_msg = """🌙 DAILY RESET COMPLETE!

Your daily limit has been refreshed.
Credits remain unchanged.
Tap 🎬 Get Video to start 🍿"""
        if USERS[uid]["notifications"]:
            await m.reply(reset_msg, reply_markup=markup)
    if upgrade_plan:
        await m.reply(f"🚀 AUTO-UPGRADED TO {upgrade_plan.upper()} PREMIUM!\nEnjoy your new benefits.", reply_markup=markup)
    if text == "🎬 Get Video":
        await send_video(m)
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
    elif text == "🛠 Admin Panel" and uid == ADMIN_ID:
        await admin(m)

async def send_video(m):
    uid = m.from_user.id
    load_user(uid)
    reset_daily(uid)
    plan = is_premium(uid)
    u = USERS[uid]
    if plan:
        daily_limit = PLAN_LIMITS[plan]
        if u["videos_today"] >= daily_limit:
            await m.reply("🚫 Daily limit for your premium plan reached.\nReset at 12:00 AM IST.", reply_markup=MAIN_MENU if uid != ADMIN_ID else ADMIN_MENU)
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
    # Fetch videos
    vids = []
    async for msg_ in app.get_chat_history(VIDEO_CHANNEL_ID, limit=1000):  # Increased for more variety
        if msg_.video and msg_.id not in u["seen_videos"]:
            vids.append(msg_)
    if not vids:
        await m.reply("No new videos available right now. Our team is adding more soon! Check back later.", reply_markup=MAIN_MENU if uid != ADMIN_ID else ADMIN_MENU)
        return
    v = random.choice(vids)
    u["seen_videos"].add(v.id)
    if using_extra:
        u["extra_videos_today"] += 1
        if u["extra_videos_today"] % 2 == 0:
            u["credits"] -= 1
            if u["credits"] < 0:
                u["credits"] = 0
            if USERS[uid]["notifications"]:
                await m.reply("📉 1 Credit used for extra videos. Keep referring to earn more!")
    else:
        u["videos_today"] += 1
    await app.copy_message(m.chat.id, VIDEO_CHANNEL_ID, v.id, protect_content=True)
    total_today = u["videos_today"] + u["extra_videos_today"]
    await m.reply(f"🍿 Enjoy your video! This is a random pick from our exclusive collection.\n\nVideos watched today: {total_today}\nRemaining today: {daily_limit - u['videos_today'] if not using_extra else 'Using extras!'}\n\nRate it or share feedback with @jioxt!", reply_markup=MAIN_MENU if uid != ADMIN_ID else ADMIN_MENU)
    save_data()

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
    daily_remaining = PLAN_LIMITS.get(plan, FREE_DAILY_LIMIT) - u["videos_today"]
    extra_remaining = videos_from_credits - u["extra_videos_today"]
    msg = f"""👤 YOUR PROFILE

━━━━━━━━━━━━━━━━━━
Videos Watched Today: {total_today}
Daily Remaining: {max(0, daily_remaining)}
Extra from Credits: {max(0, extra_remaining)}
Credits: {u['credits']} (🎥 {videos_from_credits} extra videos total)
Referrals: {u['referrals']}
Premium Status: {prem_str}
Joined Date: {joined_str}
Notifications: {notif_str}

━━━━━━━━━━━━━━━━━━
Pro Tip: Refer more friends to earn credits and auto-upgrade!"""
    await m.reply(msg, reply_markup=MAIN_MENU if uid != ADMIN_ID else ADMIN_MENU)

async def refer(m):
    uid = m.from_user.id
    u = USERS[uid]
    link = f"https://t.me/{BOT_USERNAME}?start={uid}"
    msg = f"""🤝 REFER & EARN

Earn rewards by sharing VIDEO HUB with friends!
• 1 Successful Referral = 1 Credit
• 1 Credit = 2 Extra Videos (use after daily limit)

How it Works:
- Share your unique link below.
- New users must join our channel (@cnnetworkofficial) via your link.
- Anti-fake: No self-referrals, duplicates, or bots – only genuine new users count.

AUTO-UPGRADE TARGETS
• 🥈 Silver – 15 Credits (30 videos/day for 7 days)
• 🥇 Gold – 25 Credits (50 videos/day for 7 days)
• 👑 Platinum – 40 Credits (Unlimited for 7 days)

Your Unique Referral Link:
{link}

Start referring now and unlock premium for free! 🚀"""
    await m.reply(msg, reply_markup=MAIN_MENU if uid != ADMIN_ID else ADMIN_MENU)

async def premium(m):
    msg = """💎 PREMIUM PLANS

Unlock more videos and exclusive perks with our premium subscriptions!
• 🥈 Silver – ₹69: 30 videos/day, 7 days duration – Great starter plan!
• 🥇 Gold – ₹149: 50 videos/day, 7 days duration – For serious viewers!
• 👑 Platinum – ₹499: Unlimited videos, 7 days duration – No limits, pure entertainment!

Benefits:
- Higher daily limits
- Priority video access
- Ad-free experience (no promotions in chats)
- Custom requests to @jioxt

Custom Plans: Need longer duration or special limits? Contact @jioxt for tailored options.

How to Upgrade:
1. Choose your plan.
2. Contact @jioxt for payment details (UPI, PayPal, etc.).
3. Get activated instantly!

Go premium today and elevate your video experience! 💫"""
    await m.reply(msg, reply_markup=MAIN_MENU if m.from_user.id != ADMIN_ID else ADMIN_MENU)

async def leaderboard_user(m):
    ref_list = sorted(USERS.items(), key=lambda x: x[1]["referrals"], reverse=True)[:10]
    msg = "🏆 TOP 10 REFERRERS LEADERBOARD\n\nCompete to be #1 and win special rewards from @jioxt!\n\n"
    for i, (uid, u) in enumerate(ref_list, 1):
        user = await app.get_users(uid)
        username = user.first_name or f"User {uid}"
        msg += f"{i}. {username}: {u['referrals']} referrals\n"
    msg += "\nYour Position: " + str(next((i+1 for i, (k,v) in enumerate(sorted(USERS.items(), key=lambda x: x[1]["referrals"], reverse=True)) if k == m.from_user.id), "Not in top 10")) + "\n\nRefer more to climb up!"
    await m.reply(msg, reply_markup=MAIN_MENU if m.from_user.id != ADMIN_ID else ADMIN_MENU)

async def toggle_notifications(m):
    uid = m.from_user.id
    USERS[uid]["notifications"] = not USERS[uid]["notifications"]
    status = "enabled" if USERS[uid]["notifications"] else "disabled"
    await m.reply(f"🔔 Notifications {status}.\nYou'll {'now' if USERS[uid]['notifications'] else 'no longer'} receive alerts for referrals, upgrades, resets, etc.", reply_markup=MAIN_MENU if uid != ADMIN_ID else ADMIN_MENU)
    save_data()

async def help_command(m):
    msg = """❓ HELP & GUIDE

Welcome to VIDEO HUB! Here's how to use the bot:

- 🎬 Get Video: Request a random, exclusive video from our collection.
- 👤 Profile: View your stats like videos watched, credits, referrals, and premium details.
- 🤝 Refer & Earn: Get your referral link and earn credits for new users.
- 💎 Premium: Check plans and contact @jioxt to upgrade.
- 🏆 Leaderboard: See top referrers and your position.
- 🔔 Notifications: Toggle alerts on/off.
- 📢 About Bot: Learn more about VIDEO HUB.
- Join @cnnetworkofficial for updates and community.

Tips:
- Videos are protected – no forwarding!
- Daily reset at 12:00 AM IST.
- Issues? Contact @jioxt.

Enjoy! 🍿"""
    await m.reply(msg, reply_markup=MAIN_MENU if m.from_user.id != ADMIN_ID else ADMIN_MENU)

asy
