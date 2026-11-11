"""The catalogue (docs/catalog.md): read-only, public facts only, without network."""

import copy
import dataclasses
import json
from datetime import UTC, date, datetime, time
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import pytest

from quran_reels.catalog import backgrounds as bg_mod
from quran_reels.catalog import issues, load_history, previous_backgrounds
from quran_reels.catalog import posts as posts_mod
from quran_reels.catalog import reciters as rec_mod
from quran_reels.catalog import schedule as sched_mod
from quran_reels.catalog.page import render
from quran_reels.catalog.previews import Previews
from quran_reels.config import load
from quran_reels.selector.calendar import Schedule, Series, Slot, State

PARIS = ZoneInfo("Europe/Paris")


@pytest.fixture
def cfg():
    return load()


# ---- reciters ---------------------------------------------------------------------------

@pytest.mark.parametrize("everyayah, label, same", [
    ("Ghamadi", "Saad Al-Ghamdi", True),
    ("Salah Al Budair", "Salah Budair", True),
    ("Minshawy Murattal", "Muhammad Siddiq Al-Minshawi", True),
    ("Menshawi", "Muhammad Siddiq Al-Minshawi", True),
    ("Hudhaify", "Ali Al-Hudhaifi", True),
    ("Muhammad Ayyoub", "Muhammad Ayyub", True),
    ("Hani Rifai", "Nabil Ar-Rifai", False),            # another reciter, same family name
    ("Salaah AbdulRahman Bukhatir", "Salah Budair", False),
    ("Muhammad Jibreel", "Muhammad Ayyub", False),
])
def test_everyayah_names_are_matched_with_the_list(everyayah, label, same):
    assert rec_mod.same_reciter(everyayah, label) is same


def test_everyayah_names_are_cleaned():
    assert rec_mod.clean("Husary (Muallim)") == ("Husary", "muallim")
    assert rec_mod.clean("Minshawy Mujawwad") == ("Minshawy", "mujawwad")
    assert rec_mod.clean("Ahmed ibn Ali al-Ajamy QuranExplorer.Com") == ("Ahmed ibn Ali al-Ajamy", "")
    assert rec_mod.clean("Parhizgar_64Kbps") == ("Parhizgar", "")


RECITATIONS = json.dumps({
    "ayahCount": [7, 286],
    "1": {"subfolder": "Abdul_Basit_Murattal_64kbps", "name": "Abdul Basit Murattal", "bitrate": "64kbps"},
    "2": {"subfolder": "Abdul_Basit_Murattal_192kbps", "name": "Abdul Basit Murattal", "bitrate": "192kbps"},
    "3": {"subfolder": "Abdul_Basit_Mujawwad_128kbps", "name": "Abdul Basit Mujawwad", "bitrate": "128kbps"},
    "4": {"subfolder": "Alafasy_128kbps", "name": "Alafasy", "bitrate": "128kbps"},
    "5": {"subfolder": "Alafasy_64kbps", "name": "Alafasy", "bitrate": "64kbps"},
    "6": {"subfolder": "Salah_Al_Budair_128kbps", "name": "Salah Al Budair", "bitrate": "128kbps"},
    "7": {"subfolder": "Hani_Rifai_192kbps", "name": "Hani Rifai", "bitrate": "192kbps"},
    "8": {"subfolder": "translations/urdu_x", "name": "(Urdu) X", "bitrate": "46kbps"},
    "9": {"subfolder": "English/Sahih_Intnl_Ibrahim_Walk_192kbps",
          "name": "(English) Translated by Sahih International", "bitrate": "192kbps"},
    "10": {"subfolder": "warsh/warsh_Abdul_Basit_128kbps", "name": "(Warsh) Abdul Basit", "bitrate": "128kbps"},
})


