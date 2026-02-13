# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# CatUserBot #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2020-2023 by TgCatUB@Github.

# This file is part of: https://github.com/TgCatUB/catuserbot
# and is released under the "GNU v3.0 License Agreement".

# Please see: https://github.com/TgCatUB/catuserbot/blob/master/LICENSE
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import json
import os

from google import genai
from google.genai import types
import requests
from fake_useragent import UserAgent

from userbot.Config import Config
from userbot.core.managers import edit_delete, edit_or_reply
from userbot.helpers.functions import format_image, wall_download
from userbot.sql_helper.globals import gvarstatus


async def ai_api(event):
    """Return API key for Kuki-style chatbot (used by plugins/chatbot.py)."""
    del event  # unused
    return (
        os.environ.get("KUKI_API_KEY")
        or getattr(Config, "KUKI_API_KEY", None)
        or ""
    )


# Gemini client uses GEMINI_API_KEY from Config (loaded from env)
_gemini_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        api_key = os.environ.get("GEMINI_API_KEY") or getattr(
            Config, "GEMINI_API_KEY", None
        )
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set in environment or config")
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


# In-memory conversation history: chat_id -> list of {role, content}
conversations = {}

GEMINI_MODEL = "gemini-2.0-flash"


def _openai_to_gemini_contents(messages):
    """Convert OpenAI-style messages (system/user/assistant) to Gemini contents + config."""
    system_instruction = None
    contents = []
    for msg in messages:
        role = msg.get("role")
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        if role == "system":
            system_instruction = content
            continue
        if role == "user":
            contents.append(types.Content(role="user", parts=[types.Part.from_text(content)]))
        elif role == "assistant":
            contents.append(types.Content(role="model", parts=[types.Part.from_text(content)]))
    return contents, system_instruction


def generate_gpt_response(input_text, chat_id):
    """Generate a response using Gemini (replaces OpenAI GPT)."""
    global conversations
    model = gvarstatus("CHAT_MODEL") or GEMINI_MODEL
    system_message = gvarstatus("SYSTEM_MESSAGE") or None
    messages = conversations.get(chat_id, [])

    if system_message and not messages:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": input_text})

    try:
        client = _get_gemini_client()
        contents, system_instruction = _openai_to_gemini_contents(messages)
        config = types.GenerateContentConfig()
        if system_instruction:
            config.system_instruction = types.Content(
                parts=[types.Part.from_text(system_instruction)]
            )
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
        if not response.text:
            generated_text = "`No text in Gemini response.`"
        else:
            generated_text = response.text.strip()

        messages.append({"role": "assistant", "content": generated_text})
        conversations[chat_id] = messages
    except Exception as e:
        generated_text = f"`Error generating Gemini response: {str(e)}`"
    return generated_text


def generate_gemini_response(input_text, chat_id, model=None):
    """Generate a response using Gemini (gemini-2.0-flash by default)."""
    return generate_gpt_response(input_text, chat_id)


def generate_edited_response(input_text, instructions):
    """Generate an edited version of the text following instructions (using Gemini)."""
    try:
        client = _get_gemini_client()
        prompt = (
            f"Original text:\n{input_text}\n\n"
            f"Instruction: {instructions}\n\n"
            "Provide only the edited text, with no explanation or preamble."
        )
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        if not response.text:
            edited_text = "__Error: Gemini returned no text.__"
        else:
            edited_text = response.text.strip()
    except Exception as e:
        edited_text = f"__Error generating edited response:__ `{str(e)}`"
    return edited_text


def del_convo(chat_id, checker=False):
    global conversations
    out_text = "__There is no GPT/Gemini context to delete for this chat.__"
    if chat_id in conversations:
        del conversations[chat_id]
        out_text = "__Chat context deleted for this chat.__"
    if checker:
        return out_text


async def generate_dalle_image(text, reply, event, flag=None):
    """DALL-E is not available after migration to Gemini. Inform the user."""
    catevent = await edit_or_reply(event, "__Generating image...__")
    await edit_delete(
        catevent,
        "**Image generation (DALL-E) is not available.** This plugin now uses Google Gemini for chat only. Use `.gem` or `.gpt` for AI chat.",
    )
    return None, None


class ThabAi:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers = {
            "authority": "chatbot.theb.ai",
            "content-type": "application/json",
            "origin": "https://chatbot.theb.ai",
            "user-agent": UserAgent().random,
        }

    def get_response(self, prompt: str) -> str:
        response = self.session.post(
            "https://chatbot.theb.ai/api/chat-process",
            json={"prompt": prompt, "options": {}},
            stream=True,
        )
        response.raise_for_status()
        response_lines = response.iter_lines()
        response_data = ""
        for line in response_lines:
            if line:
                data = json.loads(line)
                if "utterances" in data:
                    response_data += " ".join(
                        utterance["text"] for utterance in data["utterances"]
                    )
                elif "delta" in data:
                    response_data += data["delta"]
        return response_data
