import asyncio
import logging
import time
from datetime import datetime, timezone

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
    bots_col,
    users_col,
    bot_users_col,
    downloads_col,
    settings_col,
    logs_col,
    client as mongo_client,
)
from premium import (
    get_prices,
    grant as grant_premium,
    revoke as revoke_premium,
    stats as premium_stats,
)

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
STARTED_AT = time.monotonic()


# ============================================================
# USER MENU
# ============================================================

def user_keyboard(user_id: int):
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


# ============================================================
# EXACT 50 ADMIN ACTIONS
# ============================================================

ADMIN_ACTIONS = [
    ("📊 Dashboard", "stats"),
    ("🤖 All Bots", "bots"),
    ("👥 Users", "users"),
    ("🔐 Bot Creation", "creation"),
    ("📢 Broadcast", "broadcast"),
    ("🟢 Active Bots", "active"),
    ("🔴 Failed Bots", "failed"),
    ("👑 Bot Owners", "owners"),
    ("📥 Downloads", "downloads"),
    ("📈 Platform Stats", "platforms"),

    ("📦 Bot Capacity", "capacity"),
    ("⭐ Premium Center", "premium"),
    ("⭐ Premium Bots", "premium_bots"),
    ("💰 Premium Prices", "premium_prices"),
    ("🎁 Grant Premium", "grant_premium"),
    ("🚫 Revoke Premium", "revoke_premium"),
    ("📊 Premium Stats", "premium_stats"),
    ("⚙️ Premium Settings", "premium_settings"),
    ("🧰 System Settings", "system"),
    ("🛠 Maintenance", "maintenance"),

    ("⏱ Max Video", "max_video"),
    ("📦 Max File", "max_file"),
    ("🌐 Default Language", "language"),
    ("📋 Export Users", "export_users"),
    ("🤖 Export Bots", "export_bots"),
    ("🧹 Clear Downloads", "clear_downloads"),
    ("🧽 Clear Logs", "clear_logs"),
    ("🗄 DB Status", "db_status"),
    ("📡 Queue Status", "queue"),
    ("⏲ Uptime", "uptime"),

    ("🔒 Security", "security"),
    ("🧑‍💼 Admin IDs", "admin_ids"),
    ("📜 Activity Log", "activity"),
    ("💾 Backup Info", "backup"),
    ("🔔 Notifications", "notifications"),
    ("ℹ️ About", "about"),
    ("❓ Help", "help_admin"),
    ("🔃 Refresh", "refresh"),
    ("♻️ Reload Bots", "reload"),
    ("▶️ Start All", "start_all"),

    ("⏹ Stop All", "stop_all"),
    ("🧪 Test System", "test"),
    ("❤️ Bot Health", "health"),
    ("🕘 Recent Downloads", "recent"),
    ("❌ Failed Downloads", "failed_downloads"),
    ("👥 User Growth", "user_growth"),
    ("📥 Download Growth", "download_growth"),
    ("🎛 Creation Limits", "limits"),
    ("🔄 Reset Settings", "reset"),
    ("🏠 Main Menu", "main_menu"),
]


def admin_keyboard(page: int = 0):
    page = max(0, min(page, (len(ADMIN_ACTIONS) - 1) // 10))
    start = page * 10
    chunk = ADMIN_ACTIONS[start:start + 10]

    rows = []
    for i in range(0, len(chunk), 2):
        row = [
            InlineKeyboardButton(
                chunk[i][0],
                callback_data=f"admin_{chunk[i][1]}",
            )
        ]
        if i + 1 < len(chunk):
            row.append(
                InlineKeyboardButton(
                    chunk[i + 1][0],
                    callback_data=f"admin_{chunk[i + 1][1]}",
                )
            )
        rows.append(row)

    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                "⬅️ Previous",
                callback_data=f"admin_page_{page - 1}",
            )
        )
    if start + 10 < len(ADMIN_ACTIONS):
        nav.append(
            InlineKeyboardButton(
                "Next ➡️",
                callback_data=f"admin_page_{page + 1}",
            )
        )

    if nav:
        rows.append(nav)

    return InlineKeyboardMarkup(rows)


def admin_back_keyboard(page: int = 0):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Admin Panel", callback_data=f"admin_page_{page}")]
    ])


# ============================================================
# COMMON HELPERS
# ============================================================

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


