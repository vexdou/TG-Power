import time
import aiohttp
import psutil
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
)
from config import Config
from database import db
from bot_manager import bot_manager

class MainBotPlatform:
    def __init__(self):
        self.app = Application.builder().token(Config.BOT_TOKEN).build()
        self._setup_handlers()

    def main_keyboard(self):
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

    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("admin", self.main_admin_panel))
        self.app.add_handler(MessageHandler(filters.StatusUpdate.MANAGED_BOT_CREATED, self.handle_managed_bot_created))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_messages))
        self.app.add_handler(CallbackQueryHandler(self.handle_callbacks))

    async def get_managed_bot_token(self, bot_id: int) -> str | None:
        """Calls Telegram API getManagedBotToken to retrieve token for created bot"""
        url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/getManagedBotToken"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"user_id": bot_id}) as resp:
                result = await resp.json()
                if result.get("ok"):
                    return result.get("result")
        return None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        await db.get_or_create_user(user.id, user.username, user.full_name)

        text = (
            f"🤖 **BOT BUILDER PLATFORM**\n\n"
            f"Soolaalama **{user.first_name}** 👋\n\n"
            f"Waxaad halkan ka abuuri kartaa oo maamuli kartaa managed bot-yadaada.\n\n"
            f"Taabo **➕ Create New Bot** si aad Telegram guud ahaan ugu abuurto bot cusub."
        )

        await update.message.reply_text(
            text,
            reply_markup=self.main_keyboard(),
            parse_mode="Markdown"
        )

    async def handle_managed_bot_created(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message = update.message
        chat_id = message.chat_id
        owner_id = message.from_user.id

        managed_data = message.managed_bot_created
        if not managed_data:
            return

        bot_info = managed_data.bot
        bot_id = bot_info.id
        username = bot_info.username or ""
        first_name = bot_info.first_name or "Managed Bot"

        status_msg = await message.reply_text("⏳ **Bot waa la sameeyay! Waxaan helayaa Token-ka...**", parse_mode="Markdown")

        # Get Managed Bot Token directly via Telegram API
        token = await self.get_managed_bot_token(bot_id)

        if not token:
            await status_msg.edit_text(
                "❌ **Token lama heli karin.**\n\nHubi in Manager Bot-kaagu uu leeyahay Bot Management permissions."
            )
            return

        # Save Bot in Mongo DB
        await db.save_managed_bot(
            bot_id=bot_id,
            owner_id=owner_id,
            username=username,
            name=first_name,
            token=token
        )

        # Start Instance dynamically
        started = await bot_manager.start_bot_instance(bot_id, token)

        if started:
            keyboard = [
                [InlineKeyboardButton("🚀 Open Bot", url=f"https://t.me/{username}")],
                [InlineKeyboardButton("⚙️ Bot Admin Panel", url=f"https://t.me/{username}?start=admin")]
            ]
            await status_msg.edit_text(
                f"✅ **BOT CREATED SUCCESSFULLY!**\n\n"
                f"🤖 Name: **{first_name}**\n"
                f"🔗 Username: **@{username}**\n"
                f"🟢 Status: **Active & Running**\n\n"
                f"Bot-kaaga hadda waa shaqeynayaa oo waa Downloader Bot buuxa!",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

    async def handle_text_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        user_id = update.effective_user.id

        if text == "🤖 My Bots":
            my_bots = await db.get_user_bots(user_id)
            if not my_bots:
                await update.message.reply_text("🤖 **My Bots**\n\nWeli ma lihid managed bot.\nTaabo ➕ Create New Bot.")
                return

            lines = ["🤖 **MY MANAGED BOTS**\n"]
            for i, b in enumerate(my_bots, 1):
                lines.append(f"{i}. **{b['name']}**\n   @{b['username']}\n   Status: {b['status']}\n")

            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

        elif text == "ℹ️ Help":
            help_text = (
                "ℹ️ **BOT BUILDER HELP**\n\n"
                "➕ **Create New Bot**\n"
                "Waxay kuu furaysaa Telegram's official managed bot creation flow.\n\n"
                "🤖 **My Bots**\n"
                "Waxaad ka arki kartaa bot-yada aad abuurtay meeshan."
            )
            await update.message.reply_text(help_text, parse_mode="Markdown")

    async def main_admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in Config.ADMIN_IDS:
            return

        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        all_bots = await db.get_all_active_bots()

        text = (
            f"👑 **MAIN ADMIN PANEL**\n\n"
            f"🤖 Active Bots: {len(all_bots)}\n"
            f"💻 CPU Usage: {cpu}%\n"
            f"🧠 RAM Usage: {ram}%"
        )
        await update.message.reply_text(text, parse_mode="Markdown")

    async def handle_callbacks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

    async def run(self):
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)

main_bot = MainBotPlatform()
