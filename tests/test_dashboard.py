"""The dashboard of the statistics page (catalog/dashboard.py, catalog/charts.py): the dataset
for the sessions, what the page computes, and the charts it draws. No network."""

import json
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from quran_reels.catalog import charts, dashboard, stats
from quran_reels.catalog.page import render_stats

TZ = ZoneInfo("Europe/Paris")
NOW = datetime(2026, 11, 21, 15, tzinfo=UTC)


def snap(views, watch=None, **more):
    m = {"views": views} | ({"watch_pct": watch} if watch is not None else {}) | more
    return {"at": "2026-11-20T04:00:00+00:00", "age_h": 50, "m": m}


def reel(platform, day, views, watch, reciter="sayegh", seconds=40.0, **more):
    key = f"slot:{day}/morning"
    return {"platform": platform, "published": f"{day}T06:30:00+00:00", "kind": "reel-morning",
            "key": key, "label": "105:1-5", "first_line": "سورة الفيل · Surah Al-Fil (105:1-5)",
            "seconds": seconds, "url": "https://x", "seen": "2026-11-21T04:00:00+00:00",
            "ref": {"slot": f"{day}/morning", "item": "juz-amma/105:1-5", "passage": "105:1-5",
                    "reciter": reciter},
            "snapshots": {"48h": snap(views, watch), "latest": snap(views + 10, watch)}} | more


def insights():
    posts = {
        "facebook:1": reel("facebook", "2026-11-10", 300, 20.0,
                           retention={"0": 1, "1": 1, "2": 0.8, "3": 0.6}),
        "facebook:2": reel("facebook", "2026-11-11", 200, 30.0, reciter="minshawi",
                           retention={"0": 1, "1": 0.9, "2": 0.7, "3": 0.5}),
        "facebook:3": reel("facebook", "2026-11-12", 100, 10.0),
        "youtube:abc": reel("youtube", "2026-11-10", 900, 110.0, engaged=400),
        "facebook:4": {"platform": "facebook", "published": "2026-11-15T17:00:00+00:00",
                       "kind": "theme-short", "key": "theme:dua/short-1", "label": "Du'a 1",
                       "seconds": 100, "ref": {"theme": "dua/short-1", "series": "dua",
                                               "cut": "dua-short-1-cut.mp4"},
                       "snapshots": {"48h": snap(150, 8.0)}, "seen": "2026-11-21T04:00:00+00:00"},
    }
    return {"posts": posts, "listed": "2026-11-21T04:00:00+00:00",
            "listed_youtube": "2026-11-21T04:00:00+00:00",
            "accounts": {"youtube": {"2026-11-10": {"followers_count": 100},
                                     "2026-11-20": {"followers_count": 180}},
                         "facebook": {"2026-11-10": {"followers_count": 40},
                                      "2026-11-20": {"followers_count": 54}}},
            "manual": [
                {"platform": "youtube", "video": "slot:2026-11-10/morning",
                 "published": "2026-11-10", "seen": "2026-11-20",
                 "m": {"impressions": 70, "ctr": 8.57}, "source": "export YouTube Studio"},
                {"platform": "tiktok", "video": "105:1-5", "published": "2026-11-10",
                 "seen": "2026-11-15", "m": {"views": 700}, "source": "capture"}],
            "updated": "2026-11-21T04:39:00+00:00"}


DETAIL = {"read": "2026-11-21T03:35:08+00:00", "from": "2026-11-10", "to": "2026-11-20",
          "channel": {"countries": [{"country": "DZ", "views": 10, "pct": 20.8},
                                    {"country": "XX", "views": 5, "pct": 10.0}],
                      "search_terms": [{"insightTrafficSourceDetail": "سورة الفيل", "views": 50,
                                        "pct": 100.0}]},
          "videos": [{"id": "abc", "sources": [
              {"insightTrafficSourceType": "SHORTS", "views": 80, "pct": 80.0},
              {"insightTrafficSourceType": "YT_SEARCH", "views": 15, "pct": 15.0},
              {"insightTrafficSourceType": "EXT_URL", "views": 5, "pct": 5.0}],
              "countries": [{"country": "DZ", "views": 10, "pct": 50.0}],
              "retention": [[0.01, 1.4, 0.5], [0.5, 1.1, 0.5], [1.0, 0.9, 0.5]]}]}

SETTINGS = {"compare": {"min_videos": 3, "min_points": 12},
            "trials": [{"what": "Titres en arabe d'abord", "since": date(2026, 11, 12),
                        "where": "Facebook", "judge": "vues", "platforms": ["facebook"],
                        "kinds": ["Reels"], "days": 3}],
            "missing": [{"what": "CTR", "how": "export", "often": "hebdo",
                         "look": {"platform": "youtube", "metric": "ctr"}},
                        {"what": "Meta reach", "how": "export", "often": "hebdo",
                         "look": {"platform": "facebook", "metric": "reach"}},
                        {"what": "Audience", "how": "API", "often": "la nuit"}]}
BACKGROUNDS = {"slot:2026-11-10/morning": {"id": "sea", "theme": "mer", "kind": "scène générée"}}


def build():
    return stats.build(insights(), SETTINGS, NOW, TZ, None,
                       {"sayegh": "Tawfiq As-Sayegh", "minshawi": "Al-Minshawi"}, DETAIL,
                       BACKGROUNDS, {"juz-amma": "Juz' 'Amma"})


