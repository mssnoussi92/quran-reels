"""Calendar and series: the coming days as `quran-reels calendar --days 14` shows them, how far
each queue and series has gone, and the next Word of the day images.

Same functions as the daily run (selector.calendar.preview, reciters.choose,
images.select.upcoming) on copies of the state: nothing is changed.
"""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from quran_reels import reciters as rec
from quran_reels.config import Config
from quran_reels.selector.calendar import (
    OK_STATUSES,
    Schedule,
    Series,
    Slot,
    State,
    preview,
    queue_items,
)

DAYS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
             "septembre", "octobre", "novembre", "décembre"]


SLOTS_FR = {"morning": "matin", "evening": "soir"}


def day_label(d: date) -> str:
    return f"{DAYS_FR[d.weekday()]} {d.day} {MONTHS_FR[d.month - 1]}"


WEEKDAYS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def slot_days_label(slot: Slot, today: date) -> str:
    """When a slot publishes, in French, from today on: "" every day; else its periods still
    to come («jusqu'au vendredi 13 novembre ; puis le dimanche, à partir du dimanche 15 …»)."""
    parts = []
    for p in slot.days:
        if p.end is not None and p.end < today:
            continue
        bits = []
        if p.weekdays:
            bits.append("le " + " et le ".join(WEEKDAYS_FR[d] for d in sorted(p.weekdays)))
        if p.start and p.start > today:
            bits.append(f"à partir du {day_label(p.start)}")
        if p.end:
            bits.append(f"jusqu'au {day_label(p.end)}")
        parts.append(", ".join(bits) or "chaque jour")
    return " ; puis ".join(parts)


def pause_label(sched: Schedule, today: date) -> str:
    """The pause of the reels (schedule.yaml `pause`), in French, while it is on or to come."""
    p = sched.pause
    if p is None or (p.end is not None and p.end < today):
        return ""
    if p.end is None:
        return f"à partir du {day_label(p.start)}, jusqu'à réactivation"
    return f"du {day_label(p.start)} au {day_label(p.end)} inclus"


def ref(key: str) -> str:
    """«2:255-255» → «2:255»; «93:1-11» unchanged."""
    head, _, end = key.partition("-")
    return head if end and head.split(":")[-1] == end else key


def surah_name(src: Any, key: str) -> str:
    try:
        return src.quran.chapters[int(key.split(":")[0])]["name_simple"]
    except (KeyError, ValueError, AttributeError):
        return ""


def slot_status(record: dict | None) -> str:
    """published | partial | failed | blocked | claimed | "" (not started)."""
    if not record:
        return ""
    if record.get("claimed"):
        return "claimed"
    statuses = [r.get("status") for r in (record.get("results") or {}).values()]
    if "blocked" in statuses:
        return "blocked"
    ok = [s in OK_STATUSES for s in statuses]
    if ok and all(ok):
        return "published"
    return "partial" if any(ok) else "failed"


def calendar(cfg: Config, sched: Schedule, series: dict[str, Series], state: State,
             start: date, days: int, picker: Any, src: Any = None) -> list[dict]:
    """The coming slots, grouped by day: passage, series, reciter and its length, background."""
    order = {s.name: i for i, s in enumerate(sorted(sched.slots, key=lambda s: s.at))}
    recent = rec.recent_reciters(state, order)
    claimed = rec.claimed_reciters(state)
    rotation = rec.rotation(cfg)
    labels = {n: r.get("label", n) for n, r in (cfg.content.get("reciters") or {}).items()}
    out: dict[date, dict] = {}
    for day, slot, queue, item in preview(sched, series, state, start, days):
        row: dict[str, Any] = {"slot": slot.name, "time": f"{slot.at:%H:%M}", "queue": queue}
        record = state.slot(day, slot.name)
        row["status"] = slot_status(record)
        if item is None:
            row["empty"] = True
        else:
            total = len(item.series.passages)
            row |= {"passage": item.key, "ref": ref(item.key),
                    "surah": surah_name(src, item.key), "series": item.series.id,
                    "title_ar": item.series.title_ar, "index": item.index, "total": total,
                    "label": item.label_en or (item.series.id if total == 1
                                               else f"{item.series.id} · {item.index}/{total}")}
            if rotation:
                name = (record or {}).get("reciter")
                try:
                    if not name:
                        name = rec.choose(cfg, item.key, recent, claimed)[0]
                    secs = rec.passage_seconds(rec.with_reciter(cfg, name), item.key).seconds
                    recent.append(name)         # as `quran-reels calendar` does
                except SystemExit:
                    secs = None
                    if not record:
                        row["not_ready"] = [
                            {"name": o.name, "label": labels.get(o.name, o.name),
                             "why": o.why or (f"{o.seconds:.0f} s" if o.seconds else "")}
                            for o in rec.options(cfg, item.key, claimed)]
                if record and not record.get("reciter"):
                    row["reciter_unknown"] = True       # published: never guessed on the page
                elif name and not row.get("not_ready"):
                    row |= {"reciter": name, "reciter_label": labels.get(name, name),
                            "seconds": secs}
            try:
                row["background"] = picker.pick(item.key) if picker else None
            except Exception as e:     # noqa: BLE001  (a missing translation: no background)
                print(f"warning: background of {item.key}: {type(e).__name__}", file=sys.stderr)
        d = out.setdefault(day, {"date": day.isoformat(), "label": day_label(day),
                                 "friday": day.weekday() == 4, "today": day == start,
                                 "slots": []})
        d["slots"].append(row)
    return list(out.values())


