"""quran-reels youtube-playlists: the channel's playlists kept by the run (owner's choice, 2026-11-21).

The owner had made the six playlists of docs/profils.md by hand and kept them up to date (14, 8, 6, 4,
4 and 1 videos on 2026-11-21). The run takes them over, by their ids (config/playlists.yaml):

- every YouTube video the nightly statistics know (insights.json, a post « youtube:<id> » with the
  key of its reel or theme video) and published from `since` on (the day he handed them over:
  what he filed before stays as he filed it) goes into its playlists, 1 to 3: a reel by the series
  of its passage (published.json), a theme video by its document (quran-themes-demo), a film apart
  from its shorts where he did so (Moussa and al-Khidr: the film in the stories only);
- a video already in a playlist is left where it is; a new one is added at the end (a playlist
  sorted by date would refuse a position);
- a series or a document without a playlist gets its own, public, created with its first video and
  titled from its validated names, the Arabic first (config/series/*.yaml: title_ar, title_en; the
  first line of publication-<doc>.md); its id is kept in youtube-playlists.json (state branch). One
  he made by hand under those names, in either order, is his: taken over, never made twice;
- the six titles were written English first: each is turned around once, Arabic first (owner's
  choice, 2026-11-21), its description kept as he wrote it; a title he changes later is left alone.

The same step sends the subtitles the daily run left for the videos it uploaded (captions.py:
youtube-captions/ on the state branch), with the same token: only it holds the scope captions need;
and adds to the channel's keywords the Arabic name of a series whose first video is on YouTube
(channel.series_keywords, owner's choice, 2026-11-21).

Access: its own token, YOUTUBE_PLAYLISTS_REFRESH_TOKEN (scope youtube.force-ssl: the only one that
lets playlists be written, and it could also change or delete videos; owner's choice, 2026-11-21),
saved by the workflow youtube-auth from youtube-login.html → Playlists. Only this step reads it,
and it only calls playlists, playlistItems, captions and channels (the keywords). Without it, nothing is done (by hand, as before).
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from quran_reels.insights.youtube import DATA, YouTube, YouTubeError

SCOPES = ("https://www.googleapis.com/auth/youtube.force-ssl",)
CAPTIONS = "https://www.googleapis.com/upload/youtube/v3/captions"
SECRET = "YOUTUBE_PLAYLISTS_REFRESH_TOKEN"
STATE = "youtube-playlists.json"
SEP = " · "
HEADING = re.compile(r"^#\s*(?P<en>.+?)\s+·\s+(?P<ar>.+?)\s*:")


def settings(root: Path) -> dict[str, Any]:
    path = root / "config" / "playlists.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}


def arabic_first(en: str, ar: str) -> str:
    return f"{ar.strip()}{SEP}{en.strip()}"


def swapped(title: str) -> str:
    """« A · B » → « B · A » (a title of two halves); anything else as it is."""
    parts = title.split(SEP)
    return SEP.join(reversed(parts)) if len(parts) == 2 else title


# ------------------------------------------------------------------------------ where a video goes

@dataclass
class Names:
    """Validated names, for a playlist the run creates: series (title_ar, title_en) and theme
    documents (the heading of publication-<doc>.md), read only when needed."""
    series: dict[str, tuple[str, str]] = field(default_factory=dict)
    doc: Callable[[str], tuple[str, str] | None] = lambda doc: None
    _docs: dict[str, tuple[str, str] | None] = field(default_factory=dict)

    def of_doc(self, doc: str) -> tuple[str, str] | None:
        if doc not in self._docs:
            try:
                self._docs[doc] = self.doc(doc)
            except Exception as e:      # noqa: BLE001  (no name: no new playlist this night)
                print(f"warning: playlists: the name of {doc} not read ({type(e).__name__})",
                      file=sys.stderr)
                self._docs[doc] = None
        return self._docs[doc]


def series_names(root: Path) -> dict[str, tuple[str, str]]:
    out = {}
    for path in sorted((root / "config" / "series").glob("*.yaml")):
        d = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if d.get("title_ar") and d.get("title_en"):
            out[path.stem] = (str(d["title_en"]), str(d["title_ar"]))
    return out


def doc_name_online(repo: str, ref: str = "main", folder: str = "docs/retention"
                    ) -> Callable[[str], tuple[str, str] | None]:
    """The (English, Arabic) names of a theme document: the first line of its publication file."""
    def read(doc: str) -> tuple[str, str] | None:
        from quran_reels.sources.http import Http

        r = Http(timeout=30).get(f"https://raw.githubusercontent.com/{repo}/{ref}/{folder}/"
                                 f"publication-{doc}.md")
        r.encoding = "utf-8"
        m = HEADING.match(r.text.splitlines()[0] if r.text else "")
        return (m["en"], m["ar"]) if m else None
    return read


def where(key: str, conf: dict[str, Any], published: dict[str, Any], names: Names
          ) -> list[tuple[str, str | None]]:
    """The playlists of a video, by its statistics key: [(playlist key, title if it must be
    created)]. A key the configuration does not name gets its own playlist when its series or
    document has validated names; nothing otherwise (the Quran in order, an on-demand reel)."""
    kind, _, rest = key.partition(":")
    if kind == "slot":
        item = ((published.get("slots") or {}).get(rest) or {}).get("item") or ""
        group = item.split("/", 1)[0]
        named = (conf.get("series") or {}).get(group)
        found = names.series.get(group)
    elif kind == "hand":
        group, named, found = rest, (conf.get("hand") or {}).get(rest), None
    elif kind == "theme":
        doc, _, part = rest.partition("/")
        group = doc.removesuffix("-9x16")
        named = (conf.get("docs") or {}).get(group)
        if isinstance(named, dict):         # a film apart from the shorts
            named = named.get("film" if part == "film" else "short") or []
        found = None if named is not None else names.of_doc(group)
    else:
        return []
    if named is not None:
        return [(k, None) for k in named]
    if group and found:
        return [(group, arabic_first(*found))]
    return []


def group_of(key: str, published: dict[str, Any]) -> tuple[str, str] | None:
    """("series", the series of a reel's passage) or ("docs", a theme video's document)."""
    kind, _, rest = key.partition(":")
    if kind == "slot":
        item = ((published.get("slots") or {}).get(rest) or {}).get("item") or ""
        return ("series", item.split("/", 1)[0]) if item else None
    if kind == "theme":
        return ("docs", rest.partition("/")[0].removesuffix("-9x16"))
    return None


# ------------------------------------------------------------------------------ the channel

class Channel:
    """The few calls this needs, with the playlists' token. Never prints a token."""

    def __init__(self, client: YouTube, token: str):
        self.client, self.token, self.http = client, token, client.http

    @classmethod
    def from_environ(cls) -> Channel | None:
        cid, secret = os.environ.get("YOUTUBE_CLIENT_ID"), os.environ.get("YOUTUBE_CLIENT_SECRET")
        refresh = os.environ.get(SECRET)
        if not cid or not secret or not refresh:
            return None
        client = YouTube(cid, secret)
        return cls(client, client.access(refresh))

    def _get_all(self, url: str, **params: Any) -> list[dict[str, Any]]:
        out, page = [], None
        while True:
            body = self.client.get(url, self.token, maxResults="50",
                                   **params, **({"pageToken": page} if page else {}))
            out += body.get("items") or []
            page = body.get("nextPageToken")
            if not page:
                return out

    def playlists(self) -> dict[str, dict[str, Any]]:
        return {p["id"]: p.get("snippet") or {} for p in
                self._get_all(f"{DATA}/playlists", part="snippet", mine="true")}

    def items(self, playlist: str) -> list[str]:
        return [(i.get("snippet") or {}).get("resourceId", {}).get("videoId") for i in
                self._get_all(f"{DATA}/playlistItems", part="snippet", playlistId=playlist)]

    def _send(self, method: str, url: str, part: str, body: dict[str, Any]) -> dict[str, Any]:
        r = self.http.request(method, url, params={"part": part}, json=body,
                              headers={"Authorization": f"Bearer {self.token}"},
                              timeout=self.client.timeout)
        try:
            answer = r.json()
        except ValueError:
            answer = {}
        if r.status_code != 200:
            err = answer.get("error") or {}
            raise YouTubeError(f"{method} {url.rsplit('/', 1)[-1]}: HTTP {r.status_code} "
                               f"{err.get('message', '') if isinstance(err, dict) else err}".strip())
        return answer

    def create(self, title: str) -> str:
        return self._send("POST", f"{DATA}/playlists", "snippet,status", {
            "snippet": {"title": title}, "status": {"privacyStatus": "public"}})["id"]

    def rename(self, playlist: str, title: str, snippet: dict[str, Any]) -> None:
        """The title only: the description (and language) sent back as they are, or YouTube
        would clear them."""
        keep = {k: snippet[k] for k in ("description", "defaultLanguage") if snippet.get(k)}
        self._send("PUT", f"{DATA}/playlists", "snippet", {
            "id": playlist, "snippet": {"title": title, **keep}})

    def caption(self, video: str, lang: str, name: str, text: str) -> str:
        """A subtitle track (captions.insert, multipart: its snippet, then the SRT file); its id."""
        boundary = "quran-reels-captions"
        meta = json.dumps({"snippet": {"videoId": video, "language": lang, "name": name,
                                       "isDraft": False}}, ensure_ascii=False)
        body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n"
                f"--{boundary}\r\nContent-Type: application/octet-stream\r\n\r\n{text}\r\n"
                f"--{boundary}--\r\n").encode()
        r = self.http.request("POST", CAPTIONS, params={"part": "snippet",
                                                        "uploadType": "multipart"},
                              data=body, headers={
                                  "Authorization": f"Bearer {self.token}",
                                  "Content-Type": f"multipart/related; boundary={boundary}"},
                              timeout=self.client.timeout)
        try:
            answer = r.json()
        except ValueError:
            answer = {}
        if r.status_code != 200 or "id" not in answer:
            err = answer.get("error") or {}
            raise YouTubeError(f"POST captions: HTTP {r.status_code} "
                               f"{err.get('message', '') if isinstance(err, dict) else err}".strip())
        return answer["id"]

    def add(self, playlist: str, video: str) -> None:
        """At the end (a position is refused by a playlist sorted by date)."""
        self._send("POST", f"{DATA}/playlistItems", "snippet", {"snippet": {
            "playlistId": playlist, "resourceId": {"kind": "youtube#video", "videoId": video}}})


