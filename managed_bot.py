import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import config
from database import add_bot_user, log_download, get_bot_by_username, bot_users_col, bots_col
from downloader import download_media, cleanup_file

def build_managed_bot_handlers(app: Client, bot_username: str, owner_id: int):

    @app.on_message(filters.command("start") & filters.private)
    async def start_cmd(c: Client, m: Message):
        await add_bot_user(bot_username, m.from_user.id, m.from_user.first_name)
        
        # Check Force Join Channels
        bot_info = await get_bot_by_username(bot_username)
        channels = bot_info.get("force_join_channels", [])
        
        buttons = []
        for ch in channels:
            buttons.append([InlineKeyboardButton(f"📢 Join {ch}", url=f"https://t.me/{ch.replace('@','')}")])
        
        if buttons:
            buttons.append([InlineKeyboardButton("✅ Check Membership", callback_data="check_join")])
            await m.reply_text("⚠️ **Fadlan ugu horeyn ku qoormo boosaska si aad bot-ka u isticmaasho:**", reply_markup=InlineKeyboardMarkup(buttons))
            return

        await m.reply_text(
            f"👋 **Kusoo dhawoow @{bot_username}!**\n\n"
            f"Soo dir Link-ga TikTok, YouTube, Instagram, Facebook, ama Twitter si aad u soo dejisato."
        )

    # Owner Admin Panel command inside their own bot
    @app.on_message(filters.command("admin") & filters.private & filters.user(owner_id))
    async def owner_admin_panel(c: Client, m: Message):
        bot_data = await get_bot_by_username(bot_username)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Statistics", callback_data="owner_stats"), InlineKeyboardButton("📢 Broadcast", callback_data="owner_broadcast")],
            [InlineKeyboardButton("📢 Force Join", callback_data="owner_forcejoin")]
        ])
        await m.reply_text(
            f"⚙️ **Bot Admin Panel (@{bot_username})**\n\n"
            f"👥 Total Users: {bot_data.get('total_users', 0)}\n"
            f"📥 Total Downloads: {bot_data.get('total_downloads', 0)}",
            reply_markup=keyboard
        )

    @app.on_callback_query()
    async def cb_handler(c: Client, q: CallbackQuery):
        data = q.data
        if data == "owner_stats" and q.from_user.id == owner_id:
            bot_data = await get_bot_by_username(bot_username)
            await q.answer(f"Users: {bot_data.get('total_users', 0)} | Downloads: {bot_data.get('total_downloads', 0)}", show_alert=True)
        elif data == "check_join":
            await q.message.delete()
            await q.message.reply_text("✅ Waxaad ka tirsantahay boosaska! Soo dir link-gaaga kowaad.")

    @app.on_message(filters.text & filters.private & ~filters.command(["start", "admin"]))
    async def handle_download_request(c: Client, m: Message):
        await add_bot_user(bot_username, m.from_user.id, m.from_user.first_name)
        url = m.text.strip()
        
        if not (url.startswith("http://") or url.startswith("https://")):
            await m.reply_text("👋 Soo dir Link saxa ah oo fiidiyow ah.")
            return

        msg = await m.reply_text("⏳ *Muuqaalkaagii waa lagu jiraa, fadlan yara sug...*")
        try:
            filepath, title, extractor = await download_media(url)
            await msg.edit_text("⬆️ *Uploading to Telegram...*")
            
            await m.reply_video(video=filepath, caption=f"🎬 **{title}**\n\n🤖 Powered by @{bot_username}")
            await msg.delete()
            
            cleanup_file(filepath)
            await log_download(bot_username, m.from_user.id, extractor)
        except Exception as e:
            await msg.edit_text(f"❌ *Cillad ayaa dhacday:* {str(e)}")
