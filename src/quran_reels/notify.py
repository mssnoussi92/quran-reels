"""quran-reels notify: tell the owner, through GitHub issues, what the daily run did.

- A failed run opens the issue «⚠️ Publication quotidienne en échec», assigned to the owner
  (a push notification in the GitHub app), or comments on it if it is already open. The next
  run that publishes comments and closes it.
- Every publishing run updates the issue «📋 Légendes à copier (TikTok, YouTube)»: the
  captions of the latest videos as TikTok takes them (5 hashtags at most), to paste on its
  drafts. caption.txt, in the run's artifact, keeps every hashtag (YouTube).
  Editing it notifies nobody; TikTok already notifies its drafts.

Input: out/daily-report.json, written by `quran-reels daily`. Uses the gh CLI with the
workflow's token (permissions: issues: write). Nothing here contains a secret: errors are
built without tokens, as in the logs, which are public too.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Callable
from datetime import date
from pathlib import Path

FAILURE_TITLE = "⚠️ Publication quotidienne en échec"
CAPTIONS_TITLE = "📋 Légendes à copier (TikTok, YouTube)"
KEEP_CAPTIONS = 4               # the last two days

_DAYS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
_MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.",
           "nov.", "déc."]
_STATUS = {"published": "publié", "draft": "brouillon", "ready": "prêt (dry run)",
           "manual": "à publier à la main", "failed": "échec"}


def _when(item: dict) -> str:
    d = date.fromisoformat(item["day"])
    return f"{_DAYS[d.weekday()]} {d.day} {_MONTHS[d.month - 1]} · {item['time']}"


def _results(item: dict, errors: bool = False) -> str:
    parts = []
    for platform, r in item["results"].items():
        label = ("brouillon dans ta boîte TikTok" if (platform, r["status"]) == ("tiktok", "draft")
                 else _STATUS.get(r["status"], r["status"]))
        label = f"[{label}]({r['url']})" if r.get("url") else label
        parts.append(f"{platform} : {label}")
    out = " · ".join(parts)
    if errors:
        out += "".join(f"\n  - {p} : `{r['error']}`" for p, r in item["results"].items()
                       if r.get("error"))
    return out


def failure_text(report: dict | None, run_url: str) -> str:
    lines = [f"Run : {run_url}", ""]
    if not report or not (report.get("items") or report.get("errors")):
        lines.append("Le run a échoué avant de publier : ouvre le lien ci-dessus (journal).")
    for item in (report or {}).get("items", []):
        lines.append(f"- **{_when(item)} · {item['passage']}** — {_results(item, errors=True)}")
    for e in (report or {}).get("errors", []):
        lines += ["", "```text", e.strip(), "```"]
    lines += ["", ("Un créneau en échec est réessayé à chaque passage du workflow pendant 3 h "
                   "(une fois par heure). Ce ticket se ferme tout seul à la prochaine "
                   "publication réussie.")]
    return "\n".join(lines)


def _entry(item: dict, dry_run: bool) -> str:
    title = f"### {_when(item)} · {item['passage']}" + (" (dry run)" if dry_run else "")
    if item.get("label"):
        title += f" · {item['label']}"
    return "\n".join([f"<!-- entry {item['key']} -->", title, "", _results(item), "",
                      "```text", item["caption"].strip(), "```"])


_ENTRY = re.compile(r"<!-- entry (\S+) -->")


def merge_captions(body: str, report: dict, keep: int = KEEP_CAPTIONS) -> str:
    """The captions issue body: the report's entries first, then the previous ones."""
    old: dict[str, str] = {}
    marks = list(_ENTRY.finditer(body or ""))
    for k, m in enumerate(marks):
        end = marks[k + 1].start() if k + 1 < len(marks) else len(body)
        old[m[1]] = body[m.start():end].strip()
    new = {i["key"]: _entry(i, report.get("dry_run", False))
           for i in reversed(report.get("items", [])) if i.get("caption")}
    entries = list(new.items()) + [(k, v) for k, v in old.items() if k not in new]
    head = ("Légendes des dernières vidéos, à coller sur le brouillon TikTok (il arrive dans "
            "ta boîte) : 5 hashtags, la limite de TikTok. Mis à jour à chaque publication ; "
            "les plus récentes en haut. Tous les hashtags (YouTube) : caption.txt dans "
            "l'artefact du run.")
    return "\n\n".join([head, *(v for _, v in entries[:keep])]) + "\n"


class Issues:
    """The few gh commands needed, on $GITHUB_REPOSITORY."""

    def __init__(self, repo: str, runner: Callable[..., str] | None = None):
        self.repo = repo
        self._run = runner or self._gh

    @staticmethod
    def _gh(*args: str, stdin: str | None = None) -> str:
        done = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True,
                              check=False)
        if done.returncode:
            raise RuntimeError(f"gh {args[0]} {args[1]}: {done.stderr.strip()[:300]}")
        return done.stdout

    def find(self, title: str) -> dict | None:
        out = self._run("issue", "list", "--repo", self.repo, "--state", "open", "--limit",
                        "100", "--json", "number,title,body")
        return next((i for i in json.loads(out or "[]") if i["title"] == title), None)

    def create(self, title: str, body: str, assignee: str | None = None) -> int:
        args = ["issue", "create", "--repo", self.repo, "--title", title, "--body-file", "-"]
        if assignee:
            args += ["--assignee", assignee]
        url = self._run(*args, stdin=body).strip()
        return int(url.rstrip("/").rsplit("/", 1)[-1])

    def comment(self, number: int, body: str) -> None:
        self._run("issue", "comment", str(number), "--repo", self.repo, "--body-file", "-",
                  stdin=body)

    def edit(self, number: int, body: str) -> None:
        self._run("issue", "edit", str(number), "--repo", self.repo, "--body-file", "-",
                  stdin=body)

    def close(self, number: int) -> None:
        self._run("issue", "close", str(number), "--repo", self.repo)

    def pin(self, number: int) -> None:
        try:
            self._run("issue", "pin", str(number), "--repo", self.repo)
        except RuntimeError:
            pass                    # pinning is a convenience


def run(report_path: Path, outcome: str, run_url: str, owner: str | None,
        issues: Issues | None = None) -> int:
    issues = issues or Issues(os.environ["GITHUB_REPOSITORY"])
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else None
    dry_run = bool(report and report.get("dry_run"))

    if report and any(i.get("caption") for i in report.get("items", [])):
        current = issues.find(CAPTIONS_TITLE)
        if current:
            issues.edit(current["number"], merge_captions(current.get("body") or "", report))
        else:
            issues.pin(issues.create(CAPTIONS_TITLE, merge_captions("", report)))
        print("captions issue updated")

    if dry_run:
        return 0                    # a test run never opens nor closes the failure issue
    failure = issues.find(FAILURE_TITLE)
    if outcome == "failure":
        text = failure_text(report, run_url)
        if failure:
            issues.comment(failure["number"], "Encore en échec.\n\n" + text)
        else:
            mention = f"@{owner} : " if owner else ""
            issues.create(FAILURE_TITLE, mention + "la publication quotidienne a échoué.\n\n"
                          + text, assignee=owner)
        print("failure issue updated")
    elif outcome == "success" and failure and report and report.get("items"):
        done = "\n".join(f"- {_when(i)} · {i['passage']} — {_results(i)}"
                         for i in report["items"])
        issues.comment(failure["number"], f"✅ Réglé par {run_url}\n\n{done}")
        issues.close(failure["number"])
        print("failure issue closed")
    return 0
