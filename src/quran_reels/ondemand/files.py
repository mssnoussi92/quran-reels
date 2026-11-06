"""Where the owner's phone finds the files (docs/on-demand.md, « Héberger »):

- MP4s: assets of one GitHub pre-release, tag `reels`. Public URL, no sign-in, served as a
  download (Content-Disposition: attachment): the phone saves it in Downloads, the gallery and
  the YouTube app see it. Not in git, deleted after KEEP_DAYS.
- Key frames (JPEG) and reel.json (what docs/reel.html shows): branch `previews`, never
  merged, read through raw.githubusercontent.com (images shown in comments, JSON with CORS).
  A folder per reel, removed after KEEP_DAYS.

Nothing here is secret: the repository and its releases are public.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from quran_reels.ondemand.gh import GitHub

TAG = "reels"
BRANCH = "previews"
KEEP_DAYS = 30
RELEASE_TITLE = "Fichiers des reels (téléchargement direct, 30 jours)"
RELEASE_NOTES = ("MP4 des reels, à télécharger depuis le téléphone (YouTube à la main) : "
                 "aperçus à la demande et vidéos publiées. Supprimés après 30 jours. "
                 "Voir docs/on-demand.md.")
IDENTITY = ["-c", "user.name=quran-reels",
            "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com"]


def _git(*args: str, cwd: Path) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if done.returncode:
        raise RuntimeError(f"git {args[0]}: {done.stderr.strip()[:300]}")
    return done.stdout


class Hosting:
    def __init__(self, gh: GitHub, root: Path, git: Callable[..., str] = _git,
                 sleep: Callable[[float], None] = time.sleep):
        self.gh, self.root, self._git, self._sleep = gh, root, git, sleep
        self._release: dict | None = None

    # ---- addresses ------------------------------------------------------------------
    def asset_url(self, name: str) -> str:
        return f"https://github.com/{self.gh.repo}/releases/download/{TAG}/{name}"

    def raw_url(self, path: str) -> str:
        return f"https://raw.githubusercontent.com/{self.gh.repo}/{BRANCH}/{path}"

    def page_url(self, rid: str, version: str = "") -> str:
        owner, name = self.gh.repo.split("/")
        return (f"https://{owner}.github.io/{name}/reel.html?r={rid}"
                + (f"&v={version}" if version else ""))

    # ---- release assets -----------------------------------------------------------------
    def release(self) -> dict:
        if self._release is None:
            self._release = self.gh.release(TAG, RELEASE_TITLE, RELEASE_NOTES)
        return self._release

    def upload(self, path: Path, name: str) -> str:
        self.release()
        self.gh.upload(TAG, path, name)
        return self.asset_url(name)

    def prune_assets(self, days: int = KEEP_DAYS, now: datetime | None = None) -> list[str]:
        limit = (now or datetime.now(UTC)) - timedelta(days=days)
        gone = []
        for a in self.gh.assets(self.release()["id"]):
            created = datetime.fromisoformat(a["created_at"])
            if created < limit:
                self.gh.delete_asset(a["id"])
                gone.append(a["name"])
        return gone

    # ---- branch `previews` --------------------------------------------------------------
    def _worktree(self) -> Path:
        wt = self.root / ".previews-branch"
        if (wt / ".git").exists():
            return wt
        try:
            self._git("ls-remote", "--exit-code", "--heads", "origin", BRANCH, cwd=self.root)
            self._git("fetch", "--depth=1", "origin", f"+{BRANCH}:refs/remotes/origin/{BRANCH}",
                      cwd=self.root)
            self._git("worktree", "add", "--detach", str(wt), f"origin/{BRANCH}", cwd=self.root)
        except RuntimeError:
            self._git("worktree", "add", "--orphan", "-b", f"{BRANCH}-new", str(wt),
                      cwd=self.root)
        return wt

    def read(self, rel: str) -> str | None:
        """A file of the `previews` branch as it is now on GitHub, or None."""
        wt = self._worktree()
        try:
            self._git("fetch", "--depth=1", "origin",
                      f"+{BRANCH}:refs/remotes/origin/{BRANCH}", cwd=wt)
            self._git("reset", "--hard", f"origin/{BRANCH}", cwd=wt)
        except RuntimeError:
            return None
        path = wt / rel
        return path.read_text(encoding="utf-8") if path.is_file() else None

    def publish(self, files: dict[str, Path | str], message: str,
                prune_days: int | None = KEEP_DAYS, now: datetime | None = None) -> None:
        """Write files (path in the branch → local file or text) on `previews` and push;
        on a refused push, start again from the new tip (other runs write other folders)."""
        wt = self._worktree()
        for attempt in range(5):
            try:
                self._git("fetch", "--depth=1", "origin",
                          f"+{BRANCH}:refs/remotes/origin/{BRANCH}", cwd=wt)
                self._git("reset", "--hard", f"origin/{BRANCH}", cwd=wt)
            except RuntimeError:
                pass                                # first push: the branch does not exist
            for rel, content in files.items():
                dest = wt / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(content, Path):
                    shutil.copyfile(content, dest)
                else:
                    dest.write_text(content, encoding="utf-8")
            if prune_days:
                prune_folders(wt, prune_days, now, keep=set(files))
            self._git("add", "-A", ".", cwd=wt)
            status = self._git("status", "--porcelain", cwd=wt)
            if not status.strip():
                return
            self._git(*IDENTITY, "commit", "-q", "-m", message, cwd=wt)
            try:
                self._git("push", "-q", "origin", f"HEAD:refs/heads/{BRANCH}", cwd=wt)
                return
            except RuntimeError as e:
                if attempt == 4:
                    raise
                print(f"previews: push refused ({e}), again", file=sys.stderr)
                self._sleep(2 ** attempt)


def prune_folders(wt: Path, days: int, now: datetime | None = None,
                  keep: set[str] = frozenset()) -> list[str]:
    """Folders of the previews branch whose reel.json is older than `days`."""
    limit = (now or datetime.now(UTC)) - timedelta(days=days)
    gone = []
    for meta in wt.glob("**/reel.json"):
        rel = meta.relative_to(wt).as_posix()
        if rel in keep:
            continue
        try:
            created = datetime.fromisoformat(json.loads(meta.read_text(encoding="utf-8"))
                                             ["created"])
        except (ValueError, KeyError, OSError):
            continue
        if created < limit:
            shutil.rmtree(meta.parent)
            gone.append(meta.parent.relative_to(wt).as_posix())
    return gone
