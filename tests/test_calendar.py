"""Calendar: slots, queues, Fridays, state and retries, without network or rendering."""

import json
from datetime import UTC, date, datetime, time
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from quran_reels import daily
from quran_reels.models import PublishResult, PublishStatus
from quran_reels.selector.calendar import (
    Schedule,
    Series,
    Slot,
    State,
    _passage_key,
    mark_done,
    next_item,
    preview,
)

PARIS = ZoneInfo("Europe/Paris")
SERIES = {
    "juz-amma": Series("juz-amma", ("114:1-6", "113:1-5", "112:1-4"), from_plan=True),
    "mushaf": Series("mushaf", ("1:1-7",), from_plan=True),
    "kursi": Series("kursi", ("2:255-255",), "آية الكرسي", "Ayat al-Kursi"),
    "dua": Series("dua", ("2:186-186", "2:201-201", "3:8-9"), "آيات الدعاء",
                  "Supplications from the Quran"),
    "kahf": Series("kahf", ("18:1-5", "18:6-12", "18:13-14"), "سورة الكهف يوم الجمعة",
                   "Surah Al-Kahf on Friday", repeat=True, from_plan=True,
                   hashtags=("#Jumuah",)),
    "kahf-first-ten": Series("kahf-first-ten", ("18:1-10",), "أول عشر آيات من سورة الكهف",
                             "The first ten verses of Surah Al-Kahf", repeat=True),
    "kahf-rest": Series("kahf-rest", ("18:11-14", "18:15-16"), "سورة الكهف يوم الجمعة",
                        "Surah Al-Kahf on Friday", repeat=True),
}


def schedule(**kw) -> Schedule:
    return Schedule(tz=PARIS, enabled=True,
                    slots=[Slot("morning", time(7, 30), "reading"),
                           Slot("evening", time(19, 30), "themes")],
                    queues={"reading": ["juz-amma", "mushaf"], "themes": ["kursi", "dua"],
                            "kahf": ["kahf"]},
                    friday_queue="kahf", fallback={"themes": "reading"}, **kw)


def paris(y, m, d, hh, mm) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=PARIS)


def test_slot_window_in_local_time_summer_and_winter():
    s = schedule()
    # winter (UTC+1): the 06:13 UTC run is 07:13 in Paris, inside the morning window
    assert [x.name for _, x in s.due(datetime(2026, 11, 5, 6, 13, tzinfo=UTC))] == ["morning"]
    assert s.due(datetime(2026, 11, 5, 5, 13, tzinfo=UTC)) == []      # 06:13 local: too early
    # summer (UTC+2): the same slot is due at 05:13 UTC
    assert [x.name for _, x in s.due(datetime(2027, 6, 3, 5, 13, tzinfo=UTC))] == ["morning"]
    assert s.due(paris(2026, 11, 5, 10, 31)) == []                     # more than 3 h late


def test_queues_play_their_series_in_order_and_fridays_read_al_kahf():
    days = preview(schedule(), SERIES, State(), date(2026, 11, 5), 2)   # Thursday, Friday
    assert [(q, i.key) for _, _, q, i in days] == [
        ("reading", "114:1-6"), ("themes", "2:255-255"), ("kahf", "18:1-5"), ("kahf", "18:6-12")]


def per_slot_fridays() -> Schedule:
    s = schedule()
    s.queues |= {"kahf-first-ten": ["kahf-first-ten"], "kahf-rest": ["kahf-rest"]}
    s.friday_queue = None
    s.friday_queues = {"morning": "kahf-first-ten", "evening": "kahf-rest"}
    return s


def test_friday_slots_can_each_have_their_queue():
    # The owner's choice: 18:1-10 every Friday morning, the rest of Al-Kahf in the evening.
    days = preview(per_slot_fridays(), SERIES, State(), date(2026, 11, 6), 8)  # 2 Fridays
    fridays = [(d.isoformat(), q, i.key) for d, _, q, i in days if d.weekday() == 4]
    assert fridays == [("2026-11-06", "kahf-first-ten", "18:1-10"),
                       ("2026-11-06", "kahf-rest", "18:11-14"),
                       ("2026-11-13", "kahf-first-ten", "18:1-10"),     # the same, each week
                       ("2026-11-13", "kahf-rest", "18:15-16")]
    weekdays = {q for d, _, q, _ in days if d.weekday() != 4}
    assert weekdays == {"reading", "themes"}


def test_a_friday_slot_not_listed_takes_the_friday_queue():
    s = per_slot_fridays()
    s.friday_queue, s.friday_queues = "kahf", {"evening": "kahf-rest"}
    friday = date(2026, 11, 6)
    assert [s.queue_for(x, friday) for x in s.slots] == ["kahf", "kahf-rest"]


