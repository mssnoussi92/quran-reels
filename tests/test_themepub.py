"""The theme videos of quran-themes-demo on the Page (themepub/, docs/themes.md): texts, calendar,
the day due, the run with fake publishers, Facebook's long videos, covers. No network."""

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from quran_reels.config import load
from quran_reels.models import PublishResult, PublishStatus
from quran_reels.publishers.facebook_video import FacebookVideoPublisher
from quran_reels.publishers.meta import Graph
from quran_reels.publishers.rights import RightsCheck
from quran_reels.themepub import calendar as cal
from quran_reels.themepub import run as R
from quran_reels.themepub import texts as T

SHORTS = """# Du'a · الدعاء : textes de publication

## Le film · Du'a: 3 wrong ideas · الدعاء: ٣ أفكار

`dua-film-16x9.mp4` · 7:36 · 16:9 · YouTube · miniature : `dua-film-thumbnail.jpg`

**Titre YouTube (78/100)**

```text
Du'a: 3 wrong ideas · الدعاء: ٣ أفكار
```

## Short 1 · Patient… and he asked · صابر… ودعا!

`dua-short-1-asked.mp4` (TikTok : `dua-short-1-asked-tiktok.mp4`, signée `@quran.words.daily`) · 1:49 · 9:16 · Facebook, Instagram, TikTok, YouTube Shorts · couverture : `dua-short-1-asked-cover.jpg`

**Facebook (8 hashtags)**

```text
Patient… and he asked
صابر… ودعا!

@quran_words_daily

#QuranWordsDaily #Dua
```

**Instagram (5 hashtags)**

```text
Patient… and he asked (IG)
```

**TikTok : la vidéo `dua-short-1-asked-tiktok.mp4` (5 hashtags)**

```text
Patient… and he asked (TT)
@quran.words.daily
```

**Titre YouTube (35/100)**

```text
Patient… and he asked · صابر… ودعا!
```
"""
FILM_916 = """# Du'a · الدعاء : le film en 9:16

## Le film en 9:16 · Du'a: 3 wrong ideas · الدعاء: ٣ أفكار

`dua-film-9x16.mp4` · 7:36 · 9:16 · Facebook

**Facebook (3 hashtags)**

```text
Du'a, the film (FB)
```
"""
SIGNS = """# Signs · سنريهم آياتنا : textes de publication

## Short 2 · Even Einstein got this wrong · حتى أينشتاين غلط فيها

`signs-short-2-universe.mp4` (TikTok : `signs-short-2-universe-tiktok.mp4`) · 1:34 · 9:16 · Facebook, Instagram, TikTok, YouTube Shorts · couverture : `signs-short-2-universe-cover.jpg`

**Facebook (3 hashtags)**

```text
Einstein (FB)
```

**Instagram (5 hashtags)**

```text
Einstein (IG)
```

**TikTok : la vidéo `signs-short-2-universe-tiktok.mp4` (5 hashtags)**

```text
Einstein (TT)
```
"""
FARQ = SIGNS.replace("signs-short-2-universe", "farq-short-2-adab").replace(
    "Even Einstein got this wrong", "Once he said I").replace("Einstein", "Adab")
CALENDAR = """# Calendrier

## Le calendrier

| Date | Quoi | Où | Fichiers | Texte |
| --- | --- | --- | --- | --- |
| ~~ven. 13 nov.~~ | ~~Khidr, short 1~~ | les quatre | `x.mp4` | `publication-moussa-khidr.md` : « Short 1 » |
| lun. 23 nov., soir | Du'a : le film | YouTube (16:9) ; Facebook (vertical) | releases `dua-candidate`, `dua-9x16-candidate` | `publication-dua.md` : « Le film » ; `publication-dua-9x16.md` |
| mar. 24 nov. | Du'a, short 1 : Ayyoub | les quatre | release `dua-candidate` | `publication-dua.md` : « Short 1 » |
| sam. 28 nov. | « سنريهم آياتنا » 2 : le cosmos | les quatre | release `signs-candidate` | `publication-signs.md` : « Short 2 » |
| lun. 30 nov. → mar. 1 déc. | **une histoire nouvelle** | | à faire | à faire |
| ven. 25 déc. | « لاحظت الفرق؟ » 2 : l'adab | les quatre | release `farq-candidate` | « Short 2 » |
| sam. 26 déc. | mismatch | les quatre | release `farq-candidate` | `publication-signs.md` : « Short 2 » |
"""


