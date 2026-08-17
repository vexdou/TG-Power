from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
import config
from database import (
    init_db, add_user, get_user_bots, count_user_bots, get_main_stats,
    can_create_bot, is_bot_creation_enabled, set_creation_access, toggle_bot_creation,
    get_bot_by_owner, get_bot_by_username, set_bot_status, delete_bot, log_event,
)
from bot_creator import create_bot_via_botfather
from bot_manager import start_managed_bot, stop_managed_bot

main_app = Client(
    "main_saas_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    workers=16,
)

async def ensure_user(message):
    u = message.from_user
    await add_user(u.id, u.first_name or "", u.username or "")

def main_keyboard(user_id: int):
    rows = [
        [InlineKeyboardButton("➕ Create New Bot", callback_data="main:create"),
         InlineKeyboardButton("📦 My Bots", callback_data="main:mybots")],
        [InlineKeyboardButton("📊 My Statistics", callback_data="main:mystats")],
        [InlineKeyboardButton("📚 Help", callback_data="main:help")],
    ]
    if user_id in config.ADMIN_IDS:
        rows.append([InlineKeyboardButton("👑 Main Admin Panel", callback_data="main:admin")])
    return InlineKeyboardMarkup(rows)

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Statistics", callback_data="admin:stats"),
         InlineKeyboardButton("🤖 All Bots", callback_data="admin:bots")],
        [InlineKeyboardButton("👥 Users", callback_data="admin:users"),
         InlineKeyboardButton("📢 Broadcast", callback_data="admin:broadcast")],
        [InlineKeyboardButton("📢 Broadcast All Bots", callback_data="admin:allbroadcast")],
        [InlineKeyboardButton("🔐 Bot Creation", callback_data="admin:creation")],
    ])

@main_app.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    await ensure_user(message)
    await message.reply_text(
        "👋 **Welcome to Managed Downloader Bots!**\n\n"
        "Create and manage your own downloader bot from this platform.",
        reply_markup=main_keyboard(message.from_user.id),
    )

@main_app.on_message(filters.command("admin") & filters.private)
async def admin_cmd(client: Client, message: Message):
    await ensure_user(message)
    if message.from_user.id not in config.ADMIN_IDS:
        return await message.reply_text("⛔ Admin only.")
    await message.reply_text("👑 **Main Admin Panel**", reply_markup=admin_keyboard())

@main_app.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    await query.answer()
    uid = query.from_user.id
    data = query.data or ""

    if data == "main:create":
        if not await can_create_bot(uid):
            return await query.message.edit_text(
                "⛔ You do not have bot-creation access yet.\n\nAsk the Main Admin to grant access.",
                reply_markup=main_keyboard(uid),
            )
        if await count_user_bots(uid) >= config.MAX_BOTS_PER_USER:
            return await query.message.edit_text(
                f"⛔ Maximum {config.MAX_BOTS_PER_USER} bots per user.",
                reply_markup=main_keyboard(uid),
            )
        await query.message.edit_text(
            "🤖 **Create New Bot**\n\n"
            "Send the bot name and username in one message:\n\n"
            "`My Downloader | MyDownloaderBot`\n\n"
            "The username must end with `bot`.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main:back")]]),
        )
        pending_create[uid] = True
        return

    if data == "main:back":
        return await query.message.edit_text("🏠 Main Menu", reply_markup=main_keyboard(uid))

    if data == "main:mybots":
        bots = await get_user_bots(uid)
        if not bots:
            text = "📦 You have no managed bots yet."
        else:
            text = "📦 **Your Managed Bots**\n\n" + "\n".join(
                f"🤖 @{b['username']} — {b.get('status', 'active')} — {b.get('total_users', 0)} users"
                for b in bots
            )
        return await query.message.edit_text(text, reply_markup=main_keyboard(uid))

    if data == "main:mystats":
        bots = await get_user_bots(uid)
        downloads = sum(b.get("total_downloads", 0) for b in bots)
        users = sum(b.get("total_users", 0) for b in bots)
        return await query.message.edit_text(
            f"📊 **My Statistics**\n\n🤖 Bots: {len(bots)}\n👥 Users: {users}\n📥 Downloads: {downloads}",
            reply_markup=main_keyboard(uid),
        )

    if data == "main:help":
        return await query.message.edit_text(
            "📚 **Help**\n\n"
            "Create a bot, open its `/admin` panel, configure Force Join and broadcasts, then share the bot with your users.",
            reply_markup=main_keyboard(uid),
        )

    if data == "main:admin":
        if uid not in config.ADMIN_IDS:
            return
        return await query.message.edit_text("👑 **Main Admin Panel**", reply_markup=admin_keyboard())

    if data.startswith("admin:"):
        if uid not in config.ADMIN_IDS:
            return await query.answer("Admin only.", show_alert=True)
        action = data.split(":")[1]
        if action == "stats":
            s = await get_main_stats()
            return await query.message.edit_text(
                f"📊 **System Statistics**\n\n👥 Users: {s['users']}\n🤖 Active Bots: {s['bots']}\n📥 Downloads: {s['downloads']}\n👑 Owners: {len(s['owners'])}",
                reply_markup=admin_keyboard(),
            )
        if action == "bots":
            bots = await get_user_bots(uid, limit=1000)
            # Admin's own bots are not the complete list; fetch from DB here.
            from database import bots_col
            all_bots = await bots_col.find({"status": {"$ne": "deleted"}}).sort("created_at", -1).to_list(length=100)
            text = "🤖 **All Managed Bots**\n\n" + ("\n".join(
                f"@{b['username']} | owner {b['owner_id']} | {b.get('total_users',0)} users | {b.get('status')}"
                for b in all_bots
            ) if all_bots else "No bots.")
            return await query.message.edit_text(text[:3900], reply_markup=admin_keyboard())
        if action == "users":
            from database import users_col
            total = await users_col.count_documents({})
            return await query.message.edit_text(f"👥 Total Main Bot Users: {total}", reply_markup=admin_keyboard())
        if action == "creation":
            enabled = await is_bot_creation_enabled()
            return await query.message.edit_text(
                f"🔐 **Bot Creation**\n\nStatus: {'🟢 ENABLED' if enabled else '🔴 DISABLED'}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🟢 Enable", callback_data="admin:create_on"),
                     InlineKeyboardButton("🔴 Disable", callback_data="admin:create_off")],
                    [InlineKeyboardButton("🔙 Back", callback_data="main:admin")]
                ])
            )
        if action in {"broadcast", "allbroadcast"}:
            pending_admin[uid] = action
            return await query.message.edit_text(
                "📢 Send the message/media to broadcast.\n\n"
                "For `broadcast`, this implementation targets Main Bot users.\n"
                "For `allbroadcast`, it targets users of every active managed bot.\n\nSend /cancel to abort."
            )

    if data in {"admin:create_on", "admin:create_off"}:
        if uid not in config.ADMIN_IDS:
            return
        await toggle_bot_creation(data.endswith("on"))
        return await query.message.edit_text("✅ Setting updated.", reply_markup=admin_keyboard())

