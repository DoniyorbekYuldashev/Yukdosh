"""Canonicalization: map the many spellings/scripts of cities, truck types and
currencies to one canonical value. Used to clean both mock and LLM output, and
it's what makes dedup and matching reliable."""
import re
from difflib import SequenceMatcher as _SM

# Canonical city -> region, plus every spelling/script we might see.
CITY_ALIASES = {
    # Uzbekistan
    "toshkent": ("Toshkent", "Toshkent"),
    "тошкент": ("Toshkent", "Toshkent"),
    "tashkent": ("Toshkent", "Toshkent"),
    "ташкент": ("Toshkent", "Toshkent"),
    "samarqand": ("Samarqand", "Samarqand"),
    "самарканд": ("Samarqand", "Samarqand"),
    "samarkand": ("Samarqand", "Samarqand"),
    "buxoro": ("Buxoro", "Buxoro"),
    "бухоро": ("Buxoro", "Buxoro"),
    "bukhara": ("Buxoro", "Buxoro"),
    "andijon": ("Andijon", "Andijon"),
    "андижон": ("Andijon", "Andijon"),
    "fargona": ("Fargona", "Fargona"),
    "фаргона": ("Fargona", "Fargona"),
    "namangan": ("Namangan", "Namangan"),
    "наманган": ("Namangan", "Namangan"),
    "nukus": ("Nukus", "Qoraqalpogiston"),
    "нукус": ("Nukus", "Qoraqalpogiston"),
    "qarshi": ("Qarshi", "Qashqadaryo"),
    "карши": ("Qarshi", "Qashqadaryo"),
    "termiz": ("Termiz", "Surxondaryo"),
    "термиз": ("Termiz", "Surxondaryo"),
    "urganch": ("Urganch", "Xorazm"),
    "ургенч": ("Urganch", "Xorazm"),
    # Kazakhstan
    "almaty": ("Almaty", "Kazakhstan"),
    "алматы": ("Almaty", "Kazakhstan"),
    "олматы": ("Almaty", "Kazakhstan"),
    "astana": ("Astana", "Kazakhstan"),
    "астана": ("Astana", "Kazakhstan"),
    "shymkent": ("Shymkent", "Kazakhstan"),
    "шымкент": ("Shymkent", "Kazakhstan"),
    # Russia (common destinations)
    "moskva": ("Moskva", "Russia"),
    "москва": ("Moskva", "Russia"),
    "moscow": ("Moskva", "Russia"),
    "sankt-peterburg": ("Sankt-Peterburg", "Russia"),
    "санкт-петербург": ("Sankt-Peterburg", "Russia"),
    "с-петербург": ("Sankt-Peterburg", "Russia"),
    "spb": ("Sankt-Peterburg", "Russia"),
    "питер": ("Sankt-Peterburg", "Russia"),
    # Others
    "bishkek": ("Bishkek", "Kyrgyzstan"),
    "бишкек": ("Bishkek", "Kyrgyzstan"),
    "dushanbe": ("Dushanbe", "Tajikistan"),
    "душанбе": ("Dushanbe", "Tajikistan"),
}

TRUCK_ALIASES = {
    "tent": "tent", "тент": "tent", "фура": "tent", "fura": "tent",
    "ref": "ref", "реф": "ref", "рефрижератор": "ref", "refrijerator": "ref",
    "isotherm": "isotherm", "изотерм": "isotherm", "izoterm": "isotherm",
    "flatbed": "flatbed", "площадка": "flatbed", "bortli": "flatbed", "борт": "flatbed",
    "container": "container", "контейнер": "container", "konteyner": "container",
    "dump": "dump", "самосвал": "dump", "samosval": "dump",
}

CURRENCY_ALIASES = {
    "sum": "UZS", "сум": "UZS", "so'm": "UZS", "som": "UZS", "uzs": "UZS",
    "rub": "RUB", "руб": "RUB", "рубль": "RUB", "rubl": "RUB",
    "tenge": "KZT", "тенге": "KZT", "kzt": "KZT",
    "usd": "USD", "$": "USD", "dollar": "USD", "доллар": "USD",
    "сўм": "UZS", "so‘m": "UZS", "soʻm": "UZS", "сом": "UZS", "₽": "RUB", "eur": "EUR", "€": "EUR",
    "евро": "EUR", "euro": "EUR",
}


def canonical_city(raw):
    if not raw:
        return "", ""
    key = raw.strip().lower()
    if key in CITY_ALIASES:
        return CITY_ALIASES[key]
    for token in re.split(r"[\s,.;]+", key):
        if token in CITY_ALIASES:
            return CITY_ALIASES[token]
    return raw.strip().title(), ""


def canonical_truck(raw):
    if not raw:
        return ""
    key = raw.strip().lower()
    if key in TRUCK_ALIASES:
        return TRUCK_ALIASES[key]
    for token in re.split(r"[\s,.;/]+", key):
        if token in TRUCK_ALIASES:
            return TRUCK_ALIASES[token]
    return "other"


def canonical_currency(raw):
    if not raw:
        return ""
    key = raw.strip().lower()
    return CURRENCY_ALIASES.get(key, raw.strip().upper())


