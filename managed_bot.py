
import asyncio
import logging
import os

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

CHANNEL_URL = "https://t.me/downloadermain"

LANGUAGES = {
    "en": {
        "name": "English 🇬🇧",
        "welcome": "👋 Welcome! Send me a video link from YouTube, TikTok, Facebook, Pinterest, Instagram, Snapchat or X/Twitter.",
        "invalid": "❌ Please send a valid link.",
        "error": "❌ Error occurred.",
    },
    "so": {
        "name": "Soomaali 🇸🇴",
        "welcome": "👋 Soo dhawoow! Ii soo dir link video ah oo ka socda TikTok, Facebook, YouTube, Pinterest, Instagram, Snapchat ama X/Twitter.",
        "invalid": "❌ Fadlan dir link sax ah.",
        "error": "❌ Cilad ayaa dhacday.",
    },
    "ar": {
        "name": "العربية 🇸🇦",
        "welcome": "👋 أهلاً بك! أرسل رابط فيديو من YouTube أو TikTok أو Facebook أو Pinterest أو Instagram أو Snapchat أو X.",
        "invalid": "❌ يرجى إرسال رابط صحيح.",
        "error": "❌ حدث خطأ.",
    },
    "es": {
        "name": "Español 🇪🇸",
        "welcome": "👋 ¡Bienvenido! Envíame un enlace de vídeo de una plataforma compatible.",
        "invalid": "❌ Por favor envía un enlace válido.",
        "error": "❌ Ocurrió un error.",
    },
    "fr": {
        "name": "Français 🇫🇷",
        "welcome": "👋 Bienvenue ! Envoyez un lien vidéo depuis une plateforme prise en charge.",
        "invalid": "❌ Veuillez envoyer un lien valide.",
        "error": "❌ Une erreur est survenue.",
    },
    "tr": {
        "name": "Türkçe 🇹🇷",
        "welcome": "👋 Hoş geldiniz! Desteklenen bir platformdan video bağlantısı gönderin.",
        "invalid": "❌ Lütfen geçerli bir bağlantı gönderin.",
        "error": "❌ Bir hata oluştu.",
    },
    "de": {
        "name": "Deutsch 🇩🇪",
        "welcome": "👋 Willkommen! Senden Sie einen Videolink von einer unterstützten Plattform.",
        "invalid": "❌ Bitte senden Sie einen gültigen Link.",
        "error": "❌ Ein Fehler ist aufgetreten.",
    },
    "ru": {
        "name": "Русский 🇷🇺",
        "welcome": "👋 Добро пожаловать! Отправьте ссылку на видео с поддерживаемой платформы.",
        "invalid": "❌ Пожалуйста, отправьте действующую ссылку.",
        "error": "❌ Произошла ошибка.",
    },
    "hi": {
        "name": "हिन्दी 🇮🇳",
        "welcome": "👋 स्वागत है! किसी समर्थित प्लेटफ़ॉर्म का वीडियो लिंक भेजें।",
        "invalid": "❌ कृपया एक मान्य लिंक भेजें।",
        "error": "❌ त्रुटि।",
    },
    "pt": {
        "name": "Português 🇵🇹",
        "welcome": "👋 Bem-vindo! Envie um link de vídeo de uma plataforma suportada.",
        "invalid": "❌ Por favor envie um link válido.",
        "error": "❌ Ocorreu um erro.",
    },
}


