"""Recitations published one file per surah: where each ayah starts, and where to cut."""

import shutil
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
    # one word of the next ayah is enough to refuse the cut (Al-Ghamdi's 112, «ولم»)
    assert heard_matches("بسم الله الرحمن الرحيم قل هو", AN_NAS[0], "", "قُلْ هُوَ ٱللَّهُ أَحَدٌ") == 0
    assert heard_matches("لم يلد ولم يولد ولم", "لَمْ يَلِدْ وَلَمْ يُولَدْ",
                         "", "وَلَمْ يَكُن لَّهُۥ كُفُوًا أَحَدٌۢ") == 0


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
        data = read_json(path)      # what rendering uses: the checked segments, in order
        times = [t for k, seg in data["segments"].items() if k in data["match"] for t in seg]
        assert times == sorted(times), path
        from quran_reels.sources.surah_audio import MIN_MATCH
        assert min(data["match"].values()) >= MIN_MATCH, path


def test_the_basmala_ends_at_the_reciters_stop_not_at_a_late_published_start():
    from quran_reels.sources.surah_audio import Pause, basmala_stop
    # Budair, surah 2: basmala, silence 3.9-4.64, «Alif» 4.68-5.12, mp3quran's 2:1 at 5.2
    silences = [Pause(0.0, 0.19), Pause(1.6, 1.62), Pause(3.9, 4.64)]
    assert basmala_stop(silences, 0.19, 5.2 + 0.4) == Pause(3.9, 4.64)
    assert basmala_stop([Pause(0.0, 0.19)], 0.19, 5.6) is None      # no stop heard: as before


class HeardAround:
    """A recogniser for check_cut: each sample holds its own time, so a clip says where it is;
    it answers what a reciter says just before or just after the cut."""

    def __init__(self, cut, before, after):
        self.cut, self.before, self.after = cut, before, after

    def text(self, samples):
        return self.after if samples[0] >= self.cut - 0.01 else self.before


def timed(seconds):
    import numpy as np
    return (np.arange(int(seconds * 16000), dtype=np.float64) / 16000).astype(np.float32)


LEFT = "وَلَا يَـُٔودُهُۥ حِفْظُهُمَا ۚ وَهُوَ ٱلْعَلِىُّ ٱلْعَظِيمُ"
RIGHT = "لَآ إِكْرَاهَ فِى ٱلدِّينِ ۖ قَد تَّبَيَّنَ"


def test_a_cut_that_leaves_the_next_ayahs_first_word_before_it_is_refused():
    from quran_reels.sources.surah_audio import check_cut
    # Budair's old 2:255|2:256 cut, as recognised: «لا» lost before, «ذكراه» first after
    rec = HeardAround(10.0, "وَهُوَ الْعَلِيُّ الْعَظِيمُ", "ذَكْرَاهَ فِي الدِّينِ")
    assert "is not after the cut" in check_cut(rec, timed(20), 10.0, 10.0, LEFT, RIGHT)
    rec = HeardAround(10.0, "وَهُوَ الْعَلِيُّ الْعَظِيمُ", "لَا إِكْرَاهَ فِي الدِّينِ")
    assert check_cut(rec, timed(20), 10.0, 10.0, LEFT, RIGHT) == ""


def test_a_basmala_that_ends_with_the_first_ayahs_word_is_refused():
    from quran_reels.sources.surah_audio import check_cut
    basmala = "بِسْمِ ٱللَّهِ ٱلرَّحْمَـٰنِ ٱلرَّحِيمِ"
    rec = HeardAround(5.0, "الرَّحِيمِ الم", "الم ذَلِكَ")           # «Alif» kept before the cut
    assert "of the next ayah is before the cut" in check_cut(rec, timed(12), 5.0, 5.0, basmala,
                                                             "الٓمٓ")


def test_a_segment_refused_again_with_the_same_cuts_is_not_kept_as_checked():
    from quran_reels.sources.surah_audio import kept_scores
    before = {"segments": {"2": [1.0, 4.0], "3": [4.0, 9.0], "4": [9.0, 15.0]},
              "match": {"2": 0.96, "3": 1.0, "4": 1.0}}
    segments = {"2": [1.0, 4.0], "3": [4.0, 9.0], "4": [9.0, 15.0]}
    labels = ["2", "3", "4"]
    # the audit re-checks 2-4: 3 and 4 refused (bad cut 3|4), the same cuts found again
    assert kept_scores(before, segments, {"2": 0.96}, {"2", "3", "4"}, labels) == {"2": 0.96}
    # one passage re-checked (2): 3 and 4, left out and not moved, stay checked
    assert kept_scores(before, segments, {"2": 0.9}, {"2"}, labels) == {
        "2": 0.9, "3": 1.0, "4": 1.0}
    # a cut that moved is not kept; everything re-checked (None) keeps nothing old
    moved = {**segments, "4": [9.5, 15.0]}
    assert kept_scores(before, moved, {"2": 0.9}, {"2"}, labels) == {"2": 0.9, "3": 1.0}
    assert kept_scores(before, segments, {"2": 0.9}, None, labels) == {"2": 0.9}


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_a_cut_that_starts_on_a_tiny_frame(tmp_path):
    # ffmpeg 9.0.2 (the workflows' static build) refused this cut of an MP3 with «flac:
    # invalid block size: 11» (Omar Hisham 101:2, 2026-11-06): same times, generated audio.
    from quran_reels.sources.surah_audio import cut, duration

    mp3 = tmp_path / "s.mp3"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                    "sine=frequency=440:sample_rate=44100:duration=12", "-ac", "2",
                    "-c:a", "libmp3lame", "-b:a", "320k", str(mp3)], check=True)
    out = cut(mp3, 7.080, 8.490, tmp_path / "c.flac")
    assert abs(duration(out) - 1.41) < 0.03
