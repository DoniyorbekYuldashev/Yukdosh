"""Deduplication. The same load is reposted across MANY groups, re-posted hourly, and often
with small wording changes. We fingerprint on the load's real IDENTITY — normalized route +
phone — so drivers see it once, even across channels."""
import hashlib
import re

from ..schemas import ParsedLoad
from .normalize import norm_city

_DIGITS = re.compile(r"\d+")


def _phone_key(raw: str) -> str:
    """All phone numbers reduced to their last 9 digits (drops country-code/format variance),
    de-duplicated and sorted, so the same contact matches regardless of how it was typed."""
    cleaned = re.sub(r"[ \t()\-+.]", "", raw or "")  # drop spaces/dashes/format, keep , ; as separators
    nums = {g[-9:] for g in _DIGITS.findall(cleaned) if len(g) >= 7}
    return ",".join(sorted(nums))


def dedup_hash(load: ParsedLoad) -> str:
    o = norm_city(load.origin_city or "")
    d = norm_city(load.destination_city or "")
    phones = _phone_key(load.contact_phone or "")
    if phones:
        # route + phone = the same listing, even if reposted with different wording/price
        key = f"{o}|{d}|{phones}"
    else:
        # no phone to key on — fall back to route + cargo + weight so distinct loads stay distinct
        key = f"{o}|{d}|{(load.cargo_type or '').strip().lower()}|{load.weight_tons or ''}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
