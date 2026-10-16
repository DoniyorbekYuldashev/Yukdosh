"""Render a structured load as a clean card for drivers, in the user's language."""
import re
from datetime import datetime, timezone, timedelta
from html import escape

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from ..parser.geo import flag_of
from .clean import strip_source
from .i18n import t, DEFAULT_LANG

TASHKENT = timezone(timedelta(hours=5))  # Uzbekistan time (UTC+5)

_CURRENCY_SYMBOL = {"UZS": "so'm", "RUB": "rub", "KZT": "tenge", "USD": "$"}
_TRUCK_KEYS = {
    "tent": "tk_tent", "ref": "tk_ref", "isotherm": "tk_isotherm",
    "flatbed": "tk_flatbed", "container": "tk_container", "dump": "tk_dump",
    "isuzu": "tk_isuzu", "paravoz": "tk_paravoz", "labo": "tk_labo", "other": "tk_other",
}


def _when(dt, lang):
    """Tashkent local time: 'Bugun 16:54' / 'Сегодня 16:54' / 'Бүгін 16:54'."""
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(TASHKENT)
    today = datetime.now(TASHKENT).date()
    if local.date() == today:
        day = t(lang, "today")
    elif local.date() == today - timedelta(days=1):
        day = t(lang, "yesterday")
    else:
        day = local.strftime("%d.%m")
    return f"{day} {local.strftime('%H:%M')}"


def _money(amount, currency, lang):
    if not amount:
        return t(lang, "price_none")
    cur = _CURRENCY_SYMBOL.get(currency, currency or "")
    return f"{amount:,.0f} {cur}".strip()


def _advance(value, lang):
    """'1000 USD' -> 'Avans: 1,000 $'; '30%' -> 'Avans: 30%'; 'yes' -> 'Avans bor'."""
    v = (value or "").strip()
    if not v:
        return ""
    if v == "yes":
        return t(lang, "advance_yes")
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([A-Z]{3})?", v)
    if m:
        v = _money(float(m.group(1)), m.group(2) or "", lang)
    return f"{t(lang, 'advance')}: {v}"


def _load_day(l, lang):
    """'ready' / 'today' / 'tomorrow' in the reader's language — today/tomorrow counted from the
    post time, so yesterday's "ertaga" shows as "Bugun"; real dates ("17.10") as written."""
    v = (getattr(l, "loading_date", "") or "").strip()
    if v == "ready":
        return t(lang, "date_ready")
    if v in ("today", "tomorrow"):
        base = l.posted_at or datetime.now(timezone.utc)
        if base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)
        day = base.astimezone(TASHKENT).date() + timedelta(days=1 if v == "tomorrow" else 0)
        today = datetime.now(TASHKENT).date()
        names = {today: "today", today + timedelta(days=1): "tomorrow", today - timedelta(days=1): "yesterday"}
        return t(lang, names[day]) if day in names else day.strftime("%d.%m")
    return v


def _truck_label(code, lang):
    code = (code or "").strip()
    key = _TRUCK_KEYS.get(code)
    return t(lang, key) if key else code


def _place(name):
    """'🇺🇿 Toshkent' — the country flag in front of a place we can place; just the name otherwise."""
    name = name or "?"
    flag = "" if any("🇦" <= ch <= "🇿" for ch in name) else flag_of(name)
    return f"{flag} {escape(name)}" if flag else escape(name)


def _num(num):
    return f"<b>{num}.</b> " if num else ""


def _post_link(l):
    sg = l.source_group or ""
    mid = getattr(l, "source_msg_id", "") or ""
    if sg.startswith("https://t.me/") and mid:
        return sg.rstrip("/") + "/" + str(mid)
    return ""


_USERNAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{3,31}")


def _tg_contact(l) -> str:
    """The poster's @username as a link — used ONLY when the load has no phone, so drivers can
    still reach the poster. Skipped for bots (other apps' forwarders) and for the group itself
    (anonymous admins post as the group — showing it would reveal the source)."""
    u = (getattr(l, "poster_username", "") or "").strip().lstrip("@")
    if not _USERNAME.fullmatch(u) or u.lower().endswith("bot"):
        return ""
    group = (l.source_group or "").rstrip("/").rsplit("/", 1)[-1].lstrip("@").lower()
    if u.lower() == group:
        return ""
    return f'<a href="https://t.me/{u}">@{u}</a>'


def has_original(l) -> bool:
    """Scraped loads keep the original post text; loads posted through the bot don't."""
    return (l.source_group or "") != "bot"


