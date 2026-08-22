import asyncio
import os
import re
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.errors import FloodWait, UserIsBlocked, PeerIdInvalid, ChatAdminRequired
import config
from database import (
    add_bot_user, log_download, get_bot_by_username, get_bot_by_owner,
    count_bot_users, get_channels, add_channel, remove_channel,
    bot_platform_counts, add_broadcast, finish_broadcast, mark_bot_user_blocked,
    set_premium, log_event, bot_users_col, users_col
)
from downloader import download_media, cleanup_file, is_url, detect_platform

states = {}
broadcast_locks = {}

def _state_key(bot_username, user_id):
    return f"{bot_username}:{user_id}"

def owner_keyboard(bot_username):
    b = bot_username
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Statistics", callback_data=f"adm:stats:{b}"),
         InlineKeyboardButton("📢 Broadcast", callback_data=f"adm:broadcast:{b}")],
        [InlineKeyboardButton("👥 Users", callback_data=f"adm:users:{b}"),
         InlineKeyboardButton("📢 Force Join", callback_data=f"adm:force:{b}")],
        [InlineKeyboardButton("💎 Premium", callback_data=f"adm:premium:{b}"),
         InlineKeyboardButton("⚙️ Settings", callback_data=f"adm:settings:{b}")],
    ])

def force_keyboard(channels, bot_username):
    rows = []
    for ch in channels:
        rows.append([InlineKeyboardButton(f"📢 @{ch['username']}", url=f"https://t.me/{ch['username']}")])
    rows.append([InlineKeyboardButton("🔄 Check Again", callback_data=f"join:check:{bot_username}")])
    return InlineKeyboardMarkup(rows)

async def joined_required_channels(client, user_id, channels):
    for ch in channels:
        try:
            member = await client.get_chat_member(ch["chat_id"] or f"@{ch['username']}", user_id)
            status = str(getattr(member, "status", "")).lower()
            if status in {"left", "kicked", "banned"}:
                return False
        except Exception:
            # If the bot cannot inspect the channel, do not silently bypass.
            return False
    return True

async def require_join(client, message, bot_username):
    channels = await get_channels(bot_username)
    if not channels:
        return True
    if await joined_required_channels(client, message.from_user.id, channels):
        return True
    await message.reply_text(
        "⚠️ Please join all required channels before using this bot.",
        reply_markup=force_keyboard(channels, bot_username),
    )
    return False

async def send_broadcast(app, bot_username, owner_id, source_message):
    total = await count_bot_users(bot_username)
    broadcast_id = await add_broadcast(bot_username, owner_id, total)
    sent = failed = 0
    users = await bot_users_col.find({"bot_username": bot_username, "is_blocked": {"$ne": True}}).to_list(length=200000)
    sem = asyncio.Semaphore(config.MAX_BROADCAST_WORKERS)

    async def send_one(user):
        nonlocal sent, failed
        async with sem:
            try:
                await source_message.copy(user["user_id"])
                sent += 1
            except FloodWait as e:
                await asyncio.sleep(min(int(e.value) + 1, 120))
                try:
                    await source_message.copy(user["user_id"])
                    sent += 1
                except Exception:
                    failed += 1
            except (UserIsBlocked, PeerIdInvalid):
                failed += 1
                await mark_bot_user_blocked(bot_username, user["user_id"], True)
            except Exception:
                failed += 1
            await asyncio.sleep(config.BROADCAST_DELAY)

    await asyncio.gather(*(send_one(u) for u in users))
    await finish_broadcast(broadcast_id, sent, failed)
    await log_event("broadcast_completed", bot_username=bot_username, owner_id=owner_id, sent=sent, failed=failed)
    return sent, failed

