import asyncio
import logging

from telegram import Update

from managed_bot import ManagedBotHandler
from database import db

logger = logging.getLogger(__name__)


class DynamicBotManager:
    def __init__(self):
        self.running_bots = {}
        self.starting_bots = set()

    async def load_and_start_all(self):
        bots = await db.get_all_bots()
        active = [b for b in bots if b.get("status") == "active"]
        logger.info("🔄 Loading %s active managed bots...", len(active))
        tasks = []
        for bot in active:
            bot_id = bot.get("bot_id")
            token = bot.get("token")
            if not bot_id or not token:
                logger.error("⚠️ Invalid managed bot record: %s", bot)
                continue
            tasks.append(asyncio.create_task(self.start_bot_instance(bot_id, token)))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def start_bot_instance(self, bot_id, token):
        if bot_id in self.running_bots:
            return True
        if bot_id in self.starting_bots:
            return False

        self.starting_bots.add(bot_id)
        handler = None
        try:
            handler = ManagedBotHandler(bot_id, token)
            await handler.app.initialize()
            me = await handler.app.bot.get_me()
            await handler.app.bot.delete_webhook(drop_pending_updates=True)
            await handler.app.start()
            if handler.app.updater is None:
                raise RuntimeError("Telegram updater is not available.")
            await handler.app.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES,
                poll_interval=1.0,
                timeout=30,
            )
            self.running_bots[bot_id] = handler
            await db.update_bot_status(bot_id, "active")
            logger.info("🟢 Managed Bot @%s (%s) is fully ONLINE!", me.username, bot_id)
            return True
        except Exception as exc:
            logger.exception("🔴 Failed to start managed bot %s", bot_id)
            if handler:
                try:
                    if handler.app.updater and handler.app.updater.running:
                        await handler.app.updater.stop()
                except Exception:
                    pass
                try:
                    if handler.app.running:
                        await handler.app.stop()
                except Exception:
                    pass
                try:
                    await handler.app.shutdown()
                except Exception:
                    pass
            try:
                await db.update_bot_status(bot_id, "failed", str(exc))
            except Exception:
                logger.exception("Could not update bot %s status", bot_id)
            return False
        finally:
            self.starting_bots.discard(bot_id)

    async def stop_bot_instance(self, bot_id):
        handler = self.running_bots.pop(bot_id, None)
        if not handler:
            return
        try:
            if handler.app.updater and handler.app.updater.running:
                await handler.app.updater.stop()
            if handler.app.running:
                await handler.app.stop()
            await handler.app.shutdown()
            await db.update_bot_status(bot_id, "stopped")
        except Exception:
            logger.exception("Error stopping bot %s", bot_id)

    async def stop_all(self):
        ids = list(self.running_bots)
        if ids:
            await asyncio.gather(
                *[self.stop_bot_instance(bot_id) for bot_id in ids],
                return_exceptions=True,
            )


bot_manager = DynamicBotManager()
