import asyncio
import logging
import os

from aiohttp import web

from database import db
from bot_manager import bot_manager
from main_bot import main_bot
from config import Config

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=os.getenv("LOG_LEVEL", "INFO"),
)
logger = logging.getLogger("TG-Power")


async def handle_ping(request):
    return web.Response(text="TG-Power Platform is ALIVE 24/7!")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info("🌐 Web Server started on port %s", port)


async def load_persisted_settings():
    max_video = await db.get_system_setting("max_video_seconds", None)
    max_file = await db.get_system_setting("max_file_mb", None)
    if isinstance(max_video, int) and max_video > 0:
        Config.MAX_VIDEO_DURATION_SECONDS = max_video
    if isinstance(max_file, int) and max_file > 0:
        Config.MAX_FILE_SIZE_MB = max_file


async def main():
    logger.info("🚀 Starting TG-Power Platform...")

    await start_web_server()

    logger.info("Initializing Database...")
    await db.connect()
    await load_persisted_settings()

    logger.info("Starting Main SaaS Controller Bot...")
    await main_bot.start_controller()

    logger.info("Loading Active Managed Bots...")
    await bot_manager.load_and_start_all()

    logger.info("✅ TG-Power Platform is FULLY ACTIVE and listening!")

    try:
        await asyncio.Event().wait()
    finally:
        await bot_manager.stop_all()
        await main_bot.stop_controller()
        await db.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Platform shutting down safely...")