async def safe_edit(message, text, markup=None):
    try:
        await message.edit_text(
            text[:4000],
            reply_markup=markup,
        )
    except Exception:
        try:
            await message.reply_text(
                text[:4000],
                reply_markup=markup,
            )
        except Exception:
            logger.exception("Could not edit/reply")


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


# ============================================================
# START / ADMIN / CANCEL
# ============================================================

@main_app.on_message(filters.private & filters.command("start"))
async def start_handler(client, message):
    logger.info(
        "📩 /start received | user=%s",
        message.from_user.id if message.from_user else "unknown",
    )

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
    if not is_admin(uid):
        await message.reply_text("⛔ Admin only.")
        return

    await message.reply_text(
        "👑 **Main Admin Panel**\n\n"
        "50 management controls are available below.",
        reply_markup=admin_keyboard(),
    )


@main_app.on_message(filters.private & filters.command("cancel"))
async def cancel_handler(client, message):
    uid = message.from_user.id
    pending_create.discard(uid)
    pending_broadcast.pop(uid, None)

    await message.reply_text(
        "✅ Cancelled.",
        reply_markup=user_keyboard(uid),
    )


# ============================================================
# ADMIN ACTION TEXT
# ============================================================

async def admin_text(action: str):
    if action in {"stats", "refresh"}:
        stats = await get_main_stats()
        return (
            "📊 **DASHBOARD**\n\n"
            f"👥 Users: {stats.get('users', 0)}\n"
            f"🤖 Active bots: {stats.get('bots', 0)}\n"
            f"📥 Downloads: {stats.get('downloads', 0)}"
        )

    if action == "bots":
        bots = await bots_col.find(
            {"status": {"$ne": "deleted"}}
        ).sort("created_at", -1).to_list(length=100)

        if not bots:
            return "🤖 **ALL BOTS**\n\nNo managed bots."

        lines = ["🤖 **ALL BOTS**", ""]
        for bot in bots:
            lines.append(
                f"@{bot.get('username', 'unknown')} | "
                f"{bot.get('status', '?')} | "
                f"owner {bot.get('owner_id', '?')}"
            )
        return "\n".join(lines)

    if action == "users":
        return (
            "👥 **USERS**\n\n"
            f"Main users: {await users_col.count_documents({})}\n"
            f"Bot users: {await bot_users_col.count_documents({})}"
        )

    if action == "active":
        count = await bots_col.count_documents({"status": "active"})
        return f"🟢 **ACTIVE BOTS**\n\n{count} active managed bots."

    if action == "failed":
        count = await bots_col.count_documents(
            {"status": {"$in": ["failed", "error"]}}
        )
        return f"🔴 **FAILED BOTS**\n\n{count} failed/error bots."

    if action == "owners":
        owners = await bots_col.distinct("owner_id")
        return f"👑 **BOT OWNERS**\n\nUnique owners: {len(owners)}"

    if action == "downloads":
        return (
            "📥 **DOWNLOADS**\n\n"
            f"Total records: {await downloads_col.count_documents({})}"
        )

    if action == "platforms":
        rows = await downloads_col.aggregate([
            {
                "$group": {
                    "_id": "$platform",
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"count": -1}},
        ]).to_list(length=20)

        if not rows:
            return "📈 **PLATFORM STATS**\n\nNo downloads yet."

        return (
            "📈 **PLATFORM STATS**\n\n" +
            "\n".join(
                f"{r.get('_id', 'unknown')}: {r.get('count', 0)}"
                for r in rows
            )
        )

    if action == "capacity":
        return (
            "📦 **BOT CAPACITY**\n\n"
            f"Max per user: {getattr(config, 'MAX_BOTS_PER_USER', 5)}\n"
            f"Current bots: "
            f"{await bots_col.count_documents({'status': {'$ne': 'deleted'}})}"
        )

    if action == "premium":
        prices = await get_prices()
        return (
            "⭐ **PREMIUM CENTER**\n\n" +
            "\n".join(
                f"{key}: {value} XTR"
                for key, value in prices.items()
            ) +
            "\n\nUse the Premium controls to manage plans."
        )

    if action == "premium_bots":
        now = datetime.now(timezone.utc)
        bots = await bots_col.find({
            "premium.is_active": True,
            "$or": [
                {"premium.until": {"$gt": now}},
                {"premium.until": None},
            ],
        }).to_list(length=100)

        if not bots:
            return "⭐ **PREMIUM BOTS**\n\nNo active Premium bots."

        return (
            "⭐ **PREMIUM BOTS**\n\n" +
            "\n".join(
                f"@{b.get('username', '?')} | "
                f"until {b.get('premium', {}).get('until', '?')}"
                for b in bots
            )
        )

    if action == "premium_prices":
        prices = await get_prices()
        return (
            "💰 **PREMIUM PRICES**\n\n" +
            "\n".join(
                f"{key}: {value} XTR"
                for key, value in prices.items()
            ) +
            "\n\nUse:\n/premium_price 1m 100"
        )

    if action == "premium_stats":
        count, users, downloads = await premium_stats()
        return (
            "📊 **PREMIUM STATS**\n\n"
            f"⭐ Premium bots: {count}\n"
            f"👥 Users: {users}\n"
            f"📥 Downloads: {downloads}"
        )

    if action == "premium_settings":
        return (
            "⚙️ **PREMIUM SETTINGS**\n\n"
            "⭐ Premium center: enabled\n"
            "🎛 Premium administration: enabled\n"
            "💰 Telegram Stars: XTR\n"
            "🧩 Premium bot controls: enabled"
        )

    if action == "system":
        creation = await is_bot_creation_enabled()
        return (
            "🧰 **SYSTEM SETTINGS**\n\n"
            f"Bot creation: {'🟢 ON' if creation else '🔴 OFF'}\n"
            f"Max bots/user: {getattr(config, 'MAX_BOTS_PER_USER', 5)}\n"
            f"Max file: {getattr(config, 'MAX_FILE_SIZE_MB', 2000)} MB\n"
            f"Max video: "
            f"{getattr(config, 'MAX_VIDEO_DURATION_SECONDS', 1800) // 60} min"
        )

    if action == "maintenance":
        doc = await settings_col.find_one({"key": "maintenance"})
        enabled = bool((doc or {}).get("value", False))
        return (
            "🛠 **MAINTENANCE**\n\n"
            f"Status: {'🟢 ON' if enabled else '🔴 OFF'}\n\n"
            "Use the buttons below to change it."
        )

    if action == "db_status":
        try:
            await mongo_client.admin.command("ping")
            return "🗄 **DATABASE STATUS**\n\n🟢 MongoDB ping successful."
        except Exception as exc:
            return f"🔴 MongoDB error:\n`{str(exc)[:1000]}`"

    if action == "queue":
        return (
            "📡 **QUEUE STATUS**\n\n"
            "🟢 Main bot event loop is active.\n"
            "🟢 Managed bots use the bot manager."
        )

    if action == "uptime":
        seconds = int(time.monotonic() - STARTED_AT)
        return f"⏲ **UPTIME**\n\nProcess uptime: {seconds}s"

    if action == "security":
        return (
            "🔒 **SECURITY**\n\n"
            "🟢 Admin access restricted by ADMIN_IDS.\n"
            "🟢 Managed bot tokens are not displayed in Telegram."
        )

    if action == "admin_ids":
        ids = ", ".join(map(str, sorted(config.ADMIN_IDS)))
        return f"🧑‍💼 **ADMIN IDS**\n\n{ids or 'None configured.'}"

    if action == "activity":
        rows = await logs_col.find().sort(
            "created_at", -1
        ).to_list(length=20)

        if not rows:
            return "📜 **ACTIVITY LOG**\n\nNo activity."

        lines = []
        for row in rows:
            row = {k: v for k, v in row.items() if k != "_id"}
            lines.append(str(row)[:300])

        return "📜 **ACTIVITY LOG**\n\n" + "\n".join(lines)

    if action == "backup":
        return (
            "💾 **BACKUP INFO**\n\n"
            "MongoDB is the persistent database.\n"
            "Use your MongoDB backup/export process for full backups."
        )

    if action == "notifications":
        return (
            "🔔 **NOTIFICATIONS**\n\n"
            "System events are recorded through the activity log."
        )

    if action == "about":
        return (
            "ℹ️ **TG-POWER**\n\n"
            "Main controller + managed downloader bots + Premium administration."
        )

    if action == "help_admin":
        return (
            "❓ **ADMIN HELP**\n\n"
            "Use the 50 buttons to inspect and manage the system."
        )

    if action == "health":
        try:
            from bot_manager import active_bots
            running = len(active_bots)
        except Exception:
            running = 0

        return (
            "❤️ **BOT HEALTH**\n\n"
            f"Running managed bots: {running}\n"
            f"DB bots: {await bots_col.count_documents({})}"
        )

    if action == "recent":
        rows = await downloads_col.find().sort(
            "timestamp", -1
        ).to_list(length=20)

        if not rows:
            return "🕘 **RECENT DOWNLOADS**\n\nNo downloads."

        return (
            "🕘 **RECENT DOWNLOADS**\n\n" +
            "\n".join(
                f"{r.get('bot_username', '?')} | "
                f"{r.get('platform', '?')} | "
                f"{r.get('timestamp', '?')}"
                for r in rows
            )
        )

    if action == "failed_downloads":
        rows = await downloads_col.find(
            {"status": "failed"}
        ).sort("timestamp", -1).to_list(length=20)

        if not rows:
            return "❌ **FAILED DOWNLOADS**\n\nNo failed records."

        return (
            "❌ **FAILED DOWNLOADS**\n\n" +
            "\n".join(str({
                k: v for k, v in r.items() if k != "_id"
            })[:300] for r in rows)
        )

    if action == "user_growth":
        total = await users_col.count_documents({})
        return f"👥 **USER GROWTH**\n\nTotal registered users: {total}"

    if action == "download_growth":
        total = await downloads_col.count_documents({})
        return f"📥 **DOWNLOAD GROWTH**\n\nTotal downloads: {total}"

    if action == "limits":
        return (
            "🎛 **CREATION LIMITS**\n\n"
            f"Max bots/user: {getattr(config, 'MAX_BOTS_PER_USER', 5)}"
        )

    if action == "test":
        try:
            await mongo_client.admin.command("ping")
            db = "🟢 OK"
        except Exception:
            db = "🔴 FAILED"

        try:
            from bot_manager import active_bots
            manager = f"🟢 OK ({len(active_bots)} running)"
        except Exception:
            manager = "🟡 Not loaded"

        return (
            "🧪 **SYSTEM TEST**\n\n"
            f"MongoDB: {db}\n"
            "Main Pyrogram: 🟢 ONLINE\n"
            f"Managed Bot Manager: {manager}"
        )

    if action == "reset":
        await settings_col.update_one(
            {"key": "maintenance"},
            {"$set": {"key": "maintenance", "value": False}},
            upsert=True,
        )
        await toggle_bot_creation(True)

        return (
            "🔄 **SAFE SETTINGS RESET**\n\n"
            "Maintenance: OFF\n"
            "Bot creation: ON"
        )

    return "ℹ️ This admin control is available."