def test_a_finished_queue_hands_over_to_its_fallback():
    state = State()
    for item_id in ("kursi/2:255-255", "dua/2:186-186", "dua/2:201-201", "dua/3:8-9"):
        state.queue("themes")["done"].append(item_id)
    assert next_item(schedule(), SERIES, state, "themes")[0] == "reading"


def test_a_repeating_series_starts_over():
    state = State()
    for key in SERIES["kahf"].passages:
        state.queue("kahf")["done"].append(f"kahf/{key}")
    queue, item = next_item(schedule(), SERIES, state, "kahf")
    assert (queue, item.key, state.queue("kahf")["round"]) == ("kahf", "18:1-5", 2)


def test_labels_number_the_passage_in_its_series():
    _, item = next_item(schedule(), SERIES, State(), "themes")
    assert item.label_ar == "آية الكرسي" and item.label_en == "Ayat al-Kursi"    # one passage
    state = State()
    mark_done(state, "themes", item)
    _, item = next_item(schedule(), SERIES, state, "themes")
    assert item.label_ar == "آيات الدعاء · ١ من ٣"
    assert item.label_en == "Supplications from the Quran · 1/3"
    _, item = next_item(schedule(), SERIES, State(), "reading")
    assert item.label_ar == item.label_en == ""                         # plain reading


@pytest.mark.parametrize(("raw", "key"), [("2:127-128", "2:127-128"), ("2:255", "2:255-255"),
                                          (666, "11:6-6")])   # YAML reads 11:6 as 11×60+6
def test_passage_keys(raw, key):
    assert _passage_key(raw, "test") == key


# ---- daily runs -------------------------------------------------------------------------

@pytest.fixture
def world(monkeypatch, tmp_path):
    """daily.run with the schedule above, fake rendering and fake platforms."""
    calls = {"render": [], "publish": []}
    answers: dict[str, list[PublishStatus]] = {}

    monkeypatch.setattr(daily, "load_series", lambda cfg: SERIES)
    monkeypatch.setattr(daily, "load_schedule", lambda cfg, series: schedule())
    monkeypatch.setattr(daily.publish_mod, "platforms_for", lambda cfg, req: ["facebook",
                                                                              "instagram"])
    monkeypatch.setattr(daily.publish_mod, "meta_check", lambda cfg, p: None)

    class Rendered:
        def __init__(self, key):
            self.video = tmp_path / f"{key}.mp4"

    def render(cfg, key, label_ar="", label_en="", series_tags=()):
        calls["render"].append((key, label_en))
        calls.setdefault("tags", []).append(tuple(series_tags))
        return Rendered(key)

    def publish(cfg, video, platforms, dry_run, checked=None):
        calls["publish"].append((video.stem, tuple(platforms)))
        return [PublishResult(p, answers[p].pop(0) if answers.get(p) else PublishStatus.PUBLISHED,
                              remote_id="1")
                for p in platforms]

    import quran_reels.render as render_mod
    monkeypatch.setattr(render_mod, "render_passage", render)
    monkeypatch.setattr(daily.publish_mod, "publish_reel", publish)
    return calls, answers, tmp_path / "published.json"


def test_daily_publishes_the_slot_once(world):
    calls, _, path = world
    now = paris(2026, 11, 5, 7, 20)
    assert daily.run(None, path, now=now) == 0
    assert calls["publish"] == [("114:1-6", ("facebook", "instagram"))]
    assert daily.run(None, path, now=paris(2026, 11, 5, 8, 20)) == 0    # next run: nothing
    assert len(calls["publish"]) == 1
    state = State.load(path)
    assert state.queue("reading")["done"] == ["juz-amma/114:1-6"]
    assert state.slot(date(2026, 11, 5), "morning")["results"]["instagram"]["status"] == \
        "published"


def test_a_failed_platform_is_retried_with_the_same_passage(world):
    calls, answers, path = world
    answers["instagram"] = [PublishStatus.FAILED]
    assert daily.run(None, path, now=paris(2026, 11, 5, 7, 20)) == 1
    assert daily.run(None, path, now=paris(2026, 11, 5, 8, 20)) == 0
    assert calls["publish"] == [("114:1-6", ("facebook", "instagram")),
                                ("114:1-6", ("instagram",))]
    assert State.load(path).queue("reading")["done"] == ["juz-amma/114:1-6"]


def test_a_slot_that_failed_everywhere_keeps_its_passage_for_the_next_day(world):
    calls, answers, path = world
    answers["facebook"] = [PublishStatus.FAILED]
    answers["instagram"] = [PublishStatus.FAILED]
    daily.run(None, path, now=paris(2026, 11, 5, 7, 20))
    assert State.load(path).queue("reading")["done"] == []
    daily.run(None, path, now=paris(2026, 11, 7, 7, 20))              # Saturday
    assert [c[0] for c in calls["publish"]] == ["114:1-6", "114:1-6"]


