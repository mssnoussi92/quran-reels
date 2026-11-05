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

The verified split (times only) is in config/splits/<reciter>/SSS.json (committed) or on the
state branch (splits/, written each night by the prepare workflow for the coming week), so
the daily pipeline needs neither the model nor the check: `quran-reels split` makes it.
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
MIN_MATCH = 0.75         # a segment's recognised text must match its ayah this well
                         # (no neighbour's word either: recognition.heard_matches)
PUBLISHED_WINDOW = (0.6, 0.4)   # around a published start: cut close to it
TRIES = 5                # quiet moments tried for one cut before giving up
CUT_WINDOW = 3.0         # seconds on each side of a cut, recognised together (check_cut)
CUT_TOLERANCE = 0.2      # a word may start this much on the wrong side (timestamp precision)
CUT_CONTEXT = 4          # words of each ayah next to a cut
LONG_WORDS = 15          # ayahs at least this long keep their word times (several screens)
RATE = 16000
MP3QURAN = "https://www.mp3quran.net/api/v3"


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


def duration(path: Path) -> float:
    """Length of an audio or video file in seconds, from ffmpeg's header read (no ffprobe:
    the workflows use the static ffmpeg of imageio-ffmpeg, which comes without it)."""
    out = subprocess.run(["ffmpeg", "-nostdin", "-i", str(path)], capture_output=True,
                         text=True, check=False).stderr      # no output file: exit code 1
    h, m, sec = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out).groups()
    return int(h) * 3600 + int(m) * 60 + float(sec)


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


def ranked(e: float, candidates: list[Pause], after: float,
           window: tuple[float, float] = WINDOW, scale: float = 0.4) -> list[Pause]:
    """Quiet moments for a cut expected at e, best first (strong and close), then e itself."""
    near = [p for p in candidates if p.middle > after and e - window[0] <= p.middle <= e + window[1]]
    near.sort(key=lambda p: -(p.weight - abs(p.middle - e) / scale))
    e = max(e, after + 0.1)            # never before the previous cut
    return near + [Pause(e, e)]


def snap(cuts: list[float], candidates: list[Pause], speech: tuple[float, float]) -> list[Pause]:
    """The quiet moment chosen for each cut: the strongest pause near it, in order."""
    chosen, after = [], speech[0]
    for e in cuts:
        p = ranked(e, candidates, after)[0]
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


def _heard(recognizer, samples: np.ndarray, lo: float, hi: float) -> list:
    """Words recognised between lo and hi (seconds), with times in the recording."""
    from quran_reels.sources.recognition import Word

    return [Word(w.text, w.start + lo, w.end + lo)
            for w in recognizer.words(samples[int(lo * RATE):int(hi * RATE)])]


def check_cut(recognizer, samples: np.ndarray, end: float, start: float, left: str,
              right: str) -> str:
    """'' when a cut keeps each ayah's words on its side (the left segment ends at `end`, the
    right one starts at `start`), else what is wrong. The words next to the cut are recognised
    together, CUT_WINDOW seconds on each side: with both sides heard, a short word is not lost,
    as it was in the recognition of each segment alone («لا» of 2:256 at the end of Budair's
    2:255, «Alif» of 2:1 at the end of his basmala, 2026-11-05)."""
    from quran_reels.sources.recognition import align_words

    lo, hi = max(0.0, end - CUT_WINDOW), min(len(samples) / RATE, start + CUT_WINDOW)
    lw, rw = left.split()[-CUT_CONTEXT:], right.split()[:CUT_CONTEXT]
    matched = align_words(lw + rw, _heard(recognizer, samples, lo, hi))
    last_left = next((w for w in reversed(matched[:len(lw)]) if w is not None), None)
    first_right = next((w for w in matched[len(lw):] if w is not None), None)
    problems = []
    if first_right is not None and first_right.start < end - CUT_TOLERANCE:
        problems.append(f"«{first_right.text}» of the next ayah is before the cut")
    if last_left is not None and last_left.start > start + CUT_TOLERANCE:
        problems.append(f"«{last_left.text}» is after the cut")
    return "; ".join(problems)


