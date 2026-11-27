"""A whole surah as one long 16:9 video (longvideo.py, config/long.yaml)."""

import json
import re

from quran_reels import config, longvideo


def manifest(seconds: float = 1746.0, ayahs: int = 110) -> dict:
    step = (seconds - 4) / ayahs
    return {
        "passage": f"18:1-{ayahs}", "seconds": seconds,
        "surah": {"number": 18, "name_ar": "الكهف", "name_en": "Al-Kahf"},
        "editions": {"reciter": "tawfeeq-sayegh"},
        "hashtags": ["#QuranWordsDaily", "#Quran", "#SurahAlKahf", "#سورة_الكهف", "#القرآن_الكريم"],
        "ayahs": [{"ref": f"18:{a}", "start": round(2.8 + (a - 1) * step, 3), "seconds": step,
                   "glosses": [{"word": "x"}] * (a % 3)} for a in range(1, ayahs + 1)],
    }


def test_config_is_16_9_with_every_word_meaning_the_basmala_and_youtubes_reciter():
    cfg = config.load()
    lcfg = longvideo.config_for(cfg)
    assert (lcfg.video["width"], lcfg.video["height"]) == (1920, 1080)
    assert lcfg.video["template"] == "long.html.j2" and "hook" not in lcfg.video
    assert lcfg.content["glosses"]["max_per_ayah"] >= 7          # Al-Kahf: 7 at most
    assert lcfg.content["basmala"]["enabled"] is True
    assert lcfg.content["reciter"]["name"] == cfg.project["platforms"]["youtube"]["reciter"]
    assert lcfg.out == cfg.out / "long"
    assert cfg.video["width"] == 1080 and "template" not in cfg.video   # the reels unchanged


def test_chapters_start_at_zero_and_at_their_first_ayah():
    cfg = config.load()
    m = manifest()
    lines = longvideo.chapters(longvideo.config_for(cfg), m)
    assert lines[0].startswith("0:00 ") and "(18:1-8)" in lines[0]
    cave = next(x for x in lines if "أصحاب الكهف" in x)
    start = next(a["start"] for a in m["ayahs"] if a["ref"] == "18:9")
    assert cave.startswith(f"{int(start) // 60}:{int(start) % 60:02d} ") and "(18:9-26)" in cave
    assert lines[-1].endswith("(18:99-110)")
    assert not re.search("[٠-٩]", "\n".join(lines))                  # numbers 123


def test_texts_arabic_first_title_under_youtubes_limit():
    cfg = config.load()
    t = longvideo.texts(longvideo.config_for(cfg), manifest())
    assert len(t["title"]) <= 100 and t["title"].startswith("سورة الكهف كاملة")
    first = t["description"].splitlines()[0]
    assert first.startswith("سورة الكهف كاملة") and "توفيق الصايغ" in first
    tags = t["description"].rstrip().splitlines()[-1].split()
    assert tags[:2] == ["#سورة_الكهف", "#القرآن_الكريم"] and "#QuranWordsDaily" in tags
    assert "Tafsir al-Muyassar" in t["description"] and "@quran_words_daily" in t["description"]


def test_pieces_cover_the_video_each_under_the_limit_cut_at_an_ayah():
    m = manifest()
    parts = longvideo.pieces(m, 600)
    assert parts[0][0] == 0 and parts[-1][1] == m["seconds"]
    assert all(b - a <= 600 for a, b in parts)
    assert all(parts[i][1] == parts[i + 1][0] for i in range(len(parts) - 1))
    starts = {a["start"] for a in m["ayahs"]}
    assert all(b in starts for _, b in parts[:-1])
    assert longvideo.pieces(manifest(seconds=300, ayahs=10), 600) == [(0.0, 300)]


def test_never_uploaded_twice(tmp_path, monkeypatch):
    cfg = config.load()
    work = tmp_path / "018_001-110"
    work.mkdir()
    (work / "manifest.json").write_text(json.dumps(manifest()), encoding="utf-8")
    video = tmp_path / "018_001-110.mp4"
    video.write_bytes(b"")
    state = tmp_path / "long.json"
    state.write_text(json.dumps({"18:1-110/tawfeeq-sayegh": {
        "youtube": {"status": "published", "url": "https://www.youtube.com/watch?v=x"}}}))

    def no_check(*a, **kw):
        raise AssertionError("checked and sent again")

    monkeypatch.setattr(longvideo, "check", no_check)
    assert longvideo.publish(cfg, 18, state, video=video) == 0


def test_nothing_goes_up_when_metas_check_is_not_clear(tmp_path, monkeypatch):
    cfg = config.load()
    work = tmp_path / "018_001-110"
    work.mkdir()
    (work / "manifest.json").write_text(json.dumps(manifest()), encoding="utf-8")
    video = tmp_path / "018_001-110.mp4"
    video.write_bytes(b"")
    monkeypatch.setattr(longvideo, "check", lambda *a: (False, ["check-1 : ❌ facebook : match"]))
    monkeypatch.setenv("YOUTUBE_UPLOAD_REFRESH_TOKEN", "")
    state = tmp_path / "long.json"
    assert longvideo.publish(cfg, 18, state, video=video) == 1
    assert json.loads(state.read_text())["18:1-110/tawfeeq-sayegh"]["youtube"]["status"] == "blocked"
