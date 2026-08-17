import re
import asyncio
from pyrogram import Client
import config

creator_app = None

if config.USER_SESSION:
    creator_app = Client("bot_creator_session", api_id=config.API_ID, api_hash=config.API_HASH, session_string=config.USER_SESSION)

async def create_bot_via_botfather(bot_name: str, bot_username: str):
    """
    Userbot-kani wuxuu si toos ah fariin u siinayaa @BotFather
    si uu bot cusub ugu dhasho oo uu token-ka u soo nala soo saaro.
    """
    if not creator_app:
        raise Exception("USER_SESSION is not configured in Environment Variables.")

    async with creator_app:
        # Send /newbot to BotFather
        await creator_app.send_message("BotFather", "/newbot")
        await asyncio.sleep(1.5)

        # Send Bot Display Name
        await creator_app.send_message("BotFather", bot_name)
        await asyncio.sleep(1.5)

        # Send Bot Username (must end in 'bot')
        if not bot_username.lower().endswith("bot"):
            bot_username += "_bot"

        await creator_app.send_message("BotFather", bot_username)
        await asyncio.sleep(2.5)

        # Get latest message from BotFather
        async for msg in creator_app.get_chat_history("BotFather", limit=1):
            text = msg.text or ""
            # Extract API Token via Regex
            match = re.search(r"(\d+:[A-Za-z0-9_-]{35})", text)
            if match:
                token = match.group(1)
                return token, bot_username
            else:
                if "sorry" in text.lower() or "taken" in text.lower():
                    raise Exception("Username-kan waa mid hore loo qaatay ama waa maadi. Isku day kan kale.")
                raise Exception(f"BotFather Error: {text}")

    raise Exception("Fashil ayaa ka dhacay sameynta bot-ka.")
