"""The generated scenes drawn for real (WebGL in Chromium), as the bottom of a reel reaches the
viewer. Its own module: test_render_chromium keeps a Playwright browser open for its whole
module, and Playwright's sync API cannot be started a second time inside it.

No picture is compared (a new Chromium moves pixels): what is checked is what must stay true.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import numpy as np
import pytest

from quran_reels import config


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
        pytest.skip(f"no Chromium or WebGL here ({type(e).__name__}: {e})")
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