def test_check_and_dry_run_change_nothing(world):
    calls, _, path = world
    assert daily.run(None, path, now=paris(2026, 11, 5, 7, 20), check=True) == 0
    assert calls["render"] == [] and not path.exists()
    daily.run(None, path, now=paris(2026, 11, 5, 7, 20), dry_run=True)
    assert calls["render"] == [("114:1-6", "")] and not path.exists()


def test_disabled_schedule_publishes_nothing(world, monkeypatch):
    calls, _, path = world
    off = schedule()
    off.enabled = False
    monkeypatch.setattr(daily, "load_schedule", lambda cfg, series: off)
    assert daily.run(None, path, now=paris(2026, 11, 5, 7, 20)) == 0
    assert calls["render"] == []


def test_friday_evening_continues_al_kahf_with_its_label(world):
    calls, _, path = world
    daily.run(None, path, now=paris(2026, 11, 6, 7, 20))
    daily.run(None, path, now=paris(2026, 11, 6, 19, 20))
    assert calls["render"] == [("18:1-5", "Surah Al-Kahf on Friday · 1/3"),
                               ("18:6-12", "Surah Al-Kahf on Friday · 2/3")]
    assert calls["tags"] == [("#Jumuah",), ("#Jumuah",)]


def test_a_passage_published_by_hand_is_skipped():
    s = schedule(published_by_hand=frozenset({"113:1-5"}))
    days = preview(s, SERIES, State(), date(2026, 11, 7), 2)      # Saturday, Sunday
    assert [i.key for _, slot, _, i in days if slot.name == "morning"] == ["114:1-6", "112:1-4"]


def test_daily_writes_a_report_for_notify_even_when_it_stops(world, monkeypatch, tmp_path):
    import json as _json

    _, answers, path = world
    report = tmp_path / "out" / "daily-report.json"
    answers["instagram"] = [PublishStatus.FAILED]
    assert daily.run(None, path, now=paris(2026, 11, 5, 7, 20), report=report) == 1
    data = _json.loads(report.read_text(encoding="utf-8"))
    [entry] = data["items"]
    assert (entry["key"], entry["passage"], entry["time"]) == ("2026-11-05/morning", "114:1-6",
                                                              "07:30")
    assert entry["results"]["instagram"]["status"] == "failed"

    def expired(cfg, platforms):
        raise SystemExit("Meta token check failed:\ndata access expires in 3 days")

    monkeypatch.setattr(daily.publish_mod, "meta_check", expired)
    with pytest.raises(SystemExit):
        daily.run(None, path, now=paris(2026, 11, 5, 19, 20), report=report)
    data = _json.loads(report.read_text(encoding="utf-8"))
    assert data["items"] == [] and "expires in 3 days" in data["errors"][0]


def test_a_slot_blocked_by_the_rights_check_is_not_retried(world):
    calls, answers, path = world
    answers["facebook"] = [PublishStatus.BLOCKED]
    answers["instagram"] = [PublishStatus.BLOCKED]
    assert daily.run(None, path, now=paris(2026, 11, 5, 7, 20)) == 1       # alert
    assert daily.run(None, path, now=paris(2026, 11, 5, 8, 20)) == 0       # no new upload
    assert len(calls["publish"]) == 1
    assert State.load(path).queue("reading")["done"] == []                 # still first


# ---- the record written at once, another try in the same run ------------------------------

def test_what_is_out_is_recorded_before_anything_else_is_tried(world, monkeypatch):
    """Daily run #8 was cancelled inside its publish step: a run stopped after Facebook has the
    reel must have said so, or the next run posts it again."""
    calls, _, path = world

    def crash(*a, **k):
        assert State.load(path).slot(date(2026, 11, 5), "morning")["results"]["facebook"][
            "status"] == "published"                     # on disk before the YouTube version
        raise KeyboardInterrupt

    monkeypatch.setattr(daily, "youtube_version", crash)
    with pytest.raises(KeyboardInterrupt):
        daily.run(None, path, now=paris(2026, 11, 5, 7, 20))
    assert State.load(path).queue("reading")["done"] == ["juz-amma/114:1-6"]
    assert daily.run(None, path, now=paris(2026, 11, 5, 8, 20)) == 0     # nothing posted twice
    assert len(calls["publish"]) == 1


@pytest.fixture
def uploads(world, monkeypatch):
    """Platforms answering in turn, platforms.retry on: one more try after 180 s."""
    calls, _, path = world
    answers: dict[str, list[PublishResult]] = {}
    waits: list[float] = []

    def publish(cfg, video, platforms, dry_run, checked=None):
        calls["publish"].append((video.stem, tuple(platforms)))
        return [answers[p].pop(0) if answers.get(p)
                else PublishResult(p, PublishStatus.PUBLISHED, remote_id="1") for p in platforms]

    monkeypatch.setattr(daily.publish_mod, "publish_reel", publish)
    monkeypatch.setattr(daily.publish_mod, "retry_settings", lambda cfg: (1, 180.0))
    return calls, answers, path, waits


