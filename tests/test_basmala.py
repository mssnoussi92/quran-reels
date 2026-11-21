from pathlib import Path

import pytest
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
                      label_ar="آيات الدعاء · 4 من 38",
                      label_en="Supplications from the Quran · 4/38")
    assert ayah_context(passage, passage.basmala, basmala=True, first=True)["series"] == \
        "آيات الدعاء · 4 من 38"
    assert ayah_context(passage, passage.ayahs[0])["series"] == ""     # only the first frame
    content = {"reciter": {"label": "R"}, "translation": {"label": "T"},
               "glosses": {"label": "G"}}
    c = Config(root=Path("."), project={"content": content, "video": {"handle": "@h"}},
               backgrounds=[], gloss_headwords={})
    # titles in Arabic and English (owner, 2026-11-09), the Arabic first everywhere (2026-11-21),
    # one counter
    assert caption(c, passage).splitlines()[0] == \
        "آيات الدعاء · Supplications from the Quran · 4/38"
    # one ayah: «(2:201)», never «(2:201-201)» (seen on 6:17 and 2:255, 2026-11-09)
    assert caption(c, passage).splitlines()[1] == "سورة البقرة · Surah Al-Baqarah (2:201)"


def test_series_titles_never_contain_the_separator():
    """render.series_line splits the labels at « · »: a title must not contain one."""
    import yaml

    for f in sorted(Path("config/series").glob("*.yaml")):
        s = yaml.safe_load(f.read_text(encoding="utf-8"))
        for key in ("title_ar", "title_en"):
            assert " · " not in (s.get(key) or ""), f"{f.name}: {key}"


def test_series_line_without_a_counter():
    from quran_reels.render import series_line

    p = Passage(2, 255, 255, "البقرة", "Al-Baqarah", label_ar="آية الكرسي",
                label_en="Ayat al-Kursi")
    # the Arabic first on every platform, titles and descriptions (owner, 2026-11-21)
    assert series_line(p) == "آية الكرسي · Ayat al-Kursi"
    assert series_line(Passage(93, 1, 11, "الضحى", "Ad-Duhaa")) == ""


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


def test_text_to_paste_on_tiktok_keeps_five_hashtags(tmp_path):
    import json

    from quran_reels.daily import copy_text
    from quran_reels.models import Reel

    work = tmp_path / "114_001-006"
    work.mkdir()
    tags = [f"#t{i}" for i in range(1, 12)]
    (work / "caption.txt").write_text(
        Reel(Passage(114, 1, 6, "الناس", "An-Nas"), tmp_path / "x.mp4", "Body\n",
             hashtags=tags).text(), encoding="utf-8")
    (work / "manifest.json").write_text(json.dumps({
        "passage": "114:1-6", "surah": {"name_ar": "الناس", "name_en": "An-Nas"},
        "hashtags": tags, "ayahs": [{"ref": "114:1", "glosses": [], "start": 0.4,
                                     "seconds": 3.0}]}), encoding="utf-8")
    c = Config(root=Path("."), project={"platforms": {"tiktok": {"max_hashtags": 5}}},
               backgrounds=[], gloss_headwords={})
    assert copy_text(c, tmp_path / "114_001-006.mp4") == "Body\n\n#t1 #t2 #t3 #t4 #t5\n"
    assert copy_text(c, tmp_path / "missing.mp4") == ""


# ---- days without the basmala (content.basmala.days_off; owner's choice, 2026-11-15) -------

def off(start="2026-11-16", until=None, enabled=True) -> Config:
    c = cfg(enabled=enabled)
    c.content["basmala"]["days_off"] = {"from": start, "until": until}
    return c


def test_the_calendar_drops_the_basmala_from_its_first_day_off_until_turned_back_on():
    from datetime import date

    from quran_reels.passage import basmala_on, for_day

    c = off()
    assert basmala_on(c, date(2026, 11, 15)) and for_day(c, date(2026, 11, 15)) is c
    for day in (date(2026, 11, 16), date(2027, 6, 1)):          # no end: until turned back on
        assert not basmala_on(c, day)
        d = for_day(c, day)
        assert not needs_basmala(d, 106, 1)                     # at the start of a surah too
        assert not needs_basmala(d, 18, 17)                     # and mid-surah
    assert needs_basmala(c, 106, 1)                             # cfg itself is not changed
    back = off(until="2026-11-30")                              # turned back on the next day
    assert not basmala_on(back, date(2026, 11, 30)) and basmala_on(back, date(2026, 12, 1))
    assert not basmala_on(cfg(enabled=False), date(2026, 11, 1))


@pytest.mark.parametrize(("days_off", "message"), [
    ({"until": "2026-11-30"}, "give its first day"),
    ({"from": "2026-11-16", "until": "2026-11-01"}, "is before"),
    ({"from": "16/11/2026"}, "is not a day"),
    ({"from": "2026-11-16", "weekdays": ["friday"]}, "only from and until")])
def test_a_wrong_days_off_says_what_to_write(days_off, message):
    from datetime import date

    from quran_reels.passage import basmala_on

    c = cfg()
    c.content["basmala"]["days_off"] = days_off
    with pytest.raises(SystemExit, match=message):
        basmala_on(c, date(2026, 11, 16))


def test_the_owners_choice_no_basmala_from_2026_11_16():
    """config/project.yaml as the owner chose on 2026-11-15 (CLAUDE.md, « Basmala »)."""
    from datetime import date

    from quran_reels.config import load
    from quran_reels.passage import basmala_on

    real = load()
    assert basmala_on(real, date(2026, 11, 15))
    assert not basmala_on(real, date(2026, 11, 16))


def test_the_daily_run_renders_a_day_off_without_the_basmala(monkeypatch, tmp_path):
    from datetime import datetime
    from types import SimpleNamespace
    from zoneinfo import ZoneInfo

    import quran_reels.render as render_mod
    from quran_reels import daily
    from quran_reels.models import PublishResult, PublishStatus
    from tests.test_calendar import SERIES, schedule

    seen = []
    monkeypatch.setattr(daily, "load_series", lambda c: SERIES)
    monkeypatch.setattr(daily, "load_schedule", lambda c, series: schedule())
    monkeypatch.setattr(daily.publish_mod, "platforms_for", lambda c, req: ["facebook"])
    monkeypatch.setattr(daily.publish_mod, "meta_check", lambda c, p: None)
    monkeypatch.setattr(daily.publish_mod, "publish_reel", lambda c, video, platforms, dry, ch=None:
                        [PublishResult(p, PublishStatus.PUBLISHED, remote_id="1")
                         for p in platforms])

    def render(c, key, *args, **kw):
        seen.append((key, needs_basmala(c, 114, 1)))
        return SimpleNamespace(video=tmp_path / f"{key}.mp4")

    monkeypatch.setattr(render_mod, "render_passage", render)
    c = off(start="2026-11-07")
    c = Config(root=tmp_path, project={**c.project, "platforms": {}}, backgrounds=[],
               gloss_headwords={})
    paris = ZoneInfo("Europe/Paris")
    path = tmp_path / "published.json"
    daily.run(c, path, now=datetime(2026, 11, 5, 7, 20, tzinfo=paris))
    daily.run(c, path, now=datetime(2026, 11, 7, 7, 20, tzinfo=paris))     # Saturday
    assert seen == [("114:1-6", True), ("113:1-5", False)]
