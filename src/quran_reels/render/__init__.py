"""Render a passage: frames (HTML → PNG), audio timeline, background, MP4.

out/
  093_001-003.mp4             the reel
  093_001-003/
    frames/                   static.png + one PNG per ayah (and the HTML they come from)
    preview/                  each ayah composed on the mockup gradient, for a quick look
    manifest.json             every text shown, with its edition and source URL; timings;
                              Facebook's short caption (captions.facebook); the loudness
                              measured and the gain applied (loudness)
    caption.txt               deterministic caption with the credits

A morning reel of the daily run may open on a question about one of its words (video.hook,
hook_for): a screen of its own (frames/hook.png, preview/hook.png), the narrator's voice asking it,
then the first ayah.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import date
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
LEVEL_TOLERANCE = 1.0  # LU: further from the target after the limiter, the render says so


_ARABIC = re.compile(r"[\u0600-\u06FF\u0750-\u077F]")


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


def arabic_first(cfg: Config, passage: Passage) -> list[str]:
    """hashtags() with the Arabic ones that say what the reel is in front (owner's trial,
    2026-11-23, platforms.<name>.hashtags: arabic_first): the broad Arabic tag, the surah's, the
    series' first Arabic tag, then the others in their order. On 101:1-11, « #القرآن_الكريم
    #سورة_القارعة #جزء_عم #QuranWordsDaily #Quran » are the five Instagram and TikTok keep, where
    hashtags() gives « #QuranWordsDaily #Quran #JuzAmma #SurahAlQariah #سورة_القارعة »."""
    conf = cfg.project.get("captions") or {}
    head = [*(t for t in conf.get("broad") or [] if _ARABIC.search(t)),
            f"#سورة_{_tag(passage.surah_name_ar, '_')}",
            *[t for t in passage.series_tags if _ARABIC.search(t)][:1]]
    return list(dict.fromkeys([*head, *hashtags(cfg, passage)]))


def platform_hashtags(cfg: Config, passage: Passage) -> dict[str, list[str]]:
    """The platforms that take their hashtags in another order than hashtags():
    {"instagram": [...], "tiktok": [...]} (platforms.<name>.hashtags: arabic_first)."""
    out = {}
    for name, conf in (cfg.project.get("platforms") or {}).items():
        if isinstance(conf, dict) and conf.get("hashtags") == "arabic_first":
            out[name] = arabic_first(cfg, passage)
    return out


def _hook_conf(cfg: Config | None) -> dict:
    project = getattr(cfg, "project", None) or {}
    return (project.get("video") or {}).get("hook") or {}


def hook_slot(cfg: Config | None, slot: str, day: date | None = None) -> bool:
    """Does a reel of this slot of the daily run, on `day`, open on the question of video.hook?
    Not before its `from` day (the owner's « dès mardi »: 2026-11-24)."""
    conf = _hook_conf(cfg)
    if not conf or slot not in (conf.get("slots") or []):
        return False
    start = conf.get("from")
    if start and day is not None:
        return day >= (start if isinstance(start, date) else date.fromisoformat(str(start)))
    return True


def hook_for(cfg: Config, passage: Passage, day: date) -> dict | None:
    """The question on a word of the reel (video.hook, owner's trial of 2026-11-23): the first
    word explained after the first ayah, so that its answer comes later in the reel, of max_words
    words at most if there is one; None without such a word (a single ayah) or without video.hook.
    The texts are the config's, the word the verse's as its gloss shows it. The narrator's voice
    asks one of `voices` (they turn with the day) and never says the word: it is written, then
    recited (no synthetic voice on the Quran)."""
    conf = _hook_conf(cfg)
    if not conf or not passage.segments:
        return None
    first = passage.segments[0]
    later = [g for a in passage.ayahs if a is not first for g in a.glosses]
    if not later:
        return None
    short = [g for g in later if len(words(g.word)) <= int(conf.get("max_words", 2))]
    g = (short or later)[0]
    voices = [cfg.root / v for v in conf.get("voices") or []]
    return {"word": g.word, "ref": str(g.ref), "question": str(conf.get("question") or ""),
            "en": str(conf.get("en") or ""),
            "voice": voices[day.toordinal() % len(voices)] if voices else None,
            "at": float(conf.get("voice_at", 0.3)), "after": float(conf.get("voice_after", 0.5)),
            "line": str(conf.get("voice_line") or ""),
            "line_short": str(conf.get("voice_line_short") or conf.get("voice_line") or "")}


def _recitation(cfg: Config) -> str:
    r = cfg.content["reciter"]
    return f"Recitation: {r['label']}" + (f" ({r['producer']})" if r.get("producer") else "")


