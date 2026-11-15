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
                                           "statistics": {"subscriberCount": "57", "videoCount": "22"},
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


S = {"days": 35, "refresh_days": 8, "tolerance_hours": 48,
     "checkpoints": {"48h": 48, "7d": 168, "28d": 672}}


def posts_of_meta():
    """What the Meta reading left: a reel's twins on Facebook, a theme film in 9:16."""
    return {
        "facebook:1": {"platform": "facebook", "key": "slot:2026-11-14/morning", "kind": "reel-morning",
                       "label": "107:1-7", "ref": {"passage": "107:1-7", "reciter": "fares_abbad"},
                       "published": "2026-11-14T06:23:00+00:00", "first_line": "Surah Al-Ma'un (107:1-7)",
                       "snapshots": {}},
        "facebook:2": {"platform": "facebook", "key": "theme:moussa-khidr/short-1",
                       "kind": "theme-short", "label": "Why did he tear…", "ref": {},
                       "published": "2026-11-13T18:00:00+00:00", "snapshots": {}},
    }


def test_each_public_video_is_a_post_beside_its_twins(tmp_path):
    path = tmp_path / "insights.json"
    path.write_text(json.dumps({"posts": posts_of_meta(), "manual": [
        {"platform": "youtube", "video": "107:1-7", "seen": "2026-11-15", "m": {"views": 1},
         "source": "youtube-api"},                                    # the first evening's way
        {"platform": "tiktok", "video": "107:1-7", "seen": "2026-11-15", "m": {"views": 9}}]}))
    line = Y.collect(path, S, now=NOW, client=Y.YouTube("cid", "secret", FakeHttp()), env=ENV)
    assert "57 subscribers" in line and "3 public videos" in line
    data = json.loads(path.read_text())
    yt = {uid: r for uid, r in data["posts"].items() if r["platform"] == "youtube"}
    assert set(yt) == {"youtube:v1", "youtube:v2", "youtube:v3"}            # v4 private, v5 old
    v1 = yt["youtube:v1"]
    assert v1["key"] == "slot:2026-11-14/morning" and v1["kind"] == "reel-morning"
    assert v1["url"] == "https://www.youtube.com/shorts/v1" and v1["seconds"] == 36
    assert v1["snapshots"]["latest"]["m"] == {"views": 120, "likes": 9, "comments": 1,
                                              "avg_watch": 20.0, "watch_pct": 55.5, "shares": 0,
                                              "follows": 0}
    assert "48h" not in v1["snapshots"]                     # 39 h old: not yet
    assert yt["youtube:v3"]["key"] == "youtube:v3" and yt["youtube:v3"]["kind"] == "other"
    assert data["accounts"]["youtube"]["2026-11-15"] == {"followers_count": 57, "media_count": 22}
    assert [m["platform"] for m in data["manual"]] == ["tiktok"]           # screenshots kept
    assert data["listed_youtube"] == NOW.isoformat(timespec="seconds")
    # two days later the 48 h checkpoint is taken, from the same video
    Y.collect(path, S, now=datetime(2026, 11, 16, 7, 0, tzinfo=UTC),
              client=Y.YouTube("cid", "secret", FakeHttp()), env=ENV)
    snaps = json.loads(path.read_text())["posts"]["youtube:v1"]["snapshots"]
    assert set(snaps) == {"48h", "latest"} and snaps["48h"]["age_h"] == 48.5