def videos():
    return T.parse("dua", SHORTS) | T.parse("dua-9x16", FILM_916) | T.parse("signs", SIGNS) | \
        T.parse("farq", FARQ)


def sources():
    vids = videos()
    rows = cal.rows(CALENDAR, date(2026, 11, 20))
    for r in rows:
        cal.resolve(r, vids, ["facebook", "instagram", "tiktok"])
    return R.Sources(vids, rows)


def row(day):
    return next(r for r in sources().rows if r.day == day)


# ------------------------------------------------------------------------------ texts, calendar


def test_publication_texts_with_every_platform_block():
    v = videos()["dua/short-1"]
    assert (v.video, v.tiktok, v.cover, v.seconds) == (
        "dua-short-1-asked.mp4", "dua-short-1-asked-tiktok.mp4", "dua-short-1-asked-cover.jpg", 109)
    assert v.platforms == ["facebook", "instagram", "tiktok", "youtube"]
    assert v.captions["facebook"].startswith("Patient… and he asked\nصابر… ودعا!\n")
    assert v.captions["facebook"].endswith("#QuranWordsDaily #Dua\n")
    assert v.captions["instagram"] == "Patient… and he asked (IG)\n"
    assert v.captions["tiktok"] == "Patient… and he asked (TT)\n@quran.words.daily\n"
    assert v.captions["youtube_title"] == "Patient… and he asked · صابر… ودعا!\n"
    film = videos()["dua/film"]
    assert (film.video, film.thumbnail, film.platforms) == (
        "dua-film-16x9.mp4", "dua-film-thumbnail.jpg", ["youtube"])
    assert videos()["dua-9x16/film"].captions == {"facebook": "Du'a, the film (FB)\n"}


def test_each_row_is_tied_to_its_video_per_platform():
    film = row(date(2026, 11, 23))
    assert {p: v.id for p, v in film.videos.items()} == {"facebook": "dua-9x16/film"}
    assert not film.problems                       # Instagram and TikTok are not on the row
    short = row(date(2026, 11, 24))
    assert {p: v.id for p, v in short.videos.items()} == {
        "facebook": "dua/short-1", "instagram": "dua/short-1", "tiktok": "dua/short-1"}
    assert R.youtube_video(film, videos()).id == "dua/film"
    assert R.youtube_video(short, videos()).id == "dua/short-1"


def test_a_row_takes_its_text_from_its_release_never_from_the_row_before():
    """2026-11-15: the 25 December row (« Short 2 », release farq-candidate) came after a
    « سنريهم آياتنا » row and took its text: signs/short-2 would have gone out."""
    adab = row(date(2026, 12, 25))
    assert {v.id for v in adab.videos.values()} == {"farq/short-2"}
    mismatch = row(date(2026, 12, 26))
    assert not mismatch.videos and "ne nomment pas le même texte" in mismatch.problems[0]


def test_texts_not_validated_yet_are_never_published():
    """2026-11-15: the short captions are proposed in the texts before the owner validates them;
    publish.py says so in the opening paragraph, and nothing goes out with them."""
    pending = SHORTS.replace("textes de publication\n",
                             "textes de publication\n\nLégendes courtes **proposées par la session, pas "
                             "encore validées par le propriétaire** : rien n'est publié avec elles avant.\n", 1)
    vids = T.parse("dua", pending)
    assert vids["dua/short-1"].pending and not videos()["dua/short-1"].pending
    r = next(r for r in cal.rows(CALENDAR, date(2026, 11, 20)) if r.day == date(2026, 11, 24))
    cal.resolve(r, vids | T.parse("dua-9x16", FILM_916), ["facebook", "instagram", "tiktok"])
    assert not r.videos and all("pas encore validés" in p for p in r.problems)