def test_candidates_are_the_everyayah_recitations_not_in_the_list(cfg):
    cands, known, left_out = rec_mod.candidates(cfg, rec_mod.recitations(RECITATIONS))
    assert [c["label"] for c in cands] == ["Abdul Basit (mujawwad)", "Abdul Basit (murattal)",
                                           "Hani Rifai"]
    murattal = cands[1]
    assert [f["kbps"] for f in murattal["folders"]] == [192, 64]      # the best one first
    assert murattal["sample"][0].endswith("/Abdul_Basit_Murattal_192kbps/bismillah.mp3")
    assert murattal["sample"][1:] == [
        f"https://everyayah.com/data/Abdul_Basit_Murattal_192kbps/112{a:03d}.mp3" for a in range(1, 5)]
    assert left_out == {"translation": 2, "warsh": 1}
    assert [f["folder"] for f in known["budair"]] == ["Salah_Al_Budair_128kbps"]
    assert [f["folder"] for f in known["alafasy"]] == ["Alafasy_64kbps"]   # its own folder: no


def test_every_reciter_has_the_same_sample_from_its_source(cfg):
    out = rec_mod.collect(cfg, {}, load_history(), None, None)
    by = {r["name"]: r for r in out["list"]}
    assert by["budair"]["sample"] == ["https://cdn.mp3quran.net/audio/salah-budair/r1/112.mp3"]
    assert by["omar_hisham"]["sample"] == ["https://archive.org/download/omar-hisham-al-arabi/112.mp3"]
    assert by["hudhaifi"]["sample"][0] == "https://everyayah.com/data/Hudhaify_128kbps/bismillah.mp3"
    assert by["ayyoub"]["sample"][0].endswith("/Muhammad_Ayyoub_128kbps/001001.mp3")  # its basmala
    rotation = cfg.content["rotation"]["reciters"]
    assert [r["name"] for r in out["list"] if r["status"] == "rotation"] == rotation
    assert all("retirer" in parse_qs(urlparse(by[n]["issue"]).query)["title"][0] for n in rotation)


def test_a_reciter_added_for_a_test_is_shown_as_testing(cfg):
    out = rec_mod.collect(cfg, {}, load_history(), None, None)
    by = {r["name"]: r for r in out["list"]}
    assert by["husary"]["status"] == "testing"               # history: kind test, not rotation
    assert by["husary"]["sample"][0] == "https://everyayah.com/data/Husary_128kbps/bismillah.mp3"
    assert "rotation" in parse_qs(urlparse(by["husary"]["issue"]).query)["title"][0]
    assert by["hudhaifi"]["status"] == "retired"


def test_published_videos_and_claims_come_from_the_state(cfg):
    state = {"slots": {
        "2026-11-05/evening": {"passage": "2:255-255", "reciter": "budair",
                               "results": {"facebook": {"status": "published"}}},
        "2026-11-06/morning": {"passage": "18:1-10", "reciter": "budair",
                               "results": {"facebook": {"status": "failed"}}},
        "2026-11-05/morning": {"passage": "114:1-6",
                               "results": {"facebook": {"status": "published"}}}},
        "removed": [{"slot": "2026-11-05/evening", "why": "muted",
                     "record": {"passage": "2:255-255", "reciter": "rifai", "results": {}}}],
        "claimed": {"sayegh": {"passage": "1:1-7", "reason": "blocked", "at": "2026-11-09T19:40:00+00:00"}}}
    out = rec_mod.collect(cfg, state, load_history(), None, None)
    by = {r["name"]: r for r in out["list"]}
    assert by["budair"]["published"] == 1 and by["budair"]["last"] == "jeudi 5 novembre, soir"
    assert out["unattributed"] == 1
    assert by["rifai"]["removed"][0]["why"] == "muted" and by["rifai"]["claimed"]
    assert by["sayegh"]["claimed"] and by["sayegh"]["events"][-1]["date"] == "2026-11-09"


# ---- issues -------------------------------------------------------------------------------

def test_issue_links_are_prefilled_and_labelled():
    url = issues.remove_background("pb-storm", {"Source": "Pixabay", "Utilisations": 0,
                                                "Page": "https://pixabay.com/videos/id-223338/"})
    parsed = urlparse(url)
    assert (parsed.netloc, parsed.path) == ("github.com", "/mssnoussi92/quran-reels/issues/new")
    q = parse_qs(parsed.query)
    assert q["title"] == ["Catalogue : retirer le fond pb-storm"]
    assert q["labels"] == ["catalog"]
    body = q["body"][0]
    assert "`pb-storm`" in body and "- Source : Pixabay" in body
    assert "Utilisations" not in body                       # empty facts are left out
    assert "catalog/#bg-pb-storm" in body
    for approve in (True, False):
        title = parse_qs(urlparse(issues.clip_decision(approve, "pixabay-1", {})).query)["title"][0]
        assert title.startswith("Catalogue : approuver" if approve else "Catalogue : refuser")


