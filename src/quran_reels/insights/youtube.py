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
        items = self.get(f"{DATA}/channels", token, part="contentDetails,snippet,statistics",
                         mine="true").get("items") or []
        if not items:
            raise YouTubeError("no YouTube channel for this Google account")
        c = items[0]
        st = c.get("statistics") or {}
        return {"id": c["id"], "title": (c.get("snippet") or {}).get("title", ""),
                "uploads": c["contentDetails"]["relatedPlaylists"]["uploads"],
                "subscribers": None if st.get("hiddenSubscriberCount") else _int(
                    st.get("subscriberCount")),
                "videos": _int(st.get("videoCount"))}

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
                    "title": (v.get("snippet") or {}).get("title", ""),
                    "description": (v.get("snippet") or {}).get("description", "")}
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


def video_key(title: str, description: str = "") -> str:
    """What the statistics page matches a YouTube video with: a reel's passage, written as the
    calendar writes it (« 106:1-4 », a single ayah « 9:51-51 »), from its title or, titled by
    hand, from its description's surah line (the reel's caption.txt: « Surah At-Tawbah (9:51) ·
    سورة التوبة » in its first lines); otherwise the title itself (a theme video, matched by its
    title; its description quotes verses too, never on a line of its own that starts with
    « Surah »)."""
    m = PASSAGE.search(title or "")
    if not m:
        for line in (description or "").splitlines()[:4]:
            if line.strip().startswith("Surah ") and (m := PASSAGE.search(line)):
                break
    if m:
        surah, first, last = m.groups()
        return f"{int(surah)}:{int(first)}-{int(last or first)}"
    return (title or "").strip()


SHORT_MAX = 180          # seconds: longer, a YouTube video (the 16:9 film), not a Short


def numbers(stats: dict[str, Any], extra: dict[str, Any] | None) -> dict[str, Any]:
    """The numbers of one video, named as the page names Meta's (metrics.NUMBERS)."""
    m = {k: stats[k] for k in ("views", "likes", "comments") if stats.get(k) is not None}
    m |= {k: x for k, x in (extra or {}).items() if x is not None}
    return m


def match(title: str, description: str, published: datetime, posts: dict[str, dict],
          themes: Any = None) -> dict[str, Any]:
    """Which video of the Page a YouTube video is (key, kind, label, ref), so that it stands beside
    its Facebook and Instagram twins: a reel by its reference (title, or the description's surah
    line) or by the names in its title; a theme video by its title (the 16:9 film beside its 9:16
    version). Unknown: on its own, kind « other »."""
    key = video_key(title, description)
    twin = None
    if PASSAGE.fullmatch(f"({key})"):
        twin = next((r for r in posts.values() if r.get("platform") != "youtube" and
                     (r.get("ref") or {}).get("passage") == key), None)
    if twin is None and themes is not None:
        video = themes.match(title, "youtube")
        if video:
            info = {"key": f"theme:{video.id}", "kind": video.kind,
                    "label": f"{video.title_en} · {video.title_ar}",
                    "ref": {"theme": video.id, "series": video.series, "part": video.part}}
            if video.id.endswith("/film"):
                tall = f"theme:{video.id[:-len('/film')]}-9x16/film"
                if any(r.get("key") == tall for r in posts.values()):
                    info["key"] = tall
            return info
    if twin is None:
        found = _by_name(title, published, posts)
        twin = posts.get(found) if found else None
    if twin is not None:
        return {k: twin.get(k) for k in ("key", "kind", "label", "ref")} | {
            "ref": dict(twin.get("ref") or {})}
    return {"key": "", "kind": "other", "label": title, "ref": {}}


def _by_name(title: str, published: datetime, posts: dict[str, dict]) -> str | None:
    """A reel known only by the names in its title (« Surah Al-Masad · سورة المسد », « آية الكرسي -
    Ayat al-Kursi »): the reel whose first caption line carries one of them; several (a surah
    read in parts), the last one published before it, a day's margin. Returns its uid."""
    from quran_reels.insights.themes import norm

    parts = [norm(x) for x in re.split(r" · | - | \| ", title or "")]
    parts = [x for x in parts if len(x) >= 6]
    if not parts:
        return None
    found = []
    for uid, rec in posts.items():
        line = norm(rec.get("first_line") or "")
        if (rec.get("key") or "").startswith("slot:") and line and any(x in line for x in parts):
            found.append((rec.get("published", ""), uid))
    if not found:
        return None
    limit = (published + timedelta(days=1)).isoformat()
    before = [f for f in found if f[0] <= limit]
    return (max(before) if before else min(found))[1]


def collect(path: Path, s: dict[str, Any], now: datetime | None = None,
            client: YouTube | None = None, env: YouTubeEnv | None = None,
            dry_run: bool = False, themes: Any = None) -> str:
    """Read the channel into insights.json, as the Meta posts are: one post per public video
    (« youtube:<id> », its link, its title), its snapshots at 48 h, 7 days and 28 days and the
    latest (collect.due; a video seen for the first time gets one at once), the subscribers of the
    day. Returns a line for the log."""
    from quran_reels.insights.collect import PARIS, due, load, save

    env = env or YouTubeEnv.from_environ()
    if env is None:
        return "youtube: not configured (YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, " \
               f"{REFRESH_SECRET}): screenshots only"
    now = now or datetime.now(UTC)
    yt = client or YouTube(env.client_id, env.client_secret)
    token = yt.access(str(env.refresh_token))
    ch = yt.channel(token)
    found = yt.uploads(token, ch["uploads"], now - timedelta(days=int(s.get("days", 35))))
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

    data = load(path)
    # Read once as screenshot-like entries (2026-11-15, the first evening): posts now.
    data["manual"] = [m for m in data["manual"] if m.get("source") != "youtube-api"]
    today = now.astimezone(PARIS).date().isoformat()
    if ch.get("subscribers") is not None:
        data["accounts"].setdefault("youtube", {})[today] = {
            "followers_count": ch["subscribers"], "media_count": ch.get("videos")}
    listed = now.isoformat(timespec="seconds")
    data["listed_youtube"] = listed           # a video not listed again is no longer public
    taken = 0
    for v in found:
        st = stats.get(v["id"])
        if not st:
            continue
        uid = f"youtube:{v['id']}"
        title = st.get("title") or v["title"]
        seconds_ = st.get("seconds")
        short = seconds_ is not None and seconds_ <= SHORT_MAX
        rec = data["posts"].setdefault(uid, {"snapshots": {}})
        rec |= {"platform": "youtube", "id": v["id"], "seen": listed,
                "url": f"https://www.youtube.com/{'shorts/' + v['id'] if short else 'watch?v=' + v['id']}",
                "published": v["published"].isoformat(timespec="seconds"),
                "kind_meta": "youtube-short" if short else "youtube-video",
                "first_line": title[:140]}
        if seconds_:
            rec["seconds"] = seconds_
        info = match(title, st.get("description") or "", v["published"], data["posts"], themes)
        rec |= {"key": info["key"] or uid, "kind": info["kind"], "label": info["label"],
                "ref": info["ref"]}
        age_h = (now - v["published"]).total_seconds() / 3600
        names = due(rec, age_h, s) or ([] if rec["snapshots"] else ["latest"])
        if names:
            snap = {"at": listed, "age_h": round(age_h, 1), "m": numbers(st, extra.get(v["id"]))}
            for name in names:
                rec["snapshots"][name] = snap
            taken += 1
    if not dry_run:
        save(path, data)
    return (f"youtube: channel « {ch['title']} » ({ch.get('subscribers')} subscribers), "
            f"{len(public)} public videos, {taken} read"
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
