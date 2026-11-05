"""TikTok, draft mode: the reel is sent to the TikTok inbox and posted by hand from the app.

Content Posting API, upload to inbox (scope video.upload):
  POST /v2/post/publish/inbox/video/init/   → publish_id, upload_url
  PUT  upload_url (Content-Range chunks)
  POST /v2/post/publish/status/fetch/       → SEND_TO_USER_INBOX when it is in the inbox
Nothing is ever public: the owner gets a notification and finishes the post in the app.
TikTok keeps at most 5 such pending drafts per 24 hours.

Sign-in (once, then about once a year): docs/tiktok-login.html builds the authorization URL,
TikTok sends the code to docs/tiktok-callback.html, the tiktok-auth workflow exchanges it.
The access token lasts 24 hours: every run gets a new one from TIKTOK_REFRESH_TOKEN, and the
refresh token TikTok sends back, when it changed, replaces the secret at once.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

import requests

from quran_reels import __version__
from quran_reels.gh_secrets import SecretSaveError, mask
from quran_reels.models import PublishResult, PublishStatus, Reel
from quran_reels.publishers.base import PublisherError, wait

API = "https://open.tiktokapis.com"
AUTHORIZE = "https://www.tiktok.com/v2/auth/authorize/"
SCOPES = ("user.info.basic", "video.upload")
REFRESH_SECRET = "TIKTOK_REFRESH_TOKEN"
USER_AGENT = f"quran-reels/{__version__} (+https://github.com/mssnoussi92/quran-reels)"

MAX_SINGLE_CHUNK = 64 * 2**20      # up to 64 MB in one piece
CHUNK = 10 * 2**20                 # otherwise 10 MB chunks, the last one takes the rest


class TikTokError(PublisherError):
    pass


def auth_url(client_key: str, redirect_uri: str, state: str,
             scopes: tuple[str, ...] = SCOPES) -> str:
    params = {"client_key": client_key, "scope": ",".join(scopes), "response_type": "code",
              "redirect_uri": redirect_uri, "state": state}
    return AUTHORIZE + "?" + "&".join(f"{k}={quote(v, safe=',')}" for k, v in params.items())


def chunking(size: int) -> tuple[int, int]:
    """(chunk_size, total_chunk_count) following TikTok's rules for FILE_UPLOAD."""
    if size <= MAX_SINGLE_CHUNK:
        return size, 1
    return CHUNK, size // CHUNK


class TikTok:
    def __init__(self, client_key: str, client_secret: str,
                 session: requests.Session | None = None, timeout: float = 120):
        self.client_key = client_key
        self.client_secret = client_secret
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.timeout = timeout

    def _request(self, method: str, url: str, what: str, **kw: Any) -> requests.Response:
        try:
            return self.session.request(method, url, timeout=self.timeout, **kw)
        except requests.RequestException as e:
            raise TikTokError(f"{what}: network error ({type(e).__name__})", transient=True) from None

    # ---- OAuth -----------------------------------------------------------------------

    def _token(self, what: str, **form: str) -> dict:
        r = self._request("POST", f"{API}/v2/oauth/token/", what,
                          data={"client_key": self.client_key,
                                "client_secret": self.client_secret, **form},
                          headers={"Content-Type": "application/x-www-form-urlencoded",
                                   "Cache-Control": "no-cache"})
        try:
            body = r.json()
        except ValueError:
            body = {}
        if r.status_code >= 400 or body.get("error") or "access_token" not in body:
            raise TikTokError(f"{what}: {body.get('error') or f'HTTP {r.status_code}'} "
                              f"{body.get('error_description', '')} "
                              f"(log_id {body.get('log_id', '-')})".replace("  ", " "),
                              transient=r.status_code >= 500)
        for key in ("access_token", "refresh_token"):
            mask(body.get(key, ""))
        return body

    def exchange(self, code: str, redirect_uri: str) -> dict:
        return self._token("token exchange", grant_type="authorization_code",
                           code=unquote(code.strip()), redirect_uri=redirect_uri)

    def refresh(self, refresh_token: str) -> dict:
        return self._token("token refresh", grant_type="refresh_token",
                           refresh_token=refresh_token)

    # ---- API -------------------------------------------------------------------------

    def api(self, access_token: str, method: str, path: str, body: dict | None = None,
            params: dict | None = None) -> dict:
        r = self._request(method, f"{API}{path}", path, json=body, params=params,
                          headers={"Authorization": f"Bearer {access_token}",
                                   "Content-Type": "application/json; charset=UTF-8"})
        try:
            payload = r.json()
        except ValueError:
            payload = {}
        err = payload.get("error") or {}
        if r.status_code >= 400 or err.get("code") not in (None, "ok"):
            raise TikTokError(f"{path}: {err.get('code') or f'HTTP {r.status_code}'} "
                              f"{err.get('message', '')} (log_id {err.get('log_id', '-')})",
                              transient=r.status_code >= 500)
        return payload.get("data") or {}

    def user(self, access_token: str) -> dict:
        data = self.api(access_token, "GET", "/v2/user/info/",
                        params={"fields": "open_id,display_name"})
        return data.get("user") or {}

    def upload(self, upload_url: str, video: Path, chunk_size: int, count: int) -> None:
        size = video.stat().st_size
        with video.open("rb") as f:
            for i in range(count):
                start = i * chunk_size
                end = size - 1 if i == count - 1 else start + chunk_size - 1
                f.seek(start)
                data = f.read(end - start + 1)
                r = self._request("PUT", upload_url, f"upload chunk {i + 1}/{count}", data=data,
                                  headers={"Content-Type": "video/mp4",
                                           "Content-Length": str(len(data)),
                                           "Content-Range": f"bytes {start}-{end}/{size}"})
                if r.status_code not in (200, 201, 206):
                    raise TikTokError(f"upload chunk {i + 1}/{count}: HTTP {r.status_code}")


