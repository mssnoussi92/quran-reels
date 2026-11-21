"""The reels' exact subtitles on YouTube (captions.py): written after the upload, sent at night."""

import json

from quran_reels import captions as C
from quran_reels import playlists as P
from quran_reels.insights import youtube as Y

MANIFEST = {
    "passage": "2:255-255",
    "basmala": {"text": "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ",
                "translation": "In the name of Allah, the Entirely Merciful, the Especially Merciful.",
                "start": 0.0, "seconds": 4.2},
    "ayahs": [
        {"ref": "112:1", "text": "قُلْ هُوَ ٱللَّهُ أَحَدٌ", "translation": "Say, \"He is Allah, [who is] One,",
         "start": 4.2, "seconds": 3.5},
        {"ref": "2:255", "text": "WHOLE-AYAH", "translation": "WHOLE-AYAH", "start": 7.7, "seconds": 20.0,
         "screens": [{"start": 7.7, "words": "ٱللَّهُ لَآ إِلَٰهَ إِلَّا هُوَ", "translation": "Allah - there is no deity except Him,"},
                     {"start": 15.25, "words": "لَهُۥ مَا فِى ٱلسَّمَٰوَٰتِ", "translation": "To Him belongs whatever is in the heavens"}]},
    ],
}


def test_each_ayah_and_each_screen_is_a_subtitle_at_its_own_time():
    ar = C.srt(MANIFEST, "ar")
    assert ar.startswith("1\n00:00:00,000 --> 00:00:04,200\nبِسْمِ ٱللَّهِ")
    assert "2\n00:00:04,200 --> 00:00:07,700\nقُلْ هُوَ ٱللَّهُ أَحَدٌ\n" in ar
    assert "3\n00:00:07,700 --> 00:00:15,250\nٱللَّهُ لَآ إِلَٰهَ إِلَّا هُوَ\n" in ar
    assert "4\n00:00:15,250 --> 00:00:27,700\nلَهُۥ مَا فِى ٱلسَّمَٰوَٰتِ\n" in ar
    en = C.srt(MANIFEST, "en")
    assert "Say, \"He is Allah, [who is] One," in en and "To Him belongs whatever" in en
    assert "WHOLE-AYAH" not in ar and "WHOLE-AYAH" not in en    # the screens, not the whole


def test_the_tracks_wait_in_the_state_and_go_once(tmp_path):
    work = tmp_path / "out" / "002_255-255"
    work.mkdir(parents=True)
    (work / "manifest.json").write_text(json.dumps(MANIFEST, ensure_ascii=False), encoding="utf-8")
    folder = tmp_path / "state" / C.DIR
    path = C.queue(folder, "vid1", work / "manifest.json", "slot:2026-11-22/morning", ["ar", "en"])
    assert path == folder / "vid1.json"
    assert C.queue(folder, "vid2", tmp_path / "missing.json", "k", ["ar"]) is None

    class Channel:
        def __init__(self, fail=()):
            self.sent, self.fail = [], set(fail)

        def caption(self, video, lang, name, text):
            if lang in self.fail:
                raise RuntimeError("HTTP 403 forbidden")
            self.sent.append((video, lang, name, text[:2]))
            return f"cap-{lang}"

    assert C.upload_pending(folder, Channel(), dry_run=True) == [
        "subtitles ar → vid1 (slot:2026-11-22/morning)", "subtitles en → vid1 (slot:2026-11-22/morning)"]
    assert json.loads(path.read_text(encoding="utf-8"))["done"] == {}
    ch = Channel(fail={"en"})
    lines = C.upload_pending(folder, ch)
    assert ch.sent == [("vid1", "ar", "نص المصحف", "1\n")] and "not sent" in lines[-1]
    assert json.loads(path.read_text(encoding="utf-8"))["done"] == {"ar": "cap-ar"}
    ch = Channel()
    C.upload_pending(folder, ch)                                   # the next night: English only
    assert [s[1] for s in ch.sent] == ["en"]
    assert C.upload_pending(folder, Channel()) == []               # never twice


def test_a_track_goes_as_youtube_asks_a_multipart_upload():
    class Http:
        def request(self, method, url, params=None, data=None, json=None, headers=None, timeout=None):
            self.call = (method, url, params, data, headers)

            class R:
                status_code = 200

                def json(self):
                    return {"id": "capX"}
            return R()

    http = Http()
    assert P.Channel(Y.YouTube("cid", "secret", http), "at").caption("vid1", "ar", "نص المصحف",
                                                                     "1\n00:00:00,000 --> 00:00:01,000\nx\n") == "capX"
    method, url, params, data, headers = http.call
    assert (method, url) == ("POST", P.CAPTIONS)
    assert params == {"part": "snippet", "uploadType": "multipart"}
    assert headers["Content-Type"].startswith("multipart/related; boundary=")
    body = data.decode("utf-8")
    assert '"videoId": "vid1"' in body and '"language": "ar"' in body and "00:00:00,000 -->" in body
