import re
import asyncio
from telethon import TelegramClient
from config import Config

class BotFatherCreator:
    def __init__(self):
        self.session_name = Config.BOTFATHER_SESSION
        self.api_id = Config.API_ID
        self.api_hash = Config.API_HASH

    async def create_new_bot(self, bot_name: str, bot_username: str) -> dict:
        """
        Wuxuu si toos ah uga dhalayaa BotFather bot cusub wuxuna soo celinayaa Token-ka iyo Bot ID-ga.
        """
        async with TelegramClient(self.session_name, self.api_id, self.api_hash) as client:
            # U bilaw xiriirka BotFather
            async with client.conversation("@BotFather", timeout=30) as conv:
                await conv.send_message("/newbot")
                response = await conv.get_response()

                if "Choose a name" not in response.text and "Alright" not in response.text:
                    await conv.send_message("/cancel")
                    return {"success": False, "error": f"BotFather Response Error: {response.text}"}

                # Dir magaca Bot-ka
                await conv.send_message(bot_name)
                response = await conv.get_response()

                if "Good" not in response.text and "Choose a username" not in response.text:
                    await conv.send_message("/cancel")
                    return {"success": False, "error": f"Invalid Name: {response.text}"}

                # Dir username-ka Bot-ka (waa in uu ku dhamaadaa 'bot')
                if not bot_username.lower().endswith("bot"):
                    bot_username += "_bot"

                await conv.send_message(bot_username)
                response = await conv.get_response()

                if "Done!" in response.text or "Use this token" in response.text:
                    # Ka soo saar Token-ka fariinta
                    match = re.search(r"(\d+:[A-Za-z0-9_-]+)", response.text)
                    if match:
                        token = match.group(1)
                        bot_id = int(token.split(":")[0])
                        return {
                            "success": True,
                            "bot_id": bot_id,
                            "token": token,
                            "username": bot_username,
                            "name": bot_name
                        }
                
                await conv.send_message("/cancel")
                return {"success": False, "error": f"Creation Failed: {response.text}"}

bot_creator = BotFatherCreator()
