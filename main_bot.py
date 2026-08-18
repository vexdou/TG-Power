import psutil
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ConversationHandler, filters, ContextTypes
)
from config import Config
from database import db
from bot_creator import bot_creator
from bot_manager import bot_manager

# States for Bot Creation Conversation
NAME, USERNAME = range(2)

class MainBotPlatform:
    def __init__(self):
        self.app = Application.builder().token(Config.BOT_TOKEN).build()
        self._setup_handlers()

    def _setup_handlers(self):
        # Conversation handler for bot creation
        conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.start_bot_creation, pattern="^create_bot$")],
            states={
                NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_bot_name)],
                USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_bot_username)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel_creation)],
        )

        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("admin", self.main_admin_panel))
        self.app.add_handler(conv_handler)
        self.app.add_handler(CallbackQueryHandler(self.handle_callbacks))

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        await db.get_or_create_user(user.id, user.username, user.full_name)

        keyboard = [
            [InlineKeyboardButton("🤖 Create New Bot", callback_data="create_bot"), InlineKeyboardButton("🤖 My Bots", callback_data="my_bots")],
            [InlineKeyboardButton("📊 My Statistics", callback_data="my_stats"), InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
            [InlineKeyboardButton("📚 Help", callback_data="help"), InlineKeyboardButton("👨‍💻 Support", callback_data="support")]
        ]
        
        if user.id in Config.ADMIN_IDS:
            keyboard.append([InlineKeyboardButton("👑 MAIN ADMIN PANEL", callback_data="main_admin")])

        await update.message.reply_text(
            f"👋 Soo dhawoow {user.first_name}!\n\n"
            f"Kani waa **Telegram Managed Bot Creation Platform**. Waxaad si toos ah oo otomaatig ah uga dhex sameaysan kartaa Telegram Bot kuu gaar ah oo soo dejiya muqaallada baraha bulshada.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    async def start_bot_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        user_bots = await db.get_user_bots(query.from_user.id)
        if len(user_bots) >= Config.MAX_BOTS_PER_USER and query.from_user.id not in Config.ADMIN_IDS:
            await query.message.edit_text(f"❌ Waxaad gaartay xadka bot-yada kuu allowed-ka ah ({Config.MAX_BOTS_PER_USER}).")
            return ConversationHandler.END

        await query.message.edit_text("🤖 **Bilaawga Bot Cusub**\n\nFadlan ii soo dir **Magaca** aad u rabto Bot-kaaga (musaal: Downloader Pro):")
        return NAME

    async def get_bot_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["new_bot_name"] = update.message.text.strip()
        await update.message.reply_text("✅ Magacu waa sax!\n\nHadda soo dir **Username-ka** bot-ka (waa in uu ku dhamaadaa 'bot', musaal: MyDownloaderBot):")
        return USERNAME

    async def get_bot_username(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        username = update.message.text.strip().replace("@", "")
        context.user_data["new_bot_username"] = username
        
        status_msg = await update.message.reply_text("⏳ U diyaarinaya BotFather... Fadlan sug wax yar...")

        # Ka abuur BotFather
        result = await bot_creator.create_new_bot(context.user_data["new_bot_name"], username)

        if not result["success"]:
            await status_msg.edit_text(f"❌ Abuuristu waa ay fashilantay:\n`{result['error']}`", parse_mode="Markdown")
            return ConversationHandler.END

        # Kaydi Mongo
        bot_id = result["bot_id"]
        token = result["token"]
        await db.add_bot(bot_id, update.effective_user.id, result["name"], result["username"], token)

        # Bilaw Bot-ka
        started = await bot_manager.start_bot_instance(bot_id, token)

        if started:
            keyboard = [
                [InlineKeyboardButton("🚀 Open Bot", url=f"https://t.me/{result['username']}")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
            ]
            await status_msg.edit_text(
                f"✅ **Bot Created Successfully!**\n\n"
                f"🤖 **Name:** {result['name']}\n"
                f"🔗 **Username:** @{result['username']}\n"
                f"⚙️ Status: Running",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            await status_msg.edit_text("⚠️ Bot-ka waa la abuuray laakiin waa lagu fashilmay in laga dhex bilaabo Bot Manager.")

        return ConversationHandler.END

    async def cancel_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🚫 Abuuristii bot-ka waa la kansalay.")
        return ConversationHandler.END

    async def main_admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in Config.ADMIN_IDS:
            return

        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        all_bots = await db.get_all_active_bots()

        text = (
            f"👑 **MAIN ADMIN PANEL**\n\n"
            f"🤖 Active Managed Bots: {len(all_bots)}\n"
            f"💻 CPU Usage: {cpu}%\n"
            f"🧠 RAM Usage: {ram}%\n"
            f"⚙️ Dynamic Bot Engine: Running"
        )

        keyboard = [
            [InlineKeyboardButton("🤖 All Managed Bots", callback_data="admin_all_bots")],
            [InlineKeyboardButton("📢 Broadcast All Bots", callback_data="admin_bc_all")],
            [InlineKeyboardButton("🔧 System Health", callback_data="admin_health")]
        ]

        if update.message:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    async def handle_callbacks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if query.data == "my_bots":
            user_bots = await db.get_user_bots(query.from_user.id)
            if not user_bots:
                await query.message.edit_text("❌ Wali ma aadan abuurin wax Bot ah.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🤖 Create Bot", callback_data="create_bot")]]))
                return

            text = "🤖 **Bot-yadaada:**\n\n"
            keyboard = []
            for b in user_bots:
                text += f"• @{b['username']} ({b['status']})\n"
                keyboard.append([InlineKeyboardButton(f"⚙️ Manage @{b['username']}", url=f"https://t.me/{b['username']}?start=admin")])

            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

        elif query.data == "main_admin":
            await self.main_admin_panel(update, context)

    async def run(self):
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)

main_bot = MainBotPlatform()