def test_struck_and_to_do_rows_publish_nothing():
    rows = sources().rows
    assert next(r for r in rows if r.day == date(2026, 11, 13)).published
    todo = [r for r in rows if r.todo]
    assert [r.day for r in todo] == [date(2026, 11, 30), date(2026, 12, 1)]
    assert all(not r.videos and not r.problems for r in todo)


# ------------------------------------------------------------------------------ the day due

S = {"enabled": True, "from": "2026-11-23", "time": "19:00", "early_minutes": 20,
     "window_hours": 3, "platforms": ["facebook", "instagram", "tiktok"],
     "repo": "o/themes", "release_prefix": "page-", "reels_max_seconds": 90}


def paris(day, hhmm):
    return datetime.fromisoformat(f"{day}T{hhmm}:00+01:00")


def test_the_day_is_due_from_18_40_to_22_00_paris():
    src, state = sources(), {"posts": {}}
    assert R.due(S, state, src, paris("2026-11-24", "18:39")) is None
    assert R.due(S, state, src, paris("2026-11-24", "18:41")).day == date(2026, 11, 24)
    assert R.due(S, state, src, paris("2026-11-24", "22:01")) is None
    assert R.due(S, state, src, paris("2026-11-21", "19:00")) is None   # before `from`
    done = {"posts": {"2026-11-24": {"results": {
        "facebook": {"status": "published"}, "instagram": {"status": "published"},
        "tiktok": {"status": "failed", "remote_id": "v_inbox~1"}}}}}
    assert R.due(S, done, src, paris("2026-11-24", "19:30")) is None    # TikTok may have it
    again = {"posts": {"2026-11-24": {"results": {
        "facebook": {"status": "published"}, "instagram": {"status": "failed"}}}}}
    assert R.due(S, again, src, paris("2026-11-24", "19:30")).day == date(2026, 11, 24)


# ------------------------------------------------------------------------------ the run


class FakePub:
    def __init__(self, name, clear=True):
        self.name, self.clear, self.calls = name, clear, []

    def prepare(self, reel):
        self.calls.append(("prepare", reel))
        return f"{self.name}-draft"

    def rights(self, object_id):
        return RightsCheck(self.name, "complete", matches_found=not self.clear)

    def commit(self, draft_id, reel):
        self.calls.append(("commit", reel))
        return PublishResult(self.name, PublishStatus.PUBLISHED, remote_id=f"{self.name}-1",
                             url=f"https://{self.name}/1")

    def publish(self, reel, dry_run=False):
        self.calls.append(("publish", reel))
        return PublishResult(self.name, PublishStatus.DRAFT, remote_id="v_inbox~1")

    def remove(self, object_id):
        self.calls.append(("remove", object_id))

    def cover(self, object_id, reel):
        self.calls.append(("cover", object_id))


@pytest.fixture
def setup(tmp_path, monkeypatch):
    cfg = load()
    monkeypatch.setattr(R, "settings", lambda cfg: S)
    pubs = {"facebook": FakePub("facebook"), "instagram": FakePub("instagram"),
            "tiktok": FakePub("tiktok")}
    fetched = []

    def download(s, doc, name, folder):
        fetched.append(name)
        f = tmp_path / "files" / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"x")
        return f

    def run(**kw):
        return R.run(cfg, tmp_path / "themes.json", src=sources(), download=download,
                     encode=lambda video: video.with_name(video.stem + "-instagram.mp4"),
                     publish_file=lambda path: f"https://example.org/reels/{path.name}",
                     make_publishers=lambda cfg, s, row, wanted: pubs,
                     report=tmp_path / "report.json", **kw)
    return run, pubs, fetched, tmp_path


