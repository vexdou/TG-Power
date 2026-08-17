import asyncio
import os
import threading
from flask import Flask, jsonify
from main_bot import main_app, startup
from bot_manager import init_all_bots

web_app = Flask(__name__)

@web_app.get("/")
def home():
    return jsonify({"ok": True, "service": "TG-Power", "status": "online"})

@web_app.get("/health")
def health():
    return jsonify({"ok": True})

async def run_services():
    await startup()
    await init_all_bots()
    await main_app.start()
    print("🟢 Main Bot is running.")
    await asyncio.Event().wait()

def run_flask():
    port = int(os.getenv("PORT", "10000"))
    web_app.run(host="0.0.0.0", port=port, threaded=True)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(run_services())
