"""Interfaces for every data source. Implementations live next to this file.

Every source returns published content verbatim. Nothing here may generate or rephrase
Quran text, translations or explanations.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from quran_reels.models import AyahRef, GlossEntry


class QuranTextSource(Protocol):            # quran_com.QuranCom
    def text(self, refs: list[AyahRef]) -> dict[AyahRef, str]: ...


class TranslationSource(Protocol):          # quran_com.QuranCom
    def translate(self, slug: str, refs: list[AyahRef]) -> dict[AyahRef, str]: ...


class GlossSource(Protocol):                # tafsir_app.TafsirApp
    edition: str

    def entries(self, refs: list[AyahRef],
                index: Callable[[AyahRef], int]) -> dict[AyahRef, list[GlossEntry]]: ...


class AudioSource(Protocol):                # everyayah.EveryAyah
    reciter: str

    def url(self, ref: AyahRef) -> str: ...

    def fetch(self, ref: AyahRef) -> Path: ...


# Backgrounds: backgrounds.pick(cfg, passage_key) -> (path, credit), clip list or generated.
