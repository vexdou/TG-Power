import asyncio
import logging
import os
import re
import tempfile
import time
from datetime import datetime, timezone

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
from force_join import force_join_checker

logger = logging.getLogger(__name__)

LANGUAGES = {
    "en": "English 🇬🇧",
    "so": "Soomaali 🇸🇴",
    "ar": "العربية 🇸🇦",
    "es": "Español 🇪🇸",
}

ADMIN_BUTTONS = [
    "📊 Dashboard", "🤖 All Bots", "🔎 Search Bot", "👥 Users",
    "👥 Bot Users", "👑 Bot Owners", "📥 Downloads", "📈 Download Stats",
    "❌ Failed Downloads", "🕘 Recent Downloads", "📢 Broadcast All", "📣 Broadcast Bot",
    "👀 Broadcast Preview", "🔐 Force Join", "🔎 Force Join Check", "⚙️ Bot Creation",
    "▶️ Start Bot", "⏹ Stop Bot", "🔄 Restart Bot", "🗑 Delete Bot",
    "❤️ Bot Health", "🚨 Bot Errors", "♻️ Reload Bots", "🛠 Maintenance",
    "🧰 System Settings", "⏱ Max Video", "📦 Max File", "🌐 Default Language",
    "📋 User Export", "🤖 Bot Export", "🧹 Clear Downloads", "🧽 Clear Pending",
    "🧼 Cleanup Temp", "🗄 Database Status", "📡 Queue Status", "⏲ Uptime",
    "🔒 Security", "🧑‍💼 Admin ID", "📊 Platform Stats", "🔄 Reset Settings",
    "📜 Activity Log", "💾 Backup Info", "📦 Bot Capacity", "🔔 Notifications",
    "ℹ️ About", "❓ Help", "🔃 Refresh", "🔙 User Panel",
    "🧪 Test System", "📍 Channel Settings",
]


def admin_ids():
    ids = set()
    try:
        if Config.OWNER_ID:
            ids.add(int(Config.OWNER_ID))
    except (TypeError, ValueError):
        pass
    for value in getattr(Config, "ADMIN_IDS", []):
        try:
            ids.add(int(value))
        except (TypeError, ValueError):
            pass
    return ids


def is_admin(user_id: int) -> bool:
    return int(user_id) in admin_ids()


def main_keyboard(user_id=None):
    request_id = int(time.time() * 1000) % 2147483647
    try:
        create_button = KeyboardButton(
            text="➕ Create New Bot",
            request_managed_bot=KeyboardButtonRequestManagedBot(
                request_id=request_id,
                suggested_name="My Downloader Bot",
                suggested_username="MyDownloaderBot",
            ),
        )
    except TypeError:
        create_button = KeyboardButton("➕ Create New Bot")

    rows = [
        [create_button],
        [KeyboardButton("🤖 My Bots"), KeyboardButton("🌐 Language")],
        [KeyboardButton("ℹ️ Help")],
    ]
    if user_id is not None and is_admin(user_id):
        rows.append([KeyboardButton("👑 Admin Panel")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, is_persistent=True)


def admin_keyboard():
    rows = []
    for i in range(0, len(ADMIN_BUTTONS), 2):
        rows.append([KeyboardButton(ADMIN_BUTTONS[i]), KeyboardButton(ADMIN_BUTTONS[i + 1])])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, is_persistent=True)


def language_keyboard():
    keys = list(LANGUAGES)
    rows = []
    for i in range(0, len(keys), 2):
        row = [InlineKeyboardButton(LANGUAGES[keys[i]], callback_data=f"lang_{keys[i]}")]
        if i + 1 < len(keys):
            row.append(InlineKeyboardButton(LANGUAGES[keys[i + 1]], callback_data=f"lang_{keys[i + 1]}"))
        rows.append(row)
    return InlineKeyboardMarkup(rows)


