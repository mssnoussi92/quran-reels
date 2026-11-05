"""Recitations published one file per surah: the ayahs are found on the pauses."""

import subprocess
from pathlib import Path

import pytest

from quran_reels.sources.surah_audio import Pause, SplitError, pauses, split


def test_the_cuts_follow_the_reference_lengths_and_skip_a_short_pause_inside_an_ayah():
    # 3 segments of 4, 6, 5 s with 1 s pauses; a 0.4 s pause in the middle of the second.
    found = [Pause(0, 0.5), Pause(4.5, 5.5), Pause(8.3, 8.7), Pause(11.5, 12.5), Pause(17.5, 18)]
    segs = split(found, 18, [4, 6, 5])
    assert [round(b - a, 2) for a, b in segs] == [4.5, 6.5, 5.5]     # 0.25 s kept on each side
    assert segs[1] == (5.25, 11.75)


def test_a_longer_pause_wins_near_the_expected_place():
    found = [Pause(3.6, 4.0), Pause(4.4, 5.6)]           # both close to 4.5 s: the long one
    assert split(found, 10, [4.5, 4.5])[0][1] == pytest.approx(4.65)


def test_a_recording_that_does_not_fit_stops_the_render():
    with pytest.raises(SplitError, match="2 pauses for 4 segments"):
        split([Pause(3, 4), Pause(6, 7)], 10, [2, 2, 2, 2])
    with pytest.raises(SplitError, match="segment 1/2"):   # 1 s where 5 s were expected
        split([Pause(1, 1.5)], 10, [5, 5])


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


def test_dips_find_the_quiet_moments_that_reverb_keeps_above_silence():
    import numpy as np

    from quran_reels.sources.surah_audio import FRAME, dips

    env = np.full(int(6 / FRAME), -20.0)            # 6 s of speech at -20 dB
    env[int(2 / FRAME):int(2.3 / FRAME)] = -34      # a 14 dB dip at 2 s (reverb, not silence)
    env[int(4 / FRAME):int(4.1 / FRAME)] = -24      # a shallow one at 4 s
    [d] = dips(env, 8.0)
    assert d.start == pytest.approx(2, abs=FRAME) and d.end == pytest.approx(2.3, abs=FRAME)
    assert d.depth == 14 and d.weight == pytest.approx(1.4)
    assert len(dips(env, 3.0)) == 2
