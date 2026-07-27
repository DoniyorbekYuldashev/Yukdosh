"""Clear the scraped-message queue and reset scrape cursors, so the next pipeline run starts
FRESH — it re-scrapes only the recent window (scrape_hours_back). Run with the app stopped:

    py -m app.clearqueue

Your parsed loads, drivers' saved routes, groups and settings are NOT touched.
"""
import asyncio

from sqlalchemy import text, update

from .db import init_db, SessionLocal
from .models import Group, Load


async def main():
    await init_db()
    async with SessionLocal() as s:
        # loads reference raw_messages via a foreign key — unlink first, otherwise Postgres
        # refuses the delete. Loads keep their own raw_text copy, so nothing is lost.
        await s.execute(update(Load).values(raw_message_id=None)
                        .execution_options(synchronize_session=False))
        await s.execute(text("DELETE FROM raw_messages"))
        await s.execute(update(Group).values(last_msg_id=None))
        await s.commit()
    print("Queue cleared + scrape cursors reset. Loads/routes/groups/settings kept.")
    print("Next run will scrape only the recent window and parse those.")


if __name__ == "__main__":
    asyncio.run(main())
