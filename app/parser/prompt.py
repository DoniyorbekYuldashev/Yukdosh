"""Builds the extraction prompt. A message may hold MANY loads — the model returns a list.
Base instruction + DOMAIN NOTES (data/patterns.md) + few-shot EXAMPLES (data/few_shot.jsonl)."""
import json
from .. import config

SYSTEM_PROMPT = """You are a freight data extractor for Central Asia. A single Telegram
message often contains MULTIPLE separate load announcements (2 to 20). SPLIT them and
return ONE object per load.

CRITICAL FIELD RULES:
- is_load: DEFAULT true (it is a LOAD/cargo). Set false ONLY when the message clearly offers an
  EMPTY TRUCK looking for cargo — phrases like "bo'sh mashina", "bo'sh fura", "fura bor",
  "mashina bor", "свободная машина", "свободна", "свободен", "пустая". If unsure -> true.
- origin_city (From) and destination_city (Destination) are ALMOST ALWAYS BOTH present. The
  route is written as "A - B", "A—B", "A/B", "A → B", or A on the first line and B on the next.
  The FIRST city/region/country is origin, the SECOND is destination.
- Each "A - B" direction is EXACTLY ONE load (A = origin, B = destination). A message with
  several directions = several separate loads. NEVER mix cities from different directions:
  e.g. "Borisov-Tashkent" and "Borisov-Navoi" are TWO loads (Borisov→Tashkent and Borisov→Navoi),
  NOT one "Tashkent-Navoi". Country flags/emojis are noise — ignore them.
- truck_type: the VEHICLE/trailer type(s) ONLY, from: tent, ref, isotherm, flatbed, container,
  dump, other. Words like "тент", "фура", "tent", "реф", "ref", "изотерм", "борт", "контейнер"
  are truck_type — NEVER cargo. If SEVERAL types are accepted (e.g. "tent ref", "тент/реф"),
  list ALL of them comma-separated: "tent, ref". If it says "farqi yo'q" / "no matter" / no type
  is given, leave truck_type EMPTY (means any truck).
- cargo_type: WHAT the goods physically are (e.g. "metal rulon", "paxta", "steklovata", "meva",
  "масло"). NEVER put a truck/trailer word here.
- truck_count: how many trucks (a number, e.g. "тент 13" -> 13), else null.
- weight_tons: load amount in tons (number), else null.
- price: set price_amount ONLY if a currency is shown. Map $ -> USD, so'm/sum/сум -> UZS,
  руб/rub -> RUB, тенге/tenge -> KZT, any other -> that currency. A BARE number with NO currency
  sign (e.g. "2000", "4200") -> leave price_amount null AND price_currency "". Do NOT guess USD
  or UZS for bare numbers.
- contact_phone: ALL phone numbers, comma-separated.
- comment: EVERY other detail not captured above (dates, conditions, payment terms, notes).
  Nothing from the message may be lost. If unsure where a detail goes, put it in comment.
- language_detected: uz-latn, uz-cyrl, ru, kk, tg, or other.

REQUIRED fields (always present in these posts — always fill them): origin_city (From),
destination_city (Destination), truck_type, contact_phone. Optional: weight_tons, cargo_type,
truck_count, price. If ONE phone/contact is given for SEVERAL loads in the message, put that
same phone on EVERY load. A load with no From/Destination is not valid — skip it.

Ignore pure ads / greetings / promos (return no load for them).
Follow the DOMAIN NOTES and EXAMPLES below.

Return ONLY JSON of the form: {"loads": [ {load1}, {load2}, ... ]}. If nothing, {"loads": []}."""


def _data(name):
    return config.BASE_DIR / "data" / name


def _load_notes() -> str:
    p = _data("patterns.md")
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _load_examples(limit: int = 30) -> list[dict]:
    p = _data("few_shot.jsonl")
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict) and "text" in row and "output" in row:
            out.append(row)
        if len(out) >= limit:
            break
    return out


_PROMPT_CACHE: dict[int, str] = {}


def build_system_prompt(limit: int = 30) -> str:
    # Memoized: the system prompt is static, so build it once per process. Keeping it
    # byte-identical across every call is what lets OpenAI (50% off) and Gemini flash
    # (~75% off) cache the repeated prefix — the message is the only variable part.
    if limit in _PROMPT_CACHE:
        return _PROMPT_CACHE[limit]
    parts = [SYSTEM_PROMPT]
    notes = _load_notes()
    if notes:
        parts.append("DOMAIN NOTES (priority guidance):\n" + notes)
    examples = _load_examples(limit)
    if examples:
        lines = ["EXAMPLES (message -> exact JSON to return):"]
        for e in examples:
            lines.append("Message: " + e["text"])
            lines.append("JSON: " + json.dumps(e["output"], ensure_ascii=False))
        parts.append("\n".join(lines))
    built = "\n\n".join(parts)
    _PROMPT_CACHE[limit] = built
    return built


def user_prompt(text: str) -> str:
    return f"Extract every load from this message:\n\n{text}"
