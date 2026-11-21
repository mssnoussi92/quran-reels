"""The calendar's Short uploaded to YouTube by the run (publishers/youtube.py), without network."""

from __future__ import annotations

import json

import pytest
import requests

from quran_reels.insights import youtube as Y
from quran_reels.models import PublishStatus
from quran_reels.publishers import youtube as U

SESSION = "https://upload.example/session?upload_id=SECRET-SESSION"


class Answer:
    def __init__(self, status, body=None, headers=None):
        self.status_code, self._body, self.headers = status, body, headers or {}

    def json(self):
        if self._body is None:
            raise ValueError("no body")
        return self._body


class Google:
    """Token, resumable session, file, status: each answer as YouTube gives it. `puts`: what
    each PUT answers in turn (an Answer, or an exception to raise)."""

    def __init__(self, puts=None, status=None, start=None, token=None):
        self.calls: list = []
        self.puts = list(puts or [Answer(201, {"id": "vid1", "status": {
            "uploadStatus": "uploaded", "privacyStatus": "public"}})])
        self.status = status or {"uploadStatus": "processed", "privacyStatus": "public"}
        self.start = start or Answer(200, {}, {"Location": SESSION})
        self.token = token or Answer(200, {"access_token": "AT-SECRET"})

    def post(self, url, params=None, data=None, headers=None, timeout=None):
        self.calls.append(("POST", url, params, data, headers))
        if url == Y.TOKEN_URL:
            return self.token
        assert headers["Authorization"] == "Bearer AT-SECRET"
        return self.start

    def put(self, url, data=None, headers=None, timeout=None):
        assert url == SESSION and headers["Authorization"] == "Bearer AT-SECRET"
        self.calls.append(("PUT", data, dict(headers)))
        answer = self.puts.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(("GET", url, params))
        return Answer(200, {"items": [{"id": params["id"], "status": self.status}]})


def uploader(http, **kw):
    return U.Uploader(Y.YouTube("cid", "secret", http), "RT-SECRET", sleep=lambda s: None, **kw)


@pytest.fixture
def video(tmp_path):
    path = tmp_path / "114_001-006.mp4"
    path.write_bytes(b"0123456789")
    return U.Video(path=path, title="سورة الناس · Surah An-Nas (114:1-6)",
                   description="سورة الناس <b>\n\n#Quran", tags=["Quran"])


def no_secret(text):
    return all(s not in (text or "") for s in ("AT-SECRET", "RT-SECRET", "SECRET-SESSION"))


def test_a_short_goes_up_public_with_the_texts_of_the_page(video):
    http = Google()
    result = uploader(http).upload(video)
    assert result.status == PublishStatus.PUBLISHED
    assert (result.remote_id, result.url) == ("vid1", "https://youtube.com/shorts/vid1")
    start = http.calls[1]
    assert start[2] == {"uploadType": "resumable", "part": "snippet,status"}
    assert start[4]["X-Upload-Content-Length"] == "10"
    body = json.loads(start[3])
    assert body["snippet"]["title"] == "سورة الناس · Surah An-Nas (114:1-6)"
    assert body["snippet"]["description"] == "سورة الناس b\n\n#Quran"     # no < > for YouTube
    assert body["status"] == {"privacyStatus": "public", "selfDeclaredMadeForKids": False,
                              "containsSyntheticMedia": False}
    assert "categoryId" not in body["snippet"]          # YouTube's default, as by hand
    assert http.calls[2][1] == b"0123456789"            # the whole file
    assert http.calls[3][0] == "GET"                    # then its processing is read


def test_an_interrupted_upload_sends_only_what_youtube_lacks(video):
    http = Google(puts=[requests.ConnectionError("reset"),
                        Answer(308, None, {"Range": "bytes=0-3"}),
                        Answer(201, {"id": "vid1", "status": {"uploadStatus": "processed",
                                                              "privacyStatus": "public"}})])
    result = uploader(http).upload(video)
    assert result.status == PublishStatus.PUBLISHED and result.remote_id == "vid1"
    puts = [c for c in http.calls if c[0] == "PUT"]
    assert puts[1][2]["Content-Range"] == "bytes */10"          # how much arrived?
    assert puts[2][1] == b"456789" and puts[2][2]["Content-Range"] == "bytes 4-9/10"


