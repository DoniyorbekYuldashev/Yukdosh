"""See what's in the database and where it lives.

    py -m app.dbview            # where it is + table counts + last 15 loads
    py -m app.dbview loads 30   # last 30 loads
    py -m app.dbview raw 20     # last 20 raw (scraped) messages
    py -m app.dbview subs       # saved driver routes
"""
import asyncio
import sys

from sqlalchemy import select, func, desc

from .db import init_db, SessionLocal
from .models import Load, RawMessage, Group, Setting, Subscription
from . import config


def _short(x, n=22):
    x = str(x or "")
    return (x[:n] + "…") if len(x) > n else x


async def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "summary"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 15
    await init_db()

    kind = "SQLite file" if config.DATABASE_URL.startswith("sqlite") else "PostgreSQL"
    print(f"\nDATABASE: {kind}")
    print(f"  {config.DATABASE_URL}\n")

    async with SessionLocal() as s:
        if what in ("summary", "loads"):
            for tbl, model in [("loads", Load), ("raw_messages", RawMessage),
                               ("groups", Group), ("subscriptions", Subscription), ("settings", Setting)]:
                n = (await s.execute(select(func.count()).select_from(model))).scalar_one()
                print(f"  {tbl:14} {n} rows")
            print(f"\n--- last {limit} loads ---")
            rows = (await s.execute(select(Load).order_by(desc(Load.posted_at)).limit(limit))).scalars().all()
            for l in rows:
                src = "bot" if l.source_group == "bot" else l.source_group.replace("https://t.me/", "@")
                print(f"  #{l.id} {_short(l.origin_city,12)}→{_short(l.destination_city,12)} | "
                      f"{_short(l.cargo_type,14)} | {l.weight_tons or '-'}t | {_short(l.truck_type,8)} x{l.truck_count or '-'} | "
                      f"{_short(l.contact_phone,16)} | {l.posted_at:%m-%d %H:%M} | {src}")

        elif what == "raw":
            rows = (await s.execute(select(RawMessage).order_by(desc(RawMessage.posted_at)).limit(limit))).scalars().all()
            print(f"--- last {limit} raw messages ---")
            for r in rows:
                flag = "parsed" if r.processed else "queued"
                print(f"  #{r.id} [{flag}] {r.posted_at:%m-%d %H:%M} {r.source_group.replace('https://t.me/','@')}: {_short(r.text,70)}")

        elif what == "subs":
            rows = (await s.execute(select(Subscription).where(Subscription.active == True))).scalars().all()  # noqa: E712
            print("--- active saved routes ---")
            for sub in rows:
                print(f"  #{sub.id} user={sub.tg_user_id} {sub.origin or 'any'}→{sub.destination or 'any'} {sub.truck_type or ''}")


if __name__ == "__main__":
    asyncio.run(main())
