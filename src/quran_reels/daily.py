"""quran-reels daily: publish what the schedule says is due now, and record it.

The daily workflow calls this several times around each slot, because GitHub's schedule is
in UTC (summer time moves the slots by an hour) and often runs late. Each run:
  - takes the slots whose window contains now (config/schedule.yaml);
  - a slot not started today gets the next passage of its queue (Al-Kahf on Fridays);
  - a slot started today retries only the platforms that failed, with the same passage;
  - writes the state as soon as a slot's reel has been sent (published.json, kept on the
    `state` branch): before another try, before the YouTube version, so that a run stopped
    half way has still said what is out and nothing is published twice;
  - tries once more, in the same run, a platform that did not get the reel at all
    (platforms.retry, publish.to_retry): Instagram refusing the upload, TikTok's failing.

A passage counts as published, and its queue moves on, once one platform has it: a failed
platform is retried while the slot's window lasts, never with another passage. A slot blocked
by Meta's copyright check is not retried: the same recitation would be refused again. Its
passage stays first in its queue until the recitation changes.

A reel claimed after publication (Meta mutes or blocks it: publish.after_check right away,
`recheck` at the next runs, for RECHECK_DAYS) is taken down from Facebook and Instagram, its
slot is marked `claimed` and not retried, its passage goes back to the head of its queue, and
its reciter joins the state's `claimed` list: the rotation never picks it again.

A reciter whose basmala the recording itself contradicts (sources/surah_audio.py: CutError,
raised by the render) is passed over for that passage: the next one of the rotation takes the
slot, and nothing with that cut is published.

YouTube (uploaded by hand) has its own reciter, always the same (platforms.youtube.reciter:
Tawfiq As-Sayegh): when the rotation picks another one, the run renders the passage again by
him into out/youtube/ for the owner to upload, and the captions issue says so. A passage he is
not ready for gets nothing for YouTube that day. Without that setting, YouTube takes the reel
as it is unless its Content ID claims the reciter (platforms.youtube.exclude_reciters).
"""

from __future__ import annotations

import dataclasses
import json
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from quran_reels import publish as publish_mod
from quran_reels.config import Config
from quran_reels.models import PublishResult, PublishStatus
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
    missed_slots,
    next_item,
)

RECHECK_DAYS = 2          # reels read again at each run for this long after publication
SECRETS_DAYS = 14         # GH_SECRETS_TOKEN: the owner is told this long before it expires
YOUTUBE_DIR = "youtube"    # out/youtube/: the version for YouTube, when it differs


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
        if record and record.get("by_hand"):
            continue        # published by hand (state record): a platform left out is left out
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
        check: bool = False, force: bool = False, report: Path | None = None,
        sleep: Callable[[float], None] = time.sleep, watch: bool | None = None) -> int:
    """check: only say whether something is due (output `due`), for the workflow to skip
    installing ffmpeg and Chromium. force: run even if schedule.enabled is false or the day is
    one of the pause (schedule.yaml `pause`).
    report: JSON of what this run published, for `quran-reels notify` (written even when the
    run fails half way, with the error). sleep: the wait before another try (tests).
    watch: look for slots nobody tried (output `missed`, state `missed`); by default on a real
    run only, at the real time (not a dry run, not a forced or simulated one)."""
    if watch is None:
        watch = now is None and not dry_run and not force
    now = now or datetime.now(UTC)
    series = load_series(cfg)
    sched = load_schedule(cfg, series)
    if not sched.enabled and not force:
        print("schedule disabled (config/schedule.yaml: enabled: false): nothing published")
        _output("due", "false")
        return 0
    state = State.load(state_path)
    missed = missed_slots(sched, state, now) if watch else []
    if missed:      # told once: written in the state, which the workflow saves
        print("no run took " + ", ".join(missed) + ": nothing was published for "
              + ("it" if len(missed) == 1 else "them"), file=sys.stderr)
        for key in missed:
            state.data.setdefault("missed", {})[key] = {
                "noticed": datetime.now(UTC).isoformat(timespec="seconds")}
        state.save(state_path)
    _output("missed", ",".join(missed))
    platforms = publish_mod.platforms_for(cfg, None)
    if dry_run:     # TikTok's only test mode is a real draft in the owner's inbox
        platforms = [x for x in platforms if x != "tiktok"]
    todo = pending(sched, series, state, now, platforms)
    local = now.astimezone(sched.tz)
    if not force:       # a day of the pause: its slots wait, their passages stay first in line
        for p in todo:
            if sched.paused(p.day):
                print(f"{p.day} {p.slot.name}: paused ({sched.pause}, config/schedule.yaml): "
                      "nothing published")
        todo = [p for p in todo if not sched.paused(p.day)]
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
        return _publish(cfg, sched, series, state, state_path, todo, platforms, dry_run, log,
                        now, sleep)
    except BaseException as e:      # SystemExit from the Meta token check included
        log["errors"].append(f"{type(e).__name__}: {e}" if not isinstance(e, SystemExit)
                             else str(e))
        raise
    finally:
        if report:
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")


