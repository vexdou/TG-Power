import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from config import Config

from database import (
    add_user,
    get_user_bots,
    count_user_bots,
    get_main_stats,
    can_create_bot,
    is_bot_creation_enabled,
    toggle_bot_creation,
    log_event,
    get_main_user_help,
)

logger = logging.getLogger("TG-POWER.MAIN")

main_app = Client(
    "main_saas_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
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
    if user_id in Config.ADMIN_IDS:
        rows.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin")])
    return InlineKeyboardMarkup(rows)

def admin_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
            InlineKeyboardButton("🤖 All Bots", callback_data="admin_bots"),
        ],
        [
            InlineKeyboardButton("👥 Users", callback_data="admin_users"),
            InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
        ],
        [InlineKeyboardButton("🔐 Bot Creation", callback_data="admin_creation")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="back")],
    ])

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
    if uid not in Config.ADMIN_IDS:
        await message.reply_text("⛔ Admin only.")
        return
    await message.reply_text("👑 **Main Admin Panel**", reply_markup=admin_keyboard())

@main_app.on_message(filters.private & filters.command("cancel"))
async def cancel_handler(client, message):
    uid = message.from_user.id
    pending_create.discard(uid)
    pending_broadcast.pop(uid, None)
    await message.reply_text("✅ Cancelled.", reply_markup=user_keyboard(uid))

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
        maximum = getattr(Config, "MAX_BOTS_PER_USER", 5)
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
        try:
            info = await get_main_user_help(uid)
        except Exception:
            logger.exception("Could not load Help profile for user %s", uid)
            info = None

        if info:
            username = info.get("username") or "Not set"
            username_display = (
                f"@{username.lstrip('@')}" if username != "Not set" else username
            )
            joined_at = info.get("created_at")
            joined_text = (
                joined_at.strftime("%Y-%m-%d %H:%M:%S UTC")
                if joined_at
                else "Not available"
            )

            help_text = (
                "📚 **TG-Power Help & Your Info**\n\n"
                "👤 **Your Information**\n"
                f"• Name: {info.get('first_name') or 'Not set'}\n"
                f"• Username: {username_display}\n"
                f"• Telegram ID: `{info.get('user_id', uid)}`\n"
                f"• Joined: {joined_text}\n"
                f"• Language: {info.get('lang') or 'so'}\n"
                f"• Bots Created: {info.get('bot_count', 0)}\n"
                f"• Downloads: {info.get('download_count', 0)}\n\n"
                "ℹ️ **About TG-Power**\n"
                "TG-Power lets you create and manage your own Telegram downloader bots. "
                "Your bots can handle supported social-media links and give users an easy "
                "way to download media.\n\n"
                "🚀 **How to use**\n"
                "• ➕ Create New Bot — create your downloader bot.\n"
                "• 📦 My Bots — view your created bots.\n"
                "• 📊 My Statistics — view your statistics.\n"
                "• /cancel — cancel an active action."
            )
        else:
            help_text = (
                "📚 **TG-Power Help**\n\n"
                "Your profile could not be loaded yet. Please use /start again.\n\n"
                "TG-Power lets you create and manage Telegram downloader bots.\n\n"
                "• ➕ Create New Bot — create your downloader bot.\n"
                "• 📦 My Bots — view your bots.\n"
                "• 📊 My Statistics — view statistics."
            )

        await query.message.edit_text(help_text, reply_markup=user_keyboard(uid))
        return

    if data == "admin":
        if uid not in Config.ADMIN_IDS:
            return
        await query.message.edit_text(
            "👑 **Main Admin Panel**", reply_markup=admin_keyboard()
        )
        return

    if uid not in Config.ADMIN_IDS or not data.startswith("admin_"):
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
    if mode and uid in Config.ADMIN_IDS:
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
