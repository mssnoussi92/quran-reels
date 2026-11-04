"""Audio timeline and final MP4 (H.264 + AAC) with ffmpeg.

Each ayah's MP3 is decoded to PCM so its length is known to the sample. The ayah's frame is
on screen exactly while its recitation plays, rounded to whole video frames; the audio track
is padded so that both streams end on the same frame.
"""

from __future__ import annotations

import subprocess
import wave
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

SAMPLE_RATE = 48_000
CHANNELS = 2


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

    @property
    def samples_per_frame(self) -> int:
        return SAMPLE_RATE // self.fps

    @property
    def seconds(self) -> float:
        return self.total_frames / self.fps

    def frame_counts(self) -> list[int]:
        """Video frames for each ayah's image; the first absorbs the lead, the last the tail."""
        spf = self.samples_per_frame
        bounds, acc = [0], self.lead_samples
        for n in self.ayah_samples[:-1]:
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


def build_timeline(ayah_samples: list[int], fps: int, lead: float, tail: float) -> Timeline:
    if SAMPLE_RATE % fps:
        raise ValueError(f"fps {fps} must divide {SAMPLE_RATE}")
    spf = SAMPLE_RATE // fps
    lead_samples = round(lead * SAMPLE_RATE)
    end = lead_samples + sum(ayah_samples) + round(tail * SAMPLE_RATE)
    return Timeline(fps=fps, ayah_samples=ayah_samples, lead_samples=lead_samples,
                    total_frames=-(-end // spf))


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


def compose(background: Path, static: Path, frames: list[Path], timeline: Timeline,
            audio: Path, dest: Path, width: int, height: int, fade: float = 0.25,
            crf: int = 19) -> Path:
    """Background (looped) + static layer + one faded layer per ayah + audio → MP4."""
    fps, total = timeline.fps, timeline.total_frames
    counts = timeline.frame_counts()
    cmd = ["ffmpeg", "-v", "error", "-y",
           "-stream_loop", "-1", "-i", str(background),
           "-loop", "1", "-framerate", str(fps), "-i", str(static)]
    for f in frames:
        cmd += ["-loop", "1", "-framerate", str(fps), "-i", str(f)]
    cmd += ["-i", str(audio)]

    graph = [
        (f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
         f"crop={width}:{height},fps={fps},setsar=1,"
         f"trim=end_frame={total},setpts=PTS-STARTPTS[bg]"),
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
            "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(fps), "-g", str(fps * 2),
            "-c:a", "aac", "-b:a", "192k", "-ar", str(SAMPLE_RATE), "-ac", str(CHANNELS),
            "-frames:v", str(total), "-movflags", "+faststart", str(dest)]
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(cmd)
    return dest
