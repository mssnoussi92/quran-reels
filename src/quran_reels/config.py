"""Project configuration and paths."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


def find_root(start: Path | None = None) -> Path:
    """Project root: $QURAN_REELS_ROOT, else the first parent holding config/project.yaml."""
    if env := os.environ.get("QURAN_REELS_ROOT"):
        return Path(env).resolve()
    for d in [(start or Path.cwd()).resolve(), *(start or Path.cwd()).resolve().parents]:
        if (d / "config" / "project.yaml").is_file():
            return d
    pkg_root = Path(__file__).resolve().parents[2]
    if (pkg_root / "config" / "project.yaml").is_file():
        return pkg_root
    raise SystemExit("config/project.yaml not found: run from the repository or set QURAN_REELS_ROOT")


@dataclass
class Config:
    root: Path
    project: dict[str, Any]
    backgrounds: list[dict[str, Any]]
    gloss_headwords: dict[str, dict[str, str]]

    @property
    def cache(self) -> Path:
        return Path(os.environ.get("QURAN_REELS_CACHE", self.root / ".cache"))

    @property
    def out(self) -> Path:
        return self.root / "out"

    @property
    def fonts(self) -> Path:
        return self.root / "assets" / "fonts"

    @property
    def content(self) -> dict[str, Any]:
        return self.project["content"]

    @property
    def video(self) -> dict[str, Any]:
        return self.project["video"]


def _yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load(root: Path | None = None) -> Config:
    root = root or find_root()
    return Config(
        root=root,
        project=_yaml(root / "config" / "project.yaml"),
        backgrounds=_yaml(root / "config" / "backgrounds.yaml").get("clips") or [],
        gloss_headwords=_yaml(root / "config" / "glosses.yaml").get("headwords") or {},
    )
