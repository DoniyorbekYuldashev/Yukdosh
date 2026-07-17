from app.parser.geo import location_match, classify_query


def test_region_matches_its_districts():
    assert location_match("Kitob", "Qashqadaryo")      # district in region
    assert location_match("Qarshi", "Qashqadaryo")
    assert location_match("Urganch", "Xorazm")
    assert not location_match("Kitob", "Xorazm")       # wrong region


def test_district_search_is_exact():
    assert location_match("Qarshi", "Qarshi")
    assert not location_match("Kitob", "Qarshi")       # different district


def test_country_matches_everything_inside():
    assert location_match("Kitob", "Uzbekistan")
    assert location_match("Urganch", "Ozbekiston")     # Uzbek spelling
    assert location_match("Almaty", "Kazakhstan")
    assert not location_match("Almaty", "Russia")


def test_cross_border_example():
    assert location_match("Ворсино", "Russia")         # Moscow-oblast town
    assert location_match("Ворсино", "Moskva")
    assert location_match("Сырдарья", "Uzbekistan")    # UZ, not RU


def test_classify():
    assert classify_query("Qashqadaryo")[0] == "region"
    assert classify_query("кашкадарья")[1] == "Qashqadaryo"
    assert classify_query("Rossiya")[0] == "country"
    assert classify_query("Qarshi")[0] == "city"
