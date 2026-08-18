import os
import asyncio
import re
from pathlib import Path
import yt_dlp

class MediaDownloader:
    def __init__(self, download_dir: str = "downloads"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        self.processing_urls = set()
        self.lock = asyncio.Lock()

    def extract_platform(self, url: str) -> str:
        patterns = {
            "tiktok": r"(tiktok\.com)",
            "youtube": r"(youtube\.com|youtu\.be)",
            "instagram": r"(instagram\.com)",
            "twitter": r"(twitter\.com|x\.com)",
            "facebook": r"(facebook\.com|fb\.watch)",
            "pinterest": r"(pinterest\.com|pin\.it)",
            "snapchat": r"(snapchat\.com)"
        }
        for platform, pattern in patterns.items():
            if re.search(pattern, url, re.IGNORECASE):
                return platform
        return "unknown"

    async def download(self, url: str, user_id: int) -> dict:
        async with self.lock:
            if url in self.processing_urls:
                return {"success": False, "error": "Geedi-socodkan horay ayaa loogu jiraa (Duplicate request)."}
            self.processing_urls.add(url)

        try:
            platform = self.extract_platform(url)
            out_template = str(self.download_dir / f"{user_id}_%(id)s.%(ext)s")
            
            ydl_opts = {
                'outtmpl': out_template,
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'quiet': True,
                'no_warnings': True,
                'max_filesize': 50 * 1024 * 1024,  # Limit to 50MB for Telegram Standard Bot API
            }

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: self._exec_dlp(ydl_opts, url))
            
            return {
                "success": True,
                "file_path": result['file_path'],
                "title": result.get('title', 'Media'),
                "platform": platform,
                "media_type": result.get('media_type', 'video')
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            async with self.lock:
                self.processing_urls.discard(url)

    def _exec_dlp(self, opts: dict, url: str) -> dict:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return {
                "file_path": filename,
                "title": info.get('title', 'Media'),
                "media_type": "audio" if info.get('vcodec') == 'none' else "video"
            }

    def cleanup(self, file_path: str):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass

downloader = MediaDownloader()
