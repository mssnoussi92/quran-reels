"""A YouTube Studio « Contenu » export → manual entries for `insights.yml` (input `manual`).

The owner exports (Analytics → Advanced mode → export) a zip of CSV files; the one with a row per
video (« Informations relatives aux tableaux.csv », « Table data.csv »…) holds what the API does
not give: thumbnail impressions and click-through rate (`impressions`, `ctr`), and, when the
columns are there, the share of a Short's viewers who chose to watch it (`viewed_pct`). Nothing
else is kept: the API already reads the views, the watch time and the rest every night.

Each row is tied to its video by its YouTube id: `youtube:<id>` in insights.json gives the `key`
the page groups the platforms under (`slot:2026-11-21/morning`, `theme:dua/short-1`), which is
what the manual entry's `video` must be. An id the state does not know is reported and left out.
Headers are read in French and in English; one that is not known is ignored.
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

from quran_reels.insights.collect import PARIS

SOURCE = "export YouTube Studio"

ID_HEADERS = {"contenu", "content", "video", "vidéo", "id de la vidéo", "video id"}
VIEWED_HEADERS = {
    "ont choisi de regarder (%)", "ont choisi de regarder",
    "vues (vs balayées) (%)", "vues (vs balayées)", "regardées (vs balayées) (%)",
    "stayed to watch (%)", "stayed to watch",
    "viewed (vs. swiped away) (%)", "viewed (vs. swiped away)",
    "viewed vs swiped away (%)", "viewed vs. swiped away (%)",
}
MONTHS = {"jan": 1, "janv": 1, "feb": 2, "fév": 2, "févr": 2, "fev": 2, "mar": 3, "mars": 3,
          "apr": 4, "avr": 4, "may": 5, "mai": 5, "jun": 6, "juin": 6, "jul": 7, "juil": 7,
          "aug": 8, "août": 8, "aout": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11,
          "dec": 12, "déc": 12}


def _norm(header: str) -> str:
    return re.sub(r"\s+", " ", header.replace("﻿", "").replace("\xa0", " ")).strip().casefold()


def classify(header: str) -> str | None:
    """A column's header → the number it holds (impressions, ctr, viewed_pct), `id`, or None."""
    h = _norm(header)
    if h in ID_HEADERS:
        return "id"
    if h in VIEWED_HEADERS:
        return "viewed_pct"
    if "taux de clics" in h or "click-through" in h or h == "ctr":
        return "ctr"
    if h.startswith("impressions"):
        return "impressions"
    return None


def parse_number(text: str, integer: bool = False) -> float | int | None:
    """« 2,71 » → 2.71 ; « 1 252 » → 1252 ; « 14,056 » (a count) → 14056 ; empty or « - » → None."""
    t = (text or "").replace("\xa0", "").replace(" ", "").replace(" ", "").replace("%", "")
    if t in ("", "-", "—", "–"):
        return None
    if "," in t and "." in t:                       # 1,234.5 (English thousands)
        t = t.replace(",", "")
    elif "," in t:
        if integer and re.fullmatch(r"\d{1,3}(,\d{3})+", t):
            t = t.replace(",", "")                  # a count: thousands
        else:
            t = t.replace(",", ".")                 # the French decimal comma
    try:
        value = float(t)
    except ValueError:
        return None
    return int(value) if integer else value


def parse_date(text: str) -> str:
    """« Nov 19, 2026 », « 19 nov. 2026 », « 2026-11-19 » → YYYY-MM-DD ; unreadable → ''."""
    t = (text or "").strip()
    try:
        return date.fromisoformat(t[:10]).isoformat()
    except ValueError:
        pass
    for m in (re.fullmatch(r"([A-Za-zéûè]+)\.? (\d{1,2}), (\d{4})", t),
              re.fullmatch(r"(\d{1,2}) ([A-Za-zéûè]+)\.? (\d{4})", t)):
        if not m:
            continue
        a, b, year = m.groups()
        month, day = (a, b) if a.isalpha() else (b, a)
        n = MONTHS.get(month.casefold())
        if n:
            try:
                return date(int(year), n, int(day)).isoformat()
            except ValueError:
                return ""
    return ""


