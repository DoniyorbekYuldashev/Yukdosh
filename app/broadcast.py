"""Post digests of fresh loads into Telegram groups/channels (admin → Settings → "Groups to post
loads to"). Called by the scheduler after each pipeline run.

Each target has its own interval, loads per post, route filter and language. A load is never
posted twice to the same target. Group cards omit the source link and end with a pointer to the
bot. The bot must be a member of each group allowed to send messages (an admin in channels)."""
import asyncio
from datetime import datetime, timedelta, timezone

from aiogram.types import LinkPreviewOptions
from sqlalchemy import select, desc
from sqlalchemy.orm import defer

from .db import SessionLocal
from .models import Load, PostTarget, PostedLoad
from .bot.formatting import format_load
from .bot.i18n import t
from .bot.queries import _active_cutoff, _truck_ok
from .parser.geo import location_match

MAX_LOADS_PER_POST = 10
_TG_LIMIT = 4000              # Telegram caps one message at 4096 characters
_SEP = "\n\n➖➖➖\n\n"
_bot_username = ""


def normalize_chat(raw: str) -> str:
    """'https://t.me/name' | 't.me/name' | 'name' | '@name' -> '@name'; numeric ids ('-100…') kept."""
    s = (raw or "").strip()
    for prefix in ("https://", "http://"):
        if s.startswith(prefix):
            s = s[len(prefix):]
    if s.startswith("t.me/"):
        s = s[len("t.me/"):]
    s = s.strip("/").split("/")[0].split("?")[0]
    if not s or s.lstrip("-").isdigit():
        return s
    return "@" + s.lstrip("@")


def _route_ok(load, target) -> bool:
    o, d = (target.origin or "").strip(), (target.destination or "").strip()
    if o and o != "-" and not location_match(load.origin_city, o):
        return False
    if d and d != "-" and not location_match(load.destination_city, d):
        return False
    return _truck_ok(load.truck_type, target.truck_type or "")


async def select_loads(s, target, cutoff, limit):
    """Newest active loads matching the target's filter that it hasn't received yet."""
    already = select(PostedLoad.load_id).where(PostedLoad.target_id == target.id)
    q = (select(Load).options(defer(Load.raw_text))
         .where(Load.is_load == True, Load.listing_type != "goods",  # noqa: E712
                Load.id.not_in(already))
         .order_by(desc(Load.posted_at)))
    if cutoff is not None:
        q = q.where(Load.posted_at >= cutoff)
    rows = (await s.execute(q)).scalars().all()
    return [l for l in rows if _route_ok(l, target)][:limit]


def build_post(loads, lang, bot_username=""):
    """Digest text + the loads that fit in one Telegram message."""
    header = f"<b>{t(lang, 'latest_title')}</b>"
    footer = t(lang, "group_post_footer", bot=bot_username) if bot_username else ""
    blocks, used = [], []
    for l in loads:
        block = format_load(l, lang, source=False)
        size = len(header) + len(footer) + len(_SEP.join(blocks + [block])) + 4
        if blocks and size > _TG_LIMIT:
            break
        blocks.append(block)
        used.append(l)
    text = header + "\n\n" + _SEP.join(blocks)
    if footer:
        text += "\n\n" + footer
    return text, used


async def post_to_groups(bot) -> int:
    """Send one digest to every enabled target that is due and has new matching loads."""
    global _bot_username
    if not _bot_username:
        try:
            _bot_username = "@" + (await bot.get_me()).username
        except Exception as exc:
            print(f"[broadcast] get_me failed: {exc}")
    sent = 0
    now = datetime.now(timezone.utc)
    async with SessionLocal() as s:
        targets = (await s.execute(
            select(PostTarget).where(PostTarget.enabled == True))).scalars().all()  # noqa: E712
        cutoff = await _active_cutoff(s)
        for tg in targets:
            last = tg.last_posted_at
            if last is not None and last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if last is not None and now - last < timedelta(minutes=max(1, tg.interval_minutes or 60)):
                continue
            limit = min(MAX_LOADS_PER_POST, max(1, tg.loads_per_post or 5))
            loads = await select_loads(s, tg, cutoff, limit)
            if not loads:
                continue
            text, used = build_post(loads, tg.lang or "uz", _bot_username)
            chat = int(tg.chat) if tg.chat.lstrip("-").isdigit() else tg.chat
            try:
                await bot.send_message(chat, text,
                                       link_preview_options=LinkPreviewOptions(is_disabled=True))
            except Exception as exc:
                # e.g. bot not in the group / no rights — show it in the admin, retry next interval
                tg.last_error = str(exc)[:300]
                tg.last_posted_at = now
                await s.commit()
                print(f"[broadcast] {tg.chat}: {exc}")
                continue
            for l in used:
                s.add(PostedLoad(target_id=tg.id, load_id=l.id))
            tg.last_posted_at = now
            tg.last_error = ""
            await s.commit()
            sent += 1
            await asyncio.sleep(1)
    return sent
