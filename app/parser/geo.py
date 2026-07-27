"""Geographic hierarchy: Country -> Region -> District/City.

Makes search smart about administrative levels:
  * search a REGION (e.g. "Qashqadaryo")  -> returns loads from its districts (Kitob, Qarshi, ...)
  * search a DISTRICT/CITY (e.g. "Qarshi") -> returns that place
  * search a COUNTRY (e.g. "Rossiya")      -> returns everything inside that country

Built on norm_city(), so it is script- and typo-tolerant (Cyrillic/Latin, q/k, x/h, ...).
Extend the dicts freely as you see new places in real posts.
"""
import re
from difflib import SequenceMatcher as _SM
from functools import lru_cache

from .normalize import norm_city, city_match

# ── Uzbekistan: region -> its districts/cities (the ones that show up in freight posts) ──
_UZ_REGIONS = {
    "Toshkent": ["Toshkent", "Nurafshon", "Bekobod", "Chirchiq", "Angren", "Olmaliq", "Ohangaron",
                 "Yangiyol", "Gazalkent", "Chinoz", "Parkent", "Boka", "Piskent", "Qibray",
                 "Zangiota", "Yuqorichirchiq", "Quyichirchiq", "Ortachirchiq", "Bostonliq", "Buka"],
    "Andijon": ["Andijon", "Asaka", "Xonobod", "Shahrixon", "Marhamat", "Baliqchi", "Qorasuv",
                "Poytug", "Xojaobod", "Paxtaobod", "Buloqboshi", "Izboskan", "Jalaquduq",
                "Ulugnor", "Qorgontepa", "Boz", "Oltinkol"],
    "Fargona": ["Fargona", "Qoqon", "Margilon", "Quva", "Rishton", "Beshariq", "Yaypan", "Quvasoy",
                "Oltiariq", "Bagdod", "Buvayda", "Dangara", "Furqat", "Toshloq", "Uchkoprik",
                "Yozyovon", "Sox", "Qoshtepa", "Uzbekiston"],
    "Namangan": ["Namangan", "Chust", "Pop", "Uchqorgon", "Kosonsoy", "Chortoq", "Toraqorgon",
                 "Uychi", "Yangiqorgon", "Norin", "Mingbuloq", "Davlatobod", "Chodak"],
    "Samarqand": ["Samarqand", "Kattaqorgon", "Urgut", "Bulungur", "Ishtixon", "Jomboy", "Payariq",
                  "Pastdargom", "Nurobod", "Oqdaryo", "Toyloq", "Qoshrabot", "Narpay", "Paxtachi",
                  "Kattakurgan", "Chelak", "Juma", "Loyish"],
    "Buxoro": ["Buxoro", "Kogon", "Gijduvon", "Vobkent", "Romitan", "Shofirkon", "Olot", "Peshku",
               "Qorakol", "Qorovulbozor", "Jondor", "Gazli"],
    "Navoiy": ["Navoiy", "Zarafshon", "Uchquduq", "Karmana", "Nurota", "Konimex", "Xatirchi",
               "Qiziltepa", "Tomdi", "Gazgan", "Yangirabot"],
    "Qashqadaryo": ["Qarshi", "Shahrisabz", "Kitob", "Guzor", "Koson", "Kasbi", "Muborak",
                    "Chiroqchi", "Yakkabog", "Dehqonobod", "Kamashi", "Nishon", "Mirishkor",
                    "Qamashi", "Beshkent", "Karshi"],
    "Surxondaryo": ["Termiz", "Denov", "Sherobod", "Shorchi", "Boysun", "Qumqorgon", "Angor",
                    "Jarqorgon", "Sariosiyo", "Uzun", "Muzrabot", "Oltinsoy", "Bandixon",
                    "Qiziriq", "Termez"],
    "Jizzax": ["Jizzax", "Gagarin", "Dustlik", "Zomin", "Gallaorol", "Paxtakor", "Zafarobod",
               "Baxmal", "Forish", "Mirzachol", "Yangiobod", "Arnasoy", "Zarbdor", "Sharof Rashidov"],
    "Sirdaryo": ["Guliston", "Sirdaryo", "Yangiyer", "Shirin", "Boyovut", "Sardoba", "Xovos",
                 "Baxt", "Sayxunobod", "Mirzaobod", "Oqoltin", "Gulistan", "Xavast", "Syrdarya", "Sirdarya"],
    "Xorazm": ["Urganch", "Xiva", "Hazorasp", "Gurlan", "Shovot", "Bogot", "Yangiariq", "Xonqa",
               "Qoshkopir", "Pitnak", "Yangibozor", "Tuproqqala", "Xazorasp", "Urgench"],
    "Qoraqalpogiston": ["Nukus", "Xojayli", "Chimboy", "Beruniy", "Turtkol", "Qongirot", "Moynaq",
                        "Taxiatosh", "Kegeyli", "Shumanay", "Amudaryo", "Ellikqala", "Qanlikol",
                        "Taxtakopir", "Boozatov", "Nukus"],
}

