"""Which theme video goes out which day: docs/retention/calendar.md of quran-themes-demo, as written.

« Le calendrier » has one row per day:

    | Date | Quoi | Où | Fichiers | Texte |
    | mar. 17 nov. | Du'a, short 1 : Ayyoub | les quatre | release `dua-candidate` | `publication-dua.md` : « Short 1 » |
    | mer. 18 nov. | Du'a, short 2 : Younous | les quatre | release `dua-candidate` | « Short 2 » |
    | lun. 23 nov., soir | Dhul-Qarnayn : le film | YouTube (16:9) ; Facebook (vertical) | … | `publication-qarnayn.md` : « Le film » ; `publication-qarnayn-9x16.md` |

The « Texte » column names the section (« Short N », « Le film ») and often the text
(publication-<doc>.md); « Fichiers » always names the release (`<doc>-candidate`), which says the
text when « Texte » does not. Never the row before: series alternate (2026-11-15, the 25 December
row of « لاحظت الفرق؟ » took the text of the « سنريهم آياتنا » row above it). When both name texts
they must agree. « Où » gives the platforms (« les quatre »: all). For each platform the video is the one of those texts whose file line lists it:
the 9:16 film for Facebook, the 16:9 one for YouTube. A row this cannot tie to a video is
reported and never published.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from quran_reels.insights.themes import _clean, _dates
from quran_reels.themepub.texts import Video

DOC = re.compile(r"publication-([a-z0-9-]+)\.md")
RELEASE = re.compile(r"`([a-z0-9-]+)-candidate`")
PART = re.compile(r"«\s*(Short\s+\d+|Le film[^»]*)\s*»")
ALL = ("facebook", "instagram", "tiktok", "youtube")


@dataclass
class Row:
    day: date
    label: str
    where: str
    docs: list[str]
    part: str                       # "short-1" or "film"; "" when the row names none
    platforms: list[str]
    published: bool = False         # struck: done by hand
    todo: bool = False              # « à faire »: nothing to publish yet
    videos: dict[str, Video] = field(default_factory=dict)      # platform → video
    problems: list[str] = field(default_factory=list)


def _platforms(where: str) -> list[str]:
    w = where.casefold()
    if "les quatre" in w:
        return list(ALL)
    return [p for p in ALL if p in w]


def rows(text: str, today: date) -> list[Row]:
    out: list[Row] = []
    inside = False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line.strip() == "## Le calendrier"
            continue
        if not inside or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5 or set(cells[0]) <= {"-", " ", ":"} or cells[0] == "Date":
            continue
        days = _dates(cells[0], today)
        if not days:
            continue
        named = list(dict.fromkeys(DOC.findall(cells[4])))
        released = list(dict.fromkeys(RELEASE.findall(cells[3])))
        docs = named or released
        clash = bool(named and released and set(named) != set(released))
        m = PART.search(cells[4])
        part = ""
        if m:
            p = m[1]
            part = "film" if p.startswith("Le film") else "short-" + re.sub(r"\D", "", p)
        struck = cells[0].startswith("~~") or cells[1].startswith("~~")
        todo = "à faire" in line or "histoire nouvelle" in cells[1].casefold()
        for d in days:
            row = Row(day=d, label=_clean(cells[1]), where=_clean(cells[2]),
                      docs=list(docs) if part else [], part=part,
                      platforms=_platforms(cells[2]), published=struck, todo=todo)
            if clash:
                row.problems.append("« Texte » (" + ", ".join(named) + ") et « Fichiers » ("
                                    + ", ".join(released) + ") ne nomment pas le même texte")
            out.append(row)
    return out


def resolve(row: Row, videos: dict[str, Video], wanted: list[str]) -> Row:
    """Tie each platform of the row to one video; what cannot be tied is a problem."""
    row.videos = {}
    if row.todo or row.published or row.problems:
        return row
    if not row.part or not row.docs:
        row.problems.append("la colonne « Texte » ne nomme ni texte ni section")
        return row
    candidates = [videos[f"{d}/{row.part}"] for d in row.docs if f"{d}/{row.part}" in videos]
    if not candidates:
        row.problems.append(f"« {row.part} » introuvable dans "
                            + ", ".join(f"publication-{d}.md" for d in row.docs))
        return row
    for platform in (p for p in row.platforms if p in wanted):
        video = next((v for v in candidates if platform in v.platforms), None)
        if video is None:
            row.problems.append(f"{platform} : aucune vidéo de "
                                + ", ".join(v.id for v in candidates) + " ne le prévoit")
        elif platform in ("facebook", "instagram") and not video.captions.get(platform):
            row.problems.append(f"{platform} : {video.id} n'a pas de texte pour {platform}")
        elif platform == "tiktok" and not (video.tiktok and video.captions.get("tiktok")):
            row.problems.append(f"tiktok : {video.id} n'a pas de version ou de texte TikTok")
        else:
            row.videos[platform] = video
    return row
