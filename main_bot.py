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
from premium import register_premium_handlers, premium_command, admin_premium_center

logger = logging.getLogger(__name__)

LANGUAGES = {
    "en": "English 🇬🇧",
    "so": "Soomaali 🇸🇴",
    "ar": "العربية 🇸🇦",
    "es": "Español 🇪🇸",
}

# Main-bot user interface translations. Admin panel intentionally stays in English
# so administrators have stable button names regardless of their personal language.
USER_I18N = {
    "en": {
        "create": "➕ Create New Bot", "my_bots": "🤖 My Bots", "premium": "⭐ Premium", "language": "🌐 Language", "help": "ℹ️ Help", "admin": "👑 Admin Panel",
        "choose_language": "🌐 Choose your language:",
        "language_saved": "✅ Language saved: English 🇬🇧",
        "welcome_title": "🤖 — Downloader Bot Builder",
        "welcome": "This main bot creates ready-to-use video downloader bots.",
        "platforms": "Your created bots can download supported videos from:\n• TikTok\n• Facebook\n• YouTube (up to 10 minutes)\n• Pinterest\n• Instagram\n• Snapchat\n• X/Twitter",
        "features": "🎵 Every downloaded video has a MUSIC button to convert it to MP3.",
        "instructions": "➕ Create New Bot — create your own downloader bot\n🤖 My Bots — manage your bots\n🌐 Language — choose your language",
        "help_text": "ℹ️ HELP\n\n➕ Create New Bot — create a downloader bot.\n🤖 My Bots — see your bots.\nSend a video link to a created bot to download it.\nThe downloaded video has a MUSIC button.\nMUSIC creates MP3.",
        "id": "🆔 Your Telegram ID:\n\n{uid}\n\nSet this number in Render as OWNER_ID.",
        "unauthorized": "⛔ You are not authorized.\n\nYour ID: {uid}\nAdd this ID to Render OWNER_ID or ADMIN_IDS.",
        "bot_online": "✅ Bot is online!\n\n@{username}\nhttps://t.me/{username}\n\nSend /start to your new bot. It will remember your language after you choose it.",
        "bot_saved_failed": "⚠️ Bot was saved, but could not be started. Check Render logs.",
        "token_missing": "❌ Managed bot token could not be retrieved.",
        "creation_disabled": "⛔ Bot creation is currently disabled.",
    },
    "so": {
        "create": "➕ Samee Bot Cusub", "my_bots": "🤖 Bots-kayga", "premium": "⭐ Premium", "language": "🌐 Luuqad", "help": "ℹ️ Caawimo", "admin": "👑 Admin Panel",
        "choose_language": "🌐 Dooro luuqadda:",
        "language_saved": "✅ Luuqadda waa la keydiyey: Soomaali 🇸🇴",
        "welcome_title": "🤖 — Dhisaha Downloader Bot",
        "welcome": "Bot-kan weyn wuxuu kuu sameeyaa bots diyaar u ah dajinta videos-ka.",
        "platforms": "Bots-ka aad sameysato waxay ka dajin karaan videos:\n• TikTok\n• Facebook\n• YouTube (ilaa 10 daqiiqo)\n• Pinterest\n• Instagram\n• Snapchat\n• X/Twitter",
        "features": "🎵 Video kasta oo la dajiyo wuxuu leeyahay MUSIC si loogu beddelo MP3.",
        "instructions": "➕ Samee Bot Cusub — samee downloader bot-kaaga\n🤖 Bots-kayga — maamul bots-kaaga\n🌐 Luuqad — beddel luuqadda bot-ka",
        "help_text": "ℹ️ CAAWIMO\n\n➕ Samee Bot Cusub — samee downloader bot.\n🤖 Bots-kayga — eeg oo maamul bots-kaaga.\nLink video u dir bot-ka aad sameysatay si loo dajiyo.\nVideo-ga wuxuu leeyahay MUSIC.\nMUSIC wuxuu sameeyaa MP3.",
        "id": "🆔 Telegram ID-gaaga:\n\n{uid}\n\nNumber-kan ku geli Render OWNER_ID.",
        "unauthorized": "⛔ Looma oggola.\n\nID-gaaga: {uid}\nKu dar Render OWNER_ID ama ADMIN_IDS.",
        "bot_online": "✅ Bot-ku wuu shaqeynayaa!\n\n@{username}\nhttps://t.me/{username}\n\nU dir /start bot-kaaga cusub. Luuqadda aad doorato wuu xasuusanayaa.",
        "bot_saved_failed": "⚠️ Bot-ka waa la keydiyey laakiin lama bilaabi karin. Fiiri Render logs.",
        "token_missing": "❌ Token-ka bot-ka lama heli karo.",
        "creation_disabled": "⛔ Sameynta bots-ka hadda waa la xiray.",
    },
    "ar": {
        "create": "➕ إنشاء بوت جديد", "my_bots": "🤖 بوتاتي", "premium": "⭐ بريميوم", "language": "🌐 اللغة", "help": "ℹ️ المساعدة", "admin": "👑 لوحة الإدارة",
        "choose_language": "🌐 اختر لغتك:",
        "language_saved": "✅ تم حفظ اللغة: العربية 🇸🇦",
        "welcome_title": "🤖 — منشئ بوتات التحميل",
        "welcome": "هذا البوت الرئيسي ينشئ لك بوتات جاهزة لتحميل الفيديوهات.",
        "platforms": "يمكن لبوتاتك تحميل الفيديو من:\n• TikTok\n• Facebook\n• YouTube (حتى 10 دقائق)\n• Pinterest\n• Instagram\n• Snapchat\n• X/Twitter",
        "features": "🎵 كل فيديو يتم تحميله يحتوي على زر MUSIC لتحويله إلى MP3.",
        "instructions": "➕ إنشاء بوت جديد — أنشئ بوت التحميل الخاص بك\n🤖 بوتاتي — إدارة بوتاتك\n🌐 اللغة — تغيير لغة البوت",
        "help_text": "ℹ️ المساعدة\n\n➕ إنشاء بوت جديد — إنشاء بوت لتحميل الفيديو.\n🤖 بوتاتي — عرض وإدارة بوتاتك.\nأرسل رابط فيديو إلى البوت ليتم تحميله.\nالفيديو يحتوي على زر MUSIC.\nMUSIC يحول الفيديو إلى MP3.",
        "id": "🆔 معرف Telegram الخاص بك:\n\n{uid}\n\nضع هذا الرقم في Render باسم OWNER_ID.",
        "unauthorized": "⛔ غير مصرح لك.\n\nمعرفك: {uid}\nأضف المعرف إلى OWNER_ID أو ADMIN_IDS في Render.",
        "bot_online": "✅ البوت يعمل الآن!\n\n@{username}\nhttps://t.me/{username}\n\nأرسل /start إلى البوت الجديد. سيحفظ اللغة التي تختارها.",
        "bot_saved_failed": "⚠️ تم حفظ البوت ولكن تعذر تشغيله. راجع سجلات Render.",
        "token_missing": "❌ تعذر الحصول على رمز البوت.",
        "creation_disabled": "⛔ إنشاء البوتات متوقف حالياً.",
    },
    "es": {
        "create": "➕ Crear bot nuevo", "my_bots": "🤖 Mis bots", "premium": "⭐ Premium", "language": "🌐 Idioma", "help": "ℹ️ Ayuda", "admin": "👑 Panel de administración",
        "choose_language": "🌐 Elige tu idioma:",
        "language_saved": "✅ Idioma guardado: Español 🇪🇸",
        "welcome_title": "🤖 — Creador de bots descargadores",
        "welcome": "Este bot principal crea bots listos para descargar vídeos.",
        "platforms": "Tus bots pueden descargar vídeos de:\n• TikTok\n• Facebook\n• YouTube (hasta 10 minutos)\n• Pinterest\n• Instagram\n• Snapchat\n• X/Twitter",
        "features": "🎵 Cada vídeo descargado tiene un botón MUSIC para convertirlo a MP3.",
        "instructions": "➕ Crear bot nuevo — crea tu bot descargador\n🤖 Mis bots — administra tus bots\n🌐 Idioma — cambia el idioma del bot",
        "help_text": "ℹ️ AYUDA\n\n➕ Crear bot nuevo — crea un bot descargador.\n🤖 Mis bots — mira tus bots.\nEnvía un enlace de vídeo a un bot creado para descargarlo.\nEl vídeo tiene un botón MUSIC.\nMUSIC crea MP3.",
        "id": "🆔 Tu ID de Telegram:\n\n{uid}\n\nPon este número en Render como OWNER_ID.",
        "unauthorized": "⛔ No tienes autorización.\n\nTu ID: {uid}\nAñádelo a OWNER_ID o ADMIN_IDS en Render.",
        "bot_online": "✅ ¡El bot está activo!\n\n@{username}\nhttps://t.me/{username}\n\nEnvía /start a tu nuevo bot. Recordará el idioma que elijas.",
        "bot_saved_failed": "⚠️ El bot se guardó, pero no pudo iniciarse. Revisa los logs de Render.",
        "token_missing": "❌ No se pudo obtener el token del bot.",
        "creation_disabled": "⛔ La creación de bots está desactivada actualmente.",
    },
}

