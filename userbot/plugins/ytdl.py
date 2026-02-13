# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# CatUserBot #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2020-2023 by TgCatUB@Github.

# This file is part of: https://github.com/TgCatUB/catuserbot
# and is released under the "GNU v3.0 License Agreement".

# Please see: https://github.com/TgCatUB/catuserbot/blob/master/LICENSE
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import glob
import io
import os
import pathlib
import shutil
import subprocess
import sys
from time import time

from telethon.errors.rpcerrorlist import YouBlockedUserError
from telethon.tl import types
from telethon.tl.functions.contacts import UnblockRequest as unblock
from telethon.utils import get_attributes
from urlextract import URLExtract
from wget import download
from yt_dlp import YoutubeDL
from yt_dlp.utils import (
    ContentTooShortError,
    DownloadError,
    ExtractorError,
    GeoRestrictedError,
    MaxDownloadsReached,
    PostProcessingError,
    UnavailableVideoError,
    XAttrMetadataError,
)

from ..Config import Config
from ..core import pool
from ..core.logger import logging
from ..core.managers import edit_delete, edit_or_reply
from ..helpers import progress, reply_id
from ..helpers.functions import delete_conv
from ..helpers.functions.utube import _mp3Dl, get_yt_video_id, get_ytthumb, ytsearch
from ..helpers.utils import _format
from . import catub

BASE_YT_URL = "https://www.youtube.com/watch?v="
extractor = URLExtract()
LOGS = logging.getLogger(__name__)

plugin_category = "misc"


video_opts = {
    "format": "best",
    "addmetadata": True,
    "key": "FFmpegMetadata",
    "writethumbnail": True,
    "prefer_ffmpeg": True,
    "geo_bypass": True,
    "nocheckcertificate": True,
    "postprocessors": [
        {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"},
        {"key": "FFmpegMetadata"},
    ],
    "outtmpl": "cat_ytv.mp4",
    "logtostderr": False,
    "quiet": True,
    # YouTube bot-detection bypass for datacenter IPs
    "extractor_args": {"youtube": {"player_client": ["mweb", "android"]}},
    "http_headers": {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Mobile Safari/537.36"
        ),
    },
}

# Add cookies if file exists
_cookies_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "cookies.txt")
if os.path.isfile(_cookies_path):
    video_opts["cookiefile"] = _cookies_path

YT_AUDIO_BOT = "@YtbAudioBot"
TTSAVE_BOT = "@ttsavebot"


async def ytdl_down(event, opts, url):
    ytdl_data = None
    try:
        await event.edit("`Fetching data, please wait..`")
        with YoutubeDL(opts) as ytdl:
            ytdl_data = ytdl.extract_info(url)
    except DownloadError as DE:
        await event.edit(f"`{DE}`")
    except ContentTooShortError:
        await event.edit("`The download content was too short.`")
    except GeoRestrictedError:
        await event.edit(
            "`Video is not available from your geographic location due to geographic restrictions imposed by a website.`"
        )
    except MaxDownloadsReached:
        await event.edit("`Max-downloads limit has been reached.`")
    except PostProcessingError:
        await event.edit("`There was an error during post processing.`")
    except UnavailableVideoError:
        await event.edit("`Media is not available in the requested format.`")
    except XAttrMetadataError as XAME:
        await event.edit(f"`{XAME.code}: {XAME.msg}\n{XAME.reason}`")
    except ExtractorError:
        await event.edit("`There was an error during info extraction.`")
    except Exception as e:
        await event.edit(f"**Error : **\n__{e}__")
    return ytdl_data


