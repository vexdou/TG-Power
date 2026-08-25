import asyncio
import logging
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
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


# =========================================================
# LANGUAGES
# =========================================================

LANGUAGES = {
    "en": {
        "welcome": (
            "👋 Welcome!\n\n"
            "Send me a public video/media link from:\n"
            "YouTube, TikTok, Instagram, Facebook, "
            "X/Twitter, Pinterest or Snapchat.\n\n"
            "🎬 Send any video link to download it.\n"
            "🎵 Click the MUSIC button under the video to get MP3 audio."
        ),
        "invalid": "❌ Please send a valid http/https media link.",
        "downloading": "⏳ Downloading media... Please wait.",
        "music_downloading": "🎵 Downloading and converting to MP3... Please wait.",
        "error": "❌ Error:",
        "music_ready": "🎵 Converting video to MP3...",
        "video_ready": "🎬 VIDEO mode enabled.\n\nSend me a video/media link.",
        "language_changed": "✅ Language changed.",
        "select_language": "🌐 Select your language:",
        "stats": "📊 BOT OWNER STATS",
        "users": "👥 Users",
        "downloads": "📥 Downloads",
    },

    "so": {
        "welcome": (
            "👋 Soo dhawoow!\n\n"
            "Ii soo dir link public ah oo ka socda:\n"
            "YouTube, TikTok, Instagram, Facebook, "
            "X/Twitter, Pinterest ama Snapchat.\n\n"
            "🎬 Video: Link-ga soo dir si aad video u hesho.\n"
            "🎵 Music: Marka video-ga uu soo dhaco, taabo button-ka MUSIC 🎵 si aad MP3 ugu badalato."
        ),
        "invalid": "❌ Fadlan soo dir link http/https sax ah.",
        "downloading": "⏳ Video-ga ayaa la soo dejinayaa... Fadlan sug.",
        "music_downloading": "🎵 Music-ga ayaa la soo dejinayaa oo MP3 loo badalayaa... Fadlan sug.",
        "error": "❌ Cilad:",
        "music_ready": "🎵 Video-ga waxaa loo badalayaa MP3...",
        "video_ready": "🎬 VIDEO-ga waa diyaar.\n\nIi soo dir link video/media ah.",
        "language_changed": "✅ Luqadda waa la beddelay.",
        "select_language": "🌐 Dooro luuqadda:",
        "stats": "📊 XOGTA BOTKA",
        "users": "👥 Users",
        "downloads": "📥 Downloads",
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
        "music_downloading": "🎵 جارٍ تحويل الفيديو إلى MP3... يرجى الانتظار.",
        "error": "❌ خطأ:",
        "music_ready": "🎵 جارٍ تحويل الفيديو إلى MP3...",
        "video_ready": "🎬 تم تفعيل وضع VIDEO.",
        "language_changed": "✅ تم تغيير اللغة.",
        "select_language": "🌐 اختر لغتك:",
        "stats": "📊 إحصائيات البوت",
        "users": "👥 المستخدمون",
        "downloads": "📥 التنزيلات",
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
        "music_downloading": "🎵 Convirtiendo a MP3... Por favor espera.",
        "error": "❌ Error:",
        "music_ready": "🎵 Convirtiendo video a MP3...",
        "video_ready": "🎬 Modo VIDEO activado.",
        "language_changed": "✅ Idioma cambiado.",
        "select_language": "🌐 Selecciona tu idioma:",
        "stats": "📊 ESTADÍSTICAS DEL BOT",
        "users": "👥 Usuarios",
        "downloads": "📥 Descargas",
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
        "music_downloading": "🎵 Conversion en MP3... Veuillez patienter.",
        "error": "❌ Erreur :",
        "music_ready": "🎵 Conversion de la vidéo en MP3...",
        "video_ready": "🎬 Mode VIDEO activé.",
        "language_changed": "✅ Langue modifiée.",
        "select_language": "🌐 Sélectionnez votre langue :",
        "stats": "📊 STATISTIQUES DU BOT",
        "users": "👥 Utilisateurs",
        "downloads": "📥 Téléchargements",
    },

    "tr": {
        "welcome": (
            "👋 Hoş geldiniz!\n\n"
            "YouTube, TikTok, Instagram, Facebook, "
            "X, Pinterest veya Snapchat bağlantısı gönderin."
        ),
        "invalid": "❌ Geçerli bir http/https bağlantısı gönderin.",
        "downloading": "⏳ İndiriliyor... Lütfen bekleyin.",
        "music_downloading": "🎵 MP3'e dönüştürülüyor... Lütfen bekleyin.",
        "error": "❌ Hata:",
        "music_ready": "🎵 Video MP3'e dönüştürülüyor...",
        "video_ready": "🎬 VIDEO modu etkinleştirildi.",
        "language_changed": "✅ Dil değiştirildi.",
        "select_language": "🌐 Dilinizi seçin:",
        "stats": "📊 BOT İSTATİSTİKLERİ",
        "users": "👥 Kullanıcılar",
        "downloads": "📥 İndirmeler",
    },

    "de": {
        "welcome": "👋 Willkommen!\n\nSende mir einen öffentlichen Video-/Medienlink.",
        "invalid": "❌ Bitte sende einen gültigen http/https-Link.",
        "downloading": "⏳ Medien werden heruntergeladen...",
        "music_downloading": "🎵 Wird in MP3 konvertiert...",
        "error": "❌ Fehler:",
        "music_ready": "🎵 Video wird in MP3 konvertiert...",
        "video_ready": "🎬 VIDEO-Modus aktiviert.",
        "language_changed": "✅ Sprache geändert.",
        "select_language": "🌐 Sprache auswählen:",
        "stats": "📊 BOT-STATISTIKEN",
        "users": "👥 Benutzer",
        "downloads": "📥 Downloads",
    },

    "pt": {
        "welcome": "👋 Bem-vindo!\n\nEnvie um link público de vídeo/mídia.",
        "invalid": "❌ Envie um link http/https válido.",
        "downloading": "⏳ Baixando mídia...",
        "music_downloading": "🎵 Convertendo para MP3...",
        "error": "❌ Erro:",
        "music_ready": "🎵 Convertendo vídeo para MP3...",
        "video_ready": "🎬 Modo VIDEO ativado.",
        "language_changed": "✅ Idioma alterado.",
        "select_language": "🌐 Selecione seu idioma:",
        "stats": "📊 ESTATÍSTICAS DO BOT",
        "users": "👥 Usuários",
        "downloads": "📥 Downloads",
    },

    "hi": {
        "welcome": "👋 स्वागत है!\n\nYouTube, TikTok, Instagram आदि का सार्वजनिक लिंक भेजें।",
        "invalid": "❌ कृपया सही http/https लिंक भेजें।",
        "downloading": "⏳ मीडिया डाउनलोड हो रहा है...",
        "music_downloading": "🎵 MP3 में बदला जा रहा है...",
        "error": "❌ त्रुटि:",
        "music_ready": "🎵 वीडियो को MP3 में बदला जा रहा है...",
        "video_ready": "🎬 VIDEO मोड सक्रिय है।",
        "language_changed": "✅ भाषा बदल दी गई।",
        "select_language": "🌐 अपनी भाषा चुनें:",
        "stats": "📊 BOT आँकड़े",
        "users": "👥 उपयोगकर्ता",
        "downloads": "📥 डाउनलोड",
    },

    "id": {
        "welcome": "👋 Selamat datang!\n\nKirim tautan video/media publik.",
        "invalid": "❌ Kirim tautan http/https yang valid.",
        "downloading": "⏳ Media sedang diunduh...",
        "music_downloading": "🎵 Mengonversi ke MP3...",
        "error": "❌ Kesalahan:",
        "music_ready": "🎵 Mengonversi video ke MP3...",
        "video_ready": "🎬 Mode VIDEO aktif.",
        "language_changed": "✅ Bahasa berhasil diubah.",
        "select_language": "🌐 Pilih bahasa:",
        "stats": "📊 STATISTIK BOT",
        "users": "👥 Pengguna",
        "downloads": "📥 Unduhan",
    },
}