def test_the_day_goes_out_with_its_own_texts_files_and_cover(setup):
    run, pubs, _fetched, tmp = setup
    out = run(now=paris("2026-11-24", "18:45"))
    assert out["due"] and not out["failed"]
    fb_reel = pubs["facebook"].calls[0][1]
    assert fb_reel.caption.startswith("Patient… and he asked\n") and fb_reel.seconds == 109
    assert fb_reel.cover_image.name == "dua-short-1-asked-cover.jpg"
    assert pubs["instagram"].calls[0][1].cover_url == (
        "https://github.com/o/themes/releases/download/page-dua/dua-short-1-asked-cover.jpg")
    assert pubs["tiktok"].calls[0][1].video.name == "dua-short-1-asked-tiktok.mp4"
    assert pubs["instagram"].calls[0][1].video.name == "dua-short-1-asked-instagram.mp4"
    assert pubs["instagram"].calls[0][1].video_url == (
        "https://example.org/reels/dua-short-1-asked-instagram.mp4")
    assert fb_reel.video.name == "dua-short-1-asked.mp4"           # Facebook: the file as it is
    assert pubs["tiktok"].calls[0][1].caption.endswith("@quran.words.daily\n")
    state = json.loads((tmp / "themes.json").read_text())["posts"]["2026-11-24"]
    assert {p: r["status"] for p, r in state["results"].items()} == {
        "facebook": "published", "instagram": "published", "tiktok": "draft"}
    item = json.loads((tmp / "report.json").read_text())["items"][0]
    assert item["files"]["mp4"].endswith("page-dua/dua-short-1-asked-tiktok.mp4")
    assert "dua-short-1-asked.mp4" in item["notes"][1] and "YouTube" in item["notes"][1]
    # the page publier.html (feed.py): the TikTok text of the draft, the YouTube file and title
    assert item["match"] == ["theme:dua/short-1"]
    assert item["youtube"] == {
        "title": "Patient… and he asked · صابر… ودعا!", "description": "", "hashtags": "",
        "file": "https://github.com/o/themes/releases/download/page-dua/dua-short-1-asked.mp4"}

    class Previews:
        def publish(self, files, message, derived=None):
            self.files, self.derived = files, derived

    from quran_reels import feed

    previews = Previews()
    assert R.page_files(tmp / "report.json", previews) == 0
    assert previews.derived is feed.files
    e = feed.entry(json.loads(previews.files["theme/2026-11-24/reel.json"]))
    assert (e["kind"], e["key"], e["day"], e["time"]) == ("theme", "theme:2026-11-24",
                                                          "2026-11-24", "19:00")
    assert e["tiktok"] == item["caption"] and e["youtube"] == item["youtube"]
    assert e["match"] == ["theme:dua/short-1"] and e["title"] == item["label"]
    assert {r["name"]: r["label"] for r in e["results"]} == {
        "Facebook": "publié", "Instagram": "publié", "TikTok": "brouillon, non publié"}
    # the next run of the window does nothing more
    for p in pubs.values():
        p.calls.clear()
    assert not run(now=paris("2026-11-24", "19:50"))["due"]
    assert not any(p.calls for p in pubs.values())


def test_facebook_instagram_and_youtube_take_the_short_version(setup, monkeypatch):
    """2026-11-16 (quran-themes-demo, PR #36; the owner's trial on Dhul-Qarnayn's three shorts):
    a short cut for Facebook and Instagram, named on the line of files after the cover; YouTube
    too since 2026-11-18 (owner's choice: the page publier.html gives it that file to upload);
    TikTok keeps the whole short, and every platform its own text."""
    line = "couverture : `dua-short-1-asked-cover.jpg`"
    monkeypatch.setitem(globals(), "SHORTS", SHORTS.replace(
        line, line + " · version courte pour Facebook et Instagram : `dua-short-1-asked-cut.mp4`, 1:13",
        1))
    v = videos()["dua/short-1"]
    assert (v.video, v.cut, v.cut_seconds, v.seconds, v.aspect) == (
        "dua-short-1-asked.mp4", "dua-short-1-asked-cut.mp4", 73, 109, "9:16")
    assert v.platforms == ["facebook", "instagram", "tiktok", "youtube"]
    assert [R.file_for(p, v) for p in ("facebook", "instagram", "tiktok", "youtube")] == [
        ("dua-short-1-asked-cut.mp4", 73), ("dua-short-1-asked-cut.mp4", 73),
        ("dua-short-1-asked-tiktok.mp4", 109), ("dua-short-1-asked-cut.mp4", 73)]
    run, pubs, _fetched, tmp = setup
    out = run(now=paris("2026-11-24", "18:45"))
    assert out["due"] and not out["failed"]
    fb, ig, tt = (pubs[p].calls[0][1] for p in ("facebook", "instagram", "tiktok"))
    assert (fb.video.name, fb.seconds) == ("dua-short-1-asked-cut.mp4", 73)
    assert ig.video.name == "dua-short-1-asked-cut-instagram.mp4"
    assert tt.video.name == "dua-short-1-asked-tiktok.mp4"
    assert fb.caption.startswith("Patient… and he asked\n")
    state = json.loads((tmp / "themes.json").read_text())["posts"]["2026-11-24"]
    assert state["cut"] == {"facebook": "dua-short-1-asked-cut.mp4",
                            "instagram": "dua-short-1-asked-cut.mp4"}
    item = json.loads((tmp / "report.json").read_text())["items"][0]
    assert item["youtube"]["file"].endswith("page-dua/dua-short-1-asked-cut.mp4")
    assert "page-dua/dua-short-1-asked-cut.mp4)" in "\n".join(item["notes"])


