"""Save a value into a GitHub Actions secret of this repository (TikTok's rotating token).

Uses the gh CLI, preinstalled on GitHub runners, authenticated with GH_SECRETS_TOKEN: a
fine-grained personal access token limited to this repository with the permission
"Secrets: read and write". The value goes through stdin, never through argv or a log.
"""

from __future__ import annotations

import os
import subprocess


class SecretSaveError(RuntimeError):
    pass


def mask(value: str) -> None:
    """Hide a value created during the run (new token) from the GitHub Actions log."""
    if value and os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::add-mask::{value}", flush=True)


def save_secret(name: str, value: str) -> None:
    mask(value)
    token = os.environ.get("GH_SECRETS_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        missing = [n for n, v in (("GH_SECRETS_TOKEN", token), ("GITHUB_REPOSITORY", repo)) if not v]
        raise SecretSaveError(f"cannot save {name}: {', '.join(missing)} not set")
    env = {**os.environ, "GH_TOKEN": token}
    env.pop("GITHUB_TOKEN", None)
    try:
        proc = subprocess.run(["gh", "secret", "set", name, "--repo", repo], input=value,
                              text=True, capture_output=True, env=env, check=False, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise SecretSaveError(f"cannot save {name}: gh failed ({type(e).__name__})") from None
    if proc.returncode != 0:
        raise SecretSaveError(f"cannot save {name}: {proc.stderr.strip()[-300:]}")
