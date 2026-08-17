import os
import asyncio
import threading
from flask import Flask, request, jsonify, render_template_string
from main_bot import main_app

web_app = Flask(__name__)

HTML_FORM = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Create Bot</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #17212b;
            color: #ffffff;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 16px;
        }
        .container {
            width: 100%;
            max-width: 400px;
            background-color: #242f3d;
            border-radius: 14px;
            padding: 24px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        }
        h2 { font-size: 20px; text-align: center; margin-bottom: 20px; color: #64b5f6; }
        .form-group { margin-bottom: 16px; }
        label { display: block; font-size: 13px; color: #7f91a4; margin-bottom: 6px; }
        input {
            width: 100%; padding: 12px; border-radius: 8px; border: 1px solid #0e1621;
            background-color: #0e1621; color: #fff; font-size: 15px; outline: none;
        }
        .btn {
            width: 100%; padding: 14px; margin-top: 10px; background-color: #2481cc;
            border: none; border-radius: 8px; color: #fff; font-size: 16px; font-weight: bold; cursor: pointer;
        }
        .error { color: #e53935; font-size: 13px; margin-top: 10px; text-align: center; display: none; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Create Bot</h2>
        <div class="form-group">
            <label>Bot Name</label>
            <input type="text" id="bot_name" placeholder="My New Bot" autocomplete="off">
        </div>
        <div class="form-group">
            <label>Bot Username</label>
            <input type="text" id="bot_username" placeholder="MyNew_Bot" autocomplete="off">
        </div>
        <div id="err_msg" class="error"></div>
        <button class="btn" id="submit_btn" onclick="submitBot()">Create Bot</button>
    </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();

        async function submitBot() {
            const bot_name = document.getElementById('bot_name').value.trim();
            const bot_username = document.getElementById('bot_username').value.trim();
            const errDiv = document.getElementById('err_msg');
            const submitBtn = document.getElementById('submit_btn');
            const user_id = tg.initDataUnsafe?.user?.id;

            errDiv.style.display = "none";

            if (!bot_name || !bot_username) {
                errDiv.innerText = "Fadlan dhammaan sanduuqyada buuxi!";
                errDiv.style.display = "block";
                return;
            }

            submitBtn.disabled = true;
            submitBtn.innerText = "Creating Bot...";

            try {
                const response = await fetch('/api/create-bot-app', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id, bot_name, bot_username })
                });

                const data = await response.json();

                if (data.ok) {
                    tg.close();
                } else {
                    errDiv.innerText = data.error || "Cillad ayaa dhacday!";
                    errDiv.style.display = "block";
                    submitBtn.disabled = false;
                    submitBtn.innerText = "Create Bot";
                }
            } catch (e) {
                errDiv.innerText = "Server Connection Error!";
                errDiv.style.display = "block";
                submitBtn.disabled = false;
                submitBtn.innerText = "Create Bot";
            }
        }
    </script>
</body>
</html>
"""

async def process_creation(user_id, bot_name, bot_username):
    from bot_creator import create_bot_via_botfather
    from database import register_bot
    from bot_manager import start_managed_bot

    token, final_username = await create_bot_via_botfather(bot_name, bot_username)
    await register_bot(user_id, token, bot_name, final_username)
    await start_managed_bot(token, final_username, user_id)
    return final_username

@web_app.route('/')
def home():
    return "SaaS Web Service & Telegram Bot Server are live!"

@web_app.route('/create-app')
def create_app_page():
    return render_template_string(HTML_FORM)

@web_app.route('/api/create-bot-app', methods=['POST'])
def api_create_bot():
    data = request.json or {}
    user_id = data.get("user_id")
    bot_name = data.get("bot_name")
    bot_username = data.get("bot_username", "").replace("@", "").strip()

    if not user_id or not bot_name or not bot_username:
        return jsonify({"ok": False, "error": "Xogta la soo diray waa kuwo aan dhameystirnayn!"})

    try:
        # Shaqada toos waxaa looga dhex kicinayaa Main Bot Event Loop-kiisa
        future = asyncio.run_coroutine_threadsafe(
            process_creation(user_id, bot_name, bot_username),
            main_app.loop
        )
        final_username = future.result(timeout=45)
        return jsonify({"ok": True, "username": final_username})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("🚀 Starting Main SaaS Bot and Web App Server...")
    main_app.run()
