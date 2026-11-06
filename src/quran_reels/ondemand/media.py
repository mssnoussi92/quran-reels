"""What a phone loads quickly: a light copy of the reel and a few frames, cut from the MP4 the
pipeline rendered (never a new rendering: what is previewed is what is published)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

PREVIEW_WIDTH = 540


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _ffmpeg(*args: str) -> None:
    done = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *args],
                          capture_output=True, text=True, check=False)
    if done.returncode:
        raise RuntimeError(f"ffmpeg: {done.stderr.strip()[-300:]}")


def light(video: Path, dest: Path, width: int = PREVIEW_WIDTH) -> Path:
    """540 px wide, a few MB: to watch the preview on mobile data."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    _ffmpeg("-i", str(video), "-vf", f"scale={width}:-2", "-c:v", "libx264", "-preset",
            "veryfast", "-crf", "28", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
            "-movflags", "+faststart", str(dest))
    return dest


def moments(manifest: dict, count: int = 3) -> list[float]:
    """Times worth a look: the first screen, one with a word meaning, the last one (middle of
    each screen, so that the text has faded in)."""
    screens: list[tuple[float, float, bool]] = []
    for a in manifest.get("ayahs") or []:
        parts = a.get("screens") or [{"start": a["start"]}]
        ends = [p["start"] for p in parts[1:]] + [a["start"] + a["seconds"]]
        for p, end in zip(parts, ends, strict=True):
            screens.append((p["start"], end, bool(a.get("glosses"))))
    if not screens:
        return []
    picks = [screens[0]]
    middle = screens[1:-1]
    if middle and count > 2:
        glossed = [s for s in middle if s[2]]
        picks.append(glossed[0] if glossed else middle[len(middle) // 2])
    if len(screens) > 1:
        picks.append(screens[-1])
    return [round((a + b) / 2, 2) for a, b, _ in dict.fromkeys(picks)][:count]


def frames(video: Path, dest_dir: Path, width: int = PREVIEW_WIDTH) -> list[Path]:
    """JPEG frames of the reel at moments() of its manifest (out/<slug>/manifest.json)."""
    manifest = json.loads((video.with_suffix("") / "manifest.json").read_text(encoding="utf-8"))
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for i, t in enumerate(moments(manifest), start=1):
        jpg = dest_dir / f"frame-{i}.jpg"
        _ffmpeg("-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-vf",
                f"scale={width}:-2", "-q:v", "4", str(jpg))
        out.append(jpg)
    return out
