"""The publication texts of quran-themes-demo (docs/retention/publication-<doc>.md), as validated.

One section per video:

    ## Short 1 · <English title> · <Arabic title>          (or « ## Le film · … », « ## Le film en 9:16 · … »)

    `dua-short-1-asked.mp4` (TikTok : `dua-short-1-asked-tiktok.mp4`, …) · 1:49 · 9:16 · Facebook, Instagram, TikTok, YouTube Shorts · couverture : `dua-short-1-asked-cover.jpg`

    **Facebook (8 hashtags)**   then a ```text block: what Facebook gets, word for word
    **Instagram (5 hashtags)**  **TikTok : la vidéo `…-tiktok.mp4` (5 hashtags)**
    **Titre YouTube (35/100)**  **Description YouTube (Shorts)**

Every text is taken as it is: nothing is cut, added or rewritten here (the owner validated them).
A text the file's opening paragraph says is not validated yet (« pas encore validé(e)s », as
tools/trial/publish.py writes it: the short captions proposed on 2026-11-15) is `pending`, and
never published.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from quran_reels.insights.themes import SECTION

FILE_LINE = re.compile(r"·\s*(?P<dur>\d+:\d{2})\s*·\s*(?P<aspect>\d+:\d+)\s*·\s*(?P<where>[^·]+)")
PENDING = re.compile(r"pas encore validée?s?\b", re.IGNORECASE)
BLOCKS = (("titre youtube", "youtube_title"), ("description youtube", "youtube_description"),
          ("tiktok", "tiktok"), ("instagram", "instagram"), ("facebook", "facebook"))


@dataclass
class Video:
    id: str                         # "<doc>/<part>": "dua/short-1", "dua-9x16/film"
    doc: str
    part: str                       # "short-1" … or "film"
    title_en: str
    title_ar: str
    video: str = ""                 # file names in the release page-<doc>
    tiktok: str = ""
    cover: str = ""
    thumbnail: str = ""
    seconds: float | None = None
    aspect: str = ""
    platforms: list[str] = field(default_factory=list)
    captions: dict[str, str] = field(default_factory=dict)
    pending: bool = False           # the file says its texts are not validated yet

    @property
    def title(self) -> str:
        return f"{self.title_en} · {self.title_ar}"


def _platforms(where: str) -> list[str]:
    w = where.casefold()
    return [p for p in ("facebook", "instagram", "tiktok", "youtube") if p in w]


def parse(doc: str, text: str) -> dict[str, Video]:
    """publication-<doc>.md → {video id: Video}."""
    lines = text.splitlines()
    head = "\n".join(lines[:next((k for k, x in enumerate(lines) if x.startswith("## ")), len(lines))])
    pending = bool(PENDING.search(head))
    out: dict[str, Video] = {}
    current: Video | None = None
    label: str | None = None
    i = 0
    while i < len(lines):
        line = lines[i]
        m = SECTION.match(line)
        if m:
            head = m["head"].strip()
            part = ("film" if head.startswith("Le film") else
                    "short-" + (re.sub(r"\D", "", head) or "0") if head.startswith("Short")
                    else "")
            current = Video(f"{doc}/{part}", doc, part, m["en"].strip(), m["ar"].strip(),
                            pending=pending) if part else None
            if current:
                out[current.id] = current
            label = None
        elif current and line.startswith("`") and not current.video:
            names = re.findall(r"`([^`]+\.(?:mp4|jpg))`", line)
            for n in names:
                if n.endswith("-tiktok.mp4"):
                    current.tiktok = n
                elif n.endswith(".mp4") and not current.video:
                    current.video = n
                elif n.endswith("-cover.jpg"):
                    current.cover = n
                elif n.endswith(".jpg"):
                    current.thumbnail = n
            f = FILE_LINE.search(line)
            if f:
                mm, ss = f["dur"].split(":")
                current.seconds = int(mm) * 60 + int(ss)
                current.aspect = f["aspect"]
                current.platforms = _platforms(f["where"])
        elif current and line.startswith("**") and line.rstrip().endswith("**"):
            low = line.strip("* ").casefold()
            label = next((key for word, key in BLOCKS if low.startswith(word)), None)
        elif current and label and line.strip() == "```text":
            j = i + 1
            while j < len(lines) and lines[j].strip() != "```":
                j += 1
            current.captions[label] = "\n".join(lines[i + 1:j]).strip("\n") + "\n"
            label = None
            i = j
        i += 1
    return out
