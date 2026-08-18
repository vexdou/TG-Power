import asyncio
import logging
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yt_dlp

logger = logging.getLogger(__name__)

executor = ThreadPoolExecutor(max_workers=10)


class MediaDownloader:
    def __init__(self, download_dir: str = "downloads"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self.processing = set()
        self.lock = asyncio.Lock()

    def extract_platform(self, url: str) -> str:
        patterns = {
            "youtube": r"(youtube\.com|youtu\.be)",
            "tiktok": r"(tiktok\.com)",
            "instagram": r"(instagram\.com)",
            "twitter": r"(twitter\.com|x\.com)",
            "facebook": r"(facebook\.com|fb\.watch)",
            "pinterest": r"(pinterest\.com|pin\.it)",
            "snapchat": r"(snapchat\.com)",
        }

        for platform, pattern in patterns.items():
            if re.search(pattern, url, re.IGNORECASE):
                return platform

        return "general"

    async def download(
        self,
        url: str,
        user_id: int,
        bot_id: int | None = None,
    ) -> dict:
        url = url.strip()

        platform = self.extract_platform(url)
        request_key = f"{bot_id}:{user_id}:{url}"

        async with self.lock:
            if request_key in self.processing:
                return {
                    "success": False,
                    "error": "This download is already in progress.",
                }

            self.processing.add(request_key)

        try:
            bot_folder = str(
                self.download_dir / str(bot_id or "main")
            )
            Path(bot_folder).mkdir(parents=True, exist_ok=True)

            out_template = os.path.join(
                bot_folder,
                f"{user_id}_%(id)s.%(ext)s",
            )

            ydl_opts = {
                "outtmpl": out_template,
                "noplaylist": True,

                # Keep Telegram Bot API upload size in mind.
                "max_filesize": 49 * 1024 * 1024,

                # Prefer a single MP4 file when available.
                "format": (
                    "best[ext=mp4][filesize<49M]/"
                    "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
                    "best[filesize<49M]/best"
                ),

                "merge_output_format": "mp4",

                "quiet": True,
                "no_warnings": True,

                "http_headers": {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 "
                        "(KHTML, like Gecko) "
                        "Chrome/120.0 Safari/537.36"
                    )
                },

                # Avoid certificate problems on restricted hosts.
                "nocheckcertificate": True,

                # Make downloads more reliable.
                "retries": 3,
                "fragment_retries": 3,
                "socket_timeout": 30,
            }

            # YouTube extractor options.
            ydl_opts["extractor_args"] = {
                "youtube": {
                    "player_client": ["android", "web"]
                }
            }

            loop = asyncio.get_running_loop()

            result = await loop.run_in_executor(
                executor,
                lambda: self._exec_dlp(ydl_opts, url),
            )

            file_path = result["file_path"]

            if not os.path.exists(file_path):
                raise FileNotFoundError(
                    "yt-dlp finished but the output file was not found."
                )

            size = os.path.getsize(file_path)

            if size > 49 * 1024 * 1024:
                self.cleanup(file_path)
                raise ValueError(
                    "Downloaded media is larger than Telegram's "
                    "bot upload limit."
                )

            return {
                "success": True,
                "file_path": file_path,
                "title": result.get(
                    "title", "Downloaded Media"
                ),
                "platform": platform,
                "media_type": result.get(
                    "media_type", "video"
                ),
            }

        except Exception as exc:
            logger.exception(
                "Download error [%s]: %s",
                platform,
                exc,
            )
            return {
                "success": False,
                "error": str(exc),
            }

        finally:
            async with self.lock:
                self.processing.discard(request_key)

    def _exec_dlp(self, opts: dict, url: str) -> dict:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(
                url,
                download=True,
            )

            if info.get("entries"):
                entries = [
                    entry for entry in info["entries"]
                    if entry
                ]
                if entries:
                    info = entries[0]

            filename = ydl.prepare_filename(info)

            # Merging video+audio normally changes the extension.
            if not os.path.exists(filename):
                base, _ = os.path.splitext(filename)

                candidates = [
                    ".mp4",
                    ".mkv",
                    ".webm",
                    ".m4a",
                    ".mp3",
                    ".opus",
                ]

                for ext in candidates:
                    candidate = base + ext
                    if os.path.exists(candidate):
                        filename = candidate
                        break

            # Search by video id if the prepared filename was changed.
            if not os.path.exists(filename):
                media_id = str(info.get("id", ""))

                if media_id:
                    parent = Path(filename).parent

                    matches = list(
                        parent.glob(
                            f"*{media_id}*"
                        )
                    )

                    if matches:
                        filename = str(
                            max(
                                matches,
                                key=lambda p: p.stat().st_mtime,
                            )
                        )

            if not os.path.exists(filename):
                raise FileNotFoundError(
                    "Downloaded file could not be located."
                )

            media_type = (
                "audio"
                if info.get("vcodec") == "none"
                else "video"
            )

            return {
                "file_path": filename,
                "title": info.get(
                    "title",
                    "Media",
                ),
                "media_type": media_type,
            }

    def cleanup(self, file_path: str):
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            logger.exception(
                "Could not remove downloaded file: %s",
                file_path,
            )


downloader = MediaDownloader()
