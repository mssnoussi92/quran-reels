"""The question on a word of the reel (video.hook) and the Arabic hashtags first (owner's trial
of 2026-11-23, docs/insights.md « La question du mot »)."""

from __future__ import annotations

import shutil
import subprocess
import wave
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from quran_reels.config import Config
from quran_reels.models import Ayah, AyahRef, Passage, Reel, WordGloss
from quran_reels.render import (
    arabic_first,
    hashtags,
    hook_for,
    hook_slot,
    platform_hashtags,
    video,
)

HOOK = {"slots": ["morning"], "max_words": 2, "question": "تعرف معناها؟",
        "en": "Do you know what this word means?",
        "voices": ["assets/hook/voice-1.flac", "assets/hook/voice-2.flac", "assets/hook/voice-3.flac"],
        "voice_line": "🎙️ صوت مولَّد بالذكاء الاصطناعي · AI-generated voice",
        "voice_line_short": "🎙️ صوت بالذكاء الاصطناعي · AI voice"}
DAY = date(2026, 11, 24)


def cfg_with(video_conf: dict | None = None, platforms: dict | None = None) -> Config:
    return Config(root=Path("."), backgrounds=[], gloss_headwords={}, project={
        "content": {"reciter": {"hashtags": ["#OmarHisham", "#عمر_هشام_العربي"]},
                    "glosses": {"hashtags": ["#تفسير_القرآن"]}},
        "captions": {"brand": "#QuranWordsDaily", "broad": ["#Quran", "#القرآن_الكريم"]},
        **({"video": video_conf} if video_conf is not None else {}),
        "platforms": platforms or {}})


def gloss(surah: int, ayah: int, word: str) -> WordGloss:
    return WordGloss(AyahRef(surah, ayah), word, "…", "ar-muyassar-ghareeb", positions=(0,))


def passage(glosses: dict[int, list[str]], start: int = 1, end: int = 3,
            basmala: bool = False) -> Passage:
    p = Passage(101, start, end, "القارعة", "Al-Qari'ah", series_tags=("#JuzAmma", "#جزء_عم"))
    for n in range(start, end + 1):
        p.ayahs.append(Ayah(AyahRef(101, n), "…", "…",
                            glosses=[gloss(101, n, w) for w in glosses.get(n, [])]))
    if basmala:
        p.basmala = Ayah(AyahRef(1, 1), "…", "…")
    return p


def test_the_question_asks_a_word_whose_answer_comes_later():
    cfg = cfg_with({"hook": HOOK})
    p = passage({1: ["ٱلْقَارِعَةُ"], 2: ["مَا ٱلْقَارِعَةُ"], 5: ["كَٱلْعِهْنِ ٱلْمَنفُوشِ"]})
    asked = hook_for(cfg, p, DAY)
    assert asked["word"] == "مَا ٱلْقَارِعَةُ" and asked["ref"] == "101:2"   # not ayah 1's
    assert asked["question"] == "تعرف معناها؟"
    assert asked["en"] == "Do you know what this word means?"


def test_the_three_voices_turn_with_the_day():
    cfg = cfg_with({"hook": HOOK})
    p = passage({2: ["أَنقَضَ"]})
    names = [hook_for(cfg, p, DAY + timedelta(days=i))["voice"].name for i in range(4)]
    assert len(set(names[:3])) == 3 and names[3] == names[0]
    assert hook_for(cfg, p, DAY)["voice"] == hook_for(cfg, p, DAY)["voice"]    # the same day


def test_a_short_word_is_preferred_to_a_long_phrase():
    cfg = cfg_with({"hook": HOOK})
    p = passage({2: ["وَوَضَعْنَا عَنكَ وِزْرَكَ"], 3: ["أَنقَضَ"]})
    assert hook_for(cfg, p, DAY)["word"] == "أَنقَضَ"
    p = passage({2: ["وَوَضَعْنَا عَنكَ وِزْرَكَ"]})          # only a long one: it is asked
    assert hook_for(cfg, p, DAY)["word"] == "وَوَضَعْنَا عَنكَ وِزْرَكَ"


def test_no_question_without_a_word_after_the_first_screen_or_without_the_setting():
    p = passage({1: ["أَعْثَرْنَا"]}, start=21, end=21)     # a single ayah: its answer at once
    assert hook_for(cfg_with({"hook": HOOK}), p, DAY) is None
    assert hook_for(cfg_with({}), passage({2: ["أَنقَضَ"]}), DAY) is None
    # With the basmala first, the first ayah's words come after it.
    p = passage({1: ["ٱلْقَارِعَةُ"]}, basmala=True)
    assert hook_for(cfg_with({"hook": HOOK}), p, DAY)["ref"] == "101:1"


