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
              "instagram_basic", "instagram_content_publish"]


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
    with pytest.raises(GraphError, match="Invalid OAuth .code 190") as e:
        g.get("me")
    assert TOKEN not in str(e.value)


# ---- Facebook ------------------------------------------------------------------------

def facebook_routes(publish_status="complete"):
    return {
        ("POST", f"/{PAGE}/video_reels"): lambda f: (
            {"video_id": "111", "upload_url": "https://rupload.facebook.com/video-upload/v24.0/111"}
            if f["upload_phase"] == "start" else {"success": True}),
        ("POST", "/video-upload/v24.0/111"): {"success": True},
        ("GET", "/111"): lambda f: (
            {"permalink_url": "/reel/111/"} if f.get("fields") == "permalink_url" else
            {"status": {"video_status": "ready",
                        "processing_phase": {"status": "complete"},
                        "publishing_phase": {"status": publish_status}}}),
    }


def test_facebook_dry_run_leaves_a_draft(reel):
    g = graph(facebook_routes(publish_status="not_started"))
    r = FacebookPublisher(g, PAGE, poll_interval=0).publish(reel, dry_run=True)
    assert (r.status, r.remote_id) == (PublishStatus.DRAFT, "111")
    [finish] = [c for c in g.session.find("POST", f"/{PAGE}/video_reels")
                if c[2]["upload_phase"] == "finish"]
    assert finish[2]["video_state"] == "DRAFT"
    assert finish[2]["description"] == reel.caption
    [upload] = g.session.find("POST", "/video-upload/v24.0/111")
    assert upload[3]["file_size"] == "1234" and upload[3]["offset"] == "0"
    assert upload[3]["Authorization"] == f"OAuth {TOKEN}"


def test_facebook_publish(reel):
    g = graph(facebook_routes())
    r = FacebookPublisher(g, PAGE, poll_interval=0).publish(reel)
    assert (r.status, r.url) == (PublishStatus.PUBLISHED, "https://www.facebook.com/reel/111/")
    states = [c[2].get("video_state") for c in g.session.find("POST", f"/{PAGE}/video_reels")]
    assert states == [None, "PUBLISHED"]


def test_facebook_processing_error_is_reported(reel):
    routes = facebook_routes() | {("GET", "/111"): {"status": {
        "processing_phase": {"status": "error", "errors": [{"message": "Video too short"}]}}}}
    r = FacebookPublisher(graph(routes), PAGE, poll_interval=0).publish(reel)
    assert r.status is PublishStatus.FAILED and "Video too short" in r.error


# ---- Instagram -----------------------------------------------------------------------

def instagram_routes(states=("IN_PROGRESS", "FINISHED")):
    seq = iter(states)
    return {
        ("POST", f"/{IG}/media"): {"id": "222",
                                   "uri": "https://rupload.facebook.com/ig-api-upload/v24.0/222"},
        ("POST", "/ig-api-upload/v24.0/222"): {"success": True},
        ("GET", "/222"): lambda f: {"status_code": next(seq)},
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
                              "caption": reel.caption, "share_to_feed": "true",
                              "thumb_offset": "3700"}


def test_instagram_publish(reel):
    g = graph(instagram_routes())
    r = InstagramPublisher(g, IG, poll_interval=0).publish(reel)
    assert (r.status, r.remote_id, r.url) == (PublishStatus.PUBLISHED, "333",
                                              "https://www.instagram.com/reel/abc/")
    assert g.session.find("POST", f"/{IG}/media_publish")[0][2] == {"creation_id": "222"}


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
    routes = instagram_routes() | {("GET", "/222"): lambda f: next(answers)}
    r = InstagramPublisher(graph(routes), IG, poll_interval=0).publish(reel, dry_run=True)
    assert r.status is PublishStatus.READY
