"""One-time Telegram userbot login. Run ONCE in a terminal:
    py -m app.scraper.login
It asks for the login code Telegram sends you (and your 2FA password if set), then saves
a session file (sarbon_session.session). After that, the web app's 'Run pipeline now' can
scrape without any prompts."""
import asyncio
from .. import config


async def main():
    if not (config.TELEGRAM_API_ID and config.TELEGRAM_API_HASH and config.TELEGRAM_PHONE):
        raise SystemExit("Set TELEGRAM_API_ID, TELEGRAM_API_HASH and TELEGRAM_PHONE in .env first.")
    from telethon import TelegramClient
    client = TelegramClient("sarbon_session", int(config.TELEGRAM_API_ID), config.TELEGRAM_API_HASH)
    await client.start(phone=config.TELEGRAM_PHONE)
    me = await client.get_me()
    uname = f"@{me.username}" if me.username else me.first_name
    print(f"\n✅ Logged in as {uname}. Session saved as sarbon_session.session")
    print("You can now scrape from the web app (Run pipeline now).")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
