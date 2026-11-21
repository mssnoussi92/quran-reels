"""Statistics of the Page (insights/): theme texts and calendar, metrics, the nightly run against a
fake Graph API, manual numbers. No network, no secrets."""

import json
from datetime import UTC, date, datetime, timedelta

import pytest

from quran_reels.config import load
from quran_reels.insights import collect as C
from quran_reels.insights import metrics as M
from quran_reels.insights import themes as T
from quran_reels.publishers.meta import Graph

TEXTS = """# Du'a · الدعاء : textes de publication

## Le film · Du'a: 3 wrong ideas that keep you from asking · الدعاء: ٣ أفكار غلط بتبعدك عنه

`dua-film-16x9.mp4` · 7:36 · 16:9 · YouTube · miniature : `dua-film-thumbnail.jpg`

## Short 1 · Patient… and he asked · صابر… ودعا!

`dua-short-1-asked.mp4` (TikTok : `dua-short-1-asked-tiktok.mp4`) · 1:49 · 9:16 · Facebook, Instagram, TikTok, YouTube Shorts · couverture : `c.jpg`
"""
TEXTS_916 = """# Du'a · الدعاء : le film en 9:16

## Le film en 9:16 · Du'a: 3 wrong ideas that keep you from asking · الدعاء: ٣ أفكار غلط بتبعدك عنه

`dua-film-9x16.mp4` · 7:36 · 9:16 · Facebook
"""
SERIES = """# A Verse and Its Story · آية وحكايتها : textes de publication

## Short 1 · They walked out of the Friday sermon… why? · سابوا خطبة الجمعة… ليه؟

`ayah-short-1-caravan.mp4` · 1:40 · 9:16 · Facebook, Instagram, TikTok, YouTube Shorts
"""
CALENDAR = """# Calendrier

## Ce qui est publié

| Quand | Quoi | Où |
| --- | --- | --- |
| jeu. 12 nov., soir | Moussa et al-Khadir : le film | Facebook |

## Le calendrier

| Date | Quoi | Où | Fichiers | Texte |
| --- | --- | --- | --- | --- |
| ~~jeu. 12 nov., soir~~ | ~~Moussa et al-Khadir : le film~~ | YouTube (16:9) ; Facebook (vertical) | a | b |
| lun. 16 nov., soir | Du'a : le film | YouTube (16:9) ; Facebook (vertical) | a | b |
| lun. 30 nov. → jeu. 3 déc. | **une histoire nouvelle** : son film, ses trois shorts | | à faire | à faire |
| ven. 1 janv. | « لاحظت الفرق؟ » 3 : la justice (`qist`) | les quatre | a | b |

## La fiche

| Publiée le | Heure |
| --- | --- |
| 12 nov. | soir |
"""


def index():
    return T.ThemeIndex(T.parse_texts("dua", TEXTS) + T.parse_texts("dua-9x16", TEXTS_916)
                        + T.parse_texts("ayah", SERIES))


# ------------------------------------------------------------------------------ themes


def test_publication_texts_are_parsed():
    films = T.parse_texts("dua", TEXTS)
    assert [v.id for v in films] == ["dua/film", "dua/short-1"]
    film, short = films
    assert (film.kind, film.seconds, film.platforms) == ("theme-film", 456, ["youtube"])
    assert (short.kind, short.seconds) == ("theme-short", 109)
    assert short.platforms == ["facebook", "instagram", "tiktok", "youtube"]
    assert short.series == "Du'a · الدعاء" and short.title_ar == "صابر… ودعا!"
    episode = T.parse_texts("ayah", SERIES)[0]
    assert episode.kind == "theme-episode" and episode.series == "A Verse and Its Story · آية وحكايتها"
    assert T.parse_texts("dua-9x16", TEXTS_916)[0].series == "Du'a · الدعاء"


def test_a_post_is_recognised_by_the_first_line_of_its_caption():
    idx = index()
    caption = "They walked out of the Friday sermon... why?\nسابوا خطبة الجمعة… ليه؟\n\nOne Friday…"
    assert idx.match(caption, "instagram").id == "ayah/short-1"       # "..." and "…" alike
    # the same title: the 9:16 film on Facebook, the 16:9 one on YouTube
    film = "Du'a: 3 wrong ideas that keep you from asking\nالدعاء"
    assert idx.match(film, "facebook").id == "dua-9x16/film"
    assert idx.match(film, "youtube").id == "dua/film"
    assert idx.match("PATIENT… AND HE ASKED", "tiktok").id == "dua/short-1"
    assert idx.match("Surah Ad-Duhaa · 93:1-11", "facebook") is None
    assert idx.match("", "facebook") is None


