"""Driver/seller/buyer DB queries over the parsed listings. Shared with the web app's DB.

Search matches the driver's typed place through the geo hierarchy (country > region > district)
and an optional truck-type filter, and only returns loads within the freshness window
(load_active_hours) so drivers see current loads."""
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, desc, or_, func
from sqlalchemy.orm import defer

from ..db import SessionLocal
from ..models import Load, Setting
from ..parser.dedup import dedup_hash
from ..parser.normalize import canonical_city, canonicalize_trucks
from ..parser.geo import location_match
from ..schemas import ParsedLoad
from .clean import clean_original


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _truck_ok(load_trucks: str, want: str) -> bool:
    """Truck-type filter. Driver picked no type -> all loads. Load's type unspecified -> shown
    to everyone. Otherwise the driver's chosen type must be among the load's accepted types."""
    w = canonicalize_trucks(want)
    if not w:
        return True
    have = [t.strip() for t in (load_trucks or "").split(",") if t.strip()]
    if not have:
        return True
    wants = set(w.split(", "))
    return any(t in wants for t in have)


async def _active_cutoff(s):
    """Datetime before which loads are considered stale (load_active_hours setting)."""
    row = (await s.execute(select(Setting).where(Setting.key == "load_active_hours"))).scalar_one_or_none()
    hours = int(row.value) if row and str(row.value).isdigit() else 12
    if hours <= 0:
        return None
    return datetime.now(timezone.utc) - timedelta(hours=hours)


async def search_loads(origin: str = "", destination: str = "", truck_type: str = "",
                       limit: int = 10, offset: int = 0):
    async with SessionLocal() as s:
        # cards never show the original post text — skip it, it's most of each row's bytes
        q = (select(Load).options(defer(Load.raw_text))
             .where(Load.is_load == True, Load.listing_type != "goods"))  # noqa: E712
        cutoff = await _active_cutoff(s)
        if cutoff is not None:
            q = q.where(Load.posted_at >= cutoff)
        rows = (await s.execute(q.order_by(desc(Load.posted_at)))).scalars().all()
    # hierarchy-aware matching: region -> its districts, country -> everything, city -> fuzzy/cross-script
    if origin.strip():
        rows = [l for l in rows if location_match(l.origin_city, origin)]
    if destination.strip():
        rows = [l for l in rows if location_match(l.destination_city, destination)]
    if (truck_type or "").strip():
        rows = [l for l in rows if _truck_ok(l.truck_type, truck_type)]
    return rows[offset:offset + limit]


# What bot cards show about the source (admin → Settings → Bot cards). Group posts: never.
CARD_SOURCE_MODES = ("original", "link", "both", "none")
_mode_cache = {"value": "original", "at": -1e9}


async def card_source_mode() -> str:
    """'original' (📄 Asl matn button) | 'link' (🔗 E'lon manbasi) | 'both' | 'none'.
    Re-read every 30 s so an admin change applies without restarting the bot."""
    if time.monotonic() - _mode_cache["at"] > 30:
        async with SessionLocal() as s:
            row = (await s.execute(select(Setting).where(Setting.key == "card_source_mode"))).scalar_one_or_none()
        value = row.value if row and row.value in CARD_SOURCE_MODES else "original"
        _mode_cache.update(value=value, at=time.monotonic())
    return _mode_cache["value"]


async def card_options() -> tuple[bool, bool]:
    """(show the source link, show 📄 Asl matn buttons) for bot cards."""
    mode = await card_source_mode()
    return mode in ("link", "both"), mode in ("original", "both")


async def original_text(load_id: int) -> str:
    """The scraped post behind a load, cleaned of source hints and ads. "" if gone/bot-posted."""
    async with SessionLocal() as s:
        row = (await s.execute(select(Load.raw_text, Load.source_group)
                               .where(Load.id == load_id))).first()
    if not row or row.source_group == "bot":
        return ""
    return clean_original(row.raw_text)[:3800]   # Telegram limit is 4096 incl. the title


async def _latest(where_clause, limit):
    async with SessionLocal() as s:
        q = select(Load).options(defer(Load.raw_text)).where(where_clause)
        cutoff = await _active_cutoff(s)
        if cutoff is not None:
            q = q.where(Load.posted_at >= cutoff)
        q = q.order_by(desc(Load.posted_at)).limit(limit)
        return (await s.execute(q)).scalars().all()


async def latest_loads(limit: int = 10):
    return await _latest((Load.is_load == True) & (Load.listing_type != "goods"), limit)  # noqa: E712


async def latest_trucks(limit: int = 10):
    return await _latest(Load.is_load == False, limit)  # noqa: E712


async def browse_goods(limit: int = 10):
    return await _latest(Load.listing_type == "goods", limit)


async def insert_listing(data: dict, listing_type: str, posted_by_tg: str) -> int:
    """Save a first-party listing posted through the bot. Returns the new load id."""
    pl = ParsedLoad(
        is_load=(listing_type != "truck"),
        cargo_type=data.get("cargo", ""),
        weight_tons=data.get("weight"),
        truck_type=data.get("truck_type", ""),
        price_amount=data.get("price"),
        price_currency=data.get("currency", ""),
        contact_phone=data.get("phone", ""),
        contact_name=data.get("name", ""),
    )
    oc, oreg = canonical_city(data.get("origin", ""))
    dc, dreg = canonical_city(data.get("destination", ""))
    async with SessionLocal() as s:
        load = Load(
            is_load=pl.is_load, listing_type=listing_type,
            origin_city=oc, origin_region=oreg,
            destination_city=dc, destination_region=dreg,
            cargo_type=pl.cargo_type, weight_tons=pl.weight_tons,
            truck_type=pl.truck_type, price_amount=pl.price_amount, price_currency=pl.price_currency,
            contact_phone=pl.contact_phone, contact_name=pl.contact_name,
            parser_provider="bot", dedup_hash=dedup_hash(pl),
            source_group="bot", posted_by_tg=str(posted_by_tg),
            raw_text=data.get("cargo", ""),
        )
        s.add(load)
        await s.commit()
        await s.refresh(load)
        return load.id
