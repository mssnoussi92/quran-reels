"""A long ayah on several screens: cuts at pause marks and sentence ends, timed by its words."""

from types import SimpleNamespace

from quran_reels import render
from quran_reels.render import video
from quran_reels.render.screens import plan, translation_pieces

# 2:255 (Uthmani, Quran.com) and Sahih International, as rendered
KURSI = ("ٱللَّهُ لَآ إِلَـٰهَ إِلَّا هُوَ ٱلْحَىُّ ٱلْقَيُّومُ ۚ لَا تَأْخُذُهُۥ سِنَةٌ وَلَا نَوْمٌ ۚ لَّهُۥ مَا فِى "
         "ٱلسَّمَـٰوَٰتِ وَمَا فِى ٱلْأَرْضِ ۗ مَن ذَا ٱلَّذِى يَشْفَعُ عِندَهُۥٓ إِلَّا بِإِذْنِهِۦ ۚ يَعْلَمُ مَا "
         "بَيْنَ أَيْدِيهِمْ وَمَا خَلْفَهُمْ ۖ وَلَا يُحِيطُونَ بِشَىْءٍ مِّنْ عِلْمِهِۦٓ إِلَّا بِمَا شَآءَ ۚ وَسِعَ "
         "كُرْسِيُّهُ ٱلسَّمَـٰوَٰتِ وَٱلْأَرْضَ ۖ وَلَا يَـُٔودُهُۥ حِفْظُهُمَا ۚ وَهُوَ ٱلْعَلِىُّ ٱلْعَظِيمُ")
KURSI_EN = ("Allāh - there is no deity except Him, the Ever-Living, the Self-Sustaining. Neither "
            "drowsiness overtakes Him nor sleep. To Him belongs whatever is in the heavens and "
            "whatever is on the earth. Who is it that can intercede with Him except by His "
            "permission? He knows what is [presently] before them and what will be after them, "
            "and they encompass not a thing of His knowledge except for what He wills. His Kursī "
            "extends over the heavens and the earth, and their preservation tires Him not. And He "
            "is the Most High, the Most Great.")


def test_parts_pair_arabic_clauses_with_their_translation():
    tokens = KURSI.split()
    parts = plan(tokens, KURSI_EN, 3, 38.0)
    texts = [" ".join(tokens[p.first:p.end]) for p in parts]
    assert texts[1].startswith("مَن ذَا") and parts[1].translation.startswith("Who is it")
    assert texts[2].startswith("وَلَا يُحِيطُونَ") and parts[2].translation.startswith("and they")
    assert " ".join(texts) == KURSI                         # nothing left out, nothing added
    assert " ".join(p.translation for p in parts) == KURSI_EN
    assert all(tokens[p.first - 1] in "ۖۗۘۙۚۛۜ" for p in parts[1:])   # cut after a pause mark


def test_each_part_starts_when_its_first_word_is_recited():
    tokens = KURSI.split()
    times = [None] * len(tokens)
    times[tokens.index("مَن")], times[tokens.index("يُحِيطُونَ") - 1] = 13.2, 22.4
    parts = plan(tokens, KURSI_EN, 3, 38.0, times)
    assert [p.start for p in parts] == [0.0, 13.2, 22.4]
    unheard = plan(tokens, KURSI_EN, 3, 38.0)              # no word times: by letters
    assert 0 < unheard[1].start < unheard[2].start < 38.0


def test_a_part_too_short_on_screen_joins_its_neighbour():
    tokens = KURSI.split()
    times = [None] * len(tokens)
    times[tokens.index("مَن")], times[tokens.index("يُحِيطُونَ") - 1] = 13.2, 14.0
    parts = plan(tokens, KURSI_EN, 3, 38.0, times)
    assert len(parts) == 2 and parts[1].start == 13.2


def test_translation_pieces_are_sentences_and_clauses_of_long_ones():
    pieces = translation_pieces(KURSI_EN)
    assert pieces[0] == "Allāh - there is no deity except Him, the Ever-Living, the Self-Sustaining."
    assert "".join(pieces).replace(" ", "") == KURSI_EN.replace(" ", "")


def test_screens_split_the_ayah_frames_only():
    t = video.build_timeline([48000, 96000], fps=30, lead=0.4, tail=1.2,
                             screens=[48000, 60000, 36000])
    assert len(t.frame_counts()) == 3 and sum(t.frame_counts()) == t.total_frames
    assert [round(s, 2) for s in t.starts()] == [0.4, 1.4]  # the ayahs' starts are unchanged


