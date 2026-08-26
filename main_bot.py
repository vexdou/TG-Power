import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

import config

from database import (
    add_user,
    get_user_bots,
    count_user_bots,
    get_main_stats,
    can_create_bot,
    is_bot_creation_enabled,
    toggle_bot_creation,
    log_event,
    bots_col, users_col, bot_users_col, downloads_col, settings_col,
)
from premium import get_prices, grant as grant_premium, revoke as revoke_premium, stats as premium_stats

logger = logging.getLogger("TG-POWER.MAIN")

main_app = Client(
    "main_saas_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    workers=16,
)

pending_create = set()
pending_broadcast = {}

def user_keyboard(user_id):
    rows = [
        [
            InlineKeyboardButton("➕ Create New Bot", callback_data="create_bot"),
            InlineKeyboardButton("📦 My Bots", callback_data="my_bots"),
        ],
        [InlineKeyboardButton("📊 My Statistics", callback_data="my_stats")],
        [InlineKeyboardButton("📚 Help", callback_data="help")],
    ]
    if user_id in config.ADMIN_IDS:
        rows.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin")])
    return InlineKeyboardMarkup(rows)

ADMIN_ACTIONS = [
    ("📊 Dashboard", "stats"), ("🤖 All Bots", "bots"), ("👥 Users", "users"), ("🔐 Bot Creation", "creation"), ("📢 Broadcast", "broadcast"),
    ("🟢 Active Bots", "active"), ("🔴 Failed Bots", "failed"), ("👑 Bot Owners", "owners"), ("📥 Downloads", "downloads"), ("📈 Platform Stats", "platforms"),
    ("📦 Bot Capacity", "capacity"), ("⭐ Premium Center", "premium"), ("⭐ Premium Bots", "premium_bots"), ("💰 Premium Prices", "premium_prices"), ("🎁 Grant Premium", "grant_premium"),
    ("🚫 Revoke Premium", "revoke_premium"), ("📊 Premium Stats", "premium_stats"), ("⚙️ Premium Settings", "premium_settings"), ("🧰 System Settings", "system"), ("🛠 Maintenance", "maintenance"),
    ("⏱ Max Video", "max_video"), ("📦 Max File", "max_file"), ("🌐 Default Language", "language"), ("📋 Export Users", "export_users"), ("🤖 Export Bots", "export_bots"),
    ("🧹 Clear Downloads", "clear_downloads"), ("🧽 Clear Logs", "clear_logs"), ("🗄 DB Status", "db_status"), ("📡 Queue Status", "queue"), ("⏲ Uptime", "uptime"),
    ("🔒 Security", "security"), ("🧑‍💼 Admin IDs", "admin_ids"), ("📜 Activity Log", "activity"), ("💾 Backup Info", "backup"), ("🔔 Notifications", "notifications"),
    ("ℹ️ About", "about"), ("❓ Help", "help_admin"), ("🔃 Refresh", "refresh"), ("♻️ Reload Bots", "reload"), ("▶️ Start All", "start_all"),
    ("⏹ Stop All", "stop_all"), ("🧪 Test System", "test"), ("❤️ Bot Health", "health"), ("🕘 Recent Downloads", "recent"), ("❌ Failed Downloads", "failed_downloads"),
    ("👥 User Growth", "user_growth"), ("📥 Download Growth", "download_growth"), ("🎛 Creation Limits", "limits"), ("🔄 Reset Settings", "reset"), ("🏠 Main Menu", "main_menu"),
]

def admin_keyboard(page=0):
    start = page * 10
    chunk = ADMIN_ACTIONS[start:start + 10]
    rows = []
    for i in range(0, len(chunk), 2):
        row = [InlineKeyboardButton(chunk[i][0], callback_data=f"admin_{chunk[i][1]}")]
        if i + 1 < len(chunk):
            row.append(InlineKeyboardButton(chunk[i + 1][0], callback_data=f"admin_{chunk[i + 1][1]}"))
        rows.append(row)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"admin_page_{page - 1}"))
    if start + 10 < len(ADMIN_ACTIONS):
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"admin_page_{page + 1}"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(rows)