def test_a_platform_that_did_not_get_the_reel_is_tried_again_in_the_same_run(uploads):
    """Instagram refusing the upload (runs #10, #13), TikTok's HTTP 500 (#28): each was a failed
    run, an alert and a second run for one platform."""
    calls, answers, path, waits = uploads
    answers["instagram"] = [PublishResult("instagram", PublishStatus.FAILED,
                                          error="HTTP 400, type ProcessingFailedError")]
    assert daily.run(None, path, now=paris(2026, 11, 5, 7, 20), sleep=waits.append) == 0
    assert calls["publish"] == [("114:1-6", ("facebook", "instagram")),
                                ("114:1-6", ("instagram",))]
    assert waits == [180.0]
    results = State.load(path).slot(date(2026, 11, 5), "morning")["results"]
    assert {p: r["status"] for p, r in results.items()} == {"facebook": "published",
                                                            "instagram": "published"}


def test_the_other_try_comes_after_the_first_answers_are_recorded(uploads):
    calls, answers, path, _ = uploads
    answers["instagram"] = [PublishResult("instagram", PublishStatus.FAILED, error="x")]

    def cancelled(seconds):                               # the run is stopped while it waits
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        daily.run(None, path, now=paris(2026, 11, 5, 7, 20), sleep=cancelled)
    results = State.load(path).slot(date(2026, 11, 5), "morning")["results"]
    assert results["facebook"]["status"] == "published"
    assert results["instagram"]["status"] == "failed"
    assert daily.run(None, path, now=paris(2026, 11, 5, 8, 20), sleep=cancelled) == 0
    assert calls["publish"][-1] == ("114:1-6", ("instagram",))     # the next run: Instagram only


def test_one_more_try_only_then_the_run_fails_as_before(uploads):
    calls, answers, path, waits = uploads
    answers["instagram"] = [PublishResult("instagram", PublishStatus.FAILED, error="x")] * 2
    assert daily.run(None, path, now=paris(2026, 11, 5, 7, 20), sleep=waits.append) == 1
    assert len(calls["publish"]) == 2 and waits == [180.0]
    assert State.load(path).queue("reading")["done"] == ["juz-amma/114:1-6"]   # Facebook has it


def test_a_failure_while_publishing_is_not_tried_again(uploads):
    """Facebook's «does not exist» right after a publication: the reel may be live."""
    calls, answers, path, waits = uploads
    answers["facebook"] = [PublishResult("facebook", PublishStatus.FAILED, remote_id="draft-1",
                                         error="the published reel 9 may be live anyway")]
    assert daily.run(None, path, now=paris(2026, 11, 5, 7, 20), sleep=waits.append) == 1
    assert len(calls["publish"]) == 1 and waits == []


def test_nothing_is_tried_again_after_a_refusal_by_the_rights_check(uploads):
    calls, answers, path, waits = uploads
    answers["facebook"] = [PublishResult("facebook", PublishStatus.BLOCKED, remote_id="d")]
    answers["instagram"] = [PublishResult("instagram", PublishStatus.FAILED, error="x")]
    assert daily.run(None, path, now=paris(2026, 11, 5, 7, 20), sleep=waits.append) == 1
    assert len(calls["publish"]) == 1 and waits == []


def test_a_dry_run_tries_nothing_again(uploads):
    calls, answers, path, waits = uploads
    answers["instagram"] = [PublishResult("instagram", PublishStatus.FAILED, error="x")]
    daily.run(None, path, now=paris(2026, 11, 5, 7, 20), dry_run=True, sleep=waits.append)
    assert len(calls["publish"]) == 1 and waits == [] and not path.exists()


def test_what_is_worth_another_try():
    from types import SimpleNamespace

    from quran_reels.publish import retry_settings, to_retry

    failed = PublishResult("tiktok", PublishStatus.FAILED, error="upload chunk 1/1: HTTP 500")
    live = PublishResult("facebook", PublishStatus.PUBLISHED, remote_id="1")
    assert to_retry([live, failed]) == ["tiktok"]
    assert to_retry([live, PublishResult("tiktok", PublishStatus.FAILED, remote_id="v1")]) == []
    assert to_retry([PublishResult("facebook", PublishStatus.REMOVED, remote_id="1"), failed]) == []
    assert to_retry([live, PublishResult("tiktok", PublishStatus.DRAFT, remote_id="v1")]) == []
    assert retry_settings(None) == (0, 0.0)
    cfg = SimpleNamespace(project={"platforms": {"retry": {"times": 1, "wait": 90}}})
    assert retry_settings(cfg) == (1, 90.0)
    assert retry_settings(SimpleNamespace(project={"platforms": {}})) == (0, 0.0)


