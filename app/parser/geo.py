"""Geographic hierarchy: Country -> Region -> District/City.

Makes search smart about administrative levels:
  * search a REGION (e.g. "Qashqadaryo")  -> returns loads from its districts (Kitob, Qarshi, ...)
  * search a DISTRICT/CITY (e.g. "Qarshi") -> returns that place
  * search a COUNTRY (e.g. "Rossiya")      -> returns everything inside that country

Built on norm_city(), so it is script- and typo-tolerant (Cyrillic/Latin, q/k, x/h, ...).
Extend the dicts freely as you see new places in real posts.
"""
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


def region_of(place: str):
    return _CITY2REGION.get(norm_city(place))


def country_of(place: str):
    return _CITY2COUNTRY.get(norm_city(place))


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
    # plain city/district — fall back to fuzzy cross-script matching
    return city_match(load_place, query)
