"""Bot usage tracking: who started the bot, when, and how active they are."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func

from .db import SessionLocal
from .models import BotUser


async def record_user(u) -> None:
    """Upsert a bot user on every interaction (first_seen once, last_seen + actions each time)."""
    if u is None:
        return
    now = datetime.now(timezone.utc)
    async with SessionLocal() as s:
        row = await s.get(BotUser, str(u.id))
        if row:
            row.last_seen = now
            row.actions = (row.actions or 0) + 1
            if getattr(u, "username", None):
                row.username = u.username
        else:
            s.add(BotUser(
                tg_user_id=str(u.id),
                username=getattr(u, "username", "") or "",
                first_name=getattr(u, "first_name", "") or "",
                language=getattr(u, "language_code", "") or "",
                actions=1, first_seen=now, last_seen=now,
            ))
        await s.commit()


async def get_stats() -> dict:
    now = datetime.now(timezone.utc)
    d1, d7 = now - timedelta(hours=24), now - timedelta(days=7)

    def _count(where=None):
        q = select(func.count()).select_from(BotUser)
        return q if where is None else q.where(where)

    async with SessionLocal() as s:
        total = (await s.execute(_count())).scalar_one()
        new1 = (await s.execute(_count(BotUser.first_seen >= d1))).scalar_one()
        new7 = (await s.execute(_count(BotUser.first_seen >= d7))).scalar_one()
        act1 = (await s.execute(_count(BotUser.last_seen >= d1))).scalar_one()
        act7 = (await s.execute(_count(BotUser.last_seen >= d7))).scalar_one()
        recent = (await s.execute(
            select(BotUser).order_by(BotUser.last_seen.desc()).limit(200))).scalars().all()
    return {"total": total, "new1": new1, "new7": new7, "act1": act1, "act7": act7, "recent": recent}
