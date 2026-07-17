"""Reset raw messages that were stored but failed to parse (no load created), so the next
pipeline run re-parses them with the current parser/schema.

    py -m app.reprocess

Run it with the web app stopped, then start the app and click 'Run pipeline now'.
"""
import asyncio
from sqlalchemy import select

from .db import init_db, SessionLocal
from .models import RawMessage, Load


async def main():
    await init_db()
    async with SessionLocal() as s:
        loads = (await s.execute(select(Load))).scalars().all()
        parsed_raw_ids = {l.raw_message_id for l in loads if l.raw_message_id is not None}
        raws = (await s.execute(select(RawMessage))).scalars().all()
        n = 0
        for r in raws:
            if r.processed and r.id not in parsed_raw_ids:
                r.processed = False
                n += 1
        await s.commit()
    print(f"Reset {n} unparsed message(s). Start the app and click 'Run pipeline now' to re-parse them.")


if __name__ == "__main__":
    asyncio.run(main())
