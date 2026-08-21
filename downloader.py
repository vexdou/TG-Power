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
            response = requests.head(url, allow_redirects=True, timeout=10, headers=headers)
            if response.url:
                return response.url
        except Exception:
            pass
        try:
            response = requests.get(url, allow_redirects=True, timeout=10, headers=headers, stream=True)
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

    def _base_opts(self, out_template: str) -> dict:
        opts = {
            "outtmpl": out_template,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "restrictfilenames": True,
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": 30,
            "nocheckcertificate": True,
            "max_filesize": Config.MAX_FILE_SIZE_MB * 1024 * 1024,
            "user_agent": self._user_agent(),
            "http_headers": {
                "User-Agent": self._user_agent(),
                "Accept-Language": "en-US,en;q=0.9",
            },
            "concurrent_fragment_downloads": 4,
        }

        # Newer yt-dlp YouTube extraction can use Deno + remote EJS scripts.
        if shutil.which("deno"):
            opts["js_runtimes"] = {"deno": {}}
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
                cookie_path.write_bytes(base64.b64decode(cookie_b64))
                result["cookiefile"] = str(cookie_path)
            except Exception:
                logger.warning("Invalid YOUTUBE_COOKIES_BASE64")

        po_token = os.getenv("YOUTUBE_PO_TOKEN", "").strip()
        if po_token:
            args = dict(result.get("extractor_args", {}))
            args["youtube"] = {
                "player_client": ["mweb"],
                "po_token": [f"mweb.gvs+{po_token}"],
            }
            result["extractor_args"] = args
        return result

    def _youtube_variants(self, opts: dict) -> list[dict]:
        common = self._youtube_common(opts)
        variants = []

        if os.getenv("YOUTUBE_PO_TOKEN", "").strip():
            variants.append(dict(common))

        # These are intentionally tried separately. YouTube changes which
        # clients are accepted on cloud IPs, so one client failing does not
        # immediately fail the whole download.
        for client in ("tv", "web_embedded", "android_vr", "ios", "mweb", "web_creator"):
            candidate = dict(common)
            args = dict(candidate.get("extractor_args", {}))
            yt = dict(args.get("youtube", {}))
            yt["player_client"] = [client]
            args["youtube"] = yt
            candidate["extractor_args"] = args
            variants.append(candidate)

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

    async def download(self, url: str, user_id: int) -> dict:
        async with self.lock:
            if url in self.processing_urls:
                return {"success": False, "error": "This link is already being downloaded."}
            self.processing_urls.add(url)

        try:
            loop = asyncio.get_running_loop()
            real_url = await loop.run_in_executor(executor, lambda: self.expand_url(url))
            platform = self.extract_platform(real_url)
            out_template = str(self.download_dir / f"{user_id}_%(id)s.%(ext)s")
            base = self._base_opts(out_template)
            base.update({
                "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best",
                "merge_output_format": "mp4",
            })
            if platform == "youtube":
                base["match_filter"] = self._youtube_duration_filter

            result = await self._try_download(loop, base, real_url, platform)
            return {
                "success": True,
                "file_path": result["file_path"],
                "title": result.get("title", "Downloaded Video"),
                "platform": platform,
                "media_type": result.get("media_type", "video"),
            }
        except Exception as exc:
            logger.error("Download error [%s]: %s", url, exc, exc_info=True)
            return {"success": False, "error": self._clean_error(str(exc))}
        finally:
            async with self.lock:
                self.processing_urls.discard(url)

    async def download_audio(self, url: str, user_id: int) -> dict:
        async with self.lock:
            if url in self.processing_urls:
                return {"success": False, "error": "Audio conversion is already running."}
            self.processing_urls.add(url)

        try:
            loop = asyncio.get_running_loop()
            real_url = await loop.run_in_executor(executor, lambda: self.expand_url(url))
            platform = self.extract_platform(real_url)
            out_template = str(self.download_dir / f"audio_{user_id}_%(id)s.%(ext)s")
            base = self._base_opts(out_template)
            base.update({
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            })
            if platform == "youtube":
                base["match_filter"] = self._youtube_duration_filter

            result = await self._try_download(loop, base, real_url, platform)
            return {
                "success": True,
                "file_path": result["file_path"],
                "title": result.get("title", "Music"),
                "platform": platform,
                "media_type": "audio",
            }
        except Exception as exc:
            logger.error("Audio download error [%s]: %s", url, exc, exc_info=True)
            return {"success": False, "error": self._clean_error(str(exc))}
        finally:
            async with self.lock:
                self.processing_urls.discard(url)

    async def _try_download(self, loop, base_opts, url, platform):
        errors = []
        for opts in self._variants(base_opts, platform):
            try:
                return await loop.run_in_executor(
                    executor,
                    lambda o=opts: self._exec_dlp(o, url),
                )
            except Exception as exc:
                errors.append(str(exc))
                logger.warning("yt-dlp attempt failed for %s: %s", platform, exc)

        last = errors[-1] if errors else "yt-dlp could not download the media."
        if platform == "youtube" and (
            "Sign in to confirm" in last
            or "not a bot" in last
            or "HTTP Error 403" in last
        ):
            raise RuntimeError(
                "YouTube is blocking this Render/cloud IP. "
                "The downloader now tries multiple YouTube clients and Deno/EJS automatically. "
                "If YouTube still blocks the server, add a valid YOUTUBE_COOKIES_BASE64 or "
                "YOUTUBE_PO_TOKEN secret in Render."
            )
        raise RuntimeError(self._clean_error(last))

    @staticmethod
    def _youtube_duration_filter(info_dict, *, incomplete):
        duration = info_dict.get("duration")
        if duration is not None and duration > Config.MAX_VIDEO_DURATION_SECONDS:
            minutes, seconds = divmod(Config.MAX_VIDEO_DURATION_SECONDS, 60)
            return f"YouTube videos longer than {minutes}:{seconds:02d} are not supported."
        return None

    def _exec_dlp(self, opts: dict, url: str) -> dict:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise RuntimeError("yt-dlp did not return media information.")
            if "entries" in info:
                entries = info.get("entries") or []
                if not entries:
                    raise RuntimeError("No media was found.")
                info = entries[0]

            filename = ydl.prepare_filename(info)
            if not os.path.exists(filename):
                base, _ = os.path.splitext(filename)
                for ext in (".mp4", ".mkv", ".webm", ".m4a", ".mp3", ".ogg", ".mov", ".jpg", ".jpeg", ".png", ".webp"):
                    candidate = base + ext
                    if os.path.exists(candidate):
                        filename = candidate
                        break

            if not os.path.exists(filename):
                media_id = info.get("id")
                if media_id:
                    candidates = list(self.download_dir.glob(f"*{media_id}*"))
                    if candidates:
                        filename = str(max(candidates, key=lambda p: p.stat().st_mtime))

            if not os.path.exists(filename):
                raise FileNotFoundError("The media was downloaded but the output file was not found.")

            lower = filename.lower()
            if lower.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
                media_type = "photo"
            elif info.get("vcodec") == "none" or lower.endswith(".mp3"):
                media_type = "audio"
            else:
                media_type = "video"
            return {
                "file_path": filename,
                "title": info.get("title", "Media"),
                "media_type": media_type,
            }

    @staticmethod
    def _clean_error(error: str) -> str:
        error = re.sub(r"\x1b\[[0-9;]*m", "", error or "")
        error = error.replace("\n", " ").strip()
        if len(error) > 500:
            error = error[:497] + "..."
        return error

    @staticmethod
    def cleanup(file_path: str):
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            logger.exception("Cleanup error")


downloader = MediaDownloader()