def progress(sched: Schedule, series: dict[str, Series], state: State,
             today: date | None = None) -> list[dict]:
    """Each queue: its round, its series in order, how many passages each has published.
    A slot that ended before today (schedule.yaml `until`) uses no queue any more."""
    data = state.copy()
    users: dict[str, list[str]] = {}
    live = {s.name for s in sched.slots if today is None or not s.ended(today)}
    for s in sched.slots:
        if s.name in live:
            users.setdefault(s.queue, []).append(f"{SLOTS_FR.get(s.name, s.name)} {s.at:%H:%M}")
    for slot, q in sched.friday_queues.items():
        if slot in live:
            users.setdefault(q, []).append(f"vendredi {SLOTS_FR.get(slot, slot)}")
    if sched.friday_queue:
        users.setdefault(sched.friday_queue, []).append("vendredi")
    out = []
    for q, ids in sched.queues.items():
        qs = data.queue(q)
        done = set(qs.get("done") or [])
        items = queue_items(sched, series, q)
        nxt = next((i for i in items if i.id not in done and i.key not in sched.published_by_hand),
                   None)
        rows = []
        for sid in ids:
            s = series[sid]
            n_done = sum(1 for k in s.passages if f"{sid}/{k}" in done)
            by_hand = sum(1 for k in s.passages if k in sched.published_by_hand
                          and f"{sid}/{k}" not in done)
            rows.append({"id": sid, "title": s.title_en or sid, "title_ar": s.title_ar,
                         "total": len(s.passages), "done": n_done, "by_hand": by_hand,
                         "repeat": s.repeat, "skipped": len(s.skipped),
                         "next": ref(nxt.key) if nxt and nxt.series.id == sid else "",
                         "first": s.passages[0], "last": s.passages[-1]})
        total = sum(r["total"] for r in rows)
        out.append({"queue": q, "used_by": users.get(q, []), "round": qs.get("round", 1),
                    "done": sum(r["done"] + r["by_hand"] for r in rows), "total": total,
                    "fallback": sched.fallback.get(q, ""), "series": rows,
                    "next": ref(nxt.key) if nxt else ""})
    return out


def words(cfg: Config, src: Any, state_path: Path | None, now: datetime, days: int
          ) -> dict[str, Any]:
    """The next Word of the day images (config/images.yaml), as `images next` shows them:
    from today, or from tomorrow once today's window has passed without a post."""
    from quran_reels.images import candidates as cand_mod
    from quran_reels.images import daily as images_daily
    from quran_reels.images.select import ImageState, load_exclusions, upcoming

    settings = images_daily.settings(cfg)
    conf = (settings.get("formats") or {}).get("word") or {}
    state = ImageState.load(state_path) if state_path else ImageState()
    now = now.astimezone(UTC)
    start = now.date()
    at = datetime.combine(start, time.fromisoformat(str(conf.get("time_utc", "23:59"))), UTC)
    if not state.post("word", start) and now > at + timedelta(
            hours=float(settings.get("window_hours", 6))):
        start += timedelta(days=1)
    picks = upcoming(cand_mod.load(cfg, "word"), state, "word",
                     conf.get("seed", "quran-words-daily"), load_exclusions(cfg), start, days)
    max_chars = int(cfg.content["glosses"].get("max_chars", 170))
    rows = []
    for day, c in picks:
        posted = state.post("word", day) or {}
        row = {"date": day.isoformat(), "label": day_label(day), "ayah": c.key,
               "surah": src.quran.chapters[c.surah]["name_simple"],
               "surah_ar": src.quran.chapters[c.surah]["name_arabic"],
               "image2": f"{c.surah}:{c.context[0]}" if c.context[0] == c.context[1]
               else f"{c.surah}:{c.context[0]}-{c.context[1]}",
               "posted": bool(posted.get("results")), "word": "", "gloss": ""}
        try:
            row |= _word(cfg, src, c, max_chars)
        except Exception as e:     # noqa: BLE001  (tafsir.app down: the word only)
            print(f"warning: word of {day}: {type(e).__name__}", file=sys.stderr)
            try:
                from quran_reels.arabic import words as tokens
                from quran_reels.models import AyahRef
                from quran_reels.passage import shown_words

                ref = AyahRef(c.surah, c.ayah)
                row["word"] = shown_words(tokens(src.quran.text([ref])[ref]), c.positions)
            except Exception as e2:     # noqa: BLE001
                print(f"warning: word of {day}: {type(e2).__name__}", file=sys.stderr)
        rows.append(row)
    return {"enabled": bool(conf.get("enabled")), "time_utc": str(conf.get("time_utc", "")),
            "days": rows, "gloss_source": cfg.content["glosses"].get("label", "")}


def _word(cfg: Config, src: Any, c: Any, max_chars: int) -> dict[str, str]:
    from quran_reels.images import candidates as cand_mod
    from quran_reels.models import AyahRef
    from quran_reels.sources.tafsir_app import parse_entries

    ref = AyahRef(c.surah, c.ayah)
    raw = src.glosses.raw([ref], src.quran.global_index).get(ref, "")
    entries = parse_entries(raw, ref, cfg.content["glosses"]["edition"])
    if c.entry >= len(entries):
        raise ValueError("entry missing")
    content = cand_mod.word_content(src, c, entries[c.entry].text, max_chars)
    return {"word": content.word, "gloss": content.gloss}