def _tail(l, lang):
    parts = []
    if l.posted_at:
        parts.append(f"🕒 {_when(l.posted_at, lang)}")
    if l.source_group == "bot":
        parts.append(t(lang, "via_bot"))
    return ("<i>" + " · ".join(parts) + "</i>") if parts else ""


def _common_tail(l, lines, lang, link=False):
    comment = strip_source(getattr(l, "comment", "")).strip(" ,;")
    if comment:
        lines.append(f"📝 {escape(comment)}")
    url = _post_link(l) if link else ""
    if url:
        lines.append(f'🔗 <a href="{escape(url)}">{t(lang, "source_link")}</a>')
    tail = _tail(l, lang)
    if tail:
        lines.append(tail)
    return "\n".join(lines)


def format_goods(l, lang=DEFAULT_LANG, num=None, link=False):
    lines = [f"{_num(num)}🛒 <b>{escape(l.cargo_type or t(lang, 'goods'))}</b>"]
    meta = []
    if l.weight_tons:
        meta.append(f"⚖️ {float(l.weight_tons):g} t")
    if l.origin_city:
        meta.append(f"📍 {escape(l.origin_city)}")
    if meta:
        lines.append(" · ".join(meta))
    lines.append(f"💰 {escape(_money(float(l.price_amount) if l.price_amount else None, l.price_currency, lang))}")
    if l.contact_phone:
        lines.append(f"📞 {escape(l.contact_phone)}")
    return _common_tail(l, lines, lang, link)


def format_load(l, lang=DEFAULT_LANG, num=None, link=False):
    """num numbers the card in a multi-card message (matches the 📄 N buttons);
    link=True adds the '🔗 E'lon manbasi' link (admin setting card_source_mode)."""
    if getattr(l, "listing_type", "load") == "goods":
        return format_goods(l, lang, num, link)
    head = "📦" if l.is_load else "🚛"
    lines = [f"{_num(num)}{head} <b>{_place(l.origin_city)} → {_place(l.destination_city)}</b>"]

    row = []
    if l.truck_type:
        parts = [_truck_label(x, lang) for x in l.truck_type.split(",") if x.strip()]
        label = ", ".join(parts)
        if getattr(l, "truck_count", None):
            label += f" ×{l.truck_count}"
        row.append(f"🚚 {escape(label)}")
    elif getattr(l, "truck_count", None):
        row.append(f"🚚 ×{l.truck_count}")
    size = []
    if l.weight_tons:
        size.append(f"{float(l.weight_tons):g} t")
    if getattr(l, "volume_m3", None):
        size.append(f"{float(l.volume_m3):g} m³")
    if size:
        row.append("⚖️ " + ", ".join(size))
    if row:
        lines.append(" · ".join(row))

    if l.cargo_type:
        lines.append(f"📦 {escape(l.cargo_type)}")
    day = _load_day(l, lang)
    if day:
        lines.append(f"📅 {t(lang, 'date_label')}: {escape(day)}")
    price = _money(float(l.price_amount) if l.price_amount else None, l.price_currency, lang)
    adv = _advance(getattr(l, "advance", ""), lang)
    lines.append(f"💰 {escape(price)}" + (f" · {escape(adv)}" if adv else ""))
    if l.contact_phone:
        lines.append(f"📞 {escape(l.contact_phone)}")
    elif _tg_contact(l):
        lines.append(f"✉️ {_tg_contact(l)}")
    return _common_tail(l, lines, lang, link)


def format_results(loads, header, lang=DEFAULT_LANG, link=False, buttons=True):
    if not loads:
        return f"<b>{header}</b>\n\n{t(lang, 'nothing_found')}"
    numbered = buttons and len(loads) > 1
    blocks = [format_load(l, lang, num=i if numbered else None, link=link)
              for i, l in enumerate(loads, 1)]
    text = f"<b>{header}</b> ({len(loads)})\n\n" + "\n\n➖➖➖\n\n".join(blocks)
    if numbered and any(has_original(l) for l in loads):
        text += "\n\n<i>" + t(lang, "raw_hint") + "</i>"
    return text


def original_kb(loads, lang, extra_rows=()):
    """'📄 N' buttons (one per scraped load) — or a single '📄 Asl matn' for one card."""
    numbered = len(loads) > 1
    buttons = [InlineKeyboardButton(text=f"📄 {i}" if numbered else t(lang, "raw_btn"),
                                    callback_data=f"raw:{l.id}")
               for i, l in enumerate(loads, 1) if has_original(l)]
    rows = [buttons[i:i + 5] for i in range(0, len(buttons), 5)] + list(extra_rows)
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
