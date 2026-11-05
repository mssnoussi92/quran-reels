"""Recitations published only as one file per surah (archive.org), split into ayahs.

No ayah timing exists for these recordings, and pauses alone do not find the ayahs: Omar
Hisham joins some ayahs without a breath and repeats others (114: ayahs 2 and 3 in one
breath, ayah 6 twice). So the split is found by speech recognition (sources/recognition.py):

1. the words recognised in the file, with their times, are aligned with the ayahs' Uthmani
   text: where each ayah's first word starts (a repetition stays with its ayah);
2. each cut goes to the quietest moment near that time: a silence, or a dip of the loudness
   envelope (reverb keeps the gaps above any silence threshold); a cut whose start was not
   recognised is placed in proportion to the reference lengths (Alafasy);
3. every segment is recognised again and compared with its ayah: one that does not match
   stops everything. Wrong text on screen is worse than no video.

The verified split is committed in config/splits/<reciter>/SSS.json (times only), so the
daily pipeline needs neither the model nor the check: `quran-reels split <surah>` makes it.
Same interface as EveryAyah (fetch, basmala, url, seconds…); segments are cut losslessly to
FLAC, which the renderer decodes like the MP3s.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

import numpy as np

from quran_reels.models import AyahRef
from quran_reels.sources.http import Http, read_json, write_json

NOISE = "-35dB"          # silence threshold
MIN_PAUSE = 0.3          # shortest silence that counts (seconds)
FRAME = 0.02             # loudness envelope: 20 ms frames, smoothed over 100 ms
MIN_DIP = 2.0            # dips at least this many dB below the speech within 1 s
WINDOW = (1.2, 0.8)      # a cut is looked for this long before / after the ayah's first word
PAD = 0.25               # quiet kept before and after each ayah
MAX_PAUSE = 2.0          # weight of a pause: its length, or its depth / 10 dB, capped
MIN_MATCH = 0.85         # a segment's recognised text must match its ayah this well
RATE = 16000


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
    def middle(self) -> float:
        return (self.start + self.end) / 2

    @property
    def weight(self) -> float:
        return min(self.length if self.depth is None else self.depth / 10, MAX_PAUSE)


def decode(path: Path) -> np.ndarray:
    """Mono 16 kHz samples, as the recogniser wants them."""
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-ac", "1",
                          "-ar", str(RATE), "-f", "f32le", "-"], capture_output=True,
                         check=True).stdout
    return np.frombuffer(raw, np.float32)


def envelope(samples: np.ndarray) -> np.ndarray:
    """Loudness in dB per FRAME, smoothed over 5 frames."""
    size = int(RATE * FRAME)
    n = len(samples) // size
    rms = np.sqrt((samples[:n * size].reshape(n, size).astype(np.float64) ** 2).mean(axis=1)
                  + 1e-10)
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


def estimates(starts: list[float | None], speech: tuple[float, float],
              expected: list[float]) -> list[float]:
    """Where each cut should be (before segments 1..n-1): the recognised start of the
    segment when plausible (increasing, inside the speech, not at its very start: a first word
    can swallow the basmala), otherwise in proportion to the reference lengths between the
    known cuts around it."""
    n = len(expected)
    known, last = {0: speech[0]}, speech[0]
    for k in range(1, n):
        t = starts[k]
        if t is not None and last + 0.5 < t < speech[1] - 0.5:
            known[k], last = t, t
    known[n] = speech[1]
    keys = sorted(known)
    est = dict(known)
    for a, b in pairwise(keys):
        t, total = known[a], sum(expected[a:b])
        for k in range(a + 1, b):
            t += (known[b] - known[a]) * expected[k - 1] / total
            est[k] = t
    return [est[k] for k in range(1, n)]


def snap(cuts: list[float], candidates: list[Pause], speech: tuple[float, float]) -> list[Pause]:
    """The quiet moment chosen for each cut: the strongest pause near it, in order."""
    chosen, after = [], speech[0]
    for e in cuts:
        near = [p for p in candidates
                if p.middle > after and e - WINDOW[0] <= p.middle <= e + WINDOW[1]]
        p = max(near, key=lambda p: p.weight - abs(p.middle - e) / 0.4) if near else Pause(e, e)
        chosen.append(p)
        after = p.middle
    return chosen


def bounds(chosen: list[Pause], speech: tuple[float, float], total: float
           ) -> list[tuple[float, float]]:
    start = max(speech[0] - PAD, 0.0)
    out = []
    for p in chosen:
        out.append((start, min(p.start + PAD, p.middle)))
        start = max(p.end - PAD, p.middle)
    out.append((start, min(speech[1] + PAD, total)))
    return [(round(a, 3), round(b, 3)) for a, b in out]


def speech_span(silences: list[Pause], total: float) -> tuple[float, float]:
    start = silences[0].end if silences and silences[0].start <= 0.05 else 0.0
    end = silences[-1].start if silences and silences[-1].end >= total - 0.05 else total
    return start, end


def find_split(audio: Path, labels: list[str], texts: list[str], expected: list[float],
               recognizer) -> tuple[dict[str, tuple[float, float]], dict[str, float]]:
    """Segments {label: (start, end)} and how well each one's recognised text matches."""
    from quran_reels.sources.recognition import ayah_starts, heard_matches

    samples = decode(audio)
    total = len(samples) / RATE
    silences, _ = pauses(audio)
    speech = speech_span(silences, total)
    starts = ayah_starts([t.split() for t in texts], recognizer.words(samples))
    candidates = sorted([p for p in silences if speech[0] < p.middle < speech[1]]
                        + dips(envelope(samples), MIN_DIP), key=lambda p: p.start)
    cut = bounds(snap(estimates(starts, speech, expected), candidates, speech), speech, total)
    scores, wrong = {}, []
    for i, (label, text, (a, b)) in enumerate(zip(labels, texts, cut)):
        heard = recognizer.text(samples[int(a * RATE):int(b * RATE)])
        before = texts[i - 1] if i else ""
        after = texts[i + 1] if i + 1 < len(texts) else ""
        scores[label] = round(heard_matches(heard, text, before, after), 2)
        if scores[label] < MIN_MATCH:
            wrong.append(f"{label} ({scores[label]:.2f})")
    if wrong:
        raise SplitError(f"segments not recognised as their ayah: {', '.join(wrong)}")
    return dict(zip(labels, cut)), scores


