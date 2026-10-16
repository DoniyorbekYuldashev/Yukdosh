"""Zero-dependency test runner — no pytest, no pip needed.
Run:  py run_tests.py
Checks the core logic: geo hierarchy, truck types, and deduplication."""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows console: emoji/Cyrillic safe

from app.parser.geo import location_match, classify_query
from app.parser.normalize import canonicalize_trucks as ct
from app.schemas import ParsedLoad
from app.parser.dedup import dedup_hash as h

_passed = 0
_failed = 0


def check(desc, got, want):
    global _passed, _failed
    ok = got == want
    _passed += ok
    _failed += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} {desc}" + ("" if ok else f"   got={got!r} want={want!r}"))


print("\n[Geo hierarchy: region/country -> districts]")
check("region Qashqadaryo finds district Kitob", location_match("Kitob", "Qashqadaryo"), True)
check("region Xorazm finds Urganch", location_match("Urganch", "Xorazm"), True)
check("wrong region excluded", location_match("Kitob", "Xorazm"), False)
check("district search is exact", location_match("Qarshi", "Qarshi"), True)
check("country Uzbekistan finds Kitob", location_match("Kitob", "Uzbekistan"), True)
check("country (Uzbek spelling) finds Urganch", location_match("Urganch", "Ozbekiston"), True)
check("Vorsino belongs to Russia", location_match("Ворсино", "Russia"), True)
check("Syrdarya is Uzbekistan not Russia", location_match("Сырдарья", "Russia"), False)
check("classify region", classify_query("Qashqadaryo")[0], "region")
check("classify country", classify_query("Rossiya")[0], "country")

print("\n[Truck types: paravoz, isuzu, typos]")
check("tent + paravoz listed together", ct("тент паравоз"), "tent, paravoz")
check("isuzu recognized", ct("kichkina isuzu"), "isuzu")
check("isuzu typo tolerated", ct("katta isuzi"), "isuzu")
check("multi-type", ct("Тент - Реф"), "tent, ref")
check("unknown -> any", ct("farqi yoq"), "")

print("\n[Deduplication: cross-channel reposts collapse]")
a = ParsedLoad(origin_city="Toshkent", destination_city="Moskva", contact_phone="+998 90 123 45 67", comment="tent")
b = ParsedLoad(origin_city="Тошкент", destination_city="Москва", contact_phone="998901234567", comment="срочно")
c = ParsedLoad(origin_city="Toshkent", destination_city="Samarqand", contact_phone="+998901234567")
check("same route+phone -> same fingerprint", h(a) == h(b), True)
check("different route -> different fingerprint", h(a) != h(c), True)

print("\n[Cards: no source link, numbered, 'Asl matn' buttons; group posting]")
from types import SimpleNamespace
from app.broadcast import normalize_chat, build_post
from app.bot.formatting import format_load, format_results, original_kb
from app.bot.clean import clean_original, strip_source
check("t.me link -> @username", normalize_chat("https://t.me/yuk_guruh"), "@yuk_guruh")
check("bare name -> @username", normalize_chat("yuk_guruh"), "@yuk_guruh")
check("numeric chat id kept", normalize_chat("-1001234567890"), "-1001234567890")
card = SimpleNamespace(id=7, listing_type="load", is_load=True, origin_city="Toshkent", destination_city="Сарахс",
                       truck_type="tent", truck_count=5, weight_tons=18, cargo_type="запчасти & <детали>",
                       price_amount=None, price_currency="", contact_phone="+998 93 995 34 04", comment="",
                       source_group="https://t.me/Yuk_markazi_yuk_yukla", source_msg_id="16700127",
                       posted_at=None)
own = SimpleNamespace(**{**vars(card), "id": 8, "source_group": "bot"})
check("card has no source link by default", "t.me/" in format_load(card, "uz") or "manbasi" in format_load(card, "uz"), False)
check("link mode adds the post link",
      'href="https://t.me/Yuk_markazi_yuk_yukla/16700127"' in format_load(card, "uz", link=True), True)
check("bot-posted load never gets a link", "href" in format_load(own, "uz", link=True), False)
check("no-buttons mode: cards not numbered, no hint",
      "<b>1.</b>" in format_results([card, own], "x", "uz", buttons=False)
      or "asl matni" in format_results([card, own], "x", "uz", buttons=False), False)
check("special chars escaped for Telegram HTML", "&amp; &lt;детали&gt;" in format_load(card, "uz"), True)
page = format_results([card, own], "🔍", "uz")
check("multi-card message is numbered", "<b>1.</b>" in page and "<b>2.</b>" in page, True)
check("multi-card message explains the N buttons", "asl matni" in page, True)
kb = original_kb([card, own], "uz")
check("one original-text button per scraped load (none for bot posts)",
      [b.callback_data for r in kb.inline_keyboard for b in r], ["raw:7"])
