"""A persistent Telegram scraper: keeps the Telethon client connected across scrape cycles,
in its own thread + event loop. The scheduler starts it once so short intervals stay cheap
(no reconnect per run). Thread-safe: scrape requests are marshalled onto the worker's loop."""
import asyncio
import threading

from .. import config


class ScraperWorker:
    def __init__(self):
        self._loop = None
        self._client = None
        self._thread = None
        self._ready = threading.Event()
        self._error = None

    def start(self, timeout: int = 60) -> bool:
        if self._thread:
            return self._client is not None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout)
        if self._error:
            raise self._error
        return self._client is not None

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect())
        except Exception as exc:  # surface to start()
            self._error = exc
            self._ready.set()
            return
        self._ready.set()
        self._loop.run_forever()

    async def _connect(self):
        from telethon import TelegramClient
        self._client = TelegramClient(
            config.TG_SESSION, int(config.TELEGRAM_API_ID), config.TELEGRAM_API_HASH)
        await self._client.connect()
        if not await self._client.is_user_authorized():
            raise RuntimeError("Telegram userbot not logged in — run: py -m app.scraper.login")

    def fetch(self, specs: list[dict]) -> list[dict]:
        from .telethon_client import collect
        fut = asyncio.run_coroutine_threadsafe(collect(self._client, specs), self._loop)
        return fut.result(180)
