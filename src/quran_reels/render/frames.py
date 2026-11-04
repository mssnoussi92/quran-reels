"""HTML template → transparent PNG layers, with headless Chromium (Playwright)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Self

from jinja2 import Environment, FileSystemLoader, select_autoescape

from quran_reels.arabic import arabic_digits, words
from quran_reels.config import Config
from quran_reels.models import Ayah, Passage

TEMPLATES = Path(__file__).parent / "templates"


def base_context(cfg: Config) -> dict[str, Any]:
    c, v = cfg.content, cfg.video
    return {
        "fonts_dir": cfg.fonts.resolve().as_uri(),
        "safe": v["safe_area"],
        "highlight": v["highlight_color"],
        "handle": v["handle"],
        "credit": f"{c['reciter']['label']} · {c['translation']['label']}",
        "gloss_source": c["glosses"]["label"],
    }


def ayah_context(passage: Passage, ayah: Ayah, basmala: bool = False) -> dict[str, Any]:
    """basmala: the opening frame, surah name only, no reference or ayah number."""
    highlighted = {p for g in ayah.glosses for p in g.positions}
    return {
        "surah_name_ar": f"سورة {passage.surah_name_ar}",
        "ref": "" if basmala else str(ayah.ref),
        "tokens": [{"text": t, "hl": i in highlighted} for i, t in enumerate(words(ayah.text))],
        "ayah_number": "" if basmala else arabic_digits(ayah.ref.ayah),
        "translation": ayah.translation,
        "glosses": [{"word": g.word, "gloss": g.gloss} for g in ayah.glosses],
    }


class FrameRenderer:
    """One browser for all the frames of a reel. Use as a context manager."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.env = Environment(loader=FileSystemLoader(TEMPLATES),
                               autoescape=select_autoescape(["html", "j2"]))
        self.template = self.env.get_template("reel.html.j2")

    def __enter__(self) -> Self:
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        v = self.cfg.video
        self._page = self._browser.new_page(
            viewport={"width": v["width"], "height": v["height"]}, device_scale_factor=1)
        return self

    def __exit__(self, *exc: object) -> None:
        self._browser.close()
        self._pw.stop()

    def render(self, layer: str, dest: Path, **context: Any) -> float:
        """Write dest (PNG, transparent outside the drawn parts). Returns the text scale."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        html = dest.with_suffix(".html")
        html.write_text(self.template.render(layer=layer, **base_context(self.cfg), **context),
                        encoding="utf-8")
        self._page.goto(html.resolve().as_uri())
        self._page.wait_for_function("window.__fit !== undefined")
        fit = float(self._page.evaluate("window.__fit"))
        self._page.screenshot(path=str(dest), omit_background=(layer != "preview"))
        return fit