def test_a_title_in_either_order_and_either_digits_finds_its_video():
    """YouTube titles of theme videos are « Arabic · English » from 2026-11-21, the older ones
    stay « English · Arabic »; ٣ and 3 compare equal (owner's rule: numbers are 123)."""
    idx = index()
    old = "Du'a: 3 wrong ideas that keep you from asking · الدعاء: ٣ أفكار غلط بتبعدك عنه"
    new = "الدعاء: ٣ أفكار غلط بتبعدك عنه · Du'a: 3 wrong ideas that keep you from asking"
    assert idx.match(old, "youtube").id == "dua/film"
    assert idx.match(new, "youtube").id == "dua/film"
    assert idx.match(new, "facebook").id == "dua-9x16/film"        # the platform still decides
    assert idx.match("الدعاء: 3 أفكار غلط بتبعدك عنه · Du'a", "youtube").id == "dua/film"
    assert T.norm("٣ و۴") == T.norm("3 و4") == "3 و4"
    assert idx.match("سابوا خطبة الجمعة… ليه؟ · They walked out", "youtube").id == "ayah/short-1"
    assert idx.match("صابر… ودعا! · Patient… and he asked", "youtube").id == "dua/short-1"
    # a short Arabic title is not enough by its start alone: a line that merely begins with it
    short = T.ThemeIndex([T.ThemeVideo(id="x/short-1", doc="x", series="", part="Short 1",
                                       title_en="A long English title of its own",
                                       title_ar="قصير", platforms=["youtube"])])
    assert short.match("قصير وبعده كلام آخر كثير", "youtube") is None
    assert short.match("A long English title of its own · قصير", "youtube").id == "x/short-1"


def test_calendar_rows_become_days():
    days = T.parse_calendar(CALENDAR, date(2026, 11, 15))
    assert [d.day for d in days] == ["2026-11-12", "2026-11-16", "2026-11-30", "2026-12-01",
                                     "2026-12-02", "2026-12-03", "2027-01-01"]
    first, film, new = days[0], days[1], days[2]
    assert first.published and first.evening and first.label == "Moussa et al-Khadir : le film"
    assert film.evening and not film.published
    assert new.todo and new.span == "lun. 30 nov. → jeu. 3 déc." and "**" not in new.label
    assert days[-1].label == "« لاحظت الفرق؟ » 3 : la justice (qist)"   # next year, no backticks


# ------------------------------------------------------------------------------ metrics


def test_instagram_reel_numbers():
    raw = M.values({"data": [
        {"name": "views", "values": [{"value": 412}]},
        {"name": "reach", "total_value": {"value": 300}},
        {"name": "reels_skip_rate", "values": [{"value": 61.5}]},
        {"name": "ig_reels_avg_watch_time", "values": [{"value": 23500}]},
        {"name": "shares", "values": [{"value": 3}]},
        {"name": "saved", "values": [{"value": 5}]}]})
    m = M.normalize("instagram-reel", raw, 100)
    assert m == {"views": 412, "reach": 300, "hook": 38.5, "avg_watch": 23.5, "watch_pct": 23.5,
                 "shares": 3, "saves": 5}


def test_facebook_reel_numbers_without_the_retention_graph():
    """2026-11-15, first real reading: the graph was at 100 % until 3 s on reels watched 4 to 8 s
    on average. It is kept raw, never turned into a hook (metrics.py)."""
    graph = {str(s): v for s, v in enumerate([1.0, 0.8, 0.6, 0.45, 0.4] + [0.3] * 36)}
    raw = {"blue_reels_play_count": 120, "post_impressions_unique": 90,
           "post_video_avg_time_watched": 14200, "post_video_followers": 2,
           "post_video_social_actions": {"COMMENT": 1, "SHARE": 4},
           "post_video_retention_graph": graph}
    m = M.normalize("facebook-reel", raw, 60)
    assert "hook" not in m and "kept_30s" not in m
    assert (m["views"], m["reach"], m["follows"], m["shares"], m["comments"]) == (120, 90, 2, 4, 1)
    assert m["avg_watch"] == 14.2 and m["watch_pct"] == 23.7
    assert M.normalize("facebook-photo", {"post_media_view": 21,
                                          "post_total_media_view_unique": 0}, None) == {"views": 21}


def test_retention_in_forty_intervals_of_a_long_video():
    graph = {str(i): 100 - 2 * i for i in range(41)}           # percentages, 40 intervals
    # a 400 s film: interval i is at 10 i seconds
    assert M.retention_at(graph, 30, 400) == 94.0
    assert M.retention_at(graph, 3, 400) == pytest.approx(99.4)
    assert M.retention_at({}, 3, 60) is None
    assert M.retention_at(graph, 500, 400) is None


def test_a_missing_number_stays_missing():
    m = M.normalize("instagram-reel", {"views": 10}, None)
    assert m == {"views": 10}                     # no hook, no watch_pct: never 0


# ------------------------------------------------------------------------------ the run

PAGE, IG = "1494879297031390", "17841475111287268"
NOW = datetime(2026, 11, 20, 2, 50, tzinfo=UTC)


