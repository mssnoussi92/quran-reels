"""Where each ayah starts in a recording, by speech recognition (optional: `pip install
-e .[asr]`, torch from https://download.pytorch.org/whl/cpu).

Used once per surah for reciters published one file per surah (sources/surah_audio.py), and
the verified split is committed (config/splits/): the daily pipeline never needs the model.

Model: tarteel-ai/whisper-base-ar-quran, Whisper fine-tuned on Quran recitation. Its word
times come from the cross-attention of openai/whisper-base, the model it was trained from.
The recognised words are only compared with the Uthmani text from Quran.com, to find where
each ayah starts and to check every segment; they are never displayed nor published.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass

import numpy as np

from quran_reels.arabic import normalize

MODEL = "tarteel-ai/whisper-base-ar-quran"
ALIGNMENT_FROM = "openai/whisper-base"
RATE = 16000


@dataclass(frozen=True)
class Word:
    text: str          # normalised
    start: float
    end: float


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalize(a), normalize(b), autojunk=False).ratio()


def heard_matches(heard: str, want: str, before: str = "", after: str = "") -> float:
    """How well a segment's recognised text matches its ayah, a repeated ayah included
    (reciters often recite the last ayah twice). 0 when it matches better with words of a
    neighbouring ayah added, even one: the cut is then a word off (بسم الله… قل هو), and ayahs
    that share words (مَلِكِ ٱلنَّاسِ, إِلَـٰهِ ٱلنَّاسِ) would otherwise pass."""
    h, w = normalize(heard), normalize(want)
    if not h or not w:
        return 0.0
    repeats = max(1, round(len(h) / len(w)))
    score = max(similarity(h, w), similarity(h, w * repeats))
    nxt = [normalize(x) for x in after.split() if normalize(x)]
    prv = [normalize(x) for x in before.split() if normalize(x)]
    joined = ([w + "".join(nxt[:k]) for k in range(1, len(nxt) + 1)]
              + ["".join(prv[-k:]) + w for k in range(1, len(prv) + 1)])
    if any(similarity(h, j) > score + 0.02 for j in joined):
        return 0.0
    return score


class Recognizer:
    def __init__(self) -> None:
        try:
            from transformers import GenerationConfig, pipeline
        except ImportError as e:
            raise SystemExit("splitting a recording needs the asr extra: pip install torch "
                             "--index-url https://download.pytorch.org/whl/cpu && pip install "
                             "-e .[asr]") from e
        self.asr = pipeline("automatic-speech-recognition", model=MODEL, chunk_length_s=30,
                            device="cpu")
        self.asr.model.generation_config = GenerationConfig.from_pretrained(ALIGNMENT_FROM)
        self.kwargs = {"generate_kwargs": {"language": "ar", "task": "transcribe"}}

    def words(self, samples: np.ndarray) -> list[Word]:
        out = self.asr(samples, return_timestamps="word", **self.kwargs)
        found = []
        for c in out["chunks"]:
            start, end = c["timestamp"]
            text = normalize(c["text"])
            if text and start is not None:
                found.append(Word(text, float(start), float(end if end is not None else start)))
        return found

    def text(self, samples: np.ndarray) -> str:
        return self.asr(samples, **self.kwargs)["text"]


GAP_TEXT = -0.7        # an ayah word not heard
GAP_HEARD = -0.4       # a heard word in no ayah (repetition, isti'adha, misheard)
# A match: +1 when identical, 0 at 2/3 similar, below a mismatch (short words that
# share the article look alike: الناس / اله are 0.75 similar).


def match_score(sim: float) -> float:
    return 3 * sim - 2


def align_words(words: list[str], heard: list[Word], min_similarity: float = 0.75
                ) -> list[Word | None]:
    """The heard word matched to each text word (normalised), or None.

    Global alignment of the text with the heard words; a heard word in no ayah (isti'adha,
    repetition, misheard) costs the same wherever it is, so a repeated passage is a tie, which
    goes to the earliest match: a word is placed at its first recitation.
    """
    flat = [normalize(w) for w in words]
    n, m = len(flat), len(heard)
    score = np.zeros((n + 1, m + 1))
    for i in range(1, n + 1):
        score[i][0] = score[i - 1][0] + GAP_TEXT
    for j in range(1, m + 1):
        score[0][j] = score[0][j - 1] + GAP_HEARD
    sims = np.array([[similarity(flat[i], heard[j].text) for j in range(m)] for i in range(n)])
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            score[i][j] = max(score[i][j - 1] + GAP_HEARD,
                              score[i - 1][j - 1] + match_score(sims[i - 1][j - 1]),
                              score[i - 1][j] + GAP_TEXT)
    matched: list[Word | None] = [None] * n
    i, j = n, m
    while i > 0:                       # back from the end: heard words first, so matches
        if j > 0 and np.isclose(score[i][j], score[i][j - 1] + GAP_HEARD):
            j -= 1
        elif j > 0 and np.isclose(score[i][j],
                                  score[i - 1][j - 1] + match_score(sims[i - 1][j - 1])):
            if sims[i - 1][j - 1] >= min_similarity:
                matched[i - 1] = heard[j - 1]
            i, j = i - 1, j - 1
        else:
            i -= 1
    return matched


def ayah_starts(ayahs: list[list[str]], heard: list[Word], min_similarity: float = 0.75
                ) -> list[float | None]:
    """Start time of each ayah (its first word matched in `heard`), or None."""
    owner = [k for k, words in enumerate(ayahs) for w in words if normalize(w)]
    flat = [w for words in ayahs for w in words if normalize(w)]
    starts: list[float | None] = [None] * len(ayahs)
    for k, word in reversed(list(zip(owner, align_words(flat, heard, min_similarity),
                                     strict=True))):
        if word is not None:
            starts[k] = word.start          # the earliest matched word wins
    return starts
