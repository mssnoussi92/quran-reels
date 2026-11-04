"""Interfaces for every data source. Implementations live next to this file.

Every source returns published content verbatim. Nothing here may generate or rephrase
Quran text, translations or explanations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from quran_reels.models import AyahRef, WordGloss


class QuranTextSource(Protocol):
    def text(self, refs: list[AyahRef]) -> dict[AyahRef, str]: ...


class TranslationSource(Protocol):
    edition: str

    def translate(self, refs: list[AyahRef]) -> dict[AyahRef, str]: ...


class GlossSource(Protocol):
    edition: str

    def glosses(self, refs: list[AyahRef]) -> list[WordGloss]: ...


class AudioSource(Protocol):
    reciter: str

    def fetch(self, ref: AyahRef, dest: Path) -> Path: ...


class BackgroundSource(Protocol):
    def pick(self, mood: list[str] | None, min_seconds: float, dest: Path) -> Path: ...
