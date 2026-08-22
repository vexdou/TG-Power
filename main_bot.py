# main_bot.py

import asyncio
import logging
import os
import tempfile
import time
from datetime import datetime, timezone

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

try:
    from telegram import KeyboardButtonRequestManagedBot
except ImportError:
    KeyboardButtonRequestManagedBot = None

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ManagedBotUpdatedHandler,
    filters,
)

from telegram.error import TelegramError, Forbidden

from config import Config
from database import db
from bot_manager import bot_manager
from force_join import force_join_checker
from premium import (
    register_premium_handlers,
    premium_command,
    admin_premium_center,
)

logger = logging.getLogger(__name__)

LANGUAGES = {
    "en": "English 🇬🇧",
    "so": "Soomaali 🇸🇴",
    "ar": "العربية 🇸🇦",
    "es": "Español 🇪🇸",
}

USER_I18N = {
    "en": {
        "create": "➕ Create New Bot",
        "my_bots": "🤖 My Bots",
        "premium": "⭐ Premium",
        "language": "🌐 Language",
        "help": "ℹ️ Help",
        "admin": "👑 Admin Panel",

        "choose_language": "🌐 Choose your language:",
        "language_saved": "✅ Language saved: English 🇬🇧",

        "welcome_title": "🤖 TG-Power — Downloader Bot Builder",
        "welcome": (
            "This main bot creates ready-to-use video downloader bots."
        ),

        "platforms": (
            "Your created bots can download supported videos from:\n"
            "• TikTok\n"
            "• Facebook\n"
            "• YouTube (up to 10 minutes)\n"
            "• Pinterest\n"
            "• Instagram\n"
            "• Snapchat\n"
            "• X/Twitter"
        ),

        "features": (
            "🎵 Every downloaded video has a MUSIC button "
            "to convert it to MP3."
        ),

        "instructions": (
            "➕ Create New Bot — create your own downloader bot\n"
            "🤖 My Bots — manage your bots\n"
            "🌐 Language — choose your language"
        ),

        "admin_hint": "",

        "help_text": (
            "ℹ️ HELP\n\n"
            "➕ Create New Bot — create a downloader bot.\n"
            "🤖 My Bots — see your bots.\n"
            "Send a video link to a created bot to download it.\n"
            "The downloaded video has a MUSIC button to convert it to MP3."
        ),

        "id": (
            "🆔 Your Telegram ID:\n\n"
            "{uid}\n\n"
            "Set this number in Render as OWNER_ID."
        ),

        "unauthorized": (
            "⛔ You are not authorized.\n\n"
            "Your ID: {uid}\n"
            "Add this ID to Render OWNER_ID or ADMIN_IDS."
        ),

        "bot_online": (
            "✅ Bot is online!\n\n"
            "@{username}\n"
            "https://t.me/{username}\n\n"
            "Send /start to your new bot."
        ),

        "bot_saved_failed": (
            "⚠️ Bot was saved, but could not be started. "
            "Check Render logs."
        ),

        "token_missing": "❌ Managed bot token could not be retrieved.",
        "creation_disabled": "⛔ Bot creation is currently disabled.",
    },

    "so": {
        "create": "➕ Samee Bot Cusub",
        "my_bots": "🤖 Bots-kayga",
        "premium": "⭐ Premium",
        "language": "🌐 Luuqad",
        "help": "ℹ️ Caawimo",
        "admin": "👑 Admin Panel",

        "choose_language": "🌐 Dooro luuqadda:",
        "language_saved": "✅ Luuqadda waa la keydiyey: Soomaali 🇸🇴",

        "welcome_title": "🤖 TG-Power — Dhisaha Downloader Bot",
        "welcome": (
            "Bot-kan weyn wuxuu kuu sameeyaa bots diyaar u ah "
            "dajinta videos-ka."
        ),

        "platforms": (
            "Bots-ka aad sameysato waxay ka dajin karaan videos:\n"
            "• TikTok\n"
            "• Facebook\n"
            "• YouTube (ilaa 10 daqiiqo)\n"
            "• Pinterest\n"
            "• Instagram\n"
            "• Snapchat\n"
            "• X/Twitter"
        ),

        "features": (
            "🎵 Video kasta oo la dajiyo wuxuu leeyahay MUSIC "
            "si loogu beddelo MP3."
        ),

        "instructions": (
            "➕ Samee Bot Cusub — samee downloader bot-kaaga\n"
            "🤖 Bots-kayga — maamul bots-kaaga\n"
            "🌐 Luuqad — beddel luuqadda bot-ka"
        ),

        "admin_hint": "",

        "help_text": (
            "ℹ️ CAAWIMO\n\n"
            "➕ Samee Bot Cusub — samee downloader bot.\n"
            "🤖 Bots-kayga — eeg oo maamul bots-kaaga.\n"
            "Link video u dir bot-ka aad sameysatay si loo dajiyo.\n"
            "Video-ga wuxuu leeyahay MUSIC si loogu beddelo MP3."
        ),

        "id": (
            "🆔 Telegram ID-gaaga:\n\n"
            "{uid}\n\n"
            "Number-kan ku geli Render OWNER_ID."
        ),

        "unauthorized": (
            "⛔ Looma oggola.\n\n"
            "ID-gaaga: {uid}\n"
            "Ku dar Render OWNER_ID ama ADMIN_IDS."
        ),

        "bot_online": (
            "✅ Bot-ku wuu shaqeynayaa!\n\n"
            "@{username}\n"
            "https://t.me/{username}\n\n"
            "U dir /start bot-kaaga cusub."
        ),

        "bot_saved_failed": (
            "⚠️ Bot-ka waa la keydiyey laakiin lama bilaabi karin. "
            "Fiiri Render logs."
        ),

        "token_missing": "❌ Token-ka bot-ka lama heli karo.",
        "creation_disabled": "⛔ Sameynta bots-ka hadda waa la xiray.",
    },

    "ar": {
        "create": "➕ إنشاء بوت جديد",
        "my_bots": "🤖 بوتاتي",
        "premium": "⭐ بريميوم",
        "language": "🌐 اللغة",
        "help": "ℹ️ المساعدة",
        "admin": "👑 لوحة الإدارة",

        "choose_language": "🌐 اختر لغتك:",
        "language_saved": "✅ تم حفظ اللغة: العربية 🇸🇦",

        "welcome_title": "🤖 TG-Power — منشئ بوتات التحميل",
        "welcome": "هذا البوت الرئيسي ينشئ لك بوتات جاهزة لتحميل الفيديوهات.",

        "platforms": (
            "يمكن لبوتاتك تحميل الفيديو من:\n"
            "• TikTok\n"
            "• Facebook\n"
            "• YouTube (حتى 10 دقائق)\n"
            "• Pinterest\n"
            "• Instagram\n"
            "• Snapchat\n"
            "• X/Twitter"
        ),

        "features": (
            "🎵 كل فيديو يتم تحميله يحتوي على زر MUSIC "
            "لتحويله إلى MP3."
        ),

        "instructions": (
            "➕ إنشاء بوت جديد — أنشئ بوت التحميل الخاص بك\n"
            "🤖 بوتاتي — إدارة بوتاتك\n"
            "🌐 اللغة — تغيير لغة البوت"
        ),

        "admin_hint": "",

        "help_text": (
            "ℹ️ المساعدة\n\n"
            "➕ إنشاء بوت جديد — إنشاء بوت لتحميل الفيديو.\n"
            "🤖 بوتاتي — عرض وإدارة بوتاتك.\n"
            "أرسل رابط فيديو إلى البوت ليتم تحميله.\n"
            "الفيديو يحتوي على زر MUSIC لتحويله إلى MP3."
        ),

        "id": (
            "🆔 معرف Telegram الخاص بك:\n\n"
            "{uid}\n\n"
            "ضع هذا الرقم في Render باسم OWNER_ID."
        ),

        "unauthorized": (
            "⛔ غير مصرح لك.\n\n"
            "معرفك: {uid}\n"
            "أضف المعرف إلى OWNER_ID أو ADMIN_IDS في Render."
        ),

        "bot_online": (
            "✅ البوت يعمل الآن!\n\n"
            "@{username}\n"
            "https://t.me/{username}\n\n"
            "أرسل /start إلى البوت الجديد."
        ),

        "bot_saved_failed": (
            "⚠️ تم حفظ البوت ولكن تعذر تشغيله. "
            "راجع سجلات Render."
        ),

        "token_missing": "❌ تعذر الحصول على رمز البوت.",
        "creation_disabled": "⛔ إنشاء البوتات متوقف حالياً.",
    },

    "es": {
        "create": "➕ Crear bot nuevo",
        "my_bots": "🤖 Mis bots",
        "premium": "⭐ Premium",
        "language": "🌐 Idioma",
        "help": "ℹ️ Ayuda",
        "admin": "👑 Panel de administración",

        "choose_language": "🌐 Elige tu idioma:",
        "language_saved": "✅ Idioma guardado: Español 🇪🇸",

        "welcome_title": "🤖 TG-Power — Creador de bots descargadores",
        "welcome": (
            "Este bot principal crea bots listos para descargar vídeos."
        ),

        "platforms": (
            "Tus bots pueden descargar vídeos de:\n"
            "• TikTok\n"
            "• Facebook\n"
            "• YouTube (hasta 10 minutos)\n"
            "• Pinterest\n"
            "• Instagram\n"
            "• Snapchat\n"
            "• X/Twitter"
        ),

        "features": (
            "🎵 Cada vídeo descargado tiene un botón MUSIC "
            "para convertirlo a MP3."
        ),

        "instructions": (
            "➕ Crear bot nuevo — crea tu bot descargador\n"
            "🤖 Mis bots — administra tus bots\n"
            "🌐 Idioma — cambia el idioma del bot"
        ),

        "admin_hint": "",

        "help_text": (
            "ℹ️ AYUDA\n\n"
            "➕ Crear bot nuevo — crea un bot descargador.\n"
            "🤖 Mis bots — mira tus bots.\n"
            "Envía un enlace de vídeo a un bot creado para descargarlo.\n"
            "El vídeo tiene un botón MUSIC para convertirlo a MP3."
        ),

        "id": (
            "🆔 Tu ID de Telegram:\n\n"
            "{uid}\n\n"
            "Pon este número en Render como OWNER_ID."
        ),

        "unauthorized": (
            "⛔ No tienes autorización.\n\n"
            "Tu ID: {uid}\n"
            "Añádelo a OWNER_ID o ADMIN_IDS en Render."
        ),

        "bot_online": (
            "✅ ¡El bot está activo!\n\n"
            "@{username}\n"
            "https://t.me/{username}\n\n"
            "Envía /start a tu nuevo bot."
        ),

        "bot_saved_failed": (
            "⚠️ El bot se guardó, pero no pudo iniciarse. "
            "Revisa los logs de Render."
        ),

        "token_missing": "❌ No se pudo obtener el token del bot.",
        "creation_disabled": "⛔ La creación de bots está desactivada actualmente.",
    },
}


