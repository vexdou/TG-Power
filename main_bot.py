import time
import asyncio
import logging
import aiohttp
import psutil
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
)
from config import Config
from database import db
from bot_manager import bot_manager

logger = logging.getLogger(__name__)

# 10 Languages for Main Platform Bot
MAIN_LANGUAGES = {
    "en": {"name": "English 🇬🇧", "welcome": "👋 Welcome to Bot Builder Platform! Create and manage your own downloader bots effortlessly.", "choose_lang": "🌐 Choose your language:", "create_btn": "➕ Create New Bot", "my_bots_btn": "🤖 My Bots", "help_btn": "ℹ️ Help", "lang_btn": "🌐 Language"},
    "so": {"name": "Soomaali 🇸🇴", "welcome": "👋 Soo dhawoow Platform-ka Dhisidda Bot-yada! Ka dhex abuur bot-yadaada soo dejinta si fudud.", "choose_lang": "🌐 Dooro luuqadaada:", "create_btn": "➕ Create New Bot", "my_bots_btn": "🤖 Bot-yadayda", "help_btn": "ℹ️ Caawinaad", "lang_btn": "🌐 Luuqada"},
    "ar": {"name": "العربية 🇸🇦", "welcome": "👋 مرحبًا بك في منصة إنشاء البوتات! قم بإنشاء وإدارة بوتات التحميل الخاصة بك بسهولة.", "choose_lang": "🌐 اختر لغتك:", "create_btn": "➕ Create New Bot", "my_bots_btn": "🤖 بوتاتي", "help_btn": "ℹ️ المساعدة", "lang_btn": "🌐 اللغة"},
    "es": {"name": "Español 🇪🇸", "welcome": "👋 ¡Bienvenido a la plataforma de creación de bots! Crea y gestiona tus propios bots de descarga.", "choose_lang": "🌐 Elige tu idioma:", "create_btn": "➕ Create New Bot", "my_bots_btn": "🤖 Mis Bots", "help_btn": "ℹ️ Ayuda", "lang_btn": "🌐 Idioma"},
    "fr": {"name": "Français 🇫🇷", "welcome": "👋 Bienvenue sur la plateforme de création de bots ! Créez et gérez vos propres bots de téléchargement.", "choose_lang": "🌐 Choisissez votre langue :", "create_btn": "➕ Create New Bot", "my_bots_btn": "🤖 Mes Bots", "help_btn": "ℹ️ Aide", "lang_btn": "🌐 Langue"},
    "tr": {"name": "Türkçe 🇹🇷", "welcome": "👋 Bot Oluşturma Platformuna Hoş Geldiniz! Kendi indirme botlarınızı kolayca oluşturun.", "choose_lang": "🌐 Dilinizi seçin:", "create_btn": "➕ Create New Bot", "my_bots_btn": "🤖 Botlarım", "help_btn": "ℹ️ Yardım", "lang_btn": "🌐 Dil"},
    "de": {"name": "Deutsch 🇩🇪", "welcome": "👋 Willkommen auf der Bot-Erstellungsplattform! Erstellen und verwalten Sie Ihre eigenen Downloader-Bots.", "choose_lang": "🌐 Wählen Sie Ihre Sprache:", "create_btn": "➕ Create New Bot", "my_bots_btn": "🤖 Meine Bots", "help_btn": "ℹ️ Hilfe", "lang_btn": "🌐 Sprache"},
    "ru": {"name": "Русский 🇷🇺", "welcome": "👋 Добро пожаловать на платформу создания ботов! Создавайте и управляйте своими ботами.", "choose_lang": "🌐 Выберите ваш язык:", "create_btn": "➕ Create New Bot", "my_bots_btn": "🤖 Мои боты", "help_btn": "ℹ️ Помощь", "lang_btn": "🌐 Язык"},
    "hi": {"name": "हिन्दी 🇮🇳", "welcome": "👋 बॉट बिल्डर प्लेटफॉर्म पर आपका स्वागत है! अपने डाउनलोडर बॉट बनाएं और प्रबंधित करें।", "choose_lang": "🌐 अपनी भाषा चुनें:", "create_btn": "➕ Create New Bot", "my_bots_btn": "🤖 मेरे बॉट्स", "help_btn": "ℹ️ मदद", "lang_btn": "🌐 भाषा"},
    "pt": {"name": "Português 🇵🇹", "welcome": "👋 Bem-vindo à Plataforma Bot Builder! Crie e gerencie seus próprios bots de download.", "choose_lang": "🌐 Escolha seu idioma:", "create_btn": "➕ Create New Bot", "my_bots_btn": "🤖 Meus Bots", "help_btn": "ℹ️ Ajuda", "lang_btn": "🌐 Idioma"}
}

