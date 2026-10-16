"""Pydantic schema for one parsed load. A message may contain MANY loads (up to ~20);
the parser returns a list of these. Every field maps to a column; anything that doesn't
fit a field goes into `comment` so no information is ever lost."""
import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator

_STR_FIELDS = (
    "origin_city", "origin_region", "destination_city", "destination_region",
    "cargo_type", "truck_type", "price_currency", "advance", "loading_date",
    "contact_phone", "contact_name", "language_detected", "comment",
)
_NUM_FIELDS = ("weight_tons", "volume_m3", "price_amount")


class ParsedLoad(BaseModel):
    is_load: bool = Field(True, description="True = cargo/goods; False = empty truck")

    origin_city: str = ""          # From
    origin_region: str = ""
    destination_city: str = ""     # Destination
    destination_region: str = ""

    cargo_type: str = ""           # Load type (what is it)
    weight_tons: Optional[float] = None   # Load amount (tons)
    volume_m3: Optional[float] = None
    truck_type: str = ""           # Truck / trailer type
    truck_count: Optional[int] = None     # Truck amount (how many trucks)

    price_amount: Optional[float] = None
    price_currency: str = ""
    advance: str = ""             # "1000 USD" | "30%" | "yes" (advance mentioned, no amount)

    loading_date: str = ""         # "17.10" | "28-30.07" | "ready" | "today" | "tomorrow" | short text
    contact_phone: str = ""        # Phone number(s), comma-separated
    contact_name: str = ""

    comment: str = ""              # EVERYTHING else — no text left out
    language_detected: str = ""

    @field_validator(*_STR_FIELDS, mode="before")
    @classmethod
    def _clean_str(cls, v):
        if v is None:
            return ""
        if isinstance(v, (list, tuple)):
            return ", ".join(str(x).strip() for x in v if x is not None and str(x).strip())
        return str(v)

    @field_validator(*_NUM_FIELDS, mode="before")
    @classmethod
    def _clean_num(cls, v):
        if isinstance(v, (list, tuple)):
            v = v[0] if v else None
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip().replace(" ", "")
        if not s:
            return None
        m = re.search(r"-?\d+(?:[.,]\d+)?", s)
        return float(m.group().replace(",", ".")) if m else None

    @field_validator("truck_count", mode="before")
    @classmethod
    def _clean_int(cls, v):
        if isinstance(v, (list, tuple)):
            v = v[0] if v else None
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            return int(v)
        m = re.search(r"\d+", str(v))
        return int(m.group()) if m else None

    @field_validator("is_load", mode="before")
    @classmethod
    def _clean_bool(cls, v):
        if v is None:
            return True
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        if s in ("false", "0", "no", "yo'q", "yoq", "net", "нет", "bo'sh", "bosh"):
            return False
        return True
