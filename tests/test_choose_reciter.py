"""Which reciter recites a passage: fits, variety, then closest to a minute."""

import pytest

from quran_reels import reciters
from quran_reels.reciters import Option
from quran_reels.selector.calendar import State


class Cfg:
    def __init__(self, avoid_last=2):
        self.content = {"rotation": {"reciters": ["omar_hisham", "minshawi", "sayegh"],
                                     "avoid_last": avoid_last},
                        "passage": {"max_seconds": 90, "target_seconds": 60}}


@pytest.fixture
def seconds(monkeypatch):
    table = {}
    monkeypatch.setattr(reciters, "options",
                        lambda cfg, key: [Option(n, s, "" if s else "not split")
                                          for n, s in table[key].items()])
    return table


def test_the_closest_to_a_minute_among_those_that_fit(seconds):
    seconds["2:1-5"] = {"omar_hisham": None, "minshawi": 95.0, "sayegh": 62.0}
    assert reciters.choose(Cfg(), "2:1-5", [])[0] == "sayegh"        # Minshawi: too long
    seconds["112"] = {"omar_hisham": 25.0, "minshawi": 26.0, "sayegh": 18.0}
    assert reciters.choose(Cfg(), "112", [])[0] == "minshawi"        # a short surah: slower


def test_the_last_reciters_are_avoided_unless_nothing_else_fits(seconds):
    seconds["114"] = {"omar_hisham": 47.0, "minshawi": 40.0, "sayegh": 35.0}
    assert reciters.choose(Cfg(), "114", ["omar_hisham"])[0] == "minshawi"
    assert reciters.choose(Cfg(), "114", ["minshawi", "omar_hisham"])[0] == "sayegh"
    seconds["2:282"] = {"omar_hisham": None, "minshawi": 130.0, "sayegh": 88.0}
    assert reciters.choose(Cfg(), "2:282", ["sayegh"])[0] == "sayegh"   # the only one


def test_no_reciter_ready_publishes_nothing(seconds):
    seconds["2:255"] = {"omar_hisham": None, "minshawi": None, "sayegh": None}
    with pytest.raises(SystemExit, match="quran-reels split 2:255"):
        reciters.choose(Cfg(), "2:255", [])


def test_recent_reciters_in_publication_order():
    state = State({"slots": {
        "2026-11-06/evening": {"reciter": "sayegh"},
        "2026-11-06/morning": {"reciter": "minshawi"},
        "2026-11-05/evening": {"reciter": "omar_hisham"},
        "2026-11-05/morning": {}}})
    assert reciters.recent_reciters(state, {"morning": 0, "evening": 1}) == [
        "omar_hisham", "minshawi", "sayegh"]


def test_the_configured_rotation_names_known_reciters():
    from quran_reels.config import load

    cfg = load()
    assert set(reciters.rotation(cfg)) <= set(cfg.content["reciters"])
