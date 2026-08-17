import asyncio
import os
import re
import uuid
import yt_dlp
import config

download_semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_DOWNLOADS)
URL_RE = re.compile(r"^https?://\S+$", re.I)

def is_url(value: str) -> bool:
    return bool(URL_RE.match((value or "").strip()))

def detect_platform(url: str) -> str:
    u = (url or "").lower()
    if "youtu.be" in u or "youtube.com" in u:
        return "YouTube"
    if "tiktok.com" in u:
        return "TikTok"
    if "instagram.com" in u:
        return "Instagram"
    if "facebook.com" in u or "fb.watch" in u:
        return "Facebook"
    if "pinterest.com" in u or "pin.it" in u:
        return "Pinterest"
    if "twitter.com" in u or "x.com" in u:
        return "X/Twitter"
    if "snapchat.com" in u:
        return "Snapchat"
    return "Other"

async def download_media(url: str, download_path: str = "./downloads"):
    if not is_url(url):
        raise ValueError("Invalid URL")
    os.makedirs(download_path, exist_ok=True)
    job_id = uuid.uuid4().hex
    outtmpl = os.path.join(download_path, f"{job_id}.%(ext)s")
    ydl_opts = {
        "format": "bestvideo*+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "max_filesize": config.MAX_FILE_SIZE_MB * 1024 * 1024,
        "socket_timeout": 30,
        "retries": 3,
    }

    async with download_semaphore:
        def _run():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                # yt-dlp may merge into mp4, so prefer the merged file if present.
                base, _ = os.path.splitext(filename)
                candidates = [filename, base + ".mp4", base + ".mkv", base + ".webm"]
                final = next((p for p in candidates if os.path.exists(p)), None)
                if not final:
                    raise FileNotFoundError("Downloaded file was not found")
                size = os.path.getsize(final)
                if size > config.MAX_FILE_SIZE_MB * 1024 * 1024:
                    cleanup_file(final)
                    raise ValueError("File is larger than the configured Telegram upload limit")
                return final, info.get("title") or "Media", info.get("extractor_key") or detect_platform(url)

        try:
            return await asyncio.wait_for(asyncio.to_thread(_run), timeout=config.DOWNLOAD_TIMEOUT)
        except Exception:
            # Remove partial files created by this job.
            for name in os.listdir(download_path):
                if name.startswith(job_id):
                    cleanup_file(os.path.join(download_path, name))
            raise

def cleanup_file(filepath: str):
    if filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
        except OSError:
            pass
