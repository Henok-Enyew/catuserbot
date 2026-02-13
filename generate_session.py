#!/usr/bin/env python3
"""
Generate a new Telethon STRING_SESSION.

Run this locally (NOT in Docker/Render):
    python3 generate_session.py

You'll need: pip install telethon
"""

import asyncio
import sys

try:
    from telethon import TelegramClient
    from telethon.sessions import StringSession
except ImportError:
    print("Telethon not installed. Run: pip install telethon")
    sys.exit(1)


async def main():
    print("=" * 50)
    print("  CatUserBot - STRING_SESSION Generator")
    print("=" * 50)
    print()

    api_id = input("Enter your API_ID (from my.telegram.org): ").strip()
    api_hash = input("Enter your API_HASH (from my.telegram.org): ").strip()

    if not api_id or not api_hash:
        print("Error: API_ID and API_HASH are required.")
        sys.exit(1)

    try:
        api_id = int(api_id)
    except ValueError:
        print("Error: API_ID must be a number.")
        sys.exit(1)

    print()
    print("Connecting to Telegram...")
    print("You will be asked for your phone number and a verification code.")
    print()

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.start()

    session_string = client.session.save()

    await client.disconnect()

    print()
    print("=" * 50)
    print("  SUCCESS! Here is your new STRING_SESSION:")
    print("=" * 50)
    print()
    print(session_string)
    print()
    print("=" * 50)
    print("NEXT STEPS:")
    print("  1. Copy the string above")
    print("  2. Update STRING_SESSION in your Render env vars")
    print("  3. Redeploy on Render")
    print()
    print("IMPORTANT: Do NOT run the bot locally while it's")
    print("running on Render - that will kill the session again!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
