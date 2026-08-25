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
        "welcome": (
            "👋 Welcome! Send me a public video/media link from "
            "YouTube, TikTok, Instagram, Facebook, X/Twitter, "
            "Pinterest or Snapchat."
        ),
        "invalid": "❌ Please send a valid http/https link.",
        "downloading": "⏳ Downloading media... Please wait.",
        "error": "❌ Error:",
    },
    "so": {
        "welcome": (
            "👋 Soo dhawoow! Ii soo dir link public ah oo "
            "YouTube, TikTok, Instagram, Facebook, X/Twitter, "
            "Pinterest ama Snapchat ah."
        ),
        "invalid": "❌ Fadlan soo dir link http/https sax ah.",
        "downloading": "⏳ Media-ga ayaa la soo dejinayaa... Fadlan sug.",
        "error": "❌ Cilad:",
    },
    "ar": {
        "welcome": (
            "👋 أهلاً بك! أرسل رابط وسائط عام من YouTube أو TikTok "
            "أو Instagram أو Facebook أو X أو Pinterest أو Snapchat."
        ),
        "invalid": "❌ أرسل رابط http/https صحيح.",
        "downloading": "⏳ جارٍ التنزيل... يرجى الانتظار.",
        "error": "❌ خطأ:",
    },
    "es": {
        "welcome": (
            "👋 ¡Bienvenido! Envíame un enlace público de YouTube, "
            "TikTok, Instagram, Facebook, X, Pinterest o Snapchat."
        ),
        "invalid": "❌ Envía un enlace http/https válido.",
        "downloading": "⏳ Descargando... Por favor espera.",
        "error": "❌ Error:",
    },
    "fr": {
        "welcome": (
            "👋 Bienvenue ! Envoyez un lien public YouTube, TikTok, "
            "Instagram, Facebook, X, Pinterest ou Snapchat."
        ),
        "invalid": "❌ Envoyez un lien http/https valide.",
        "downloading": "⏳ Téléchargement en cours...",
        "error": "❌ Erreur:",
    },
    "tr": {
        "welcome": (
            "👋 Hoş geldiniz! YouTube, TikTok, Instagram, Facebook, "
            "X, Pinterest veya Snapchat bağlantısı gönderin."
        ),
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
        self.app.add_handler(
            CommandHandler("start", self.start_command)
        )

        self.app.add_handler(
            CommandHandler("stats", self.stats_command)
        )

        self.app.add_handler(
            CommandHandler("broadcast", self.broadcast_command)
        )

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

    # ---------------------------------------------------------
    # START
    # ---------------------------------------------------------

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
            logger.exception(
                "Managed /start error for bot %s",
                self.bot_id,
            )

            try:
                await update.message.reply_text(
                    "👋 Welcome! Send me a public media link."
                )
            except Exception:
                pass

    # ---------------------------------------------------------
    # MESSAGE / DOWNLOAD
    # ---------------------------------------------------------

    async def handle_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        if not update.message or not update.effective_user:
            return

        user = update.effective_user

        url = (update.message.text or "").strip()

        if not (
            url.startswith("http://")
            or url.startswith("https://")
        ):
            await update.message.reply_text(
                "❌ Please send a valid http/https media link."
            )
            return

        try:
            # Save/update user
            await db.save_bot_user(
                self.bot_id,
                user.id,
                user.username or "",
                user.full_name or "",
            )
        except Exception:
            logger.exception(
                "Could not save managed bot user: bot=%s user=%s",
                self.bot_id,
                user.id,
            )

        # Get user's language
        lang = "en"

        try:
            bot_user = await db.get_bot_user(
                self.bot_id,
                user.id,
            )

            lang = (bot_user or {}).get(
                "language",
                "en",
            )

        except Exception:
            logger.exception(
                "Could not get user language: bot=%s user=%s",
                self.bot_id,
                user.id,
            )

        texts = LANGUAGES.get(
            lang,
            LANGUAGES["en"],
        )

        status_msg = None
        file_path = None

        try:
            status_msg = await update.message.reply_text(
                texts["downloading"]
            )

            logger.info(
                "Starting download: bot=%s user=%s url=%s",
                self.bot_id,
                user.id,
                url,
            )

            # IMPORTANT:
            # downloader.py accepts:
            # download(url, user_id, premium=False)
            #
            # Do NOT pass bot_id here.
            result = await downloader.download(
                url=url,
                user_id=user.id,
                premium=False,
            )

            logger.info(
                "Download result: bot=%s user=%s success=%s",
                self.bot_id,
                user.id,
                result.get("success"),
            )

            # -------------------------------------------------
            # DOWNLOAD FAILED
            # -------------------------------------------------

            if not result.get("success"):
                error_text = str(
                    result.get(
                        "error",
                        "Unknown download error.",
                    )
                )

                logger.error(
                    "Managed bot download failed: "
                    "bot=%s user=%s error=%s",
                    self.bot_id,
                    user.id,
                    error_text,
                )

                error_text = error_text[:3500]

                if status_msg:
                    try:
                        await status_msg.edit_text(
                            f"❌ Download failed:\n\n{error_text}"
                        )
                    except Exception:
                        try:
                            await status_msg.edit_text(
                                "❌ Download failed. "
                                "Please try another link."
                            )
                        except Exception:
                            pass

                return

            # -------------------------------------------------
            # GET RESULT
            # -------------------------------------------------

            file_path = result.get("file_path")

            title = (
                result.get("title")
                or "Downloaded Media"
            )

            media_type = (
                result.get("media_type")
                or "video"
            )

            platform = (
                result.get("platform")
                or "general"
            )

            if not file_path:
                logger.error(
                    "Downloader returned success without file: "
                    "bot=%s user=%s result=%s",
                    self.bot_id,
                    user.id,
                    result,
                )

                if status_msg:
                    try:
                        await status_msg.edit_text(
                            "❌ Download completed, "
                            "but no file was produced."
                        )
                    except Exception:
                        pass

                return

            logger.info(
                "Downloaded file: bot=%s user=%s "
                "platform=%s type=%s path=%s",
                self.bot_id,
                user.id,
                platform,
                media_type,
                file_path,
            )

            # -------------------------------------------------
            # FILE CHECK
            # -------------------------------------------------

            import os

            if not os.path.isfile(file_path):
                logger.error(
                    "Downloaded file does not exist: %s",
                    file_path,
                )

                if status_msg:
                    try:
                        await status_msg.edit_text(
                            "❌ The download finished, "
                            "but the file could not be found."
                        )
                    except Exception:
                        pass

                return

            # -------------------------------------------------
            # SEND MEDIA
            # -------------------------------------------------

            if media_type == "audio":
                logger.info(
                    "Uploading audio: bot=%s user=%s",
                    self.bot_id,
                    user.id,
                )

                with open(
                    file_path,
                    "rb",
                ) as audio_file:
                    await update.message.reply_audio(
                        audio=audio_file,
                        title=title[:64],
                    )

            elif media_type == "photo":
                logger.info(
                    "Uploading photo: bot=%s user=%s",
                    self.bot_id,
                    user.id,
                )

                with open(
                    file_path,
                    "rb",
                ) as photo_file:
                    await update.message.reply_photo(
                        photo=photo_file,
                        caption=f"✅ {title[:1000]}",
                    )

            else:
                logger.info(
                    "Uploading video: bot=%s user=%s",
                    self.bot_id,
                    user.id,
                )

                with open(
                    file_path,
                    "rb",
                ) as video_file:
                    await update.message.reply_video(
                        video=video_file,
                        caption=f"✅ {title[:1000]}",
                        supports_streaming=True,
                    )

            # -------------------------------------------------
            # LOG DOWNLOAD
            # -------------------------------------------------

            try:
                await db.log_download(
                    self.bot_id,
                    user.id,
                    platform,
                    media_type,
                )

            except Exception:
                logger.exception(
                    "Could not log download: bot=%s user=%s",
                    self.bot_id,
                    user.id,
                )

            # -------------------------------------------------
            # REMOVE STATUS MESSAGE
            # -------------------------------------------------

            if status_msg:
                try:
                    await status_msg.delete()
                except Exception:
                    pass

            logger.info(
                "Managed bot download completed: "
                "bot=%s user=%s",
                self.bot_id,
                user.id,
            )

        # -----------------------------------------------------
        # TELEGRAM UPLOAD ERROR
        # -----------------------------------------------------

        except Exception as exc:
            logger.exception(
                "Managed bot media processing/upload error: "
                "bot=%s user=%s",
                self.bot_id,
                user.id,
            )

            error_text = str(exc).strip()

            if not error_text:
                error_text = "Unknown Telegram upload error."

            # Don't expose an enormous Telegram traceback
            error_text = error_text[:1500]

            if status_msg:
                try:
                    await status_msg.edit_text(
                        "❌ Could not send the downloaded media.\n\n"
                        f"{error_text}"
                    )
                except Exception:
                    pass

        # -----------------------------------------------------
        # CLEANUP
        # -----------------------------------------------------

        finally:
            if file_path:
                try:
                    downloader.cleanup(file_path)
                except Exception:
                    logger.exception(
                        "Downloader cleanup failed: %s",
                        file_path,
                    )

    # ---------------------------------------------------------
    # STATS
    # ---------------------------------------------------------

    async def stats_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        if not update.message or not update.effective_user:
            return

        try:
            bot_data = await db.get_bot(
                self.bot_id
            )

            if (
                not bot_data
                or bot_data.get("owner_id")
                != update.effective_user.id
            ):
                return

            stats = await db.get_bot_stats(
                self.bot_id
            )

            await update.message.reply_text(
                "📊 BOT OWNER STATS\n\n"
                f"👥 Users: {stats.get('total_users', 0)}\n"
                f"📥 Downloads: {stats.get('total_downloads', 0)}"
            )

        except Exception:
            logger.exception(
                "Stats error for bot %s",
                self.bot_id,
            )

    # ---------------------------------------------------------
    # BROADCAST
    # ---------------------------------------------------------

    async def broadcast_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        if not update.message or not update.effective_user:
            return

        try:
            bot_data = await db.get_bot(
                self.bot_id
            )

            if (
                not bot_data
                or bot_data.get("owner_id")
                != update.effective_user.id
            ):
                return

            if not context.args:
                await update.message.reply_text(
                    "Usage:\n/broadcast Your message"
                )
                return

            text = " ".join(
                context.args
            ).strip()

            if not text:
                await update.message.reply_text(
                    "❌ Broadcast message cannot be empty."
                )
                return

            users = await db.get_all_bot_users(
                self.bot_id
            )

            progress = await update.message.reply_text(
                f"📢 Broadcasting to {len(users)} users..."
            )

            sent = 0
            failed = 0

            for user in users:
                try:
                    user_id = user.get("user_id")

                    if not user_id:
                        failed += 1
                        continue

                    await self.app.bot.send_message(
                        chat_id=user_id,
                        text=text,
                    )

                    sent += 1

                    # Small delay to reduce Telegram flood risk
                    await asyncio.sleep(0.05)

                except Exception as exc:
                    failed += 1

                    logger.warning(
                        "Broadcast failed: bot=%s user=%s error=%s",
                        self.bot_id,
                        user.get("user_id"),
                        exc,
                    )

            try:
                await progress.edit_text(
                    "✅ Broadcast finished.\n\n"
                    f"Sent: {sent}\n"
                    f"Failed: {failed}"
                )
            except Exception:
                pass

        except Exception:
            logger.exception(
                "Broadcast error for bot %s",
                self.bot_id,
            )

    # ---------------------------------------------------------
    # CALLBACKS / LANGUAGE
    # ---------------------------------------------------------

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

            data = query.data or ""

            if data.startswith("msetlang_"):
                lang_code = data.split(
                    "_",
                    1,
                )[1]

                if lang_code not in LANGUAGES:
                    lang_code = "en"

                await db.set_user_language(
                    self.bot_id,
                    query.from_user.id,
                    lang_code,
                )

                texts = LANGUAGES[
                    lang_code
                ]

                if query.message:
                    try:
                        await query.message.edit_text(
                            f"✅ Language changed.\n\n"
                            f"{texts['welcome']}"
                        )
                    except Exception:
                        await query.message.reply_text(
                            texts["welcome"]
                        )

        except Exception:
            logger.exception(
                "Callback error for bot %s",
                self.bot_id,
            )

    # ---------------------------------------------------------
    # GLOBAL ERROR HANDLER
    # ---------------------------------------------------------

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
