import asyncio
import logging
import os
import signal
import threading

from flask import Flask, jsonify

import config
from database import init_db
from main_bot import main_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    force=True,
)
logger = logging.getLogger("TG-POWER")

web_app = Flask(__name__)
DATABASE_ONLINE = False
TELEGRAM_ONLINE = False
MANAGED_BOTS_ONLINE = False

@web_app.get("/")
def home():
    return jsonify({
        "service": "TG-Power",
        "status": "online",
        "telegram": TELEGRAM_ONLINE,
        "database": DATABASE_ONLINE,
        "managed_bots": MANAGED_BOTS_ONLINE,
    })

@web_app.get("/health")
def health():
    ok = DATABASE_ONLINE and TELEGRAM_ONLINE
    return jsonify({
        "ok": ok,
        "service": "TG-Power",
        "telegram": TELEGRAM_ONLINE,
        "database": DATABASE_ONLINE,
        "managed_bots": MANAGED_BOTS_ONLINE,
    }), (200 if ok else 503)

@web_app.get("/healthz")
def healthz():
    return jsonify({"status": "healthy"}), 200

def run_web():
    port = int(os.getenv("PORT", "10000"))
    logger.info("🌐 Health server listening on 0.0.0.0:%s", port)
    web_app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
        threaded=True,
    )

async def start_services():
    global DATABASE_ONLINE, TELEGRAM_ONLINE, MANAGED_BOTS_ONLINE

    logger.info("==============================================")
    logger.info("🚀 TG-POWER STARTING")
    logger.info("==============================================")

    required = {
        "BOT_TOKEN": getattr(config, "BOT_TOKEN", None),
        "API_ID": getattr(config, "API_ID", None),
        "API_HASH": getattr(config, "API_HASH", None),
        "MONGO_URI": getattr(config, "MONGO_URI", None),
    }
    missing = [
        key for key, value in required.items()
        if value is None or value == "" or value == 0
    ]
    if missing:
        raise RuntimeError("Missing environment/config values: " + ", ".join(missing))

    logger.info("🗄️ Initializing MongoDB...")
    await init_db()
    DATABASE_ONLINE = True
    logger.info("🟢 MongoDB ready")

    logger.info("🤖 Starting Main Bot...")
    try:
        await main_app.start()
        me = await main_app.get_me()
    except Exception:
        logger.exception("❌ Main Bot failed to start")
        raise

    TELEGRAM_ONLINE = True
    logger.info("==============================================")
    logger.info("🟢 MAIN BOT ONLINE")
    logger.info("Name: %s", me.first_name or "")
    logger.info("Username: @%s", me.username or "")
    logger.info("ID: %s", me.id)
    logger.info("📡 Telegram updates: ACTIVE")
    logger.info("==============================================")

    try:
        from bot_manager import init_all_bots
        logger.info("🤖 Starting Managed Bot Manager...")
        result = await init_all_bots()
        MANAGED_BOTS_ONLINE = True
        logger.info("🟢 Managed Bot Manager ready: %s", result)
    except Exception:
        MANAGED_BOTS_ONLINE = False
        logger.exception("⚠️ Managed Bot Manager had errors; Main Bot remains online")

    logger.info("==============================================")
    logger.info("🟢 TG-POWER ONLINE")
    logger.info("==============================================")
    await asyncio.Event().wait()

async def shutdown():
    global TELEGRAM_ONLINE, MANAGED_BOTS_ONLINE

    logger.info("🛑 Shutdown requested")

    try:
        from bot_manager import shutdown_all_bots
        await shutdown_all_bots()
    except Exception:
        logger.exception("⚠️ Managed bot shutdown error")

    try:
        if main_app.is_connected:
            await main_app.stop()
            logger.info("🔴 Main Bot stopped")
    except Exception:
        logger.exception("⚠️ Main Bot shutdown error")

    TELEGRAM_ONLINE = False
    MANAGED_BOTS_ONLINE = False

def main():
    threading.Thread(
        target=run_web,
        name="render-health",
        daemon=True,
    ).start()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def stop_signal():
        logger.info("🛑 Shutdown signal received")
        for task in asyncio.all_tasks(loop):
            if not task.done():
                task.cancel()

    try:
        loop.add_signal_handler(signal.SIGTERM, stop_signal)
        loop.add_signal_handler(signal.SIGINT, stop_signal)
    except (NotImplementedError, RuntimeError):
        pass

    try:
        loop.run_until_complete(start_services())
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        try:
            loop.run_until_complete(shutdown())
        except Exception:
            logger.exception("⚠️ Cleanup failed")

        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
        except Exception:
            pass
        loop.close()

if __name__ == "__main__":
    main()
