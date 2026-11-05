from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from quran_reels.config import Config
from quran_reels.models import Ayah, AyahRef, Passage
from quran_reels.passage import needs_basmala
from quran_reels.render.frames import TEMPLATES, ayah_context

BASMALA = "بِسْمِ ٱللَّهِ ٱلرَّحْمَـٰنِ ٱلرَّحِيمِ"


def cfg(enabled=True, skip=(9,)) -> Config:
    content = {"basmala": {"enabled": enabled, "audio": "bismillah", "skip_surahs": list(skip)}}
    return Config(root=Path("."), project={"content": content}, backgrounds=[], gloss_headwords={})


def test_basmala_before_every_passage_even_mid_surah():
    assert needs_basmala(cfg(), 93, 1)
    assert needs_basmala(cfg(), 2, 255)          # a passage from the middle of a surah


def test_no_basmala_for_at_tawbah_nor_before_al_fatiha_1():
    assert not needs_basmala(cfg(), 9, 1)
    assert not needs_basmala(cfg(), 9, 40)
    assert not needs_basmala(cfg(), 1, 1)        # 1:1 is the basmala itself
    assert needs_basmala(cfg(), 1, 2)


def test_basmala_can_be_turned_off():
    assert not needs_basmala(cfg(enabled=False), 93, 1)


def test_basmala_frame_has_no_reference_nor_number():
    passage = Passage(93, 1, 11, "الضحى", "Ad-Duhaa")
    basmala = Ayah(ref=AyahRef(1, 1), text=BASMALA,
                   translation="In the name of Allāh, the Entirely Merciful, the Especially Merciful.")
    ctx = ayah_context(passage, basmala, basmala=True)
    assert (ctx["ref"], ctx["ayah_number"]) == ("", "")
    html = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True) \
        .get_template("reel.html.j2").render(
            layer="content", fonts_dir="", safe={"top": 250, "bottom": 420, "sides": 90},
            highlight="#f6c86b", handle="@h", credit="c", gloss_source="s", **ctx)
    assert BASMALA.split()[0] in html and "﴿" not in html and "· 1:1" not in html
    assert "سورة الضحى" in html


def test_passage_segments_start_with_the_basmala():
    p = Passage(93, 1, 2, "الضحى", "Ad-Duhaa",
                ayahs=[Ayah(AyahRef(93, 1), "a", "a", seconds=2.0),
                       Ayah(AyahRef(93, 2), "b", "b", seconds=3.0)],
                basmala=Ayah(AyahRef(1, 1), BASMALA, "t", seconds=6.0))
    assert [a.ref for a in p.segments] == [AyahRef(1, 1), AyahRef(93, 1), AyahRef(93, 2)]
    assert p.seconds == 11.0


def test_series_title_on_the_first_frame_and_first_caption_line():
    from quran_reels.render import caption

    passage = Passage(2, 201, 201, "البقرة", "Al-Baqarah",
                      ayahs=[Ayah(AyahRef(2, 201), "رَبَّنَآ ءَاتِنَا", "Our Lord, give us")],
                      basmala=Ayah(AyahRef(1, 1), BASMALA, "In the name of Allāh"),
                      label_ar="آيات الدعاء · ٤ من ٣٨",
                      label_en="Supplications from the Quran · 4/38")
    assert ayah_context(passage, passage.basmala, basmala=True, first=True)["series"] == \
        "آيات الدعاء · ٤ من ٣٨"
    assert ayah_context(passage, passage.ayahs[0])["series"] == ""     # only the first frame
    content = {"reciter": {"label": "R"}, "translation": {"label": "T"},
               "glosses": {"label": "G"}}
    c = Config(root=Path("."), project={"content": content, "video": {"handle": "@h"}},
               backgrounds=[], gloss_headwords={})
    assert caption(c, passage).splitlines()[0] == "Supplications from the Quran · 4/38"


def test_hashtags_brand_first_then_series_surah_broad_reciter_glosses():
    from quran_reels.models import WordGloss
    from quran_reels.render import hashtags

    content = {"reciter": {"label": "R", "hashtags": ["#Alafasy"]},
               "glosses": {"label": "G", "hashtags": ["#تفسير_القرآن"]}}
    c = Config(root=Path("."), project={"content": content, "captions": {
        "brand": "#QuranWordsDaily", "broad": ["#Quran", "#القرآن_الكريم"]}},
        backgrounds=[], gloss_headwords={})
    p = Passage(93, 1, 11, "الضحى", "Ad-Duhaa", series_tags=("#JuzAmma", "#جزء_عم"),
                ayahs=[Ayah(AyahRef(93, 2), "وَٱلَّيْلِ إِذَا سَجَىٰ", "t")])
    assert hashtags(c, p) == ["#QuranWordsDaily", "#Quran", "#JuzAmma", "#SurahAdDuhaa",
                              "#سورة_الضحى", "#القرآن_الكريم", "#جزء_عم", "#Alafasy"]
    p.ayahs[0].glosses = [WordGloss(AyahRef(93, 2), "سَجَىٰ", "سكن", "e")]
    p2 = Passage(3, 1, 5, "آل عمران", "Ali 'Imran", ayahs=p.ayahs)
    assert hashtags(c, p2)[2:4] == ["#SurahAliImran", "#سورة_آل_عمران"]
    assert hashtags(c, p2)[-1] == "#تفسير_القرآن"


def test_caption_file_round_trip_keeps_body_and_hashtags(tmp_path):
    import json

    from quran_reels.models import Reel
    from quran_reels.publish import load_reel

    work = tmp_path / "093_001-011"
    (work / "preview").mkdir(parents=True)
    tags = ["#QuranWordsDaily", "#Quran"]
    (work / "caption.txt").write_text(
        Reel(Passage(93, 1, 11, "الضحى", "Ad-Duhaa"), tmp_path / "x.mp4", "Body\n",
             hashtags=tags).text(), encoding="utf-8")
    (work / "manifest.json").write_text(json.dumps({
        "passage": "93:1-11", "surah": {"name_ar": "الضحى", "name_en": "Ad-Duhaa"},
        "hashtags": tags, "ayahs": [{"ref": "93:1", "glosses": [], "start": 0.4,
                                     "seconds": 3.0}]}), encoding="utf-8")
    reel = load_reel(tmp_path / "093_001-011.mp4")
    assert (reel.caption, reel.hashtags) == ("Body\n", tags)
    assert reel.text(1) == "Body\n\n#QuranWordsDaily\n"