# ---- calendar -----------------------------------------------------------------------------

SERIES = {
    "juz-amma": Series("juz-amma", ("114:1-6", "113:1-5", "112:1-4"), from_plan=True),
    "kursi": Series("kursi", ("2:255-255",), "آية الكرسي", "Ayat al-Kursi"),
    "dua": Series("dua", ("2:186-186", "2:201-201"), "آيات الدعاء", "Supplications from the Quran"),
    "kahf": Series("kahf", ("18:1-10",), "سورة الكهف", "Surah Al-Kahf", repeat=True),
}


def schedule() -> Schedule:
    return Schedule(tz=PARIS, enabled=True,
                    slots=[Slot("morning", time(7, 30), "reading"),
                           Slot("evening", time(19, 30), "themes")],
                    queues={"reading": ["juz-amma"], "themes": ["kursi", "dua"], "kahf": ["kahf"]},
                    friday_queue="kahf", fallback={"themes": "reading"},
                    published_by_hand=frozenset({"113:1-5"}))


def no_rotation(cfg):
    project = copy.deepcopy(cfg.project)
    project["content"]["rotation"] = {}
    return dataclasses.replace(cfg, project=project)


def published_state() -> State:
    return State({"queues": {"reading": {"round": 1, "done": ["juz-amma/114:1-6"]}},
                  "slots": {"2026-11-05/morning": {
                      "queue": "reading", "item": "juz-amma/114:1-6", "passage": "114:1-6",
                      "results": {"facebook": {"status": "published", "url": "https://fb/1"},
                                  "tiktok": {"status": "draft", "id": "v_inbox_file~secret"}}}}})


def test_the_calendar_is_the_daily_logic_and_changes_nothing(cfg):
    state = published_state()
    before = json.dumps(state.data, sort_keys=True)
    days = sched_mod.calendar(no_rotation(cfg), schedule(), SERIES, state, date(2026, 11, 5), 2,
                              None)
    assert json.dumps(state.data, sort_keys=True) == before
    thursday, friday = days
    assert thursday["today"] and not thursday["friday"] and friday["friday"]
    assert [(s["ref"], s["status"]) for s in thursday["slots"]] == [("114:1-6", "published"),
                                                                    ("2:255", "")]
    assert [s["ref"] for s in friday["slots"]] == ["18:1-10", "18:1-10"]
    assert thursday["slots"][1]["label"] == "Ayat al-Kursi"
    assert thursday["slots"][0]["label"] == "juz-amma · 1/3"


def test_series_progress_counts_what_each_queue_published(cfg):
    state = published_state()
    before = json.dumps(state.data, sort_keys=True)
    queues = {q["queue"]: q for q in sched_mod.progress(schedule(), SERIES, state)}
    assert json.dumps(state.data, sort_keys=True) == before
    reading = queues["reading"]
    assert (reading["done"], reading["total"], reading["next"]) == (2, 3, "112:1-4")
    assert reading["series"][0]["by_hand"] == 1               # 113 was published by hand
    assert queues["themes"]["fallback"] == "reading"
    assert queues["kahf"]["used_by"] == ["vendredi"]
    assert queues["themes"]["next"] == "2:255"


def test_passage_references_read_like_the_mushaf():
    assert sched_mod.ref("2:255-255") == "2:255"
    assert sched_mod.ref("93:1-11") == "93:1-11"


# ---- posts --------------------------------------------------------------------------------

def test_posts_show_public_links_and_statuses_only(cfg):
    out = posts_mod.collect(cfg, schedule(), SERIES, published_state().data, None, {}, {})
    post = out["slots"][0]
    assert (post["day"], post["slot_fr"], post["ref"]) == ("jeudi 5 novembre", "matin", "114:1-6")
    by = {r["platform"]: r for r in post["results"]}
    assert by["facebook"]["url"] == "https://fb/1"
    assert by["tiktok"] == {"platform": "tiktok", "name": "TikTok", "status": "draft",
                            "label": "brouillon dans la boîte TikTok", "url": None}
    assert "secret" not in json.dumps(out)                   # inbox ids are not shown


