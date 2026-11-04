from quran_reels.arabic import (
    arabic_digits,
    locate,
    normalize,
    quoted_words,
    similarity,
    trim,
    words,
)


def test_normalize_uthmani_and_imlai_agree():
    # tafsir.app (imla'i) vs Quran.com (Uthmani)
    assert normalize("سَجَى") == normalize("سَجَىٰ")
    assert normalize("قَلَى") == normalize("قَلَىٰ")
    assert normalize("ٱلصَّلَوٰةَ") == normalize("الصَّلَاةَ")
    assert normalize("وَلَلْـَٔاخِرَةُ") == normalize("وللآخرة")
    assert normalize("ۚ") == ""


def test_similarity_tolerates_spelling_and_citation_form():
    assert similarity("ٱلْكِتَٰبُ", "الكتاب") >= 0.95
    assert similarity("وَٱلَّيْلِ", "وَاللَّيْلِ") >= 0.7
    assert similarity("الطَّلُّ", "فَطَلٌّ") >= 0.9        # cited with the article
    assert similarity("سجى", "ضحى") < 0.7


def test_locate_lemma_in_ayah():
    ayah = words("وَٱلَّيْلِ إِذَا سَجَىٰ")
    assert locate("وَاللَّيْلِ إِذَا سَجَى", ayah) == [0, 1, 2]
    ayah = words("مَا وَدَّعَكَ رَبُّكَ وَمَا قَلَىٰ")
    assert locate("وَمَا قَلَى", ayah) == [3, 4]
    assert locate("خَتَمَ اللَّهُ", ayah) is None


def test_locate_skips_pause_marks():
    ayah = words("ذَٰلِكَ ٱلْكِتَٰبُ لَا رَيْبَ ۛ فِيهِ ۛ هُدًى لِّلْمُتَّقِينَ")
    assert locate("لا رَيْبَ فِيهِ", ayah) == [2, 3, 5]


def test_vocative_is_one_word_in_uthmani():
    assert quoted_words("قَالَ يَا بُشْرَى هَذَا غُلامٌ") == ["قَالَ", "يَابُشْرَى", "هَذَا", "غُلامٌ"]
    ayah = words("وَجَآءَتْ سَيَّارَةٌ فَأَرْسَلُوا۟ وَارِدَهُمْ فَأَدْلَىٰ دَلْوَهُۥ ۖ قَالَ يَـٰبُشْرَىٰ "
                 "هَـٰذَا غُلَـٰمٌ")
    assert locate("قَالَ يَا بُشْرَى هَذَا غُلامٌ", ayah) == [7, 8, 9, 10]


def test_trim_drops_particles_at_the_edges_only():
    def kept(lemma):
        q = quoted_words(lemma)
        start, end = trim(q)
        return q[start:end]

    assert kept("فَإِنْ عُثِرَ") == ["عُثِرَ"]
    assert kept("وَمَا قَلَى") == ["قَلَى"]
    assert kept("فَلا جُنَاحَ عَلَيْهِمَا") == ["جُنَاحَ"]
    assert kept("فِي مَا أَفَضْتُمْ فِيهِ") == ["أَفَضْتُمْ"]
    assert kept("حَبِطَتْ أَعْمَالُهُمْ") == ["حَبِطَتْ", "أَعْمَالُهُمْ"]
    assert kept("وَاللَّيْلِ إِذَا سَجَى") == ["وَاللَّيْلِ", "إِذَا", "سَجَى"]
    assert kept("صُمٌّ بُكْمٌ") == ["صُمٌّ", "بُكْمٌ"]            # بُكْمٌ is not بِكُمْ
    assert kept("لا") == ["لا"]


def test_arabic_digits():
    assert arabic_digits(93) == "٩٣"


def test_short_words_do_not_collapse_to_one_letter():
    ayah = words("لَا يَرْقُبُوا۟ فِيكُمْ إِلًّا وَلَا ذِمَّةً")
    assert locate("الإلُّ", ayah) == [3]
