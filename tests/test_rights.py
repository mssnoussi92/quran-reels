"""Meta's copyright check: polling, and nothing published unless every platform is clear."""

from types import SimpleNamespace

import pytest

from quran_reels import publish as publish_mod
from quran_reels.models import Passage, PublishResult, PublishStatus, Reel
from quran_reels.publishers import rights
from quran_reels.publishers.meta import GraphError


class Answers:
    """A Graph whose GET returns the given bodies (or raises them) in turn."""

    def __init__(self, *bodies):
        self.bodies = list(bodies)

    def get(self, object_id, fields):
        body = self.bodies.pop(0) if len(self.bodies) > 1 else self.bodies[0]
        if isinstance(body, Exception):
            raise body
        return body


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


def run(graph, platform="instagram", timeout=60):
    clock = Clock()
    return rights.check(graph, platform, "1", timeout=timeout, interval=10, clock=clock,
                        sleep=clock.sleep)


def test_both_answer_shapes():
    fb = {"copyright_check_information": {"status": {"status": "complete",
                                                     "matches_found": False}}}
    ig = {"copyright_check_status": {"status": "completed", "matches_found": False}}
    assert run(Answers(fb), "facebook").clear and run(Answers(ig), "instagram").clear


def test_no_answer_in_time_blocks():
    c = run(Answers({"copyright_check_status": {"status": "in_progress"}}), timeout=60)
    assert (c.status, c.clear) == ("timeout", False) and c.seconds > 60
    assert "non terminée" in c.describe()


def test_complete_without_matches_found_is_not_clear():
    c = run(Answers({"copyright_check_status": {"status": "complete"}}), timeout=30)
    assert not c.clear


def test_transient_errors_are_retried_then_give_up():
    flaky = GraphError("GET 1: Service unavailable (HTTP 503)", transient=True)
    clear = {"copyright_check_status": {"status": "complete", "matches_found": False}}
    assert run(Answers(flaky, flaky, clear)).clear
    c = run(Answers(flaky))
    assert c.status == "unavailable" and "503" in c.describe()


# ---- publish_reel: every Meta platform must be clear -----------------------------------

class FakeMeta:
    calls: list

    def __init__(self, name, check, log, after=None, removable=True):
        self.name, self.check, self.log = name, check, log
        self.after, self.removable = after or CLEAR_AFTER, removable

    def rights_after(self, remote_id, timeout=0):
        self.log.append(("after", self.name))
        return self.after

    def remove(self, remote_id):
        if not self.removable:
            raise GraphError("(#10) Application does not have permission for this action")
        self.log.append(("remove", self.name))

    def prepare(self, reel):
        self.log.append(("prepare", self.name))
        return f"{self.name}-id"

    def rights(self, object_id):
        return self.check

    def commit(self, object_id, reel):
        self.log.append(("commit", self.name))
        return PublishResult(self.name, PublishStatus.PUBLISHED, remote_id=object_id)


CLEAR = rights.RightsCheck("x", "complete", False)
CLEAR_AFTER = rights.RightsCheck("x", "complete", False)
GEOS = ["Iran", "Syria", "China", "Cuba", "Azerbaijan", "Belarus", "Ethiopia", "Gabon"]
MUTED = rights.RightsCheck("facebook", "complete", True, [{
    "content_title": "Ayat al-Kursi", "owner_copyright_policy": {
        "name": "Recitations Ltd", "actions": [{"action": "MUTE", "geos": GEOS}]},
    "matched_segments": [{"segment_type": "AUDIO"}]}])
TRACKED = rights.RightsCheck("facebook", "complete", True, [{
    "owner_copyright_policy": {"name": "Recitations Ltd",
                               "actions": [{"action": "TRACK", "geos": GEOS}]}}])
MATCH = rights.RightsCheck("x", "complete", True, [{"author": "Rights Holder Ltd",
                                                    "content_title": "Surah Ad-Duha"}])


@pytest.fixture
def world(monkeypatch, tmp_path):
    log, checks = [], {"facebook": CLEAR, "instagram": CLEAR}
    after = {"facebook": CLEAR_AFTER, "instagram": CLEAR_AFTER, "ig_removable": True}
    video = tmp_path / "093_001-011.mp4"
    (tmp_path / "093_001-011").mkdir()
    reel = Reel(Passage(93, 1, 11, "الضحى", "Ad-Duhaa"), video, "caption")
    token = SimpleNamespace(summary=lambda: "token ok")
    env = SimpleNamespace(page_id="p", ig_user_id="i")
    monkeypatch.setattr(publish_mod, "load_reel", lambda v: reel)
    monkeypatch.setattr(publish_mod, "FacebookPublisher",
                        lambda *a, **k: FakeMeta("facebook", checks["facebook"], log,
                                                 after["facebook"]))
    monkeypatch.setattr(publish_mod, "InstagramPublisher",
                        lambda *a, **k: FakeMeta("instagram", checks["instagram"], log,
                                                 after["instagram"], after["ig_removable"]))

    class TikTok:
        def publish(self, reel, dry_run=False):
            log.append(("publish", "tiktok"))
            return PublishResult("tiktok", PublishStatus.DRAFT)

    monkeypatch.setattr(publish_mod, "tiktok_publisher", lambda: TikTok())
    cfg = SimpleNamespace(project={"platforms": {"meta": {"rights_after_timeout": 1}}})

    def go(dry_run=False):
        return {r.platform: r for r in publish_mod.publish_reel(
            cfg, video, ["facebook", "instagram", "tiktok"], dry_run, (None, env, token))}
    checks["after"] = after                    # what Meta answers once the reels are live
    return go, log, checks