# ------------------------------------------------------------------------------ the night's work

def sync(conf: dict[str, Any], insights: dict[str, Any], published: dict[str, Any],
         state: dict[str, Any], channel: Any, names: Names, dry_run: bool = False) -> list[str]:
    """Rename, create and fill the playlists; `state` gets the ids of the playlists created.
    The lines of what was (or, dry run, would be) done."""
    known = conf.get("playlists") or {}
    ids: dict[str, str] = {k: str(v["id"]) for k, v in known.items() if v.get("id")}
    ids |= {k: v for k, v in (state.get("playlists") or {}).items() if k not in ids}
    since = str(conf.get("since") or "")
    existing = channel.playlists()
    done: list[str] = []

    for k, v in known.items():              # the owner's titles, Arabic first, once
        pid, want = ids.get(k), v.get("title")
        snippet = existing.get(pid or "")
        if not pid or not want:
            continue
        if not snippet:
            done.append(f"warning: playlist {k} ({pid}) not on the channel")
            continue
        current = snippet.get("title", "")
        if current != want and swapped(current) == want:
            done.append(f"rename « {current} » → « {want} »")
            if not dry_run:
                channel.rename(pid, want, snippet)

    posts = {k[len("youtube:"):]: p for k, p in (insights.get("posts") or {}).items()
             if k.startswith("youtube:") and p.get("key")
             and str(p.get("published", ""))[:10] >= since}
    contents: dict[str, list[str]] = {}
    for vid, post in sorted(posts.items(), key=lambda kp: str(kp[1].get("published", ""))):
        for k, title in where(post["key"], conf, published, names):
            pid = ids.get(k)
            if not pid:
                if not title:
                    continue
                # One he made by hand with the same names, in either order: his, taken over
                # (2026-11-21: « We Will Show Them Our Signs · سنريهم آياتنا », made the evening
                # its first Short went out, would have been made a second time).
                mine = next((i for i, sn in existing.items()
                             if sn.get("title", "").strip() in (title, swapped(title))), None)
                if mine:
                    current = existing[mine].get("title", "")
                    done.append(f"take over « {current} » ({k})")
                    pid = mine
                    if not dry_run:
                        state.setdefault("playlists", {})[k] = pid
                    if current != title:
                        done.append(f"rename « {current} » → « {title} »")
                        if not dry_run:
                            channel.rename(pid, title, existing[mine])
                else:
                    done.append(f"create « {title} » ({k})")
                    if dry_run:
                        pid = f"(new {k})"
                    else:
                        pid = channel.create(title)
                        state.setdefault("playlists", {})[k] = pid
                        contents[pid] = []
                ids[k] = pid
                if pid.startswith("(new"):
                    contents[pid] = []
            if pid not in contents:
                contents[pid] = channel.items(pid) if not pid.startswith("(new") else []
            items = contents[pid]
            if vid in items:
                continue
            done.append(f"add {post['key']} ({vid}) → {k}")
            if not dry_run:
                channel.add(pid, vid)
            items.append(vid)
    return done