# ---- claims after publication (Meta mutes or blocks a reel) -------------------------------

@pytest.fixture
def two_reciters(monkeypatch):
    from quran_reels import reciters
    monkeypatch.setattr(reciters, "rotation", lambda cfg: ["rifai", "ghamdi"])
    monkeypatch.setattr(reciters, "with_reciter", lambda cfg, name: cfg)
    monkeypatch.setattr(reciters, "choose", lambda cfg, key, recent, claimed=(): (
        "ghamdi" if "rifai" in claimed else "rifai", []))


def test_a_reel_taken_down_after_publication_comes_back_with_another_reciter(world,
                                                                             two_reciters):
    calls, answers, path = world
    answers["facebook"] = [PublishStatus.REMOVED]
    answers["instagram"] = [PublishStatus.REMOVED]
    assert daily.run(None, path, now=paris(2026, 11, 5, 7, 20)) == 1
    state = State.load(path)
    morning = state.slot(date(2026, 11, 5), "morning")
    assert morning["claimed"] and state.queue("reading")["done"] == []
    assert list(state.data["claimed"]) == ["rifai"]
    assert daily.run(None, path, now=paris(2026, 11, 5, 8, 20)) == 0     # not retried
    daily.run(None, path, now=paris(2026, 11, 7, 7, 20))                  # Saturday
    assert [c[0] for c in calls["publish"]] == ["114:1-6", "114:1-6"]
    assert State.load(path).slot(date(2026, 11, 7), "morning")["reciter"] == "ghamdi"


@pytest.fixture
def youtube(world, two_reciters, monkeypatch, tmp_path):
    """daily.run for a reel by Ar-Rifai (the rotation's choice), with a real Config whose
    platforms.youtube is given: youtube(conf) → (cfg, outs, signed, report path)."""
    from types import SimpleNamespace

    from quran_reels.config import Config

    calls, _, _ = world
    outs, signed = [], []

    def render(cfg, key, label_ar="", label_en="", series_tags=(), variants=True):
        outs.append(cfg.out)
        signed.append(variants)
        calls["render"].append((key, label_en))
        return SimpleNamespace(video=cfg.out / "114_001-006.mp4")

    def load_reel(video):
        reel = SimpleNamespace(text=lambda n=None: f"caption {video.parent.name}\n")
        reel.for_platform = lambda platform: reel
        return reel

    import quran_reels.render as render_mod
    monkeypatch.setattr(render_mod, "render_passage", render)
    monkeypatch.setattr(daily.publish_mod, "load_reel", load_reel)

    def make(conf):
        cfg = Config(root=tmp_path, backgrounds=[], gloss_headwords={}, project={
            "content": {"passage": {"max_seconds": 90, "target_seconds": 60},
                        "reciters": {"rifai": {"label": "Nabil Ar-Rifai"},
                                     "ghamdi": {"label": "Saad Al-Ghamdi"}}},
            "platforms": {"youtube": {"mode": "manual", "max_seconds": 180, **conf}}})
        return cfg, outs, signed, tmp_path / "report.json"
    return make


def test_a_reciter_youtube_claims_gets_a_youtube_version(world, youtube, monkeypatch, tmp_path):
    """Meta publishes the rotation's choice; YouTube (by hand) gets the same passage by a
    reciter it does not claim, rendered into out/youtube/ and named in the report."""
    from quran_reels import reciters
    from quran_reels.reciters import Option

    calls, _, path = world
    cfg, outs, signed, report = youtube({"exclude_reciters": ["rifai"]})
    monkeypatch.setattr(reciters, "options", lambda cfg, key, claimed=(): [
        Option("rifai", 50.0), Option("ghamdi", 120.0)])     # over 90 s: fine on YouTube
    assert daily.run(cfg, path, now=paris(2026, 11, 5, 7, 20), report=report) == 0
    assert outs == [tmp_path / "out", tmp_path / "out" / "youtube"]
    assert signed == [True, False]       # no TikTok version of the YouTube one
    assert calls["publish"] == [("114_001-006", ("facebook", "instagram"))]   # Meta: rifai
    item = json.loads(report.read_text(encoding="utf-8"))["items"][0]
    assert item["reciter"] == "rifai"
    assert item["youtube"] == {"reciter": "ghamdi", "video": "youtube/114_001-006.mp4",
                               "caption": "caption youtube\n", "label": "Saad Al-Ghamdi",
                               "instead_of": "Nabil Ar-Rifai"}
    assert State.load(path).slot(date(2026, 11, 5), "morning")["youtube"] == {
        "reciter": "ghamdi", "video": "youtube/114_001-006.mp4"}