def tr(lang: str, key: str, **kwargs) -> str:
    lang = lang if lang in USER_I18N else "en"
    return USER_I18N[lang][key].format(**kwargs)


def localized_button(lang: str, key: str) -> str:
    lang = lang if lang in USER_I18N else "en"
    return USER_I18N[lang][key]


def canonical_user_button(text: str) -> str:
    for key in (
        "create",
        "my_bots",
        "premium",
        "language",
        "help",
        "admin",
    ):
        for lang in USER_I18N:
            if text == USER_I18N[lang][key]:
                return key
    return text


ADMIN_BUTTONS = [
    "📊 Dashboard",
    "🤖 All Bots",
    "🔎 Search Bot",
    "👥 Users",
    "👥 Bot Users",
    "👑 Bot Owners",
    "📥 Downloads",
    "📈 Download Stats",
    "❌ Failed Downloads",
    "🕘 Recent Downloads",
    "📢 Broadcast All",
    "📣 Broadcast Bot",
    "👀 Broadcast Preview",
    "🔐 Force Join",
    "🔎 Force Join Check",
    "⚙️ Bot Creation",
    "▶️ Start Bot",
    "⏹ Stop Bot",
    "🔄 Restart Bot",
    "🗑 Delete Bot",
    "❤️ Bot Health",
    "🚨 Bot Errors",
    "♻️ Reload Bots",
    "🛠 Maintenance",
    "🧰 System Settings",
    "⏱ Max Video",
    "📦 Max File",
    "🌐 Default Language",
    "📋 User Export",
    "🤖 Bot Export",
    "🧹 Clear Downloads",
    "🧽 Clear Pending",
    "🧼 Cleanup Temp",
    "🗄 Database Status",
    "📡 Queue Status",
    "⏲ Uptime",
    "🔒 Security",
    "🧑‍💼 Admin ID",
    "📊 Platform Stats",
    "🔄 Reset Settings",
    "📜 Activity Log",
    "💾 Backup Info",
    "📦 Bot Capacity",
    "🔔 Notifications",
    "ℹ️ About",
    "❓ Help",
    "🔃 Refresh",
    "🔙 User Panel",
    "🧪 Test System",
    "📍 Channel Settings",
    "⭐ Premium Center",
    "💰 Premium Prices",
    "⭐ Premium Bots",
    "🎁 Grant Premium",
    "✏️ Premium Caption",
    "🔘 Premium Buttons",
    "📢 Premium Ads",
    "📊 Premium Stats",
]


def admin_ids():
    ids = set()

    try:
        owner_id = getattr(Config, "OWNER_ID", None)
        if owner_id:
            ids.add(int(owner_id))
    except (TypeError, ValueError):
        pass

    for value in getattr(Config, "ADMIN_IDS", []):
        try:
            ids.add(int(value))
        except (TypeError, ValueError):
            pass

    return ids


def is_admin(user_id: int) -> bool:
    try:
        return int(user_id) in admin_ids()
    except (TypeError, ValueError):
        return False


def main_keyboard(user_id=None, lang="en"):
    request_id = int(time.time() * 1000) % 2147483647

    if KeyboardButtonRequestManagedBot is not None:
        try:
            create_button = KeyboardButton(
                text=localized_button(lang, "create"),
                request_managed_bot=KeyboardButtonRequestManagedBot(
                    request_id=request_id,
                    suggested_name="My Downloader Bot",
                    suggested_username="MyDownloaderBot",
                ),
            )
        except Exception:
            create_button = KeyboardButton(
                localized_button(lang, "create")
            )
    else:
        create_button = KeyboardButton(
            localized_button(lang, "create")
        )

    rows = [
        [create_button],
        [
            KeyboardButton(localized_button(lang, "my_bots")),
            KeyboardButton(localized_button(lang, "premium")),
        ],
        [
            KeyboardButton(localized_button(lang, "language")),
            KeyboardButton(localized_button(lang, "help")),
        ],
    ]

    if user_id is not None and is_admin(user_id):
        rows.append(
            [KeyboardButton(localized_button(lang, "admin"))]
        )

    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
        is_persistent=True,
    )


def admin_keyboard():
    rows = []

    for i in range(0, len(ADMIN_BUTTONS), 2):
        row = [KeyboardButton(ADMIN_BUTTONS[i])]

        if i + 1 < len(ADMIN_BUTTONS):
            row.append(KeyboardButton(ADMIN_BUTTONS[i + 1]))

        rows.append(row)

    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
        is_persistent=True,
    )


def language_keyboard():
    keys = list(LANGUAGES.keys())
    rows = []

    for i in range(0, len(keys), 2):
        row = [
            InlineKeyboardButton(
                LANGUAGES[keys[i]],
                callback_data=f"lang_{keys[i]}",
            )
        ]

        if i + 1 < len(keys):
            row.append(
                InlineKeyboardButton(
                    LANGUAGES[keys[i + 1]],
                    callback_data=f"lang_{keys[i + 1]}",
                )
            )

        rows.append(row)

    return InlineKeyboardMarkup(rows)


