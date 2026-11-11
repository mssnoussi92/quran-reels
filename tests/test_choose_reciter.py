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
                        lambda cfg, key, claimed=(): [
                            Option(n, None if n in claimed else s, "" if s else "not split")
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


def test_a_claimed_reciter_is_never_chosen_again(seconds):
    # Meta muted one of its reels (state `claimed`, daily.py): out of the rotation for good
    seconds["2:255"] = {"ghamdi": 56.6, "sayegh": 49.6, "budair": 45.5}
    assert reciters.choose(Cfg(), "2:255", [])[0] == "ghamdi"
    assert reciters.choose(Cfg(), "2:255", [], claimed={"ghamdi"})[0] == "sayegh"


def test_options_mark_claimed_reciters_not_ready(monkeypatch):
    monkeypatch.setattr(reciters, "rotation", lambda cfg: ["rifai", "budair"])
    monkeypatch.setattr(reciters, "with_reciter", lambda cfg, name: name)
    monkeypatch.setattr(reciters, "passage_seconds", lambda cfg, key: Option(cfg, 50.0))
    opts = reciters.options(None, "2:255", claimed={"rifai"})
    assert [(o.name, o.seconds) for o in opts] == [("rifai", None), ("budair", 50.0)]
    assert "revendiqué" in opts[0].why


def test_a_platform_that_claims_the_reciter_gets_another_one():
    class C:
        def __init__(self):
            self.content = {"passage": {"max_seconds": 90, "target_seconds": 60}}
            self.project = {"platforms": {"youtube": {"exclude_reciters": ["budair"],
                                                      "max_seconds": 180}}}
    opts = [Option("omar_hisham", None, "not split"), Option("minshawi", 132.1),
            Option("sayegh", 109.0), Option("budair", 87.6)]
    assert reciters.choose_for(C(), "youtube", "sayegh", opts) == "sayegh"     # not claimed
    assert reciters.choose_for(C(), "youtube", "budair", opts) == "sayegh"     # 18:1-10
    assert reciters.choose_for(C(), "facebook", "budair", opts) == "budair"    # Meta: fine
    long = [Option("minshawi", 200.0), Option("budair", 87.6)]
    assert reciters.choose_for(C(), "youtube", "budair", long) is None         # over 3 min


class Platforms:
    """18:1-10: Budair 87.6 s (the rotation's choice on Friday), As-Sayegh 109 s."""

    def __init__(self, **youtube):
        self.content = {"passage": {"max_seconds": 90, "target_seconds": 60},
                        "rotation": {"reciters": ["minshawi", "sayegh", "budair"]},
                        "reciters": {n: {} for n in ("minshawi", "sayegh", "budair")}}
        self.project = {"platforms": {"facebook": {"enabled": True},
                                      "youtube": {"max_seconds": 180, **youtube}}}


@pytest.fixture
def sayegh(monkeypatch):
    """passage_seconds for the reciter with_reciter was asked for: answers[key] or 109 s."""
    answers = {}
    monkeypatch.setattr(reciters, "with_reciter", lambda cfg, name: name)
    monkeypatch.setattr(reciters, "passage_seconds",
                        lambda name, key: answers.get(key, Option(name, 109.0)))
    return answers


def test_a_platform_with_its_own_reciter_takes_him_and_no_one_else(sayegh):
    """YouTube: always Tawfiq As-Sayegh (owner's choice, 2026-11-11)."""
    cfg = Platforms(reciter="sayegh", exclude_reciters=["budair"])
    assert reciters.fixed_on(cfg, "youtube") == "sayegh" and not reciters.fixed_on(cfg, "facebook")
    assert reciters.fixed_reciters(cfg) == ["sayegh"]
    assert reciters.allowed_on(cfg, "youtube", "sayegh")
    assert not reciters.allowed_on(cfg, "youtube", "minshawi")      # not claimed, not him
    assert reciters.allowed_on(cfg, "facebook", "minshawi")
    assert reciters.other_for(cfg, "youtube", "18:1-10", "sayegh") is None     # the same video
    assert reciters.other_for(cfg, "facebook", "18:1-10", "budair") is None
    assert reciters.other_for(cfg, "youtube", "18:1-10", "budair") == Option("sayegh", 109.0)
    # A claim on Meta takes him out of the rotation, not off YouTube.
    assert reciters.other_for(cfg, "youtube", "18:1-10", "minshawi",
                              claimed={"sayegh"}) == Option("sayegh", 109.0)


def test_no_one_stands_in_for_a_platforms_own_reciter(sayegh):
    cfg = Platforms(reciter="sayegh")
    sayegh["102:1-8"] = Option("sayegh", None, "surah 102 not split")
    opt = reciters.other_for(cfg, "youtube", "102:1-8", "minshawi")
    assert opt.seconds is None and reciters.why(opt) == "sourate 102 pas encore découpée"
    sayegh["2:282-282"] = Option("sayegh", 200.0)                   # longer than a Short
    opt = reciters.other_for(cfg, "youtube", "2:282-282", "minshawi")
    assert (opt.name, opt.seconds) == ("sayegh", None)
    assert reciters.why(opt) == "200 s, plus que 180 s"
    assert reciters.fixed_gaps(cfg, "youtube", ["18:1-10", "102:1-8", "2:282-282"]) == {
        "102:1-8": "surah 102 not split", "2:282-282": "200 s, over 180 s"}
    assert reciters.fixed_gaps(cfg, "facebook", ["102:1-8"]) == {}


def test_without_its_own_reciter_a_platform_takes_any_it_does_not_claim(seconds):
    cfg = Platforms(exclude_reciters=["budair"])
    assert reciters.fixed_on(cfg, "youtube") is None and reciters.fixed_reciters(cfg) == []
    assert reciters.other_for(cfg, "youtube", "18:1-10", "minshawi") is None
    seconds["18:1-10"] = {"minshawi": 132.1, "sayegh": 109.0, "budair": 87.6}
    assert reciters.other_for(cfg, "youtube", "18:1-10", "budair") == Option("sayegh", 109.0, "")
    seconds["18:1-10"] = {"minshawi": 200.0, "sayegh": None, "budair": 87.6}
    opt = reciters.other_for(cfg, "youtube", "18:1-10", "budair")
    assert opt.seconds is None and "aucun autre récitateur" in opt.why


def test_the_configured_youtube_reciter_is_tawfiq_as_sayegh():
    from quran_reels.config import load

    cfg = load()
    assert reciters.fixed_on(cfg, "youtube") == "sayegh"
    assert set(reciters.fixed_reciters(cfg)) <= set(cfg.content["reciters"])
    assert reciters.with_reciter(cfg, "sayegh").content["reciter"]["label"] == "Tawfiq As-Sayegh"
