"""Download third-party datasets into the cache. Nothing downloaded here is committed."""

from __future__ import annotations

import sys

from quran_reels.config import Config
from quran_reels.models import AyahRef, parse_passage
from quran_reels.sources import Sources


def run(cfg: Config, passage: str | None = None, all_glosses: bool = False,
        refresh: bool = False) -> None:
    src = Sources.from_config(cfg)

    print("quran.com: chapters, Uthmani text, translation", file=sys.stderr)
    src.quran.ingest(src.translation_slug, refresh=refresh)
    print(f"tafsir.app: index of {src.glosses.src}", file=sys.stderr)
    src.glosses.book(refresh=refresh)

    if all_glosses:
        refs = src.all_refs()
        with_entry = sum(src.glosses.has_entry(src.quran.global_index(r)) for r in refs)
        print(f"tafsir.app: {src.glosses.src}, {with_entry} ayahs with an entry", file=sys.stderr)
        n = src.glosses.fetch(refs, src.quran.global_index, progress=True)
        print(f"tafsir.app: {n} entries downloaded", file=sys.stderr)

    if passage:
        surah, start, end = parse_passage(passage)
        refs = [AyahRef(surah, a) for a in range(start, end + 1)]
        src.glosses.fetch(refs, src.quran.global_index)
        for r in refs:
            src.audio.fetch(r)
        print(f"{passage}: glosses and audio ({src.audio.reciter}) cached", file=sys.stderr)

    print(f"cache: {cfg.cache}", file=sys.stderr)