async def fix_attributes(
    path, info_dict: dict, supports_streaming: bool = False, round_message: bool = False
) -> list:
    """Avoid multiple instances of an attribute."""
    new_attributes = []
    video = False
    audio = False

    uploader = info_dict.get("uploader", "Unknown artist")
    duration = int(info_dict.get("duration", 0))
    suffix = path.suffix[1:]
    if supports_streaming and suffix != "mp4":
        supports_streaming = True

    attributes, mime_type = get_attributes(path)
    if suffix == "mp3":
        title = str(info_dict.get("title", info_dict.get("id", "Unknown title")))
        audio = types.DocumentAttributeAudio(
            duration=duration, voice=None, title=title, performer=uploader
        )
    elif suffix == "mp4":
        width = int(info_dict.get("width", 0))
        height = int(info_dict.get("height", 0))
        for attr in attributes:
            if isinstance(attr, types.DocumentAttributeVideo):
                duration = duration or attr.duration
                width = width or attr.w
                height = height or attr.h
                break
        video = types.DocumentAttributeVideo(
            duration=duration,
            w=width,
            h=height,
            round_message=round_message,
            supports_streaming=supports_streaming,
        )

    if audio and isinstance(audio, types.DocumentAttributeAudio):
        new_attributes.append(audio)
    if video and isinstance(video, types.DocumentAttributeVideo):
        new_attributes.append(video)

    new_attributes.extend(
        attr
        for attr in attributes
        if (
            isinstance(attr, types.DocumentAttributeAudio)
            and not audio
            or not isinstance(attr, types.DocumentAttributeAudio)
            and not video
            or not isinstance(attr, types.DocumentAttributeAudio)
            and not isinstance(attr, types.DocumentAttributeVideo)
        )
    )
    return new_attributes, mime_type


async def _yta_via_bot(event, url, catevent, reply_to_id):
    """Fallback: download YouTube audio via @YtbAudioBot."""
    try:
        await catevent.edit("`yt-dlp failed, trying @YtbAudioBot...`")
        async with event.client.conversation(YT_AUDIO_BOT) as conv:
            try:
                flag_msg = await conv.send_message(url)
            except YouBlockedUserError:
                await catub(unblock("YtbAudioBot"))
                flag_msg = await conv.send_message(url)
            # Wait for the bot to process (it may send a text first, then audio)
            for _ in range(3):
                resp = await conv.get_response(timeout=30)
                await event.client.send_read_acknowledge(conv.chat_id)
                if resp.media and getattr(resp.media, "document", None):
                    await catevent.delete()
                    await event.client.send_file(
                        event.chat_id,
                        resp.media,
                        reply_to=reply_to_id,
                    )
                    await delete_conv(event, YT_AUDIO_BOT, flag_msg)
                    return True
            await delete_conv(event, YT_AUDIO_BOT, flag_msg)
    except (asyncio.TimeoutError, asyncio.CancelledError, ConnectionError, Exception) as e:
        LOGS.debug(f"YtbAudioBot fallback failed: {e}")
    return False


