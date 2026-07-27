"""Builds the extraction prompt. A message may hold MANY loads — the model returns a list.
Base instruction + DOMAIN NOTES (data/patterns.md) + few-shot EXAMPLES (data/few_shot.jsonl)."""
import json
from .. import config

SYSTEM_PROMPT = """You are a freight data extractor for Central Asia. Output STRICT JSON only.

### RULE 1 — SPLIT MULTIPLE LOADS (most important)
A single message very often contains SEVERAL separate loads (2 to 20). You MUST return ONE
object per load. Read the WHOLE message top to bottom and never stop after the first one.
- Each direction "A - B" (or "A → B", or A on one line and B on the next, or separated by
  blank lines / ─── lines / flags) is a SEPARATE load. Four directions = four objects.
- NEVER merge cities from different directions. "Ryazan→Tashkent" and "Moscow→Tashkent" are
  TWO loads, not one "Tashkent→..." and not one "Ryazan→Moscow".
- If ONE phone is given at the end for all directions, put that SAME phone on EVERY load.
- Count how many directions the message has; your "loads" array MUST have that many objects.

### FIELD RULES
- is_load: default true. false ONLY for an empty truck seeking cargo ("bo'sh mashina",
  "fura bor", "свободная машина", "свободна", "пустая"). If unsure -> true.
- origin_city / destination_city: keep the place EXACTLY as written, INCLUDING the district or
  neighbourhood. "Toshkent Yashnobod" stays "Toshkent Yashnobod" (do NOT shorten to "Toshkent"
  and do NOT convert a district to its region). First place = origin, second = destination.
- truck_type: vehicle/trailer type(s) only, from: tent, ref, isotherm, flatbed, container,
  dump, isuzu, labo, paravoz, other. "тент/реф" -> "tent, ref". "тент/120" -> "tent" (120 is
  volume -> comment). "isuzu kerak", "katta isuzu" -> "isuzu". "Labo" -> "labo". "paravoz/
  паровоз/автопоезд" is a road-train -> list it in ADDITION ("tent, paravoz"). "Сборка/сборный"
  is NOT a truck (it means consolidated cargo) -> leave truck_type empty, note it in comment.
  "farqi yo'q"/no type -> empty.
- cargo_type: WHAT the goods are (paxta, масло, пиломатериалы, полиэтилен, "bolgariskiy"=pepper,
  granula). NEVER a truck word.
- truck_count: number of trucks ("4 авто", "20 mashina", "2 тента", "тент 13") -> the number.
- weight_tons: tons as a number. "23т" -> 23; a RANGE "22-23т" -> 22; KG -> convert ("200 кг" ->
  0.2, "500 kg" -> 0.5). "до 23т" -> 23.
- price: set price_amount ONLY when a real NUMBER + currency is present. Map $ -> USD, so'm/сум ->
  UZS, руб -> RUB, тенге -> KZT.
    * A DATE is NEVER a price. "30.07", "28-30.07", "на 28.07", "1 авто на 29.07" are DATES -> put
      them in comment, and DO NOT turn them into a price (never "$3007" from "30.07").
    * "$", "наличными", "накд", "наличный", "naqd", "нал" WITHOUT a clear number = cash payment,
      no amount -> price_amount null, price_currency "", and write "naqd"/"наличный" in comment.
    * a bare number with no currency ("2000", "4200") -> price_amount null, currency "".
- contact_phone: ALL phone numbers, comma-separated. Shared phone -> on every load.
- comment: PUT EVERYTHING ELSE HERE — loading dates ("28-30.07"), urgency ("СРОЧНО", "ГОРИТ 🔥"),
  payment terms ("наличный", "по факту"), volume ("90 куб", "82-96 м3"), unload side ("зад"),
  "Дагрузка"/"dagruz", extra notes. The comment is rarely empty on a real load — do not drop these.
- language_detected: uz-latn, uz-cyrl, ru, kk, tg, or other.

REQUIRED on every load: origin_city, destination_city, truck_type (may be empty), contact_phone.
A load with no From/Destination is invalid — skip it. Ignore pure ads / greetings / promos.
Follow the DOMAIN NOTES and EXAMPLES below.

Return ONLY JSON: {"loads": [ {load1}, {load2}, ... ]}. If nothing, {"loads": []}."""


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
    return f"Extract EVERY load from this message (there may be several):\n\n{text}"