def test_only_the_slots_named_open_on_the_question():
    cfg = cfg_with({"hook": HOOK})
    assert hook_slot(cfg, "morning") and not hook_slot(cfg, "evening")
    assert not hook_slot(cfg_with({}), "morning") and not hook_slot(cfg_with(), "morning")
    assert not hook_slot(None, "morning")


def test_the_voice_files_are_in_the_repository():
    from quran_reels import config

    cfg = config.load()
    conf = cfg.video["hook"]
    assert len(conf["voices"]) == 3 and all((cfg.root / v).is_file() for v in conf["voices"])
    assert cfg.project["platforms"]["youtube"]["hook"] is False      # the control


def test_the_captions_say_a_synthetic_voice_speaks():
    from quran_reels.render import caption, facebook_caption, social_caption

    cfg = cfg_with({"handle": "@quran_words_daily"},
                   {"facebook": {"max_caption_chars": 400, "max_hashtags": 8}})
    cfg.project["content"].update({"translation": {"label": "Sahih International"},
                                   "glosses": {"label": "Tafsir al-Muyassar"}})
    cfg.project["content"]["reciter"]["label"] = "Fares Abbad"
    p = passage({2: ["أَنقَضَ"]})
    line, short = HOOK["voice_line"], HOOK["voice_line_short"]
    assert line in social_caption(cfg, p, voice=line)
    assert line not in social_caption(cfg, p)
    fb = facebook_caption(cfg, p, hashtags(cfg, p), voice=short)
    assert short in fb and len(fb) <= 400
    assert line in caption(cfg, p, voice=line)


def test_instagram_and_tiktok_take_the_arabic_hashtags_first():
    platforms = {"instagram": {"hashtags": "arabic_first"}, "tiktok": {"hashtags": "arabic_first"},
                 "facebook": {}}
    cfg = cfg_with({}, platforms)
    p = passage({2: ["مَا ٱلْقَارِعَةُ"]})
    assert hashtags(cfg, p)[:5] == ["#QuranWordsDaily", "#Quran", "#JuzAmma", "#SurahAlQariah",
                                    "#سورة_القارعة"]
    assert arabic_first(cfg, p)[:5] == ["#القرآن_الكريم", "#سورة_القارعة", "#جزء_عم",
                                        "#QuranWordsDaily", "#Quran"]
    assert sorted(arabic_first(cfg, p)) == sorted(hashtags(cfg, p))      # the same, reordered
    assert set(platform_hashtags(cfg, p)) == {"instagram", "tiktok"}
    assert platform_hashtags(cfg_with({}), p) == {}


def test_each_platform_gets_its_own_order_of_hashtags():
    reel = Reel(passage=passage({}), video=Path("r.mp4"), caption="c",
                hashtags=["#QuranWordsDaily", "#Quran", "#سورة_القارعة"],
                social="short", variants={"tiktok": (Path("t.mp4"), "signed")},
                platform_hashtags={"instagram": ["#سورة_القارعة", "#QuranWordsDaily"],
                                   "tiktok": ["#سورة_القارعة", "#Quran"]})
    assert reel.for_platform("instagram").text(5) == "short\n\n#سورة_القارعة #QuranWordsDaily\n"
    tiktok = reel.for_platform("tiktok")
    assert tiktok.video == Path("t.mp4") and tiktok.text(5) == "signed\n\n#سورة_القارعة #Quran\n"
    assert reel.for_platform("youtube").hashtags == ["#QuranWordsDaily", "#Quran", "#سورة_القارعة"]


def _png(path: Path, color: str, size: int = 64) -> Path:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"color=c={color}:s={size}x{size}", "-frames:v", "1", str(path)], check=True)
    return path


def _clear_png(path: Path, size: int = 64) -> Path:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"color=c=black@0.0:s={size}x{size},format=rgba", "-frames:v", "1",
                    str(path)], check=True)
    return path


