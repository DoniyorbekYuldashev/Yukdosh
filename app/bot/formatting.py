"""Render a structured load as a clean card for drivers, showing the full field set:
From, Destination, truck/trailer type + count, load type + amount, price, phone, comment."""
from datetime import datetime, timezone, timedelta

TASHKENT = timezone(timedelta(hours=5))  # Uzbekistan time (UTC+5)

_CURRENCY_SYMBOL = {"UZS": "so'm", "RUB": "rub", "KZT": "tenge", "USD": "$"}
_TRUCK_LABEL = {
    "tent": "Tent", "ref": "Refrijerator", "isotherm": "Izoterm",
    "flatbed": "Bortli", "container": "Konteyner", "dump": "Samosval",
    "isuzu": "Isuzu", "paravoz": "Paravoz", "other": "Boshqa",
}


def _when(dt):
    """Proper Tashkent local time: 'Bugun 16:54', 'Kecha 21:30', or '10.07 09:15'."""
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(TASHKENT)
    today = datetime.now(TASHKENT).date()
    if local.date() == today:
        day = "Bugun"
    elif local.date() == today - timedelta(days=1):
        day = "Kecha"
    else:
        day = local.strftime("%d.%m")
    return f"{day} {local.strftime('%H:%M')}"


def _money(amount, currency):
    if not amount:
        return "keltirilmagan"
    cur = _CURRENCY_SYMBOL.get(currency, currency or "")
    return f"{amount:,.0f} {cur}".strip()


def _post_link(l):
    sg = (l.source_group or "")
    mid = getattr(l, "source_msg_id", "") or ""
    if sg.startswith("https://t.me/") and mid:
        return sg.rstrip("/") + "/" + str(mid)
    return ""


def _tail(l):
    t = []
    if l.posted_at:
        t.append(f"🕒 {_when(l.posted_at)}")
    if l.source_group == "bot":
        t.append("Sarbon24 orqali")
    elif l.source_group:
        t.append("manba: " + l.source_group.replace("https://t.me/", "@"))
    return ("<i>" + " · ".join(t) + "</i>") if t else ""


def format_goods(l):
    lines = [f"🛒 <b>{l.cargo_type or 'Mahsulot'}</b>"]
    meta = []
    if l.weight_tons:
        meta.append(f"⚖️ {float(l.weight_tons):g} t")
    if l.origin_city:
        meta.append(f"📍 {l.origin_city}")
    if meta:
        lines.append(" · ".join(meta))
    lines.append(f"💰 {_money(float(l.price_amount) if l.price_amount else None, l.price_currency)}")
    if l.contact_phone:
        lines.append(f"📞 {l.contact_phone}")
    if getattr(l, 'comment', ''):
        lines.append(f"📝 {l.comment}")
    link = _post_link(l)
    if link:
        lines.append(f'🔗 <a href="{link}">E\'lon manbasi</a>')
    tail = _tail(l)
    if tail:
        lines.append(tail)
    return "\n".join(lines)


def format_load(l):
    if getattr(l, "listing_type", "load") == "goods":
        return format_goods(l)
    head = "📦" if l.is_load else "🚛"
    lines = [f"{head} <b>{l.origin_city or '?'} → {l.destination_city or '?'}</b>"]

    row = []
    if l.truck_type:
        parts = [_TRUCK_LABEL.get(x.strip(), x.strip()) for x in l.truck_type.split(",") if x.strip()]
        t = ", ".join(parts)
        if getattr(l, "truck_count", None):
            t += f" ×{l.truck_count}"
        row.append(f"🚚 {t}")
    elif getattr(l, "truck_count", None):
        row.append(f"🚚 ×{l.truck_count}")
    if l.weight_tons:
        row.append(f"⚖️ {float(l.weight_tons):g} t")
    if row:
        lines.append(" · ".join(row))

    if l.cargo_type:
        lines.append(f"📦 {l.cargo_type}")
    lines.append(f"💰 {_money(float(l.price_amount) if l.price_amount else None, l.price_currency)}")
    if l.contact_phone:
        lines.append(f"📞 {l.contact_phone}")
    if getattr(l, "comment", ""):
        lines.append(f"📝 {l.comment}")
    link = _post_link(l)
    if link:
        lines.append(f'🔗 <a href="{link}">E\'lon manbasi</a>')
    tail = _tail(l)
    if tail:
        lines.append(tail)
    return "\n".join(lines)


def format_results(loads, header):
    if not loads:
        return f"<b>{header}</b>\n\nHech narsa topilmadi. Keyinroq urinib ko'ring."
    blocks = [format_load(l) for l in loads]
    return f"<b>{header}</b> ({len(loads)})\n\n" + "\n\n➖➖➖\n\n".join(blocks)
