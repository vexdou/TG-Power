# TG-Power Fixed Package

This package is centered on `bot.py`, which contains the main manager bot, Telegram Managed Bot creation flow, managed downloader workers, MongoDB persistence, admin controls, and premium owner controls.

## Required environment variables

- `BOT_TOKEN` — Main TG-Power bot token
- `MONGO_URI` — MongoDB connection string
- `OWNER_ID` — Main owner Telegram ID
- `ADMIN_IDS` — Optional comma-separated admin IDs
- `BOT2_TOKEN` — Optional verification bot token
- `API_ID` / `API_HASH` — only needed by legacy components; safe to provide when available
- `PREMIUM_PRICE_STARS` — Premium price in Telegram Stars (default 250)
- `MAX_YOUTUBE_DURATION` — YouTube duration in seconds (default 600)
- `MAX_CONCURRENT_DOWNLOADS` — concurrent download workers (default 20)
- `MAX_BOTS_PER_USER` — managed bots per owner (default 5)

## Run

```bash
pip install -r requirements.txt
python bot.py
```

For Render, use the included `Procfile` or Dockerfile.

## Admin

The admin menu contains the existing controls plus extended database, health, capacity, cleanup, export, platform, force-join, reload, and premium-center controls.

## Managed Bot Premium

Each managed bot owner gets a 10-button Premium section:

1. Premium Status
2. Buy Premium
3. Grant Premium
4. Premium Days
5. Premium Caption
6. Premium Buttons
7. Premium Ads
8. Premium Stats
9. Premium Users
10. Premium Settings

Telegram Stars payments activate 30 days of Premium after successful payment.