def test_youtube_always_gets_its_own_reciter(world, youtube, monkeypatch, tmp_path):
    """platforms.youtube.reciter (owner's choice, 2026-11-11: always Tawfiq As-Sayegh): the
    reel of the day is by the rotation's reciter, YouTube's version by its own, whatever
    Meta claimed of him."""
    from quran_reels import reciters
    from quran_reels.reciters import Option

    calls, _, path = world
    cfg, outs, signed, report = youtube({"reciter": "ghamdi"})
    asked = []
    monkeypatch.setattr(reciters, "passage_seconds",
                        lambda cfg, key: asked.append(key) or Option("ghamdi", 120.0))
    State({"claimed": {"ghamdi": {"reason": "muted on Meta"}}}).save(path)
    assert daily.run(cfg, path, now=paris(2026, 11, 5, 7, 20), report=report) == 0
    assert asked == ["114:1-6"]
    assert outs == [tmp_path / "out", tmp_path / "out" / "youtube"] and signed == [True, False]
    assert calls["publish"] == [("114_001-006", ("facebook", "instagram"))]   # Meta: rifai
    item = json.loads(report.read_text(encoding="utf-8"))["items"][0]
    assert item["reciter"] == "rifai"
    assert item["youtube"] == {"reciter": "ghamdi", "video": "youtube/114_001-006.mp4",
                               "caption": "caption youtube\n", "label": "Saad Al-Ghamdi",
                               "instead_of": "Nabil Ar-Rifai", "always": True}
    assert State.load(path).slot(date(2026, 11, 5), "morning")["youtube"] == {
        "reciter": "ghamdi", "video": "youtube/114_001-006.mp4"}


def test_a_reel_by_youtubes_own_reciter_goes_there_as_it_is(world, youtube, monkeypatch):
    from quran_reels import reciters

    _, _, path = world
    cfg, outs, _, report = youtube({"reciter": "rifai"})
    monkeypatch.setattr(reciters, "passage_seconds", lambda cfg, key: 1 / 0)    # not asked
    assert daily.run(cfg, path, now=paris(2026, 11, 5, 7, 20), report=report) == 0
    assert len(outs) == 1                                 # one render, the same video
    item = json.loads(report.read_text(encoding="utf-8"))["items"][0]
    assert item["reciter"] == "rifai" and "youtube" not in item
    assert "youtube" not in State.load(path).slot(date(2026, 11, 5), "morning")


def test_youtube_gets_nothing_when_its_own_reciter_is_not_ready(world, youtube, monkeypatch,
                                                                capsys):
    """No other reciter in his place (owner's choice): the report and the state say that
    nothing goes to YouTube for this slot, and why; the reel is out all the same."""
    from quran_reels import reciters
    from quran_reels.reciters import Option

    calls, _, path = world
    cfg, outs, _, report = youtube({"reciter": "ghamdi"})
    monkeypatch.setattr(reciters, "passage_seconds",
                        lambda cfg, key: Option("ghamdi", None, "surah 114 not split"))
    assert daily.run(cfg, path, now=paris(2026, 11, 5, 7, 20), report=report) == 0
    assert len(outs) == 1 and calls["publish"] == [("114_001-006", ("facebook", "instagram"))]
    item = json.loads(report.read_text(encoding="utf-8"))["items"][0]
    assert item["youtube"] == {"reciter": None, "error": "sourate 114 pas encore découpée",
                               "always": True, "wanted": "Saad Al-Ghamdi"}
    slot = State.load(path).slot(date(2026, 11, 5), "morning")
    assert slot["youtube"] == {"reciter": None, "error": "sourate 114 pas encore découpée"}
    assert slot["results"]["facebook"]["status"] == "published"
    assert "no YouTube version (ghamdi: surah 114 not split)" in capsys.readouterr().err

    # Too long for a Short: nothing either, rather than another reciter.
    monkeypatch.setattr(reciters, "passage_seconds", lambda cfg, key: Option("ghamdi", 200.0))
    assert daily.youtube_version(cfg, SimpleNamespace(item=SimpleNamespace(key="2:282-282")),
                                 "rifai", set())["error"] == "200 s, plus que 180 s"