# =========================================================
# MANAGED BOT
# =========================================================

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

    # =====================================================
    # KEYBOARDS (REPLY KEYBOARDS & INLINE KEYBOARDS)
    # =====================================================

    async def get_main_keyboard(self, user_id: int):
        """Keyboard Button-nadu waa ReplyKeyboardMarkup ma aha Inline"""
        if await self.is_owner(user_id):
            return ReplyKeyboardMarkup(
                [
                    [KeyboardButton("🌐 Language")],
                    [KeyboardButton("👨‍💼 Admin Panel")]
                ],
                resize_keyboard=True
            )
        return ReplyKeyboardMarkup(
            [
                [KeyboardButton("🌐 Language")]
            ],
            resize_keyboard=True
        )

    def get_admin_keyboard(self):
        """Admin Panel menu keyboard buttons"""
        return ReplyKeyboardMarkup(
            [
                [KeyboardButton("📢 Broadcast"), KeyboardButton("📊 Stats")],
                [KeyboardButton("🔙 Main Menu")]
            ],
            resize_keyboard=True
        )

    def video_music_keyboard(self):
        """KALIYA MUSIC🎵 ayaa la soconaya video-ga"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🎵 MUSIC",
                    callback_data="convert_music",
                )
            ]
        ])

    def language_keyboard(self):
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("English 🇬🇧", callback_data="msetlang_en"),
                InlineKeyboardButton("Soomaali 🇸🇴", callback_data="msetlang_so"),
            ],
            [
                InlineKeyboardButton("العربية 🇸🇦", callback_data="msetlang_ar"),
                InlineKeyboardButton("Español 🇪🇸", callback_data="msetlang_es"),
            ],
            [
                InlineKeyboardButton("Français 🇫🇷", callback_data="msetlang_fr"),
                InlineKeyboardButton("Türkçe 🇹🇷", callback_data="msetlang_tr"),
            ],
            [
                InlineKeyboardButton("Deutsch 🇩🇪", callback_data="msetlang_de"),
                InlineKeyboardButton("Português 🇵🇹", callback_data="msetlang_pt"),
            ],
            [
                InlineKeyboardButton("हिन्दी 🇮🇳", callback_data="msetlang_hi"),
                InlineKeyboardButton("Bahasa 🇮🇩", callback_data="msetlang_id"),
            ],
        ])

    # =====================================================
    # HANDLERS SETUP
    # =====================================================

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

        self.app.add_handler(
            MessageHandler(
                filters.PHOTO | filters.VIDEO,
                self.handle_broadcast_media,
            )
        )

        self.app.add_error_handler(self.error_handler)

    # =====================================================
    # HELPERS
    # =====================================================

    async def get_language(self, user_id):
        try:
            user = await db.get_bot_user(
                self.bot_id,
                user_id,
            )

            lang = (
                (user or {}).get("language")
                or "en"
            )

            if lang not in LANGUAGES:
                lang = "en"

            return lang

        except Exception:
            logger.exception("Could not get language")
            return "en"

    async def is_owner(self, user_id):
        try:
            bot_data = await db.get_bot(self.bot_id)

            return bool(
                bot_data
                and int(bot_data.get("owner_id", 0)) == int(user_id)
            )

        except Exception:
            logger.exception("Could not check bot owner")
            return False

    async def send_stats_msg(self, update: Update, user_id: int):
        stats = await db.get_bot_stats(self.bot_id)
        lang = await self.get_language(user_id)
        texts = LANGUAGES[lang]

        await update.message.reply_text(
            f"{texts['stats']}\n\n"
            f"{texts['users']}: {stats.get('total_users', 0)}\n"
            f"{texts['downloads']}: {stats.get('total_downloads', 0)}",
            reply_markup=await self.get_main_keyboard(user_id),
        )

    # =====================================================
    # START COMMAND
    # =====================================================

    async def start_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        if not update.message or not update.effective_user:
            return

        user = update.effective_user

        try:
            await db.save_bot_user(
                self.bot_id,
                user.id,
                user.username or "",
                user.full_name or "",
            )
        except Exception:
            logger.exception("save_bot_user failed")

        # Marka /start la soo qoro mar walba Select your language ayaa loo soo dirayaa (Sida sawirka 2aad)
        await update.message.reply_text(
            "🌐 Select your language:",
            reply_markup=self.language_keyboard(),
        )

    # =====================================================
    # MESSAGE / DOWNLOAD / KEYBOARD BUTTON HANDLER
    # =====================================================

    async def handle_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        if not update.message or not update.effective_user:
            return

        user = update.effective_user
        text = (update.message.text or "").strip()

        # ---------------------------------------------
        # 1. KEYBOARD BUTTON ACTIONS
        # ---------------------------------------------
        if text in ["🌐 Language", "Language"]:
            await update.message.reply_text(
                "🌐 Select your language:",
                reply_markup=self.language_keyboard(),
            )
            return

        if text in ["👨‍💼 Admin Panel", "Admin Panel"]:
            if await self.is_owner(user.id):
                await update.message.reply_text(
                    "⚙️ **ADMIN PANEL**\n\nDooro waaxda aad rabto:",
                    parse_mode="Markdown",
                    reply_markup=self.get_admin_keyboard(),
                )
            return

        if text in ["🔙 Main Menu", "Main Menu"]:
            main_kbd = await self.get_main_keyboard(user.id)
            await update.message.reply_text(
                "🔙 Main Menu",
                reply_markup=main_kbd,
            )
            return

        if text in ["📊 Stats", "Stats"]:
            if await self.is_owner(user.id):
                await self.send_stats_msg(update, user.id)
                return

        if text in ["📢 Broadcast", "Broadcast"]:
            if await self.is_owner(user.id):
                context.user_data["broadcast_mode"] = True
                await update.message.reply_text(
                    "📢 **BROADCAST MODE**\n\n"
                    "Soo dir qoraal, sawir ama video si loogu diro dhammaan isticmaaleyaasha bot-ka.",
                    parse_mode="Markdown",
                )
                return

        # ---------------------------------------------
        # 2. MEDIA DOWNLOAD LOGIC
        # ---------------------------------------------
        url = text

        if not (url.startswith("http://") or url.startswith("https://")):
            lang = await self.get_language(user.id)
            texts = LANGUAGES[lang]

            await update.message.reply_text(
                texts["invalid"],
                reply_markup=await self.get_main_keyboard(user.id),
            )
            return

        try:
            await db.save_bot_user(
                self.bot_id,
                user.id,
                user.username or "",
                user.full_name or "",
            )
        except Exception:
            logger.exception("Could not save bot user")

        # Save active URL for fast MP3 conversion
        context.user_data["last_url"] = url

        lang = await self.get_language(user.id)
        texts = LANGUAGES[lang]

        status_msg = None
        file_path = None

        try:
            status_msg = await update.message.reply_text(texts["downloading"])

            logger.info(
                "Starting download bot=%s user=%s url=%s",
                self.bot_id,
                user.id,
                url,
            )

            result = await downloader.download(
                url=url,
                user_id=user.id,
                premium=False,
            )

            if not result.get("success"):
                error_text = str(
                    result.get(
                        "error",
                        "Unknown download error.",
                    )
                )[:3000]

                await status_msg.edit_text(
                    f"{texts['error']}\n\n{error_text}",
                    reply_markup=await self.get_main_keyboard(user.id),
                )
                return

            file_path = result.get("file_path")

            if not file_path or not os.path.isfile(file_path):
                await status_msg.edit_text(
                    "❌ Download completed but output file was not found.",
                    reply_markup=await self.get_main_keyboard(user.id),
                )
                return

            title = str(result.get("title", "Downloaded Media"))
            platform = result.get("platform", "general")
            media_type = result.get("media_type", "video")

            # ---------------------------------------------
            # SEND DOWNLOADED MEDIA WITH MUSIC 🎵 BUTTON
            # ---------------------------------------------

            if media_type == "audio":
                with open(file_path, "rb") as audio:
                    await update.message.reply_audio(
                        audio=audio,
                        title=title[:64],
                        performer="TG-Power",
                        caption=f"🎵 {title[:900]}",
                    )

            elif media_type == "photo":
                with open(file_path, "rb") as photo:
                    await update.message.reply_photo(
                        photo=photo,
                        caption=f"✅ {title[:900]}",
                    )

            else:
                # Video-ga kaliya waxaa la socda Inline Button-ka MUSIC 🎵
                with open(file_path, "rb") as video:
                    await update.message.reply_video(
                        video=video,
                        caption=f"✅ {title[:900]}",
                        supports_streaming=True,
                        reply_markup=self.video_music_keyboard(),
                    )

            try:
                await db.log_download(
                    self.bot_id,
                    user.id,
                    platform,
                    media_type,
                )
            except Exception:
                logger.exception("Could not log download")

            try:
                await status_msg.delete()
            except Exception:
                pass

        except Exception as exc:
            logger.exception("Managed bot download error")
            if status_msg:
                try:
                    await status_msg.edit_text(
                        f"❌ Error:\n\n{str(exc)[:1500]}",
                        reply_markup=await self.get_main_keyboard(user.id),
                    )
                except Exception:
                    pass

        finally:
            if file_path:
                try:
                    downloader.cleanup(file_path)
                except Exception:
                    logger.exception("Cleanup failed")

    # =====================================================
    # MUSIC FAST CONVERT BUTTON (CALLBACK)
    # =====================================================

    async def convert_music(
        self,
        query,
        context,
    ):
        """Marka 🎵 MUSIC button-ka la taabto si madafsan MP3 ugu badal video-ga"""
        user = query.from_user
        lang = await self.get_language(user.id)
        texts = LANGUAGES[lang]

        url = context.user_data.get("last_url")

        if not url:
            await query.message.reply_text(
                "❌ Fadlan soo dir link-ga video-ga mar kale."
            )
            return

        status_msg = await query.message.reply_text(texts["music_downloading"])
        file_path = None

        try:
            # MP3 audio extraction
            result = await downloader.download(
                url=url,
                user_id=user.id,
                premium=False,
                media_type="audio",
            )

            if not result.get("success"):
                error_text = str(result.get("error", "Failed to convert music"))[:3000]
                await status_msg.edit_text(f"{texts['error']}\n\n{error_text}")
                return

            file_path = result.get("file_path")

            if file_path and os.path.isfile(file_path):
                title = str(result.get("title", "Audio Track"))
                with open(file_path, "rb") as audio:
                    await query.message.reply_audio(
                        audio=audio,
                        title=title[:64],
                        performer="TG-Power",
                        caption=f"🎵 {title[:900]}",
                    )
                await status_msg.delete()
            else:
                await status_msg.edit_text("❌ MP3 file error.")

        except Exception as exc:
            logger.exception("Music conversion error")
            if status_msg:
                try:
                    await status_msg.edit_text(f"❌ Error:\n\n{str(exc)[:1500]}")
                except Exception:
                    pass
        finally:
            if file_path:
                try:
                    downloader.cleanup(file_path)
                except Exception:
                    pass

    # =====================================================
    # CALLBACKS
    # =====================================================

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
            user_id = query.from_user.id

            # ---------------------------------------------
            # LANGUAGE SELECTION & DELETE MESSAGE
            # ---------------------------------------------
            if data.startswith("msetlang_"):
                lang_code = data.split("_", 1)[1]

                if lang_code not in LANGUAGES:
                    lang_code = "en"

                await db.set_user_language(
                    self.bot_id,
                    user_id,
                    lang_code,
                )

                # 1. Tirtir doorashadii luqadda (delete message)
                try:
                    await query.message.delete()
                except Exception:
                    pass

                texts = LANGUAGES[lang_code]
                main_kbd = await self.get_main_keyboard(user_id)

                # 2. Soo dir sharaxaad botka iyo sidu u shaqeyo + ReplyKeyboard
                await context.bot.send_message(
                    chat_id=user_id,
                    text=texts["welcome"],
                    reply_markup=main_kbd,
                )
                return

            # ---------------------------------------------
            # MUSIC CONVERT
            # ---------------------------------------------
            if data == "convert_music":
                await self.convert_music(query, context)
                return

        except Exception:
            logger.exception("Callback error for bot %s", self.bot_id)

    # =====================================================
    # COMMAND HANDLERS
    # =====================================================

    async def stats_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        if not update.message or not update.effective_user:
            return

        user_id = update.effective_user.id

        if not await self.is_owner(user_id):
            return

        await self.send_stats_msg(update, user_id)

    async def broadcast_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        if not update.message or not update.effective_user:
            return

        user_id = update.effective_user.id

        if not await self.is_owner(user_id):
            return

        context.user_data["broadcast_mode"] = True

        await update.message.reply_text(
            "📢 **BROADCAST MODE**\n\n"
            "Soo dir qoraal, sawir ama video. Waxaa loo diri doonaa dhammaan users-ka bot-ka.",
            parse_mode="Markdown",
        )

    # =====================================================
    # BROADCAST MEDIA / MESSAGE HANDLER
    # =====================================================

    async def handle_broadcast_media(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        if not update.message or not update.effective_user:
            return

        user_id = update.effective_user.id

        if not context.user_data.get("broadcast_mode"):
            return

        if not await self.is_owner(user_id):
            context.user_data["broadcast_mode"] = False
            return

        users = await db.get_all_bot_users(self.bot_id)

        progress = await update.message.reply_text(
            f"📢 Broadcasting to {len(users)} users..."
        )

        sent = 0
        failed = 0

        for bot_user in users:
            target_id = bot_user.get("user_id")

            if not target_id:
                continue

            try:
                if update.message.text:
                    await self.app.bot.send_message(
                        chat_id=target_id,
                        text=update.message.text,
                    )
                elif update.message.photo:
                    photo = update.message.photo[-1]
                    await self.app.bot.send_photo(
                        chat_id=target_id,
                        photo=photo.file_id,
                        caption=update.message.caption or "",
                    )
                elif update.message.video:
                    await self.app.bot.send_video(
                        chat_id=target_id,
                        video=update.message.video.file_id,
                        caption=update.message.caption or "",
                    )
                else:
                    continue

                sent += 1
                await asyncio.sleep(0.05)

            except Exception as exc:
                failed += 1
                logger.warning(
                    "Broadcast failed user=%s error=%s",
                    target_id,
                    exc,
                )

        context.user_data["broadcast_mode"] = False

        try:
            await progress.edit_text(
                "✅ Broadcast finished.\n\n"
                f"📤 Sent: {sent}\n"
                f"❌ Failed: {failed}"
            )
        except Exception:
            pass

    # =====================================================
    # ERROR HANDLER
    # =====================================================

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