def test_a_rights_match_stops_every_platform_tiktok_included(setup):
    run, pubs, _, tmp = setup
    pubs["instagram"].clear = False
    out = run(now=paris("2026-11-24", "18:45"))
    results = json.loads((tmp / "themes.json").read_text())["posts"]["2026-11-24"]["results"]
    assert {p: r["status"] for p, r in results.items()} == {
        "facebook": "blocked", "instagram": "blocked", "tiktok": "blocked"}
    assert not [c for c in pubs["facebook"].calls if c[0] == "commit"]
    assert not pubs["tiktok"].calls and out["failed"]


def test_a_dry_run_records_nothing_and_sends_tiktok_nothing(setup):
    run, pubs, _, tmp = setup
    out = run(day=date(2026, 11, 23), dry_run=True)
    assert out["items"][0]["results"]["facebook"]["status"] == "draft"
    assert ("remove", "facebook-draft") in pubs["facebook"].calls
    assert not (tmp / "themes.json").exists()
    assert not pubs["tiktok"].calls and not pubs["instagram"].calls     # the film: Facebook only


QUIZ = SIGNS.replace("signs-short-2-universe", "quiz-short-1-sayyara").replace(
    "## Short 2 · Even Einstein got this wrong · حتى أينشتاين غلط فيها",
    "## Short 1 · A car in Surat Yusuf? · سيارة في سورة يوسف؟").replace("Einstein", "Sayyara")
QUIZ_ROW = ("| lun. 23 nov. | « معاك 5 ثواني » 1 : سيارة | Instagram | release `quiz-candidate` | "
            "`publication-quiz.md` : « Short 1 » |\n")


@pytest.fixture
def quiz_monday(monkeypatch):
    """2026-11-17, the owner's choice: the quiz on Instagram on a Monday whose film Instagram does
    not get, both published by quran-reels."""
    film = "| mar. 24 nov. | Du'a, short 1"
    monkeypatch.setitem(globals(), "CALENDAR", CALENDAR.replace(film, QUIZ_ROW + film, 1))
    plain = videos
    monkeypatch.setitem(globals(), "videos", lambda: plain() | T.parse("quiz", QUIZ))


