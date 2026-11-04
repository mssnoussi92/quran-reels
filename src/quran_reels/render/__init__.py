"""Render a passage: frames (HTML → PNG), audio timeline, background, MP4.

out/
  093_001-003.mp4             the reel
  093_001-003/
    frames/                   static.png + one PNG per ayah (and the HTML they come from)
    preview/                  each ayah composed on the mockup gradient, for a quick look
    manifest.json             every text shown, with its edition and source URL; timings
    caption.txt               deterministic caption with the credits
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from quran_reels import __version__
from quran_reels.arabic import arabic_digits
from quran_reels.config import Config
from quran_reels.models import Passage
from quran_reels.passage import build
from quran_reels.render import video
from quran_reels.render.frames import FrameRenderer, ayah_context
from quran_reels.sources import Sources, backgrounds


@dataclass
class RenderResult:
    passage: Passage
    video: Path
    workdir: Path
    seconds: float


def caption(cfg: Config, passage: Passage) -> str:
    c = cfg.content
    lines = [f"Surah {passage.surah_name_en} ({passage.key}) · سورة {passage.surah_name_ar}", ""]
    for a in passage.ayahs:
        lines += [f"{a.text} ﴿{arabic_digits(a.ref.ayah)}﴾", f"{a.ref.ayah}. {a.translation}", ""]
    lines += [
        f"Recitation: {c['reciter']['label']}",
        f"Translation: {c['translation']['label']}",
        f"Word meanings: {c['glosses']['label']}",
        "",
        cfg.video["handle"],
    ]
    return "\n".join(lines) + "\n"


def manifest(cfg: Config, src: Sources, passage: Passage, timeline: video.Timeline,
             background: dict) -> dict:
    c = cfg.content
    starts = timeline.starts()
    return {
        "passage": passage.key,
        "surah": {"number": passage.surah, "name_ar": passage.surah_name_ar,
                  "name_en": passage.surah_name_en},
        "seconds": round(timeline.seconds, 3),
        "editions": {
            "text": c["quran_text"]["edition"],
            "translation": c["translation"]["edition"],
            "glosses": c["glosses"]["edition"],
            "reciter": c["reciter"]["id"],
        },
        "sources": {
            "text": "https://api.quran.com/api/v4/quran/verses/uthmani",
            "translation": f"https://api.quran.com/api/v4 (slug {src.translation_slug})",
            "glosses": f"https://tafsir.app/{src.glosses.src}",
            "audio": f"https://everyayah.com/data/{src.audio.reciter}/",
        },
        "background": background,
        "ayahs": [
            {
                "ref": str(a.ref),
                "text": a.text,
                "translation": a.translation,
                "glosses": [{"word": g.word, "lemma": g.lemma, "gloss": g.gloss,
                             "edition": g.edition, "positions": list(g.positions)}
                            for g in a.glosses],
                "audio": src.audio.url(a.ref),
                "start": round(start, 3),
                "seconds": round(a.seconds or 0, 3),
            }
            for a, start in zip(passage.ayahs, starts)
        ],
        "renderer": f"quran-reels {__version__}",
    }


def _warn(msg: str) -> None:
    print(f"warning: {msg}", file=sys.stderr)


def render_passage(cfg: Config, key: str) -> RenderResult:
    src = Sources.from_config(cfg)
    passage = build(cfg, key, src)
    v = cfg.video
    work = cfg.out / passage.slug
    if work.exists():
        shutil.rmtree(work)
    frames_dir, audio_dir = work / "frames", work / "audio"

    # Audio first: it decides how long each frame stays on screen.
    samples = []
    wavs = []
    for a in passage.ayahs:
        wav = audio_dir / f"{a.ref.everyayah}.wav"
        n = video.decode(a.audio, wav)
        a.seconds = n / video.SAMPLE_RATE
        samples.append(n)
        wavs.append(wav)
    timeline = video.build_timeline(samples, fps=v["fps"], lead=float(v.get("lead_seconds", 0.4)),
                                    tail=float(v.get("tail_seconds", 1.2)))
    p = cfg.content["passage"]
    if not p["min_seconds"] <= timeline.seconds <= p["max_seconds"]:
        _warn(f"{passage.key} lasts {timeline.seconds:.1f} s, outside "
              f"{p['min_seconds']}–{p['max_seconds']} s (rendered anyway)")

    frames = []
    with FrameRenderer(cfg) as fr:
        static = frames_dir / "static.png"
        fr.render("static", static)
        for a in passage.ayahs:
            ctx = ayah_context(passage, a)
            png = frames_dir / f"{a.ref.everyayah}.png"
            fit = fr.render("content", png, **ctx)
            if fit < 0.7:
                _warn(f"{a.ref}: text scaled to {fit:.0%} to fit the safe area")
            fr.render("preview", work / "preview" / f"{a.ref.everyayah}.png", **ctx)
            frames.append(png)

    bg_path, bg_info = backgrounds.pick(cfg, passage.key)
    audio = video.write_audio(wavs, timeline, audio_dir / "passage.wav")
    out = cfg.out / f"{passage.slug}.mp4"
    video.compose(bg_path, static, frames, timeline, audio, out,
                  width=v["width"], height=v["height"], fade=float(v.get("fade_seconds", 0.25)))

    (work / "manifest.json").write_text(
        json.dumps(manifest(cfg, src, passage, timeline, bg_info), ensure_ascii=False, indent=2),
        encoding="utf-8")
    (work / "caption.txt").write_text(caption(cfg, passage), encoding="utf-8")
    shutil.rmtree(audio_dir)
    return RenderResult(passage=passage, video=out, workdir=work, seconds=timeline.seconds)
