"""Rules 5-6 of docs/images.md: exclusions, stable order, and the state of what was posted.

5. config/exclude.yaml: ayahs, ranges or surahs never posted as images (read at every run).
6. A stable permutation of all candidates: each one's rank is a hash of (seed, round, id), so
   adding or removing candidates never reshuffles the others. No candidate comes back before
   all of them are done (then a new round, in a new order), and never the same surah two days
   in a row: a candidate of yesterday's surah waits for the next day.

State: images.json on the `state` branch, next to the reels' published.json:
{"word": {"round": 1, "done": ["93:3#0", ...], "posts": {"2026-11-06": {...}}}, "ayah": {...}}
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

from quran_reels.config import Config
from quran_reels.images.candidates import Candidate

# ---- exclusions -------------------------------------------------------------------------

@dataclass
class Exclusions:
    surahs: set[int] = field(default_factory=set)
    ranges: list[tuple[int, int, int]] = field(default_factory=list)     # surah, from, to

    def covers(self, surah: int, start: int, end: int) -> bool:
        """True if any ayah of surah:start-end is excluded."""
        return surah in self.surahs or any(
            s == surah and a <= end and start <= b for s, a, b in self.ranges)

    def excludes(self, c: Candidate) -> bool:
        return self.covers(c.surah, *c.context) or (
            c.kind == "word" and self.covers(c.surah, c.ayah, c.ayah))


def parse_exclusions(raw: list[Any], where: str = "config/exclude.yaml") -> Exclusions:
    out = Exclusions()
    for item in raw or []:
        text = str(item).strip()
        try:
            if ":" not in text:
                out.surahs.add(int(text))
                continue
            surah, rng = text.split(":")
            a, _, b = rng.partition("-")
            out.ranges.append((int(surah), int(a), int(b or a)))
        except ValueError:
            raise SystemExit(f"{where}: cannot read {text!r} (expected 9, 2:255 or 2:1-5)") \
                from None
    return out


def load_exclusions(cfg: Config) -> Exclusions:
    path = cfg.root / "config" / "exclude.yaml"
    if not path.is_file():
        return Exclusions()
    # BaseLoader: every value stays a string, so an unquoted 2:55 is not read as 175
    # (YAML 1.1 reads it as a base-60 number).
    raw = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader) or {}
    return parse_exclusions(raw.get("exclude") or [])


# ---- state ------------------------------------------------------------------------------

class ImageState:
    def __init__(self, data: dict | None = None):
        self.data = data or {}

    @classmethod
    def load(cls, path: Path) -> ImageState:
        return cls(json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {})

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")

    def copy(self) -> ImageState:
        return ImageState(copy.deepcopy(self.data))

    def kind(self, kind: str) -> dict:
        return self.data.setdefault(kind, {"round": 1, "done": [], "posts": {}})

    def post(self, kind: str, day: date) -> dict | None:
        return self.kind(kind)["posts"].get(day.isoformat())

    def set_post(self, kind: str, day: date, record: dict) -> None:
        self.kind(kind)["posts"][day.isoformat()] = record

    def last_surah(self, kind: str, before: date) -> int | None:
        posts = self.kind(kind)["posts"]
        days = sorted(d for d in posts if d < before.isoformat())
        return posts[days[-1]]["surah"] if days else None

    def mark_done(self, kind: str, c: Candidate) -> None:
        k = self.kind(kind)
        if c.id not in k["done"]:
            k["done"].append(c.id)


# ---- order ------------------------------------------------------------------------------

def rank(seed: str, round_: int, candidate_id: str) -> str:
    return hashlib.sha256(f"{seed}:{round_}:{candidate_id}".encode()).hexdigest()


def next_candidate(candidates: list[Candidate], state: ImageState, kind: str, seed: str,
                   exclusions: Exclusions, day: date) -> Candidate | None:
    """The candidate for `day`; starts a new round in the state when all are done."""
    k = state.kind(kind)
    allowed = [c for c in candidates if not exclusions.excludes(c)]
    if not allowed:
        return None
    pool = [c for c in allowed if c.id not in set(k["done"])]
    if not pool:                                # all done: a new round, in a new order
        k["round"] += 1
        k["done"] = []
        pool = allowed
    pool.sort(key=lambda c: rank(seed, k["round"], c.id))
    yesterday = state.last_surah(kind, day)
    return next((c for c in pool if c.surah != yesterday), pool[0])


def upcoming(candidates: list[Candidate], state: ImageState, kind: str, seed: str,
             exclusions: Exclusions, start: date, days: int) -> list[tuple[date, Candidate]]:
    """What the next `days` days will post, from `start` (the state is not changed)."""
    sim = state.copy()
    out = []
    for n in range(days):
        day = start + timedelta(days=n)
        existing = sim.post(kind, day)
        if existing:
            c = next((x for x in candidates if x.id == existing["id"]), None)
        else:
            c = next_candidate(candidates, sim, kind, seed, exclusions, day)
            if c:
                sim.mark_done(kind, c)
                sim.set_post(kind, day, {"id": c.id, "surah": c.surah, "planned": True})
        if c:
            out.append((day, c))
    return out
