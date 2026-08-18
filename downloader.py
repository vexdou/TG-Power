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
                response = requests.head(url, allow_redirects=True, timeout=5)
                return response.url
        except Exception:
            pass
        return url

    # ------------------ VIDEO DOWNLOAD ------------------
    async def download(self, url: str, user_id: int) -> dict:
        async with self.lock:
            if url in self.processing_urls:
                return {"success": False, "error": "Soo dejinta link-gan waa ay socotaa. Fadlan int yar sug."}
            self.processing_urls.add(url)

        try:
            loop = asyncio.get_running_loop()
            real_url = await loop.run_in_executor(executor, lambda: self.expand_url(url))
            platform = self.extract_platform(real_url)
            
            out_template = str(self.download_dir / f"{user_id}_%(id)s.%(ext)s")
            
            ydl_opts = {
                'outtmpl': out_template,
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best',
                'quiet': True,
                'no_warnings': True,
                'max_filesize': Config.MAX_FILE_SIZE_MB * 1024 * 1024,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'extractor_args': {
                    'youtube': {
                        'player_client': ['mweb', 'ios', 'tv'],
                        'skip': ['dash', 'hls']
                    }
                },
                'nocheckcertificate': True
            }

            result = await loop.run_in_executor(executor, lambda: self._exec_dlp(ydl_opts, real_url))
            
            return {
                "success": True,
                "file_path": result['file_path'],
                "title": result.get('title', 'Downloaded Media'),
                "platform": platform,
                "media_type": result.get('media_type', 'video')
            }
        except Exception as e:
            logger.error(f"Download Error [{url}]: {str(e)}")
            return {"success": False, "error": str(e)}
        finally:
            async with self.lock:
                self.processing_urls.discard(url)

    # ------------------ MUSIC / AUDIO EXTRACTOR ------------------
    async def download_audio(self, url: str, user_id: int) -> dict:
        """Video-ga ama link-ga toos wuxuu uga soo saarayaa MP3 Audio"""
        async with self.lock:
            if url in self.processing_urls:
                return {"success": False, "error": "Bedelida codku waa ay socotaa. Fadlan int yar sug."}
            self.processing_urls.add(url)

        try:
            loop = asyncio.get_running_loop()
            real_url = await loop.run_in_executor(executor, lambda: self.expand_url(url))
            out_template = str(self.download_dir / f"audio_{user_id}_%(id)s.%(ext)s")
            
            ydl_opts = {
                'outtmpl': out_template,
                'format': 'bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'max_filesize': Config.MAX_FILE_SIZE_MB * 1024 * 1024,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'nocheckcertificate': True
            }

            result = await loop.run_in_executor(executor, lambda: self._exec_dlp(ydl_opts, real_url))
            return {
                "success": True,
                "file_path": result['file_path'],
                "title": result.get('title', 'Music Track'),
                "media_type": "audio"
            }
        except Exception as e:
            logger.error(f"Audio Download Error [{url}]: {str(e)}")
            return {"success": False, "error": str(e)}
        finally:
            async with self.lock:
                self.processing_urls.discard(url)

    def _exec_dlp(self, opts: dict, url: str) -> dict:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if 'entries' in info and info['entries']:
                info = info['entries'][0]
            filename = ydl.prepare_filename(info)
            
            if not os.path.exists(filename):
                base, _ = os.path.splitext(filename)
                for ext in ['.mp3', '.mp4', '.m4a', '.webm', '.ogg']:
                    if os.path.exists(base + ext):
                        filename = base + ext
                        break

            return {
                "file_path": filename,
                "title": info.get('title', 'Media'),
                "media_type": "audio" if info.get('vcodec') == 'none' or filename.endswith('.mp3') else "video"
            }

    def cleanup(self, file_path: str):
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

downloader = MediaDownloader()