def signatures(cfg: Config) -> dict[str, str]:
    """Platforms signed with another name than video.handle (platforms.<name>.signature):
    {"tiktok": "@quran.words.daily"}. Each gets its own MP4 (out/<passage>/<name>.mp4, the
    static layer drawn again with that name) and its caption ends with it."""
    main = cfg.video["handle"]
    out = {}
    for name, conf in (cfg.project.get("platforms") or {}).items():
        sig = conf.get("signature") if isinstance(conf, dict) else None
        if sig and sig != main:
            out[name] = str(sig)
    return out


def series_line(passage: Passage) -> str:
    """The series in both languages, the Arabic first, one counter last: «آيات الدعاء ·
    Supplications from the Quran · 3/38». Titles are always given in Arabic and English (owner,
    2026-11-09), **the Arabic first everywhere**, titles and descriptions, on every platform
    (owner, 2026-11-21: « je veux l'arabe d'abord partout titres et description », correcting a
    session that had put the English first back on Facebook, Instagram and TikTok; 74 % of the
    channel's views come from Arabic-speaking countries). The Arabic title is label_ar without its
    Arabic counter, the English one label_en without its counter (series titles never contain
    « · », tests/test_basmala.py)."""
    if not passage.label_en:
        return ""
    en, _, count = passage.label_en.partition(" · ")
    ar = passage.label_ar.partition(" · ")[0]
    return " · ".join(x for x in (ar, en, count) if x)


def surah_line(passage: Passage) -> str:
    """« سورة الضحى · Surah Ad-Duhaa (93:1-11) »: the Arabic first, everywhere (owner, 2026-11-21)."""
    return f"سورة {passage.surah_name_ar} · Surah {passage.surah_name_en} ({passage.reference})"