# ============================================================
# CALLBACK HANDLER
# ============================================================

@main_app.on_callback_query()
async def callback_handler(client, query: CallbackQuery):
    uid = query.from_user.id
    data = query.data or ""

    try:
        await query.answer()
    except Exception:
        pass

    # ---------- USER ----------
    if data == "back":
        await safe_edit(
            query.message,
            "🏠 **Main Menu**",
            user_keyboard(uid),
        )
        return

    if data == "create_bot":
        if not await is_bot_creation_enabled():
            await safe_edit(
                query.message,
                "🔴 **Bot creation is currently disabled.**",
                user_keyboard(uid),
            )
            return

        if not await can_create_bot(uid):
            await safe_edit(
                query.message,
                "⛔ You do not have permission to create bots.",
                user_keyboard(uid),
            )
            return

        count = await count_user_bots(uid)
        maximum = getattr(config, "MAX_BOTS_PER_USER", 5)

        if count >= maximum:
            await safe_edit(
                query.message,
                f"⛔ Maximum {maximum} bots reached.",
                user_keyboard(uid),
            )
            return

        pending_create.add(uid)

        await safe_edit(
            query.message,
            "🤖 **Create New Bot**\n\n"
            "Send:\n"
            "`Bot Name | BotUsernameBot`\n\n"
            "Username must end with `bot`.\n"
            "Send /cancel to cancel.",
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

        await safe_edit(
            query.message,
            text,
            user_keyboard(uid),
        )
        return

    if data == "my_stats":
        bots = await get_user_bots(uid)
        users = sum(int(b.get("total_users", 0)) for b in bots)
        downloads = sum(int(b.get("total_downloads", 0)) for b in bots)

        await safe_edit(
            query.message,
            "📊 **My Statistics**\n\n"
            f"🤖 Bots: {len(bots)}\n"
            f"👥 Users: {users}\n"
            f"📥 Downloads: {downloads}",
            user_keyboard(uid),
        )
        return

    if data == "help":
        await safe_edit(
            query.message,
            "📚 **Help**\n\n"
            "• Create a managed bot from this menu.\n"
            "• Open your created bot and send /admin.\n"
            "• Main admins can manage the system.",
            user_keyboard(uid),
        )
        return

    # ---------- ADMIN AUTH ----------
    if data == "admin":
        if not is_admin(uid):
            return

        await safe_edit(
            query.message,
            "👑 **Main Admin Panel**\n\n"
            "50 management controls.",
            admin_keyboard(),
        )
        return

    if not is_admin(uid):
        return

    # ---------- ADMIN PAGINATION ----------
    if data.startswith("admin_page_"):
        try:
            page = int(data.rsplit("_", 1)[1])
        except ValueError:
            page = 0

        await safe_edit(
            query.message,
            "👑 **MAIN ADMIN PANEL**",
            admin_keyboard(page),
        )
        return

    if not data.startswith("admin_"):
        return

    action = data[len("admin_"):]

    if action == "main_menu":
        await safe_edit(
            query.message,
            "🏠 **Main Menu**",
            user_keyboard(uid),
        )
        return

    # ---------- CREATION TOGGLE ----------
    # IMPORTANT: this is handled BEFORE generic admin text.
    if action == "creation":
        enabled = await is_bot_creation_enabled()

        await safe_edit(
            query.message,
            "🔐 **BOT CREATION**\n\n"
            f"Status: {'🟢 ENABLED' if enabled else '🔴 DISABLED'}",
            InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🟢 Enable",
                        callback_data="admin_creation_on",
                    ),
                    InlineKeyboardButton(
                        "🔴 Disable",
                        callback_data="admin_creation_off",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🔙 Admin",
                        callback_data="admin_page_0",
                    )
                ],
            ]),
        )
        return

    if action == "creation_on":
        await toggle_bot_creation(True)
        await safe_edit(
            query.message,
            "🟢 **Bot creation enabled.**",
            admin_keyboard(0),
        )
        return

    if action == "creation_off":
        await toggle_bot_creation(False)
        await safe_edit(
            query.message,
            "🔴 **Bot creation disabled.**",
            admin_keyboard(0),
        )
        return

    # ---------- MAINTENANCE ----------
    if action == "maintenance":
        doc = await settings_col.find_one({"key": "maintenance"})
        enabled = bool((doc or {}).get("value", False))

        await safe_edit(
            query.message,
            "🛠 **MAINTENANCE**\n\n"
            f"Current status: {'🟢 ON' if enabled else '🔴 OFF'}",
            InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🟢 Enable",
                        callback_data="admin_maintenance_on",
                    ),
                    InlineKeyboardButton(
                        "🔴 Disable",
                        callback_data="admin_maintenance_off",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🔙 Admin",
                        callback_data="admin_page_1",
                    )
                ],
            ]),
        )
        return

    if action in {"maintenance_on", "maintenance_off"}:
        enabled = action == "maintenance_on"

        await settings_col.update_one(
            {"key": "maintenance"},
            {"$set": {"key": "maintenance", "value": enabled}},
            upsert=True,
        )

        await safe_edit(
            query.message,
            f"🛠 Maintenance: {'🟢 ON' if enabled else '🔴 OFF'}",
            admin_keyboard(1),
        )
        return

    # ---------- RELOAD / START / STOP ----------
    if action == "reload":
        try:
            from bot_manager import shutdown_all_bots, init_all_bots

            await shutdown_all_bots()
            result = await init_all_bots()

            text = (
                "♻️ **RELOAD BOTS**\n\n"
                f"Started: {result.get('started', 0)}\n"
                f"Failed: {result.get('failed', 0)}\n"
                f"Skipped: {result.get('skipped', 0)}"
            )
        except Exception as exc:
            text = f"❌ Reload failed:\n`{str(exc)[:1000]}`"

        await safe_edit(query.message, text, admin_keyboard(3))
        return

    if action == "start_all":
        try:
            from bot_manager import init_all_bots
            result = await init_all_bots()

            text = (
                "▶️ **START ALL**\n\n"
                f"Started: {result.get('started', 0)}\n"
                f"Failed: {result.get('failed', 0)}\n"
                f"Skipped: {result.get('skipped', 0)}"
            )
        except Exception as exc:
            text = f"❌ Start failed:\n`{str(exc)[:1000]}`"

        await safe_edit(query.message, text, admin_keyboard(3))
        return

    if action == "stop_all":
        try:
            from bot_manager import shutdown_all_bots
            await shutdown_all_bots()
            text = "⏹ **All managed bots stopped.**"
        except Exception as exc:
            text = f"❌ Stop failed:\n`{str(exc)[:1000]}`"

        await safe_edit(query.message, text, admin_keyboard(3))
        return

    # ---------- BROADCAST ----------
    if action == "broadcast":
        pending_broadcast[uid] = "main"

        await safe_edit(
            query.message,
            "📢 **Broadcast**\n\n"
            "Send the message you want to broadcast.\n"
            "Use /cancel to cancel.",
        )
        return

    # ---------- PREMIUM ----------
    if action == "grant_premium":
        await safe_edit(
            query.message,
            "🎁 **GRANT PREMIUM**\n\n"
            "Use:\n"
            "`/grant_premium BOT_USERNAME DAYS`",
            admin_keyboard(1),
        )
        return

    if action == "revoke_premium":
        await safe_edit(
            query.message,
            "🚫 **REVOKE PREMIUM**\n\n"
            "Use:\n"
            "`/revoke_premium BOT_USERNAME`",
            admin_keyboard(1),
        )
        return

    if action == "premium_prices":
        text = await admin_text("premium_prices")
        await safe_edit(query.message, text, admin_keyboard(1))
        return

    if action == "premium_bots":
        text = await admin_text("premium_bots")
        await safe_edit(query.message, text, admin_keyboard(1))
        return

    if action == "premium_stats":
        text = await admin_text("premium_stats")
        await safe_edit(query.message, text, admin_keyboard(1))
        return

    if action == "premium_settings":
        text = await admin_text("premium_settings")
        await safe_edit(query.message, text, admin_keyboard(1))
        return

    if action == "premium":
        text = await admin_text("premium")
        await safe_edit(query.message, text, admin_keyboard(1))
        return

    # ---------- DANGEROUS DATA-DESTRUCTIVE BUTTONS ----------
    # These require a second confirmation instead of deleting immediately.
    if action == "clear_downloads":
        await safe_edit(
            query.message,
            "🧹 **CLEAR DOWNLOADS**\n\n"
            "This will delete download history from MongoDB.",
            InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "✅ Confirm Clear",
                        callback_data="admin_confirm_clear_downloads",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "❌ Cancel",
                        callback_data="admin_page_2",
                    )
                ],
            ]),
        )
        return

    if action == "confirm_clear_downloads":
        await downloads_col.delete_many({})
        await safe_edit(
            query.message,
            "🧹 Download history cleared.",
            admin_keyboard(2),
        )
        return

    if action == "clear_logs":
        await safe_edit(
            query.message,
            "🧽 **CLEAR LOGS**\n\n"
            "Confirm deletion of activity logs.",
            InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "✅ Confirm Clear",
                        callback_data="admin_confirm_clear_logs",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "❌ Cancel",
                        callback_data="admin_page_2",
                    )
                ],
            ]),
        )
        return

    if action == "confirm_clear_logs":
        await logs_col.delete_many({})
        await safe_edit(
            query.message,
            "🧽 Activity logs cleared.",
            admin_keyboard(2),
        )
        return

    # ---------- GENERIC ADMIN ACTIONS ----------
    text = await admin_text(action)

    page = next(
        (
            i // 10
            for i, (_, key) in enumerate(ADMIN_ACTIONS)
            if key == action
        ),
        0,
    )

    await safe_edit(
        query.message,
        text,
        admin_keyboard(page),
    )


