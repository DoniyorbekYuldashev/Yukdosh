"""Orchestrates the pipeline: fetch raw messages -> parse (in parallel) -> filter junk ->
normalize -> dedup -> store. Driven by the dynamic settings/groups in the DB."""
import asyncio
import hashlib
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, delete

from .db import SessionLocal
from .models import Group, Setting, RawMessage, Load
from .parser.factory import get_parser
from .parser.dedup import dedup_hash
from .scraper import telethon_client
from . import config

DEDUP_WINDOW_HOURS = 24    # collapse repeats of the same load within this window
PARSE_CONCURRENCY = 5      # how many messages to parse at once
RAW_RETENTION_DAYS = 14    # delete already-parsed raw messages older than this (keeps DB lean)
MAX_PARSE_PER_RUN = 200    # parse newest N queued messages per run (prioritise fresh loads)

_NOISE_RE = re.compile(r"https?://\S+|t\.me/\S+|@\w+")


async def _load_settings(session) -> dict:
    rows = (await session.execute(select(Setting))).scalars().all()
    return {r.key: r.value for r in rows}


def _text_signal(text: str) -> str:
    """Message reduced to its letters+digits (urls/mentions/emoji/punct stripped), lowercased.
    Used to detect empty noise and to collapse byte-identical reposts."""
    stripped = _NOISE_RE.sub(" ", text or "")
    return re.sub(r"[^0-9a-zA-Zа-яА-ЯёЁ]+", "", stripped).lower()


def _looks_like_junk(text: str) -> bool:
    """Conservative pre-filter — only True when the message clearly CANNOT be a load, so we
    skip the API call for it. Real loads carry cities (+usually a phone) = lots of alnum chars,
    so they always pass. Kills stickers, lone emoji, and link-only / mention-only forwards."""
    if not text or not text.strip():
        return True
    return len(_text_signal(text)) < 4


def _dedup_key(text: str) -> str:
    return hashlib.md5(_text_signal(text).encode("utf-8")).hexdigest()


def _is_meaningful(pl) -> bool:
    """A valid load must have a route: BOTH From and Destination (always present in real posts).
    Ads / greetings / bad parses lacking a route are skipped."""
    return bool(pl.origin_city and pl.destination_city)


_PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{6,}\d")


def _extract_phones(text: str) -> list[str]:
    """Pull phone-like numbers from the raw message (7-15 digits)."""
    out = []
    for c in _PHONE_RE.findall(text or ""):
        if 7 <= len(re.sub(r"\D", "", c)) <= 15:
            c = c.strip()
            if c not in out:
                out.append(c)
    return out


def _fill_shared_phone(loads, raw_text: str) -> None:
    """Multi-direction posts list the phone ONCE (usually at the end) for ALL loads.
    Any load the model left without a phone inherits the message's shared number(s)."""
    present = [pl.contact_phone.strip() for pl in loads if (pl.contact_phone or "").strip()]
    fallback = ", ".join(dict.fromkeys(present)) if present else ", ".join(_extract_phones(raw_text)[:2])
    if not fallback:
        return
    for pl in loads:
        if not (pl.contact_phone or "").strip():
            pl.contact_phone = fallback


