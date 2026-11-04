"""Data sources, wired from config/project.yaml."""

from __future__ import annotations

from dataclasses import dataclass

from quran_reels.config import Config
from quran_reels.models import AyahRef
from quran_reels.sources.everyayah import EveryAyah
from quran_reels.sources.http import Http
from quran_reels.sources.quran_com import QuranCom
from quran_reels.sources.tafsir_app import TafsirApp


@dataclass
class Sources:
    quran: QuranCom          # Uthmani text, chapters, translation
    glosses: TafsirApp       # word meanings
    audio: EveryAyah         # recitation, one MP3 per ayah
    translation_slug: str

    @classmethod
    def from_config(cls, cfg: Config, http: Http | None = None) -> Sources:
        http = http or Http()
        content = cfg.content
        for key, expected in (("quran_text", "quran.com"), ("translation", "quran.com"),
                              ("glosses", "tafsir.app")):
            source = content[key].get("source", expected)
            if source != expected:
                raise SystemExit(f"content.{key}.source: {source!r} is not supported yet")
        g = content["glosses"]
        return cls(
            quran=QuranCom(cfg.cache, http),
            glosses=TafsirApp(cfg.cache, http, src=g["source_id"], edition=g["edition"]),
            audio=EveryAyah(cfg.cache, http, reciter=content["reciter"]["id"]),
            translation_slug=content["translation"]["edition"],
        )

    def all_refs(self) -> list[AyahRef]:
        return [AyahRef(s, a) for s, c in sorted(self.quran.chapters.items())
                for a in range(1, c["verses_count"] + 1)]
