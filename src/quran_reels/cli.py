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

    publish = sub.add_parser("publish", help="publish an already rendered reel")
    publish.add_argument("video")

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

        key = args.passage.strip()
        if key.isdigit():
            from quran_reels.selector.plan import plan_surah

            plan = plan_surah(cfg, int(key))
            if len(plan) > 1:
                print(f"surah {key} is too long for one video ({sum(p.seconds for p in plan):.0f} s)."
                      f" Its passages (quran-reels passages {key}):", file=sys.stderr)
                for p in plan:
                    print(f"  quran-reels render {p.key:<10} # {p.seconds:.0f} s", file=sys.stderr)
                return 2
            key = plan[0].key
        result = render_passage(cfg, key)
        print(result.video)
        return 0

    print(f"'{args.command}' is not implemented yet", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