class Resp:
    def __init__(self, body, status=200, usage=5):
        self.body, self.status_code = body, status
        self.headers = {"X-App-Usage": json.dumps({"call_count": usage})}

    def json(self):
        return self.body


class FakeGraph:
    """GET routes by path; records calls; can refuse a metric name with Meta's code 100."""

    def __init__(self, routes, refuse=(), usage=5):
        self.routes, self.refuse, self.usage, self.calls = routes, set(refuse), usage, []
        self.headers = {}

    def request(self, method, url, timeout=None, params=None, headers=None, **kw):
        assert method == "GET", "insights never write"
        path = url.split("/v24.0/", 1)[1]
        self.calls.append((path, dict(params or {})))
        metric = (params or {}).get("metric", "")
        if any(name in metric.split(",") for name in self.refuse):
            return Resp({"error": {"message": "(#100) The value must be a valid insights metric",
                                   "code": 100}}, 400, self.usage)
        body = self.routes.get(path)
        if callable(body):
            body = body(params or {})
        return Resp(body if body is not None else {"data": []}, 200, self.usage)


def stamp(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S+0000")


def ins(**values):
    return {"data": [{"name": k, "values": [{"value": v}]} for k, v in values.items()]}


@pytest.fixture
def state(tmp_path):
    d = tmp_path / "state"
    d.mkdir()
    (d / "published.json").write_text(json.dumps({"slots": {"2026-11-18/morning": {
        "queue": "reading", "item": "juz-amma/104:1-9", "passage": "104:1-9", "reciter": "minshawi",
        "results": {"facebook": {"status": "published", "id": "111"},
                    "instagram": {"status": "published", "id": "211"}}}}}))
    (d / "images.json").write_text(json.dumps({"word": {"posts": {"2026-11-19": {
        "word": "ٱلتَّابُوتُ", "ayah": "2:248",
        "results": {"facebook": {"status": "published", "id": f"{PAGE}_9"},
                    "instagram": {"status": "published", "id": "219"}}}}}}))
    return d


def routes():
    reel_t = stamp(NOW - timedelta(hours=50))          # the 48 h checkpoint is due
    theme_t = stamp(NOW - timedelta(hours=10))
    return {
        PAGE: {"followers_count": 70, "fan_count": 66},
        IG: {"followers_count": 120, "media_count": 40},
        f"{PAGE}/video_reels": {"data": [
            {"id": "111", "created_time": reel_t, "description": "Surah Al-Humazah", "length": 58.2,
             "permalink_url": "/reel/111/"},
            {"id": "112", "created_time": theme_t, "length": 109.0,
             "description": "Patient… and he asked\nصابر… ودعا!"}]},
        f"{PAGE}/videos": {"data": [
            {"id": "199", "created_time": theme_t, "length": 24.0, "published": False}]},
        f"{IG}/media": {"data": [
            {"id": "211", "timestamp": reel_t, "caption": "Surah Al-Humazah",
             "media_product_type": "REELS"},
            {"id": "212", "timestamp": theme_t, "caption": "Patient... and he asked\nx",
             "media_product_type": "REELS"},
            {"id": "219", "timestamp": stamp(NOW - timedelta(hours=15)), "caption": "Word",
             "media_product_type": "FEED"},
            {"id": "299", "timestamp": stamp(NOW - timedelta(days=60)), "caption": "old",
             "media_product_type": "REELS"}]},
        "111/video_insights": ins(blue_reels_play_count=80, post_video_avg_time_watched=20000),
        "112/video_insights": ins(blue_reels_play_count=30, post_video_avg_time_watched=40000),
        f"{PAGE}_9/insights": ins(post_media_view=55),
        "211/insights": ins(views=150, reels_skip_rate=40),
        "212/insights": ins(views=60, ig_reels_avg_watch_time=30000),
        "219/insights": ins(views=90, reach=70),
    }


def graph(fake):
    return Graph("EAAB-secret", "v24.0", session=fake)


def test_the_nightly_run_reads_classifies_and_keeps_checkpoints(state):
    fake = FakeGraph(routes())
    out = C.run(load(), state, graph(fake), PAGE, IG, index(), now=NOW)
    assert out["stopped"] == "" and out["errors"] == []
    data = json.loads((state / "insights.json").read_text())
    posts = data["posts"]
    assert set(posts) == {"facebook:111", "facebook:112", f"facebook:{PAGE}_9",
                          "instagram:211", "instagram:212", "instagram:219"}   # 60 days: not read
    reel_fb, reel_ig = posts["facebook:111"], posts["instagram:211"]
    assert reel_fb["key"] == reel_ig["key"] == "slot:2026-11-18/morning"
    assert reel_fb["kind"] == "reel-morning" and reel_fb["ref"]["reciter"] == "minshawi"
    assert set(reel_fb["snapshots"]) == {"48h", "latest"}
    assert reel_ig["seconds"] == 58.2                      # its Facebook twin's length
    assert reel_ig["snapshots"]["48h"]["m"] == {"views": 150, "hook": 60.0}
    theme_ig = posts["instagram:212"]
    assert theme_ig["key"] == "theme:dua/short-1" and theme_ig["kind"] == "theme-short"
    assert theme_ig["snapshots"]["latest"]["m"]["watch_pct"] == 27.5     # 30 s of 1:49
    assert set(theme_ig["snapshots"]) == {"latest"}                      # 10 h old
    assert posts[f"facebook:{PAGE}_9"]["key"] == posts["instagram:219"]["key"] == "word:2026-11-19"
    assert data["accounts"]["facebook"]["2026-11-20"] == {"followers_count": 70, "fan_count": 66}
    assert data["runs"][-1]["read"] == 6


def test_a_checkpoint_is_kept_for_good(state):
    C.run(load(), state, graph(FakeGraph(routes())), PAGE, IG, index(), now=NOW)
    later = NOW + timedelta(days=1)
    r = routes()
    r["211/insights"] = ins(views=999)
    C.run(load(), state, graph(FakeGraph(r)), PAGE, IG, index(), now=later)
    snaps = json.loads((state / "insights.json").read_text())["posts"]["instagram:211"]["snapshots"]
    assert snaps["48h"]["m"]["views"] == 150 and snaps["latest"]["m"]["views"] == 999


def test_an_unknown_metric_is_learnt_once(state):
    fake = FakeGraph(routes(), refuse={"reels_skip_rate"})
    out = C.run(load(), state, graph(fake), PAGE, IG, index(), now=NOW)
    assert out["errors"] == []
    data = json.loads((state / "insights.json").read_text())
    assert data["unsupported"]["instagram-reel"] == ["reels_skip_rate"]
    asked = [p for p, params in fake.calls if p == "211/insights"]
    assert len(asked) == 1 + len(M.REQUEST["instagram-reel"])     # all, then one by one
    fake2 = FakeGraph(routes(), refuse={"reels_skip_rate"})
    C.run(load(), state, graph(fake2), PAGE, IG, index(), now=NOW + timedelta(hours=1))
    assert all("reels_skip_rate" not in params.get("metric", "") for _, params in fake2.calls)


def test_the_run_stops_before_the_app_budget_runs_out(state):
    fake = FakeGraph(routes(), usage=80)
    out = C.run(load(), state, graph(fake), PAGE, IG, index(), now=NOW)
    assert "budget" in out["stopped"] and len(fake.calls) == 1   # the first answer said 80 %
    data = json.loads((state / "insights.json").read_text())
    assert data["runs"][-1]["stopped"]


def test_dry_run_saves_nothing(state):
    C.run(load(), state, graph(FakeGraph(routes())), PAGE, IG, index(), now=NOW, dry_run=True)
    assert not (state / "insights.json").exists()


def test_due_snapshots():
    s = {"checkpoints": {"48h": 48, "7d": 168}, "tolerance_hours": 48, "refresh_days": 8}
    assert C.due({}, 10, s) == ["latest"]
    assert C.due({}, 50, s) == ["48h", "latest"]
    assert C.due({"snapshots": {"48h": {}}}, 50, s) == ["latest"]
    assert C.due({}, 100, s) == ["latest"]                 # 48 h missed: never back-filled
    assert C.due({"snapshots": {"48h": {}}}, 170, s) == ["7d", "latest"]
    assert C.due({"snapshots": {"48h": {}, "7d": {}}}, 300, s) == []


# ------------------------------------------------------------------------------ manual


def test_manual_numbers_from_a_screenshot(tmp_path):
    path = tmp_path / "insights.json"
    entry = {"platform": "YouTube", "video": "dua/short-1", "published": "2026-11-17",
             "seen": "2026-11-22", "metrics": {"views": 340, "avg_watch": 41.5}}
    C.add_manual(path, [entry])
    C.add_manual(path, [entry | {"metrics": {"views": 360}}])          # same day: replaced
    manual = json.loads(path.read_text())["manual"]
    assert len(manual) == 1 and manual[0]["m"] == {"views": 360}
    assert manual[0]["platform"] == "youtube"
    with pytest.raises(ValueError):
        C.add_manual(path, [entry | {"platform": "snapchat"}])
    with pytest.raises(ValueError):
        C.add_manual(path, [entry | {"metrics": {"likes_per_hour": 3}}])
    # TikTok's « watched the full video »; an entry sent with a wrong video, taken back
    wrong = {"platform": "tiktok", "video": "107:1-77", "seen": "2026-11-22",
             "metrics": {"views": 676, "finished": 31.2}}
    C.add_manual(path, [wrong])
    assert json.loads(path.read_text())["manual"][-1]["m"] == {"views": 676, "finished": 31.2}
    C.add_manual(path, [{"platform": "tiktok", "video": "107:1-77", "seen": "2026-11-22",
                         "remove": True}])
    assert [m["video"] for m in json.loads(path.read_text())["manual"]] == ["dua/short-1"]


# ------------------------------------------------------------------------------ the page


def test_the_statistics_page(state):
    from zoneinfo import ZoneInfo

    from quran_reels.catalog import stats as S
    from quran_reels.catalog.page import render_stats

    C.run(load(), state, graph(FakeGraph(routes())), PAGE, IG, index(), now=NOW)
    C.add_manual(state / "insights.json", [
        {"platform": "youtube", "video": "dua/short-1", "seen": "2026-11-20",
         "metrics": {"views": 340, "avg_watch": 41.5}},
        {"platform": "tiktok", "video": "<b>unknown</b>", "seen": "2026-11-20",
         "metrics": {"views": 12}}], now=NOW)
    data = json.loads((state / "insights.json").read_text())
    s = S.build(data, C.settings(load()), NOW + timedelta(hours=1), ZoneInfo("Europe/Paris"),
                index())
    assert not s["empty"] and not s["stale"]
    keys = [v["key"] for v in s["videos"]]
    assert keys[0] == "theme:dua/short-1"                      # the most recent first
    theme = s["videos"][0]
    assert [r["platform"] for r in theme["rows"]] == ["Facebook", "Instagram"]
    assert theme["manual"][0]["platform"] == "YouTube"
    assert s["manual"][0]["video"] == "<b>unknown</b>"        # not recognised: listed apart
    morning = [k for k in s["kinds"] if k["kind"] == "Reel du matin (lecture)"]
    assert {k["platform"] for k in morning} == {"Facebook", "Instagram"}
    assert all(k["n"] == 1 and k["few"] for k in morning)    # 1 video: no difference claimed
    fb = s["followers"][0]
    assert (fb["platform"], fb["now"], fb["delta"]) == ("Facebook", 70, None)   # 1 day: no change
    html = render_stats({"repo": "o/r", "stats": json.loads(json.dumps(s, default=str))})
    assert "Comparer les types de vidéos" in html and "Patient… and he asked" in html
    assert "&lt;b&gt;unknown&lt;/b&gt;" in html and "<b>unknown</b>" not in html
    assert "trop peu" in html and "60 %" in html                # Instagram reel: 100 − 40
    assert "0 vues" not in html                                  # nothing invented


def test_the_short_version_is_a_row_of_its_short_and_compared_apart():
    """Facebook and Instagram got the short version (themes.json `cut`): the page shows it
    under its short, with its own length, and compares it apart from the whole shorts."""
    from zoneinfo import ZoneInfo

    from quran_reels.catalog import stats as S
    from quran_reels.insights.classify import Classifier

    snap = {"at": "2026-11-26T02:00:00+00:00", "age_h": 55, "m": {"views": 300}}
    posts = {
        "facebook:fb1": {"platform": "facebook", "id": "fb1", "seconds": 73,
                         "published": "2026-11-24T18:01:00+00:00",
                         "first_line": "Patient… and he asked", "snapshots": {"48h": snap}},
        "instagram:ig1": {"platform": "instagram", "id": "ig1",
                          "published": "2026-11-24T18:02:00+00:00",
                          "first_line": "Patient… and he asked", "snapshots": {"48h": snap}},
        "youtube:yt1": {"platform": "youtube", "id": "yt1", "seconds": 109,
                        "published": "2026-11-24T20:00:00+00:00",
                        "first_line": "Patient… and he asked", "snapshots": {"48h": snap}},
    }
    themes_state = {"posts": {"2026-11-24": {
        "videos": {"facebook": "dua/short-1", "instagram": "dua/short-1", "tiktok": "dua/short-1"},
        "cut": {"facebook": "dua-short-1-asked-cut.mp4", "instagram": "dua-short-1-asked-cut.mp4"},
        "results": {"facebook": {"status": "published", "remote_id": "fb1"},
                    "instagram": {"status": "published", "remote_id": "ig1"},
                    "tiktok": {"status": "draft", "remote_id": "v_inbox~1"}}}}}
    Classifier({}, {}, index(), themes_state).apply(posts)
    assert {u: (r["key"], r["kind"], r["seconds"]) for u, r in posts.items()} == {
        "facebook:fb1": ("theme:dua/short-1", "theme-short-cut", 73),
        "instagram:ig1": ("theme:dua/short-1", "theme-short-cut", 73),      # its twin's length
        "youtube:yt1": ("theme:dua/short-1", "theme-short", 109)}
    assert posts["facebook:fb1"]["ref"]["cut"] == "dua-short-1-asked-cut.mp4"
    s = S.build({"posts": posts}, {"days": 35}, datetime(2026, 11, 26, 8, tzinfo=UTC),
                ZoneInfo("Europe/Paris"))
    video = s["videos"][0]
    assert (video["kind_label"], video["seconds"]) == ("Thème : short d'histoire", 109)
    assert [(r["platform"], r["is_cut"], r["cut"]) for r in video["rows"]] == [
        ("Facebook", True, 73), ("Instagram", True, 73), ("YouTube", False, None)]
    assert {(k["kind"], k["platform"]) for k in s["kinds"]} == {
        ("Thème : short, version courte", "Facebook"), ("Thème : short, version courte", "Instagram"),
        ("Thème : short d'histoire", "YouTube")}
    from quran_reels.catalog.page import render_stats

    html = render_stats({"repo": "o/r", "stats": json.loads(json.dumps(s, default=str))})
    assert html.count("· version courte, 73 s") == 2


def test_the_short_version_on_youtube_is_known_by_its_length():
    """2026-11-18 (owner's choice): YouTube gets the short version too, uploaded by hand with the
    short's title; nothing in themes.json names it, its length does (73 s, against 109 s for the
    whole short), on the Meta classifier's pass as on the YouTube reading's."""
    from types import SimpleNamespace

    from quran_reels.insights import youtube as Y
    from quran_reels.insights.classify import Classifier

    line = "couverture : `c.jpg`"
    texts = TEXTS.replace(line, line + " · version courte pour Facebook et Instagram : "
                          "`dua-short-1-asked-cut.mp4`, 1:13")
    themes = T.ThemeIndex(T.parse_texts("dua", texts))
    short = themes.by_id["dua/short-1"]
    assert (short.cut, short.cut_seconds, short.seconds) == ("dua-short-1-asked-cut.mp4", 73, 109)
    assert short.is_cut(74) and not short.is_cut(109) and not short.is_cut(None)
    assert not themes.by_id["dua/film"].is_cut(73)          # no short version: never one
    snap = {"at": "2026-11-26T02:00:00+00:00", "age_h": 55, "m": {"views": 300}}
    posts = {f"youtube:{i}": {"platform": "youtube", "id": i, "seconds": sec,
                              "published": "2026-11-24T20:00:00+00:00",
                              "first_line": "Patient… and he asked", "snapshots": {"48h": snap}}
             for i, sec in (("cut", 74), ("whole", 109))}
    Classifier({}, {}, themes, {}).apply(posts)
    assert {u: (r["key"], r["kind"], (r["ref"] or {}).get("cut")) for u, r in posts.items()} == {
        "youtube:cut": ("theme:dua/short-1", "theme-short-cut", "dua-short-1-asked-cut.mp4"),
        "youtube:whole": ("theme:dua/short-1", "theme-short", None)}
    assert posts["youtube:cut"]["seconds"] == 74                 # its own length, kept
    published = datetime(2026, 11, 24, 20, tzinfo=UTC)
    cut = Y.match("Patient… and he asked · صابر… ودعا!", "", published, {}, themes, 74)
    whole = Y.match("Patient… and he asked · صابر… ودعا!", "", published, {}, themes, 109)
    assert (cut["kind"], cut["ref"]["cut"]) == ("theme-short-cut", "dua-short-1-asked-cut.mp4")
    assert whole["kind"] == "theme-short" and "cut" not in whole["ref"]
    # a theme index that does not know short versions (a stub) still matches
    stub = SimpleNamespace(match=lambda title, platform: SimpleNamespace(
        id="dua/short-1", kind="theme-short", title_en="P", title_ar="ص", series="", part="Short 1"))
    assert Y.match("P", "", published, {}, stub, 74)["kind"] == "theme-short"


def test_an_empty_statistics_page_says_when_it_starts():
    from zoneinfo import ZoneInfo

    from quran_reels.catalog import stats as S
    from quran_reels.catalog.page import render_stats

    s = S.build(None, {}, NOW, ZoneInfo("Europe/Paris"))
    assert s == {"empty": True}
    assert "premier relevé" in render_stats({"repo": "o/r", "stats": s})


def test_theme_videos_join_the_calendar():
    from quran_reels.catalog import stats as S

    calendar = [{"date": "2026-11-16", "slots": []}, {"date": "2026-11-17", "slots": []}]
    S.merge_calendar(calendar, T.parse_calendar(CALENDAR, date(2026, 11, 15)), "19:00")
    assert [t["label"] for t in calendar[0]["themes"]] == ["Du'a : le film"]
    assert calendar[0]["themes"][0]["time"] == "19:00" and calendar[1]["themes"] == []


def test_a_refused_list_costs_that_list_only(state):
    r = routes()
    fake = FakeGraph(r)
    base = fake.request

    def request(method, url, **kw):
        if url.endswith(f"{PAGE}/videos"):
            return Resp({"error": {"message": "(#10) Not allowed", "code": 10}}, 400)
        return base(method, url, **kw)

    fake.request = request
    out = C.run(load(), state, graph(fake), PAGE, IG, index(), now=NOW, notes=["jeton sans X"])
    assert len(out["errors"]) == 1 and "code 10" in out["errors"][0]
    data = json.loads((state / "insights.json").read_text())
    assert "instagram:211" in data["posts"] and "facebook:111" in data["posts"]
    assert data["runs"][-1]["notes"] == ["jeton sans X"]


def test_a_long_video_is_read_as_a_video_once_learnt(state):
    r = routes()
    r["112/video_insights"] = lambda params: (
        ins(total_video_views=12, total_video_avg_time_watched=90000)
        if "total_video_views" in params.get("metric", "") else ins(post_video_view_time=5))
    fake = FakeGraph(r)
    C.run(load(), state, graph(fake), PAGE, IG, index(), now=NOW)
    rec = json.loads((state / "insights.json").read_text())["posts"]["facebook:112"]
    assert rec["profile"] == "facebook-video" and rec["snapshots"]["latest"]["m"]["views"] == 12
    fake2 = FakeGraph(r)
    C.run(load(), state, graph(fake2), PAGE, IG, index(), now=NOW + timedelta(hours=2))
    assert len([c for c in fake2.calls if c[0] == "112/video_insights"]) == 1


def test_drafts_and_scheduled_videos_are_not_read(state):
    fake = FakeGraph(routes())
    C.run(load(), state, graph(fake), PAGE, IG, index(), now=NOW)
    data = json.loads((state / "insights.json").read_text())
    assert "facebook:199" not in data["posts"]
    assert all(p["seen"] == data["listed"] for p in data["posts"].values())


def test_a_post_gone_from_the_listing_leaves_the_page(state):
    from zoneinfo import ZoneInfo

    from quran_reels.catalog import stats as S

    C.run(load(), state, graph(FakeGraph(routes())), PAGE, IG, index(), now=NOW)
    data = json.loads((state / "insights.json").read_text())
    data["posts"]["facebook:old-draft"] = {
        "platform": "facebook", "published": (NOW - timedelta(days=3)).isoformat(),
        "kind": "other", "key": "facebook:old-draft", "label": "draft", "kind_meta":
        "facebook-video", "snapshots": {"48h": {"at": "", "age_h": 50, "m": {"views": 0}}}}
    s = S.build(data, C.settings(load()), NOW, ZoneInfo("Europe/Paris"), index())
    assert "facebook:old-draft" not in [v["key"] for v in s["videos"]]
    assert not [k for k in s["kinds"] if k["kind"] == "Autre publication"]


def test_version_1_numbers_that_proved_wrong_are_taken_out(tmp_path):
    path = tmp_path / "insights.json"
    path.write_text(json.dumps({"posts": {
        "facebook:1": {"platform": "facebook", "kind_meta": "facebook-reel", "snapshots": {
            "48h": {"m": {"views": 10, "hook": 91.0, "kept_30s": 8.3}}}},
        "facebook:2": {"platform": "facebook", "kind_meta": "facebook-photo", "snapshots": {
            "latest": {"m": {"views": 21, "reach": 0}}}},
        "instagram:3": {"platform": "instagram", "kind_meta": "instagram-reel", "snapshots": {
            "latest": {"m": {"views": 5, "hook": 28.0, "reach": 2}}}}}}))
    data = C.load(path)
    assert data["version"] == 2
    assert data["posts"]["facebook:1"]["snapshots"]["48h"]["m"] == {"views": 10}
    assert data["posts"]["facebook:2"]["snapshots"]["latest"]["m"] == {"views": 21}
    assert data["posts"]["instagram:3"]["snapshots"]["latest"]["m"] == {
        "views": 5, "hook": 28.0, "reach": 2}


def test_facebook_publication_status_is_read_and_kept(state):
    r = routes()
    r[f"{PAGE}/videos"] = {"data": [
        {"id": "301", "created_time": stamp(NOW - timedelta(hours=60)), "length": 20.0,
         "status": {"video_status": "ready", "publishing_phase": {"status": "not_started"}}},
        {"id": "302", "created_time": stamp(NOW - timedelta(hours=60)), "length": 20.0,
         "status": {"publishing_phase": {"status": "complete", "publish_status": "scheduled"}}},
        {"id": "303", "created_time": stamp(NOW - timedelta(hours=60)), "length": 20.0,
         "description": "Something", "published": True,
         "status": {"video_status": "ready", "publishing_phase": {"status": "complete"}}}]}
    C.run(load(), state, graph(FakeGraph(r)), PAGE, IG, index(), now=NOW)
    posts = json.loads((state / "insights.json").read_text())["posts"]
    assert "facebook:301" not in posts and "facebook:302" not in posts
    assert posts["facebook:303"]["fb_status"] == {"published": True, "phase": "complete",
                                                  "video_status": "ready"}


def test_a_facebook_video_nobody_saw_is_not_shown(state):
    from zoneinfo import ZoneInfo

    from quran_reels.catalog import stats as S

    C.run(load(), state, graph(FakeGraph(routes())), PAGE, IG, index(), now=NOW)
    data = json.loads((state / "insights.json").read_text())
    data["posts"]["facebook:404"] = {
        "platform": "facebook", "published": (NOW - timedelta(days=3)).isoformat(),
        "seen": data["listed"], "kind": "other", "key": "facebook:404", "label": "x",
        "first_line": "", "snapshots": {"latest": {"at": "", "age_h": 72, "m": {"views": 0}}}}
    s = S.build(data, C.settings(load()), NOW, ZoneInfo("Europe/Paris"), index())
    assert "facebook:404" not in [v["key"] for v in s["videos"]]


def test_the_test_page_numbers_go_to_their_own_file(state):
    """The test page « معاك 5 ثواني » (2026-11-19): read with its own token, kept in insights-ma3ak.json,
    the Page's insights.json untouched."""
    before = (state / "insights.json").read_text() if (state / "insights.json").exists() else None
    out = C.run(load(), state, graph(FakeGraph(routes())), PAGE, IG, index(), now=NOW,
                file="insights-ma3ak.json", themes_state="themes-ma3ak.json")
    assert out["errors"] == []
    assert json.loads((state / "insights-ma3ak.json").read_text())["posts"]
    after = (state / "insights.json").read_text() if (state / "insights.json").exists() else None
    assert after == before


def test_the_test_page_never_reads_the_page_word_of_the_day(state):
    """2026-11-20: the test page's first night tried to read the Page's Word of the day posts, known by
    images.json, with its own token (« not enough permission »). Another page reads neither images.json
    nor published.json, and a Facebook post of another Page is taken out of its file."""
    (state / "insights-ma3ak.json").write_text(json.dumps({"posts": {
        "facebook:999_5": {"platform": "facebook", "id": "999_5", "snapshots": {}},
        "facebook:7001": {"platform": "facebook", "id": "7001", "snapshots": {}}}}))
    C.run(load(), state, graph(FakeGraph(routes())), PAGE, IG, index(), now=NOW,
          file="insights-ma3ak.json", themes_state="themes-ma3ak.json")
    posts = json.loads((state / "insights-ma3ak.json").read_text())["posts"]
    assert f"facebook:{PAGE}_9" not in posts                         # the Page's Word of the day (images.json)
    assert "facebook:999_5" not in posts and "facebook:7001" in posts   # another Page's post out; a reel's id kept
    assert posts["facebook:111"]["kind"] == "other"                     # published.json not read: not the Page's reel


def test_a_youtube_title_of_its_own_is_recognised():
    """2026-11-21 (owner's choice): the film of Dhul-Qarnayn is titled on YouTube « قصة ذو القرنين: 3
    اختبارات للقوة · The story of Dhul-Qarnayn: 3 tests of power », not like its heading: the « YouTube ·
    Titre » block of its section is read, and that title is matched whole, never by a prefix."""
    texts = """# Dhul-Qarnayn · ذو القرنين : textes de publication

## Le film · Dhul-Qarnayn: 3 tests of power · ذو القرنين: ٣ اختبارات للقوة

`qarnayn-film-16x9.mp4` · 8:24 · 16:9 · YouTube · miniature : `qarnayn-film-thumbnail.jpg`

**YouTube · Titre (78/100)**

```text
قصة ذو القرنين: 3 اختبارات للقوة · The story of Dhul-Qarnayn: 3 tests of power
```

## Short 1 · The fate of a whole people… at his word · مصير قوم كاملين… بكلمة منه!

`qarnayn-short-1-west.mp4` · 2:06 · 9:16 · Facebook, Instagram, TikTok, YouTube Shorts · couverture : `c.jpg`

**YouTube · Titre (69/100)**

```text
مصير قوم كاملين… بكلمة منه! · The fate of a whole people… at his word
```
"""
    videos = T.parse_texts("qarnayn", texts)
    assert videos[0].title_youtube == ("قصة ذو القرنين: 3 اختبارات للقوة · The story of Dhul-Qarnayn: "
                                       "3 tests of power")
    themes = T.ThemeIndex(videos)
    assert themes.match(videos[0].title_youtube, "youtube").id == "qarnayn/film"
    assert themes.match("Dhul-Qarnayn: 3 tests of power · ذو القرنين: ٣ اختبارات للقوة", "youtube").id \
        == "qarnayn/film"                                        # the heading's order still works
    assert themes.match("قصة ذو القرنين: 3 اختبارات للقوة", "youtube") is None   # its half: not whole
    assert themes.match(videos[1].title_youtube, "youtube").id == "qarnayn/short-1"
