"""Background video: a hand-picked clip from config/backgrounds.yaml, or a generated one.

The generated background is provisional, until the clip list is filled. It is a seamless
12-second loop drawn with numpy (night sky turning to dawn, twinkling stars, slow drifting
light) and cached in .cache/backgrounds/. Clips and the generated loop are used the same way:
looped, scaled and cropped to 9:16 by ffmpeg.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from quran_reels.config import Config
from quran_reels.sources.http import Http

PROVISIONAL_VERSION = 1

# Same palette as the validated mockup (docs/mockup/apercu-reel-93-2.png).
_SKY = [(0.00, "#0b1026"), (0.45, "#1a2350"), (0.72, "#3b3a6b"), (1.00, "#8a5a5a")]


def _rgb(hex_color: str) -> np.ndarray:
    h = hex_color.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32) / 255


def _gaussian(n: int, center: float, sigma: float) -> np.ndarray:
    x = np.arange(n, dtype=np.float32)
    return np.exp(-0.5 * ((x - center) / sigma) ** 2)


def _frames(w: int, h: int, fps: int, seconds: int, seed: int = 93):
    rng = np.random.default_rng(seed)
    period = seconds
    ys = np.linspace(0, 1, h, dtype=np.float32)
    stops = np.array([s for s, _ in _SKY], dtype=np.float32)
    colors = np.stack([_rgb(c) for _, c in _SKY])
    # Channel-first (3, h, w) so that each light is one matrix product per channel.
    column = np.stack([np.interp(ys, stops, colors[:, i]) for i in range(3)])
    base = np.broadcast_to(column[:, :, None], (3, h, w)).astype(np.float32)
    dither = rng.random((h, w), dtype=np.float32) - rng.random((h, w), dtype=np.float32)

    # Light: a dawn glow under the horizon and three faint clouds on closed orbits.
    lights = [  # color, intensity, cx, cy, sigma x, sigma y, orbit x, orbit y, phase, pulse
        (_rgb("#ffb07a"), 0.20, 0.50 * w, 1.06 * h, 0.55 * w, 0.20 * h, 0.04 * w, 0.01 * h, 0.0, 0.12),
        (_rgb("#5a6fd0"), 0.10, 0.25 * w, 0.30 * h, 0.40 * w, 0.18 * h, 0.14 * w, 0.05 * h, 0.0, 0.0),
        (_rgb("#9a5fb0"), 0.08, 0.80 * w, 0.55 * h, 0.38 * w, 0.16 * h, 0.12 * w, 0.06 * h, 2.1, 0.0),
        (_rgb("#3f8fb0"), 0.06, 0.45 * w, 0.12 * h, 0.45 * w, 0.12 * h, 0.16 * w, 0.03 * h, 4.2, 0.0),
    ]

    # Stars: denser and brighter high in the sky, fading towards the dawn.
    n = 340
    sx = rng.random(n) * w
    sy = (rng.random(n) ** 1.7) * 0.82 * h
    size = 0.55 + rng.random(n) ** 3 * 1.1
    bright = (0.25 + 0.75 * rng.random(n) ** 2.2) * (1 - sy / h) ** 0.8
    cycles = rng.integers(1, 4, n)              # whole cycles per loop: seamless
    phase = rng.random(n) * 2 * np.pi
    depth = 0.25 + 0.55 * rng.random(n)
    tint = np.where(rng.random((n, 1)) < 0.5, _rgb("#fff4e0"), _rgb("#e6eeff"))
    r = 4
    grid = np.arange(-r, r + 1, dtype=np.float32)
    sprites = []
    for i in range(n):
        fx, fy = sx[i] - np.floor(sx[i]), sy[i] - np.floor(sy[i])
        g = np.exp(-0.5 * (((grid[None, :] - fx + 0.5) ** 2 + (grid[:, None] - fy + 0.5) ** 2)
                           / size[i] ** 2))
        sprites.append(tint[i][:, None, None] * g[None, :, :])

    for f in range(fps * seconds):
        t = f / fps
        a = 2 * np.pi * t / period
        gys = np.stack([_gaussian(h, cy + oy * np.sin(a + ph), sgy)
                        for _, _, _, cy, _, sgy, _, oy, ph, _ in lights], axis=1)    # (h, L)
        gxs = np.stack([_gaussian(w, cx + ox * np.cos(a + ph), sgx)
                        for _, _, cx, _, sgx, _, ox, _, ph, _ in lights])            # (L, w)
        amp = np.stack([color * k * (1 + pulse * np.sin(a))
                        for color, k, *_, pulse in lights])                          # (L, 3)
        frame = base.copy()
        for ch in range(3):
            frame[ch] += (gys * amp[:, ch]) @ gxs
        level = bright * (1 - depth * (0.5 + 0.5 * np.sin(cycles * a + phase)))
        for i in range(n):
            x0, y0 = int(sx[i]) - r, int(sy[i]) - r
            if x0 < 0 or y0 < 0 or x0 + 2 * r + 1 > w or y0 + 2 * r + 1 > h:
                continue
            frame[:, y0:y0 + 2 * r + 1, x0:x0 + 2 * r + 1] += sprites[i] * level[i]
        out = np.clip(frame * 255 + dither, 0, 255).astype(np.uint8)
        yield np.ascontiguousarray(out.transpose(1, 2, 0))


def provisional(cfg: Config, seconds: int = 12) -> Path:
    v = cfg.video
    w, h, fps = v["width"], v["height"], v["fps"]
    dest = cfg.cache / "backgrounds" / f"provisional-v{PROVISIONAL_VERSION}-{w}x{h}-{fps}.mp4"
    if dest.is_file():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}")
    proc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
         "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p",
         "-g", str(fps * 2), "-movflags", "+faststart", "-f", "mp4", str(tmp)],
        stdin=subprocess.PIPE)
    assert proc.stdin
    try:
        for frame in _frames(w, h, fps, seconds):
            proc.stdin.write(frame.tobytes())
    finally:
        proc.stdin.close()
    if proc.wait() != 0:
        tmp.unlink(missing_ok=True)
        raise RuntimeError("ffmpeg failed while encoding the provisional background")
    tmp.replace(dest)
    return dest


def pick(cfg: Config, passage_key: str, http: Http | None = None) -> tuple[Path, dict[str, Any]]:
    """Background file for a passage, and what to credit. Same passage → same clip."""
    clips = [c for c in cfg.backgrounds if c.get("file")]
    if not clips:
        return provisional(cfg), {"id": f"provisional-v{PROVISIONAL_VERSION}",
                                  "source": "generated"}
    digest = int(hashlib.sha1(passage_key.encode()).hexdigest(), 16)
    clip = clips[digest % len(clips)]
    dest = cfg.cache / "backgrounds" / f"{clip['id']}.mp4"
    if not dest.is_file():
        (http or Http()).download(clip["file"], dest, min_bytes=50_000)
    return dest, clip
