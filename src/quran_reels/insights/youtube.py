"""The channel's YouTube numbers, read with the owner's consent (docs/insights.md, « YouTube »).

Owner's choice, 2026-11-15: rather than a screenshot of YouTube Studio every Sunday, the nightly
reading asks YouTube itself, read-only:

- YouTube Data API (youtube.readonly): the channel's uploads of the last `days`, public ones only,
  with their views, likes and comments (live counters);
- YouTube Analytics API (yt-analytics.readonly): average view duration and percentage, shares,
  subscribers gained, per video (YouTube computes them with a delay of a day or two).

They go where the screenshots went (`manual` of insights.json, source « youtube-api »), one entry
per video and per day, matched to the reel or theme video by its title (a reel's title carries its
reference, « (106:1-4) »; a theme video's is its own title). TikTok stays on screenshots.

Access: an OAuth client of the owner's Google Cloud project (YOUTUBE_CLIENT_ID,
YOUTUBE_CLIENT_SECRET) and a refresh token saved once by the workflow youtube-auth
(YOUTUBE_REFRESH_TOKEN, docs/plateformes.md). Nothing here can upload, edit or delete: the scopes
are read-only. Tokens never reach a log (errors are rebuilt without them).
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
DATA = "https://www.googleapis.com/youtube/v3"
ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"
SCOPES = ("https://www.googleapis.com/auth/youtube.readonly",
          "https://www.googleapis.com/auth/yt-analytics.readonly")
REFRESH_SECRET = "YOUTUBE_REFRESH_TOKEN"
PASSAGE = re.compile(r"\((\d{1,3}):(\d{1,3})(?:-(\d{1,3}))?\)")
DURATION = re.compile(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?")
ANALYTICS_METRICS = ("views", "averageViewDuration", "averageViewPercentage", "shares",
                     "subscribersGained")


class YouTubeError(RuntimeError):
    pass


@dataclass
class YouTubeEnv:
    client_id: str
    client_secret: str
    refresh_token: str | None

    @classmethod
    def from_environ(cls, need_refresh: bool = True) -> YouTubeEnv | None:
        """None when the client is not configured (YouTube is then left to the screenshots)."""
        cid, secret = os.environ.get("YOUTUBE_CLIENT_ID"), os.environ.get("YOUTUBE_CLIENT_SECRET")
        refresh = os.environ.get(REFRESH_SECRET)
        if not cid or not secret or (need_refresh and not refresh):
            return None
        return cls(cid, secret, refresh)


def auth_url(client_id: str, redirect_uri: str, state: str = "quran-reels") -> str:
    from urllib.parse import urlencode

    return AUTH_URL + "?" + urlencode({
        "client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code",
        "scope": " ".join(SCOPES), "access_type": "offline", "prompt": "consent",
        "include_granted_scopes": "true", "state": state})


class YouTube:
    def __init__(self, client_id: str, client_secret: str, session: Any = None,
                 timeout: float = 60):
        if session is None:
            import requests

            session = requests.Session()
        self.client_id, self.client_secret = client_id, client_secret
        self.http, self.timeout = session, timeout

    # ---- tokens ---------------------------------------------------------------------------
    def _token(self, data: dict[str, str], what: str) -> dict[str, Any]:
        r = self.http.post(TOKEN_URL, data={**data, "client_id": self.client_id,
                                            "client_secret": self.client_secret},
                           timeout=self.timeout)
        body = _json(r)
        if r.status_code != 200 or "access_token" not in body:
            raise YouTubeError(f"{what}: HTTP {r.status_code} {body.get('error', '')} "
                               f"{body.get('error_description', '')}".strip())
        return body

    def exchange(self, code: str, redirect_uri: str) -> dict[str, Any]:
        """The one-time code of youtube-callback.html → tokens (refresh_token included)."""
        return self._token({"code": code, "redirect_uri": redirect_uri,
                            "grant_type": "authorization_code"}, "Google code exchange")

    def access(self, refresh_token: str) -> str:
        return self._token({"refresh_token": refresh_token, "grant_type": "refresh_token"},
                           "Google token refresh")["access_token"]

    # ---- reading --------------------------------------------------------------------------
    def get(self, url: str, token: str, **params: Any) -> dict[str, Any]:
        r = self.http.get(url, params=params, headers={"Authorization": f"Bearer {token}"},
                          timeout=self.timeout)
        body = _json(r)
        if r.status_code != 200:
            err = body.get("error") or {}
            message = err.get("message", "") if isinstance(err, dict) else str(err)
            raise YouTubeError(f"GET {url.rsplit('/', 1)[-1]}: HTTP {r.status_code} {message}"
                               .strip())
        return body

    def channel(self, token: str) -> dict[str, str]:
        items = self.get(f"{DATA}/channels", token, part="contentDetails,snippet",
                         mine="true").get("items") or []
        if not items:
            raise YouTubeError("no YouTube channel for this Google account")
        c = items[0]
        return {"id": c["id"], "title": (c.get("snippet") or {}).get("title", ""),
                "uploads": c["contentDetails"]["relatedPlaylists"]["uploads"]}

    def uploads(self, token: str, playlist: str, since: datetime) -> list[dict[str, Any]]:
        """The channel's videos published since `since`, newest first (the uploads playlist is
        in that order: stop at the first older one)."""
        out: list[dict[str, Any]] = []
        page = None
        while True:
            params = {"part": "contentDetails,snippet", "playlistId": playlist, "maxResults": 50}
            if page:
                params["pageToken"] = page
            body = self.get(f"{DATA}/playlistItems", token, **params)
            for item in body.get("items") or []:
                cd = item.get("contentDetails") or {}
                published = cd.get("videoPublishedAt") or (item.get("snippet") or {}).get(
                    "publishedAt")
                if not published:
                    continue
                when = datetime.fromisoformat(published)
                if when < since:
                    return out
                out.append({"id": cd.get("videoId"), "published": when,
                            "title": (item.get("snippet") or {}).get("title", "")})
            page = body.get("nextPageToken")
            if not page:
                return out

    def videos(self, token: str, ids: list[str]) -> dict[str, dict[str, Any]]:
        """Public videos only: {id: {views, likes, comments, seconds, title}}."""
        out = {}
        for i in range(0, len(ids), 50):
            body = self.get(f"{DATA}/videos", token, part="statistics,status,contentDetails,snippet",
                            id=",".join(ids[i:i + 50]))
            for v in body.get("items") or []:
                if (v.get("status") or {}).get("privacyStatus") != "public":
                    continue
                s = v.get("statistics") or {}
                out[v["id"]] = {
                    "views": _int(s.get("viewCount")), "likes": _int(s.get("likeCount")),
                    "comments": _int(s.get("commentCount")),
                    "seconds": seconds((v.get("contentDetails") or {}).get("duration") or ""),
                    "title": (v.get("snippet") or {}).get("title", "")}
        return out

    def analytics(self, token: str, ids: list[str], start: date, end: date
                  ) -> dict[str, dict[str, Any]]:
        """{id: {avg_watch, watch_pct, shares, follows}} from YouTube Analytics (lifetime of the
        window start → end; YouTube fills it with a delay of a day or two)."""
        out: dict[str, dict[str, Any]] = {}
        for i in range(0, len(ids), 200):
            body = self.get(ANALYTICS, token, ids="channel==MINE", startDate=start.isoformat(),
                            endDate=end.isoformat(), metrics=",".join(ANALYTICS_METRICS),
                            dimensions="video", filters="video==" + ",".join(ids[i:i + 200]),
                            sort="-views", maxResults=200)
            names = [h.get("name") for h in body.get("columnHeaders") or []]
            for row in body.get("rows") or []:
                r = dict(zip(names, row, strict=False))
                out[str(r.get("video"))] = {
                    "avg_watch": _num(r.get("averageViewDuration")),
                    "watch_pct": _num(r.get("averageViewPercentage")),
                    "shares": _int(r.get("shares")), "follows": _int(r.get("subscribersGained"))}
        return out


def _json(r: Any) -> dict[str, Any]:
    try:
        body = r.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _int(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _num(v: Any) -> float | None:
    try:
        return round(float(v), 1)
    except (TypeError, ValueError):
        return None


def seconds(iso: str) -> float | None:
    """« PT1M5S » → 65.0."""
    m = DURATION.fullmatch(iso or "")
    if not iso or not m or not any(m.groups()):
        return None
    d, h, mi, s = (float(x) if x else 0.0 for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def video_key(title: str) -> str:
    """What the statistics page matches a YouTube video with: a reel's passage, written as the
    calendar writes it (« 106:1-4 », a single ayah « 9:51-51 »), or the title itself (a theme
    video, matched by its title)."""
    m = PASSAGE.search(title or "")
    if m:
        surah, first, last = m.groups()
        return f"{int(surah)}:{int(first)}-{int(last or first)}"
    return (title or "").strip()


def entries(found: list[dict[str, Any]], stats: dict[str, dict], extra: dict[str, dict],
            today: date) -> list[dict[str, Any]]:
    """One insights `manual` entry per public video (source « youtube-api »)."""
    out = []
    for v in found:
        s = stats.get(v["id"])
        if not s:
            continue                       # private, unlisted or gone
        nums = {k: s[k] for k in ("views", "likes", "comments") if s.get(k) is not None}
        nums |= {k: x for k, x in (extra.get(v["id"]) or {}).items() if x is not None}
        if not nums:
            continue
        out.append({"platform": "youtube", "video": video_key(s.get("title") or v["title"]),
                    "published": v["published"].date().isoformat(), "seen": today.isoformat(),
                    "metrics": nums, "source": "youtube-api"})
    return out


def collect(path: Path, days: int = 35, now: datetime | None = None,
            client: YouTube | None = None, env: YouTubeEnv | None = None,
            dry_run: bool = False) -> str:
    """Read the channel and add its numbers to insights.json. Returns a line for the log."""
    from quran_reels.insights.collect import add_manual

    env = env or YouTubeEnv.from_environ()
    if env is None:
        return "youtube: not configured (YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, " \
               f"{REFRESH_SECRET}): screenshots only"
    now = now or datetime.now(UTC)
    yt = client or YouTube(env.client_id, env.client_secret)
    token = yt.access(str(env.refresh_token))
    ch = yt.channel(token)
    found = yt.uploads(token, ch["uploads"], now - timedelta(days=days))
    ids = [v["id"] for v in found if v.get("id")]
    stats = yt.videos(token, ids) if ids else {}
    public = [i for i in ids if i in stats]
    extra: dict[str, dict] = {}
    note = ""
    if public:
        start = min(v["published"] for v in found if v["id"] in stats).date()
        try:
            extra = yt.analytics(token, public, start, now.date())
        except YouTubeError as e:            # the counters are still worth keeping
            note = f" (YouTube Analytics unavailable: {e})"
    rows = entries(found, stats, extra, now.date())
    if rows and not dry_run:
        add_manual(path, rows, now=now)
    return (f"youtube: channel « {ch['title']} », {len(rows)} public videos read"
            f"{' (dry run, nothing saved)' if dry_run else ''}{note}")


def auth(redirect_uri: str, code: str | None, client: YouTube | None = None) -> int:
    """Exchange the code of youtube-callback.html, save YOUTUBE_REFRESH_TOKEN (workflow
    youtube-auth). The code is read from the workflow's event file, never printed."""
    from quran_reels.gh_secrets import SecretSaveError, mask, save_secret
    from quran_reels.publish import _event_input, _summary

    code = code or os.environ.get("YOUTUBE_AUTH_CODE") or _event_input("code")
    if not code:
        raise SystemExit("no authorization code: pass --code or run the youtube-auth workflow")
    mask(code)
    env = YouTubeEnv.from_environ(need_refresh=False)
    if env is None:
        raise SystemExit("YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET are needed (GitHub secrets)")
    yt = client or YouTube(env.client_id, env.client_secret)
    try:
        t = yt.exchange(code, redirect_uri)
        mask(t["access_token"])
        ch = yt.channel(t["access_token"])
    except YouTubeError as e:
        _summary(f"## ❌ Connexion YouTube\n\n{e}\n\nLe code ne sert qu'une fois et expire en "
                 "quelques minutes : recommencer depuis youtube-login.html.")
        raise SystemExit(f"YouTube sign-in failed: {e}") from None
    granted = set((t.get("scope") or "").split())
    missing = [s.rsplit("/", 1)[-1] for s in SCOPES if s not in granted]
    if not t.get("refresh_token"):
        raise SystemExit("Google gave no refresh token: sign in again from youtube-login.html "
                         "(it asks for consent each time)")
    try:
        save_secret(REFRESH_SECRET, t["refresh_token"])
    except SecretSaveError as e:
        _summary(f"## ❌ Connexion YouTube\n\nJeton obtenu mais non enregistré : {e}")
        raise SystemExit(str(e)) from None
    lines = [f"Chaîne : {ch['title']}", f"{REFRESH_SECRET} enregistré (lecture seule)."]
    if missing:
        lines.append("Autorisations refusées : " + ", ".join(missing)
                     + " : recommencer en cochant tout.")
    _summary("## ✅ YouTube connecté\n\n" + "\n\n".join(lines))
    print("\n".join(lines), file=sys.stderr)
    return 1 if missing else 0
