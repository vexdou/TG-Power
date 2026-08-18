import asyncio
import logging
from database import db
from bot_manager import bot_manager
from main_bot import main_bot

# Logger configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("TG-Power")

async def main():
    logger.info("🚀 Starting TG-Power Platform...")

    # 1. Initialize MongoDB Database
    logger.info("Initializing Database...")
    await db.init_db()

    # 2. Start Main SaaS Controller Bot (Non-blocking)
    logger.info("Starting Main SaaS Controller Bot...")
    await main_bot.start_bot()

    # 3. Load & Start All Active Sub-Bots (Managed Bots)
    logger.info("Loading Active Managed Bots...")
    await bot_manager.load_and_start_all()

    logger.info("✅ TG-Power Platform is FULLY ACTIVE and listening!")

    # Keep loop running infinitely without blocking background tasks
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Platform shutting down safely...")
