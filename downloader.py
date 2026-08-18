import os
import asyncio
import re
import logging
import requests
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import yt_dlp
from config import Config

logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=10)


class MediaDownloader:
    def __init__(self):
        self.download_dir = Path(Config.DOWNLOAD_DIR)
        self.download_dir.mkdir(exist_ok=True)
        self.processing_urls = set()
        self.lock = asyncio.Lock()

    def extract_platform(self, url: str) -> str:
        patterns = {
            "youtube": r"(youtube\.com|youtu\.be)",
            "tiktok": r"(tiktok\.com)",
            "instagram": r"(instagram\.com)",
            "twitter": r"(twitter\.com|x\.com)",
            "facebook": r"(facebook\.com|fb\.watch)",
            "pinterest": r"(pinterest\.com|pin\.it)",
            "snapchat": r"(snapchat\.com)"
        }

        for platform, pattern in patterns.items():
            if re.search(pattern, url, re.IGNORECASE):
                return platform

        return "general"

    def expand_url(self, url: str) -> str:
        try:
            if "pin.it" in url or "youtu.be" in url:
                response = requests.head(
                    url,
                    allow_redirects=True,
                    timeout=10,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/122.0.0.0 Safari/537.36"
                        )
                    }
                )

                if response.url:
                    return response.url

        except Exception as e:
            logger.warning(f"URL expansion failed: {e}")

        return url

    # ------------------ VIDEO DOWNLOAD ------------------

    async def download(self, url: str, user_id: int) -> dict:

        async with self.lock:
            if url in self.processing_urls:
                return {
                    "success": False,
                    "error": "Soo dejinta link-gan waa ay socotaa. Fadlan int yar sug."
                }

            self.processing_urls.add(url)

        try:
            loop = asyncio.get_running_loop()

            real_url = await loop.run_in_executor(
                executor,
                lambda: self.expand_url(url)
            )

            platform = self.extract_platform(real_url)

            out_template = str(
                self.download_dir /
                f"{user_id}_%(id)s.%(ext)s"
            )

            # =========================================================
            # COMMON OPTIONS
            # =========================================================

            ydl_opts = {
                "outtmpl": out_template,

                # Better compatibility for YouTube + Pinterest
                "format": (
                    "bestvideo*+bestaudio*/"
                    "bestvideo*/"
                    "best"
                ),

                "merge_output_format": "mp4",

                "quiet": True,
                "no_warnings": True,

                "max_filesize": (
                    Config.MAX_FILE_SIZE_MB * 1024 * 1024
                ),

                "user_agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),

                "http_headers": {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "en-US,en;q=0.9"
                },

                "nocheckcertificate": True,

                "retries": 3,
                "fragment_retries": 3,

                "socket_timeout": 30,

                "ignoreerrors": False,

                # Don't download playlists
                "noplaylist": True,

                # Keep filenames safe
                "restrictfilenames": True,
            }

            # =========================================================
            # YOUTUBE SETTINGS
            # =========================================================

            if platform == "youtube":

                ydl_opts["extractor_args"] = {
                    "youtube": {
                        "player_client": [
                            "android_vr",
                            "web",
                            "ios"
                        ]
                    }
                }

            # =========================================================
            # PINTEREST SETTINGS
            # =========================================================

            elif platform == "pinterest":

                # Pinterest frequently provides direct MP4 media URLs.
                # These options make yt-dlp prefer the best available
                # video without forcing a YouTube-only format.
                ydl_opts["format"] = (
                    "bestvideo*+bestaudio*/"
                    "bestvideo*/"
                    "best"
                )

                ydl_opts["merge_output_format"] = "mp4"

                ydl_opts["http_headers"] = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    "Referer": "https://www.pinterest.com/",
                    "Accept": (
                        "text/html,application/xhtml+xml,"
                        "application/xml;q=0.9,image/avif,"
                        "image/webp,*/*;q=0.8"
                    ),
                    "Accept-Language": "en-US,en;q=0.9"
                }

            # =========================================================
            # DOWNLOAD
            # =========================================================

            result = await loop.run_in_executor(
                executor,
                lambda: self._exec_dlp(
                    ydl_opts,
                    real_url
                )
            )

            return {
                "success": True,
                "file_path": result["file_path"],
                "title": result.get(
                    "title",
                    "Downloaded Media"
                ),
                "platform": platform,
                "media_type": result.get(
                    "media_type",
                    "video"
                )
            }

        except Exception as e:

            logger.error(
                f"Download Error [{url}]: {str(e)}",
                exc_info=True
            )

            return {
                "success": False,
                "error": str(e)
            }

        finally:

            async with self.lock:
                self.processing_urls.discard(url)

    # ================================================================
    # MUSIC / AUDIO / MP3
    # ================================================================

    async def download_audio(
        self,
        url: str,
        user_id: int
    ) -> dict:

        async with self.lock:

            if url in self.processing_urls:
                return {
                    "success": False,
                    "error": (
                        "Bedelida codku waa ay socotaa. "
                        "Fadlan int yar sug."
                    )
                }

            self.processing_urls.add(url)

        try:

            loop = asyncio.get_running_loop()

            real_url = await loop.run_in_executor(
                executor,
                lambda: self.expand_url(url)
            )

            platform = self.extract_platform(real_url)

            out_template = str(
                self.download_dir /
                f"audio_{user_id}_%(id)s.%(ext)s"
            )

            # =========================================================
            # MP3 SETTINGS
            # =========================================================

            ydl_opts = {
                "outtmpl": out_template,

                "format": "bestaudio/best",

                "quiet": True,
                "no_warnings": True,

                "max_filesize": (
                    Config.MAX_FILE_SIZE_MB * 1024 * 1024
                ),

                "user_agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),

                "http_headers": {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "en-US,en;q=0.9"
                },

                "nocheckcertificate": True,

                "retries": 3,
                "fragment_retries": 3,

                "socket_timeout": 30,

                "noplaylist": True,

                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192"
                    }
                ]
            }

            # YouTube audio compatibility
            if platform == "youtube":

                ydl_opts["extractor_args"] = {
                    "youtube": {
                        "player_client": [
                            "android_vr",
                            "web",
                            "ios"
                        ]
                    }
                }

            # Pinterest audio compatibility
            elif platform == "pinterest":

                ydl_opts["http_headers"] = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    "Referer": "https://www.pinterest.com/",
                    "Accept-Language": "en-US,en;q=0.9"
                }

            result = await loop.run_in_executor(
                executor,
                lambda: self._exec_dlp(
                    ydl_opts,
                    real_url
                )
            )

            return {
                "success": True,
                "file_path": result["file_path"],
                "title": result.get(
                    "title",
                    "Music Track"
                ),
                "platform": platform,
                "media_type": "audio"
            }

        except Exception as e:

            logger.error(
                f"Audio Download Error [{url}]: {str(e)}",
                exc_info=True
            )

            return {
                "success": False,
                "error": str(e)
            }

        finally:

            async with self.lock:
                self.processing_urls.discard(url)

    # ================================================================
    # YT-DLP EXECUTOR
    # ================================================================

    def _exec_dlp(
        self,
        opts: dict,
        url: str
    ) -> dict:

        with yt_dlp.YoutubeDL(opts) as ydl:

            info = ydl.extract_info(
                url,
                download=True
            )

            if not info:
                raise Exception(
                    "yt-dlp ma helin media-kan."
                )

            if "entries" in info:

                entries = info.get("entries")

                if entries:
                    info = entries[0]

            filename = ydl.prepare_filename(info)

            # =========================================================
            # FIND REAL DOWNLOADED FILE
            # =========================================================

            if not os.path.exists(filename):

                base, _ = os.path.splitext(filename)

                possible_extensions = [
                    ".mp4",
                    ".mkv",
                    ".webm",
                    ".m4a",
                    ".mp3",
                    ".ogg",
                    ".mov"
                ]

                for ext in possible_extensions:

                    candidate = base + ext

                    if os.path.exists(candidate):
                        filename = candidate
                        break

            # =========================================================
            # SEARCH BY ID IF MERGING CHANGED FILENAME
            # =========================================================

            if not os.path.exists(filename):

                media_id = info.get("id")

                if media_id:

                    candidates = list(
                        self.download_dir.glob(
                            f"*{media_id}*"
                        )
                    )

                    if candidates:

                        filename = str(
                            max(
                                candidates,
                                key=lambda p: p.stat().st_mtime
                            )
                        )

            if not os.path.exists(filename):

                raise FileNotFoundError(
                    "Media-ga waa la soo dejiyey laakiin "
                    "file-ka lama helin."
                )

            return {
                "file_path": filename,
                "title": info.get(
                    "title",
                    "Media"
                ),
                "media_type": (
                    "audio"
                    if info.get("vcodec") == "none"
                    or filename.lower().endswith(".mp3")
                    else "video"
                )
            }

    # ================================================================
    # CLEANUP
    # ================================================================

    def cleanup(self, file_path: str):

        try:

            if file_path and os.path.exists(file_path):
                os.remove(file_path)

        except Exception as e:

            logger.error(
                f"Cleanup error: {e}"
            )


downloader = MediaDownloader()