@catub.cat_cmd(
    pattern="yta(?:\s|$)([\s\S]*)",
    command=("yta", plugin_category),
    info={
        "header": "To download audio from many sites like Youtube, Facebook, Instagram, etc.",
        "description": "downloads the audio from the given link. Falls back to @YtbAudioBot for YouTube if yt-dlp fails on datacenter IPs.",
        "examples": ["{tr}yta <reply to link>", "{tr}yta <link>"],
    },
)
async def download_audio(event):  # sourcery skip: low-code-quality
    """To download audio from YouTube and many other sites."""
    msg = event.pattern_match.group(1)
    rmsg = await event.get_reply_message()
    if not msg and rmsg:
        msg = rmsg.text
    urls = extractor.find_urls(msg)
    if not urls:
        return await edit_or_reply(event, "What I am Supposed to do? Give link")
    catevent = await edit_or_reply(event, "`Preparing to download...`")
    reply_to_id = await reply_id(event)
    for url in urls:
        try:
            vid_data = YoutubeDL({"no-playlist": True, **video_opts}).extract_info(
                url, download=False
            )
        except ExtractorError:
            vid_data = {"title": url, "uploader": "Catuserbot", "formats": []}
        except Exception:
            vid_data = {"title": url, "uploader": "Catuserbot", "formats": []}
        startTime = time()
        retcode = await _mp3Dl(url=url, starttime=startTime, uid="320")
        if retcode != 0:
            # yt-dlp failed -- try Telegram bot fallback for YouTube
            if "youtube.com" in url or "youtu.be" in url:
                if await _yta_via_bot(event, url, catevent, reply_to_id):
                    return
            return await edit_delete(catevent, f"`Download failed: {retcode}`", 15)
        _fpath = ""
        thumb_pic = None
        for _path in glob.glob(os.path.join(Config.TEMP_DIR, str(startTime), "*")):
            if _path.lower().endswith((".jpg", ".png", ".webp")):
                thumb_pic = _path
            else:
                _fpath = _path
        if not _fpath:
            return await edit_delete(catevent, "__Unable to upload file__")
        await catevent.edit(
            f"`Preparing to upload audio:`\
            \n**{vid_data['title']}**"
        )
        attributes, mime_type = get_attributes(str(_fpath))
        ul = io.open(pathlib.Path(_fpath), "rb")
        if thumb_pic is None:
            try:
                thumb_pic = str(
                    await pool.run_in_thread(download)(
                        await get_ytthumb(get_yt_video_id(url))
                    )
                )
            except Exception:
                thumb_pic = None
        uploaded = await event.client.fast_upload_file(
            file=ul,
            progress_callback=lambda d, t: asyncio.get_event_loop().create_task(
                progress(
                    d,
                    t,
                    catevent,
                    startTime,
                    "trying to upload",
                    file_name=os.path.basename(pathlib.Path(_fpath)),
                )
            ),
        )
        ul.close()
        media = types.InputMediaUploadedDocument(
            file=uploaded,
            mime_type=mime_type,
            attributes=attributes,
            force_file=False,
            thumb=await event.client.upload_file(thumb_pic) if thumb_pic else None,
        )
        await event.client.send_file(
            event.chat_id,
            file=media,
            caption=f"<b>File Name : </b><code>{vid_data.get('title', os.path.basename(pathlib.Path(_fpath)))}</code>",
            supports_streaming=True,
            reply_to=reply_to_id,
            parse_mode="html",
        )
        for _path in [_fpath, thumb_pic]:
            if _path and os.path.exists(_path):
                os.remove(_path)
    await catevent.delete()


@catub.cat_cmd(
    pattern="ytv(?:\s|$)([\s\S]*)",
    command=("ytv", plugin_category),
    info={
        "header": "To download video from many sites like Youtube, Facebook, Instagram",
        "description": "downloads the video from the given link ([Supported Sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md))",
        "examples": [
            "{tr}ytv <reply to link>",
            "{tr}ytv <link>",
        ],
    },
)
async def download_video(event):
    """To download video from YouTube and many other sites."""
    msg = event.pattern_match.group(1)
    rmsg = await event.get_reply_message()
    if not msg and rmsg:
        msg = rmsg.text
    urls = extractor.find_urls(msg)
    if not urls:
        return await edit_or_reply(event, "What I am Supposed to do? Give link")
    catevent = await edit_or_reply(event, "`Preparing to download...`")
    reply_to_id = await reply_id(event)
    for url in urls:
        ytdl_data = await ytdl_down(catevent, video_opts, url)
        if ytdl_down is None:
            return
        try:
            f = pathlib.Path("cat_ytv.mp4")
            catthumb = pathlib.Path("cat_ytv.jpg")
            if not os.path.exists(catthumb):
                catthumb = pathlib.Path("cat_ytv.webp")
            if not os.path.exists(catthumb):
                catthumb = None
            await catevent.edit(
                f"`Preparing to upload video:`\
                \n**{ytdl_data['title']}**"
            )
            ul = io.open(f, "rb")
            c_time = time()
            attributes, mime_type = await fix_attributes(
                f, ytdl_data, supports_streaming=True
            )
            uploaded = await event.client.fast_upload_file(
                file=ul,
                progress_callback=lambda d, t: asyncio.get_event_loop().create_task(
                    progress(
                        d, t, catevent, c_time, "Upload :", file_name=ytdl_data["title"]
                    )
                ),
            )
            ul.close()
            media = types.InputMediaUploadedDocument(
                file=uploaded,
                mime_type=mime_type,
                attributes=attributes,
            )
            await event.client.send_file(
                event.chat_id,
                file=media,
                reply_to=reply_to_id,
                caption=f'**Title :** `{ytdl_data["title"]}`',
                thumb=catthumb,
            )
            os.remove(f)
            if catthumb:
                os.remove(catthumb)
        except TypeError:
            await asyncio.sleep(2)
    await event.delete()


