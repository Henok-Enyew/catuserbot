# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# CatUserBot #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2020-2023 by TgCatUB@Github.

# This file is part of: https://github.com/TgCatUB/catuserbot
# and is released under the "GNU v3.0 License Agreement".

# Please see: https://github.com/TgCatUB/catuserbot/blob/master/LICENSE
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import json
import os
import shutil
import subprocess
import sys
import time

from urlextract import URLExtract

from userbot import catub

from ..Config import Config
from ..core import pool
from ..core.logger import logging
from ..core.managers import edit_delete, edit_or_reply
from ..helpers import reply_id

extractor = URLExtract()
LOGS = logging.getLogger(__name__)

plugin_category = "misc"

# Path to optional cookies file (place cookies.txt in the project root or set COOKIES_FILE env)
COOKIES_FILE = os.environ.get(
    "COOKIES_FILE",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "cookies.txt"),
)


def _get_first_url(text):
    """Extract first URL from text. Returns None if none found."""
    if not text or not text.strip():
        return None
    urls = extractor.find_urls(text)
    return urls[0] if urls else None


def _find_downloaded_file(temp_dir, exclude_extensions=(".jpg", ".jpeg", ".webp", ".png")):
    """Return path to the primary downloaded file in temp_dir (skip thumbnails)."""
    if not os.path.isdir(temp_dir):
        return None
    for name in os.listdir(temp_dir):
        if name.startswith("."):
            continue
        if any(name.lower().endswith(ext) for ext in exclude_extensions):
            continue
        path = os.path.join(temp_dir, name)
        if os.path.isfile(path):
            return path
    return None


def _is_youtube_url(url):
    """Check if URL is a YouTube link."""
    yt_hosts = ("youtube.com", "youtu.be", "youtube-nocookie.com", "m.youtube.com")
    return any(h in url.lower() for h in yt_hosts)


def _run_ytdlp(args, url, temp_dir, timeout=300):
    """Run yt-dlp with enhanced options to bypass YouTube bot detection."""
    outtmpl = os.path.join(temp_dir, "%(id)s.%(ext)s")
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-o", outtmpl,
        "--no-check-certificate",
        "--no-warnings",
        "--quiet",
    ]
    # Use cookies file if available (needed for YouTube on datacenter IPs)
    if os.path.isfile(COOKIES_FILE):
        cmd += ["--cookies", COOKIES_FILE]
    # YouTube-specific: try alternate player clients to dodge bot detection
    if _is_youtube_url(url):
        cmd += [
            "--extractor-args", "youtube:player_client=mweb,android",
            "--user-agent", "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        ]
    cmd += [*args, url]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=temp_dir,
    )
    if result.returncode != 0:
        error_msg = (result.stderr or result.stdout or "yt-dlp failed").strip()
        # Provide user-friendly message for common YouTube blocks
        if "Sign in to confirm" in error_msg or "bot" in error_msg.lower():
            raise RuntimeError(
                "YouTube blocked the request (datacenter IP detected). "
                "Try a non-YouTube link, or add a cookies.txt file to the project root."
            )
        raise RuntimeError(error_msg)
    path = _find_downloaded_file(temp_dir)
    if not path:
        raise RuntimeError("No media file produced")
    return path