pending_create = {}
pending_admin = {}

@main_app.on_message(filters.private & ~filters.command(["start", "admin", "cancel"]))
async def text_handler(client: Client, message: Message):
    await ensure_user(message)
    uid = message.from_user.id

    if uid in pending_create:
        pending_create.pop(uid, None)
        raw = message.text or ""
        if "|" not in raw:
            return await message.reply_text("Use: `Bot Name | BotUsernameBot`")
        bot_name, bot_username = [x.strip() for x in raw.split("|", 1)]
        status = await message.reply_text("⏳ Creating your bot through BotFather...")
        try:
            token, final_username = await create_bot_via_botfather(bot_name, bot_username)
            # Register first, then let the Bot Manager start the managed bot.
            # The manager performs the real Bot API validation.
            await database_register(uid, token, bot_name, final_username, None)
            started = await start_managed_bot(token, final_username, uid)
            if not started:
                raise RuntimeError("Bot was created but could not be started on the server.")
            await status.edit_text(
                f"✅ **Bot Created Successfully**\n\n🤖 @{final_username}\n\n"
                f"Open it: https://t.me/{final_username}\n\n"
                "Admin panel: send `/admin` inside your managed bot.",
                reply_markup=main_keyboard(uid),
            )
        except Exception as exc:
            await status.edit_text(f"❌ Bot creation failed:\n\n{str(exc)[:1000]}")
        return

    if uid in pending_admin:
        mode = pending_admin.pop(uid)
        await message.reply_text("📢 Broadcast processing started...")
        # Main Bot broadcast implementation.
        if mode == "broadcast":
            from database import users_col
            users = await users_col.find({"user_id": {"$ne": uid}}).to_list(length=200000)
            sent = failed = 0
            for user in users:
                try:
                    await message.copy(user["user_id"])
                    sent += 1
                except Exception:
                    failed += 1
            await message.reply_text(f"📢 Broadcast finished.\n\n✅ Sent: {sent}\n❌ Failed: {failed}")
        else:
            from database import bots_col, bot_users_col
            from bot_manager import active_bots
            bots = await bots_col.find({"status": "active"}).to_list(length=2000)
            sent = failed = 0
            seen = set()
            for bot in bots:
                users = await bot_users_col.find({"bot_username": bot["username"], "is_blocked": {"$ne": True}}).to_list(length=200000)
                app = active_bots.get(bot["username"])
                if not app:
                    continue
                for user in users:
                    target = user["user_id"]
                    if target in seen:
                        continue
                    seen.add(target)
                    try:
                        await app.send_message(target, message.text or "")
                        sent += 1
                    except Exception:
                        failed += 1
            await message.reply_text(f"📢 All-bots broadcast finished.\n\n✅ Sent: {sent}\n❌ Failed: {failed}")
        return

@main_app.on_message(filters.command("cancel") & filters.private)
async def cancel_cmd(client: Client, message: Message):
    pending_create.pop(message.from_user.id, None)
    pending_admin.pop(message.from_user.id, None)
    await message.reply_text("✅ Cancelled.")

async def database_register(owner_id, token, name, username, bot_id=None):
    from database import register_bot, log_event
    await register_bot(owner_id, token, name, username, bot_id)
    await log_event("bot_created", owner_id=owner_id, bot_username=username)

async def startup():
    await init_db()