def run(root: Path, state_dir: Path, dry_run: bool = False, channel: Any = None,
        names: Names | None = None) -> int:
    conf = settings(root)
    if not conf.get("enabled", False):
        print("playlists: off (config/playlists.yaml)")
        return 0
    try:
        channel = channel or Channel.from_environ()
    except YouTubeError as e:
        raise SystemExit(f"YouTube sign-in for the playlists failed: {e}: sign in again "
                         "(youtube-login.html → Playlists, then the workflow youtube-auth)") from None
    if channel is None:
        print(f"playlists: no token ({SECRET}): nothing done, by hand as before")
        return 0

    def read(name: str) -> dict[str, Any]:
        path = state_dir / name
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

    state = read(STATE)
    if names is None:
        themes = conf.get("themes") or {}
        names = Names(series=series_names(root),
                      doc=doc_name_online(themes.get("repo", "mssnoussi92/quran-themes-demo"),
                                          themes.get("ref", "main"),
                                          themes.get("texts", "docs/retention")))
    insights, published = read("insights.json"), read("published.json")
    lines = sync(conf, insights, published, state, channel, names, dry_run)
    from quran_reels import captions  # the reels' subtitles, written by the daily run

    lines += captions.upload_pending(state_dir / captions.DIR, channel, dry_run)
    from quran_reels import channel as settings_of_channel  # a series' name, at its first video

    posts = sorted((p for k, p in (insights.get("posts") or {}).items()
                    if k.startswith("youtube:") and p.get("key")),
                   key=lambda p: str(p.get("published", "")))
    groups = [g for p in posts if (g := group_of(p["key"], published))]
    lines += settings_of_channel.series_keywords(root, groups, channel, names, dry_run)
    for line in lines or ["playlists: nothing to do"]:
        print(line)
    if not dry_run:
        (state_dir / STATE).write_text(json.dumps(state, ensure_ascii=False, indent=1) + "\n",
                                       encoding="utf-8")
    return 0
