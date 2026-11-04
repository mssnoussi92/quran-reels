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

    publish = sub.add_parser("publish", help="publish a reel on Facebook and Instagram")
    publish.add_argument("target", help="out/093_001-011.mp4, or a passage/surah to render first")
    publish.add_argument("--dry-run", action="store_true",
                         help="stop before publishing: Facebook draft, Instagram container")
    publish.add_argument("--platform", action="append", choices=["facebook", "instagram"],
                         help="repeat for several; default: enabled platforms in project.yaml")

    check = sub.add_parser("meta-check", help="check the Meta Page token (fails < 14 days)")
    check.add_argument("--platform", action="append", choices=["facebook", "instagram"])

    sub.add_parser("run", help="select today's passage, render and publish")

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
        checked = publish_mod.meta_check(cfg, platforms)    # before rendering: fail fast
        video = Path(args.target)
        if video.suffix != ".mp4":
            from quran_reels.render import render_passage
            from quran_reels.selector.plan import resolve

            video = render_passage(cfg, resolve(cfg, args.target)).video
        elif not video.is_file():
            raise SystemExit(f"{video}: no such file")
        return publish_mod.run(cfg, video, platforms, dry_run=args.dry_run, checked=checked)

    print(f"'{args.command}' is not implemented yet", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
