"""Render a structured load as a clean card for drivers, in the user's language."""
from datetime import datetime, timezone, timedelta

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


def _truck_label(code, lang):
    code = (code or "").strip()
    key = _TRUCK_KEYS.get(code)
    return t(lang, key) if key else code


def _post_link(l):
    sg = (l.source_group or "")
    mid = getattr(l, "source_msg_id", "") or ""
    if sg.startswith("https://t.me/") and mid:
        return sg.rstrip("/") + "/" + str(mid)
    return ""


def _tail(l, lang):
    parts = []
    if l.posted_at:
        parts.append(f"🕒 {_when(l.posted_at, lang)}")
    if l.source_group == "bot":
        parts.append(t(lang, "via_bot"))
    return ("<i>" + " · ".join(parts) + "</i>") if parts else ""


def _common_tail(l, lines, lang):
    if getattr(l, "comment", ""):
        lines.append(f"📝 {l.comment}")
    link = _post_link(l)
    if link:
        lines.append(f'🔗 <a href="{link}">{t(lang, "source_link")}</a>')
    tail = _tail(l, lang)
    if tail:
        lines.append(tail)
    return "\n".join(lines)


def format_goods(l, lang=DEFAULT_LANG):
    lines = [f"🛒 <b>{l.cargo_type or t(lang, 'goods')}</b>"]
    meta = []
    if l.weight_tons:
        meta.append(f"⚖️ {float(l.weight_tons):g} t")
    if l.origin_city:
        meta.append(f"📍 {l.origin_city}")
    if meta:
        lines.append(" · ".join(meta))
    lines.append(f"💰 {_money(float(l.price_amount) if l.price_amount else None, l.price_currency, lang)}")
    if l.contact_phone:
        lines.append(f"📞 {l.contact_phone}")
    return _common_tail(l, lines, lang)


def format_load(l, lang=DEFAULT_LANG):
    if getattr(l, "listing_type", "load") == "goods":
        return format_goods(l, lang)
    head = "📦" if l.is_load else "🚛"
    lines = [f"{head} <b>{l.origin_city or '?'} → {l.destination_city or '?'}</b>"]

    row = []
    if l.truck_type:
        parts = [_truck_label(x, lang) for x in l.truck_type.split(",") if x.strip()]
        label = ", ".join(parts)
        if getattr(l, "truck_count", None):
            label += f" ×{l.truck_count}"
        row.append(f"🚚 {label}")
    elif getattr(l, "truck_count", None):
        row.append(f"🚚 ×{l.truck_count}")
    if l.weight_tons:
        row.append(f"⚖️ {float(l.weight_tons):g} t")
    if row:
        lines.append(" · ".join(row))

    if l.cargo_type:
        lines.append(f"📦 {l.cargo_type}")
    lines.append(f"💰 {_money(float(l.price_amount) if l.price_amount else None, l.price_currency, lang)}")
    if l.contact_phone:
        lines.append(f"📞 {l.contact_phone}")
    return _common_tail(l, lines, lang)


def format_results(loads, header, lang=DEFAULT_LANG):
    if not loads:
        return f"<b>{header}</b>\n\n{t(lang, 'nothing_found')}"
    blocks = [format_load(l, lang) for l in loads]
    return f"<b>{header}</b> ({len(loads)})\n\n" + "\n\n➖➖➖\n\n".join(blocks)
