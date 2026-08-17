import asyncio
import logging
import os
import signal
import threading
from flask import Flask, jsonify

import config
from database import init_db
from main_bot import main_app


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    force=True,
)

logger = logging.getLogger("TG-POWER")


# ============================================================
# FLASK HEALTH SERVER
# ============================================================

web_app = Flask(__name__)

TELEGRAM_ONLINE = False
DATABASE_ONLINE = False
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
    ok = TELEGRAM_ONLINE and DATABASE_ONLINE

    return jsonify({
        "ok": ok,
        "service": "TG-Power",
        "telegram": TELEGRAM_ONLINE,
        "database": DATABASE_ONLINE,
        "managed_bots": MANAGED_BOTS_ONLINE,
    }), (200 if ok else 503)


@web_app.get("/healthz")
def healthz():
    return jsonify({
        "status": "healthy"
    })


def run_web_server():
    """
    Render health server.
    This server does NOT control the Telegram event loop.
    """

    port = int(os.getenv("PORT", "10000"))

    logger.info("🌐 Starting Render health server on port %s", port)

    try:
        web_app.run(
            host="0.0.0.0",
            port=port,
            debug=False,
            use_reloader=False,
            threaded=True,
        )

    except Exception:
        logger.exception("❌ Health server crashed")


# ============================================================
# TELEGRAM / SERVICES
# ============================================================

async def start_services():
    global TELEGRAM_ONLINE
    global DATABASE_ONLINE
    global MANAGED_BOTS_ONLINE

    logger.info("")
    logger.info("==============================================")
    logger.info("             TG-POWER STARTING")
    logger.info("==============================================")

    # --------------------------------------------------------
    # CONFIGURATION CHECK
    # --------------------------------------------------------

    logger.info("🔍 Checking configuration...")

    required = {
        "BOT_TOKEN": getattr(config, "BOT_TOKEN", None),
        "API_ID": getattr(config, "API_ID", None),
        "API_HASH": getattr(config, "API_HASH", None),
        "MONGO_URI": getattr(config, "MONGO_URI", None),
    }

    missing = [
        name
        for name, value in required.items()
        if value is None or value == "" or value == 0
    ]

    if missing:
        logger.error(
            "❌ Missing required environment variables: %s",
            ", ".join(missing),
        )
        raise RuntimeError(
            "Missing required configuration: "
            + ", ".join(missing)
        )

    logger.info("✅ Configuration looks valid.")

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    logger.info("🗄️ Connecting to MongoDB...")

    try:
        await init_db()

        DATABASE_ONLINE = True

        logger.info("🟢 MongoDB connected successfully.")

    except Exception:
        DATABASE_ONLINE = False

        logger.exception("❌ MongoDB initialization failed.")

        raise

    # --------------------------------------------------------
    # MAIN TELEGRAM BOT
    # --------------------------------------------------------

    logger.info("🤖 Connecting Main Telegram Bot...")

    try:
        await main_app.start()

        me = await main_app.get_me()

        TELEGRAM_ONLINE = True

        logger.info("")
        logger.info("==============================================")
        logger.info("        MAIN TELEGRAM BOT CONNECTED")
        logger.info("==============================================")
        logger.info("🤖 Name: %s", me.first_name or "")
        logger.info("👤 Username: @%s", me.username or "")
        logger.info("🆔 ID: %s", me.id)
        logger.info("📡 Telegram updates: ACTIVE")
        logger.info("==============================================")

    except Exception as exc:

        TELEGRAM_ONLINE = False

        logger.exception(
            "❌ MAIN TELEGRAM BOT FAILED TO START: %s",
            exc,
        )

        raise

    # --------------------------------------------------------
    # MANAGED BOT MANAGER
    # --------------------------------------------------------

    logger.info("🤖 Starting Managed Bot Manager...")

    try:
        from bot_manager import init_all_bots

        await init_all_bots()

        MANAGED_BOTS_ONLINE = True

        logger.info(
            "🟢 Managed Bot Manager initialized successfully."
        )

    except Exception as exc:

        MANAGED_BOTS_ONLINE = False

        # Important:
        # Main Bot should remain online even if one managed bot
        # has a bad token.
        logger.exception(
            "⚠️ Managed Bot Manager failed: %s",
            exc,
        )

    # --------------------------------------------------------
    # FINAL STATUS
    # --------------------------------------------------------

    logger.info("")
    logger.info("==============================================")
    logger.info("              TG-POWER ONLINE")
    logger.info("==============================================")
    logger.info(
        "🗄️ MongoDB:       %s",
        "🟢 ONLINE" if DATABASE_ONLINE else "🔴 OFFLINE",
    )
    logger.info(
        "🤖 Main Bot:      %s",
        "🟢 ONLINE" if TELEGRAM_ONLINE else "🔴 OFFLINE",
    )
    logger.info(
        "🤖 Bot Manager:   %s",
        "🟢 ONLINE" if MANAGED_BOTS_ONLINE else "🟡 LIMITED",
    )
    logger.info("🌐 Health Server:  🟢 ONLINE")
    logger.info("==============================================")
    logger.info("")

    # Keep asyncio loop alive.
    await asyncio.Event().wait()


