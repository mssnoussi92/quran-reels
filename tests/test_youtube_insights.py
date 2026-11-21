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

    def __init__(self, analytics_ok=True, days_ok=True, engaged_ok=True, search_ok=True):
        self.calls, self.analytics_ok, self.days_ok = [], analytics_ok, days_ok
        self.engaged_ok, self.search_ok = engaged_ok, search_ok

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
            if "engagedViews" in params["metrics"] and not self.engaged_ok:
                return Answer(400, {"error": {"message": "Unknown identifier (engagedViews)"}})
            if params["dimensions"] == "insightTrafficSourceType":
                if not self.search_ok:
                    return Answer(403, {"error": {"message": "forbidden"}})
                assert params["metrics"] == "views" and params["filters"].startswith("video==v")
                return Answer(200, {"columnHeaders": [{"name": "insightTrafficSourceType"},
                                                      {"name": "views"}],
                                    "rows": TRAFFIC.get(params["filters"], [])})
            if params["dimensions"] == "day":
                if not self.days_ok:
                    return Answer(400, {"error": {"message": "Unknown identifier (day)"}})
                assert params["sort"] == "day" and params["ids"] == "channel==MINE"
                names = ["day", *params["metrics"].split(",")]
                rows = [r[:len(names)] for r in DAYS.get(params["filters"], [])
                        if params["startDate"] <= r[0] <= params["endDate"]]
                return Answer(200, {"columnHeaders": [{"name": n} for n in names], "rows": rows})
            assert params["filters"] == "video==v1,v2,v3" and params["ids"] == "channel==MINE"
            rows = [["v2", 600, 68, 73.2, 4, 2, 480], ["v1", 110, 20, 55.5, 0, 0, 70]]
            names = ["video", *params["metrics"].split(",")]
            assert names[:6] == ["video", "views", "averageViewDuration", "averageViewPercentage",
                                 "shares", "subscribersGained"]
            return Answer(200, {"columnHeaders": [{"name": n} for n in names],
                                "rows": [r[:len(names)] for r in rows]})
        raise AssertionError(url)


