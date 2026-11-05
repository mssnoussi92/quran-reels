"""What each image shows, and the browser that measures and draws it (1080×1350 JPEG)."""

from __future__ import annotations

import hashlib
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

from jinja2 import Environment, FileSystemLoader, select_autoescape

from quran_reels.arabic import arabic_digits, words
from quran_reels.config import Config
from quran_reels.models import AyahRef

TEMPLATES = Path(__file__).parent / "templates"
WIDTH, HEIGHT = 1080, 1350
WORD_CARDS = ("word-1", "word-2", "word-3")


def template_digest() -> str:
    """Changes when the template changes: the frozen fit measurements are then stale."""
    return hashlib.sha1((TEMPLATES / "card.html.j2").read_bytes()).hexdigest()[:10]


@dataclass
class Content:
    """Everything an image shows, from the sources (cache)."""
    surah: int
    surah_name_ar: str
    surah_name_en: str
    ref: str                               # the word's ayah, "93:3"
    context: tuple[int, int]               # ayahs shown on the verse image
    texts: dict[int, str]                  # Uthmani text per ayah of the context
    translations: dict[int, str]
    highlight: dict[int, tuple[int, ...]]  # word positions per ayah
    word: str = ""                         # the highlighted words as shown («…» for a gap)
    gloss: str = ""                        # the word meaning, verbatim and whole

    @property
    def context_ref(self) -> str:
        a, b = self.context
        return f"{self.surah}:{a}" if a == b else f"{self.surah}:{a}-{b}"

    def context_vars(self, cfg: Config) -> dict[str, Any]:
        c = cfg.content
        a, b = self.context
        return {
            "word": self.word, "gloss": self.gloss, "ref": self.ref,
            "context_ref": self.context_ref,
            "surah_name_ar": f"سورة {self.surah_name_ar}", "surah_name_en": self.surah_name_en,
            "translation": " ".join(self.translations[i] for i in range(a, b + 1)),
            "ayahs": [{"number": arabic_digits(i),
                       "tokens": [{"text": t, "hl": k in self.highlight.get(i, ())}
                                  for k, t in enumerate(words(self.texts[i]))]}
                      for i in range(a, b + 1)],
            "translation_label": c["translation"]["label"],
            "gloss_source": c["glosses"]["label"],
        }


def content_for(src: Any, surah: int, context: tuple[int, int], ayah: int | None = None,
                positions: tuple[int, ...] = (), word: str = "", gloss: str = "") -> Content:
    chapter = src.quran.chapters[surah]
    refs = [AyahRef(surah, i) for i in range(context[0], context[1] + 1)]
    texts = src.quran.text(refs)
    translations = src.quran.translate(src.translation_slug, refs)
    return Content(
        surah=surah, surah_name_ar=chapter["name_arabic"], surah_name_en=chapter["name_simple"],
        ref=f"{surah}:{ayah if ayah else context[0]}", context=context,
        texts={r.ayah: texts[r] for r in refs},
        translations={r.ayah: translations[r] for r in refs},
        highlight={ayah: positions} if ayah else {}, word=word, gloss=gloss)


class CardRenderer:
    """One browser for many images. Use as a context manager."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        env = Environment(loader=FileSystemLoader(TEMPLATES),
                          autoescape=select_autoescape(["html", "j2"]))
        self.template = env.get_template("card.html.j2")
        v = cfg.video
        self.base = {"fonts_dir": cfg.fonts.resolve().as_uri(), "highlight": v["highlight_color"],
                     "handle": v["handle"]}

    def __enter__(self) -> Self:
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        self._page = self._browser.new_page(viewport={"width": WIDTH, "height": HEIGHT},
                                            device_scale_factor=1)
        self._tmp = tempfile.TemporaryDirectory()
        return self

    def __exit__(self, *exc: object) -> None:
        self._browser.close()
        self._pw.stop()
        self._tmp.cleanup()

    def _load(self, card: str, content: Content, html: Path) -> float:
        # A file, not set_content: fonts load from file:// URLs, refused from about:blank.
        html.write_text(self.template.render(card=card, **self.base,
                                             **content.context_vars(self.cfg)), encoding="utf-8")
        self._page.goto(html.resolve().as_uri())
        self._page.wait_for_function("window.__fit !== undefined")
        return float(self._page.evaluate("window.__fit"))

    def measure(self, card: str, content: Content) -> float:
        """The text scale the image needs (1 = as designed)."""
        return self._load(card, content, Path(self._tmp.name) / "measure.html")

    def render(self, card: str, content: Content, dest: Path) -> float:
        dest.parent.mkdir(parents=True, exist_ok=True)
        fit = self._load(card, content, dest.with_suffix(".html"))
        self._page.screenshot(path=str(dest), type="jpeg", quality=95)
        dest.with_suffix(".html").unlink()
        return fit
