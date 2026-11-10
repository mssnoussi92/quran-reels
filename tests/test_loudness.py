"""Every reel at the same loudness (video.loudness, the owner's choice, 2026-11-10): one gain for
the whole track from its integrated loudness, then a limiter; no sample added, dropped or moved.
Generated sound, the real ffmpeg; no network."""

import shutil
import wave
from pathlib import Path

import numpy as np
import pytest

from quran_reels import render
from quran_reels.config import Config, load
from quran_reels.render import video
from quran_reels.render.video import SAMPLE_RATE

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")

TARGET, LIMIT = -16.0, 0.8
LEAD, TAIL = 0.4, 1.2                   # video.lead_seconds, video.tail_seconds


def write(path: Path, signal: np.ndarray) -> Path:
    """A reel's track as write_audio leaves it: lead silence, the sound, tail silence, 48 kHz
    stereo 16 bits. signal: floats in −1..1."""
    mono = np.concatenate([np.zeros(round(LEAD * SAMPLE_RATE)), signal,
                           np.zeros(round(TAIL * SAMPLE_RATE))])
    pcm = np.round(mono * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(np.repeat(pcm[:, None], 2, axis=1).tobytes())
    return path


def read(path: Path) -> np.ndarray:
    """Samples × channels, floats in −1..1."""
    with wave.open(str(path)) as w:
        assert (w.getframerate(), w.getsampwidth()) == (SAMPLE_RATE, 2)
        raw = np.frombuffer(w.readframes(w.getnframes()), "<i2")
        return raw.reshape(-1, w.getnchannels()) / 32768


def voice(peak: float, seconds: float = 8.0, bursts: float = 0.0) -> np.ndarray:
    """Something like a voice: the harmonics of 140 Hz, in syllables (3 a second). bursts > 0:
    40 ms each second that many times louder than the rest (a reciter's loud attack)."""
    t = np.arange(round(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    x = sum(np.sin(2 * np.pi * 140 * k * t + k) / k for k in range(1, 12))
    x *= 0.15 + 0.85 * np.clip(np.sin(2 * np.pi * 3.1 * t), 0, None) ** 2
    x /= np.abs(x).max()
    if bursts:
        x *= np.where((t % 1.0 > 0.5) & (t % 1.0 < 0.54), bursts, 1.0)
        x /= np.abs(x).max()
    return x * peak


def sound(samples: np.ndarray) -> tuple[int, int]:
    """First and last sample that is not silence."""
    heard = np.flatnonzero(np.abs(samples).max(axis=1) > 0)
    return int(heard[0]), int(heard[-1])


@needs_ffmpeg
@pytest.mark.parametrize("peak", [10 ** (-12 / 20), 0.999], ids=["quiet", "loud"])
def test_a_quiet_and_a_loud_track_end_at_the_target(tmp_path, peak):
    src = write(tmp_path / "passage.wav", voice(peak))
    before = video.loudness(src)
    assert abs(before - TARGET) > 5                       # −22.4 and −10.4 LUFS
    out = tmp_path / "level.wav"
    done = video.level(src, out, TARGET, LIMIT)

    assert done["measured_lufs"] == before
    assert done["gain_db"] == pytest.approx(TARGET - before, abs=0.01)
    assert abs(video.loudness(out) - TARGET) <= 0.7
    assert done["result_lufs"] == video.loudness(out)
    a, b = read(src), read(out)
    assert np.abs(b).max() <= LIMIT + 0.002
    # the frames are timed to the sample: as many samples, the sound where it was
    assert b.shape == a.shape
    assert sound(b) == sound(a) == (round(LEAD * SAMPLE_RATE), len(a) - round(TAIL * SAMPLE_RATE) - 1)
    # one gain for the whole track: every sample of the recording is multiplied by the same
    gain = 10 ** (done["gain_db"] / 20)
    assert np.abs(b - a * gain).max() < 2e-4


@needs_ffmpeg
def test_the_limiter_holds_the_peaks_under_the_ceiling(tmp_path):
    # attacks 2.5 times louder than the rest: at −16 LUFS they would reach 1.18 of full scale
    src = write(tmp_path / "passage.wav", voice(0.5, bursts=2.5))
    out = tmp_path / "level.wav"
    done = video.level(src, out, TARGET, LIMIT)                      # −16.4 LUFS
    a, b = read(src), read(out)
    assert np.abs(a).max() * 10 ** (done["gain_db"] / 20) > 1.1      # clipped without it
    assert LIMIT - 0.01 < np.abs(b).max() <= LIMIT + 0.002
    assert abs(done["result_lufs"] - TARGET) <= 0.7
    assert b.shape == a.shape and sound(b) == sound(a)               # delay compensated


@needs_ffmpeg
def test_the_same_track_gives_the_same_sound(tmp_path):
    src = write(tmp_path / "passage.wav", voice(0.5, bursts=2.5))
    first = video.level(src, tmp_path / "1.wav", TARGET, LIMIT)
    again = video.level(src, tmp_path / "2.wav", TARGET, LIMIT)
    assert first == again
    assert (tmp_path / "1.wav").read_bytes() == (tmp_path / "2.wav").read_bytes()


@needs_ffmpeg
def test_silence_is_left_as_it_is(tmp_path, capsys):
    src = write(tmp_path / "passage.wav", np.zeros(3 * SAMPLE_RATE))
    assert video.loudness(src) is None
    out = tmp_path / "level.wav"
    assert video.level(src, out, TARGET, LIMIT) == {
        "measured_lufs": None, "gain_db": 0.0, "result_lufs": None}
    assert out.read_bytes() == src.read_bytes()
    # in a render: said, the reel still comes out
    path, record = render.level_audio(cfg({"lufs": TARGET, "limit": LIMIT}), src, "112:1-4")
    assert path.read_bytes() == src.read_bytes() and record["gain_db"] == 0.0
    assert "112:1-4: no loudness measured" in capsys.readouterr().err


def cfg(loudness=None, **more):
    block = {"handle": "@quran_words_daily", **more}
    if loudness is not None:
        block["loudness"] = loudness
    return Config(root=Path("."), backgrounds={}, gloss_headwords={}, project={"video": block})


def test_the_project_levels_every_reel_at_minus_16():
    assert load().video["loudness"] == {"lufs": -16, "limit": 0.8}


@pytest.mark.parametrize("conf", [cfg(), cfg(loudness={}), cfg(loudness={"lufs": None}),
                                  cfg(loudness={"lufs": None, "limit": 0.8})],
                         ids=["absent", "empty", "null", "limit alone"])
def test_without_the_setting_the_sound_is_not_touched(tmp_path, conf, monkeypatch):
    src = write(tmp_path / "passage.wav", voice(0.5, seconds=1.0))
    before = src.read_bytes()
    monkeypatch.setattr(video, "level", lambda *a, **k: pytest.fail("levelled"))
    assert render.level_audio(conf, src) == (src, None)
    assert src.read_bytes() == before and list(tmp_path.iterdir()) == [src]


@needs_ffmpeg
def test_a_render_levels_the_track_and_keeps_the_measure(tmp_path, capsys):
    src = write(tmp_path / "passage.wav", voice(0.999))
    before = src.read_bytes()
    path, record = render.level_audio(cfg({"lufs": TARGET, "limit": LIMIT}), src, "112:1-4")
    assert path == tmp_path / "passage.level.wav" and src.read_bytes() == before
    assert record == {"target_lufs": TARGET, "limit": LIMIT, "measured_lufs": -10.4,
                      "gain_db": -5.6, "result_lufs": -16.0}
    assert capsys.readouterr().err == ""
    # no ceiling in the config: the default one
    assert render.level_audio(cfg({"lufs": -16}), src)[1]["limit"] == video.LIMIT


@needs_ffmpeg
def test_a_broken_file_is_not_raised_by_thirty_decibels(tmp_path, capsys):
    """A track 30 dB under the target is not a soft recitation: the gain stops at MAX_GAIN (its
    noise is not made as loud as a voice) and the render says how far from the target it is."""
    src = write(tmp_path / "passage.wav", voice(0.004))
    _, record = render.level_audio(cfg({"lufs": TARGET, "limit": LIMIT}), src, "2:255")
    assert record["measured_lufs"] < TARGET - 30 and record["gain_db"] == video.MAX_GAIN
    assert record["result_lufs"] == pytest.approx(record["measured_lufs"] + video.MAX_GAIN, abs=0.2)
    assert "2:255:" in capsys.readouterr().err


def test_a_limiter_that_takes_too_much_is_said(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(video, "level", lambda *a: {"measured_lufs": -25.5, "gain_db": 9.5,
                                                    "result_lufs": -19.2})
    src = tmp_path / "passage.wav"
    _, record = render.level_audio(cfg({"lufs": TARGET, "limit": LIMIT}), src, "2:255")
    assert record["result_lufs"] == -19.2
    assert "2:255: -19.2 LUFS after the limiter, target -16" in capsys.readouterr().err


def ffmpeg_writing(samples_off: int, monkeypatch, rate: int = SAMPLE_RATE):
    """level() with an ffmpeg that returns `samples_off` more (or fewer) samples than it got."""
    def run(cmd):
        src, dest = Path(cmd[cmd.index("-i") + 1]), Path(cmd[-1])
        with wave.open(str(src)) as w:
            data = w.readframes(w.getnframes())
        size = len(data) + samples_off * 4
        with wave.open(str(dest), "wb") as out:
            out.setnchannels(2)
            out.setsampwidth(2)
            out.setframerate(rate)
            out.writeframes(data[:size].ljust(size, b"\x01"))
    monkeypatch.setattr(video, "_run", run)
    monkeypatch.setattr(video, "loudness", lambda path: -20.0)


@pytest.mark.parametrize("off", [-3, 2, video.LEVEL_SLACK])
def test_a_few_samples_more_or_fewer_are_made_good(tmp_path, monkeypatch, off):
    src = write(tmp_path / "passage.wav", voice(0.5, seconds=1.0))
    ffmpeg_writing(off, monkeypatch)
    out = tmp_path / "level.wav"
    video.level(src, out, TARGET, LIMIT)
    a, b = read(src), read(out)
    assert b.shape == a.shape
    kept = len(a) + min(off, 0)
    assert np.array_equal(b[:kept], a[:kept]) and not b[kept:].any()     # padded with silence


@pytest.mark.parametrize("off", [-240, video.LEVEL_SLACK + 1])
def test_more_than_a_few_samples_stops_the_render(tmp_path, monkeypatch, off):
    src = write(tmp_path / "passage.wav", voice(0.5, seconds=1.0))
    ffmpeg_writing(off, monkeypatch)
    with pytest.raises(RuntimeError, match="would no longer follow the frames"):
        video.level(src, tmp_path / "level.wav", TARGET, LIMIT)


def test_another_sample_rate_stops_the_render(tmp_path, monkeypatch):
    src = write(tmp_path / "passage.wav", voice(0.5, seconds=1.0))
    ffmpeg_writing(0, monkeypatch, rate=44_100)
    with pytest.raises(RuntimeError, match="44100 Hz"):
        video.level(src, tmp_path / "level.wav", TARGET, LIMIT)
