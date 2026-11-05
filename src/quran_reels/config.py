"""Project configuration and paths."""

from __future__ import annotations

import os
import re
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
    backgrounds: dict[str, Any]           # config/backgrounds.yaml
    gloss_headwords: dict[str, list[tuple[str, ...]]]   # "93:2" → [("سجى",)]

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


_AYAH_KEY = re.compile(r"^\s*(\d{1,3})\s*:\s*(\d{1,3})\s*$")


def parse_headwords(raw: Any) -> dict[str, list[tuple[str, ...]]]:
    """config/glosses.yaml headwords → {"S:A": [choice, ...]}, each choice one or two words.

    A string is one choice («سجى», «زهرة الحياة»); a list holds one choice per gloss of the
    ayah («[ريب, هدى]»).
    """
    if not raw:
        return {}
    if not isinstance(raw, dict):
        raise SystemExit("config/glosses.yaml: headwords must map ayahs (\"93:2\") to words")
    out: dict[str, list[tuple[str, ...]]] = {}
    for key, value in raw.items():
        if isinstance(key, int) and not isinstance(key, bool):
            key = f"{key // 60}:{key % 60}"     # 93:2 without quotes is read as 93×60+2
        m = _AYAH_KEY.match(str(key))
        if not m:
            raise SystemExit(f"config/glosses.yaml: «{key}» is not an ayah such as \"93:2\"")
        ayah = f"{int(m[1])}:{int(m[2])}"
        items = value if isinstance(value, list) else [value]
        choices = []
        for item in items:
            if isinstance(item, dict) or item is None:
                raise SystemExit(f"config/glosses.yaml, {ayah}: write the word(s) to highlight, "
                                 "e.g. \"93:2\": سجى")
            chosen = tuple(str(item).split())
            if not 1 <= len(chosen) <= 2:
                raise SystemExit(f"config/glosses.yaml, {ayah}: «{item}»: choose one or two words")
            choices.append(chosen)
        out[ayah] = choices
    return out


def load(root: Path | None = None) -> Config:
    root = root or find_root()
    return Config(
        root=root,
        project=_yaml(root / "config" / "project.yaml"),
        backgrounds=_yaml(root / "config" / "backgrounds.yaml"),
        gloss_headwords=parse_headwords(_yaml(root / "config" / "glosses.yaml").get("headwords")),
    )