# ── A light region layer for the most common CIS oblasts that appear in cross-border posts ──
_CIS_REGIONS = {
    "Moskva": ["Moskva", "Vorsino", "Podolsk", "Domodedovo", "Ximki", "Elektrostal", "Noginsk",
               "Balashixa", "Mitishi", "Lyubertsi", "Odintsovo", "Vnukovo", "Chexov", "Serpuxov"],
    "Sankt-Peterburg": ["Sankt-Peterburg", "Gatchina", "Vsevolojsk", "Kolpino", "Pushkin", "Shushari"],
    "Almaty obl": ["Almaty", "Taldykorgan", "Kapshagay", "Talgar", "Esik", "Qonaev"],
}

# ── Flat country -> cities without their own region layer here ──
_COUNTRY_FLAT = {
    "Kazakhstan": ["Almaty", "Astana", "Nur-Sultan", "Shymkent", "Karaganda", "Aktobe", "Taraz",
                   "Pavlodar", "Oskemen", "Ust-Kamenogorsk", "Kostanay", "Kyzylorda", "Atyrau",
                   "Aktau", "Semey", "Turkestan", "Petropavl", "Kokshetau", "Taldykorgan", "Oral",
                   "Uralsk", "Ekibastuz", "Temirtau", "Zhezkazgan", "Balqash", "Saryagash", "Kentau"],
    "Russia": ["Moskva", "Sankt-Peterburg", "Novosibirsk", "Yekaterinburg", "Krasnodar", "Kazan",
               "Samara", "Rostov", "Chelyabinsk", "Ufa", "Volgograd", "Voronej", "Saratov",
               "Orenburg", "Nijniy Novgorod", "Perm", "Krasnoyarsk", "Omsk", "Tyumen", "Tula",
               "Lipetsk", "Belgorod", "Astraxan", "Ekaterinburg"],
    "Kyrgyzstan": ["Bishkek", "Osh", "Jalal-Abad", "Karakol", "Talas", "Naryn", "Batken", "Tokmok",
                   "Kara-Balta", "Kant", "Uzgen", "Kara-Suu"],
    "Tajikistan": ["Dushanbe", "Khujand", "Xujand", "Bokhtar", "Kurgan-Tyube", "Kulob", "Istaravshan",
                   "Panjakent", "Isfara", "Konibodom", "Tursunzoda", "Vahdat", "Hisor"],
    "Uzbekistan": [],  # covered by the region layer above
    "Turkmenistan": ["Ashgabat", "Turkmenabat", "Dashoguz", "Mary", "Balkanabat", "Turkmenbashi"],
    "Turkey": ["Istanbul", "Ankara", "Izmir", "Bursa", "Mersin", "Gaziantep"],
}

# which country each region belongs to
_REGION_COUNTRY = {r: "Uzbekistan" for r in _UZ_REGIONS}
_REGION_COUNTRY.update({"Moskva": "Russia", "Sankt-Peterburg": "Russia", "Almaty obl": "Kazakhstan"})

_ALL_REGIONS = {**_UZ_REGIONS, **_CIS_REGIONS}

# ── country name spellings (norm_city folds scripts/typos, these add the obvious variants) ──
_COUNTRY_ALIASES = {
    "Uzbekistan": ["uzbekistan", "ozbekiston", "o'zbekiston", "узбекистан", "узбекистон", "uz", "uzb"],
    "Kazakhstan": ["kazakhstan", "qozogiston", "qozoqiston", "казахстан", "қазақстан", "kz", "kaz"],
    "Russia": ["russia", "rossiya", "россия", "рф", "rf", "ru", "rossiyaga"],
    "Kyrgyzstan": ["kyrgyzstan", "qirgiziston", "kirgiziston", "киргизия", "кыргызстан", "kg"],
    "Tajikistan": ["tajikistan", "tojikiston", "таджикистан", "тоҷикистон", "tj"],
    "Turkmenistan": ["turkmenistan", "turkманистан", "туркменистан", "tm"],
    "Turkey": ["turkey", "turkiya", "турция", "туркия"],
}

