"""The request: the body of an issue «À la demande : …», as the catalogue's form writes it.

    ### Récitateur
    minshawi            (or auto: the rotation's choice for this passage)
    ### Passage
    93                  (the whole surah) or 93:1-5 (ayahs 1 to 5)
    ### Fond
    auto                (chosen from what the passage says) or an id of backgrounds.yaml
    ### Plateformes
    facebook, instagram, tiktok, youtube

Only the first non-empty line under each heading counts; anything else (the catalogue's
footer) is ignored. Pure parsing: what is allowed is decided by check.py.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

TITLE_PREFIX = "À la demande"
PLATFORMS = ("facebook", "instagram", "tiktok", "youtube")
AUTO = "auto"

LABELS = {"reciter": "Récitateur", "passage": "Passage", "background": "Fond",
          "platforms": "Plateformes"}
_ALIASES = {"recitateur": "reciter", "reciter": "reciter", "passage": "passage",
            "sourate": "passage", "fond": "background", "background": "background",
            "plateformes": "platforms", "platforms": "platforms"}
_PLATFORM_ALIASES = {"fb": "facebook", "ig": "instagram", "insta": "instagram",
                     "tt": "tiktok", "yt": "youtube"}
_HEADING = re.compile(r"^\s*#{2,4}\s*(.+?)\s*$")
_PASSAGE = re.compile(r"^(\d{1,3})(?:\s*:\s*(\d{1,3})(?:\s*-\s*(\d{1,3}))?)?$")
_NO_RESPONSE = "_no response_"


class RequestError(ValueError):
    """The body cannot be read: each problem in plain words, for the owner."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class Request:
    reciter: str                    # AUTO or a name of content.reciters
    surah: int
    start: int | None               # None: the whole surah
    end: int | None
    background: str = AUTO          # AUTO or an id of config/backgrounds.yaml
    platforms: tuple[str, ...] = field(default=PLATFORMS)

    @property
    def whole(self) -> bool:
        return self.start is None

    @property
    def passage(self) -> str:
        """As written: 93, or 93:1-5."""
        return str(self.surah) if self.whole else f"{self.surah}:{self.start}-{self.end}"


def _plain(text: str) -> str:
    """Lower case without accents: «Récitateur» → «recitateur»."""
    return "".join(c for c in unicodedata.normalize("NFD", text.lower())
                   if unicodedata.category(c) != "Mn").strip(" :*")


def sections(body: str) -> dict[str, str]:
    """{field: first non-empty line under its heading}, for the known headings."""
    out: dict[str, str] = {}
    current = None
    for line in (body or "").replace("\r\n", "\n").split("\n"):
        m = _HEADING.match(line)
        if m:
            current = _ALIASES.get(_plain(m[1]))
            continue
        if line.strip() == "---":
            current = None
            continue
        value = line.strip().strip("`").strip()
        if current and value and current not in out:
            out[current] = "" if value.lower() == _NO_RESPONSE else value
    return out


def parse_passage(text: str) -> tuple[int, int | None, int | None]:
    """'93' → (93, None, None); '93:1-5' → (93, 1, 5); '2:255' → (2, 255, 255)."""
    t = re.sub(r"\s+", " ", text.strip().lower())
    t = re.sub(r"^(sourate|surah|surat)\s+", "", t)
    t = re.sub(r"\s*(entiere|entière|whole)$", "", t)
    t = t.replace("–", "-").replace("—", "-")
    m = _PASSAGE.match(t)
    if not m:
        raise ValueError(f"« {text} » : écrire la sourate (93) ou un passage (93:1-5)")
    surah = int(m[1])
    if not 1 <= surah <= 114:
        raise ValueError(f"sourate {surah} : entre 1 et 114")
    if m[2] is None:
        return surah, None, None
    start = int(m[2])
    end = int(m[3]) if m[3] else start
    if start < 1 or end < start:
        raise ValueError(f"« {text} » : de l'ayah {start} à l'ayah {end} ?")
    return surah, start, end


def parse_platforms(text: str) -> tuple[str, ...]:
    words = [w for w in re.split(r"[\s,;+/]+", re.sub(r"\([^)]*\)", " ", text.lower())) if w]
    out = []
    for w in words:
        name = _PLATFORM_ALIASES.get(w, w)
        if name not in PLATFORMS:
            raise ValueError(f"plateforme « {w} » inconnue (au choix : {', '.join(PLATFORMS)})")
        if name not in out:
            out.append(name)
    if not out:
        raise ValueError("aucune plateforme choisie")
    return tuple(p for p in PLATFORMS if p in out)


def parse(body: str) -> Request:
    found = sections(body)
    problems = []
    if not found.get("passage"):
        problems.append(f"section « {LABELS['passage']} » vide ou absente (ex. 93 ou 93:1-5)")
    surah, start, end = 0, None, None
    if found.get("passage"):
        try:
            surah, start, end = parse_passage(found["passage"])
        except ValueError as e:
            problems.append(str(e))
    platforms: tuple[str, ...] = PLATFORMS
    if found.get("platforms"):
        try:
            platforms = parse_platforms(found["platforms"])
        except ValueError as e:
            problems.append(str(e))
    if problems:
        raise RequestError(problems)
    reciter = (found.get("reciter") or AUTO).strip().lower()
    background = (found.get("background") or AUTO).strip()
    return Request(reciter=reciter, surah=surah, start=start, end=end,
                   background=AUTO if background.lower() == AUTO else background,
                   platforms=platforms)


def body(req: Request, footer: str = "") -> str:
    """The issue body for a request (the catalogue's script writes the same)."""
    parts = [f"### {LABELS['reciter']}\n\n{req.reciter}", f"### {LABELS['passage']}\n\n{req.passage}",
             f"### {LABELS['background']}\n\n{req.background}",
             f"### {LABELS['platforms']}\n\n{', '.join(req.platforms)}"]
    return "\n\n".join(parts) + (f"\n\n---\n{footer}" if footer else "") + "\n"


def is_request(title: str, text: str) -> bool:
    """An issue that asks for an on-demand reel: its title, or its headings."""
    if _plain(title or "").startswith(_plain(TITLE_PREFIX)):
        return True
    found = sections(text)
    return "passage" in found and "reciter" in found