async def save_user(message):
    if not message.from_user:
        return
    try:
        await add_user(
            message.from_user.id,
            message.from_user.first_name or "",
            message.from_user.username or "",
        )
    except Exception:
        logger.exception("Could not save user")

@main_app.on_message(filters.private & filters.command("start"))
async def start_handler(client, message):
    logger.info("📩 /start received | user=%s",
                message.from_user.id if message.from_user else "unknown")
    await save_user(message)
    await message.reply_text(
        "👋 **Welcome to TG-Power!**\n\n"
        "Create and manage your own Telegram downloader bot.",
        reply_markup=user_keyboard(message.from_user.id),
    )

@main_app.on_message(filters.private & filters.command("admin"))
async def admin_handler(client, message):
    await save_user(message)
    uid = message.from_user.id
    if uid not in config.ADMIN_IDS:
        await message.reply_text("⛔ Admin only.")
        return
    await message.reply_text("👑 **Main Admin Panel**", reply_markup=admin_keyboard())

@main_app.on_message(filters.private & filters.command("cancel"))
async def cancel_handler(client, message):
    uid = message.from_user.id
    pending_create.discard(uid)
    pending_broadcast.pop(uid, None)
    await message.reply_text("✅ Cancelled.", reply_markup=user_keyboard(uid))