# ============================================================
# SHUTDOWN
# ============================================================

async def shutdown():
    global TELEGRAM_ONLINE

    logger.info("🛑 Shutdown requested.")

    try:
        from bot_manager import active_bots, manager_lock

        async with manager_lock:
            bots = list(active_bots.items())

        for username, app in bots:
            try:
                if app.is_connected:
                    logger.info(
                        "🔴 Stopping managed bot @%s",
                        username,
                    )
                    await app.stop()
            except Exception:
                logger.exception(
                    "⚠️ Failed stopping @%s",
                    username,
                )

        active_bots.clear()

    except Exception:
        logger.exception(
            "⚠️ Managed bot shutdown error."
        )

    try:
        if main_app.is_connected:
            logger.info("🔴 Stopping Main Telegram Bot...")
            await main_app.stop()

    except Exception:
        logger.exception(
            "⚠️ Main Bot shutdown error."
        )

    TELEGRAM_ONLINE = False

    logger.info("✅ TG-Power shutdown completed.")


# ============================================================
# SIGNAL HANDLING
# ============================================================

def install_signal_handlers(loop):
    def request_shutdown():
        logger.info(
            "🛑 Operating system shutdown signal received."
        )

        for task in asyncio.all_tasks(loop):
            if not task.done():
                task.cancel()

    try:
        loop.add_signal_handler(
            signal.SIGTERM,
            request_shutdown,
        )

        loop.add_signal_handler(
            signal.SIGINT,
            request_shutdown,
        )

    except (NotImplementedError, RuntimeError):
        logger.warning(
            "⚠️ Async signal handlers are unavailable."
        )


# ============================================================
# MAIN
# ============================================================

def main():

    logger.info("🚀 TG-Power process starting...")

    # --------------------------------------------------------
    # START WEB SERVER
    # --------------------------------------------------------

    web_thread = threading.Thread(
        target=run_web_server,
        name="render-health-server",
        daemon=True,
    )

    web_thread.start()

    logger.info(
        "🌐 Render health server thread started."
    )

    # --------------------------------------------------------
    # ASYNCIO LOOP
    # --------------------------------------------------------

    loop = asyncio.new_event_loop()

    asyncio.set_event_loop(loop)

    install_signal_handlers(loop)

    try:

        loop.run_until_complete(
            start_services()
        )

    except asyncio.CancelledError:

        logger.info(
            "🛑 Main asyncio task cancelled."
        )

    except KeyboardInterrupt:

        logger.info(
            "🛑 Keyboard interrupt received."
        )

    except Exception:

        logger.exception(
            "❌ TG-Power stopped because of a fatal error."
        )

        # Let Render know that the process really failed.
        raise

    finally:

        try:
            loop.run_until_complete(
                shutdown()
            )
        except Exception:
            logger.exception(
                "⚠️ Shutdown cleanup failed."
            )

        try:

            pending = asyncio.all_tasks(loop)

            for task in pending:
                task.cancel()

            if pending:
                loop.run_until_complete(
                    asyncio.gather(
                        *pending,
                        return_exceptions=True,
                    )
                )

        except Exception:
            logger.exception(
                "⚠️ Failed cancelling pending tasks."
            )

        try:
            loop.close()
        except Exception:
            logger.exception(
                "⚠️ Failed closing asyncio loop."
            )

    logger.info("🛑 TG-Power process stopped.")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
