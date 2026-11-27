"""A long ayah on several screens, each shown while its words are recited.

An ayah whose text needs a scale under MIN_FIT to fit the safe area (2:255 came out at 45 %,
hard to read on a phone) is shown in parts. The Uthmani text is cut after pause marks
(ۚ ۖ ۗ ۛ ۘ ۙ ۜ, the places where a reciter may stop), and where none is left, before a word that
opens a clause with the conjunction و or ف (فَٱبْعَثُوٓا۟, وَلَا: never inside «وَلَا يُشْعِرَنَّ»);
the translation after sentence ends. Both run through the ayah's clauses in the same order: each
Arabic cut takes the translation's sentence end closest to it, so a sentence stays on the screen
of its words (18:19: «They said, "Your Lord is most knowing…» went one screen before
قَالُوا۟ رَبُّكُمْ). Each part appears when its first word is recited: word times found when the
recording was split (sources/surah_audio.py, `words`), else in proportion to the letters before it.

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
CLAUSE_COST = 0.004      # the translation cut at a comma rather than a sentence end: only when
                         # it is clearly closer to the Arabic cut (0.004: about 6 % of the ayah)
PAUSE_MARKS = frozenset("ۖۗۘۙۚۛۜ")
FATHA = "\u064e"
_SENTENCE_END = re.compile(r"[.?!;][\"'”’»)\]]*(?=\s)")   # its closing quotes stay with it
_CLAUSE = re.compile(r"(?<=[,:])\s+|\s+(?=-\s)")
_BRACKETS = re.compile(r"\[[^\]]*\]")


def sentences(text: str) -> list[str]:
    """The translation's sentences, each with its closing quotes and brackets (« [here]?" »:
    the split dropped them until 2026-11-27, 18:19)."""
    out, at = [], 0
    for m in _SENTENCE_END.finditer(text):
        out.append(text[at:m.end()].strip())
        at = m.end()
    out.append(text[at:].strip())
    return [x for x in out if x]


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


def clause_cuts(tokens: list[str]) -> list[int]:
    """Where a part may start when no pause mark is left: a word opening with the conjunction
    و or ف (the letter, then a fatha: not فِى «in»)."""
    return [i for i, t in enumerate(tokens) if i and len(t) > 2 and t[0] in "وف"
            and t[1] == FATHA]


def translation_pieces(text: str) -> list[str]:
    """Sentences, and within a long one its clauses: the pieces a part is made of."""
    out = []
    for sentence in (s for s in sentences(text) if s):
        out.extend(p for p in _CLAUSE.split(sentence) if p) if len(sentence) > 140 \
            else out.append(sentence)
    return out


def translation_clauses(text: str) -> list[tuple[str, bool]]:
    """Every clause of every sentence, each with whether it ends its sentence: where the
    translation may be cut to follow the Arabic."""
    out = []
    for sentence in (s for s in sentences(text) if s):
        clauses: list[str] = []
        for p in (p for p in _CLAUSE.split(sentence) if p):
            if clauses and clauses[-1].count("[") > clauses[-1].count("]"):
                clauses[-1] += " " + p              # never inside « [i.e., beauty] »
            else:
                clauses.append(p)
        out.extend((c, i == len(clauses) - 1) for i, c in enumerate(clauses))
    return out


def _pair(cuts: list[float], ends: list[tuple[float, bool]]) -> list[int]:
    """The translation boundary for each Arabic cut (both as relative positions, in order):
    indices into ends, strictly increasing, with the least squared distance, a clause end that
    is not a sentence end costing CLAUSE_COST more."""
    m, n = len(cuts), len(ends)
    if not m:
        return []
    cost = [[float("inf")] * n for _ in range(m)]
    back = [[0] * n for _ in range(m)]
    for j, at in enumerate(cuts):
        for i in range(j, n - (m - 1 - j)):
            pos, sentence_end = ends[i]
            own = (pos - at) ** 2 + (0.0 if sentence_end else CLAUSE_COST)
            if j == 0:
                cost[j][i] = own
                continue
            h = min(range(j - 1, i), key=lambda h: cost[j - 1][h])
            cost[j][i], back[j][i] = cost[j - 1][h] + own, h
    i = min(range(n), key=lambda i: cost[m - 1][i])
    out = [i]
    for j in range(m - 1, 0, -1):
        i = back[j][i]
        out.append(i)
    return out[::-1]


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
    # Relative positions: of each token in the Arabic (by letters), of each sentence end in
    # the translation (by characters).
    letters = _letters(tokens)
    total = max(sum(letters), 1)
    where = [sum(letters[:i]) / total for i in range(len(tokens) + 1)]
    tr_total = max(sum(len(p) for p in pieces), 1)
    tr_at = [sum(len(p) for p in pieces[:b]) / tr_total for b in range(len(pieces) + 1)]
    # The Arabic cut for each translation boundary, in order: the pause mark at the closest
    # relative position; when no mark is left, the closest word opening a clause; else none.
    marks, clauses = pause_cuts(tokens), clause_cuts(tokens)
    cuts, last = [], 0
    for b in starts[1:]:
        options = [c for c in marks if c > last] or [c for c in clauses if c > last]
        if not options:
            break
        c = min(options, key=lambda c: abs(where[c] - tr_at[b]))
        cuts.append(c)
        last = c
    # Then the translation is cut where the Arabic was (a pause mark is rarely where the even
    # split of the translation fell): the cuts take sentence ends, or clause ends, all together.
    fine = translation_clauses(translation)
    cuts = cuts[:len(fine) - 1]          # never more screens than the translation has clauses
    sizes = [len(_BRACKETS.sub("", p)) for p, _ in fine]    # « [i.e., beauty] »: not in the Arabic
    ends = [(sum(sizes[:i + 1]) / max(sum(sizes), 1), end) for i, (_, end) in enumerate(fine[:-1])]
    picked = [i + 1 for i in _pair([where[c] for c in cuts], ends)]
    texts = [" ".join(p for p, _ in fine[a:b]) for a, b in pairwise([0, *picked, len(fine)])]
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