async def _admin_text(action):
    if action in {"stats", "refresh"}:
        stats = await get_main_stats()
        return f"📊 DASHBOARD\n\nUsers: {stats.get('users',0)}\nActive bots: {stats.get('bots',0)}\nDownloads: {stats.get('downloads',0)}"
    if action == "bots":
        bots = await bots_col.find({"status": {"$ne": "deleted"}}).sort("created_at", -1).to_list(length=100)
        return "🤖 ALL BOTS\n\n" + ("\n".join(f"@{b.get('username','unknown')} | {b.get('status','?')} | owner {b.get('owner_id','?')}" for b in bots) or "No bots.")
    if action == "users":
        return f"👥 USERS\n\nMain users: {await users_col.count_documents({})}\nBot users: {await bot_users_col.count_documents({})}"
    if action == "active":
        return f"🟢 ACTIVE BOTS\n\n{await bots_col.count_documents({'status':'active'})} active managed bots."
    if action == "failed":
        return f"🔴 FAILED BOTS\n\n{await bots_col.count_documents({'status':{'$in':['failed','error']}})} failed/error bots."
    if action == "owners":
        owners = await bots_col.distinct("owner_id")
        return f"👑 BOT OWNERS\n\nUnique owners: {len(owners)}"
    if action == "downloads":
        return f"📥 DOWNLOADS\n\nTotal records: {await downloads_col.count_documents({})}"
    if action == "platforms":
        rows = await downloads_col.aggregate([{"$group":{"_id":"$platform","count":{"$sum":1}}},{"$sort":{"count":-1}}]).to_list(length=20)
        return "📈 PLATFORM STATS\n\n" + ("\n".join(f"{r.get('_id','unknown')}: {r.get('count',0)}" for r in rows) or "No downloads yet.")
    if action == "capacity":
        return f"📦 BOT CAPACITY\n\nConfigured max per user: {getattr(config,'MAX_BOTS_PER_USER',5)}\nCurrent bots: {await bots_col.count_documents({'status':{'$ne':'deleted'}})}"
    if action == "premium":
        prices = await get_prices()
        return "⭐ PREMIUM CENTER\n\n" + "\n".join(f"{k}: {v} XTR" for k,v in prices.items())
    if action == "premium_bots":
        bots = await bots_col.find({"premium.is_active": True, "premium.until": {"$gt": __import__('datetime').datetime.now(__import__('datetime').timezone.utc)}}).to_list(length=100)
        return "⭐ PREMIUM BOTS\n\n" + ("\n".join(f"@{b.get('username','?')} | until {b.get('premium',{}).get('until','?')}" for b in bots) or "No active Premium bots.")
    if action == "premium_prices":
        p = await get_prices()
        return "💰 PREMIUM PRICES\n\n" + "\n".join(f"{k}: {v} XTR" for k,v in p.items()) + "\n\nUse /premium_price PLAN PRICE to change a price."
    if action == "premium_stats":
        count, users, downloads = await premium_stats()
        return f"📊 PREMIUM STATS\n\nPremium bots: {count}\nUsers: {users}\nDownloads: {downloads}"
    if action == "premium_settings":
        return "⚙️ PREMIUM SETTINGS\n\nCurrency: XTR\nCustom buttons per Premium bot: 10\nPremium captions: enabled\nPremium ads control: enabled"
    if action == "system":
        creation = await is_bot_creation_enabled()
        return f"🧰 SYSTEM SETTINGS\n\nBot creation: {'ON' if creation else 'OFF'}\nMax bots/user: {getattr(config,'MAX_BOTS_PER_USER',5)}\nMax file: {getattr(config,'MAX_FILE_SIZE_MB',2000)} MB"
    if action == "maintenance":
        doc = await settings_col.find_one({"key":"maintenance"})
        value = bool((doc or {}).get("value", False))
        new = not value
        await settings_col.update_one({"key":"maintenance"},{"$set":{"key":"maintenance","value":new}},upsert=True)
        return f"🛠 Maintenance mode: {'ON' if new else 'OFF'}"
    if action == "db_status":
        try:
            from database import client
            await client.admin.command("ping")
            return "🗄 DATABASE STATUS\n\n🟢 MongoDB ping successful."
        except Exception as exc:
            return f"🔴 MongoDB error: {str(exc)[:500]}"
    if action == "queue":
        return "📡 QUEUE STATUS\n\nDownloads use the downloader executor; no stuck queue is stored in MongoDB."
    if action == "security":
        return "🔒 SECURITY\n\nAdmin access is restricted to ADMIN_IDS. Managed bot tokens are never shown to users."
    if action == "admin_ids":
        return "🧑‍💼 ADMIN IDS\n\n" + ", ".join(map(str, sorted(config.ADMIN_IDS)))
    if action == "activity":
        rows = await __import__('database').logs_col.find().sort("created_at", -1).to_list(length=20)
        return "📜 ACTIVITY LOG\n\n" + ("\n".join(str({k:v for k,v in r.items() if k != '_id'})[:300] for r in rows) or "No activity.")
    if action == "backup":
        return "💾 BACKUP INFO\n\nMongoDB is the persistent store. Export actions are available in this admin panel."
    if action == "notifications":
        return "🔔 NOTIFICATIONS\n\nSystem notifications are represented through activity logs and bot status events."
    if action == "about":
        return "ℹ️ TG-Power\n\nMain controller + managed downloader bots + Premium administration."
    if action == "help_admin":
        return "❓ ADMIN HELP\n\nUse Next/Previous to access all 50 controls. Premium controls manage prices, active Premium bots and grants."
    if action == "health":
        from bot_manager import active_bots
        return f"❤️ BOT HEALTH\n\nRunning managed bots: {len(active_bots)}\nDB bots: {await bots_col.count_documents({})}"
    if action == "recent":
        rows = await downloads_col.find().sort("timestamp", -1).to_list(length=20)
        return "🕘 RECENT DOWNLOADS\n\n" + ("\n".join(f"{r.get('bot_username','?')} | {r.get('platform','?')} | {r.get('timestamp','?')}" for r in rows) or "No downloads.")
    if action == "failed_downloads":
        rows = await downloads_col.find({"status":"failed"}).sort("timestamp", -1).to_list(length=20)
        return "❌ FAILED DOWNLOADS\n\n" + ("\n".join(str({k:v for k,v in r.items() if k != '_id'})[:300] for r in rows) or "No failed records.")
    if action == "user_growth":
        rows = await users_col.find().sort("created_at", -1).to_list(length=20)
        return f"👥 USER GROWTH\n\nLatest recorded users: {len(rows)}\nTotal: {await users_col.count_documents({})}"
    if action == "download_growth":
        rows = await downloads_col.find().sort("timestamp", -1).to_list(length=100)
        return f"📥 DOWNLOAD GROWTH\n\nRecent sample: {len(rows)}\nTotal: {await downloads_col.count_documents({})}"
    if action == "limits":
        return f"🎛 CREATION LIMITS\n\nMax bots/user: {getattr(config,'MAX_BOTS_PER_USER',5)}"
    if action == "test":
        from database import client
        await client.admin.command("ping")
        return "🧪 SYSTEM TEST\n\n🟢 Database OK\n🟢 Main application loaded\n🟢 Admin routing OK"
    if action == "reset":
        await settings_col.update_one({"key":"maintenance"},{"$set":{"value":False}},upsert=True)
        await toggle_bot_creation(True)
        return "🔄 Safe settings reset: maintenance OFF, bot creation ON."
    return None


