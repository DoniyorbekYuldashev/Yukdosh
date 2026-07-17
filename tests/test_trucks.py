from app.parser.normalize import canonicalize_trucks as ct


def test_paravoz_listed_in_addition():
    assert ct("тент паравоз") == "tent, paravoz"
    assert ct("паровоз тент") == "paravoz, tent"


def test_isuzu_and_sizes():
    assert ct("isuzu") == "isuzu"
    assert ct("kichkina isuzu") == "isuzu"
    assert ct("katta isuzi") == "isuzu"     # typo tolerated


def test_multi_type_and_empty():
    assert ct("Тент - Реф") == "tent, ref"
    assert ct("izoterm ref") == "isotherm, ref"
    assert ct("farqi yoq") == ""            # unknown -> any truck
