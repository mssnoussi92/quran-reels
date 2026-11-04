"""Recitation audio from EveryAyah: one MP3 per ayah."""

from __future__ import annotations

from pathlib import Path

from quran_reels.models import AyahRef
from quran_reels.sources.http import Http

BASE = "https://everyayah.com/data"


class EveryAyah:
    def __init__(self, cache: Path, http: Http, reciter: str):
        self.dir = cache / "everyayah" / reciter
        self.http = http
        self.reciter = reciter

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
