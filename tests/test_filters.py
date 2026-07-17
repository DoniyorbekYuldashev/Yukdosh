import pytest


def test_junk_prefilter():
    telethon = pytest.importorskip("telethon")  # pipeline imports the scraper
    from app.pipeline import _looks_like_junk
    assert _looks_like_junk("👍👍🔥")            # stickers/emoji
    assert _looks_like_junk("https://t.me/x")   # link only
    assert not _looks_like_junk("Тошкент — Москва тент 20т +998901234567")


def test_truck_filter_shows_unspecified_to_all():
    from app.bot.queries import _truck_ok
    assert _truck_ok("tent, ref", "tent")       # driver wants tent, load has it
    assert not _truck_ok("tent", "ref")         # load is tent-only, driver wants ref
    assert _truck_ok("", "tent")                # load type unspecified -> shown to all
    assert _truck_ok("ref", "")                 # driver picked nothing -> all