def _mean(mp4: Path, at: float) -> float:
    """The mean brightness of one frame, 0 to 255."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{at}", "-i", str(mp4), "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True,
                         check=True).stdout
    return sum(raw) / len(raw)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_the_question_has_its_screen_and_its_voice_before_the_first_ayah(tmp_path):
    """Black background, a white question screen, clear ayah layers: white for its frames (it
    grows, so its centre), then gone; its voice in the lead, before the first ayah's sound; the
    reel lasts as long as its timeline."""
    fps, sr = 10, video.SAMPLE_RATE
    bg = _png(tmp_path / "bg.png", "black")
    clear = _clear_png(tmp_path / "clear.png")
    hook = _png(tmp_path / "hook.png", "white")
    voice = tmp_path / "voice.wav"
    with wave.open(str(voice), "wb") as w:              # 0.5 s of a loud constant
        w.setnchannels(video.CHANNELS)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"\x00\x40" * (video.CHANNELS * sr // 2))
    ayah = tmp_path / "ayah.wav"
    with wave.open(str(ayah), "wb") as w:
        w.setnchannels(video.CHANNELS)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"\0" * 2 * sr * video.CHANNELS * 2)
    timeline = video.build_timeline([2 * sr], fps=fps, lead=1.5 + 0.2, tail=0.0)
    audio = video.write_audio([ayah], timeline, tmp_path / "a.wav", intro=(voice, sr // 4))
    with wave.open(str(audio)) as w:
        raw = w.readframes(w.getnframes())
    step = video.CHANNELS * 2
    level = [abs(int.from_bytes(raw[i * step:i * step + 2], "little", signed=True))
             for i in (sr // 8, sr // 2, sr, 2 * sr)]
    assert level[0] == 0 and level[1] > 10_000 and level[3] == 0      # the voice from 0.25 s
    out = video.compose(bg, clear, [clear], timeline, audio, tmp_path / "r.mp4",
                        width=64, height=64, fade=0.2, intro=(hook, 15))
    assert _mean(out, 0.8) > 150            # the question's screen, white over black
    assert _mean(out, 2.5) < 30             # gone after its 15 frames (1.5 s): the first ayah
    with pytest.raises(ValueError):         # never longer than the lead it takes its place in
        video.compose(bg, clear, [clear], timeline, audio, tmp_path / "s.mp4",
                      width=64, height=64, intro=(hook, 100))


def test_youtubes_version_is_made_again_without_the_question(monkeypatch, tmp_path):
    """The reel by YouTube's own reciter, with the question: YouTube (the control) gets it again
    from the same reciter without it, checked by Meta as any YouTube version (`plain`)."""
    from quran_reels import daily
    from quran_reels import reciters as rec

    made = []

    def render(cfg, key, label_ar="", label_en="", series_tags=(), variants=True, hook_day=None):
        made.append((cfg.out, variants, hook_day))
        return SimpleNamespace(video=cfg.out / "101_001-011.mp4")

    import quran_reels.render as render_mod
    monkeypatch.setattr(render_mod, "render_passage", render)
    monkeypatch.setattr(rec, "with_reciter", lambda cfg, name: cfg)
    reel = SimpleNamespace(text=lambda n=None: "caption\n")
    monkeypatch.setattr(daily.publish_mod, "load_reel", lambda video: reel)
    cfg = Config(root=tmp_path, backgrounds=[], gloss_headwords={}, project={
        "content": {"reciters": {"sayegh": {"label": "Tawfiq As-Sayegh"}}},
        "video": {"hook": HOOK},
        "platforms": {"youtube": {"mode": "manual", "reciter": "sayegh", "hook": False}}})
    p = SimpleNamespace(item=SimpleNamespace(key="101:1-11", label_ar="", label_en="",
                                             series=SimpleNamespace(hashtags=())))
    assert daily.youtube_version(cfg, p, "sayegh", set()) is None       # no question: the same
    got = daily.youtube_version(cfg, p, "sayegh", set(), hooked=True)
    assert made == [(tmp_path / "out" / "youtube", False, None)]
    assert got["reciter"] == "sayegh" and got["plain"] and got["always"]
    assert got["video"] == "youtube/101_001-011.mp4"
    # YouTube taking the question too: the same video, as before.
    cfg.project["platforms"]["youtube"]["hook"] = True
    assert daily.youtube_version(cfg, p, "sayegh", set(), hooked=True) is None


def test_the_ticket_says_why_youtube_has_another_video():
    from quran_reels import notify

    item = {"youtube": {"reciter": "sayegh", "video": "youtube/x.mp4", "caption": "c",
                        "label": "Tawfiq As-Sayegh", "instead_of": "Tawfiq As-Sayegh",
                        "always": True, "plain": True}}
    text = "\n".join(notify._youtube(item))
    assert "sans la question du début" in text
