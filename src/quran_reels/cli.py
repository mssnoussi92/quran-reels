"""Command line entry point: quran-reels ingest|render|publish|run."""

from __future__ import annotations

import argparse
import sys

from quran_reels import config


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

    if args.command == "render":
        from quran_reels.render import render_passage
        from quran_reels.selector.plan import resolve

        print(render_passage(cfg, resolve(cfg, args.passage)).video)
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

            video = render_passage(cfg, resolve(cfg, args.target)).video
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
        for day, slot, queue, item in preview(sched, series, state, start, args.days):
            what = f"{item.key:<10} {item.label_en or item.series.id}" if item else "— nothing left"
            print(f"{day:%a %Y-%m-%d} {slot.at:%H:%M} {queue:<8} {what}")
        return 0

    if args.command in ("daily", "run"):
        from datetime import datetime
        from pathlib import Path

        from quran_reels import daily

        now = datetime.fromisoformat(args.now) if args.now else None
        return daily.run(cfg, Path(args.state), now=now, dry_run=args.dry_run,
                         check=args.check, force=args.force,
                         report=cfg.out / "daily-report.json")

    if args.command == "notify":
        from pathlib import Path

        from quran_reels import notify

        report = Path(args.report) if args.report else cfg.out / "daily-report.json"
        return notify.run(report, args.outcome, args.run_url, args.owner)

    print(f"'{args.command}' is not implemented yet", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
