import asyncio
from pyrogram import Client
import config
from database import get_all_active_bots, get_bot_by_username, log_event
from managed_bot import build_managed_bot_handlers

active_bots = {}
manager_lock = asyncio.Lock()

async def start_managed_bot(token: str, bot_username: str, owner_id: int):
    bot_username = bot_username.lstrip("@")
    async with manager_lock:
        if bot_username in active_bots:
            return True
        app = Client(
            name=f"managed_{bot_username}",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=token,
            in_memory=True,
            workers=8,
        )
        build_managed_bot_handlers(app, bot_username, owner_id)
        try:
            await app.start()
            active_bots[bot_username] = app
            await log_event("bot_started", bot_username=bot_username, owner_id=owner_id)
            print(f"🟢 Started @{bot_username}")
            return True
        except Exception as exc:
            try:
                await app.stop()
            except Exception:
                pass
            print(f"🔴 Failed to start @{bot_username}: {exc}")
            await log_event("bot_start_failed", bot_username=bot_username, error=str(exc))
            return False

async def stop_managed_bot(bot_username: str):
    bot_username = bot_username.lstrip("@")
    async with manager_lock:
        app = active_bots.pop(bot_username, None)
        if not app:
            return
        try:
            await app.stop()
        finally:
            await log_event("bot_stopped", bot_username=bot_username)

async def init_all_bots():
    bots = await get_all_active_bots()
    for bot in bots:
        await start_managed_bot(bot["token"], bot["username"], bot["owner_id"])

async def restart_bot_from_db(bot_username: str):
    bot = await get_bot_by_username(bot_username)
    if not bot:
        return False
    await stop_managed_bot(bot_username)
    return await start_managed_bot(bot["token"], bot["username"], bot["owner_id"])
