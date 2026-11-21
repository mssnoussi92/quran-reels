"""Each line of a description keeps its own direction wherever YouTube shows it (bidi.py)."""

from quran_reels.bidi import LRE, RLE, directed, directions, needs_mark, plain

TITLE = "القرآن والسنة في حياتك اليومية · Quran & Sunnah for everyday life"
BULLET = "• تلاوة كل صباح: الترجمة الإنجليزية (Sahih International) ومعاني الكلمات."
VERSE = "كِتَـٰبٌ أَنزَلْنَـٰهُ إِلَيْكَ مُبَـٰرَكٌ لِّيَدَّبَّرُوٓا۟ ءَايَـٰتِهِۦ وَلِيَتَذَكَّرَ أُو۟لُوا۟ ٱلْأَلْبَـٰبِ"
ENGLISH = "Quran every morning. Every verse from a published source."
TRANSLATION = '"[This is] a blessed Book which We have revealed to you." (Sad, 38:29)'
PURE = "Quran every morning"


def test_a_line_gets_the_mark_of_its_own_direction_only_where_it_needs_one():
    text = f"{TITLE}\n\n{BULLET}\n{VERSE}\n{ENGLISH}\n{TRANSLATION}\n{PURE}\n•\n"
    out = directed(text).split("\n")
    assert out[0] == RLE + TITLE                 # both directions in the line
    assert out[1] == ""                          # an empty line stays empty
    assert out[2] == RLE + BULLET                # a bullet first, a period last, English inside
    assert out[3] == VERSE                       # Arabic from its first letter to its last vowel
    assert out[4] == LRE + ENGLISH               # its period on the right, on a right-to-left page
    assert out[5] == LRE + TRANSLATION           # « [This is] » stays at the start
    assert out[6] == PURE and out[7] == "•"      # nothing to fix: no mark
    assert directions(text) == "AR+ AR+ AR EN+ EN+ EN"


def test_no_word_changes_and_twice_is_once():
    text = f"{TITLE}\n{BULLET}\n{VERSE}\n{ENGLISH}\n{TRANSLATION}"
    assert plain(directed(text)) == text
    assert directed(directed(text)) == directed(text)
    assert len(directed(text)) - len(text) == 4  # one mark a line that needs it, no closing mark


def test_a_vowel_sign_at_the_end_is_not_a_sign_without_direction():
    assert not needs_mark("بِسْمِ ٱللَّهِ")
    assert needs_mark("بِسْمِ ٱللَّهِ.") and needs_mark("(1) بسم الله")
