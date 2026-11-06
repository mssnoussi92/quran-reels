"""`quran-reels on-demand route|check|preview|publish|youtube|daily-files`: the steps of the
on-demand workflow. The event (issue, comment, inputs) is read from $GITHUB_EVENT_PATH, never
passed through the shell."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from quran_reels.config import Config


def add_parser(sub: argparse._SubParsersAction) -> None:
    od = sub.add_parser("on-demand", help="on-demand reels: preview, approval, publication "
                                          "(docs/on-demand.md)")
    od_sub = od.add_subparsers(dest="od_command", required=True)
    od_sub.add_parser("route", help="what this event asks (outputs command, issue, kind)")
    for name, text in (("check", "check the request (comments a refusal or a split)"),
                       ("preview", "render, upload the preview, comment it"),
                       ("publish", "publish the previewed reel after the owner's approval"),
                       ("youtube", "record a YouTube upload made by hand"),
                       ("words", "/mots: write the chosen word meanings in the request")):
        p = od_sub.add_parser(name, help=text)
        p.add_argument("--issue", type=int, required=True)
        p.add_argument("--state", default="state/published.json")
        if name in ("check", "preview"):
            p.add_argument("--split-seconds", type=float,
                           help="the recording was split in this run, in that time")
        if name == "publish":
            p.add_argument("--mode", choices=["publish", "dry-run"], required=True)
        if name == "youtube":
            p.add_argument("--kind", choices=["request", "captions"], default="request")
    df = od_sub.add_parser("daily-files", help="direct downloads of the daily reels (after "
                                               "`daily`, before `notify`)")
    df.add_argument("--report", default="out/daily-report.json")


def _event() -> tuple[str, dict]:
    path = os.environ.get("GITHUB_EVENT_PATH")
    payload = json.loads(Path(path).read_text(encoding="utf-8")) if path and \
        os.path.isfile(path) else {}
    return os.environ.get("GITHUB_EVENT_NAME", ""), payload


def _comment(payload: dict) -> tuple[int | None, str]:
    """The triggering comment's id and its command's arguments (dispatch: inputs.args)."""
    from quran_reels.ondemand.commands import command

    c = payload.get("comment") or {}
    if c:
        return c.get("id"), command(c.get("body"))[1]
    return None, ((payload.get("inputs") or {}).get("args") or "").strip()


def run(cfg: Config, args: argparse.Namespace) -> int:
    from quran_reels.ondemand import flow
    from quran_reels.ondemand.files import Hosting
    from quran_reels.ondemand.gh import GitHub
    from quran_reels.selector.calendar import State

    gh = GitHub()
    if args.od_command == "route":
        event, payload = _event()
        owner = os.environ.get("GITHUB_REPOSITORY_OWNER") or gh.owner
        out = flow.route(event, payload, owner)
        if event == "workflow_dispatch" and out["command"] and out["issue"]:
            title = gh.issue(int(out["issue"])).get("title") or ""
            out["kind"] = "captions" if title == flow.CAPTIONS_TITLE else "request"
        if out["command"] not in ("", "preview", "publish", "dry-run", "youtube", "words"):
            out["command"] = ""
        if out.get("why"):
            print(f"ignored: {out['why']}")
        for key in ("command", "issue", "kind"):
            flow.output(key, str(out[key]))
        return 0
    if args.od_command == "daily-files":
        return flow.daily_files(cfg, Hosting(gh, cfg.root), Path(args.report))

    state_path = Path(args.state)
    if args.od_command == "check":
        status, checked, _ = flow.run_check(cfg, gh, args.issue, State.load(state_path).data,
                                            args.split_seconds)
        flow.output("status", status)
        flow.output("reciter", checked.split if checked and checked.split else
                    (checked.reciter if checked else ""))
        flow.output("key", checked.key if checked else "")
        return 0
    hosting = Hosting(gh, cfg.root)
    if args.od_command == "preview":
        return flow.run_preview(cfg, gh, hosting, args.issue, State.load(state_path).data,
                                os.environ.get("GITHUB_RUN_ID", "local"), args.split_seconds)
    _, payload = _event()
    comment_id, rest = _comment(payload)
    if args.od_command == "publish":
        return flow.run_publish(cfg, gh, hosting, args.issue, args.mode, state_path, comment_id)
    if args.od_command == "youtube":
        return flow.run_youtube(cfg, gh, args.issue, rest, state_path, comment_id, args.kind)
    if args.od_command == "words":
        ok = flow.run_words(gh, args.issue, rest)
        flow.output("skip", "false" if ok else "true")
        return 0
    return 2
