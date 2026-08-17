import asyncio
import os
import threading
import signal
import logging
from flask import Flask, jsonify

from main_bot import main_app, startup
from bot_manager import init_all_bots


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("TG-POWER")


# ============================================================
# FLASK HEALTH SERVER
# ============================================================

web_app = Flask(__name__)


@web_app.get("/")
def home():
    return jsonify({
        "ok": True,
        "service": "TG-Power",
        "status": "online",
    })


@web_app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "service": "TG-Power",
        "telegram": "running",
    })


@web_app.get("/healthz")
def healthz():
    return jsonify({
        "status": "healthy"
    })


def run_flask():
    """
    Render health/web server.

    Telegram bot itself runs in the main asyncio event loop.
    Flask is only used for Render health checks.
    """

    port = int(os.getenv("PORT", "10000"))

    logger.info("🌐 Starting health server on port %s", port)

    try:
        # Disable Flask reloader because it can start the application twice.
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
# STARTUP
# ============================================================

async def run_services():
    """
    Start the complete TG-Power system.

    Startup order:

    1. MongoDB
    2. Main Telegram Bot
    3. Managed Bots
    4. Keep asyncio loop alive
    """

    logger.info("")
    logger.info("========================================")
    logger.info("        TG-POWER STARTING")
    logger.info("========================================")

    try:

        # ----------------------------------------------------
        # DATABASE
        # ----------------------------------------------------

        logger.info("🗄️ Initializing database...")

        await startup()

        logger.info("🗄️ Database initialization completed.")

        # ----------------------------------------------------
        # MANAGED BOTS
        # ----------------------------------------------------

        logger.info("🤖 Loading managed bots...")

        try:
            await init_all_bots()
            logger.info("🤖 Managed bot manager initialized.")
        except Exception:
            logger.exception("⚠️ Managed bot initialization failed.")
            logger.warning(
                "⚠️ Main Bot will continue running even if managed bots failed."
            )

        # ----------------------------------------------------
        # MAIN TELEGRAM BOT
        # ----------------------------------------------------

        logger.info("📡 Connecting Main Telegram Bot...")

        try:
            await main_app.start()

        except Exception:
            logger.exception("❌ Main Telegram Bot failed to start.")
            raise

        # ----------------------------------------------------
        # VERIFY BOT IDENTITY
        # ----------------------------------------------------

        try:
            me = await main_app.get_me()

            logger.info("")
            logger.info("========================================")
            logger.info("       TELEGRAM CONNECTION OK")
            logger.info("========================================")
            logger.info("🤖 Bot Name: %s", me.first_name)
            logger.info("👤 Username: @%s", me.username)
            logger.info("🆔 Bot ID: %s", me.id)
            logger.info("📡 Telegram Updates: ACTIVE")
            logger.info("========================================")

        except Exception:
            logger.exception(
                "⚠️ Bot started but get_me() verification failed."
            )

        # ----------------------------------------------------
        # SYSTEM ONLINE
        # ----------------------------------------------------

        logger.info("")
        logger.info("========================================")
        logger.info("          TG-POWER ONLINE")
        logger.info("========================================")
        logger.info("🟢 Main Bot: ONLINE")
        logger.info("🟢 Database: INITIALIZED")
        logger.info("🟢 Bot Manager: ONLINE")
        logger.info("🟢 Health Server: ONLINE")
        logger.info("========================================")
        logger.info("")

        # ----------------------------------------------------
        # KEEP ASYNCIO LOOP ALIVE
        # ----------------------------------------------------

        await asyncio.Event().wait()

    except asyncio.CancelledError:

        logger.info("🛑 Service shutdown requested.")

        raise

    except KeyboardInterrupt:

        logger.info("🛑 Keyboard interrupt received.")

    except Exception:

        logger.exception("❌ TG-Power startup/runtime failure.")

        raise

    finally:

        # ----------------------------------------------------
        # SHUTDOWN MAIN BOT
        # ----------------------------------------------------

        try:

            if main_app.is_connected:

                logger.info("🔴 Stopping Main Telegram Bot...")

                await main_app.stop()

                logger.info("✅ Main Telegram Bot stopped.")

        except Exception:

            logger.exception(
                "⚠️ Error while stopping Main Telegram Bot."
            )

        logger.info("🛑 TG-Power shutdown completed.")


# ============================================================
# SIGNAL HANDLING
# ============================================================

def install_signal_handlers(loop):
    """
    Gracefully stop asyncio application on SIGTERM/SIGINT.

    Render normally sends SIGTERM during deployment/restart.
    """

    def shutdown_signal():

        logger.info(
            "🛑 Shutdown signal received from operating system."
        )

        for task in asyncio.all_tasks(loop):

            if task is not asyncio.current_task(loop):

                task.cancel()

    try:

        loop.add_signal_handler(
            signal.SIGTERM,
            shutdown_signal,
        )

        loop.add_signal_handler(
            signal.SIGINT,
            shutdown_signal,
        )

    except (NotImplementedError, RuntimeError):

        # Some operating systems do not support
        # asyncio signal handlers.
        logger.warning(
            "⚠️ Async signal handlers are not available."
        )


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def main():

    logger.info("🚀 Starting TG-Power process...")

    # --------------------------------------------------------
    # START RENDER HEALTH SERVER
    # --------------------------------------------------------

    flask_thread = threading.Thread(
        target=run_flask,
        name="render-health-server",
        daemon=True,
    )

    flask_thread.start()

    logger.info("🌐 Render health server thread started.")

    # --------------------------------------------------------
    # CREATE ASYNCIO LOOP
    # --------------------------------------------------------

    loop = asyncio.new_event_loop()

    asyncio.set_event_loop(loop)

    install_signal_handlers(loop)

    # --------------------------------------------------------
    # RUN TELEGRAM SERVICES
    # --------------------------------------------------------

    try:

        loop.run_until_complete(
            run_services()
        )

    except KeyboardInterrupt:

        logger.info("🛑 Keyboard interrupt.")

    except asyncio.CancelledError:

        logger.info("🛑 Async tasks cancelled.")

    except Exception:

        logger.exception(
            "❌ TG-Power stopped because of an unexpected error."
        )

    finally:

        # ----------------------------------------------------
        # CANCEL REMAINING TASKS
        # ----------------------------------------------------

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
                "⚠️ Error while cleaning asyncio tasks."
            )

        # ----------------------------------------------------
        # CLOSE LOOP
        # ----------------------------------------------------

        try:

            loop.close()

        except Exception:

            logger.exception(
                "⚠️ Error while closing asyncio loop."
            )

        logger.info("")
        logger.info("========================================")
        logger.info("          TG-POWER STOPPED")
        logger.info("========================================")


# ============================================================
# EXECUTE
# ============================================================

if __name__ == "__main__":

    main()