def test_later_runs_take_down_a_reel_claimed_after_its_check(world, two_reciters, monkeypatch):
    from types import SimpleNamespace

    from quran_reels.publishers.rights import RightsCheck

    calls, _, path = world
    daily.run(None, path, now=paris(2026, 11, 5, 7, 20))                 # published, clear
    assert State.load(path).queue("reading")["done"] == ["juz-amma/114:1-6"]
    removed = []
    muted = RightsCheck("facebook", "complete", True, [{"owner_copyright_policy": {
        "name": "Recitations Ltd", "actions": [{"action": "MUTE", "geos": ["Iran"]}]}}])

    class Fake:
        def __init__(self, name, answer):
            self.name, self.answer = name, answer

        def rights_after(self, remote_id, timeout=0):
            return self.answer

        def remove(self, remote_id):
            removed.append(self.name)

    clear = RightsCheck("instagram", "complete", False)
    monkeypatch.setattr(daily.publish_mod, "meta_check", lambda cfg, p: (
        None, SimpleNamespace(page_id="p", ig_user_id="i"), None))
    monkeypatch.setattr(daily.publish_mod, "after_timeout", lambda cfg: 300)
    monkeypatch.setattr(daily.publish_mod, "meta_publishers", lambda cfg, g, env, p: {
        "facebook": Fake("facebook", muted), "instagram": Fake("instagram", clear)})
    assert daily.run(None, path, now=paris(2026, 11, 5, 19, 20)) == 1    # evening run
    state = State.load(path)
    morning = state.slot(date(2026, 11, 5), "morning")
    assert removed == ["facebook", "instagram"]                          # both taken down
    assert {r["status"] for r in morning["results"].values()} == {"removed"}
    assert "Iran" in morning["claimed"] and list(state.data["claimed"]) == ["rifai"]
    assert state.queue("reading")["done"] == []                          # back at the head
    assert calls["publish"][-1][0] == "2:255-255"                        # the evening went on


def test_a_reopened_slot_publishes_its_passage_again(world):
    from quran_reels.selector.calendar import reopen

    calls, _, path = world
    daily.run(None, path, now=paris(2026, 11, 5, 7, 20))
    state = State.load(path)
    reopen(state, "2026-11-05/morning", "bad cut at the basmala", claimed=False)
    state.save(path)
    assert State.load(path).queue("reading")["done"] == []
    daily.run(None, path, now=paris(2026, 11, 5, 8, 20))      # same window: published again
    assert [c[0] for c in calls["publish"]] == ["114:1-6", "114:1-6"]
    state = State.load(path)
    assert state.data["removed"][0]["why"] == "bad cut at the basmala"
    with pytest.raises(SystemExit, match="no such slot"):
        reopen(state, "2026-11-06/morning", "x")


# ---- a slot published by hand (publish-test, mode publish) --------------------------------

FACEBOOK = [{"platform": "facebook", "status": "published", "remote_id": "9", "url": "u",
             "error": None}]


def test_a_reopened_slot_published_by_hand_is_not_published_again(world):
    """The republish skill said to «write the new posts into the slot»: the passage stayed
    first in its queue and the next slot published it a second time."""
    from quran_reels.selector.calendar import record_by_hand, reopen

    calls, _, path = world
    daily.run(None, path, now=paris(2026, 11, 5, 7, 20))                 # 114 published
    state = State.load(path)
    reopen(state, "2026-11-05/morning", "bad cut")
    assert next_item(schedule(), SERIES, state, "reading")[1].key == "114:1-6"
    record = record_by_hand(schedule(), SERIES, state, "2026-11-05/morning", "114:1-6",
                            FACEBOOK, reciter="sayegh")
    state.save(path)
    assert record["by_hand"] and record["reciter"] == "sayegh"
    assert record["results"]["facebook"]["id"] == "9"
    assert state.queue("reading")["done"] == ["juz-amma/114:1-6"]
    assert daily.run(None, path, now=paris(2026, 11, 5, 8, 20)) == 0     # same window
    daily.run(None, path, now=paris(2026, 11, 7, 7, 20))                  # Saturday: the next
    assert [c[0] for c in calls["publish"]] == ["114:1-6", "113:1-5"]


def test_the_daily_run_does_not_complete_a_slot_published_by_hand(world):
    """A reciter's first reel goes to Facebook alone: Instagram waits for the owner to see no
    claim, the next run in the window must not post it."""
    from quran_reels.selector.calendar import record_by_hand

    calls, _, path = world
    state = State()
    record_by_hand(schedule(), SERIES, state, "2026-11-05/morning", "114:1-6", FACEBOOK)
    state.save(path)
    assert daily.run(None, path, now=paris(2026, 11, 5, 7, 40)) == 0
    assert calls["publish"] == []
    more = [{"platform": "instagram", "status": "published", "remote_id": "7"}]
    record = record_by_hand(schedule(), SERIES, state, "2026-11-05/morning", "114:1-6", more)
    assert set(record["results"]) == {"facebook", "instagram"}            # added, not replaced


