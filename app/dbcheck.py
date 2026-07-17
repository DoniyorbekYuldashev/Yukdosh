"""Verify the database schema — confirms every expected column exists (i.e. all migrations
are applied). Running it also APPLIES any missing migrations first. Run with the app stopped:

    py -m app.dbcheck
"""
import asyncio

from sqlalchemy import inspect

from .db import init_db, engine

EXPECTED = {
    "groups": ["max_messages", "hours_back", "last_msg_id"],
    "loads": ["listing_type", "posted_by_tg", "truck_count", "comment", "source_msg_id", "notified"],
    "subscriptions": ["tg_user_id", "origin", "destination", "truck_type", "active"],
    "raw_messages": ["processed"],
}


async def main():
    await init_db()  # applies any missing migrations first

    def _check(sync_conn):
        insp = inspect(sync_conn)
        all_ok = True
        for tbl, need in EXPECTED.items():
            cols = {c["name"] for c in insp.get_columns(tbl)}
            print(f"[{tbl}]")
            for c in need:
                ok = c in cols
                all_ok = all_ok and ok
                print(f"   {'OK      ' if ok else 'MISSING '} {c}")
        print("\nAll migrations applied." if all_ok else "\nSome columns were missing — now added.")

    async with engine.begin() as conn:
        await conn.run_sync(_check)


if __name__ == "__main__":
    asyncio.run(main())
