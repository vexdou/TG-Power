TG-Power restored/fixed build

Files intentionally included are the restored architecture plus the required
Premium/database compatibility fixes. No bot.py downloader architecture is used.

Main controller: main.py + main_bot.py (Pyrogram)
Managed downloader bots: bot_manager.py + managed_bot.py (python-telegram-bot)
Database: database.py (MongoDB)
Downloader: downloader.py (yt-dlp/ffmpeg)
Premium: premium.py

Main Admin: 50 controls across 5 pages.
Managed Bot Owner Admin: 10 controls.
Premium custom buttons: up to 10 per Premium bot.

Required Render environment variables are listed in .env.example.
