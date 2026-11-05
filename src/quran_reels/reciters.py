"""Which reciter recites a passage (content.rotation in config/project.yaml).

The owner's reciters (2026-11-05): Omar Hisham, Al-Minshawi, Saad Al-Ghamdi, Nabil Ar-Rifai,
Tawfiq As-Sayegh, Salah Budair. For each passage, among those that are ready for it (their
recording split and every needed ayah checked, config/splits/) and fit in max_seconds:

1. not one of the last `avoid_last` reciters published (variety), unless no other fits;
2. the closest to target_seconds: a long passage goes to a quick reciter (As-Sayegh,
   Ar-Rifai: about 0.77 of Alafasy's time), a short surah to a slower one (Al-Minshawi 1.16,
   Omar Hisham); ties go to the order of the list.

Deterministic: the same state gives the same choice. When no reciter of the rotation is ready,
nothing is published for that slot (an error names the command that prepares it).
"""

from __future__ import annotations

import copy
import dataclasses
from collections.abc import Iterable
from dataclasses import dataclass

from quran_reels.config import Config
from quran_reels.models import parse_passage


@dataclass(frozen=True)
class Option:
    name: str
    seconds: float | None        # None: not ready (recording not split or not checked)
    why: str = ""


def rotation(cfg: Config | None) -> list[str]:
    """The reciters chosen from, per passage; empty: content.reciter for every passage."""
    if cfg is None:
        return []
    return list((cfg.content.get("rotation") or {}).get("reciters") or [])


def with_reciter(cfg: Config, name: str) -> Config:
    """The same configuration with another reciter of the catalogue."""
    catalogue = cfg.content.get("reciters") or {}
    if name not in catalogue:
        raise SystemExit(f"unknown reciter {name!r}: config/project.yaml has {', '.join(catalogue)}")
    project = copy.deepcopy(cfg.project)
    project["content"]["reciter"] = {"name": name, **catalogue[name]}
    return dataclasses.replace(cfg, project=project)


def passage_seconds(cfg: Config, key: str) -> Option:
    """How long the passage lasts with cfg's reciter (basmala, lead and tail included)."""
    from quran_reels.passage import needs_basmala
    from quran_reels.sources import Sources
    from quran_reels.sources.surah_audio import MIN_MATCH, SurahFiles

    name = cfg.content["reciter"]["name"]
    surah, start, end = parse_passage(key)
    src = Sources.from_config(cfg)
    v = cfg.video
    overhead = float(v.get("lead_seconds", 0.4)) + float(v.get("tail_seconds", 1.2))
    if isinstance(src.audio, SurahFiles):
        if not src.audio.split_path(surah).is_file():
            return Option(name, None, f"surah {surah} not split")
        segments = src.audio.segments(surah)
        match = src.audio.matches(surah)
        labels = [str(a) for a in range(start, end + 1)]
        if needs_basmala(cfg, surah, start):
            labels.insert(0, "basmala" if surah not in (1, 9) else "1")
        missing = [k for k in labels if match.get(k, 0) < MIN_MATCH]
        if missing:
            return Option(name, None, f"{surah}:{','.join(missing)} not checked")
        return Option(name, round(sum(segments[k][1] - segments[k][0] for k in labels)
                              + overhead, 1))
    src.quran.ensure(src.translation_slug)
    seconds = src.ayah_seconds(cfg, surah)
    total = sum(seconds[a] for a in range(start, end + 1)) + overhead
    if needs_basmala(cfg, surah, start):
        total += src.basmala_seconds(cfg, surah)
    return Option(name, round(total, 1))


def options(cfg: Config, key: str, claimed: Iterable[str] = ()) -> list[Option]:
    """Each reciter of the rotation for key; a claimed one (Meta muted or blocked one of its
    reels: state `claimed`, daily.py) is never ready again."""
    claimed = set(claimed)
    return [Option(name, None, "écarté : un de ses reels a été revendiqué sur Meta")
            if name in claimed else passage_seconds(with_reciter(cfg, name), key)
            for name in rotation(cfg)]


def choose(cfg: Config, key: str, recent: list[str], claimed: Iterable[str] = ()
           ) -> tuple[str, list[Option]]:
    """The reciter for a passage, and every option considered (for the log).
    recent: reciters published so far, oldest first; claimed: never chosen."""
    rot = cfg.content.get("rotation") or {}
    p = cfg.content["passage"]
    high, target = float(p["max_seconds"]), float(p.get("target_seconds", 60))
    opts = options(cfg, key, claimed)
    fits = [o for o in opts if o.seconds is not None and o.seconds <= high]
    if not fits:
        why = "; ".join(f"{o.name}: {o.why or f'{o.seconds} s'}" for o in opts)
        raise SystemExit(f"{key}: no reciter of the rotation is ready ({why}); "
                         f"prepare it with: quran-reels split {key}")
    avoid = set(recent[-int(rot.get("avoid_last", 2)):]) if rot.get("avoid_last", 2) else set()
    pool = [o for o in fits if o.name not in avoid] or fits
    best = min(pool, key=lambda o: abs(o.seconds - target))     # min keeps the list order
    return best.name, opts


def claimed_reciters(state) -> set[str]:
    """Reciters taken out after a claim (selector.calendar.State, key `claimed`)."""
    return set(state.data.get("claimed") or {})


def recent_reciters(state, slot_order: dict[str, int]) -> list[str]:
    """Reciters of the published slots, oldest first (state: selector.calendar.State)."""
    def order(key: str) -> tuple[str, int]:
        day, slot = key.split("/")
        return day, slot_order.get(slot, 0)
    return [rec["reciter"] for key, rec in sorted(state.data["slots"].items(),
                                                  key=lambda kv: order(kv[0]))
            if rec.get("reciter")]
