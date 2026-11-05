"""Light previews of the stock clips: a few seconds in 360p, no sound, and a poster image.

The media rules of docs/catalog.md: Pexels and Pixabay clips are never put on the site
whole, only a short preview (PREVIEW_SECONDS at 360×640, cropped to 9:16 as in the reel)
with author, licence and a link to the page they come from. Generated scenes need no file:
the page draws them live from their shader.

Previews are cached under .cache/catalog/previews/ (the workflow keeps that cache): a clip is
downloaded once. Its source, in this order: the reel's processed loop when the daily cache is
there (.cache/backgrounds/clip-<id>-*.mp4), else the file itself (Pexels: direct URL;
Pixabay: the API gives its URL, `small` rendition; a search candidate: its preview URL).
Pixabay's CDN limits downloads: one every CDN_INTERVAL seconds, Retry-After is respected.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from quran_reels.config import Config
from quran_reels.sources.http import Http

PREVIEW_VERSION = 1
PREVIEW_SECONDS = 4
WIDTH, HEIGHT = 360, 640
CDN_INTERVAL = 5.0            # seconds between two Pixabay CDN downloads (their rate limit)


class Previews:
    def __init__(self, cfg: Config, out: Path, enabled: bool = True):
        self.cfg = cfg
        self.out = out / "previews"
        self.cache = cfg.cache / "catalog" / "previews"
        self.enabled = enabled and shutil.which("ffmpeg") is not None
        self.notes: list[str] = []
        if enabled and not self.enabled:
            self.notes.append("ffmpeg absent : aperçus des clips non construits")
        self._http: Http | None = None
        self._cdn: Http | None = None

    def _get(self, url: str, dest: Path) -> Path:
        if "pixabay.com" in url:
            self._cdn = self._cdn or Http(min_interval=CDN_INTERVAL, timeout=180)
            return self._cdn.download(url, dest, min_bytes=50_000)
        self._http = self._http or Http(timeout=300)
        return self._http.download(url, dest, min_bytes=50_000)

    def clip(self, key: str, origin: str, url: Any, focus: float = 0.5,
             soften: bool = True) -> dict[str, str] | None:
        """Preview of one clip: {"video": "previews/<key>.mp4", "poster": ...}, or None.

        key: file name on the site; origin: what identifies the footage (stable, without any
        key); url: its file URL, or a function that returns it (called only when needed)."""
        if not self.enabled:
            return None
        s = (self.cfg.backgrounds.get("soften") or {}) if soften else {}
        blur, dim = float(s.get("blur", 0)) * WIDTH / 1080, float(s.get("dim", 0))
        digest = hashlib.sha1(f"{origin}|{focus}|{blur:.3f}|{dim}|{PREVIEW_SECONDS}|"
                              f"{WIDTH}x{HEIGHT}|{PREVIEW_VERSION}".encode()).hexdigest()[:10]
        video = self.cache / f"{key}-{digest}.mp4"
        poster = video.with_suffix(".jpg")
        if not (video.is_file() and poster.is_file()):
            try:
                self._make(key, url, video, poster, focus, blur, dim)
            except Exception as e:     # noqa: BLE001  (one clip never stops the catalogue)
                why = str(e) if isinstance(e, (SystemExit, RuntimeError)) and "key=" not in str(e) \
                    else type(e).__name__
                print(f"warning: preview {key}: {why}", file=sys.stderr)
                self.notes.append(f"aperçu de {key} indisponible ({type(e).__name__})")
                return None
        self.out.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(video, self.out / f"{key}.mp4")
        shutil.copyfile(poster, self.out / f"{key}.jpg")
        return {"video": f"previews/{key}.mp4", "poster": f"previews/{key}.jpg"}

    def _make(self, key: str, url: Any, video: Path, poster: Path, focus: float,
              blur: float, dim: float) -> None:
        loops = sorted((self.cfg.cache / "backgrounds").glob(f"clip-{key}-*.mp4"))
        tmp = self.cache / f".src-{key}.mp4"
        if loops:                                  # the reel's own loop: already 9:16, soft
            source, crop, look = loops[-1], "", ""
        else:
            target = url() if callable(url) else url
            if not target:
                raise RuntimeError("no file URL")
            source = self._get(str(target), tmp)
            crop = (f"crop='min(iw,ih*{WIDTH}/{HEIGHT})':'min(ih,iw*{HEIGHT}/{WIDTH})':"
                    f"'(iw-ow)*{focus}':'(ih-oh)/2',")
            look = f"gblur=sigma={blur:.2f}," if blur > 0 else ""
            if dim > 0:
                k = 1 - dim
                look += f"colorchannelmixer=rr={k}:gg={k}:bb={k},"
        video.parent.mkdir(parents=True, exist_ok=True)
        part = video.with_name(f".{video.name}")
        try:
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-ss", "0.5", "-t", str(PREVIEW_SECONDS),
                 "-i", str(source), "-an",
                 "-vf", (f"{crop}scale={WIDTH}:{HEIGHT}:flags=lanczos,{look}fps=24,setsar=1,"
                         "format=yuv420p"),
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-movflags", "+faststart",
                 "-f", "mp4", str(part)], check=True, capture_output=True)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(part), "-frames:v", "1",
                            "-q:v", "6", str(poster)], check=True, capture_output=True)
            part.replace(video)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"ffmpeg: {(e.stderr or b'').decode(errors='replace')[-200:]}")
        finally:
            part.unlink(missing_ok=True)
            tmp.unlink(missing_ok=True)
