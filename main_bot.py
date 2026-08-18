import logging
import time
import json
import httpx
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes
)
from config import Config
from database import db
from bot_manager import bot_manager

logger = logging.getLogger(__name__)

def main_keyboard():
    # Telegram Native Request Managed Bot Button Keyboard
    return {
        "keyboard": [
            [
                {
                    "text": "➕ Create New Bot",
                    "request_managed_bot": {
                        "request_id": int(time.time()),
                        "suggested_name": "My Downloader Bot",
                        "suggested_username": "MyDownloaderBot"
                    }
                }
            ],
            [
                {"text": "🤖 My Bots"},
                {"text": "ℹ️ Help"}
            ]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }

class MainSaaSBot:
    def __init__(self):
        self.app = Application.builder().token(Config.BOT_TOKEN).build()
        self._setup_handlers()

    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(MessageHandler(filters.StatusUpdate.MANAGED_BOT_CREATED, self.handle_managed_bot_created))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_messages))
        self.app.add_error_handler(self.error_handler)

    async def start_bot(self):
        await self.app.initialize()
        await self.app.bot.delete_webhook(drop_pending_updates=True)
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)
        bot_me = await self.app.bot.get_me()
        logger.info(f"👑 Main Managed SaaS Bot Online: @{bot_me.username}")

    async def get_managed_bot_token(self, bot_id: int) -> str:
        """Kuxirida Telegram API si loogu soo saaro Managed Bot Token"""
        url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/getManagedBotToken"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json={"user_id": bot_id}, timeout=10.0)
                res = response.json()
                if res.get("ok"):
                    return res["result"]
            except Exception as e:
                logger.error(f"Error fetching managed bot token: {e}")
        return None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        text = (
            f"🤖 **BOT BUILDER PLATFORM**\n\n"
            f"Soo dhawoow **{user.first_name}** 👋\n\n"
            f"Waxaad halkan ka abuuri kartaa downloader bot kuuu gaar ah oo toos u shaqeeya iyadoon loo baahnayn Token.\n\n"
            f"Taabo **➕ Create New Bot** si aad Telegram gudaheeda uga abuurto."
        )
        # Custom dict JSON keyboard sending
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=json.dumps(main_keyboard()),
            parse_mode="Markdown"
        )

    async def handle_managed_bot_created(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message = update.message
        managed = message.managed_bot_created
        if not managed or not managed.bot:
            return

        bot_info = managed.bot
        bot_id = bot_info.id
        username = bot_info.username or ""
        first_name = bot_info.first_name or "Managed Bot"
        owner_id = update.effective_user.id

        status_msg = await update.message.reply_text("⏳ **Bot-ka waa la sameeyay! Waxaan helayaa Token-ka oo kicinayaa...**", parse_mode="Markdown")

        # 1. Soo saar Token-ka otomaatiga ah ee Telegram Managed Bot API
        token = await self.get_managed_bot_token(bot_id)

        if not token:
            await status_msg.edit_text("❌ **Cilad:** Token-ka bot-ka ma soo bixin. Hubi in Manager Bot-kaagu leeyahay Bot Management Mode.")
            return

        # 2. Ku kaydi Database-ka
        await db.add_new_bot(owner_id=owner_id, token=token, bot_id=bot_id, username=username)

        # 3. Kici Bot-ka yar (Managed Bot Instance)
        started = await bot_manager.start_bot_instance(bot_id, token)

        if started:
            await status_msg.edit_text(
                f"✅ **BOT-KAA TIKTO/YT/IG DOWNLOADER WAA LA KICIYAY!**\n\n"
                f"🤖 Name: **{first_name}**\n"
                f"🔗 Username: **@{username}**\n"
                f"🟢 Status: **Active & Online**\n\n"
                f"👉 Taabo halkan si aad u gasho: https://t.me/{username}",
                parse_mode="Markdown"
            )
        else:
            await status_msg.edit_text("❌ Bot-ka waa la abuuray lkn waa kici waayay. Fadlan eeg system logs.")

    async def handle_text_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        user_id = update.effective_user.id

        if text == "🤖 My Bots":
            cursor = db.bots.find({"owner_id": user_id})
            user_bots = await cursor.to_list(length=None)

            if not user_bots:
                await update.message.reply_text("❌ Weli ma lihid managed bot. Taabo **➕ Create New Bot**.")
                return

            msg = "🤖 **BOT-YADAADA ACTIVE-KA AH:**\n\n"
            for b in user_bots:
                msg += f"• **Name:** @{b.get('username', 'N/A')}\n  `ID: {b['bot_id']}` | Status: `{b['status']}`\n\n"
            await update.message.reply_text(msg, parse_mode="Markdown")

        elif text == "ℹ️ Help":
            await update.message.reply_text(
                "ℹ️ **BOT BUILDER HELP**\n\n"
                "Taabo **➕ Create New Bot** si Telegram toos kuugu muujiyo bogga abuurista bot-ka iyadoon BotFather lagu wareegayn.",
                parse_mode="Markdown"
            )

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Main Bot Error: {context.error}")

main_bot = MainSaaSBot()
