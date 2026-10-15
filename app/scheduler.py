"""Background auto-scraper. Runs the pipeline on a timer while enabled in Settings.

    py -m app.scheduler

Reads settings fresh each cycle, so toggling it on/off or changing the interval in the web
UI takes effect without a restart."""
import asyncio

from sqlalchemy import select

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from .broadcast import post_to_groups
from .config import BOT_TOKEN
from .db import init_db, SessionLocal
from .notify import notify_new_loads
from .models import Setting
from .pipeline import run_pipeline
from .scraper import telethon_client
from .scraper.worker import ScraperWorker


async def _get(key: str, default: str) -> str:
    async with SessionLocal() as s:
        row = (await s.execute(select(Setting).where(Setting.key == key))).scalar_one_or_none()
        return row.value if row else default


async def main():
    await init_db()
    # Keep one persistent Telegram connection for the scheduler's lifetime (efficient for
    # short intervals). Falls back to per-run connect if this fails.
    if telethon_client._credentials_ready():
        try:
            w = ScraperWorker()
            if w.start():
                telethon_client.use_persistent(w)
                print("[scheduler] persistent Telegram connection established")
        except Exception as exc:
            print(f"[scheduler] persistent connect failed ({exc}); using per-run scraping")
    notif_bot = None
    if BOT_TOKEN:
        notif_bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        print("[scheduler] notifications enabled (matching loads -> drivers' saved routes)")
    print("Yukdosh scheduler running. Enable it in Settings (scheduler on/off + interval).")
    while True:
        enabled = (await _get("scheduler_enabled", "false")).strip().lower() in ("1", "true", "yes", "on")
        interval = int((await _get("scheduler_interval_minutes", "10")) or 10)
        if enabled:
            try:
                st = await run_pipeline()
                saved = st.get('prefiltered_junk', 0) + st.get('duplicate_texts_skipped', 0)
                msg = (f"[scheduler] [{st.get('provider','?')}] +{st['loads_created']} loads, {st['new_raw_messages']} new msgs, "
                       f"{st['junk_skipped']} junk skipped, {st.get('api_calls', 0)} model calls "
                       f"({saved} calls saved: noise+reposts)")
                if st.get("api_error"):
                    msg += f"\n           ⚠ API: {st['api_error']}"
                if notif_bot:
                    sent = await notify_new_loads(notif_bot)
                    msg += f", {sent} notifications sent"
                print(msg)
            except Exception as exc:
                print(f"[scheduler] pipeline error: {exc}")
            if notif_bot:
                try:
                    posts = await post_to_groups(notif_bot)
                    if posts:
                        print(f"[scheduler] {posts} group post(s) sent")
                except Exception as exc:
                    print(f"[scheduler] group posting error: {exc}")
            await asyncio.sleep(max(1, interval) * 60)
        else:
            await asyncio.sleep(15)  # idle: re-check the toggle every 15s


if __name__ == "__main__":
    asyncio.run(main())
