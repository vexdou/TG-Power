import asyncio
import logging
import os
import re
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.error import TelegramError, Forbidden

from database import db
from downloader import downloader
from force_join import force_join_checker

logger = logging.getLogger(__name__)

CHANNEL_URL = "https://t.me/downloadermain"

LANGUAGES = {
    "en": {"name": "English 🇬🇧", "welcome": "👋 Welcome! Send me a video link from YouTube, TikTok, Facebook, Pinterest, Instagram, Snapchat or X/Twitter.", "invalid": "❌ Please send a valid video link.", "error": "❌ Error occurred."},
    "so": {"name": "Soomaali 🇸🇴", "welcome": "👋 Soo dhawoow! Ii soo dir link video ah oo ka socda YouTube, TikTok, Facebook, Pinterest, Instagram, Snapchat ama X/Twitter.", "invalid": "❌ Fadlan soo dir link video sax ah.", "error": "❌ Cilad ayaa dhacday."},
    "ar": {"name": "العربية 🇸🇦", "welcome": "👋 أهلاً بك! أرسل رابط فيديو من منصة مدعومة.", "invalid": "❌ يرجى إرسال رابط فيديو صحيح.", "error": "❌ حدث خطأ."},
    "es": {"name": "Español 🇪🇸", "welcome": "👋 ¡Bienvenido! Envíame un enlace de vídeo de una plataforma compatible.", "invalid": "❌ Envía un enlace válido.", "error": "❌ Ocurrió un error."},
    "fr": {"name": "Français 🇫🇷", "welcome": "👋 Bienvenue ! Envoyez un lien vidéo depuis une plateforme prise en charge.", "invalid": "❌ Envoyez un lien valide.", "error": "❌ Une erreur est survenue."},
    "tr": {"name": "Türkçe 🇹🇷", "welcome": "👋 Hoş geldiniz! Desteklenen bir platformdan video bağlantısı gönderin.", "invalid": "❌ Geçerli bir bağlantı gönderin.", "error": "❌ Bir hata oluştu."},
    "de": {"name": "Deutsch 🇩🇪", "welcome": "👋 Willkommen! Senden Sie einen Videolink von einer unterstützten Plattform.", "invalid": "❌ Bitte senden Sie einen gültigen Link.", "error": "❌ Ein Fehler ist aufgetreten."},
    "ru": {"name": "Русский 🇷🇺", "welcome": "👋 Добро пожаловать! Отправьте ссылку на видео с поддерживаемой платформы.", "invalid": "❌ Отправьте действующую ссылку.", "error": "❌ Произошла ошибка."},
    "hi": {"name": "हिन्दी 🇮🇳", "welcome": "👋 स्वागत है! किसी समर्थित प्लेटफ़ॉर्म का वीडियो लिंक भेजें।", "invalid": "❌ कृपया मान्य लिंक भेजें।", "error": "❌ त्रुटि।"},
    "pt": {"name": "Português 🇵🇹", "welcome": "👋 Bem-vindo! Envie um link de vídeo de uma plataforma suportada.", "invalid": "❌ Envie um link válido.", "error": "❌ Ocorreu um erro."},
}

URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)


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
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.app.add_error_handler(self.error_handler)

    def get_language_keyboard(self):
        keys = list(LANGUAGES)
        rows = []
        for i in range(0, len(keys), 2):
            row = [InlineKeyboardButton(LANGUAGES[keys[i]]["name"], callback_data=f"msetlang_{keys[i]}")]
            if i + 1 < len(keys):
                row.append(InlineKeyboardButton(LANGUAGES[keys[i + 1]]["name"], callback_data=f"msetlang_{keys[i + 1]}"))
            rows.append(row)
        return InlineKeyboardMarkup(rows)

    @staticmethod
    def get_channel_keyboard():
        return InlineKeyboardMarkup([[InlineKeyboardButton("CHANNEL 📢", url=CHANNEL_URL)]])

    async def _premium_state(self):
        active = await db.is_bot_premium(self.bot_id)
        settings = await db.get_bot_premium_settings(self.bot_id) if active else {}
        return active, settings

    @staticmethod
    def _custom_buttons(settings):
        rows = []
        for item in (settings.get("buttons") or [])[:10]:
            label = str(item.get("label", "Button"))[:64]
            url = str(item.get("url", "")).strip()
            if url.startswith(("http://", "https://", "tg://")):
                rows.append([InlineKeyboardButton(label, url=url)])
        return rows

    async def get_video_keyboard(self, url_key: str):
        premium, settings = await self._premium_state()
        rows = [[InlineKeyboardButton("MUSIC 🎵", callback_data=f"mconvert_{url_key}")]]
        rows.extend(self._custom_buttons(settings))
        return InlineKeyboardMarkup(rows)

    @staticmethod
    def extract_url(text: str) -> str | None:
        match = URL_RE.search(text or "")
        if not match:
            return None
        return match.group(0).rstrip(".,!?)]}>\"'")

    async def get_user_lang(self, user_id: int):
        user = await db.get_bot_user(self.bot_id, user_id)
        lang = (user or {}).get("language", "en")
        return lang if lang in LANGUAGES else "en"

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_user or not update.message:
            return
        user = update.effective_user
        existing = await db.get_bot_user(self.bot_id, user.id)
        first_start = not existing
        lang = (existing or {}).get("language", "en")
        if lang not in LANGUAGES:
            lang = "en"
        await db.save_bot_user(self.bot_id, user.id, user.username or "", user.full_name or "", lang)
        text = LANGUAGES[lang]["welcome"]
        await update.message.reply_text(
            text,
            reply_markup=self.get_language_keyboard() if first_start else None,
        )

    async def language_command(self, update, context):
        if update.message:
            await update.message.reply_text("🌐 Select Language / Dooro Luuqada:", reply_markup=self.get_language_keyboard())

    async def _maintenance_enabled(self):
        return bool(await db.get_system_setting("maintenance_mode", False))

    async def _force_join_channels(self):
        return await db.get_global_force_join_channels()

    @staticmethod
    def _channel_url(channel: str) -> str | None:
        if channel.startswith("@"):
            return f"https://t.me/{channel[1:]}"
        if channel.startswith("https://t.me/") or channel.startswith("http://t.me/"):
            return channel
        return None

    async def _is_joined_all(self, user_id: int, channels: list[str]) -> bool:
        # IMPORTANT: use the MAIN controller bot for every membership check.
        # Managed downloader bots do NOT need to be channel admins.
        ok, failed_channel = await force_join_checker.check_user(user_id, channels)
        if not ok:
            logger.info("Central Force-Join denied user=%s channel=%s", user_id, failed_channel)
        return ok

    def _force_join_keyboard(self, channels: list[str]):
        rows = []
        for i, channel in enumerate(channels, 1):
            url = self._channel_url(channel)
            label = f"📢 Channel {i}"
            if url:
                rows.append([InlineKeyboardButton(label, url=url)])
        rows.append([InlineKeyboardButton("✅ I Joined — Check", callback_data="fjcheck")])
        return InlineKeyboardMarkup(rows)

    async def _require_force_join(self, update: Update, url: str, user_id: int) -> bool:
        channels = await self._force_join_channels()
        if not channels:
            return False
        if await self._is_joined_all(user_id, channels):
            return False
        await db.set_pending_download(self.bot_id, user_id, url)
        target = update.message if update.message else None
        if target:
            await target.reply_text(
                "⚠️ You must join our Channel to Download Video ⚠️\n\n"
                "Join all required channels below, then press I Joined — Check.",
                reply_markup=self._force_join_keyboard(channels),
            )
        return True

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message or not update.effective_user:
            return
        url = self.extract_url(update.message.text or "")
        user_id = update.effective_user.id
        lang = await self.get_user_lang(user_id)
        texts = LANGUAGES[lang]

        if not url:
            await update.message.reply_text(texts["invalid"])
            return

        if await self._maintenance_enabled():
            await update.message.reply_text("🛠 The downloader is temporarily under maintenance. Please try again later.")
            return

        if await self._require_force_join(update, url, user_id):
            return

        await self.download_and_send(update.effective_chat.id, user_id, url, context, texts)

    async def download_and_send(self, chat_id: int, user_id: int, url: str, context, texts=None):
        texts = texts or LANGUAGES[await self.get_user_lang(user_id)]
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="upload_video")
        except Exception:
            pass

        premium, premium_settings = await self._premium_state()
        result = await downloader.download(url, user_id, premium=premium)
        if not result.get("success"):
            await context.bot.send_message(chat_id=chat_id, text=f"{texts['error']} {result.get('error', '')}".strip())
            return

        file_path = result["file_path"]
        url_key = str(abs(hash(f"{self.bot_id}:{user_id}:{url}")))[:16]
        self.url_cache[url_key] = url
        media_type = result.get("media_type", "video")

        try:
            caption = str(premium_settings.get("caption", "")).strip() if premium else ""
            ad_text = str(premium_settings.get("ad_text", "")).strip() if premium else ""
            # Premium bots never show system/custom ads. Admin-configured ads are
            # intentionally suppressed while Premium is active.
            if not premium and ad_text:
                caption = ad_text
            custom_rows = self._custom_buttons(premium_settings) if premium else []

            if media_type == "photo":
                await context.bot.send_chat_action(chat_id=chat_id, action="upload_photo")
                with open(file_path, "rb") as f:
                    await context.bot.send_photo(
                        chat_id=chat_id, photo=f, caption=caption or None,
                        reply_markup=InlineKeyboardMarkup(custom_rows) if custom_rows else None,
                    )
            elif media_type == "audio":
                await context.bot.send_chat_action(chat_id=chat_id, action="upload_audio")
                rows = [[InlineKeyboardButton("CHANNEL 📢", url=CHANNEL_URL)]]
                rows.extend(custom_rows)
                with open(file_path, "rb") as f:
                    await context.bot.send_audio(
                        chat_id=chat_id, audio=f, caption=caption or None,
                        reply_markup=InlineKeyboardMarkup(rows),
                    )
            else:
                await context.bot.send_chat_action(chat_id=chat_id, action="upload_video")
                rows = [[InlineKeyboardButton("MUSIC 🎵", callback_data=f"mconvert_{url_key}")]]
                rows.extend(custom_rows)
                with open(file_path, "rb") as f:
                    await context.bot.send_video(
                        chat_id=chat_id, video=f, caption=caption or None,
                        reply_markup=InlineKeyboardMarkup(rows),
                    )

            await db.add_download(
                self.bot_id, user_id, url=url,
                platform=result.get("platform", "general"),
                media_type=media_type, status="success",
                file_size=os.path.getsize(file_path),
            )
        except Exception as exc:
            logger.exception("Sending media failed")
            await context.bot.send_message(chat_id=chat_id, text=f"{texts['error']} {exc}")
        finally:
            downloader.cleanup(file_path)

    async def handle_callbacks(self, update, context):
        query = update.callback_query
        if not query:
            return
        data = query.data or ""

        if data.startswith("msetlang_"):
            await query.answer()
            lang = data.split("_", 1)[1]
            if lang in LANGUAGES:
                await db.update_bot_user_language(self.bot_id, query.from_user.id, lang)
                try:
                    await query.message.edit_text(LANGUAGES[lang]["welcome"], reply_markup=None)
                except Exception:
                    pass
            return

        if data == "fjcheck":
            await query.answer()
            uid = query.from_user.id
            channels = await self._force_join_channels()
            if await self._is_joined_all(uid, channels):
                pending = await db.get_pending_download(self.bot_id, uid)
                await db.clear_pending_download(self.bot_id, uid)
                try:
                    await query.message.delete()
                except Exception:
                    pass
                if pending and pending.get("url"):
                    await self.download_and_send(query.message.chat_id, uid, pending["url"], context)
            else:
                await query.answer("❌ You still need to join all required channels.", show_alert=True)
            return

        if not data.startswith("mconvert_"):
            await query.answer()
            return

        await query.answer()
        url_key = data.split("_", 1)[1]
        url = self.url_cache.get(url_key)
        if not url:
            await query.message.reply_text("❌ This video button has expired. Please send the link again.")
            return

        try:
            await context.bot.send_chat_action(chat_id=query.message.chat_id, action="upload_audio")
        except Exception:
            pass

        premium, premium_settings = await self._premium_state()
        result = await downloader.download_audio(url, query.from_user.id, premium=premium)
        if not result.get("success"):
            await query.message.reply_text(f"❌ {result.get('error', 'MP3 conversion failed')}")
            return

        file_path = result["file_path"]
        try:
            caption = str(premium_settings.get("caption", "")).strip() if premium else ""
            rows = [[InlineKeyboardButton("CHANNEL 📢", url=CHANNEL_URL)]]
            if premium:
                rows.extend(self._custom_buttons(premium_settings))
            with open(file_path, "rb") as f:
                await context.bot.send_audio(
                    chat_id=query.message.chat_id,
                    audio=f, caption=caption or None,
                    reply_markup=InlineKeyboardMarkup(rows),
                )
            await db.add_download(
                self.bot_id, query.from_user.id, url=url,
                platform=result.get("platform", "general"),
                media_type="audio", status="success",
                file_size=os.path.getsize(file_path),
            )
        except Exception as exc:
            logger.exception("Sending MP3 failed")
            await query.message.reply_text(f"❌ {exc}")
        finally:
            downloader.cleanup(file_path)

    async def stats_command(self, update, context):
        if not update.message or not update.effective_user:
            return
        bot = await db.get_bot(self.bot_id)
        if not bot or int(bot.get("owner_id", 0)) != update.effective_user.id:
            return
        stats = await db.get_bot_stats(self.bot_id)
        await update.message.reply_text(
            "📊 BOT OWNER STATS\n\n"
            f"👥 Users: {stats['total_users']}\n"
            f"📥 Downloads: {stats['total_downloads']}\n"
            f"🎬 Videos: {stats['videos']}\n"
            f"🎵 Audio: {stats['audio']}\n"
            f"🖼 Photos: {stats['photos']}"
        )

    async def broadcast_command(self, update, context):
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
        success = failed = 0
        for user in users:
            try:
                await self.app.bot.send_message(user["user_id"], text=text)
                success += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.04)
        await update.message.reply_text(f"📢 Broadcast complete.\n🟢 Sent: {success}\n🔴 Failed: {failed}")

    async def error_handler(self, update, context):
        logger.error("Managed Bot Exception [%s]: %s", self.bot_id, context.error, exc_info=True)