def _decode(raw: bytes) -> str:
    return raw.decode("utf-8-sig")


def table_from_csv(text: str) -> list[dict[str, str]] | None:
    """The rows of a CSV that has a row per video (an id column, no per-day `Date` column),
    keyed by the original headers; None for any other file (Totaux, Données de graphique)."""
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return None
    heads = rows[0]
    if not any(classify(h) == "id" for h in heads):
        return None
    if any(_norm(h) in ("date", "jour", "day") for h in heads):
        return None
    return [dict(zip(heads, r, strict=False)) for r in rows[1:] if any(c.strip() for c in r)]


def read_table(zip_path: Path | None = None, csv_path: Path | None = None) -> list[dict[str, str]]:
    if csv_path is not None:
        table = table_from_csv(_decode(csv_path.read_bytes()))
        if table is None:
            raise ValueError(f"{csv_path}: not a per-video table (no « Contenu » column)")
        return table
    assert zip_path is not None
    with zipfile.ZipFile(zip_path) as z:
        names = sorted((n for n in z.namelist() if n.casefold().endswith(".csv")),
                       key=lambda n: 0 if re.search(r"tableau|table", n.casefold()) else 1)
        for name in names:
            table = table_from_csv(_decode(z.read(name)))
            if table is not None:
                return table
    raise ValueError(f"{zip_path}: no CSV with a row per video")


def youtube_keys(insights: dict[str, Any]) -> dict[str, dict[str, str]]:
    """{video id: {"key", "published"}} for the YouTube posts of insights.json."""
    out = {}
    for uid, rec in (insights.get("posts") or {}).items():
        if rec.get("platform") == "youtube" and uid.startswith("youtube:"):
            out[uid.split(":", 1)[1]] = {"key": rec.get("key") or uid,
                                         "published": str(rec.get("published") or "")[:10]}
    return out


def entries(table: list[dict[str, str]], known: dict[str, dict[str, str]], seen: str,
            skipped: list[str] | None = None) -> list[dict[str, Any]]:
    """The manual entries of the table (see add_manual); `skipped` collects the ids left out."""
    date.fromisoformat(seen)
    out = []
    for row in table:
        cols: dict[str, str] = {}
        for header in row:
            kind = classify(header)
            if kind and kind not in cols:
                cols[kind] = header
        vid = (row.get(cols.get("id", ""), "") or "").strip()
        if not vid or vid.casefold() in ("total", "totale"):
            continue
        metrics = {}
        for name in ("impressions", "ctr", "viewed_pct"):
            if name in cols:
                v = parse_number(row.get(cols[name], ""), integer=name == "impressions")
                if v is not None:
                    metrics[name] = v
        if not metrics:
            continue
        info = known.get(vid)
        if info is None:
            if skipped is not None:
                skipped.append(vid)
            continue
        published = info["published"]
        if not published:
            published = next((parse_date(v) for h, v in row.items()
                              if "publication" in _norm(h) or "published" in _norm(h)), "")
        out.append({"platform": "youtube", "video": info["key"], "published": published,
                    "seen": seen, "metrics": metrics, "source": SOURCE})
    return out


def main(zip_path: Path | None, csv_path: Path | None, state: Path, seen: str | None) -> int:
    """CLI: prints one JSON line (the list for `manual`); unknown ids go to stderr."""
    seen = seen or datetime.now(PARIS).date().isoformat()
    path = state / "insights.json"
    if not path.is_file():
        raise SystemExit(f"{path}: no insights.json (a checkout of the state branch)")
    known = youtube_keys(json.loads(path.read_text(encoding="utf-8")))
    try:
        table = read_table(zip_path, csv_path)
    except (ValueError, zipfile.BadZipFile, OSError) as e:
        raise SystemExit(f"insights import-youtube: {e}") from None
    skipped: list[str] = []
    out = entries(table, known, seen, skipped)
    for vid in skipped:
        print(f"import-youtube: {vid} is not in insights.json (not read yet, or private): left out",
              file=sys.stderr)
    print(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    return 0