def test_failed_results_show_no_raw_error():
    shown = posts_mod.results({"results": {"instagram": {
        "status": "failed", "error": "container 1789: still processing", "url": None}}})
    assert shown == [{"platform": "instagram", "name": "Instagram", "status": "failed",
                      "label": "échec", "url": None}]


def test_a_post_keeps_the_background_first_computed(cfg, tmp_path):
    record = published_state().data["slots"]["2026-11-05/morning"]
    ident = posts_mod.identity("2026-11-05/morning", record)
    prev = tmp_path / "data.json"
    prev.write_text(json.dumps({"posts": {"slots": [
        {"id": ident, "background": {"id": "sea", "theme": "default", "from": "calculé le 2026-11-05"}}],
        "removed": []}}), encoding="utf-8")
    kept = previous_backgrounds(str(prev))
    out = posts_mod.collect(cfg, schedule(), SERIES, published_state().data, None, kept, {})
    assert out["slots"][0]["background"]["id"] == "sea"
    manifest = {("114:1-6", ""): {"id": "night", "theme": "night"}}
    out = posts_mod.collect(cfg, schedule(), SERIES, published_state().data, None, kept, manifest)
    assert out["slots"][0]["background"] == {"id": "night", "theme": "night", "from": "manifeste"}
    assert previous_backgrounds(str(tmp_path / "missing.json")) == {}


# ---- backgrounds --------------------------------------------------------------------------

def test_backgrounds_count_uses_list_refused_clips_and_filter_candidates(cfg, tmp_path):
    used = [{"background": {"id": "night", "theme": "sky"}, "passage": "2:255-255",
             "when": "2026-11-05 evening"}]
    planned = [{"background": {"id": "night", "theme": "default"}, "passage": "112:1-4",
                "when": "2026-11-08 morning"}]
    clips = [{"id": 95188, "theme": "sky", "author": "NickyPe"},        # refused: not proposed
             {"id": 22512, "theme": "mountains"},                      # listed: not proposed
             {"id": 99999, "theme": "sea", "author": "someone", "tags": ", ".join("abcdefghij"),
              "page": "https://pixabay.com/videos/id-99999/", "duration": 12}]
    out = bg_mod.collect(cfg, load_history(), used, planned, Previews(cfg, tmp_path, enabled=False),
                         clips)
    by = {b["id"]: b for b in out["list"]}
    assert by["night"]["uses"] == [{"when": "2026-11-05 evening", "passage": "2:255", "theme": "sky"}]
    assert by["night"]["themes"] == {"sky": 1} and len(by["night"]["planned"]) == 1
    assert by["night"]["shader"].startswith("#version 300 es")          # drawn live, not a file
    assert by["pb-storm"]["licence"]["name"] == "Licence de contenu Pixabay"
    assert "pb-moving-clouds" in {r["id"] for r in out["refused"]}
    assert [c["pixabay_id"] for c in out["candidates"]] == [99999]
    assert out["candidates"][0]["tags"] == "a, b, c, d, e, f, g, h …"
    assert not list(tmp_path.iterdir())                                 # previews off: no file


# ---- page ---------------------------------------------------------------------------------

def test_the_page_renders_and_escapes(cfg, tmp_path):
    reciters = rec_mod.collect(cfg, {}, load_history(), None, None)
    data = {
        "built_local": "05/11/2026 23:00", "timezone": "Europe/Paris", "commit": "abc1234",
        "state_commit": "", "repo": "mssnoussi92/quran-reels",
        "schedule": {"enabled": True, "days": 2, "fridays": {},
                     "slots": [{"name": "morning", "time": "07:30", "queue": "reading"}]},
        "reciters": reciters,
        "backgrounds": bg_mod.collect(cfg, load_history(), [], [], Previews(cfg, tmp_path, False), None),
        "calendar": sched_mod.calendar(no_rotation(cfg), schedule(), SERIES, published_state(),
                                       date(2026, 11, 5), 2, None),
        "queues": sched_mod.progress(schedule(), SERIES, published_state()),
        "words": {"enabled": True, "time_utc": "11:30", "gloss_source": "", "days": []},
        "posts": posts_mod.collect(cfg, schedule(), SERIES, published_state().data, None, {}, {})
        | {"images": []},
        "notes": ["<script>alert(1)</script>"],
    }
    html = render(data)
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html and "<script>alert" not in html
    for section in ("reciters", "backgrounds", "calendar", "posts"):
        assert f'<section id="{section}">' in html
    assert "Retirer ce récitateur" in html and "Retirer ce fond" in html
    assert 'href="../style.css"' in html                     # the site's own style
    shaders = html.split('<script type="application/json" id="shaders">')[1].split("</script>")[0]
    assert set(json.loads(shaders)) == {"dawn", "night", "sea"}