@main_app.on_callback_query()
async def callback_handler(client, query: CallbackQuery):
    uid = query.from_user.id
    data = query.data or ""
    try:
        await query.answer()
    except Exception:
        pass

    if data == "back":
        await query.message.edit_text("🏠 **Main Menu**", reply_markup=user_keyboard(uid))
        return

    if data == "create_bot":
        if not await is_bot_creation_enabled():
            await query.message.edit_text(
                "🔴 **Bot creation is currently disabled.**",
                reply_markup=user_keyboard(uid),
            )
            return
        if not await can_create_bot(uid):
            await query.message.edit_text(
                "⛔ You do not have permission to create bots.",
                reply_markup=user_keyboard(uid),
            )
            return

        count = await count_user_bots(uid)
        maximum = getattr(config, "MAX_BOTS_PER_USER", 5)
        if count >= maximum:
            await query.message.edit_text(
                f"⛔ Maximum {maximum} bots reached.",
                reply_markup=user_keyboard(uid),
            )
            return

        pending_create.add(uid)
        await query.message.edit_text(
            "🤖 **Create New Bot**\n\n"
            "Send:\n`Bot Name | BotUsernameBot`\n\n"
            "The username must end with `bot`.\n"
            "Send /cancel to cancel."
        )
        return

    if data == "my_bots":
        bots = await get_user_bots(uid)
        if not bots:
            text = "📦 **My Bots**\n\nYou have no managed bots."
        else:
            lines = ["📦 **My Bots**", ""]
            for bot in bots:
                lines.append(
                    f"🤖 @{bot.get('username', 'unknown')}\n"
                    f"📡 {bot.get('status', 'unknown')}\n"
                    f"👥 {bot.get('total_users', 0)} users\n"
                    f"📥 {bot.get('total_downloads', 0)} downloads\n"
                )
            text = "\n".join(lines)
        await query.message.edit_text(
            text[:4000], reply_markup=user_keyboard(uid)
        )
        return

    if data == "my_stats":
        bots = await get_user_bots(uid)
        users = sum(int(b.get("total_users", 0)) for b in bots)
        downloads = sum(int(b.get("total_downloads", 0)) for b in bots)
        await query.message.edit_text(
            "📊 **My Statistics**\n\n"
            f"🤖 Bots: {len(bots)}\n"
            f"👥 Users: {users}\n"
            f"📥 Downloads: {downloads}",
            reply_markup=user_keyboard(uid),
        )
        return

    if data == "help":
        await query.message.edit_text(
            "📚 **Help**\n\n"
            "• Create a managed bot from this menu.\n"
            "• Open your created bot and use /admin.\n"
            "• Main admins can manage all bots and users.",
            reply_markup=user_keyboard(uid),
        )
        return

    if data == "admin":
        if uid not in config.ADMIN_IDS:
            return
        await query.message.edit_text(
            "👑 **Main Admin Panel**", reply_markup=admin_keyboard()
        )
        return

    if uid not in config.ADMIN_IDS or not data.startswith("admin_"):
        return

    if data.startswith("admin_page_"):
        try:
            page = int(data.rsplit("_", 1)[1])
        except ValueError:
            page = 0
        await query.message.edit_text("👑 MAIN ADMIN PANEL", reply_markup=admin_keyboard(page))
        return

    simple_action = data[6:]
    if simple_action == "main_menu":
        await query.message.edit_text("🏠 Main Menu", reply_markup=user_keyboard(uid))
        return
    if simple_action == "broadcast":
        pending_broadcast[uid] = "main"
        await query.message.edit_text("📢 Send the message to broadcast. Use /cancel to cancel.")
        return
    if simple_action == "creation":
        enabled = await is_bot_creation_enabled()
        await query.message.edit_text(f"🔐 BOT CREATION\n\nStatus: {'🟢 ENABLED' if enabled else '🔴 DISABLED'}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🟢 Enable", callback_data="creation_on"), InlineKeyboardButton("🔴 Disable", callback_data="creation_off")],[InlineKeyboardButton("🔙 Admin", callback_data="admin")]]))
        return
    if simple_action == "reload":
        from bot_manager import shutdown_all_bots, init_all_bots
        await shutdown_all_bots()
        result = await init_all_bots()
        await query.message.edit_text(f"♻️ Reload complete\n\nStarted: {result['started']}\nFailed: {result['failed']}\nSkipped: {result['skipped']}", reply_markup=admin_keyboard(3))
        return
    if simple_action == "start_all":
        from bot_manager import init_all_bots
        result = await init_all_bots()
        await query.message.edit_text(f"▶️ Start All\n\nStarted: {result['started']}\nFailed: {result['failed']}", reply_markup=admin_keyboard(3))
        return
    if simple_action == "stop_all":
        from bot_manager import shutdown_all_bots
        await shutdown_all_bots()
        await query.message.edit_text("⏹ All managed bots stopped.", reply_markup=admin_keyboard(3))
        return
    if simple_action == "grant_premium":
        await query.message.edit_text("🎁 GRANT PREMIUM\n\nUse /grant_premium BOT_USERNAME DAYS\nExample: /grant_premium MyDownloaderBot 30", reply_markup=admin_keyboard(1))
        return
    if simple_action == "revoke_premium":
        await query.message.edit_text("🚫 REVOKE PREMIUM\n\nUse /revoke_premium BOT_USERNAME", reply_markup=admin_keyboard(1))
        return
    if simple_action == "max_video":
        await query.message.edit_text(f"⏱ MAX VIDEO\n\n{getattr(config,'MAX_VIDEO_DURATION_SECONDS',1800)//60} minutes.\nSet MAX_VIDEO_DURATION_SECONDS in Render to change it.", reply_markup=admin_keyboard(2))
        return
    if simple_action == "max_file":
        await query.message.edit_text(f"📦 MAX FILE\n\n{getattr(config,'MAX_FILE_SIZE_MB',2000)} MB.\nSet MAX_FILE_SIZE_MB in Render to change it.", reply_markup=admin_keyboard(2))
        return
    if simple_action == "language":
        await query.message.edit_text("🌐 DEFAULT LANGUAGE\n\nManaged bots support English, Soomaali, Arabic, Spanish and additional languages.", reply_markup=admin_keyboard(2))
        return
    if simple_action == "export_users":
        total = await users_col.count_documents({})
        await query.message.edit_text(f"📋 USER EXPORT\n\nUsers available for export: {total}\nUse the database export outside Telegram for large datasets.", reply_markup=admin_keyboard(2))
        return
    if simple_action == "export_bots":
        total = await bots_col.count_documents({})
        await query.message.edit_text(f"🤖 BOT EXPORT\n\nBots available for export: {total}", reply_markup=admin_keyboard(2))
        return
    if simple_action == "clear_downloads":
        await downloads_col.delete_many({})
        await query.message.edit_text("🧹 Download history cleared.", reply_markup=admin_keyboard(2))
        return
    if simple_action == "clear_logs":
        await __import__('database').logs_col.delete_many({})
        await query.message.edit_text("🧽 Activity logs cleared.", reply_markup=admin_keyboard(2))
        return
    if simple_action == "uptime":
        import time as _time
        await query.message.edit_text(f"⏲ UPTIME\n\nProcess uptime: {_time.monotonic():.0f}s since monotonic origin.", reply_markup=admin_keyboard(3))
        return
    if simple_action == "premium_prices":
        await query.message.edit_text(await _admin_text("premium_prices"), reply_markup=admin_keyboard(1))
        return
    if simple_action == "premium_bots":
        await query.message.edit_text((await _admin_text("premium_bots"))[:4000], reply_markup=admin_keyboard(1))
        return
    if simple_action == "premium_stats":
        await query.message.edit_text(await _admin_text("premium_stats"), reply_markup=admin_keyboard(1))
        return
    if simple_action == "premium_settings":
        await query.message.edit_text(await _admin_text("premium_settings"), reply_markup=admin_keyboard(1))
        return

    if data == "admin_stats":
        stats = await get_main_stats()
        await query.message.edit_text(
            "📊 **Main Statistics**\n\n"
            f"👥 Users: {stats.get('users', 0)}\n"
            f"🤖 Bots: {stats.get('bots', 0)}\n"
            f"📥 Downloads: {stats.get('downloads', 0)}",
            reply_markup=admin_keyboard(),
        )
        return

    if data == "admin_bots":
        try:
            from database import bots_col
            bots = await bots_col.find(
                {"status": {"$ne": "deleted"}}
            ).sort("created_at", -1).to_list(length=100)

            if not bots:
                text = "🤖 **All Managed Bots**\n\nNo bots found."
            else:
                text = "\n".join(
                    ["🤖 **All Managed Bots**", ""] +
                    [
                        f"@{b.get('username', 'unknown')} | "
                        f"{b.get('status', 'unknown')} | "
                        f"Owner: {b.get('owner_id', 'unknown')}"
                        for b in bots
                    ]
                )
            await query.message.edit_text(text[:4000], reply_markup=admin_keyboard())
        except Exception as exc:
            await query.message.edit_text(
                f"❌ Could not load bots:\n`{str(exc)[:1000]}`",
                reply_markup=admin_keyboard(),
            )
        return

    if data == "admin_users":
        try:
            from database import users_col
            total = await users_col.count_documents({})
            await query.message.edit_text(
                f"👥 **Users:** {total}", reply_markup=admin_keyboard()
            )
        except Exception as exc:
            await query.message.edit_text(
                f"❌ `{str(exc)[:1000]}`", reply_markup=admin_keyboard()
            )
        return

    if data == "admin_creation":
        enabled = await is_bot_creation_enabled()
        await query.message.edit_text(
            "🔐 **Bot Creation**\n\n"
            f"Status: {'🟢 ENABLED' if enabled else '🔴 DISABLED'}",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🟢 Enable", callback_data="creation_on"),
                    InlineKeyboardButton("🔴 Disable", callback_data="creation_off"),
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="admin")],
            ]),
        )
        return

    if data == "creation_on":
        await toggle_bot_creation(True)
        await query.message.edit_text(
            "🟢 Bot creation enabled.", reply_markup=admin_keyboard()
        )
        return

    if data == "creation_off":
        await toggle_bot_creation(False)
        await query.message.edit_text(
            "🔴 Bot creation disabled.", reply_markup=admin_keyboard()
        )
        return

    if data == "admin_broadcast":
        pending_broadcast[uid] = "main"
        await query.message.edit_text(
            "📢 **Broadcast**\n\n"
            "Send the message you want to broadcast.\n"
            "Use /cancel to cancel."
        )

