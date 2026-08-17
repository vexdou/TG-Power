import os
import asyncio
import re
from pyrogram import Client

API_ID = int(os.environ.get("API_ID", 123456))
API_HASH = os.environ.get("API_HASH", "")
USER_SESSION = os.environ.get("USER_SESSION", "")

async def create_bot_via_botfather(bot_name: str, bot_username: str):
    # Async context manager-ku si nadiif ah ayuu Client-ka ugu dhex kiciyaa loop-ka socda
    async with Client(
        "user_bot_session",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=USER_SESSION,
        in_memory=True
    ) as user_bot:

        # 1. U dir /newbot BotFather
        await user_bot.send_message("BotFather", "/newbot")
        await asyncio.sleep(1.5)

        # 2. U dir Magaca Bot-ka
        await user_bot.send_message("BotFather", bot_name)
        await asyncio.sleep(1.5)

        # 3. U dir Username-ka Bot-ka
        await user_bot.send_message("BotFather", bot_username)
        await asyncio.sleep(2)

        # 4. Akhri fariinta ugu dambeysay ee BotFather
        async for message in user_bot.get_chat_history("BotFather", limit=1):
            text = message.text or ""
            
            if "Use this token" in text or "API token" in text:
                match = re.search(r"(\d+:[A-Za-z0-9_-]+)", text)
                if match:
                    return match.group(1), bot_username
                else:
                    raise Exception("BotFather wuxuu soo diray fariin aan Token lahayn!")
            
            elif "Sorry, this username is taken" in text:
                raise Exception("Username-kan waa lagu daahaday (Taken), mid kale dooro!")
            elif "Sorry, too many bots" in text:
                raise Exception("Akoonkaaga BotFather wuxuu gaaray xadkii ugu sareeyay!")
            else:
                raise Exception(f"BotFather Error: {text[:60]}")
