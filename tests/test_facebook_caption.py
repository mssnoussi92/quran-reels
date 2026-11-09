"""Facebook's short caption (render.facebook_caption): at most 400 characters with its
hashtags, neither the Arabic text of the ayahs nor the translation (owner's choice, 2026-11-09),
titles in Arabic and English (owner, 2026-11-09), the credits always; too long, hashtags go from
the end. Placeholder translations: no Quran text is typed here. No network."""

import json
import re
from dataclasses import replace

import pytest

from quran_reels import reciters as rec
from quran_reels.config import load
from quran_reels.models import Ayah, AyahRef, Passage, Reel, WordGloss
from quran_reels.ondemand import page
from quran_reels.publish import load_reel
from quran_reels.render import facebook_caption, hashtags

LIMIT = 400
ARABIC = re.compile(r"[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]")
RECITATION = "Recitation: Fares Abbad"
TRANSLATION = "Translation: Sahih International"
MEANINGS = "Word meanings: Tafsir al-Muyassar, King Fahd Complex"


@pytest.fixture
def cfg():
    return rec.with_reciter(load(), "fares_abbad")


def passage(ayahs=1, chars=60, label="The seven munjiyat verses · 2/7", glossed=False):
    p = Passage(6, 17, 16 + ayahs, "الأنعام", "Al-An'am",
                ayahs=[Ayah(AyahRef(6, 17 + i), "كَلِمَة", f"{i}" + "x" * (chars - 1))
                       for i in range(ayahs)],
                basmala=Ayah(AyahRef(1, 1), "بِسْمِ", "basmala"),
                label_ar="السبع آيات المنجيات · ٢ من ٧" if label else "", label_en=label,
                series_tags=("#المنجيات", "#السبع_المنجيات"))
    if glossed:
        p.ayahs[0].glosses = [WordGloss(AyahRef(6, 17), "كَلِمَة", "معنى", "e", positions=(0,))]
    return p


def no_ayah_text(body):
    """Arabic only in the title lines (series, surah), never an ayah or the basmala."""
    rest = body.partition("\n\n")[2]
    return "كَلِمَة" not in body and "بِسْمِ" not in body and not ARABIC.search(rest)


def split(text):
    """(body, hashtags) of a caption whose last paragraph may be its hashtags."""
    body, _, last = text.rpartition("\n\n")
    if last.startswith("#"):
        return body, last.split()
    return text, []


def test_series_reference_credits_handle_and_hashtags(cfg):
    p = passage(chars=60)
    text = facebook_caption(cfg, p, hashtags(cfg, p))
    body, tags = split(text)
    assert len(text) <= LIMIT
    assert body.split("\n\n") == [
        ("The seven munjiyat verses · السبع آيات المنجيات · 2/7\n"
         "Surah Al-An'am (6:17) · سورة الأنعام"),
        f"{RECITATION} · {TRANSLATION}",
        "@quran_words_daily"]
    assert tags == hashtags(cfg, p)[:8]                  # platforms.facebook.max_hashtags
    assert no_ayah_text(body)                            # the ayahs are in the video


def test_never_the_translation_even_a_short_one(cfg):
    for ayahs, chars in ((1, 10), (10, 150)):
        p = passage(ayahs=ayahs, chars=chars)
        text = facebook_caption(cfg, p, hashtags(cfg, p))
        assert "x" * 5 not in text and "17. " not in text   # its translation is in the video
        assert split(text)[1] == hashtags(cfg, p)[:8]


def test_hashtags_go_from_the_end_when_too_long(cfg):
    p = passage(chars=60, label="L" * 230)
    all_tags = hashtags(cfg, p)
    text = facebook_caption(cfg, p, all_tags)
    body, tags = split(text)
    assert len(text) <= LIMIT
    assert 0 < len(tags) < 8 and tags == all_tags[:len(tags)]   # the first ones, in order
    assert len(f"{body}\n\n{' '.join(all_tags[:len(tags) + 1])}") > LIMIT   # as many as fit


@pytest.mark.parametrize("glossed", [False, True])
def test_never_over_400_and_always_credited(cfg, glossed):
    for label in ("", "The first ten verses of Surah Al-Kahf", "L" * 120, "L" * 260):
        for ayahs, chars in ((1, 10), (1, 150), (3, 80), (10, 300)):
            p = passage(ayahs, chars, label, glossed)
            text = facebook_caption(cfg, p, hashtags(cfg, p))
            body, _ = split(text)
            assert 10 <= len(text) <= LIMIT, (label, ayahs, chars)
            assert f"{RECITATION} · {TRANSLATION}" in body
            assert (MEANINGS in body) is glossed         # credited when the reel shows some
            assert no_ayah_text(body)


def test_the_reciter_s_producer_is_credited(cfg):
    p = passage()
    text = facebook_caption(rec.with_reciter(load(), "hudhaifi"), p, hashtags(cfg, p))
    assert "Recitation: Ali Al-Hudhaifi (King Fahd Complex) · " in text


def test_no_short_caption_without_a_limit(cfg):
    project = json.loads(json.dumps(cfg.project))
    del project["platforms"]["facebook"]["max_caption_chars"]
    p = passage()
    assert facebook_caption(replace(cfg, project=project), p, hashtags(cfg, p)) == ""


def test_the_rendered_reel_carries_it_to_facebook_and_its_page(cfg, tmp_path):
    p = passage(glossed=True)
    tags = hashtags(cfg, p)
    short = facebook_caption(cfg, p, tags)
    work = tmp_path / "006_017-017"
    (work / "preview").mkdir(parents=True)
    (work / "caption.txt").write_text(Reel(p, tmp_path / "x.mp4", "Full\n", hashtags=tags)
                                      .text(), encoding="utf-8")
    (work / "manifest.json").write_text(json.dumps({
        "passage": "6:17-17", "surah": {"name_ar": "الأنعام", "name_en": "Al-An'am"},
        "hashtags": tags, "captions": {"facebook": short},
        "ayahs": [{"ref": "6:17", "glosses": [], "start": 0.4, "seconds": 3.0}]}),
        encoding="utf-8")
    reel = load_reel(tmp_path / "006_017-017.mp4")
    assert reel.text_for("facebook", 8) == short
    assert reel.text_for("instagram", 5) == reel.text(5) == "Full\n\n" + " ".join(tags[:5]) + "\n"
    shown = page.captions(cfg, reel, ["facebook", "instagram", "tiktok", "youtube"])
    assert shown == [{"label": "Facebook", "text": short},
                     {"label": "Instagram, TikTok", "text": reel.text(5)}]
    reel.facebook = ""                                   # rendered before: the full caption
    assert reel.text_for("facebook", 8) == reel.text(8)