def test_each_screen_plays_its_own_image(tmp_path, monkeypatch):
    """No split reads at 70 %: every try is drawn and the first stays the best. A later try must
    not overwrite its images (18:19 on 2026-11-27: the 5-screen images on the 4-screen times)."""
    class Renderer:
        def render(self, layer, dest, **ctx):
            dest.write_text(ctx["translation"])
            return 0.6                                  # every try alike: the first one is kept

    monkeypatch.setattr(render, "part_context",
                        lambda passage, a, start, end, translation, **kw: {"translation": translation})
    ayah = SimpleNamespace(text=KURSI, translation=KURSI_EN, ref=SimpleNamespace(surah=2, ayah=255))
    samples = 38 * video.SAMPLE_RATE
    out = render._long_ayah(Renderer(), SimpleNamespace(audio=None), None, ayah, samples,
                            tmp_path / "002_255", first=False)
    assert len(out) == 2                                # the 2-screen try, drawn first
    assert len({png for png, _, _ in out}) == len(out)
    assert [png.read_text() for png, _, _ in out] == [ctx["translation"] for _, ctx, _ in out]
    assert sum(n for _, _, n in out) == samples


# 18:19 (Uthmani, Quran.com) and Sahih International, as rendered: no pause mark in its last 23 words
CAVE = 'وَكَذَٰلِكَ بَعَثْنَـٰهُمْ لِيَتَسَآءَلُوا۟ بَيْنَهُمْ ۚ قَالَ قَآئِلٌ مِّنْهُمْ كَمْ لَبِثْتُمْ ۖ قَالُوا۟ لَبِثْنَا يَوْمًا أَوْ بَعْضَ يَوْمٍ ۚ قَالُوا۟ رَبُّكُمْ أَعْلَمُ بِمَا لَبِثْتُمْ فَٱبْعَثُوٓا۟ أَحَدَكُم بِوَرِقِكُمْ هَـٰذِهِۦٓ إِلَى ٱلْمَدِينَةِ فَلْيَنظُرْ أَيُّهَآ أَزْكَىٰ طَعَامًا فَلْيَأْتِكُم بِرِزْقٍ مِّنْهُ وَلْيَتَلَطَّفْ وَلَا يُشْعِرَنَّ بِكُمْ أَحَدًا'
CAVE_EN = 'And similarly, We awakened them that they might question one another. Said a speaker from among them, "How long have you remained [here]?" They said, "We have remained a day or part of a day." They said, "Your Lord is most knowing of how long you remained. So send one of you with this silver coin of yours to the city and let him look to which is the best of food and bring you provision from it and let him be cautious. And let no one be aware of you.'


def test_each_sentence_stays_on_the_screen_of_its_words():
    """18:19 on 2026-11-27: «They said, "Your Lord is most knowing…» came one screen before
    قَالُوا۟ رَبُّكُمْ, and «وَلَا» was left on a screen apart from «يُشْعِرَنَّ بِكُمْ أَحَدًا»."""
    tokens = CAVE.split()
    for k in (3, 4, 5):
        parts = plan(tokens, CAVE_EN, k, 47.0)
        for p in parts:
            words = tokens[p.first:p.end]
            if "رَبُّكُمْ" in words:
                assert "Your Lord is most knowing" in p.translation
            if "يُشْعِرَنَّ" in words:
                assert "وَلَا" in words and "let no one be aware" in p.translation
        assert " ".join(p.translation for p in parts) == CAVE_EN


def test_a_screen_without_a_pause_mark_left_starts_at_a_clause():
    """No mark after يَوْمٍ ۚ: the screens start at a word opening a clause (و, ف), never
    inside one (وَلَا | يُشْعِرَنَّ)."""
    tokens = CAVE.split()
    for k in (4, 5):
        for p in plan(tokens, CAVE_EN, k, 47.0)[1:]:
            assert tokens[p.first - 1] in "ۖۗۘۙۚۛۜ" or tokens[p.first][0] in "وف"


def test_the_translation_is_never_cut_inside_brackets():
    from quran_reels.render.screens import translation_clauses

    clauses = [c for c, _ in translation_clauses("and not expose their adornment [i.e., beauty] "
                                                  "except to their husbands, their fathers.")]
    assert all(c.count("[") == c.count("]") for c in clauses)