def user_lang(uid: int) -> str:
    # Callers that already have a stored language should pass it through.
    return "en"

def tr(lang: str, key: str, **kwargs) -> str:
    lang = lang if lang in USER_I18N else "en"
    return USER_I18N[lang][key].format(**kwargs)


def localized_button(lang: str, key: str) -> str:
    lang = lang if lang in USER_I18N else "en"
    return USER_I18N[lang][key]


def canonical_user_button(text: str) -> str:
    for key in ("create", "my_bots", "premium", "language", "help", "admin"):
        for lang in USER_I18N:
            if text == USER_I18N[lang][key]:
                return key
    return text


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
    "⭐ Premium Center", "💰 Premium Prices",
    "⭐ Premium Bots", "🎁 Grant Premium",
    "✏️ Premium Caption", "🔘 Premium Buttons",
    "📢 Premium Ads", "📊 Premium Stats",
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


def main_keyboard(user_id=None, lang="en"):
    request_id = int(time.time() * 1000) % 2147483647
    try:
        create_button = KeyboardButton(
            text=localized_button(lang, "create"),
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
        [KeyboardButton(localized_button(lang, "my_bots")), KeyboardButton(localized_button(lang, "premium"))],
        [KeyboardButton(localized_button(lang, "language")), KeyboardButton(localized_button(lang, "help"))],
    ]
    if user_id is not None and is_admin(user_id):
        rows.append([KeyboardButton(localized_button(lang, "admin"))])
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
        register_premium_handlers(self.app)
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
            lang = await db.get_main_user_language(update.effective_user.id)
            await update.message.reply_text(tr(lang, "id", uid=update.effective_user.id))

    async def language_command(self, update, context):
        if update.message:
            lang = await db.get_main_user_language(update.effective_user.id)
            await update.message.reply_text(
                tr(lang, "choose_language"),
                reply_markup=language_keyboard(),
            )

    async def start_command(self, update, context):
        if not update.effective_user or not update.message:
            return
        user = update.effective_user
        await db.save_main_user(user.id, user.username or "", user.full_name or "")
        lang = await db.get_main_user_language(user.id)
        await update.message.reply_text(
            f"{tr(lang, 'welcome_title')}\n\n"
            f"👋 Welcome, {user.first_name or 'USER'}!\n\n"
            f"{tr(lang, 'welcome')}\n\n"
            f"{tr(lang, 'platforms')}\n\n"
            f"{tr(lang, 'features')}\n\n"
            f"{tr(lang, 'instructions')}",
            reply_markup=main_keyboard(user.id, lang),
        )

    async def admin_command(self, update, context):
        if not update.effective_user or not update.message:
            return
        if not is_admin(update.effective_user.id):
            lang = await db.get_main_user_language(update.effective_user.id)
            await update.message.reply_text(tr(lang, "unauthorized", uid=update.effective_user.id))
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

        lang = await db.get_main_user_language(uid)
        button = canonical_user_button(text)
        if button == "admin" and is_admin(uid):
            await self.show_dashboard(update)
            return
        if button == "my_bots":
            await self.show_my_bots(update)
            return
        if button == "premium":
            await premium_command(update, context)
            return
        if button == "language":
            await self.language_command(update, context)
            return
        if button == "help":
            await update.message.reply_text(tr(lang, "help_text"))
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
            "Halkan waa koodkaagii oo dhamaystiran, oo laga reebay dhammaan fariimaha ku saabsan Admin Panel-ka iyo Channel Button-ka MP3-ga:

