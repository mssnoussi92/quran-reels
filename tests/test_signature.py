"""A platform signed with its own name (render.signatures): TikTok, where @quran_words_daily is
someone else's account (2026-11-09), gets its own MP4 and its caption ends with its own name;
the others keep video.handle. No network, no Chromium."""

import json
from pathlib import Path
from types import SimpleNamespace

from quran_reels import publish as publish_mod
from quran_reels.config import Config, load
from quran_reels.models import Passage, PublishResult, PublishStatus, Reel, with_signature
from quran_reels.render import signatures

MAIN, TIKTOK = "@quran_words_daily", "@quran.words.daily"


def cfg(platforms):
    return Config(root=Path("."), backgrounds=[], gloss_headwords={},
                  project={"video": {"handle": MAIN}, "platforms": platforms})


def test_tiktok_is_signed_with_its_own_name():
    assert signatures(load()) == {"tiktok": TIKTOK}
    assert signatures(cfg({"tiktok": {"signature": MAIN}, "facebook": {"enabled": True}})) == {}


def test_only_the_signature_line_changes():
    text = f"Surah Ad-Duhaa (93:1-11) · سورة الضحى\n\n{MAIN}\n"
    assert with_signature(text, MAIN, TIKTOK) == f"Surah Ad-Duhaa (93:1-11) · سورة الضحى\n\n{TIKTOK}\n"
    assert with_signature(f"x {MAIN}\n", MAIN, TIKTOK) == f"x {MAIN}\n"     # a whole line only


def rendered(tmp_path, with_mp4=True):
    """What render_passage leaves: out/093_001-011.mp4 and out/093_001-011/."""
    video, work = tmp_path / "093_001-011.mp4", tmp_path / "093_001-011"
    work.mkdir()
    video.write_bytes(b"main")
    if with_mp4:
        (work / "tiktok.mp4").write_bytes(b"tiktok")
    tags = ["#QuranWordsDaily", "#Quran"]
    (work / "manifest.json").write_text(json.dumps({
        "passage": "93:1-11", "surah": {"name_ar": "الضحى", "name_en": "Ad-Duhaa"},
        "ayahs": [{"ref": "93:1", "glosses": [], "start": 1.0, "seconds": 2.0}],
        "hashtags": tags, "captions": {"facebook": f"Surah Ad-Duhaa (93:1-11)\n\n{MAIN}"},
        "variants": {"tiktok": {"video": "tiktok.mp4", "signature": TIKTOK,
                                "instead_of": MAIN}}}), encoding="utf-8")
    (work / "caption.txt").write_text(f"Surah Ad-Duhaa (93:1-11)\n\n{MAIN}\n\n{' '.join(tags)}\n",
                                      encoding="utf-8")
    return video


def test_tiktok_gets_its_own_video_and_caption(tmp_path):
    reel = publish_mod.load_reel(rendered(tmp_path))
    tiktok = reel.for_platform("tiktok")
    assert tiktok.video.name == "tiktok.mp4" and tiktok.hashtags == reel.hashtags
    assert reel.text_for("tiktok", 5).split("\n\n")[1] == TIKTOK
    assert reel.text_for("instagram", 5).split("\n\n")[1] == MAIN
    assert MAIN in reel.text_for("facebook")
    assert reel.for_platform("instagram") is reel


def test_without_its_mp4_tiktok_gets_the_main_reel(tmp_path):
    reel = publish_mod.load_reel(rendered(tmp_path, with_mp4=False))
    assert reel.for_platform("tiktok") is reel        # an artifact from before: no failure


def test_publish_sends_tiktok_its_own_reel(monkeypatch, tmp_path):
    video = rendered(tmp_path)
    sent = []

    class TikTok:
        def publish(self, reel, dry_run=False):
            sent.append((reel.video.name, reel.caption.split("\n\n")[1].strip()))
            return PublishResult("tiktok", PublishStatus.DRAFT)

    monkeypatch.setattr(publish_mod, "tiktok_publisher", lambda: TikTok())
    publish_mod.publish_reel(SimpleNamespace(project={}), video, ["tiktok"], False)
    assert sent == [("tiktok.mp4", TIKTOK)]


def test_a_reel_without_variants_is_itself_everywhere():
    reel = Reel(Passage(93, 1, 11, "الضحى", "Ad-Duhaa"), Path("x.mp4"), f"x\n\n{MAIN}\n")
    assert reel.for_platform("tiktok") is reel
