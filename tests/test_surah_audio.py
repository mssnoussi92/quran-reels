"""Recitations published one file per surah: where each ayah starts, and where to cut."""

import subprocess
from pathlib import Path

import numpy as np
import pytest

from quran_reels.sources.recognition import Word, ayah_starts, heard_matches
from quran_reels.sources.surah_audio import FRAME, PAD, Pause, bounds, dips, estimates, pauses, snap

AN_NAS = ["بِسْمِ ٱللَّهِ ٱلرَّحْمَـٰنِ ٱلرَّحِيمِ", "قُلْ أَعُوذُ بِرَبِّ ٱلنَّاسِ", "مَلِكِ ٱلنَّاسِ",
          "إِلَـٰهِ ٱلنَّاسِ"]


def heard(*pairs):
    return [Word(w, t, t + 0.5) for w, t in pairs]


def test_each_ayah_starts_at_its_first_recognised_word():
    # Omar Hisham's 114: the first word swallows the basmala, ayahs 2 and 3 in one breath.
    words = heard(("قل", 0.0), ("اعوذ", 5.3), ("برب", 6.0), ("الناس", 6.6), ("ملك", 8.6),
                  ("الناس", 9.7), ("اله", 12.7), ("الناس", 13.4))
    assert ayah_starts([t.split() for t in AN_NAS], words) == [None, 0.0, 8.6, 12.7]


def test_a_repeated_ayah_starts_at_its_first_recitation():
    words = heard(("ملك", 1.0), ("الناس", 1.5), ("ملك", 3.0), ("الناس", 3.5), ("اله", 5.0),
                  ("الناس", 5.5), ("اله", 7.0), ("الناس", 7.5))
    assert ayah_starts([t.split() for t in AN_NAS[2:]], words) == [1.0, 5.0]


def test_unknown_or_implausible_starts_are_placed_in_proportion():
    # cut 1 recognised at the very start of the speech (swallowed basmala): proportional
    est = estimates([None, 0.1, 8.6, 12.7], (0.2, 16.0), [6.1, 6.1, 5.3, 5.4])
    assert est[0] == pytest.approx(0.2 + 8.4 * 0.5) and est[1:] == [8.6, 12.7]


def test_cuts_snap_to_the_strongest_quiet_moment_nearby():
    candidates = [Pause(4.0, 4.2, depth=4), Pause(4.8, 5.1, depth=12), Pause(12.5, 12.6, depth=3)]
    chosen = snap([4.4, 12.7, 14.0], candidates, (0.2, 16.0))
    assert chosen[:2] == [candidates[1], candidates[2]]
    assert chosen[2] == Pause(14.0, 14.0)            # nothing near: the estimate itself
    segs = bounds(chosen, (0.2, 16.0), 16.5)
    assert segs[0] == (0.0, round(5.1 - 0.15, 3)) and segs[1][0] == round(4.8 + 0.15, 3)
    assert segs[-1] == (14.0, 16.0 + PAD)


def test_a_segment_must_be_heard_as_its_ayah_a_repetition_allowed():
    assert heard_matches("مَلِكِ ٱلنَّاسِ", AN_NAS[2]) == 1.0
    assert heard_matches("ملك الناس ملك الناس", AN_NAS[2]) == 1.0
    assert heard_matches("ملك الناس اله الناس", AN_NAS[2], AN_NAS[1], AN_NAS[3]) == 0
    assert heard_matches("قل اعوذ برب الناس ملك الناس", AN_NAS[2], AN_NAS[1], AN_NAS[3]) == 0


def test_dips_find_the_quiet_moments_that_reverb_keeps_above_silence():
    env = np.full(int(6 / FRAME), -20.0)            # 6 s of speech at -20 dB
    env[int(2 / FRAME):int(2.3 / FRAME)] = -34      # a 14 dB dip at 2 s (reverb, not silence)
    env[int(4 / FRAME):int(4.1 / FRAME)] = -24      # a shallow one at 4 s
    [d] = dips(env, 8.0)
    assert d.start == pytest.approx(2, abs=FRAME) and d.end == pytest.approx(2.3, abs=FRAME)
    assert d.depth == 14 and d.weight == pytest.approx(1.4)
    assert len(dips(env, 3.0)) == 2


def test_pauses_read_from_ffmpeg(tmp_path: Path):
    wav = tmp_path / "a.wav"
    tone = "sine=f=440:d=2"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", tone, "-f", "lavfi", "-i",
                    "anullsrc=r=44100:cl=mono:d=1", "-f", "lavfi", "-i", tone, "-filter_complex",
                    "[0][1][2]concat=n=3:v=0:a=1", "-ar", "44100", "-ac", "1", str(wav)],
                   check=True)
    found, total = pauses(wav)
    assert total == pytest.approx(5, abs=0.05)
    assert len(found) == 1 and found[0].start == pytest.approx(2, abs=0.05)
    assert found[0].length == pytest.approx(1, abs=0.05)


def test_the_committed_splits_are_complete():
    from quran_reels.sources.http import read_json

    root = Path(__file__).resolve().parents[1] / "config" / "splits"
    for path in root.glob("*/*.json"):
        data = read_json(path)
        times = [t for seg in data["segments"].values() for t in seg]
        assert times == sorted(times), path
        assert min(data["match"].values()) >= 0.85, path
