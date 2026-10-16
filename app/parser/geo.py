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
                   "Uralsk", "Ekibastuz", "Temirtau", "Zhezkazgan", "Balqash", "Saryagash", "Kentau",
                   "Атырау", "Atirau", "Кызылорда", "Арыс", "Сарыагаш", "Сарыагач", "Келес",
                   "Актогай", "Бакты", "Джамбулская", "Жамбыл", "Тараз", "Актобе", "Костанай",
                   "Усть-Каменогорск", "Семей", "Экибастуз", "Жезказган", "Туркестан", "Кентау",
                   # look like Uzbek places to the fuzzy matcher (Shardara~Sirdaryo, Zharkent~Parkent)
                   "Шардара", "Shardara", "Жаркент", "Zharkent", "Бахты", "Бахти", "Bakhty",
                   "Сарань", "Saran"],
    "Russia": ["Moskva", "Sankt-Peterburg", "Novosibirsk", "Yekaterinburg", "Krasnodar", "Kazan",
               "Samara", "Rostov", "Chelyabinsk", "Ufa", "Volgograd", "Voronej", "Saratov",
               "Orenburg", "Nijniy Novgorod", "Perm", "Krasnoyarsk", "Omsk", "Tyumen", "Tula",
               "Lipetsk", "Belgorod", "Astraxan", "Ekaterinburg",
               # seen in real posts (most frequent first)
               "Kirov", "Yegoryevsk", "Егорьевск", "Tobolsk", "Barnaul", "Kaluga", "Sharya", "Vologda",
               "Cherepovets", "Shatura", "Tambov", "Severouralsk", "Smolensk", "Syktyvkar", "Izhevsk",
               "Tomsk", "Asino", "Ivanovo", "Volchansk", "Makhachkala", "Махачкала", "Sergiev Posad",
               "Klin", "Kurganinsk", "Yaroslavl", "Kostroma", "Irkutsk", "Taganrog", "Verkhnyaya Tura",
               "Верхняя Тура", "Verxnotura", "Novorossiysk", "Yelabuga", "Елабуга", "Ilsky",
               "Elektrogorsk", "Rubtsovsk", "Lobnya", "Alapaevsk", "Nizhnekamsk", "Krymsk", "Grozny",
               "Veliky Novgorod", "Stavropol", "Krasnouralsk", "Lyudinovo", "Людиново", "Bryansk",
               "Pyatigorsk", "Vladimir", "Balabanovo", "Ryazan", "Murom", "Kemerovo",
               "Khanty-Mansiysk", "Tver", "Boguchany", "Karpinsk", "Peresvet", "Sayanogorsk",
               "Sterlitamak", "Vokhtoga", "Вохтога", "Kursk", "Oryol", "Penza", "Ulyanovsk",
               "Kaliningrad", "Murmansk", "Arkhangelsk", "Petrozavodsk", "Novokuznetsk", "Surgut",
               "Nizhnevartovsk", "Tolyatti", "Naberezhnye Chelny", "Cheboksary", "Saransk", "Kurgan",
               "Magnitogorsk", "Vladivostok", "Khabarovsk", "Chita", "Ulan-Ude", "Abakan", "Sochi",
               "Vladikavkaz", "Nalchik", "Derbent", "Khasavyurt", "Yakutsk", "Norilsk", "Novy Urengoy",
               "Noyabrsk", "Orsk", "Engels", "Kamyshin", "Volzhsky", "Dzerzhinsk", "Kolomna",
               "Serpukhov", "Obninsk", "Kovrov", "Rybinsk", "Velikiye Luki", "Pskov", "Ukhta",
               "Vorkuta", "Kotlas", "Miass", "Zlatoust", "Nefteyugansk",
               # Cyrillic forms where the Latin spelling normalizes differently (ы, ж, ё)
               "Сыктывкар", "Ижевск", "Крымск", "Набережные Челны", "Ростов-на-Дону", "Дзержинск",
               "Орел", "Орёл", "Воронеж", "Voronezh", "Нижнекамский", "Томский", "Иркутский",
               "Электрогорский", "Электрагорский", "Шуя", "Волоколамск", "Белорецк", "Ейск",
               "Галич", "Лесосибирск", "Lesosibirsk", "Свердловская", "Sverdlovsk", "Коми",
               "Дагестан", "Карелия", "Татарстан", "Башкортостан", "Чечня", "Якутия", "Пермь",
               "Сургут", "Нижневартовск", "Тольятти", "Чебоксары", "Ульяновск", "Ярославль",
               "Новый Уренгой", "Ноябрьск", "Ханты-Мансийск", "Кызыл", "Ува", "Uva"],
    "Belarus": ["Minsk", "Brest", "Borisov", "Gomel", "Grodno", "Vitebsk", "Mogilev", "Bobruisk",
                "Baranovichi", "Molodechno", "Svisloch", "Свислочь", "Orsha", "Pinsk", "Lida",
                "Речица", "Ивацевичи", "Солигорск", "Жодино"],
    "Azerbaijan": ["Baku", "Boku", "Ganja", "Sumgait", "Mingachevir"],
    "Georgia": ["Tbilisi", "Poti", "Batumi", "Kutaisi", "Rustavi"],
    "Armenia": ["Yerevan", "Gyumri"],
    "Lithuania": ["Vilnius", "Kaunas", "Klaipeda"],
    "Latvia": ["Riga", "Daugavpils"],
    "Estonia": ["Tallinn"],
    "Poland": ["Warsaw", "Varshava", "Lodz", "Poznan", "Wroclaw", "Krakow", "Malaszewicze"],
    "Germany": ["Berlin", "Hamburg", "Munich", "Frankfurt", "Duisburg", "Bremen"],
    "China": ["Urumqi", "Urumchi", "Урумчи", "Alashankou", "Алашанькоу", "Kashgar", "Кашгар",
              "Yiwu", "Guangzhou", "Beijing", "Shanghai", "Xian"],
    "Afghanistan": ["Kabul", "Mazar-i-Sharif", "Мазари-Шариф", "Mazari Sharif", "Hairatan",
                    "Хайратон", "Herat", "Kandahar", "Kunduz"],
    "Iran": ["Tehran", "Bandar Abbas", "Mashhad", "Tabriz"],
    "Kyrgyzstan": ["Bishkek", "Osh", "Jalal-Abad", "Karakol", "Talas", "Naryn", "Batken", "Tokmok",
                   "Kara-Balta", "Kant", "Uzgen", "Kara-Suu"],
    "Tajikistan": ["Dushanbe", "Khujand", "Xujand", "Bokhtar", "Kurgan-Tyube", "Kulob", "Istaravshan",
                   "Panjakent", "Isfara", "Konibodom", "Tursunzoda", "Vahdat", "Hisor"],
    "Uzbekistan": ["Vodiy", "Водий", "Наваи", "Ахангаран", "Akchalak", "Акчалак", "Qoraqalpoq",
                   "Nazarbek", "Назарбек", "Keles"],  # cities are in the region layer; "Vodiy" = Fergana valley
    "Turkmenistan": ["Ashgabat", "Ашхабад", "Turkmenabat", "Dashoguz", "Mary", "Balkanabat",
                     "Turkmenbashi", "Sarakhs", "Сарахс", "Саракс", "Farap", "Фарап"],
    "Turkey": ["Istanbul", "Stambul", "Стамбул", "Ankara", "Izmir", "Bursa", "Mersin", "Gaziantep",
               "Gebze", "Гебзе", "Tuzla", "Тузла", "Kocaeli", "Konya", "Kayseri", "Antalya"],
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
    "Belarus": ["belarus", "belarus'", "беларусь", "белоруссия", "беларуссия", "belorussiya", "belarusiya",
                "белорус", "belarusiya", "rb"],
    "Azerbaijan": ["azerbaijan", "ozarbayjon", "азербайджан", "озарбайжон"],
    "Georgia": ["georgia", "gruziya", "грузия", "gurjiston"],
    "Armenia": ["armenia", "armaniston", "армения", "armeniya"],
    "Lithuania": ["lithuania", "litva", "литва"],
    "Latvia": ["latvia", "latviya", "латвия"],
    "Estonia": ["estonia", "estoniya", "эстония"],
    "Poland": ["poland", "polsha", "польша"],
    "Germany": ["germany", "germaniya", "германия"],
    "China": ["china", "xitoy", "китай", "хитой"],
    "Afghanistan": ["afghanistan", "afgoniston", "афганистан", "афгонистон"],
    "Iran": ["iran", "eron", "иран", "эрон"],
    "Ukraine": ["ukraine", "ukraina", "украина"],
    "Moldova": ["moldova", "молдова", "молдавия"],
    "Austria": ["austria", "avstriya", "австрия"],
    "Italy": ["italy", "italiya", "италия"],
    "Romania": ["romania", "ruminiya", "румыния"],
    "United Kingdom": ["uk", "england", "angliya", "великобритания", "англия", "buyuk britaniya"],
    "Czechia": ["czechia", "chexiya", "чехия"],
    "Hungary": ["hungary", "vengriya", "венгрия"],
    "Bulgaria": ["bulgaria", "bolgariya", "болгария"],
    "Netherlands": ["netherlands", "niderlandiya", "голландия", "нидерланды", "gollandiya"],
    "France": ["france", "fransiya", "франция"],
    "Spain": ["spain", "ispaniya", "испания"],
    "Mongolia": ["mongolia", "mongoliya", "монголия"],
    "Pakistan": ["pakistan", "pokiston", "пакистан"],
    "India": ["india", "hindiston", "индия"],
    "UAE": ["uae", "oae", "оаэ", "dubai", "dubay", "дубай"],
}

