# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# CatUserBot #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2020-2023 by TgCatUB@Github.

# This file is part of: https://github.com/TgCatUB/catuserbot
# and is released under the "GNU v3.0 License Agreement".

# Please see: https://github.com/TgCatUB/catuserbot/blob/master/LICENSE
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import asyncio
import os

from telethon.errors.rpcerrorlist import YouBlockedUserError
from telethon.tl import types
from telethon.tl.functions.contacts import UnblockRequest as unblock

from userbot import catub

from ..Config import Config
from ..core.managers import edit_delete, edit_or_reply
from ..helpers.functions import delete_conv
from ..helpers.utils import _catutils

plugin_category = "misc"

BOT_V1 = "Fullsavebot"
BOT_V2 = "@videomaniacbot"


def _extract_instagram_link(text):
    if not text or "instagram.com" not in text:
        return None
    text = text.strip()
    for part in text.split():
        if "instagram.com" in part:
            return part
    return text


async def _fetch_insta_media(event, link, catevent):
    """Use Telegram bots to fetch Instagram media. Returns (media_list, conv_chat, flag_msg) or (None, None, None)."""
    media_list = []
    async with event.client.conversation(BOT_V1) as conv:
        try:
            v1_flag = await conv.send_message("/start")
        except YouBlockedUserError:
            await catub(unblock(BOT_V1))
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
                return media_list, BOT_V1, v1_flag
        except asyncio.TimeoutError:
            pass
        await delete_conv(event, BOT_V1, v1_flag)

    await edit_or_reply(catevent, "**Switching to backup bot...**")
    async with event.client.conversation(BOT_V2) as conv:
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
            return [media], BOT_V2, v2_flag
        await delete_conv(event, BOT_V2, v2_flag)
        return None, None, None


@catub.cat_cmd(
    pattern="inv(?:\s|$)([\s\S]*)",
    command=("inv", plugin_category),
    info={
        "header": "Download Instagram video or photo",
        "description": "Uses Telegram bots to download Instagram posts/reels (no login). Prefer .inv for Instagram over .dlv.",
        "usage": [
            "{tr}inv <instagram link>",
            "{tr}inv (reply to a message with the link)",
        ],
        "examples": ["{tr}inv https://instagram.com/...", "{tr}inv (reply)"],
    },
)
async def insta_video(event):
    "Download Instagram video/photo via Telegram bots."
    msg = event.pattern_match.group(1)
    reply = await event.get_reply_message()
    if not msg and reply:
        msg = reply.text or ""
    link = _extract_instagram_link(msg)
    if not link:
        return await edit_delete(
            event, "`Give an Instagram link or reply to a message with the link.`", 10
        )
    catevent = await edit_or_reply(event, "`Downloading...`")
    media_list, conv_chat, flag_msg = await _fetch_insta_media(event, link, catevent)
    if not media_list or not conv_chat:
        return await edit_delete(
            catevent, "`Could not get media from this link. Try another or check the URL.`", 15
        )
    details = media_list[0].message.splitlines() if media_list[0].message else []
    caption = f"**{details[0]}**" if details else None
    await catevent.delete()
    await event.client.send_file(event.chat_id, media_list, caption=caption)
    await delete_conv(event, conv_chat, flag_msg)


@catub.cat_cmd(
    pattern="ina(?:\s|$)([\s\S]*)",
    command=("ina", plugin_category),
    info={
        "header": "Download Instagram audio (MP3 from reel/video)",
        "description": "Gets Instagram media via Telegram bots and extracts audio as MP3. Use for reels/videos; .inv for photos.",
        "usage": [
            "{tr}ina <instagram reel/video link>",
            "{tr}ina (reply to a message with the link)",
        ],
        "examples": ["{tr}ina https://instagram.com/reel/...", "{tr}ina (reply)"],
    },
)
async def insta_audio(event):
    "Download Instagram audio from reel/video via Telegram bots."
    msg = event.pattern_match.group(1)
    reply = await event.get_reply_message()
    if not msg and reply:
        msg = reply.text or ""
    link = _extract_instagram_link(msg)
    if not link:
        return await edit_delete(
            event, "`Give an Instagram link or reply to a message with the link.`", 10
        )
    catevent = await edit_or_reply(event, "`Downloading...`")
    media_list, conv_chat, flag_msg = await _fetch_insta_media(event, link, catevent)
    if not media_list or not conv_chat:
        return await edit_delete(
            catevent, "`Could not get media from this link. Try another or check the URL.`", 15
        )
    # Find first video in the list
    video_msg = None
    for m in media_list:
        if m.media and getattr(m.media, "document", None):
            for attr in getattr(m.media.document, "attributes", []) or []:
                if isinstance(attr, types.DocumentAttributeVideo):
                    video_msg = m
                    break
            if video_msg:
                break
        if getattr(m, "video", False):
            video_msg = m
            break
    if not video_msg:
        await delete_conv(event, conv_chat, flag_msg)
        await catevent.delete()
        return await edit_delete(
            event, "`No video in this post; cannot extract audio. Use .inv for photos/videos.`", 10
        )
    os.makedirs(Config.TEMP_DIR, exist_ok=True)
    temp_dir = os.path.join(Config.TEMP_DIR, f"ina_{event.chat_id}_{event.id}")
    os.makedirs(temp_dir, exist_ok=True)
    try:
        video_path = await event.client.download_media(video_msg, temp_dir)
        if not video_path or not os.path.isfile(video_path):
            await delete_conv(event, conv_chat, flag_msg)
            return await edit_delete(catevent, "`Download failed.`", 10)
        out_mp3 = os.path.join(temp_dir, "audio.mp3")
        stdout, stderr, ret, _ = await _catutils.runcmd(
            f'ffmpeg -y -i "{video_path}" -vn -acodec libmp3lame -q:a 2 "{out_mp3}"'
        )
        await delete_conv(event, conv_chat, flag_msg)
        if ret != 0 or not os.path.isfile(out_mp3):
            return await edit_delete(
                catevent, "`Audio extraction failed (ffmpeg). Is ffmpeg installed?`", 10
            )
        await catevent.edit("`Uploading...`")
        await event.client.send_file(event.chat_id, out_mp3)
    finally:
        await catevent.delete()
        if os.path.isdir(temp_dir):
            for f in os.listdir(temp_dir):
                try:
                    os.remove(os.path.join(temp_dir, f))
                except OSError:
                    pass
            try:
                os.rmdir(temp_dir)
            except OSError:
                pass
