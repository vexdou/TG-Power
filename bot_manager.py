from pyrogram import Client
import config
from database import get_all_active_bots
from managed_bot import build_managed_bot_handlers

active_bots = {}

async def start_managed_bot(token: str, bot_username: str, owner_id: int):
    try:
        app = Client(
            name=f"bot_{bot_username}",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=token,
            in_memory=True
        )
        build_managed_bot_handlers(app, bot_username, owner_id)
        await app.start()
        active_bots[bot_username] = app
        print(f"🟢 Started Managed Bot: @{bot_username}")
        return True
    except Exception as e:
        print(f"🔴 Error starting @{bot_username}: {e}")
        return False

async def init_all_bots():
    bots = await get_all_active_bots()
    for b in bots:
        await start_managed_bot(b['token'], b['username'], b['owner_id'])
