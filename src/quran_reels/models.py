"""Domain objects shared by every stage of the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


@dataclass(frozen=True, order=True)
class AyahRef:
    surah: int
    ayah: int

    @classmethod
    def parse(cls, key: str) -> AyahRef:
        surah, ayah = key.split(":")
        return cls(int(surah), int(ayah))

    def __str__(self) -> str:
        return f"{self.surah}:{self.ayah}"

    @property
    def everyayah(self) -> str:
        """File stem used by EveryAyah, e.g. 093002."""
        return f"{self.surah:03d}{self.ayah:03d}"


@dataclass(frozen=True)
class WordGloss:
    """Explanation of a difficult word, quoted verbatim from a published source."""

    ref: AyahRef
    word: str          # the word as written in the Uthmani text
    gloss: str         # verbatim explanation (Arabic)
    edition: str       # e.g. ar-ghareeb-ibn-qutaybah


@dataclass
class Ayah:
    ref: AyahRef
    text: str                        # canonical Uthmani text
    translation: str                 # verbatim translation
    glosses: list[WordGloss] = field(default_factory=list)
    audio: Path | None = None
    seconds: float | None = None


@dataclass
class Passage:
    surah: int
    start: int
    end: int
    surah_name_ar: str
    surah_name_en: str
    ayahs: list[Ayah] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.surah}:{self.start}-{self.end}"

    @property
    def seconds(self) -> float:
        return sum(a.seconds or 0 for a in self.ayahs)


@dataclass
class Reel:
    passage: Passage
    video: Path
    caption: str
    cover: Path | None = None


class PublishStatus(str, Enum):
    PUBLISHED = "published"   # live on the platform
    DRAFT = "draft"           # sent to the owner's inbox (TikTok before audit)
    MANUAL = "manual"         # file ready, owner uploads by hand (YouTube before audit)
    FAILED = "failed"


@dataclass
class PublishResult:
    platform: str
    status: PublishStatus
    remote_id: str | None = None
    url: str | None = None
    error: str | None = None