def test_a_refusal_says_why_without_any_token(video):
    http = Google(start=Answer(403, {"error": {"message": "The request cannot be completed "
                                               "because you have exceeded your quota.",
                                               "errors": [{"reason": "quotaExceeded"}]}}))
    result = uploader(http).upload(video)
    assert result.status == PublishStatus.FAILED and result.remote_id is None   # tried again later
    assert "HTTP 403 quotaExceeded" in result.error and no_secret(result.error)

    http = Google(puts=[requests.ConnectionError("x")] * 6)
    result = uploader(http).upload(video)
    assert result.status == PublishStatus.FAILED and result.remote_id is None
    assert "3 essais" in result.error and no_secret(result.error)


def test_a_lost_sign_in_says_how_to_sign_in_again(video):
    http = Google(token=Answer(400, {"error": "invalid_grant",
                                     "error_description": "Token has been expired or revoked."}))
    result = uploader(http).upload(video)
    assert result.status == PublishStatus.FAILED and "youtube-login.html" in result.error
    assert no_secret(result.error)


@pytest.mark.parametrize(("status", "words"), [
    ({"uploadStatus": "processed", "privacyStatus": "private"}, "« private » au lieu de « public »"),
    ({"uploadStatus": "rejected", "rejectionReason": "duplicate"}, "rejected : duplicate"),
])
def test_a_video_youtube_keeps_private_or_refuses_keeps_its_id(video, status, words):
    """Never uploaded again by a later run (the id is kept): the owner looks at it in Studio."""
    result = uploader(Google(status=status)).upload(video)
    assert result.status == PublishStatus.FAILED and result.remote_id == "vid1"
    assert words in result.error


def test_a_processing_that_lasts_is_not_a_failure(video):
    ticks = iter(range(0, 10_000, 100))
    http = Google(status={"uploadStatus": "uploaded", "privacyStatus": "public"})
    result = uploader(http, clock=lambda: next(ticks), process_timeout=250).upload(video)
    assert result.status == PublishStatus.PUBLISHED and result.remote_id == "vid1"


def test_tags_are_the_hashtags_under_youtubes_limit():
    tags = U.tags_of(["#QuranWordsDaily", "#Quran", "#سورة_الناس", "#Quran", "#" + "x" * 500])
    assert tags == ["QuranWordsDaily", "Quran", "سورة الناس"]


def test_only_the_upload_setting_turns_it_on():
    from types import SimpleNamespace

    assert U.settings(None) is None
    assert U.settings(SimpleNamespace(project={"platforms": {"youtube": {"mode": "manual"}}})) \
        is None
    on = {"daily": True, "privacy": "public"}
    assert U.settings(SimpleNamespace(project={"platforms": {"youtube": {"upload": on}}})) == on


def test_the_uploads_sign_in_asks_its_own_scopes_and_saves_its_own_secret(monkeypatch):
    url = Y.auth_url("cid", "https://x/cb", "s", upload=True)
    assert "youtube.upload" in url and "yt-analytics" not in url
    assert "include_granted_scopes=false" in url      # the statistics' token stays read-only

    class Exchange:
        def __init__(self):
            self.calls = []

        def post(self, url, data=None, timeout=None):
            return Answer(200, {"access_token": "at", "refresh_token": "rt-upload",
                                "scope": " ".join(U.UPLOAD_SCOPES)})

        def get(self, url, params=None, headers=None, timeout=None):
            return Answer(200, {"items": [{"id": "UC1", "snippet": {"title": "Quran Words Daily"},
                                           "statistics": {},
                                           "contentDetails": {"relatedPlaylists": {"uploads": "U"}}}]})

    saved = {}
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "cid")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "secret")
    monkeypatch.setattr("quran_reels.gh_secrets.save_secret", lambda n, v: saved.update({n: v}))
    assert Y.auth("https://x/cb", "code", Y.YouTube("cid", "secret", Exchange())) == 0
    assert saved == {U.UPLOAD_SECRET: "rt-upload"}             # never the statistics' secret
