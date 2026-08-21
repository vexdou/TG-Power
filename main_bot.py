import asyncio
import logging
import os
import time

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButtonRequestManagedBot,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.error import TelegramError, Forbidden

from config import Config
from database import db
from bot_manager import bot_manager

logger = logging.getLogger(__name__)

LANGUAGES = {
    "en": {"name": "English 🇬🇧"},
    "so": {"name": "Soomaali 🇸🇴"},
    "ar": {"name": "العربية 🇸🇦"},
    "es": {"name": "Español 🇪🇸"},
}


def admin_ids():
    ids = set()
    try:
        if Config.OWNER_ID:
            ids.add(int(Config.OWNER_ID))
    except Exception:
        pass
    for value in getattr(Config, "ADMIN_IDS", []):
        try:
            ids.add(int(value))
        except (TypeError, ValueError):
            pass
    return ids


def is_admin(user_id: int) -> bool:
    return int(user_id) in admin_ids()


def main_keyboard(user_id: int | None = None):
    request_id = int(time.time() * 1000) % 2147483647
    create_button = KeyboardButton(
        text="➕ Create New Bot",
        request_managed_bot=KeyboardButtonRequestManagedBot(
            request_id=request_id,
            suggested_name="My Downloader Bot",
            suggested_username="MyDownloaderBot",
        ),
    )
    rows = [
        [create_button],
        [KeyboardButton("🤖 My Bots"), KeyboardButton("🌐 Language")],
        [KeyboardButton("ℹ️ Help")],
    ]
    if user_id is not None and is_admin(user_id):
        rows.append([KeyboardButton("👑 Admin Panel")])
    return ReplyKeyboardMarkup(
        rows, resize_keyboard=True, is_persistent=True
    )


def admin_keyboard():
    # 16 admin controls. Inline buttons are used only inside menus
    # where selecting a specific bot/channel is required.
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📊 Dashboard"), KeyboardButton("🤖 All Bots")],
            [KeyboardButton("👥 Users"), KeyboardButton("📥 Downloads")],
            [KeyboardButton("📢 Broadcast All"), KeyboardButton("📣 Broadcast Bot")],
            [KeyboardButton("🔐 Force Join"), KeyboardButton("⚙️ Bot Creation")],
            [KeyboardButton("▶️ Start Bot"), KeyboardButton("⏹ Stop Bot")],
            [KeyboardButton("🗑 Delete Bot"), KeyboardButton("❤️ Bot Health")],
            [KeyboardButton("🧰 System Settings"), KeyboardButton("🧹 Cleanup")],
            [KeyboardButton("🌐 Language"), KeyboardButton("🔙 User Panel")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def language_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("English 🇬🇧", callback_data="lang_en"),
            InlineKeyboardButton("Soomaali 🇸🇴", callback_data="lang_so"),
        ],
        [
            InlineKeyboardButton("العربية 🇸🇦", callback_data="lang_ar"),
            InlineKeyboardButton("Español 🇪🇸", callback_data="lang_es"),
        ],
    ])