# YouTube Analytics day by day (Pacific days): day, views, average view duration, average view
# percentage, likes, comments, shares, subscribers gained, engaged views
DAYS = {
    "video==v1": [("2026-11-13", 30, 20, 60.0, 2, 0, 0, 0, 20), ("2026-11-14", 70, 22, 58.0, 5, 1, 0, 1, 40),
                  ("2026-11-15", 20, 18, 50.0, 1, 0, 1, 0, 10), ("2026-11-16", 9, 15, 40.0, 0, 0, 0, 0, 5)],
    "video==v3": [("2026-11-11", 10, 12, 85.0, 1, 0, 0, 0, 9), ("2026-11-12", 50, 11, 80.0, 3, 1, 1, 2, 40),
                  ("2026-11-13", 20, 9, 70.0, 1, 0, 0, 0, 15), ("2026-11-14", 5, 9, 70.0, 0, 0, 0, 0, 3)],
}
# views by traffic source (lifetime of the window)
TRAFFIC = {
    "video==v1": [("SHORTS", 80), ("YT_SEARCH", 15), ("EXT_URL", 5)],
    "video==v2": [("SHORTS", 500), ("YT_SEARCH", 25)],
    "video==v3": [],
}

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
    before = {"youtube:v2": {"platform": "youtube", "snapshots": {    # tonight's first reading
        "48h": {"at": "2026-11-15T21:00:00+00:00", "age_h": 51.0, "m": {"views": 600}}}}}
    path.write_text(json.dumps({"posts": posts_of_meta() | before, "manual": [
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
                                              "follows": 0, "engaged": 70, "search_pct": 15.0}
    assert "48h" not in v1["snapshots"]                     # 39 h old: not yet
    # 9:51 (v3), published 2026-11-12 06:30 UTC, 22:30 the day before in Pacific time: its 48 h
    # are YouTube's days 11-11 to 11-13, counted once 11-13 is two days old, though first read
    # at 3 days and a half
    assert yt["youtube:v3"]["snapshots"]["48h"] == {
        "at": NOW.isoformat(timespec="seconds"), "days": ["2026-11-11", "2026-11-13"],
        "age_h": 49.5, "m": {"views": 80, "likes": 5, "comments": 1, "shares": 1, "follows": 2,
                             "engaged": 64, "avg_watch": 10.6, "watch_pct": 78.1}}
    assert "48h" not in yt["youtube:v2"]["snapshots"]       # as on Meta, the first evening: gone
    assert yt["youtube:v3"]["key"] == "youtube:v3" and yt["youtube:v3"]["kind"] == "other"
    assert data["accounts"]["youtube"]["2026-11-15"] == {"followers_count": 57, "media_count": 22}
    assert [m["platform"] for m in data["manual"]] == ["tiktok"]           # screenshots kept
    assert data["listed_youtube"] == NOW.isoformat(timespec="seconds")
    # its own 48 h (Pacific days 11-13 to 11-15) once 11-15 is two days old
    Y.collect(path, S, now=datetime(2026, 11, 16, 7, 0, tzinfo=UTC),
              client=Y.YouTube("cid", "secret", FakeHttp()), env=ENV)
    assert "48h" not in json.loads(path.read_text())["posts"]["youtube:v1"]["snapshots"]
    Y.collect(path, S, now=datetime(2026, 11, 18, 7, 0, tzinfo=UTC),
              client=Y.YouTube("cid", "secret", FakeHttp()), env=ENV)
    snaps = json.loads(path.read_text())["posts"]["youtube:v1"]["snapshots"]
    assert set(snaps) == {"48h", "latest"} and snaps["48h"]["days"] == ["2026-11-13", "2026-11-15"]
    assert snaps["48h"]["age_h"] == 49.5 and snaps["48h"]["m"]["views"] == 120
    assert snaps["latest"]["at"] == "2026-11-18T07:00:00+00:00"   # read every night


def test_a_checkpoint_covers_whole_pacific_days_from_48_to_72_hours():
    morning = datetime(2026, 11, 12, 6, 30, tzinfo=UTC)       # 07:30 Paris, 22:30 the day before
    evening = datetime(2026, 11, 12, 18, 30, tzinfo=UTC)      # 19:30 Paris, 10:30 Pacific
    d = lambda s: datetime.fromisoformat(s).date()
    assert Y.window(morning, 48) == (d("2026-11-11"), d("2026-11-13"))       # 49.5 h
    assert Y.window(evening, 48) == (d("2026-11-12"), d("2026-11-14"))       # 61.5 h
    assert Y.window(morning, 168) == (d("2026-11-11"), d("2026-11-18"))
    assert Y.total([], d("2026-11-11"), d("2026-11-13")) is None
    zero = Y.total([{"day": "2026-11-11", "views": 0}], d("2026-11-11"), d("2026-11-13"))
    assert zero == {"views": 0, "likes": 0, "comments": 0, "shares": 0, "follows": 0}


def test_without_analytics_by_day_the_checkpoints_are_taken_as_on_meta(tmp_path):
    path = tmp_path / "insights.json"
    later = datetime(2026, 11, 16, 7, 0, tzinfo=UTC)
    line = Y.collect(path, S, now=later, client=Y.YouTube("cid", "secret", FakeHttp(days_ok=False)),
                     env=ENV)
    assert "by day unavailable" in line and "Unknown identifier" in line
    snaps = json.loads(path.read_text())["posts"]["youtube:v1"]["snapshots"]
    assert set(snaps) == {"48h", "latest"} and snaps["48h"]["age_h"] == 48.5
    assert "days" not in snaps["48h"]


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
    assert [v["name"] for v in rows["slot:2026-11-14/morning"][0]["views"]] == ["48h"]
    # YouTube's 48 h counted on its days the same night as its latest reading: both shown
    days = snap | {"days": ["2026-11-13", "2026-11-15"], "m": {"views": 100}}
    data["posts"]["youtube:v1"]["snapshots"] = {"48h": days, "latest": snap}
    out = St.build(data, {"days": 35}, datetime(2026, 11, 16, 8, tzinfo=UTC), ZoneInfo("Europe/Paris"))
    views = next(v for v in out["videos"] if v["key"] == "slot:2026-11-14/morning")["rows"][0]["views"]
    assert [(v["name"], v["m"]["views"]) for v in views] == [("48h", 100), ("latest", 120)]


def test_a_reel_published_by_hand_is_one_video_on_every_platform():
    """93:1-11, published by hand on 2026-11-05 before the calendar: its Instagram post, its
    YouTube Short titled « سورة الضحى » and its screenshots stand together; a reel of the calendar
    with the same names still comes first (114:1-6 in the morning, again by hand at 16:28)."""
    from quran_reels.catalog.stats import _manual_key
    from quran_reels.insights.classify import Classifier

    class NoTheme:
        def match(self, line, platform):
            return None

    posts = {
        "instagram:h": {"platform": "instagram", "published": "2026-11-05T00:12:00+00:00",
                        "first_line": "Surah Ad-Duhaa (93:1-11) · سورة الضحى"},
        "facebook:s": {"platform": "facebook", "published": "2026-11-05T08:45:00+00:00",
                       "first_line": "Surah An-Nas (114:1-6) · سورة الناس"},
        "facebook:t": {"platform": "facebook", "published": "2026-11-05T16:28:00+00:00",
                       "first_line": "Surah An-Nas (114:1-6) · سورة الناس"},
        "facebook:x": {"platform": "facebook", "published": "2026-11-07T14:33:00+00:00",
                       "first_line": ""},
    }
    published = {"slots": {"2026-11-05/morning": {"queue": "reading", "passage": "114:1-6",
                                                  "results": {"facebook": {"id": "s"}}}}}
    Classifier(published, {}, NoTheme()).apply(posts)
    assert {k: posts["instagram:h"][k] for k in ("key", "kind", "label", "ref")} == {
        "key": "hand:93:1-11", "kind": "reel-hand", "label": "93:1-11", "ref": {"passage": "93:1-11"}}
    assert posts["facebook:s"]["key"] == "slot:2026-11-05/morning"
    assert posts["facebook:t"]["key"] == "hand:114:1-6"
    assert posts["facebook:x"]["kind"] == "other"
    assert Y.match("سورة الضحى", "", datetime(2026, 11, 4, 23, 51, tzinfo=UTC),
                   posts)["key"] == "hand:93:1-11"
    assert Y.match("سورة الناس - Surah An-Nas", "", datetime(2026, 11, 5, 8, 56, tzinfo=UTC),
                   posts)["key"] == "slot:2026-11-05/morning"
    assert _manual_key({"platform": "tiktok", "video": "93:1-11"}, posts, None) == "hand:93:1-11"


class DetailHttp(FakeHttp):
    """FakeHttp, and the reports of the detailed reading by their dimensions; engaged views
    refused, as YouTube would for a metric it does not serve."""

    def get(self, url, params=None, headers=None, timeout=None):
        if url != Y.ANALYTICS:
            return super().get(url, params, headers, timeout)
        self.calls.append(("GET", url, params))
        assert params["ids"] == "channel==MINE" and params["endDate"] == "2026-11-15"
        dim = params["dimensions"]
        heads = {"insightTrafficSourceType": ("insightTrafficSourceType", "views",
                                              "estimatedMinutesWatched"),
                 "country": ("country", "views", "averageViewDuration"),
                 "elapsedVideoTimeRatio": ("elapsedVideoTimeRatio", "audienceWatchRatio",
                                           "relativeRetentionPerformance"),
                 "insightTrafficSourceDetail": ("insightTrafficSourceDetail", "views")}
        rows = {"insightTrafficSourceType": [["SHORTS", 90, 30.0], ["YT_SEARCH", 10, 4.0]],
                "country": [["EG", 60, 40], ["DZ", 40, 35]],
                "elapsedVideoTimeRatio": [[0.01, 1.2, 0.4], [0.5, 0.6, 0.3]],
                "insightTrafficSourceDetail": [["dua for rizq", 3]]}
        if dim == "video":
            return Answer(400, {"error": {"message": "Unknown identifier (engagedViews)"}})
        return Answer(200, {"columnHeaders": [{"name": n} for n in heads[dim]],
                            "rows": rows[dim]})


def test_the_detailed_reading_keeps_sources_countries_and_retention(tmp_path):
    from quran_reels.insights import youtube_detail as D

    out = tmp_path / "detail.json"
    http = DetailHttp()
    text = D.main(out, now=NOW, client=Y.YouTube("cid", "secret", http), env=ENV)
    detail = json.loads(out.read_text(encoding="utf-8"))
    assert [v["id"] for v in detail["videos"]] == ["v1", "v2", "v3"]      # the private one left out
    v1 = detail["videos"][0]
    assert v1["sources"][0] == {"insightTrafficSourceType": "SHORTS", "views": 90, "pct": 90.0,
                                "minutes": 30.0}
    assert v1["countries"][1]["country"] == "DZ" and v1["countries"][1]["pct"] == 40.0
    assert v1["retention"][0] == [0.01, 1.2, 0.4] and "engaged" not in v1
    reports = [p for m, u, p in http.calls if u == Y.ANALYTICS]
    assert {p["filters"] for p in reports if p["dimensions"] == "elapsedVideoTimeRatio"} == {
        "video==v1", "video==v2", "video==v3"}
    first = next(p for p in reports if p["filters"] == "video==v3")
    assert first["startDate"] == "2026-11-11"                    # its publication, Pacific day
    assert detail["channel"]["search_terms"][0]["views"] == 3
    assert len(detail["errors"]) == 3 and "engagedViews" in detail["errors"][0]
    assert "\n" not in out.read_text(encoding="utf-8")            # compact: no indent
    assert "dua for rizq" not in text                            # no search term in the log
    assert "SHORTS 90%" in text and "EG 60%" in text


def test_an_arabic_first_title_finds_its_reel_as_the_english_first_one_did():
    """Owner, 2026-11-21: YouTube titles of reels put the Arabic first."""
    assert Y.video_key("سورة الماعون · Surah Al-Ma'un (107:1-7)") == "107:1-7"
    assert Y.video_key("سورة التوبة · Surah At-Tawbah (9:51)") == "9:51-51"
    assert Y.video_key("آيات الدعاء · Supplications · 3/38 · سورة غافر · Surah Ghafir (40:60)") == "40:60-60"
    # titled by hand, a caption rendered since 2026-11-21: its surah line starts in Arabic
    assert Y.video_key("سورة التوبة",
                       "السبع آيات المنجيات · The seven munjiyat verses · 1/7\n"
                       "سورة التوبة · Surah At-Tawbah (9:51)\n\nبِسْمِ") == "9:51-51"
    # a theme video's line « سورة الكهف (18:10) » is not a reel's surah line
    assert Y.video_key("Light", "سورة الكهف (18:10)\nx") == "Light"
    published = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)
    posts = {
        "facebook:a": {"platform": "facebook", "key": "slot:2026-11-09/morning", "kind": "reel-morning",
                       "label": "111:1-5", "ref": {"passage": "111:1-5"},
                       "published": "2026-11-09T06:20:00+00:00",
                       "first_line": "Surah Al-Masad (111:1-5) · سورة المسد"},
        "facebook:k1": {"platform": "facebook", "key": "slot:2026-11-06/evening", "kind": "reel-kahf",
                        "published": "2026-11-06T18:30:00+00:00",
                        "first_line": "Surah Al-Kahf on Friday · سورة الكهف يوم الجمعة · 1/36"},
    }
    # by its reference
    assert Y.match("سورة المسد · Surah Al-Masad (111:1-5)", "", published, posts)["key"] == (
        "slot:2026-11-09/morning")
    # by its names only
    assert Y.match("سورة المسد · Surah Al-Masad", "", published, posts)["key"] == (
        "slot:2026-11-09/morning")
    assert Y.match("سورة الكهف يوم الجمعة · Surah Al-Kahf on Friday · 1/36", "",
                   datetime(2026, 11, 7, tzinfo=UTC), posts)["key"] == "slot:2026-11-06/evening"


def test_engaged_views_and_the_search_share_are_kept(tmp_path):
    path = tmp_path / "insights.json"
    Y.collect(path, S, now=NOW, client=Y.YouTube("cid", "secret", FakeHttp()), env=ENV)
    yt = json.loads(path.read_text())["posts"]
    v2 = yt["youtube:v2"]["snapshots"]["latest"]["m"]
    assert v2["engaged"] == 480 and v2["search_pct"] == 4.8          # 25 of 525
    assert "search_pct" not in yt["youtube:v3"]["snapshots"]["latest"]["m"]   # no view by source
    assert "search_pct" not in yt["youtube:v3"]["snapshots"]["48h"]["m"]      # latest only
    assert "engaged" in yt["youtube:v3"]["snapshots"]["48h"]["m"]


def test_the_search_query_asks_the_views_of_one_video_from_its_pacific_day(tmp_path):
    http = FakeHttp()
    Y.collect(tmp_path / "i.json", S, now=NOW, client=Y.YouTube("cid", "secret", http), env=ENV)
    asked = [p for m, u, p in http.calls if u == Y.ANALYTICS
             and p["dimensions"] == "insightTrafficSourceType"]
    v3 = next(p for p in asked if p["filters"] == "video==v3")
    assert v3["startDate"] == "2026-11-11" and v3["endDate"] == "2026-11-15"
    assert len(asked) == 3


def test_a_refused_engaged_views_is_asked_again_without_it(tmp_path):
    path = tmp_path / "insights.json"
    http = FakeHttp(engaged_ok=False)
    line = Y.collect(path, S, now=NOW, client=Y.YouTube("cid", "secret", http), env=ENV)
    assert "unavailable" not in line                                 # the other numbers all there
    yt = json.loads(path.read_text())["posts"]
    v1 = yt["youtube:v1"]["snapshots"]["latest"]["m"]
    assert v1["watch_pct"] == 55.5 and "engaged" not in v1
    assert "engaged" not in yt["youtube:v3"]["snapshots"]["48h"]["m"]
    assert yt["youtube:v3"]["snapshots"]["48h"]["m"]["views"] == 80
    # asked twice each time: with, then without
    with_ = [p for m, u, p in http.calls if u == Y.ANALYTICS and "engagedViews" in p["metrics"]]
    without = [p for m, u, p in http.calls if u == Y.ANALYTICS
               and p["dimensions"] in ("video", "day") and "engagedViews" not in p["metrics"]]
    assert with_ and len(with_) == len(without)


def test_a_refused_search_query_costs_only_its_number(tmp_path):
    path = tmp_path / "insights.json"
    line = Y.collect(path, S, now=NOW, client=Y.YouTube("cid", "secret", FakeHttp(search_ok=False)),
                     env=ENV)
    assert "unavailable" not in line
    m = json.loads(path.read_text())["posts"]["youtube:v1"]["snapshots"]["latest"]["m"]
    assert m["engaged"] == 70 and "search_pct" not in m and m["views"] == 120


def test_the_page_shows_engaged_views_and_the_search_share_for_youtube():
    from zoneinfo import ZoneInfo

    from quran_reels.catalog import stats as St
    from quran_reels.catalog.page import render_stats

    snap = {"at": "2026-11-16T07:00:00+00:00", "age_h": 48.5,
            "m": {"views": 120, "engaged": 70, "search_pct": 12.5}}
    data = {"listed": "2026-11-16T01:00:00+00:00", "listed_youtube": "2026-11-16T01:05:00+00:00",
            "accounts": {},
            "posts": {"youtube:v1": {
                "platform": "youtube", "key": "slot:2026-11-14/morning", "kind": "reel-morning",
                "label": "107:1-7", "ref": {}, "published": "2026-11-14T06:30:00+00:00",
                "seen": "2026-11-16T01:05:00+00:00", "url": "https://www.youtube.com/shorts/v1",
                "snapshots": {"latest": snap}}}}
    out = St.build(data, {"days": 35}, datetime(2026, 11, 16, 8, tzinfo=UTC), ZoneInfo("Europe/Paris"))
    html = render_stats({"repo": "o/r", "stats": json.loads(json.dumps(out, default=str))})
    assert "<b>70</b> vues engagées" in html
    assert "<b>12,5</b> par la recherche (%)" in html
    # a video without them shows neither
    data["posts"]["youtube:v1"]["snapshots"]["latest"]["m"] = {"views": 120}
    out = St.build(data, {"days": 35}, datetime(2026, 11, 16, 8, tzinfo=UTC), ZoneInfo("Europe/Paris"))
    html = render_stats({"repo": "o/r", "stats": json.loads(json.dumps(out, default=str))})
    videos = html[html.index('<section id="videos">'):]          # the video's own lines
    assert "vues engagées" not in videos and "par la recherche" not in videos


# ------------------------------------------------------------------ Studio export (import-youtube)

DATA = __import__("pathlib").Path(__file__).parent / "data"


def _state(tmp_path, ids):
    posts = {f"youtube:{i}": {"platform": "youtube", "key": k, "published": "2026-11-13T08:00:00+00:00"}
             for i, k in ids.items()}
    (tmp_path / "insights.json").write_text(json.dumps({"posts": posts}), encoding="utf-8")
    return tmp_path


def test_the_studio_export_gives_impressions_and_ctr_under_the_page_key(tmp_path, capsys):
    from quran_reels.insights import youtube_import as I

    state = _state(tmp_path, {"75zO0MtWtVo": "theme:moussa-khidr/short-1",
                              "JONE82FSqd4": "slot:2026-11-08/morning"})
    assert I.main(None, DATA / "youtube_studio_table_fr.csv", state, "2026-11-22") == 0
    cap = capsys.readouterr()
    out = json.loads(cap.out)                       # one line of JSON
    assert cap.out.count("\n") == 1
    assert out[0] == {"platform": "youtube", "video": "theme:moussa-khidr/short-1",
                      "published": "2026-11-13", "seen": "2026-11-22",
                      "metrics": {"impressions": 97, "ctr": 9.28}, "source": "export YouTube Studio"}
    assert out[1]["video"] == "slot:2026-11-08/morning" and out[1]["metrics"]["impressions"] == 70
    assert len(out) == 2                            # Total row skipped, unknown ids left out
    for vid in ("Dnbn1ANNUnE", "FUg5tLOqPME"):
        assert vid in cap.err
    from quran_reels.insights import collect as C
    assert C.add_manual(tmp_path / "m.json", out) == 2          # `manual` accepts the line


def test_the_zip_and_english_headers(tmp_path):
    import zipfile

    from quran_reels.insights import youtube_import as I

    table = ("Content,Video title,Video publish time,Duration,Views,Impressions,"
             "Impressions click-through rate (%),Viewed (vs. swiped away) (%)\n"
             "Total,,,,10,\"14,056\",2.7,\n"
             "abc,T,\"Nov 19, 2026\",30,10,\"1,234\",\"4,5\",71.2\n")
    z = tmp_path / "e.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("Chart data.csv", "Date,Content,Views\n2026-11-04,abc,1\n")
        f.writestr("Table data.csv", table)
    state = _state(tmp_path, {"abc": "slot:2026-11-19/morning"})
    got = I.entries(I.read_table(zip_path=z), I.youtube_keys(json.loads(
        (state / "insights.json").read_text())), "2026-11-22")
    assert got[0]["metrics"] == {"impressions": 1234, "ctr": 4.5, "viewed_pct": 71.2}


def test_numbers_and_dates_of_the_export():
    from quran_reels.insights import youtube_import as I

    assert I.parse_number("2,71") == 2.71 and I.parse_number("1 252", integer=True) == 1252
    assert I.parse_number("") is None and I.parse_number("-") is None
    assert I.parse_date("Nov 19, 2026") == "2026-11-19" and I.parse_date("19 nov. 2026") == "2026-11-19"


def test_manual_accepts_the_new_numbers(tmp_path):
    from quran_reels.insights import collect as C

    C.add_manual(tmp_path / "i.json", [{"platform": "facebook", "video": "slot:2026-11-21/morning",
                                        "seen": "2026-11-22", "metrics": {"reach": 900}},
                                       {"platform": "youtube", "video": "slot:2026-11-21/morning",
                                        "seen": "2026-11-22",
                                        "metrics": {"impressions": 97, "ctr": 9.28, "viewed_pct": 71}}])
    assert len(json.loads((tmp_path / "i.json").read_text())["manual"]) == 2
