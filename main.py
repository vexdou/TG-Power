import asyncio
import threading
from flask import Flask
import config
from database import init_db
from bot_manager import init_all_bots
from main_bot import main_app

web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Main SaaS Downloader Platform is Live 24/7!"

def run_web():
    web_app.run(host="0.0.0.0", port=config.PORT)

async def main():
    # 1. Start Web Server
    threading.Thread(target=run_web, daemon=True).start()
    
    # 2. Init DB
    await init_db()
    
    # 3. Start Main Bot
    await main_app.start()
    print("👑 Main SaaS Bot Online!")
    
    # 4. Load all created bots
    await init_all_bots()
    
    # Keep Running
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