# region name spellings (Cyrillic / common variants); norm_city handles most, these are safety
_REGION_ALIASES = {
    "Qashqadaryo": ["кашкадарья", "qashqadaryo", "qashqa"],
    "Surxondaryo": ["сурхандарья", "surxondaryo"],
    "Sirdaryo": ["сырдарья", "syrdarya", "sirdaryo"],
    "Xorazm": ["хорезм", "khorezm", "xorazm"],
    "Toshkent": ["ташкентская", "tashkent"],
    "Fargona": ["ферганская", "fergana"],
    "Andijon": ["андижанская"],
    "Namangan": ["наманганская"],
    "Samarqand": ["самаркандская"],
    "Buxoro": ["бухарская"],
    "Navoiy": ["навоийская"],
    "Jizzax": ["джизакская"],
    "Qoraqalpogiston": ["каракалпакстан", "karakalpakstan", "qoraqalpogiston"],
}

# ── build lookup tables (all keyed by norm_city) ─────────────────────────────────
_CITY2REGION: dict[str, str] = {}
for _reg, _cities in _ALL_REGIONS.items():
    for _c in _cities:
        _CITY2REGION.setdefault(norm_city(_c), _reg)

_REGION_KEYS: dict[str, str] = {}
for _reg in _ALL_REGIONS:
    _REGION_KEYS[norm_city(_reg)] = _reg
for _reg, _al in _REGION_ALIASES.items():
    for _a in _al:
        _REGION_KEYS[norm_city(_a)] = _reg

_COUNTRY_KEYS: dict[str, str] = {}
for _country, _al in _COUNTRY_ALIASES.items():
    _COUNTRY_KEYS[norm_city(_country)] = _country
    for _a in _al:
        _COUNTRY_KEYS[norm_city(_a)] = _country

_CITY2COUNTRY: dict[str, str] = {}
for _reg, _country in _REGION_COUNTRY.items():
    _CITY2COUNTRY.setdefault(norm_city(_reg), _country)
    for _c in _ALL_REGIONS.get(_reg, []):
        _CITY2COUNTRY.setdefault(norm_city(_c), _country)
for _country, _cities in _COUNTRY_FLAT.items():
    for _c in _cities:
        _CITY2COUNTRY.setdefault(norm_city(_c), _country)
for _k, _country in _COUNTRY_KEYS.items():
    _CITY2COUNTRY.setdefault(_k, _country)



# ── Alternate spellings (Russian vs Uzbek forms) -> ONE canonical place ────────
# Loads are stored exactly as written, so "Коканд" and "Qoqon" must resolve to the same city,
# otherwise Russian-written loads become invisible to Uzbek searches (and vice versa).
_CITY_ALT = {
    "Toshkent": ["Tashkent"], "Chirchiq": ["Chirchik"], "Olmaliq": ["Almalyk"],
    "Bekobod": ["Bekabad"], "Angren": [], "Yangiyol": ["Yangiyul"],
    "Buxoro": ["Bukhara", "Buxara"], "Kogon": ["Kagan"], "Gijduvon": ["Gizhduvan"],
    "Navoiy": ["Navoi"], "Zarafshon": ["Zarafshan"], "Uchquduq": ["Uchkuduk"],
    "Fargona": ["Fergana", "Ferghana"], "Qoqon": ["Kokand", "Kokan"],
    "Margilon": ["Margilan"], "Quvasoy": ["Kuvasay"], "Rishton": ["Rishtan"],
    "Andijon": ["Andijan"], "Asaka": [], "Xonobod": ["Khanabad"], "Qorasuv": ["Karasu"],
    "Namangan": [], "Chust": [], "Uchqorgon": ["Uchkurgan"], "Kosonsoy": ["Kasansay"],
    "Samarqand": ["Samarkand"], "Kattaqorgon": ["Kattakurgan"], "Urgut": [],
    "Qarshi": ["Karshi"], "Shahrisabz": ["Shakhrisabz"], "Kitob": ["Kitab"],
    "Guzor": ["Guzar"], "Koson": ["Kasan"], "Muborak": ["Mubarek"],
    "Termiz": ["Termez"], "Denov": ["Denau"], "Sherobod": ["Sherabad"],
    "Shorchi": ["Shurchi"], "Boysun": ["Baysun"],
    "Jizzax": ["Dzhizak", "Djizak", "Jizzakh"], "Gagarin": [], "Zomin": ["Zaamin"],
    "Guliston": ["Gulistan"], "Yangiyer": [], "Sirdaryo": ["Syrdarya", "Sirdarya"],
    "Urganch": ["Urgench"], "Xiva": ["Khiva"], "Hazorasp": ["Khazarasp"],
    "Gurlan": ["Gurlen"], "Pitnak": [],
    "Nukus": [], "Xojayli": ["Khodjeyli"], "Chimboy": ["Chimbay"],
    "Beruniy": ["Beruni"], "Turtkol": ["Turtkul"], "Qongirot": ["Kungrad"],
    "Moskva": ["Moscow"], "Sankt-Peterburg": ["Saint-Petersburg", "Spb"],
    "Almaty": ["Alma-Ata"], "Shymkent": ["Chimkent"], "Astana": ["Nur-Sultan"],
    "Bishkek": ["Bishkek"], "Dushanbe": ["Dushanbe"],
}

