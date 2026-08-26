import asyncio
import logging
import os
from urllib.parse import urlparse

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.constants import ChatAction
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
        "admin_panel": "⚙️ **ADMIN PANEL**\n\nSelect an option:",
        "broadcast_prompt": "📢 **BROADCAST MODE**\n\nSend me a message, photo, or video to broadcast to all users.",
        "broadcast_start": "📢 Broadcasting to {count} users...",
        "broadcast_success": "✅ Broadcast finished.\n\n📤 Sent: {sent}\n❌ Failed: {failed}",
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
        "admin_panel": "⚙️ **ADMIN PANEL**\n\nDooro waaxda aad rabto:",
        "broadcast_prompt": "📢 **BROADCAST MODE**\n\nSoo dir qoraal, sawir ama video si loogu diro dhammaan isticmaaleyaasha bot-ka.",
        "broadcast_start": "📢 Waxaa loo meel marinayaa {count} users...",
        "broadcast_success": "✅ Broadcast-gii waa dhammaaday.\n\n📤 Loo diray: {sent}\n❌ Ku dhowaad/Hurtay: {failed}",
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
        "admin_panel": "⚙️ **لوحة التحكم**\n\nاختر خيارًا:",
        "broadcast_prompt": "📢 **وضع الإذاعة**\n\nأرسل نصًا أو صورة أو فيديو لإرساله إلى جميع المستخدمين.",
        "broadcast_start": "📢 جارٍ الإرسال إلى {count} من المستخدمين...",
        "broadcast_success": "✅ اكتملت الإذاعة.\n\n📤 تم الإرسال: {sent}\n❌ فشل: {failed}",
    },
    "es": {
        "welcome": "👋 ¡Bienvenido!\n\nEnvíame un enlace público.",
        "invalid": "❌ Envía un enlace http/https válido.",
        "downloading": "⏳ Descargando... Por favor espera.",
        "music_downloading": "🎵 Convirtiendo a MP3...",
        "error": "❌ Error:",
        "music_ready": "🎵 Convirtiendo video a MP3...",
        "video_ready": "🎬 Modo VIDEO activado.",
        "language_changed": "✅ Idioma cambiado.",
        "select_language": "🌐 Selecciona tu idioma:",
        "stats": "📊 ESTADÍSTICAS DEL BOT",
        "users": "👥 Usuarios",
        "downloads": "📥 Descargas",
        "admin_panel": "⚙️ **PANEL DE CONTROL**",
        "broadcast_prompt": "📢 **MODO TRANSMISIÓN**",
        "broadcast_start": "📢 Transmitiendo a {count} usuarios...",
        "broadcast_success": "✅ Transmisión finalizada.\n\n📤 Enviados: {sent}\n❌ Fallidos: {failed}",
    },
    "fr": {
        "welcome": "👋 Bienvenue !",
        "invalid": "❌ Envoyez un lien http/https valide.",
        "downloading": "⏳ Téléchargement en cours...",
        "music_downloading": "🎵 Conversion en MP3...",
        "error": "❌ Erreur :",
        "music_ready": "🎵 Conversion en MP3...",
        "video_ready": "🎬 Mode VIDEO activé.",
        "language_changed": "✅ Langue modifiée.",
        "select_language": "🌐 Sélectionnez votre langue :",
        "stats": "📊 STATISTIQUES DU BOT",
        "users": "👥 Utilisateurs",
        "downloads": "📥 Téléchargements",
        "admin_panel": "⚙️ **PANNEAU D'ADMINISTRATION**",
        "broadcast_prompt": "📢 **MODE DIFFUSION**",
        "broadcast_start": "📢 Diffusion auprès de {count} utilisateurs...",
        "broadcast_success": "✅ Diffusion terminée.\n\n📤 Envoyés : {sent}\n❌ Échecs : {failed}",
    },
    "tr": {
        "welcome": "👋 Hoş geldiniz!",
        "invalid": "❌ Geçerli bir bağlantı gönderin.",
        "downloading": "⏳ İndiriliyor...",
        "music_downloading": "🎵 MP3'e dönüştürülüyor...",
        "error": "❌ Hata:",
        "music_ready": "🎵 MP3'e dönüştürülüyor...",
        "video_ready": "🎬 VIDEO modu etkinleştirildi.",
        "language_changed": "✅ Dil değiştirildi.",
        "select_language": "🌐 Dilinizi seçin:",
        "stats": "📊 BOT İSTATİSTİKLERİ",
        "users": "👥 Kullanıcılar",
        "downloads": "📥 İndirmeler",
        "admin_panel": "⚙️ **YÖNETİCİ PANELSİ**",
        "broadcast_prompt": "📢 **YAYIN MODU**",
        "broadcast_start": "📢 {count} kullanıcıya yayın yapılıyor...",
        "broadcast_success": "✅ Yayın tamamlandı.\n\n📤 Gönderilen: {sent}\n❌ Başarısız: {failed}",
    },
    "de": {
        "welcome": "👋 Willkommen!",
        "invalid": "❌ Bitte sende einen gültigen Link.",
        "downloading": "⏳ Herunterladen...",
        "music_downloading": "🎵 Konvertieren in MP3...",
        "error": "❌ Fehler:",
        "music_ready": "🎵 Konvertieren in MP3...",
        "video_ready": "🎬 VIDEO-Modus aktiviert.",
        "language_changed": "✅ Sprache geändert.",
        "select_language": "🌐 Sprache auswählen:",
        "stats": "📊 BOT-STATISTIKEN",
        "users": "👥 Benutzer",
        "downloads": "📥 Downloads",
        "admin_panel": "⚙️ **ADMIN-PANEL**",
        "broadcast_prompt": "📢 **BROADCAST-MODUS**",
        "broadcast_start": "📢 Senden an {count} Benutzer...",
        "broadcast_success": "✅ Broadcast beendet.\n\n📤 Gesendet: {sent}\n❌ Fehlschläge: {failed}",
    },
    "pt": {
        "welcome": "👋 Bem-vindo!",
        "invalid": "❌ Envie um link válido.",
        "downloading": "⏳ Baixando...",
        "music_downloading": "🎵 Convertendo para MP3...",
        "error": "❌ Erro:",
        "music_ready": "🎵 Convertendo para MP3...",
        "video_ready": "🎬 Modo VIDEO ativado.",
        "language_changed": "✅ Idioma alterado.",
        "select_language": "🌐 Selecione seu idioma:",
        "stats": "📊 ESTATÍSTICAS DO BOT",
        "users": "👥 Usuários",
        "downloads": "📥 Downloads",
        "admin_panel": "⚙️ **PAINEL DE ADMINISTRAÇÃO**",
        "broadcast_prompt": "📢 **MODO TRANSMISSÃO**",
        "broadcast_start": "📢 Transmitindo para {count} usuários...",
        "broadcast_success": "✅ Transmissão concluída.\n\n📤 Enviados: {sent}\n❌ Falhas: {failed}",
    },
    "hi": {
        "welcome": "👋 स्वागत है!",
        "invalid": "❌ कृपया सही लिंक भेजें।",
        "downloading": "⏳ डाउनलोड हो रहा है...",
        "music_downloading": "🎵 MP3 में बदला जा रहा है...",
        "error": "❌ त्रुटि:",
        "music_ready": "🎵 MP3 में बदला जा रहा है...",
        "video_ready": "🎬 VIDEO मोड सक्रिय है।",
        "language_changed": "✅ भाषा बदल दी गई।",
        "select_language": "🌐 अपनी भाषा चुनें:",
        "stats": "📊 BOT आँकड़े",
        "users": "👥 उपयोगकर्ता",
        "downloads": "📥 डाउनलोड",
        "admin_panel": "⚙️ **एडमिन पैनल**",
        "broadcast_prompt": "📢 **ब्रॉडकास्ट मोड**",
        "broadcast_start": "📢 {count} उपयोगकर्ताओं को भेजा जा रहा है...",
        "broadcast_success": "✅ ब्रॉडकास्ट पूरा हुआ。\n\n📤 भेजे गए: {sent}\n❌ असफल: {failed}",
    },
    "id": {
        "welcome": "👋 Selamat datang!",
        "invalid": "❌ Kirim tautan yang valid.",
        "downloading": "⏳ Mengunduh...",
        "music_downloading": "🎵 Mengonversi ke MP3...",
        "error": "❌ Kesalahan:",
        "music_ready": "🎵 Mengonversi ke MP3...",
        "video_ready": "🎬 Mode VIDEO aktif.",
        "language_changed": "✅ Bahasa berhasil diubah.",
        "select_language": "🌐 Pilih bahasa:",
        "stats": "📊 STATISTIK BOT",
        "users": "👥 Pengguna",
        "downloads": "📥 Unduhan",
        "admin_panel": "⚙️ **PANEL ADMIN**",
        "broadcast_prompt": "📢 **MODE SIARAN**",
        "broadcast_start": "📢 Menyiarkan ke {count} pengguna...",
        "broadcast_success": "✅ Siaran selesai.\n\n📤 Terkirim: {sent}\n❌ Gagal: {failed}",
    },
}


