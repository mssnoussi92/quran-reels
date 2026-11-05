"""Command line entry point: quran-reels ingest|render|publish|run."""

from __future__ import annotations

import argparse
import sys

from quran_reels import config


def _reciter_for(cfg, key: str):
    """$QURAN_REELS_RECITER, or else the reciter the rotation chooses for this passage."""
    import os

    from quran_reels import reciters as rec
    from quran_reels.config import RECITER_ENV

    if os.environ.get(RECITER_ENV) or not rec.rotation(cfg):
        return cfg
    name, _ = rec.choose(cfg, key, [])
    print(f"{key}: {name} (content.rotation)", file=sys.stderr)
    return rec.with_reciter(cfg, name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="quran-reels")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="download the datasets into .cache/")
    ingest.add_argument("--passage", help="also fetch glosses and audio for e.g. 93:1-3")
    ingest.add_argument("--all-glosses", action="store_true",
                        help="download every gloss entry (about 2,400 requests, resumable)")
    ingest.add_argument("--refresh", action="store_true", help="download again what is cached")

    render = sub.add_parser("render", help="build the MP4 for a passage or a short surah")
    render.add_argument("passage", help="e.g. 2:1-5, or 93 for a whole surah that fits")

    passages = sub.add_parser("passages", help="split a surah into passages of about a minute")
    passages.add_argument("surah", type=int)

    split = sub.add_parser("split", help="reciter with one file per surah: find where each "
                                         "ayah starts (speech recognition), check, write "
                                         "config/splits/ (needs the asr extra)")
    split.add_argument("passages", nargs="*", help="surahs (114) or passages (2:255-257): "
                                                   "only their ayahs are checked")
    split.add_argument("--force", action="store_true", help="check again what is checked")
    split.add_argument("--upcoming", type=int, metavar="DAYS",
                       help="the passages of the next DAYS days, for every reciter of "
                            "content.rotation (the prepare workflow)")
    split.add_argument("--state", default="state/published.json")

    publish = sub.add_parser("publish", help="publish a reel (Facebook, Instagram, TikTok draft)")
    publish.add_argument("target", help="out/093_001-011.mp4, or a passage/surah to render first")
    publish.add_argument("--dry-run", action="store_true",
                         help="stop before publishing: Facebook draft, Instagram container")
    publish.add_argument("--platform", action="append",
                         choices=["facebook", "instagram", "tiktok"],
                         help="repeat for several; default: enabled platforms in project.yaml")

    check = sub.add_parser("meta-check", help="check the Meta Page token (fails < 14 days)")
    check.add_argument("--platform", action="append", choices=["facebook", "instagram"])

    auth_url = sub.add_parser("tiktok-auth-url",
                              help="print the TikTok sign-in URL (needs TIKTOK_CLIENT_KEY)")
    auth_url.add_argument("--state", default="quran-reels")
    auth = sub.add_parser("tiktok-auth", help="exchange the TikTok code, save the refresh token")
    auth.add_argument("--code", help="default: $TIKTOK_AUTH_CODE or the workflow input")

    plan = sub.add_parser("plan", help="split every surah; --write freezes config/plan.yaml")
    plan.add_argument("--write", action="store_true")

    sub.add_parser("series-check", help="check config/series: whole sentences, duration")

    cal = sub.add_parser("calendar", help="what the next days publish (nothing is published)")
    cal.add_argument("--days", type=int, default=14)
    cal.add_argument("--state", default="state/published.json")
    cal.add_argument("--from", dest="start", help="first day, YYYY-MM-DD (default: today)")

    for name, text in (("daily", "publish the slots due now (config/schedule.yaml)"),
                       ("run", "same as daily")):
        d = sub.add_parser(name, help=text)
        d.add_argument("--state", default="state/published.json")
        d.add_argument("--now", help="ISO date-time instead of now, for tests")
        d.add_argument("--dry-run", action="store_true", help="drafts only, state unchanged")
        d.add_argument("--check", action="store_true", help="only say whether a slot is due")
        d.add_argument("--force", action="store_true", help="even if schedule.enabled is false")

    img = sub.add_parser("images", help="daily image posts (docs/images.md)")
    img_sub = img.add_subparsers(dest="images_command", required=True)
    b = img_sub.add_parser("build", help="rules 1-4 → config/image-candidates.yaml")
    b.add_argument("--surah", type=int, action="append", help="only this surah (repeatable)")
    for name, text in (("next", "what the next days post (nothing is published)"),
                       ("render", "render the next days' posts into out/images/ (preview)")):
        n = img_sub.add_parser(name, help=text)
        n.add_argument("--days", type=int, default=7)
        n.add_argument("--kind", default="word", choices=["word", "ayah"])
        n.add_argument("--from", dest="start", help="first day, YYYY-MM-DD (default: today)")
        n.add_argument("--state", default="state/images.json")
    r = img_sub.add_parser("run", help="post the image formats due now (config/images.yaml)")
    r.add_argument("--state", default="state/images.json")
    r.add_argument("--now", help="ISO date-time instead of now, for tests")
    r.add_argument("--dry-run", action="store_true", help="nothing posted, state unchanged")
    r.add_argument("--check", action="store_true", help="only say whether a post is due")

    bgs = sub.add_parser("backgrounds", help="background clips")
    bgs_sub = bgs.add_subparsers(dest="backgrounds_command", required=True)
    se = bgs_sub.add_parser("search", help="Pixabay candidates per theme (to check frame by frame)")
    se.add_argument("--theme", action="append", help="only this theme (repeatable)")
    se.add_argument("--per-theme", type=int, default=4)
    se.add_argument("--out", default="out/pixabay/candidates.json")

    note = sub.add_parser("notify", help="GitHub issues: failure alert, captions to copy")
    note.add_argument("--outcome", required=True, help="the job status: success or failure")
    note.add_argument("--run-url", required=True)
    note.add_argument("--owner", help="assigned to the failure issue (push notification)")
    note.add_argument("--report", help="default: out/daily-report.json")

    args = parser.parse_args(argv)
    cfg = config.load()

    if args.command == "ingest":
        from quran_reels import ingest as ingest_mod

        ingest_mod.run(cfg, passage=args.passage, all_glosses=args.all_glosses,
                       refresh=args.refresh)
        return 0

    if args.command == "passages":
        from quran_reels.selector.plan import plan_surah

        for p in plan_surah(cfg, args.surah):
            notes = [n for n, on in (("whole surah", p.whole_surah),
                                     ("cut inside a tafsir group", p.relaxed)) if on]
            print(f"{p.key:<10} {p.seconds:6.1f} s  {', '.join(notes)}".rstrip())
        return 0

    if args.command == "split" and args.upcoming:
        import os
        import subprocess
        from datetime import UTC, datetime
        from pathlib import Path

        from quran_reels import reciters as rec
        from quran_reels.config import RECITER_ENV
        from quran_reels.selector.calendar import State, load_schedule, load_series, preview

        series = load_series(cfg)
        sched = load_schedule(cfg, series)
        today = datetime.now(UTC).astimezone(sched.tz).date()
        keys = list(dict.fromkeys(item.key for _, _, _, item in preview(
            sched, series, State.load(Path(args.state)), today, args.upcoming) if item))
        print(f"next {args.upcoming} days: {' '.join(keys)}")
        for name in rec.rotation(cfg):      # one process per reciter: its own sources
            env = {**os.environ, RECITER_ENV: name}
            subprocess.run(["quran-reels", "split", *keys], env=env, check=False)
        missing = []                        # a reciter may fail; a passage must have one
        for key in keys:
            ready = [o.name for o in rec.options(cfg, key) if o.seconds is not None]
            print(f"{key:<12} {', '.join(ready) or 'NO RECITER READY'}")
            if not ready:
                missing.append(key)
        if missing:
            print(f"no reciter ready for {', '.join(missing)}: nothing would be published",
                  file=sys.stderr)
        return 1 if missing else 0

    if args.command == "split":
        from quran_reels.sources import Sources
        from quran_reels.sources.surah_audio import SurahFiles

        if not args.passages:
            raise SystemExit("quran-reels split: give passages, or --upcoming DAYS")
        src = Sources.from_config(cfg)
        if not isinstance(src.audio, SurahFiles):
            raise SystemExit(f"{cfg.content['reciter']['name']}: one file per ayah, nothing to "
                             f"split (choose one with QURAN_REELS_RECITER)")
        from quran_reels.models import parse_passage
        from quran_reels.sources.surah_audio import MIN_MATCH

        src.quran.ensure(src.translation_slug)
        failed = []
        for key in args.passages:
            surah, start, end = parse_passage(key if ":" in key else f"{key}:1-999")
            end = min(end, src.quran.chapters[surah]["verses_count"])
            check = {str(a) for a in range(start, end + 1)}
            if surah not in (1, 9):
                check.add("basmala")
            done = {k for k, v in src.audio.matches(surah).items() if v >= MIN_MATCH}
            if check <= done and not args.force:
                print(f"{key}: already checked ({src.audio.split_path(surah)})")
                continue
            try:
                src.audio.make_split(surah, None if ":" not in key else check)
            except SystemExit as e:
                print(e, file=sys.stderr)
                failed.append(key)
        if failed:
            print(f"not ready: {', '.join(failed)}", file=sys.stderr)
        return 1 if failed else 0

    if args.command == "render":
        from quran_reels.render import render_passage
        from quran_reels.selector.plan import resolve

        key = resolve(cfg, args.passage)
        print(render_passage(_reciter_for(cfg, key), key).video)
        return 0

    if args.command == "meta-check":
        from quran_reels.publish import meta_check, platforms_for

        _, _, report = meta_check(cfg, platforms_for(cfg, args.platform))
        print(report.summary())
        return 0

    if args.command == "publish":
        from pathlib import Path

        from quran_reels import publish as publish_mod

        platforms = publish_mod.platforms_for(cfg, args.platform)
        if not platforms:
            raise SystemExit("no platform to publish to (see platforms in config/project.yaml)")
        meta = [p for p in platforms if p in publish_mod.META]
        checked = publish_mod.meta_check(cfg, meta) if meta else None  # before rendering
        video = Path(args.target)
        if video.suffix != ".mp4":
            from quran_reels.render import render_passage
            from quran_reels.selector.plan import resolve

            key = resolve(cfg, args.target)
            cfg = _reciter_for(cfg, key)
            video = render_passage(cfg, key).video
        elif not video.is_file():
            raise SystemExit(f"{video}: no such file")
        return publish_mod.run(cfg, video, platforms, dry_run=args.dry_run, checked=checked)

    if args.command == "tiktok-auth-url":
        import os

        from quran_reels.publishers.tiktok import auth_url

        if not os.environ.get("TIKTOK_CLIENT_KEY"):
            raise SystemExit("TIKTOK_CLIENT_KEY not set; on a phone use docs/tiktok-login.html")
        conf = cfg.project["platforms"]["tiktok"]
        print(auth_url(os.environ["TIKTOK_CLIENT_KEY"], conf["redirect_uri"], args.state))
        return 0

    if args.command == "tiktok-auth":
        from quran_reels import publish as publish_mod

        return publish_mod.tiktok_auth(cfg, args.code)

    if args.command == "plan":
        from quran_reels.selector.calendar import write_plan
        from quran_reels.selector.plan import plan_surah

        if args.write:
            print(write_plan(cfg))
            return 0
        n = sum(len(plan_surah(cfg, s)) for s in range(1, 115))
        print(f"{n} passages (add --write to save config/plan.yaml)")
        return 0

    if args.command == "series-check":
        from quran_reels.selector.calendar import check_series, load_series

        bad = 0
        for c in check_series(cfg, load_series(cfg)):
            if c.problems:
                long_only = all(p.startswith("longer than max_seconds") for p in c.problems)
                bad += not long_only
                print(f"{'note' if long_only else 'ERROR'} {c.series}: {c.key} "
                      f"{'; '.join(c.problems)}")
        print("series OK" if not bad else f"{bad} passage(s) to fix")
        return 1 if bad else 0

    if args.command == "calendar":
        from datetime import UTC, date, datetime
        from pathlib import Path

        from quran_reels.selector.calendar import State, load_schedule, load_series, preview

        series = load_series(cfg)
        sched = load_schedule(cfg, series)
        state = State.load(Path(args.state))
        start = (date.fromisoformat(args.start) if args.start
                 else datetime.now(UTC).astimezone(sched.tz).date())
        if not sched.enabled:
            print("(schedule disabled: this is what it would publish)")
        from quran_reels import reciters as rec

        order = {s.name: i for i, s in enumerate(sorted(sched.slots, key=lambda s: s.at))}
        recent = rec.recent_reciters(state, order)
        for day, slot, queue, item in preview(sched, series, state, start, args.days):
            what = f"{item.key:<10} {item.label_en or item.series.id}" if item else "— nothing left"
            reciter = ""
            if item and rec.rotation(cfg):
                done = state.slot(day, slot.name) or {}
                try:
                    name = done.get("reciter") or rec.choose(cfg, item.key, recent)[0]
                    secs = rec.passage_seconds(rec.with_reciter(cfg, name), item.key).seconds
                    reciter = f"  [{name}, {secs} s]"
                    recent.append(name)
                except SystemExit:
                    reciter = "  [no reciter ready: quran-reels split " + item.key + "]"
            print(f"{day:%a %Y-%m-%d} {slot.at:%H:%M} {queue:<8} {what}{reciter}")
        return 0

    if args.command in ("daily", "run"):
        from datetime import datetime
        from pathlib import Path

        from quran_reels import daily

        now = datetime.fromisoformat(args.now) if args.now else None
        return daily.run(cfg, Path(args.state), now=now, dry_run=args.dry_run,
                         check=args.check, force=args.force,
                         report=cfg.out / "daily-report.json")

    if args.command == "images":
        return _images(cfg, args)

    if args.command == "backgrounds":
        import json
        from pathlib import Path

        from quran_reels.sources.pixabay import candidates

        found = candidates(cfg, args.theme, args.per_theme)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding="utf-8")
        for c in found:                 # one line each: public metadata only, never the key
            print(json.dumps(c, ensure_ascii=False))
        print(f"{len(found)} candidates → {out}", file=sys.stderr)
        return 0

    if args.command == "notify":
        from pathlib import Path

        from quran_reels import notify

        report = Path(args.report) if args.report else cfg.out / "daily-report.json"
        return notify.run(report, args.outcome, args.run_url, args.owner)

    print(f"'{args.command}' is not implemented yet", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())


