"""Calendar: slots, queues, Fridays, state and retries, without network or rendering."""

from datetime import UTC, date, datetime, time
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