class ManagedBotHandler:
    def __init__(self, bot_id, token: str):
        self.bot_id = str(bot_id).lstrip("@").lower()
        self.token = token

        self.app = (
            Application.builder()
            .token(token)
            .concurrent_updates(True)
            .build()
        )

        self._setup_handlers()

    # =====================================================
    # KEYBOARDS & PREMIUM BUTTONS
    # =====================================================

    async def get_main_keyboard(self, user_id: int):
        if await self.is_owner(user_id):
            return ReplyKeyboardMarkup(
                [
                    [KeyboardButton("🌐 Language")],
                    [KeyboardButton("👨‍💼 Admin Panel")],
                ],
                resize_keyboard=True,
            )

        return ReplyKeyboardMarkup(
            [[KeyboardButton("🌐 Language")]],
            resize_keyboard=True,
        )

    def get_admin_keyboard(self):
        return ReplyKeyboardMarkup(
            [
                [KeyboardButton("📊 Stats"), KeyboardButton("📢 Broadcast")],
                [KeyboardButton("👥 Bot Users"), KeyboardButton("📥 Download Stats")],
                [KeyboardButton("⭐ Premium Status"), KeyboardButton("✏️ Start Message")],
                [KeyboardButton("🔘 Custom Buttons"), KeyboardButton("🎨 Premium Caption")],
                [KeyboardButton("📢 Premium Ads"), KeyboardButton("⚙️ Premium Settings")],
            ],
            resize_keyboard=True,
            is_persistent=True,
        )

    def video_music_keyboard(self):
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🎵 MUSIC",
                        callback_data="convert_music",
                    )
                ]
            ]
        )

    @staticmethod
    def _valid_button_url(url: str) -> bool:
        try:
            parsed = urlparse(url)
            return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
        except Exception:
            return False

    async def get_custom_keyboard(
        self,
        is_prem: bool,
        default_keyboard=None,
    ):
        keyboard = []

        if is_prem:
            try:
                settings = (
                    await db.get_bot_premium_settings(self.bot_id)
                    or {}
                )
                raw_buttons = settings.get("buttons", [])

                row = []

                for btn in raw_buttons[:10]:
                    label = str(
                        btn.get("label", "Button")
                    ).strip()[:64]

                    url = str(
                        btn.get("url", "")
                    ).strip()

                    if not label or not self._valid_button_url(url):
                        continue

                    row.append(
                        InlineKeyboardButton(
                            label,
                            url=url,
                        )
                    )

                    if len(row) == 2:
                        keyboard.append(row)
                        row = []

                if row:
                    keyboard.append(row)

            except Exception:
                logger.exception(
                    "Error building custom premium buttons"
                )

        if (
            default_keyboard
            and isinstance(
                default_keyboard,
                InlineKeyboardMarkup,
            )
        ):
            for row in default_keyboard.inline_keyboard:
                keyboard.append(row)

        elif default_keyboard and isinstance(
            default_keyboard,
            list,
        ):
            for row in default_keyboard:
                keyboard.append(row)

        return (
            InlineKeyboardMarkup(keyboard)
            if keyboard
            else None
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
                [
                    InlineKeyboardButton(
                        "Deutsch 🇩🇪",
                        callback_data="msetlang_de",
                    ),
                    InlineKeyboardButton(
                        "Português 🇵🇹",
                        callback_data="msetlang_pt",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "हिन्दी 🇮🇳",
                        callback_data="msetlang_hi",
                    ),
                    InlineKeyboardButton(
                        "Bahasa 🇮🇩",
                        callback_data="msetlang_id",
                    ),
                ],
            ]
        )

    # =====================================================
    # HANDLERS SETUP
    # =====================================================

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

        self.app.add_handler(
            MessageHandler(
                filters.PHOTO | filters.VIDEO,
                self.handle_broadcast_media,
            )
        )

        self.app.add_error_handler(
            self.error_handler
        )

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
            bot_data = await db.get_bot(
                self.bot_id
            )

            return bool(
                bot_data
                and int(
                    bot_data.get(
                        "owner_id",
                        0,
                    )
                )
                == int(user_id)
            )

        except Exception:
            logger.exception(
                "Could not check bot owner"
            )
            return False

    async def send_stats_msg(
        self,
        update: Update,
        user_id: int,
    ):
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
            reply_markup=await self.get_main_keyboard(
                user_id
            ),
        )

    async def execute_broadcast(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        user_id = update.effective_user.id
        lang = await self.get_language(user_id)
        texts = LANGUAGES[lang]

        users = await db.get_all_bot_users(
            self.bot_id
        )

        progress = await update.message.reply_text(
            texts.get(
                "broadcast_start",
                "📢 Broadcasting to {count} users...",
            ).format(count=len(users))
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
            success_text = texts.get(
                "broadcast_success",
                "✅ Broadcast finished.\n\n"
                "📤 Sent: {sent}\n"
                "❌ Failed: {failed}",
            ).format(
                sent=sent,
                failed=failed,
            )

            await progress.edit_text(
                success_text
            )

        except Exception:
            pass

    # =====================================================
    # START COMMAND
    # =====================================================

    async def start_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        if (
            not update.message
            or not update.effective_user
        ):
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
            logger.exception(
                "save_bot_user failed"
            )

        is_prem = await db.is_bot_premium(
            self.bot_id
        )

        settings = (
            await db.get_bot_premium_settings(
                self.bot_id
            )
            if is_prem
            else {}
        )

        custom_start = (
            settings.get("start_message")
            if is_prem
            else None
        )

        if custom_start:
            reply_markup = (
                await self.get_custom_keyboard(
                    is_prem,
                    None,
                )
            )

            await update.message.reply_text(
                custom_start,
                reply_markup=reply_markup,
            )

        else:
            await update.message.reply_text(
                "🌐 Select your language:",
                reply_markup=self.language_keyboard(),
            )

    # =====================================================
    # MEDIA HELPERS
    # =====================================================

    @staticmethod
    def _is_photo_file(path: str) -> bool:
        return str(path).lower().endswith(
            (
                ".jpg",
                ".jpeg",
                ".png",
                ".webp",
                ".gif",
            )
        )

    @staticmethod
    def _is_video_file(path: str) -> bool:
        return str(path).lower().endswith(
            (
                ".mp4",
                ".mkv",
                ".webm",
                ".mov",
                ".m4v",
            )
        )

    async def _send_photo_files(
        self,
        update: Update,
        paths: list[str],
        title: str,
        is_prem: bool,
        custom_caption=None,
    ):
        paths = [
            path
            for path in paths
            if path and os.path.isfile(path)
        ]

        if not paths:
            raise FileNotFoundError(
                "No photo files were found."
            )

        # Telegram allows max 10 items per media group.
        if len(paths) == 1:
            markup = await self.get_custom_keyboard(
                is_prem,
                None,
            )

            caption = (
                custom_caption
                if custom_caption
                else f"✅ {title[:900]}"
            )

            await context_message_reply_photo(
                update,
                paths[0],
                caption,
                markup,
            )
            return

        # Multiple TikTok slideshow images.
        for start in range(0, len(paths), 10):
            chunk = paths[start:start + 10]
            handles = []

            try:
                media = []

                for index, path in enumerate(chunk):
                    handle = open(path, "rb")
                    handles.append(handle)

                    media.append(
                        InputMediaPhoto(
                            media=handle,
                            caption=(
                                custom_caption
                                if (
                                    start == 0
                                    and index == 0
                                    and custom_caption
                                )
                                else (
                                    f"✅ {title[:900]}"
                                    if start == 0
                                    and index == 0
                                    else None
                                )
                            ),
                        )
                    )

                await update.message.reply_media_group(
                    media=media,
                )

            finally:
                for handle in handles:
                    try:
                        handle.close()
                    except Exception:
                        pass

        # Inline buttons cannot be attached to a media group.
        if is_prem:
            markup = await self.get_custom_keyboard(
                is_prem,
                None,
            )

            if markup:
                await update.message.reply_text(
                    "🔗",
                    reply_markup=markup,
                )

    # =====================================================
    # MESSAGE HANDLER
    # =====================================================

    async def handle_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        if (
            not update.message
            or not update.effective_user
        ):
            return

        user = update.effective_user
        text = (
            update.message.text
            or ""
        ).strip()

        lang = await self.get_language(
            user.id
        )
        texts = LANGUAGES[lang]

        # ---------------------------------------------
        # 1. BROADCAST CHECK
        # ---------------------------------------------
        if context.user_data.get(
            "broadcast_mode"
        ):
            if await self.is_owner(user.id):
                await self.execute_broadcast(
                    update,
                    context,
                )
                return

            context.user_data[
                "broadcast_mode"
            ] = False

        # ---------------------------------------------
        # PREMIUM ADMIN EDIT STATES
        # ---------------------------------------------
        if context.user_data.get("set_caption_mode"):
            if await self.is_owner(user.id):
                context.user_data.pop("set_caption_mode", None)
                settings = await db.get_bot_premium_settings(self.bot_id)
                settings["caption"] = text[:900]
                await db.update_bot_premium_settings(self.bot_id, settings)
                await update.message.reply_text("✅ Premium caption saved.", reply_markup=self.get_admin_keyboard())
                return
            context.user_data.pop("set_caption_mode", None)

        if context.user_data.get("set_ads_mode"):
            if await self.is_owner(user.id):
                context.user_data.pop("set_ads_mode", None)
                value = text.lower() in {"on", "yes", "1", "true", "enable", "enabled"}
                settings = await db.get_bot_premium_settings(self.bot_id)
                settings["ads_enabled"] = value
                await db.update_bot_premium_settings(self.bot_id, settings)
                await update.message.reply_text(f"✅ Premium ads are {'ON' if value else 'OFF'}.", reply_markup=self.get_admin_keyboard())
                return
            context.user_data.pop("set_ads_mode", None)

        # ---------------------------------------------
        # 1.1 ADMIN CUSTOM START EDIT MODE
        # ---------------------------------------------
        if context.user_data.get(
            "set_start_mode"
        ):
            if await self.is_owner(user.id):
                context.user_data[
                    "set_start_mode"
                ] = False

                try:
                    settings = (
                        await db.get_bot_premium_settings(
                            self.bot_id
                        )
                        or {}
                    )

                    settings[
                        "start_message"
                    ] = text

                    if hasattr(
                        db,
                        "update_bot_premium_settings",
                    ):
                        await db.update_bot_premium_settings(
                            self.bot_id,
                            settings,
                        )

                    await update.message.reply_text(
                        "✅ Fariinta /start waxaa loo badalay si guul leh!",
                        reply_markup=self.get_admin_keyboard(),
                    )

                except Exception as exc:
                    await update.message.reply_text(
                        f"❌ Cilad ayaa dhacday: {exc}",
                        reply_markup=self.get_admin_keyboard(),
                    )

                return

            context.user_data[
                "set_start_mode"
            ] = False

        # ---------------------------------------------
        # 1.2 ADMIN CUSTOM BUTTONS EDIT MODE
        # ---------------------------------------------
        if context.user_data.get(
            "set_buttons_mode"
        ):
            if await self.is_owner(user.id):
                context.user_data[
                    "set_buttons_mode"
                ] = False

                try:
                    lines = text.splitlines()
                    new_buttons = []

                    for line in lines:
                        if "|" not in line:
                            continue

                        label, url = line.split(
                            "|",
                            1,
                        )

                        label = label.strip()
                        url = url.strip()

                        if (
                            label
                            and self._valid_button_url(url)
                        ):
                            new_buttons.append(
                                {
                                    "label": label[:64],
                                    "url": url,
                                }
                            )

                    settings = (
                        await db.get_bot_premium_settings(
                            self.bot_id
                        )
                        or {}
                    )

                    settings["buttons"] = (
                        new_buttons[:10]
                    )

                    if hasattr(
                        db,
                        "update_bot_premium_settings",
                    ):
                        await db.update_bot_premium_settings(
                            self.bot_id,
                            settings,
                        )

                    await update.message.reply_text(
                        "✅ Si guul leh ayaa loo keydiyay "
                        f"{len(new_buttons[:10])} badhamo!",
                        reply_markup=self.get_admin_keyboard(),
                    )

                except Exception as exc:
                    await update.message.reply_text(
                        f"❌ Cilad ayaa dhacday: {exc}",
                        reply_markup=self.get_admin_keyboard(),
                    )

                return

            context.user_data[
                "set_buttons_mode"
            ] = False

        # ---------------------------------------------
        # 2. KEYBOARD BUTTON ACTIONS
        # ---------------------------------------------
        if text == "👥 Bot Users":
            if await self.is_owner(user.id):
                users = await db.get_all_bot_users(self.bot_id)
                await update.message.reply_text(f"👥 BOT USERS\n\nTotal: {len(users)}", reply_markup=self.get_admin_keyboard())
            return

        if text == "📥 Download Stats":
            if await self.is_owner(user.id):
                stats = await db.get_bot_stats(self.bot_id)
                await update.message.reply_text(
                    "📥 DOWNLOAD STATS\n\n"
                    f"Total: {stats.get('total_downloads', 0)}\n"
                    f"🎬 Videos: {stats.get('videos', 0)}\n"
                    f"🎵 Audio: {stats.get('audio', 0)}\n"
                    f"🖼 Photos: {stats.get('photos', 0)}",
                    reply_markup=self.get_admin_keyboard(),
                )
            return

        if text == "⭐ Premium Status":
            if await self.is_owner(user.id):
                bot = await db.get_bot(self.bot_id)
                premium = (bot or {}).get("premium") or {}
                active = await db.is_bot_premium(self.bot_id)
                await update.message.reply_text(
                    "⭐ PREMIUM STATUS\n\n"
                    f"Status: {'🟢 ACTIVE' if active else '🔴 INACTIVE'}\n"
                    f"Plan: {premium.get('plan', 'N/A')}\n"
                    f"Expires: {premium.get('until', 'N/A')}",
                    reply_markup=self.get_admin_keyboard(),
                )
            return

        if text == "🎨 Premium Caption":
            if await self.is_owner(user.id):
                context.user_data["set_caption_mode"] = True
                await update.message.reply_text("🎨 Send the Premium caption text:")
            return

        if text == "📢 Premium Ads":
            if await self.is_owner(user.id):
                context.user_data["set_ads_mode"] = True
                settings = await db.get_bot_premium_settings(self.bot_id)
                await update.message.reply_text(
                    f"📢 Current Premium ads: {'ON' if settings.get('ads_enabled') else 'OFF'}\n\nSend ON or OFF."
                )
            return

        if text == "⚙️ Premium Settings":
            if await self.is_owner(user.id):
                settings = await db.get_bot_premium_settings(self.bot_id)
                await update.message.reply_text(
                    "⚙️ PREMIUM SETTINGS\n\n"
                    f"Custom buttons: {len(settings.get('buttons', []))}/10\n"
                    f"Caption: {'configured' if settings.get('caption') else 'default'}\n"
                    f"Ads: {'ON' if settings.get('ads_enabled') else 'OFF'}",
                    reply_markup=self.get_admin_keyboard(),
                )
            return

        if text in [
            "🌐 Language",
            "Language",
        ]:
            await update.message.reply_text(
                texts["select_language"],
                reply_markup=self.language_keyboard(),
            )
            return

        if text in [
            "👨‍💼 Admin Panel",
            "Admin Panel",
        ]:
            if await self.is_owner(user.id):
                await update.message.reply_text(
                    texts.get(
                        "admin_panel",
                        "⚙️ **ADMIN PANEL**",
                    ),
                    parse_mode="Markdown",
                    reply_markup=self.get_admin_keyboard(),
                )
            return

        if text in [
            "🔙 Main Menu",
            "Main Menu",
        ]:
            await update.message.reply_text(
                "🔙 Main Menu",
                reply_markup=await self.get_main_keyboard(
                    user.id
                ),
            )
            return

        if text in [
            "📊 Stats",
            "Stats",
        ]:
            if await self.is_owner(user.id):
                await self.send_stats_msg(
                    update,
                    user.id,
                )
            return

        if text in [
            "📢 Broadcast",
            "Broadcast",
        ]:
            if await self.is_owner(user.id):
                context.user_data[
                    "broadcast_mode"
                ] = True

                await update.message.reply_text(
                    texts.get(
                        "broadcast_prompt",
                        "📢 **BROADCAST MODE**",
                    ),
                    parse_mode="Markdown",
                )
            return

        if text == "✏️ Start Message":
            if await self.is_owner(user.id):
                context.user_data[
                    "set_start_mode"
                ] = True

                await update.message.reply_text(
                    "✏️ **Fadlan soo dir qoraalka cusub "
                    "ee aad rabto inuu noqdo Fariinta /start:**\n\n"
                    "(Waxaad isticmaali kartaa Emoji ama qaabeynta Markdown).",
                    parse_mode="Markdown",
                )
            return

        if text == "🔘 Custom Buttons":
            if await self.is_owner(user.id):
                context.user_data[
                    "set_buttons_mode"
                ] = True

                await update.message.reply_text(
                    "🔲 **Fadlan soo dir badhamadaada adoo "
                    "raacinaya qaabkan (Line walba hal button):**\n\n"
                    "Magaca Button-ka | https://t.me/linkgaaga\n"
                    "Channel-keena | https://t.me/ChannelName\n"
                    "Group-ka | https://t.me/GroupName\n\n"
                    "(Ilaa 10 badhamo ayaad gelin kartaa).",
                    parse_mode="Markdown",
                )
            return

        # ---------------------------------------------
        # 3. MEDIA DOWNLOAD LOGIC
        # ---------------------------------------------
        url = text

        if not (
            url.startswith("http://")
            or url.startswith("https://")
        ):
            await update.message.reply_text(
                texts["invalid"],
                reply_markup=await self.get_main_keyboard(
                    user.id
                ),
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
            logger.exception(
                "Could not save bot user"
            )

        context.user_data[
            "last_url"
        ] = url

        status_msg = None
        file_paths = []

        is_prem = await db.is_bot_premium(
            self.bot_id
        )

        settings = (
            await db.get_bot_premium_settings(
                self.bot_id
            )
            if is_prem
            else {}
        )

        try:
            status_msg = (
                await update.message.reply_text(
                    texts["downloading"]
                )
            )

            logger.info(
                "Starting download bot=%s user=%s url=%s premium=%s",
                self.bot_id,
                user.id,
                url,
                is_prem,
            )

            result = await downloader.download(
                url=url,
                user_id=user.id,
                premium=is_prem,
            )

            if not result.get("success"):
                error_text = str(
                    result.get(
                        "error",
                        "Unknown download error.",
                    )
                )[:3000]

                await status_msg.edit_text(
                    f"{texts['error']}\n\n"
                    f"{error_text}",
                    reply_markup=await self.get_main_keyboard(
                        user.id
                    ),
                )
                return

            file_paths = [
                path
                for path in (
                    result.get("file_paths")
                    or [result.get("file_path")]
                )
                if path
                and os.path.isfile(path)
            ]

            if not file_paths:
                await status_msg.edit_text(
                    "❌ Download completed but output file was not found.",
                    reply_markup=await self.get_main_keyboard(
                        user.id
                    ),
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

            custom_caption = (
                settings.get("caption")
                if is_prem
                else None
            )

            # ---------------------------------------------
            # PHOTO / TIKTOK SLIDESHOW
            # ---------------------------------------------
            if (
                media_type == "photo"
                or all(
                    self._is_photo_file(path)
                    for path in file_paths
                )
            ):
                await context.bot.send_chat_action(
                    chat_id=user.id,
                    action=ChatAction.UPLOAD_PHOTO,
                )

                await self._send_photo_files(
                    update=update,
                    paths=file_paths,
                    title=title,
                    is_prem=is_prem,
                    custom_caption=custom_caption,
                )

            # ---------------------------------------------
            # AUDIO
            # ---------------------------------------------
            elif media_type == "audio":
                file_path = file_paths[0]

                await context.bot.send_chat_action(
                    chat_id=user.id,
                    action=ChatAction.UPLOAD_AUDIO,
                )

                audio_caption = (
                    custom_caption
                    if custom_caption
                    else f"🎵 {title[:900]}"
                )

                audio_markup = (
                    await self.get_custom_keyboard(
                        is_prem,
                        None,
                    )
                )

                with open(
                    file_path,
                    "rb",
                ) as audio:
                    await update.message.reply_audio(
                        audio=audio,
                        title=title[:64],
                        performer="TG-Power",
                        caption=audio_caption,
                        reply_markup=audio_markup,
                    )

            # ---------------------------------------------
            # VIDEO
            # ---------------------------------------------
            else:
                # A normal single video is expected.
                # If a downloader returns multiple video files,
                # send them one by one instead of silently losing them.
                video_paths = [
                    path
                    for path in file_paths
                    if self._is_video_file(path)
                ] or file_paths[:1]

                for index, file_path in enumerate(
                    video_paths
                ):
                    await context.bot.send_chat_action(
                        chat_id=user.id,
                        action=ChatAction.UPLOAD_VIDEO,
                    )

                    video_caption = (
                        custom_caption
                        if custom_caption
                        else f"✅ {title[:900]}"
                    )

                    reply_markup = (
                        await self.get_custom_keyboard(
                            is_prem,
                            self.video_music_keyboard()
                            if index == 0
                            else None,
                        )
                    )

                    with open(
                        file_path,
                        "rb",
                    ) as video:
                        await update.message.reply_video(
                            video=video,
                            caption=video_caption,
                            supports_streaming=True,
                            reply_markup=reply_markup,
                        )

            try:
                await db.log_download(
                    self.bot_id,
                    user.id,
                    platform,
                    url,
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
                        f"❌ Error:\n\n"
                        f"{str(exc)[:1500]}",
                        reply_markup=await self.get_main_keyboard(
                            user.id
                        ),
                    )
                except Exception:
                    pass

        finally:
            if file_paths:
                try:
                    downloader.cleanup(
                        file_paths
                    )
                except Exception:
                    logger.exception(
                        "Cleanup failed"
                    )

    # =====================================================
    # MUSIC FAST CONVERT BUTTON
    # =====================================================

    async def convert_music(
        self,
        query,
        context,
    ):
        user = query.from_user
        lang = await self.get_language(
            user.id
        )
        texts = LANGUAGES[lang]

        url = context.user_data.get(
            "last_url"
        )

        if not url:
            await query.message.reply_text(
                "❌ URL Not Found."
            )
            return

        status_msg = await query.message.reply_text(
            texts["music_downloading"]
        )

        file_paths = []
        mp3_path = None

        is_prem = await db.is_bot_premium(
            self.bot_id
        )

        try:
            result = await downloader.download(
                url=url,
                user_id=user.id,
                premium=is_prem,
            )

            if not result.get("success"):
                error_text = str(
                    result.get(
                        "error",
                        "Failed to download media",
                    )
                )[:3000]

                await status_msg.edit_text(
                    f"{texts['error']}\n\n"
                    f"{error_text}"
                )
                return

            file_paths = [
                path
                for path in (
                    result.get("file_paths")
                    or [result.get("file_path")]
                )
                if path
                and os.path.isfile(path)
            ]

            if not file_paths:
                await status_msg.edit_text(
                    "❌ File not found."
                )
                return

            # MUSIC is intended for video/audio media.
            source_path = next(
                (
                    path
                    for path in file_paths
                    if self._is_video_file(path)
                ),
                file_paths[0],
            )

            title = str(
                result.get(
                    "title",
                    "Audio Track",
                )
            )

            mp3_path = (
                os.path.splitext(
                    source_path
                )[0]
                + ".mp3"
            )

            proc = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-y",
                "-i",
                source_path,
                "-vn",
                "-acodec",
                "libmp3lame",
                "-b:a",
                "192k",
                mp3_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            _, stderr = await proc.communicate()

            if (
                proc.returncode != 0
                or not os.path.exists(mp3_path)
            ):
                error_detail = (
                    stderr.decode(
                        "utf-8",
                        errors="ignore",
                    )[-800:]
                    if stderr
                    else "FFmpeg conversion failed."
                )

                raise RuntimeError(
                    error_detail
                )

            await context.bot.send_chat_action(
                chat_id=user.id,
                action=ChatAction.UPLOAD_AUDIO,
            )

            audio_markup = (
                await self.get_custom_keyboard(
                    is_prem,
                    None,
                )
            )

            with open(
                mp3_path,
                "rb",
            ) as audio:
                await query.message.reply_audio(
                    audio=audio,
                    title=title[:64],
                    performer="TG-Power",
                    caption=f"🎵 {title[:900]}",
                    reply_markup=audio_markup,
                )

            try:
                await status_msg.delete()
            except Exception:
                pass

        except Exception as exc:
            logger.exception(
                "Music conversion error"
            )

            if status_msg:
                try:
                    await status_msg.edit_text(
                        f"{texts['error']}\n\n"
                        f"{str(exc)[:1500]}"
                    )
                except Exception:
                    pass

        finally:
            if mp3_path and os.path.exists(
                mp3_path
            ):
                try:
                    os.remove(mp3_path)
                except Exception:
                    pass

            if file_paths:
                try:
                    downloader.cleanup(
                        file_paths
                    )
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
                    user_id,
                    lang_code,
                )

                try:
                    await query.message.delete()
                except Exception:
                    pass

                texts = LANGUAGES[
                    lang_code
                ]

                await context.bot.send_message(
                    chat_id=user_id,
                    text=texts["welcome"],
                    reply_markup=await self.get_main_keyboard(
                        user_id
                    ),
                )
                return

            if data == "convert_music":
                await self.convert_music(
                    query,
                    context,
                )
                return

        except Exception:
            logger.exception(
                "Callback error for bot %s",
                self.bot_id,
            )

    # =====================================================
    # COMMAND HANDLERS
    # =====================================================

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

        user_id = update.effective_user.id

        if not await self.is_owner(
            user_id
        ):
            return

        await self.send_stats_msg(
            update,
            user_id,
        )

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

        user_id = update.effective_user.id

        if not await self.is_owner(
            user_id
        ):
            return

        lang = await self.get_language(
            user_id
        )
        texts = LANGUAGES[lang]

        context.user_data[
            "broadcast_mode"
        ] = True

        await update.message.reply_text(
            texts.get(
                "broadcast_prompt",
                "📢 **BROADCAST MODE**",
            ),
            parse_mode="Markdown",
        )

    # =====================================================
    # BROADCAST MEDIA HANDLER
    # =====================================================

    async def handle_broadcast_media(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        if (
            not update.message
            or not update.effective_user
        ):
            return

        user_id = update.effective_user.id

        if not context.user_data.get(
            "broadcast_mode"
        ):
            return

        if not await self.is_owner(
            user_id
        ):
            context.user_data[
                "broadcast_mode"
            ] = False
            return

        await self.execute_broadcast(
            update,
            context,
        )

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


async def context_message_reply_photo(
    update: Update,
    path: str,
    caption: str,
    reply_markup=None,
):
    with open(path, "rb") as photo:
        await update.message.reply_photo(
            photo=photo,
            caption=caption,
            reply_markup=reply_markup,
        )