def word_times(recognizer, samples: np.ndarray, a: float, b: float, text: str
               ) -> list[float | None]:
    """When each word of the ayah starts in its segment (seconds from a), None if unheard."""
    from quran_reels.sources.recognition import align_words

    return [None if w is None else round(max(w.start - a, 0.0), 2)
            for w in align_words(text.split(), _heard(recognizer, samples, a, b))]


BASMALA_MIN = 2.0         # seconds: no basmala is shorter (Budair 3.7, the quickest ≈ 3)


def basmala_stop(silences: list[Pause], speech_start: float, before: float) -> Pause | None:
    """The stop after the basmala: the last real silence (silencedetect) before ayah 1's
    estimated start. Reciters always stop there, while the published start of ayah 1 can be
    late: Budair's 2:1 on mp3quran starts after «Alif», and the cut near it left «A» at the
    end of the basmala, heard before every passage of Al-Baqarah (2:255, 2026-11-05)."""
    stops = [p for p in silences
             if speech_start + BASMALA_MIN <= p.middle <= before and p.length >= MIN_PAUSE]
    return stops[-1] if stops else None


def find_split(audio: Path, labels: list[str], texts: list[str], expected: list[float],
               recognizer, starts: list[float | None] | None = None,
               check: set[str] | None = None, end: float | None = None
               ) -> tuple[dict[str, tuple[float, float]], dict[str, float]]:
    """Segments {label: (start, end)} and how well each checked one's recognised text
    matches (check: these labels only, e.g. one passage of a long surah; None: all).
    starts: where each segment starts when published (mp3quran's timings), otherwise found
    from the recognised words. end: where the last ayah ends when published: the recording
    may go on with words that are not the surah («صدق الله العظيم»)."""
    from quran_reels.sources.recognition import ayah_starts, heard_matches

    samples = decode(audio)
    total = len(samples) / RATE
    silences, _ = pauses(audio)
    speech = speech_span(silences, total)
    published = starts is not None
    if starts is None:
        starts = ayah_starts([t.split() for t in texts], recognizer.words(samples))
    candidates = sorted([p for p in silences if speech[0] < p.middle < speech[1]]
                        + dips(envelope(samples), MIN_DIP), key=lambda p: p.start)
    if end is not None and end < speech[1] - 0.5:
        near = [p for p in candidates if end - WINDOW[1] <= p.middle <= end + WINDOW[0]]
        stop = max(near, key=lambda p: p.weight - abs(p.middle - end) / 0.4) if near else None
        speech = (speech[0], stop.start + min(PAD, stop.length / 2) - PAD if stop else end)
    window, scale = (PUBLISHED_WINDOW, 0.25) if published else (WINDOW, 0.4)
    heard: dict[tuple[str, float, float], float] = {}

    def score(i: int, a: float, b: float) -> float:
        key = (labels[i], round(a, 3), round(b, 3))
        if key not in heard:
            text = recognizer.text(samples[int(a * RATE):int(b * RATE)])
            heard[key] = round(heard_matches(text, texts[i], texts[i - 1] if i else "",
                                             texts[i + 1] if i + 1 < len(texts) else ""), 2)
        return heard[key]

    def wanted(i: int) -> bool:
        return check is None or labels[i] in check

    cuts: dict[tuple[int, float, float], str] = {}

    def cut_problem(k: int, p: Pause) -> str:
        """check_cut between labels k and k+1 for the quiet moment p."""
        end, start = min(p.start + PAD, p.middle), max(p.end - PAD, p.middle)
        key = (k, round(end, 3), round(start, 3))
        if key not in cuts:
            cuts[key] = check_cut(recognizer, samples, end, start, texts[k], texts[k + 1])
        return cuts[key]

    # Left to right: each cut at the best quiet moment near its estimate whose segment before
    # it is recognised as its ayah (no word of the next one, none of its own missing).
    chosen, after = [], speech[0]
    seg_start = max(speech[0] - PAD, 0.0)
    for k, e in enumerate(estimates(starts, speech, expected)):
        options = ranked(e, candidates, after, window, scale)
        if k == 0 and labels[0] == "basmala":
            stop = basmala_stop(silences, speech[0], e + window[1])
            if stop is not None:
                options = [stop, *[o for o in options if o is not stop]]
        p = options[0]
        if wanted(k) or wanted(k + 1):
            for option in options[:TRIES]:
                if score(k, seg_start, min(option.start + PAD, option.middle)) >= MIN_MATCH \
                        and not cut_problem(k, option):
                    p = option
                    break
        chosen.append(p)
        after = p.middle
        seg_start = max(p.end - PAD, p.middle)
    cut = bounds(chosen, speech, total)
    edges: dict[int, str] = {}           # a cut that moves words of one ayah to the other
    for k, p in enumerate(chosen):
        if wanted(k) or wanted(k + 1):
            problem = cut_problem(k, p)
            if problem:
                edges[k] = edges[k + 1] = f"cut {labels[k]}|{labels[k + 1]}: {problem}"
    scores, wrong = {}, []
    for i, (a, b) in enumerate(cut):
        if not wanted(i):
            continue
        scores[labels[i]] = 0.0 if i in edges else score(i, a, b)
        if scores[labels[i]] < MIN_MATCH:
            wrong.append(f"{labels[i]} ({edges.get(i) or f'{scores[labels[i]]:.2f}'})")
    if wrong and len(wrong) == len(scores):
        raise SplitError(f"segments not recognised as their ayah: {', '.join(wrong)}")
    if wrong:       # the others stay usable: a passage needs all of its own ayahs checked
        print(f"not recognised as their ayah: {', '.join(wrong)} (left unchecked)",
              file=sys.stderr)
    return dict(zip(labels, cut)), {k: v for k, v in scores.items() if v >= MIN_MATCH}


