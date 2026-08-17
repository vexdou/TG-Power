import os
import asyncio
import re
from pyrogram import Client

API_ID = int(os.environ.get("API_ID", 123456))
API_HASH = os.environ.get("API_HASH", "")
USER_SESSION = os.environ.get("USER_SESSION", "")

async def create_bot_via_botfather(bot_name: str, bot_username: str):
    # Dhisida Client cusub oo in-memory ah
    user_bot = Client(
        "user_bot_session",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=USER_SESSION,
        in_memory=True
    )

    try:
        # Hubi haddii uusan mar hore xiriirsanayn
        if not user_bot.is_connected:
            await user_bot.start()

        # 1. U dir /newbot BotFather
        await user_bot.send_message("BotFather", "/newbot")
        await asyncio.sleep(1.5)

        # 2. U dir Magaca Bot-ka
        await user_bot.send_message("BotFather", bot_name)
        await asyncio.sleep(1.5)

        # 3. U dir Username-ka Bot-ka
        await user_bot.send_message("BotFather", bot_username)
        await asyncio.sleep(2)

        # 4. Ka noqoshada iyo akhri fariinta ugu dambeysay ee BotFather
        async for message in user_bot.get_chat_history("BotFather", limit=1):
            text = message.text or ""
            
            # Haddii token-kii la helay
            if "Use this token" in text or "API token" in text:
                match = re.search(r"(\d+:[A-Za-z0-9_-]+)", text)
                if match:
                    token = match.group(1)
                    return token, bot_username
                else:
                    raise Exception("BotFather wuxuu soo diray fariin aan Token lahayn!")
            
            elif "Sorry, this username is taken" in text:
                raise Exception("Username-kan waa lagu daahaday (Taken), mid kale dooro!")
            elif "Sorry, too many bots" in text:
                raise Exception("Akoonkaaga BotFather wuxuu gaaray xadkii ugu sareeyay ee bot-yada!")
            else:
                raise Exception(f"BotFather Error: {text[:50]}...")

    finally:
        # Marka ay shaqadu dhammato si nadiif ah u xir xiriirka
        if user_bot.is_connected:
            await user_bot.stop()