class ManagedBotHandler:
    def __init__(self, bot_id: int, token: str):
        self.bot_id = bot_id
        self.token = token
        self.url_cache: dict[str, str] = {}

        self.app = Application.builder().token(token).build()
        self._setup_handlers()

    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("language", self.language_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CommandHandler("broadcast", self.broadcast_command))
        self.app.add_handler(CallbackQueryHandler(self.handle_callbacks))
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        self.app.add_error_handler(self.error_handler)

    def get_language_keyboard(self):
        keys = list(LANGUAGES)
        rows = []
        for i in range(0, len(keys), 2):
            row = [
                InlineKeyboardButton(
                    LANGUAGES[keys[i]]["name"],
                    callback_data=f"msetlang_{keys[i]}",
                )
            ]
            if i + 1 < len(keys):
                row.append(
                    InlineKeyboardButton(
                        LANGUAGES[keys[i + 1]]["name"],
                        callback_data=f"msetlang_{keys[i + 1]}",
                    )
                )
            rows.append(row)
        return InlineKeyboardMarkup(rows)

    @staticmethod
    def get_channel_keyboard():
        # CHANNEL is intentionally ONLY attached to MP3/audio messages.
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton("CHANNEL 📢", url=CHANNEL_URL)]]
        )

    def get_video_keyboard(self, url_key: str):
        # Video gets ONLY the MUSIC button.
        return InlineKeyboardMarkup(
            [[
                InlineKeyboardButton(
                    "MUSIC 🎵",
                    callback_data=f"mconvert_{url_key}",
                )
            ]]
        )

    async def get_user_lang(self, user_id: int) -> str:
        try:
            user = await db.get_bot_user(self.bot_id, user_id)
            if user and user.get("language") in LANGUAGES:
                return user["language"]
        except Exception:
            logger.exception("Error getting language for %s", user_id)
        return "en"

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user or not update.message:
            return

        user = update.effective_user

        # Keep the user's previously selected language. The old code called
        # save_bot_user() with its default language on every /start, which
        # could reset a user's language back to English.
        existing = None
        try:
            existing = await db.get_bot_user(self.bot_id, user.id)
        except Exception:
            logger.exception("Could not read bot user")

        first_start = not existing
        lang = (existing or {}).get("language") if existing else "en"
        if lang not in LANGUAGES:
            lang = "en"

        try:
            await db.save_bot_user(
                self.bot_id,
                user.id,
                user.username or "",
                user.full_name or "",
                language=lang,
            )
        except Exception:
            logger.exception("Could not save bot user")

        # Ask for language only on the first /start. Afterwards /start keeps
        # the saved language and never shows the selector again.
        await update.message.reply_text(
            LANGUAGES[lang]["welcome"],
            reply_markup=(self.get_language_keyboard() if first_start else None),
        )

    async def language_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message:
            await update.message.reply_text(
                "🌐 Select Language / Dooro Luuqada:",
                reply_markup=self.get_language_keyboard(),
            )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.message.text:
            return

        url = update.message.text.strip()
        user_id = update.effective_user.id
        lang = await self.get_user_lang(user_id)
        texts = LANGUAGES.get(lang, LANGUAGES["en"])

        if not (url.startswith("http://") or url.startswith("https://")):
            await update.message.reply_text(texts["invalid"])
            return

        # Do not send a "Downloading..." message. Telegram's native chat
        # action is used instead.
        try:
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action="upload_video",
            )
        except Exception:
            pass

        result = await downloader.download(url, user_id)

        if not result.get("success"):
            await update.message.reply_text(
                f"{texts['error']} {result.get('error', '')}".strip()
            )
            return

        file_path = result["file_path"]
        try:
            url_key = str(abs(hash(f"{self.bot_id}:{user_id}:{url}")))[:16]
            self.url_cache[url_key] = url

            media_type = result.get("media_type", "video")

            # Telegram's native action is shown while the media is uploaded;
            # no separate "Downloading..." message is created.
            if media_type == "photo":
                await context.bot.send_chat_action(
                    chat_id=update.effective_chat.id,
                    action="upload_photo",
                )
                with open(file_path, "rb") as photo_file:
                    await update.message.reply_photo(
                        photo=photo_file,
                    )
            else:
                await context.bot.send_chat_action(
                    chat_id=update.effective_chat.id,
                    action="upload_video",
                )
                with open(file_path, "rb") as video_file:
                    await update.message.reply_video(
                        video=video_file,
                        reply_markup=self.get_video_keyboard(url_key),
                    )

            try:
                await db.add_download(
                    self.bot_id,
                    user_id,
                    url=url,
                    platform=result.get("platform", "general"),
                    media_type=media_type,
                    status="success",
                    file_size=os.path.getsize(file_path),
                )
            except Exception:
                logger.exception("Could not save video download record")

        except Exception as exc:
            logger.exception("Sending video failed")
            await update.message.reply_text(
                f"{texts['error']} {str(exc)}"
            )
        finally:
            downloader.cleanup(file_path)

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.effective_user:
            return

        bot = await db.get_bot(self.bot_id)
        if not bot or int(bot.get("owner_id", 0)) != update.effective_user.id:
            return

        stats = await db.get_bot_stats(self.bot_id)
        await update.message.reply_text(
            "📊 BOT OWNER STATS\n\n"
            f"👥 Total Users: {stats['total_users']}\n"
            f"📥 Downloads: {stats['total_downloads']}\n"
            f"🎬 Videos: {stats['videos']}\n"
            f"🎵 Audio: {stats['audio']}",
        )

    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.effective_user:
            return

        bot = await db.get_bot(self.bot_id)
        if not bot or int(bot.get("owner_id", 0)) != update.effective_user.id:
            return

        if not context.args:
            await update.message.reply_text("⚠️ Usage: /broadcast Your message here")
            return

        text = " ".join(context.args)
        users = await db.get_all_bot_users(self.bot_id)
        status = await update.message.reply_text(
            f"📢 Starting broadcast to {len(users)} users..."
        )

        success = failed = 0
        for user in users:
            try:
                await self.app.bot.send_message(
                    chat_id=user["user_id"],
                    text=text,
                )
                success += 1
                await asyncio.sleep(0.04)
            except Exception:
                failed += 1

        await status.edit_text(
            f"✅ Broadcast completed. Sent: {success}, Failed: {failed}"
        )

    async def handle_callbacks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        if not query:
            return

        await query.answer()

        if query.data.startswith("msetlang_"):
            lang_code = query.data.split("_", 1)[1]
            if lang_code not in LANGUAGES:
                return

            await db.update_bot_user_language(
                self.bot_id,
                query.from_user.id,
                lang_code,
            )
            await query.message.edit_text(
                f"✅ Language changed to {LANGUAGES[lang_code]['name']}"
            )
            return

        if not query.data.startswith("mconvert_"):
            return

        url_key = query.data.split("_", 1)[1]
        url = self.url_cache.get(url_key)
        if not url:
            await query.message.reply_text(
                "❌ This link has expired. Please send the link again."
            )
            return

        # No status message. Telegram's native UPLOAD_AUDIO action shows
        # "Sending audio…" at the top of the chat while the MP3 is sent.
        try:
            await context.bot.send_chat_action(
                chat_id=query.message.chat_id,
                action="upload_audio",
            )
        except Exception:
            pass

        result = await downloader.download_audio(
            url,
            query.from_user.id,
        )

        if not result.get("success"):
            await query.message.reply_text(
                f"❌ {result.get('error', 'MP3 conversion failed')}"
            )
            return

        file_path = result["file_path"]
        try:
            await context.bot.send_chat_action(
                chat_id=query.message.chat_id,
                action="upload_audio",
            )

            with open(file_path, "rb") as audio_file:
                # No caption and no Markdown parsing. Only CHANNEL button.
                await query.message.reply_audio(
                    audio=audio_file,
                    reply_markup=self.get_channel_keyboard(),
                )

            try:
                await db.add_download(
                    self.bot_id,
                    query.from_user.id,
                    url=url,
                    platform=result.get("platform", "general"),
                    media_type="audio",
                    status="success",
                    file_size=os.path.getsize(file_path),
                )
            except Exception:
                logger.exception("Could not save audio download record")

        except Exception as exc:
            logger.exception("Sending MP3 failed")
            await query.message.reply_text(
                f"❌ {str(exc)}"
            )
        finally:
            downloader.cleanup(file_path)

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        logger.error(
            "Managed Bot Exception [%s]: %s",
            self.bot_id,
            context.error,
            exc_info=True,
        )
