"""TikTok publisher and sign-in against a fake TikTok API; GitHub secret saving with a fake gh."""

import json
import subprocess

import pytest

from quran_reels import gh_secrets
from quran_reels.gh_secrets import SecretSaveError, save_secret
from quran_reels.models import Passage, PublishStatus, Reel
from quran_reels.publishers import tiktok
from quran_reels.publishers.tiktok import TikTok, TikTokError, TikTokPublisher, auth_url, chunking

KEY, SECRET = "sbawkey", "client-secret-value"
REDIRECT = "https://mssnoussi92.github.io/quran-reels/tiktok-callback.html"


class Resp:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status

    def json(self):
        return self.body


class FakeSession:
    def __init__(self, routes):
        self.routes, self.calls, self.headers = routes, [], {}

    def request(self, method, url, timeout=None, params=None, data=None, json=None, headers=None):
        self.calls.append({"method": method, "url": url, "params": params, "data": data,
                           "json": json, "headers": headers or {}})
        for (m, suffix), answer in self.routes.items():
            if m == method and url.split("?")[0].endswith(suffix):
                body = answer(self.calls[-1]) if callable(answer) else answer
                return body if isinstance(body, Resp) else Resp(body)
        raise AssertionError(f"unexpected {method} {url}")

    def find(self, method, suffix):
        return [c for c in self.calls if c["method"] == method and c["url"].endswith(suffix)]


def token(refresh="rt-1", scope="user.info.basic,video.upload"):
    return {"access_token": "act-1", "expires_in": 86400, "open_id": "o1", "scope": scope,
            "refresh_token": refresh, "refresh_expires_in": 31536000, "token_type": "Bearer"}


def ok(data):
    return {"data": data, "error": {"code": "ok", "message": "", "log_id": "L"}}


def routes(refresh="rt-1", statuses=("PROCESSING_UPLOAD", "SEND_TO_USER_INBOX"), scope=None):
    seq = iter(statuses)
    return {
        ("POST", "/v2/oauth/token/"): token(refresh, scope or "user.info.basic,video.upload"),
        ("POST", "/v2/post/publish/inbox/video/init/"): ok({
            "publish_id": "v_inbox_file~v2.1", "upload_url": "https://open-upload.tiktokapis.com/video/?upload_id=1"}),
        ("PUT", "/video/"): Resp({}, 201),
        ("POST", "/v2/post/publish/status/fetch/"): lambda c: ok({"status": next(seq)}),
        ("GET", "/v2/user/info/"): ok({"user": {"open_id": "o1", "display_name": "Quran Words Daily"}}),
    }


@pytest.fixture
def reel(tmp_path):
    video = tmp_path / "093_001-011.mp4"
    video.write_bytes(bytes(range(256)) * 5)          # 1,280 bytes
    return Reel(passage=Passage(93, 1, 11, "الضحى", "Ad-Duhaa"), video=video, caption="c")


def publisher(r, saved, refresh="rt-1"):
    return TikTokPublisher(TikTok(KEY, SECRET, session=FakeSession(r)), refresh,
                           save_refresh=saved.append, poll_interval=0)


def test_auth_url():
    url = auth_url(KEY, REDIRECT, "s1")
    assert url == ("https://www.tiktok.com/v2/auth/authorize/?client_key=sbawkey"
                   "&scope=user.info.basic,video.upload&response_type=code"
                   "&redirect_uri=https%3A%2F%2Fmssnoussi92.github.io%2Fquran-reels%2F"
                   "tiktok-callback.html&state=s1")


def test_chunking_follows_tiktok_rules():
    assert chunking(3 * 2**20) == (3 * 2**20, 1)                # under 5 MB: one piece
    assert chunking(64 * 2**20) == (64 * 2**20, 1)
    assert chunking(95 * 2**20) == (10 * 2**20, 9)               # last chunk takes the rest


def test_inbox_upload_is_a_draft(reel):
    saved = []
    p = publisher(routes(), saved)
    r = p.publish(reel)
    assert (r.status, r.remote_id) == (PublishStatus.DRAFT, "v_inbox_file~v2.1")
    s = p.client.session
    [init] = s.find("POST", "/v2/post/publish/inbox/video/init/")
    assert init["json"] == {"source_info": {"source": "FILE_UPLOAD", "video_size": 1280,
                                            "chunk_size": 1280, "total_chunk_count": 1}}
    assert init["headers"]["Authorization"] == "Bearer act-1"
    [put] = s.find("PUT", "/video/?upload_id=1")
    assert put["headers"]["Content-Range"] == "bytes 0-1279/1280" and len(put["data"]) == 1280
    assert not saved                                      # same refresh token: nothing to save
    [refresh] = s.find("POST", "/v2/oauth/token/")
    assert refresh["data"]["grant_type"] == "refresh_token" and refresh["data"]["refresh_token"] == "rt-1"


def test_rotated_refresh_token_is_saved_before_the_upload(reel):
    saved = []
    p = publisher(routes(refresh="rt-2"), saved)
    assert p.publish(reel).status is PublishStatus.DRAFT
    assert saved == ["rt-2"] and p.refresh_token == "rt-2"


