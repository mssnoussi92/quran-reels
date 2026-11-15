"""The channel's YouTube numbers (insights/youtube.py): read only, matched to our videos by their
title, kept where the screenshots went. Fake HTTP: no network."""

import json
from datetime import UTC, datetime

import pytest

from quran_reels.insights import youtube as Y


class Answer:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


class FakeHttp:
    """Google's answers by URL: tokens, channel, uploads, videos, analytics."""

    def __init__(self, analytics_ok=True):
        self.calls, self.analytics_ok = [], analytics_ok

    def post(self, url, data=None, timeout=None):
        self.calls.append(("POST", url, data))
        if data.get("grant_type") == "authorization_code":
            return Answer(200, {"access_token": "at", "refresh_token": "rt",
                                "scope": " ".join(Y.SCOPES)})
        return Answer(200, {"access_token": "at"})

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(("GET", url, params))
        assert headers == {"Authorization": "Bearer at"}
        if url.endswith("/channels"):
            return Answer(200, {"items": [{"id": "UC1", "snippet": {"title": "Quran Words Daily"},
                                           "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]})
        if url.endswith("/playlistItems"):
            items = [
                ("v1", "2026-11-14T06:30:00Z", "Surah Al-Ma'un (107:1-7) · سورة الماعون"),
                ("v2", "2026-11-13T18:00:00Z", "Why did he tear a hole in the boat? · ليه خرق السفينة؟"),
                ("v3", "2026-11-12T06:30:00Z", "Surah At-Tawbah (9:51) · سورة التوبة"),
                ("v4", "2026-11-10T06:30:00Z", "a private test"),
                ("v5", "2026-09-01T06:30:00Z", "too old"),
            ]
            return Answer(200, {"items": [
                {"contentDetails": {"videoId": i, "videoPublishedAt": p}, "snippet": {"title": t}}
                for i, p, t in items]})
        if url.endswith("/videos"):
            ids = params["id"].split(",")
            assert "v5" not in ids
            stats = {"v1": ("120", "9", "1", "PT36S"), "v2": ("625", "40", "3", "PT1M33S"),
                     "v3": ("80", "5", None, "PT14S"), "v4": ("2", "0", "0", "PT10S")}
            return Answer(200, {"items": [
                {"id": i, "status": {"privacyStatus": "private" if i == "v4" else "public"},
                 "snippet": {"title": ""}, "contentDetails": {"duration": stats[i][3]},
                 "statistics": {k: v for k, v in zip(("viewCount", "likeCount", "commentCount"),
                                                     stats[i][:3], strict=False) if v}}
                for i in ids if i in stats]})
        if url == Y.ANALYTICS:
            if not self.analytics_ok:
                return Answer(403, {"error": {"message": "YouTube Analytics API has not been used"}})
            assert params["filters"] == "video==v1,v2,v3" and params["ids"] == "channel==MINE"
            return Answer(200, {
                "columnHeaders": [{"name": n} for n in ("video", "views", "averageViewDuration",
                                                        "averageViewPercentage", "shares",
                                                        "subscribersGained")],
                "rows": [["v2", 600, 68, 73.2, 4, 2], ["v1", 110, 20, 55.5, 0, 0]]})
        raise AssertionError(url)


ENV = Y.YouTubeEnv("cid", "secret", "refresh")
NOW = datetime(2026, 11, 15, 22, 0, tzinfo=UTC)


def test_a_reel_is_matched_by_its_reference_a_theme_video_by_its_title():
    assert Y.video_key("Surah Al-Ma'un (107:1-7) · سورة الماعون") == "107:1-7"
    assert Y.video_key("Surah At-Tawbah (9:51) · سورة التوبة") == "9:51-51"
    assert Y.video_key("Supplications · آيات الدعاء · 3/38 · Surah Ghafir (40:60)") == "40:60-60"
    assert Y.video_key(" Why did he tear a hole in the boat? · ليه خرق السفينة؟ ") == (
        "Why did he tear a hole in the boat? · ليه خرق السفينة؟")
    assert Y.seconds("PT1M33S") == 93 and Y.seconds("PT14S") == 14 and Y.seconds("") is None
    # titled by hand: the reference is in the description pasted from reel.html (caption.txt)
    assert Y.video_key("Surah At-Tawbah · سورة التوبة",
                       "The seven munjiyat verses · السبع آيات المنجيات · 1/7\n"
                       "Surah At-Tawbah (9:51) · سورة التوبة\n\nبِسْمِ") == "9:51-51"
    # a theme video's description quotes verses, never on a line of its own starting « Surah »
    assert Y.video_key("Light in the Quran… how many times?",
                       "The word 'light' in the Quran… The first time, a light that is lost (2:17).") == (
        "Light in the Quran… how many times?")


def test_the_public_videos_go_where_the_screenshots_went(tmp_path):
    path = tmp_path / "insights.json"
    line = Y.collect(path, 35, now=NOW, client=Y.YouTube("cid", "secret", FakeHttp()), env=ENV)
    assert "3 public videos" in line and "Quran Words Daily" in line
    manual = {e["video"]: e for e in json.loads(path.read_text())["manual"]}
    assert set(manual) == {"107:1-7", "9:51-51",
                           "Why did he tear a hole in the boat? · ليه خرق السفينة؟"}
    boat = manual["Why did he tear a hole in the boat? · ليه خرق السفينة؟"]
    assert boat["m"] == {"views": 625, "likes": 40, "comments": 3, "avg_watch": 68.0,
                         "watch_pct": 73.2, "shares": 4, "follows": 2}
    assert boat["platform"] == "youtube" and boat["source"] == "youtube-api"
    assert boat["published"] == "2026-11-13" and boat["seen"] == "2026-11-15"
    assert manual["9:51-51"]["m"] == {"views": 80, "likes": 5}       # no analytics row yet
    # the next night replaces nothing of today's, adds its own day
    Y.collect(path, 35, now=datetime(2026, 11, 16, 22, 0, tzinfo=UTC),
              client=Y.YouTube("cid", "secret", FakeHttp()), env=ENV)
    assert len(json.loads(path.read_text())["manual"]) == 6


def test_without_analytics_the_counters_are_still_kept(tmp_path):
    path = tmp_path / "insights.json"
    line = Y.collect(path, 35, now=NOW, client=Y.YouTube("cid", "secret", FakeHttp(False)), env=ENV)
    assert "YouTube Analytics unavailable" in line and "has not been used" in line
    assert len(json.loads(path.read_text())["manual"]) == 3


def test_a_dry_run_saves_nothing_and_no_secrets_means_screenshots(tmp_path, monkeypatch):
    path = tmp_path / "insights.json"
    Y.collect(path, 35, now=NOW, client=Y.YouTube("cid", "secret", FakeHttp()), env=ENV,
              dry_run=True)
    assert not path.exists()
    for name in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", Y.REFRESH_SECRET):
        monkeypatch.delenv(name, raising=False)
    assert "screenshots only" in Y.collect(path, 35, now=NOW)


def test_errors_never_carry_the_token():
    class Refused(FakeHttp):
        def get(self, url, params=None, headers=None, timeout=None):
            return Answer(401, {"error": {"message": "Invalid Credentials"}})

    with pytest.raises(Y.YouTubeError) as e:
        Y.YouTube("cid", "secret", Refused()).channel("at")
    assert "Invalid Credentials" in str(e.value) and "at" not in str(e.value).split()


def test_sign_in_saves_the_refresh_token_once(monkeypatch):
    saved = {}
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "cid")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "secret")
    monkeypatch.setattr("quran_reels.gh_secrets.save_secret", lambda n, v: saved.update({n: v}))
    http = FakeHttp()
    assert Y.auth("https://x/youtube-callback.html", "the-code", Y.YouTube("cid", "secret", http)) == 0
    assert saved == {Y.REFRESH_SECRET: "rt"}
    exchange = http.calls[0][2]
    assert exchange["redirect_uri"] == "https://x/youtube-callback.html" and exchange["code"] == "the-code"


def test_the_sign_in_address_asks_read_only_scopes_and_a_refresh_token():
    url = Y.auth_url("cid.apps.googleusercontent.com", "https://x/cb", "s")
    assert "access_type=offline" in url and "prompt=consent" in url
    assert "youtube.readonly" in url and "yt-analytics.readonly" in url and "upload" not in url
