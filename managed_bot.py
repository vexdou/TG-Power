import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
)
from database import db
from downloader import downloader

logger = logging.getLogger(__name__)

LANGUAGES = {
    "en": {"name": "English 🇬🇧", "welcome": "👋 Welcome! Send me any video link from YouTube, TikTok, IG, FB, Twitter.", "invalid": "❌ Please send a valid link.", "downloading": "⏳ Downloading... Please wait.", "error": "❌ Error occurred:"},
    "so": {"name": "Soomaali 🇸🇴", "welcome": "👋 Soo dhawoow! Iisoo dir link kasta oo video ah (YouTube, TikTok, IG, FB, Twitter).", "invalid": "❌ Fadlan dir link sax ah.", "downloading": "⏳ Soo dejintu waa ay socotaa... Fadlan sug.", "error": "❌ Cilad ayaa dhacday:"},
    "ar": {"name": "العربية 🇸🇦", "welcome": "👋 أهلاً بك! أرسل لي أي رابط فيديو من يوتيوب، تيك توك، إنستغرام، فيسبوك.", "invalid": "❌ يرجى إرسال رابط صحيح.", "downloading": "⏳ جاري التحميل... يرجى الانتظار.", "error": "❌ حدث خطأ:"},
    "es": {"name": "Español 🇪🇸", "welcome": "👋 ¡Bienvenido! Envíame cualquier enlace de video de YouTube, TikTok, IG, FB.", "invalid": "❌ Por favor envía un enlace válido.", "downloading": "⏳ Descargando... Por favor espera.", "error": "❌ Ocurrió un error:"},
    "fr": {"name": "Français 🇫🇷", "welcome": "👋 Bienvenue ! Envoyez-moi n'importe quel lien vidéo.", "invalid": "❌ Veuillez envoyer un lien valide.", "downloading": "⏳ Téléchargement en cours...", "error": "❌ Une erreur est survenue :"},
    "tr": {"name": "Türkçe 🇹🇷", "welcome": "👋 Hoş geldiniz! YouTube, TikTok, IG, FB'den herhangi bir video bağlantısı gönderin.", "invalid": "❌ Lütfen geçerli bir bağlantı gönderin.", "downloading": "⏳ İndiriliyor...", "error": "❌ Bir hata oluştu:"},
    "de": {"name": "Deutsch 🇩🇪", "welcome": "👋 Willkommen! Senden Sie mir einen beliebigen Videolink.", "invalid": "❌ Bitte senden Sie einen gültigen Link.", "downloading": "⏳ Herunterladen...", "error": "❌ Ein Fehler ist aufgetreten:"},
    "ru": {"name": "Русский 🇷🇺", "welcome": "👋 Добро пожаловать! Отправьте мне ссылку на видео.", "invalid": "❌ Пожалуйста, отправьте действующую ссылку.", "downloading": "⏳ Скачивание...", "error": "❌ Произошла ошибка:"},
    "hi": {"name": "हिन्दी 🇮🇳", "welcome": "👋 स्वागत है! मुझे कोई भी वीडियो लिंक भेजें।", "invalid": "❌ कृपया एक मान्य लिंक भेजें।", "downloading": "⏳ डाउनलोड हो रहा है...", "error": "❌ त्रुटि:"},
    "pt": {"name": "Português 🇵🇹", "welcome": "👋 Bem-vindo! Envie-me qualquer link de vídeo.", "invalid": "❌ Por favor envie um link válido.", "downloading": "⏳ Baixando...", "error": "❌ Ocorreu um erro:"}
}

