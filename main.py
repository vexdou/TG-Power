import asyncio
import logging
from config import Config
from database import db
from bot_manager import bot_manager
from main_bot import main_bot

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("TG-Power")

async def main():
    logger.info("Starting TG-Power Platform...")

    # 1. Initialize MongoDB Indexes
    logger.info("Initializing Database...")
    await db.init_db()

    # 2. Dynamic Loader for Managed Bots
    logger.info("Loading Active Managed Bots...")
    await bot_manager.load_and_start_all()

    # 3. Start Main Bot Platform
    logger.info("Starting Main SaaS Controller Bot...")
    await main_bot.run()

    logger.info("TG-Power Platform is FULLY ACTIVE and online!")
    
    # Run loop infinitely
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Platform shutting down safely...")
