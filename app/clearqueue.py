"""Clear the scraped-message queue and reset scrape cursors, so the next pipeline run starts
FRESH — it re-scrapes only the recent window (scrape_hours_back). Run with the app stopped:

    py -m app.clearqueue
"""
import asyncio

from sqlalchemy import text, update

from .db import init_db, SessionLocal
from .models import Group


async def main():
    await init_db()
    async with SessionLocal() as s:
        await s.execute(text("DELETE FROM raw_messages"))
        await s.execute(update(Group).values(last_msg_id=None))
        await s.commit()
    print("Queue cleared + scrape cursors reset.")
    print("Next 'Run pipeline now' will scrape only the recent window and parse those.")


if __name__ == "__main__":
    asyncio.run(main())
