"""Builds the extraction prompt. A message may hold MANY loads — the model returns a list.
Base instruction + DOMAIN NOTES (data/patterns.md) + few-shot EXAMPLES (data/few_shot.jsonl)."""
import json
from .. import config

SYSTEM_PROMPT = """You are a freight data extractor for Central Asia. Output STRICT JSON only, and
OMIT any field that is empty/null (never output empty strings).

RULE 1 - SPLIT EVERY LOAD (most important): a message often lists SEVERAL loads (2-20). Return one
object per load. Each direction "A - B" (or A->B, A/B, A on one line and B on the next, or blocks
split by blank / --- lines / flags) is a SEPARATE load. NEVER merge cities across directions
("Ryazan->Tashkent" and "Moscow->Tashkent" are TWO loads). If one phone is given for all, put it on
EVERY load. The "loads" array must have as many objects as there are directions.

FIELDS:
- is_load: default true (omit it); false ONLY for an empty truck seeking cargo ("bo'sh mashina",
  "свободная машина", "фура бор").
- origin_city / destination_city: keep EXACTLY as written INCLUDING district ("Toshkent Yashnobod"
  stays; don't shorten or convert to region). First place = origin, second = destination.
- truck_type: type(s) only from tent/ref/isotherm/flatbed/container/dump/isuzu/labo/paravoz.
  "тент/реф"->"tent, ref"; "isuzu kerak"->"isuzu"; "Labo"->"labo"; "paravoz/автопоезд" is a
  road-train -> add it ("tent, paravoz"). "Сборка/сборный" is NOT a truck (-> comment). "тент/120":
  120 is volume -> comment. "farqi yo'q"/none -> omit truck_type.
- cargo_type: the goods (paxta, масло, полиэтилен, "bolgariskiy"=pepper). Never a truck word.
- truck_count: number of trucks ("4 авто", "20 mashina", "тент 13").
- weight_tons: tons number; range "22-23т"->22; kg->tons ("200 кг"->0.2, "20000 кг"->20).
- price: set price_amount ONLY with a real number+currency ($->USD, сум->UZS, руб->RUB, тенге->KZT;
  "45 mln"->45000000). A DATE ("30.07", "28-30.07", "на 28.07") is NEVER a price -> comment.
  "$"/"наличный"/"накд"/"naqd" with NO number = cash -> omit price, write "naqd" in comment. A bare
  number with no currency -> omit price.
- contact_phone: ALL phones, comma-separated; shared phone on every load.
- comment: EVERYTHING else - dates, urgency (СРОЧНО/ГОРИТ), payment ("наличный"), volume ("90 куб"),
  "dagruz", unload side. Rarely empty on a real load.

A load needs origin_city + destination_city; skip it if either is missing. Ignore ads/greetings/promos.
Follow the DOMAIN NOTES and EXAMPLES below.
Return ONLY: {"loads": [ {...}, ... ]}. If nothing, {"loads": []}."""


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


def batch_user_prompt(texts: list[str]) -> str:
    """Pack several messages into ONE request (used by paid APIs to cut request count)."""
    parts = ["You are given SEVERAL separate Telegram messages, numbered below.",
             "Extract loads from EACH message INDEPENDENTLY — never merge routes across messages.",
             "",
             'Return ONLY JSON: {"results": [{"i": <number>, "loads": [ {load}, ... ]}, ...]}',
             "Include an entry for EVERY number; use an empty list when a message has no load.",
             ""]
    for idx, text in enumerate(texts, 1):
        parts.append(f"### MESSAGE {idx}")
        parts.append(text)
        parts.append("")
    return "\n".join(parts)
