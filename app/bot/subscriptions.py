"""Driver saved-route subscriptions: add / list / delete, canonicalized like search."""
from sqlalchemy import select

from ..db import SessionLocal
from ..models import Subscription
from ..parser.normalize import canonical_city, canonical_truck


async def add_subscription(uid, origin: str, destination: str, truck_type: str = "") -> int:
    oc = canonical_city(origin)[0] if origin.strip() else ""
    dc = canonical_city(destination)[0] if destination.strip() else ""
    tt = canonical_truck(truck_type) if truck_type.strip() else ""
    if tt == "other":
        tt = ""
    async with SessionLocal() as s:
        sub = Subscription(tg_user_id=str(uid), origin=oc, destination=dc, truck_type=tt, active=True)
        s.add(sub)
        await s.commit()
        await s.refresh(sub)
        return sub.id


async def list_subscriptions(uid):
    async with SessionLocal() as s:
        return (await s.execute(
            select(Subscription).where(
                Subscription.tg_user_id == str(uid), Subscription.active == True)  # noqa: E712
            .order_by(Subscription.id)
        )).scalars().all()


async def delete_subscription(sub_id: int, uid) -> bool:
    async with SessionLocal() as s:
        sub = (await s.execute(select(Subscription).where(
            Subscription.id == sub_id, Subscription.tg_user_id == str(uid)))).scalar_one_or_none()
        if sub:
            sub.active = False
            await s.commit()
            return True
        return False