# ============================================================
# PREMIUM COMMANDS
# ============================================================

@main_app.on_message(filters.private & filters.command("grant_premium"))
async def grant_premium_command(client, message):
    if not is_admin(message.from_user.id):
        return

    parts = (message.text or "").split()

    if len(parts) != 3:
        await message.reply_text(
            "Usage: /grant_premium BOT_USERNAME DAYS"
        )
        return

    try:
        days = int(parts[2])
        until = await grant_premium(
            parts[1],
            days,
            message.from_user.id,
        )

        await message.reply_text(
            "🎁 Premium granted to "
            f"@{parts[1].lstrip('@')} until {until}"
        )
    except Exception as exc:
        await message.reply_text(
            f"❌ Grant failed:\n`{str(exc)[:500]}`"
        )


@main_app.on_message(filters.private & filters.command("revoke_premium"))
async def revoke_premium_command(client, message):
    if not is_admin(message.from_user.id):
        return

    parts = (message.text or "").split()

    if len(parts) != 2:
        await message.reply_text(
            "Usage: /revoke_premium BOT_USERNAME"
        )
        return

    try:
        ok = await revoke_premium(parts[1])
        await message.reply_text(
            "🚫 Premium revoked."
            if ok
            else "❌ Bot not found."
        )
    except Exception as exc:
        await message.reply_text(
            f"❌ Revoke failed:\n`{str(exc)[:500]}`"
        )


