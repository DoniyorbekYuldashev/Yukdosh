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
  stays; don't shorten or convert to region), minus "(poytaxt)"/"(столица)". First place = origin.
- truck_type: type(s) only from tent/ref/isotherm/flatbed/container/dump/isuzu/labo/paravoz.
  "тент/реф"->"tent, ref"; "isuzu kerak"->"isuzu"; "Labo"->"labo"; "paravoz/автопоезд" is a
  road-train -> add it ("tent, paravoz"). "fura"/"фура" with no type ("fura kerak") -> "tent";
  "ref fura" -> "ref". A truck line for the whole post ("🚛 Тент ёки Реф фура керак") goes on
  EVERY load. "Сборка/сборный" is NOT a truck (-> comment). "тент/120":
  120 is volume -> volume_m3. "farqi yo'q"/none -> omit truck_type.
- cargo_type: the goods (paxta, масло, полиэтилен, "bolgariskiy"=pepper). Never a truck word.
  A header over a list ("Napitka 👇", "Chips 👇👇") is the cargo of every load under it.
- truck_count: number of trucks ("4 авто", "20 mashina", "тент 13").
- weight_tons: tons number; range "22-23т"->22; kg->tons ("200 кг"->0.2, "20000 кг"->20).
- volume_m3: cubic meters ("96 m³", "96 куб", "120 kub", "тент 120"); range "96-105"->96.
- price_amount + price_currency: the FULL freight price ("4000 USD", "3 900 000 сум"->3900000 UZS,
  "45 mln"->45000000, "11 milyon 500 ming"->11500000, "2.5 млн"->2500000). $->USD, сум/so'm->UZS,
  руб->RUB, тенге->KZT. A price may be a bare number with no currency word: a big round number
  (>=100 000) next to a route or after "narx/цена/фрахт/ставка/to'lov/оплата" is a price in UZS;
  a smaller labelled one ("Фрахт: 2200") is a price with currency omitted. Each direction line with
  its own price ("Ғазалкент - Қўқон 2 та - 3 900 000 сум") -> that price belongs to THAT load only.
  NOT a price: dates ("30.07", "28-30.07"), counts ("2 та"), tons, volumes, phones.
  "kelishiladi"/"договорная" or cash words with no number ("naqd", "$ накд") -> omit price.
- advance: the prepayment, if mentioned ("Avans 1000.00 USD"->"1000 USD", "аванс 30%"->"30%",
  "аванс 500$"->"500 USD", "аванс есть"/"avans bor"->"yes"). Never add the advance to the price.
- loading_date: WHEN to load, if mentioned: "17.10", "28-30.07", "17 oktyabr"->"17.10";
  "Ortishga tayyor"/"груз готов"/"yuk tayyor"->"ready"; "bugun"/"сегодня"->"today";
  "ertaga"/"завтра"->"tomorrow"; other short words as written ("dushanba"). Omit if not mentioned.
- contact_phone: phones are removed from the text before you see it, so normally omit it. Only
  if you still see a phone NUMBER (digits), copy it; never put words there.
- comment: EVERYTHING else - urgency (СРОЧНО/ГОРИТ), payment method ("naqd", "перечисление",
  "Pul o'tkazma"), "dagruz", customs, unload side. Do NOT repeat what is already in a field
  (price, advance, date, volume, weight), and never write "kelishiladi"/"договорная" or contact
  app names (WhatsApp, Telegram, IMO) there.

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
    n = len(texts)
    # Say the count: without it the model kept adding {"i": 6..857, "loads": []} until the token
    # limit (a repetition loop at temperature 0 -> broken JSON, every retry the same).
    parts = [f"You are given exactly {n} separate Telegram messages, numbered 1 to {n} below.",
             "Extract loads from EACH message INDEPENDENTLY — never merge routes across messages.",
             "",
             'Return ONLY JSON: {"results": [{"i": <number>, "loads": [ {load}, ... ]}, ...]}',
             f"Return exactly {n} entries, i = 1 to {n} (empty list when a message has no load), "
             "then close the JSON. Never add entries beyond " + str(n) + ".",
             ""]
    for idx, text in enumerate(texts, 1):
        parts.append(f"### MESSAGE {idx}")
        parts.append(text)
        parts.append("")
    return "\n".join(parts)
