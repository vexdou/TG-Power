import asyncio
import logging
import re

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    CallbackQuery,
)

import config

from database import (
    init_db,
    add_user,
    get_user_bots,
    count_user_bots,
    get_main_stats,
    can_create_bot,
    is_bot_creation_enabled,
    toggle_bot_creation,
    get_bot_by_username,
    log_event,
)

from bot_creator import create_bot_via_botfather


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger("TG-POWER.MAIN-BOT")


# ============================================================
# MAIN BOT CLIENT
# ============================================================

main_app = Client(
    name="main_saas_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    workers=16,
)


# ============================================================
# STATES
# ============================================================

pending_create = {}
pending_admin = {}


# ============================================================
# USER HELPERS
# ============================================================

async def ensure_user(message: Message):

    if not message.from_user:
        return

    try:
        await add_user(
            message.from_user.id,
            message.from_user.first_name or "",
            message.from_user.username or "",
        )

    except Exception:
        logger.exception(
            "Failed to save user %s",
            message.from_user.id,
        )


# ============================================================
# MAIN KEYBOARD
# ============================================================

def main_keyboard(user_id: int):

    rows = [
        [
            InlineKeyboardButton(
                "➕ Create New Bot",
                callback_data="main:create",
            ),
            InlineKeyboardButton(
                "📦 My Bots",
                callback_data="main:mybots",
            ),
        ],
        [
            InlineKeyboardButton(
                "📊 My Statistics",
                callback_data="main:mystats",
            ),
        ],
        [
            InlineKeyboardButton(
                "📚 Help",
                callback_data="main:help",
            ),
        ],
    ]

    if user_id in config.ADMIN_IDS:

        rows.append([
            InlineKeyboardButton(
                "👑 Main Admin Panel",
                callback_data="main:admin",
            )
        ])

    return InlineKeyboardMarkup(rows)


# ============================================================
# ADMIN KEYBOARD
# ============================================================

def admin_keyboard():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📊 Statistics",
                callback_data="admin:stats",
            ),
            InlineKeyboardButton(
                "🤖 All Bots",
                callback_data="admin:bots",
            ),
        ],
        [
            InlineKeyboardButton(
                "👥 Users",
                callback_data="admin:users",
            ),
            InlineKeyboardButton(
                "📢 Broadcast",
                callback_data="admin:broadcast",
            ),
        ],
        [
            InlineKeyboardButton(
                "📢 Broadcast All Bots",
                callback_data="admin:allbroadcast",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔐 Bot Creation",
                callback_data="admin:creation",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔙 Main Menu",
                callback_data="main:back",
            ),
        ],
    ])


# ============================================================
# /START
# ============================================================

@main_app.on_message(
    filters.command("start") & filters.private
)
async def start_cmd(client: Client, message: Message):

    logger.info(
        "📩 /start received from user %s",
        message.from_user.id if message.from_user else "unknown",
    )

    await ensure_user(message)

    await message.reply_text(
        "👋 **Welcome to Managed Downloader Bots!**\n\n"
        "Create and manage your own Telegram downloader bot "
        "from this platform.",
        reply_markup=main_keyboard(
            message.from_user.id
        ),
    )


# ============================================================
# /ADMIN
# ============================================================

@main_app.on_message(
    filters.command("admin") & filters.private
)
async def admin_cmd(client: Client, message: Message):

    await ensure_user(message)

    uid = message.from_user.id

    if uid not in config.ADMIN_IDS:
        await message.reply_text(
            "⛔ Admin only."
        )
        return

    await message.reply_text(
        "👑 **Main Admin Panel**",
        reply_markup=admin_keyboard(),
    )


# ============================================================
# CALLBACKS
# ============================================================