def test_a_short_titled_by_hand_finds_its_reel_and_a_film_its_vertical_twin():
    published = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)
    posts = {
        "facebook:a": {"platform": "facebook", "key": "slot:2026-11-09/morning", "kind": "reel-morning",
                       "label": "111:1-5", "ref": {"passage": "111:1-5"},
                       "published": "2026-11-09T06:20:00+00:00",
                       "first_line": "Surah Al-Masad (111:1-5) · سورة المسد"},
        "facebook:k1": {"platform": "facebook", "key": "slot:2026-11-06/evening", "kind": "reel-kahf",
                        "published": "2026-11-06T18:30:00+00:00",
                        "first_line": "Surah Al-Kahf on Friday · سورة الكهف يوم الجمعة · 1/36"},
        "facebook:k2": {"platform": "facebook", "key": "slot:2026-11-13/evening", "kind": "reel-kahf",
                        "published": "2026-11-13T21:19:00+00:00",
                        "first_line": "Surah Al-Kahf on Friday · سورة الكهف يوم الجمعة · 2/36"},
        "facebook:f": {"platform": "facebook", "key": "theme:moussa-khidr-9x16/film"},
    }
    assert Y.match("Surah Al-Masad · سورة المسد", "", published, posts)["key"] == "slot:2026-11-09/morning"
    assert Y.match("سورة الكهف - Surah Al-Kahf", "", datetime(2026, 11, 7, tzinfo=UTC),
                   posts)["key"] == "slot:2026-11-06/evening"
    assert Y.match("سورة الكهف - Surah Al-Kahf", "", datetime(2026, 11, 14, tzinfo=UTC),
                   posts)["key"] == "slot:2026-11-13/evening"
    assert Y.match("Something else", "", published, posts) == {
        "key": "", "kind": "other", "label": "Something else", "ref": {}}

    class Themes:
        def match(self, title, platform):
            from types import SimpleNamespace
            return SimpleNamespace(id="moussa-khidr/film", kind="theme-film", title_en="Moses",
                                   title_ar="موسى", series="", part="Le film") if "Moses" in title else None

    film = Y.match("Moses and al-Khidr · موسى والخضر", "", published, posts, Themes())
    assert film["key"] == "theme:moussa-khidr-9x16/film" and film["kind"] == "theme-film"


def test_without_analytics_the_counters_are_still_kept(tmp_path):
    path = tmp_path / "insights.json"
    line = Y.collect(path, S, now=NOW, client=Y.YouTube("cid", "secret", FakeHttp(False)), env=ENV)
    assert "YouTube Analytics unavailable" in line and "has not been used" in line
    v2 = json.loads(path.read_text())["posts"]["youtube:v2"]["snapshots"]["latest"]["m"]
    assert v2 == {"views": 625, "likes": 40, "comments": 3}


def test_a_dry_run_saves_nothing_and_no_secrets_means_screenshots(tmp_path, monkeypatch):
    path = tmp_path / "insights.json"
    Y.collect(path, S, now=NOW, client=Y.YouTube("cid", "secret", FakeHttp()), env=ENV,
              dry_run=True)
    assert not path.exists()
    for name in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", Y.REFRESH_SECRET):
        monkeypatch.delenv(name, raising=False)
    assert "screenshots only" in Y.collect(path, S, now=NOW)


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


def test_the_page_shows_youtube_like_facebook_and_instagram():
    """Subscribers, the comparison at 48 h and each video's line: YouTube beside Meta; a YouTube
    post is judged gone by YouTube's own listing, never by Meta's."""
    from zoneinfo import ZoneInfo

    from quran_reels.catalog import stats as St

    snap = {"at": "2026-11-16T07:00:00+00:00", "age_h": 48.5, "m": {"views": 120, "likes": 9}}
    data = {
        "listed": "2026-11-16T01:00:00+00:00", "listed_youtube": "2026-11-16T01:05:00+00:00",
        "accounts": {"youtube": {"2026-11-08": {"followers_count": 40},
                                 "2026-11-15": {"followers_count": 57}}},
        "posts": {
            "youtube:v1": {"platform": "youtube", "key": "slot:2026-11-14/morning",
                           "kind": "reel-morning", "label": "107:1-7", "ref": {},
                           "published": "2026-11-14T06:30:00+00:00",
                           "seen": "2026-11-16T01:05:00+00:00",
                           "url": "https://www.youtube.com/shorts/v1",
                           "snapshots": {"48h": snap, "latest": snap}},
            "youtube:gone": {"platform": "youtube", "key": "youtube:gone", "kind": "other",
                             "label": "made private", "published": "2026-11-12T06:30:00+00:00",
                             "seen": "2026-11-15T01:05:00+00:00", "snapshots": {"latest": snap}},
        }}
    out = St.build(data, {"days": 35}, datetime(2026, 11, 16, 8, tzinfo=UTC), ZoneInfo("Europe/Paris"))
    assert [(f["platform"], f["now"], f["delta"]) for f in out["followers"]] == [("YouTube", 57, 17)]
    assert [(k["kind"], k["platform"], k["views"]) for k in out["kinds"]] == [
        ("Reel du matin (lecture)", "YouTube", 120)]
    rows = {v["key"]: v["rows"] for v in out["videos"]}
    assert set(rows) == {"slot:2026-11-14/morning"}
    assert rows["slot:2026-11-14/morning"][0]["url"] == "https://www.youtube.com/shorts/v1"
