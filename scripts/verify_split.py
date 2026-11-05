"""Check a per-surah reciter's split by speech recognition (run on a GitHub runner).

For each surah given: split it with sources/surah_audio.py, transcribe every segment with
tarteel-ai/whisper-base-ar-quran (Whisper fine-tuned on recitation), and compare with the
ayah's Uthmani text, normalised (no diacritics, unified alif/ya). Also transcribes the whole
file with word timestamps, to see where each ayah really starts. Prints a table; nothing is
written to the repository. The recognised text is only compared, never shown or published.
"""

from __future__ import annotations

import difflib
import os
import subprocess
import sys

import numpy as np

from quran_reels.arabic import normalize
from quran_reels.config import load
from quran_reels.models import AyahRef
from quran_reels.sources import Sources


def audio(path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-ac", "1",
                          "-ar", "16000", "-f", "f32le", "-"], capture_output=True,
                         check=True).stdout
    return np.frombuffer(raw, np.float32)


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalize(a).replace(" ", ""),
                                   normalize(b).replace(" ", "")).ratio()


def main(surahs: list[int]) -> None:
    from transformers import pipeline

    asr = pipeline("automatic-speech-recognition", model="tarteel-ai/whisper-base-ar-quran",
                   chunk_length_s=30, device="cpu")
    cfg = load()
    src = Sources.from_config(cfg)
    src.quran.ensure(src.translation_slug)
    basmala_text = src.quran.text([AyahRef(1, 1)])[AyahRef(1, 1)]
    for surah in surahs:
        segs = src.audio.segments(surah)
        texts = src.quran.text([AyahRef(surah, int(k)) for k in segs if k != "basmala"])
        print(f"\n== surah {surah}: {len(segs)} segments")
        for label, (a, b) in segs.items():
            path = src.audio._cut(surah, label)
            heard = asr(audio(path))["text"]
            want = basmala_text if label == "basmala" else texts[AyahRef(surah, int(label))]
            print(f"  {label:>8} {a:7.2f}-{b:7.2f}  match {similarity(heard, want):.2f}  "
                  f"heard: {normalize(heard)}  |  ayah: {normalize(want)}")
        whole = asr(audio(src.audio.dir / f"{surah:03d}.mp3"), return_timestamps="word")
        print("  words:", " ".join(f"{normalize(c['text'])}@{c['timestamp'][0]:.1f}"
                                  for c in whole["chunks"]))


if __name__ == "__main__":
    os.environ.setdefault("QURAN_REELS_RECITER", "omar_hisham")
    main([int(s) for s in sys.argv[1:]] or [114, 1])