def test_two_videos_on_one_day_each_on_its_own_platforms(setup, quiz_monday):
    rows = [r for r in sources().rows if r.day == date(2026, 11, 23)]
    assert [(r.n, sorted(r.videos)) for r in rows] == [(1, ["facebook"]), (2, ["instagram"])]
    assert not any(r.problems for r in rows)
    assert [r.label for r in R.due_rows(S, {"posts": {}}, sources(), paris("2026-11-23", "18:45"))] \
        == [rows[0].label, rows[1].label]
    run, pubs, _fetched, tmp = setup
    out = run(now=paris("2026-11-23", "18:45"))
    assert out["due"] and not out["failed"]
    assert pubs["facebook"].calls[0][1].video.name == "dua-film-9x16.mp4"
    assert pubs["instagram"].calls[0][1].video.name == "quiz-short-1-sayyara-instagram.mp4"
    assert pubs["instagram"].calls[0][1].caption.startswith("Sayyara (IG)")
    assert not pubs["tiktok"].calls                       # neither row has TikTok
    entry = json.loads((tmp / "themes.json").read_text())["posts"]["2026-11-23"]
    assert {p: r["status"] for p, r in entry["results"].items()} == {
        "facebook": "published", "instagram": "published"}
    assert entry["videos"] == {"facebook": "dua-9x16/film", "instagram": "quiz/short-1"}
    items = json.loads((tmp / "report.json").read_text())["items"]
    assert [(i["key"], sorted(i["results"])) for i in items] == [
        ("theme:2026-11-23", ["facebook"]), ("theme:2026-11-23-2", ["instagram"])]

    class Previews:
        def publish(self, files, message, derived=None):
            self.files = files

    previews = Previews()
    R.page_files(tmp / "report.json", previews)
    assert sorted(previews.files) == ["theme/2026-11-23-2/reel.json", "theme/2026-11-23/reel.json"]
    from quran_reels import feed

    second = feed.entry(json.loads(previews.files["theme/2026-11-23-2/reel.json"]))
    assert (second["key"], second["day"]) == ("theme:2026-11-23-2", "2026-11-23")
    # done: the next run of the window sends nothing again
    for p in pubs.values():
        p.calls.clear()
    assert not run(now=paris("2026-11-23", "19:40"))["due"]
    assert not any(p.calls for p in pubs.values())


def test_a_second_video_on_a_platform_already_taken_that_day_never_goes_out():
    text = CALENDAR.replace("| sam. 28 nov. |", "| sam. 28 nov. | doublon | Instagram ; TikTok | "
                            "release `farq-candidate` | « Short 2 » |\n| sam. 28 nov. |", 1)
    rows = [r for r in cal.rows(text, date(2026, 11, 20)) if r.day == date(2026, 11, 28)]
    assert [r.n for r in rows] == [1, 2] and not rows[0].problems
    assert rows[1].problems and "instagram, tiktok" in rows[1].problems[0]
    vids = videos()
    for r in rows:
        cal.resolve(r, vids, ["facebook", "instagram", "tiktok"])
    assert rows[0].videos and not rows[1].videos


def test_the_catalogue_shows_each_video_of_a_day_with_its_own_platforms():
    from quran_reels.catalog import stats as stats_mod
    from quran_reels.insights.themes import ThemeDay

    calendar = [{"date": "2026-11-23"}]
    stats_mod.merge_calendar(calendar, [
        ThemeDay(day="2026-11-23", label="film", where="YouTube (16:9) ; Facebook (vertical)"),
        ThemeDay(day="2026-11-23", label="quiz", where="Instagram")],
        "19:00", "2026-11-23",
        {"2026-11-23": {"results": {"facebook": {"status": "published"},
                                    "instagram": {"status": "published"}}}})
    assert [(t["label"], t["sent"]) for t in calendar[0]["themes"]] == [
        ("film", ["facebook"]), ("quiz", ["instagram"])]


def test_upcoming_check_names_what_would_stop_a_day(monkeypatch):
    monkeypatch.setattr(R, "settings", lambda cfg: S)
    _lines, problems = R.check_upcoming(load(), days=50, today=date(2026, 11, 20), src=sources(),
                                       exists=lambda url: "cover" not in url)
    assert any("2026-11-24" in p and "dua-short-1-asked-cover.jpg" in p for p in problems)
    assert any("2026-11-30" in p and "à faire" in p for p in problems)
    assert any("2026-12-26" in p for p in problems)


# ------------------------------------------------------------------------------ Facebook, long


class Resp:
    def __init__(self, body, status=200):
        self.body, self.status_code, self.headers = body, status, {}

    def json(self):
        return self.body


