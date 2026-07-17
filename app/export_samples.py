"""Dump scraped raw messages to data/real_samples.jsonl so you can review them and copy
the good ones (with corrected JSON) into data/few_shot.jsonl to teach the parser.

    py -m app.export_samples            # export all raw messages
    py -m app.export_samples 100        # export the latest 100
"""
import asyncio
import json
import sys

from sqlalchemy import select, desc

from .db import init_db, SessionLocal
from .models import RawMessage
from . import config


async def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
    await init_db()
    async with SessionLocal() as s:
        q = select(RawMessage).order_by(desc(RawMessage.posted_at))
        if limit:
            q = q.limit(limit)
        rows = (await s.execute(q)).scalars().all()

    out_path = config.BASE_DIR / "data" / "real_samples.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({
                "id": r.id, "source_group": r.source_group,
                "posted_at": r.posted_at.isoformat() if r.posted_at else "",
                "text": r.text,
            }, ensure_ascii=False) + "\n")
    print(f"Exported {len(rows)} messages -> {out_path}")
    print("Review them, then add tricky ones (with corrected JSON) to data/few_shot.jsonl.")


if __name__ == "__main__":
    asyncio.run(main())