def test_one_row_per_video_and_platform_with_what_is_known_about_it():
    rows = build()["dataset"]
    fb = next(r for r in rows if r["id"] == "facebook:1")
    assert fb | {} == fb and fb["video"] == "slot:2026-11-10/morning"
    assert (fb["group"], fb["reciter"], fb["series"], fb["series_label"]) == (
        "Reels", "Tawfiq As-Sayegh", "juz-amma", "Juz' 'Amma")
    assert (fb["background"], fb["background_theme"], fb["background_kind"]) == (
        "sea", "mer", "scène générée")
    assert fb["weekday"] == 1 and fb["hour"] == "07:30"            # a Tuesday, Paris time
    assert fb["m48"]["views"] == 300 and fb["latest"]["views"] == 310
    assert fb["length"] == "30 s à 1 min"
    # YouTube: the Studio export joins its row, the night's detail too
    yt = next(r for r in rows if r["platform"] == "youtube")
    assert yt["studio"] == {"impressions": 70, "ctr": 8.57, "seen": "2026-11-20"}
    assert yt["yt"]["sources"]["SHORTS"] == 80.0
    # a short version is marked, its own kind kept
    cut = next(r for r in rows if r["id"] == "facebook:4")
    assert cut["cut"] and cut["group"] == "Shorts thématiques"
    # TikTok: a row of its own from the capture, with the reel's attributes
    tt = next(r for r in rows if r["platform"] == "tiktok")
    assert tt["video"] == "slot:2026-11-10/morning" and tt["kind"] == "reel-morning"
    assert tt["latest"]["views"] == 700 and tt["reciter"] == "Tawfiq As-Sayegh"
    json.dumps(rows)                                    # dataset.json: plain JSON


def test_audits_mark_groups_too_small_to_conclude():
    dash = build()["dash"]
    by_reciter = next(a for a in dash["audits"] if a["title"] == "Par récitateur")
    sayegh = next(r for r in by_reciter["rows"] if r["name"] == "Tawfiq As-Sayegh")
    assert sayegh["cells"]["facebook"] == {"n": 2, "few": True, "views": 200.0, "watch": 15.0}
    cut = next(a for a in dash["audits"] if a["title"].startswith("Version courte"))
    assert [r["name"] for r in cut["rows"]] == ["version courte"]


def test_before_and_after_a_change_and_what_is_missing():
    dash = build()["dash"]
    (b,) = dash["before_after"]
    (line,) = b["lines"]
    # 2026-11-12: two reels in the three days before, one from that day
    assert (line["n_before"], line["before"], line["n_after"], line["after"]) == (2, 250.0, 1, 100.0)
    assert line["few"] and dash["trials"][0]["since"] == "2026-11-12"
    assert [m["last"] for m in dash["missing"]] == ["2026-11-20", "", None]


def test_followers_youtube_detail_and_retention():
    dash = build()["dash"]
    yt = next(t for t in dash["followers"]["tiles"] if t["platform"] == "youtube")
    assert (yt["now"], yt["week"]) == (180, 80)
    d = dash["youtube"]
    assert d["sources"] == [{"group": "Reels", "views": {"Fil des Shorts": 80, "Recherche": 15,
                                                         "Autres": 5}}]
    assert d["countries"][0] == {"name": "Algérie", "pct": 20.8}
    assert d["countries"][1]["name"] == "XX"                      # unknown code: as is
    assert d["retention"][0]["points"][0] == [0.01, 1.4]
    (fb,) = dash["facebook_retention"]
    assert fb["n"] == 2 and fb["points"][2] == [2.0, 0.75]       # median of 0.8 and 0.7
    assert dash["ctr"]["rows"][0]["points"] == [{"v": 8.57, "label": "105:1-5"}]


def test_the_page_draws_every_chart_with_its_tooltips():
    s = build()
    s.pop("dataset")
    s = json.loads(json.dumps(s, default=str))                   # as data.json holds it
    html = render_stats({"repo": "o/r", "stats": s})
    assert html.count("<svg") >= 8 and 'data-tip="105:1-5 : 300"' in html
    for section in ("overview", "works", "audits", "youtube", "facebook", "tiktok", "trials",
                    "missing", "sessions", "videos"):
        assert f'id="{section}"' in html
    assert "dataset.json" in html and "Algérie" in html and "سورة الفيل" in html


def test_charts_say_when_there_is_nothing_and_write_numbers_in_french():
    assert "Pas encore" in charts.strip([("Reel", "#000", [])], "x")
    assert "Pas encore" in charts.line_chart([], "x")
    assert charts.fmt(1234.5, 1, " %") == "1 234,5 %" and charts.fmt(None) == "—"
    svg = charts.strip([("Reel", "#000", [(10.0, "a"), (1000.0, "b")])], "vues")
    assert svg.count('class="hit"') == 2 and "médiane" in svg


def test_dashboard_groups():
    assert dashboard.group_of("reel-kahf") == "Reels"
    assert dashboard.group_of("theme-film") == "Films"
    assert dashboard.group_of("theme-short-cut") == "Shorts thématiques"
    assert dashboard.group_of("word") is None
