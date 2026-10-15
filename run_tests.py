"""Zero-dependency test runner — no pytest, no pip needed.
Run:  py run_tests.py
Checks the core logic: geo hierarchy, truck types, and deduplication."""
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

print("\n[Group posting: chat ids, cards without source link]")
from types import SimpleNamespace
from app.broadcast import normalize_chat, build_post
from app.bot.formatting import format_load
check("t.me link -> @username", normalize_chat("https://t.me/yuk_guruh"), "@yuk_guruh")
check("bare name -> @username", normalize_chat("yuk_guruh"), "@yuk_guruh")
check("numeric chat id kept", normalize_chat("-1001234567890"), "-1001234567890")
card = SimpleNamespace(listing_type="load", is_load=True, origin_city="Toshkent", destination_city="Сарахс",
                       truck_type="tent", truck_count=5, weight_tons=18, cargo_type="запчасти & <детали>",
                       price_amount=None, price_currency="", contact_phone="+998 93 995 34 04", comment="",
                       source_group="https://t.me/Yuk_markazi_yuk_yukla", source_msg_id="16700127",
                       posted_at=None)
check("bot card keeps source link", "E'lon manbasi" in format_load(card, "uz"), True)
check("group card drops source link", "t.me/" in format_load(card, "uz", source=False), False)
check("special chars escaped for Telegram HTML", "&amp; &lt;детали&gt;" in format_load(card, "uz"), True)
text, used = build_post([card] * 3, "uz", "@yukdoshbot")
check("digest holds all loads that fit", len(used), 3)
check("digest ends with bot pointer", text.rstrip().endswith("@yukdoshbot"), True)

print(f"\n{'='*40}\nPASSED {_passed}  FAILED {_failed}\n")
raise SystemExit(1 if _failed else 0)