class SurahFiles:
    """One file per surah ({surah:03d} in `url`), split into the basmala and the ayahs.

    The file of every surah but 1 and 9 starts with the basmala; Al-Fatiha's is its first
    ayah. reference(surah) gives Alafasy's ayah lengths (reference(1)[1] the basmala's), and
    texts(surah) the Uthmani text of {"basmala" | "<ayah>"}. Splits are read from `splits`
    (committed); a missing one is made with the recogniser, then written there.
    """

    def __init__(self, cache: Path, http: Http, reciter: str, url: str, splits: Path,
                 reference: Callable[[int], dict[int, float]],
                 texts: Callable[[int], dict[str, str]]):
        self.dir = cache / "surah-audio" / reciter
        self.splits = splits
        self.http = http
        self.reciter = reciter
        self.template = url
        self.reference = reference
        self.texts = texts
        self._recognizer = None

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

    def audio(self, surah: int) -> Path:
        path = self.dir / f"{surah:03d}.mp3"
        if not path.is_file():
            self.http.download(self.surah_url(surah), path, min_bytes=20_000)
        return path

    def split_path(self, surah: int) -> Path:
        return self.splits / f"{surah:03d}.json"

    def segments(self, surah: int) -> dict[str, tuple[float, float]]:
        """{"basmala" | "<ayah>": (start, end)} for a surah, from its committed split."""
        path = self.split_path(surah)
        if not path.is_file():
            self.make_split(surah)
        return {k: tuple(v) for k, v in read_json(path)["segments"].items()}

    def make_split(self, surah: int) -> dict:
        """Find and check the split by speech recognition, write it to `splits`."""
        from quran_reels.sources.recognition import MODEL, Recognizer

        texts = self.texts(surah)
        labels = list(texts)
        ref = self.reference(surah)
        expected = [self.reference(1)[1] if k == "basmala" else ref[int(k)] for k in labels]
        if self._recognizer is None:
            self._recognizer = Recognizer()
        try:
            segments, scores = find_split(self.audio(surah), labels, list(texts.values()),
                                          expected, self._recognizer)
        except SplitError as e:
            raise SystemExit(f"{self.reciter}, surah {surah}: {e}; nothing rendered") from e
        print(f"{self.reciter} {surah}: " + ", ".join(
            f"{k} {b - a:.1f} s ({scores[k]:.2f})" for k, (a, b) in segments.items()),
            file=sys.stderr)
        data = {"source": self.surah_url(surah),
                "method": f"word times recognised by {MODEL}, aligned on the Uthmani text, "
                          "cut at the quietest moment nearby; each segment recognised again",
                "segments": segments, "match": scores}
        write_json(self.split_path(surah), data)
        return data

    def _cut(self, surah: int, label: str) -> Path:
        dest = self.dir / f"{surah:03d}{label.zfill(3) if label != 'basmala' else 'bsm'}.flac"
        if not dest.is_file():
            a, b = self.segments(surah)[label]
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{a:.3f}",
                            "-to", f"{b:.3f}", "-i", str(self.audio(surah)),
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