def _try_cobalt_download(url, temp_dir, audio_only=False):
    """Try downloading via cobalt API (works for YouTube, TikTok, Twitter, etc.). Returns path or None."""
    try:
        import requests
    except ImportError:
        return None
    # Try multiple cobalt instances
    cobalt_instances = [
        "https://api.cobalt.tools",
    ]
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    body = {"url": url}
    if audio_only:
        body["downloadMode"] = "audio"
        body["audioFormat"] = "mp3"
    for instance in cobalt_instances:
        try:
            resp = requests.post(
                instance,
                json=body,
                headers=headers,
                timeout=30,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            dl_url = data.get("url")
            if not dl_url:
                # Handle picker responses (multiple formats)
                picker = data.get("picker")
                if picker and len(picker) > 0:
                    dl_url = picker[0].get("url")
            if not dl_url:
                continue
            # Download the actual file
            ext = "mp3" if audio_only else "mp4"
            out_path = os.path.join(temp_dir, f"cobalt_dl.{ext}")
            dl_resp = requests.get(dl_url, timeout=120, stream=True)
            if dl_resp.status_code == 200:
                with open(out_path, "wb") as f:
                    for chunk in dl_resp.iter_content(chunk_size=1024 * 1024):
                        f.write(chunk)
                if os.path.isfile(out_path) and os.path.getsize(out_path) > 1000:
                    return out_path
        except Exception as e:
            LOGS.debug(f"Cobalt instance {instance} failed: {e}")
            continue
    return None


@pool.run_in_thread
def _download_video(url, temp_dir):
    """Download video -- tries cobalt first (for YouTube), then yt-dlp."""
    if _is_youtube_url(url):
        cobalt_path = _try_cobalt_download(url, temp_dir, audio_only=False)
        if cobalt_path:
            return cobalt_path
    try:
        return _run_ytdlp(
            [
                "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "--merge-output-format", "mp4",
            ],
            url,
            temp_dir,
        )
    except RuntimeError:
        # If yt-dlp fails and we haven't tried cobalt yet, try it
        if not _is_youtube_url(url):
            cobalt_path = _try_cobalt_download(url, temp_dir, audio_only=False)
            if cobalt_path:
                return cobalt_path
        raise


@pool.run_in_thread
def _download_audio(url, temp_dir):
    """Download audio -- tries cobalt first (for YouTube), then yt-dlp."""
    if _is_youtube_url(url):
        cobalt_path = _try_cobalt_download(url, temp_dir, audio_only=True)
        if cobalt_path:
            return cobalt_path
    try:
        return _run_ytdlp(
            ["-x", "--audio-format", "mp3", "--audio-quality", "320K"],
            url,
            temp_dir,
        )
    except RuntimeError:
        if not _is_youtube_url(url):
            cobalt_path = _try_cobalt_download(url, temp_dir, audio_only=True)
            if cobalt_path:
                return cobalt_path
        raise


async def _ensure_temp_dir():
    """Create a unique temp subdir and return its path."""
    temp_base = Config.TEMP_DIR
    os.makedirs(temp_base, exist_ok=True)
    subdir = os.path.join(temp_base, str(time.time_ns()))
    os.makedirs(subdir, exist_ok=True)
    return subdir


@catub.cat_cmd(
    pattern="dlv(?:\s|$)([\s\S]*)",
    command=("dlv", plugin_category),
    info={
        "header": "Download video from a link",
        "description": "Downloads video from YouTube, TikTok, Twitter, and other sites. For Instagram use .inv instead.",
        "usage": [
            "{tr}dlv <link>",
            "{tr}dlv (reply to a message containing a link)",
        ],
        "examples": ["{tr}dlv https://youtube.com/...", "{tr}dlv (reply)"],
    },
)
async def universal_dl_video(event):
    """Download video from link (or reply)."""
    msg = event.pattern_match.group(1)
    reply = await event.get_reply_message()
    if not msg and reply:
        msg = reply.text or ""
    url = _get_first_url(msg)
    if not url:
        return await edit_delete(
            event, "Give a link or reply to a message with a link.", 10
        )
    temp_dir = await _ensure_temp_dir()
    catevent = await edit_or_reply(event, "`Downloading...`")
    try:
        path = await _download_video(url, temp_dir)
    except Exception as e:
        LOGS.exception("universal_dl video")
        if os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        return await edit_delete(catevent, f"`Download failed: {e}`", 15)
    try:
        await catevent.edit("`Uploading...`")
        reply_to_id = await reply_id(event)
        await event.client.send_file(
            event.chat_id,
            path,
            reply_to=reply_to_id,
            supports_streaming=True,
        )
    finally:
        if os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
    await catevent.delete()


@catub.cat_cmd(
    pattern="dla(?:\s|$)([\s\S]*)",
    command=("dla", plugin_category),
    info={
        "header": "Download audio (MP3) from a link",
        "description": "Downloads and extracts audio as MP3 from YouTube, TikTok, etc. For Instagram use .ina instead.",
        "usage": [
            "{tr}dla <link>",
            "{tr}dla (reply to a message containing a link)",
        ],
        "examples": ["{tr}dla https://youtube.com/...", "{tr}dla (reply)"],
    },
)
async def universal_dl_audio(event):
    """Download audio from link (or reply)."""
    msg = event.pattern_match.group(1)
    reply = await event.get_reply_message()
    if not msg and reply:
        msg = reply.text or ""
    url = _get_first_url(msg)
    if not url:
        return await edit_delete(
            event, "Give a link or reply to a message with a link.", 10
        )
    temp_dir = await _ensure_temp_dir()
    catevent = await edit_or_reply(event, "`Downloading...`")
    try:
        path = await _download_audio(url, temp_dir)
    except Exception as e:
        LOGS.exception("universal_dl audio")
        if os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        return await edit_delete(catevent, f"`Download failed: {e}`", 15)
    try:
        await catevent.edit("`Uploading...`")
        reply_to_id = await reply_id(event)
        await event.client.send_file(
            event.chat_id,
            path,
            reply_to=reply_to_id,
        )
    finally:
        if os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
    await catevent.delete()