@main_app.on_callback_query()
async def callback_handler(
    client: Client,
    query: CallbackQuery,
):

    uid = query.from_user.id
    data = query.data or ""

    try:
        await query.answer()
    except Exception:
        pass

    # --------------------------------------------------------
    # MAIN: BACK
    # --------------------------------------------------------

    if data == "main:back":

        await query.message.edit_text(
            "🏠 **Main Menu**",
            reply_markup=main_keyboard(uid),
        )

        return

    # --------------------------------------------------------
    # CREATE BOT
    # --------------------------------------------------------

    if data == "main:create":

        if not await is_bot_creation_enabled():

            await query.message.edit_text(
                "🔴 **Bot Creation is currently disabled.**",
                reply_markup=main_keyboard(uid),
            )

            return

        if not await can_create_bot(uid):

            await query.message.edit_text(
                "⛔ **You don't have bot creation access.**\n\n"
                "Please contact the Main Admin.",
                reply_markup=main_keyboard(uid),
            )

            return

        count = await count_user_bots(uid)

        if count >= config.MAX_BOTS_PER_USER:

            await query.message.edit_text(
                f"⛔ You can create a maximum of "
                f"**{config.MAX_BOTS_PER_USER} bots**.",
                reply_markup=main_keyboard(uid),
            )

            return

        pending_create[uid] = True

        await query.message.edit_text(
            "🤖 **Create New Bot**\n\n"
            "Send the bot name and username in this format:\n\n"
            "`My Downloader | MyDownloaderBot`\n\n"
            "The username must end with `bot`.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "❌ Cancel",
                        callback_data="main:cancel",
                    )
                ]
            ]),
        )

        return

    # --------------------------------------------------------
    # CANCEL
    # --------------------------------------------------------

    if data == "main:cancel":

        pending_create.pop(uid, None)
        pending_admin.pop(uid, None)

        await query.message.edit_text(
            "✅ Cancelled.",
            reply_markup=main_keyboard(uid),
        )

        return

    # --------------------------------------------------------
    # MY BOTS
    # --------------------------------------------------------

    if data == "main:mybots":

        bots = await get_user_bots(uid)

        if not bots:

            text = (
                "📦 **My Bots**\n\n"
                "You don't have any managed bots yet."
            )

        else:

            lines = [
                "📦 **My Managed Bots**\n"
            ]

            for bot in bots:

                username = bot.get(
                    "username",
                    "unknown",
                )

                status = bot.get(
                    "status",
                    "unknown",
                )

                users = bot.get(
                    "total_users",
                    0,
                )

                downloads = bot.get(
                    "total_downloads",
                    0,
                )

                lines.append(
                    f"🤖 @{username}\n"
                    f"   Status: {status}\n"
                    f"   👥 Users: {users}\n"
                    f"   📥 Downloads: {downloads}\n"
                )

            text = "\n".join(lines)

        await query.message.edit_text(
            text,
            reply_markup=main_keyboard(uid),
        )

        return

    # --------------------------------------------------------
    # MY STATS
    # --------------------------------------------------------

    if data == "main:mystats":

        bots = await get_user_bots(uid)

        total_users = sum(
            int(bot.get("total_users", 0))
            for bot in bots
        )

        total_downloads = sum(
            int(bot.get("total_downloads", 0))
            for bot in bots
        )

        await query.message.edit_text(
            "📊 **My Statistics**\n\n"
            f"🤖 Bots: {len(bots)}\n"
            f"👥 Users: {total_users}\n"
            f"📥 Downloads: {total_downloads}",
            reply_markup=main_keyboard(uid),
        )

        return

    # --------------------------------------------------------
    # HELP
    # --------------------------------------------------------

    if data == "main:help":

        await query.message.edit_text(
            "📚 **Help**\n\n"
            "1. Create a managed bot.\n"
            "2. Open your bot.\n"
            "3. Send `/admin` from the owner account.\n"
            "4. Configure your bot.\n"
            "5. Share the bot with your users.",
            reply_markup=main_keyboard(uid),
        )

        return

    # --------------------------------------------------------
    # MAIN ADMIN
    # --------------------------------------------------------

    if data == "main:admin":

        if uid not in config.ADMIN_IDS:

            await query.answer(
                "Admin only.",
                show_alert=True,
            )

            return

        await query.message.edit_text(
            "👑 **Main Admin Panel**",
            reply_markup=admin_keyboard(),
        )

        return

    # --------------------------------------------------------
    # ADMIN CALLBACKS
    # --------------------------------------------------------

    if data.startswith("admin:"):

        if uid not in config.ADMIN_IDS:

            await query.answer(
                "Admin only.",
                show_alert=True,
            )

            return

        action = data.split(":", 1)[1]

        # ----------------------------------------------------
        # STATS
        # ----------------------------------------------------

        if action == "stats":

            stats = await get_main_stats()

            await query.message.edit_text(
                "📊 **Main Statistics**\n\n"
                f"👥 Users: {stats.get('users', 0)}\n"
                f"🤖 Bots: {stats.get('bots', 0)}\n"
                f"📥 Downloads: {stats.get('downloads', 0)}\n"
                f"👑 Owners: {len(stats.get('owners', []))}",
                reply_markup=admin_keyboard(),
            )

            return

        # ----------------------------------------------------
        # ALL BOTS
        # ----------------------------------------------------

        if action == "bots":

            from database import bots_col

            bots = await bots_col.find(
                {
                    "status": {
                        "$ne": "deleted"
                    }
                }
            ).sort(
                "created_at",
                -1,
            ).to_list(
                length=100
            )

            if not bots:

                text = (
                    "🤖 **All Managed Bots**\n\n"
                    "No managed bots found."
                )

            else:

                lines = [
                    "🤖 **All Managed Bots**\n"
                ]

                for bot in bots:

                    lines.append(
                        f"🤖 @{bot.get('username', 'unknown')}\n"
                        f"👤 Owner: `{bot.get('owner_id')}`\n"
                        f"👥 Users: {bot.get('total_users', 0)}\n"
                        f"📥 Downloads: {bot.get('total_downloads', 0)}\n"
                        f"📡 Status: {bot.get('status', 'unknown')}\n"
                    )

                text = "\n".join(lines)

            await query.message.edit_text(
                text[:4000],
                reply_markup=admin_keyboard(),
            )

            return

        # ----------------------------------------------------
        # USERS
        # ----------------------------------------------------

        if action == "users":

            from database import users_col

            total = await users_col.count_documents({})

            await query.message.edit_text(
                "👥 **Main Bot Users**\n\n"
                f"Total users: **{total}**",
                reply_markup=admin_keyboard(),
            )

            return

        # ----------------------------------------------------
        # CREATION SETTINGS
        # ----------------------------------------------------

        if action == "creation":

            enabled = await is_bot_creation_enabled()

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🟢 Enable",
                        callback_data="admin:create_on",
                    ),
                    InlineKeyboardButton(
                        "🔴 Disable",
                        callback_data="admin:create_off",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data="main:admin",
                    )
                ],
            ])

            await query.message.edit_text(
                "🔐 **Bot Creation Settings**\n\n"
                f"Status: {'🟢 ENABLED' if enabled else '🔴 DISABLED'}",
                reply_markup=keyboard,
            )

            return

        # ----------------------------------------------------
        # BROADCAST
        # ----------------------------------------------------

        if action in {
            "broadcast",
            "allbroadcast",
        }:

            pending_admin[uid] = action

            await query.message.edit_text(
                "📢 **Broadcast**\n\n"
                "Send the message/media now.\n\n"
                "Send `/cancel` to cancel."
            )

            return

    # --------------------------------------------------------
    # CREATION ON / OFF
    # --------------------------------------------------------

    if data in {
        "admin:create_on",
        "admin:create_off",
    }:

        if uid not in config.ADMIN_IDS:
            return

        enabled = data.endswith("on")

        await toggle_bot_creation(enabled)

        await query.message.edit_text(
            "✅ **Bot Creation Updated**\n\n"
            f"Status: {'🟢 ENABLED' if enabled else '🔴 DISABLED'}",
            reply_markup=admin_keyboard(),
        )

        return