check("single card gets a labelled button",
      original_kb([card], "uz").inline_keyboard[0][0].text.endswith("Asl matn"), True)
check("links, @mentions and #hashtags stripped",
      strip_source("Tent kerak @Yuk_markazi https://t.me/x/1 #yuk tel 901234567 a@b.uz").split(),
      ["Tent", "kerak", "tel", "901234567", "a@b.uz"])
ad = ("Toshkent - Qo'shrabot\nTent kerak, 20 t, 901234567\n"
      "Yukingizni joylashtiring - LOGIT SMARTBOT uni hamkor Telegram guruhlariga tarqatadi.\n"
      "LOGIT SMARTBOT'ga kirish:\nYuk Markazi guruhi\nKanal: @logist\nAdmin: @someone")
check("ad / group / admin lines removed, load kept",
      clean_original(ad), "Toshkent - Qo'shrabot\nTent kerak, 20 t, 901234567")
check("-obot place names are not ads",
      clean_original("Samarqand Qoshrabot\nNAMANGANDAN BEGOBOTGA TENT KERAK\nБУХОРО -АШХАБОТ"),
      "Samarqand Qoshrabot\nNAMANGANDAN BEGOBOTGA TENT KERAK\nБУХОРО -АШХАБОТ")
check("contact line mentioning Telegram keeps its phone",
      clean_original("Tel +998910577979 (WhatsApp, Telegram, Imo)"), "Tel +998910577979 (WhatsApp, Telegram, Imo)")
check("'Kanalizatsionnye truby' (sewer pipes) is cargo, not a channel",
      clean_original("Груз: Канализационные трубы"), "Груз: Канализационные трубы")
diip = ("[**diip.uz**](https://diip.uz/applink)**; da yangi yuk!**\n**🇺🇿Toshkent → 🇦🇿Boku**\n"
        "Нуриддин Гайратов : +998880800706\n"
        "Bu yuk [diip.uz](https://diip.uz/applink); ilovasi orqali bepul va avtomatik tarqatilmoqda.")
check("freight-app ads (diip.uz) and markdown removed",
      clean_original(diip), "🇺🇿Toshkent → 🇦🇿Boku\nНуриддин Гайратов : +998880800706")
check("'-ilova' surnames are not app ads",
      clean_original("Dilnoza Isroilova, tent kerak"), "Dilnoza Isroilova, tent kerak")
check("wa.me link keeps its phone number",
      clean_original("Телефон: [Wa.me/+79646254848](http://Wa.me/+79646254848)"), "Телефон: +79646254848")
check("e-mail is not a domain ad", clean_original("Pochta: info@yuk.uz"), "Pochta: info@yuk.uz")
noted = SimpleNamespace(**{**vars(card), "comment": "Оплата нагляд, @kanal"})
check("card comment loses @mentions", "@kanal" in format_load(noted, "uz"), False)
text, used = build_post([card] * 3, "uz", "@yukdoshbot")
check("digest holds all loads that fit", len(used), 3)
check("digest ends with bot pointer", text.rstrip().endswith("@yukdoshbot"), True)

print("\n[Flags: country flag before each place on cards]")
from app.parser.geo import flag_of
check("Uzbek city, region and suffixed forms -> 🇺🇿",
      [flag_of(p) for p in ("Toshkent", "Farg'ona", "Xorazm Viloyati", "Toshkentdan", "Хоразим")], ["🇺🇿"] * 5)
check("Moskva / Москва / 'Киров Мураши' -> 🇷🇺",
      [flag_of(p) for p in ("Moskva", "Москва", "Киров Мураши")], ["🇷🇺"] * 3)
check("fuzzy traps: Chinoz is not China, Ува not Quva, Shardara not Sirdaryo",
      [flag_of(p) for p in ("Чиназ", "Ува", "Шардара", "Жаркент")], ["🇺🇿", "🇷🇺", "🇰🇿", "🇰🇿"])
check("ambiguous / unknown places get no flag", [flag_of(p) for p in ("Хоргос", "Симферополь", "Xyzabc")], ["", "", ""])
check("card route line carries flags", "🇺🇿 Toshkent → 🇹🇲 Сарахс" in format_load(card, "uz"), True)

print("\n[Languages: every language has every text]")
from app.bot.i18n import TEXTS, LANG_NAMES, variants
for code in TEXTS:
    check(f"'{code}' has all {len(TEXTS['uz'])} texts", sorted(set(TEXTS["uz"]) - set(TEXTS[code])), [])
check("language picker lists every language", sorted(LANG_NAMES), sorted(TEXTS))
check("menu buttons don't collide across languages",
      len(variants("btn_search")) == len(TEXTS) and len(variants("btn_post")) == len(TEXTS), True)

print(f"\n{'='*40}\nPASSED {_passed}  FAILED {_failed}\n")
raise SystemExit(1 if _failed else 0)