def test_a_by_hand_record_is_checked_before_it_is_written():
    from quran_reels.selector.calendar import record_by_hand

    state = State()
    with pytest.raises(SystemExit, match="not a passage of the queue"):
        record_by_hand(schedule(), SERIES, state, "2026-11-05/morning", "2:1-5", FACEBOOK)
    with pytest.raises(SystemExit, match="no slot «noon»"):
        record_by_hand(schedule(), SERIES, state, "2026-11-05/noon", "114:1-6", FACEBOOK)
    with pytest.raises(SystemExit, match="not a slot"):
        record_by_hand(schedule(), SERIES, state, "yesterday", "114:1-6", FACEBOOK)
    assert state.data["slots"] == {}
    failed = [{"platform": "facebook", "status": "failed", "error": "x"}]
    record_by_hand(schedule(), SERIES, state, "2026-11-05/morning", "114:1-6", failed)
    assert state.queue("reading")["done"] == []           # nobody has it: still first
    with pytest.raises(SystemExit, match="already holds 114:1-6"):
        record_by_hand(schedule(), SERIES, state, "2026-11-05/morning", "113:1-5", FACEBOOK)
    # the evening queue hands over to the reading queue when its series are done
    done = State({"queues": {"themes": {"round": 1, "done": [
        "kursi/2:255-255", "dua/2:186-186", "dua/2:201-201", "dua/3:8-9"]}}})
    record = record_by_hand(schedule(), SERIES, done, "2026-11-05/evening", "114:1-6", FACEBOOK)
    assert record["queue"] == "reading" and done.queue("reading")["done"] == ["juz-amma/114:1-6"]


def test_state_record_reads_publish_json(tmp_path, monkeypatch, capsys):
    from quran_reels import cli
    from quran_reels.selector import calendar

    monkeypatch.setattr(calendar, "load_series", lambda cfg: SERIES)
    monkeypatch.setattr(calendar, "load_schedule", lambda cfg, series: schedule())
    posted = tmp_path / "publish.json"
    state = tmp_path / "published.json"
    posted.write_text(json.dumps({"passage": "114:1-6", "dry_run": True, "results": FACEBOOK}),
                      encoding="utf-8")
    argv = ["state", "record", "2026-11-05/morning", "--publish", str(posted), "--reciter",
            "sayegh", "--state", str(state)]
    with pytest.raises(SystemExit, match="dry run"):
        cli.main(argv)
    posted.write_text(json.dumps({"passage": "114:1-6", "dry_run": False, "results": FACEBOOK}),
                      encoding="utf-8")
    assert cli.main(argv) == 0
    assert "queue reading moves on" in capsys.readouterr().out
    assert State.load(state).slot(date(2026, 11, 5), "morning")["reciter"] == "sayegh"


# ---- a slot no run ever took --------------------------------------------------------------

def test_a_slot_nobody_tried_is_seen_by_a_later_run(world):
    """2026-11-09 evening: GitHub started no job for two dispatches. Had the third not come,
    nothing would have told the owner: the alert is written by the run."""
    from quran_reels.selector.calendar import missed_slots

    _, _, path = world
    daily.run(None, path, now=paris(2026, 11, 5, 7, 20))                 # Thursday morning
    state = State.load(path)
    assert missed_slots(schedule(), state, paris(2026, 11, 5, 22, 0)) == []   # window open
    assert missed_slots(schedule(), state, paris(2026, 11, 5, 22, 31)) == []  # the first day
    daily.run(None, path, now=paris(2026, 11, 6, 7, 20))                 # Friday morning
    state = State.load(path)
    assert missed_slots(schedule(), state, paris(2026, 11, 6, 22, 29)) == []
    late = paris(2026, 11, 7, 12, 0)             # a run on Saturday noon, GitHub's late cron
    assert missed_slots(schedule(), state, late) == ["2026-11-06/evening", "2026-11-07/morning"]
    assert missed_slots(schedule(), State(), late) == []                 # nothing published yet


def test_a_missed_slot_is_told_once_and_not_a_reopened_one(world, monkeypatch, tmp_path):
    from quran_reels.selector.calendar import missed_slots, reopen

    _, _, path = world
    daily.run(None, path, now=paris(2026, 11, 5, 7, 20))
    daily.run(None, path, now=paris(2026, 11, 6, 7, 20))
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    noon = paris(2026, 11, 7, 12, 0)
    assert daily.run(None, path, now=noon, check=True, watch=True) == 0
    assert "missed=2026-11-06/evening,2026-11-07/morning" in out.read_text()
    assert set(State.load(path).data["missed"]) == {"2026-11-06/evening", "2026-11-07/morning"}
    out.write_text("")
    daily.run(None, path, now=noon, check=True, watch=True)              # the next run
    assert "missed=\n" in out.read_text()
    state = State.load(path)
    reopen(state, "2026-11-06/morning", "bad cut")
    assert missed_slots(schedule(), state, noon) == []
    assert daily.run(None, path, now=paris(2026, 11, 8, 12, 0), check=True) == 0   # simulated
    assert "2026-11-08/morning" not in State.load(path).data["missed"]            # time: no