_ALIAS2CANON: dict[str, str] = {}
for _canon, _alts in _CITY_ALT.items():
    _ALIAS2CANON[norm_city(_canon)] = _canon
    for _a in _alts:
        _ALIAS2CANON[norm_city(_a)] = _canon

# alt spellings inherit the canonical place's region + country
for _key, _canon in list(_ALIAS2CANON.items()):
    _ck = norm_city(_canon)
    if _ck in _CITY2REGION:
        _CITY2REGION.setdefault(_key, _CITY2REGION[_ck])
    if _ck in _CITY2COUNTRY:
        _CITY2COUNTRY.setdefault(_key, _CITY2COUNTRY[_ck])

# Russian-form REGION names, so "Бухара" / "Fergana" are recognised as regions
_REGION_ALT = {
    "Toshkent": ["Tashkent"], "Buxoro": ["Bukhara", "Buxara"], "Navoiy": ["Navoi"],
    "Fargona": ["Fergana", "Ferghana"], "Andijon": ["Andijan"], "Samarqand": ["Samarkand"],
    "Jizzax": ["Dzhizak", "Djizak", "Jizzakh"], "Xorazm": ["Khorezm"],
    "Qashqadaryo": ["Kashkadarya"], "Surxondaryo": ["Surkhandarya"],
    "Sirdaryo": ["Syrdarya"], "Qoraqalpogiston": ["Karakalpakstan"],
}
for _reg, _alts in _REGION_ALT.items():
    if _reg in _ALL_REGIONS:
        for _a in _alts:
            _REGION_KEYS[norm_city(_a)] = _reg


def classify_query(query: str):
    """Return ('country'|'region'|'city'|'any', canonical_name_or_None) for a search term."""
    qn = norm_city(query)
    if not qn:
        return ("any", None)
    if qn in _COUNTRY_KEYS:
        return ("country", _COUNTRY_KEYS[qn])
    if qn in _REGION_KEYS:
        return ("region", _REGION_KEYS[qn])
    return ("city", None)


@lru_cache(maxsize=8192)
def _resolve(pn: str):
    """(region, country) for a normalized place key, with a fuzzy fallback for typos."""
    if not pn:
        return (None, None)
    if pn in _CITY2COUNTRY or pn in _CITY2REGION:
        return (_CITY2REGION.get(pn), _CITY2COUNTRY.get(pn))
    best, score = None, 0.0
    for key in _CITY2COUNTRY:
        r = _SM(None, pn, key).ratio()
        if r > score:
            best, score = key, r
    if best and score >= 0.85:
        return (_CITY2REGION.get(best), _CITY2COUNTRY.get(best))
    return (None, None)


def region_of(place: str):
    return _resolve(norm_city(place))[0]


def country_of(place: str):
    return _resolve(norm_city(place))[1]


def location_match(load_place: str, query: str) -> bool:
    """True if a load whose origin/destination is `load_place` should show for `query`,
    honoring the country > region > district hierarchy."""
    if not (query or "").strip():
        return True
    kind, name = classify_query(query)
    if kind == "country":
        return country_of(load_place) == name
    if kind == "region":
        return region_of(load_place) == name or norm_city(load_place) == norm_city(name)
    # plain city/district: same canonical place (handles Коканд == Qoqon), else fuzzy
    ca = _ALIAS2CANON.get(norm_city(load_place))
    cb = _ALIAS2CANON.get(norm_city(query))
    if ca and cb:
        return ca == cb
    return city_match(load_place, query)


def has_known_place(text: str) -> bool:
    """True if the text mentions any place we know (city / district / region / country)."""
    for tok in re.split(r"[^\w']+", text or ""):
        if len(tok) < 3:
            continue
        k = norm_city(tok)
        if k and (k in _CITY2COUNTRY or k in _REGION_KEYS or k in _COUNTRY_KEYS):
            return True
    return False
