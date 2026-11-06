"""The few GitHub calls of the on-demand flow, through the gh CLI and the workflow's token
(GH_TOKEN = github.token: issues, contents and actions of this repository only).

Injectable runner for the tests (no network). Nothing printed here contains a secret; issue
texts and comments are public anyway.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

BOT = "github-actions[bot]"


class GhError(RuntimeError):
    pass


def _gh(*args: str, stdin: str | None = None) -> str:
    done = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True,
                          check=False)
    if done.returncode:
        raise GhError(f"gh {' '.join(args[:3])}: {done.stderr.strip()[:300]}")
    return done.stdout


class GitHub:
    def __init__(self, repo: str | None = None, runner: Callable[..., str] | None = None):
        self.repo = repo or os.environ.get("GITHUB_REPOSITORY", "mssnoussi92/quran-reels")
        self._run = runner or _gh

    @property
    def owner(self) -> str:
        return self.repo.split("/")[0]

    def api(self, path: str, method: str = "GET", body: dict | None = None) -> Any:
        args = ["api", "-X", method, f"repos/{self.repo}/{path}"]
        if body is not None:
            args += ["--input", "-"]
        out = self._run(*args, stdin=json.dumps(body) if body is not None else None)
        return json.loads(out) if out.strip() else None

    def api_list(self, path: str) -> list[Any]:
        """Every element of a paginated list (one JSON object per line from gh)."""
        out = self._run("api", f"repos/{self.repo}/{path}", "--paginate", "--jq", ".[]")
        return [json.loads(line) for line in out.splitlines() if line.strip()]

    # ---- issues ---------------------------------------------------------------------
    def issue(self, number: int) -> dict:
        return self.api(f"issues/{number}")

    def comments(self, number: int) -> list[dict]:
        return self.api_list(f"issues/{number}/comments?per_page=100")

    def comment(self, number: int, body: str) -> dict:
        return self.api(f"issues/{number}/comments", "POST", {"body": body})

    def edit_comment(self, comment_id: int, body: str) -> None:
        self.api(f"issues/comments/{comment_id}", "PATCH", {"body": body})

    def edit_issue(self, number: int, **fields: Any) -> None:
        self.api(f"issues/{number}", "PATCH", fields)

    def react(self, number: int, content: str = "eyes", comment_id: int | None = None) -> None:
        path = (f"issues/comments/{comment_id}/reactions" if comment_id
                else f"issues/{number}/reactions")
        try:
            self.api(path, "POST", {"content": content})
        except GhError:
            pass                    # a reaction is a courtesy

    def label(self, number: int, name: str, color: str = "0e8a16",
              description: str = "") -> None:
        try:
            self.api("labels", "POST", {"name": name, "color": color,
                                        "description": description})
        except GhError:
            pass                    # it exists
        try:
            self.api(f"issues/{number}/labels", "POST", {"labels": [name]})
        except GhError:
            pass

    # ---- runs and artifacts -----------------------------------------------------------
    def run_info(self, run_id: int) -> dict:
        return self.api(f"actions/runs/{run_id}")

    def download_artifact(self, run_id: int, name: str, dest: Path) -> None:
        self._run("run", "download", str(run_id), "--repo", self.repo, "-n", name,
                  "-D", str(dest))

    # ---- release assets -----------------------------------------------------------------
    def release(self, tag: str, title: str, notes: str) -> dict:
        """The release that holds the files, created once (pre-release, never «latest»)."""
        try:
            return self.api(f"releases/tags/{tag}")
        except GhError:
            return self.api("releases", "POST", {
                "tag_name": tag, "name": title, "body": notes, "prerelease": True,
                "make_latest": "false"})

    def upload(self, tag: str, path: Path, name: str) -> None:
        if path.name != name:
            import shutil
            import tempfile

            tmp = Path(tempfile.mkdtemp()) / name
            shutil.copyfile(path, tmp)
            path = tmp
        self._run("release", "upload", tag, str(path), "--repo", self.repo, "--clobber")

    def assets(self, release_id: int) -> list[dict]:
        return self.api_list(f"releases/{release_id}/assets?per_page=100")

    def delete_asset(self, asset_id: int) -> None:
        self.api(f"releases/assets/{asset_id}", "DELETE")
