"""Background choice from the translation, and seamless clip loops."""

import subprocess
from pathlib import Path

import pytest

from quran_reels.config import load
from quran_reels.models import Ayah, AyahRef, Passage
from quran_reels.sources import backgrounds


def passage(key: str, *translations: str) -> Passage:
    s, rng = key.split(":")
    a, b = (int(x) for x in rng.split("-"))
    return Passage(int(s), a, b, "", "", ayahs=[
        Ayah(AyahRef(int(s), a + i), "", t) for i, t in enumerate(translations)])


@pytest.fixture
def cfg():
    return load()


def test_the_config_lists_valid_backgrounds(cfg):
    bgs, themes, default = backgrounds.catalogue(cfg)
    ids = {b.id for b in bgs}
    assert len(ids) == len(bgs) and set(default) <= ids
    for b in bgs:
        assert bool(b.scene) != bool(b.file), b.id
        assert set(b.tags) <= set(themes), b.id
        assert 0 <= b.focus <= 1
    assert all(any(t in b.tags for b in bgs) for t in themes)    # every theme can be shown


def test_mountains_win_over_a_passing_mention_of_the_heavens(cfg):
    p = passage("78:6-7", "Have We not made the earth a resting place?",
                "And the mountains as stakes? Above you are the heavens.")
    bg, theme, scores = backgrounds.choose(cfg, p)
    assert (theme, bg.id) == ("mountains", "mountains-clouds")
    assert scores["mountains"] == 3 and scores["sky"] == 1


def test_whole_words_only_and_the_basmala_is_not_counted(cfg):
    p = passage("112:1-2", "Say, He is Allah, [who is] One,", "Allah, the Eternal Refuge.")
    p.basmala = Ayah(AyahRef(1, 1), "", "In the name of Allah, the Entirely Merciful")
    p.ayahs[0].translation += " overseas"            # not the sea
    _, theme, scores = backgrounds.choose(cfg, p)
    assert theme == "" and not scores


def test_a_passage_without_theme_takes_a_default_and_always_the_same(cfg):
    p = passage("114:1-6", "Say, I seek refuge in the Lord of mankind,")
    first = backgrounds.choose(cfg, p)[0]
    assert first.id in backgrounds.catalogue(cfg)[2]
    assert all(backgrounds.choose(cfg, p)[0] == first for _ in range(3))


def test_the_night_passage_of_ad_duha(cfg):
    p = passage("93:1-2", "By the morning brightness", "And [by] the night when it covers with "
                "darkness,")
    bg, theme, _ = backgrounds.choose(cfg, p)
    assert theme == "night" and bg.id == "night"


def test_make_loop_blends_the_end_into_the_start(tmp_path: Path):
    src = tmp_path / "src.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=s=320x180:r=30:d=4", "-pix_fmt", "yuv420p", str(src)], check=True)
    out = backgrounds.make_loop(src, tmp_path / "loop.mp4", 90, 160, 30, fade=1.0)
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-count_frames",
                            "-show_entries", "stream=width,height,nb_read_frames", "-of", "csv=p=0",
                            str(out)], capture_output=True, text=True, check=True).stdout
    assert probe.strip() == "90,160,90"                 # 4 s - 1 s faded, cropped to 9:16
