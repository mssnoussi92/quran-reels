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