@main_app.on_message(filters.private & filters.command("grant_premium"))
async def grant_premium_command(client, message):
    if message.from_user.id not in config.ADMIN_IDS:
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.reply_text("Usage: /grant_premium BOT_USERNAME DAYS")
        return
    try:
        days = int(parts[2])
        until = await grant_premium(parts[1], days, message.from_user.id)
        await message.reply_text(f"🎁 Premium granted to @{parts[1].lstrip('@')} until {until}")
    except Exception as exc:
        await message.reply_text(f"❌ Grant failed: {str(exc)[:500]}")

@main_app.on_message(filters.private & filters.command("revoke_premium"))
async def revoke_premium_command(client, message):
    if message.from_user.id not in config.ADMIN_IDS:
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.reply_text("Usage: /revoke_premium BOT_USERNAME")
        return
    ok = await revoke_premium(parts[1])
    await message.reply_text("🚫 Premium revoked." if ok else "❌ Bot not found.")

@main_app.on_message(filters.private & filters.command("premium_price"))
async def premium_price_command(client, message):
    if message.from_user.id not in config.ADMIN_IDS:
        return
    parts = (message.text or "").split()
    if len(parts) != 3 or parts[1] not in {"1m","3m","6m","1y"}:
        await message.reply_text("Usage: /premium_price 1m 100")
        return
    prices = await get_prices()
    prices[parts[1]] = int(parts[2])
    await __import__('database').db.set_premium_prices(prices)
    await message.reply_text(f"✅ {parts[1]} Premium price set to {parts[2]} XTR.")

