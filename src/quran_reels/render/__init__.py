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
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from quran_reels import __version__
from quran_reels.arabic import arabic_digits
from quran_reels.config import Config
from quran_reels.models import Ayah, Passage, Reel
from quran_reels.passage import build
from quran_reels.render import video
from quran_reels.render.frames import FrameRenderer, ayah_context
from quran_reels.sources import Sources, backgrounds, basmala_stem


@dataclass
class RenderResult:
    passage: Passage
    video: Path
    workdir: Path
    seconds: float


CAPTION_LIMIT = 2200   # Instagram


def _tag(text: str, joiner: str = "") -> str:
    """One hashtag word: 'Ali 'Imran' → 'AliImran'; with joiner '_', 'آل عمران' → 'آل_عمران'."""
    return re.sub(r"[^\w]", "", re.sub(r"\s+", joiner, text.strip()))


def hashtags(cfg: Config, passage: Passage) -> list[str]:
    """The caption's hashtags, most important first, without duplicates (see project.yaml)."""
    c = cfg.content
    conf = cfg.project.get("captions") or {}
    broad = list(conf.get("broad") or [])
    series = list(passage.series_tags)
    glossed = any(a.glosses for a in passage.ayahs)
    tags = [conf.get("brand"), *broad[:1], *series[:1],
            f"#Surah{_tag(passage.surah_name_en)}", f"#سورة_{_tag(passage.surah_name_ar, '_')}",
            *broad[1:], *series[1:], *(c["reciter"].get("hashtags") or []),
            *((c["glosses"].get("hashtags") or []) if glossed else [])]
    return list(dict.fromkeys(t for t in tags if t))


def caption(cfg: Config, passage: Passage, limit: int = CAPTION_LIMIT) -> str:
    """Reference, Arabic and translation of each ayah, credits, handle.

    Too long for Instagram: the Arabic goes first, then the translation. Credits always stay.
    """
    c = cfg.content
    head = [f"Surah {passage.surah_name_en} ({passage.key}) · سورة {passage.surah_name_ar}", ""]
    if passage.label_en:
        head = [passage.label_en, *head]
    tail = [
        f"Recitation: {c['reciter']['label']}" + (f" ({c['reciter']['producer']})"
                                                   if c["reciter"].get("producer") else ""),
        f"Translation: {c['translation']['label']}",
        f"Word meanings: {c['glosses']['label']}",
        "",
        cfg.video["handle"],
    ]
    for with_arabic, with_translation in ((True, True), (False, True), (False, False)):
        body = [passage.basmala.text, ""] if passage.basmala and with_arabic else []
        for a in passage.ayahs:
            if with_arabic:
                body.append(f"{a.text} ﴿{arabic_digits(a.ref.ayah)}﴾")
            if with_translation:
                body.append(f"{a.ref.ayah}. {a.translation}")
            if with_arabic or with_translation:
                body.append("")
        text = "\n".join(head + body + tail) + "\n"
        if len(text) <= limit:
            break
    return text


def manifest(cfg: Config, src: Sources, passage: Passage, timeline: video.Timeline,
             background: dict) -> dict:
    c = cfg.content
    starts = timeline.starts()
    basmala = None
    if passage.basmala:
        b, starts = passage.basmala, starts[1:]
        basmala = {"ref": str(b.ref), "text": b.text, "translation": b.translation,
                   "audio": src.audio.basmala_url(passage.surah, basmala_stem(cfg)),
                   "start": round(timeline.starts()[0], 3), "seconds": round(b.seconds or 0, 3)}
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
            "audio": src.audio.base_url,
        },
        "reciter": {k: c["reciter"][k] for k in ("name", "label", "producer", "rights")
                    if c["reciter"].get(k)},
        "background": background,
        "series": {"ar": passage.label_ar, "en": passage.label_en} if passage.label_en
        or passage.label_ar else None,
        "hashtags": hashtags(cfg, passage),
        "basmala": basmala,
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


def render_passage(cfg: Config, key: str, label_ar: str = "", label_en: str = "",
                   series_tags: tuple[str, ...] = ()) -> RenderResult:
    """label_ar / label_en: the series the passage belongs to, on the first frame and caption;
    series_tags: its hashtags."""
    src = Sources.from_config(cfg)
    passage = build(cfg, key, src)
    passage.label_ar, passage.label_en = label_ar, label_en
    passage.series_tags = tuple(series_tags)
    v = cfg.video
    work = cfg.out / passage.slug
    if work.exists():
        shutil.rmtree(work)
    frames_dir, audio_dir = work / "frames", work / "audio"

    # Audio first: it decides how long each frame stays on screen.
    def name(a: Ayah) -> str:
        return "basmala" if a is passage.basmala else a.ref.everyayah

    samples = []
    wavs = []
    for a in passage.segments:
        wav = audio_dir / f"{name(a)}.wav"
        n = video.decode(a.audio, wav)
        a.seconds = n / video.SAMPLE_RATE
        samples.append(n)
        wavs.append(wav)
    timeline = video.build_timeline(samples, fps=v["fps"], lead=float(v.get("lead_seconds", 0.4)),
                                    tail=float(v.get("tail_seconds", 1.2)))
    p = cfg.content["passage"]
    whole = passage.start == 1 and passage.end == src.quran.chapters[passage.surah]["verses_count"]
    themed = bool(label_ar or label_en)       # a theme passage may be one short du'a
    if timeline.seconds > p["max_seconds"] or (
            timeline.seconds < p["min_seconds"] and not whole and not themed):
        _warn(f"{passage.key} lasts {timeline.seconds:.1f} s, outside "
              f"{p['min_seconds']}–{p['max_seconds']} s (rendered anyway)")

    frames = []
    with FrameRenderer(cfg) as fr:
        static = frames_dir / "static.png"
        fr.render("static", static)
        for a in passage.segments:
            ctx = ayah_context(passage, a, basmala=a is passage.basmala,
                               first=a is passage.segments[0])
            png = frames_dir / f"{name(a)}.png"
            fit = fr.render("content", png, **ctx)
            if fit < 0.7:
                _warn(f"{name(a)}: text scaled to {fit:.0%} to fit the safe area")
            fr.render("preview", work / "preview" / f"{name(a)}.png", **ctx)
            frames.append(png)

    bg_path, bg_info = backgrounds.pick(cfg, passage)
    audio = video.write_audio(wavs, timeline, audio_dir / "passage.wav")
    out = cfg.out / f"{passage.slug}.mp4"
    video.compose(bg_path, static, frames, timeline, audio, out,
                  width=v["width"], height=v["height"], fade=float(v.get("fade_seconds", 0.25)))

    (work / "manifest.json").write_text(
        json.dumps(manifest(cfg, src, passage, timeline, bg_info), ensure_ascii=False, indent=2),
        encoding="utf-8")
    tags = hashtags(cfg, passage)
    room = CAPTION_LIMIT - len(" ".join(tags)) - 2       # all of them, even on Instagram
    reel_text = Reel(passage, out, caption(cfg, passage, room), hashtags=tags).text()
    (work / "caption.txt").write_text(reel_text, encoding="utf-8")
    shutil.rmtree(audio_dir)
    return RenderResult(passage=passage, video=out, workdir=work, seconds=timeline.seconds)