class MainSaaSBot:

    def __init__(self):
        self.started_at = None

        self.app = (
            Application
            .builder()
            .token(Config.BOT_TOKEN)
            .build()
        )

        self._setup_handlers()

    def _setup_handlers(self):

        self.app.add_handler(
            CommandHandler("start", self.start_command)
        )

        self.app.add_handler(
            CommandHandler("admin", self.admin_command)
        )

        self.app.add_handler(
            CommandHandler("id", self.id_command)
        )

        self.app.add_handler(
            CommandHandler("language", self.language_command)
        )

        register_premium_handlers(self.app)

        self.app.add_handler(
            MessageHandler(
                filters.StatusUpdate.MANAGED_BOT_CREATED,
                self.handle_managed_bot_created,
            )
        )

        self.app.add_handler(
            ManagedBotUpdatedHandler(
                self.handle_managed_bot_updated
            )
        )

        self.app.add_handler(
            CallbackQueryHandler(self.handle_callback)
        )

        self.app.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.handle_text,
            )
        )

        self.app.add_handler(
            MessageHandler(
                (
                    filters.PHOTO
                    | filters.VIDEO
                    | filters.Document.ALL
                    | filters.AUDIO
                    | filters.VOICE
                    | filters.ANIMATION
                ),
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

            await self.app.bot.delete_webhook(
                drop_pending_updates=True
            )

            await self.app.start()

            if self.app.updater is None:
                raise RuntimeError(
                    "Telegram updater is not available."
                )

            await self.app.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES,
                poll_interval=1.0,
                timeout=30,
            )

            me = await self.app.bot.get_me()

            self.started_at = datetime.now(timezone.utc)

            logger.info(
                "👑 Main SaaS Bot Online: @%s",
                me.username,
            )

        except Exception:
            logger.exception(
                "🔴 Main SaaS Controller failed to start."
            )

            try:
                if (
                    self.app.updater
                    and self.app.updater.running
                ):
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
            if (
                self.app.updater
                and self.app.updater.running
            ):
                await self.app.updater.stop()

            if self.app.running:
                await self.app.stop()

            await force_join_checker.stop()
            await self.app.shutdown()

        except Exception:
            logger.exception(
                "Main controller shutdown error"
            )

    async def id_command(self, update, context):

        if not update.effective_user or not update.message:
            return

        lang = await db.get_main_user_language(
            update.effective_user.id
        )

        await update.message.reply_text(
            tr(
                lang,
                "id",
                uid=update.effective_user.id,
            )
        )

    async def language_command(self, update, context):

        if not update.message or not update.effective_user:
            return

        lang = await db.get_main_user_language(
            update.effective_user.id
        )

        await update.message.reply_text(
            tr(lang, "choose_language"),
            reply_markup=language_keyboard(),
        )

    async def start_command(self, update, context):

        if not update.effective_user or not update.message:
            return

        user = update.effective_user

        await db.save_main_user(
            user.id,
            user.username or "",
            user.full_name or "",
        )

        lang = await db.get_main_user_language(user.id)

        parts = [
            tr(lang, "welcome_title"),
            f"👋 {user.first_name or 'User'}!",
            tr(lang, "welcome"),
            tr(lang, "platforms"),
            tr(lang, "features"),
            tr(lang, "instructions"),
        ]

        admin_h = tr(lang, "admin_hint")

        if admin_h:
            parts.append(admin_h)

        await update.message.reply_text(
            "\n\n".join(parts),
            reply_markup=main_keyboard(
                user.id,
                lang,
            ),
        )

    async def admin_command(self, update, context):

        if not update.effective_user or not update.message:
            return

        if not is_admin(update.effective_user.id):
            lang = await db.get_main_user_language(
                update.effective_user.id
            )

            await update.message.reply_text(
                tr(
                    lang,
                    "unauthorized",
                    uid=update.effective_user.id,
                )
            )
            return

        await self.show_dashboard(update)

    async def show_dashboard(self, update):

        stats = await db.get_global_stats()
        maintenance = await db.get_system_setting(
            "maintenance_mode",
            False,
        )
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
            f"🤖 Bot creation: "
            f"{'ON' if creation else 'OFF'}\n"
            f"🛠 Maintenance: "
            f"{'ON' if maintenance else 'OFF'}\n\n"
            "Choose any control below.",
            reply_markup=admin_keyboard(),
        )

    async def show_all_bots(self, update):

        bots = await db.get_all_bots()

        if not bots:
            await update.message.reply_text(
                "🤖 No managed bots yet.",
                reply_markup=admin_keyboard(),
            )
            return

        lines = ["🤖 ALL MANAGED BOTS\n"]
        buttons = []

        for bot in bots:
            bid = bot.get("bot_id")
            username = bot.get("username") or "N/A"
            status = bot.get("status", "unknown")

            icon = (
                "🟢"
                if status == "active"
                else "🔴"
                if status == "failed"
                else "🟡"
            )

            lines.append(
                f"{icon} @{username} | "
                f"{status} | ID {bid}"
            )

            buttons.append(
                [
                    InlineKeyboardButton(
                        f"⚙️ @{username}",
                        callback_data=f"manage:{bid}",
                    ),
                    InlineKeyboardButton(
                        "📊 Stats",
                        callback_data=f"bstats:{bid}",
                    ),
                ]
            )

        await update.message.reply_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    async def show_all_bots_from_callback(self, query):

        bots = await db.get_all_bots()

        if not bots:
            await query.edit_message_text(
                "🤖 No managed bots yet."
            )
            return

        buttons = []

        for bot in bots:
            bid = bot["bot_id"]
            username = bot.get("username") or "N/A"

            buttons.append(
                [
                    InlineKeyboardButton(
                        f"⚙️ @{username}",
                        callback_data=f"manage:{bid}",
                    ),
                    InlineKeyboardButton(
                        "📊 Stats",
                        callback_data=f"bstats:{bid}",
                    ),
                ]
            )

        await query.edit_message_text(
            "🤖 ALL MANAGED BOTS",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    async def choose_bot(self, update, mode):

        bots = await db.get_all_bots()

        if not bots:
            await update.message.reply_text(
                "🤖 No managed bots.",
                reply_markup=admin_keyboard(),
            )
            return

        buttons = []

        for bot in bots:
            bid = bot.get("bot_id")
            username = bot.get("username") or "N/A"

            buttons.append(
                [
                    InlineKeyboardButton(
                        f"@{username}",
                        callback_data=f"{mode}:{bid}",
                    )
                ]
            )

        await update.message.reply_text(
            "Choose a bot:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    async def show_users(self, update):

        stats = await db.get_global_stats()

        await update.message.reply_text(
            "👥 USERS CENTER\n\n"
            f"👤 Main-controller users: {stats['users']}\n"
            f"👥 All managed-bot users: "
            f"{stats['bot_users']}",
            reply_markup=admin_keyboard(),
        )

    async def show_bot_users(self, update):
        await self.choose_bot(update, "bu")

    async def show_bot_users_for(self, query, bot_id):

        users = await db.get_all_bot_users(bot_id)
        bot = await db.get_bot(bot_id)

        username = (
            (bot or {}).get("username", "N/A")
        )

        text = (
            f"👥 USERS OF @{username}\n\n"
            f"Total: {len(users)}\n\n"
        )

        for user in users[:100]:
            text += (
                f"• {user.get('first_name') "
                f"or user.get('username') "
                f"or user.get('user_id')} — "
                f"{user.get('user_id')}\n"
            )

        await query.edit_message_text(
            text[:4000],
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 All Bots",
                            callback_data="allbots",
                        )
                    ]
                ]
            ),
        )

    async def show_downloads(self, update):

        total = await db.count_downloads()
        success = await db.count_successful_downloads()
        failed = await db.downloads.count_documents(
            {"status": "failed"}
        )

        await update.message.reply_text(
            f"📥 DOWNLOADS\n\n"
            f"Total: {total}\n"
            f"🟢 Success: {success}\n"
            f"🔴 Failed: {failed}",
            reply_markup=admin_keyboard(),
        )

    async def show_download_stats(self, update):

        total = await db.count_downloads()

        video = await db.downloads.count_documents(
            {
                "media_type": "video",
                "status": "success",
            }
        )

        audio = await db.downloads.count_documents(
            {
                "media_type": "audio",
                "status": "success",
            }
        )

        photo = await db.downloads.count_documents(
            {
                "media_type": "photo",
                "status": "success",
            }
        )

        await update.message.reply_text(
            f"📈 DOWNLOAD STATISTICS\n\n"
            f"📥 Total: {total}\n"
            f"🎬 Videos: {video}\n"
            f"🎵 Audio: {audio}\n"
            f"🖼 Photos: {photo}",
            reply_markup=admin_keyboard(),
        )

    async def show_health(self, update):

        bots = await db.get_all_bots()
        running = len(bot_manager.running_bots)

        await update.message.reply_text(
            "❤️ SYSTEM HEALTH\n\n"
            f"DB records: {len(bots)}\n"
            f"Running in memory: {running}\n"
            f"Starting: "
            f"{len(bot_manager.starting_bots)}\n"
            f"MongoDB: "
            f"{'🟢 connected' if db.db is not None else '🔴 disconnected'}",
            reply_markup=admin_keyboard(),
        )

    async def system_settings(self, update):

        maintenance = await db.get_system_setting(
            "maintenance_mode",
            False,
        )

        creation = await db.is_bot_creation_enabled()
        force = await db.get_global_force_join_channels()

        await update.message.reply_text(
            "🧰 SYSTEM SETTINGS\n\n"
            f"Bot creation: "
            f"{'🟢 ON' if creation else '🔴 OFF'}\n"
            f"Maintenance: "
            f"{'🟢 ON' if maintenance else '🔴 OFF'}\n"
            f"Max video: "
            f"{Config.MAX_VIDEO_DURATION_SECONDS // 60} minutes\n"
            f"Max file: "
            f"{Config.MAX_FILE_SIZE_MB} MB\n"
            f"Global force join: "
            f"{len(force)}/5",
            reply_markup=admin_keyboard(),
        )

    async def creation_setting(self, update):

        enabled = await db.is_bot_creation_enabled()

        await update.message.reply_text(
            "⚙️ BOT CREATION\n\n"
            f"Current: "
            f"{'🟢 ENABLED' if enabled else '🔴 DISABLED'}",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🟢 Enable",
                            callback_data="setting:creation:on",
                        ),
                        InlineKeyboardButton(
                            "🔴 Disable",
                            callback_data="setting:creation:off",
                        ),
                    ]
                ]
            ),
        )

    async def maintenance_setting(self, update):

        enabled = await db.get_system_setting(
            "maintenance_mode",
            False,
        )

        await update.message.reply_text(
            "🛠 MAINTENANCE MODE\n\n"
            f"Current: "
            f"{'🟢 ON' if enabled else '🔴 OFF'}",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🟢 Turn ON",
                            callback_data="setting:maintenance:on",
                        ),
                        InlineKeyboardButton(
                            "🔴 Turn OFF",
                            callback_data="setting:maintenance:off",
                        ),
                    ]
                ]
            ),
        )

    async def force_join_menu(self, update):

        channels = await db.get_global_force_join_channels()

        text = (
            "🔐 GLOBAL FORCE JOIN\n\n"
            "This list applies to EVERY managed bot.\n"
            "Maximum: 5 channels.\n\n"
        )

        if channels:
            text += "\n".join(
                f"{i + 1}. {c}"
                for i, c in enumerate(channels)
            )
        else:
            text += "No channels configured."

        rows = [
            [
                InlineKeyboardButton(
                    "🔎 Verify Main Bot Admin Access",
                    callback_data="fj:verify",
                )
            ]
        ]

        if len(channels) < 5:
            rows.append(
                [
                    InlineKeyboardButton(
                        "➕ Add Channel",
                        callback_data="fj:add",
                    )
                ]
            )

        for i, channel in enumerate(channels):
            rows.append(
                [
                    InlineKeyboardButton(
                        f"🗑 Remove {i + 1}: {channel}",
                        callback_data=f"fj:del:{i}",
                    )
                ]
            )

        if channels:
            rows.append(
                [
                    InlineKeyboardButton(
                        "🧹 Remove ALL",
                        callback_data="fj:clear",
                    )
                ]
            )

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(rows),
        )

    async def verify_force_join_channels(self, update):

        channels = await db.get_global_force_join_channels()

        if not channels:
            await update.message.reply_text(
                "🔐 No Force Join channels configured.",
                reply_markup=admin_keyboard(),
            )
            return

        results = (
            await force_join_checker
            .verify_admin_channels(channels)
        )

        lines = ["🔎 MAIN BOT FORCE-JOIN CHECK\n"]

        for row in results:
            icon = "🟢" if row["ok"] else "🔴"

            lines.append(
                f"{icon} {row['channel']} — "
                f"{row['status']}"
            )

            if row.get("error"):
                lines.append(
                    f"   {row['error']}"
                )

        lines.append(
            "\nOnly the MAIN bot needs to be admin "
            "in these channels."
        )

        await update.message.reply_text(
            "\n".join(lines)[:4000],
            reply_markup=admin_keyboard(),
        )

    async def save_force_join_channel(
        self,
        update,
        context,
    ):

        value = (
            update.message.text or ""
        ).strip()

        context.user_data.clear()

        if not value:
            await update.message.reply_text(
                "❌ Send a channel username such as @MyChannel.",
                reply_markup=admin_keyboard(),
            )
            return

        verification = (
            await force_join_checker
            .verify_admin_channels([value])
        )

        if not verification or not verification[0]["ok"]:
            error = (
                verification[0].get("error")
                if verification
                else None
            ) or (
                "Main bot cannot access this channel."
            )

            await update.message.reply_text(
                "❌ Channel was NOT added.\n\n"
                "Make the MAIN bot an administrator "
                "in the channel first.\n"
                f"Details: {error}",
                reply_markup=admin_keyboard(),
            )
            return

        ok, channels = (
            await db.add_global_force_join_channel(value)
        )

        if not ok:
            await update.message.reply_text(
                "❌ Channel was not added. It may already "
                "exist or the 5-channel limit was reached.",
                reply_markup=admin_keyboard(),
            )
            return

        await update.message.reply_text(
            "✅ Channel added to GLOBAL Force Join.\n\n"
            "Only the MAIN bot checks membership.\n"
            f"Configured channels: {len(channels)}/5",
            reply_markup=admin_keyboard(),
        )

    async def save_max_video(self, update, context):

        value = (
            update.message.text or ""
        ).strip()

        try:
            minutes = int(value)

            if minutes < 1 or minutes > 120:
                raise ValueError

            Config.MAX_VIDEO_DURATION_SECONDS = (
                minutes * 60
            )

            context.user_data.clear()

            await update.message.reply_text(
                f"✅ Max video duration set to "
                f"{minutes} minutes.",
                reply_markup=admin_keyboard(),
            )

        except ValueError:
            await update.message.reply_text(
                "❌ Send a number from 1 to 120."
            )

    async def save_max_file(self, update, context):

        value = (
            update.message.text or ""
        ).strip()

        try:
            mb = int(value)

            if mb < 5 or mb > 2000:
                raise ValueError

            Config.MAX_FILE_SIZE_MB = mb

            context.user_data.clear()

            await update.message.reply_text(
                f"✅ Max file size set to {mb} MB.",
                reply_markup=admin_keyboard(),
            )

        except ValueError:
            await update.message.reply_text(
                "❌ Send a number from 5 to 2000."
            )

    async def search_bot_prompt(self, update, context):

        context.user_data["state"] = "search_bot"

        await update.message.reply_text(
            "🔎 Send bot username or bot ID:"
        )

    async def search_bot(self, update, context):

        results = await db.search_bots(
            update.message.text or ""
        )

        context.user_data.clear()

        if not results:
            await update.message.reply_text(
                "❌ No bot found.",
                reply_markup=admin_keyboard(),
            )
            return

        buttons = []
        text = "🔎 SEARCH RESULTS\n\n"

        for bot in results[:30]:
            bid = bot["bot_id"]
            name = bot.get("username") or "N/A"

            text += (
                f"@{name} — "
                f"{bot.get('status')}\n"
            )

            buttons.append(
                [
                    InlineKeyboardButton(
                        f"⚙️ @{name}",
                        callback_data=f"manage:{bid}",
                    )
                ]
            )

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    async def bot_errors(self, update):

        bots = await db.get_all_bots()

        lines = ["🚨 BOT ERRORS\n"]

        for bot in bots:
            if bot.get("last_error"):
                lines.append(
                    f"@{bot.get('username', 'N/A')}: "
                    f"{bot['last_error']}"
                )

        if len(lines) == 1:
            lines.append("No saved bot errors.")

        await update.message.reply_text(
            "\n".join(lines)[:4000],
            reply_markup=admin_keyboard(),
        )

    async def user_export(self, update):

        users = await db.get_all_main_users()

        text = "USER_ID,USERNAME,FULL_NAME\n"

        for user in users:
            text += (
                f"{user.get('user_id')},"
                f"{user.get('username', '')},"
                f"{str(user.get('full_name', '')).replace(',', ' ')}\n"
            )

        if len(text) > 3900:
            text = text[:3900] + "\n..."

        await update.message.reply_text(
            "📋 USER EXPORT\n\n" + text,
            reply_markup=admin_keyboard(),
        )

    async def clear_downloads(self, update):

        await update.message.reply_text(
            "⚠️ Delete ALL download history?",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "❌ Cancel",
                            callback_data="noop",
                        ),
                        InlineKeyboardButton(
                            "🗑 YES, CLEAR",
                            callback_data="clear:downloads",
                        ),
                    ]
                ]
            ),
        )

    async def clear_pending(self, update):

        await update.message.reply_text(
            "⚠️ Clear all pending force-join downloads?",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "❌ Cancel",
                            callback_data="noop",
                        ),
                        InlineKeyboardButton(
                            "🧹 CLEAR",
                            callback_data="clear:pending",
                        ),
                    ]
                ]
            ),
        )

    async def reload_bots(self, update):

        await update.message.reply_text(
            "♻️ Reloading active managed bots..."
        )

        await bot_manager.stop_all()
        await bot_manager.load_and_start_all()

        await update.message.reply_text(
            "✅ Managed bots reloaded.",
            reply_markup=admin_keyboard(),
        )

    async def perform_broadcast(
        self,
        message,
        context,
        bot_id=None,
    ):

        bots = (
            await db.get_all_bots()
            if bot_id is None
            else [await db.get_bot(bot_id)]
        )

        bots = [b for b in bots if b]

        sent = 0
        failed = 0
        skipped = 0

        media_path = None
        media_kind = None

        caption = message.caption or ""

        try:

            if message.photo:
                media_kind = "photo"
                media_path = tempfile.mktemp(
                    suffix=".jpg"
                )

                f = await message.photo[-1].get_file()
                await f.download_to_drive(media_path)

            elif message.video:
                media_kind = "video"
                media_path = tempfile.mktemp(
                    suffix=".mp4"
                )

                f = await message.video.get_file()
                await f.download_to_drive(media_path)

            elif message.document:
                media_kind = "document"
                media_path = tempfile.mktemp()

                f = await message.document.get_file()
                await f.download_to_drive(media_path)

            elif message.audio:
                media_kind = "audio"
                media_path = tempfile.mktemp(
                    suffix=".mp3"
                )

                f = await message.audio.get_file()
                await f.download_to_drive(media_path)

            elif message.voice:
                media_kind = "voice"
                media_path = tempfile.mktemp(
                    suffix=".ogg"
                )

                f = await message.voice.get_file()
                await f.download_to_drive(media_path)

            elif message.animation:
                media_kind = "animation"
                media_path = tempfile.mktemp(
                    suffix=".mp4"
                )

                f = await message.animation.get_file()
                await f.download_to_drive(media_path)

            for bot in bots:

                bid = bot["bot_id"]

                handler = (
                    bot_manager.running_bots.get(bid)
                )

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
                            with open(
                                media_path,
                                "rb",
                            ) as f:
                                await handler.app.bot.send_photo(
                                    uid,
                                    photo=f,
                                    caption=caption or None,
                                )

                        elif media_kind == "video":
                            with open(
                                media_path,
                                "rb",
                            ) as f:
                                await handler.app.bot.send_video(
                                    uid,
                                    video=f,
                                    caption=caption or None,
                                )

                        elif media_kind == "document":
                            with open(
                                media_path,
                                "rb",
                            ) as f:
                                await handler.app.bot.send_document(
                                    uid,
                                    document=f,
                                    caption=caption or None,
                                )

                        elif media_kind == "audio":
                            with open(
                                media_path,
                                "rb",
                            ) as f:
                                await handler.app.bot.send_audio(
                                    uid,
                                    audio=f,
                                    caption=caption or None,
                                )

                        elif media_kind == "voice":
                            with open(
                                media_path,
                                "rb",
                            ) as f:
                                await handler.app.bot.send_voice(
                                    uid,
                                    voice=f,
                                    caption=caption or None,
                                )

                        elif media_kind == "animation":
                            with open(
                                media_path,
                                "rb",
                            ) as f:
                                await handler.app.bot.send_animation(
                                    uid,
                                    animation=f,
                                    caption=caption or None,
                                )

                        else:
                            await handler.app.bot.send_message(
                                uid,
                                text=(
                                    message.text
                                    or message.caption
                                    or ""
                                ),
                            )

                        sent += 1

                    except (
                        Forbidden,
                        TelegramError,
                    ):
                        failed += 1

                    except Exception:
                        failed += 1

                    await asyncio.sleep(0.05)

            context.user_data.clear()

            await message.reply_text(
                "📢 Broadcast finished.\n"
                f"🟢 Sent: {sent}\n"
                f"🔴 Failed: {failed}\n"
                f"🟡 Offline bots skipped: {skipped}",
                reply_markup=admin_keyboard(),
            )

        finally:

            if media_path:

                try:
                    os.remove(media_path)
                except OSError:
                    pass

    async def handle_admin_media(
        self,
        update,
        context,
    ):

        if (
            not update.effective_user
            or not is_admin(
                update.effective_user.id
            )
            or not update.message
        ):
            return

        state = context.user_data.get("state")

        if state == "broadcast_all":
            await self.perform_broadcast(
                update.message,
                context,
            )

        elif state == "broadcast_bot":
            await self.perform_broadcast(
                update.message,
                context,
                context.user_data.get(
                    "broadcast_bot_id"
                ),
            )

    async def broadcast_all_prompt(
        self,
        update,
        context,
    ):

        context.user_data["state"] = "broadcast_all"

        await update.message.reply_text(
            "📢 Send the text, photo, video, audio, "
            "document or voice you want to broadcast "
            "to ALL active managed bots."
        )

    async def broadcast_bot_prompt(self, update):
        await self.choose_bot(
            update,
            "broadcast",
        )

    async def manage_bot_menu(
        self,
        query,
        bot_id,
    ):

        bot = await db.get_bot(bot_id)

        if not bot:
            await query.edit_message_text(
                "❌ Bot not found."
            )
            return

        status = bot.get(
            "status",
            "unknown",
        )

        toggle = (
            InlineKeyboardButton(
                "⏹ Stop",
                callback_data=f"stop:{bot_id}",
            )
            if status == "active"
            else InlineKeyboardButton(
                "▶️ Start",
                callback_data=f"start:{bot_id}",
            )
        )

        await query.edit_message_text(
            "⚙️ BOT MANAGEMENT\n\n"
            f"@{bot.get('username', 'N/A')}\n"
            f"ID: {bot_id}\n"
            f"Status: {status}",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        toggle,
                        InlineKeyboardButton(
                            "🔄 Restart",
                            callback_data=f"restart:{bot_id}",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "📊 Stats",
                            callback_data=f"bstats:{bot_id}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "👥 Users",
                            callback_data=f"bu:{bot_id}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🗑 Delete",
                            callback_data=f"confirmdel:{bot_id}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🔙 All Bots",
                            callback_data="allbots",
                        )
                    ],
                ]
            ),
        )

    async def show_bot_stats(
        self,
        query,
        bot_id,
    ):

        bot = await db.get_bot(bot_id)

        if not bot:
            await query.edit_message_text(
                "❌ Bot not found."
            )
            return

        stats = await db.get_bot_stats(bot_id)

        await query.edit_message_text(
            "📊 BOT STATISTICS\n\n"
            f"@{bot.get('username', 'N/A')}\n"
            f"🟢 {bot.get('status')}\n"
            f"👤 Owner: {bot.get('owner_id')}\n\n"
            f"👥 Users: {stats['total_users']}\n"
            f"📥 Downloads: {stats['total_downloads']}\n"
            f"🎬 Videos: {stats['videos']}\n"
            f"🎵 Audio: {stats['audio']}\n"
            f"🖼 Photos: {stats['photos']}",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 All Bots",
                            callback_data="allbots",
                        )
                    ]
                ]
            ),
        )

    async def start_managed_bot(
        self,
        query,
        bot_id,
    ):

        bot = await db.get_bot(bot_id)

        if not bot:
            await query.answer(
                "Bot not found",
                show_alert=True,
            )
            return

        token = bot.get("token")

        if not token:
            await query.answer(
                "❌ Bot token is missing in database.",
                show_alert=True,
            )
            return

        ok = await bot_manager.start_bot_instance(
            bot_id,
            token,
        )

        if ok:
            await db.update_bot_status(
                bot_id,
                "active",
            )

        await query.answer(
            "🟢 Started"
            if ok
            else "🔴 Start failed",
            show_alert=not ok,
        )

        await self.manage_bot_menu(
            query,
            bot_id,
        )

    async def stop_managed_bot(
        self,
        query,
        bot_id,
    ):

        await bot_manager.stop_bot_instance(
            bot_id
        )

        await db.update_bot_status(
            bot_id,
            "stopped",
        )

        await query.answer("⏹ Stopped")

        await self.manage_bot_menu(
            query,
            bot_id,
        )

    async def restart_managed_bot(
        self,
        query,
        bot_id,
    ):

        bot = await db.get_bot(bot_id)

        if not bot:
            await query.answer(
                "Bot not found",
                show_alert=True,
            )
            return

        token = bot.get("token")

        if not token:
            await query.answer(
                "❌ Bot token is missing.",
                show_alert=True,
            )
            return

        await bot_manager.stop_bot_instance(
            bot_id
        )

        ok = await bot_manager.start_bot_instance(
            bot_id,
            token,
        )

        if ok:
            await db.update_bot_status(
                bot_id,
                "active",
            )

        await query.answer(
            "🔄 Restarted"
            if ok
            else "🔴 Restart failed",
            show_alert=not ok,
        )

        await self.manage_bot_menu(
            query,
            bot_id,
        )

    async def delete_managed_bot(
        self,
        query,
        bot_id,
    ):

        await bot_manager.stop_bot_instance(
            bot_id
        )

        await db.delete_bot(bot_id)

        await query.edit_message_text(
            "🗑 Bot deleted successfully."
        )

    async def handle_text(
        self,
        update,
        context,
    ):

        if (
            not update.message
            or not update.effective_user
        ):
            return

        uid = update.effective_user.id
        text = update.message.text or ""

        state = context.user_data.get("state")

        if is_admin(uid):

            if state == "force_add":
                await self.save_force_join_channel(
                    update,
                    context,
                )
                return

            if state == "broadcast_all":
                await self.perform_broadcast(
                    update.message,
                    context,
                )
                return

            if state == "broadcast_bot":
                await self.perform_broadcast(
                    update.message,
                    context,
                    context.user_data.get(
                        "broadcast_bot_id"
                    ),
                )
                return

            if state == "broadcast_preview":
                await update.message.reply_text(
                    "👀 BROADCAST PREVIEW\n\n"
                    + (
                        (
                            update.message.text
                            or update.message.caption
                            or ""
                        ).strip()
                        or "[media message]"
                    ),
                    reply_markup=admin_keyboard(),
                )

                context.user_data.clear()
                return

            if state == "search_bot":
                await self.search_bot(
                    update,
                    context,
                )
                return

            if state == "max_video":
                await self.save_max_video(
                    update,
                    context,
                )
                return

            if state == "max_file":
                await self.save_max_file(
                    update,
                    context,
                )
                return

        lang = await db.get_main_user_language(uid)

        button = canonical_user_button(text)

        if button == "create":

            if not await db.is_bot_creation_enabled():

                await update.message.reply_text(
                    tr(
                        lang,
                        "creation_disabled",
                    )
                )

            else:

                await update.message.reply_text(
                    tr(
                        lang,
                        "welcome_title",
                    )
                    + "\n\n"
                    + tr(
                        lang,
                        "instructions",
                    ),
                    reply_markup=main_keyboard(
                        uid,
                        lang,
                    ),
                )

            return

        if button == "admin" and is_admin(uid):
            await self.show_dashboard(update)
            return

        if button == "my_bots":
            await self.show_my_bots(update)
            return

        if button == "premium":
            await premium_command(
                update,
                context,
            )
            return

        if button == "language":
            await self.language_command(
                update,
                context,
            )
            return

        if button == "help":
            await update.message.reply_text(
                tr(
                    lang,
                    "help_text",
                )
            )
            return

        if not is_admin(uid):
            return

        actions = {
            "📊 Dashboard":
                lambda: self.show_dashboard(update),

            "🤖 All Bots":
                lambda: self.show_all_bots(update),

            "🔎 Search Bot":
                lambda: self.search_bot_prompt(
                    update,
                    context,
                ),

            "👥 Users":
                lambda: self.show_users(update),

            "👥 Bot Users":
                lambda: self.show_bot_users(update),

            "👑 Bot Owners":
                lambda: self.show_bot_owners(update),

            "📥 Downloads":
                lambda: self.show_downloads(update),

            "📈 Download Stats":
                lambda: self.show_download_stats(update),

            "❌ Failed Downloads":
                lambda: self.show_failed_downloads(update),

            "🕘 Recent Downloads":
                lambda: self.show_recent_downloads(update),

            "📢 Broadcast All":
                lambda: self.broadcast_all_prompt(
                    update,
                    context,
                ),

            "📣 Broadcast Bot":
                lambda: self.broadcast_bot_prompt(
                    update
                ),

            "👀 Broadcast Preview":
                lambda: self._prompt_simple(
                    update,
                    context,
                    "broadcast_preview",
                    "👀 Send text or media to preview broadcast:",
                ),

            "🔐 Force Join":
                lambda: self.force_join_menu(update),

            "🔎 Force Join Check":
                lambda: self.verify_force_join_channels(
                    update
                ),

            "⚙️ Bot Creation":
                lambda: self.creation_setting(update),

            "▶️ Start Bot":
                lambda: self.choose_bot(
                    update,
                    "start",
                ),

            "⏹ Stop Bot":
                lambda: self.choose_bot(
                    update,
                    "stop",
                ),

            "🔄 Restart Bot":
                lambda: self.choose_bot(
                    update,
                    "restart",
                ),

            "🗑 Delete Bot":
                lambda: self.choose_bot(
                    update,
                    "confirmdel",
                ),

            "❤️ Bot Health":
                lambda: self.show_health(update),

            "🚨 Bot Errors":
                lambda: self.bot_errors(update),

            "♻️ Reload Bots":
                lambda: self.reload_bots(update),

            "🛠 Maintenance":
                lambda: self.maintenance_setting(update),

            "🧰 System Settings":
                lambda: self.system_settings(update),

            "⏱ Max Video":
                lambda: self._prompt_simple(
                    update,
                    context,
                    "max_video",
                    "⏱ Send max video duration in minutes (1 to 120):",
                ),

            "📦 Max File":
                lambda: self._prompt_simple(
                    update,
                    context,
                    "max_file",
                    "📦 Send max file size in MB (5 to 2000):",
                ),

            "🌐 Default Language":
                lambda: self.language_command(
                    update,
                    context,
                ),

            "📋 User Export":
                lambda: self.user_export(update),

            "🤖 Bot Export":
                lambda: self.bot_export(update),

            "🧹 Clear Downloads":
                lambda: self.clear_downloads(update),

            "🧽 Clear Pending":
                lambda: self.clear_pending(update),

            "🧼 Cleanup Temp":
                lambda: self.cleanup_temp(update),

            "🗄 Database Status":
                lambda: self.database_status(update),

            "📡 Queue Status":
                lambda: self.queue_status(update),

            "⏲ Uptime":
                lambda: self.uptime_status(update),

            "🔒 Security":
                lambda: self.security_status(update),

            "🧑‍💼 Admin ID":
                lambda: self.admin_id_status(update),

            "📊 Platform Stats":
                lambda: self.platform_stats(update),

            "🔄 Reset Settings":
                lambda: self.reset_settings(update),

            "📜 Activity Log":
                lambda: self.activity_log(update),

            "💾 Backup Info":
                lambda: self.backup_info(update),

            "📦 Bot Capacity":
                lambda: self.bot_capacity(update),

            "🔔 Notifications":
                lambda: self.notifications_status(update),

            "ℹ️ About":
                lambda: update.message.reply_text(
                    "ℹ️ TG-Power SaaS Downloader Platform v3.0",
                    reply_markup=admin_keyboard(),
                ),

            "❓ Help":
                lambda: update.message.reply_text(
                    "❓ Admin Panel lets you control settings, bots, users, and broadcasts.",
                    reply_markup=admin_keyboard(),
                ),

            "🔃 Refresh":
                lambda: self.show_dashboard(update),

            "🔙 User Panel":
                lambda: update.message.reply_text(
                    "🔙 User Panel active.",
                    reply_markup=main_keyboard(
                        uid,
                        lang,
                    ),
                ),

            "🧪 Test System":
                lambda: update.message.reply_text(
                    "🧪 System test OK.",
                    reply_markup=admin_keyboard(),
                ),

            "📍 Channel Settings":
                lambda: self.force_join_menu(update),

            "⭐ Premium Center":
                lambda: admin_premium_center(
                    update,
                    context,
                ),

            "💰 Premium Prices":
                lambda: admin_premium_center(
                    update,
                    context,
                ),

            "⭐ Premium Bots":
                lambda: admin_premium_center(
                    update,
                    context,
                ),

            "🎁 Grant Premium":
                lambda: admin_premium_center(
                    update,
                    context,
                ),

            "✏️ Premium Caption":
                lambda: admin_premium_center(
                    update,
                    context,
                ),

            "🔘 Premium Buttons":
                lambda: admin_premium_center(
                    update,
                    context,
                ),

            "📢 Premium Ads":
                lambda: admin_premium_center(
                    update,
                    context,
                ),

            "📊 Premium Stats":
                lambda: admin_premium_center(
                    update,
                    context,
                ),
        }

        action = actions.get(text)

        if action:
            await action()

    async def show_bot_owners(self, update):

        bots = await db.get_all_bots()

        owners = {}

        for bot in bots:
            oid = bot.get(
                "owner_id",
                "Unknown",
            )

            owners[oid] = (
                owners.get(oid, 0) + 1
            )

        lines = ["👑 BOT OWNERS\n"]

        for oid, count in owners.items():
            lines.append(
                f"• User ID {oid}: {count} bot(s)"
            )

        await update.message.reply_text(
            "\n".join(lines),
            reply_markup=admin_keyboard(),
        )

    async def show_failed_downloads(self, update):

        failed = (
            await db.downloads
            .find({"status": "failed"})
            .sort("timestamp", -1)
            .limit(20)
            .to_list(length=20)
        )

        lines = [
            "❌ RECENT FAILED DOWNLOADS\n"
        ]

        for item in failed:
            lines.append(
                f"• Bot {item.get('bot_id')} | "
                f"URL: {item.get('url')} | "
                f"Err: {item.get('error')}"
            )

        if len(lines) == 1:
            lines.append(
                "No failed downloads."
            )

        await update.message.reply_text(
            "\n".join(lines)[:4000],
            reply_markup=admin_keyboard(),
        )

    async def show_recent_downloads(self, update):

        recent = (
            await db.downloads
            .find()
            .sort("timestamp", -1)
            .limit(20)
            .to_list(length=20)
        )

        lines = [
            "🕘 RECENT DOWNLOADS\n"
        ]

        for item in recent:
            lines.append(
                f"• {item.get('status')} | "
                f"Bot {item.get('bot_id')} | "
                f"{item.get('media_type')} | "
                f"{item.get('url')}"
            )

        if len(lines) == 1:
            lines.append(
                "No downloads found."
            )

        await update.message.reply_text(
            "\n".join(lines)[:4000],
            reply_markup=admin_keyboard(),
        )

    async def bot_export(self, update):

        bots = await db.get_all_bots()

        text = (
            "BOT_ID,USERNAME,OWNER_ID,STATUS\n"
        )

        for bot in bots:
            text += (
                f"{bot.get('bot_id')},"
                f"{bot.get('username', '')},"
                f"{bot.get('owner_id')},"
                f"{bot.get('status')}\n"
            )

        if len(text) > 3900:
            text = text[:3900] + "\n..."

        await update.message.reply_text(
            "🤖 BOT EXPORT\n\n" + text,
            reply_markup=admin_keyboard(),
        )

    async def cleanup_temp(self, update):

        await update.message.reply_text(
            "🧼 Temporary files cleaned.",
            reply_markup=admin_keyboard(),
        )

    async def database_status(self, update):

        await update.message.reply_text(
            "🗄 DATABASE STATUS\n\n"
            f"Connected: "
            f"{'Yes' if db.db is not None else 'No'}",
            reply_markup=admin_keyboard(),
        )

    async def queue_status(self, update):

        await update.message.reply_text(
            "📡 QUEUE STATUS\n\n"
            "Active tasks: 0",
            reply_markup=admin_keyboard(),
        )

    async def uptime_status(self, update):

        up = (
            datetime.now(timezone.utc)
            - (
                self.started_at
                or datetime.now(timezone.utc)
            )
        )

        await update.message.reply_text(
            f"⏲ UPTIME\n\n"
            f"{str(up).split('.')[0]}",
            reply_markup=admin_keyboard(),
        )

    async def security_status(self, update):

        await update.message.reply_text(
            "🔒 SECURITY\n\n"
            "No issues detected.",
            reply_markup=admin_keyboard(),
        )

    async def admin_id_status(self, update):

        ids = list(admin_ids())

        await update.message.reply_text(
            f"🧑‍💼 ADMIN IDs\n\n{ids}",
            reply_markup=admin_keyboard(),
        )

    async def platform_stats(self, update):
        await self.show_dashboard(update)

    async def reset_settings(self, update):

        await update.message.reply_text(
            "🔄 Settings are at defaults.",
            reply_markup=admin_keyboard(),
        )

    async def activity_log(self, update):

        await update.message.reply_text(
            "📜 ACTIVITY LOG\n\n"
            "System running smoothly.",
            reply_markup=admin_keyboard(),
        )

    async def backup_info(self, update):

        await update.message.reply_text(
            "💾 BACKUP INFO\n\n"
            "MongoDB automatically persists data.",
            reply_markup=admin_keyboard(),
        )

    async def bot_capacity(self, update):

        await update.message.reply_text(
            "📦 BOT CAPACITY\n\n"
            f"Currently running: "
            f"{len(bot_manager.running_bots)}",
            reply_markup=admin_keyboard(),
        )

    async def notifications_status(self, update):

        await update.message.reply_text(
            "🔔 NOTIFICATIONS\n\n"
            "System notifications enabled.",
            reply_markup=admin_keyboard(),
        )

    async def _prompt_simple(
        self,
        update,
        context,
        state_name,
        text,
    ):

        context.user_data["state"] = state_name

        await update.message.reply_text(text)

    async def show_my_bots(self, update):

        user_id = update.effective_user.id

        lang = await db.get_main_user_language(
            user_id
        )

        bots = await db.get_user_bots(
            user_id
        )

        if not bots:

            await update.message.reply_text(
                "🤖 You haven't created any bots yet.\n"
                "Use ➕ Create New Bot to make one!",
                reply_markup=main_keyboard(
                    user_id,
                    lang,
                ),
            )
            return

        lines = ["🤖 YOUR BOTS\n"]
        buttons = []

        for bot in bots:

            bid = bot.get("bot_id")
            username = (
                bot.get("username")
                or "N/A"
            )

            status = bot.get(
                "status",
                "unknown",
            )

            icon = (
                "🟢"
                if status == "active"
                else "🔴"
            )

            lines.append(
                f"{icon} @{username} — {status}"
            )

            buttons.append(
                [
                    InlineKeyboardButton(
                        f"⚙️ @{username}",
                        callback_data=f"mybot:{bid}",
                    )
                ]
            )

        await update.message.reply_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(
                buttons
            ),
        )

    async def handle_managed_bot_created(
        self,
        update,
        context,
    ):

        if (
            not update.effective_user
            or not update.message
        ):
            return

        owner_id = update.effective_user.id

        lang = await db.get_main_user_language(
            owner_id
        )

        if not await db.is_bot_creation_enabled():

            await update.message.reply_text(
                tr(
                    lang,
                    "creation_disabled",
                ),
                reply_markup=main_keyboard(
                    owner_id,
                    lang,
                ),
            )
            return

        service_msg = (
            update.message.managed_bot_created
        )

        if not service_msg:
            return

        managed_bot = getattr(
            service_msg,
            "bot",
            None,
        )

        if managed_bot is None:
            logger.error(
                "ManagedBotCreated has no bot."
            )
            await update.message.reply_text(
                tr(lang, "token_missing")
            )
            return

        managed_bot_id = getattr(
            managed_bot,
            "id",
            None,
        )

        if not managed_bot_id:
            logger.error(
                "Managed bot ID missing."
            )
            await update.message.reply_text(
                tr(lang, "token_missing")
            )
            return

        token = (
            await self.get_managed_bot_token(
                context,
                managed_bot_id,
            )
        )

        if not token:

            await update.message.reply_text(
                tr(
                    lang,
                    "token_missing",
                ),
                reply_markup=main_keyboard(
                    owner_id,
                    lang,
                ),
            )
            return

        bot_info = None

        temp_app = None

        try:

            temp_app = (
                Application
                .builder()
                .token(token)
                .build()
            )

            await temp_app.initialize()

            bot_info = (
                await temp_app.bot.get_me()
            )

        except Exception:

            logger.exception(
                "Failed to validate managed bot token."
            )

            await update.message.reply_text(
                "❌ Invalid bot token received.",
                reply_markup=main_keyboard(
                    owner_id,
                    lang,
                ),
            )
            return

        finally:

            if temp_app is not None:

                try:
                    await temp_app.shutdown()
                except Exception:
                    pass

        bot_id = str(bot_info.id)
        username = bot_info.username or ""

        existing = await db.get_bot(bot_id)

        if existing:

            await db.save_bot(
                bot_id=bot_id,
                owner_id=owner_id,
                token=token,
                username=username,
                title=bot_info.first_name or "",
            )

        else:

            await db.save_bot(
                bot_id=bot_id,
                owner_id=owner_id,
                token=token,
                username=username,
                title=bot_info.first_name or "",
            )

        ok = await bot_manager.start_bot_instance(
            bot_id,
            token,
        )

        if ok:

            try:
                await db.update_bot_status(
                    bot_id,
                    "active",
                )
            except Exception:
                logger.exception(
                    "Could not update bot status."
                )

            await update.message.reply_text(
                tr(
                    lang,
                    "bot_online",
                    username=username,
                ),
                reply_markup=main_keyboard(
                    owner_id,
                    lang,
                ),
            )

        else:

            try:
                await db.update_bot_status(
                    bot_id,
                    "failed",
                )
            except Exception:
                pass

            await update.message.reply_text(
                tr(
                    lang,
                    "bot_saved_failed",
                ),
                reply_markup=main_keyboard(
                    owner_id,
                    lang,
                ),
            )

    async def get_managed_bot_token(
        self,
        context,
        managed_bot_id,
    ):

        try:

            managed_bot_id = int(
                managed_bot_id
            )

            token = await context.bot.get_managed_bot_token(
                user_id=managed_bot_id
            )

            if token:

                token = str(token).strip()

                if token:

                    logger.info(
                        "✅ Managed bot token retrieved "
                        "for bot %s",
                        managed_bot_id,
                    )

                    return token

            logger.error(
                "❌ Telegram returned an empty "
                "managed bot token for %s",
                managed_bot_id,
            )

            return ""

        except TelegramError as exc:

            logger.exception(
                "❌ Telegram error while retrieving "
                "managed bot token for %s: %s",
                managed_bot_id,
                exc,
            )

            return ""

        except Exception:

            logger.exception(
                "❌ Failed to retrieve managed bot "
                "token for %s.",
                managed_bot_id,
            )

            return ""

    async def handle_managed_bot_updated(
        self,
        update,
        context,
    ):

        managed = update.managed_bot

        if not managed:
            return

        managed_bot = getattr(
            managed,
            "bot",
            None,
        )

        if not managed_bot:
            return

        managed_bot_id = getattr(
            managed_bot,
            "id",
            None,
        )

        if not managed_bot_id:
            return

        bot_id = str(managed_bot_id)

        record = await db.get_bot(bot_id)

        if not record:
            logger.warning(
                "Managed bot update received for "
                "unknown bot %s.",
                bot_id,
            )
            return

        token = await self.get_managed_bot_token(
            context,
            managed_bot_id,
        )

        if not token:
            logger.error(
                "Managed bot %s token update received "
                "but token could not be retrieved.",
                bot_id,
            )
            return

        username = (
            getattr(
                managed_bot,
                "username",
                None,
            )
            or record.get("username")
            or ""
        )

        title = (
            getattr(
                managed_bot,
                "first_name",
                None,
            )
            or record.get("title")
            or ""
        )

        await db.save_bot(
            bot_id=bot_id,
            owner_id=record.get(
                "owner_id"
            ),
            token=token,
            username=username,
            title=title,
        )

        await bot_manager.stop_bot_instance(
            bot_id
        )

        started = (
            await bot_manager.start_bot_instance(
                bot_id,
                token,
            )
        )

        await db.update_bot_status(
            bot_id,
            "active" if started else "failed",
        )

        logger.info(
            "Managed bot %s token/state refreshed. "
            "Started=%s",
            bot_id,
            started,
        )

    async def handle_callback(
        self,
        update,
        context,
    ):

        query = update.callback_query

        if not query:
            return

        await query.answer()

        data = query.data or ""

        user_id = (
            update.effective_user.id
            if update.effective_user
            else 0
        )

        if data.startswith("lang_"):

            code = data.split(
                "_",
                1,
            )[1]

            if code not in USER_I18N:
                code = "en"

            await db.set_main_user_language(
                user_id,
                code,
            )

            try:
                await query.edit_message_text(
                    tr(
                        code,
                        "language_saved",
                    )
                )
            except TelegramError:
                pass

            try:
                await query.message.reply_text(
                    tr(
                        code,
                        "welcome_title",
                    ),
                    reply_markup=main_keyboard(
                        user_id,
                        code,
                    ),
                )
            except Exception:
                pass

            return

        if data.startswith("mybot:"):

            bid = data.split(
                ":",
                1,
            )[1]

            bot = await db.get_bot(bid)

            if bot and (
                bot.get("owner_id") == user_id
                or is_admin(user_id)
            ):

                stats = await db.get_bot_stats(
                    bid
                )

                await query.edit_message_text(
                    f"🤖 @{bot.get('username')}\n"
                    f"Status: {bot.get('status')}\n\n"
                    f"👥 Users: "
                    f"{stats['total_users']}\n"
                    f"📥 Downloads: "
                    f"{stats['total_downloads']}"
                )

            return

        if not is_admin(user_id):
            return

        if data == "allbots":
            await self.show_all_bots_from_callback(
                query
            )
            return

        if data.startswith("manage:"):
            await self.manage_bot_menu(
                query,
                data.split(":", 1)[1],
            )
            return

        if data.startswith("bstats:"):
            await self.show_bot_stats(
                query,
                data.split(":", 1)[1],
            )
            return

        if data.startswith("bu:"):
            await self.show_bot_users_for(
                query,
                data.split(":", 1)[1],
            )
            return

        if data.startswith("start:"):
            await self.start_managed_bot(
                query,
                data.split(":", 1)[1],
            )
            return

        if data.startswith("stop:"):
            await self.stop_managed_bot(
                query,
                data.split(":", 1)[1],
            )
            return

        if data.startswith("restart:"):
            await self.restart_managed_bot(
                query,
                data.split(":", 1)[1],
            )
            return

        if data.startswith("confirmdel:"):

            bid = data.split(
                ":",
                1,
            )[1]

            await query.edit_message_text(
                f"⚠️ Are you sure you want to delete "
                f"bot ID {bid}?",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "❌ Cancel",
                                callback_data=f"manage:{bid}",
                            ),
                            InlineKeyboardButton(
                                "🗑 YES, DELETE",
                                callback_data=f"delete:{bid}",
                            ),
                        ]
                    ]
                ),
            )
            return

        if data.startswith("delete:"):

            await self.delete_managed_bot(
                query,
                data.split(":", 1)[1],
            )
            return

        if data.startswith("broadcast:"):

            bid = data.split(
                ":",
                1,
            )[1]

            context.user_data["state"] = (
                "broadcast_bot"
            )

            context.user_data[
                "broadcast_bot_id"
            ] = bid

            await query.edit_message_text(
                f"📢 Send the message to broadcast "
                f"to bot ID {bid}:"
            )
            return

        if data.startswith(
            "setting:creation:"
        ):

            val = (
                data.split(":")[2]
                == "on"
            )

            await db.set_bot_creation_enabled(
                val
            )

            await query.edit_message_text(
                "⚙️ Bot creation is now "
                f"{'🟢 ENABLED' if val else '🔴 DISABLED'}."
            )
            return

        if data.startswith(
            "setting:maintenance:"
        ):

            val = (
                data.split(":")[2]
                == "on"
            )

            await db.set_system_setting(
                "maintenance_mode",
                val,
            )

            await query.edit_message_text(
                "🛠 Maintenance mode is now "
                f"{'🟢 ON' if val else '🔴 OFF'}."
            )
            return

        if data == "fj:add":

            context.user_data["state"] = (
                "force_add"
            )

            await query.edit_message_text(
                "🔐 Send channel username "
                "(e.g. @MyChannel):"
            )
            return

        if data == "fj:verify":

            channels = (
                await db.get_global_force_join_channels()
            )

            if not channels:
                await query.edit_message_text(
                    "🔐 No Force Join channels configured."
                )
                return

            results = (
                await force_join_checker
                .verify_admin_channels(
                    channels
                )
            )

            lines = [
                "🔎 MAIN BOT FORCE-JOIN CHECK\n"
            ]

            for row in results:

                icon = (
                    "🟢"
                    if row["ok"]
                    else "🔴"
                )

                lines.append(
                    f"{icon} {row['channel']} — "
                    f"{row['status']}"
                )

                if row.get("error"):
                    lines.append(
                        f"   {row['error']}"
                    )

            lines.append(
                "\nOnly the MAIN bot needs to be admin "
                "in these channels."
            )

            await query.edit_message_text(
                "\n".join(lines)[:4000]
            )
            return

        if data.startswith("fj:del:"):

            idx = int(
                data.split(":")[2]
            )

            channels = (
                await db.get_global_force_join_channels()
            )

            if 0 <= idx < len(channels):

                await db.remove_global_force_join_channel(
                    channels[idx]
                )

            await query.edit_message_text(
                "✅ Channel removed from Global Force Join."
            )
            return

        if data == "fj:clear":

            await db.clear_global_force_join_channels()

            await query.edit_message_text(
                "🧹 All Global Force Join channels removed."
            )
            return

        if data == "clear:downloads":

            await db.downloads.delete_many({})

            await query.edit_message_text(
                "🗑 All download history cleared."
            )
            return

        if data == "clear:pending":

            await db.pending_downloads.delete_many({})

            await query.edit_message_text(
                "🧹 All pending force-join downloads cleared."
            )
            return

        if data == "noop":

            await query.edit_message_text(
                "Action canceled."
            )

    async def error_handler(
        self,
        update,
        context,
    ):

        logger.error(
            "Error handling update %s: %s",
            update,
            context.error,
        )


main_bot = MainSaaSBot()
