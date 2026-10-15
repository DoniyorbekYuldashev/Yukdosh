"""Push new matching loads to drivers who saved a route. Called by the scheduler after each
scrape. A load matches a subscription if origin, destination (hierarchy-aware) and the
optional truck type fit."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import defer

from .db import SessionLocal
from .models import Load, Subscription, Setting
from .bot.formatting import format_load, original_kb
from .bot.i18n import t, get_lang
from .parser.geo import location_match

MAX_PER_DRIVER = 10   # cap notifications per driver per run (avoid flooding)


def _norm(x):
    return (x or "").strip().lower()


def _matches(sub, load) -> bool:
    if sub.origin and not location_match(load.origin_city, sub.origin):
        return False
    if sub.destination and not location_match(load.destination_city, sub.destination):
        return False
    if sub.truck_type:
        lt = [t.strip().lower() for t in (load.truck_type or "").split(",") if t.strip()]
        if lt and _norm(sub.truck_type) not in lt:  # load specifies types & driver's isn't one
            return False
    return True


async def _active_hours(s) -> int:
    row = (await s.execute(select(Setting).where(Setting.key == "load_active_hours"))).scalar_one_or_none()
    return int(row.value) if row and str(row.value).isdigit() else 12


async def notify_new_loads(bot) -> int:
    """Send unnotified fresh loads to matching drivers. Returns messages sent."""
    sent = 0
    async with SessionLocal() as s:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=await _active_hours(s))
        new_loads = (await s.execute(
            select(Load).options(defer(Load.raw_text)).where(
                Load.notified == False, Load.is_load == True,          # noqa: E712
                Load.listing_type != "goods", Load.posted_at >= cutoff)
            .order_by(Load.posted_at)
        )).scalars().all()
        subs = (await s.execute(
            select(Subscription).where(Subscription.active == True))).scalars().all()  # noqa: E712

        per_driver = {}
        for load in new_loads:
            matched = {sub.tg_user_id for sub in subs if _matches(sub, load)}
            for uid in matched:
                if per_driver.get(uid, 0) >= MAX_PER_DRIVER:
                    continue
                try:
                    ulang = await get_lang(uid)
                    await bot.send_message(int(uid), t(ulang, "notify_new") + format_load(load, ulang),
                                           reply_markup=original_kb([load], ulang))
                    per_driver[uid] = per_driver.get(uid, 0) + 1
                    sent += 1
                except Exception as exc:
                    print(f"[notify] send to {uid} failed: {exc}")
            load.notified = True
        await s.commit()
    return sent