@dataclass
class TikTokEnv:
    client_key: str
    client_secret: str
    refresh_token: str | None

    @classmethod
    def from_environ(cls, need_refresh: bool = True) -> TikTokEnv:
        names = ["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET"] + ([REFRESH_SECRET] if need_refresh
                                                                 else [])
        missing = [n for n in names if not os.environ.get(n)]
        if missing:
            hint = (" Run the tiktok-auth workflow first (docs/plateformes.md)."
                    if REFRESH_SECRET in missing else "")
            raise SystemExit(f"missing environment variables: {', '.join(missing)}.{hint}")
        return cls(os.environ["TIKTOK_CLIENT_KEY"], os.environ["TIKTOK_CLIENT_SECRET"],
                   os.environ.get(REFRESH_SECRET))


class TikTokPublisher:
    name = "tiktok"
    mode = "draft"

    def __init__(self, client: TikTok, refresh_token: str,
                 save_refresh: Callable[[str], None], poll_interval: float = 5,
                 timeout: float = 600):
        self.client = client
        self.refresh_token = refresh_token
        self.save_refresh = save_refresh
        self.poll_interval = poll_interval
        self.timeout = timeout

    def access_token(self) -> str:
        """A fresh access token. A new refresh token is saved before anything else."""
        t = self.client.refresh(self.refresh_token)
        new = t.get("refresh_token")
        if new and new != self.refresh_token:
            try:
                self.save_refresh(new)
            except SecretSaveError as e:
                raise TikTokError(f"{e}. TikTok sent a new refresh token that could not be "
                                  "kept: if the next run fails, sign in again "
                                  "(tiktok-auth workflow).") from None
            self.refresh_token = new
        scopes = set((t.get("scope") or "").split(","))
        if "video.upload" not in scopes:
            raise TikTokError("the TikTok token lacks the video.upload scope: sign in again")
        return t["access_token"]

    def _status(self, access: str, publish_id: str) -> tuple[bool, str]:
        data = self.client.api(access, "POST", "/v2/post/publish/status/fetch/",
                               {"publish_id": publish_id})
        status = data.get("status", "")
        if status == "FAILED":
            raise TikTokError(f"tiktok {publish_id}: FAILED {data.get('fail_reason', '')}")
        return status in ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE"), status

    def publish(self, reel: Reel, dry_run: bool = False) -> PublishResult:
        """Draft mode only: a dry run does the same inbox upload, which is never public."""
        try:
            access = self.access_token()
            size = reel.video.stat().st_size
            chunk, count = chunking(size)
            data = self.client.api(access, "POST", "/v2/post/publish/inbox/video/init/", {
                "source_info": {"source": "FILE_UPLOAD", "video_size": size,
                                "chunk_size": chunk, "total_chunk_count": count}})
            publish_id = data["publish_id"]
            self.client.upload(data["upload_url"], reel.video, chunk, count)
            wait(lambda: self._status(access, publish_id), f"tiktok {publish_id}",
                 self.timeout, self.poll_interval)
        except (PublisherError, KeyError) as e:      # TikTokError, or still processing
            return PublishResult(self.name, PublishStatus.FAILED, error=str(e))
        return PublishResult(self.name, PublishStatus.DRAFT, remote_id=publish_id)