def test_clear_everywhere_publishes_everywhere(world):
    go, log, _ = world
    results = go()
    assert [r.status for r in results.values()] == [PublishStatus.PUBLISHED,
                                                     PublishStatus.PUBLISHED, PublishStatus.DRAFT]
    assert log == [("prepare", "facebook"), ("prepare", "instagram"), ("commit", "facebook"),
                   ("commit", "instagram"), ("publish", "tiktok"),
                   ("after", "facebook"), ("after", "instagram")]     # read again once live


# ---- after publication: the check before it missed Alafasy and Ar-Rifai ---------------------

def test_a_reel_muted_after_publication_is_taken_down_everywhere(world):
    go, log, checks = world
    checks["after"]["facebook"] = MUTED            # Ar-Rifai, 2:255, 2026-11-05: 24 territories
    results = go()
    assert results["facebook"].status == results["instagram"].status == PublishStatus.REMOVED
    assert ("remove", "facebook") in log and ("remove", "instagram") in log
    assert "MUTE dans 8 territoires (Iran, Syria" in results["facebook"].error
    assert "Recitations Ltd" in results["instagram"].error
    assert results["tiktok"].status == PublishStatus.DRAFT       # in the inbox: not to be posted
    assert "ne publie pas ce brouillon" in results["tiktok"].error
    assert results["facebook"].rights_after["matches_found"]


def test_a_claim_that_only_tracks_keeps_the_reel(world):
    go, log, checks = world
    checks["after"]["facebook"] = TRACKED
    results = go()
    assert results["facebook"].status == PublishStatus.PUBLISHED
    assert not [c for c in log if c[0] == "remove"]


def test_an_instagram_reel_that_cannot_be_removed_is_flagged_for_the_owner(world):
    go, _, checks = world
    checks["after"]["facebook"], checks["after"]["ig_removable"] = MUTED, False
    results = go()
    assert results["facebook"].status == PublishStatus.REMOVED
    assert results["instagram"].status == PublishStatus.PUBLISHED
    assert results["instagram"].error.startswith("À RETIRER À LA MAIN")


def test_restricted_reads_meta_actions():
    assert MUTED.restricted and not TRACKED.restricted and not CLEAR_AFTER.restricted
    unknown = rights.RightsCheck("instagram", "completed", True, [{"author": "X"}])
    assert unknown.restricted                  # a match without any action given: taken down


def test_one_match_stops_every_platform_and_names_the_holder(world):
    go, log, checks = world
    checks["instagram"] = MATCH
    results = go()
    assert {r.status for r in results.values()} == {PublishStatus.BLOCKED}
    assert not [c for c in log if c[0] in ("commit", "publish")]
    assert "Rights Holder Ltd" in results["facebook"].error
    assert "93:1-11 non publié" in results["facebook"].error
    assert results["facebook"].rights["clear"] and not results["instagram"].rights["clear"]


def test_dry_run_reports_each_check(world):
    go, log, checks = world
    checks["facebook"] = MATCH
    results = go(dry_run=True)
    assert results["facebook"].status is PublishStatus.DRAFT
    assert results["facebook"].rights["summary"].startswith("contenu protégé reconnu")
    assert results["instagram"].rights["summary"] == "aucune correspondance"
    assert results["tiktok"].status is PublishStatus.BLOCKED       # no TikTok draft either
    assert not [c for c in log if c[0] in ("commit", "publish")]


def test_the_check_after_publication_keeps_reading_until_a_late_claim():
    # Al-Ghamdi, 2026-11-05: complete without a match at first, claimed by UMG minutes later
    log, t = [], [0.0]

    answers = [CLEAR_AFTER, CLEAR_AFTER, MUTED]

    class Seq(FakeMeta):
        def rights_after(self, remote_id, timeout=0):
            return answers.pop(0)

    fb = Seq("facebook", CLEAR, log)
    results = {"facebook": PublishResult("facebook", PublishStatus.PUBLISHED, remote_id="v1")}

    def sleep(s):
        t[0] += s

    reason = publish_mod.after_check({"facebook": fb}, results, 300, 30,
                                     clock=lambda: t[0], sleep=sleep)
    assert t[0] == 60 and "MUTE" in reason
    assert results["facebook"].status == PublishStatus.REMOVED and ("remove", "facebook") in log


def test_the_check_after_publication_stops_at_its_timeout():
    t = [0.0]
    fb = FakeMeta("facebook", CLEAR, [])
    results = {"facebook": PublishResult("facebook", PublishStatus.PUBLISHED, remote_id="v1")}
    assert publish_mod.after_check({"facebook": fb}, results, 300, 30, clock=lambda: t[0],
                                   sleep=lambda s: t.__setitem__(0, t[0] + s)) is None
    assert t[0] == 300 and results["facebook"].status == PublishStatus.PUBLISHED