class FakeSession:
    def __init__(self):
        self.calls, self.headers, self.n = [], {}, 0

    def request(self, method, url, timeout=None, params=None, data=None, headers=None,
                files=None):
        self.calls.append((method, url, dict(data or {}), sorted(files or {}), timeout))
        if url.endswith("/videos"):
            self.n += 1
            return Resp({"id": f"v{self.n}"})
        if method == "GET" and (params or {}).get("fields") == "status":
            return Resp({"status": {"video_status": "ready",
                                    "processing_phase": {"status": "complete"},
                                    "publishing_phase": {"status": "complete"}}})
        if method == "GET":
            return Resp({"permalink_url": "/reel/v2/"})
        return Resp({"success": True})


def test_a_long_video_goes_through_the_page_video_edge_twice(tmp_path):
    video, cover = tmp_path / "film.mp4", tmp_path / "cover.jpg"
    video.write_bytes(b"v")
    cover.write_bytes(b"c")
    session = FakeSession()
    pub = FacebookVideoPublisher(Graph("EAAB", "v24.0", session=session), "PAGE",
                                 poll_interval=0)
    reel = R.ThemeReel(video=video, caption="Film (FB)\n", title="Film · فيلم", seconds=456,
                       cover_image=cover)
    draft = pub.prepare(reel)
    first = session.calls[0]
    assert first[1] == "https://graph-video.facebook.com/v24.0/PAGE/videos"
    assert first[2] == {"description": "Film (FB)\n", "published": "false",
                        "title": "Film · فيلم"} and first[3] == ["source"] and first[4] == 1800
    result = pub.commit(draft, reel)
    assert result.status == PublishStatus.PUBLISHED and result.remote_id == "v2"
    assert result.url == "https://www.facebook.com/reel/v2/"
    published = [c for c in session.calls if c[1].endswith("/videos")][1]
    assert published[2]["published"] == "true"
    assert ("DELETE", "https://graph.facebook.com/v24.0/v1") in [c[:2] for c in session.calls]
    assert any(c[1].endswith("v2/thumbnails") for c in session.calls)


def test_instagram_takes_the_cover_by_its_address():
    from quran_reels.publishers.instagram import InstagramPublisher

    pub = InstagramPublisher(Graph("EAAB", "v24.0", session=FakeSession()), "IG")
    params = pub._params(R.ThemeReel(video=Path("x.mp4"), caption="IG\n",
                                     cover_url="https://example/cover.jpg"))
    assert params["cover_url"] == "https://example/cover.jpg" and "thumb_offset" not in params
    assert params["caption"] == "IG\n"


def test_theme_failures_have_their_own_issue_and_youtube_lines():
    from quran_reels import notify

    item = {"key": "theme:2026-11-24", "day": "2026-11-24", "time": "19:00",
            "passage": "Du'a, short 1", "label": "", "caption": "TT\n",
            "results": {"tiktok": {"status": "draft"}}, "files": {"mp4": "https://x/tt.mp4"},
            "notes": ["", "**YouTube (à la main)** : [ce MP4](https://x/short.mp4)"]}
    body = notify.merge_captions("", {"items": [item]})
    assert "**YouTube (à la main)**" in body and "⬇️ [MP4](https://x/tt.mp4)" in body
    assert notify.ALERTS["themes"] == "⚠️ Vidéo thématique en échec"
    text = notify.failure_text({"items": [item | {"results": {
        "facebook": {"status": "blocked", "error": "droits"}}}]}, "https://run")
    assert "quran-theme" in text and "récitateur" not in text


CARDS = """# Du'a · الدعاء : textes de publication

Pour chaque short, les textes à copier. Légendes courtes **validées par le propriétaire le 2026-11-16**.

## Short 1 · Patient… and he asked · صابر… ودعا!

`dua-short-1-asked.mp4` (TikTok : `dua-short-1-asked-tiktok.mp4`, signée `@quran.words.daily`) · 1:49 · 9:16 · Facebook, Instagram, TikTok, YouTube Shorts · couverture : `dua-short-1-asked-cover.jpg`

**Facebook · Titre**

```text
Patient… and he asked
صابر… ودعا!
```

**Facebook · Description**

```text
Hook (ar)
Hook (en)

🎙️ AI-generated voice
```

**Facebook · Hashtags (3)**

```text
#a #b #c
```

Sur TikTok : la vidéo `dua-short-1-asked-tiktok.mp4`, signée `@quran.words.daily`.

**TikTok · Titre**

```text
Patient… and he asked
صابر… ودعا!
```

**TikTok · Description**

```text
Hook (TT)
```

**TikTok · Hashtags (5)**

```text
#a #b #c #d #e
```

**YouTube · Titre (35/100)**

```text
Patient… and he asked · صابر… ودعا!
```

**YouTube · Description**

```text
The long description
```

**YouTube · Crédits**

```text
Quoted:
• a source
```

**YouTube · Hashtags (5)**

```text
#a #b #c #d #e
```
"""


