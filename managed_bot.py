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
    "en": {"welcome": "👋 Welcome! Send me any video link (YouTube, TikTok, IG, FB, Twitter).", "invalid": "❌ Please send a valid video link.", "downloading": "⏳ Downloading... Please wait.", "error": "❌ Error:"},
    "so": {"welcome": "👋 Soo dhawoow! Iisoo dir link kasta oo video ah (YouTube, TikTok, IG, FB, Twitter).", "invalid": "❌ Fadlan dir link sax ah.", "downloading": "⏳ Soo dejintu waa ay socotaa... Fadlan sug.", "error": "❌ Cilad:"},
    "ar": {"welcome": "👋 أهلاً بك! أرسل لي أي رابط فيديو من يوتيوب، تيك توك، إنستغرام، فيسبوك.", "invalid": "❌ يرجى إرسال رابط صحيح.", "downloading": "⏳ جاري التحميل... يرجى الانتظار.", "error": "❌ حدث خطأ:"},
    "es": {"welcome": "👋 ¡Bienvenido! Envíame cualquier enlace de video de YouTube, TikTok, IG, FB.", "invalid": "❌ Por favor envía un enlace válido.", "downloading": "⏳ Descargando... Por favor espera.", "error": "❌ Ocurrió un error:"},
    "fr": {"welcome": "👋 Bienvenue ! Envoyez-moi n'importe quel lien vidéo.", "invalid": "❌ Veuillez envoyer un lien valide.", "downloading": "⏳ Téléchargement en cours...", "error": "❌ Une erreur est survenue :"},
    "tr": {"welcome": "👋 Hoş geldiniz! YouTube, TikTok, IG, FB'den herhangi bir video bağlantısı gönderin.", "invalid": "❌ Lütfen geçerli bir bağlantı gönderin.", "downloading": "⏳ İndiriliyor...", "error": "❌ Bir hata oluştu:"},
    "de": {"welcome": "👋 Willkommen! Senden Sie mir einen beliebigen Videolink.", "invalid": "❌ Bitte senden Sie einen gültigen Link.", "downloading": "⏳ Herunterladen...", "error": "❌ Ein Fehler ist aufgetreten:"},
    "ru": {"welcome": "👋 Добро пожаловать! Отправьте мне ссылку на видео.", "invalid": "❌ Пожалуйста, отправьте действующую ссылку.", "downloading": "⏳ Скачивание...", "error": "❌ Произошла ошибка:"},
    "hi": {"welcome": "👋 स्वागत है! मुझे कोई भी वीडियो लिंक भेजें।", "invalid": "❌ कृपया एक मान्य लिंक भेजें।", "downloading": "⏳ डाउनलोड हो रहा है...", "error": "❌ त्रुटि:"},
    "pt": {"welcome": "👋 Bem-vindo! Envie-me qualquer link de vídeo.", "invalid": "❌ Por favor envie um link válido.", "downloading": "⏳ Baixando...", "error": "❌ Ocorreu um erro:"}
}

class ManagedBotHandler:
    def __init__(self, bot_id: int, token: str):
        self.bot_id = bot_id
        self.token = token
        self.app = Application.builder().token(token).build()
        self._setup_handlers()

    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CommandHandler("broadcast", self.broadcast_command))
        self.app.add_handler(CallbackQueryHandler(self.handle_callbacks))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.app.add_error_handler(self.error_handler)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user = update.effective_user
            await db.save_bot_user(self.bot_id, user.id, user.username or "", user.full_name or "")

            buttons = [
                [InlineKeyboardButton("English 🇬🇧", callback_data="msetlang_en"), InlineKeyboardButton("Soomaali 🇸🇴", callback_data="msetlang_so")],
                [InlineKeyboardButton("العربية 🇸🇦", callback_data="msetlang_ar"), InlineKeyboardButton("Español 🇪🇸", callback_data="msetlang_es")],
                [InlineKeyboardButton("Français 🇫🇷", callback_data="msetlang_fr"), InlineKeyboardButton("Türkçe 🇹🇷", callback_data="msetlang_tr")]
            ]
            await update.message.reply_text(
                "🌐 **Select Language / Dooro Luuqadaada:**\n\nSend any media link anytime to download!",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Managed start error: {e}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            url = update.message.text.strip()
            user_id = update.effective_user.id

            if not (url.startswith("http://") or url.startswith("https://")):
                await update.message.reply_text("❌ Please send a valid link (YouTube, TikTok, IG, FB, etc.).")
                return

            status_msg = await update.message.reply_text("⏳ **Downloading media... Please wait.**", parse_mode="Markdown")
            result = await downloader.download(url, user_id)

            if not result["success"]:
                await status_msg.edit_text(f"❌ **Error:** {result['error']}", parse_mode="Markdown")
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
                await status_msg.edit_text(f"❌ Telegram Upload Error: {str(e)}")
            finally:
                downloader.cleanup(file_path)

        except Exception as e:
            logger.error(f"Managed message handling error: {e}")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.effective_user.id
            bot_data = await db.get_bot(self.bot_id)
            if not bot_data or bot_data.get("owner_id") != user_id:
                return

            stats = await db.get_bot_stats(self.bot_id)
            await update.message.reply_text(
                f"📊 **BOT OWNER STATS**\n\n👥 Users: `{stats['total_users']}`\n📥 Downloads: `{stats['total_downloads']}`",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Stats error: {e}")

    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.effective_user.id
            bot_data = await db.get_bot(self.bot_id)
            if not bot_data or bot_data.get("owner_id") != user_id:
                return

            if not context.args:
                await update.message.reply_text("⚠️ Usage: `/broadcast Your message`", parse_mode="Markdown")
                return

            bc_text = " ".join(context.args)
            users = await db.get_all_bot_users(self.bot_id)
            msg = await update.message.reply_text(f"📢 Sending to {len(users)} users...")

            s, f = 0, 0
            for u in users:
                try:
                    await self.app.bot.send_message(chat_id=u["user_id"], text=bc_text)
                    s += 1
                    await asyncio.sleep(0.04)
                except Exception:
                    f += 1

            await msg.edit_text(f"✅ Broadcast Done! Sent: {s}, Failed: {f}")
        except Exception as e:
            logger.error(f"Broadcast error: {e}")

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
            logger.error(f"Callback error: {e}")

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Managed Bot Exception: {context.error}")
