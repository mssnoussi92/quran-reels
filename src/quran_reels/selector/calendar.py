"""What to publish when: daily slots, series of passages, and what is already published.

config/schedule.yaml   time zone, slots (a time and a queue each), Friday rule, queues
config/series/*.yaml   a series: passages in order, or whole surahs split as config/plan.yaml
published.json         the state: what each queue has published, what each slot did
                       (kept on the `state` branch by the daily workflow)

A queue plays its series one after the other. Each slot takes the first passage of its queue
that is not published yet, so a day that fails is taken up again and nothing is skipped or
posted twice. On Fridays the slots take from the Friday queues instead (one per slot, or one
for all). A queue whose series repeat starts over when it is done; any other queue, once done,
hands over to its fallback.

Nothing here is generated: series list references chosen by people (proposed in a pull
request, validated by the owner); the texts come from the sources at render time.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
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
    hashtags: tuple[str, ...] = ()


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
                                from_plan=bool(raw.get("surahs")),
                                hashtags=tuple(str(t) for t in raw.get("hashtags") or ()))
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

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


@dataclass(frozen=True)
class Period:
    """Days a slot publishes (schedule.yaml, `days` of a slot): from `start` to `end`, both
    included and either open, and only on `weekdays` when some are given (0 = Monday)."""
    start: date | None = None
    end: date | None = None
    weekdays: frozenset[int] = frozenset()

    def covers(self, day: date) -> bool:
        return ((self.start is None or self.start <= day) and (self.end is None or day <= self.end)
                and (not self.weekdays or day.weekday() in self.weekdays))


@dataclass(frozen=True)
class Slot:
    name: str
    at: time
    queue: str
    # Owner's choices, 2026-11-13: one reel a day from the 14th, the morning one, and the theme
    # series on Sunday evenings only. Empty: every day.
    days: tuple[Period, ...] = ()

    def on(self, day: date) -> bool:
        """Does this slot publish on that day? Outside its days it is not due, not shown,
        never a missed slot."""
        return not self.days or any(p.covers(day) for p in self.days)

    def ended(self, today: date) -> bool:
        """No day left from today on (all its periods are over)."""
        return bool(self.days) and all(p.end is not None and p.end < today for p in self.days)


@dataclass(frozen=True)
class Pause:
    """Days without a reel (owner's choice: 2026-11-12, the theme episodes start). Nothing is
    published on them and no slot of theirs is missed; the queues wait, so the first slot after
    the pause publishes the passage that was next. end: the last day without a reel; None until
    the owner turns the reels back on."""
    start: date
    end: date | None = None

    def covers(self, day: date) -> bool:
        return self.start <= day and (self.end is None or day <= self.end)

    def __str__(self) -> str:
        return f"from {self.start}" + (f" to {self.end}" if self.end else
                                        " until the reels are turned back on")


@dataclass
class Schedule:
    tz: ZoneInfo
    enabled: bool
    slots: list[Slot]
    queues: dict[str, list[str]]                  # queue → series ids, played in order
    friday_queue: str | None = None               # every slot on Fridays, unless listed below
    friday_queues: dict[str, str] = field(default_factory=dict)   # slot → queue on Fridays
    fallback: dict[str, str] = field(default_factory=dict)
    published_by_hand: frozenset[str] = frozenset()   # passage keys the calendar skips
    early_minutes: int = 20                       # a run this early still takes the slot
    window_hours: float = 3                       # later than this, the slot is missed
    pause: Pause | None = None                    # days without a reel (schedule.yaml, pause)

    def paused(self, day: date) -> bool:
        return self.pause is not None and self.pause.covers(day)

    def queue_for(self, slot: Slot, day: date) -> str:
        if day.weekday() == FRIDAY:
            return self.friday_queues.get(slot.name) or self.friday_queue or slot.queue
        return slot.queue

    def due(self, now: datetime) -> list[tuple[date, Slot]]:
        """Slots whose window contains now (local time of the schedule)."""
        local = now.astimezone(self.tz)
        out = []
        for slot in self.slots:
            if not slot.on(local.date()):
                continue
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


def _day(value: Any, where: str) -> date | None:
    """A day of schedule.yaml (YAML reads 2026-11-13 as a date); empty: None."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise SystemExit(f"{where}: «{value}» is not a day such as 2026-11-13") from None


def _periods(raw: Any, where: str) -> tuple[Period, ...]:
    """A slot's `days`: a list of {from, until, weekdays}, each key optional."""
    if not raw:
        return ()
    if not isinstance(raw, list):
        raise SystemExit(f"{where}: a list, e.g. `- {{from: 2026-11-15, weekdays: [sunday]}}`")
    out = []
    for i, item in enumerate(raw, 1):
        here = f"{where} #{i}"
        if not isinstance(item, dict) or set(item) - {"from", "until", "weekdays"}:
            raise SystemExit(f"{here}: only from, until and weekdays")
        names = [str(w).lower() for w in item.get("weekdays") or ()]
        wrong = [w for w in names if w not in WEEKDAYS]
        if wrong:
            raise SystemExit(f"{here}: weekdays {', '.join(wrong)}? ({', '.join(WEEKDAYS)})")
        period = Period(_day(item.get("from"), f"{here}, from"),
                        _day(item.get("until"), f"{here}, until"),
                        frozenset(WEEKDAYS.index(w) for w in names))
        if period.start and period.end and period.end < period.start:
            raise SystemExit(f"{here}: until ({period.end}) is before from ({period.start})")
        out.append(period)
    return tuple(out)


def _pause(raw: Any) -> Pause | None:
    """schedule.yaml `pause: {from: 2026-11-13, until: …}`; until empty: no end yet."""
    if not raw:
        return None
    where = "config/schedule.yaml, pause"
    if not isinstance(raw, dict) or not raw.get("from"):
        raise SystemExit(f"{where}: give its first day, `from: 2026-11-13`")
    start, end = _day(raw["from"], f"{where}, from"), _day(raw.get("until"), f"{where}, until")
    if start is None:
        raise SystemExit(f"{where}: give its first day, `from: 2026-11-13`")
    if end is not None and end < start:
        raise SystemExit(f"{where}: until ({end}) is before from ({start})")
    return Pause(start, end)


def load_schedule(cfg: Config, series: dict[str, Series] | None = None) -> Schedule:
    path = cfg.root / "config" / "schedule.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None
    if not raw:
        raise SystemExit(f"{path} is missing")
    queues = {str(q): [str(s) for s in v] for q, v in (raw.get("queues") or {}).items()}
    slots = [Slot(str(name), _time(s.get("time"), f"schedule.yaml, slot {name}"),
                  str(s.get("queue")),
                  _periods(s.get("days"), f"config/schedule.yaml, slot {name}, days"))
             for name, s in (raw.get("slots") or {}).items()]
    fridays = dict(raw.get("fridays") or {})       # {queue: q} for every slot, {slot: q} each
    friday_queue = fridays.pop("queue", None)
    names = {s.name for s in slots}
    for name in fridays:
        if name not in names:
            raise SystemExit(f"config/schedule.yaml: fridays: no slot «{name}» "
                             f"(slots: {', '.join(sorted(names))})")
    sched = Schedule(tz=ZoneInfo(str(raw.get("timezone", "Europe/Paris"))),
                     enabled=bool(raw.get("enabled", False)), slots=slots, queues=queues,
                     friday_queue=str(friday_queue) if friday_queue else None,
                     friday_queues={str(k): str(v) for k, v in fridays.items()},
                     fallback={str(k): str(v) for k, v in (raw.get("fallback") or {}).items()},
                     published_by_hand=frozenset(
                         _passage_key(k, "config/schedule.yaml, published_by_hand")
                         for k in raw.get("published_by_hand") or ()),
                     early_minutes=int(raw.get("early_minutes", 20)),
                     window_hours=float(raw.get("window_hours", 3)),
                     pause=_pause(raw.get("pause")))
    used = {s.queue for s in slots} | set(sched.fallback.values()) | (
        {sched.friday_queue} if sched.friday_queue else set()) | set(sched.friday_queues.values())
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
            if item.id not in done and item.key not in sched.published_by_hand:
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


def reopen(state: State, key: str, why: str, claimed: bool = False) -> dict:
    """A slot whose posts the owner deleted (a bad cut, a claim): its passage goes back to the
    head of its queue and the slot is free again, so the next run in its window, or the next
    slot of its queue, publishes it again. The old record is kept under `removed`, with why.
    claimed: the recording was claimed, its reciter is never chosen again."""
    record = state.data["slots"].pop(key, None)
    if record is None:
        raise SystemExit(f"{key}: no such slot in the state (day/slot, e.g. 2026-11-05/evening)")
    done = state.queue(record["queue"])["done"]
    if record["item"] in done:
        done.remove(record["item"])
    state.data.setdefault("removed", []).append({"slot": key, "record": record, "why": why})
    if claimed and record.get("reciter"):
        state.data.setdefault("claimed", {}).setdefault(record["reciter"], {
            "slot": key, "passage": record["passage"], "reason": why})
    return record


MISSED_DAYS = 2            # how far back a slot nobody tried is looked for


def missed_slots(sched: Schedule, state: State, now: datetime,
                 days: int = MISSED_DAYS) -> list[str]:
    """Slots of the last days whose window is over and that no run ever started: a slot a run
    took has a record, even failed or blocked; these have none. Nothing else notices them: the
    failure alert is written by a run, and here no run came (the scheduler did not fire, or
    GitHub started no job: 2026-11-09 evening, runs #26 and #27 without a job).

    Not the slots before the first one ever published, not a reopened slot (its passage is
    republished by the next slot of its queue), not one already reported (state `missed`), not
    a day of the pause (nothing was meant to go out: the reels turned back on, no alarm)."""
    if not state.data["slots"]:
        return []
    first = min(state.data["slots"]).split("/")[0]
    reopened = {r.get("slot") for r in state.data.get("removed", [])}
    told = state.data.get("missed", {})
    local = now.astimezone(sched.tz)
    out = []
    for back in range(days - 1, -1, -1):
        day = local.date() - timedelta(days=back)
        if sched.paused(day):
            continue
        for slot in sorted(sched.slots, key=lambda s: s.at):
            if not slot.on(day):
                continue
            end = datetime.combine(day, slot.at, sched.tz) + timedelta(hours=sched.window_hours)
            key = f"{day.isoformat()}/{slot.name}"
            if local >= end and day.isoformat() > first and key not in state.data["slots"] \
                    and key not in reopened and key not in told:
                out.append(key)
    return out


def record_by_hand(sched: Schedule, series: dict[str, Series], state: State, key: str,
                   passage: str, results: list[dict], reciter: str | None = None) -> dict:
    """A slot published outside the daily run (publish-test in mode publish: a reopened slot, a
    reciter's first reel), written as the daily run would have: the slot's record and, once a
    platform has the reel, its passage done in its queue. Writing the record alone is not
    enough: the passage stays first in its queue and the next slot publishes it again.

    results: publish.json's (platform, status, remote_id, url, error); a later call for the
    same slot adds its platforms (Facebook first, Instagram once the owner has seen no claim).
    The record is marked `by_hand`: the daily run never completes it, a platform left out is
    left out on purpose (the owner checks the rights before Instagram)."""
    try:
        day_s, slot_name = key.split("/")
        day = date.fromisoformat(day_s)
    except ValueError:
        raise SystemExit(f"{key}: not a slot (day/slot, e.g. 2026-11-05/evening)") from None
    slot = next((sl for sl in sched.slots if sl.name == slot_name), None)
    if slot is None:
        raise SystemExit(f"{key}: no slot «{slot_name}» in config/schedule.yaml")
    wanted = _passage_key(passage, "state record")
    record = state.slot(day, slot.name)
    if record and record["passage"] != wanted:
        raise SystemExit(f"{key} already holds {record['passage']}, not {wanted}: reopen it "
                         "first (quran-reels state reopen) if its posts were deleted")
    if not record:
        queue, seen, item = sched.queue_for(slot, day), set(), None
        while queue not in seen and item is None:        # the queue, then its fallbacks
            seen.add(queue)
            item = next((i for i in queue_items(sched, series, queue) if i.key == wanted), None)
            if item is None:
                if queue not in sched.fallback:
                    break
                queue = sched.fallback[queue]
        if item is None:
            raise SystemExit(f"{wanted} is not a passage of the queue of {key} "
                             f"({sched.queue_for(slot, day)}): nothing recorded")
        record = {"queue": queue, "item": item.id, "passage": wanted, "results": {}}
    for r in results:
        record["results"][r["platform"]] = {
            "status": r["status"], "id": r.get("remote_id") or r.get("id"), "url": r.get("url"),
            "error": r.get("error"), "at": datetime.now(UTC).isoformat(timespec="seconds")}
    record["by_hand"] = True
    if reciter:
        record["reciter"] = reciter
    state.set_slot(day, slot.name, record)
    if any(r["status"] in OK_STATUSES for r in record["results"].values()):
        done = state.queue(record["queue"])["done"]
        if record["item"] not in done:
            done.append(record["item"])
    return record


def preview(sched: Schedule, series: dict[str, Series], state: State, start: date,
            days: int, skip_paused: bool = True) -> list[tuple[date, Slot, str, Item | None]]:
    """What the next days would publish if every slot succeeded (the state is not changed).
    The days of the pause publish nothing (skip_paused=False: as if there were none, for the
    passages that come first once the reels are back on: the queues wait meanwhile)."""
    sim = state.copy()
    out = []
    for d in range(days):
        day = start + timedelta(days=d)
        if skip_paused and sched.paused(day):
            continue
        for slot in sorted(sched.slots, key=lambda s: s.at):
            if not slot.on(day):
                continue
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
    the reciter's timings, the video's lead and tail, the basmala. With content.rotation, a
    passage too long for that estimate passes if a reciter of the rotation, ready for it, fits
    (reciters.choose picks among those: 18:1-10 is 88 s with Salah Budair, over 108 s with the
    others).
    """
    from quran_reels.models import AyahRef
    from quran_reels.passage import needs_basmala
    from quran_reels.selector.plan import ends_sentence, sentence_ends, starts_sentence
    from quran_reels.sources import Sources

    src = src or Sources.from_config(cfg)
    src.quran.ensure(src.translation_slug)
    v, p = cfg.video, cfg.content["passage"]
    overhead = float(v.get("lead_seconds", 0.4)) + float(v.get("tail_seconds", 1.2))
    high = float(p["max_seconds"])
    basmala = src.basmala_seconds(cfg)
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
            timings = src.ayah_seconds(cfg, surah)
            seconds = sum(timings[a] for a in range(start, end + 1)) + overhead + (
                basmala if needs_basmala(cfg, surah, start) else 0.0)
            problems = []
            if not starts_sentence(start, ends[surah]):
                problems.append(f"starts mid-sentence ({surah}:{start - 1} does not end one)")
            if not ends_sentence(end, n, ends[surah]):
                problems.append(f"ends mid-sentence ({surah}:{end} does not end one)")
            if seconds > high:
                fit = _rotation_fit(cfg, key, high)
                if fit is not None:
                    seconds = fit
                else:
                    problems.append(f"{seconds:.0f} s, longer than {high:.0f} s")
            out.append(Checked(s.id, key, round(seconds, 1), problems))
    return out


def _rotation_fit(cfg: Config, key: str, high: float) -> float | None:
    """Seconds of the shortest reciter of the rotation ready for key and within high."""
    from quran_reels.reciters import options, rotation

    if not rotation(cfg):
        return None
    fits = [o.seconds for o in options(cfg, key) if o.seconds is not None and o.seconds <= high]
    return min(fits) if fits else None
