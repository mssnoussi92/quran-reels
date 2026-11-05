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

    def __init__(self, name, check, log):
        self.name, self.check, self.log = name, check, log

    def prepare(self, reel):
        self.log.append(("prepare", self.name))
        return f"{self.name}-id"

    def rights(self, object_id):
        return self.check

    def commit(self, object_id, reel):
        self.log.append(("commit", self.name))
        return PublishResult(self.name, PublishStatus.PUBLISHED, remote_id=object_id)


CLEAR = rights.RightsCheck("x", "complete", False)
MATCH = rights.RightsCheck("x", "complete", True, [{"author": "Rights Holder Ltd",
                                                    "content_title": "Surah Ad-Duha"}])


@pytest.fixture
def world(monkeypatch, tmp_path):
    log, checks = [], {"facebook": CLEAR, "instagram": CLEAR}
    video = tmp_path / "093_001-011.mp4"
    (tmp_path / "093_001-011").mkdir()
    reel = Reel(Passage(93, 1, 11, "الضحى", "Ad-Duhaa"), video, "caption")
    token = SimpleNamespace(summary=lambda: "token ok")
    env = SimpleNamespace(page_id="p", ig_user_id="i")
    monkeypatch.setattr(publish_mod, "load_reel", lambda v: reel)
    monkeypatch.setattr(publish_mod, "FacebookPublisher",
                        lambda *a, **k: FakeMeta("facebook", checks["facebook"], log))
    monkeypatch.setattr(publish_mod, "InstagramPublisher",
                        lambda *a, **k: FakeMeta("instagram", checks["instagram"], log))

    class TikTok:
        def publish(self, reel, dry_run=False):
            log.append(("publish", "tiktok"))
            return PublishResult("tiktok", PublishStatus.DRAFT)

    monkeypatch.setattr(publish_mod, "tiktok_publisher", lambda: TikTok())
    cfg = SimpleNamespace(project={})

    def go(dry_run=False):
        return {r.platform: r for r in publish_mod.publish_reel(
            cfg, video, ["facebook", "instagram", "tiktok"], dry_run, (None, env, token))}
    return go, log, checks


def test_clear_everywhere_publishes_everywhere(world):
    go, log, _ = world
    results = go()
    assert [r.status for r in results.values()] == [PublishStatus.PUBLISHED,
                                                     PublishStatus.PUBLISHED, PublishStatus.DRAFT]
    assert log == [("prepare", "facebook"), ("prepare", "instagram"), ("commit", "facebook"),
                   ("commit", "instagram"), ("publish", "tiktok")]


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
