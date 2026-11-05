"""Background video for a passage: chosen from what its translation mentions.

config/backgrounds.yaml lists the backgrounds, each with tags: generated scenes
(sources/scenes/*.frag) and hand-picked clips (direct file URLs, Pexels, no API key). Its
`themes` are patterns on the translation (Sahih International): a passage that mentions the
mountains three times scores `mountains` 3 × the theme's weight. The best-scoring theme that
has a background wins; the same passage always gets the same background among those with the
tag. A passage that mentions none takes one of `default`.

Clips are cropped to 9:16 (`focus`: horizontal centre of the crop), scaled to the video size
and made into a seamless loop once (their last seconds blend into their first ones), then
cached in .cache/backgrounds/. The compositor loops them under the video.

Without any background listed, a provisional night sky is generated with numpy.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from quran_reels.config import Config
from quran_reels.models import Passage
from quran_reels.sources.http import Http

CLIP_VERSION = 1             # bump when the clip processing changes
CLIP_FADE = 2.0              # seconds blended at the loop point
_BRACKETS = re.compile(r"\[[^\]]*\]")


@dataclass(frozen=True)
class Background:
    id: str
    tags: tuple[str, ...]
    scene: str = ""          # generated: sources/scenes/<scene>.frag
    file: str = ""           # clip: direct file URL
    page: str = ""           # clip: where it comes from (licence, credit)
    source: str = ""         # pexels | pixabay | generated
    focus: float = 0.5       # clip: horizontal centre of the 9:16 crop, 0 left … 1 right
    extra: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)


def catalogue(cfg: Config) -> tuple[list[Background], dict[str, tuple[re.Pattern, float]],
                                    list[str]]:
    """(backgrounds, themes, default ids) from config/backgrounds.yaml."""
    raw = cfg.backgrounds
    out = []
    for c in raw.get("backgrounds") or []:
        if not (c.get("scene") or c.get("file")):
            continue
        out.append(Background(
            id=str(c["id"]), tags=tuple(c.get("tags") or ()), scene=c.get("scene", ""),
            file=c.get("file", ""), page=c.get("page", ""),
            source=c.get("source") or ("generated" if c.get("scene") else ""),
            focus=float(c.get("focus", .5)),
            extra={k: v for k, v in c.items() if k in ("note", "seconds")}))
    themes = {}
    for tag, (pattern, weight) in (raw.get("themes") or {}).items():
        themes[str(tag)] = (re.compile(pattern, re.IGNORECASE), float(weight))
    return out, themes, [str(x) for x in raw.get("default") or []]


def theme_scores(passage: Passage, themes: dict[str, tuple[re.Pattern, float]]) -> Counter:
    """Score per theme from the passage's translation (the basmala is not counted). The
    translator's additions in brackets do not count: «[clouds of] dust» is not about clouds."""
    text = _BRACKETS.sub(" ", " ".join(a.translation for a in passage.ayahs))
    scores: Counter = Counter()
    for tag, (rx, weight) in themes.items():
        n = len(rx.findall(text))
        if n:
            scores[tag] = n * weight
    return scores


def _stable(key: str) -> int:
    return int(hashlib.sha1(key.encode()).hexdigest(), 16)


def choose(cfg: Config, passage: Passage) -> tuple[Background, str, Counter] | None:
    """The background for a passage, the theme that chose it ("" for the default), scores."""
    bgs, themes, default = catalogue(cfg)
    if not bgs:
        return None
    scores = theme_scores(passage, themes)
    order = list(themes)
    for tag, _ in sorted(scores.items(), key=lambda kv: (-kv[1], order.index(kv[0]))):
        pool = [b for b in bgs if tag in b.tags]
        if pool:
            return pool[_stable(passage.key) % len(pool)], tag, scores
    pool = [b for b in bgs if b.id in default] or bgs
    return pool[_stable(passage.key) % len(pool)], "", scores


def clip(cfg: Config, bg: Background, http: Http | None = None) -> Path:
    """A clip cropped to 9:16, at the video size, as a seamless loop (cached)."""
    v = cfg.video
    w, h, fps = v["width"], v["height"], v["fps"]
    digest = hashlib.sha1(f"{bg.file}|{bg.focus}|{w}x{h}|{fps}|{CLIP_VERSION}".encode())
    dest = cfg.cache / "backgrounds" / f"clip-{bg.id}-{digest.hexdigest()[:10]}.mp4"
    if dest.is_file():
        return dest
    raw = dest.with_name(f".raw-{bg.id}.mp4")
    (http or Http(timeout=120)).download(bg.file, raw, min_bytes=200_000)
    try:
        make_loop(raw, dest, w, h, fps, bg.focus)
    finally:
        raw.unlink(missing_ok=True)
    return dest


def make_loop(src: Path, dest: Path, w: int, h: int, fps: int, focus: float = .5,
              fade: float = CLIP_FADE) -> Path:
    """Crop/scale to w×h and blend the last `fade` seconds into the first ones: the result
    (fade seconds shorter) loops without a jump."""
    duration = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
         str(src)], capture_output=True, text=True, check=True).stdout.strip())
    fade_frames = max(1, round(min(fade, duration / 4) * fps))
    total = int(duration * fps)               # frames after the fps filter, rounded down
    keep = total - fade_frames                # frames in the loop
    graph = ";".join([
        (f"[0:v]crop='min(iw,ih*{w}/{h})':'min(ih,iw*{h}/{w})':'(iw-ow)*{focus}':'(ih-oh)/2',"
         f"scale={w}:{h}:flags=lanczos,fps={fps},setsar=1,format=yuv420p,split=3[a][b][c]"),
        f"[a]trim=start_frame={keep}:end_frame={total},setpts=PTS-STARTPTS[tail]",
        f"[b]trim=end_frame={fade_frames},setpts=PTS-STARTPTS[head]",
        f"[c]trim=start_frame={fade_frames}:end_frame={keep},setpts=PTS-STARTPTS[rest]",
        (f"[tail][head]blend=all_expr='A*(1-N/{fade_frames})+B*N/{fade_frames}':shortest=1,"
         "setpts=PTS-STARTPTS[mix]"),
        "[mix][rest]concat=n=2:v=1:a=0[v]",
    ])
    tmp = dest.with_name(f".{dest.name}")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-filter_complex", graph, "-map", "[v]",
         "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-g", str(fps * 2), "-movflags", "+faststart", "-f", "mp4", str(tmp)], check=True)
    tmp.replace(dest)
    return dest


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


def pick(cfg: Config, passage: Passage, http: Http | None = None) -> tuple[Path, dict[str, Any]]:
    """Background file for a passage, and what the manifest records about it."""
    chosen = choose(cfg, passage)
    if chosen is None:
        return provisional(cfg), {"id": f"provisional-v{PROVISIONAL_VERSION}",
                                  "source": "generated"}
    bg, theme, scores = chosen
    if bg.scene:
        from quran_reels.sources import scenes
        path = scenes.render(cfg, bg.scene)
    else:
        path = clip(cfg, bg, http)
    info = {"id": bg.id, "source": bg.source, "theme": theme or "default",
            "scores": dict(scores)}
    if bg.page:
        info["page"] = bg.page
    return path, info
