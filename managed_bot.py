import asyncio
import logging
import os

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
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
            "👋 Welcome!\n\n"
            "Send me a public video/media link from:\n"
            "YouTube, TikTok, Instagram, Facebook, "
            "X/Twitter, Pinterest or Snapchat."
        ),
        "invalid": "❌ Please send a valid http/https media link.",
        "downloading": "⏳ Downloading media... Please wait.",
        "music_downloading": "🎵 Downloading and converting to MP3... Please wait.",
        "error": "❌ Error:",
        "music_ready": "🎵 MUSIC mode enabled.\n\nSend me a video/media link and I will convert it to MP3.",
        "video_ready": "🎬 VIDEO mode enabled.\n\nSend me a video/media link.",
        "language_changed": "✅ Language changed.",
    },
    "so": {
        "welcome": (
            "👋 Soo dhawoow!\n\n"
            "Ii soo dir link public ah oo ka socda:\n"
            "YouTube, TikTok, Instagram, Facebook, "
            "X/Twitter, Pinterest ama Snapchat."
        ),
        "invalid": "❌ Fadlan soo dir link http/https sax ah.",
        "downloading": "⏳ Media-ga ayaa la soo dejinayaa... Fadlan sug.",
        "music_downloading": "🎵 Music-ga ayaa la soo dejinayaa oo MP3 loo badalayaa... Fadlan sug.",
        "error": "❌ Cilad:",
        "music_ready": "🎵 MUSIC mode waa la shiday.\n\nIi soo dir link video/media ah, waxaan kuu badalayaa MP3.",
        "video_ready": "🎬 VIDEO mode waa la shiday.\n\nIi soo dir link video/media ah.",
        "language_changed": "✅ Luqadda waa la beddelay.",
    },
    "ar": {
        "welcome": (
            "👋 أهلاً بك!\n\n"
            "أرسل رابط وسائط عام من:\n"
            "YouTube أو TikTok أو Instagram أو Facebook أو "
            "X أو Pinterest أو Snapchat."
        ),
        "invalid": "❌ أرسل رابط http/https صحيح.",
        "downloading": "⏳ جارٍ تنزيل الوسائط... يرجى الانتظار.",
        "music_downloading": "🎵 جارٍ تنزيل الصوت وتحويله إلى MP3... يرجى الانتظار.",
        "error": "❌ خطأ:",
        "music_ready": "🎵 تم تفعيل وضع MUSIC.\n\nأرسل رابط فيديو لتحويله إلى MP3.",
        "video_ready": "🎬 تم تفعيل وضع VIDEO.\n\nأرسل رابط فيديو.",
        "language_changed": "✅ تم تغيير اللغة.",
    },
    "es": {
        "welcome": (
            "👋 ¡Bienvenido!\n\n"
            "Envíame un enlace público de:\n"
            "YouTube, TikTok, Instagram, Facebook, "
            "X, Pinterest o Snapchat."
        ),
        "invalid": "❌ Envía un enlace http/https válido.",
        "downloading": "⏳ Descargando... Por favor espera.",
        "music_downloading": "🎵 Descargando y convirtiendo a MP3... Por favor espera.",
        "error": "❌ Error:",
        "music_ready": "🎵 Modo MUSIC activado.\n\nEnvíame un enlace de video y lo convertiré a MP3.",
        "video_ready": "🎬 Modo VIDEO activado.\n\nEnvíame un enlace de video.",
        "language_changed": "✅ Idioma cambiado.",
    },
    "fr": {
        "welcome": (
            "👋 Bienvenue !\n\n"
            "Envoyez-moi un lien public depuis :\n"
            "YouTube, TikTok, Instagram, Facebook, "
            "X, Pinterest ou Snapchat."
        ),
        "invalid": "❌ Envoyez un lien http/https valide.",
        "downloading": "⏳ Téléchargement en cours... Veuillez patienter.",
        "music_downloading": "🎵 Téléchargement et conversion en MP3... Veuillez patienter.",
        "error": "❌ Erreur :",
        "music_ready": "🎵 Mode MUSIC activé.\n\nEnvoyez un lien vidéo pour le convertir en MP3.",
        "video_ready": "🎬 Mode VIDEO activé.\n\nEnvoyez un lien vidéo.",
        "language_changed": "✅ Langue modifiée.",
    },
    "tr": {
        "welcome": (
            "👋 Hoş geldiniz!\n\n"
            "YouTube, TikTok, Instagram, Facebook, "
            "X, Pinterest veya Snapchat bağlantısı gönderin."
        ),
        "invalid": "❌ Geçerli bir http/https bağlantısı gönderin.",
        "downloading": "⏳ İndiriliyor... Lütfen bekleyin.",
        "music_downloading": "🎵 İndiriliyor ve MP3'e dönüştürülüyor... Lütfen bekleyin.",
        "error": "❌ Hata:",
        "music_ready": "🎵 MUSIC modu etkinleştirildi.\n\nMP3'e dönüştürmek için video bağlantısı gönderin.",
        "video_ready": "🎬 VIDEO modu etkinleştirildi.\n\nVideo bağlantısı gönderin.",
        "language_changed": "✅ Dil değiştirildi.",
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

    # =========================================================
    # KEYBOARD
    # =========================================================

    def main_keyboard(self):
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🎬 VIDEO",
                        callback_data="mode_video",
                    ),
                    InlineKeyboardButton(
                        "🎵 MUSIC",
                        callback_data="mode_music",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🌐 LANGUAGE",
                        callback_data="show_languages",
                    ),
                ],
            ]
        )

    def language_keyboard(self):
        return InlineKeyboardMarkup(
            [
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
        )

    # =========================================================
    # HANDLERS
    # =========================================================

    def _setup_handlers(self):

        self.app.add_handler(
            CommandHandler(
                "start",
                self.start_command,
            )
        )

        self.app.add_handler(
            CommandHandler(
                "stats",
                self.stats_command,
            )
        )

        self.app.add_handler(
            CommandHandler(
                "broadcast",
                self.broadcast_command,
            )
        )

        self.app.add_handler(
            CallbackQueryHandler(
                self.handle_callbacks,
            )
        )

        self.app.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.handle_message,
            )
        )

        self.app.add_error_handler(
            self.error_handler
        )

    # =========================================================
    # START
    # =========================================================

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

            lang = (
                (bot_user or {}).get(
                    "language",
                    "en",
                )
                or "en"
            )

            texts = LANGUAGES.get(
                lang,
                LANGUAGES["en"],
            )

            # Default mode
            context.user_data["download_mode"] = "video"

            await update.message.reply_text(
                texts["welcome"],
                reply_markup=self.main_keyboard(),
            )

        except Exception:
            logger.exception(
                "Managed /start error for bot %s",
                self.bot_id,
            )

            try:
                await update.message.reply_text(
                    "👋 Welcome!\n\n"
                    "Send me a public media link.",
                    reply_markup=self.main_keyboard(),
                )
            except Exception:
                pass

    # =========================================================
    # MESSAGE / DOWNLOAD
    # =========================================================

    async def handle_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        if not update.message or not update.effective_user:
            return

        user = update.effective_user

        url = (
            update.message.text or ""
        ).strip()

        # -----------------------------------------------------
        # VALIDATE URL
        # -----------------------------------------------------

        if not (
            url.startswith("http://")
            or url.startswith("https://")
        ):
            try:
                await update.message.reply_text(
                    "❌ Please send a valid http/https media link.",
                    reply_markup=self.main_keyboard(),
                )
            except Exception:
                pass

            return

        # -----------------------------------------------------
        # SAVE USER
        # -----------------------------------------------------

        try:
            await db.save_bot_user(
                self.bot_id,
                user.id,
                user.username or "",
                user.full_name or "",
            )
        except Exception:
            logger.exception(
                "Could not save managed bot user: "
                "bot=%s user=%s",
                self.bot_id,
                user.id,
            )

        # -----------------------------------------------------
        # GET LANGUAGE
        # -----------------------------------------------------

        lang = "en"

        try:
            bot_user = await db.get_bot_user(
                self.bot_id,
                user.id,
            )

            lang = (
                (bot_user or {}).get(
                    "language",
                    "en",
                )
                or "en"
            )

        except Exception:
            logger.exception(
                "Could not get user language: "
                "bot=%s user=%s",
                self.bot_id,
                user.id,
            )

        texts = LANGUAGES.get(
            lang,
            LANGUAGES["en"],
        )

        # -----------------------------------------------------
        # GET MODE
        # -----------------------------------------------------

        mode = context.user_data.get(
            "download_mode",
            "video",
        )

        if mode not in (
            "video",
            "music",
        ):
            mode = "video"

        status_msg = None
        file_path = None

        try:

            # -------------------------------------------------
            # STATUS MESSAGE
            # -------------------------------------------------

            if mode == "music":
                status_msg = await update.message.reply_text(
                    texts["music_downloading"]
                )
            else:
                status_msg = await update.message.reply_text(
                    texts["downloading"]
                )

            logger.info(
                "Starting managed bot download: "
                "bot=%s user=%s mode=%s url=%s",
                self.bot_id,
                user.id,
                mode,
                url,
            )

            # -------------------------------------------------
            # MUSIC / MP3
            # -------------------------------------------------

            if mode == "music":

                result = await downloader.download_audio(
                    url=url,
                    user_id=user.id,
                    premium=False,
                )

            # -------------------------------------------------
            # NORMAL VIDEO
            # -------------------------------------------------

            else:

                result = await downloader.download(
                    url=url,
                    user_id=user.id,
                    premium=False,
                )

            logger.info(
                "Downloader result: "
                "bot=%s user=%s mode=%s success=%s",
                self.bot_id,
                user.id,
                mode,
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
                    "bot=%s user=%s mode=%s error=%s",
                    self.bot_id,
                    user.id,
                    mode,
                    error_text,
                )

                error_text = error_text[:3000]

                if status_msg:
                    try:

                        await status_msg.edit_text(
                            f"{texts['error']}\n\n"
                            f"{error_text}",
                            reply_markup=self.main_keyboard(),
                        )

                    except Exception:
                        pass

                return

            # -------------------------------------------------
            # RESULT
            # -------------------------------------------------

            file_path = result.get(
                "file_path"
            )

            title = (
                result.get("title")
                or (
                    "Music"
                    if mode == "music"
                    else "Downloaded Media"
                )
            )

            platform = (
                result.get("platform")
                or "general"
            )

            media_type = (
                result.get("media_type")
                or (
                    "audio"
                    if mode == "music"
                    else "video"
                )
            )

            # Force audio for music mode
            if mode == "music":
                media_type = "audio"

            # -------------------------------------------------
            # FILE PATH CHECK
            # -------------------------------------------------

            if not file_path:

                logger.error(
                    "Downloader returned success "
                    "without file path: "
                    "bot=%s user=%s result=%s",
                    self.bot_id,
                    user.id,
                    result,
                )

                if status_msg:
                    try:
                        await status_msg.edit_text(
                            "❌ Download completed, "
                            "but no output file was produced.",
                            reply_markup=self.main_keyboard(),
                        )
                    except Exception:
                        pass

                return

            # -------------------------------------------------
            # FILE EXISTS CHECK
            # -------------------------------------------------

            if not os.path.isfile(
                file_path
            ):

                logger.error(
                    "Downloaded file does not exist: %s",
                    file_path,
                )

                if status_msg:
                    try:
                        await status_msg.edit_text(
                            "❌ The download finished, "
                            "but the output file could not be found.",
                            reply_markup=self.main_keyboard(),
                        )
                    except Exception:
                        pass

                return

            # -------------------------------------------------
            # SEND AUDIO / MP3
            # -------------------------------------------------

            if media_type == "audio":

                logger.info(
                    "Uploading MP3/audio: "
                    "bot=%s user=%s file=%s",
                    self.bot_id,
                    user.id,
                    file_path,
                )

                with open(
                    file_path,
                    "rb",
                ) as audio_file:

                    await update.message.reply_audio(
                        audio=audio_file,
                        title=str(title)[:64],
                        performer="TG-Power",
                        caption=f"🎵 {str(title)[:900]}",
                    )

            # -------------------------------------------------
            # SEND PHOTO
            # -------------------------------------------------

            elif media_type == "photo":

                logger.info(
                    "Uploading photo: "
                    "bot=%s user=%s file=%s",
                    self.bot_id,
                    user.id,
                    file_path,
                )

                with open(
                    file_path,
                    "rb",
                ) as photo_file:

                    await update.message.reply_photo(
                        photo=photo_file,
                        caption=(
                            f"✅ {str(title)[:900]}"
                        ),
                    )

            # -------------------------------------------------
            # SEND VIDEO
            # -------------------------------------------------

            else:

                logger.info(
                    "Uploading video: "
                    "bot=%s user=%s file=%s",
                    self.bot_id,
                    user.id,
                    file_path,
                )

                with open(
                    file_path,
                    "rb",
                ) as video_file:

                    await update.message.reply_video(
                        video=video_file,
                        caption=(
                            f"✅ {str(title)[:900]}"
                        ),
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
                    "Could not log download: "
                    "bot=%s user=%s",
                    self.bot_id,
                    user.id,
                )

            # -------------------------------------------------
            # DELETE STATUS
            # -------------------------------------------------

            if status_msg:

                try:
                    await status_msg.delete()
                except Exception:
                    pass

            # -------------------------------------------------
            # RESET MODE
            # -------------------------------------------------

            context.user_data[
                "download_mode"
            ] = "video"

            logger.info(
                "Managed bot download completed: "
                "bot=%s user=%s mode=%s",
                self.bot_id,
                user.id,
                mode,
            )

        # =====================================================
        # ERROR
        # =====================================================

        except Exception as exc:

            logger.exception(
                "Managed bot media processing/upload error: "
                "bot=%s user=%s mode=%s",
                self.bot_id,
                user.id,
                mode,
            )

            error_text = str(
                exc
            ).strip()

            if not error_text:
                error_text = (
                    "Unknown Telegram upload error."
                )

            error_text = error_text[:1500]

            if status_msg:

                try:

                    await status_msg.edit_text(
                        "❌ Could not send the downloaded media.\n\n"
                        f"{error_text}",
                        reply_markup=self.main_keyboard(),
                    )

                except Exception:
                    pass

        # =====================================================
        # CLEANUP
        # =====================================================

        finally:

            if file_path:

                try:

                    downloader.cleanup(
                        file_path
                    )

                except Exception:

                    logger.exception(
                        "Downloader cleanup failed: %s",
                        file_path,
                    )

    # =========================================================
    # STATS
    # =========================================================

    async def stats_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        if (
            not update.message
            or not update.effective_user
        ):
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
                f"👥 Users: "
                f"{stats.get('total_users', 0)}\n"
                f"📥 Downloads: "
                f"{stats.get('total_downloads', 0)}",
                reply_markup=self.main_keyboard(),
            )

        except Exception:

            logger.exception(
                "Stats error for bot %s",
                self.bot_id,
            )

    # =========================================================
    # BROADCAST
    # =========================================================

    async def broadcast_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        if (
            not update.message
            or not update.effective_user
        ):
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
                    "Usage:\n"
                    "/broadcast Your message"
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
                f"📢 Broadcasting to "
                f"{len(users)} users..."
            )

            sent = 0
            failed = 0

            for bot_user in users:

                try:

                    user_id = bot_user.get(
                        "user_id"
                    )

                    if not user_id:

                        failed += 1
                        continue

                    await self.app.bot.send_message(
                        chat_id=user_id,
                        text=text,
                    )

                    sent += 1

                    await asyncio.sleep(
                        0.05
                    )

                except Exception as exc:

                    failed += 1

                    logger.warning(
                        "Broadcast failed: "
                        "bot=%s user=%s error=%s",
                        self.bot_id,
                        bot_user.get("user_id"),
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

    # =========================================================
    # CALLBACKS
    # =========================================================

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

            # -------------------------------------------------
            # MUSIC MODE
            # -------------------------------------------------

            if data == "mode_music":

                context.user_data[
                    "download_mode"
                ] = "music"

                bot_user = None

                try:
                    bot_user = await db.get_bot_user(
                        self.bot_id,
                        query.from_user.id,
                    )
                except Exception:
                    pass

                lang = (
                    (bot_user or {}).get(
                        "language",
                        "en",
                    )
                    or "en"
                )

                texts = LANGUAGES.get(
                    lang,
                    LANGUAGES["en"],
                )

                if query.message:

                    await query.message.reply_text(
                        texts["music_ready"],
                        reply_markup=self.main_keyboard(),
                    )

                return

            # -------------------------------------------------
            # VIDEO MODE
            # -------------------------------------------------

            if data == "mode_video":

                context.user_data[
                    "download_mode"
                ] = "video"

                bot_user = None

                try:
                    bot_user = await db.get_bot_user(
                        self.bot_id,
                        query.from_user.id,
                    )
                except Exception:
                    pass

                lang = (
                    (bot_user or {}).get(
                        "language",
                        "en",
                    )
                    or "en"
                )

                texts = LANGUAGES.get(
                    lang,
                    LANGUAGES["en"],
                )

                if query.message:

                    await query.message.reply_text(
                        texts["video_ready"],
                        reply_markup=self.main_keyboard(),
                    )

                return

            # -------------------------------------------------
            # SHOW LANGUAGES
            # -------------------------------------------------

            if data == "show_languages":

                if query.message:

                    await query.message.reply_text(
                        "🌐 Select your language:",
                        reply_markup=self.language_keyboard(),
                    )

                return

            # -------------------------------------------------
            # LANGUAGE
            # -------------------------------------------------

            if data.startswith(
                "msetlang_"
            ):

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

                context.user_data[
                    "download_mode"
                ] = "video"

                if query.message:

                    try:

                        await query.message.edit_text(
                            f"{texts['language_changed']}\n\n"
                            f"{texts['welcome']}",
                            reply_markup=self.main_keyboard(),
                        )

                    except Exception:

                        await query.message.reply_text(
                            f"{texts['language_changed']}\n\n"
                            f"{texts['welcome']}",
                            reply_markup=self.main_keyboard(),
                        )

                return

        except Exception:

            logger.exception(
                "Callback error for bot %s",
                self.bot_id,
            )

    # =========================================================
    # GLOBAL ERROR HANDLER
    # =========================================================

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
