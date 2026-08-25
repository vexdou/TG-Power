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


# =========================================================
# LANGUAGES
# =========================================================

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
            "🎬 Video: link-ga soo dir si aad video u hesho.\n"
            "🎵 Music: marka video-ga la soo diro kadib "
            "button-ka MUSIC 🎵 ayaa kuu soo bixi doona."
        ),
        "invalid": "❌ Fadlan soo dir link http/https sax ah.",
        "downloading": "⏳ Video-ga ayaa la soo dejinayaa... Fadlan sug.",
        "music_downloading": "🎵 Music-ga ayaa la soo dejinayaa oo MP3 loo badalayaa... Fadlan sug.",
        "error": "❌ Cilad:",
        "music_ready": "🎵 MUSIC-ga waa diyaar.\n\nHadda video-ga la soo diray MP3 ayaan kuu badalayaa.",
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
        "music_downloading": "🎵 جارٍ تنزيل الصوت وتحويله إلى MP3... يرجى الانتظار.",
        "error": "❌ خطأ:",
        "music_ready": "🎵 تم تفعيل وضع MUSIC.\n\nأرسل رابط فيديو لتحويله إلى MP3.",
        "video_ready": "🎬 تم تفعيل وضع VIDEO.\n\nأرسل رابط فيديو.",
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
        "music_downloading": "🎵 Descargando y convirtiendo a MP3... Por favor espera.",
        "error": "❌ Error:",
        "music_ready": "🎵 Modo MUSIC activado.\n\nEnvíame un video para convertirlo a MP3.",
        "video_ready": "🎬 Modo VIDEO activado.\n\nEnvíame un enlace de video.",
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
        "music_downloading": "🎵 Téléchargement et conversion en MP3... Veuillez patienter.",
        "error": "❌ Erreur :",
        "music_ready": "🎵 Mode MUSIC activé.\n\nEnvoyez un lien vidéo pour le convertir en MP3.",
        "video_ready": "🎬 Mode VIDEO activé.\n\nEnvoyez un lien vidéo.",
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
        "music_downloading": "🎵 İndiriliyor ve MP3'e dönüştürülüyor... Lütfen bekleyin.",
        "error": "❌ Hata:",
        "music_ready": "🎵 MUSIC modu etkinleştirildi.\n\nMP3'e dönüştürmek için video bağlantısı gönderin.",
        "video_ready": "🎬 VIDEO modu etkinleştirildi.\n\nVideo bağlantısı gönderin.",
        "language_changed": "✅ Dil değiştirildi.",
        "select_language": "🌐 Dilinizi seçin:",
        "stats": "📊 BOT İSTATİSTİKLERİ",
        "users": "👥 Kullanıcılar",
        "downloads": "📥 İndirmeler",
    },

    # Extra languages
    "de": {
        "welcome": "👋 Willkommen!\n\nSende mir einen öffentlichen Video-/Medienlink.",
        "invalid": "❌ Bitte sende einen gültigen http/https-Link.",
        "downloading": "⏳ Medien werden heruntergeladen...",
        "music_downloading": "🎵 Audio wird heruntergeladen und in MP3 konvertiert...",
        "error": "❌ Fehler:",
        "music_ready": "🎵 MUSIC-Modus aktiviert.",
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
        "music_downloading": "🎵 Baixando e convertendo para MP3...",
        "error": "❌ Erro:",
        "music_ready": "🎵 Modo MUSIC ativado.",
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
        "music_downloading": "🎵 ऑडियो डाउनलोड करके MP3 में बदला जा रहा है...",
        "error": "❌ त्रुटि:",
        "music_ready": "🎵 MUSIC मोड सक्रिय है।",
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
        "music_downloading": "🎵 Audio sedang diunduh dan dikonversi ke MP3...",
        "error": "❌ Kesalahan:",
        "music_ready": "🎵 Mode MUSIC aktif.",
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
    # KEYBOARDS
    # =====================================================

    def main_keyboard(self, is_owner=False):
        rows = [
            [
                InlineKeyboardButton(
                    "🌐 LANGUAGE",
                    callback_data="show_languages",
                )
            ]
        ]

        if is_owner:
            rows.append([
                InlineKeyboardButton(
                    "📢 BROADCAST",
                    callback_data="owner_broadcast",
                ),
                InlineKeyboardButton(
                    "📊 STATS",
                    callback_data="owner_stats",
                ),
            ])

        return InlineKeyboardMarkup(rows)

    def video_music_keyboard(self, is_owner=False):
        rows = [
            [
                InlineKeyboardButton(
                    "🎵 MUSIC",
                    callback_data="convert_music",
                )
            ],
            [
                InlineKeyboardButton(
                    "🌐 LANGUAGE",
                    callback_data="show_languages",
                )
            ],
        ]

        if is_owner:
            rows.append([
                InlineKeyboardButton(
                    "📢 BROADCAST",
                    callback_data="owner_broadcast",
                ),
                InlineKeyboardButton(
                    "📊 STATS",
                    callback_data="owner_stats",
                ),
            ])

        return InlineKeyboardMarkup(rows)

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
    # HANDLERS
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
            logger.exception(
                "Could not get language"
            )
            return "en"

    async def is_owner(self, user_id):
        try:
            bot_data = await db.get_bot(self.bot_id)

            return bool(
                bot_data
                and int(bot_data.get("owner_id", 0))
                == int(user_id)
            )

        except Exception:
            logger.exception(
                "Could not check bot owner"
            )
            return False

    async def owner_keyboard(self, user_id):
        return self.main_keyboard(
            await self.is_owner(user_id)
        )

    # =====================================================
    # START
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

        # Check if this is first use
        bot_user = None

        try:
            bot_user = await db.get_bot_user(
                self.bot_id,
                user.id,
            )
        except Exception:
            pass

        language = (
            (bot_user or {}).get("language")
            or ""
        )

        # First start: force language selection
        if not language:
            await update.message.reply_text(
                "🌐 Welcome!\n\n"
                "Please select your language first:",
                reply_markup=self.language_keyboard(),
            )
            return

        language = (
            language
            if language in LANGUAGES
            else "en"
        )

        texts = LANGUAGES[language]

        await update.message.reply_text(
            texts["welcome"],
            reply_markup=await self.owner_keyboard(user.id),
        )

    # =====================================================
    # MESSAGE / DOWNLOAD
    # =====================================================

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

        if not (
            url.startswith("http://")
            or url.startswith("https://")
        ):
            lang = await self.get_language(user.id)
            texts = LANGUAGES[lang]

            await update.message.reply_text(
                texts["invalid"],
                reply_markup=await self.owner_keyboard(user.id),
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

        lang = await self.get_language(user.id)
        texts = LANGUAGES[lang]

        status_msg = None
        file_path = None

        try:
            status_msg = await update.message.reply_text(
                texts["downloading"]
            )

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
                    reply_markup=await self.owner_keyboard(user.id),
                )
                return

            file_path = result.get("file_path")

            if not file_path:
                await status_msg.edit_text(
                    "❌ Download completed but no output file was produced.",
                    reply_markup=await self.owner_keyboard(user.id),
                )
                return

            if not os.path.isfile(file_path):
                await status_msg.edit_text(
                    "❌ The downloaded file could not be found.",
                    reply_markup=await self.owner_keyboard(user.id),
                )
                return

            title = str(
                result.get(
                    "title",
                    "Downloaded Media",
                )
            )

            platform = result.get(
                "platform",
                "general",
            )

            media_type = result.get(
                "media_type",
                "video",
            )

            # ---------------------------------------------
            # SEND DOWNLOADED MEDIA
            # ---------------------------------------------

            if media_type == "audio":

                with open(
                    file_path,
                    "rb",
                ) as audio:

                    await update.message.reply_audio(
                        audio=audio,
                        title=title[:64],
                        performer="TG-Power",
                        caption=f"🎵 {title[:900]}",
                        reply_markup=self.video_music_keyboard(
                            await self.is_owner(user.id)
                        ),
                    )

            elif media_type == "photo":

                with open(
                    file_path,
                    "rb",
                ) as photo:

                    await update.message.reply_photo(
                        photo=photo,
                        caption=f"✅ {title[:900]}",
                        reply_markup=self.video_music_keyboard(
                            await self.is_owner(user.id)
                        ),
                    )

            else:

                with open(
                    file_path,
                    "rb",
                ) as video:

                    await update.message.reply_video(
                        video=video,
                        caption=f"✅ {title[:900]}",
                        supports_streaming=True,
                        reply_markup=self.video_music_keyboard(
                            await self.is_owner(user.id)
                        ),
                    )

            try:
                await db.log_download(
                    self.bot_id,
                    user.id,
                    platform,
                    media_type,
                )
            except Exception:
                logger.exception(
                    "Could not log download"
                )

            try:
                await status_msg.delete()
            except Exception:
                pass

        except Exception as exc:

            logger.exception(
                "Managed bot download error"
            )

            if status_msg:
                try:
                    await status_msg.edit_text(
                        f"❌ Error:\n\n{str(exc)[:1500]}",
                        reply_markup=await self.owner_keyboard(user.id),
                    )
                except Exception:
                    pass

        finally:

            if file_path:
                try:
                    downloader.cleanup(file_path)
                except Exception:
                    logger.exception(
                        "Cleanup failed"
                    )

    # =====================================================
    # MUSIC BUTTON
    # =====================================================

    async def convert_music(
        self,
        query,
        context,
    ):
        """
        MUSIC button:
        Telegram callback itself does not contain the original URL.
        The bot asks the user to send the same URL again.
        """

        user = query.from_user

        lang = await self.get_language(
            user.id
        )

        texts = LANGUAGES[lang]

        context.user_data[
            "music_next"
        ] = True

        if query.message:
            await query.message.reply_text(
                texts["music_ready"]
            )

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
            # LANGUAGE
            # ---------------------------------------------

            if data == "show_languages":

                await query.message.reply_text(
                    "🌐 Select your language:",
                    reply_markup=self.language_keyboard(),
                )
                return

            if data.startswith("msetlang_"):

                lang_code = data.split(
                    "_",
                    1,
                )[1]

                if lang_code not in LANGUAGES:
                    lang_code = "en"

                await db.set_user_language(
                    self.bot_id,
                    user_id,
                    lang_code,
                )

                texts = LANGUAGES[lang_code]

                await query.message.edit_text(
                    f"{texts['language_changed']}\n\n"
                    f"{texts['welcome']}",
                    reply_markup=await self.owner_keyboard(
                        user_id
                    ),
                )

                return

            # ---------------------------------------------
            # MUSIC
            # ---------------------------------------------

            if data == "convert_music":

                await self.convert_music(
                    query,
                    context,
                )
                return

            # ---------------------------------------------
            # OWNER STATS
            # ---------------------------------------------

            if data == "owner_stats":

                if not await self.is_owner(user_id):
                    return

                stats = await db.get_bot_stats(
                    self.bot_id
                )

                lang = await self.get_language(
                    user_id
                )

                texts = LANGUAGES[lang]

                await query.message.reply_text(
                    f"{texts['stats']}\n\n"
                    f"{texts['users']}: "
                    f"{stats.get('total_users', 0)}\n"
                    f"{texts['downloads']}: "
                    f"{stats.get('total_downloads', 0)}"
                )

                return

            # ---------------------------------------------
            # OWNER BROADCAST
            # ---------------------------------------------

            if data == "owner_broadcast":

                if not await self.is_owner(user_id):
                    return

                context.user_data[
                    "broadcast_mode"
                ] = True

                await query.message.reply_text(
                    "📢 BROADCAST MODE\n\n"
                    "Send me a message, photo or video.\n"
                    "It will be sent to all users of this bot."
                )

                return

        except Exception:

            logger.exception(
                "Callback error for bot %s",
                self.bot_id,
            )

    # =====================================================
    # STATS COMMAND
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

        try:

            stats = await db.get_bot_stats(
                self.bot_id
            )

            lang = await self.get_language(
                user_id
            )

            texts = LANGUAGES[lang]

            await update.message.reply_text(
                f"{texts['stats']}\n\n"
                f"{texts['users']}: "
                f"{stats.get('total_users', 0)}\n"
                f"{texts['downloads']}: "
                f"{stats.get('total_downloads', 0)}",
                reply_markup=await self.owner_keyboard(
                    user_id
                ),
            )

        except Exception:

            logger.exception(
                "Stats error"
            )

    # =====================================================
    # BROADCAST COMMAND
    # =====================================================

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

        context.user_data[
            "broadcast_mode"
        ] = True

        await update.message.reply_text(
            "📢 BROADCAST MODE\n\n"
            "Send me a message, photo or video.\n"
            "It will be sent to all users of this bot."
        )

    # =====================================================
    # BROADCAST MEDIA / MESSAGE
    # =====================================================

    async def handle_broadcast_media(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        if not update.message or not update.effective_user:
            return

        user_id = update.effective_user.id

        if not context.user_data.get(
            "broadcast_mode"
        ):
            return

        if not await self.is_owner(user_id):
            context.user_data[
                "broadcast_mode"
            ] = False
            return

        users = await db.get_all_bot_users(
            self.bot_id
        )

        progress = await update.message.reply_text(
            f"📢 Broadcasting to {len(users)} users..."
        )

        sent = 0
        failed = 0

        for bot_user in users:

            target_id = bot_user.get(
                "user_id"
            )

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
                        caption=(
                            update.message.caption
                            or ""
                        ),
                    )

                elif update.message.video:

                    await self.app.bot.send_video(
                        chat_id=target_id,
                        video=update.message.video.file_id,
                        caption=(
                            update.message.caption
                            or ""
                        ),
                    )

                else:
                    continue

                sent += 1

                await asyncio.sleep(
                    0.05
                )

            except Exception as exc:

                failed += 1

                logger.warning(
                    "Broadcast failed user=%s error=%s",
                    target_id,
                    exc,
                )

        context.user_data[
            "broadcast_mode"
        ] = False

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