```python
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
from premium import register_premium_handlers, premium_command, admin_premium_center

logger = logging.getLogger(__name__)

LANGUAGES = {
    "en": "English 🇬🇧",
    "so": "Soomaali 🇸🇴",
    "ar": "العربية 🇸🇦",
    "es": "Español 🇪🇸",
}

# Main-bot user interface translations. Admin panel intentionally stays in English
# so administrators have stable button names regardless of their personal language.
USER_I18N = {
    "en": {
        "create": "➕ Create New Bot", "my_bots": "🤖 My Bots", "premium": "⭐ Premium", "language": "🌐 Language", "help": "ℹ️ Help", "admin": "👑 Admin Panel",
        "choose_language": "🌐 Choose your language:",
        "language_saved": "✅ Language saved: English 🇬🇧",
        "welcome_title": "🤖 — Downloader Bot Builder",
        "welcome": "This main bot creates ready-to-use video downloader bots.",
        "platforms": "Your created bots can download supported videos from:\n• TikTok\n• Facebook\n• YouTube (up to 10 minutes)\n• Pinterest\n• Instagram\n• Snapchat\n• X/Twitter",
        "features": "🎵 Every downloaded video has a MUSIC button to convert it to MP3.",
        "instructions": "➕ Create New Bot — create your own downloader bot\n🤖 My Bots — manage your bots\n🌐 Language — choose your language",
        "help_text": "ℹ️ HELP\n\n➕ Create New Bot — create a downloader bot.\n🤖 My Bots — see your bots.\nSend a video link to a created bot to download it.\nThe downloaded video has a MUSIC button.\nMUSIC creates MP3.",
        "id": "🆔 Your Telegram ID:\n\n{uid}\n\nSet this number in Render as OWNER_ID.",
        "unauthorized": "⛔ You are not authorized.\n\nYour ID: {uid}\nAdd this ID to Render OWNER_ID or ADMIN_IDS.",
        "bot_online": "✅ Bot is online!\n\n@{username}\n[https://t.me/](https://t.me/){username}\n\nSend /start to your new bot. It will remember your language after you choose it.",
        "bot_saved_failed": "⚠️ Bot was saved, but could not be started. Check Render logs.",
        "token_missing": "❌ Managed bot token could not be retrieved.",
        "creation_disabled": "⛔ Bot creation is currently disabled.",
    },
    "so": {
        "create": "➕ Samee Bot Cusub", "my_bots": "🤖 Bots-kayga", "premium": "⭐ Premium", "language": "🌐 Luuqad", "help": "ℹ️ Caawimo", "admin": "👑 Admin Panel",
        "choose_language": "🌐 Dooro luuqadda:",
        "language_saved": "✅ Luuqadda waa la keydiyey: Soomaali 🇸🇴",
        "welcome_title": "🤖 — Dhisaha Downloader Bot",
        "welcome": "Bot-kan weyn wuxuu kuu sameeyaa bots diyaar u ah dajinta videos-ka.",
        "platforms": "Bots-ka aad sameysato waxay ka dajin karaan videos:\n• TikTok\n• Facebook\n• YouTube (ilaa 10 daqiiqo)\n• Pinterest\n• Instagram\n• Snapchat\n• X/Twitter",
        "features": "🎵 Video kasta oo la dajiyo wuxuu leeyahay MUSIC si loogu beddelo MP3.",
        "instructions": "➕ Samee Bot Cusub — samee downloader bot-kaaga\n🤖 Bots-kayga — maamul bots-kaaga\n🌐 Luuqad — beddel luuqadda bot-ka",
        "help_text": "ℹ️ CAAWIMO\n\n➕ Samee Bot Cusub — samee downloader bot.\n🤖 Bots-kayga — eeg oo maamul bots-kaaga.\nLink video u dir bot-ka aad sameysatay si loo dajiyo.\nVideo-ga wuxuu leeyahay MUSIC.\nMUSIC wuxuu sameeyaa MP3.",
        "id": "🆔 Telegram ID-gaaga:\n\n{uid}\n\nNumber-kan ku geli Render OWNER_ID.",
        "unauthorized": "⛔ Looma oggola.\n\nID-gaaga: {uid}\nKu dar Render OWNER_ID ama ADMIN_IDS.",
        "bot_online": "✅ Bot-ku wuu shaqeynayaa!\n\n@{username}\n[https://t.me/](https://t.me/){username}\n\nU dir /start bot-kaaga cusub. Luuqadda aad doorato wuu xasuusanayaa.",
        "bot_saved_failed": "⚠️ Bot-ka waa la keydiyey laakiin lama bilaabi karin. Fiiri Render logs.",
        "token_missing": "❌ Token-ka bot-ka lama heli karo.",
        "creation_disabled": "⛔ Sameynta bots-ka hadda waa la xiray.",
    },
    "ar": {
        "create": "➕ إنشاء بوت جديد", "my_bots": "🤖 بوتاتي", "premium": "⭐ بريميوم", "language": "🌐 اللغة", "help": "ℹ️ المساعدة", "admin": "👑 لوحة الإدارة",
        "choose_language": "🌐 اختر لغتك:",
        "language_saved": "✅ تم حفظ اللغة: العربية 🇸🇦",
        "welcome_title": "🤖 — منشئ بوتات التحميل",
        "welcome": "هذا البوت الرئيسي ينشئ لك بوتات جاهزة لتحميل الفيديوهات.",
        "platforms": "يمكن لبوتاتك تحميل الفيديو من:\n• TikTok\n• Facebook\n• YouTube (حتى 10 دقائق)\n• Pinterest\n• Instagram\n• Snapchat\n• X/Twitter",
        "features": "🎵 كل فيديو يتم تحميله يحتوي على زر MUSIC لتحويله إلى MP3.",
        "instructions": "➕ إنشاء بوت جديد — أنشئ بوت التحميل الخاص بك\n🤖 بوتاتي — إدارة بوتاتك\n🌐 اللغة — تغيير لغة البوت",
        "help_text": "ℹ️ المساعدة\n\n➕ إنشاء بوت جديد — إنشاء بوت لتحميل الفيديو.\n🤖 بوتاتي — عرض وإدارة بوتاتك.\nأرسل رابط فيديو إلى البوت ليتم تحميله.\nالفيديو يحتوي على زر MUSIC.\nMUSIC يحول الفيديو إلى MP3.",
        "id": "🆔 معرف Telegram الخاص بك:\n\n{uid}\n\nضع هذا الرقم
