"""The theme videos of quran-themes-demo, read from that repository (public, read only).

Two of its files are used, never copied into this one:

- docs/retention/publication-*.md: one section per video, « ## Short 1 · <English title> ·
  <Arabic title> » (or « ## Le film · … », « ## Le film en 9:16 · … »), then a line with the
  file, its duration and its platforms. The English title is the first line of every caption
  the owner pastes, so a post on the Page is recognised by it (`ThemeIndex.match`).
- docs/retention/calendar.md, section « Le calendrier »: one row per day (date, what, where);
  a struck row (~~…~~) is published. Shown with the reels in the catalogue's calendar.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Any

MONTHS = {"janv": 1, "jan": 1, "févr": 2, "fev": 2, "fév": 2, "mars": 3, "avr": 4, "mai": 5,
          "juin": 6, "juil": 7, "août": 8, "aout": 8, "sept": 9, "oct": 10, "nov": 11,
          "déc": 12, "dec": 12}
SECTION = re.compile(r"^##\s+(?P<head>[^·]+?)\s+·\s+(?P<en>.+?)\s+·\s+(?P<ar>.+?)\s*$")
FILE = re.compile(r"^`(?P<file>[^`]+\.mp4)`.*?·\s*(?P<dur>\d+:\d{2})\s*·\s*(?P<aspect>\d+:\d+)"
                  r"\s*·\s*(?P<where>[^·]+)")
CUT = re.compile(r"`(?P<name>[^`]+-cut\.mp4)`(?:\s*,\s*(?P<dur>\d+:\d{2}))?")
YOUTUBE_TITLE = re.compile(r"^\*\*YouTube · Titre\b")
DAY = re.compile(r"(?P<d>\d{1,2})\s+(?P<m>[a-zéûè]+)\.?", re.IGNORECASE)


_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
ARABIC_MIN = 8       # an Arabic title shorter than this is never matched by its start alone


def norm(text: str) -> str:
    """A title as compared: case, quotes, ellipses, dashes and spaces made alike, Arabic-Indic
    digits written 0-9 (owner's rule: numbers are 123; a validated title may still have ٣)."""
    t = unicodedata.normalize("NFKC", text or "").casefold().translate(_DIGITS)
    t = (t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
         .replace("…", "...").replace("–", "-").replace("—", "-"))
    t = re.sub(r"\s+", " ", t).strip()
    return t.rstrip(" .!?:;,")


@dataclass
class ThemeVideo:
    id: str                      # "<doc>/<part>", e.g. "dua/short-1", "dua-9x16/film"
    doc: str                     # publication-<doc>.md
    series: str                  # the file's own title, e.g. "A Verse and Its Story · آية وحكايتها"
    part: str                    # "Short 1", "Le film", "Le film en 9:16"
    title_en: str
    title_ar: str
    file: str = ""
    seconds: float | None = None
    aspect: str = ""
    platforms: list[str] = field(default_factory=list)
    kind: str = "theme-short"    # theme-short | theme-film | theme-episode
    cut: str = ""                # its short version (« -cut.mp4 », on the line of files)
    title_youtube: str = ""      # the « YouTube · Titre » block when the section has one (it may
                                 # differ from the heading: « قصة ذو القرنين: 3 اختبارات للقوة · … »)
    cut_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def is_cut(self, seconds: float | None) -> bool:
        """A copy `seconds` long is the short version: on YouTube, uploaded by hand, it is known by
        its length only (owner's choice, 2026-11-18: the short version there too), closer to the
        short version's than to the whole short's."""
        return bool(self.cut and seconds and self.cut_seconds and self.seconds
                    and abs(seconds - self.cut_seconds) < abs(seconds - self.seconds))


def _seconds(mmss: str) -> float:
    m, s = mmss.split(":")
    return int(m) * 60 + int(s)


def _platforms(where: str) -> list[str]:
    w = where.casefold()
    return [p for p, k in (("facebook", "facebook"), ("instagram", "instagram"),
                           ("tiktok", "tiktok"), ("youtube", "youtube")) if k in w]


def parse_texts(doc: str, text: str) -> list[ThemeVideo]:
    """publication-<doc>.md → its videos, in order."""
    lines = text.splitlines()
    series = ""
    if lines and lines[0].startswith("# "):
        series = re.sub(r"\s+:\s+.*$", "", lines[0][2:]).strip()
    films = any(re.match(r"^##\s+Le film", ln) for ln in lines) or doc.endswith("-9x16")
    out: list[ThemeVideo] = []
    for i, line in enumerate(lines):
        m = SECTION.match(line)
        if not m:
            continue
        head = m["head"].strip()
        if head.startswith("Short"):
            n = re.sub(r"\D", "", head) or str(len(out) + 1)
            part_id, kind = f"short-{n}", "theme-short" if films else "theme-episode"
        elif head.startswith("Le film"):
            part_id, kind = "film", "theme-film"
        else:
            continue
        video = ThemeVideo(id=f"{doc}/{part_id}", doc=doc, series=series, part=head,
                           title_en=m["en"].strip(), title_ar=m["ar"].strip(), kind=kind)
        for nxt in lines[i + 1:i + 6]:
            f = FILE.match(nxt.strip())
            if f:
                video.file, video.seconds = f["file"], _seconds(f["dur"])
                video.aspect, video.platforms = f["aspect"], _platforms(f["where"])
                c = CUT.search(nxt)
                if c:
                    video.cut = c["name"]
                    video.cut_seconds = _seconds(c["dur"]) if c["dur"] else None
                break
        for j, nxt in enumerate(lines[i + 1:], start=i + 1):
            if nxt.startswith("## "):
                break
            if YOUTUBE_TITLE.match(nxt.strip()):
                block = [ln.strip() for ln in lines[j + 1:j + 6]]
                if "```text" in block:
                    k = block.index("```text")
                    video.title_youtube = block[k + 1] if k + 1 < len(block) else ""
                break
        out.append(video)
    return out


def _starts(line: str, title: str) -> bool:
    return bool(title) and (line == title or line.startswith(title))


class ThemeIndex:
    """Every theme video, found by the first line of a caption."""

    def __init__(self, videos: list[ThemeVideo]):
        self.videos = videos
        self.by_id = {v.id: v for v in videos}

    def match(self, caption: str | None, platform: str) -> ThemeVideo | None:
        first = next((ln for ln in (caption or "").splitlines() if ln.strip()), "")
        line = norm(first)
        if len(line) < 8:
            return None
        # A theme video's YouTube title is « <English> · <Arabic> » (published until 2026-11-21) or
        # « <Arabic> · <English> » (from then on): either title starts the line.
        # Its own YouTube title, when the file writes one apart from the heading (2026-11-21).
        found = [v for v in self.videos if _starts(line, norm(v.title_en)) or (
            len(norm(v.title_ar)) >= ARABIC_MIN and _starts(line, norm(v.title_ar))) or (
            len(norm(v.title_youtube)) >= ARABIC_MIN and line == norm(v.title_youtube))]
        if not found:
            return None
        # The 16:9 film (YouTube) and its 9:16 version (Facebook) share a title.
        on = [v for v in found if platform in v.platforms]
        return (on or found)[0]

    def to_dict(self) -> dict[str, Any]:
        return {v.id: v.to_dict() for v in self.videos}


# ---------------------------------------------------------------------------- calendar


@dataclass
class ThemeDay:
    day: str                    # ISO date
    label: str                  # « Du'a, short 1 : Ayyoub »
    where: str                  # « les quatre », « YouTube (16:9) ; Facebook (vertical) »
    evening: bool = False       # « soir » in the date cell (a film)
    published: bool = False     # struck row
    todo: bool = False          # « à faire » / « une histoire nouvelle »
    span: str = ""              # the whole cell when it covers several days

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _year(month: int, day_: int, today: date) -> date:
    """The date nearest to today with this day and month."""
    options = []
    for y in (today.year - 1, today.year, today.year + 1):
        try:
            options.append(date(y, month, day_))
        except ValueError:
            pass
    return min(options, key=lambda d: abs((d - today).days))


def _dates(cell: str, today: date) -> list[date]:
    found = []
    for m in DAY.finditer(cell):
        month = MONTHS.get(m["m"].casefold().rstrip("."))
        if month:
            found.append(_year(month, int(m["d"]), today))
    if len(found) == 2 and "→" in cell and found[1] > found[0]:
        span = (found[1] - found[0]).days
        return [found[0] + timedelta(days=i) for i in range(span + 1)]
    return found[:1]


def _clean(cell: str) -> str:
    return re.sub(r"\s+", " ", cell.replace("~~", "").replace("**", "").replace("`", "")).strip()


def parse_calendar(text: str, today: date) -> list[ThemeDay]:
    """The « Le calendrier » table of calendar.md → one entry per day."""
    out: list[ThemeDay] = []
    inside = False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line.strip() == "## Le calendrier"
            continue
        if not inside or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or set(cells[0]) <= {"-", " ", ":"} or cells[0] == "Date":
            continue
        days = _dates(cells[0], today)
        if not days:
            continue
        what = _clean(cells[1])
        struck = cells[0].startswith("~~") or cells[1].startswith("~~")
        todo = "à faire" in line or "une histoire nouvelle" in what.casefold()
        for d in days:
            out.append(ThemeDay(day=d.isoformat(), label=what, where=_clean(cells[2]),
                                evening="soir" in cells[0], published=struck, todo=todo,
                                span=_clean(cells[0]) if len(days) > 1 else ""))
    return out


# ---------------------------------------------------------------------------- reading


def raw_url(repo: str, ref: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{ref}/{path}"


def load(cfg_themes: dict[str, Any], get_text: Callable[[str], str],
         list_dir: Callable[[str], list[str]], today: date) -> tuple[ThemeIndex, list[ThemeDay]]:
    """Read the publication texts and the calendar of quran-themes-demo.

    get_text(url) returns a file; list_dir(path) the file names of a folder of the repository.
    """
    repo, ref = cfg_themes["repo"], cfg_themes.get("ref", "main")
    texts = cfg_themes.get("texts", "docs/retention").rstrip("/")
    videos: list[ThemeVideo] = []
    for name in sorted(list_dir(texts)):
        m = re.fullmatch(r"publication-(.+)\.md", name)
        if m:
            videos += parse_texts(m[1], get_text(raw_url(repo, ref, f"{texts}/{name}")))
    days = parse_calendar(get_text(raw_url(repo, ref, cfg_themes["calendar"])), today)
    return ThemeIndex(videos), days


def load_github(cfg_themes: dict[str, Any], today: date,
                token: str | None = None) -> tuple[ThemeIndex, list[ThemeDay]]:
    """load() over HTTPS: raw files and the contents API. The repository is public; a token
    (GITHUB_TOKEN in a workflow) only raises the API's rate limit, and only the API gets it."""
    from quran_reels.sources.http import Http

    http = Http(timeout=30)
    repo, ref = cfg_themes["repo"], cfg_themes.get("ref", "main")

    def get_text(url: str) -> str:
        r = http.get(url)
        r.encoding = "utf-8"
        return r.text

    def list_dir(path: str) -> list[str]:
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        r = http.session.get(url, params={"ref": ref}, headers=headers, timeout=http.timeout)
        r.raise_for_status()
        return [i["name"] for i in r.json() if i.get("type") == "file"]

    return load(cfg_themes, get_text, list_dir, today)
