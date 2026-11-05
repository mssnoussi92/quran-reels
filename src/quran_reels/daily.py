"""quran-reels daily: publish what the schedule says is due now, and record it.

The daily workflow calls this several times around each slot, because GitHub's schedule is
in UTC (summer time moves the slots by an hour) and often runs late. Each run:
  - takes the slots whose window contains now (config/schedule.yaml);
  - a slot not started today gets the next passage of its queue (Al-Kahf on Fridays);
  - a slot started today retries only the platforms that failed, with the same passage;
  - saves the state after each slot (published.json, kept on the `state` branch).

A passage counts as published, and its queue moves on, once one platform has it: a failed
platform is retried while the slot's window lasts, never with another passage. A slot blocked
by Meta's copyright check is not retried: the same recitation would be refused again. Its
passage stays first in its queue until the recitation changes.

A reel claimed after publication (Meta mutes or blocks it: publish.after_check right away,
`recheck` at the next runs, for RECHECK_DAYS) is taken down from Facebook and Instagram, its
slot is marked `claimed` and not retried, its passage goes back to the head of its queue, and
its reciter joins the state's `claimed` list: the rotation never picks it again.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from quran_reels import publish as publish_mod
from quran_reels.config import Config
from quran_reels.models import PublishStatus
from quran_reels.selector.calendar import (
    OK_STATUSES,
    Item,
    Schedule,
    Series,
    Slot,
    State,
    item_by_id,
    load_schedule,
    load_series,
    mark_done,
    next_item,
)

RECHECK_DAYS = 2          # reels read again at each run for this long after publication


@dataclass
class Pending:
    day: date
    slot: Slot
    queue: str
    item: Item
    platforms: list[str]          # still to do for this slot
    retry: bool                   # the slot was started by an earlier run


def pending(sched: Schedule, series: dict[str, Series], state: State, now: datetime,
            platforms: list[str]) -> list[Pending]:
    """What this run has to do. Picks next passages on a copy: the state is not changed."""
    sim = state.copy()
    out = []
    for day, slot in sched.due(now):
        record = sim.slot(day, slot.name)
        if record and (record.get("claimed") or any(
                r.get("status") == PublishStatus.BLOCKED.value
                for r in record["results"].values())):
            print(f"{day} {slot.name}: blocked or claimed by the rights check, not retried "
                  f"({record['passage']})", file=sys.stderr)
            continue
        if record:
            done = {p for p, r in record["results"].items() if r.get("status") in OK_STATUSES}
            todo = [p for p in platforms if p not in done]
            if todo:
                item = item_by_id(sched, series, record["queue"], record["item"])
                out.append(Pending(day, slot, record["queue"], item, todo, retry=True))
            continue
        got = next_item(sched, series, sim, sched.queue_for(slot, day))
        if got is None:
            print(f"warning: {day} {slot.name}: queue {sched.queue_for(slot, day)} has nothing "
                  "left to publish (add a series to config/schedule.yaml)", file=sys.stderr)
            continue
        queue, item = got
        mark_done(sim, queue, item)
        out.append(Pending(day, slot, queue, item, list(platforms), retry=False))
    return out


def _output(name: str, value: str) -> None:
    """A step output on GitHub Actions (steps.<id>.outputs.<name>)."""
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")


def run(cfg: Config, state_path: Path, now: datetime | None = None, dry_run: bool = False,
        check: bool = False, force: bool = False, report: Path | None = None) -> int:
    """check: only say whether something is due (output `due`), for the workflow to skip
    installing ffmpeg and Chromium. force: run even if schedule.enabled is false.
    report: JSON of what this run published, for `quran-reels notify` (written even when the
    run fails half way, with the error)."""
    now = now or datetime.now(UTC)
    series = load_series(cfg)
    sched = load_schedule(cfg, series)
    if not sched.enabled and not force:
        print("schedule disabled (config/schedule.yaml: enabled: false): nothing published")
        _output("due", "false")
        return 0
    state = State.load(state_path)
    platforms = publish_mod.platforms_for(cfg, None)
    if dry_run:     # TikTok's only test mode is a real draft in the owner's inbox
        platforms = [x for x in platforms if x != "tiktok"]
    todo = pending(sched, series, state, now, platforms)
    local = now.astimezone(sched.tz)
    if not todo:
        print(f"{local:%Y-%m-%d %H:%M} {sched.tz.key}: nothing due")
    for p in todo:
        what = "retry " + "+".join(p.platforms) if p.retry else "+".join(p.platforms)
        print(f"{p.day} {p.slot.name} ({p.slot.at:%H:%M}): {p.queue} → {p.item.id} [{what}]")
    _output("due", "true" if todo else "false")
    if check or not todo:
        return 0

    log: dict = {"dry_run": dry_run, "items": [], "errors": []}
    try:
        return _publish(cfg, sched, series, state, state_path, todo, platforms, dry_run, log)
    except BaseException as e:      # SystemExit from the Meta token check included
        log["errors"].append(f"{type(e).__name__}: {e}" if not isinstance(e, SystemExit)
                             else str(e))
        raise
    finally:
        if report:
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")


def claim(state: State, key: str, record: dict, reason: str) -> None:
    """A slot whose reel Meta muted or blocked: not retried, passage back at the head of its
    queue, reciter never chosen again."""
    record["claimed"] = reason
    done = state.queue(record["queue"])["done"]
    if record["item"] in done:
        done.remove(record["item"])
    if record.get("reciter"):
        state.data.setdefault("claimed", {}).setdefault(record["reciter"], {
            "slot": key, "passage": record["passage"], "reason": reason,
            "at": datetime.now(UTC).isoformat(timespec="seconds")})


def recheck(cfg: Config, sched: Schedule, state: State, publishers: dict, now: datetime,
            log: dict) -> bool:
    """Read Meta's check again on the reels of the last RECHECK_DAYS days (a claim can come
    after the check that follows publication); take a claimed one down. True if one was."""
    found = False
    times = {sl.name: f"{sl.at:%H:%M}" for sl in sched.slots}
    for key, record in sorted(state.data["slots"].items()):
        day_s, slot = key.split("/")
        if record.get("claimed") or now.date() - date.fromisoformat(day_s) > timedelta(
                days=RECHECK_DAYS):
            continue
        checks = {}
        for name, r in record["results"].items():
            if name in publishers and r.get("status") == PublishStatus.PUBLISHED.value \
                    and r.get("id"):
                checks[name] = publishers[name].rights_after(r["id"])
        claimed = {n: c for n, c in checks.items() if c.restricted}
        if not claimed:
            continue
        reason = "; ".join(f"{n} : {c.describe()}" for n, c in claimed.items())
        print(f"{key}: claimed after publication: {reason}", file=sys.stderr)
        publish_mod.take_down(publishers, record["results"], reason)
        claim(state, key, record, reason)
        found = True
        log["items"].append({
            "key": key, "day": day_s, "time": times.get(slot, ""), "passage": record["passage"],
            "label": "", "reciter": record.get("reciter"), "retry": True, "caption": "",
            "results": {n: {"status": r.get("status"), "url": r.get("url"),
                            "error": r.get("error")} for n, r in record["results"].items()}})
    return found


def copy_text(cfg: Config, video: Path) -> str:
    """The caption to paste on TikTok's draft: its hashtag limit (platforms.tiktok)."""
    try:
        reel = publish_mod.load_reel(video)
    except (OSError, KeyError, ValueError):
        return ""
    return reel.text(publish_mod.max_hashtags(cfg, "tiktok"))


