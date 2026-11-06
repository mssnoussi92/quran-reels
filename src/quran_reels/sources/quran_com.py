"""Uthmani text, chapter names and translations from the Quran.com API (v4).

The whole Quran fits in one request per resource, so ingestion stores the raw responses in
.cache/quran.com/ and every later read is local.
"""

from __future__ import annotations

import html
import re
from functools import cached_property
from pathlib import Path

from quran_reels.models import AyahRef
from quran_reels.sources.http import Http, read_json, write_json

API = "https://api.quran.com/api/v4"

_FOOTNOTE = re.compile(r"<sup\b[^>]*>.*?</sup>", re.DOTALL | re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")


def clean_translation(text: str) -> str:
    """Drop footnote markers (<sup foot_note=…>1</sup>) and markup. Words are untouched."""
    text = _FOOTNOTE.sub("", text)
    text = _TAG.sub("", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


class QuranCom:
    def __init__(self, cache: Path, http: Http):
        self.dir = cache / "quran.com"
        self.http = http

    # ---- ingestion -------------------------------------------------------------------

    def ingest(self, translation_slug: str, refresh: bool = False) -> None:
        self._fetch("chapters.json", f"{API}/chapters", refresh)
        self._fetch("uthmani.json", f"{API}/quran/verses/uthmani", refresh)
        tid = self._translation_id(translation_slug, refresh)
        self._fetch(f"translation-{translation_slug}.json",
                    f"{API}/quran/translations/{tid}", refresh, fields="verse_key")

    def _fetch(self, name: str, url: str, refresh: bool, **params: str) -> Path:
        dest = self.dir / name
        if refresh or not dest.is_file():
            write_json(dest, self.http.json(url, **params))
        return dest

    def _translation_id(self, slug: str, refresh: bool) -> int:
        index = read_json(self._fetch("translations-index.json",
                                      f"{API}/resources/translations", refresh))
        for t in index["translations"]:
            if t.get("slug") == slug:
                return int(t["id"])
        raise SystemExit(f"translation {slug!r} not found on Quran.com")

    def translation_id(self, slug: str) -> int:
        """Quran.com's id of a translation (the catalogue's form reads it from the API)."""
        return self._translation_id(slug, False)

    def ensure(self, translation_slug: str) -> None:
        needed = ["chapters.json", "uthmani.json", f"translation-{translation_slug}.json"]
        if not all((self.dir / n).is_file() for n in needed):
            self.ingest(translation_slug)

    # ---- reads -----------------------------------------------------------------------

    @cached_property
    def chapters(self) -> dict[int, dict]:
        data = read_json(self.dir / "chapters.json")
        return {c["id"]: c for c in data["chapters"]}

    @cached_property
    def _uthmani(self) -> dict[str, str]:
        data = read_json(self.dir / "uthmani.json")
        return {v["verse_key"]: v["text_uthmani"].strip() for v in data["verses"]}

    def text(self, refs: list[AyahRef]) -> dict[AyahRef, str]:
        return {r: self._uthmani[str(r)] for r in refs}

    def translate(self, slug: str, refs: list[AyahRef]) -> dict[AyahRef, str]:
        data = read_json(self.dir / f"translation-{slug}.json")
        by_key = {t["verse_key"]: t["text"] for t in data["translations"]}
        return {r: clean_translation(by_key[str(r)]) for r in refs}

    def global_index(self, ref: AyahRef) -> int:
        """1-based position of the ayah in the mushaf (1:1 = 1, 114:6 = 6236)."""
        before = sum(self.chapters[s]["verses_count"] for s in range(1, ref.surah))
        return before + ref.ayah

    # ---- passage planning ------------------------------------------------------------
    # Small per-surah files, fetched on demand: only what the planner needs is kept.

    def timings(self, surah: int, recitation_id: int) -> dict[int, float]:
        """Seconds per ayah in the reciter's chapter recording (same recording as EveryAyah's
        files, within about 2 %): enough to plan passages without downloading the MP3s."""
        path = self.dir / f"timings-{recitation_id}" / f"{surah:03d}.json"
        if not path.is_file():
            url = f"{API}/chapter_recitations/{recitation_id}/{surah}"
            stamps = self.http.json(url, segments="true")["audio_file"]["timestamps"]
            write_json(path, {"source": f"{url}?segments=true", "seconds": {
                t["verse_key"].split(":")[1]: (t["timestamp_to"] - t["timestamp_from"]) / 1000
                for t in stamps}})
        return {int(a): s for a, s in read_json(path)["seconds"].items()}

    def tafsir_groups(self, surah: int, slug: str) -> list[tuple[int, int]]:
        """Ayah groups a tafsir explains together, e.g. Ibn Kathir 2:8-9: never split.

        Quran.com leaves the text of the second and following ayahs of a group empty.
        """
        path = self.dir / f"tafsir-groups-{slug}" / f"{surah:03d}.json"
        if not path.is_file():
            tid = self._tafsir_id(slug)
            url = f"{API}/tafsirs/{tid}/by_chapter/{surah}"
            starts, page = [], 1
            while page:
                data = self.http.json(url, per_page=50, page=page)
                starts += [int(t["verse_key"].split(":")[1]) for t in data["tafsirs"]
                           if (t.get("text") or "").strip()]
                page = data["pagination"].get("next_page")
            write_json(path, {"source": url, "group_starts": sorted(set(starts))})
        starts = read_json(path)["group_starts"]
        n = self.chapters[surah]["verses_count"]
        starts = sorted({1, *starts})
        return [(a, b - 1) for a, b in zip(starts, [*starts[1:], n + 1], strict=True)]

    def _tafsir_id(self, slug: str) -> int:
        index = read_json(self._fetch("tafsirs-index.json", f"{API}/resources/tafsirs", False))
        for t in index["tafsirs"]:
            if t.get("slug") == slug:
                return int(t["id"])
        raise SystemExit(f"tafsir {slug!r} not found on Quran.com")