def caption(cfg: Config, passage: Passage, limit: int = CAPTION_LIMIT, voice: str = "") -> str:
    """Reference, Arabic and translation of each ayah, credits, handle.

    Too long for Instagram: the Arabic goes first, then the translation. Credits always stay.
    voice: the line that says a synthetic voice speaks in the reel (video.hook), after the credits.
    """
    c = cfg.content
    head = [surah_line(passage), ""]
    if passage.label_en:
        head = [series_line(passage), *head]
    tail = [
        _recitation(cfg),
        f"Translation: {c['translation']['label']}",
        f"Word meanings: {c['glosses']['label']}",
        *([voice] if voice else []),
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


def _credits(cfg: Config, passage: Passage) -> list[str]:
    """Reciter and translation; the word meanings when the reel shows some."""
    c = cfg.content
    credits = [_recitation(cfg), f"Translation: {c['translation']['label']}"]
    if any(a.glosses for a in passage.ayahs):
        g = c["glosses"]
        credits.append(f"Word meanings: {g.get('label_en') or g['label']}")
    return credits


def _reference(passage: Passage, label: bool = True) -> str:
    """The series line (when the passage has one) over the surah and its reference, each in
    Arabic first (owner, 2026-11-21: everywhere)."""
    return (series_line(passage) + "\n" if passage.label_en and label else "") + surah_line(passage)


def social_caption(cfg: Config, passage: Passage, limit: int = CAPTION_LIMIT,
                   verses: bool = True, voice: str = "") -> str:
    """Instagram's and TikTok's caption, without hashtags (owner, 2026-11-15: shorter, the Arabic
    kept): series and reference, the Arabic of each ayah (a verse is looked up by its words, and
    both apps search captions), the credits on one line, the handle. No translation: it is in the
    video, as the credits are. Over `limit`: without the Arabic, as Facebook's. `verses` False:
    never the Arabic (Instagram since 2026-11-21, `platforms.instagram.caption_verses`). voice: the
    line that says a synthetic voice speaks in the reel (video.hook), after the credits."""
    arabic = [passage.basmala.text] if passage.basmala else []
    arabic += [f"{a.text} ﴿{arabic_digits(a.ref.ayah)}﴾" for a in passage.ayahs]
    for body in ("\n".join(arabic) if verses else "", ""):
        blocks = [_reference(passage), body, " · ".join(_credits(cfg, passage)), voice,
                  cfg.video["handle"]]
        text = "\n\n".join(b for b in blocks if b) + "\n"
        if len(text) <= limit:
            break
    return text


def facebook_caption(cfg: Config, passage: Passage, tags: list[str], voice: str = "") -> str:
    """Facebook's short caption, hashtags included, at most platforms.facebook.
    max_caption_chars (400: Facebook's quality checklist asks for 10 to 400 characters, and
    flagged the full caption, 2026-11-09). "" when that limit is not set: Facebook then gets
    the full caption.

    Series, reference, the credits on one line, the handle, the first
    platforms.facebook.max_hashtags hashtags. Neither the Arabic text nor the translation (the
    owner's choice, 2026-11-09): the ayahs, their translation and the credits are in the video.
    Too long: hashtags go from the end (they are in priority order); the credits always stay.
    The word meanings are credited when the reel shows some; voice: the line that says a synthetic
    voice speaks in the reel (video.hook), kept with the credits.
    """
    conf = (cfg.project.get("platforms") or {}).get("facebook") or {}
    limit = int(conf.get("max_caption_chars") or 0)
    if not limit:
        return ""
    if conf.get("max_hashtags") is not None:
        tags = tags[:int(conf["max_hashtags"])]
    credits = _credits(cfg, passage)

    def text(n_tags: int, handle: bool = True, label: bool = True) -> str:
        blocks = [_reference(passage, label), " · ".join(credits), voice,
                  cfg.video["handle"] if handle else "", " ".join(tags[:n_tags])]
        return "\n\n".join(b for b in blocks if b)

    for n in range(len(tags), -1, -1):
        if len(out := text(n)) <= limit:
            return out
    for out in (text(0, handle=False), text(0, handle=False, label=False)):
        if len(out) <= limit:      # never with the project's labels: a config mistake
            return out
    _warn(f"{passage.key}: no Facebook caption fits in {limit} characters, even the reference "
          f"and credits alone; Facebook gets the full caption")
    return ""


def level_audio(cfg: Config, audio: Path, key: str = "") -> tuple[Path, dict | None]:
    """The reel's sound at video.loudness.lufs, under the ceiling video.loudness.limit
    (video.level: one gain for the whole reel, then a limiter): −16 LUFS, the owner's choice
    (2026-11-10), as in the thematic videos; 8 published reels went from −19.4 to −10.7 LUFS.
    Returns the levelled WAV, beside `audio`, and what the manifest keeps (loudness): target,
    ceiling, loudness measured, gain applied, loudness after. (audio, None) when the block is
    absent or null: the sound as recorded."""
    conf = cfg.video.get("loudness") or {}
    if conf.get("lufs") is None:
        return audio, None
    target = float(conf["lufs"])
    limit = float(conf["limit"]) if conf.get("limit") is not None else video.LIMIT
    dest = audio.with_name(f"{audio.stem}.level.wav")
    done = video.level(audio, dest, target, limit)
    name, result = key or audio.name, done["result_lufs"]
    if done["measured_lufs"] is None:
        _warn(f"{name}: no loudness measured (silent?), the sound is left as it is")
    elif result is None or abs(result - target) > LEVEL_TOLERANCE:
        _warn(f"{name}: {result} LUFS after the limiter, target {target:g} "
              f"({done['measured_lufs']} LUFS before, {done['gain_db']:+.1f} dB)")
    return dest, {"target_lufs": target, "limit": limit, **done}


def manifest(cfg: Config, src: Sources, passage: Passage, timeline: video.Timeline,
             background: dict, screens: dict[str, list[dict]] | None = None,
             loudness: dict | None = None) -> dict:
    """screens: {ref: [{start, words, translation}]} for the ayahs shown on several screens;
    loudness: what level_audio measured and applied (None: the sound was not levelled)."""
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
        "loudness": loudness,
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
                   glosses: dict | None = None, variants: bool = True,
                   hook_day: date | None = None) -> RenderResult:
    """label_ar / label_en: the series the passage belongs to, on the first frame and caption;
    series_tags: its hashtags; background: an id of config/backgrounds.yaml imposed by the
    owner (on-demand reels), otherwise chosen from what the passage says; glosses: the word
    meanings chosen by the owner (passage.build), otherwise the usual rules; variants: also the
    MP4 of each platform signed with its own name (signatures), the same frames and sound;
    hook_day: open on the question of video.hook (hook_for), on a screen of its own before the
    first ayah, its voice the one of that day (the daily run's slots of hook_slot; their YouTube
    version is rendered without)."""
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
    # The question's screen (video.hook) comes first, its voice in the lead of the first ayah.
    asked = hook_for(cfg, passage, hook_day) if hook_day else None
    lead = float(v.get("lead_seconds", 0.4))
    intro = None
    if asked:
        if not asked["voice"] or not asked["voice"].is_file():
            raise SystemExit(f"video.hook: no voice file ({asked['voice']})")
        said = audio_dir / "hook-voice.wav"
        n_said = video.decode(asked["voice"], audio_dir / "hook-raw.wav")
        target = (v.get("loudness") or {}).get("lufs")
        if target is not None:
            video.level(audio_dir / "hook-raw.wav", said, float(target))
        else:
            shutil.copyfile(audio_dir / "hook-raw.wav", said)
        at = round(asked["at"] * video.SAMPLE_RATE)
        spf = video.SAMPLE_RATE // v["fps"]
        n_intro = at + n_said + round(asked["after"] * video.SAMPLE_RATE)
        n_intro = -(-n_intro // spf) * spf                      # whole video frames
        intro = {"samples": n_intro, "at": at, "wav": said}
        lead += n_intro / video.SAMPLE_RATE
    timeline = video.build_timeline(samples, fps=v["fps"], lead=lead,
                                    tail=float(v.get("tail_seconds", 1.2)))
    p = cfg.content["passage"]
    whole = passage.start == 1 and passage.end == src.quran.chapters[passage.surah]["verses_count"]
    themed = bool(label_ar or label_en)       # a theme passage may be one short du'a
    if timeline.seconds > p["max_seconds"] or (
            timeline.seconds < p["min_seconds"] and not whole and not themed):
        _warn(f"{passage.key} lasts {timeline.seconds:.1f} s, outside "
              f"{p['min_seconds']}–{p['max_seconds']} s (rendered anyway)")

    frames, screens, shown = [], [], {}
    signed = signatures(cfg) if variants else {}
    with FrameRenderer(cfg) as fr:
        static = frames_dir / "static.png"
        fr.render("static", static)
        statics = {}
        for platform, sig in signed.items():
            statics[platform] = frames_dir / f"static.{platform}.png"
            fr.render("static", statics[platform], handle=sig)
        if intro:
            intro["png"] = frames_dir / "hook.png"
            fr.render("hook", intro["png"], hook=asked)
            fr.render("hookpreview", work / "preview" / "hook.png", hook=asked)
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
        timeline = video.build_timeline(samples, fps=v["fps"], lead=lead,
                                        tail=float(v.get("tail_seconds", 1.2)), screens=screens)

    bg_path, bg_info = backgrounds.pick(cfg, passage, force=background)
    if zoom := backgrounds.push_in(cfg, bg_info, timeline.seconds):
        bg_info["push_in"] = zoom
    audio = video.write_audio(wavs, timeline, audio_dir / "passage.wav",
                              intro=(intro["wav"], intro["at"]) if intro else None)
    audio, levelled = level_audio(cfg, audio, passage.key)    # every version below plays it
    out = cfg.out / f"{passage.slug}.mp4"
    for platform in [None, *signed]:
        video.compose(bg_path, statics[platform] if platform else static, frames, timeline,
                      audio, work / f"{platform}.mp4" if platform else out, width=v["width"],
                      height=v["height"], fade=float(v.get("fade_seconds", 0.25)), zoom=zoom,
                      intro=(intro["png"], intro["samples"] // (video.SAMPLE_RATE // v["fps"]))
                      if intro else None)

    tags = hashtags(cfg, passage)
    record = manifest(cfg, src, passage, timeline, bg_info, shown, levelled)
    voice = ""
    if intro:                   # the question: its texts, its word, its voice, where the answer is
        record["hook"] = {"word": asked["word"], "question": asked["question"], "en": asked["en"],
                          "answer": asked["ref"], "voice": asked["voice"].name,
                          "seconds": round(intro["samples"] / video.SAMPLE_RATE, 3)}
        voice = asked["line"]
    if by_platform := platform_hashtags(cfg, passage):     # publish.load_reel: Reel.for_platform
        record["platform_hashtags"] = by_platform
    room = CAPTION_LIMIT - len(" ".join(tags)) - 2       # all of them, even on Instagram
    # What Facebook gets, and Instagram and TikTok (publish.load_reel); caption.txt keeps it all
    # (YouTube, by hand).
    record["captions"] = {"social": social_caption(cfg, passage, room, voice=voice)}
    # Instagram without the verses (the owner, 2026-11-21: « Instagram coupe parfois la couverture à cause
    # des mots dans les versets »); TikTok keeps them.
    insta = (cfg.project.get("platforms") or {}).get("instagram") or {}
    if insta.get("caption_verses") is False:
        record["captions"]["instagram"] = social_caption(cfg, passage, room, verses=False,
                                                         voice=voice)
    if short := facebook_caption(cfg, passage, tags, voice=asked["line_short"] if intro else ""):
        record["captions"]["facebook"] = short
    if signed:                  # publish.load_reel: their MP4 and caption
        record["variants"] = {p: {"video": f"{p}.mp4", "signature": sig,
                                  "instead_of": v["handle"]} for p, sig in signed.items()}
    (work / "manifest.json").write_text(json.dumps(record, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    reel_text = Reel(passage, out, caption(cfg, passage, room, voice=voice), hashtags=tags).text()
    (work / "caption.txt").write_text(reel_text, encoding="utf-8")
    shutil.rmtree(audio_dir)
    return RenderResult(passage=passage, video=out, workdir=work, seconds=timeline.seconds)