@catub.cat_cmd(
    pattern="insta(?: |$)([\s\S]*)",
    command=("insta", plugin_category),
    info={
        "header": "To download instagram video/photo",
        "description": "Note downloads only public profile photos/videos.",
        "examples": [
            "{tr}insta <link>",
        ],
    },
)
async def insta_dl(event):
    "For downloading instagram media"
    link = event.pattern_match.group(1)
    reply = await event.get_reply_message()
    if not link and reply:
        link = reply.text
    if not link:
        return await edit_delete(event, "**ಠ∀ಠ Give me link to search..**", 10)
    if "instagram.com" not in link:
        return await edit_delete(
            event, "` I need a Instagram link to download it's Video...`(*_*)", 10
        )
    # v1 = "@instasave_bot"
    # v1 = "@IgGramBot"
    v1 = "Fullsavebot"
    v2 = "@videomaniacbot"
    media_list = []
    catevent = await edit_or_reply(event, "**Downloading.....**")
    async with event.client.conversation(v1) as conv:
        try:
            v1_flag = await conv.send_message("/start")
        except YouBlockedUserError:
            await catub(unblock("Fullsavebot"))
            v1_flag = await conv.send_message("/start")
        checker = await conv.get_response()
        await event.client.send_read_acknowledge(conv.chat_id)
        if "Choose the language you like" in checker.message:
            await checker.click(1)
            await conv.send_message(link)
            await conv.get_response()
            await event.client.send_read_acknowledge(conv.chat_id)
        await conv.send_message(link)
        await conv.get_response()
        await event.client.send_read_acknowledge(conv.chat_id)
        try:
            media = await conv.get_response(timeout=10)
            await event.client.send_read_acknowledge(conv.chat_id)
            if media.media:
                while True:
                    media_list.append(media)
                    try:
                        media = await conv.get_response(timeout=2)
                        await event.client.send_read_acknowledge(conv.chat_id)
                    except asyncio.TimeoutError:
                        break
                details = media_list[0].message.splitlines()
                await catevent.delete()
                await event.client.send_file(
                    event.chat_id,
                    media_list,
                    caption=f"**{details[0]}**",
                )
                return await delete_conv(event, v1, v1_flag)
        except asyncio.TimeoutError:
            await delete_conv(event, v1, v1_flag)
        await edit_or_reply(catevent, "**Switching v2...**")
        async with event.client.conversation(v2) as conv:
            try:
                v2_flag = await conv.send_message("/start")
            except YouBlockedUserError:
                await catub(unblock("videomaniacbot"))
                v2_flag = await conv.send_message("/start")
            await conv.get_response()
            await event.client.send_read_acknowledge(conv.chat_id)
            await asyncio.sleep(1)
            await conv.send_message(link)
            await conv.get_response()
            await event.client.send_read_acknowledge(conv.chat_id)
            media = await conv.get_response()
            await event.client.send_read_acknowledge(conv.chat_id)
            if media.media:
                await catevent.delete()
                await event.client.send_file(event.chat_id, media)
            else:
                await edit_delete(
                    catevent,
                    f"**#ERROR\nv1 :** __Not valid URL__\n\n**v2 :**__ {media.text}__",
                    40,
                )
            await delete_conv(event, v2, v2_flag)


