import os
import asyncio
import re
import logging
from pathlib import Path
import yt_dlp

logger = logging.getLogger(__name__)

class MediaDownloader:
    def __init__(self, download_dir: str = "downloads"):
        self.download_dir = Path(download_dir)
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

    async def download(self, url: str, user_id: int) -> dict:
        async with self.lock:
            if url in self.processing_urls:
                return {"success": False, "error": "Duplicate URL request. Processing..."}
            self.processing_urls.add(url)

        try:
            platform = self.extract_platform(url)
            out_template = str(self.download_dir / f"{user_id}_%(id)s.%(ext)s")
            
            # YouTube & Multi-platform robust settings
            ydl_opts = {
                'outtmpl': out_template,
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'quiet': True,
                'no_warnings': True,
                'max_filesize': 50 * 1024 * 1024, # 50MB Telegram Limit
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web'],
                    }
                },
                'nocheckcertificate': True
            }

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: self._exec_dlp(ydl_opts, url))
            
            return {
                "success": True,
                "file_path": result['file_path'],
                "title": result.get('title', 'Downloaded Media'),
                "platform": platform,
                "media_type": result.get('media_type', 'video')
            }
        except Exception as e:
            logger.error(f"Download Error for {url}: {str(e)}")
            return {"success": False, "error": str(e)}
        finally:
            async with self.lock:
                self.processing_urls.discard(url)

    def _exec_dlp(self, opts: dict, url: str) -> dict:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if 'entries' in info:
                info = info['entries'][0]
            filename = ydl.prepare_filename(info)
            
            # Ensure file extension fix if merged
            if not os.path.exists(filename):
                base, _ = os.path.splitext(filename)
                for ext in ['.mp4', '.mkv', '.webm', '.mp3', '.m4a']:
                    if os.path.exists(base + ext):
                        filename = base + ext
                        break

            return {
                "file_path": filename,
                "title": info.get('title', 'Media'),
                "media_type": "audio" if info.get('vcodec') == 'none' else "video"
            }

    def cleanup(self, file_path: str):
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

downloader = MediaDownloader()