def test_the_cards_of_a_platform_make_its_caption_in_their_order():
    """2026-11-15: the texts come in cards (title, description, credits, hashtags), each copied on
    the owner's page and pasted into one caption; reading only one of them would have posted the
    hashtags alone."""
    v = T.parse("dua", CARDS)["dua/short-1"]
    assert v.captions["facebook"] == ("Patient… and he asked\nصابر… ودعا!\n\nHook (ar)\nHook (en)\n\n"
                                      "🎙️ AI-generated voice\n\n#a #b #c\n")
    assert v.captions["tiktok"] == "Patient… and he asked\nصابر… ودعا!\n\nHook (TT)\n\n#a #b #c #d #e\n"
    assert "instagram" not in v.captions and not v.pending
    assert v.captions["youtube_title"] == "Patient… and he asked · صابر… ودعا!\n"
    assert v.captions["youtube_description"] == ("The long description\n\nQuoted:\n• a source\n\n"
                                                 "#a #b #c #d #e\n")
    # on the page publier.html, the hashtags have their own Copy button
    assert R.youtube_texts({"repo": "o/themes"}, v) == {
        "title": "Patient… and he asked · صابر… ودعا!",
        "description": "The long description\n\nQuoted:\n• a source", "hashtags": "#a #b #c #d #e",
        "file": "https://github.com/o/themes/releases/download/page-dua/dua-short-1-asked.mp4"}
    assert (v.video, v.tiktok, v.seconds) == ("dua-short-1-asked.mp4", "dua-short-1-asked-tiktok.mp4", 109)


def test_the_instagram_copy_has_no_edit_list_and_no_b_frames(tmp_path):
    """2026-11-15: a theme short (Remotion, two edit lists) stayed IN_PROGRESS on Instagram for
    20 minutes; the daily reels are encoded without edit list for the same reason."""
    import shutil
    import subprocess

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    src = tmp_path / "short.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=108x192:rate=30",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100", "-t", "2",
                    "-c:v", "libx264", "-bf", "3", "-c:a", "aac", "-shortest", str(src)], check=True)
    out = R.for_instagram(src)
    data = out.read_bytes()
    assert out.name == "short-instagram.mp4" and b"elst" not in data and b"ctts" not in data
    probe = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(out)], capture_output=True, text=True,
                           check=False)
    assert "48000 Hz" in probe.stderr and "h264 (High)" in probe.stderr
    assert R.for_instagram(src) == out                    # done once


def test_instagram_fetches_a_video_given_by_its_address():
    """2026-11-15: sent to Instagram's upload address, a 2-minute short failed every time; by
    `video_url` Instagram fetches the file, and nothing is sent to rupload."""
    from types import SimpleNamespace

    from quran_reels.publishers.instagram import InstagramPublisher

    posted, uploads = [], []
    graph = SimpleNamespace(version="v24.0",
                            post=lambda path, **kw: posted.append(kw) or {"id": "c1"},
                            upload=lambda *a: uploads.append(a))
    pub = InstagramPublisher(graph, "ig")
    reel = R.ThemeReel(video=Path("x.mp4"), caption="Title\n", video_url="https://h/x.mp4",
                       cover_url="https://h/c.jpg")
    params = pub._params(reel)
    assert params["video_url"] == "https://h/x.mp4" and "upload_type" not in params
    assert pub._upload(reel, params) == ("c1", False) and not uploads
    assert posted[0]["cover_url"] == "https://h/c.jpg"
