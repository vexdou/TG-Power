# TG-Power — Managed Telegram Downloader Bots

A MongoDB-backed Telegram platform with:

- Main management bot
- Managed downloader bots
- Owner admin panels
- Statistics
- Force Join
- Broadcasts
- Multi-bot runner
- yt-dlp + FFmpeg downloader
- Render/Docker deployment

## Important: bot creation

Telegram's normal Bot API does **not** expose a `createBot()` endpoint. This project therefore uses a private Telegram user session (`USER_SESSION`) to automate the official BotFather conversation.

Keep `USER_SESSION` secret. Never place it in source code or expose it to bot owners.

## Environment

Copy `.env.example` values into Render environment variables.

Required:

- BOT_TOKEN
- API_ID
- API_HASH
- USER_SESSION
- MONGO_URI
- ADMIN_IDS

## MongoDB

MongoDB Atlas is suitable. The application creates its indexes automatically at startup.

## Render

Deploy this repository as a Docker web service.

The service exposes:

- `/`
- `/health`

The bot process and Flask health server run together.

## Usage

1. Start Main Bot with `/start`.
2. Grant a user bot-creation access from the database/admin workflow if needed.
3. Use **Create New Bot**.
4. Enter:
   `My Downloader | MyDownloaderBot`
5. The system automates BotFather, stores the bot token privately in MongoDB, and starts the managed bot.
6. Open the managed bot and send `/admin` as its owner.

## Channel Force Join

The managed bot must be an administrator in required channels so it can verify membership.

## Notes

The platform should be treated as a real multi-bot service: monitor Render logs, MongoDB usage, Telegram limits, and downloader resource usage.