# Shown before each place on cards. Unknown country -> no flag (better than a wrong one).
FLAGS = {
    "Uzbekistan": "🇺🇿", "Kazakhstan": "🇰🇿", "Russia": "🇷🇺", "Kyrgyzstan": "🇰🇬",
    "Tajikistan": "🇹🇯", "Turkmenistan": "🇹🇲", "Turkey": "🇹🇷", "Belarus": "🇧🇾",
    "Azerbaijan": "🇦🇿", "Georgia": "🇬🇪", "Armenia": "🇦🇲", "Lithuania": "🇱🇹",
    "Latvia": "🇱🇻", "Estonia": "🇪🇪", "Poland": "🇵🇱", "Germany": "🇩🇪", "China": "🇨🇳",
    "Afghanistan": "🇦🇫", "Iran": "🇮🇷", "Ukraine": "🇺🇦", "Moldova": "🇲🇩", "Austria": "🇦🇹",
    "Italy": "🇮🇹", "Romania": "🇷🇴", "United Kingdom": "🇬🇧", "Czechia": "🇨🇿", "Hungary": "🇭🇺",
    "Bulgaria": "🇧🇬", "Netherlands": "🇳🇱", "France": "🇫🇷", "Spain": "🇪🇸", "Mongolia": "🇲🇳",
    "Pakistan": "🇵🇰", "India": "🇮🇳", "UAE": "🇦🇪",
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
    "Bekobod": ["Bekabad"], "Angren": [], "Chinoz": ["Chinaz"], "Yangiyol": ["Yangiyul"],
    "Buxoro": ["Bukhara", "Buxara"], "Kogon": ["Kagan"], "Gijduvon": ["Gizhduvan"],
    "Navoiy": ["Navoi"], "Zarafshon": ["Zarafshan"], "Uchquduq": ["Uchkuduk"],
    "Fargona": ["Fergana", "Ferghana"], "Qoqon": ["Kokand", "Kokan", "Kukon", "Kokon"],
    "Margilon": ["Margilan"], "Quvasoy": ["Kuvasay"], "Rishton": ["Rishtan"],
    "Andijon": ["Andijan"], "Asaka": [], "Xonobod": ["Khanabad"], "Qorasuv": ["Karasu"],
    "Namangan": [], "Chust": [], "Uchqorgon": ["Uchkurgan"], "Kosonsoy": ["Kasansay"],
    "Samarqand": ["Samarkand"], "Kattaqorgon": ["Kattakurgan"], "Urgut": [],
    "Qarshi": ["Karshi"], "Shahrisabz": ["Shakhrisabz"], "Kitob": ["Kitab"],
    "Guzor": ["Guzar"], "Koson": ["Kasan"], "Muborak": ["Mubarek"],
    "Termiz": ["Termez"], "Denov": ["Denau"], "Sherobod": ["Sherabad"],
    "Shorchi": ["Shurchi"], "Boysun": ["Baysun"],
    "Jizzax": ["Dzhizak", "Djizak", "Jizzakh", "Djizzak", "Жиззак"], "Gagarin": [], "Zomin": ["Zaamin"],
    "Guliston": ["Gulistan"], "Yangiyer": [], "Sirdaryo": ["Syrdarya", "Sirdarya"],
    "Urganch": ["Urgench"], "Xiva": ["Khiva"], "Hazorasp": ["Khazarasp"],
    "Gurlan": ["Gurlen"], "Pitnak": [],
    "Nukus": [], "Xojayli": ["Khodjeyli"], "Chimboy": ["Chimbay"],
    "Beruniy": ["Beruni"], "Turtkol": ["Turtkul"], "Qongirot": ["Kungrad"],
    "Moskva": ["Moscow", "Maskva", "Масква"], "Sankt-Peterburg": ["Saint-Petersburg", "Spb", "Piter"],
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

# every region spelling ("Хорезм", "Сурхандарья") also tells the country
for _k, _reg in _REGION_KEYS.items():
    _CITY2COUNTRY.setdefault(_k, _REGION_COUNTRY.get(_reg))

# "Xorazm viloyati", "Toshkent shahri", "Ташкентская обл." -> drop the admin word
_ADMIN_WORD = re.compile(r"(?i)^(?:viloyat\w*|vil|respublika\w*|tuman\w*|shahr\w*|обл\w*|край|"
                         r"республика|район|р-н|г|город|poytaxt)$")
# Uzbek case endings in places the parser copied as written: Toshkentdan, Qarshiga
_UZ_SUFFIX = re.compile(r"(?i)(?:gacha|dan|ga|da|ni|ning|гача|дан|га|да|ни|нинг)$")


def _exact(k: str):
    if k and (k in _CITY2COUNTRY or k in _CITY2REGION or k in _REGION_KEYS):
        return (_CITY2REGION.get(k) or _REGION_KEYS.get(k), _CITY2COUNTRY.get(k))
    return None


@lru_cache(maxsize=8192)
def _resolve_place(place: str):
    """(region, country) for a place as written. Tries the whole name, then without admin
    words, then word by word ("Киров Мураши", "Toshkentdan"), then a fuzzy match for typos."""
    pn = norm_city(place)
    hit = _exact(pn)
    if hit:
        return hit
    words = [w for w in re.findall(r"[\w'’ʻ‘`-]+", place or "") if not _ADMIN_WORD.match(w)]
    hit = _exact(norm_city(" ".join(words)))
    if hit:
        return hit
    for w in words:
        k = norm_city(w)
        if len(k) < 4:                       # short words ("Pop", "Osh") only as a whole name
            continue
        stem = norm_city(_UZ_SUFFIX.sub("", w))
        hit = _exact(k) or (len(stem) >= 4 and _exact(stem))
        if hit:
            return hit
    return _resolve(pn)


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
    return _resolve_place(place or "")[0]


def country_of(place: str):
    return _resolve_place(place or "")[1]


def flag_of(place: str) -> str:
    """'🇺🇿' for Toshkent / Farg'ona, '🇷🇺' for Moskva; '' when the country is unknown."""
    return FLAGS.get(country_of(place), "")


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
