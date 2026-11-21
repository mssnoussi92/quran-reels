"""YouTube Shorts uploaded by the daily run (owner's choice, 2026-11-21).

Until 2026-11-02, a video uploaded through the API by a project that had not passed YouTube's
audit was locked as private, so the owner uploaded every Short by hand. YouTube lifted that lock
on 2026-11-02 (Data API revision history: « no longer restricted to private viewing mode ») and
gives uploads their own quota (100 a day, 1 unit each). The daily run now uploads the calendar's
Short itself, public (platforms.youtube.upload of config/project.yaml; daily.py decides which
file and checks Meta's rights on it first).

- Access: the OAuth client of the statistics (YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET) with a
  token of its own, YOUTUBE_UPLOAD_REFRESH_TOKEN: youtube-login.html, button « Mise en ligne »,
  then the workflow youtube-auth. Scopes youtube.upload and youtube.readonly: it uploads and
  reads, it can neither change nor delete a video. The statistics keep their read-only token.
- Upload: resumable. The metadata is posted first (YouTube answers with a session address), the
  file is put there; after a network error or HTTP 5xx YouTube is asked how much arrived and the
  rest is sent, UPLOAD_TRIES times in all.
- Then the video is read (videos.list) until YouTube has processed it, PROCESS_TIMEOUT at most:
  a rejection, a failed processing or a video that came out private is a failure that keeps
  the video's id, so that no later run uploads it a second time.
- A theme video gets its thumbnail (the film's drawn one, a short's cover: thumbnails.set, which
  takes Shorts since 2026-11-03, once processed) and is first looked for among the channel's
  latest uploads by its title (`dedupe`): one the owner put there by hand is not put again.

Content ID (YouTube's claims) cannot be read through the API by a channel like this one. What
goes up is by Tawfiq As-Sayegh (platforms.youtube.reciter), never claimed so far.
Tokens and the session address never reach a log: errors are rebuilt without them.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from quran_reels.insights.youtube import DATA, YouTube, YouTubeError
from quran_reels.models import PublishResult, PublishStatus

UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"
THUMBNAIL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
THUMBNAIL_MAX = 2 * 2**20   # bytes: YouTube refuses a bigger image
UPLOAD_SCOPES = ("https://www.googleapis.com/auth/youtube.upload",
                 "https://www.googleapis.com/auth/youtube.readonly")
UPLOAD_SECRET = "YOUTUBE_UPLOAD_REFRESH_TOKEN"
UPLOAD_TRIES = 3            # the file, sent again from where it stopped
UPLOAD_PAUSE = 10.0         # seconds before the second try, twice that before the third
PROCESS_TIMEOUT = 300.0     # seconds spent waiting for YouTube's processing
PROCESS_INTERVAL = 15.0
TITLE_MAX = 100             # YouTube refuses a longer title
DESCRIPTION_MAX = 5000      # bytes
TAGS_MAX = 450              # characters of all tags together (YouTube: 500, counted its way)
DONE = ("processed",)
REFUSED = ("rejected", "failed", "deleted")


class UploadError(RuntimeError):
    """A refusal or a failure, said without any token or session address."""

    def __init__(self, message: str, transient: bool = False):
        super().__init__(message)
        self.transient = transient


@dataclass
class Video:
    """What goes up: the file and the texts the owner pasted by hand until now."""
    path: Path
    title: str
    description: str
    tags: list[str] = field(default_factory=list)
    category: str | None = None         # None: YouTube's default, as for an upload by hand
    privacy: str = "public"
    made_for_kids: bool = False
    synthetic_media: bool = False
    long: bool = False                  # a film (16:9): its address is not a Short's
    language: str | None = None         # the video's and its texts' language (owner, 2026-11-21: ar)

    def body(self) -> dict[str, Any]:
        snippet: dict[str, Any] = {"title": clean(self.title)[:TITLE_MAX],
                                   "description": _cut_bytes(described(self.description),
                                                             DESCRIPTION_MAX)}
        if self.tags:
            snippet["tags"] = self.tags
        if self.category:
            snippet["categoryId"] = str(self.category)
        if self.language:       # what Studio asks of an upload by hand: the audio, the texts
            snippet["defaultLanguage"] = snippet["defaultAudioLanguage"] = self.language
        return {"snippet": snippet,
                "status": {"privacyStatus": self.privacy,
                           "selfDeclaredMadeForKids": self.made_for_kids,
                           "containsSyntheticMedia": self.synthetic_media}}


def clean(text: str) -> str:
    """YouTube refuses « < » and « > » in a title or a description."""
    return text.replace("<", "").replace(">", "")


def described(text: str) -> str:
    """The description as sent: each line that needs it starts with the invisible mark of its own
    direction (bidi.directed, no word changed; the Arabic first and English lines read right
    wherever YouTube shows them, as on the channel's description, 2026-11-21); without the marks
    if they alone would push it over YouTube's limit."""
    from quran_reels.bidi import directed

    text = clean(text)
    marked = directed(text)
    return marked if len(marked.encode("utf-8")) <= DESCRIPTION_MAX else text


def _cut_bytes(text: str, limit: int) -> str:
    data = text.encode("utf-8")
    if len(data) <= limit:
        return text
    return data[:limit].decode("utf-8", errors="ignore").rsplit("\n", 1)[0]


def tags_of(hashtags: list[str], limit: int = TAGS_MAX) -> list[str]:
    """The reel's hashtags as YouTube tags, without « # », in order, under YouTube's limit."""
    out: list[str] = []
    used = 0
    for h in hashtags:
        tag = clean(h.lstrip("#").replace("_", " ").strip())
        cost = len(tag) + (2 if " " in tag else 0) + (1 if out else 0)
        if not tag or tag in out or used + cost > limit:
            continue
        out.append(tag)
        used += cost
    return out


def settings(cfg: Any) -> dict[str, Any] | None:
    """platforms.youtube.upload when the daily run uploads the calendar's Shorts (`daily: true`),
    else None."""
    project = getattr(cfg, "project", None) or {}
    conf = ((project.get("platforms") or {}).get("youtube") or {}).get("upload") or {}
    return conf if conf.get("daily") else None


def video_for(reel: Any, conf: dict[str, Any], max_tags: int | None = None) -> Video:
    """The texts of the page « À publier » (publish.youtube_texts): the caption's head as title,
    the caption as description, its hashtags at the end of it and as tags."""
    from quran_reels.publish import youtube_texts

    texts = youtube_texts(reel, max_tags)
    description = texts["description"].rstrip()
    if texts["hashtags"]:
        description += "\n\n" + texts["hashtags"]
    return Video(path=reel.video, title=texts["title"], description=description + "\n",
                 tags=tags_of(reel.hashtags if max_tags is None else reel.hashtags[:max_tags]),
                 category=conf.get("category"), privacy=str(conf.get("privacy", "public")),
                 made_for_kids=bool(conf.get("made_for_kids", False)),
                 synthetic_media=bool(conf.get("synthetic_media", False)),
                 language=conf.get("language"))


def short_url(video_id: str) -> str:
    return f"https://youtube.com/shorts/{video_id}"


def video_url(video_id: str, video: Video | None = None) -> str:
    """A Short's address, or a film's (`long`: a 16:9 video, never a Short)."""
    if video is not None and video.long:
        return f"https://www.youtube.com/watch?v={video_id}"
    return short_url(video_id)


class Uploader:
    def __init__(self, client: YouTube, refresh_token: str,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic,
                 process_timeout: float = PROCESS_TIMEOUT):
        self.client, self.refresh = client, refresh_token
        self.http = client.http
        self.sleep, self.clock, self.process_timeout = sleep, clock, process_timeout

    @classmethod
    def from_environ(cls, **kw: Any) -> Uploader | None:
        """None when the upload token is not there yet (the owner has not signed in for it)."""
        cid, secret = os.environ.get("YOUTUBE_CLIENT_ID"), os.environ.get("YOUTUBE_CLIENT_SECRET")
        refresh = os.environ.get(UPLOAD_SECRET)
        if not cid or not secret or not refresh:
            return None
        return cls(YouTube(cid, secret), refresh, **kw)

    # ---- one upload -----------------------------------------------------------------------
    def upload(self, video: Video, thumbnail: Path | None = None,
               dedupe: bool = False) -> PublishResult:
        """The video on YouTube: PUBLISHED with its Short's address, or FAILED (with the id when
        YouTube has the video: never to be uploaded again). thumbnail: set once it is processed
        (a failure there is said in `error`, the video stays published). dedupe: a video of the
        same title among the channel's latest uploads is taken as this one."""
        try:
            token = self.client.access(self.refresh)
        except YouTubeError as e:
            return PublishResult("youtube", PublishStatus.FAILED, error=_signin(str(e)))
        if dedupe:
            try:
                found = self.find(clean(video.title)[:TITLE_MAX], token)
            except YouTubeError as e:
                print(f"warning: youtube: the channel's uploads not read ({e})", file=sys.stderr)
                found = None
            if found:
                print(f"youtube: « {video.title} » is on the channel already ({found}), not "
                      "uploaded again", file=sys.stderr)
                return PublishResult("youtube", PublishStatus.PUBLISHED, remote_id=found,
                                     url=video_url(found, video),
                                     error="déjà sur la chaîne (mise en ligne à la main ?), "
                                           "pas remise")
        try:
            session = self._start(video, token)
            answer = self._send(session, video.path, token)
        except UploadError as e:
            return PublishResult("youtube", PublishStatus.FAILED, error=str(e))
        vid = answer.get("id")
        if not vid:
            return PublishResult("youtube", PublishStatus.FAILED,
                                 error="YouTube a reçu le fichier sans donner d'identifiant")
        url = video_url(vid, video)
        print(f"youtube: uploaded {vid}, waiting for YouTube's processing", file=sys.stderr)
        status = answer.get("status") or {}
        try:
            status = self._processed(vid, token, status)
        except Exception as e:      # noqa: BLE001  (YouTube has it: the id must not be lost)
            print(f"warning: youtube: status of {vid} not read ({type(e).__name__})",
                  file=sys.stderr)
        privacy = status.get("privacyStatus")
        upload = status.get("uploadStatus")
        if upload in REFUSED:
            why = status.get("rejectionReason") or status.get("failureReason") or upload
            return PublishResult("youtube", PublishStatus.FAILED, remote_id=vid, url=url,
                                 error=f"YouTube l'a refusée après l'envoi ({upload} : {why})")
        if privacy and privacy != video.privacy:
            return PublishResult(
                "youtube", PublishStatus.FAILED, remote_id=vid, url=url,
                error=(f"en ligne mais « {privacy} » au lieu de « {video.privacy} » : la changer "
                       "dans YouTube Studio (Contenu → Visibilité)"))
        if upload not in DONE:
            print(f"youtube: {vid} still « {upload} » after {self.process_timeout:.0f} s: "
                  "YouTube goes on processing it", file=sys.stderr)
        note = self.thumbnail(vid, thumbnail, token) if thumbnail else None
        return PublishResult("youtube", PublishStatus.PUBLISHED, remote_id=vid, url=url,
                             error=note)

    def find(self, title: str, token: str, latest: int = 50) -> str | None:
        """The id of a video of exactly this title among the channel's `latest` uploads."""
        items = self.client.get(f"{DATA}/channels", token, part="contentDetails",
                                mine="true").get("items") or []
        if not items:
            return None
        uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
        page = self.client.get(f"{DATA}/playlistItems", token, part="snippet",
                               playlistId=uploads, maxResults=str(latest))
        for i in page.get("items") or []:
            sn = i.get("snippet") or {}
            if sn.get("title", "").strip() == title.strip():
                return (sn.get("resourceId") or {}).get("videoId")
        return None

    def thumbnail(self, vid: str, image: Path, token: str) -> str | None:
        """The video's custom thumbnail; None when set, else what went wrong (never raises)."""
        try:
            data = image.read_bytes()
        except OSError as e:
            return f"miniature non posée ({type(e).__name__})"
        if len(data) > THUMBNAIL_MAX:
            return f"miniature non posée : {len(data) / 2**20:.1f} Mo, plus que 2 Mo"
        kind = "image/png" if image.suffix.lower() == ".png" else "image/jpeg"
        try:
            r = self.http.post(THUMBNAIL, params={"videoId": vid}, data=data,
                               headers={"Authorization": f"Bearer {token}",
                                        "Content-Type": kind}, timeout=self.client.timeout)
        except Exception as e:      # noqa: BLE001
            return f"miniature non posée : erreur réseau ({type(e).__name__})"
        if r.status_code != 200:
            return "miniature non posée : " + _error(r)
        print(f"youtube: thumbnail of {vid} set ({image.name})", file=sys.stderr)
        return None

    def _start(self, video: Video, token: str) -> str:
        """The resumable session for this file (its address is never printed)."""
        size = video.path.stat().st_size
        try:
            r = self.http.post(
                UPLOAD, params={"uploadType": "resumable", "part": "snippet,status"},
                data=json.dumps(video.body(), ensure_ascii=False).encode("utf-8"),
                headers={"Authorization": f"Bearer {token}",
                         "Content-Type": "application/json; charset=UTF-8",
                         "X-Upload-Content-Type": "video/mp4",
                         "X-Upload-Content-Length": str(size)},
                timeout=self.client.timeout)
        except Exception as e:      # noqa: BLE001  (requests' errors, without the address)
            raise UploadError(f"YouTube, début de l'envoi : erreur réseau ({type(e).__name__})")
        if r.status_code != 200 or not r.headers.get("Location"):
            raise UploadError("YouTube, début de l'envoi : " + _error(r))
        return r.headers["Location"]

    def _send(self, session: str, path: Path, token: str) -> dict[str, Any]:
        data = path.read_bytes()
        size, offset = len(data), 0
        auth = {"Authorization": f"Bearer {token}"}
        for attempt in range(1, UPLOAD_TRIES + 1):
            try:
                headers = auth | {"Content-Type": "video/mp4"}
                if offset:
                    headers["Content-Range"] = f"bytes {offset}-{size - 1}/{size}"
                r = self.http.put(session, data=data[offset:], headers=headers,
                                  timeout=max(self.client.timeout, 600))
                if r.status_code in (200, 201):
                    return _json(r)
                if r.status_code < 500 and r.status_code != 308:
                    raise UploadError("YouTube, envoi du fichier : " + _error(r))
                why = f"HTTP {r.status_code}"
            except UploadError:
                raise
            except Exception as e:  # noqa: BLE001  (network: ask how much arrived)
                why = f"erreur réseau ({type(e).__name__})"
            if attempt == UPLOAD_TRIES:
                raise UploadError(f"YouTube, envoi du fichier : {why}, {UPLOAD_TRIES} essais")
            print(f"warning: youtube: upload interrupted ({why}), asking how much arrived "
                  f"({attempt}/{UPLOAD_TRIES})", file=sys.stderr)
            self.sleep(UPLOAD_PAUSE * attempt)
            offset, done = self._received(session, size, auth)
            if done is not None:
                return done
        raise UploadError("YouTube, envoi du fichier : inachevé")   # not reached

    def _received(self, session: str, size: int, auth: dict[str, str]
                  ) -> tuple[int, dict[str, Any] | None]:
        """How many bytes YouTube has (HTTP 308 and its Range), or the video when it has all."""
        try:
            r = self.http.put(session, data=b"",
                              headers=auth | {"Content-Range": f"bytes */{size}"},
                              timeout=self.client.timeout)
        except Exception:           # noqa: BLE001  (from the start again)
            return 0, None
        if r.status_code in (200, 201):
            return size, _json(r)
        if r.status_code == 308:
            got = r.headers.get("Range", "")
            return (int(got.rsplit("-", 1)[1]) + 1 if got else 0), None
        if r.status_code == 404:
            raise UploadError("YouTube, envoi du fichier : la session d'envoi a expiré")
        return 0, None

    def _processed(self, vid: str, token: str, status: dict[str, Any]) -> dict[str, Any]:
        """The video's status once YouTube has processed it (or the last one read)."""
        start = self.clock()
        while status.get("uploadStatus") not in (*DONE, *REFUSED) \
                and self.clock() - start < self.process_timeout:
            self.sleep(PROCESS_INTERVAL)
            try:
                items = self.client.get(f"{DATA}/videos", token, part="status",
                                        id=vid).get("items") or []
            except YouTubeError as e:
                print(f"warning: youtube: status of {vid} not read ({e})", file=sys.stderr)
                continue
            if items:
                status = items[0].get("status") or status
        return status


def _json(r: Any) -> dict[str, Any]:
    try:
        body = r.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _error(r: Any) -> str:
    """HTTP status, YouTube's reason and message (quotaExceeded, uploadLimitExceeded…)."""
    err = _json(r).get("error") or {}
    if not isinstance(err, dict):
        return f"HTTP {r.status_code} {err}".strip()
    reasons = ", ".join(sorted({e.get("reason", "") for e in err.get("errors") or []
                                if e.get("reason")}))
    return " ".join(x for x in (f"HTTP {r.status_code}", reasons,
                                str(err.get("message") or "")) if x)


def _signin(message: str) -> str:
    if "invalid_grant" in message:
        return (f"{message} : connexion YouTube perdue (mot de passe Google changé ou accès "
                "retiré) ; la refaire : youtube-login.html → « Mise en ligne », puis le "
                "workflow youtube-auth")
    return message
