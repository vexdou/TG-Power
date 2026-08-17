import asyncio
import logging

from pyrogram import Client

import config
from database import get_all_active_bots, get_bot_by_username, log_event
from managed_bot import build_managed_bot_handlers

logger = logging.getLogger("TG-POWER.BOT-MANAGER")

active_bots = {}
manager_lock = asyncio.Lock()

def _clean_username(username):
    return (username or "").strip().lstrip("@").lower()

async def start_managed_bot(token: str, bot_username: str, owner_id: int):
    username = _clean_username(bot_username)

    if not token or not username or not owner_id:
        logger.error(
            "❌ Invalid managed bot data: username=%r owner=%r",
            username, owner_id
        )
        return False

    # Never run the Main Bot twice.
    if token.strip() == config.BOT_TOKEN.strip():
        logger.error(
            "⛔ Refusing to start @%s as a managed bot because it uses Main BOT_TOKEN.",
            username,
        )
        return False

    async with manager_lock:
        if username in active_bots:
            return True

        app = Client(
            name=f"managed_{username}",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=token,
            in_memory=True,
            workers=8,
        )

        build_managed_bot_handlers(app, username, owner_id)

        try:
            await app.start()
            me = await app.get_me()

            active_bots[username] = app

            try:
                await log_event(
                    "bot_started",
                    bot_username=username,
                    owner_id=owner_id,
                )
            except Exception:
                logger.exception("Could not log managed bot start")

            logger.info(
                "🟢 Managed bot started: @%s",
                me.username or username,
            )
            return True

        except Exception as exc:
            logger.exception(
                "🔴 Failed to start managed bot @%s: %s",
                username, exc
            )
            try:
                await app.stop()
            except Exception:
                pass

            try:
                await log_event(
                    "bot_start_failed",
                    bot_username=username,
                    owner_id=owner_id,
                    error=str(exc),
                )
            except Exception:
                pass

            return False

async def stop_managed_bot(bot_username: str):
    username = _clean_username(bot_username)

    async with manager_lock:
        app = active_bots.pop(username, None)

    if not app:
        return False

    try:
        if app.is_connected:
            await app.stop()

        try:
            await log_event("bot_stopped", bot_username=username)
        except Exception:
            pass

        logger.info("🔴 Managed bot stopped: @%s", username)
        return True
    except Exception:
        logger.exception("⚠️ Failed to stop @%s", username)
        return False

async def init_all_bots():
    try:
        bots = await get_all_active_bots()
    except Exception:
        logger.exception("❌ Could not load managed bots from database")
        return {"started": 0, "failed": 0, "skipped": 0}

    started = failed = skipped = 0

    for bot in bots:
        token = (bot.get("token") or "").strip()
        username = _clean_username(bot.get("username"))
        owner_id = bot.get("owner_id")

        if not token or not username or not owner_id:
            skipped += 1
            logger.warning(
                "⚠️ Skipping malformed bot record @%s",
                username or "unknown",
            )
            continue

        if token == config.BOT_TOKEN.strip():
            skipped += 1
            logger.warning(
                "⛔ Skipping @%s: it uses the Main BOT_TOKEN.",
                username,
            )
            continue

        try:
            ok = await start_managed_bot(
                token, username, int(owner_id)
            )
            if ok:
                started += 1
            else:
                failed += 1
        except Exception:
            failed += 1
            logger.exception(
                "⚠️ Unexpected error starting @%s", username
            )

    logger.info(
        "📊 Managed bot startup: started=%s failed=%s skipped=%s",
        started, failed, skipped
    )
    return {
        "started": started,
        "failed": failed,
        "skipped": skipped,
    }

async def restart_bot_from_db(bot_username: str):
    username = _clean_username(bot_username)
    bot = await get_bot_by_username(username)
    if not bot:
        return False

    await stop_managed_bot(username)

    return await start_managed_bot(
        bot["token"],
        bot["username"],
        bot["owner_id"],
    )

async def shutdown_all_bots():
    async with manager_lock:
        items = list(active_bots.items())
        active_bots.clear()

    for username, app in items:
        try:
            if app.is_connected:
                await app.stop()
            logger.info("🔴 Shutdown managed bot @%s", username)
        except Exception:
            logger.exception(
                "⚠️ Error shutting down @%s", username
            )