# ============================================================
# MAIN TEXT HANDLER
# ============================================================

@main_app.on_message(
    filters.private
    & ~filters.command([
        "start",
        "admin",
        "cancel",
    ])
)
async def text_handler(
    client: Client,
    message: Message,
):

    await ensure_user(message)

    uid = message.from_user.id

    # --------------------------------------------------------
    # CREATE BOT
    # --------------------------------------------------------

    if uid in pending_create:

        pending_create.pop(uid, None)

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

        status_message = await message.reply_text(
            "⏳ **Creating your bot...**\n\n"
            "Please wait."
        )

        try:

            token, final_username = (
                await create_bot_via_botfather(
                    bot_name,
                    bot_username,
                )
            )

            # Save bot to DB.
            from database import register_bot

            await register_bot(
                uid,
                token,
                bot_name,
                final_username,
                None,
            )

            # Start the managed bot only after registration.
            from bot_manager import start_managed_bot

            started = await start_managed_bot(
                token,
                final_username,
                uid,
            )

            if not started:

                raise RuntimeError(
                    "Bot was created, but the server could not start it."
                )

            await log_event(
                "bot_created",
                owner_id=uid,
                bot_username=final_username,
            )

            await status_message.edit_text(
                "✅ **Bot Created Successfully!**\n\n"
                f"🤖 @{final_username}\n\n"
                f"🔗 https://t.me/{final_username}\n\n"
                "Use `/admin` inside your bot to open the owner panel.",
                reply_markup=main_keyboard(uid),
            )

        except Exception as exc:

            logger.exception(
                "Bot creation failed for user %s",
                uid,
            )

            await status_message.edit_text(
                "❌ **Bot Creation Failed**\n\n"
                f"`{str(exc)[:1200]}`",
                reply_markup=main_keyboard(uid),
            )

        return

    # --------------------------------------------------------
    # ADMIN BROADCAST
    # --------------------------------------------------------

    if uid in pending_admin:

        mode = pending_admin.pop(uid, None)

        if uid not in config.ADMIN_IDS:
            return

        await message.reply_text(
            "📢 Broadcast started..."
        )

        if mode == "broadcast":

            from database import users_col

            users = await users_col.find(
                {}
            ).to_list(
                length=200000
            )

            sent = 0
            failed = 0

            for user in users:

                target = user.get("user_id")

                if not target:
                    continue

                try:

                    await message.copy(
                        target
                    )

                    sent += 1

                    await asyncio.sleep(
                        0.05
                    )

                except Exception:

                    failed += 1

            await message.reply_text(
                "📢 **Broadcast Finished**\n\n"
                f"✅ Sent: {sent}\n"
                f"❌ Failed: {failed}"
            )

            return

        if mode == "allbroadcast":

            from database import (
                bots_col,
                bot_users_col,
            )

            from bot_manager import active_bots

            bots = await bots_col.find(
                {
                    "status": "active"
                }
            ).to_list(
                length=2000
            )

            sent = 0
            failed = 0
            seen = set()

            for bot in bots:

                username = bot.get(
                    "username"
                )

                if not username:
                    continue

                app = active_bots.get(
                    username
                )

                if not app:
                    continue

                users = await bot_users_col.find(
                    {
                        "bot_username": username,
                        "is_blocked": {
                            "$ne": True
                        },
                    }
                ).to_list(
                    length=200000
                )

                for user in users:

                    target = user.get(
                        "user_id"
                    )

                    if not target:
                        continue

                    if target in seen:
                        continue

                    seen.add(target)

                    try:

                        await message.copy(
                            target
                        )

                        sent += 1

                        await asyncio.sleep(
                            0.05
                        )

                    except Exception:

                        failed += 1

            await message.reply_text(
                "📢 **All Bots Broadcast Finished**\n\n"
                f"✅ Sent: {sent}\n"
                f"❌ Failed: {failed}"
            )

            return

    # --------------------------------------------------------
    # DEFAULT RESPONSE
    # --------------------------------------------------------

    await message.reply_text(
        "Use the menu below:",
        reply_markup=main_keyboard(uid),
    )


# ============================================================
# CANCEL
# ============================================================

@main_app.on_message(
    filters.command("cancel") & filters.private
)
async def cancel_cmd(
    client: Client,
    message: Message,
):

    uid = message.from_user.id

    pending_create.pop(uid, None)
    pending_admin.pop(uid, None)

    await message.reply_text(
        "✅ Cancelled.",
        reply_markup=main_keyboard(uid),
    )


# ============================================================
# DATABASE STARTUP
# ============================================================

async def startup():

    logger.info(
        "🗄️ Initializing database..."
    )

    await init_db()

    logger.info(
        "🟢 Database initialized."
        )
