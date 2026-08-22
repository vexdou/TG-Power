import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from database import db
from downloader import downloader

logger = logging.getLogger(__name__)

LANGUAGES = {
    "en": {
        "welcome": "👋 Welcome! Send me a public video/media link from YouTube, TikTok, Instagram, Facebook, X/Twitter, Pinterest or Snapchat.",
        "invalid": "❌ Please send a valid http/https link.",
        "downloading": "⏳ Downloading media... Please wait.",
        "error": "❌ Error:",
    },
    "so": {
        "welcome": "👋 Soo dhawoow! Ii soo dir link public ah oo YouTube, TikTok, Instagram, Facebook, X/Twitter, Pinterest ama Snapchat ah.",
        "invalid": "❌ Fadlan soo dir link http/https sax ah.",
        "downloading": "⏳ Media-ga ayaa la soo dejinayaa... Fadlan sug.",
        "error": "❌ Cilad:",
    },
    "ar": {
        "welcome": "👋 أهلاً بك! أرسل رابط وسائط عام من YouTube أو TikTok أو Instagram أو Facebook أو X أو Pinterest أو Snapchat.",
        "invalid": "❌ أرسل رابط http/https صحيح.",
        "downloading": "⏳ جارٍ التنزيل... يرجى الانتظار.",
        "error": "❌ خطأ:",
    },
    "es": {
        "welcome": "👋 ¡Bienvenido! Envíame un enlace público de YouTube, TikTok, Instagram, Facebook, X, Pinterest o Snapchat.",
        "invalid": "❌ Envía un enlace http/https válido.",
        "downloading": "⏳ Descargando... Por favor espera.",
        "error": "❌ Error:",
    },
    "fr": {
        "welcome": "👋 Bienvenue ! Envoyez un lien public YouTube, TikTok, Instagram, Facebook, X, Pinterest ou Snapchat.",
        "invalid": "❌ Envoyez un lien http/https valide.",
        "downloading": "⏳ Téléchargement en cours...",
        "error": "❌ Erreur:",
    },
    "tr": {
        "welcome": "👋 Hoş geldiniz! YouTube, TikTok, Instagram, Facebook, X, Pinterest veya Snapchat bağlantısı gönderin.",
        "invalid": "❌ Geçerli bir http/https bağlantısı gönderin.",
        "downloading": "⏳ İndiriliyor...",
        "error": "❌ Hata:",
    },
}