class MainSaaSBot:
    def __init__(self):
        self.app = (
            Application.builder()
            .token(Config.BOT_TOKEN)
            .build()
        )
        self._setup_handlers()

    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("admin", self.admin_command))
        self.app.add_handler(CommandHandler("id", self.id_command))
        self.app.add_handler(CommandHandler("language", self.language_command))

        self.app.add_handler(
            MessageHandler(
                filters.StatusUpdate.MANAGED_BOT_CREATED,
                self.handle_managed_bot_created,
            )
        )
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text)
        )
        self.app.add_error_handler(self.error_handler)

    async def start_bot(self):
        await self.app.initialize()
        await self.app.bot.delete_webhook(drop_pending_updates=True)
        await self.app.start()
        if self.app.updater is None:
            raise RuntimeError("Main bot updater is not available.")
        await self.app.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
            poll_interval=1.0,
            timeout=30,
        )
        me = await self.app.bot.get_me()
        logger.info("👑 Main SaaS Bot Online: @%s", me.username)

    async def stop_bot(self):
        try:
            if self.app.updater and self.app.updater.running:
                await self.app.updater.stop()
            if self.app.running:
                await self.app.stop()
            await self.app.shutdown()
        except Exception:
            logger.exception("Main bot shutdown error")

    async def id_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user:
            return
        uid = update.effective_user.id
        await update.message.reply_text(
            f"🆔 Your Telegram ID is:\n\n{uid}\n\n"
            "Admin-ka haddii uusan kuu furmin, ku dar ID-kan Render Environment Variable:\n"
            "OWNER_ID=<ID>\n"
            "ama ADMIN_IDS=<ID1,ID2>"
        )

    async def get_language(self, user_id):
        try:
            return await db.get_main_user_language(user_id)
        except Exception:
            user = await db.get_main_user(user_id)
            return (user or {}).get("language", "en")

    async def save_language(self, user_id, language):
        await db.set_main_user_language(user_id, language)

    async def language_command(self, update, context):
        if update.effective_user:
            await update.message.reply_text(
                "🌐 Choose your language / Dooro luuqadda:",
                reply_markup=language_keyboard(),
            )

    async def start_command(self, update, context):
        if not update.effective_user:
            return
        u = update.effective_user
        try:
            # save_main_user uses $setOnInsert for language, so /start
            # NEVER resets an existing user's selected language.
            await db.save_main_user(
                user_id=u.id,
                username=u.username or "",
                full_name=u.full_name or "",
            )
        except Exception:
            logger.exception("Could not save main user")

        await update.message.reply_text(
            "🤖 TG-Power Bot Builder\n\n"
            f"Welcome, {u.first_name or 'User'}! 👋\n\n"
            "Create and manage your downloader bot from Telegram.",
            reply_markup=main_keyboard(u.id),
        )

    async def admin_command(self, update, context):
        if not update.effective_user:
            return
        if not is_admin(update.effective_user.id):
            await update.message.reply_text(
                "⛔ You are not authorized.\n\n"
                f"Your ID: {update.effective_user.id}\n"
                "Use /id and set OWNER_ID or ADMIN_IDS in Render."
            )
            return
        await self.show_dashboard(update)

    async def show_dashboard(self, update):
        s = await self.stats()
        await update.message.reply_text(
            "👑 MAIN ADMIN PANEL\n\n"
            f"👥 Users: {s['users']}\n"
            f"🤖 Bots: {s['bots']}\n"
            f"🟢 Active: {s['active']}\n"
            f"🔴 Failed: {s['failed']}\n"
            f"📥 Downloads: {s['downloads']}\n\n"
            "Dooro maamulka aad rabto:",
            reply_markup=admin_keyboard(),
        )

    async def stats(self):
        try:
            return {
                "users": await db.main_users.count_documents({}),
                "bots": await db.bots.count_documents({}),
                "active": await db.bots.count_documents({"status": "active"}),
                "failed": await db.bots.count_documents({"status": "failed"}),
                "downloads": await db.downloads.count_documents({}),
            }
        except Exception:
            return {"users": 0, "bots": 0, "active": 0, "failed": 0, "downloads": 0}

    async def show_all_bots(self, update):
        bots = await db.get_all_bots()
        if not bots:
            await update.message.reply_text("🤖 No managed bots yet.")
            return
        buttons = []
        text = "🤖 ALL MANAGED BOTS\n\n"
        for b in bots:
            bid = b.get("bot_id")
            name = b.get("username") or "N/A"
            status = b.get("status", "unknown")
            text += f"{'🟢' if status == 'active' else '🔴'} @{name}\nID: {bid}\nStatus: {status}\n\n"
            buttons.append([
                InlineKeyboardButton("📊 Stats", callback_data=f"bstats:{bid}"),
                InlineKeyboardButton("⚙️ Manage", callback_data=f"manage:{bid}"),
            ])
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    async def bot_stats(self, query, bot_id):
        bot = await db.get_bot(bot_id)
        if not bot:
            await query.edit_message_text("❌ Bot not found.")
            return
        s = await db.get_bot_stats(bot_id)
        await query.edit_message_text(
            "📊 BOT STATISTICS\n\n"
            f"🤖 @{bot.get('username','N/A')}\n"
            f"🆔 {bot_id}\n"
            f"👤 Owner: {bot.get('owner_id','N/A')}\n"
            f"🟢 Status: {bot.get('status','unknown')}\n\n"
            f"👥 Users: {s.get('total_users',0)}\n"
            f"📥 Downloads: {s.get('total_downloads',0)}\n"
            f"🎬 Videos: {s.get('videos',0)}\n"
            f"🎵 Audio: {s.get('audio',0)}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 All Bots", callback_data="allbots")
            ]]),
        )

    async def manage_bot(self, query, bot_id):
        bot = await db.get_bot(bot_id)
        if not bot:
            await query.edit_message_text("❌ Bot not found.")
            return
        status = bot.get("status", "unknown")
        action = (
            InlineKeyboardButton("⏹ Stop", callback_data=f"stop:{bot_id}")
            if status == "active"
            else InlineKeyboardButton("▶️ Start", callback_data=f"startbot:{bot_id}")
        )
        await query.edit_message_text(
            "⚙️ BOT MANAGEMENT\n\n"
            f"🤖 @{bot.get('username','N/A')}\n"
            f"🆔 {bot_id}\n"
            f"Status: {status}",
            reply_markup=InlineKeyboardMarkup([
                [action, InlineKeyboardButton("📊 Stats", callback_data=f"bstats:{bot_id}")],
                [InlineKeyboardButton("🔐 Force Join", callback_data=f"force:{bot_id}")],
                [InlineKeyboardButton("🗑 Delete", callback_data=f"confirmdel:{bot_id}")],
                [InlineKeyboardButton("🔙 All Bots", callback_data="allbots")],
            ]),
        )

    async def choose_bot(self, update, mode):
        bots = await db.get_all_bots()
        if not bots:
            await update.message.reply_text("🤖 No managed bots.")
            return
        buttons = []
        for b in bots:
            bid = b.get("bot_id")
            name = b.get("username") or "N/A"
            buttons.append([InlineKeyboardButton(
                f"@{name}", callback_data=f"{mode}:{bid}"
            )])
        await update.message.reply_text(
            "Choose a bot:", reply_markup=InlineKeyboardMarkup(buttons)
        )

    async def start_bot(self, query, bot_id):
        bot = await db.get_bot(bot_id)
        if not bot:
            await query.answer("Bot not found", show_alert=True)
            return
        ok = await bot_manager.start_bot_instance(bot_id, bot.get("token"))
        if ok:
            await db.update_bot_status(bot_id, "active")
            await query.answer("🟢 Started")
        else:
            await query.answer("🔴 Failed. Check Render logs.", show_alert=True)
        await self.manage_bot(query, bot_id)

    async def stop_bot(self, query, bot_id):
        try:
            await bot_manager.stop_bot_instance(bot_id)
            await db.update_bot_status(bot_id, "stopped")
            await query.answer("⏹ Stopped")
        except Exception:
            await query.answer("❌ Stop failed", show_alert=True)
        await self.manage_bot(query, bot_id)

    async def delete_bot(self, query, bot_id):
        await bot_manager.stop_bot_instance(bot_id)
        await db.delete_bot(bot_id)
        await query.edit_message_text("🗑 Bot deleted successfully.")

    async def show_users(self, update):
        main_users = await db.main_users.count_documents({})
        bot_users = await db.users.count_documents({})
        unique = len(await db.users.distinct("user_id"))
        await update.message.reply_text(
            "👥 USER CENTER\n\n"
            f"👤 Main users: {main_users}\n"
            f"👥 Bot user records: {bot_users}\n"
            f"🧑 Unique bot users: {unique}"
        )

    async def show_downloads(self, update):
        total = await db.downloads.count_documents({})
        ok = await db.downloads.count_documents({"status": "success"})
        failed = await db.downloads.count_documents({"status": "failed"})
        await update.message.reply_text(
            "📥 DOWNLOAD ANALYTICS\n\n"
            f"📥 Total: {total}\n"
            f"🟢 Success: {ok}\n"
            f"🔴 Failed: {failed}"
        )

    async def show_health(self, update):
        bots = await db.get_all_bots()
        running = len(bot_manager.running_bots)
        starting = len(bot_manager.starting_bots)
        failed = sum(1 for b in bots if b.get("status") == "failed")
        await update.message.reply_text(
            "❤️ SYSTEM HEALTH\n\n"
            f"🤖 DB bots: {len(bots)}\n"
            f"🟢 Running in memory: {running}\n"
            f"🟡 Starting: {starting}\n"
            f"🔴 Failed: {failed}\n"
            f"🟢 MongoDB: {'connected' if db.db is not None else 'not connected'}"
        )

    async def system_settings(self, update):
        creation = await db.get_system_setting("bot_creation_enabled", True)
        await update.message.reply_text(
            "🧰 SYSTEM SETTINGS\n\n"
            f"🤖 Bot creation: {'🟢 ON' if creation else '🔴 OFF'}\n"
            f"⏱ Max video duration: {Config.MAX_VIDEO_DURATION_SECONDS // 60} min\n"
            f"📦 Max file size: {Config.MAX_FILE_SIZE_MB} MB\n\n"
            "You can change OWNER_ID/ADMIN_IDS and other environment settings in Render."
        )

    async def creation_setting(self, update):
        enabled = await db.get_system_setting("bot_creation_enabled", True)
        await update.message.reply_text(
            f"⚙️ BOT CREATION\n\nCurrent: {'🟢 ENABLED' if enabled else '🔴 DISABLED'}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🟢 Enable", callback_data="creation:on"),
                InlineKeyboardButton("🔴 Disable", callback_data="creation:off"),
            ]]),
        )

    async def force_join(self, update):
        await self.choose_bot(update, "force")

    async def force_menu(self, query, bot_id):
        bot = await db.get_bot(bot_id)
        if not bot:
            await query.edit_message_text("❌ Bot not found.")
            return
        channels = bot.get("force_join_channels", [])
        text = "🔐 FORCE JOIN\n\n" + (
            "\n".join(f"• {c}" for c in channels) if channels else "• None"
        )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add", callback_data=f"forceadd:{bot_id}")],
                [InlineKeyboardButton("➖ Remove", callback_data=f"forcerem:{bot_id}")],
                [InlineKeyboardButton("🔙 Back", callback_data=f"manage:{bot_id}")],
            ]),
        )

    async def force_add_prompt(self, query, bot_id, context):
        context.user_data["state"] = "force_add"
        context.user_data["force_bot_id"] = bot_id
        await query.edit_message_text("➕ Send channel username, e.g. @MyChannel")

    async def force_remove_menu(self, query, bot_id):
        bot = await db.get_bot(bot_id)
        channels = (bot or {}).get("force_join_channels", [])
        if not channels:
            await query.answer("No channels configured.", show_alert=True)
            return
        buttons = [[InlineKeyboardButton(c, callback_data=f"forcedel:{bot_id}:{c[1:]}")] for c in channels]
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"force:{bot_id}")])
        await query.edit_message_text("➖ Remove channel:", reply_markup=InlineKeyboardMarkup(buttons))

    async def save_force_channel(self, update, context):
        bot_id = context.user_data.get("force_bot_id")
        channel = (update.message.text or "").strip()
        if not bot_id:
            return
        if not channel.startswith("@"):
            await update.message.reply_text("❌ Channel-ku waa inuu ku bilaabmaa @.")
            return
        await db.bots.update_one(
            {"bot_id": bot_id},
            {"$addToSet": {"force_join_channels": channel}},
        )
        context.user_data.clear()
        await update.message.reply_text("✅ Force Join channel added.", reply_markup=admin_keyboard())

    async def broadcast_all_prompt(self, update, context):
        context.user_data["state"] = "broadcast_all"
        await update.message.reply_text("📢 Send the message/media to broadcast to all managed-bot users.")

    async def broadcast_one_prompt(self, update):
        await self.choose_bot(update, "broadcast")

    async def perform_broadcast(self, update, context, bot_id=None):
        message = update.message
        if bot_id is None:
            bots = await db.get_all_bots()
        else:
            bots = [await db.get_bot(bot_id)]
        sent = failed = 0
        for bot in bots:
            if not bot:
                continue
            users = await db.get_all_bot_users(bot["bot_id"])
            for u in users:
                uid = u.get("user_id")
                if not uid:
                    continue
                try:
                    await message.copy(chat_id=uid)
                    sent += 1
                except (Forbidden, TelegramError):
                    failed += 1
                except Exception:
                    failed += 1
                await asyncio.sleep(0.05)
        context.user_data.clear()
        await message.reply_text(
            f"📢 Broadcast finished.\n\n🟢 Sent: {sent}\n🔴 Failed: {failed}",
            reply_markup=admin_keyboard(),
        )

    async def show_cleanup(self, update):
        failed = await db.bots.count_documents({"status": "failed"})
        stopped = await db.bots.count_documents({"status": "stopped"})
        await update.message.reply_text(
            "🧹 CLEANUP\n\n"
            f"🔴 Failed bot records: {failed}\n"
            f"⏹ Stopped bot records: {stopped}\n\n"
            "Use Delete Bot to remove a specific bot safely."
        )

    async def handle_text(self, update, context):
        if not update.message or not update.effective_user:
            return
        uid = update.effective_user.id
        text = update.message.text or ""
        state = context.user_data.get("state")

        if is_admin(uid):
            if state == "force_add":
                await self.save_force_channel(update, context)
                return
            if state == "broadcast_all":
                await self.perform_broadcast(update, context)
                return
            if state == "broadcast_one":
                bid = context.user_data.get("broadcast_bot_id")
                await self.perform_broadcast(update, context, bid)
                return

        if text == "👑 Admin Panel" and is_admin(uid):
            await self.show_dashboard(update)
            return
        if text == "🤖 My Bots":
            await self.show_my_bots(update)
            return
        if text == "🌐 Language":
            await self.language_command(update, context)
            return
        if text == "ℹ️ Help":
            await update.message.reply_text(
                "ℹ️ HELP\n\n"
                "Create New Bot → create a downloader bot.\n"
                "My Bots → see your bots.\n"
                "Language → change language."
            )
            return

        if not is_admin(uid):
            return

        actions = {
            "📊 Dashboard": lambda: self.show_dashboard(update),
            "🤖 All Bots": lambda: self.show_all_bots(update),
            "👥 Users": lambda: self.show_users(update),
            "📥 Downloads": lambda: self.show_downloads(update),
            "📢 Broadcast All": lambda: self.broadcast_all_prompt(update, context),
            "📣 Broadcast Bot": lambda: self.broadcast_one_prompt(update),
            "🔐 Force Join": lambda: self.force_join(update),
            "⚙️ Bot Creation": lambda: self.creation_setting(update),
            "▶️ Start Bot": lambda: self.choose_bot(update, "startbot"),
            "⏹ Stop Bot": lambda: self.choose_bot(update, "stop"),
            "🗑 Delete Bot": lambda: self.choose_bot(update, "confirmdel"),
            "❤️ Bot Health": lambda: self.show_health(update),
            "🧰 System Settings": lambda: self.system_settings(update),
            "🧹 Cleanup": lambda: self.show_cleanup(update),
            "🌐 Language": lambda: self.language_command(update, context),
        }
        action = actions.get(text)
        if action:
            await action()
            return
        if text == "🔙 User Panel":
            await update.message.reply_text("👤 User Panel", reply_markup=main_keyboard(uid))

    async def show_my_bots(self, update):
        bots = await db.get_user_bots(update.effective_user.id)
        if not bots:
            await update.message.reply_text("❌ You do not have a managed bot yet.")
            return
        text = "🤖 MY BOTS\n\n"
        buttons = []
        for b in bots:
            text += f"@{b.get('username','N/A')} — {b.get('status','unknown')}\n"
            buttons.append([InlineKeyboardButton(
                f"📊 @{b.get('username','N/A')}",
                callback_data=f"ownerstats:{b.get('bot_id')}"
            )])
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    async def handle_managed_bot_created(self, update, context):
        message = update.message
        if not message or not getattr(message, "managed_bot_created", None):
            return
        info = message.managed_bot_created
        bot_info = getattr(info, "bot", None)
        owner = update.effective_user
        if not bot_info or not owner:
            return
        if not await db.get_system_setting("bot_creation_enabled", True) and not is_admin(owner.id):
            await message.reply_text("⛔ Bot creation is currently disabled.")
            return
        bot_id = bot_info.id
        token = await self.get_managed_bot_token(bot_id)
        if not token:
            await message.reply_text(
                "❌ Managed bot token could not be retrieved. "
                "Make sure this main bot is configured as the Manager Bot."
            )
            return
        await db.add_new_bot(
            owner_id=owner.id,
            token=token,
            bot_id=bot_id,
            username=bot_info.username or "",
        )
        started = await bot_manager.start_bot_instance(bot_id, token)
        if started:
            await db.update_bot_status(bot_id, "active")
            await message.reply_text(
                f"✅ Bot is online!\n\n@{bot_info.username}\n"
                f"https://t.me/{bot_info.username}"
            )
        else:
            await message.reply_text(
                "⚠️ Bot was saved, but could not be started. Check Render logs."
            )

    async def get_managed_bot_token(self, bot_id):
        try:
            return await self.app.bot.get_managed_bot_token(bot_id)
        except Exception:
            logger.exception("Managed bot token error")
            return None

    async def handle_callback(self, update, context):
        q = update.callback_query
        if not q:
            return
        data = q.data or ""
        uid = q.from_user.id

        # Admin callbacks
        admin_prefixes = (
            "allbots", "bstats:", "manage:", "startbot:", "stop:",
            "confirmdel:", "force:", "forceadd:", "forcerem:", "forcedel:",
            "broadcast:", "creation:", "ownerstats:"
        )
        if data.startswith(admin_prefixes) and data.startswith("ownerstats:") is False:
            if not is_admin(uid):
                await q.answer("⛔ Admin only.", show_alert=True)
                return

        try:
            await q.answer()
        except Exception:
            pass

        if data.startswith("lang_"):
            lang = data.split("_", 1)[1]
            if lang in LANGUAGES:
                await self.save_language(uid, lang)
                await q.edit_message_text(f"✅ Language saved: {LANGUAGES[lang]['name']}")
            return

        if data == "allbots":
            bots = await db.get_all_bots()
            buttons = []
            for b in bots:
                bid = b["bot_id"]
                name = b.get("username") or "N/A"
                buttons.append([
                    InlineKeyboardButton(f"📊 @{name}", callback_data=f"bstats:{bid}"),
                    InlineKeyboardButton("⚙️ Manage", callback_data=f"manage:{bid}"),
                ])
            await q.edit_message_text(
                "🤖 ALL MANAGED BOTS",
                reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
            )
            return

        if data.startswith("bstats:"):
            await self.bot_stats(q, int(data.split(":")[1]))
            return

        if data.startswith("manage:"):
            await self.manage_bot(q, int(data.split(":")[1]))
            return

        if data.startswith("startbot:"):
            await self.start_bot(q, int(data.split(":")[1]))
            return

        if data.startswith("stop:"):
            await self.stop_bot(q, int(data.split(":")[1]))
            return

        if data.startswith("confirmdel:"):
            bid = int(data.split(":")[1])
            await q.edit_message_text(
                "⚠️ Are you sure you want to permanently delete this bot?",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Cancel", callback_data=f"manage:{bid}"),
                    InlineKeyboardButton("🗑 YES DELETE", callback_data=f"delete:{bid}"),
                ]]),
            )
            return

        if data.startswith("delete:"):
            await self.delete_bot(q, int(data.split(":")[1]))
            return

        if data.startswith("force:"):
            await self.force_menu(q, int(data.split(":")[1]))
            return

        if data.startswith("forceadd:"):
            await self.force_add_prompt(q, int(data.split(":")[1]), context)
            return

        if data.startswith("forcerem:"):
            await self.force_remove_menu(q, int(data.split(":")[1]))
            return

        if data.startswith("forcedel:"):
            parts = data.split(":", 2)
            await db.bots.update_one(
                {"bot_id": int(parts[1])},
                {"$pull": {"force_join_channels": "@" + parts[2]}},
            )
            await self.force_menu(q, int(parts[1]))
            return

        if data.startswith("broadcast:"):
            bid = int(data.split(":")[1])
            context.user_data["state"] = "broadcast_one"
            context.user_data["broadcast_bot_id"] = bid
            await q.edit_message_text("📣 Send the message/media to broadcast to this bot's users.")
            return

        if data.startswith("creation:"):
            value = data.split(":")[1] == "on"
            await db.set_system_setting("bot_creation_enabled", value)
            await q.edit_message_text(
                f"⚙️ Bot creation is now {'🟢 ENABLED' if value else '🔴 DISABLED'}."
            )
            return

        if data.startswith("ownerstats:"):
            bid = int(data.split(":")[1])
            bot = await db.get_bot(bid)
            if not bot or bot.get("owner_id") != uid:
                await q.answer("⛔ Not your bot.", show_alert=True)
                return
            s = await db.get_bot_stats(bid)
            await q.edit_message_text(
                f"📊 @{bot.get('username','N/A')}\n\n"
                f"👥 Users: {s.get('total_users',0)}\n"
                f"📥 Downloads: {s.get('total_downloads',0)}\n"
                f"🎬 Videos: {s.get('videos',0)}\n"
                f"🎵 Audio: {s.get('audio',0)}"
            )
            return

    async def error_handler(self, update, context):
        logger.exception("Main bot error: %s", context.error)


# main.py imports MainSaaSBot from this module.

# Backward-compatible singleton expected by main.py
main_bot = MainSaaSBot()
