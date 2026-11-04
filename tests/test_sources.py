from quran_reels.models import AyahRef, parse_passage
from quran_reels.sources.quran_com import clean_translation
from quran_reels.sources.tafsir_app import excerpt, parse_entries

R = AyahRef(2, 7)
ED = "ar-ghareeb-ibn-qutaybah"


def test_clean_translation_drops_footnote_markers_only():
    raw = "And [by] the night when it covers with darkness,<sup foot_note=197778>1</sup>"
    assert clean_translation(raw) == "And [by] the night when it covers with darkness,"
    assert clean_translation("Muḥammad &amp; [you]") == "Muḥammad & [you]"


def test_parse_single_entry():
    [e] = parse_entries("﴿وَمَا قَلَى﴾ ما أبْغَضك.", AyahRef(93, 3), ED)
    assert (e.lemma, e.text, e.edition) == ("وَمَا قَلَى", "ما أبْغَضك.", ED)


def test_parse_several_entries_and_parenthesised_lemma():
    raw = "﴿لا رَيْبَ فِيهِ﴾ لا شكَّ فيه.\n﴿هُدًى لِلْمُتَّقِينَ﴾ أي: رُشدًا لهم إلى الحق."
    assert [e.lemma for e in parse_entries(raw, R, ED)] == ["لا رَيْبَ فِيهِ", "هُدًى لِلْمُتَّقِينَ"]
    [e] = parse_entries('و(الصَّيِّبُ) المطر؛ "فَيْعِل" من "صَابَ يَصُوبُ".', R, ED)
    assert e.lemma == "الصَّيِّبُ" and e.text.startswith("المطر؛")


def test_parse_removes_editor_footnotes_and_keeps_continuations():
    raw = ("﴿الْوَسْوَاسِ الْخَنَّاسِ﴾ إبليسُ يُوَسْوِسُ؛ فإذا ذُكر اللهُ: خَنَسَ، "
           "[[هذا قول ابن عباس والفراء.]] أي أقْصَرَ وكَفَّ.\nيقال: عال الرجلُ.")
    [e] = parse_entries(raw, R, ED)
    assert "[[" not in e.text and "ابن عباس" not in e.text
    assert e.text == "إبليسُ يُوَسْوِسُ؛ فإذا ذُكر اللهُ: خَنَسَ، أي أقْصَرَ وكَفَّ.\nيقال: عال الرجلُ."


def test_excerpt_keeps_whole_sentences_only():
    text = "إذا سكَن. وذلك عند تناهي ظلامِه ورُكودِه.\nفقرة ثانية."
    assert excerpt(text, 200) == "إذا سكَن. وذلك عند تناهي ظلامِه ورُكودِه."
    assert excerpt(text, 12) == "إذا سكَن."
    assert excerpt(text, 5) is None


def test_parse_passage():
    assert parse_passage("93:1-3") == (93, 1, 3)
    assert parse_passage("93:2") == (93, 2, 2)
    for bad in ("93", "93:3-1", "115:1", "a:b"):
        try:
            parse_passage(bad)
        except ValueError:
            continue
        raise AssertionError(bad)


def test_parse_entry_introduced_by_waqawluhu():
    raw = "وقوله ﴿وَجَنَّةٍ عَرْضُهَا السَّمَاوَاتُ وَالأَرْضُ﴾ يريد سعتَها."
    [e] = parse_entries(raw, AyahRef(3, 133), ED)
    assert (e.lemma, e.text) == ("وَجَنَّةٍ عَرْضُهَا السَّمَاوَاتُ وَالأَرْضُ", "يريد سعتَها.")


def test_parse_drops_separator_colon():
    [e] = parse_entries("و(الإلُّ) : العهدُ ويقال: القرابة", AyahRef(9, 8), ED)
    assert (e.lemma, e.text) == ("الإلُّ", "العهدُ ويقال: القرابة")