def secrets_note(state: State, today: date, expiry: date | None) -> str | None:
    """What to tell the owner when GH_SECRETS_TOKEN is about to expire, once per expiry date
    (state `told`). Without that token, TikTok's next refresh token cannot be saved."""
    if expiry is None:
        return None
    left = (expiry - today).days
    print(f"GH_SECRETS_TOKEN: valid until {expiry.isoformat()} ({left} days)", file=sys.stderr)
    told = state.data.setdefault("told", {})
    if left > SECRETS_DAYS or told.get("GH_SECRETS_TOKEN") == expiry.isoformat():
        return None
    told["GH_SECRETS_TOKEN"] = expiry.isoformat()
    when = f"expire le {expiry.isoformat()} (dans {left} jours)" if left >= 0 else \
        f"a expiré le {expiry.isoformat()}"
    return (f"🔑 **Le jeton GitHub `GH_SECRETS_TOKEN` {when}.** Sans lui, le prochain refresh "
            "token de TikTok ne peut plus être enregistré : les brouillons TikTok s'arrêtent "
            "et il faut se reconnecter (workflow tiktok-auth). En créer un nouveau et "
            "remplacer le secret : docs/plateformes.md, « GH_SECRETS_TOKEN » (2 minutes). "
            "Facebook et Instagram ne sont pas concernés.")


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
    return reel.for_platform("tiktok").text(publish_mod.max_hashtags(cfg, "tiktok"))


def record_slot(state: State, p: Pending, results: list[PublishResult],
                reciter: str | None) -> dict:
    """Write what the platforms answered for a slot in the state, and what follows from it: a
    reel taken down is claimed (passage back at the head of its queue), a reel that one
    platform has moves its queue on. Called again with the answers of another try."""
    slot = state.slot(p.day, p.slot.name) or {
        "queue": p.queue, "item": p.item.id, "passage": p.item.key, "results": {}}
    if reciter:
        slot["reciter"] = reciter
    for r in results:
        slot["results"][r.platform] = {
            "status": r.status.value, "id": r.remote_id, "url": r.url, "error": r.error,
            "at": datetime.now(UTC).isoformat(timespec="seconds")}
    state.set_slot(p.day, p.slot.name, slot)
    claimed = [r.rights_after["summary"] for r in results
               if r.rights_after and r.status == PublishStatus.REMOVED]
    if claimed or any(r.status == PublishStatus.REMOVED for r in results):
        claim(state, f"{p.day.isoformat()}/{p.slot.name}", slot,
              "; ".join(claimed) or "retiré après publication")
    elif any(r["status"] in OK_STATUSES for r in slot["results"].values()):
        mark_done(state, p.queue, p.item)
    return slot


