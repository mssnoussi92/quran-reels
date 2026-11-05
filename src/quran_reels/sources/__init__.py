"""Data sources, wired from config/project.yaml."""

from __future__ import annotations

from dataclasses import dataclass

from quran_reels.config import Config
from quran_reels.models import AyahRef
from quran_reels.sources.everyayah import EveryAyah
from quran_reels.sources.http import Http
from quran_reels.sources.quran_com import QuranCom
from quran_reels.sources.surah_audio import SurahFiles
from quran_reels.sources.tafsir_app import TafsirApp

REFERENCE_TIMINGS = 7      # Quran.com recitation whose ayah lengths guide the split (Alafasy)


def surah_texts(quran: QuranCom, surah: int) -> dict[str, str]:
    """Uthmani text of what a surah's file holds: the basmala (but in 1 and 9), each ayah."""
    n = quran.chapters[surah]["verses_count"]
    refs = [AyahRef(surah, a) for a in range(1, n + 1)]
    texts = {str(r.ayah): t for r, t in quran.text(refs).items()}
    if surah in (1, 9):
        return texts
    return {"basmala": quran.text([AyahRef(1, 1)])[AyahRef(1, 1)], **texts}


def basmala_stem(cfg: Config) -> str:
    """The reciter's basmala: a file of its folder ("bismillah") or an ayah ("001001")."""
    return cfg.content["reciter"].get("basmala") or cfg.content["basmala"].get("audio", "bismillah")


@dataclass
class Sources:
    quran: QuranCom          # Uthmani text, chapters, translation
    glosses: TafsirApp       # word meanings
    audio: EveryAyah | SurahFiles   # recitation: one MP3 per ayah, or per surah (split)
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
        r = content["reciter"]
        quran = QuranCom(cfg.cache, http)
        if r.get("surah_url"):
            audio = SurahFiles(cfg.cache, http, reciter=r["id"], url=r["surah_url"],
                               splits=cfg.root / "config" / "splits" / r["id"],
                               reference=lambda s: quran.timings(s, REFERENCE_TIMINGS),
                               texts=lambda s: surah_texts(quran, s))
        else:
            audio = EveryAyah(cfg.cache, http, reciter=r["id"])
        return cls(
            quran=quran,
            glosses=TafsirApp(cfg.cache, http, src=g["source_id"], edition=g["edition"]),
            audio=audio,
            translation_slug=content["translation"]["edition"],
        )

    def ayah_seconds(self, cfg: Config, surah: int) -> dict[int, float]:
        """Seconds per ayah for planning: Quran.com's timings of the same recording when the
        reciter has them (timings_id), otherwise the sizes of the EveryAyah files (kbps)."""
        r = cfg.content["reciter"]
        if r.get("timings_id"):
            return self.quran.timings(surah, int(r["timings_id"]))
        n = self.quran.chapters[surah]["verses_count"]
        return self.audio.seconds(surah, n, float(r.get("kbps") or 0))

    def basmala_seconds(self, cfg: Config, surah: int | None = None) -> float:
        """Length of the basmala before a passage (of `surah`, for reciters whose basmala
        comes from each surah's own file)."""
        r = cfg.content["reciter"]
        if r.get("timings_id"):
            return self.quran.timings(1, int(r["timings_id"]))[1]
        if surah is not None and isinstance(self.audio, SurahFiles) and surah not in (1, 9):
            a, b = self.audio.segments(surah)["basmala"]
            return b - a
        return self.audio.file_seconds(basmala_stem(cfg), float(r.get("kbps") or 0))

    def all_refs(self) -> list[AyahRef]:
        return [AyahRef(s, a) for s, c in sorted(self.quran.chapters.items())
                for a in range(1, c["verses_count"] + 1)]
