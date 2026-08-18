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
    "en": {"name": "English 🇬🇧", "welcome": "👋 Welcome! Send me any video link from YouTube, TikTok, IG, FB, Twitter.", "select_lang": "🌐 Please select your language:", "downloading": "⏳ Downloading... Please wait.", "download_success": "✅ Downloaded successfully!", "invalid_url": "❌ Please send a valid link.", "error": "❌ Error occurred:"},
    "so": {"name": "Soomaali 🇸🇴", "welcome": "👋 Soo dhawoow! Iisoo dir link kasta oo video ah (YouTube, TikTok, IG, FB, Twitter).", "select_lang": "🌐 Fadlan dooro luuqadaada:", "downloading": "⏳ Soo dejintu waa ay socotaa... Fadlan sug.", "download_success": "✅ Waa lagu guuleystay soo dejinta!", "invalid_url": "❌ Fadlan dir link sax ah.", "error": "❌ Cilad ayaa dhacday:"},
    "ar": {"name": "العربية 🇸🇦", "welcome": "👋 أهلاً بك! أرسل لي أي رابط فيديو من يوتيوب، تيك توك، إنستغرام، فيسبوك.", "select_lang": "🌐 يرجى اختيار لغتك:", "downloading": "⏳ جاري التحميل... يرجى الانتظار.", "download_success": "✅ تم التحميل بنجاح!", "invalid_url": "❌ يرجى إرسال رابط صحيح.", "error": "❌ حدث خطأ:"},
    "es": {"name": "Español 🇪🇸", "welcome": "👋 ¡Bienvenido! Envíame cualquier enlace de video de YouTube, TikTok, IG, FB.", "select_lang": "🌐 Por favor selecciona tu idioma:", "downloading": "⏳ Descargando... Por favor espera.", "download_success": "✅ ¡Descargado con éxito!", "invalid_url": "❌ Por favor envía un enlace válido.", "error": "❌ Ocurrió un error:"},
    "fr": {"name": "Français 🇫🇷", "welcome": "👋 Bienvenue ! Envoyez-moi n'importe quel lien vidéo de YouTube, TikTok, IG, FB.", "select_lang": "🌐 Veuillez choisir votre langue :", "downloading": "⏳ Téléchargement en cours... Veuillez patienter.", "download_success": "✅ Téléchargé avec succès !", "invalid_url": "❌ Veuillez envoyer un lien valide.", "error": "❌ Une erreur est survenue :"},
    "tr": {"name": "Türkçe 🇹🇷", "welcome": "👋 Hoş geldiniz! YouTube, TikTok, IG, FB'den herhangi bir video bağlantısı gönderin.", "select_lang": "🌐 Lütfen dilinizi seçin:", "downloading": "⏳ İndiriliyor... Lütfen bekleyin.", "download_success": "✅ Başarıyla indirildi!", "invalid_url": "❌ Lütfen geçerli bir bağlantı gönderin.", "error": "❌ Bir hata oluştu:"},
    "de": {"name": "Deutsch 🇩🇪", "welcome": "👋 Willkommen! Senden Sie mir einen beliebigen Videolink von YouTube, TikTok, IG, FB.", "select_lang": "🌐 Bitte wählen Sie Ihre Sprache:", "downloading": "⏳ Herunterladen... Bitte warten.", "download_success": "✅ Erfolgreich heruntergeladen!", "invalid_url": "❌ Bitte senden Sie einen gültigen Link.", "error": "❌ Ein Fehler ist aufgetreten:"},
    "ru": {"name": "Русский 🇷🇺", "welcome": "👋 Добро пожаловать! Отправьте мне любую ссылку на видео с YouTube, TikTok, IG, FB.", "select_lang": "🌐 Пожалуйста, выберите ваш язык:", "downloading": "⏳ Скачивание... Пожалуйста, подождите.", "download_success": "✅ Успешно скачано!", "invalid_url": "❌ Пожалуйста, отправьте действующую ссылку.", "error": "❌ Произошла ошибка:"},
    "hi": {"name": "हिन्दी 🇮🇳", "welcome": "👋 स्वागत है! मुझे YouTube, TikTok, IG, FB से कोई भी वीडियो लिंक भेजें।", "select_lang": "🌐 कृपया अपनी भाषा चुनें:", "downloading": "⏳ डाउनलोड हो रहा है... कृपया प्रतीक्षा करें।", "download_success": "✅ सफलतापूर्वक डाउनलोड हो गया!", "invalid_url": "❌ कृपया एक मान्य लिंक भेजें।", "error": "❌ एक त्रुटि हुई:"},
    "pt": {"name": "Português 🇵🇹", "welcome": "👋 Bem-vindo! Envie-me qualquer link de vídeo do YouTube, TikTok, IG, FB.", "select_lang": "🌐 Por favor escolha seu idioma:", "downloading": "⏳ Baixando... Por favor aguarde.", "download_success": "✅ Baixado com sucesso!", "invalid_url": "❌ Por favor envie um link válido.", "error": "❌ Ocorreu um erro:"}
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
        self.app.add_handler(CommandHandler("admin", self.stats_command))
        self.app.add_handler(CallbackQueryHandler(self.handle_callbacks))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        self.app.add_error_handler(self.error_handler)

    async def get_user_lang(self, user_id: int) -> str:
        try:
            u = await db.get_bot_user(self.bot_id, user_id)
            if u and u.get("language"):
                return u.get("language")
        except Exception as e:
            logger.error(f"Error fetching lang: {e}")
        return "en"

    def get_language_keyboard(self):
        buttons = []
        keys = list(LANGUAGES.keys())
        for i in range(0, len(keys), 2):
            row = [InlineKeyboardButton(LANGUAGES[keys[i]]["name"], callback_data=f"setlang_{keys[i]}")]
            if i + 1 < len(keys):
                row.append(InlineKeyboardButton(LANGUAGES[keys[i+1]]["name"], callback_data=f"setlang_{keys[i+1]}"))
            buttons.append(row)
        return InlineKeyboardMarkup(buttons)

    async def check_force_join(self, user_id: int) -> bool:
        try:
            bot_data = await db.get_bot(self.bot_id)
            if not bot_data:
                return True
            channels = bot_data.get("force_join_channels", [])
            if not channels:
                return True
            for channel in channels:
                try:
                    member = await self.app.bot.get_chat_member(chat_id=channel, user_id=user_id)
                    if member.status in ["left", "kicked"]:
                        return False
                except Exception:
                    return False
        except Exception as e:
            logger.error(f"Force join check error: {e}")
        return True

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user = update.effective_user
            await db.save_bot_user(self.bot_id, user.id, user.username or "", user.full_name or "")

            if not await self.check_force_join(user.id):
                bot_data = await db.get_bot(self.bot_id)
                buttons = [
                    [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{ch.replace('@','')}")]
                    for ch in bot_data.get("force_join_channels", [])
                ]
                buttons.append([InlineKeyboardButton("🔄 Check Membership", callback_data="check_fj")])
                await update.message.reply_text(
                    "⚠️ Please join our channels to use this bot:",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                return

            bot_user = await db.get_bot_user(self.bot_id, user.id)
            if not bot_user or not bot_user.get("language"):
                await update.message.reply_text(
                    "🌐 **Choose Language / Dooro Luuqada:**",
                    reply_markup=self.get_language_keyboard(),
                    parse_mode="Markdown"
                )
            else:
                lang = bot_user.get("language", "en")
                msg = LANGUAGES.get(lang, LANGUAGES["en"])["welcome"]
                await update.message.reply_text(f"{msg}\n\n🌐 Change language: /language")
        except Exception as e:
            logger.error(f"Managed start error: {e}")

    async def language_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🌐 **Select Language:**",
            reply_markup=self.get_language_keyboard(),
            parse_mode="Markdown"
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            url = update.message.text.strip()
            user_id = update.effective_user.id

            if not await self.check_force_join(user_id):
                await update.message.reply_text("⚠️ Please join channels first.")
                return

            lang = await self.get_user_lang(user_id)
            texts = LANGUAGES.get(lang, LANGUAGES["en"])

            if not url.startswith("http://") and not url.startswith("https://"):
                await update.message.reply_text(texts["invalid_url"])
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
            logger.error(f"Managed message handling error: {e}")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.effective_user.id
            bot_data = await db.get_bot(self.bot_id)

            if not bot_data or bot_data.get("owner_id") != user_id:
                return

            stats = await db.get_bot_stats(self.bot_id)
            await update.message.reply_text(
                f"📊 **BOT STATISTICS**\n\n"
                f"👥 Total Users: `{stats['total_users']}`\n"
                f"📥 Total Downloads: `{stats['total_downloads']}`\n"
                f"🎬 Videos: `{stats['videos']}`\n"
                f"🎵 Audio: `{stats['audio']}`",
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
                await update.message.reply_text("⚠️ Usage: `/broadcast Your message here...`", parse_mode="Markdown")
                return

            bc_text = " ".join(context.args)
            users = await db.get_all_bot_users(self.bot_id)
            status_msg = await update.message.reply_text(f"📢 Starting broadcast to {len(users)} users...")

            success, failed = 0, 0
            for u in users:
                try:
                    await self.app.bot.send_message(chat_id=u["user_id"], text=bc_text)
                    success += 1
                    await asyncio.sleep(0.04)
                except Exception:
                    failed += 1

            await status_msg.edit_text(f"✅ **Broadcast Done!**\n\n🟢 Sent: {success}\n🔴 Failed: {failed}", parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Broadcast error: {e}")

    async def handle_callbacks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            query = update.callback_query
            await query.answer()

            if query.data.startswith("setlang_"):
                lang_code = query.data.split("_")[1]
                await db.set_user_language(self.bot_id, query.from_user.id, lang_code)
                texts = LANGUAGES.get(lang_code, LANGUAGES["en"])
                await query.message.edit_text(f"✅ {texts['welcome']}\n\n🌐 Change language: /language")
            elif query.data == "check_fj":
                if await self.check_force_join(query.from_user.id):
                    await query.message.edit_text("✅ Joined! Now send me any video link.")
                else:
                    await query.answer("❌ You haven't joined yet!", show_alert=True)
        except Exception as e:
            logger.error(f"Callback error: {e}")

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Managed Bot Exception: {context.error}")
