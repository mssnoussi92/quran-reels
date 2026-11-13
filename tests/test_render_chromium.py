"""The reel template drawn for real, by Chromium: the fonts load, the text is there, and it stays
between the safe margins even when it has to be scaled down. Every other test stops before the
browser: a template broken by a change, or by a new Chromium, showed only in a publishing run.

No picture is compared (a new Chromium moves pixels): what is checked is what must stay true.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import numpy as np
import pytest
from test_basmala import BASMALA

from quran_reels import config
from quran_reels.models import Ayah, AyahRef, Passage
from quran_reels.render.frames import FrameRenderer, ayah_context

TRANSLATION = "In the name of Allāh, the Entirely Merciful, the Especially Merciful."


@pytest.fixture(scope="module")
def renderer():
    cfg = config.load()
    try:
        with FrameRenderer(cfg) as r:
            yield cfg, r
    except Exception as e:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            raise                   # in CI the browser is installed: a failure is a failure
        pytest.skip(f"Chromium is not installed here ({type(e).__name__}): "
                    "python -m playwright install chromium")


def pixels(png: Path) -> np.ndarray:
    """The PNG as height × width × RGBA (decoded by ffmpeg: no image library in the project)."""
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(png), "-f", "rawvideo",
                          "-pix_fmt", "rgba", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.uint8).reshape(1920, 1080, 4)


def drawn_box(image: np.ndarray) -> tuple[int, int, int, int]:
    """left, top, right, bottom of what is clearly drawn (not the soft shadows around it)."""
    rows, cols = np.nonzero(image[:, :, 3] > 128)
    return int(cols.min()), int(rows.min()), int(cols.max()), int(rows.max())


def frame(renderer, tmp_path, translation=TRANSLATION, name="frame"):
    cfg, r = renderer
    passage = Passage(93, 1, 11, "الضحى", "Ad-Duhaa")
    basmala = Ayah(ref=AyahRef(1, 1), text=BASMALA, translation=translation)
    dest = tmp_path / f"{name}.png"
    fit = r.render("content", dest, **ayah_context(passage, basmala, basmala=True))
    return cfg, r, fit, pixels(dest)


def test_the_fonts_of_the_project_are_the_ones_drawn(renderer, tmp_path):
    _, r, _, _ = frame(renderer, tmp_path)
    loaded = r._page.evaluate(
        "() => ['112px AmiriQuran', '700 40px Amiri', 'italic 46px Lora']"
        ".map(f => [f, document.fonts.check(f)])")
    assert all(ok for _, ok in loaded), loaded
    faces = r._page.evaluate("() => [...document.fonts].filter(f => f.status === 'loaded')"
                             ".map(f => f.family.replaceAll('\"', ''))")
    assert {"AmiriQuran", "Lora"} <= set(faces), faces      # used by this frame, not a fallback


def test_a_frame_is_drawn_between_the_safe_margins(renderer, tmp_path):
    cfg, _, fit, image = frame(renderer, tmp_path)
    assert image.shape == (cfg.video["height"], cfg.video["width"], 4)
    assert fit == 1.0                                        # a short text is not scaled
    assert (image[:, :, 3] > 128).sum() > 20_000             # the basmala and its translation
    safe = cfg.video["safe_area"]
    left, top, right, bottom = drawn_box(image)
    assert left >= safe["sides"] and right <= 1080 - safe["sides"], (left, right)
    assert top >= safe["top"] and bottom <= 1920 - safe["bottom"], (top, bottom)
    assert image[0, 0, 3] == 0                               # a transparent layer over the video


def test_a_text_too_long_is_scaled_down_and_stays_inside(renderer, tmp_path):
    cfg, _, fit, image = frame(renderer, tmp_path, " ".join([TRANSLATION] * 14), "long")
    assert 0.3 < fit < 1.0
    safe = cfg.video["safe_area"]
    _, top, _, bottom = drawn_box(image)
    assert top >= safe["top"] and bottom <= 1920 - safe["bottom"], (top, bottom, fit)


# ---- generated scenes: no edge that reads as a border ------------------------------------

def scene_band(cfg, name: str, tmp_path: Path) -> np.ndarray:
    """The bottom 110 px (of 1920) of a generated scene, as the viewer gets it: drawn by
    Chromium, scaled to 1080 wide, under the template's scrim (.45 at the bottom edge).
    Luma in ffmpeg's TV range (16 = black), first and last frame of 1 s."""
    from quran_reels.sources import scenes

    try:
        mp4 = scenes.render(cfg, name, loop=0, fade=1.0, width=270, height=480,
                            dest=tmp_path / f"{name}.mp4")
    except Exception as e:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            raise
        pytest.skip(f"no Chromium or WebGL here ({type(e).__name__})")
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(mp4), "-vf",
                          "scale=1080:1920", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, 1920, 1080, 3)[[0, -1], -110:]
    scrim = np.interp(np.linspace(1 - 110 / 1920, 1, 110), [.7, 1], [.15, .45])
    seen = frames / 255 * (1 - scrim)[None, :, None, None]
    return 16 + 219 * (seen @ np.array([.2126, .7152, .0722]))


@pytest.mark.parametrize("name", ["dawn", "night", "sea"])
def test_the_bottom_of_a_scene_is_never_a_flat_band(name, tmp_path):
    """Facebook's quality checklist said «vidéo avec bordures» on the night reels (2026-11-13):
    their bottom 110 px were one flat colour (spread 0.5, still), the near hill #0e0e1f under
    the scrim, which reads as a letterbox bar. The other scenes vary there (spread 8 to 50)."""
    from quran_reels.sources import scenes

    assert name in scenes.names()
    band = scene_band(config.load(), name, tmp_path)
    first = band[0].ravel()
    spread = np.percentile(first, 90) - np.percentile(first, 10)
    assert spread >= 4, f"{name}: bottom band flat (spread {spread:.1f}): a border to Facebook"
    assert np.abs(band[-1] - band[0]).mean() > .3, f"{name}: bottom band does not move"
