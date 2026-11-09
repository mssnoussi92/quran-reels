"""Background choice from the translation, and seamless clip loops."""

import re
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
        assert bool(b.scene) != bool(b.file or b.pixabay_id), b.id
        assert set(b.tags) <= set(themes), b.id
        assert 0 <= b.focus <= 1
    assert all(any(t in b.tags for b in bgs) for t in themes)    # every theme can be shown


def test_mountains_win_over_a_passing_mention_of_the_heavens(cfg):
    p = passage("78:6-7", "Have We not made the earth a resting place?",
                "And the mountains as stakes? Above you are the heavens.")
    bg, theme, scores = backgrounds.choose(cfg, p)
    assert theme == "mountains" and "mountains" in bg.tags
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
    assert theme == "night" and "night" in bg.tags


def test_make_loop_blends_the_end_into_the_start(tmp_path: Path):
    src = tmp_path / "src.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=s=320x180:r=30:d=4", "-pix_fmt", "yuv420p", str(src)], check=True)
    out = backgrounds.make_loop(src, tmp_path / "loop.mp4", 90, 160, 30, fade=1.0)
    # ffmpeg only (the static build of the workflows has no ffprobe): size and frame count
    log = subprocess.run(["ffmpeg", "-nostdin", "-i", str(out), "-map", "0:v", "-f", "null", "-"],
                         capture_output=True, text=True, check=True).stderr
    assert re.search(r"Video: .*\b90x160\b", log)
    assert int(re.findall(r"frame=\s*(\d+)", log)[-1]) == 90   # 4 s - 1 s faded, 9:16


def _clip(path, lum):
    import subprocess
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                    "color=c=gray:s=64x36:d=5:r=10", "-vf", f"format=gray,geq=lum='{lum}'",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y", str(path)], check=True)
    return path


def test_motion_tells_a_still_clip_from_a_flashing_one(tmp_path):
    from quran_reels.sources.backgrounds import motion

    still = motion(_clip(tmp_path / "still.mp4", "128"))
    flashing = motion(_clip(tmp_path / "flash.mp4", "if(mod(floor(T),2),230,20)"))
    assert still < 1 and flashing > 150


def test_the_search_leaves_out_a_clip_that_moves_too_fast(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from quran_reels.sources import backgrounds, pixabay

    def hit(i):
        return {"id": i, "tags": "clouds, sky", "duration": 20,
                "videos": {"tiny": {"url": f"https://cdn/{i}.mp4"}}}

    class Client:
        def search(self, q):
            return [hit(1), hit(2), hit(3)]

        def preview(self, h):
            return tmp_path / f"{h['id']}.mp4"

    scores = {"1.mp4": 34.9, "2.mp4": 9.5, "3.mp4": 23.5}
    monkeypatch.setattr(backgrounds, "motion", lambda p: scores[p.name])
    cfg = SimpleNamespace(cache=tmp_path, backgrounds={
        "max_motion": 30, "pixabay": {"sky": ["clouds"]}, "backgrounds": []})
    found = pixabay.candidates(cfg, per_theme=4, client=Client())
    assert [(c["id"], c["motion"]) for c in found] == [(2, 9.5), (3, 23.5)]


def test_generated_scenes_push_in_clips_do_not(cfg):
    conf = cfg.backgrounds["scenes"]
    rate, most = conf["push_in"], conf["push_in_max"]
    assert 0 < rate <= most <= .2                         # slow: the scene stays sharp enough
    scene = {"id": "night", "source": "generated"}
    assert backgrounds.push_in(cfg, scene, 60) == pytest.approx(rate)
    assert backgrounds.push_in(cfg, scene, 30) == pytest.approx(rate / 2)
    assert backgrounds.push_in(cfg, scene, 180) == pytest.approx(most)   # a YouTube version
    assert backgrounds.push_in(cfg, {"id": "river", "source": "pexels"}, 60) == 0


def test_the_push_in_zooms_into_the_centre_smoothly(tmp_path):
    """A horizontal ramp, 0 to 252 over 64 px, zoomed 2× by the last of 5 frames: its edges
    then show the middle half of the ramp; the first frame is untouched."""
    import numpy as np

    from quran_reels.render.video import push_in_filter

    out = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
         "color=c=black:s=64x64:d=5:r=1", "-vf",
         f"format=gray,geq=lum='4*X',{push_in_filter(1.0, 5)},format=gray",
         "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    frames = np.frombuffer(out, np.uint8).reshape(5, 64, 64).astype(float)
    first, middle, last = frames[0], frames[2], frames[4]
    assert abs(first[:, 0].mean() - 0) < 3 and abs(first[:, -1].mean() - 252) < 3
    assert abs(last[:, 0].mean() - 64) < 6 and abs(last[:, -1].mean() - 188) < 6
    assert first[:, 0].mean() < middle[:, 0].mean() < last[:, 0].mean()    # steady, no jump
    assert abs(last[:, 32].mean() - first[:, 32].mean()) < 4                 # the centre stays
