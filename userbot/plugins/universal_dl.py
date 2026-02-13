# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# CatUserBot #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2020-2023 by TgCatUB@Github.

# This file is part of: https://github.com/TgCatUB/catuserbot
# and is released under the "GNU v3.0 License Agreement".

# Please see: https://github.com/TgCatUB/catuserbot/blob/master/LICENSE
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import os
import shutil
import time

from urlextract import URLExtract

from ..Config import Config
from ..core import pool
from ..core.logger import logging
from ..core.managers import edit_delete, edit_or_reply
from ..helpers import reply_id
from . import catub

extractor = URLExtract()
LOGS = logging.getLogger(__name__)

plugin_category = "misc"


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


@pool.run_in_thread
def _download_video(url, temp_dir):
    """Download video (best video+audio merged) into temp_dir. Returns path or raises."""
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError

    opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": os.path.join(temp_dir, "%(id)s.%(ext)s"),
        "nocheckcertificate": True,
        "geo_bypass": True,
        "ignoreerrors": False,
        "extractor_retries": 3,
        "quiet": True,
        "logtostderr": False,
        "postprocessors": [
            {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"},
            {"key": "FFmpegMetadata"},
        ],
    }
    with YoutubeDL(opts) as ydl:
        ydl.download([url])
    path = _find_downloaded_file(temp_dir)
    if not path:
        raise DownloadError("No video file produced")
    return path


@pool.run_in_thread
def _download_audio(url, temp_dir):
    """Download and extract audio (MP3) into temp_dir. Returns path or raises."""
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError

    opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(temp_dir, "%(id)s.%(ext)s"),
        "nocheckcertificate": True,
        "geo_bypass": True,
        "ignoreerrors": False,
        "extractor_retries": 3,
        "quiet": True,
        "logtostderr": False,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            },
            {"key": "FFmpegMetadata"},
        ],
    }
    with YoutubeDL(opts) as ydl:
        ydl.download([url])
    path = _find_downloaded_file(temp_dir)
    if not path:
        raise DownloadError("No audio file produced")
    return path


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
        "description": "Downloads video from YouTube, Instagram, TikTok, etc.",
        "usage": "{tr}dlv <link> or reply to a message with a link",
        "examples": ["{tr}dlv <link>", "{tr}dlv (reply to message with link)"],
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
        "header": "Download audio from a link",
        "description": "Downloads audio (MP3) from YouTube, Instagram, TikTok, etc.",
        "usage": "{tr}dla <link> or reply to a message with a link",
        "examples": ["{tr}dla <link>", "{tr}dla (reply to message with link)"],
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
