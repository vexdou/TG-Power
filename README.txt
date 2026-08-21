TG-Power fixes
================

Replace these two files in GitHub:
- downloader.py
- managed_bot.py

Do NOT replace database.py or main.py with older versions.

Changes:
- Video has only MUSIC button.
- MP3 has only CHANNEL button.
- No extra "Downloading..." / "MP3 ready" message.
- Uses Telegram UPLOAD_VIDEO / UPLOAD_AUDIO chat actions.
- Removes Markdown parsing from media captions/errors, preventing "Can't parse entities".
- YouTube Shorts/videos are limited to 10 minutes.
- YouTube downloader no longer forces the old android_vr/web/ios client combination; it tries tv/web_embedded/android_vr and optional cookies/PO token.
- Pinterest redirects are expanded.
- Download statistics remain compatible with current database.py.

YouTube note:
YouTube's current anti-bot/PO-token system can still block a Render IP. The code adds multiple fallbacks and optional environment variables:
YOUTUBE_COOKIES_FILE
YOUTUBE_PO_TOKEN

If YouTube still blocks the Render IP, a PO-token provider or valid cookies may be required; this is an upstream YouTube restriction, not a Telegram parsing bug.
