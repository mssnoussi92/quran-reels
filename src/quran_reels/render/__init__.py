"""Render a passage: frames (HTML → PNG), audio timeline, background, MP4.

out/
  093_001-003.mp4             the reel
  093_001-003/
    frames/                   static.png + one PNG per ayah (and the HTML they come from)
    preview/                  each ayah composed on the mockup gradient, for a quick look
    manifest.json             every text shown, with its edition and source URL; timings;
                              Facebook's short caption (captions.facebook)
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
from quran_reels.arabic import arabic_digits, words
from quran_reels.config import Config
from quran_reels.models import Ayah, Passage, Reel
from quran_reels.passage import build
from quran_reels.render import screens as screens_mod
from quran_reels.render import video
from quran_reels.render.frames import FrameRenderer, ayah_context, part_context
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


def _recitation(cfg: Config) -> str:
    r = cfg.content["reciter"]
    return f"Recitation: {r['label']}" + (f" ({r['producer']})" if r.get("producer") else "")


def caption(cfg: Config, passage: Passage, limit: int = CAPTION_LIMIT) -> str:
    """Reference, Arabic and translation of each ayah, credits, handle.

    Too long for Instagram: the Arabic goes first, then the translation. Credits always stay.
    """
    c = cfg.content
    head = [f"Surah {passage.surah_name_en} ({passage.key}) · سورة {passage.surah_name_ar}", ""]
    if passage.label_en:
        head = [passage.label_en, *head]
    tail = [
        _recitation(cfg),
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


def facebook_caption(cfg: Config, passage: Passage, tags: list[str]) -> str:
    """Facebook's short caption, hashtags included, at most platforms.facebook.
    max_caption_chars (400: Facebook's quality checklist asks for 10 to 400 characters, and
    flagged the full caption, 2026-11-09). "" when that limit is not set: Facebook then gets
    the full caption.

    Series, reference, the English translation if everything fits, the credits on one line,
    the handle, the first platforms.facebook.max_hashtags hashtags. No Arabic text: the ayahs,
    their translation and the credits are in the video. Too long: the translation goes first,
    then hashtags from the end (they are in priority order); the credits always stay. The
    word meanings are credited when the reel shows some.
    """
    conf = (cfg.project.get("platforms") or {}).get("facebook") or {}
    limit = int(conf.get("max_caption_chars") or 0)
    if not limit:
        return ""
    if conf.get("max_hashtags") is not None:
        tags = tags[:int(conf["max_hashtags"])]
    c = cfg.content
    ref = f"{passage.surah}:{passage.start}" + (
        f"-{passage.end}" if passage.end != passage.start else "")
    credits = [_recitation(cfg), f"Translation: {c['translation']['label']}"]
    if any(a.glosses for a in passage.ayahs):
        g = c["glosses"]
        credits.append(f"Word meanings: {g.get('label_en') or g['label']}")
    translation = "\n".join(f"{a.ref.ayah}. {a.translation}" for a in passage.ayahs)

    def text(with_translation: bool, n_tags: int, handle: bool = True,
             label: bool = True) -> str:
        head = (passage.label_en + "\n" if passage.label_en and label else "") + \
            f"Surah {passage.surah_name_en} ({ref})"
        blocks = [head, translation if with_translation else "", " · ".join(credits),
                  cfg.video["handle"] if handle else "", " ".join(tags[:n_tags])]
        return "\n\n".join(b for b in blocks if b)

    tries = [(True, len(tags)), *((False, n) for n in range(len(tags), -1, -1))]
    for with_translation, n in tries:
        if len(out := text(with_translation, n)) <= limit:
            return out
    for out in (text(False, 0, handle=False), text(False, 0, handle=False, label=False)):
        if len(out) <= limit:      # never with the project's labels: a config mistake
            return out
    _warn(f"{passage.key}: no Facebook caption fits in {limit} characters, even the reference "
          f"and credits alone; Facebook gets the full caption")
    return ""


def manifest(cfg: Config, src: Sources, passage: Passage, timeline: video.Timeline,
             background: dict, screens: dict[str, list[dict]] | None = None) -> dict:
    """screens: {ref: [{start, words, translation}]} for the ayahs shown on several screens."""
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
                **({"screens": [{**sc, "start": round(start + sc["start"], 3)}
                                for sc in (screens or {})[str(a.ref)]]}
                   if str(a.ref) in (screens or {}) else {}),
            }
            for a, start in zip(passage.ayahs, starts)
        ],
        "renderer": f"quran-reels {__version__}",
    }


def _warn(msg: str) -> None:
    print(f"warning: {msg}", file=sys.stderr)


def _long_ayah(fr: FrameRenderer, src: Sources, passage: Passage, a: Ayah, samples: int,
               stem: Path, first: bool) -> list[tuple[Path, dict, int]] | None:
    """A long ayah on 2 to MAX_PARTS screens, each readable (render/screens.py): [(png,
    context, samples)], or None when no split reads better than the whole."""
    tokens = words(a.text)
    seconds = samples / video.SAMPLE_RATE
    starts = getattr(src.audio, "word_starts", None)
    word_starts = starts(a.ref.surah, a.ref.ayah) if starts else None
    best: tuple[float, list] | None = None
    for k in range(2, screens_mod.MAX_PARTS + 1):
        parts = screens_mod.plan(tokens, a.translation, k, seconds, word_starts)
        if len(parts) < 2:
            break
        out, fits = [], []
        for i, part in enumerate(parts):
            ctx = part_context(passage, a, part.first, part.end, part.translation,
                               first=first and i == 0)
            png = stem.with_name(f"{stem.name}-{i + 1}.png")
            fits.append(fr.render("content", png, **ctx))
            out.append((png, ctx, part.start))
        if best is None or min(fits) > best[0]:
            best = (min(fits), out)
        if min(fits) >= screens_mod.MIN_FIT:
            break
    if best is None:
        return None
    fit, out = best
    if fit < screens_mod.MIN_FIT:
        _warn(f"{a.ref}: on {len(out)} screens, text still scaled to {fit:.0%}")
    bounds = [round(t * video.SAMPLE_RATE) for _, _, t in out[1:]]
    edges = [0, *bounds, samples]
    print(f"{a.ref}: {len(out)} screens from " + ", ".join(f"{t:.1f} s" for _, _, t in out),
          file=sys.stderr)
    return [(png, ctx, edges[i + 1] - edges[i]) for i, (png, ctx, _) in enumerate(out)]


def render_passage(cfg: Config, key: str, label_ar: str = "", label_en: str = "",
                   series_tags: tuple[str, ...] = (), background: str | None = None,
                   glosses: dict | None = None) -> RenderResult:
    """label_ar / label_en: the series the passage belongs to, on the first frame and caption;
    series_tags: its hashtags; background: an id of config/backgrounds.yaml imposed by the
    owner (on-demand reels), otherwise chosen from what the passage says; glosses: the word
    meanings chosen by the owner (passage.build), otherwise the usual rules."""
    src = Sources.from_config(cfg)
    passage = build(cfg, key, src, glosses)
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

    frames, screens, shown = [], [], {}
    with FrameRenderer(cfg) as fr:
        static = frames_dir / "static.png"
        fr.render("static", static)
        for a, n in zip(passage.segments, samples, strict=True):
            first = a is passage.segments[0]
            ctx = ayah_context(passage, a, basmala=a is passage.basmala, first=first)
            png = frames_dir / f"{name(a)}.png"
            fit = fr.render("content", png, **ctx)
            if fit < screens_mod.MIN_FIT and a is not passage.basmala:
                parts = _long_ayah(fr, src, passage, a, n, frames_dir / name(a), first)
                if parts:
                    at = 0
                    for i, (png_i, ctx_i, n_i) in enumerate(parts):
                        fr.render("preview", work / "preview" / f"{name(a)}-{i + 1}.png",
                                  **ctx_i)
                        frames.append(png_i)
                        screens.append(n_i)
                        shown.setdefault(str(a.ref), []).append({
                            "start": at / video.SAMPLE_RATE,
                            "words": " ".join(t["text"] for t in ctx_i["tokens"]),
                            "translation": ctx_i["translation"]})
                        at += n_i
                    continue
                _warn(f"{name(a)}: text scaled to {fit:.0%} to fit the safe area")
            fr.render("preview", work / "preview" / f"{name(a)}.png", **ctx)
            frames.append(png)
            screens.append(n)
    if len(screens) != len(samples):
        timeline = video.build_timeline(samples, fps=v["fps"],
                                        lead=float(v.get("lead_seconds", 0.4)),
                                        tail=float(v.get("tail_seconds", 1.2)), screens=screens)

    bg_path, bg_info = backgrounds.pick(cfg, passage, force=background)
    if zoom := backgrounds.push_in(cfg, bg_info, timeline.seconds):
        bg_info["push_in"] = zoom
    audio = video.write_audio(wavs, timeline, audio_dir / "passage.wav")
    out = cfg.out / f"{passage.slug}.mp4"
    video.compose(bg_path, static, frames, timeline, audio, out,
                  width=v["width"], height=v["height"], fade=float(v.get("fade_seconds", 0.25)),
                  zoom=zoom)

    tags = hashtags(cfg, passage)
    record = manifest(cfg, src, passage, timeline, bg_info, shown)
    if short := facebook_caption(cfg, passage, tags):    # what Facebook gets (publish.py)
        record["captions"] = {"facebook": short}
    (work / "manifest.json").write_text(json.dumps(record, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    room = CAPTION_LIMIT - len(" ".join(tags)) - 2       # all of them, even on Instagram
    reel_text = Reel(passage, out, caption(cfg, passage, room), hashtags=tags).text()
    (work / "caption.txt").write_text(reel_text, encoding="utf-8")
    shutil.rmtree(audio_dir)
    return RenderResult(passage=passage, video=out, workdir=work, seconds=timeline.seconds)