def _publish(cfg: Config, sched: Schedule, series: dict[str, Series], state: State,
             state_path: Path, todo: list[Pending], platforms: list[str], dry_run: bool,
             log: dict) -> int:
    from quran_reels import reciters as rec
    from quran_reels.render import render_passage

    order = {s.name: i for i, s in enumerate(sorted(sched.slots, key=lambda s: s.at))}
    meta = [x for x in platforms if x in publish_mod.META]
    checked = publish_mod.meta_check(cfg, meta) if meta else None     # before rendering
    failed = False
    if checked and not dry_run:
        graph, env, _ = checked
        try:
            failed |= recheck(cfg, sched, state,
                              publish_mod.meta_publishers(cfg, graph, env, meta),
                              datetime.now(UTC), log)
        except Exception as e:      # noqa: BLE001  (never in the way of the slots due)
            print(f"warning: recheck of the last reels failed: {type(e).__name__}: {e}",
                  file=sys.stderr)
        state.save(state_path)
    for p in todo:
        if (state.slot(p.day, p.slot.name) or {}).get("claimed"):
            continue        # recheck just took this slot down: not retried
        if not p.retry:     # pick again on the real state: a repeating queue may start over
            got = next_item(sched, series, state, sched.queue_for(p.slot, p.day))
            if got is None:
                continue
            p.queue, p.item = got
        pcfg, reciter = cfg, None
        if rec.rotation(cfg):       # the reciter is chosen per passage (reciters.py)
            before = state.slot(p.day, p.slot.name) or {}
            if p.retry and before.get("reciter"):
                reciter = before["reciter"]          # a retry posts the same recitation
            else:
                reciter, opts = rec.choose(cfg, p.item.key, rec.recent_reciters(state, order),
                                           rec.claimed_reciters(state))
                print(f"{p.item.key}: {reciter} (" + ", ".join(
                    f"{o.name} {o.seconds} s" if o.seconds is not None else f"{o.name}: {o.why}"
                    for o in opts) + ")")
            pcfg = rec.with_reciter(cfg, reciter)
        video = render_passage(pcfg, p.item.key, p.item.label_ar, p.item.label_en,
                               p.item.series.hashtags).video
        results = publish_mod.publish_reel(pcfg, video, p.platforms, dry_run, checked)
        failed |= any(r.status in (PublishStatus.FAILED, PublishStatus.BLOCKED,
                                   PublishStatus.REMOVED) for r in results)
        caption = copy_text(cfg, video)
        log["items"].append({
            "key": f"{p.day.isoformat()}/{p.slot.name}", "day": p.day.isoformat(),
            "time": f"{p.slot.at:%H:%M}", "passage": p.item.key, "label": p.item.label_en,
            "reciter": reciter,
            "retry": p.retry, "caption": caption,
            "results": {r.platform: {"status": r.status.value, "url": r.url, "error": r.error}
                        for r in results}})
        if caption:
            publish_mod._summary("**Légende à coller sur le brouillon TikTok**\n\n"
                                 f"```text\n{caption.strip()}\n```")
        if dry_run:
            continue
        record = state.slot(p.day, p.slot.name) or {
            "queue": p.queue, "item": p.item.id, "passage": p.item.key, "results": {}}
        if reciter:
            record["reciter"] = reciter
        for r in results:
            record["results"][r.platform] = {
                "status": r.status.value, "id": r.remote_id, "url": r.url, "error": r.error,
                "at": datetime.now(UTC).isoformat(timespec="seconds")}
        state.set_slot(p.day, p.slot.name, record)
        claimed = [r.rights_after["summary"] for r in results
                   if r.rights_after and r.status == PublishStatus.REMOVED]
        if claimed or any(r.status == PublishStatus.REMOVED for r in results):
            claim(state, f"{p.day.isoformat()}/{p.slot.name}", record,
                  "; ".join(claimed) or "retiré après publication")
        elif any(r["status"] in OK_STATUSES for r in record["results"].values()):
            mark_done(state, p.queue, p.item)
        state.save(state_path)
    return 1 if failed else 0
