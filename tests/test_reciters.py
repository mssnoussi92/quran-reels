"""The reciter catalogue, and planning durations from EveryAyah file sizes."""

import pytest

from quran_reels.config import RECITER_ENV, load, resolve_reciter
from quran_reels.sources.everyayah import EveryAyah


def project(reciter="hudhaifi"):
    return {"content": {"reciter": reciter, "reciters": {
        "alafasy": {"id": "Alafasy_128kbps", "label": "Mishary Rashid Alafasy", "timings_id": 7},
        "hudhaifi": {"id": "Hudhaify_128kbps", "label": "Ali Al-Hudhaifi", "kbps": 128}}}}


def test_the_name_picks_an_entry_and_the_environment_overrides_it(monkeypatch):
    monkeypatch.delenv(RECITER_ENV, raising=False)
    assert resolve_reciter(project())["content"]["reciter"]["id"] == "Hudhaify_128kbps"
    monkeypatch.setenv(RECITER_ENV, "alafasy")
    r = resolve_reciter(project())["content"]["reciter"]
    assert (r["name"], r["timings_id"]) == ("alafasy", 7)


def test_unknown_reciter_is_refused(monkeypatch):
    monkeypatch.delenv(RECITER_ENV, raising=False)
    with pytest.raises(SystemExit, match="unknown reciter 'minshawi'"):
        resolve_reciter(project("minshawi"))


def test_every_configured_reciter_can_be_planned(monkeypatch):
    monkeypatch.delenv(RECITER_ENV, raising=False)
    catalogue = load().content["reciters"]
    for name, r in catalogue.items():
        assert r["id"] and r["label"], name
        assert r.get("timings_id") or r.get("kbps") or r.get("surah_url"), \
            f"{name}: no way to plan durations"
        if r.get("producer"):
            assert r.get("rights"), f"{name}: say where its licence comes from"


class Sizes:
    def __init__(self, sizes):
        self.sizes, self.asked = sizes, []

    def size(self, url):
        self.asked.append(url)
        return self.sizes[url.rsplit("/", 1)[1]]


def test_seconds_from_constant_bitrate_sizes_are_cached(tmp_path):
    http = Sizes({"093001.mp3": 37326, "093002.mp3": 54463})
    audio = EveryAyah(tmp_path, http, "Hudhaify_128kbps")
    seconds = audio.seconds(93, 2, kbps=128)
    assert round(seconds[1], 2) == 2.33 and round(seconds[2], 2) == 3.40   # ffprobe: 2.33, 3.40
    assert EveryAyah(tmp_path, http, "Hudhaify_128kbps").seconds(93, 2, 128) == seconds
    assert len(http.asked) == 2                                             # second time: cache
