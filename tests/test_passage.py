from pathlib import Path

import pytest

from quran_reels.config import Config, parse_headwords
from quran_reels.models import AyahRef, GlossEntry
from quran_reels.passage import anchor

ED = "ar-ghareeb-ibn-qutaybah"
AYAH_93_2 = "وَٱلَّيْلِ إِذَا سَجَىٰ"
AYAH_2_7 = ("خَتَمَ ٱللَّهُ عَلَىٰ قُلُوبِهِمْ وَعَلَىٰ سَمْعِهِمْ ۖ وَعَلَىٰٓ أَبْصَـٰرِهِمْ غِشَـٰوَةٌ ۖ "
            "وَلَهُمْ عَذَابٌ عَظِيمٌ")


def cfg(headwords=None) -> Config:
    content = {"glosses": {"max_per_ayah": 2, "max_chars": 170}}
    return Config(root=Path("."), project={"content": content}, backgrounds=[],
                  gloss_headwords=parse_headwords(headwords))


def entry(ref, lemma, text):
    return GlossEntry(ref=AyahRef.parse(ref), lemma=lemma, text=text, edition=ED)


R93_2 = AyahRef(93, 2)
E93_2 = entry("93:2", "وَاللَّيْلِ إِذَا سَجَى", "إذا سكَن. وذلك عند تناهي ظلامِه ورُكودِه.")
E2_7 = entry("2:7", "خَتَمَ اللَّهُ عَلَى قُلُوبِهِمْ وَعَلَى سَمْعِهِمْ", "بمنزلة طَبَعَ الله عليها.")


def test_whole_quotation_is_highlighted_by_default():
    [g] = anchor(R93_2, [E93_2], AYAH_93_2, cfg())
    assert g.positions == (0, 1, 2)
    assert g.word == AYAH_93_2
    assert g.gloss == "إذا سكَن. وذلك عند تناهي ظلامِه ورُكودِه."
    assert g.lemma == "وَاللَّيْلِ إِذَا سَجَى"


def test_one_chosen_word_without_diacritics():
    [g] = anchor(R93_2, [E93_2], AYAH_93_2, cfg({"93:2": "سجى"}))
    assert (g.positions, g.word) == ((2,), "سَجَىٰ")


def test_two_chosen_words_next_to_each_other():
    [g] = anchor(AyahRef(2, 7), [E2_7], AYAH_2_7, cfg({"2:7": "ختم الله"}))
    assert (g.positions, g.word) == ((0, 1), "خَتَمَ ٱللَّهُ")


def test_two_chosen_words_apart_are_shown_with_an_ellipsis():
    [g] = anchor(AyahRef(2, 7), [E2_7], AYAH_2_7, cfg({"2:7": "قلوبهم ختم"}))
    assert (g.positions, g.word) == ((0, 3), "خَتَمَ … قُلُوبِهِمْ")


def test_choice_not_in_the_quotation_keeps_the_default(capsys):
    [g] = anchor(R93_2, [E93_2], AYAH_93_2, cfg({"93:2": "الضحى"}))
    assert g.positions == (0, 1, 2)
    assert "«الضحى» is in no quotation" in capsys.readouterr().err


def test_one_choice_per_gloss_of_the_same_ayah():
    ayah = "ذَٰلِكَ ٱلْكِتَٰبُ لَا رَيْبَ ۛ فِيهِ ۛ هُدًى لِّلْمُتَّقِينَ"
    entries = [entry("2:2", "لا رَيْبَ فِيهِ", "لا شكَّ فيه."),
               entry("2:2", "هُدًى لِلْمُتَّقِينَ", "أي: رُشدًا لهم إلى الحق.")]
    g1, g2 = anchor(AyahRef(2, 2), entries, ayah, cfg({"2:2": ["هدى", "ريب"]}))
    assert (g1.word, g2.word) == ("رَيْبَ", "هُدًى")


def test_particles_trimmed_and_uthmani_word_shown():
    e = entry("93:3", "وَمَا قَلَى", "ما أبْغَضك.")
    [g] = anchor(AyahRef(93, 3), [e], "مَا وَدَّعَكَ رَبُّكَ وَمَا قَلَىٰ", cfg())
    assert (g.positions, g.word, g.gloss) == ((4,), "قَلَىٰ", "ما أبْغَضك.")


def test_entry_for_another_ayah_is_left_out():
    e = entry("17:30", "فَلا تُسْرِفْ فِي الْقَتْلِ", "...")
    text = "إِنَّ رَبَّكَ يَبْسُطُ ٱلرِّزْقَ لِمَن يَشَآءُ وَيَقْدِرُ ۚ إِنَّهُۥ كَانَ بِعِبَادِهِۦ خَبِيرًۢا بَصِيرًا"
    assert anchor(AyahRef(17, 30), [e], text, cfg()) == []


def test_headwords_config_forms():
    parsed = parse_headwords({"93:2": "سجى", "20:131": "زهرة الحياة", "2:2": ["ريب", "هدى"],
                              5582: "x"})
    assert parsed["93:2"] == [("x",)]          # 93:2 written without quotes reads as 5582
    assert parsed["20:131"] == [("زهرة", "الحياة")]
    assert parsed["2:2"] == [("ريب",), ("هدى",)]
    assert parse_headwords({"34:12": "أسلنا عين القطر"})["34:12"] == [("أسلنا", "عين", "القطر")]


@pytest.mark.parametrize("bad", [{"93:2": "أربع كلمات هنا أيضا"}, {"93:2": ""}, {"sajā": "سجى"},
                                 {"93:2": {"وَاللَّيْلِ إِذَا سَجَى": "سَجَى"}}])
def test_headwords_config_errors(bad):
    with pytest.raises(SystemExit):
        parse_headwords(bad)


def test_repository_glosses_yaml_is_valid():
    from quran_reels import config

    root = Path(__file__).resolve().parents[1]
    assert config.load(root).gloss_headwords["93:2"] == [("سجى",)]


# ---- the owner's choice (on-demand reels, /mots) -----------------------------------------

AYAH_93_3 = "مَا وَدَّعَكَ رَبُّكَ وَمَا قَلَىٰ"
R93_3 = AyahRef(93, 3)
E93_3 = [entry("93:3", "مَا وَدَّعَكَ", "ما تركك."), entry("93:3", "وَمَا قَلَى", "وما أبغضك."),
         entry("93:3", "وَدَّعَكَ رَبُّكَ", "ما تركك ربك.")]


def test_a_selection_replaces_the_rules():
    [g] = anchor(R93_3, E93_3, AYAH_93_3, cfg(), [(1, ())])
    assert (g.lemma, g.word) == ("وَمَا قَلَى", "قَلَىٰ")         # particles trimmed as usual
    [g] = anchor(R93_3, E93_3, AYAH_93_3, cfg(), [(0, ("ما", "ودعك"))])
    assert g.positions == (0, 1)
    assert anchor(R93_3, E93_3, AYAH_93_3, cfg(), []) == []        # none
    picked = anchor(R93_3, E93_3, AYAH_93_3, cfg(), [(1, ()), (0, ())])
    assert [g.lemma for g in picked] == ["وَمَا قَلَى", "مَا وَدَّعَكَ"]   # the owner's order


@pytest.mark.parametrize("selection, why", [
    ([(5, ())], "cannot be shown"), ([(0, ("قلى",))], "is not in"),
    ([(0, ()), (2, ())], "the same word")])
def test_a_selection_that_cannot_be_shown_stops_the_rendering(selection, why):
    with pytest.raises(SystemExit, match=why):
        anchor(R93_3, E93_3, AYAH_93_3, cfg(), selection)
