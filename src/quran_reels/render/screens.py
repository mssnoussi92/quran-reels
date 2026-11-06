"""A long ayah on several screens, each shown while its words are recited.

An ayah whose text needs a scale under MIN_FIT to fit the safe area (2:255 came out at 45 %,
hard to read on a phone) is shown in parts. The Uthmani text is cut after pause marks
(ۚ ۖ ۗ ۛ ۘ ۙ ۜ, the places where a reciter may stop), the translation after sentence ends; both
run through the ayah's clauses in the same order, so parts are paired by their position in
the ayah. Each part appears when its first word is recited: word times found when the recording
was split (sources/surah_audio.py, `words`), else in proportion to the letters before it.

Nothing is rewritten: every part is a contiguous piece of the published text, and the parts
together are the whole ayah.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import pairwise

from quran_reels.arabic import normalize

MIN_FIT = 0.7            # below this text scale, the ayah goes on several screens
MAX_PARTS = 5
MIN_PART_SECONDS = 2.5   # a part shorter than this on screen is merged with its neighbour
PAUSE_MARKS = frozenset("ۖۗۘۙۚۛۜ")
_SENTENCE = re.compile(r"(?<=[.?!;])[\"'”’»)\]]*\s+")
_CLAUSE = re.compile(r"(?<=[,:])\s+|\s+(?=-\s)")


@dataclass(frozen=True)
class Part:
    first: int           # index of its first token (arabic.words)
    end: int             # one past its last token
    translation: str
    start: float         # seconds from the start of the ayah's recitation


def _letters(tokens: list[str]) -> list[int]:
    return [len(normalize(t)) for t in tokens]


def pause_cuts(tokens: list[str]) -> list[int]:
    """Token indices where a part may start: just after a pause mark."""
    return [i + 1 for i, t in enumerate(tokens[:-1]) if t in PAUSE_MARKS]


def translation_pieces(text: str) -> list[str]:
    """Sentences, and within a long one its clauses: the pieces a part is made of."""
    out = []
    for sentence in (s for s in _SENTENCE.split(text.strip()) if s):
        out.extend(p for p in _CLAUSE.split(sentence) if p) if len(sentence) > 140 \
            else out.append(sentence)
    return out


def _group(lengths: list[int], k: int) -> list[int]:
    """Where k contiguous groups start (indices into lengths), as even as possible."""
    n, total = len(lengths), sum(lengths)
    if k >= n:
        return list(range(n))
    acc = [0]
    for x in lengths:
        acc.append(acc[-1] + x)
    best: dict[tuple[int, int], tuple[float, list[int]]] = {}

    def go(i: int, parts: int) -> tuple[float, list[int]]:
        """Cost and starts of splitting lengths[i:] into `parts` groups."""
        if (i, parts) in best:
            return best[(i, parts)]
        if parts == 1:
            res = ((acc[n] - acc[i] - total / k) ** 2, [i])
        else:
            res = (float("inf"), [])
            for j in range(i + 1, n - parts + 2):
                cost, rest = go(j, parts - 1)
                cost += (acc[j] - acc[i] - total / k) ** 2
                if cost < res[0]:
                    res = (cost, [i, *rest])
        best[(i, parts)] = res
        return res

    return go(0, k)[1]


def plan(tokens: list[str], translation: str, k: int, seconds: float,
         word_starts: list[float | None] | None = None) -> list[Part]:
    """The ayah in k parts (fewer if its text has fewer places to cut)."""
    pieces = translation_pieces(translation)
    k = max(1, min(k, len(pieces)))
    if k == 1:
        return [Part(0, len(tokens), translation, 0.0)]
    starts = _group([len(p) for p in pieces], k)
    bounds = [*starts, len(pieces)]
    texts = [" ".join(pieces[a:b]) for a, b in pairwise(bounds)]
    # The Arabic cut for each translation boundary: the pause mark at the closest relative
    # position (by letters), in order; a plain word boundary when there is no mark left.
    letters = _letters(tokens)
    total = max(sum(letters), 1)
    where = [sum(letters[:i]) / total for i in range(len(tokens) + 1)]
    marks = pause_cuts(tokens) or list(range(1, len(tokens)))
    tr_total = max(sum(len(p) for p in pieces), 1)
    cuts, last = [], 0
    for b in starts[1:]:
        q = sum(len(p) for p in pieces[:b]) / tr_total
        options = [c for c in marks if c > last] or [c for c in range(last + 1, len(tokens))]
        if not options:
            break
        c = min(options, key=lambda c: abs(where[c] - q))
        cuts.append(c)
        last = c
    texts = texts[:len(cuts) + 1]
    if len(texts) < len(cuts) + 1:
        texts.append(" ".join(pieces[bounds[len(cuts)]:]))
    texts[-1] = " ".join(pieces[bounds[len(texts) - 1]:])
    firsts = [0, *cuts]
    ends = [*cuts, len(tokens)]
    times = [0.0] + [_start(c, letters, seconds, word_starts) for c in cuts]
    parts = [Part(a, b, t, s) for a, b, t, s in zip(firsts, ends, texts, times, strict=True)]
    return _merge_short(parts, seconds)


def _start(i: int, letters: list[int], seconds: float, word_starts: list[float | None] | None
           ) -> float:
    """When token i is recited: its word time, or in proportion to the letters before it."""
    if word_starts and i < len(word_starts):
        heard = next((word_starts[j] for j in range(i, len(word_starts))
                      if word_starts[j] is not None), None)
        if heard is not None and 0 < heard < seconds:
            return float(heard)
    return seconds * sum(letters[:i]) / max(sum(letters), 1)


def _merge_short(parts: list[Part], seconds: float) -> list[Part]:
    """Parts in order of time, none shorter than MIN_PART_SECONDS on screen."""
    out: list[Part] = []
    for p in parts:
        if out and (p.start <= out[-1].start or p.start - out[-1].start < MIN_PART_SECONDS):
            prev = out.pop()
            p = Part(prev.first, p.end, f"{prev.translation} {p.translation}", prev.start)
        out.append(p)
    if len(out) > 1 and seconds - out[-1].start < MIN_PART_SECONDS:
        last, prev = out.pop(), out.pop()
        out.append(Part(prev.first, last.end, f"{prev.translation} {last.translation}",
                        prev.start))
    return out
