"""What to publish when: daily slots, series of passages, and what is already published.

config/schedule.yaml   time zone, slots (a time and a queue each), Friday rule, queues
config/series/*.yaml   a series: passages in order, or whole surahs split as config/plan.yaml
published.json         the state: what each queue has published, what each slot did
                       (kept on the `state` branch by the daily workflow)

A queue plays its series one after the other. Each slot takes the first passage of its queue
that is not published yet, so a day that fails is taken up again and nothing is skipped or
posted twice. On Fridays every slot takes from the Friday queue. A queue whose series repeat
starts over when it is done; any other queue, once done, hands over to its fallback.

Nothing here is generated: series list references chosen by people (proposed in a pull
request, validated by the owner); the texts come from the sources at render time.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from quran_reels.arabic import arabic_digits
from quran_reels.config import Config
from quran_reels.models import parse_passage

FRIDAY = 4


# ---- plan -----------------------------------------------------------------------------

@dataclass(frozen=True)
class PlanEntry:
    key: str
    seconds: float
    note: str = ""            # whole | relaxed | long


def plan_path(cfg: Config) -> Path:
    return cfg.root / "config" / "plan.yaml"


def write_plan(cfg: Config, path: Path | None = None) -> Path:
    """Split all 114 surahs (selector.plan) and freeze the result in config/plan.yaml."""
    from quran_reels.selector.plan import plan_surah
    from quran_reels.sources import Sources

    src = Sources.from_config(cfg)
    high = float(cfg.content["passage"]["max_seconds"])
    lines = [
        "# Every surah split into passages of about a minute, frozen so that the calendar does",
        "# not move when a source changes. Written by `quran-reels plan --write` from",
        "# config/project.yaml (passage, basmala, reciter); a cut can be edited by hand.",
        "# [passage, expected seconds, note] — note: whole (the surah in one video),",
        "# relaxed (cut inside an Ibn Kathir group), long (over max_seconds: skipped for now).",
        f"reciter: {cfg.content['reciter']['id']}",
        "surahs:",
    ]
    for s in range(1, 115):
        lines.append(f"  {s}:")
        for p in plan_surah(cfg, s, src):
            note = ("long" if p.seconds > high else "whole" if p.whole_surah
                    else "relaxed" if p.relaxed else "")
            lines.append(f'    - ["{p.key}", {p.seconds}{", " + note if note else ""}]')
    path = path or plan_path(cfg)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def load_plan(cfg: Config) -> dict[int, list[PlanEntry]]:
    path = plan_path(cfg)
    if not path.is_file():
        raise SystemExit(f"{path} is missing: run `quran-reels plan --write`")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {int(s): [PlanEntry(str(e[0]), float(e[1]), str(e[2]) if len(e) > 2 else "")
                     for e in entries]
            for s, entries in (raw.get("surahs") or {}).items()}


# ---- series ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Series:
    id: str
    passages: tuple[str, ...]
    title_ar: str = ""
    title_en: str = ""
    repeat: bool = False
    skipped: tuple[str, ...] = ()      # plan passages left out (longer than max_seconds)
    from_plan: bool = False            # whole surahs, as split in config/plan.yaml


def _passage_key(value: Any, where: str) -> str:
    """'2:127-128' or '2:255' → normalised key; YAML reads 11:6 unquoted as 11×60+6."""
    if isinstance(value, int) and not isinstance(value, bool):
        value = f"{value // 60}:{value % 60}"
    try:
        surah, start, end = parse_passage(str(value))
    except ValueError as e:
        raise SystemExit(f"{where}: {e}") from None
    return f"{surah}:{start}-{end}"


def series_dir(cfg: Config) -> Path:
    return cfg.root / "config" / "series"


def load_series(cfg: Config, plan: dict[int, list[PlanEntry]] | None = None) -> dict[str, Series]:
    out: dict[str, Series] = {}
    high = float(cfg.content["passage"]["max_seconds"])
    for path in sorted(series_dir(cfg).glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        where = f"config/series/{path.name}"
        keys: list[str] = []
        skipped: list[str] = []
        if raw.get("surahs"):
            plan = plan if plan is not None else load_plan(cfg)
            for s in raw["surahs"]:
                for e in plan[int(s)]:
                    (skipped if e.seconds > high else keys).append(e.key)
        for p in raw.get("passages") or []:
            keys.append(_passage_key(p, where))
        if not keys:
            raise SystemExit(f"{where}: no passages (give `passages` or `surahs`)")
        out[path.stem] = Series(id=path.stem, passages=tuple(keys),
                                title_ar=str(raw.get("title_ar") or ""),
                                title_en=str(raw.get("title_en") or ""),
                                repeat=bool(raw.get("repeat", False)), skipped=tuple(skipped),
                                from_plan=bool(raw.get("surahs")))
    return out


@dataclass(frozen=True)
class Item:
    """One passage of a series, as a slot publishes it."""

    series: Series
    key: str
    index: int                # 1-based position in the series

    @property
    def id(self) -> str:
        return f"{self.series.id}/{self.key}"

    @property
    def label_ar(self) -> str:
        """Shown on the first frame, e.g. «آيات الدعاء · ٣ من ٣٠»; empty without a title."""
        if not self.series.title_ar:
            return ""
        n = len(self.series.passages)
        if n == 1:
            return self.series.title_ar
        return f"{self.series.title_ar} · {arabic_digits(self.index)} من {arabic_digits(n)}"

    @property
    def label_en(self) -> str:
        """First line of the caption, e.g. «Supplications from the Quran · 3/30»."""
        if not self.series.title_en:
            return ""
        n = len(self.series.passages)
        return self.series.title_en if n == 1 else f"{self.series.title_en} · {self.index}/{n}"


# ---- schedule -------------------------------------------------------------------------

@dataclass(frozen=True)
class Slot:
    name: str
    at: time
    queue: str


@dataclass
class Schedule:
    tz: ZoneInfo
    enabled: bool
    slots: list[Slot]
    queues: dict[str, list[str]]                  # queue → series ids, played in order
    friday_queue: str | None = None
    fallback: dict[str, str] = field(default_factory=dict)
    early_minutes: int = 20                       # a run this early still takes the slot
    window_hours: float = 3                       # later than this, the slot is missed

    def queue_for(self, slot: Slot, day: date) -> str:
        if self.friday_queue and day.weekday() == FRIDAY:
            return self.friday_queue
        return slot.queue

    def due(self, now: datetime) -> list[tuple[date, Slot]]:
        """Slots whose window contains now (local time of the schedule)."""
        local = now.astimezone(self.tz)
        out = []
        for slot in self.slots:
            at = datetime.combine(local.date(), slot.at, self.tz)
            if at - timedelta(minutes=self.early_minutes) <= local \
                    < at + timedelta(hours=self.window_hours):
                out.append((local.date(), slot))
        return out


def _time(value: Any, where: str) -> time:
    if isinstance(value, int):              # YAML reads 07:30 unquoted as 450 (base 60)
        return time(value // 60, value % 60)
    try:
        return time.fromisoformat(str(value))
    except ValueError:
        raise SystemExit(f"{where}: «{value}» is not a time such as \"07:30\"") from None


def load_schedule(cfg: Config, series: dict[str, Series] | None = None) -> Schedule:
    path = cfg.root / "config" / "schedule.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None
    if not raw:
        raise SystemExit(f"{path} is missing")
    queues = {str(q): [str(s) for s in v] for q, v in (raw.get("queues") or {}).items()}
    slots = [Slot(str(name), _time(s.get("time"), f"schedule.yaml, slot {name}"),
                  str(s.get("queue")))
             for name, s in (raw.get("slots") or {}).items()]
    sched = Schedule(tz=ZoneInfo(str(raw.get("timezone", "Europe/Paris"))),
                     enabled=bool(raw.get("enabled", False)), slots=slots, queues=queues,
                     friday_queue=(raw.get("fridays") or {}).get("queue"),
                     fallback={str(k): str(v) for k, v in (raw.get("fallback") or {}).items()},
                     early_minutes=int(raw.get("early_minutes", 20)),
                     window_hours=float(raw.get("window_hours", 3)))
    used = {s.queue for s in slots} | set(sched.fallback.values()) | (
        {sched.friday_queue} if sched.friday_queue else set())
    for q in sorted(used):
        if q not in queues:
            raise SystemExit(f"config/schedule.yaml: queue «{q}» is not defined in queues")
    if series is not None:
        for q, ids in queues.items():
            for sid in ids:
                if sid not in series:
                    raise SystemExit(f"config/schedule.yaml: queue {q}: no config/series/{sid}.yaml")
    return sched


# ---- state ----------------------------------------------------------------------------

OK_STATUSES = ("published", "draft")


class State:
    """published.json: {"queues": {q: {"round": n, "done": [item ids]}}, "slots": {...}}."""

    def __init__(self, data: dict | None = None):
        self.data = data or {}
        self.data.setdefault("queues", {})
        self.data.setdefault("slots", {})

    @classmethod
    def load(cls, path: Path) -> State:
        if path.is_file() and path.read_text(encoding="utf-8").strip():
            return cls(json.loads(path.read_text(encoding="utf-8")))
        return cls()

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")

    def queue(self, name: str) -> dict:
        return self.data["queues"].setdefault(name, {"round": 1, "done": []})

    def slot(self, day: date, slot: str) -> dict | None:
        return self.data["slots"].get(f"{day.isoformat()}/{slot}")

    def set_slot(self, day: date, slot: str, record: dict) -> None:
        self.data["slots"][f"{day.isoformat()}/{slot}"] = record

    def copy(self) -> State:
        return State(copy.deepcopy(self.data))


def queue_items(sched: Schedule, series: dict[str, Series], queue: str) -> list[Item]:
    return [Item(series[sid], key, i)
            for sid in sched.queues[queue]
            for i, key in enumerate(series[sid].passages, start=1)]


def next_item(sched: Schedule, series: dict[str, Series], state: State,
              queue: str) -> tuple[str, Item] | None:
    """(queue it comes from, item) for the next publication from queue, or None."""
    seen: set[str] = set()
    while queue not in seen:
        seen.add(queue)
        items = queue_items(sched, series, queue)
        done = set(state.queue(queue)["done"])
        for item in items:
            if item.id not in done:
                return queue, item
        if items and all(i.series.repeat for i in items):
            q = state.queue(queue)
            q["round"], q["done"] = q["round"] + 1, []
            return queue, items[0]
        if queue not in sched.fallback:
            return None
        queue = sched.fallback[queue]
    return None


def item_by_id(sched: Schedule, series: dict[str, Series], queue: str, item_id: str) -> Item:
    for item in queue_items(sched, series, queue):
        if item.id == item_id:
            return item
    sid, key = item_id.split("/", 1)
    if sid in series:            # the series was edited since: keep what the slot started
        return Item(series[sid], key, 1)
    raise SystemExit(f"{item_id}: series {sid} no longer exists")


def mark_done(state: State, queue: str, item: Item) -> None:
    done = state.queue(queue)["done"]
    if item.id not in done:
        done.append(item.id)


def preview(sched: Schedule, series: dict[str, Series], state: State, start: date,
            days: int) -> list[tuple[date, Slot, str, Item | None]]:
    """What the next days would publish if every slot succeeded (the state is not changed)."""
    sim = state.copy()
    out = []
    for d in range(days):
        day = start + timedelta(days=d)
        for slot in sorted(sched.slots, key=lambda s: s.at):
            record = sim.slot(day, slot.name)
            if record:
                queue = record["queue"]
                item = item_by_id(sched, series, queue, record["item"])
            else:
                got = next_item(sched, series, sim, sched.queue_for(slot, day))
                if got is None:
                    out.append((day, slot, sched.queue_for(slot, day), None))
                    continue
                queue, item = got
                mark_done(sim, queue, item)
            out.append((day, slot, queue, item))
    return out


# ---- checks ---------------------------------------------------------------------------

@dataclass
class Checked:
    series: str
    key: str
    seconds: float
    problems: list[str]


def check_series(cfg: Config, series: dict[str, Series], src: Any = None) -> list[Checked]:
    """Hand-written passages against the rules: whole sentences, at most max_seconds.

    A passage starts at the start of a surah or after an ayah that ends a sentence in the
    translation, and ends with a sentence (selector.plan.sentence_ends). Seconds as planned:
    the reciter's timings, the video's lead and tail, the basmala.
    """
    from quran_reels.models import AyahRef
    from quran_reels.passage import needs_basmala
    from quran_reels.selector.plan import sentence_ends
    from quran_reels.sources import Sources

    src = src or Sources.from_config(cfg)
    src.quran.ensure(src.translation_slug)
    v, p = cfg.video, cfg.content["passage"]
    overhead = float(v.get("lead_seconds", 0.4)) + float(v.get("tail_seconds", 1.2))
    high = float(p["max_seconds"])
    tid = int(cfg.content["reciter"]["timings_id"])
    basmala = src.quran.timings(1, tid)[1]
    ends: dict[int, set[int]] = {}
    out = []
    for s in series.values():
        if s.from_plan:
            out += [Checked(s.id, k, 0.0, ["longer than max_seconds: left out for now"])
                    for k in s.skipped]
            continue
        for key in s.passages:
            surah, start, end = parse_passage(key)
            n = src.quran.chapters[surah]["verses_count"]
            if end > n:
                out.append(Checked(s.id, key, 0.0, [f"surah {surah} has {n} ayahs"]))
                continue
            if surah not in ends:
                refs = [AyahRef(surah, a) for a in range(1, n + 1)]
                tr = src.quran.translate(src.translation_slug, refs)
                ends[surah] = sentence_ends({r.ayah: t for r, t in tr.items()})
            timings = src.quran.timings(surah, tid)
            seconds = sum(timings[a] for a in range(start, end + 1)) + overhead + (
                basmala if needs_basmala(cfg, surah, start) else 0.0)
            problems = []
            if start > 1 and start - 1 not in ends[surah]:
                problems.append(f"starts mid-sentence ({surah}:{start - 1} does not end one)")
            if end < n and end not in ends[surah]:
                problems.append(f"ends mid-sentence ({surah}:{end} does not end one)")
            if seconds > high:
                problems.append(f"{seconds:.0f} s, longer than {high:.0f} s")
            out.append(Checked(s.id, key, round(seconds, 1), problems))
    return out
