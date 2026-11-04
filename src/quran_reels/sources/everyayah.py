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

    def url(self, ref: AyahRef) -> str:
        return f"{BASE}/{self.reciter}/{ref.everyayah}.mp3"

    def fetch(self, ref: AyahRef) -> Path:
        dest = self.dir / f"{ref.everyayah}.mp3"
        if not dest.is_file():
            self.http.download(self.url(ref), dest, min_bytes=2_000)
        return dest
