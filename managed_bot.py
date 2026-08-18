import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
)
from database import db
from downloader import downloader

class ManagedBotHandler:
    def __init__(self, bot_id: int, token: str):
        self.bot_id = bot_id
        self.token = token
        self.app = Application.builder().token(token).build()
        self._setup_handlers()

    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("admin", self.admin_panel))
        self.app.add_handler(CallbackQueryHandler(self.handle_callbacks))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def check_force_join(self, user_id: int, bot_data: dict) -> bool:
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
        return True

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        bot_data = await db.get_bot(self.bot_id)
        
        await db.bot_users.update_one(
            {"bot_id": self.bot_id, "user_id": user.id},
            {"$set": {"username": user.username, "full_name": user.full_name}},
            upsert=True
        )

        if not await self.check_force_join(user.id, bot_data):
            buttons = [
                [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{ch.replace('@','')}")]
                for ch in bot_data.get("force_join_channels", [])
            ]
            buttons.append([InlineKeyboardButton("🔄 Check Membership", callback_data="check_fj")])
            await update.message.reply_text(
                "⚠️ Sooma baahan tahay in aad ku biirto kanaalada ka hor intaadana isticmaalin bot-ka:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            return

        await update.message.reply_text(
            f"👋 Soo dhawoow {user.first_name}!\n\n"
            f"Iisoo dir Link-ga video-ga ama audio-ga aad rabto in aad soo dejiso (TikTok, YouTube, FB, IG, Twitter, Snap, Pinterest)."
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        url = update.message.text.strip()
        user_id = update.effective_user.id
        bot_data = await db.get_bot(self.bot_id)

        if not await self.check_force_join(user_id, bot_data):
            await update.message.reply_text("⚠️ Fadlan marka hore ku biir kanaalada lagama maarmaanka ah.")
            return

        if not url.startswith("http://") and not url.startswith("https://"):
            await update.message.reply_text("❌ Fadlan dir link sax ah.")
            return

        status_msg = await update.message.reply_text("⏳ Soo dejintu waa ay socotaa... Fadlan sug.")
        result = await downloader.download(url, user_id)

        if not result["success"]:
            await status_msg.edit_text(f"❌ Cilad: {result['error']}")
            return

        file_path = result["file_path"]
        try:
            await status_msg.edit_text("📤 Waa la soo dejiyay, waxaa loo soo dirayaa Telegram...")
            if result["media_type"] == "video":
                with open(file_path, "rb") as video_file:
                    await update.message.reply_video(video=video_file, caption=f"✅ {result['title']}")
            else:
                with open(file_path, "rb") as audio_file:
                    await update.message.reply_audio(audio=audio_file, caption=f"✅ {result['title']}")

            await db.log_download(self.bot_id, user_id, result["platform"], result["media_type"])
            await status_msg.delete()
        except Exception as e:
            await status_msg.edit_text(f"❌ Telegram API Error: {str(e)}")
        finally:
            downloader.cleanup(file_path)

    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        bot_data = await db.get_bot(self.bot_id)

        if bot_data["owner_id"] != user_id:
            await update.message.reply_text("⛔️ Ma lihid ruqsad aad ku gasho Panel-kan.")
            return

        stats = await db.get_bot_stats(self.bot_id)
        keyboard = [
            [InlineKeyboardButton("📊 Stats", callback_data="owner_stats"), InlineKeyboardButton("📢 Broadcast", callback_data="owner_bc")],
            [InlineKeyboardButton("👥 Users", callback_data="owner_users"), InlineKeyboardButton("⚙️ Settings", callback_data="owner_settings")]
        ]
        text = (
            f"⚙️ **BOT OWNER ADMIN PANEL**\n\n"
            f"🤖 Bot: @{bot_data['username']}\n"
            f"👥 Total Users: {stats['total_users']}\n"
            f"📥 Downloads: {stats['total_downloads']}"
        )
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    async def handle_callbacks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if query.data == "check_fj":
            bot_data = await db.get_bot(self.bot_id)
            if await self.check_force_join(query.from_user.id, bot_data):
                await query.message.edit_text("✅ Waad ku biirtay! Hadda ii soo dir link-ga aad rabto.")
            else:
                await query.answer("❌ Wali ma aadan ku biirin kanaalada!", show_alert=True)
        elif query.data == "owner_stats":
            stats = await db.get_bot_stats(self.bot_id)
            await query.message.edit_text(
                f"📊 **Bot Statistics**\n\n"
                f"👥 Users: {stats['total_users']}\n"
                f"📥 Downloads: {stats['total_downloads']}\n"
                f"🎬 Videos: {stats['videos']}\n"
                f"🎵 Audio: {stats['audio']}"
            )