async def run_pipeline() -> dict:
    """Run one full ingestion+parse pass. Returns stats for the UI."""
    async with SessionLocal() as s:
        settings = await _load_settings(s)
        global_max = int(settings.get("scrape_max_messages", "50") or 50)
        global_hours = int(settings.get("scrape_hours_back", "24") or 24)
        provider = settings.get("parser_provider", "gemini")
        gemini_key = settings.get("gemini_api_key", "") or config.GEMINI_API_KEY
        openai_key = settings.get("openai_api_key", "") or config.OPENAI_API_KEY
        if provider in ("", "mock") and gemini_key:
            provider = "gemini"
        elif provider in ("", "mock") and openai_key:
            provider = "openai"

        groups = (await s.execute(
            select(Group).where(Group.enabled == True)  # noqa: E712
        )).scalars().all()
        specs = [{
            "link": g.link,
            "max_messages": g.max_messages if g.max_messages is not None else global_max,
            "hours_back": g.hours_back if g.hours_back is not None else global_hours,
            "last_msg_id": g.last_msg_id,
        } for g in groups]

        # 1) Fetch raw messages (real Telegram or offline sample data).
        messages = telethon_client.fetch_messages(specs)

        # 2) Store new raw messages (skip ones we already have).
        new_raw = 0
        for m in messages:
            exists = (await s.execute(
                select(RawMessage).where(
                    RawMessage.source_group == m["source_group"],
                    RawMessage.source_msg_id == m["source_msg_id"],
                )
            )).scalar_one_or_none()
            if exists:
                continue
            s.add(RawMessage(
                source_group=m["source_group"], source_msg_id=m["source_msg_id"],
                sender=m["sender"], text=m["text"], posted_at=m["posted_at"],
            ))
            new_raw += 1

        # advance the incremental scrape cursor (max message id seen) per group
        by_link = {g.link: g for g in groups}
        max_seen: dict[str, int] = {}
        for m in messages:
            mid = m.get("msg_id")
            if mid is not None:
                max_seen[m["source_group"]] = max(max_seen.get(m["source_group"], 0), mid)
        for link, mid in max_seen.items():
            g = by_link.get(link)
            if g and (g.last_msg_id is None or mid > g.last_msg_id):
                g.last_msg_id = mid
        await s.commit()

        # 3) Parse unprocessed raw messages — CONCURRENTLY (bounded).
        parser = get_parser(provider, gemini_key, openai_key)
        unprocessed = (await s.execute(
            select(RawMessage).where(RawMessage.processed == False)  # noqa: E712
            .order_by(RawMessage.posted_at.desc()).limit(MAX_PARSE_PER_RUN)
        )).scalars().all()

        # 3a) Token savers BEFORE any API call (lossless):
        #  - drop obvious noise (stickers/links/emoji) with a conservative filter
        #  - collapse byte-identical reposts so we parse each unique text only ONCE
        prefiltered_junk = 0
        by_text: dict[str, list] = {}
        for r in unprocessed:
            if _looks_like_junk(r.text):
                r.processed = True
                prefiltered_junk += 1
                continue
            by_text.setdefault(_dedup_key(r.text), []).append(r)

        to_parse = []          # one representative per unique text
        duplicate_texts = 0
        for grp in by_text.values():
            to_parse.append(grp[0])
            for dup in grp[1:]:  # identical repost — the representative yields the load
                dup.processed = True
                duplicate_texts += 1

        loop = asyncio.get_event_loop()
        sem = asyncio.Semaphore(PARSE_CONCURRENCY)

        async def _parse(raw):
            async with sem:
                try:
                    pl = await loop.run_in_executor(None, parser.parse, raw.text)
                    return raw, pl, None
                except Exception as exc:
                    return raw, None, exc

        results = await asyncio.gather(*[_parse(r) for r in to_parse]) if to_parse else []

        # 4) Dedup + store (DB work stays sequential to avoid write contention).
        parsed, deduped, skipped_junk = 0, 0, 0
        window_start = datetime.now(timezone.utc) - timedelta(hours=DEDUP_WINDOW_HOURS)

        for raw, loads, err in results:
            if err is not None:
                emsg = str(err)
                if "429" in emsg or "rate_limit" in emsg.lower() or "quota" in emsg.lower():
                    # transient limit — leave unprocessed so it retries next run (no data loss)
                    print(f"[pipeline] rate-limited on msg {raw.id} — will retry")
                    continue
                raw.parse_attempts = (raw.parse_attempts or 0) + 1
                if raw.parse_attempts >= 3:
                    raw.processed = True  # give up after 3 real failures
                print(f"[pipeline] parse failed on msg {raw.id} (try {raw.parse_attempts}): {err}")
                continue
            raw.processed = True
            _fill_shared_phone(loads, raw.text)   # shared end-of-post number -> all directions
            meaningful = [pl for pl in loads if _is_meaningful(pl)]
            if not meaningful:
                skipped_junk += 1
                continue
            for pl in meaningful:  # one message can yield many loads
                h = dedup_hash(pl)
                recent_dupe = (await s.execute(
                    select(Load).where(Load.dedup_hash == h, Load.posted_at >= window_start)
                )).scalar_one_or_none()
                if recent_dupe:
                    deduped += 1
                    continue
                s.add(Load(
                    is_load=pl.is_load,
                    origin_city=pl.origin_city, origin_region=pl.origin_region,
                    destination_city=pl.destination_city, destination_region=pl.destination_region,
                    cargo_type=pl.cargo_type, weight_tons=pl.weight_tons, volume_m3=pl.volume_m3,
                    truck_type=pl.truck_type, truck_count=pl.truck_count,
                    price_amount=pl.price_amount, price_currency=pl.price_currency,
                    loading_date=pl.loading_date, contact_phone=pl.contact_phone, contact_name=pl.contact_name,
                    comment=pl.comment, language_detected=pl.language_detected,
                    parser_provider=parser.name, dedup_hash=h,
                    source_group=raw.source_group, source_msg_id=raw.source_msg_id,
                    poster_username=raw.sender or "",
                    raw_text=raw.text, posted_at=raw.posted_at, raw_message_id=raw.id,
                ))
                parsed += 1

        # prune old, already-processed raw messages so the DB stays lean on active groups
        prune_before = datetime.now(timezone.utc) - timedelta(days=RAW_RETENTION_DAYS)
        await s.execute(delete(RawMessage).where(
            RawMessage.processed == True,  # noqa: E712
            RawMessage.posted_at < prune_before).execution_options(synchronize_session=False))

        await s.commit()

    return {
        "provider": parser.name,
        "groups_scanned": len(specs),
        "new_raw_messages": new_raw,
        "loads_created": parsed,
        "duplicates_skipped": deduped,
        "junk_skipped": skipped_junk + prefiltered_junk,
        "api_calls": len(to_parse),                 # messages actually sent to the model
        "prefiltered_junk": prefiltered_junk,       # skipped the model (noise)
        "duplicate_texts_skipped": duplicate_texts, # skipped the model (identical reposts)
        "window": {"max_messages": global_max, "hours_back": global_hours},
    }
