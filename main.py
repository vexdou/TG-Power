import asyncio
import logging
import os
from aiohttp import web  # Ku dar aiohttp
from database import db
from bot_manager import bot_manager
from main_bot import main_bot

# Logger configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("TG-Power")

# Web handler ee UptimeRobot iyo Render ping-ga
async def handle_ping(request):
    return web.Response(text="TG-Power Platform is ALIVE 24/7!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))  # Render PORT-kiisa
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"🌐 Web Server started on port {port}")

async def main():
    logger.info("🚀 Starting TG-Power Platform...")

    # 1. Start Web Server for Render Keep-Alive
    await start_web_server()

    # 2. Initialize MongoDB Database
    logger.info("Initializing Database...")
    await db.init_db()

    # 3. Start Main SaaS Controller Bot (Non-blocking)
    logger.info("Starting Main SaaS Controller Bot...")
    await main_bot.start_bot()

    # 4. Load & Start All Active Sub-Bots (Managed Bots)
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
