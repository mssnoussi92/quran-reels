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




def test_the_question_has_a_screen_of_its_own_between_the_safe_margins(renderer, tmp_path):
    """video.hook: the layer « hook » draws the word large, the question and its English line,
    centred between the safe margins, nothing of an ayah; a long phrase is scaled down to fit."""
    cfg, r = renderer
    safe = cfg.video["safe_area"]
    hook = {"word": "أَثْقَالَهَا", "question": "تعرف معناها؟",
            "en": "Do you know what this word means?"}
    for name, word in (("short", hook["word"]), ("long", "لِأَحَدٍ عِندَهُۥ مِن نِّعْمَةٍ تُجْزَىٰٓ")):
        dest = tmp_path / f"{name}.png"
        fit = r.render("hook", dest, hook={**hook, "word": word})
        image = pixels(dest)
        left, top, right, bottom = drawn_box(image)
        assert left >= safe["sides"] and right <= 1080 - safe["sides"], (name, left, right)
        assert top >= safe["top"] and bottom <= 1920 - safe["bottom"], (name, top, bottom, fit)
        assert abs((left + right) / 2 - 540) < 40                     # centred
        assert (image[:, :, 3] > 128).sum() > 15_000 and image[0, 0, 3] == 0
    assert r.render("hook", tmp_path / "x.png", hook=hook) == 1.0     # the short one, full size


def test_the_sign_of_salawat_is_drawn_by_a_font_of_the_project(renderer, tmp_path):
    """Lora has no ﷺ: it showed as a box in 18:1 of the long Al-Kahf (2026-11-27). Amiri draws it."""
    _, r, _, _ = frame(renderer, tmp_path, name="salawat",
                       translation="upon His Servant [Muḥammad (ﷺ)] the Book")
    faces = r._page.evaluate("() => [...document.fonts].filter(f => f.status === 'loaded')"
                             ".map(f => f.family.replaceAll('\"', ''))")
    assert "Salawat" in faces, faces          # loaded only for a text that has the sign
