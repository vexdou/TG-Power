import asyncio
import logging

from database import get_all_active_bots, get_bot_by_username, log_event
from managed_bot import ManagedBotHandler

logger = logging.getLogger("TG-POWER.BOT-MANAGER")
active_bots = {}
manager_lock = asyncio.Lock()


def _clean_username(username):
    return (username or "").strip().lstrip("@").lower()


async def _run_handler(handler):
    await handler.app.initialize()
    await handler.app.start()
    if handler.app.updater is not None:
        await handler.app.updater.start_polling(drop_pending_updates=True)


async def start_managed_bot(token: str, bot_username: str, owner_id: int):
    username = _clean_username(bot_username)
    if not token or not username or not owner_id:
        logger.error("Invalid managed bot data: %r %r", username, owner_id)
        return False

    async with manager_lock:
        if username in active_bots:
            return True
        handler = ManagedBotHandler(username, token)
        try:
            await _run_handler(handler)
            active_bots[username] = handler
            await log_event("bot_started", bot_username=username, owner_id=owner_id)
            logger.info("🟢 Managed bot started: @%s", username)
            return True
        except Exception:
            logger.exception("🔴 Failed to start managed bot @%s", username)
            try:
                await handler.app.shutdown()
            except Exception:
                pass
            await log_event("bot_start_failed", bot_username=username, owner_id=owner_id)
            return False


async def stop_managed_bot(bot_username: str):
    username = _clean_username(bot_username)
    async with manager_lock:
        handler = active_bots.pop(username, None)
    if not handler:
        return False
    try:
        if handler.app.updater and handler.app.updater.running:
            await handler.app.updater.stop()
        if handler.app.running:
            await handler.app.stop()
        await handler.app.shutdown()
        await log_event("bot_stopped", bot_username=username)
        logger.info("🔴 Managed bot stopped: @%s", username)
        return True
    except Exception:
        logger.exception("Failed to stop @%s", username)
        return False


async def init_all_bots():
    try:
        bots = await get_all_active_bots()
    except Exception:
        logger.exception("Could not load managed bots")
        return {"started": 0, "failed": 0, "skipped": 0}
    started = failed = skipped = 0
    for bot in bots:
        token = (bot.get("token") or "").strip()
        username = _clean_username(bot.get("username"))
        owner_id = bot.get("owner_id")
        if not token or not username or not owner_id:
            skipped += 1
            continue
        if await start_managed_bot(token, username, int(owner_id)):
            started += 1
        else:
            failed += 1
    return {"started": started, "failed": failed, "skipped": skipped}


async def restart_bot_from_db(bot_username: str):
    username = _clean_username(bot_username)
    bot = await get_bot_by_username(username)
    if not bot:
        return False
    await stop_managed_bot(username)
    return await start_managed_bot(bot.get("token"), username, int(bot.get("owner_id")))


async def shutdown_all_bots():
    for username in list(active_bots):
        await stop_managed_bot(username)
