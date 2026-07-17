"""One-time cleanup after the schema upgrade. Run with the web app + bot STOPPED:

    py -m app.reset

It: (1) migrates the DB to the new columns, (2) removes the old demo/sample loads,
(3) keeps your parser provider, and (4) re-queues every scraped message so it gets
re-parsed with the new multi-load schema. Then start the app and run the pipeline."""
import asyncio

from sqlalchemy import select, text, update

from .db import init_db, SessionLocal
from .models import RawMessage, Setting


async def main():
    await init_db()  # also adds the new columns (truck_count, comment)
    async with SessionLocal() as s:
        await s.execute(text("DELETE FROM loads WHERE source_group <> 'bot'"))
        # NOTE: we intentionally do NOT change parser_provider — keep whatever you selected.
        await s.execute(update(RawMessage).values(processed=False, parse_attempts=0))
        await s.commit()
        queued = len((await s.execute(select(RawMessage))).scalars().all())
    print(f"Reset done: sample loads removed, {queued} messages queued to parse.")
    print("Now: start the web app and click 'Run pipeline now' (it runs in the background).")


if __name__ == "__main__":
    asyncio.run(main())
