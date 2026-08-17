import os
import asyncio
import yt_dlp
import config

download_semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_DOWNLOADS)

async def download_media(url: str, download_path: str = "./downloads"):
    async with download_semaphore:
        if not os.path.exists(download_path):
            os.makedirs(download_path)

        ydl_opts = {
            'format': 'best[filesize<150M]/best',
            'outtmpl': f'{download_path}/%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'max_filesize': config.MAX_FILE_SIZE_MB * 1024 * 1024,
        }

        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                return filename, info.get('title', 'Media'), info.get('extractor', 'web')

        loop = asyncio.get_event_loop()
        try:
            filename, title, extractor = await loop.run_in_executor(None, _download)
            return filename, title, extractor
        except Exception as e:
            raise Exception(f"Download Error: {str(e)}")

def cleanup_file(filepath: str):
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception:
            pass