class ManagedBotHandler:
    def __init__(self, bot_id: int, token: str):
        self.bot_id = bot_id
        self.token = token
        self.app = Application.builder().token(token).build()
        self._setup_handlers()

    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("language", self.language_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CommandHandler("broadcast", self.broadcast_command))
        self.app.add_handler(CallbackQueryHandler(self.handle_callbacks))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.app.add_error_handler(self.error_handler)

    async def get_user_lang(self, user_id: int) -> str:
        try:
            u = await db.get_bot_user(self.bot_id, user_id)
            if u and u.get("language"):
                return u.get("language")
        except Exception as e:
            logger.error(f"Error getting user language: {e}")
        return "en"

    def get_language_keyboard(self):
        buttons = []
        keys = list(LANGUAGES.keys())
        for i in range(0, len(keys), 2):
            row = [InlineKeyboardButton(LANGUAGES[keys[i]]["name"], callback_data=f"msetlang_{keys[i]}")]
            if i + 1 < len(keys):
                row.append(InlineKeyboardButton(LANGUAGES[keys[i+1]]["name"], callback_data=f"msetlang_{keys[i+1]}"))
            buttons.append(row)
        return InlineKeyboardMarkup(buttons)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user = update.effective_user
            await db.save_bot_user(self.bot_id, user.id, user.username or "", user.full_name or "")
            
            lang = await self.get_user_lang(user.id)
            welcome_text = LANGUAGES.get(lang, LANGUAGES["en"])["welcome"]

            await update.message.reply_text(
                f"{welcome_text}\n\n🌐 **Select Language / Dooro Luuqada:**",
                reply_markup=self.get_language_keyboard(),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Managed bot start error: {e}")

    async def language_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🌐 **Select Language / Dooro Luuqada:**",
            reply_markup=self.get_language_keyboard(),
            parse_mode="Markdown"
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            url = update.message.text.strip()
            user_id = update.effective_user.id
            lang = await self.get_user_lang(user_id)
            texts = LANGUAGES.get(lang, LANGUAGES["en"])

            if not (url.startswith("http://") or url.startswith("https://")):
                await update.message.reply_text(texts["invalid"])
                return

            status_msg = await update.message.reply_text(texts["downloading"])
            result = await downloader.download(url, user_id)

            if not result["success"]:
                await status_msg.edit_text(f"{texts['error']} {result['error']}")
                return

            file_path = result["file_path"]
            try:
                if result["media_type"] == "video":
                    with open(file_path, "rb") as video_file:
                        await update.message.reply_video(video=video_file, caption=f"✅ {result['title']}")
                else:
                    with open(file_path, "rb") as audio_file:
                        await update.message.reply_audio(audio=audio_file, caption=f"✅ {result['title']}")

                await db.log_download(self.bot_id, user_id, result["platform"], result["media_type"])
                await status_msg.delete()
            except Exception as e:
                await status_msg.edit_text(f"{texts['error']} {str(e)}")
            finally:
                downloader.cleanup(file_path)

        except Exception as e:
            logger.error(f"Message handling error in bot {self.bot_id}: {e}")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.effective_user.id
            bot_data = await db.get_bot(self.bot_id)

            if not bot_data or bot_data.get("owner_id") != user_id:
                return

            stats = await db.get_bot_stats(self.bot_id)
            await update.message.reply_text(
                f"📊 **BOT OWNER STATS**\n\n"
                f"👥 Total Users: `{stats['total_users']}`\n"
                f"📥 Downloads: `{stats['total_downloads']}`\n"
                f"🎬 Videos: `{stats['videos']}`\n"
                f"🎵 Audio: `{stats['audio']}`",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Stats command error: {e}")

    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.effective_user.id
            bot_data = await db.get_bot(self.bot_id)

            if not bot_data or bot_data.get("owner_id") != user_id:
                return

            if not context.args:
                await update.message.reply_text("⚠️ Usage: `/broadcast Your message here`", parse_mode="Markdown")
                return

            bc_text = " ".join(context.args)
            users = await db.get_all_bot_users(self.bot_id)
            msg = await update.message.reply_text(f"📢 Starting broadcast to {len(users)} users...")

            success, failed = 0, 0
            for u in users:
                try:
                    await self.app.bot.send_message(chat_id=u["user_id"], text=bc_text)
                    success += 1
                    await asyncio.sleep(0.04)
                except Exception:
                    failed += 1

            await msg.edit_text(f"✅ **Broadcast Completed!**\n\n🟢 Sent: {success}\n🔴 Failed: {failed}", parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Broadcast command error: {e}")

    async def handle_callbacks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            query = update.callback_query
            await query.answer()

            if query.data.startswith("msetlang_"):
                lang_code = query.data.split("_")[1]
                await db.set_user_language(self.bot_id, query.from_user.id, lang_code)
                texts = LANGUAGES.get(lang_code, LANGUAGES["en"])
                await query.message.edit_text(f"✅ {texts['welcome']}")
        except Exception as e:
            logger.error(f"Callback query error: {e}")

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Managed Bot Exception [{self.bot_id}]: {context.error}")