class MainSaaSBot:
    def __init__(self):
        self.started_at = None
        self.app = Application.builder().token(Config.BOT_TOKEN).build()
        self._setup_handlers()

    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("admin", self.admin_command))
        self.app.add_handler(CommandHandler("id", self.id_command))
        self.app.add_handler(CommandHandler("language", self.language_command))
        self.app.add_handler(
            MessageHandler(filters.StatusUpdate.MANAGED_BOT_CREATED, self.handle_managed_bot_created)
        )
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        self.app.add_handler(
            MessageHandler(
                (filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.AUDIO | filters.VOICE | filters.ANIMATION),
                self.handle_admin_media,
            )
        )
        self.app.add_error_handler(self.error_handler)

    async def start_controller(self):
        if self.app.running:
            return
        try:
            await self.app.initialize()
            await force_join_checker.start()
            await self.app.bot.delete_webhook(drop_pending_updates=True)
            await self.app.start()
            if self.app.updater is None:
                raise RuntimeError("Telegram updater is not available.")
            await self.app.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES,
                poll_interval=1.0,
                timeout=30,
            )
            me = await self.app.bot.get_me()
            self.started_at = datetime.now(timezone.utc)
            logger.info("👑 Main SaaS Bot Online: @%s", me.username)
        except Exception:
            logger.exception("🔴 Main SaaS Controller failed to start.")
            try:
                if self.app.updater and self.app.updater.running:
                    await self.app.updater.stop()
            except Exception:
                pass
            try:
                if self.app.running:
                    await self.app.stop()
            except Exception:
                pass
            try:
                await force_join_checker.stop()
            except Exception:
                pass
            try:
                await self.app.shutdown()
            except Exception:
                pass
            raise

    async def stop_controller(self):
        try:
            if self.app.updater and self.app.updater.running:
                await self.app.updater.stop()
            if self.app.running:
                await self.app.stop()
            await force_join_checker.stop()
            await self.app.shutdown()
        except Exception:
            logger.exception("Main controller shutdown error")

    async def id_command(self, update, context):
        if update.effective_user and update.message:
            await update.message.reply_text(
                f"🆔 Your Telegram ID:\n\n{update.effective_user.id}\n\n"
                "Set this number in Render as OWNER_ID."
            )

    async def language_command(self, update, context):
        if update.message:
            await update.message.reply_text(
                "🌐 Choose your language / Dooro luuqadda:",
                reply_markup=language_keyboard(),
            )

    async def start_command(self, update, context):
        if not update.effective_user or not update.message:
            return
        user = update.effective_user
        await db.save_main_user(user.id, user.username or "", user.full_name or "")
        await update.message.reply_text(
            "🤖 TG-Power — Downloader Bot Builder\n\n"
            f"👋 Welcome, {user.first_name or 'User'}!\n\n"
            "This main bot creates ready-to-use video downloader bots.\n\n"
            "Your created bots can download supported videos from:\n"
            "• TikTok\n• Facebook\n• YouTube (up to 10 minutes)\n"
            "• Pinterest\n• Instagram\n• Snapchat\n• X/Twitter\n\n"
            "🎵 Every downloaded video has a MUSIC button to convert it to MP3.\n"
            "📢 MP3 files receive a CHANNEL button.\n\n"
            "➕ Create New Bot — create your own downloader bot\n"
            "🤖 My Bots — manage your bots\n"
            "🌐 Language — choose your language\n\n"
            "If you are an administrator, use the 👑 Admin Panel button below.",
            reply_markup=main_keyboard(user.id),
        )

    async def admin_command(self, update, context):
        if not update.effective_user or not update.message:
            return
        if not is_admin(update.effective_user.id):
            await update.message.reply_text(
                "⛔ You are not authorized.\n\n"
                f"Your ID: {update.effective_user.id}\n"
                "Add this ID to Render OWNER_ID or ADMIN_IDS."
            )
            return
        await self.show_dashboard(update)

    async def show_dashboard(self, update):
        stats = await db.get_global_stats()
        maintenance = await db.get_system_setting("maintenance_mode", False)
        creation = await db.is_bot_creation_enabled()
        force = await db.get_global_force_join_channels()
        await update.message.reply_text(
            "👑 MAIN ADMIN CONTROL CENTER\n\n"
            f"👤 Main users: {stats['users']}\n"
            f"🤖 All bots: {stats['bots']}\n"
            f"🟢 Active bots: {stats['active_bots']}\n"
            f"🔴 Failed bots: {stats['failed_bots']}\n"
            f"👥 Bot users: {stats['bot_users']}\n"
            f"📥 Downloads: {stats['downloads']}\n"
            f"🔐 Force Join: {len(force)}/5 channels\n"
            f"🤖 Bot creation: {'ON' if creation else 'OFF'}\n"
            f"🛠 Maintenance: {'ON' if maintenance else 'OFF'}\n\n"
            "Choose any control below. This panel controls the whole SaaS platform.",
            reply_markup=admin_keyboard(),
        )

    async def show_all_bots(self, update):
        bots = await db.get_all_bots()
        if not bots:
            await update.message.reply_text("🤖 No managed bots yet.", reply_markup=admin_keyboard())
            return
        lines = ["🤖 ALL MANAGED BOTS\n"]
        buttons = []
        for bot in bots:
            bid = bot.get("bot_id")
            username = bot.get("username") or "N/A"
            status = bot.get("status", "unknown")
            icon = "🟢" if status == "active" else ("🔴" if status == "failed" else "🟡")
            lines.append(f"{icon} @{username} | {status} | ID {bid}")
            buttons.append([
                InlineKeyboardButton(f"⚙️ @{username}", callback_data=f"manage:{bid}"),
                InlineKeyboardButton("📊 Stats", callback_data=f"bstats:{bid}"),
            ])
        await update.message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons))

    async def show_all_bots_from_callback(self, query):
        bots = await db.get_all_bots()
        buttons = []
        for bot in bots:
            bid = bot["bot_id"]
            username = bot.get("username") or "N/A"
            buttons.append([
                InlineKeyboardButton(f"⚙️ @{username}", callback_data=f"manage:{bid}"),
                InlineKeyboardButton("📊 Stats", callback_data=f"bstats:{bid}"),
            ])
        await query.edit_message_text(
            "🤖 ALL MANAGED BOTS",
            reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
        )

    async def choose_bot(self, update, mode):
        bots = await db.get_all_bots()
        if not bots:
            await update.message.reply_text("🤖 No managed bots.", reply_markup=admin_keyboard())
            return
        buttons = []
        for bot in bots:
            bid = bot.get("bot_id")
            username = bot.get("username") or "N/A"
            buttons.append([InlineKeyboardButton(f"@{username}", callback_data=f"{mode}:{bid}")])
        await update.message.reply_text("Choose a bot:", reply_markup=InlineKeyboardMarkup(buttons))

    async def show_users(self, update):
        stats = await db.get_global_stats()
        await update.message.reply_text(
            "👥 USERS CENTER\n\n"
            f"👤 Main-controller users: {stats['users']}\n"
            f"👥 All managed-bot users: {stats['bot_users']}",
            reply_markup=admin_keyboard(),
        )

    async def show_bot_users(self, update):
        await self.choose_bot(update, "bu")

    async def show_bot_users_for(self, query, bot_id):
        users = await db.get_all_bot_users(bot_id)
        bot = await db.get_bot(bot_id)
        username = (bot or {}).get("username", "N/A")
        text = f"👥 USERS OF @{username}\n\nTotal: {len(users)}\n\n"
        for user in users[:100]:
            text += f"• {user.get('first_name') or user.get('username') or user.get('user_id')} — {user.get('user_id')}\n"
        await query.edit_message_text(text[:4000], reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 All Bots", callback_data="allbots")]
        ]))

    async def show_downloads(self, update):
        total = await db.count_downloads()
        success = await db.count_successful_downloads()
        failed = await db.downloads.count_documents({"status": "failed"})
        await update.message.reply_text(
            f"📥 DOWNLOADS\n\nTotal: {total}\n🟢 Success: {success}\n🔴 Failed: {failed}",
            reply_markup=admin_keyboard(),
        )

    async def show_download_stats(self, update):
        total = await db.count_downloads()
        video = await db.downloads.count_documents({"media_type": "video", "status": "success"})
        audio = await db.downloads.count_documents({"media_type": "audio", "status": "success"})
        photo = await db.downloads.count_documents({"media_type": "photo", "status": "success"})
        await update.message.reply_text(
            f"📈 DOWNLOAD STATISTICS\n\n📥 Total: {total}\n🎬 Videos: {video}\n🎵 Audio: {audio}\n🖼 Photos: {photo}",
            reply_markup=admin_keyboard(),
        )

    async def show_health(self, update):
        bots = await db.get_all_bots()
        running = len(bot_manager.running_bots)
        await update.message.reply_text(
            "❤️ SYSTEM HEALTH\n\n"
            f"DB records: {len(bots)}\n"
            f"Running in memory: {running}\n"
            f"Starting: {len(bot_manager.starting_bots)}\n"
            f"MongoDB: {'🟢 connected' if db.db is not None else '🔴 disconnected'}",
            reply_markup=admin_keyboard(),
        )

    async def system_settings(self, update):
        maintenance = await db.get_system_setting("maintenance_mode", False)
        creation = await db.is_bot_creation_enabled()
        force = await db.get_global_force_join_channels()
        await update.message.reply_text(
            "🧰 SYSTEM SETTINGS\n\n"
            f"Bot creation: {'🟢 ON' if creation else '🔴 OFF'}\n"
            f"Maintenance: {'🟢 ON' if maintenance else '🔴 OFF'}\n"
            f"Max video: {Config.MAX_VIDEO_DURATION_SECONDS // 60} minutes\n"
            f"Max file: {Config.MAX_FILE_SIZE_MB} MB\n"
            f"Global force join: {len(force)}/5",
            reply_markup=admin_keyboard(),
        )

    async def creation_setting(self, update):
        enabled = await db.is_bot_creation_enabled()
        await update.message.reply_text(
            f"⚙️ BOT CREATION\n\nCurrent: {'🟢 ENABLED' if enabled else '🔴 DISABLED'}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🟢 Enable", callback_data="setting:creation:on"),
                InlineKeyboardButton("🔴 Disable", callback_data="setting:creation:off"),
            ]]),
        )

    async def maintenance_setting(self, update):
        enabled = await db.get_system_setting("maintenance_mode", False)
        await update.message.reply_text(
            f"🛠 MAINTENANCE MODE\n\nCurrent: {'🟢 ON' if enabled else '🔴 OFF'}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🟢 Turn ON", callback_data="setting:maintenance:on"),
                InlineKeyboardButton("🔴 Turn OFF", callback_data="setting:maintenance:off"),
            ]]),
        )

    async def force_join_menu(self, update):
        channels = await db.get_global_force_join_channels()
        text = "🔐 GLOBAL FORCE JOIN\n\nThis list applies to EVERY managed bot.\nMaximum: 5 channels.\n\n"
        text += "\n".join(f"{i+1}. {c}" for i, c in enumerate(channels)) if channels else "No channels configured."
        rows = []
        rows.append([InlineKeyboardButton("🔎 Verify Main Bot Admin Access", callback_data="fj:verify")])
        if len(channels) < 5:
            rows.append([InlineKeyboardButton("➕ Add Channel", callback_data="fj:add")])
        for i, channel in enumerate(channels):
            rows.append([InlineKeyboardButton(f"🗑 Remove {i+1}: {channel}", callback_data=f"fj:del:{i}")])
        if channels:
            rows.append([InlineKeyboardButton("🧹 Remove ALL", callback_data="fj:clear")])
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(rows) if rows else None)

    async def verify_force_join_channels(self, update):
        channels = await db.get_global_force_join_channels()
        if not channels:
            await update.message.reply_text("🔐 No Force Join channels configured.", reply_markup=admin_keyboard())
            return
        results = await force_join_checker.verify_admin_channels(channels)
        lines = ["🔎 MAIN BOT FORCE-JOIN CHECK\n"]
        for row in results:
            icon = "🟢" if row["ok"] else "🔴"
            lines.append(f"{icon} {row['channel']} — {row['status']}")
            if row.get("error"):
                lines.append(f"   {row['error']}")
        lines.append("\nOnly the MAIN bot needs to be admin in these channels. Managed downloader bots do not.")
        await update.message.reply_text("\n".join(lines)[:4000], reply_markup=admin_keyboard())

    async def save_force_join_channel(self, update, context):
        value = (update.message.text or "").strip()
        context.user_data.clear()
        if not value:
            await update.message.reply_text("❌ Send a channel username such as @MyChannel.", reply_markup=admin_keyboard())
            return

        # The MAIN bot must be an administrator/owner before the channel can be enabled.
        verification = await force_join_checker.verify_admin_channels([value])
        if not verification or not verification[0]["ok"]:
            error = (verification[0].get("error") if verification else None) or "Main bot cannot access this channel."
            await update.message.reply_text(
                "❌ Channel was NOT added.\n\n"
                "Make the MAIN bot an administrator in the channel first.\n"
                f"Details: {error}",
                reply_markup=admin_keyboard(),
            )
            return

        ok, channels = await db.add_global_force_join_channel(value)
        if not ok:
            await update.message.reply_text(
                "❌ Channel was not added. It may already exist or the 5-channel limit was reached.",
                reply_markup=admin_keyboard(),
            )
            return
        await update.message.reply_text(
            "✅ Channel added to GLOBAL Force Join.\n\n"
            "Only the MAIN bot checks membership. Managed downloader bots do NOT need channel admin rights.\n"
            f"Configured channels: {len(channels)}/5",
            reply_markup=admin_keyboard(),
        )

    async def save_max_video(self, update, context):
        value = (update.message.text or "").strip()
        try:
            minutes = int(value)
            if minutes < 1 or minutes > 120:
                raise ValueError
            # Config is loaded at process start, but downloader reads this value dynamically.
            Config.MAX_VIDEO_DURATION_SECONDS = minutes * 60
            context.user_data.clear()
            await update.message.reply_text(f"✅ Max video duration set to {minutes} minutes.", reply_markup=admin_keyboard())
        except ValueError:
            await update.message.reply_text("❌ Send a number from 1 to 120.")

    async def save_max_file(self, update, context):
        value = (update.message.text or "").strip()
        try:
            mb = int(value)
            if mb < 5 or mb > 2000:
                raise ValueError
            Config.MAX_FILE_SIZE_MB = mb
            context.user_data.clear()
            await update.message.reply_text(f"✅ Max file size set to {mb} MB.", reply_markup=admin_keyboard())
        except ValueError:
            await update.message.reply_text("❌ Send a number from 5 to 2000.")

    async def search_bot_prompt(self, update, context):
        context.user_data["state"] = "search_bot"
        await update.message.reply_text("🔎 Send bot username or bot ID:")

    async def search_bot(self, update, context):
        results = await db.search_bots(update.message.text or "")
        context.user_data.clear()
        if not results:
            await update.message.reply_text("❌ No bot found.", reply_markup=admin_keyboard())
            return
        buttons = []
        text = "🔎 SEARCH RESULTS\n\n"
        for bot in results[:30]:
            bid = bot["bot_id"]
            name = bot.get("username") or "N/A"
            text += f"@{name} — {bot.get('status')}\n"
            buttons.append([InlineKeyboardButton(f"⚙️ @{name}", callback_data=f"manage:{bid}")])
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    async def bot_errors(self, update):
        bots = await db.get_all_bots()
        lines = ["🚨 BOT ERRORS\n"]
        for bot in bots:
            if bot.get("last_error"):
                lines.append(f"@{bot.get('username','N/A')}: {bot['last_error']}")
        if len(lines) == 1:
            lines.append("No saved bot errors.")
        await update.message.reply_text("\n".join(lines)[:4000], reply_markup=admin_keyboard())

    async def user_export(self, update):
        users = await db.get_all_main_users()
        text = "USER_ID,USERNAME,FULL_NAME\n"
        for user in users:
            text += f"{user.get('user_id')},{user.get('username','')},{str(user.get('full_name','')).replace(',',' ')}\n"
        if len(text) > 3900:
            text = text[:3900] + "\n..."
        await update.message.reply_text("📋 USER EXPORT\n\n" + text, reply_markup=admin_keyboard())

    async def clear_downloads(self, update):
        await update.message.reply_text(
            "⚠️ Delete ALL download history?",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="noop"),
                InlineKeyboardButton("🗑 YES, CLEAR", callback_data="clear:downloads"),
            ]]),
        )

    async def clear_pending(self, update):
        await update.message.reply_text(
            "⚠️ Clear all pending force-join downloads?",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="noop"),
                InlineKeyboardButton("🧹 CLEAR", callback_data="clear:pending"),
            ]]),
        )

    async def reload_bots(self, update):
        await update.message.reply_text("♻️ Reloading active managed bots...")
        await bot_manager.stop_all()
        await bot_manager.load_and_start_all()
        await update.message.reply_text("✅ Managed bots reloaded.", reply_markup=admin_keyboard())

    async def perform_broadcast(self, message, context, bot_id=None):
        bots = await db.get_all_bots() if bot_id is None else [await db.get_bot(bot_id)]
        bots = [b for b in bots if b]
        sent = failed = skipped = 0
        media_path = None
        media_kind = None
        caption = message.caption or ""

        try:
            if message.photo:
                media_kind = "photo"
                media_path = tempfile.mktemp(suffix=".jpg")
                f = await message.photo[-1].get_file()
                await f.download_to_drive(media_path)
            elif message.video:
                media_kind = "video"
                media_path = tempfile.mktemp(suffix=".mp4")
                f = await message.video.get_file()
                await f.download_to_drive(media_path)
            elif message.document:
                media_kind = "document"
                media_path = tempfile.mktemp()
                f = await message.document.get_file()
                await f.download_to_drive(media_path)
            elif message.audio:
                media_kind = "audio"
                media_path = tempfile.mktemp(suffix=".mp3")
                f = await message.audio.get_file()
                await f.download_to_drive(media_path)
            elif message.voice:
                media_kind = "voice"
                media_path = tempfile.mktemp(suffix=".ogg")
                f = await message.voice.get_file()
                await f.download_to_drive(media_path)
            elif message.animation:
                media_kind = "animation"
                media_path = tempfile.mktemp(suffix=".mp4")
                f = await message.animation.get_file()
                await f.download_to_drive(media_path)

            for bot in bots:
                bid = bot["bot_id"]
                handler = bot_manager.running_bots.get(bid)
                if not handler:
                    skipped += 1
                    continue
                users = await db.get_all_bot_users(bid)
                for user in users:
                    uid = user.get("user_id")
                    if not uid:
                        continue
                    try:
                        if media_kind == "photo":
                            with open(media_path, "rb") as f:
                                await handler.app.bot.send_photo(uid, photo=f, caption=caption or None)
                        elif media_kind == "video":
                            with open(media_path, "rb") as f:
                                await handler.app.bot.send_video(uid, video=f, caption=caption or None)
                        elif media_kind == "document":
                            with open(media_path, "rb") as f:
                                await handler.app.bot.send_document(uid, document=f, caption=caption or None)
                        elif media_kind == "audio":
                            with open(media_path, "rb") as f:
                                await handler.app.bot.send_audio(uid, audio=f, caption=caption or None)
                        elif media_kind == "voice":
                            with open(media_path, "rb") as f:
                                await handler.app.bot.send_voice(uid, voice=f, caption=caption or None)
                        elif media_kind == "animation":
                            with open(media_path, "rb") as f:
                                await handler.app.bot.send_animation(uid, animation=f, caption=caption or None)
                        else:
                            await handler.app.bot.send_message(uid, text=message.text or message.caption or "")
                        sent += 1
                    except (Forbidden, TelegramError):
                        failed += 1
                    except Exception:
                        failed += 1
                    await asyncio.sleep(0.05)

            context.user_data.clear()
            await message.reply_text(
                f"📢 Broadcast finished.\n🟢 Sent: {sent}\n🔴 Failed: {failed}\n🟡 Offline bots skipped: {skipped}",
                reply_markup=admin_keyboard(),
            )
        finally:
            if media_path:
                try:
                    os.remove(media_path)
                except OSError:
                    pass

    async def handle_admin_media(self, update, context):
        if not update.effective_user or not is_admin(update.effective_user.id) or not update.message:
            return
        state = context.user_data.get("state")
        if state == "broadcast_all":
            await self.perform_broadcast(update.message, context)
        elif state == "broadcast_bot":
            await self.perform_broadcast(update.message, context, context.user_data.get("broadcast_bot_id"))

    async def broadcast_all_prompt(self, update, context):
        context.user_data["state"] = "broadcast_all"
        await update.message.reply_text("📢 Send the text, photo, video, audio, document or voice you want to broadcast to ALL active managed bots.")

    async def broadcast_bot_prompt(self, update):
        await self.choose_bot(update, "broadcast")

    async def manage_bot_menu(self, query, bot_id):
        bot = await db.get_bot(bot_id)
        if not bot:
            await query.edit_message_text("❌ Bot not found.")
            return
        status = bot.get("status", "unknown")
        toggle = InlineKeyboardButton(
            "⏹ Stop", callback_data=f"stop:{bot_id}"
        ) if status == "active" else InlineKeyboardButton(
            "▶️ Start", callback_data=f"start:{bot_id}"
        )
        await query.edit_message_text(
            f"⚙️ BOT MANAGEMENT\n\n@{bot.get('username','N/A')}\nID: {bot_id}\nStatus: {status}",
            reply_markup=InlineKeyboardMarkup([
                [toggle, InlineKeyboardButton("🔄 Restart", callback_data=f"restart:{bot_id}")],
                [InlineKeyboardButton("📊 Stats", callback_data=f"bstats:{bot_id}")],
                [InlineKeyboardButton("👥 Users", callback_data=f"bu:{bot_id}")],
                [InlineKeyboardButton("🗑 Delete", callback_data=f"confirmdel:{bot_id}")],
                [InlineKeyboardButton("🔙 All Bots", callback_data="allbots")],
            ]),
        )

    async def show_bot_stats(self, query, bot_id):
        bot = await db.get_bot(bot_id)
        if not bot:
            await query.edit_message_text("❌ Bot not found.")
            return
        stats = await db.get_bot_stats(bot_id)
        await query.edit_message_text(
            f"📊 BOT STATISTICS\n\n@{bot.get('username','N/A')}\n"
            f"🟢 {bot.get('status')}\n👤 Owner: {bot.get('owner_id')}\n\n"
            f"👥 Users: {stats['total_users']}\n📥 Downloads: {stats['total_downloads']}\n"
            f"🎬 Videos: {stats['videos']}\n🎵 Audio: {stats['audio']}\n🖼 Photos: {stats['photos']}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 All Bots", callback_data="allbots")]]),
        )

    async def start_managed_bot(self, query, bot_id):
        bot = await db.get_bot(bot_id)
        if not bot:
            await query.answer("Bot not found", show_alert=True)
            return
        ok = await bot_manager.start_bot_instance(bot_id, bot.get("token"))
        await query.answer("🟢 Started" if ok else "🔴 Start failed", show_alert=not ok)
        await self.manage_bot_menu(query, bot_id)

    async def stop_managed_bot(self, query, bot_id):
        await bot_manager.stop_bot_instance(bot_id)
        await db.update_bot_status(bot_id, "stopped")
        await query.answer("⏹ Stopped")
        await self.manage_bot_menu(query, bot_id)

    async def restart_managed_bot(self, query, bot_id):
        bot = await db.get_bot(bot_id)
        if not bot:
            await query.answer("Bot not found", show_alert=True)
            return
        await bot_manager.stop_bot_instance(bot_id)
        ok = await bot_manager.start_bot_instance(bot_id, bot.get("token"))
        await query.answer("🔄 Restarted" if ok else "🔴 Restart failed", show_alert=not ok)
        await self.manage_bot_menu(query, bot_id)

    async def delete_managed_bot(self, query, bot_id):
        await bot_manager.stop_bot_instance(bot_id)
        await db.delete_bot(bot_id)
        await query.edit_message_text("🗑 Bot deleted successfully.")

    async def handle_text(self, update, context):
        if not update.message or not update.effective_user:
            return
        uid = update.effective_user.id
        text = update.message.text or ""
        state = context.user_data.get("state")

        if is_admin(uid):
            if state == "force_add":
                await self.save_force_join_channel(update, context)
                return
            if state == "broadcast_all":
                await self.perform_broadcast(update.message, context)
                return
            if state == "broadcast_bot":
                await self.perform_broadcast(update.message, context, context.user_data.get("broadcast_bot_id"))
                return
            if state == "broadcast_preview":
                await update.message.reply_text("👀 BROADCAST PREVIEW\n\n" + ((update.message.text or update.message.caption or "").strip() or "[media message]"), reply_markup=admin_keyboard())
                context.user_data.clear()
                return
            if state == "search_bot":
                await self.search_bot(update, context)
                return
            if state == "max_video":
                await self.save_max_video(update, context)
                return
            if state == "max_file":
                await self.save_max_file(update, context)
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
                "➕ Create New Bot — create a downloader bot.\n"
                "🤖 My Bots — see your bots.\n"
                "Send a video link to a created bot to download it.\n"
                "The downloaded video has a MUSIC button.\n"
                "MUSIC creates MP3 and adds CHANNEL.\n"
                "Admins can control the entire platform from 👑 Admin Panel."
            )
            return

        if not is_admin(uid):
            return

        actions = {
            "📊 Dashboard": lambda: self.show_dashboard(update),
            "🤖 All Bots": lambda: self.show_all_bots(update),
            "🔎 Search Bot": lambda: self.search_bot_prompt(update, context),
            "👥 Users": lambda: self.show_users(update),
            "👥 Bot Users": lambda: self.show_bot_users(update),
            "👑 Bot Owners": lambda: self.show_bot_owners(update),
            "📥 Downloads": lambda: self.show_downloads(update),
            "📈 Download Stats": lambda: self.show_download_stats(update),
            "❌ Failed Downloads": lambda: self.show_failed_downloads(update),
            "🕘 Recent Downloads": lambda: self.show_recent_downloads(update),
            "📢 Broadcast All": lambda: self.broadcast_all_prompt(update, context),
            "📣 Broadcast Bot": lambda: self.broadcast_bot_prompt(update),
            "👀 Broadcast Preview": lambda: self.broadcast_preview(update, context),
            "🔐 Force Join": lambda: self.force_join_menu(update),
            "🔎 Force Join Check": lambda: self.verify_force_join_channels(update),
            "⚙️ Bot Creation": lambda: self.creation_setting(update),
            "▶️ Start Bot": lambda: self.choose_bot(update, "start"),
            "⏹ Stop Bot": lambda: self.choose_bot(update, "stop"),
            "🔄 Restart Bot": lambda: self.choose_bot(update, "restart"),
            "🗑 Delete Bot": lambda: self.choose_bot(update, "confirmdel"),
            "❤️ Bot Health": lambda: self.show_health(update),
            "🧰 System Settings": lambda: self.system_settings(update),
            "⏱ Max Video": lambda: self._prompt_simple(update, context, "max_video", "Send maximum video duration in minutes (1–120):"),
            "📦 Max File": lambda: self._prompt_simple(update, context, "max_file", "Send maximum file size in MB (5–2000):"),
            "🛠 Maintenance": lambda: self.maintenance_setting(update),
            "♻️ Reload Bots": lambda: self.reload_bots(update),
            "🚨 Bot Errors": lambda: self.bot_errors(update),
            "📋 User Export": lambda: self.user_export(update),
            "🤖 Bot Export": lambda: self.bot_export(update),
            "🧼 Cleanup Temp": lambda: self.cleanup_temp(update),
            "🗄 Database Status": lambda: self.database_status(update),
            "📡 Queue Status": lambda: self.queue_status(update),
            "⏲ Uptime": lambda: self.uptime_status(update),
            "🔒 Security": lambda: self.security_status(update),
            "🧑‍💼 Admin ID": lambda: self.admin_id_status(update),
            "📊 Platform Stats": lambda: self.platform_stats(update),
            "🔄 Reset Settings": lambda: self.reset_settings(update),
            "📜 Activity Log": lambda: self.activity_log(update),
            "💾 Backup Info": lambda: self.backup_info(update),
            "📦 Bot Capacity": lambda: self.bot_capacity(update),
            "🔔 Notifications": lambda: self.notifications_status(update),
            "🧹 Clear Downloads": lambda: self.clear_downloads(update),
            "🧽 Clear Pending": lambda: self.clear_pending(update),
            "🌐 Default Language": lambda: self.language_command(update, context),
            "🌐 Language": lambda: self.language_command(update, context),
            "ℹ️ About": lambda: update.message.reply_text("ℹ️ TG-Power SaaS Admin Panel — global control for bots, users, downloads, force join and platform settings.", reply_markup=admin_keyboard()),
            "❓ Help": lambda: update.message.reply_text("❓ Use the 30-button admin panel to manage every part of the platform.", reply_markup=admin_keyboard()),
            "🔃 Refresh": lambda: self.show_dashboard(update),
            "🔙 User Panel": lambda: update.message.reply_text("👤 User Panel", reply_markup=main_keyboard(uid)),
            "🧪 Test System": lambda: self.show_health(update),
            "📍 Channel Settings": lambda: update.message.reply_text("📍 CHANNEL SETTINGS\n\nMP3 files use the CHANNEL button to open: https://t.me/downloadermain\n\nForce Join channels are managed separately under 🔐 Force Join.", reply_markup=admin_keyboard()),
        }
        action = actions.get(text)
        if action:
            await action()

    async def show_bot_owners(self, update):
        bots = await db.get_all_bots()
        owners = {}
        for bot in bots:
            owners.setdefault(bot.get("owner_id"), 0)
            owners[bot.get("owner_id")] += 1
        lines = ["👑 BOT OWNERS\n"] + [f"• {owner}: {count} bot(s)" for owner, count in owners.items()]
        await update.message.reply_text("\n".join(lines)[:4000], reply_markup=admin_keyboard())

    async def show_failed_downloads(self, update):
        rows = await db.downloads.find({"status": "failed"}).sort("created_at", -1).to_list(length=30)
        lines = ["❌ FAILED DOWNLOADS\n"]
        for row in rows:
            lines.append(f"• bot={row.get('bot_id')} user={row.get('user_id')}\n  {row.get('url','')}")
        if len(lines) == 1:
            lines.append("No failed downloads.")
        await update.message.reply_text("\n".join(lines)[:4000], reply_markup=admin_keyboard())

    async def show_recent_downloads(self, update):
        rows = await db.downloads.find({}).sort("created_at", -1).to_list(length=30)
        lines = ["🕘 RECENT DOWNLOADS\n"]
        for row in rows:
            lines.append(f"• {row.get('media_type','video')} | bot={row.get('bot_id')} | user={row.get('user_id')} | {row.get('status')}")
        if len(lines) == 1:
            lines.append("No downloads yet.")
        await update.message.reply_text("\n".join(lines)[:4000], reply_markup=admin_keyboard())

    async def broadcast_preview(self, update, context):
        context.user_data["state"] = "broadcast_preview"
        await update.message.reply_text("👀 Send the text/media and I will show you the broadcast preview without sending it.")

    async def bot_export(self, update):
        bots = await db.get_all_bots()
        text = "BOT_ID,USERNAME,OWNER_ID,STATUS\n"
        for b in bots:
            text += f"{b.get('bot_id')},{b.get('username','')},{b.get('owner_id')},{b.get('status','')}\n"
        await update.message.reply_text("🤖 BOT EXPORT\n\n" + text[:3800], reply_markup=admin_keyboard())

    async def cleanup_temp(self, update):
        removed = 0
        root = Config.DOWNLOAD_DIR
        if os.path.isdir(root):
            for name in os.listdir(root):
                path = os.path.join(root, name)
                try:
                    if os.path.isfile(path):
                        os.remove(path); removed += 1
                except OSError:
                    pass
        await update.message.reply_text(f"🧼 Temporary download cleanup complete. Removed: {removed}", reply_markup=admin_keyboard())

    async def database_status(self, update):
        try:
            await db.client.admin.command("ping")
            text = "🟢 MongoDB connected"
        except Exception as exc:
            text = f"🔴 MongoDB error: {exc}"
        await update.message.reply_text(f"🗄 DATABASE STATUS\n\n{text}", reply_markup=admin_keyboard())

    async def queue_status(self, update):
        pending = await db.pending_downloads.count_documents({})
        starting = len(bot_manager.starting_bots)
        running = len(bot_manager.running_bots)
        await update.message.reply_text(f"📡 QUEUE STATUS\n\nPending Force Join: {pending}\nStarting bots: {starting}\nRunning bots: {running}", reply_markup=admin_keyboard())

    async def uptime_status(self, update):
        started = getattr(self, "started_at", None)
        value = "unknown" if not started else str(datetime.now(timezone.utc) - started).split('.')[0]
        await update.message.reply_text(f"⏲ PLATFORM UPTIME\n\n{value}", reply_markup=admin_keyboard())

    async def security_status(self, update):
        await update.message.reply_text("🔒 SECURITY\n\n• Admin access uses OWNER_ID + ADMIN_IDS\n• Force Join is checked by the MAIN bot token\n• Managed bots do not need channel admin rights\n• Bot tokens are stored server-side and never shown to users.", reply_markup=admin_keyboard())

    async def admin_id_status(self, update):
        await update.message.reply_text(f"🧑‍💼 ADMIN IDS\n\nOWNER_ID: {Config.OWNER_ID}\nADMIN_IDS: {', '.join(map(str, Config.ADMIN_IDS)) or 'none'}", reply_markup=admin_keyboard())

    async def platform_stats(self, update):
        stats = await db.get_global_stats()
        await update.message.reply_text("📊 PLATFORM STATS\n\n" + "\n".join(f"{k}: {v}" for k,v in stats.items()), reply_markup=admin_keyboard())

    async def reset_settings(self, update):
        for key in ["maintenance_mode", "bot_creation_enabled", "global_force_join_channels"]:
            await db.delete_system_setting(key)
        await update.message.reply_text("🔄 Global settings reset to defaults. Force Join is now empty and bot creation is enabled by default.", reply_markup=admin_keyboard())

    async def activity_log(self, update):
        await update.message.reply_text("📜 ACTIVITY LOG\n\nUse Render logs for live process logs. MongoDB stores bot/download status and errors.", reply_markup=admin_keyboard())

    async def backup_info(self, update):
        await update.message.reply_text("💾 BACKUP INFO\n\nDatabase: MongoDB\nBot records, users, downloads and global settings are stored there. Use MongoDB Atlas backup/restore for production backups.", reply_markup=admin_keyboard())

    async def bot_capacity(self, update):
        total = await db.count_bots()
        await update.message.reply_text(f"📦 BOT CAPACITY\n\nManaged bots in database: {total}\nThe platform has no artificial 1M-bot UI limit; actual Telegram/API/hosting limits still apply.", reply_markup=admin_keyboard())

    async def notifications_status(self, update):
        await update.message.reply_text("🔔 NOTIFICATIONS\n\nAdmin notifications are currently represented by Render logs and bot status/error records.", reply_markup=admin_keyboard())

    async def _prompt_simple(self, update, context, state, text):
        context.user_data["state"] = state
        await update.message.reply_text(text)

    async def show_my_bots(self, update):
        bots = await db.get_user_bots(update.effective_user.id)
        if not bots:
            await update.message.reply_text("❌ You do not have a managed bot yet.")
            return
        buttons = []
        text = "🤖 MY BOTS\n\n"
        for bot in bots:
            name = bot.get("username", "N/A")
            text += f"@{name} — {bot.get('status','unknown')}\n"
            buttons.append([InlineKeyboardButton(f"📊 @{name}", callback_data=f"ownerstats:{bot['bot_id']}")])
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    async def handle_managed_bot_created(self, update, context):
        message = update.message
        info = getattr(message, "managed_bot_created", None) if message else None
        owner = update.effective_user
        bot_info = getattr(info, "bot", None) if info else None
        if not message or not owner or not bot_info:
            return

        if not await db.is_bot_creation_enabled() and not is_admin(owner.id):
            await message.reply_text("⛔ Bot creation is currently disabled.")
            return

        token = await self.get_managed_bot_token(bot_info.id)
        if not token:
            await message.reply_text("❌ Managed bot token could not be retrieved.")
            return

        await db.add_new_bot(owner.id, token, bot_info.id, bot_info.username or "")
        started = await bot_manager.start_bot_instance(bot_info.id, token)
        if started:
            await db.update_bot_status(bot_info.id, "active")
            await message.reply_text(
                f"✅ Bot is online!\n\n@{bot_info.username}\nhttps://t.me/{bot_info.username}\n\n"
                "Send /start to the new bot. It will ask for language once and remember it."
            )
        else:
            await message.reply_text("⚠️ Bot was saved, but could not be started. Check Render logs.")

    async def get_managed_bot_token(self, bot_id):
        try:
            return await self.app.bot.get_managed_bot_token(bot_id)
        except Exception:
            logger.exception("Managed bot token error")
            return None

    async def handle_callback(self, update, context):
        query = update.callback_query
        if not query:
            return
        data = query.data or ""
        uid = query.from_user.id
        try:
            await query.answer()
        except Exception:
            pass

        if data.startswith("lang_"):
            lang = data.split("_", 1)[1]
            if lang in LANGUAGES:
                await db.set_main_user_language(uid, lang)
                await query.edit_message_text(f"✅ Language saved: {LANGUAGES[lang]}")
            return

        if data == "noop":
            return

        if data.startswith(("manage:", "bstats:", "start:", "stop:", "restart:", "confirmdel:", "delete:", "broadcast:", "bu:", "allbots", "setting:", "fj:", "clear:")) and not is_admin(uid):
            await query.answer("⛔ Admin only.", show_alert=True)
            return

        if data == "allbots":
            await self.show_all_bots_from_callback(query)
            return
        if data.startswith("manage:"):
            await self.manage_bot_menu(query, int(data.split(":")[1]))
            return
        if data.startswith("bstats:"):
            await self.show_bot_stats(query, int(data.split(":")[1]))
            return
        if data.startswith("bu:"):
            await self.show_bot_users_for(query, int(data.split(":")[1]))
            return
        if data.startswith("start:"):
            await self.start_managed_bot(query, int(data.split(":")[1]))
            return
        if data.startswith("stop:"):
            await self.stop_managed_bot(query, int(data.split(":")[1]))
            return
        if data.startswith("restart:"):
            await self.restart_managed_bot(query, int(data.split(":")[1]))
            return
        if data.startswith("broadcast:"):
            bot_id = int(data.split(":")[1])
            context.user_data["state"] = "broadcast_bot"
            context.user_data["broadcast_bot_id"] = bot_id
            await query.edit_message_text("📣 Send the text/media to broadcast to this bot's users.")
            return
        if data.startswith("confirmdel:"):
            bot_id = int(data.split(":")[1])
            await query.edit_message_text(
                "⚠️ Permanently delete this bot?",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Cancel", callback_data=f"manage:{bot_id}"),
                    InlineKeyboardButton("🗑 YES DELETE", callback_data=f"delete:{bot_id}"),
                ]]),
            )
            return
        if data.startswith("delete:"):
            await self.delete_managed_bot(query, int(data.split(":")[1]))
            return

        if data == "fj:verify":
            channels = await db.get_global_force_join_channels()
            results = await force_join_checker.verify_admin_channels(channels)
            lines = ["🔎 MAIN BOT FORCE-JOIN CHECK\n"]
            for row in results:
                lines.append(f"{'🟢' if row['ok'] else '🔴'} {row['channel']} — {row['status']}")
                if row.get('error'):
                    lines.append(f"   {row['error']}")
            await query.edit_message_text("\n".join(lines)[:4000])
            return
        if data == "fj:add":
            context.user_data["state"] = "force_add"
            await query.edit_message_text("➕ Send channel username, for example @MyChannel.")
            return
        if data.startswith("fj:del:"):
            index = int(data.split(":")[2])
            await db.remove_global_force_join_channel(index)
            await query.edit_message_text("✅ Channel removed. Use the admin panel → 🔐 Force Join to view the new list.")
            return
        if data == "fj:clear":
            await db.clear_global_force_join_channels()
            await query.edit_message_text("🧹 Global Force Join cleared. All managed bots are now unrestricted.")
            return

        if data == "setting:creation:on":
            await db.set_bot_creation_enabled(True)
            await query.edit_message_text("✅ Bot creation ENABLED.")
            return
        if data == "setting:creation:off":
            await db.set_bot_creation_enabled(False)
            await query.edit_message_text("🔴 Bot creation DISABLED.")
            return
        if data == "setting:maintenance:on":
            await db.set_system_setting("maintenance_mode", True)
            await query.edit_message_text("🛠 Maintenance mode ENABLED for all managed bots.")
            return
        if data == "setting:maintenance:off":
            await db.set_system_setting("maintenance_mode", False)
            await query.edit_message_text("🟢 Maintenance mode DISABLED.")
            return
        if data == "clear:downloads":
            await db.downloads.delete_many({})
            await query.edit_message_text("🧹 Download history cleared.")
            return
        if data == "clear:pending":
            await db.pending_downloads.delete_many({})
            await query.edit_message_text("🧽 Pending force-join downloads cleared.")
            return

        if data.startswith("ownerstats:"):
            bot_id = int(data.split(":")[1])
            bot = await db.get_bot(bot_id)
            if not bot or int(bot.get("owner_id", 0)) != uid:
                await query.answer("⛔ Not your bot.", show_alert=True)
                return
            stats = await db.get_bot_stats(bot_id)
            await query.edit_message_text(
                f"📊 @{bot.get('username','N/A')}\n\n"
                f"👥 Users: {stats['total_users']}\n📥 Downloads: {stats['total_downloads']}\n"
                f"🎬 Videos: {stats['videos']}\n🎵 Audio: {stats['audio']}"
            )

    async def error_handler(self, update, context):
        logger.error("Main bot error: %s", context.error, exc_info=True)


main_bot = MainSaaSBot()