@catub.cat_cmd(
    pattern="yts(?: |$)(\d*)? ?([\s\S]*)",
    command=("yts", plugin_category),
    info={
        "header": "To search youtube videos",
        "description": "Fetches youtube search results with views and duration with required no of count results by default it fetches 10 results",
        "examples": [
            "{tr}yts <query>",
            "{tr}yts <1-9> <query>",
        ],
    },
)
async def yt_search(event):
    "Youtube search command"
    if event.is_reply and not event.pattern_match.group(2):
        query = await event.get_reply_message()
        query = str(query.message)
    else:
        query = str(event.pattern_match.group(2))
    if not query:
        return await edit_delete(
            event, "`Reply to a message or pass a query to search!`"
        )
    video_q = await edit_or_reply(event, "`Searching...`")
    if event.pattern_match.group(1) != "":
        lim = int(event.pattern_match.group(1))
        if lim <= 0:
            lim = 10
    else:
        lim = 10
    try:
        full_response = await ytsearch(query, limit=lim)
    except Exception as e:
        return await edit_delete(video_q, str(e), time=10, parse_mode=_format.parse_pre)
    reply_text = f"**•  Search Query:**\n`{query}`\n\n**•  Results:**\n{full_response}"
    await edit_or_reply(video_q, reply_text)


# ====================== TikTok Downloader ======================


def _find_media_file(temp_dir):
    """Find the primary downloaded media file in temp_dir (skip thumbnails)."""
    for name in os.listdir(temp_dir):
        if not name.startswith(".") and not name.lower().endswith(
            (".jpg", ".jpeg", ".webp", ".png")
        ):
            path = os.path.join(temp_dir, name)
            if os.path.isfile(path):
                return path
    return None


@pool.run_in_thread
def _tiktok_ytdlp_video(url, temp_dir):
    """Download TikTok video via yt-dlp."""
    outtmpl = os.path.join(temp_dir, "%(id)s.%(ext)s")
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-o", outtmpl,
        "--no-check-certificate", "--no-warnings", "--quiet",
        "-f", "best[ext=mp4]/best",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=temp_dir)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "yt-dlp failed for TikTok")
    path = _find_media_file(temp_dir)
    if not path:
        raise RuntimeError("No media file produced")
    return path


@pool.run_in_thread
def _tiktok_ytdlp_audio(url, temp_dir):
    """Download TikTok audio (MP3) via yt-dlp."""
    outtmpl = os.path.join(temp_dir, "%(id)s.%(ext)s")
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-o", outtmpl,
        "--no-check-certificate", "--no-warnings", "--quiet",
        "-x", "--audio-format", "mp3", "--audio-quality", "320K",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=temp_dir)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "yt-dlp audio failed for TikTok")
    path = _find_media_file(temp_dir)
    if not path:
        raise RuntimeError("No audio file produced")
    return path


async def _tiktok_via_bot(event, url, catevent, reply_to_id):
    """Fallback: download TikTok media via @ttsavebot."""
    try:
        await catevent.edit("`yt-dlp failed, trying @ttsavebot...`")
        async with event.client.conversation(TTSAVE_BOT) as conv:
            try:
                flag_msg = await conv.send_message(url)
            except YouBlockedUserError:
                await catub(unblock("ttsavebot"))
                flag_msg = await conv.send_message(url)
            for _ in range(5):
                resp = await conv.get_response(timeout=20)
                await event.client.send_read_acknowledge(conv.chat_id)
                if resp.media:
                    await catevent.delete()
                    await event.client.send_file(
                        event.chat_id, resp.media, reply_to=reply_to_id,
                    )
                    await delete_conv(event, TTSAVE_BOT, flag_msg)
                    return True
            await delete_conv(event, TTSAVE_BOT, flag_msg)
    except (asyncio.TimeoutError, asyncio.CancelledError, ConnectionError, Exception) as e:
        LOGS.debug(f"ttsavebot fallback failed: {e}")
    return False


