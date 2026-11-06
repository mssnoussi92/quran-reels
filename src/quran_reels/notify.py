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
           "manual": "à publier à la main", "cancelled": "annulé (pas mis en ligne)",
           "failed": "échec",
           "blocked": "bloqué par la vérification des droits",
           "removed": "retiré après publication (Meta l'a rendu muet ou bloqué)"}


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
    blocked = any(r.get("status") == "blocked" for i in (report or {}).get("items", [])
                  for r in i["results"].values())
    if blocked:
        lines += ["", ("⛔ Meta a reconnu un contenu protégé (ou n'a pas pu vérifier) : rien n'est "
                       "publié, sur aucune plateforme, et le créneau n'est pas réessayé. Le passage "
                       "reste en tête de sa file : changer de récitateur (config/project.yaml → "
                       "content.reciter) avant la prochaine publication.")]
    claimed = any(r.get("status") == "removed" or "À RETIRER À LA MAIN" in (r.get("error") or "")
                  for i in (report or {}).get("items", []) for r in i["results"].values())
    if claimed:
        lines += ["", ("🔇 Meta a rendu muet ou bloqué ce reel après sa publication (revendication "
                       "d'un ayant droit, détail ci-dessus) : il est retiré de Facebook et "
                       "d'Instagram (sauf mention « À RETIRER À LA MAIN »), **ne publie pas le "
                       "brouillon TikTok**. Le récitateur est écarté pour de bon (branche `state`, "
                       "`claimed`) et le passage sera republié au prochain créneau de sa file avec "
                       "un autre récitateur.")]
    lines += ["", ("Un créneau en échec est réessayé à chaque passage du workflow pendant 3 h "
                   "(une fois par heure). Ce ticket se ferme tout seul à la prochaine "
                   "publication réussie.")]
    return "\n".join(lines)


def _youtube(item: dict) -> list[str]:
    """What to put on YouTube when it is not this video (daily.youtube_version)."""
    y = item.get("youtube")
    if not y:
        return []
    if not y.get("reciter"):
        return ["", (f"**YouTube : ne pas mettre cette vidéo** (récitateur revendiqué par "
                     f"Content ID) ; pas d'autre version : {y.get('error', '')}")]
    files = item.get("files") or {}
    where = (f"[ce MP4]({files['youtube_mp4']}), récitée par {y['label']}"
             if files.get("youtube_mp4") else
             f"`{y['video']}`, récitée par {y['label']}, dans l'artefact « reel » du run")
    return ["", (f"**YouTube : pas cette vidéo** ({y['instead_of']} y est revendiqué par Content "
                 f"ID) mais {where}. Sa légende :"), "", "```text", y["caption"].strip(), "```"]


def _files(item: dict) -> list[str]:
    """Direct downloads (release `reels`) and the YouTube page, from ondemand.flow.daily_files."""
    f = item.get("files")
    if not f:
        return []
    return ["", (f"⬇️ [MP4]({f['mp4']}) · 📺 [YouTube : MP4, titre, description, hashtags à "
                 f"copier]({f['page']})"),
            f"Mis en ligne sur YouTube ? Commente ici `{f['command']} <lien>`"]


def _entry(item: dict, dry_run: bool) -> str:
    title = f"### {_when(item)} · {item['passage']}" + (" (dry run)" if dry_run else "")
    if item.get("label"):
        title += f" · {item['label']}"
    return "\n".join([f"<!-- entry {item['key']} -->", title, "", _results(item), *_files(item),
                      "", "```text", item["caption"].strip(), "```", *_youtube(item)])


_ENTRY = re.compile(r"<!-- entry (\S+) -->")


def _has_caption(item: dict) -> bool:
    """A caption to copy, for a video that went out somewhere (not one stopped by the rights
    check)."""
    results = item["results"].values()
    return bool(item.get("caption")) and not any(r.get("status") == "removed" for r in results) \
        and any(r.get("status") in ("published", "draft", "ready") for r in results)


def merge_captions(body: str, report: dict, keep: int = KEEP_CAPTIONS) -> str:
    """The captions issue body: the report's entries first, then the previous ones."""
    old: dict[str, str] = {}
    marks = list(_ENTRY.finditer(body or ""))
    for k, m in enumerate(marks):
        end = marks[k + 1].start() if k + 1 < len(marks) else len(body)
        old[m[1]] = body[m.start():end].strip()
    new = {i["key"]: _entry(i, report.get("dry_run", False))
           for i in reversed(report.get("items", [])) if _has_caption(i)}
    entries = list(new.items()) + [(k, v) for k, v in old.items() if k not in new]
    head = ("Légendes des dernières vidéos, à coller sur le brouillon TikTok (il arrive dans "
            "ta boîte) : 5 hashtags, la limite de TikTok. Mis à jour à chaque publication ; "
            "les plus récentes en haut. YouTube (à la main) : le lien ⬇️ MP4 de chaque vidéo "
            "s'enregistre sur le téléphone, la page 📺 donne titre, description et tous les "
            "hashtags à copier ; puis commente `/youtube <jour>/<créneau> <lien>` ici.")
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

    if report and any(_has_caption(i) for i in report.get("items", [])):
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
