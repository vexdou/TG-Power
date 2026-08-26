import asyncio
import base64
import logging
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
import yt_dlp

from config import Config

logger = logging.getLogger(__name__)

executor = ThreadPoolExecutor(max_workers=10)
premium_executor = ThreadPoolExecutor(max_workers=20)


class MediaDownloader:
    def __init__(self):
        self.download_dir = Path(Config.DOWNLOAD_DIR)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.processing_urls = set()
        self.lock = asyncio.Lock()

    def extract_platform(self, url: str) -> str:
        patterns = {
            "youtube": r"(youtube\.com|youtu\.be)",
            "tiktok": r"(tiktok\.com)",
            "instagram": r"(instagram\.com)",
            "twitter": r"(twitter\.com|x\.com)",
            "facebook": r"(facebook\.com|fb\.watch|fb\.com)",
            "pinterest": r"(pinterest\.com|pin\.it)",
            "snapchat": r"(snapchat\.com)",
        }

        for platform, pattern in patterns.items():
            if re.search(pattern, url, re.IGNORECASE):
                return platform

        return "general"

    def expand_url(self, url: str) -> str:
        if not any(x in url.lower() for x in ("pin.it", "youtu.be")):
            return url

        headers = {"User-Agent": self._user_agent()}

        try:
            response = requests.head(
                url,
                allow_redirects=True,
                timeout=10,
                headers=headers,
            )
            if response.url:
                return response.url
        except Exception:
            pass

        try:
            response = requests.get(
                url,
                allow_redirects=True,
                timeout=10,
                headers=headers,
                stream=True,
            )
            return response.url or url
        except Exception as exc:
            logger.warning("URL expansion failed: %s", exc)
            return url

    @staticmethod
    def _user_agent() -> str:
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/136.0.0.0 Safari/537.36"
        )

    def _base_opts(self, out_template: str, platform: str = "general") -> dict:
        opts = {
            "outtmpl": out_template,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": platform == "youtube",
            "restrictfilenames": True,
            "retries": 5,
            "fragment_retries": 5,
            "file_access_retries": 3,
            "socket_timeout": 30,
            "nocheckcertificate": True,
            "max_filesize": Config.MAX_FILE_SIZE_MB * 1024 * 1024,
            "user_agent": self._user_agent(),
            "http_headers": {
                "User-Agent": self._user_agent(),
                "Accept-Language": "en-US,en;q=0.9",
            },
            "concurrent_fragment_downloads": 4,
            "continuedl": True,
            "overwrites": True,
        }

        # TikTok photo/slideshow posts must be treated as a playlist of
        # individual image entries. They must NOT be merged into MP4.
        if platform == "tiktok":
            opts["noplaylist"] = False
            opts["format"] = "best"

        # FFmpeg is used for YouTube/video streams only.
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            opts["ffmpeg_location"] = ffmpeg_path

        # Modern yt-dlp YouTube extraction can use Deno + EJS.
        deno_path = shutil.which("deno")
        if deno_path:
            opts["js_runtimes"] = {"deno": {"path": deno_path}}
            opts["remote_components"] = ["ejs:github"]

        return opts

    def _youtube_common(self, opts: dict) -> dict:
        result = dict(opts)

        cookie_file = os.getenv("YOUTUBE_COOKIES_FILE", "").strip()
        if cookie_file and os.path.isfile(cookie_file):
            result["cookiefile"] = cookie_file

        cookie_b64 = os.getenv("YOUTUBE_COOKIES_BASE64", "").strip()
        if cookie_b64 and "cookiefile" not in result:
            try:
                cookie_path = self.download_dir / ".youtube_cookies.txt"
                cookie_path.write_bytes(base64.b64decode(cookie_b64, validate=True))
                result["cookiefile"] = str(cookie_path)
            except Exception:
                logger.warning("Invalid YOUTUBE_COOKIES_BASE64")

        po_token = os.getenv("YOUTUBE_PO_TOKEN", "").strip()
        if po_token:
            args = dict(result.get("extractor_args", {}))
            youtube_args = dict(args.get("youtube", {}))
            youtube_args["po_token"] = [f"mweb.gvs+{po_token}"]
            args["youtube"] = youtube_args
            result["extractor_args"] = args

        return result

    def _youtube_variants(self, opts: dict) -> list[dict]:
        common = self._youtube_common(opts)
        variants = []

        # If a PO token exists, try the matching mweb client first.
        if os.getenv("YOUTUBE_PO_TOKEN", "").strip():
            candidate = dict(common)
            args = dict(candidate.get("extractor_args", {}))
            youtube_args = dict(args.get("youtube", {}))
            youtube_args["player_client"] = ["mweb"]
            args["youtube"] = youtube_args
            candidate["extractor_args"] = args
            variants.append(candidate)

        # Different YouTube clients behave differently on cloud IPs.
        for client in (
            "tv",
            "web_embedded",
            "android_vr",
            "ios",
            "mweb",
            "web_creator",
        ):
            candidate = dict(common)
            args = dict(candidate.get("extractor_args", {}))
            youtube_args = dict(args.get("youtube", {}))
            youtube_args["player_client"] = [client]
            args["youtube"] = youtube_args
            candidate["extractor_args"] = args
            variants.append(candidate)

        # Final attempt: let yt-dlp choose its normal client configuration.
        variants.append(dict(common))

        return variants

    def _variants(self, opts: dict, platform: str) -> list[dict]:
        if platform == "youtube":
            return self._youtube_variants(opts)

        variants = [dict(opts)]

        if platform == "pinterest":
            candidate = dict(opts)
            candidate["http_headers"] = {
                "User-Agent": self._user_agent(),
                "Referer": "https://www.pinterest.com/",
                "Accept-Language": "en-US,en;q=0.9",
            }
            variants.insert(0, candidate)

        return variants

    async def download(
        self,
        url: str,
        user_id: int,
        premium: bool = False,
    ) -> dict:
        async with self.lock:
            if url in self.processing_urls:
                return {
                    "success": False,
                    "error": "This link is already being downloaded.",
                }
            self.processing_urls.add(url)

        try:
            loop = asyncio.get_running_loop()
            pool = premium_executor if premium else executor

            real_url = await loop.run_in_executor(
                pool,
                lambda: self.expand_url(url),
            )

            platform = self.extract_platform(real_url)

            out_template = str(
                self.download_dir
                / f"{user_id}_%(id)s_%(playlist_index)02d.%(ext)s"
            )

            base = self._base_opts(
                out_template,
                platform=platform,
            )

            # Platform-specific format selection.
            if platform == "tiktok":
                # Important: "best" allows JPG/PNG/WebP image entries.
                # Do not force video+audio merging on TikTok slideshows.
                base["format"] = "best"
                base.pop("merge_output_format", None)
            else:
                base["format"] = "bv*+ba/b"
                base["merge_output_format"] = "mp4"

            if platform == "youtube":
                base["match_filter"] = self._youtube_duration_filter

            result = await self._try_download(
                loop,
                base,
                real_url,
                platform,
                premium=premium,
            )

            return {
                "success": True,
                "file_path": result["file_paths"][0],
                "file_paths": result["file_paths"],
                "title": result.get("title", "Downloaded Media"),
                "platform": platform,
                "media_type": result.get("media_type", "video"),
            }

        except Exception as exc:
            logger.error(
                "Download error [%s]: %s",
                url,
                exc,
                exc_info=True,
            )
            return {
                "success": False,
                "error": self._clean_error(str(exc)),
            }

        finally:
            async with self.lock:
                self.processing_urls.discard(url)

    async def download_audio(
        self,
        url: str,
        user_id: int,
        premium: bool = False,
    ) -> dict:
        async with self.lock:
            if url in self.processing_urls:
                return {
                    "success": False,
                    "error": "Audio conversion is already running.",
                }
            self.processing_urls.add(url)

        try:
            loop = asyncio.get_running_loop()
            pool = premium_executor if premium else executor

            real_url = await loop.run_in_executor(
                pool,
                lambda: self.expand_url(url),
            )

            platform = self.extract_platform(real_url)

            out_template = str(
                self.download_dir
                / f"audio_{user_id}_%(id)s.%(ext)s"
            )

            base = self._base_opts(
                out_template,
                platform=platform,
            )

            base.update(
                {
                    "format": "bestaudio/best",
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }
                    ],
                }
            )

            if platform == "youtube":
                base["match_filter"] = self._youtube_duration_filter

            result = await self._try_download(
                loop,
                base,
                real_url,
                platform,
                premium=premium,
            )

            return {
                "success": True,
                "file_path": result["file_paths"][0],
                "file_paths": result["file_paths"],
                "title": result.get("title", "Music"),
                "platform": platform,
                "media_type": "audio",
            }

        except Exception as exc:
            logger.error(
                "Audio download error [%s]: %s",
                url,
                exc,
                exc_info=True,
            )
            return {
                "success": False,
                "error": self._clean_error(str(exc)),
            }

        finally:
            async with self.lock:
                self.processing_urls.discard(url)

    async def _try_download(
        self,
        loop,
        base_opts,
        url,
        platform,
        premium=False,
    ):
        errors = []
        pool = premium_executor if premium else executor

        for opts in self._variants(base_opts, platform):
            try:
                return await loop.run_in_executor(
                    pool,
                    lambda o=opts: self._exec_dlp(o, url),
                )
            except Exception as exc:
                errors.append(str(exc))
                logger.warning(
                    "yt-dlp attempt failed for %s: %s",
                    platform,
                    exc,
                )

        last = (
            errors[-1]
            if errors
            else "yt-dlp could not download the media."
        )

        if platform == "youtube" and (
            "Sign in to confirm" in last
            or "not a bot" in last
            or "HTTP Error 403" in last
            or "HTTP Error 429" in last
            or "Please sign in" in last
        ):
            raise RuntimeError(
                "YouTube is blocking this cloud IP or requires "
                "additional authentication. "
                "Add a valid YOUTUBE_COOKIES_BASE64 or "
                "YOUTUBE_PO_TOKEN to the deployment environment."
            )

        raise RuntimeError(self._clean_error(last))

    @staticmethod
    def _youtube_duration_filter(info_dict, *, incomplete):
        duration = info_dict.get("duration")

        if (
            duration is not None
            and duration > Config.MAX_VIDEO_DURATION_SECONDS
        ):
            minutes, seconds = divmod(
                Config.MAX_VIDEO_DURATION_SECONDS,
                60,
            )
            return (
                "YouTube videos longer than "
                f"{minutes}:{seconds:02d} are not supported."
            )

        return None

    def _exec_dlp(self, opts: dict, url: str) -> dict:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(
                url,
                download=True,
            )

            if not info:
                raise RuntimeError(
                    "yt-dlp did not return media information."
                )

            if "entries" in info:
                entries = [
                    entry
                    for entry in (info.get("entries") or [])
                    if entry
                ]
            else:
                entries = [info]

            if not entries:
                raise RuntimeError("No media was found.")

            file_paths = []
            media_types = []

            title = (
                info.get("title")
                or entries[0].get("title")
                or "Media"
            )

            for entry in entries:
                filename = ydl.prepare_filename(entry)

                if not os.path.exists(filename):
                    base, _ = os.path.splitext(filename)

                    for ext in (
                        ".jpg",
                        ".jpeg",
                        ".png",
                        ".webp",
                        ".gif",
                        ".mp4",
                        ".mkv",
                        ".webm",
                        ".mov",
                        ".m4v",
                        ".mp3",
                        ".m4a",
                        ".ogg",
                        ".wav",
                    ):
                        candidate = base + ext
                        if os.path.exists(candidate):
                            filename = candidate
                            break

                if not os.path.exists(filename):
                    media_id = entry.get("id")

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
                                    key=lambda p: p.stat().st_mtime,
                                )
                            )

                if not os.path.exists(filename):
                    continue

                lower = filename.lower()

                if lower.endswith(
                    (
                        ".jpg",
                        ".jpeg",
                        ".png",
                        ".webp",
                        ".gif",
                    )
                ):
                    media_type = "photo"

                elif (
                    entry.get("vcodec") == "none"
                    or lower.endswith(
                        (
                            ".mp3",
                            ".m4a",
                            ".ogg",
                            ".wav",
                        )
                    )
                ):
                    media_type = "audio"

                else:
                    media_type = "video"

                # Avoid duplicate paths if yt-dlp reports the same
                # output twice.
                if filename not in file_paths:
                    file_paths.append(filename)
                    media_types.append(media_type)

            if not file_paths:
                raise FileNotFoundError(
                    "The media was downloaded but the output "
                    "file was not found."
                )

            if all(t == "photo" for t in media_types):
                overall_type = "photo"
            elif all(t == "audio" for t in media_types):
                overall_type = "audio"
            else:
                overall_type = "video"

            return {
                "file_paths": file_paths,
                "title": title,
                "media_type": overall_type,
            }

    @staticmethod
    def _clean_error(error: str) -> str:
        error = re.sub(
            r"\x1b\[[0-9;]*m",
            "",
            error or "",
        )
        error = error.replace("\n", " ").strip()

        if len(error) > 500:
            error = error[:497] + "..."

        return error

    @staticmethod
    def cleanup(file_path):
        try:
            if isinstance(
                file_path,
                (list, set, tuple),
            ):
                for path in file_path:
                    if path and os.path.exists(path):
                        os.remove(path)

            elif file_path and os.path.exists(file_path):
                os.remove(file_path)

        except Exception:
            logger.exception("Cleanup error")


downloader = MediaDownloader()
