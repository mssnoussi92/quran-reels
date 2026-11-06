"""Facebook and Instagram publishers against a fake Graph API (no network, no secrets)."""

from datetime import UTC, datetime, timedelta

import pytest
import requests

from quran_reels.models import Passage, PublishStatus, Reel
from quran_reels.publishers.facebook import FacebookPublisher
from quran_reels.publishers.instagram import InstagramPublisher
from quran_reels.publishers.meta import Graph, GraphError, TokenProblem, check_token

TOKEN = "EAAB-secret-page-token"
PAGE, IG = "1494879297031390", "17841475111287268"
NOW = datetime(2026, 11, 4, tzinfo=UTC)
ALL_SCOPES = ["pages_show_list", "pages_read_engagement", "pages_manage_posts",
              "instagram_basic", "instagram_content_publish", "instagram_manage_contents"]


class Resp:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status

    def json(self):
        return self.body


class FakeSession:
    """Routes (method, path suffix) to canned answers and records every call."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []
        self.headers = {}

    def request(self, method, url, timeout=None, params=None, data=None, headers=None):
        fields = dict(params or {}) | (dict(data) if isinstance(data, dict) else {})
        self.calls.append((method, url, fields, headers or {}))
        for (m, suffix), answer in self.routes.items():
            if m == method and url.split("?")[0].endswith(suffix):
                body = answer(fields) if callable(answer) else answer
                return body if isinstance(body, Resp) else Resp(body)
        raise AssertionError(f"unexpected {method} {url}")

    def find(self, method, suffix):
        return [c for c in self.calls if c[0] == method and c[1].endswith(suffix)]


def debug_token(days_left=90, scopes=ALL_SCOPES, kind="PAGE", valid=True):
    return {"data": {"is_valid": valid, "type": kind, "profile_id": PAGE, "scopes": scopes,
                     "expires_at": 0,
                     "data_access_expires_at": int((NOW + timedelta(days=days_left)).timestamp())}}


def graph(routes):
    return Graph(TOKEN, "v24.0", session=FakeSession(routes))


@pytest.fixture
def reel(tmp_path):
    video = tmp_path / "093_001-011.mp4"
    video.write_bytes(b"\0" * 1234)
    return Reel(passage=Passage(93, 1, 11, "الضحى", "Ad-Duhaa"), video=video,
                caption="Surah Ad-Duhaa (93:1-11)", cover_ms=3700)


def token_routes(**kw):
    return {("GET", "/debug_token"): debug_token(**kw),
            ("GET", f"/{PAGE}"): {"name": "Quran Words Daily",
                                  "instagram_business_account": {"id": IG}}}


# ---- token check ---------------------------------------------------------------------

def test_token_ok_reports_data_access_expiry():
    g = graph(token_routes(days_left=90))
    report = check_token(g, PAGE, IG, ["facebook", "instagram"], 14, now=NOW)
    assert report.data_access_expires_at.date().isoformat() == "2027-02-02"
    assert round(report.days_left) == 90 and not report.warnings
    # the token goes in a header, never in the URL or the form
    _, url, _, headers = g.session.calls[0]
    assert TOKEN not in url and headers["Authorization"] == f"Bearer {TOKEN}"


def test_token_without_instagram_manage_contents_warns():
    # publishing works without it, but a claimed Instagram reel cannot be taken down by the API
    scopes = [x for x in ALL_SCOPES if x != "instagram_manage_contents"]
    report = check_token(graph(token_routes(scopes=scopes)), PAGE, IG, ["facebook", "instagram"],
                         14, now=NOW)
    assert any("instagram_manage_contents" in w for w in report.warnings)


def test_token_fails_14_days_before_data_access_expires():
    with pytest.raises(TokenProblem, match="expire le 2026-11-17") as e:
        check_token(graph(token_routes(days_left=13)), PAGE, IG, ["facebook"], 14, now=NOW)
    assert "META_PAGE_TOKEN" in str(e.value)          # says how to renew


def test_token_warns_under_30_days():
    report = check_token(graph(token_routes(days_left=20)), PAGE, IG, ["facebook"], 14, now=NOW)
    assert report.warnings


@pytest.mark.parametrize("kw, message", [
    ({"scopes": ["pages_show_list"]}, "Permissions manquantes"),
    ({"kind": "USER"}, "pas un jeton de Page"),
    ({"valid": False}, "pas valide"),
])
def test_token_problems(kw, message):
    with pytest.raises(TokenProblem, match=message):
        check_token(graph(token_routes(**kw)), PAGE, IG, ["facebook", "instagram"], 14, now=NOW)


def test_instagram_must_be_linked_to_the_page():
    routes = token_routes() | {("GET", f"/{PAGE}"): {"name": "Quran Words Daily"}}
    with pytest.raises(TokenProblem, match="Comptes liés"):
        check_token(graph(routes), PAGE, IG, ["instagram"], 14, now=NOW)


def test_errors_never_contain_the_token():
    class Broken(FakeSession):
        def request(self, *a, **kw):
            raise requests.ConnectionError(f"https://graph.facebook.com/x?access_token={TOKEN}")

    with pytest.raises(GraphError) as e:
        Graph(TOKEN, "v24.0", session=Broken({})).get("debug_token", input_token=TOKEN)
    assert TOKEN not in str(e.value)
    g = graph({("GET", "/me"): Resp({"error": {"message": "Invalid OAuth", "code": 190}}, 400)})
    with pytest.raises(GraphError, match=r"Invalid OAuth \(HTTP 400, code 190\)") as e:
        g.get("me")
    assert TOKEN not in str(e.value)


# ---- Facebook ------------------------------------------------------------------------

CLEAR = {"status": "complete", "matches_found": False}
MATCH = {"status": "complete", "matches_found": True}
CLAIM = [{"author": "Rights Holder Ltd", "content_title": "Surah Ad-Duha",
          "owner_copyright_policy": {"name": "Block worldwide"},
          "matched_segments": [{"start_time_in_seconds": 0, "segment_type": "AUDIO"}]}]


def facebook_routes(publish_status="complete", rights=CLEAR, matches=()):
    def video(f):
        if f.get("fields") == "permalink_url":
            return {"permalink_url": "/reel/111/"}
        if f.get("fields") == "copyright_check_information":
            r = rights() if callable(rights) else rights
            return {"copyright_check_information": {"status": r,
                                                    "copyright_matches": list(matches)}}
        return {"status": {"video_status": "ready", "processing_phase": {"status": "complete"},
                           "publishing_phase": {"status": publish_status}}}
    ids = iter(["111", "222"])          # the draft, then the published upload

    def start(f):
        if f["upload_phase"] != "start":
            return {"success": True}
        vid = next(ids)
        return {"video_id": vid, "upload_url": f"https://rupload.facebook.com/video-upload/v24.0/{vid}"}
    return {
        ("POST", f"/{PAGE}/video_reels"): start,
        ("POST", "/video-upload/v24.0/111"): {"success": True},
        ("POST", "/video-upload/v24.0/222"): {"success": True},
        ("GET", "/111"): video,
        ("GET", "/222"): video,
        ("DELETE", "/111"): {"success": True},
    }


def test_facebook_dry_run_leaves_a_draft(reel):
    g = graph(facebook_routes(publish_status="not_started"))
    r = FacebookPublisher(g, PAGE, poll_interval=0).publish(reel, dry_run=True)
    assert (r.status, r.remote_id) == (PublishStatus.DRAFT, "111")
    [finish] = [c for c in g.session.find("POST", f"/{PAGE}/video_reels")
                if c[2]["upload_phase"] == "finish"]
    assert finish[2]["video_state"] == "DRAFT"
    assert finish[2]["description"] == reel.text()
    [upload] = g.session.find("POST", "/video-upload/v24.0/111")
    assert upload[3]["file_size"] == "1234" and upload[3]["offset"] == "0"
    assert upload[3]["Authorization"] == f"OAuth {TOKEN}"


def test_facebook_publish(reel):
    g = graph(facebook_routes())
    r = FacebookPublisher(g, PAGE, poll_interval=0).publish(reel)
    assert (r.status, r.url) == (PublishStatus.PUBLISHED, "https://www.facebook.com/reel/111/")
    states = [c[2].get("video_state") for c in g.session.find("POST", f"/{PAGE}/video_reels")]
    # a draft first; once checked, uploaded again straight to PUBLISHED (a draft cannot be
    # published through the API, run #18), and the draft deleted
    assert states == [None, "DRAFT", None, "PUBLISHED"]
    assert r.remote_id == "222" and g.session.find("DELETE", "/111")
    assert r.rights["clear"] and r.rights["summary"] == "aucune correspondance"


def test_facebook_published_reel_that_answers_does_not_exist_at_first(reel):
    # Budair's 2:255, publish-test, 2026-11-05: live, yet «does not exist» right after finish
    routes = facebook_routes()
    answers = iter([Resp({"error": {"message": "Unsupported get request. Object with ID '222' "
                                    "does not exist", "code": 100, "error_subcode": 33}}, 400)])
    normal = routes[("GET", "/222")]
    routes[("GET", "/222")] = lambda f: next(answers, None) or normal(f)
    r = FacebookPublisher(graph(routes), PAGE, poll_interval=0).publish(reel)
    assert (r.status, r.remote_id) == (PublishStatus.PUBLISHED, "222")


def test_facebook_match_keeps_the_draft_and_names_the_rights_holder(reel):
    g = graph(facebook_routes(rights=MATCH, matches=CLAIM))
    r = FacebookPublisher(g, PAGE, poll_interval=0).publish(reel)
    assert r.status is PublishStatus.BLOCKED and r.remote_id == "111"
    assert "Rights Holder Ltd" in r.error and "Surah Ad-Duha" in r.error and "audio" in r.error
    states = [c[2].get("video_state") for c in g.session.find("POST", f"/{PAGE}/video_reels")]
    assert "PUBLISHED" not in states


def test_facebook_waits_for_the_check_to_complete(reel):
    answers = iter([{"status": "in_progress"}, {"status": "in_progress"}, CLEAR])
    g = graph(facebook_routes(rights=lambda: next(answers)))
    r = FacebookPublisher(g, PAGE, poll_interval=0).publish(reel)
    assert r.status is PublishStatus.PUBLISHED
    checks = [c for c in g.session.find("GET", "/111")
              if c[2].get("fields") == "copyright_check_information"]
    assert len(checks) == 3


def test_facebook_unknown_field_blocks(reel):
    routes = facebook_routes()
    status = routes[("GET", "/111")]
    routes[("GET", "/111")] = lambda f: (
        Resp({"error": {"message": "(#100) Tried accessing nonexisting field "
                                   "(copyright_check_information)", "code": 100}}, 400)
        if f.get("fields") == "copyright_check_information" else status(f))
    r = FacebookPublisher(graph(routes), PAGE, poll_interval=0).publish(reel)
    assert r.status is PublishStatus.BLOCKED and "indisponible" in r.error


def test_facebook_processing_error_is_reported(reel):
    routes = facebook_routes() | {("GET", "/111"): {"status": {
        "processing_phase": {"status": "error", "errors": [{"message": "Video too short"}]}}}}
    r = FacebookPublisher(graph(routes), PAGE, poll_interval=0).publish(reel)
    assert r.status is PublishStatus.FAILED and "Video too short" in r.error


# ---- Instagram -----------------------------------------------------------------------

def status_only(answer):
    """A container route for processing states; the copyright check answers clear."""
    def route(f):
        if f.get("fields") == "copyright_check_status":
            return {"copyright_check_status": CLEAR}
        return answer(f) if callable(answer) else answer
    return route


def instagram_routes(states=("IN_PROGRESS", "FINISHED"), rights=CLEAR):
    seq = iter(states)

    def container(f):
        if f.get("fields") == "copyright_check_status":
            return {"copyright_check_status": rights() if callable(rights) else rights,
                    "id": "222"}
        return {"status_code": next(seq)}
    return {
        ("POST", f"/{IG}/media"): {"id": "222",
                                   "uri": "https://rupload.facebook.com/ig-api-upload/v24.0/222"},
        ("POST", "/ig-api-upload/v24.0/222"): {"success": True},
        ("GET", "/222"): container,
        ("GET", f"/{IG}/content_publishing_limit"): {"data": [{"quota_usage": 3,
                                                               "config": {"quota_total": 50}}]},
        ("POST", f"/{IG}/media_publish"): {"id": "333"},
        ("GET", "/333"): {"permalink": "https://www.instagram.com/reel/abc/"},
    }


def test_instagram_dry_run_stops_before_media_publish(reel):
    g = graph(instagram_routes())
    r = InstagramPublisher(g, IG, poll_interval=0).publish(reel, dry_run=True)
    assert (r.status, r.remote_id) == (PublishStatus.READY, "222")
    assert not g.session.find("POST", f"/{IG}/media_publish")
    [create] = g.session.find("POST", f"/{IG}/media")
    assert create[2] == {"media_type": "REELS", "upload_type": "resumable",
                              "caption": reel.text(5), "share_to_feed": "true",
                              "thumb_offset": "3700"}


def test_instagram_publish(reel):
    g = graph(instagram_routes())
    r = InstagramPublisher(g, IG, poll_interval=0).publish(reel)
    assert (r.status, r.remote_id, r.url) == (PublishStatus.PUBLISHED, "333",
                                              "https://www.instagram.com/reel/abc/")
    assert g.session.find("POST", f"/{IG}/media_publish")[0][2] == {"creation_id": "222"}


def test_instagram_match_is_never_published(reel):
    g = graph(instagram_routes(rights=MATCH))
    r = InstagramPublisher(g, IG, poll_interval=0).publish(reel)
    assert r.status is PublishStatus.BLOCKED and "après publication" in r.error
    assert not g.session.find("POST", f"/{IG}/media_publish")


def test_instagram_check_that_errors_blocks(reel):
    g = graph(instagram_routes(rights={"status": "error"}))
    r = InstagramPublisher(g, IG, poll_interval=0).publish(reel)
    assert r.status is PublishStatus.BLOCKED and not g.session.find("POST", f"/{IG}/media_publish")


def test_instagram_container_error(reel):
    r = InstagramPublisher(graph(instagram_routes(("ERROR",))), IG, poll_interval=0).publish(reel)
    assert r.status is PublishStatus.FAILED and "ERROR" in r.error


def test_instagram_caption_limit(reel):
    reel.caption = "x" * 2201
    r = InstagramPublisher(graph({}), IG).publish(reel)
    assert r.status is PublishStatus.FAILED and "2200" in r.error


def test_status_polling_survives_a_transient_error(reel):
    answers = iter([Resp({"error": {"message": "Service unavailable"}}, 503),
                    {"status_code": "FINISHED"}])
    routes = instagram_routes() | {("GET", "/222"): status_only(lambda f: next(answers))}
    r = InstagramPublisher(graph(routes), IG, poll_interval=0).publish(reel, dry_run=True)
    assert r.status is PublishStatus.READY


def test_rupload_errors_are_explained(reel):
    routes = instagram_routes() | {("POST", "/ig-api-upload/v24.0/222"): Resp(
        {"debug_info": {"retriable": False, "type": "ProcessingFailedError",
                        "message": "Request processing failed"}}, 400),
        ("GET", "/222"): {"status_code": "ERROR", "status": "Error"}}
    r = InstagramPublisher(graph(routes), IG, poll_interval=0).publish(reel, dry_run=True)
    assert r.status is PublishStatus.FAILED
    assert "Request processing failed (HTTP 400, type ProcessingFailedError)" in r.error


def test_non_json_error_body_never_shows_the_token():
    class Text(Resp):
        text = f"<html>bad request for {TOKEN}</html>"

        def json(self):
            raise ValueError

    g = graph({("GET", "/me"): Text(None, 400)})
    with pytest.raises(GraphError) as e:
        g.get("me")
    assert "bad request for ***" in str(e.value) and TOKEN not in str(e.value)


def test_failed_upload_reports_the_container_status(reel):
    routes = instagram_routes() | {
        ("POST", "/ig-api-upload/v24.0/222"): Resp(
            {"debug_info": {"type": "ProcessingFailedError", "message": "Request processing failed"}},
            400),
        ("GET", "/222"): {"status_code": "ERROR", "status": "Error: 2207026"},
    }
    r = InstagramPublisher(graph(routes), IG, poll_interval=0).publish(reel, dry_run=True)
    assert r.status is PublishStatus.FAILED and "container: ERROR Error: 2207026" in r.error


def test_upload_error_while_instagram_is_processing_is_not_a_failure(reel):
    # Real run #6: rupload answered 400 while the container was IN_PROGRESS, then FINISHED.
    states = iter(["IN_PROGRESS", "IN_PROGRESS", "FINISHED"])
    routes = instagram_routes() | {
        ("POST", "/ig-api-upload/v24.0/222"): Resp(
            {"debug_info": {"type": "ProcessingFailedError", "message": "Request processing failed"}},
            400),
        ("GET", "/222"): status_only(lambda f: {
            "status_code": next(states),
            "status": "In Progress: Media is still being processed."}),
    }
    r = InstagramPublisher(graph(routes), IG, poll_interval=0).publish(reel, dry_run=True)
    assert (r.status, r.remote_id) == (PublishStatus.READY, "222")


def failing_upload():
    return Resp({"debug_info": {"type": "ProcessingFailedError",
                                "message": "Request processing failed"}}, 400)


def stuck_routes(stuck: int):
    """Containers 222, 223, 224: the first `stuck` ones never leave IN_PROGRESS."""
    ids = iter(["222", "223", "224"])
    routes = instagram_routes() | {
        ("POST", f"/{IG}/media"): lambda f: {
            "id": (c := next(ids)), "uri": f"https://rupload.facebook.com/ig-api-upload/v24.0/{c}"}}
    for n, cid in enumerate(["222", "223", "224"]):
        if n < stuck:
            routes[("POST", f"/ig-api-upload/v24.0/{cid}")] = failing_upload()
            routes[("GET", f"/{cid}")] = status_only({
                "status_code": "IN_PROGRESS",
                "status": "In Progress: Media is still being processed."})
        else:
            routes[("POST", f"/ig-api-upload/v24.0/{cid}")] = {"success": True}
            routes[("GET", f"/{cid}")] = status_only({"status_code": "FINISHED"})
    return routes


def test_container_stuck_after_an_upload_error_is_replaced(reel):
    # Real run #9: 400 ProcessingFailedError, then IN_PROGRESS for more than 15 minutes.
    g = graph(stuck_routes(stuck=1))
    r = InstagramPublisher(g, IG, poll_interval=0, stuck_after=0).publish(reel)
    assert (r.status, r.remote_id) == (PublishStatus.PUBLISHED, "333")
    assert len(g.session.find("POST", f"/{IG}/media")) == 2
    assert g.session.find("POST", f"/{IG}/media_publish")[0][2] == {"creation_id": "223"}


def test_gives_up_after_three_stuck_containers(reel):
    g = graph(stuck_routes(stuck=3))
    r = InstagramPublisher(g, IG, poll_interval=0, stuck_after=0).publish(reel, dry_run=True)
    assert r.status is PublishStatus.FAILED and "224: still processing" in r.error
    assert len(g.session.find("POST", f"/{IG}/media")) == 3
    assert not g.session.find("POST", f"/{IG}/media_publish")


def test_after_a_failed_upload_instagram_takes_facebooks_copy(reel):
    # 2026-11-06, run #10: three uploaded containers stuck in a row. Facebook's copy of the
    # draft (its CDN) goes to a container of its own; the first one ready is used.
    hosted = "https://video.xx.fbcdn.net/v/reel.mp4?sig=1"
    g = graph(stuck_routes(stuck=1))        # 222: our upload, stuck; 223: Facebook's copy
    cid = InstagramPublisher(g, IG, poll_interval=0, stuck_after=0).prepare(reel, hosted=hosted)
    assert cid == "223"                                           # the copy's container
    first, copy = g.session.find("POST", f"/{IG}/media")
    assert first[2]["upload_type"] == "resumable" and "video_url" not in first[2]
    assert copy[2]["video_url"] == hosted and "upload_type" not in copy[2]
    assert copy[2]["caption"] == first[2]["caption"] and copy[2]["media_type"] == "REELS"
    assert not g.session.find("POST", "/ig-api-upload/v24.0/223")     # Instagram fetches it


def test_a_clean_upload_never_needs_facebooks_copy(reel):
    g = graph(instagram_routes())
    assert InstagramPublisher(g, IG, poll_interval=0).prepare(reel, hosted="https://x/y") == "222"
    assert len(g.session.find("POST", f"/{IG}/media")) == 1


def test_an_earlier_stuck_container_that_finishes_late_is_used(reel):
    # the first container finishes while the second upload is watched (its states: read
    # after the upload error, first watch, then while watching the second)
    states = iter(["IN_PROGRESS", "IN_PROGRESS", "FINISHED"])
    routes = stuck_routes(stuck=2)
    routes[("GET", "/222")] = status_only(lambda f: {"status_code": next(states, "FINISHED")})
    g = graph(routes)
    assert InstagramPublisher(g, IG, poll_interval=0, stuck_after=0).prepare(reel) == "222"
    assert len(g.session.find("POST", f"/{IG}/media")) == 2


def test_facebook_gives_its_copy_without_printing_it(capsys):
    from quran_reels.publishers.facebook import FacebookPublisher

    url = "https://video.xx.fbcdn.net/v/reel.mp4?sig=secret"
    g = graph({("GET", "/444"): {"source": url, "id": "444"}})
    assert FacebookPublisher(g, PAGE).hosted_url("444") == url
    g = graph({("GET", "/444"): Resp({"error": {"message": "Unsupported get request"}}, 400)})
    assert FacebookPublisher(g, PAGE).hosted_url("444") is None
    assert "sig=secret" not in capsys.readouterr().err


def test_slow_processing_after_a_clean_upload_is_not_retried(reel):
    routes = instagram_routes() | {("GET", "/222"): status_only({"status_code": "IN_PROGRESS"})}
    g = graph(routes)
    r = InstagramPublisher(g, IG, poll_interval=0, timeout=0).publish(reel, dry_run=True)
    assert r.status is PublishStatus.FAILED and "222: still processing" in r.error
    assert len(g.session.find("POST", f"/{IG}/media")) == 1


def test_instagram_keeps_the_first_five_hashtags_facebook_its_own_cap(reel):
    from quran_reels.publishers.facebook import FacebookPublisher

    reel.hashtags = [f"#t{i}" for i in range(1, 10)]
    g = graph(instagram_routes())
    InstagramPublisher(g, IG, poll_interval=0).publish(reel, dry_run=True)
    caption = g.session.find("POST", f"/{IG}/media")[0][2]["caption"]
    assert caption.rstrip().endswith("#t1 #t2 #t3 #t4 #t5") and "#t6" not in caption
    g = graph(facebook_routes())
    FacebookPublisher(g, PAGE, poll_interval=0, max_hashtags=8).publish(reel, dry_run=True)
    finish = next(c for c in g.session.find("POST", f"/{PAGE}/video_reels")
                  if c[2].get("upload_phase") == "finish")
    assert "#t8" in finish[2]["description"] and "#t9" not in finish[2]["description"]


def test_the_fallback_alone_for_a_test_run(reel, monkeypatch):
    # publish-test, instagram_from: facebook-copy: no upload of ours, Facebook's copy only
    monkeypatch.setenv("QURAN_REELS_INSTAGRAM_FROM", "facebook-copy")
    g = graph(instagram_routes())
    assert InstagramPublisher(g, IG, poll_interval=0).prepare(reel, hosted="https://cdn/x") == "222"
    (only,) = g.session.find("POST", f"/{IG}/media")
    assert only[2]["video_url"] == "https://cdn/x" and not g.session.find("POST", "/ig-api-upload")