def test_the_request_form_knows_youtubes_own_reciter(cfg):
    """YouTube: always Tawfiq As-Sayegh (platforms.youtube.reciter). The form says who
    recites when YouTube is ticked with « Auto », and that YouTube is dropped with another."""
    from quran_reels.catalog import ondemand as od_mod

    form = od_mod.launcher(cfg, {})
    assert form["youtube_fixed"] and form["youtube_reciter"] == "Tawfiq As-Sayegh"
    assert {r["name"] for r in form["reciters"] if r["youtube"]} == {"sayegh"}
    assert len(form["reciters"]) > 1
    # Claimed on Meta: not allowed on demand, so no request can go to YouTube.
    out = od_mod.launcher(cfg, {"claimed": {"sayegh": {"reason": "muted"}}})
    assert out["youtube_fixed"] and out["youtube_reciter"] == ""
    assert not any(r["youtube"] for r in out["reciters"])


def test_history_is_dated_facts(cfg):
    history = load_history()
    listed = set(cfg.content["reciters"])
    for name, events in history["reciters"].items():
        assert name in listed, name
        for e in events:
            assert e["kind"] in ("claim", "removed", "check", "added", "test") and e["text"] and e["date"]
    for r in history["backgrounds"]["refused"]:
        assert r["id"] and r["reason"] and r["page"].startswith("https://")
    listed_bgs = {b["id"] for b in cfg.backgrounds["backgrounds"]}
    assert not listed_bgs & {r["id"] for r in history["backgrounds"]["refused"]}


def test_word_of_the_day_starts_after_a_missed_window(cfg, monkeypatch):
    from quran_reels.images import candidates as cand_mod

    c = cand_mod.Candidate("93:2#0", "word", 93, (1, 2), 2, 0, (2,))
    monkeypatch.setattr(cand_mod, "load", lambda cfg, kind: [c])

    class Quran:
        def __init__(self):
            self.chapters = {93: {"name_simple": "Ad-Duhaa", "name_arabic": "الضحى"}}

        def text(self, refs):
            return {r: "وَٱلَّيْلِ إِذَا سَجَىٰ" for r in refs}

    class Src:
        quran = Quran()

    monkeypatch.setattr(sched_mod, "_word", lambda *a: {"word": "سَجَىٰ", "gloss": "سكن"})
    late = sched_mod.words(cfg, Src(), None, datetime(2026, 11, 5, 22, 0, tzinfo=UTC), 2)
    early = sched_mod.words(cfg, Src(), None, datetime(2026, 11, 5, 9, 0, tzinfo=UTC), 2)
    assert [d["date"] for d in late["days"]] == ["2026-11-06", "2026-11-07"]
    assert [d["date"] for d in early["days"]] == ["2026-11-05", "2026-11-06"]
    assert early["days"][0]["word"] == "سَجَىٰ" and early["days"][0]["surah"] == "Ad-Duhaa"



def test_a_published_slot_without_its_reciter_is_not_guessed(cfg, monkeypatch):
    from quran_reels import reciters as rec

    # no network: the rotation's choice and lengths are stubbed
    monkeypatch.setattr(rec, "choose", lambda cfg, key, recent, claimed=(): ("budair", []))
    monkeypatch.setattr(rec, "passage_seconds", lambda cfg, key: rec.Option("budair", 40.0))
    state = published_state()          # 114:1-6 published, no reciter recorded
    days = sched_mod.calendar(cfg, schedule(), SERIES, state, date(2026, 11, 5), 1, None)
    first = days[0]["slots"][0]
    assert first["status"] == "published" and first.get("reciter_unknown")
    assert "reciter" not in first
    assert days[0]["slots"][1]["reciter"] == "budair"     # the next slot is chosen as usual
