"""A long ayah on several screens: cuts at pause marks and sentence ends, timed by its words."""

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
