"""Recitations published only as one file per surah (archive.org), split into ayahs.

No ayah timing exists for these recordings, so the ayahs are found on the pauses: ffmpeg's
silencedetect for clean studio files, or, when reverb fills the gaps, the dips of the loudness
envelope (deepest quiet moments, in dB below the speech around them). The N - 1 cuts (N = the
basmala at the start of the file, when it has one, then every ayah) are chosen among them by
dynamic programming: a marked pause close to where the reference recording (Alafasy,
Quran.com timings) ends that ayah, scaled to this recording's length. Every segment is then checked against its expected length: a split
that does not fit stops the render. Wrong text on screen is worse than no video.

Same interface as EveryAyah (fetch, fetch_file, url, seconds…); segments are cut losslessly
to FLAC, which the renderer decodes like the MP3s.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from quran_reels.models import AyahRef
from quran_reels.sources.http import Http, read_json, write_json

NOISE = "-35dB"          # silence threshold
MIN_PAUSE = 0.3          # shortest pause that can separate two ayahs (seconds)
FRAME = 0.02             # loudness envelope: 20 ms frames, smoothed over 100 ms
DIP_DEPTHS = (8.0, 5.0)  # dips at least this many dB below the speech within 1 s, in turn
PAD = 0.25               # silence kept before and after each ayah
DEVIATION = 1.0          # cost of being one ayah length away from the expected cut…
PAUSE_WEIGHT = 1.0       # …against one second more of pause, or 10 dB more of dip
MAX_PAUSE = 2.0          # (capped)
TOLERANCE = (0.55, 1.5)  # a segment's length / its expected length must stay inside


class SplitError(RuntimeError):
    pass


@dataclass(frozen=True)
class Pause:
    start: float
    end: float
    depth: float | None = None      # dips: dB below the speech around

    @property
    def length(self) -> float:
        return self.end - self.start

    @property
    def weight(self) -> float:
        return min(self.length if self.depth is None else self.depth / 10, MAX_PAUSE)

    @property
    def middle(self) -> float:
        return (self.start + self.end) / 2


def envelope(path: Path) -> np.ndarray:
    """Loudness in dB per FRAME, smoothed over 5 frames."""
    rate = 16000
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-ac", "1",
                          "-ar", str(rate), "-f", "s16le", "-"], capture_output=True,
                         check=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    size = int(rate * FRAME)
    n = len(x) // size
    rms = np.sqrt((x[:n * size].reshape(n, size) ** 2).mean(axis=1) + 1e-10)
    return np.convolve(20 * np.log10(rms), np.ones(5) / 5, mode="same")


def dips(env: np.ndarray, min_depth: float, window: float = 0.4,
         context: float = 1.0) -> list[Pause]:
    """Local minima of the envelope at least min_depth dB below the loudest point within
    `context` seconds on both sides; each spans the frames within 3 dB of its minimum."""
    w, c, n = int(window / FRAME), int(context / FRAME), len(env)
    found: list[Pause] = []
    last = -1
    for i in range(c, n - c):
        if i <= last or env[i] > env[max(0, i - w):i + w + 1].min():
            continue
        depth = min(env[i - c:i + 1].max(), env[i:i + c + 1].max()) - env[i]
        if depth < min_depth:
            continue
        a, b = i, i
        while a > 0 and env[a - 1] <= env[i] + 3:
            a -= 1
        while b < n - 1 and env[b + 1] <= env[i] + 3:
            b += 1
        found.append(Pause(a * FRAME, (b + 1) * FRAME, depth=round(float(depth), 1)))
        last = b
    return found


def pauses(path: Path, noise: str = NOISE, min_pause: float = MIN_PAUSE) -> tuple[list[Pause], float]:
    """Silences of an audio file, and its length in seconds."""
    out = subprocess.run(["ffmpeg", "-nostdin", "-v", "info", "-i", str(path), "-af",
                          f"silencedetect=noise={noise}:d={min_pause}", "-f", "null", "-"],
                         capture_output=True, text=True, check=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", out)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
    times = re.findall(r"time=(\d+):(\d+):([\d.]+)", out)
    h, m, s = times[-1]
    total = int(h) * 3600 + int(m) * 60 + float(s)
    if len(ends) < len(starts):              # silence until the end of the file
        ends.append(total)
    return [Pause(max(a, 0.0), b) for a, b in zip(starts, ends)], total


def split(found: list[Pause], total: float, expected: list[float]) -> list[tuple[float, float]]:
    """Start and end of each of len(expected) segments; expected = reference lengths, in order."""
    n = len(expected)
    speech_start = found[0].end if found and found[0].start <= 0.05 else 0.0
    speech_end = found[-1].start if found and found[-1].end >= total - 0.05 else total
    inner = [p for p in found if speech_start < p.middle < speech_end]
    if len(inner) < n - 1:
        raise SplitError(f"{len(inner)} pauses for {n} segments")
    scale = (speech_end - speech_start) / sum(expected)
    cuts_expected, t = [], speech_start
    for e in expected[:-1]:
        t += e * scale
        cuts_expected.append(t)

    def cost(j: int, k: int) -> float:     # pause j as cut k
        width = (expected[k] + expected[k + 1]) / 2 * scale
        return (DEVIATION * abs(inner[j].middle - cuts_expected[k]) / width
                - PAUSE_WEIGHT * inner[j].weight)

    m, inf = len(inner), float("inf")
    best = [[inf] * m for _ in range(n - 1)]
    back = [[-1] * m for _ in range(n - 1)]
    for k in range(n - 1):
        run, arg = inf, -1                  # best of row k - 1 over pauses before j
        for j in range(m):
            if k == 0:
                best[k][j] = cost(j, k)
            else:
                if j > 0 and best[k - 1][j - 1] < run:
                    run, arg = best[k - 1][j - 1], j - 1
                if arg >= 0:
                    best[k][j], back[k][j] = run + cost(j, k), arg
    chosen: list[Pause] = []
    if n > 1:
        j = min(range(m), key=lambda x: best[n - 2][x])
        for k in range(n - 2, -1, -1):
            chosen.append(inner[j])
            j = back[k][j]
        chosen.reverse()

    bounds = [max(speech_start - PAD, 0.0)]
    segments = []
    for p in chosen:
        segments.append((bounds[-1], min(p.start + PAD, p.middle)))
        bounds.append(max(p.end - PAD, p.middle))
    segments.append((bounds[-1], min(speech_end + PAD, total)))
    for i, ((a, b), e) in enumerate(zip(segments, expected)):
        ratio = (b - a - 2 * PAD) / (e * scale)
        if not TOLERANCE[0] <= ratio <= TOLERANCE[1]:
            raise SplitError(f"segment {i + 1}/{n}: {b - a:.1f} s for {e * scale:.1f} s expected")
    return [(round(a, 3), round(b, 3)) for a, b in segments]


class SurahFiles:
    """One file per surah ({surah:03d} in `url`), split into the basmala and the ayahs.

    reference(surah) gives the reference lengths of the surah's ayahs (Alafasy), and
    reference(1)[1] the basmala's. The file of every surah but 1 and 9 starts with the basmala
    (`basmala_in_file`); Al-Fatiha's basmala is its first ayah.
    """

    def __init__(self, cache: Path, http: Http, reciter: str, url: str,
                 reference: Callable[[int], dict[int, float]], verses: Callable[[int], int]):
        self.dir = cache / "surah-audio" / reciter
        self.http = http
        self.reciter = reciter
        self.template = url
        self.reference = reference
        self.verses = verses

    @property
    def base_url(self) -> str:
        return self.template.rsplit("/", 1)[0] + "/"

    def surah_url(self, surah: int) -> str:
        return self.template.format(surah=surah)

    def url(self, ref: AyahRef) -> str:
        return self.surah_url(ref.surah)

    def file_url(self, stem: str) -> str:
        return self.url(self._ref(stem))

    @staticmethod
    def _ref(stem: str) -> AyahRef:
        if not re.fullmatch(r"\d{6}", stem):
            raise SystemExit(f"reciter with one file per surah: basmala must be an ayah like "
                             f"'001001', not {stem!r}")
        return AyahRef(int(stem[:3]), int(stem[3:]))

    def segments(self, surah: int) -> dict[str, tuple[float, float]]:
        """{"basmala" | "<ayah>": (start, end)} for a surah, cached."""
        path = self.dir / f"split-{surah:03d}.json"
        if path.is_file():
            return {k: tuple(v) for k, v in read_json(path)["segments"].items()}
        audio = self.dir / f"{surah:03d}.mp3"
        if not audio.is_file():
            self.http.download(self.surah_url(surah), audio, min_bytes=20_000)
        ref = self.reference(surah)
        n = self.verses(surah)
        labels = [str(a) for a in range(1, n + 1)]
        expected = [ref[a] for a in range(1, n + 1)]
        if surah not in (1, 9):
            labels.insert(0, "basmala")
            expected.insert(0, self.reference(1)[1])
        silences, total = pauses(audio)
        edges = [p for p in silences if p.start <= 0.05 or p.end >= total - 0.05]
        env = None
        attempts = [("silences", f"silencedetect {NOISE} ≥ {MIN_PAUSE} s", silences)]
        for depth in DIP_DEPTHS:           # clean files first, then reverberant ones
            attempts.append(("dips", f"loudness dips ≥ {depth:g} dB", depth))
        errors = []
        for kind, method, arg in attempts:
            if kind == "dips":
                env = envelope(audio) if env is None else env
                arg = sorted(edges + [p for p in dips(env, arg)
                                      if all(p.end <= e.start or p.start >= e.end for e in edges)],
                             key=lambda p: p.start)
            try:
                cut = split(arg, total, expected)
                break
            except SplitError as e:
                errors.append(f"{method}: {e}")
        else:
            raise SystemExit(f"{self.reciter}, surah {surah}: the ayahs could not be found on the "
                             f"pauses ({'; '.join(errors)}); nothing rendered")
        segments = dict(zip(labels, cut))
        scale = sum(b - a for a, b in cut) / sum(expected)
        print(f"{self.reciter} {surah}: split on {method}: " + ", ".join(
            f"{k} {b - a:.1f} s ({e * scale:.1f})" for k, (a, b), e in zip(labels, cut, expected)),
            file=sys.stderr)
        write_json(path, {"source": self.surah_url(surah), "seconds": round(total, 3),
                          "method": f"{method}, aligned on the reference lengths (Alafasy)",
                          "segments": segments})
        return segments

    def _cut(self, surah: int, label: str) -> Path:
        dest = self.dir / f"{surah:03d}{label.zfill(3) if label != 'basmala' else 'bsm'}.flac"
        if not dest.is_file():
            a, b = self.segments(surah)[label]
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{a:.3f}",
                            "-to", f"{b:.3f}", "-i", str(self.dir / f"{surah:03d}.mp3"),
                            "-c:a", "flac", str(dest)], check=True)
        return dest

    def fetch(self, ref: AyahRef) -> Path:
        return self._cut(ref.surah, str(ref.ayah))

    def fetch_file(self, stem: str) -> Path:
        return self.fetch(self._ref(stem))

    def basmala(self, surah: int, stem: str) -> Path:
        """The basmala at the start of the surah's own file (same recording, and no
        isti'adha, which Al-Fatiha's file may start with); `stem` for surahs 1 and 9."""
        if surah in (1, 9):
            return self.fetch_file(stem)
        return self._cut(surah, "basmala")

    def basmala_url(self, surah: int, stem: str) -> str:
        return self.file_url(stem) if surah in (1, 9) else self.surah_url(surah)

    def seconds(self, surah: int, ayahs: int, kbps: float = 0) -> dict[int, float]:
        segs = self.segments(surah)
        return {a: segs[str(a)][1] - segs[str(a)][0] for a in range(1, ayahs + 1)}

    def file_seconds(self, stem: str, kbps: float = 0) -> float:
        ref = self._ref(stem)
        return self.seconds(ref.surah, ref.ayah)[ref.ayah]