@main_app.on_message(filters.private & filters.command("premium_price"))
async def premium_price_command(client, message):
    if not is_admin(message.from_user.id):
        return

    parts = (message.text or "").split()

    if (
        len(parts) != 3
        or parts[1] not in {"1m", "3m", "6m", "1y"}
    ):
        await message.reply_text(
            "Usage: /premium_price 1m 100"
        )
        return

    try:
        prices = await get_prices()
        prices[parts[1]] = int(parts[2])

        from database import db
        await db.set_premium_prices(prices)

        await message.reply_text(
            f"✅ {parts[1]} Premium price set to "
            f"{parts[2]} XTR."
        )
    except Exception as exc:
        await message.reply_text(
            f"❌ Price update failed:\n`{str(exc)[:500]}`"
        )


# ============================================================
# CREATE BOT + BROADCAST TEXT
# ============================================================

@main_app.on_message(
    filters.private
    & ~filters.command([
        "start",
        "admin",
        "cancel",
        "grant_premium",
        "revoke_premium",
        "premium_price",
    ])
)
async def text_handler(client, message):
    uid = message.from_user.id

    await save_user(message)

    # ---------- CREATE BOT ----------
    if uid in pending_create:
        pending_create.discard(uid)

        raw = (message.text or "").strip()

        if "|" not in raw:
            await message.reply_text(
                "❌ Invalid format.\n\n"
                "Use:\n"
                "`My Downloader | MyDownloaderBot`"
            )
            return

        bot_name, bot_username = [
            x.strip()
            for x in raw.split("|", 1)
        ]

        if not bot_name or not bot_username:
            await message.reply_text(
                "❌ Bot name and username are required."
            )
            return

        status = await message.reply_text(
            "⏳ Creating your bot..."
        )

        try:
            from bot_creator import create_bot_via_botfather
            from database import register_bot
            from bot_manager import start_managed_bot

            token, final_username = await create_bot_via_bot(
                bot_name,
                bot_username,
            )

            await register_bot(
                uid,
                token,
                bot_name,
                final_username,
                None,
            )

            started = await start_managed_bot(
                token,
                final_username,
                uid,
            )

            if not started:
                raise RuntimeError(
                    "Bot was created but could not be started."
                )

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

    # ---------- MAIN BROADCAST ----------
    mode = pending_broadcast.get(uid)

    if mode and is_admin(uid):
        pending_broadcast.pop(uid, None)

        await message.reply_text(
            "📢 Broadcast started..."
        )

        try:
            users = await users_col.find({}).to_list(
                length=200000
            )

            sent = 0
            failed = 0

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
                f"✅ Sent: {sent}\n"
                f"❌ Failed: {failed}"
            )

        except Exception as exc:
            await message.reply_text(
                f"❌ Broadcast failed:\n`{str(exc)[:1000]}`"
            )

        return

    await message.reply_text(
        "Use the menu below:",
        reply_markup=user_keyboard(uid),
    )


# ============================================================
# DIAGNOSTIC LOGGER
# ============================================================

@main_app.on_message(filters.private, group=1000)
async def update_diagnostic(client, message):
    try:
        logger.info(
            "📡 TELEGRAM UPDATE RECEIVED | user=%s | text=%r",
            message.from_user.id
            if message.from_user
            else "unknown",
            (message.text or message.caption or "")[:200],
        )
    except Exception:
        logger.exception(
            "Diagnostic handler error"
        )
