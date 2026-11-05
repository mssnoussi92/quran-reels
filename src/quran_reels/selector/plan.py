"""Split a surah into passages of about a minute, never in the middle of a sentence.

A surah that fits in one video (max_seconds) is one passage. A longer one is cut only after
an ayah that
  - ends a sentence in the translation (".", "?" or "!"; a comma or nothing means the
    sentence goes on: «By the morning brightness / And [by] the night…,»), and
  - ends a group of ayahs that Ibn Kathir explains together (2:8-9 stay together).
Among those cuts, the split whose passages are closest to target_seconds is chosen
(dynamic programming). If a block between two cuts is longer than max_seconds, sentence ends
inside it are allowed too, and the passages concerned are marked `relaxed`.

Durations come from the reciter's chapter timings on Quran.com, plus the lead and tail
silences of the video and the basmala that opens it (see passage.needs_basmala).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import accumulate

from quran_reels.config import Config
from quran_reels.models import AyahRef
from quran_reels.passage import needs_basmala
from quran_reels.sources import Sources

_SENTENCE_END = re.compile("[.?!][\"'”’»)\\]]*$")


@dataclass(frozen=True)
class Planned:
    surah: int
    start: int
    end: int
    seconds: float              # expected video length
    whole_surah: bool = False
    relaxed: bool = False       # cut inside a tafsir group (block longer than max_seconds)

    @property
    def key(self) -> str:
        return f"{self.surah}:{self.start}-{self.end}"


def sentence_ends(translations: dict[int, str]) -> set[int]:
    return {a for a, t in translations.items() if _SENTENCE_END.search(t.strip())}


def split(seconds: list[float], ends: set[int], groups: list[tuple[int, int]],
          target: float, low: float, high: float, overhead: float) -> list[tuple[int, int, bool]]:
    """(start, end, relaxed) passages covering ayahs 1..len(seconds)."""
    n = len(seconds)
    prefix = [0.0, *accumulate(seconds)]
    cuts = {b for _, b in groups if b in ends} | {n}

    relaxed_cuts: set[int] = set()
    bounds = sorted(cuts)
    for a, b in zip([0, *bounds], bounds, strict=False):
        if prefix[b] - prefix[a] + overhead > high:
            relaxed_cuts |= {e for e in ends if a < e < b}
    cuts |= relaxed_cuts

    def cost(d: float) -> float:
        video = d + overhead
        if video > high:
            # Every second over the limit costs more than any number of passages within it:
            # an ayah too long on its own stays alone instead of swallowing its neighbours.
            return 1e6 + (video - high) * 1e5
        if video < low:
            return 1e4 + (low - video) ** 2
        return (video - target) ** 2

    points = [0, *sorted(cuts)]
    best: list[tuple[float, int]] = [(0.0, -1)]
    for j in range(1, len(points)):
        best.append(min((best[i][0] + cost(prefix[points[j]] - prefix[points[i]]), i)
                        for i in range(j)))
    out = []
    j = len(points) - 1
    while j > 0:
        i = best[j][1]
        start, end = points[i] + 1, points[j]
        out.append((start, end, (start - 1) in relaxed_cuts or end in relaxed_cuts))
        j = i
    return out[::-1]


def plan_surah(cfg: Config, surah: int, src: Sources | None = None) -> list[Planned]:
    src = src or Sources.from_config(cfg)
    src.quran.ensure(src.translation_slug)
    p, v = cfg.content["passage"], cfg.video
    target, low, high = (float(p[k]) for k in ("target_seconds", "min_seconds", "max_seconds"))
    overhead = float(v.get("lead_seconds", 0.4)) + float(v.get("tail_seconds", 1.2))

    n = src.quran.chapters[surah]["verses_count"]
    timings = src.ayah_seconds(cfg, surah)
    missing = [a for a in range(1, n + 1) if a not in timings]
    if missing:
        raise SystemExit(f"no timing for {surah}:{missing[0]} ({cfg.content['reciter']['id']})")
    seconds = [timings[a] for a in range(1, n + 1)]

    def basmala(start: int) -> float:
        if not needs_basmala(cfg, surah, start):
            return 0.0
        return src.basmala_seconds(cfg, surah)

    whole = sum(seconds) + overhead + basmala(1)
    if p.get("whole_surah", True) and whole <= high:
        return [Planned(surah, 1, n, round(whole, 1), whole_surah=True)]
    overhead += basmala(2)          # every later passage opens with it too

    refs = [AyahRef(surah, a) for a in range(1, n + 1)]
    translations = {r.ayah: t for r, t in src.quran.translate(src.translation_slug, refs).items()}
    groups = src.quran.tafsir_groups(surah, p["groups"])
    parts = split(seconds, sentence_ends(translations), groups, target, low, high, overhead)
    return [Planned(surah, a, b, round(sum(seconds[a - 1:b]) + overhead, 1), relaxed=r)
            for a, b, r in parts]


def resolve(cfg: Config, key: str) -> str:
    """'93' → '93:1-11' when the surah fits in one video; a passage key is returned as is."""
    key = key.strip()
    if not key.isdigit():
        return key
    plan = plan_surah(cfg, int(key))
    if len(plan) > 1:
        total = sum(p.seconds for p in plan)
        lines = [f"surah {key} is too long for one video ({total:.0f} s). Its passages:"]
        lines += [f"  {p.key:<10} # {p.seconds:.0f} s" for p in plan]
        raise SystemExit("\n".join(lines))
    return plan[0].key
