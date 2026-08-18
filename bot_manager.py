import asyncio
import logging
from managed_bot import ManagedBotHandler
from database import db

logger = logging.getLogger(__name__)

class DynamicBotManager:
    def __init__(self):
        self.running_bots: dict[int, ManagedBotHandler] = {}

    async def load_and_start_all(self):
        active_bots = await db.get_all_active_bots()
        for bot in active_bots:
            await self.start_bot_instance(bot["bot_id"], bot["token"])

    async def start_bot_instance(self, bot_id: int, token: str) -> bool:
        if bot_id in self.running_bots:
            return True

        try:
            handler = ManagedBotHandler(bot_id, token)
            await handler.app.initialize()
            await handler.app.start()
            await handler.app.updater.start_polling(drop_pending_updates=True)
            self.running_bots[bot_id] = handler
            logger.info(f"Bot successfully started: {bot_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to start bot {bot_id}: {e}")
            await db.update_bot_status(bot_id, "failed")
            return False

    async def stop_bot_instance(self, bot_id: int):
        if bot_id in self.running_bots:
            handler = self.running_bots[bot_id]
            await handler.app.updater.stop()
            await handler.app.stop()
            await handler.app.shutdown()
            del self.running_bots[bot_id]
            logger.info(f"Bot stopped: {bot_id}")

bot_manager = DynamicBotManager()