class SurahFiles:
    """One file per surah ({surah:03d} in `url`), split into the basmala and the ayahs.

    The file of every surah but 1 and 9 starts with the basmala; Al-Fatiha's is its first
    ayah. reference(surah) gives Alafasy's ayah lengths (reference(1)[1] the basmala's), and
    texts(surah) the Uthmani text of {"basmala" | "<ayah>"}. Splits are read from the
    folders `splits` (the one with the most checked ayahs wins) and written to the last one.
    """

    def __init__(self, cache: Path, http: Http, reciter: str, url: str, splits: list[Path],
                 reference: Callable[[int], dict[int, float]],
                 texts: Callable[[int], dict[str, str]], mp3quran: int | None = None,
                 max_minutes: float | None = None):
        self.dir = cache / "surah-audio" / reciter
        self.splits = splits
        self.http = http
        self.reciter = reciter
        self.template = url
        self.reference = reference
        self.texts = texts
        self.mp3quran = mp3quran      # read id of mp3quran.net's ayah timings, if published
        self.max_minutes = max_minutes  # longer surah files are not split (word pass too long)
        self._recognizer = None

    def published_timing(self, surah: int) -> dict[int, tuple[float, float]]:
        """mp3quran.net's (start, end) of each ayah, in seconds (cached): volunteers' marks,
        a good first estimate that the split still snaps and checks."""
        path = self.dir / f"timing-{surah:03d}.json"
        if not path.is_file():
            url = f"{MP3QURAN}/ayat_timing"
            rows = self.http.json(url, surah=surah, read=self.mp3quran)
            write_json(path, {"source": f"{url}?surah={surah}&read={self.mp3quran}",
                              "ayahs": {str(r["ayah"]): [r["start_time"] / 1000, r["end_time"] / 1000]
                                        for r in rows if int(r["ayah"]) > 0}})
        return {int(a): tuple(t) for a, t in read_json(path)["ayahs"].items()}

    def planned_seconds(self, surah: int) -> dict[str, float]:
        """Length of the basmala and of each ayah, for choosing a reciter: the committed
        split, or else mp3quran's timings (no download)."""
        if self.split_path(surah).is_file():
            return {k: b - a for k, (a, b) in self.segments(surah).items()}
        if self.mp3quran is None:
            raise SystemExit(f"{self.reciter}: surah {surah} not split yet (quran-reels split)")
        timing = self.published_timing(surah)
        out = {str(a): t[1] - t[0] for a, t in timing.items()}
        if surah not in (1, 9):
            out = {"basmala": max(timing[1][0] - 0.3, 0.0), **out}
        return out

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
        """The split file to read: the one with the most checked ayahs, or where to write."""
        found = [d / f"{surah:03d}.json" for d in self.splits if (d / f"{surah:03d}.json").is_file()]
        if not found:
            return self.splits[-1] / f"{surah:03d}.json"
        return max(found, key=lambda f: len(read_json(f).get("match", {})))

    def segments(self, surah: int) -> dict[str, tuple[float, float]]:
        """{"basmala" | "<ayah>": (start, end)} for a surah, from its committed split."""
        path = self.split_path(surah)
        if not path.is_file():
            self.make_split(surah)
        return {k: tuple(v) for k, v in read_json(path)["segments"].items()}

    def matches(self, surah: int) -> dict[str, float]:
        """How well each checked segment was recognised as its ayah (unchecked: absent)."""
        path = self.split_path(surah)
        return read_json(path).get("match", {}) if path.is_file() else {}

    def word_starts(self, surah: int, ayah: int) -> list[float | None] | None:
        """When each word (arabic.words) of a long ayah starts in its segment, if known."""
        path = self.split_path(surah)
        return read_json(path).get("words", {}).get(str(ayah)) if path.is_file() else None

    def checked(self, surah: int, label: str) -> None:
        if self.matches(surah).get(label, 0.0) < MIN_MATCH:
            what = "the basmala" if label == "basmala" else f"{surah}:{label}"
            raise SystemExit(f"{self.reciter}: {what} is not checked; nothing rendered "
                             f"(quran-reels split {surah}" + ("" if label == "basmala" else
                                                              f":{label}") + ")")

    def make_split(self, surah: int, check: set[str] | None = None) -> dict:
        """Find the split, check its segments by speech recognition (`check`: these only;
        those already checked with the same cuts are kept), write it to `splits`."""
        from quran_reels.sources.recognition import MODEL, Recognizer

        if self.max_minutes and duration(self.audio(surah)) > self.max_minutes * 60:
            raise SystemExit(f"{self.reciter}, surah {surah}: recording longer than "
                             f"{self.max_minutes:g} min, not split")
        texts = self.texts(surah)
        labels = list(texts)
        ref = self.reference(surah)
        expected = [self.reference(1)[1] if k == "basmala" else ref[int(k)] for k in labels]
        starts, timing = None, {}
        if self.mp3quran is not None:
            # An ayah missing from the published timing (Al-Minshawi's 9:129) is placed like
            # an unrecognised one: in proportion, its length from the reference at this pace.
            timing = self.published_timing(surah)
            timed = [a for a in map(int, (k for k in labels if k != "basmala")) if a in timing]
            pace = (sum(timing[a][1] - timing[a][0] for a in timed)
                    / max(sum(ref[a] for a in timed), 1e-6)) if timed else 1.0
            starts = [timing[int(k)][0] if k != "basmala" and int(k) in timing else None
                      for k in labels]
            expected = [(timing[1][0] if 1 in timing else expected[i]) if k == "basmala"
                        else timing[int(k)][1] - timing[int(k)][0] if int(k) in timing
                        else ref[int(k)] * pace
                        for i, k in enumerate(labels)]
        if self._recognizer is None:
            self._recognizer = Recognizer()
        before = read_json(self.split_path(surah)) if self.split_path(surah).is_file() else {}
        try:
            segments, scores = find_split(self.audio(surah), labels, list(texts.values()),
                                          expected, self._recognizer, starts, check,
                                          end=timing[int(labels[-1])][1]
                                          if starts and int(labels[-1]) in timing else None)
        except SplitError as e:
            raise SystemExit(f"{self.reciter}, surah {surah}: {e}; nothing rendered") from e
        old_segments = {k: tuple(v) for k, v in before.get("segments", {}).items()}
        for k, score in before.get("match", {}).items():   # same cuts: still checked
            if k not in scores and old_segments.get(k) == tuple(segments[k]):
                scores[k] = score
        scores = {k: scores[k] for k in labels if k in scores}
        print(f"{self.reciter} {surah}: " + ", ".join(
            f"{k} {b - a:.1f} s ({scores[k]:.2f})" for k, (a, b) in segments.items()
            if k in scores), file=sys.stderr)
        data = {"source": self.surah_url(surah),
                "method": (f"ayah starts from mp3quran.net (read {self.mp3quran})"
                           if self.mp3quran is not None else
                           f"word times recognised by {MODEL}, aligned on the Uthmani text")
                + f", cut at the quietest moment nearby; each segment recognised by {MODEL}",
                "segments": segments, "match": scores}
        words = self._long_words(surah, texts, segments, scores, before)
        if words:
            data["words"] = words
        write_json(self.splits[-1] / f"{surah:03d}.json", data)
        return data

    def _long_words(self, surah: int, texts: dict[str, str], segments: dict, scores: dict,
                    before: dict) -> dict[str, list[float | None]]:
        """Word times of the checked ayahs of LONG_WORDS words or more (shown on several
        screens, render/): kept from `before` when the segment did not move."""
        old_words = before.get("words", {})
        old_segments = {k: tuple(v) for k, v in before.get("segments", {}).items()}
        samples, out = None, {}
        for k in scores:
            if k == "basmala" or len(texts[k].split()) < LONG_WORDS:
                continue
            if k in old_words and old_segments.get(k) == tuple(segments[k]):
                out[k] = old_words[k]
                continue
            samples = decode(self.audio(surah)) if samples is None else samples
            a, b = segments[k]
            out[k] = word_times(self._recognizer, samples, a, b, texts[k])
        return out

    def audit(self, surah: int) -> dict[str, str]:
        """Check the cuts of the committed split next to a checked segment (check_cut), and
        add the word times of its long ayahs. {label: problem} for the segments to split
        again (quran-reels split --audit --fix)."""
        from quran_reels.sources.recognition import Recognizer

        path = self.split_path(surah)
        data = read_json(path)
        seg, match = data["segments"], data.get("match", {})
        texts = self.texts(surah)
        labels = [k for k in texts if k in seg]
        if self._recognizer is None:
            self._recognizer = Recognizer()
        samples = decode(self.audio(surah))
        problems: dict[str, str] = {}
        for left, right in pairwise(labels):
            if match.get(left, 0) < MIN_MATCH and match.get(right, 0) < MIN_MATCH:
                continue
            problem = check_cut(self._recognizer, samples, seg[left][1], seg[right][0],
                                texts[left], texts[right])
            if problem:
                problems[left] = problems[right] = f"cut {left}|{right}: {problem}"
        words = self._long_words(surah, texts, seg, {k: v for k, v in match.items()
                                                     if k not in problems}, data)
        if words != data.get("words", {}):
            data["words"] = words
            write_json(path, data)
        return problems

    def _cut(self, surah: int, label: str) -> Path:
        """The segment as a FLAC, named after its cut times: a split made again (the basmala
        of Budair's surah 2, 2026-11-05) never reuses an old cut from the Actions cache."""
        self.checked(surah, label)
        a, b = self.segments(surah)[label]
        name = label.zfill(3) if label != "basmala" else "bsm"
        dest = self.dir / f"{surah:03d}{name}-{round(a * 1000)}-{round(b * 1000)}.flac"
        if not dest.is_file():
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