def again(cfg: Config, state: State, state_path: Path, p: Pending, video: Path,
          results: list[PublishResult], reciter: str | None, checked: tuple | None,
          sleep: Callable[[float], None]) -> list[PublishResult]:
    """The platforms that did not get the reel, tried once more in this run, alone, as a later
    run would (their own upload and rights check), after platforms.retry.wait seconds. The
    first answers are in the state already; each new one is written at once."""
    times, pause = publish_mod.retry_settings(cfg)
    for attempt in range(1, times + 1):
        todo = publish_mod.to_retry(results)
        if not todo:
            break
        print(f"{p.item.key}: {'+'.join(todo)} did not get the reel, tried again in "
              f"{pause:.0f} s ({attempt}/{times})", file=sys.stderr)
        sleep(pause)
        new = {r.platform: r
               for r in publish_mod.publish_reel(cfg, video, todo, False, checked)}
        results = [new.get(r.platform, r) for r in results]
        record_slot(state, p, list(new.values()), reciter)
        state.save(state_path)
    return results


def youtube_version(cfg: Config, p: Pending, reciter: str | None,
                    claimed: set[str]) -> dict | None:
    """The reel again for YouTube when it does not take `reciter` (reciters.other_for): by
    its own reciter (platforms.youtube.reciter, `always` in the answer), or else, when its
    Content ID claims `reciter` (a Short over 1 min with a claim is blocked worldwide), by a
    ready reciter it does not claim; in out/youtube/. None when the same video goes to
    YouTube. `reciter` None in the answer: nothing for YouTube (`error`: why), the reel of
    the day must not go there. Never fails the run."""
    from quran_reels import reciters as rec
    from quran_reels.render import render_passage

    if cfg is None or not reciter:
        return None
    yt = (cfg.project.get("platforms") or {}).get("youtube") or {}
    if yt.get("mode") != "manual" or rec.allowed_on(cfg, "youtube", reciter):
        return None
    names = cfg.content.get("reciters") or {}
    fixed = rec.fixed_on(cfg, "youtube")
    rule = {"always": True, "wanted": (names.get(fixed) or {}).get("label", fixed)} \
        if fixed else {}
    try:
        opt = rec.other_for(cfg, "youtube", p.item.key, reciter, claimed)
        if opt.seconds is None:
            print(f"warning: {p.item.key}: no YouTube version ({opt.name or 'no reciter'}: "
                  f"{opt.why})", file=sys.stderr)
            return {"reciter": None, "error": rec.why(opt), **rule}
        other = opt.name
        ycfg = dataclasses.replace(rec.with_reciter(cfg, other), out_dir=cfg.out / YOUTUBE_DIR)
        video = render_passage(ycfg, p.item.key, p.item.label_ar, p.item.label_en,
                               p.item.series.hashtags, variants=False).video
        caption = publish_mod.load_reel(video).text(publish_mod.max_hashtags(cfg, "youtube"))
        print(f"{p.item.key}: YouTube version by {other} ("
              + ("always there" if fixed else f"{reciter} is claimed there")
              + f"): out/{YOUTUBE_DIR}/{video.name}")
        return {"reciter": other, "video": f"{YOUTUBE_DIR}/{video.name}", "caption": caption,
                "label": (names.get(other) or {}).get("label", other),
                "instead_of": (names.get(reciter) or {}).get("label", reciter),
                **({"always": True} if fixed else {})}
    except (Exception, SystemExit) as e:     # noqa: BLE001  (the reel is out already)
        print(f"warning: YouTube version of {p.item.key}: {type(e).__name__}: {e}",
              file=sys.stderr)
        error = f"découpe refusée : {e}" if type(e).__name__ == "CutError" else \
            f"{type(e).__name__}: {e}"
        return {"reciter": None, "error": error, **rule}


