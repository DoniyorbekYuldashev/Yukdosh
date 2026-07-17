from app.schemas import ParsedLoad
from app.parser.dedup import dedup_hash as h


def test_repost_across_channels_collapses():
    a = ParsedLoad(origin_city="Toshkent", destination_city="Moskva",
                   contact_phone="+998 90 123 45 67", price_amount=2000, comment="tent kerak")
    b = ParsedLoad(origin_city="Тошкент", destination_city="Москва",
                   contact_phone="998901234567", comment="срочно тент")
    assert h(a) == h(b)     # same route+phone, different wording/format


def test_different_route_stays_distinct():
    a = ParsedLoad(origin_city="Toshkent", destination_city="Moskva", contact_phone="+998901234567")
    c = ParsedLoad(origin_city="Toshkent", destination_city="Samarqand", contact_phone="+998901234567")
    assert h(a) != h(c)