# --- extra aliases (extend freely as you see new spellings in real posts) ---
CITY_ALIASES.update({
    "qo'qon": ("Qoqon", "Fargona"), "коканд": ("Qoqon", "Fargona"), "qoqon": ("Qoqon", "Fargona"),
    "xiva": ("Xiva", "Xorazm"), "хива": ("Xiva", "Xorazm"),
    "jizzax": ("Jizzax", "Jizzax"), "джизак": ("Jizzax", "Jizzax"),
    "guliston": ("Guliston", "Sirdaryo"), "гулистан": ("Guliston", "Sirdaryo"),
    "navoiy": ("Navoiy", "Navoiy"), "навои": ("Navoiy", "Navoiy"),
    "qozogiston": ("Qozogiston", "Kazakhstan"), "казахстан": ("Qozogiston", "Kazakhstan"),
    "rossiya": ("Rossiya", "Russia"), "россия": ("Rossiya", "Russia"),
    "turkiya": ("Turkiya", "Turkey"), "турция": ("Turkiya", "Turkey"),
})
TRUCK_ALIASES.update({
    "холодильник": "ref", "xolodilnik": "ref",
    "бортовой": "flatbed", "ochiq": "flatbed", "otkritiy": "flatbed",
    "yopiq": "tent", "закрытый": "tent",
    "mega": "tent", "стандарт": "tent",
})

CITY_ALIASES.update({
    "термез": ("Termiz", "Surxondaryo"), "termez": ("Termiz", "Surxondaryo"),
    "краснодар": ("Krasnodar", "Russia"), "krasnodar": ("Krasnodar", "Russia"),
})

CITY_ALIASES.update({
    "тош": ("Toshkent", "Toshkent"), "tsh": ("Toshkent", "Toshkent"), "tosh": ("Toshkent", "Toshkent"),
    "смк": ("Samarqand", "Samarqand"), "smk": ("Samarqand", "Samarqand"),
    "питер": ("Sankt-Peterburg", "Russia"), "спб": ("Sankt-Peterburg", "Russia"),
})

# Road-train / trailer combination ("paravoz" = a separate trailer pulled behind), a truck type
# on its own — list it IN ADDITION to tent/ref, never instead of them.
TRUCK_ALIASES.update({
    "paravoz": "paravoz", "паравоз": "paravoz", "паровоз": "paravoz", "parovoz": "paravoz",
    "avtopoyezd": "paravoz", "автопоезд": "paravoz", "poyezd": "paravoz",
    # Isuzu (small truck brand used as a type); size words kichik/katta stay in the text
    "isuzu": "isuzu", "исузу": "isuzu", "isuzi": "isuzu", "исузи": "isuzu",
    "isuza": "isuzu", "izuzu": "isuzu", "izusu": "isuzu",
    "labo": "labo", "лабо": "labo", "labbo": "labo",
})


# ── cross-script + fuzzy city matching ──────────────────────────────────────────
# Transliterate Cyrillic (Russian/Uzbek/Kazakh) to Latin, then fold spelling variants,
# so "Чирчик" == "Chirchiq", "Новосибирск" == "Novosibirsk", and typos still match.
_CYR2LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "yu",
    "я": "ya", "ў": "o", "қ": "q", "ғ": "g", "ҳ": "h", "ә": "a", "і": "i", "ң": "ng",
    "ү": "u", "ұ": "u", "ө": "o", "һ": "h", "ї": "i", "є": "e",
}


def _translit(s: str) -> str:
    return "".join(_CYR2LAT.get(ch, ch) for ch in s)


def norm_city(s: str) -> str:
    """A script/spelling-agnostic key for a city name."""
    s = _translit((s or "").strip().lower())
    for junk in ("'", "`", "ʻ", "ʼ", "‘", "’"):
        s = s.replace(junk, "")
    for a, b in (("shch", "s"), ("sch", "s"), ("ch", "c"), ("sh", "s"), ("ts", "c"),
                 ("kh", "h"), ("yo", "o"), ("yu", "u"), ("ya", "a"), ("ye", "e")):
        s = s.replace(a, b)
    s = s.replace("q", "k").replace("x", "h").replace("w", "v")
    return re.sub(r"[^a-z0-9]", "", s)


def city_match(city: str, query: str, threshold: float = 0.8) -> bool:
    """True if `query` refers to the same city as `city`, across scripts and typos."""
    a, b = norm_city(city), norm_city(query)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    return _SM(None, a, b).ratio() >= threshold


def _fuzzy_truck(token: str):
    """Map a slightly misspelled token (e.g. 'isuzi', 'tetn', 'izoterm') to a canonical type."""
    if len(token) < 4:
        return None
    best, score = None, 0.0
    for key, canon in TRUCK_ALIASES.items():
        r = _SM(None, token, key).ratio()
        if r > score:
            best, score = canon, r
    return best if score >= 0.82 else None


def canonicalize_trucks(raw) -> str:
    """Return ALL recognized truck/trailer types, comma-separated (e.g. 'tent, ref, paravoz').
    Tolerant of typos (isuzi->isuzu). Empty if none recognized (means 'any truck')."""
    if not raw:
        return ""
    found = []
    for token in re.split(r"[\s,.;/]+", str(raw).strip().lower()):
        if not token:
            continue
        t = TRUCK_ALIASES.get(token) or _fuzzy_truck(token)
        if t and t not in found:
            found.append(t)
    return ", ".join(found)
