"""Domain objects shared by every stage of the pipeline."""

from __future__ import annotations

import re
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


_PASSAGE = re.compile(r"^\s*(\d{1,3})\s*:\s*(\d{1,3})(?:\s*-\s*(\d{1,3}))?\s*$")


def parse_passage(key: str) -> tuple[int, int, int]:
    """'93:1-3' -> (93, 1, 3); '93:2' -> (93, 2, 2)."""
    m = _PASSAGE.match(key)
    if not m:
        raise ValueError(f"invalid passage {key!r}, expected e.g. 93:1-3")
    surah, start = int(m[1]), int(m[2])
    end = int(m[3]) if m[3] else start
    if not 1 <= surah <= 114 or start < 1 or end < start:
        raise ValueError(f"invalid passage {key!r}")
    return surah, start, end


@dataclass(frozen=True)
class GlossEntry:
    """One entry of a gloss book for an ayah, as published (editor footnotes removed)."""

    ref: AyahRef
    lemma: str         # the Quran words the author quotes, in the book's own spelling
    text: str          # the author's explanation, verbatim
    edition: str


@dataclass(frozen=True)
class WordGloss:
    """Explanation of a difficult word, quoted verbatim from a published source."""

    ref: AyahRef
    word: str          # the word as written in the Uthmani text
    gloss: str         # verbatim explanation (Arabic), possibly cut at a sentence end
    edition: str       # e.g. ar-ghareeb-ibn-qutaybah
    lemma: str = ""    # what the source quotes, verbatim, for traceability
    positions: tuple[int, ...] = ()   # indexes of the highlighted words in the ayah


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
    basmala: Ayah | None = None      # recited before the passage (text and translation of 1:1)
    label_ar: str = ""               # series shown on the first frame, «آيات الدعاء · ٣ من ٣٨»
    label_en: str = ""               # same, first line of the caption
    series_tags: tuple[str, ...] = ()  # the series' hashtags (config/series/*.yaml)

    @property
    def segments(self) -> list[Ayah]:
        """What is recited, in order: the basmala if any, then the ayahs."""
        return ([self.basmala] if self.basmala else []) + self.ayahs

    @property
    def key(self) -> str:
        return f"{self.surah}:{self.start}-{self.end}"

    @property
    def reference(self) -> str:
        """The reference shown to people: 2:255 for one ayah, 93:1-11 for several."""
        return f"{self.surah}:{self.start}" + (f"-{self.end}" if self.end != self.start else "")

    @property
    def slug(self) -> str:
        """File-system friendly key, e.g. 093_001-003."""
        return f"{self.surah:03d}_{self.start:03d}-{self.end:03d}"

    @property
    def refs(self) -> list[AyahRef]:
        return [AyahRef(self.surah, a) for a in range(self.start, self.end + 1)]

    @property
    def seconds(self) -> float:
        return sum(a.seconds or 0 for a in self.segments)


@dataclass
class Reel:
    passage: Passage
    video: Path
    caption: str                     # without hashtags
    cover: Path | None = None
    cover_ms: int | None = None      # frame used as cover, in ms from the start
    hashtags: list[str] = field(default_factory=list)   # most important first
    facebook: str = ""               # Facebook's short caption, hashtags included (render)

    def text(self, max_hashtags: int | None = None) -> str:
        """The caption with the first max_hashtags hashtags (all if None) on a last line."""
        tags = self.hashtags if max_hashtags is None else self.hashtags[:max_hashtags]
        return self.caption.rstrip("\n") + ("\n\n" + " ".join(tags) if tags else "") + "\n"

    def text_for(self, platform: str, max_hashtags: int | None = None) -> str:
        """What a platform gets: Facebook its short caption (render.facebook_caption), when
        the reel has one; the others, and Facebook without it, text(max_hashtags)."""
        if platform == "facebook" and self.facebook:
            return self.facebook
        return self.text(max_hashtags)


class PublishStatus(str, Enum):
    PUBLISHED = "published"   # live on the platform
    DRAFT = "draft"           # unpublished draft (Facebook dry run, TikTok inbox before audit)
    READY = "ready"           # uploaded and processed, not published (Instagram dry run)
    MANUAL = "manual"         # file ready, owner uploads by hand (YouTube before audit)
    CANCELLED = "cancelled"   # offered, never posted: the owner dropped it (on-demand test)
    BLOCKED = "blocked"       # not published: the rights check found a match or could not end
    REMOVED = "removed"       # published, then taken down: Meta muted or blocked it (claim)
    FAILED = "failed"


@dataclass
class PublishResult:
    platform: str
    status: PublishStatus
    remote_id: str | None = None
    url: str | None = None
    error: str | None = None
    rights: dict | None = None         # the platform's copyright check (RightsCheck.as_dict)
    rights_after: dict | None = None   # the same, read on the published reel
