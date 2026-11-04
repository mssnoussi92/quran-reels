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

    render = sub.add_parser("render", help="build the MP4 for a passage")
    render.add_argument("passage", help="e.g. 93:1-3")

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

    if args.command == "render":
        from quran_reels.render import render_passage

        result = render_passage(cfg, args.passage)
        print(result.video)
        return 0

    print(f"'{args.command}' is not implemented yet", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
