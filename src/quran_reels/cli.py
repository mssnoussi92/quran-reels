"""Command line entry point: quran-reels render|publish|run."""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="quran-reels")
    sub = parser.add_subparsers(dest="command", required=True)

    render = sub.add_parser("render", help="build the MP4 for a passage")
    render.add_argument("passage", help="e.g. 93:1-3")

    publish = sub.add_parser("publish", help="publish an already rendered reel")
    publish.add_argument("video")

    sub.add_parser("run", help="select today's passage, render and publish")

    args = parser.parse_args(argv)
    raise SystemExit(f"'{args.command}' is not implemented yet (v1 in progress)")


if __name__ == "__main__":
    raise SystemExit(main())