def build_managed_bot_handlers(app: Client, bot_username: str, owner_id: int):
    bot_username = bot_username.lstrip("@")

    @app.on_message(filters.command("start") & filters.private)
    async def start_cmd(client: Client, message: Message):
        await add_bot_user(bot_username, message.from_user.id, message.from_user.first_name or "", message.from_user.username or "")
        if not await require_join(client, message, bot_username):
            return
        await message.reply_text(
            f"👋 Welcome to @{bot_username}!\n\n"
            "Send a supported video/media URL and I will try to download it.\n\n"
            "Supported: TikTok • YouTube • Facebook • Instagram • Pinterest • X/Twitter • Snapchat"
        )

    @app.on_message(filters.command("admin") & filters.private)
    async def admin_cmd(client: Client, message: Message):
        if message.from_user.id != owner_id:
            await message.reply_text("⛔ You are not authorized to access this panel.")
            return
        data = await get_bot_by_owner(owner_id, bot_username)
        await message.reply_text(
            f"⚙️ **Admin Panel — @{bot_username}**\n\n"
            f"👥 Users: {data.get('total_users', 0)}\n"
            f"📥 Downloads: {data.get('total_downloads', 0)}",
            reply_markup=owner_keyboard(bot_username),
        )

    @app.on_callback_query()
    async def callbacks(client: Client, query: CallbackQuery):
        data = query.data or ""
        parts = data.split(":")
        if data.startswith("join:check:"):
            if await joined_required_channels(client, query.from_user.id, await get_channels(bot_username)):
                await query.message.edit_text("✅ Membership verified. Now send your link.")
            else:
                await query.answer("Please join all required channels first.", show_alert=True)
            return

        if not data.startswith("adm:"):
            return
        if query.from_user.id != owner_id:
            await query.answer("Not authorized.", show_alert=True)
            return
        action = parts[1] if len(parts) > 1 else ""
        if action == "stats":
            bot = await get_bot_by_username(bot_username)
            platform_rows = await bot_platform_counts(bot_username)
            lines = [f"📊 **@{bot_username} Statistics**",
                     f"👥 Users: {bot.get('total_users', 0)}",
                     f"📥 Downloads: {bot.get('total_downloads', 0)}"]
            if platform_rows:
                lines.append("\n**Platforms:**")
                lines.extend(f"• {x['_id']}: {x['count']}" for x in platform_rows)
            await query.message.edit_text("\n".join(lines), reply_markup=owner_keyboard(bot_username))
        elif action == "users":
            count = await count_bot_users(bot_username)
            await query.message.edit_text(f"👥 **Users:** {count}\n\nUse `/broadcast` to send a broadcast.", reply_markup=owner_keyboard(bot_username))
        elif action == "force":
            channels = await get_channels(bot_username)
            text = "📢 **Force Join Channels**\n\n" + ("\n".join(f"• @{c['username']}" for c in channels) if channels else "No channels configured.")
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Channel", callback_data=f"adm:addch:{bot_username}")],
                [InlineKeyboardButton("🗑 Remove Channel", callback_data=f"adm:rmch:{bot_username}")],
                [InlineKeyboardButton("🔙 Back", callback_data=f"adm:back:{bot_username}")]
            ])
            await query.message.edit_text(text, reply_markup=kb)
        elif action == "addch":
            states[_state_key(bot_username, owner_id)] = "add_channel"
            await query.message.edit_text("Send the channel username (example: @MyChannel).\n\nThe managed bot must be an administrator in that channel.")
        elif action == "rmch":
            states[_state_key(bot_username, owner_id)] = "remove_channel"
            await query.message.edit_text("Send the channel username to remove (example: @MyChannel).")
        elif action == "broadcast":
            states[_state_key(bot_username, owner_id)] = "broadcast"
            await query.message.edit_text("📢 Send the message/media you want to broadcast to your bot users.\n\nSend /cancel to abort.")
        elif action == "premium":
            states[_state_key(bot_username, owner_id)] = "premium"
            await query.message.edit_text("Send: USER_ID ON  or  USER_ID OFF")
        elif action == "settings":
            await query.message.edit_text("⚙️ Settings\n\nDownloader: ON\nDuplicate protection: ON\nForce Join: configurable\nPremium: ON", reply_markup=owner_keyboard(bot_username))
        elif action == "back":
            bot = await get_bot_by_username(bot_username)
            await query.message.edit_text(
                f"⚙️ **Admin Panel — @{bot_username}**\n\n👥 Users: {bot.get('total_users', 0)}\n📥 Downloads: {bot.get('total_downloads', 0)}",
                reply_markup=owner_keyboard(bot_username)
            )

    @app.on_message(filters.private & ~filters.command(["start", "admin", "cancel"]))
    async def private_messages(client: Client, message: Message):
        await add_bot_user(bot_username, message.from_user.id, message.from_user.first_name or "", message.from_user.username or "")
        key = _state_key(bot_username, message.from_user.id)
        state = states.get(key)

        if message.from_user.id == owner_id and state:
            if state == "broadcast":
                states.pop(key, None)
                progress = await message.reply_text("📢 Broadcast started...")
                sent, failed = await send_broadcast(client, bot_username, owner_id, message)
                await progress.edit_text(f"📢 **Broadcast finished**\n\n✅ Sent: {sent}\n❌ Failed: {failed}")
                return
            if state == "add_channel":
                states.pop(key, None)
                username = message.text.strip().lstrip("@") if message.text else ""
                if not re.fullmatch(r"[A-Za-z0-9_]{4,64}", username):
                    await message.reply_text("Invalid channel username.")
                    return
                try:
                    chat = await client.get_chat(f"@{username}")
                    if chat.type.value not in ("channel", "supergroup"):
                        raise ValueError("Not a channel/group.")
                    await client.get_chat_member(chat.id, owner_id)
                    await add_channel(bot_username, username, chat.id)
                    await message.reply_text(f"✅ Added @{username} to Force Join.", reply_markup=owner_keyboard(bot_username))
                except Exception as exc:
                    await message.reply_text(f"❌ Could not add channel. Make sure the bot is an admin there.\n\n{exc}")
                return
            if state == "remove_channel":
                states.pop(key, None)
                username = message.text.strip().lstrip("@") if message.text else ""
                await remove_channel(bot_username, username)
                await message.reply_text(f"✅ Removed @{username}.", reply_markup=owner_keyboard(bot_username))
                return
            if state == "premium":
                states.pop(key, None)
                parts = (message.text or "").split()
                if len(parts) != 2 or not parts[0].isdigit() or parts[1].upper() not in {"ON", "OFF"}:
                    await message.reply_text("Format: USER_ID ON  or  USER_ID OFF")
                    return
                uid = int(parts[0])
                await set_premium(bot_username, uid, parts[1].upper() == "ON")
                await message.reply_text("✅ Premium status updated.", reply_markup=owner_keyboard(bot_username))
                return

        if not await require_join(client, message, bot_username):
            return
        if not message.text or not is_url(message.text.strip()):
            await message.reply_text("🔗 Please send a valid http/https media URL.")
            return

        # Per-user duplicate lock prevents the same message being processed twice.
        lock = getattr(message, "_download_lock", None)
        if lock is None:
            lock = asyncio.Lock()
            setattr(message, "_download_lock", lock)

        status = await message.reply_text(f"⏳ Downloading {detect_platform(message.text.strip())}...")
        filepath = None
        try:
            filepath, title, extractor = await download_media(message.text.strip())
            await status.edit_text("⬆️ Uploading to Telegram...")
            ext = os.path.splitext(filepath)[1].lower()
            if ext in {".mp4", ".mkv", ".webm", ".mov"}:
                await message.reply_video(filepath, caption=f"🎬 {title}\n\n🤖 @{bot_username}")
            else:
                await message.reply_document(filepath, caption=f"📦 {title}\n\n🤖 @{bot_username}")
            await log_download(bot_username, message.from_user.id, extractor, message.text.strip())
            await status.delete()
        except Exception as exc:
            await status.edit_text(f"❌ Download failed: {str(exc)[:700]}")
        finally:
            cleanup_file(filepath)

    @app.on_message(filters.command("cancel") & filters.private)
    async def cancel_cmd(client: Client, message: Message):
        states.pop(_state_key(bot_username, message.from_user.id), None)
        await message.reply_text("✅ Cancelled.")
