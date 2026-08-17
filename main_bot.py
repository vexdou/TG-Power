import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import config
from database import (
    add_user, register_bot, get_user_bots, is_bot_creation_enabled,
    toggle_bot_creation, bots_col, users_col
)
from bot_creator import create_bot_via_botfather
from bot_manager import start_managed_bot

main_app = Client("main_saas_bot", api_id=config.API_ID, api_hash=config.API_HASH, bot_token=config.BOT_TOKEN)

user_states = {}

@main_app.on_message(filters.command("start") & filters.private)
async def start_handler(c: Client, m: Message):
    await add_user(m.from_user.id, m.from_user.first_name, m.from_user.username)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 Create New Bot", callback_data="create_bot_start")],
        [InlineKeyboardButton("📦 My Bots", callback_data="my_bots"), InlineKeyboardButton("📊 Statistics", callback_data="my_stats")],
        [InlineKeyboardButton("📚 Help", callback_data="help")]
    ])
    
    if m.from_user.id in config.ADMIN_IDS:
        keyboard.inline_keyboard.append([InlineKeyboardButton("👑 Main Admin Panel", callback_data="main_admin")])

    await m.reply_text(
        f"👋 **Kusoo dhawoow Telegram Bot Creation Platform!**\n\n"
        f"Halkan waxaad ka samaysan kartaa bot-kaaga Downloader-ka ah oo si **otomaatig ah** noogu dhalanaya.\n\n"
        f"Taabo **Create New Bot** si aad u bilaawdo.",
        reply_markup=keyboard
    )

@main_app.on_callback_query()
async def cb_main(c: Client, q: CallbackQuery):
    user_id = q.from_user.id
    data = q.data

    if data == "create_bot_start":
        enabled = await is_bot_creation_enabled()
        if not enabled and user_id not in config.ADMIN_IDS:
            await q.answer("❌ Sameynta bot-yada cusub shaqada waa lagu hakiyay hadda.", show_alert=True)
            return
        
        user_states[user_id] = {"step": "awaiting_name"}
        await q.message.edit_text(
            "📝 **Tallaabada 1-aad:** Qor Magaca aad u baxanayso Bot-kaaga (Display Name).\n\n"
            "*(Tusaale: Downloader Pro)*"
        )

    elif data == "my_bots":
        my_bots = await get_user_bots(user_id)
        if not my_bots:
            await q.answer("Ma haysatid wax Bot ah wali.", show_alert=True)
            return
        text = "🤖 **Bot-yadaada:**\n\n"
        for b in my_bots:
            text += f"• @{b['username']} (Users: {b['total_users']})\n"
        await q.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="home")]]))

    elif data == "main_admin" and user_id in config.ADMIN_IDS:
        all_bots = await bots_col.count_documents({})
        all_users = await users_col.count_documents({})
        creation_status = await is_bot_creation_enabled()

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"Bot Creation: {'🟢 ON' if creation_status else '🔴 OFF'}", callback_data="toggle_creation")],
            [InlineKeyboardButton("🤖 All Managed Bots", callback_data="list_all_bots")],
            [InlineKeyboardButton("🔙 Back", callback_data="home")]
        ])
        await q.message.edit_text(
            f"👑 **MAIN SUPER ADMIN PANEL**\n\n"
            f"📊 Total Managed Bots: {all_bots}\n"
            f"👥 Total SaaS Users: {all_users}",
            reply_markup=kb
        )

    elif data == "toggle_creation" and user_id in config.ADMIN_IDS:
        curr = await is_bot_creation_enabled()
        await toggle_bot_creation(not curr)
        await q.answer(f"Bot creation set to {not curr}", show_alert=True)

    elif data == "home":
        await start_handler(c, q.message)

@main_app.on_message(filters.private & filters.text & ~filters.command(["start"]))
async def text_handler(c: Client, m: Message):
    user_id = m.from_user.id
    if user_id not in user_states:
        return

    state = user_states[user_id]

    if state.get("step") == "awaiting_name":
        state["bot_name"] = m.text.strip()
        state["step"] = "awaiting_username"
        await m.reply_text(
            "🔗 **Tallaabada 2-aad:** Qor Username-ka Bot-kaaga.\n\n"
            "*(Waa inuu ku dhamaadaa 'bot', tusaale: `MyMedia_Downloader_Bot`)*"
        )

    elif state.get("step") == "awaiting_username":
        bot_username = m.text.strip().replace("@", "")
        bot_name = state["bot_name"]
        
        msg = await m.reply_text("🔄 *BotFather ayaan si otomaatig ah bot-kaaga ugu samaynaynaa... Fadlan yara sug...*")
        try:
            # Automatic Creation via Backend Pyrogram Userbot
            token, final_username = await create_bot_via_botfather(bot_name, bot_username)
            
            # Save to MongoDB
            await register_bot(user_id, token, bot_name, final_username)
            
            # Start Worker Bot immediately
            await start_managed_bot(token, final_username, user_id)
            
            del user_states[user_id]
            
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Open Bot", url=f"https://t.me/{final_username}")],
                [InlineKeyboardButton("⚙️ Open Admin Panel", url=f"https://t.me/{final_username}?start=admin")]
            ])

            await msg.edit_text(
                f"✅ **BOT-KAAGII WAA LA SAMEEYAY SI OTOMAATIG AH!**\n\n"
                f"🤖 **Name:** {bot_name}\n"
                f"🔗 **Username:** @{final_username}\n\n"
                f"Sida ugu faniinta badan bot-kaagu wuu shaqaynayaa 24/7!",
                reply_markup=kb
            )
        except Exception as e:
            await msg.edit_text(f"❌ *Fashil:* {str(e)}")
            del user_states[user_id]