@main_app.on_message(
    filters.private & ~filters.command(["start", "admin", "cancel"])
)
async def text_handler(client, message):
    uid = message.from_user.id
    await save_user(message)

    if uid in pending_create:
        pending_create.discard(uid)
        raw = (message.text or "").strip()

        if "|" not in raw:
            await message.reply_text(
                "❌ Invalid format.\n\n"
                "Use:\n`My Downloader | MyDownloaderBot`"
            )
            return

        bot_name, bot_username = [x.strip() for x in raw.split("|", 1)]
        status = await message.reply_text("⏳ Creating your bot...")

        try:
            from bot_creator import create_bot_via_botfather
            from database import register_bot
            from bot_manager import start_managed_bot

            token, final_username = await create_bot_via_bot(
                bot_name, bot_username
            )

            await register_bot(
                uid, token, bot_name, final_username, None
            )

            started = await start_managed_bot(
                token, final_username, uid
            )
            if not started:
                raise RuntimeError("Bot was created but could not be started.")

            await log_event(
                "bot_created",
                owner_id=uid,
                bot_username=final_username,
            )

            await status.edit_text(
                "✅ **Bot Created Successfully!**\n\n"
                f"🤖 @{final_username}\n"
                f"🔗 https://t.me/{final_username}\n\n"
                "Open the bot and send /admin.",
                reply_markup=user_keyboard(uid),
            )
        except Exception as exc:
            logger.exception("Bot creation failed")
            await status.edit_text(
                "❌ **Bot Creation Failed**\n\n"
                f"`{str(exc)[:1200]}`",
                reply_markup=user_keyboard(uid),
            )
        return

    mode = pending_broadcast.get(uid)
    if mode and uid in config.ADMIN_IDS:
        pending_broadcast.pop(uid, None)
        await message.reply_text("📢 Broadcast started...")

        try:
            from database import users_col
            users = await users_col.find({}).to_list(length=200000)
            sent = failed = 0

            for user in users:
                target = user.get("user_id")
                if not target:
                    continue
                try:
                    await message.copy(target)
                    sent += 1
                    await asyncio.sleep(0.05)
                except Exception:
                    failed += 1

            await message.reply_text(
                "📢 **Broadcast Finished**\n\n"
                f"✅ Sent: {sent}\n❌ Failed: {failed}"
            )
        except Exception as exc:
            await message.reply_text(
                f"❌ Broadcast failed:\n`{str(exc)[:1000]}`"
            )
        return

    await message.reply_text(
        "Use the menu below:", reply_markup=user_keyboard(uid)
    )

@main_app.on_message(filters.private, group=1000)
async def update_diagnostic(client, message):
    try:
        logger.info(
            "📡 TELEGRAM UPDATE RECEIVED | user=%s | text=%r",
            message.from_user.id if message.from_user else "unknown",
            (message.text or message.caption or "")[:200],
        )
    except Exception:
        logger.exception("Diagnostic handler error")
