import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
)
from config import Config
from database import db
from bot_manager import bot_manager

logger = logging.getLogger(__name__)

class MainSaaSBot:
    def __init__(self):
        self.app = Application.builder().token(Config.BOT_TOKEN).build()
        self._setup_handlers()

    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("mybots", self.my_bots_command))
        self.app.add_handler(CommandHandler("admin", self.admin_command))
        self.app.add_handler(CallbackQueryHandler(self.handle_callbacks))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_token_input))
        self.app.add_error_handler(self.error_handler)

    async def start_bot(self):
        await self.app.initialize()
        await self.app.bot.delete_webhook(drop_pending_updates=True)
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)
        bot_me = await self.app.bot.get_me()
        logger.info(f"👑 Main SaaS Bot Started: @{bot_me.username}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("➕ Create Downloader Bot", callback_data="create_bot")],
            [InlineKeyboardButton("🤖 My Bots", callback_data="my_bots"), InlineKeyboardButton("📊 System Stats", callback_data="system_stats")]
        ]
        text = (
            "👋 **Soo dhawoow TG-Power Platform!**\n\n"
            "Muuqaal-soo-dejiye (Downloader Bot) kuu gaar ah halkan ka samayso.\n\n"
            "👉 Taabo **➕ Create Downloader Bot** si aad u bilaawdo."
        )
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    async def my_bots_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        cursor = db.bots.find({"owner_id": user_id})
        user_bots = await cursor.to_list(length=None)

        if not user_bots:
            await update.message.reply_text("❌ Wax bot ah oo aad samaysatay mawaad laha. Taabo /start si aad u abuurto.")
            return

        msg = "🤖 **BOT-YADAADA:**\n\n"
        for b in user_bots:
            msg += f"• **Bot ID:** `{b['bot_id']}` | Status: `{b['status']}`\n"
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def handle_token_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        user_id = update.effective_user.id

        # Hubi in qoraalku yahay Telegram Bot Token format (e.g. 123456789:ABCdefgh...)
        token_pattern = r"^\d+:[A-Za-z0-9_-]+$"
        if not re.match(token_pattern, text):
            await update.message.reply_text("❌ Token khaldan! Fadlan soo dir Bot Token sax ah oo ka soo muuqda BotFather.")
            return

        status_msg = await update.message.reply_text("⏳ **Hubinta Token-ka iyo kicinida bot-ka...**", parse_mode="Markdown")

        try:
            # Test Bot Token validity
            temp_bot = Bot(token=text)
            bot_me = await temp_bot.get_me()
            bot_id = bot_me.id
            username = bot_me.username

            # Save Bot to Database
            await db.add_new_bot(owner_id=user_id, token=text, bot_id=bot_id, username=username)

            # Instantly launch sub-bot
            started = await bot_manager.start_bot_instance(bot_id, text)

            if started:
                await status_msg.edit_text(
                    f"✅ **WAA LAGU GUULEYSTAY!**\n\n"
                    f"🤖 **Bot Name:** @{username}\n"
                    f"🆔 **Bot ID:** `{bot_id}`\n\n"
                    f"Bot-kaagii si toos ah ayuu u bilaawday oo waa shaqaynayaa!",
                    parse_mode="Markdown"
                )
            else:
                await status_msg.edit_text("❌ Bot-ka waa la kaydiyay lkn waa kici waayay. Hubi token-ka ama server log-ga.")

        except Exception as e:
            logger.error(f"Token setup error: {e}")
            await status_msg.edit_text(f"❌ **Cilad ayaa dhacday:** Token-ku ma sii shaqaynayo ama waa la tirtiray BotFather.")

    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id != Config.OWNER_ID:
            return

        total_bots = await db.bots.count_documents({})
        active_bots = await db.bots.count_documents({"status": "active"})
        total_users = await db.users.count_documents({})
        total_downloads = await db.downloads.count_documents({})

        await update.message.reply_text(
            f"👑 **SAAS ADMIN DASHBOARD**\n\n"
            f"🤖 Total Bots Created: `{total_bots}`\n"
            f"🟢 Active Bots: `{active_bots}`\n"
            f"👥 Total End Users: `{total_users}`\n"
            f"📥 Total Downloads: `{total_downloads}`",
            parse_mode="Markdown"
        )

    async def handle_callbacks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if query.data == "create_bot":
            await query.message.edit_text(
                "📝 **SIDA BOT CUSUB LOO ABUURO:**\n\n"
                "1. U tag @BotFather oo ka samey bot cusub (`/newbot`).\n"
                "2. Ka soo guuri **API Token**-ka uu ku siiyo.\n"
                "3. Token-kaas halkan iisoo dir (paste gareey).\n\n"
                "⏳ Iisoo dir Token-ka oo kaliya...",
                parse_mode="Markdown"
            )
        elif query.data == "my_bots":
            await self.my_bots_command(update, context)
        elif query.data == "system_stats":
            total_bots = await db.bots.count_documents({"status": "active"})
            await query.message.edit_text(f"📊 Total Active Bots in Platform: `{total_bots}`", parse_mode="Markdown")

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Main Bot Error: {context.error}")

main_bot = MainSaaSBot()