class MainBotPlatform:
    def __init__(self):
        self.app = Application.builder().token(Config.BOT_TOKEN).build()
        self._setup_handlers()

    def main_keyboard(self, lang: str = "en"):
        texts = MAIN_LANGUAGES.get(lang, MAIN_LANGUAGES["en"])
        return {
            "keyboard": [
                [
                    {
                        "text": texts["create_btn"],
                        "request_managed_bot": {
                            "request_id": int(time.time()),
                            "suggested_name": "Media Downloader Bot",
                            "suggested_username": "MyMediaDownloaderBot"
                        }
                    }
                ],
                [
                    {"text": texts["my_bots_btn"]},
                    {"text": texts["lang_btn"]},
                    {"text": texts["help_btn"]}
                ]
            ],
            "resize_keyboard": True,
            "is_persistent": True
        }

    def language_inline_keyboard(self):
        buttons = []
        keys = list(MAIN_LANGUAGES.keys())
        for i in range(0, len(keys), 2):
            row = [InlineKeyboardButton(MAIN_LANGUAGES[keys[i]]["name"], callback_data=f"mainlang_{keys[i]}")]
            if i + 1 < len(keys):
                row.append(InlineKeyboardButton(MAIN_LANGUAGES[keys[i+1]]["name"], callback_data=f"mainlang_{keys[i+1]}"))
            buttons.append(row)
        return InlineKeyboardMarkup(buttons)

    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("admin", self.main_admin_panel))
        self.app.add_handler(MessageHandler(filters.StatusUpdate.MANAGED_BOT_CREATED, self.handle_managed_bot_created))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_messages))
        self.app.add_handler(CallbackQueryHandler(self.handle_callbacks))
        
        # Anti-Crash Exception Handler
        self.app.add_error_handler(self.error_handler)

    async def check_global_force_join(self, user_id: int) -> tuple[bool, list[str]]:
        settings = await db.get_platform_settings()
        channels = settings.get("force_join_channels", []) if settings else []
        unjoined = []

        for ch in channels:
            try:
                member = await self.app.bot.get_chat_member(chat_id=ch, user_id=user_id)
                if member.status in ["left", "kicked"]:
                    unjoined.append(ch)
            except Exception:
                unjoined.append(ch)

        return len(unjoined) == 0, unjoined

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user = update.effective_user
            db_user = await db.get_or_create_user(user.id, user.username, user.full_name)

            if db_user.get("is_banned"):
                await update.message.reply_text("⛔️ **Akaunkaaga waa la mamnuucay (Banned).**")
                return

            # Check Global Force Join
            joined, unjoined_channels = await self.check_global_force_join(user.id)
            if not joined:
                buttons = [[InlineKeyboardButton(f"📢 Join {ch}", url=f"https://t.me/{ch.replace('@','')}")] for ch in unjoined_channels]
                buttons.append([InlineKeyboardButton("🔄 Check Join Status", callback_data="check_main_fj")])
                await update.message.reply_text(
                    "⚠️ **Soo biiridda kanaaladan waa lagama maarmaan ka hor inta aadan isticmaalin platform-ka:**",
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
                return

            # Language Selection for First Timers
            if not db_user.get("language"):
                await update.message.reply_text(
                    "🌐 **Select your Language / Dooro Luuqadaada:**",
                    reply_markup=self.language_inline_keyboard()
                )
            else:
                lang = db_user.get("language", "en")
                texts = MAIN_LANGUAGES.get(lang, MAIN_LANGUAGES["en"])
                await update.message.reply_text(
                    texts["welcome"],
                    reply_markup=self.main_keyboard(lang)
                )
        except Exception as e:
            logger.error(f"Main start error: {e}")

    async def get_managed_bot_token(self, bot_id: int) -> str | None:
        url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/getManagedBotToken"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"user_id": bot_id}) as resp:
                result = await resp.json()
                if result.get("ok"):
                    return result.get("result")
        return None

    async def handle_managed_bot_created(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            message = update.message
            owner_id = message.from_user.id
            managed_data = message.managed_bot_created
            if not managed_data:
                return

            bot_info = managed_data.bot
            bot_id, username, first_name = bot_info.id, bot_info.username or "", bot_info.first_name or "Managed Bot"

            status_msg = await message.reply_text("⏳ **Bot waa la dhisay! Waxaan helayaa Token-ka...**", parse_mode="Markdown")
            token = await self.get_managed_bot_token(bot_id)

            if not token:
                await status_msg.edit_text("❌ Token lama heli karin. Hubi Bot Management permissions.")
                return

            await db.save_managed_bot(bot_id, owner_id, username, first_name, token)
            started = await bot_manager.start_bot_instance(bot_id, token)

            if started:
                keyboard = [
                    [InlineKeyboardButton("🚀 Open Bot", url=f"https://t.me/{username}")],
                    [InlineKeyboardButton("⚙️ Bot Admin Panel", url=f"https://t.me/{username}?start=admin")]
                ]
                await status_msg.edit_text(
                    f"✅ **BOT-KAAGA WAA LA ABUURAY OON SAAXAN!**\n\n"
                    f"🤖 Name: **{first_name}**\n"
                    f"🔗 Username: **@{username}**\n"
                    f"🟢 Status: **Active & Online**",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(f"Bot creation error: {e}")

    async def handle_text_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            text = update.message.text
            user_id = update.effective_user.id
            db_user = await db.get_or_create_user(user_id)
            lang = db_user.get("language", "en")
            texts = MAIN_LANGUAGES.get(lang, MAIN_LANGUAGES["en"])

            if text in [texts["my_bots_btn"], "🤖 My Bots", "🤖 Bot-yadayda"]:
                my_bots = await db.get_user_bots(user_id)
                if not my_bots:
                    await update.message.reply_text("🤖 **My Bots**\n\nWeli ma lihid managed bot.")
                    return
                lines = ["🤖 **YOUR MANAGED BOTS**\n"]
                for i, b in enumerate(my_bots, 1):
                    lines.append(f"{i}. **{b['name']}** (@{b['username']}) - Status: `{b['status']}`")
                await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

            elif text in [texts["lang_btn"], "🌐 Language", "🌐 Luuqada"]:
                await update.message.reply_text(texts["choose_lang"], reply_markup=self.language_inline_keyboard())

            elif text in [texts["help_btn"], "ℹ️ Help", "ℹ️ Caawinaad"]:
                await update.message.reply_text(texts["welcome"])

        except Exception as e:
            logger.error(f"Main bot text handle error: {e}")

    # ==================== MAIN ADMIN PANEL (1M+ USER READY) ====================
    async def main_admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user_id = update.effective_user.id
            if user_id not in Config.ADMIN_IDS:
                return

            stats = await db.get_global_platform_stats()
            cpu, ram = psutil.cpu_percent(), psutil.virtual_memory().percent

            text = (
                f"👑 **MAIN PLATFORM ADMIN PANEL**\n\n"
                f"👥 Main Users: `{stats['total_main_users']}`\n"
                f"🤖 Total Bots: `{stats['total_created_bots']}` (Active: `{stats['active_bots']}`)\n"
                f"📥 Platform Downloads: `{stats['total_downloads']}`\n"
                f"👥 Total Bot End-Users: `{stats['total_bot_users']}`\n\n"
                f"💻 CPU: `{cpu}%` | 🧠 RAM: `{ram}%`"
            )

            keyboard = [
                [InlineKeyboardButton("📊 Stats & Metrics", callback_data="madmin_stats"), InlineKeyboardButton("📢 Global Broadcast", callback_data="madmin_bc")],
                [InlineKeyboardButton("🔗 Force Join Settings", callback_data="madmin_fj"), InlineKeyboardButton("🚫 User Management", callback_data="madmin_users")],
                [InlineKeyboardButton("🤖 Bot Fleet Control", callback_data="madmin_bots"), InlineKeyboardButton("🔄 Refresh Panel", callback_data="madmin_refresh")]
            ]

            if update.callback_query:
                await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            else:
                await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Main Admin Panel error: {e}")

    async def handle_callbacks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            query = update.callback_query
            await query.answer()

            if query.data.startswith("mainlang_"):
                lang_code = query.data.split("_")[1]
                await db.set_main_user_language(query.from_user.id, lang_code)
                texts = MAIN_LANGUAGES.get(lang_code, MAIN_LANGUAGES["en"])
                await query.message.reply_text(
                    f"✅ Language set to {MAIN_LANGUAGES[lang_code]['name']}",
                    reply_markup=self.main_keyboard(lang_code)
                )

            elif query.data == "check_main_fj":
                joined, _ = await self.check_global_force_join(query.from_user.id)
                if joined:
                    await query.message.edit_text("✅ Waad ku biirtay dhammaan kanaalada!")
                else:
                    await query.answer("❌ Wali ma aadan ku biirin kanaalada oo dhan!", show_alert=True)

            # Main Admin Callbacks
            elif query.data == "madmin_refresh" or query.data == "madmin_stats":
                await self.main_admin_panel(update, context)

            elif query.data == "madmin_bc":
                context.user_data["admin_state"] = "awaiting_broadcast_msg"
                await query.message.edit_text(
                    "📢 **GLOBAL BROADCAST SYSTEM (1M+ Users Supported)**\n\n"
                    "Fadlan u soo dir qoraalka ama fariinta aad rabto inaad u panto dhammaan isticmaalayaasha platform-ka.\n\n"
                    "👉 *Kansal garayn:* Dir `/cancel`",
                    parse_mode="Markdown"
                )

            elif query.data == "madmin_fj":
                settings = await db.get_platform_settings()
                channels = settings.get("force_join_channels", [])
                text = f"🔗 **FORCE JOIN CHANNELS**\n\nChannels: `{channels}`\n\nSi aad ugu darto ama kaga saarto u isticmaal:\n`/addchannel @channel` ama `/removechannel @channel`"
                await query.message.edit_text(text, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Main callback error: {e}")

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Global Main Bot Exception: {context.error}")

    async def run(self):
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)

main_bot = MainBotPlatform()
