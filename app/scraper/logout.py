"""Log the scraper userbot out and clear its saved session, so you can switch accounts:
    py -m app.scraper.logout      (then edit .env with the new account, and run app.scraper.login)
"""
import asyncio
import os
from .. import config


async def main():
    session_file = "sarbon_session.session"
    try:
        from telethon import TelegramClient
        client = TelegramClient(session_file.replace(".session", ""),
                                int(config.TELEGRAM_API_ID or 0), config.TELEGRAM_API_HASH or "")
        await client.connect()
        if await client.is_user_authorized():
            await client.log_out()   # revokes on Telegram's side + removes local session
            print("Logged out and session revoked.")
        else:
            print("Already logged out.")
        await client.disconnect()
    except Exception as exc:
        print(f"(couldn't do a clean server logout: {exc})")
    for f in (session_file, session_file + "-journal"):
        try:
            if os.path.exists(f):
                os.remove(f)
        except OSError:
            pass
    print("Session cleared. Now edit .env with the new account, then: py -m app.scraper.login")


if __name__ == "__main__":
    asyncio.run(main())
