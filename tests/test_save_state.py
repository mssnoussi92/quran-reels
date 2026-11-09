"""`.github/scripts/save-state.sh` against a local remote: what a run wrote on the state branch is
pushed even when another run pushed first (a publication not recorded is published again)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "save-state.sh"
ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
       "SAVE_STATE_PAUSE": "0"}
WRITER = {**ENV, "GIT_AUTHOR_NAME": "other", "GIT_AUTHOR_EMAIL": "other@example.org",
          "GIT_COMMITTER_NAME": "other", "GIT_COMMITTER_EMAIL": "other@example.org"}


def git(cwd: Path, *args: str, env: dict = ENV) -> str:
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True,
                          text=True).stdout.strip()


def state(slots: dict) -> str:
    return json.dumps({"queues": {}, "slots": slots}, ensure_ascii=False, indent=1) + "\n"


@pytest.fixture
def remote(tmp_path: Path) -> Path:
    """origin with a main branch and a state branch holding one published slot."""
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    seed = tmp_path / "seed"
    git(tmp_path, "clone", "-q", str(origin), str(seed))
    (seed / "README.md").write_text("main\n", encoding="utf-8")
    git(seed, "add", "."), git(seed, "commit", "-q", "-m", "main", env=WRITER)
    git(seed, "push", "-q", "origin", "HEAD:main", env=WRITER)
    git(seed, "checkout", "-q", "--orphan", "state"), git(seed, "rm", "-q", "-rf", ".")
    (seed / "published.json").write_text(state({"2026-11-08/evening": {"passage": "2:255"}}),
                                         encoding="utf-8")
    git(seed, "add", "."), git(seed, "commit", "-q", "-m", "state", env=WRITER)
    git(seed, "push", "-q", "origin", "state", env=WRITER)
    return origin


def run_checkout(tmp_path: Path, origin: Path, name: str = "run") -> Path:
    """What a workflow does: shallow checkout of main, the state branch in a worktree."""
    repo = tmp_path / name
    git(tmp_path, "clone", "-q", "--depth=1", "-b", "main", f"file://{origin}", str(repo))
    git(repo, "fetch", "-q", "--depth=1", "origin", "state:state")
    git(repo, "worktree", "add", "-q", "state-branch", "state")
    return repo / "state-branch"


def other_writer(tmp_path: Path, origin: Path, change, name: str = "other") -> None:
    """Another run pushes to the state branch while this one is publishing."""
    clone = tmp_path / name
    git(tmp_path, "clone", "-q", "-b", "state", str(origin), str(clone))
    change(clone)
    git(clone, "add", "."), git(clone, "commit", "-q", "-m", "other run", env=WRITER)
    git(clone, "push", "-q", "origin", "state", env=WRITER)


def save(worktree: Path, *paths: str, env: dict = ENV) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(SCRIPT), "État", *paths], cwd=worktree, env=env,
                          capture_output=True, text=True, check=False)


def on_remote(origin: Path, path: str) -> str:
    return git(origin, "show", f"state:{path}")


def publish(worktree: Path, day: str = "2026-11-09/morning", passage: str = "112:1-4") -> None:
    data = json.loads((worktree / "published.json").read_text(encoding="utf-8"))
    data["slots"][day] = {"passage": passage}
    (worktree / "published.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def test_a_change_is_committed_and_pushed(tmp_path, remote):
    wt = run_checkout(tmp_path, remote)
    publish(wt)
    done = save(wt, "published.json")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "112:1-4" in on_remote(remote, "published.json")
    assert git(remote, "log", "-1", "--format=%an %s", "state").startswith("quran-reels État 20")


def test_nothing_changed_nothing_pushed(tmp_path, remote):
    wt = run_checkout(tmp_path, remote)
    before = git(remote, "rev-parse", "state")
    done = save(wt, "published.json")
    assert done.returncode == 0 and "no change" in done.stdout
    assert git(remote, "rev-parse", "state") == before


def test_a_missing_path_or_no_worktree_is_not_an_error(tmp_path, remote):
    wt = run_checkout(tmp_path, remote)
    assert save(wt, "splits").returncode == 0               # prepare: no split written
    plain = tmp_path / "plain"                               # on-demand preview: no state branch
    plain.mkdir()
    (plain / "published.json").write_text("{}", encoding="utf-8")
    done = save(plain, "published.json")
    assert done.returncode == 0 and "no state worktree" in done.stdout


def test_splits_pushed_meanwhile_do_not_lose_the_publication(tmp_path, remote):
    """The on-demand preview is outside the `accounts` group: it pushes its splits while the
    daily run publishes. The daily push was refused and its slot lost; now it is replayed."""
    wt = run_checkout(tmp_path, remote)
    publish(wt)

    def splits(clone: Path) -> None:
        (clone / "splits" / "sayegh").mkdir(parents=True)
        (clone / "splits" / "sayegh" / "101.json").write_text("{}\n", encoding="utf-8")

    other_writer(tmp_path, remote, splits)
    done = save(wt, "published.json")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "commit replayed" in done.stdout
    assert "112:1-4" in on_remote(remote, "published.json")
    assert on_remote(remote, "splits/sayegh/101.json") == "{}"


def test_two_writers_of_the_same_file_are_merged_when_lines_differ(tmp_path, remote):
    wt = run_checkout(tmp_path, remote)
    publish(wt)                                              # adds a slot at the end

    def queues(clone: Path) -> None:                         # a session edits the first lines
        text = (clone / "published.json").read_text(encoding="utf-8")
        (clone / "published.json").write_text(
            text.replace('"queues": {}', '"queues": {"reading": {"round": 1, "done": []}}'),
            encoding="utf-8")

    other_writer(tmp_path, remote, queues)
    assert save(wt, "published.json").returncode == 0
    merged = json.loads(on_remote(remote, "published.json"))
    assert merged["queues"] == {"reading": {"round": 1, "done": []}}
    assert merged["slots"]["2026-11-09/morning"] == {"passage": "112:1-4"}


def test_a_real_conflict_fails_loudly_and_leaves_the_branch_alone(tmp_path, remote):
    wt = run_checkout(tmp_path, remote)
    publish(wt, passage="112:1-4")
    other_writer(tmp_path, remote, lambda clone: publish(clone, passage="113:1-5"))
    theirs = git(remote, "rev-parse", "state")
    done = save(wt, "published.json")
    assert done.returncode == 1
    assert "::error::" in done.stdout and "conflicts" in done.stdout
    assert git(remote, "rev-parse", "state") == theirs
    assert git(wt, "status", "--porcelain") == ""            # the rebase was aborted


def test_a_push_that_fails_once_is_tried_again(tmp_path, remote):
    hook = remote / "hooks" / "pre-receive"                  # GitHub down for one push
    hook.write_text('#!/bin/sh\nif [ ! -e "$GIT_DIR/once" ]; then touch "$GIT_DIR/once"; '
                    'echo "outage" >&2; exit 1; fi\n', encoding="utf-8")
    hook.chmod(0o755)
    wt = run_checkout(tmp_path, remote)
    publish(wt)
    done = save(wt, "published.json")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "try 2" in done.stdout and "112:1-4" in on_remote(remote, "published.json")


def test_gives_up_after_its_tries(tmp_path, remote):
    hook = remote / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    wt = run_checkout(tmp_path, remote)
    publish(wt)
    done = save(wt, "published.json", env={**ENV, "SAVE_STATE_TRIES": "3"})
    assert done.returncode == 1 and "not pushed after 3 tries" in done.stdout


def test_the_first_commit_of_a_new_state_branch(tmp_path):
    """No state branch yet: an orphan worktree; another run may create the branch first."""
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    seed = tmp_path / "seed"
    git(tmp_path, "clone", "-q", str(origin), str(seed))
    (seed / "README.md").write_text("main\n", encoding="utf-8")
    git(seed, "add", "."), git(seed, "commit", "-q", "-m", "main", env=WRITER)
    git(seed, "push", "-q", "origin", "HEAD:main", env=WRITER)

    repo = tmp_path / "run"
    git(tmp_path, "clone", "-q", "--depth=1", "-b", "main", f"file://{origin}", str(repo))
    git(repo, "worktree", "add", "-q", "--orphan", "-b", "state", "state-branch")
    wt = repo / "state-branch"
    (wt / "images.json").write_text("{}\n", encoding="utf-8")

    git(seed, "checkout", "-q", "--orphan", "state"), git(seed, "rm", "-q", "-rf", ".")
    (seed / "published.json").write_text(state({}), encoding="utf-8")
    git(seed, "add", "."), git(seed, "commit", "-q", "-m", "state", env=WRITER)
    git(seed, "push", "-q", "origin", "state", env=WRITER)

    done = save(wt, "images.json")
    assert done.returncode == 0, done.stdout + done.stderr
    assert on_remote(origin, "images.json") == "{}"
    assert on_remote(origin, "published.json") == state({}).strip()
