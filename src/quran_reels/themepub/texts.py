"""The publication texts of quran-themes-demo (docs/retention/publication-<doc>.md), as validated.

One section per video:

    ## Short 1 · <English title> · <Arabic title>          (or « ## Le film · … », « ## Le film en 9:16 · … »)

    `dua-short-1-asked.mp4` (TikTok : `dua-short-1-asked-tiktok.mp4`, …) · 1:49 · 9:16 · Facebook, Instagram, TikTok, YouTube Shorts · couverture : `dua-short-1-asked-cover.jpg`

    **Facebook (8 hashtags)**   then a ```text block: what Facebook gets, word for word
    **Instagram (5 hashtags)**  **TikTok : la vidéo `…-tiktok.mp4` (5 hashtags)**
    **Titre YouTube (35/100)**  **Description YouTube (Shorts)**

Since 2026-11-15 a platform's text comes in cards, each with its own Copy button on the owner's
page, pasted into one caption (« **Facebook · Titre** », « … · Description », « … · Crédits »,
« … · Hashtags (3) »; « **YouTube · Titre (78/100)** » is YouTube's title field, its other cards its
description): the caption here is those cards joined by a blank line, in their order. On Facebook,
Instagram and TikTok the short caption has three (title, hook with the AI-voice line, hashtags).

Since 2026-11-16 the line of files may end with a short version for Facebook and Instagram, cut
by quran-themes-demo and validated by the owner (« · version courte pour Facebook et Instagram :
`qarnayn-short-1-west-cut.mp4`, 1:13 »): `cut` and `cut_seconds`. The first `.mp4` stays the whole
short, and the duration, format and platforms read are its own. YouTube gets the short version too
since 2026-11-18 (owner's choice; uploaded by hand from the page publier.html).

Every text is taken as it is: nothing is cut, added or rewritten here (the owner validated them).
A text the file's opening paragraph says is not validated yet (« pas encore validé(e)s », as
tools/trial/publish.py writes it: the short captions proposed on 2026-11-15) is `pending`, and
never published.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from quran_reels.insights.themes import SECTION

CUT = re.compile(r"`(?P<name>[^`]+-cut\.mp4)`(?:\s*,\s*(?P<dur>\d+:\d{2}))?")
FILE_LINE = re.compile(r"·\s*(?P<dur>\d+:\d{2})\s*·\s*(?P<aspect>\d+:\d+)\s*·\s*(?P<where>[^·]+)")
CARD = re.compile(r"^(?P<platform>facebook|instagram|tiktok|youtube)\s+·\s+(?P<kind>titre|description|"
                  r"crédits|credits|hashtags)\b", re.IGNORECASE)
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
    cut: str = ""                   # the short version for Facebook, Instagram, YouTube (« -cut.mp4 »)
    cut_seconds: float | None = None
    cover: str = ""
    thumbnail: str = ""
    seconds: float | None = None
    aspect: str = ""
    platforms: list[str] = field(default_factory=list)
    captions: dict[str, str] = field(default_factory=dict)
    pending: bool = False           # the file says its texts are not validated yet
    cards: dict[str, list[tuple[str, str]]] = field(default_factory=dict)   # platform → (kind, text)

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
    card: tuple[str, str] | None = None         # (platform, kind) of a card label
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
                elif n.endswith("-cut.mp4"):
                    current.cut = n
                elif n.endswith(".mp4") and not current.video:
                    current.video = n
                elif n.endswith("-cover.jpg"):
                    current.cover = n
                elif n.endswith(".jpg"):
                    current.thumbnail = n
            c = CUT.search(line)
            if c and c["dur"]:
                mm, ss = c["dur"].split(":")
                current.cut_seconds = int(mm) * 60 + int(ss)
            f = FILE_LINE.search(line)
            if f:
                mm, ss = f["dur"].split(":")
                current.seconds = int(mm) * 60 + int(ss)
                current.aspect = f["aspect"]
                current.platforms = _platforms(f["where"])
        elif current and line.startswith("**") and line.rstrip().endswith("**"):
            low = line.strip("* ").casefold()
            c = CARD.match(low)
            card = (c["platform"], c["kind"].replace("credits", "crédits")) if c else None
            label = None if c else next((key for word, key in BLOCKS if low.startswith(word)), None)
        elif current and (label or card) and line.strip() == "```text":
            j = i + 1
            while j < len(lines) and lines[j].strip() != "```":
                j += 1
            body = "\n".join(lines[i + 1:j]).strip("\n")
            if card:
                current.cards.setdefault(card[0], []).append((card[1], body))
            else:
                current.captions[label] = body + "\n"
            label = card = None
            i = j
        i += 1
    for video in out.values():
        for platform, parts in video.cards.items():
            if platform == "youtube":
                title = [t for kind, t in parts if kind == "titre"]
                if title:
                    video.captions["youtube_title"] = title[0] + "\n"
                rest = [t for kind, t in parts if kind != "titre" and t]
                if rest:
                    video.captions["youtube_description"] = "\n\n".join(rest) + "\n"
            else:
                video.captions[platform] = "\n\n".join(t for _, t in parts if t) + "\n"
    return out
