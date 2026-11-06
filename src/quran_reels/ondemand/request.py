"""The request: the body of an issue «À la demande : …», as the catalogue's form writes it.

    ### Récitateur
    minshawi            (or auto: the rotation's choice for this passage)
    ### Passage
    93                  (the whole surah) or 93:1-5 (ayahs 1 to 5)
    ### Fond
    auto                (chosen from what the passage says) or an id of backgrounds.yaml
    ### Plateformes
    facebook, instagram, tiktok, youtube
    ### Mots                    (optional)
    auto                (the usual rules), aucun, or the numbers the preview lists, a word of
                        the quotation after «=»: 2, 5=قلى (`/mots` writes it)

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
          "platforms": "Plateformes", "words": "Mots"}
_ALIASES = {"recitateur": "reciter", "reciter": "reciter", "passage": "passage",
            "sourate": "passage", "fond": "background", "background": "background",
            "plateformes": "platforms", "platforms": "platforms", "mots": "words",
            "words": "words", "mots expliques": "words"}
_PLATFORM_ALIASES = {"fb": "facebook", "ig": "instagram", "insta": "instagram",
                     "tt": "tiktok", "yt": "youtube"}
_HEADING = re.compile(r"^\s*#{2,4}\s*(.+?)\s*$")
_PASSAGE = re.compile(r"^(\d{1,3})(?:\s*:\s*(\d{1,3})(?:\s*-\s*(\d{1,3}))?)?$")
_NO_RESPONSE = "_no response_"
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
NONE_WORDS = ("aucun", "aucune", "none", "rien", "0")

Words = tuple[tuple[int, tuple[str, ...]], ...]    # (number in the preview's list, words)


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
    words: Words | None = None      # word meanings: None the usual rules, () none

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


def parse_words(text: str) -> Words | None:
    """'auto' → None; 'aucun' → (); '2, 5=قلى, 7' → ((2, ()), (5, ('قلى',)), (7, ())):
    numbers of the preview's list, each with the words to highlight (default: the usual)."""
    t = (text or "").translate(_DIGITS).strip().strip("`").strip()
    if not t or _plain(t) == AUTO:
        return None
    if _plain(t) in NONE_WORDS:
        return ()
    out: list[tuple[int, list[str]]] = []
    for token in re.split(r"[\s,;]+", t):
        if not token:
            continue
        m = re.fullmatch(r"#?(\d+)(?:=(.*))?", token)
        if m:
            if int(m[1]) < 1:
                raise ValueError(f"mot n° {m[1]} : les numéros commencent à 1")
            out.append((int(m[1]), [m[2]] if m[2] else []))
        elif out and out[-1][1]:
            out[-1][1].append(token)        # «5=زهرة الحياة»: the next word goes with it
        else:
            raise ValueError(f"« {token} » : écrire les numéros de l'aperçu (ex. 2, 5), un mot "
                             "précis après « = » (ex. 5=قلى), « auto » ou « aucun »")
    if len({n for n, _ in out}) != len(out):
        raise ValueError("un même numéro de mot est donné deux fois")
    for n, ws in out:
        if len(ws) > 3:
            raise ValueError(f"mot n° {n} : 3 mots au plus à surligner")
    return tuple((n, tuple(ws)) for n, ws in out)


def words_text(words: Words | None) -> str:
    """The «Mots» section as parse_words reads it."""
    if words is None:
        return AUTO
    if not words:
        return "aucun"
    return ", ".join(f"{n}={' '.join(ws)}" if ws else str(n) for n, ws in words)


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
    words = None
    try:
        words = parse_words(found.get("words") or "")
    except ValueError as e:
        problems.append(str(e))
    if problems:
        raise RequestError(problems)
    reciter = (found.get("reciter") or AUTO).strip().lower()
    background = (found.get("background") or AUTO).strip()
    return Request(reciter=reciter, surah=surah, start=start, end=end,
                   background=AUTO if background.lower() == AUTO else background,
                   platforms=platforms, words=words)


def body(req: Request, footer: str = "") -> str:
    """The issue body for a request (the catalogue's script writes the same)."""
    parts = [f"### {LABELS['reciter']}\n\n{req.reciter}", f"### {LABELS['passage']}\n\n{req.passage}",
             f"### {LABELS['background']}\n\n{req.background}",
             f"### {LABELS['platforms']}\n\n{', '.join(req.platforms)}",
             f"### {LABELS['words']}\n\n{words_text(req.words)}"]
    return "\n\n".join(parts) + (f"\n\n---\n{footer}" if footer else "") + "\n"


def is_request(title: str, text: str) -> bool:
    """An issue that asks for an on-demand reel: its title, or its headings."""
    if _plain(title or "").startswith(_plain(TITLE_PREFIX)):
        return True
    found = sections(text)
    return "passage" in found and "reciter" in found


def with_words(text: str, words: Words | None) -> str:
    """The issue body with its «Mots» section set to words (added before the footer)."""
    lines = (text or "").replace("\r\n", "\n").split("\n")
    out, i, done = [], 0, False
    while i < len(lines):
        m = _HEADING.match(lines[i])
        if m and _ALIASES.get(_plain(m[1])) == "words":
            out += [lines[i], "", words_text(words), ""]
            i += 1
            while i < len(lines) and not _HEADING.match(lines[i]) and lines[i].strip() != "---":
                i += 1
            done = True
            continue
        out.append(lines[i])
        i += 1
    if not done:
        section = [f"### {LABELS['words']}", "", words_text(words), ""]
        cut = next((k for k, line in enumerate(out) if line.strip() == "---"), len(out))
        out = out[:cut] + ([""] if cut and out[cut - 1].strip() else []) + section + out[cut:]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out))
