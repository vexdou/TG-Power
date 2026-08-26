import asyncio
import re
from pyrogram import Client
import config

TOKEN_RE = re.compile(r"(\d+:[A-Za-z0-9_-]{20,})")

async def create_bot_via_botfather(bot_name: str, bot_username: str):
    if not config.ENABLE_BOTFATHER_AUTOMATION:
        raise RuntimeError("BotFather automation is disabled.")
    if not config.USER_SESSION:
        raise RuntimeError("USER_SESSION is required for automatic bot creation.")
    bot_name = bot_name.strip()
    bot_username = bot_username.strip().lstrip("@")
    if not bot_name or len(bot_name) > 64:
        raise ValueError("Bot name must be between 1 and 64 characters.")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{3,30}bot", bot_username, re.I):
        raise ValueError("Bot username must end with 'bot'.")
    app = Client("bot_creator_session", api_id=config.API_ID, api_hash=config.API_HASH,
                 session_string=config.USER_SESSION, in_memory=True, no_updates=True)
    await app.start()
    try:
        await app.send_message("BotFather", "/newbot")
        await asyncio.sleep(1.2)
        await app.send_message("BotFather", bot_name)
        await asyncio.sleep(1.2)
        await app.send_message("BotFather", bot_username)
        await asyncio.sleep(2.0)
        last = ""
        async for item in app.get_chat_history("BotFather", limit=5):
            last = item.text or ""
            match = TOKEN_RE.search(last)
            if match:
                return match.group(1), bot_username
            low = last.lower()
            if "too many bots" in low:
                raise RuntimeError("BotFather says this account has reached its bot limit.")
            if "taken" in low:
                raise RuntimeError("That bot username is already taken.")
        raise RuntimeError(f"BotFather did not return a token. Last response: {last[:300]}")
    finally:
        await app.stop()