def test_refresh_token_that_cannot_be_saved_stops_before_uploading(reel):
    def fail(value):
        raise SecretSaveError("cannot save TIKTOK_REFRESH_TOKEN: GH_SECRETS_TOKEN not set")

    p = TikTokPublisher(TikTok(KEY, SECRET, session=FakeSession(routes(refresh="rt-2"))), "rt-1",
                        save_refresh=fail, poll_interval=0)
    r = p.publish(reel)
    assert r.status is PublishStatus.FAILED and "GH_SECRETS_TOKEN" in r.error
    assert not p.client.session.find("POST", "/v2/post/publish/inbox/video/init/")


def test_missing_scope(reel):
    r = publisher(routes(scope="user.info.basic"), []).publish(reel)
    assert r.status is PublishStatus.FAILED and "video.upload" in r.error


def test_failed_processing(reel):
    rt = routes() | {("POST", "/v2/post/publish/status/fetch/"):
                     ok({"status": "FAILED", "fail_reason": "file_format_check_failed"})}
    r = publisher(rt, []).publish(reel)
    assert r.status is PublishStatus.FAILED and "file_format_check_failed" in r.error


def test_api_error_is_reported_without_tokens(reel):
    rt = routes() | {("POST", "/v2/post/publish/inbox/video/init/"): Resp({
        "data": {}, "error": {"code": "spam_risk_too_many_pending_share", "message": "Too many",
                              "log_id": "L2"}})}
    r = publisher(rt, []).publish(reel)
    assert "spam_risk_too_many_pending_share" in r.error
    assert "act-1" not in r.error and SECRET not in r.error


def test_large_video_goes_in_chunks(reel, monkeypatch):
    monkeypatch.setattr(tiktok, "MAX_SINGLE_CHUNK", 1000)
    monkeypatch.setattr(tiktok, "CHUNK", 400)
    p = publisher(routes(), [])
    assert p.publish(reel).status is PublishStatus.DRAFT
    ranges = [c["headers"]["Content-Range"] for c in p.client.session.find("PUT", "/video/?upload_id=1")]
    assert ranges == ["bytes 0-399/1280", "bytes 400-799/1280", "bytes 800-1279/1280"]


def test_exchange_decodes_the_code_and_reports_oauth_errors():
    s = FakeSession({("POST", "/v2/oauth/token/"): token()})
    TikTok(KEY, SECRET, session=s).exchange("abc%2A!d", REDIRECT)
    assert s.calls[0]["data"] == {"client_key": KEY, "client_secret": SECRET,
                                       "grant_type": "authorization_code", "code": "abc*!d",
                                       "redirect_uri": REDIRECT}
    bad = FakeSession({("POST", "/v2/oauth/token/"): Resp(
        {"error": "invalid_grant", "error_description": "Authorization code is expired.",
         "log_id": "L3"}, 400)})
    with pytest.raises(TikTokError, match="invalid_grant Authorization code is expired") as e:
        TikTok(KEY, SECRET, session=bad).exchange("x", REDIRECT)
    assert SECRET not in str(e.value)


# ---- GitHub secret ---------------------------------------------------------------------

def test_save_secret_uses_gh_with_the_value_on_stdin(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda argv, **kw: calls.append((argv, kw))
                        or subprocess.CompletedProcess(argv, 0, "", ""))
    monkeypatch.setenv("GH_SECRETS_TOKEN", "github_pat_x")
    monkeypatch.setenv("GITHUB_REPOSITORY", "mssnoussi92/quran-reels")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    save_secret("TIKTOK_REFRESH_TOKEN", "rt-secret")
    [(argv, kw)] = calls
    assert argv == ["gh", "secret", "set", "TIKTOK_REFRESH_TOKEN", "--repo", "mssnoussi92/quran-reels"]
    assert kw["input"] == "rt-secret" and kw["env"]["GH_TOKEN"] == "github_pat_x"
    assert "::add-mask::rt-secret" in capsys.readouterr().out


def test_save_secret_needs_the_fine_grained_token(monkeypatch):
    monkeypatch.delenv("GH_SECRETS_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_REPOSITORY", "mssnoussi92/quran-reels")
    with pytest.raises(SecretSaveError, match="GH_SECRETS_TOKEN"):
        save_secret("TIKTOK_REFRESH_TOKEN", "rt")


# ---- sign-in workflow ------------------------------------------------------------------

def test_tiktok_auth_reads_the_code_from_the_event_and_saves_the_token(tmp_path, monkeypatch):
    from quran_reels import config, publish

    event = tmp_path / "event.json"
    event.write_text(json.dumps({"inputs": {"code": " code-123 "}}))
    summary = tmp_path / "summary.md"
    for k, v in {"GITHUB_EVENT_PATH": str(event), "GITHUB_STEP_SUMMARY": str(summary),
                 "TIKTOK_CLIENT_KEY": KEY, "TIKTOK_CLIENT_SECRET": SECRET}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("TIKTOK_AUTH_CODE", raising=False)
    session = FakeSession(routes())
    monkeypatch.setattr(publish, "TikTok", lambda k, s: TikTok(k, s, session=session))
    saved = []
    monkeypatch.setattr(publish, "save_secret", lambda name, value: saved.append((name, value)))

    assert publish.tiktok_auth(config.load(), None) == 0
    assert session.find("POST", "/v2/oauth/token/")[0]["data"]["code"] == "code-123"
    assert saved == [("TIKTOK_REFRESH_TOKEN", "rt-1")]
    text = summary.read_text()
    assert "Quran Words Daily" in text and "rt-1" not in text and "code-123" not in text


def test_mask_only_on_github_actions(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    gh_secrets.mask("value")
    assert capsys.readouterr().out == ""