def _publish(cfg: Config, sched: Schedule, series: dict[str, Series], state: State,
             state_path: Path, todo: list[Pending], platforms: list[str], dry_run: bool,
             log: dict, now: datetime, sleep: Callable[[float], None] = time.sleep) -> int:
    from quran_reels import reciters as rec
    from quran_reels.gh_secrets import token_expiry
    from quran_reels.render import render_passage
    from quran_reels.sources.surah_audio import CutError

    order = {s.name: i for i, s in enumerate(sorted(sched.slots, key=lambda s: s.at))}
    meta = [x for x in platforms if x in publish_mod.META]
    checked = publish_mod.meta_check(cfg, meta) if meta else None     # before rendering
    failed = False
    if not dry_run and "tiktok" in platforms:
        note = secrets_note(state, now.date(), token_expiry())
        if note:
            log.setdefault("notes", []).append(note)
            state.save(state_path)
    if checked and not dry_run and publish_mod.after_timeout(cfg) > 0:
        graph, env, _ = checked
        try:
            failed |= recheck(cfg, sched, state,
                              publish_mod.meta_publishers(cfg, graph, env, meta), now, log)
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
        refused: set[str] = set()   # reciters whose cut of this passage the recording denies
        while True:
            same = False
            if rec.rotation(cfg):   # the reciter is chosen per passage (reciters.py)
                before = state.slot(p.day, p.slot.name) or {}
                same = bool(p.retry and before.get("reciter"))
                if same:
                    reciter = before["reciter"]      # a retry posts the same recitation
                else:
                    reciter, opts = rec.choose(
                        cfg, p.item.key, rec.recent_reciters(state, order),
                        rec.claimed_reciters(state) | refused)
                    print(f"{p.item.key}: {reciter} (" + ", ".join(
                        f"{o.name}: cut refused" if o.name in refused else
                        f"{o.name} {o.seconds} s" if o.seconds is not None else
                        f"{o.name}: {o.why}" for o in opts) + ")")
                pcfg = rec.with_reciter(cfg, reciter)
            try:
                video = render_passage(pcfg, p.item.key, p.item.label_ar, p.item.label_en,
                                       p.item.series.hashtags).video
                break
            except CutError as e:
                # A basmala checked by recognition that the recording itself contradicts
                # (sources/surah_audio.py): never published; the next reciter takes the slot.
                if same or not reciter or reciter in refused:
                    raise
                print(f"warning: {e}; another reciter is chosen", file=sys.stderr)
                refused.add(reciter)
        results = publish_mod.publish_reel(pcfg, video, p.platforms, dry_run, checked)
        if not dry_run:
            # Written at once: a run stopped after this (cancelled, timed out, a crash in the
            # YouTube version) has still told the state what is out.
            record_slot(state, p, results, reciter)
            state.save(state_path)
            results = again(pcfg, state, state_path, p, video, results, reciter, checked, sleep)
        failed |= any(r.status in (PublishStatus.FAILED, PublishStatus.BLOCKED,
                                   PublishStatus.REMOVED) for r in results)
        caption = copy_text(cfg, video)
        youtube = youtube_version(cfg, p, reciter, rec.claimed_reciters(state))
        log["items"].append({
            "key": f"{p.day.isoformat()}/{p.slot.name}", "day": p.day.isoformat(),
            "time": f"{p.slot.at:%H:%M}", "passage": p.item.key, "label": p.item.label_en,
            "reciter": reciter,
            "retry": p.retry, "caption": caption,
            "results": {r.platform: {"status": r.status.value, "url": r.url, "error": r.error}
                        for r in results},
            **({"youtube": youtube} if youtube else {})})
        if caption:
            publish_mod._summary("**Légende à coller sur le brouillon TikTok**\n\n"
                                 f"```text\n{caption.strip()}\n```")
        if not dry_run and youtube:
            # With a reciter: the video for YouTube. Without: none (`error`), not this reel;
            # never written over the version an earlier run of the slot made.
            record = state.slot(p.day, p.slot.name)
            if youtube.get("reciter"):
                record["youtube"] = {"reciter": youtube["reciter"], "video": youtube["video"]}
            elif not (record.get("youtube") or {}).get("reciter"):
                record["youtube"] = {"reciter": None, "error": youtube.get("error", "")}
            state.save(state_path)
    return 1 if failed else 0