def _images(cfg: config.Config, args) -> int:
    from datetime import UTC, date, datetime
    from pathlib import Path

    from quran_reels.images import candidates as cand_mod
    from quran_reels.images import daily as images_daily
    from quran_reels.images.select import ImageState, load_exclusions, upcoming
    from quran_reels.sources import Sources

    if args.images_command == "build":
        src = Sources.from_config(cfg)
        words_out, ayahs_out, left_out = cand_mod.build(cfg, src, surahs=args.surah)
        if args.surah:
            print(f"{len(words_out)} words, {len(ayahs_out)} ayahs (not written: --surah)")
            for c in words_out:
                print(c.row())
            return 0
        path = cand_mod.write(cfg, words_out, ayahs_out, left_out)
        print(f"{path}: {len(words_out)} words, {len(ayahs_out)} ayahs")
        for reason, n in sorted(left_out.items()):
            print(f"  left out, {reason}: {n}")
        return 0

    if args.images_command == "run":
        now = datetime.fromisoformat(args.now) if args.now else None
        return images_daily.run(cfg, Path(args.state), now=now, dry_run=args.dry_run,
                                check=args.check, report=cfg.out / "images-report.json")

    # next / render: the coming days, from the state, nothing published
    settings = images_daily.settings(cfg)
    conf = (settings.get("formats") or {}).get(args.kind) or {}
    start = date.fromisoformat(args.start) if args.start else datetime.now(UTC).date()
    picks = upcoming(cand_mod.load(cfg, args.kind), ImageState.load(Path(args.state)),
                     args.kind, conf.get("seed", "quran-words-daily"), load_exclusions(cfg),
                     start, args.days)
    if not conf.get("enabled"):
        print(f"({args.kind} is disabled in config/images.yaml: this is what it would post)")
    src = Sources.from_config(cfg)
    src.quran.ensure(src.translation_slug)
    if args.images_command == "next":
        from quran_reels.arabic import words
        from quran_reels.models import AyahRef
        from quran_reels.passage import shown_words

        for day, c in picks:
            name = src.quran.chapters[c.surah]["name_simple"]
            what = ""
            if c.kind == "word":
                ref = AyahRef(c.surah, c.ayah)
                what = shown_words(words(src.quran.text([ref])[ref]), c.positions)
            a, b = c.context
            shown = f"{c.surah}:{a}" if a == b else f"{c.surah}:{a}-{b}"
            print(f"{day:%a %Y-%m-%d}  {c.key:<9} {name:<16} {what:<18} image 2: {shown}")
        return 0

    from quran_reels.images.cards import CardRenderer

    with CardRenderer(cfg) as renderer:
        for day, c in picks:
            post = images_daily.render(cfg, src, args.kind, day, c, cfg.out / "images",
                                       renderer=renderer)
            print(f"{day}  {c.key}  {post.folder}")
    return 0