def _cleanup(temp_dir):
    if os.path.isdir(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)


@catub.cat_cmd(
    pattern="ttv(?:\s|$)([\s\S]*)",
    command=("ttv", plugin_category),
    info={
        "header": "Download TikTok video",
        "description": "Downloads TikTok videos using yt-dlp (fast, no watermark). Falls back to @ttsavebot if yt-dlp fails.",
        "usage": [
            "{tr}ttv <tiktok link>",
            "{tr}ttv (reply to a message with the link)",
        ],
        "examples": ["{tr}ttv https://vm.tiktok.com/...", "{tr}ttv (reply)"],
    },
)
async def tiktok_dl_video(event):
    """Download TikTok video."""
    msg = event.pattern_match.group(1)
    rmsg = await event.get_reply_message()
    if not msg and rmsg:
        msg = rmsg.text or ""
    urls = extractor.find_urls(msg)
    url = urls[0] if urls else None
    if not url:
        return await edit_delete(event, "Give a TikTok link or reply to one.", 10)

    catevent = await edit_or_reply(event, "`Downloading TikTok video...`")
    reply_to_id = await reply_id(event)
    temp_dir = os.path.join(Config.TEMP_DIR, f"ttv_{event.id}")
    os.makedirs(temp_dir, exist_ok=True)

    try:
        path = await _tiktok_ytdlp_video(url, temp_dir)
    except Exception as e:
        LOGS.debug(f"TikTok yt-dlp video failed: {e}")
        if await _tiktok_via_bot(event, url, catevent, reply_to_id):
            _cleanup(temp_dir)
            return
        _cleanup(temp_dir)
        return await edit_delete(catevent, f"`Download failed: {e}`", 15)

    try:
        await catevent.edit("`Uploading...`")
        await event.client.send_file(
            event.chat_id, path, reply_to=reply_to_id, supports_streaming=True,
        )
    finally:
        _cleanup(temp_dir)
    await catevent.delete()


@catub.cat_cmd(
    pattern="tta(?:\s|$)([\s\S]*)",
    command=("tta", plugin_category),
    info={
        "header": "Download TikTok audio (MP3)",
        "description": "Extracts audio from TikTok videos as MP3 using yt-dlp. Falls back to @ttsavebot if yt-dlp fails.",
        "usage": [
            "{tr}tta <tiktok link>",
            "{tr}tta (reply to a message with the link)",
        ],
        "examples": ["{tr}tta https://vm.tiktok.com/...", "{tr}tta (reply)"],
    },
)
async def tiktok_dl_audio(event):
    """Download TikTok audio as MP3."""
    msg = event.pattern_match.group(1)
    rmsg = await event.get_reply_message()
    if not msg and rmsg:
        msg = rmsg.text or ""
    urls = extractor.find_urls(msg)
    url = urls[0] if urls else None
    if not url:
        return await edit_delete(event, "Give a TikTok link or reply to one.", 10)

    catevent = await edit_or_reply(event, "`Downloading TikTok audio...`")
    reply_to_id = await reply_id(event)
    temp_dir = os.path.join(Config.TEMP_DIR, f"tta_{event.id}")
    os.makedirs(temp_dir, exist_ok=True)

    try:
        path = await _tiktok_ytdlp_audio(url, temp_dir)
    except Exception as e:
        LOGS.debug(f"TikTok yt-dlp audio failed: {e}")
        # For audio, bot fallback gives video; we can still try it
        if await _tiktok_via_bot(event, url, catevent, reply_to_id):
            _cleanup(temp_dir)
            return
        _cleanup(temp_dir)
        return await edit_delete(catevent, f"`Download failed: {e}`", 15)

    try:
        await catevent.edit("`Uploading...`")
        await event.client.send_file(
            event.chat_id, path, reply_to=reply_to_id,
        )
    finally:
        _cleanup(temp_dir)
    await catevent.delete()
