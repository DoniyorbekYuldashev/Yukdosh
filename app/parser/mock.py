"""Offline heuristic parser. No API key needed — lets you run the whole pipeline
and see structured output immediately. It's intentionally rule-based; the real
Gemini/Groq parsers will be far more accurate on messy text. Good enough to prove
the pipeline and to serve as a fallback."""
import re

from .base import LLMParser
from .normalize import (
    CITY_ALIASES, TRUCK_ALIASES, CURRENCY_ALIASES,
    canonical_city, canonical_truck, canonical_currency,
)
from ..schemas import ParsedLoad

EMPTY_TRUCK_HINTS = [
    "bo'sh", "bosh mashina", "бўш", "буш", "свободн", "свободная машина",
    "фура бор", "mashina bor", "moshina bor", "empty", "бос", "бош",
]
LOAD_HINTS = ["yuk", "юк", "груз", "gruz", "kerak", "керак", "керек", "load"]

CYRILLIC = re.compile(r"[а-яёұқғңүһөәі]", re.IGNORECASE)


def _detect_language(text: str) -> str:
    low = text.lower()
    if CYRILLIC.search(text):
        if any(c in low for c in ["ұқғңүһ", "ертең", "жүк"]):
            return "kk"
        if any(w in low for w in ["керак", "тўлов", "бор", "керек"]):
            return "uz-cyrl"
        return "ru"
    return "uz-latn"


def _find_cities(text: str) -> list[tuple[str, str]]:
    """Return canonical (city, region) tuples in order of appearance."""
    low = text.lower()
    hits = []
    for alias in CITY_ALIASES:
        for m in re.finditer(re.escape(alias), low):
            hits.append((m.start(), CITY_ALIASES[alias]))
    hits.sort(key=lambda x: x[0])
    # de-dup consecutive identical cities
    out = []
    for _, city in hits:
        if not out or out[-1] != city:
            out.append(city)
    return out


def _find_truck(text: str) -> str:
    low = text.lower()
    for alias in TRUCK_ALIASES:
        if alias in low:
            return TRUCK_ALIASES[alias]
    return ""


def _find_weight(text: str) -> float | None:
    m = re.search(r"(\d{1,3}(?:[.,]\d+)?)\s*(?:tonna|тонна|тонн|тн|т\b|t\b)", text, re.IGNORECASE)
    if m:
        return float(m.group(1).replace(",", "."))
    return None


def _find_price(text: str) -> tuple[float | None, str]:
    low = text.lower()
    # e.g. "45 млн сум", "45 mln", "3000 usd", "1 500 000 сум"
    m = re.search(
        r"(\d[\d\s.,]*)\s*(mln|млн|million|минг|ming|000)?\s*"
        r"(so'?m|sum|сум|руб|rubl|рубль|тенге|tenge|kzt|usd|\$|dollar|доллар)",
        low,
    )
    if not m:
        return None, ""
    num = float(re.sub(r"[\s.,]", "", m.group(1)) or 0)
    mult = m.group(2) or ""
    if mult in ("mln", "млн", "million"):
        num *= 1_000_000
    elif mult in ("минг", "ming"):
        num *= 1_000
    cur = canonical_currency(m.group(3))
    return num, cur


def _find_phone(text: str) -> str:
    m = re.search(r"(\+?\d[\d\s\-()]{7,}\d)", text)
    return re.sub(r"[\s\-()]", "", m.group(1)) if m else ""


def _is_empty_truck(text: str) -> bool:
    low = text.lower()
    empty = any(h in low for h in EMPTY_TRUCK_HINTS)
    load = any(h in low for h in LOAD_HINTS)
    # empty-truck phrasing wins if present and no strong load signal
    return empty and not (load and not empty)


class MockParser(LLMParser):
    name = "mock"

    def parse(self, text: str) -> list:
        cities = _find_cities(text)
        origin = cities[0] if len(cities) >= 1 else ("", "")
        dest = cities[1] if len(cities) >= 2 else ("", "")
        price, currency = _find_price(text)
        return [ParsedLoad(
            is_load=not _is_empty_truck(text),
            origin_city=origin[0], origin_region=origin[1],
            destination_city=dest[0], destination_region=dest[1],
            cargo_type="",
            weight_tons=_find_weight(text),
            truck_type=_find_truck(text),
            price_amount=price,
            price_currency=currency,
            contact_phone=_find_phone(text),
            language_detected=_detect_language(text),
        )]
