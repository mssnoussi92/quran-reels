"""Recitation audio from EveryAyah: one MP3 per ayah.

Durations for planning without downloading the MP3s: the files are constant bitrate (128 or
32 kb/s), so seconds = bytes × 8 / bitrate, read from a HEAD request (one per ayah, cached).
The ID3 tag counts too: a few hundred bytes, under 0.05 s at 128 kb/s.
"""

from __future__ import annotations

from pathlib import Path

from quran_reels.models import AyahRef
from quran_reels.sources.http import Http, read_json, write_json

BASE = "https://everyayah.com/data"


class EveryAyah:
    def __init__(self, cache: Path, http: Http, reciter: str):
        self.dir = cache / "everyayah" / reciter
        self.http = http
        self.reciter = reciter

    @property
    def base_url(self) -> str:
        return f"{BASE}/{self.reciter}/"

    def file_url(self, stem: str) -> str:
        return f"{BASE}/{self.reciter}/{stem}.mp3"

    def url(self, ref: AyahRef) -> str:
        return self.file_url(ref.everyayah)

    def fetch_file(self, stem: str) -> Path:
        """Any file of the reciter's folder, e.g. "bismillah" (the basmala before a surah)."""
        dest = self.dir / f"{stem}.mp3"
        if not dest.is_file():
            self.http.download(self.file_url(stem), dest, min_bytes=2_000)
        return dest

    def fetch(self, ref: AyahRef) -> Path:
        return self.fetch_file(ref.everyayah)

    def basmala(self, surah: int, stem: str) -> Path:
        """The basmala recited before a passage of `surah`: the reciter's file `stem`."""
        return self.fetch_file(stem)

    def basmala_url(self, surah: int, stem: str) -> str:
        return self.file_url(stem)

    def seconds(self, surah: int, ayahs: int, kbps: float) -> dict[int, float]:
        """Seconds per ayah of a surah, from the file sizes (cached per surah)."""
        path = self.dir / f"sizes-{surah:03d}.json"
        sizes = read_json(path)["bytes"] if path.is_file() else {}
        missing = [a for a in range(1, ayahs + 1) if str(a) not in sizes]
        for a in missing:
            sizes[str(a)] = self.http.size(self.url(AyahRef(surah, a)))
        if missing:
            write_json(path, {"source": f"{BASE}/{self.reciter}/", "bytes": sizes})
        return {int(a): n * 8 / (kbps * 1000) for a, n in sizes.items()}

    def file_seconds(self, stem: str, kbps: float) -> float:
        return self.http.size(self.file_url(stem)) * 8 / (kbps * 1000)
