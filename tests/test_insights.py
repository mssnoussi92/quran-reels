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


def test_facebook_reel_numbers_and_retention_in_seconds():
    graph = {str(s): v for s, v in enumerate([1.0, 0.8, 0.6, 0.45, 0.4] + [0.3] * 30)}
    raw = {"blue_reels_play_count": 120, "post_impressions_unique": 90,
           "post_video_avg_time_watched": 14200, "post_video_followers": 2,
           "post_video_social_actions": {"COMMENT": 1, "SHARE": 4},
           "post_video_retention_graph": graph}
    m = M.normalize("facebook-reel", raw, 60)
    assert m["hook"] == 45.0 and m["kept_30s"] == 30.0
    assert (m["views"], m["reach"], m["follows"], m["shares"], m["comments"]) == (120, 90, 2, 4, 1)
    assert m["avg_watch"] == 14.2 and m["watch_pct"] == 23.7


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
        f"{PAGE}/videos": {"data": []},
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
