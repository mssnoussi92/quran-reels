from pathlib import Path

from quran_reels.config import Config
from quran_reels.models import AyahRef, GlossEntry
from quran_reels.passage import anchor

ED = "ar-ghareeb-ibn-qutaybah"


def cfg(headwords=None) -> Config:
    content = {"glosses": {"max_per_ayah": 2, "max_chars": 170}}
    return Config(root=Path("."), project={"content": content}, backgrounds=[],
                  gloss_headwords=headwords or {})


def entry(ref, lemma, text):
    return GlossEntry(ref=AyahRef.parse(ref), lemma=lemma, text=text, edition=ED)


def test_whole_quotation_is_highlighted_by_default():
    e = entry("93:2", "وَاللَّيْلِ إِذَا سَجَى", "إذا سكَن. وذلك عند تناهي ظلامِه ورُكودِه.")
    [g] = anchor([e], "وَٱلَّيْلِ إِذَا سَجَىٰ", cfg())
    assert g.positions == (0, 1, 2)
    assert g.word == "وَٱلَّيْلِ إِذَا سَجَىٰ"
    assert g.gloss == "إذا سكَن. وذلك عند تناهي ظلامِه ورُكودِه."
    assert g.lemma == "وَاللَّيْلِ إِذَا سَجَى"


def test_editor_can_narrow_the_highlight():
    e = entry("93:2", "وَاللَّيْلِ إِذَا سَجَى", "إذا سكَن.")
    [g] = anchor([e], "وَٱلَّيْلِ إِذَا سَجَىٰ",
                 cfg({"93:2": {"وَاللَّيْلِ إِذَا سَجَى": "سَجَى"}}))
    assert (g.positions, g.word) == ((2,), "سَجَىٰ")


def test_particles_trimmed_and_uthmani_word_shown():
    e = entry("93:3", "وَمَا قَلَى", "ما أبْغَضك.")
    [g] = anchor([e], "مَا وَدَّعَكَ رَبُّكَ وَمَا قَلَىٰ", cfg())
    assert (g.positions, g.word, g.gloss) == ((4,), "قَلَىٰ", "ما أبْغَضك.")


def test_entry_for_another_ayah_is_left_out():
    e = entry("17:30", "فَلا تُسْرِفْ فِي الْقَتْلِ", "...")
    text = "إِنَّ رَبَّكَ يَبْسُطُ ٱلرِّزْقَ لِمَن يَشَآءُ وَيَقْدِرُ ۚ إِنَّهُۥ كَانَ بِعِبَادِهِۦ خَبِيرًۢا بَصِيرًا"
    assert anchor([e], text, cfg()) == []
