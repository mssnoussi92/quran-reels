"""Audio timeline and final MP4 (H.264 + AAC) with ffmpeg.

Each ayah's MP3 is decoded to PCM so its length is known to the sample. The ayah's frame is
on screen exactly while its recitation plays, rounded to whole video frames; the audio track
is padded so that both streams end on the same frame. The assembled track is then brought to one
loudness (level): a single gain for the whole reel and a limiter, no sample moved.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import wave
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

SAMPLE_RATE = 48_000
CHANNELS = 2
LIMIT = 0.8             # limiter ceiling when the config gives none: 0.8 of full scale, −1.9 dBFS
LEVEL_SLACK = 8         # samples ffmpeg may add or drop while levelling (made good); more: error
MAX_GAIN = 12.0         # dB. Recitations measured: 3 to 5 dB from the target. Further than this, the
                        # file is broken rather than soft: its noise is not raised by 30 dB


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed:\n{proc.stderr[-3000:]}")


def decode(mp3: Path, wav: Path) -> int:
    """MP3 → 48 kHz stereo PCM WAV. Returns the number of samples."""
    wav.parent.mkdir(parents=True, exist_ok=True)
    _run(["ffmpeg", "-v", "error", "-y", "-i", str(mp3), "-ac", str(CHANNELS),
          "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(wav)])
    with wave.open(str(wav)) as w:
        return w.getnframes()


@dataclass
class Timeline:
    fps: int
    ayah_samples: list[int]     # recitation length of each ayah
    lead_samples: int           # silence before the first ayah
    total_frames: int
    screens: list[int] | None = None   # samples of each content screen (a long ayah: several)

    @property
    def samples_per_frame(self) -> int:
        return SAMPLE_RATE // self.fps

    @property
    def seconds(self) -> float:
        return self.total_frames / self.fps

    def frame_counts(self) -> list[int]:
        """Video frames for each screen's image (one per ayah, or the parts of a long one);
        the first absorbs the lead, the last the tail."""
        spf = self.samples_per_frame
        bounds, acc = [0], self.lead_samples
        for n in (self.screens or self.ayah_samples)[:-1]:
            acc += n
            bounds.append(round(acc / spf))
        bounds.append(self.total_frames)
        return [b - a for a, b in pairwise(bounds)]

    def starts(self) -> list[float]:
        """When each recitation starts, in seconds."""
        out, acc = [], self.lead_samples
        for n in self.ayah_samples:
            out.append(acc / SAMPLE_RATE)
            acc += n
        return out


def build_timeline(ayah_samples: list[int], fps: int, lead: float, tail: float,
                   screens: list[int] | None = None) -> Timeline:
    if SAMPLE_RATE % fps:
        raise ValueError(f"fps {fps} must divide {SAMPLE_RATE}")
    spf = SAMPLE_RATE // fps
    lead_samples = round(lead * SAMPLE_RATE)
    end = lead_samples + sum(ayah_samples) + round(tail * SAMPLE_RATE)
    if screens is not None and sum(screens) != sum(ayah_samples):
        raise ValueError("screens must split the ayahs' samples")
    return Timeline(fps=fps, ayah_samples=ayah_samples, lead_samples=lead_samples,
                    total_frames=-(-end // spf), screens=screens)


def write_audio(wavs: list[Path], timeline: Timeline, dest: Path) -> Path:
    """Lead silence + every ayah + silence up to the last video frame, as one WAV."""
    frame_bytes = CHANNELS * 2
    with wave.open(str(dest), "wb") as out:
        out.setnchannels(CHANNELS)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        out.writeframes(b"\0" * timeline.lead_samples * frame_bytes)
        written = timeline.lead_samples
        for wav in wavs:
            with wave.open(str(wav)) as w:
                n = w.getnframes()
                out.writeframes(w.readframes(n))
                written += n
        total = timeline.total_frames * timeline.samples_per_frame
        out.writeframes(b"\0" * (total - written) * frame_bytes)
    return dest


def loudness(audio: Path) -> float | None:
    """EBU R128 integrated loudness of a file's sound, in LUFS (ffmpeg's ebur128, to 0.1 LU: the
    silence before and after the recitation is gated out). None when the meter gives no measure:
    nothing above its gate (silence, less than 0.4 s of sound) or a summary that cannot be read."""
    proc = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-nostats", "-i", str(audio),
                           "-vn", "-af", "ebur128=framelog=verbose", "-f", "null", "-"],
                          capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{proc.stderr[-3000:]}")
    found = re.findall(r"\bI:\s+(-?\d+(?:\.\d+)?) LUFS", proc.stderr)
    value = float(found[-1]) if found else None     # the summary comes last
    return value if value is not None and value > -70 else None


def _fit(wav: Path, samples: int) -> None:
    """Exactly `samples` in a WAV: its end trimmed, or padded with silence."""
    with wave.open(str(wav)) as w:
        params = w.getparams()
        data = w.readframes(params.nframes)
    size = samples * params.nchannels * params.sampwidth
    with wave.open(str(wav), "wb") as out:
        out.setparams(params)                       # the frame count is rewritten on close
        out.writeframes(data[:size].ljust(size, b"\0"))


def level(src: Path, dest: Path, lufs: float, limit: float = LIMIT) -> dict:
    """`src` (the WAV of a whole reel) at `lufs` integrated (EBU R128), in `dest`.

    One gain for the whole track, from its measured loudness: the basmala and the ayahs are one
    reciter and one recording, what is soft and what is loud between them stays so (no loudnorm,
    which rides the gain over time). Then a look-ahead limiter holds every sample under `limit`
    of full scale (0.8: −1.9 dBFS, room for the AAC encoder), its delay compensated: nothing
    moves in time and `dest` has exactly the samples of `src`, to which the frames are timed.
    The same input gives the same output. A track without a measure (silence) is copied as it is.

    Returns measured_lufs (None: not levelled), gain_db and result_lufs, the loudness of `dest`:
    under the target by what the limiter took from the peaks, or away from it when the gain
    needed was more than MAX_GAIN (the caller says so)."""
    measured = loudness(src)
    if measured is None:
        shutil.copyfile(src, dest)
        return {"measured_lufs": None, "gain_db": 0.0, "result_lufs": None}
    gain = max(-MAX_GAIN, min(MAX_GAIN, round(lufs - measured, 2)))
    _run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(src), "-af",
          f"volume={gain:.2f}dB,alimiter=limit={limit:g}:attack=5:release=50:level=0:latency=1",
          "-c:a", "pcm_s16le", str(dest)])
    with wave.open(str(src)) as a, wave.open(str(dest)) as b:
        before, after = a.getparams(), b.getparams()
    if (after.nchannels, after.framerate) != (before.nchannels, before.framerate) \
            or abs(after.nframes - before.nframes) > LEVEL_SLACK:
        raise RuntimeError(
            f"levelling {src.name}: {before.nframes} samples in ({before.nchannels} ch, "
            f"{before.framerate} Hz), {after.nframes} out ({after.nchannels} ch, "
            f"{after.framerate} Hz): the sound would no longer follow the frames")
    if after.nframes != before.nframes:
        _fit(dest, before.nframes)
    return {"measured_lufs": round(measured, 1), "gain_db": gain, "result_lufs": loudness(dest)}


def push_in_filter(zoom: float, frames: int) -> str:
    """A slow, steady zoom into the centre of the background: `zoom` larger (0.08: 8 %) at
    the last of `frames` frames than at the first. perspective samples between pixels (a crop
    or zoompan moves by whole pixels: it shakes). Before the upscale: four times fewer pixels.
    Its `in` counts the frames from 1."""
    k = f"(1-1/(1+{zoom:g}*(in-1)/{max(frames - 1, 1)}))"      # share of each side cropped
    left, top = f"W*{k}/2", f"H*{k}/2"
    right, bottom = f"W-W*{k}/2", f"H-H*{k}/2"
    return (f"perspective=x0='{left}':y0='{top}':x1='{right}':y1='{top}':"
            f"x2='{left}':y2='{bottom}':x3='{right}':y3='{bottom}':"
            "interpolation=cubic:sense=source:eval=frame")


def compose(background: Path, static: Path, frames: list[Path], timeline: Timeline,
            audio: Path, dest: Path, width: int, height: int, fade: float = 0.25,
            crf: int = 19, zoom: float = 0.0) -> Path:
    """Background (looped) + static layer + one faded layer per ayah + audio → MP4.
    zoom > 0: the background grows by that much over the reel (push_in_filter)."""
    fps, total = timeline.fps, timeline.total_frames
    counts = timeline.frame_counts()
    cmd = ["ffmpeg", "-v", "error", "-y",
           "-stream_loop", "-1", "-i", str(background),
           "-loop", "1", "-framerate", str(fps), "-i", str(static)]
    for f in frames:
        cmd += ["-loop", "1", "-framerate", str(fps), "-i", str(f)]
    cmd += ["-i", str(audio)]

    push = f"{push_in_filter(zoom, total)}," if zoom > 0 else ""
    graph = [
        (f"[0:v]fps={fps},trim=end_frame={total},setpts=PTS-STARTPTS,{push}"
         f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=bicubic,"
         f"crop={width}:{height},setsar=1[bg]"),
        f"[1:v]format=rgba,trim=end_frame={total},setpts=PTS-STARTPTS[st]",
        "[bg][st]overlay=0:0:format=auto[base]",
    ]
    for i, n in enumerate(counts):
        d = n / fps
        f_len = min(fade, d / 4)
        graph.append(
            f"[{i + 2}:v]format=rgba,trim=end_frame={n},setpts=PTS-STARTPTS,"
            f"fade=t=in:st=0:d={f_len:.3f}:alpha=1,"
            f"fade=t=out:st={d - f_len:.3f}:d={f_len:.3f}:alpha=1[t{i}]"
        )
    labels = "".join(f"[t{i}]" for i in range(len(counts)))
    graph.append(f"{labels}concat=n={len(counts)}:v=1:a=0[text]")
    graph.append("[base][text]overlay=0:0:format=auto,format=yuv420p[v]")

    cmd += ["-filter_complex", ";".join(graph),
            "-map", "[v]", "-map", f"{len(frames) + 2}:a",
            "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
            # Capped: a busy clip (white water) at crf 19 alone reached 22 Mb/s, 180 MB a minute.
            "-maxrate", "6M", "-bufsize", "12M",
            "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(fps), "-g", str(fps * 2),
            "-c:a", "aac", "-b:a", "128k", "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS),
            "-frames:v", str(total), "-movflags", "+faststart",
            # Instagram Reels: moov atom first and no edit list (ffmpeg writes one by default).
            # Without B-frames the video needs no edit list to start at 0, in sync with audio.
            "-use_editlist", "0", "-bf", "0", str(dest)]
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(cmd)
    return dest