class ManagedBotHandler:
    def __init__(self, bot_id: int, token: str):
        self.bot_id = int(bot_id)
        self.token = token

        self.app = (
            Application.builder()
            .token(token)
            .concurrent_updates(True)
            .build()
        )

        self._setup_handlers()

    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CommandHandler("broadcast", self.broadcast_command))

        self.app.add_handler(
            CallbackQueryHandler(self.handle_callbacks)
        )

        self.app.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.handle_message,
            )
        )

        self.app.add_error_handler(self.error_handler)

    async def start_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        if not update.effective_user or not update.message:
            return

        try:
            user = update.effective_user

            await db.save_bot_user(
                self.bot_id,
                user.id,
                user.username or "",
                user.full_name or "",
            )

            bot_user = await db.get_bot_user(
                self.bot_id,
                user.id,
            )
            lang = (bot_user or {}).get("language", "en")
            texts = LANGUAGES.get(lang, LANGUAGES["en"])

            buttons = [
                [
                    InlineKeyboardButton(
                        "English 🇬🇧",
                        callback_data="msetlang_en",
                    ),
                    InlineKeyboardButton(
                        "Soomaali 🇸🇴",
                        callback_data="msetlang_so",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "العربية 🇸🇦",
                        callback_data="msetlang_ar",
                    ),
                    InlineKeyboardButton(
                        "Español 🇪🇸",
                        callback_data="msetlang_es",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "Français 🇫🇷",
                        callback_data="msetlang_fr",
                    ),
                    InlineKeyboardButton(
                        "Türkçe 🇹🇷",
                        callback_data="msetlang_tr",
                    ),
                ],
            ]

            await update.message.reply_text(
                texts["welcome"],
                reply_markup=InlineKeyboardMarkup(buttons),
            )

        except Exception:
            logger.exception("Managed /start error")

            try:
                await update.message.reply_text(
                    "👋 Welcome! Send me a public media link."
                )
            except Exception:
                pass

    async def handle_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        if not update.message or not update.effective_user:
            return

        url = (update.message.text or "").strip()

        if not (
            url.startswith("http://")
            or url.startswith("https://")
        ):
            await update.message.reply_text(
                "❌ Please send a valid media link."
            )
            return

        user = update.effective_user

        await db.save_bot_user(
            self.bot_id,
            user.id,
            user.username or "",
            user.full_name or "",
        )

        status_msg = await update.message.reply_text(
            "⏳ **Downloading media... Please wait.**",
            parse_mode="Markdown",
        )

        result = await downloader.download(
            url=url,
            user_id=user.id,
            bot_id=self.bot_id,
        )

        if not result.get("success"):
            error_text = str(
                result.get("error", "Unknown download error")
            )

            try:
                await status_msg.edit_text(
                    f"❌ **Download failed:**\n`{error_text[:3500]}`",
                    parse_mode="Markdown",
                )
            except Exception:
                await status_msg.edit_text(
                    f"❌ Download failed:\n{error_text[:3500]}"
                )
            return

        file_path = result.get("file_path")
        title = result.get("title") or "Downloaded Media"
        media_type = result.get("media_type", "video")

        if not file_path:
            await status_msg.edit_text(
                "❌ Download completed but no file was produced."
            )
            return

        try:
            if media_type == "audio":
                with open(file_path, "rb") as audio_file:
                    await update.message.reply_audio(
                        audio=audio_file,
                        title=title[:64],
                    )
            else:
                with open(file_path, "rb") as video_file:
                    await update.message.reply_video(
                        video=video_file,
                        caption=f"✅ {title[:900]}",
                        supports_streaming=True,
                    )

            await db.log_download(
                self.bot_id,
                user.id,
                result.get("platform", "general"),
                media_type,
            )

            try:
                await status_msg.delete()
            except Exception:
                pass

        except Exception as exc:
            logger.exception("Telegram upload error")

            try:
                await status_msg.edit_text(
                    "❌ Telegram could not upload this file. "
                    "The downloaded file may be larger than Telegram's bot upload limit."
                )
            except Exception:
                pass

        finally:
            downloader.cleanup(file_path)

    async def stats_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        if not update.message or not update.effective_user:
            return

        try:
            bot_data = await db.get_bot(self.bot_id)

            if (
                not bot_data
                or bot_data.get("owner_id")
                != update.effective_user.id
            ):
                return

            stats = await db.get_bot_stats(self.bot_id)

            await update.message.reply_text(
                "📊 **BOT OWNER STATS**\n\n"
                f"👥 Users: `{stats['total_users']}`\n"
                f"📥 Downloads: `{stats['total_downloads']}`",
                parse_mode="Markdown",
            )

        except Exception:
            logger.exception("Stats error")

    async def broadcast_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        if not update.message or not update.effective_user:
            return

        try:
            bot_data = await db.get_bot(self.bot_id)

            if (
                not bot_data
                or bot_data.get("owner_id")
                != update.effective_user.id
            ):
                return

            if not context.args:
                await update.message.reply_text(
                    "Usage: /broadcast Your message"
                )
                return

            text = " ".join(context.args)
            users = await db.get_all_bot_users(self.bot_id)

            progress = await update.message.reply_text(
                f"📢 Broadcasting to {len(users)} users..."
            )

            sent = 0
            failed = 0

            for user in users:
                try:
                    await self.app.bot.send_message(
                        chat_id=user["user_id"],
                        text=text,
                    )
                    sent += 1
                    await asyncio.sleep(0.05)
                except Exception:
                    failed += 1

            await progress.edit_text(
                f"✅ Broadcast finished.\n\n"
                f"Sent: {sent}\n"
                f"Failed: {failed}"
            )

        except Exception:
            logger.exception("Broadcast error")

    async def handle_callbacks(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        query = update.callback_query

        if not query:
            return

        try:
            await query.answer()

            if query.data.startswith("msetlang_"):
                lang_code = query.data.split("_", 1)[1]

                if lang_code not in LANGUAGES:
                    lang_code = "en"

                await db.set_user_language(
                    self.bot_id,
                    query.from_user.id,
                    lang_code,
                )

                texts = LANGUAGES[lang_code]

                await query.message.edit_text(
                    f"✅ Language changed.\n\n{texts['welcome']}"
                )

        except Exception:
            logger.exception("Callback error")

    async def error_handler(
        self,
        update: object,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        logger.error(
            "Managed bot %s exception: %s",
            self.bot_id,
            context.error,
            exc_info=context.error,
        )
