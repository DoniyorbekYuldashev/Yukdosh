"""Orchestrates the pipeline: fetch raw messages -> parse (in parallel) -> filter junk ->
normalize -> dedup -> store. Driven by the dynamic settings/groups in the DB."""
import asyncio
import hashlib
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, delete, update

from .db import SessionLocal
from .models import Group, Setting, RawMessage, Load
from .parser.factory import get_parser
from .parser.dedup import dedup_hash
from .parser.normalize import canonicalize_trucks
from .parser.geo import has_known_place
from .scraper import telethon_client
from . import config

DEDUP_WINDOW_HOURS = 24    # collapse repeats of the same load within this window
PARSE_CONCURRENCY = 5      # how many messages to parse at once
MAX_PARSE_PER_RUN = 200    # parse newest N queued messages per run (prioritise fresh loads)
BATCH_SIZE = 10            # messages packed into ONE API call -> 10x fewer requests (RPD limits)

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


_TON_RE = re.compile(r"\d+\s*(t|т|ton|тон|tonna|kg|кг|kub|куб|m3|м3)", re.I)


def _looks_like_load(text: str) -> bool:
    """Cheap LOCAL check before spending an API call: does this message plausibly contain a
    freight load? Real posts carry a phone, a known place, a truck word or a tonnage.
    Group chatter ('ok', 'bormi', 'rahmat') has none — and never costs a call."""
    if not text or not text.strip():
        return False
    if _extract_phones(text):
        return True
    if canonicalize_trucks(text):
        return True
    if _TON_RE.search(text):
        return True
    return has_known_place(text)


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


_PHONE_CAND = re.compile(r"\+?\d[\d\s\-()]{6,}\d")


def _mask_phones(text: str) -> str:
    """Remove phone numbers from text BEFORE it is sent to any external API (privacy /
    data-minimization). A phone = a +-prefixed run, or 9+ digits (phones are 9-12; prices/
    weights are shorter, so they survive). The real number is re-attached locally afterwards."""
    def repl(m):
        s = m.group(0)
        digits = re.sub(r"\D", "", s)
        if s.strip().startswith("+") or len(digits) >= 9:
            return " "          # looks like a phone -> strip it
        return s                # short number (price/weight/count) -> keep
    return _PHONE_CAND.sub(repl, text or "")


def _reattach_phones(loads, raw_text: str) -> None:
    """Put the REAL phone back after masking. Overwrite with the number(s) extracted locally
    from the ORIGINAL text WHEN we find them (the 99% normal case) — otherwise leave whatever
    the model returned. So a normal phone is masked-then-restored, and an unusual format that
    the regex can't parse falls back to the model instead of becoming an EMPTY cell."""
    real = _extract_phones(raw_text)
    if not real:
        return  # nothing regex-detectable -> keep model's value (never blank it out)
    joined = ", ".join(dict.fromkeys(p.strip() for p in real[:2]))
    for pl in loads:
        pl.contact_phone = joined


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


def _fill_truck_from_text(loads, raw_text: str) -> None:
    """If a single-load message names a truck (e.g. 'isuzu kerak', 'tent') but the model left
    truck_type empty, recover it from the message text. Single-load only, to avoid mixing
    truck types across different directions in a multi-load post."""
    if len(loads) != 1:
        return
    pl = loads[0]
    if (pl.truck_type or "").strip():
        return
    t = canonicalize_trucks(raw_text)
    if t:
        pl.truck_type = t


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
            if _looks_like_junk(r.text) or not _looks_like_load(r.text):
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

        async def _parse_group(raws):
            """One API call for up to BATCH_SIZE messages."""
            async with sem:
                try:
                    batched = await loop.run_in_executor(
                        None, parser.parse_batch, [_mask_phones(r.text) for r in raws])
                    return [(r, batched[i] if i < len(batched) else [], None)
                            for i, r in enumerate(raws)]
                except Exception as exc:
                    return [(r, None, exc) for r in raws]

        # Parse in small chunks with a CIRCUIT BREAKER: if a whole chunk fails (dead key,
        # exhausted quota, hard rate limit) stop the run instead of firing hundreds of
        # doomed calls every cycle.
        groups = [to_parse[i:i + BATCH_SIZE] for i in range(0, len(to_parse), BATCH_SIZE)]
        results = []
        api_error = ""
        api_calls = 0
        for _i in range(0, len(groups), 2):          # 2 batched calls per wave
            _wave = groups[_i:_i + 2]
            _out = await asyncio.gather(*[_parse_group(g) for g in _wave])
            api_calls += len(_wave)
            _res = [item for sub in _out for item in sub]
            results.extend(_res)
            _errs = [e for _, _, e in _res if e is not None]
            if _errs and len(_errs) == len(_res):
                api_error = str(_errs[0])
                _low = api_error.lower()
                if "insufficient_quota" in _low or "exceeded your current quota" in _low:
                    print("[pipeline] STOPPED: API QUOTA EXHAUSTED — add credit or switch "
                          f"provider in Settings.\n           {api_error[:300]}")
                else:
                    print(f"[pipeline] STOPPED: every call failed — {api_error[:300]}")
                break

        # 4) Dedup + store (DB work stays sequential to avoid write contention).
        parsed, deduped, skipped_junk, rate_limited = 0, 0, 0, 0
        window_start = datetime.now(timezone.utc) - timedelta(hours=DEDUP_WINDOW_HOURS)

        for raw, loads, err in results:
            if err is not None:
                emsg = str(err)
                if "429" in emsg or "rate_limit" in emsg.lower() or "quota" in emsg.lower():
                    # transient limit — leave unprocessed so it retries next run (no data loss)
                    rate_limited += 1
                    continue
                raw.parse_attempts = (raw.parse_attempts or 0) + 1
                if raw.parse_attempts >= 3:
                    raw.processed = True  # give up after 3 real failures
                print(f"[pipeline] parse failed on msg {raw.id} (try {raw.parse_attempts}): {err}")
                continue
            raw.processed = True
            _reattach_phones(loads, raw.text)     # real phone (masked before API) re-attached; never blank
            _fill_truck_from_text(loads, raw.text)   # recover 'isuzu kerak' etc. into truck_type
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

        if rate_limited:
            print(f"[pipeline] {rate_limited} messages hit the API limit — will retry next run")

        # retention: old loads are long taken — delete them and their raw messages (0 = keep all)
        retention = settings.get("load_retention_days", "5")
        retention_days = int(retention) if str(retention).isdigit() else 5
        if retention_days > 0:
            prune_before = datetime.now(timezone.utc) - timedelta(days=retention_days)
            await s.execute(delete(Load).where(Load.posted_at < prune_before)
                            .execution_options(synchronize_session=False))
            _stale = select(RawMessage.id).where(
                RawMessage.processed == True,  # noqa: E712
                RawMessage.posted_at < prune_before)
            # loads point at raw_messages — unlink first (Postgres enforces the FK)
            await s.execute(update(Load).where(Load.raw_message_id.in_(_stale))
                            .values(raw_message_id=None).execution_options(synchronize_session=False))
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
        "api_calls": api_calls,                     # API REQUESTS made (batched)
        "prefiltered_junk": prefiltered_junk,       # skipped the model (noise)
        "duplicate_texts_skipped": duplicate_texts, # skipped the model (identical reposts)
        "rate_limited": rate_limited,
        "api_error": api_error[:300],
        "window": {"max_messages": global_max, "hours_back": global_hours},
    }
