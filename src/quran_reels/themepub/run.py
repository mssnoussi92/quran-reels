"""quran-reels themes run|check: the day's theme video on the Page at 18:00 (docs/themes.md).

The video of the day is the row of docs/retention/calendar.md (quran-themes-demo) for today; its
texts are those of publication-<doc>.md, word for word; its files those of the public
pre-release page-<doc> (workflow page-files). Same rule as the reels:

1. Facebook and Instagram get the video unpublished (Facebook: a draft reel up to 90 s, an
   unpublished Page video above, facebook_video.py; Instagram: a container), with its cover.
2. Meta's copyright check is read on both. Anything but clear on one, and nothing goes out,
   TikTok included.
3. Facebook and Instagram are published; TikTok gets its own version (signed
   @quran.words.daily) as a draft in the inbox.
4. YouTube (owner's choice, 2026-11-21; by hand before): its video goes up, public, with its
   validated title and description and its thumbnail (publishers/youtube.py), once Meta's check
   was clear: the same file for a short (or its short version), and for a 16:9 film the check of
   its 9:16 twin, same voice, recitation and ambience (the owner's decision: Meta checks reels,
   vertical ones). A video of the same title already on the channel (uploaded by hand) is not
   put again. Never on a dry run. The « related video » of a Short, which the API does not
   offer, stays by hand.

A platform already done for the day (themes.json, branch `state`) is never sent again; one that
failed before anything reached it is tried again by the next run of the window. A day may have
several rows on platforms of their own (themepub/calendar.py): each goes out in the same run, and
the day's entry of themes.json holds every platform's result. A dry run
uploads, reads the checks, deletes the Facebook copy and records nothing; it never sends
TikTok a draft (it would land in the owner's inbox).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from quran_reels.config import Config
from quran_reels.models import PublishResult, PublishStatus
from quran_reels.publishers.base import PublisherError
from quran_reels.themepub import calendar as cal
from quran_reels.themepub import texts as texts_mod

PARIS = ZoneInfo("Europe/Paris")
META = ("facebook", "instagram")
DONE = {"published", "draft", "blocked", "removed", "ready"}
HASHTAG = re.compile(r"#[^\s#]+")


def settings(cfg: Config, path: Path | None = None) -> dict[str, Any]:
    """config/themes.yaml, the Page's; or another page's own (`--settings`: config/themes-ma3ak.yaml,
    the test page « معاك 5 ثواني », its calendar, its time, its platforms; 2026-11-19)."""
    path = path or cfg.root / "config" / "themes.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}


@dataclass
class ThemeReel:
    """What a publisher needs of a theme video, for one platform: its file and its text,
    validated, as they are (no hashtag is cut or added: the text already has the platform's)."""
    video: Path
    caption: str
    title: str = ""
    seconds: float | None = None
    cover_image: Path | None = None       # Facebook: the cover file
    cover_url: str | None = None          # Instagram: the same, by its public address
    cover_ms: int | None = None
    video_url: str | None = None          # Instagram: the file by its public address
    hashtags: list[str] = field(default_factory=list)
    facebook: str = ""
    variants: dict = field(default_factory=dict)

    def for_platform(self, platform: str) -> ThemeReel:
        return self

    def text(self, max_hashtags: int | None = None) -> str:
        return self.caption

    def text_for(self, platform: str, max_hashtags: int | None = None) -> str:
        return self.caption


# ------------------------------------------------------------------------------ sources


@dataclass
class Sources:
    videos: dict[str, texts_mod.Video]
    rows: list[cal.Row]


def fetch(s: dict[str, Any], today: date, get_text: Callable[[str], str] | None = None,
          list_dir: Callable[[str], list[str]] | None = None) -> Sources:
    """The calendar and every publication text of quran-themes-demo (its `ref`, main)."""
    repo, ref = s["repo"], s.get("ref", "main")
    if get_text is None or list_dir is None:
        from quran_reels.sources.http import Http

        http = Http(timeout=30)
        token = os.environ.get("GITHUB_TOKEN")

        def get_text(url: str) -> str:
            r = http.get(url)
            r.encoding = "utf-8"
            return r.text

        def list_dir(path: str) -> list[str]:
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            r = http.session.get(f"https://api.github.com/repos/{repo}/contents/{path}",
                                 params={"ref": ref}, headers=headers, timeout=30)
            r.raise_for_status()
            return [i["name"] for i in r.json() if i.get("type") == "file"]

    raw = f"https://raw.githubusercontent.com/{repo}/{ref}"
    folder = s.get("texts", "docs/retention").rstrip("/")
    videos: dict[str, texts_mod.Video] = {}
    for name in sorted(list_dir(folder)):
        if name.startswith("publication-") and name.endswith(".md"):
            doc = name[len("publication-"):-3]
            videos |= texts_mod.parse(doc, get_text(f"{raw}/{folder}/{name}"))
    rows = cal.rows(get_text(f"{raw}/{s['calendar']}"), today)
    wanted = [p for p in s.get("platforms", ["facebook", "instagram", "tiktok"])]
    for row in rows:
        cal.resolve(row, videos, wanted)
    return Sources(videos, rows)


def asset_url(s: dict[str, Any], doc: str, name: str) -> str:
    return (f"https://github.com/{s['repo']}/releases/download/"
            f"{s.get('release_prefix', 'page-')}{doc}/{name}")


# ------------------------------------------------------------------------------ state


def load_state(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() and \
        path.read_text(encoding="utf-8").strip() else {}
    data.setdefault("posts", {})
    return data


def save_state(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def done(result: dict | None) -> bool:
    """Not to be sent again: it went out, or it may have (a failure with an id)."""
    return bool(result) and (result.get("status") in DONE or bool(result.get("remote_id")))


def time_for(s: dict[str, Any], day: date) -> str:
    """The theme video's hour that day, Paris time: `time`, or the last of `times` whose `from`
    has come (owner's choice, 2026-11-21: 13:00 from 2026-11-27, 18:00 before)."""
    at = str(s.get("time", "19:00"))
    for change in sorted(s.get("times") or [], key=lambda c: str(c["from"])):
        if date.fromisoformat(str(change["from"])) <= day:
            at = str(change["time"])
    return at


def slot(s: dict[str, Any], day: date) -> datetime:
    hh, mm = (int(x) for x in time_for(s, day).split(":"))
    return datetime.combine(day, time(hh, mm), PARIS)


def due(s: dict[str, Any], state: dict, src: Sources, now: datetime) -> cal.Row | None:
    """Today's first row due (due_rows), or None."""
    rows = due_rows(s, state, src, now)
    return rows[0] if rows else None


def due_rows(s: dict[str, Any], state: dict, src: Sources, now: datetime) -> list[cal.Row]:
    """Today's rows if their time has come (from early_minutes before, for window_hours) and a
    platform of theirs is still to do (or they have a problem to report), in the table's order."""
    if not s.get("enabled", True):
        return []
    today = now.astimezone(PARIS).date()
    first = date.fromisoformat(str(s.get("from"))) if s.get("from") else today
    if today < first:
        return []
    at = slot(s, today)
    start = at - timedelta(minutes=float(s.get("early_minutes", 20)))
    end = at + timedelta(hours=float(s.get("window_hours", 3)))
    if not start <= now.astimezone(PARIS) <= end:
        return []
    results = (state["posts"].get(today.isoformat()) or {}).get("results") or {}
    return [r for r in src.rows if r.day == today and not r.published
            and (r.problems or any(not done(results.get(p)) for p in r.videos))]


# ------------------------------------------------------------------------------ publishing


def _download(s: dict[str, Any], doc: str, name: str, folder: Path) -> Path:
    from quran_reels.sources.http import Http

    dest = folder / doc / name
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    return Http(timeout=600).download(asset_url(s, doc, name), dest, min_bytes=1000)


def for_instagram(video: Path) -> Path:
    """The video encoded as the daily reels are for Instagram (docs/rendu.md): H.264 High without
    B-frames, AAC 48 kHz, faststart, no edit list. The theme videos (Remotion) carry edit lists:
    Instagram never finished processing a 2-minute short (still IN_PROGRESS after 20 min, dry run
    of 2026-11-15), as it refused the reels' edit lists before. Picture and sound are re-encoded,
    nothing else changes."""
    dest = video.with_name(video.stem + "-instagram.mp4")
    if dest.is_file() and dest.stat().st_size > 0 and dest.stat().st_mtime >= video.stat().st_mtime:
        return dest
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(video),
                    "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-preset", "medium",
                    "-crf", "20", "-maxrate", "6M", "-bufsize", "12M", "-profile:v", "high",
                    "-pix_fmt", "yuv420p", "-bf", "0", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                    "-movflags", "+faststart", "-use_editlist", "0", str(dest)], check=True)
    return dest


def host(path: Path) -> str:
    """The public address of a file in the release `reels` (ondemand/files.py: public, 30 days).
    Instagram fetches a theme video from there (`video_url`): sent to its upload address, a
    2-minute short failed at once (ProcessingFailedError) and its container never left
    IN_PROGRESS, four times on 2026-11-15, re-encoded or not."""
    from quran_reels.ondemand.files import Hosting
    from quran_reels.ondemand.gh import GitHub

    return Hosting(GitHub(), Path(".")).upload(path, path.name)


def reels_for(s: dict[str, Any], row: cal.Row, folder: Path,
              download: Callable[..., Path] = _download,
              encode: Callable[[Path], Path] = for_instagram,
              publish_file: Callable[[Path], str] = host) -> dict[str, ThemeReel]:
    """Each platform's file and text, downloaded from page-<doc> (Instagram: its own encoding,
    fetched by Instagram from the release `reels`). Facebook and Instagram take the short version
    when the line of files names one (`cut`, owner's trial from 2026-11-24); same texts."""
    out = {}
    for platform, v in row.videos.items():
        if platform == "youtube":
            out[platform] = youtube_reel(s, v, folder, download)
            continue
        name, seconds = file_for(platform, v)
        cover = download(s, v.doc, v.cover, folder) if v.cover and platform != "tiktok" else None
        video = download(s, v.doc, name, folder)
        if platform == "instagram":
            video = encode(video)
        out[platform] = ThemeReel(
            video=video, video_url=publish_file(video) if platform == "instagram" else None,
            caption=v.captions[platform],
            title=v.title, seconds=seconds, cover_image=cover,
            cover_url=asset_url(s, v.doc, v.cover) if v.cover else None)
    return out


def youtube_reel(s: dict[str, Any], v: texts_mod.Video, folder: Path,
                 download: Callable[..., Path] = _download) -> ThemeReel:
    """What YouTube gets: its file (the short, its short version, or the 16:9 film), its
    validated title, its description followed by its hashtags, the hashtags as tags, and its
    thumbnail (the film's drawn one, or the short's cover). Never the credits card (owner's
    choice, 2026-11-21: « je ne veux pas que les crédits passent dans la description »); every
    citation has its reference on screen, and the CC BY images their credit on the image."""
    name, seconds = file_for("youtube", v)
    image = v.thumbnail or v.cover
    cards = v.cards.get("youtube") or []
    description = ("\n\n".join(t.strip() for kind, t in cards
                                if kind in ("description", "hashtags") and t.strip())
                   if cards else (v.captions.get("youtube_description") or "").strip())
    return ThemeReel(video=download(s, v.doc, name, folder),
                     caption=description + "\n" if description else "",
                     title=(v.captions.get("youtube_title") or "").strip(), seconds=seconds,
                     cover_image=download(s, v.doc, image, folder) if image else None,
                     hashtags=list(dict.fromkeys(HASHTAG.findall(description))))


# YouTube too since 2026-11-18 (owner's choice, after the first numbers: on YouTube a theme short
# had 279 views against 904 for a reel, watched to 47 % against 105 %): by hand, from the page
# publier.html, which gives it this file.
CUT_PLATFORMS = ("facebook", "instagram", "youtube")


def file_for(platform: str, v: texts_mod.Video) -> tuple[str, float | None]:
    """The file a platform gets, and its length: TikTok its signed version; Facebook, Instagram
    and YouTube the short version when there is one; the short itself otherwise."""
    if platform == "tiktok":
        return v.tiktok, v.seconds
    if platform in CUT_PLATFORMS and v.cut:
        return v.cut, v.cut_seconds or v.seconds
    return v.video, v.seconds


def publishers_for(cfg: Config, s: dict[str, Any], row: cal.Row, platforms: list[str]) -> dict:
    """The publishers, built only for the platforms to do (no Meta token check without Meta)."""
    from quran_reels import publish as publish_mod
    from quran_reels.publishers.facebook_video import FacebookVideoPublisher

    out: dict = {}
    meta = [p for p in platforms if p in META]
    if meta:
        graph, env, token = publish_mod.meta_check(cfg, meta)
        print(token.summary(), file=sys.stderr)
        out = publish_mod.meta_publishers(cfg, graph, env, meta)
        if "instagram" in out:      # longer than a daily reel: one container, waited for longer
            wait = float(s.get("instagram_processing_seconds", 1200))
            ig = out["instagram"]
            ig.timeout, ig.stuck_after, ig.attempts = wait, wait, 1
        fb = row.videos.get("facebook")
        if "facebook" in out and fb and (file_for("facebook", fb)[1] or 0) > float(
                s.get("reels_max_seconds", 90)):
            out["facebook"] = FacebookVideoPublisher(
                graph, env.page_id, rights_timeout=out["facebook"].rights_timeout)
    if "tiktok" in platforms:
        out["tiktok"] = publish_mod.tiktok_publisher()
    if "youtube" in platforms:
        from quran_reels.publishers import youtube as youtube_mod

        out["youtube"] = youtube_mod.Uploader.from_environ()     # None: not signed in for it
    return out


def to_youtube(s: dict[str, Any], uploader: Any, reel: ThemeReel, checks: dict, blocked: dict,
               reason: str, previous: dict, dry_run: bool, film: bool) -> PublishResult | None:
    """YouTube's answer for the row, or None: Meta's check has not seen the video yet (its upload
    failed), a later run of the window will try. Never raises: the others are out."""
    from quran_reels.publishers import youtube as youtube_mod

    if dry_run:
        return PublishResult("youtube", PublishStatus.CANCELLED,
                             error="essai à blanc : rien sur YouTube")
    earlier = [p for p in META if (previous.get(p) or {}).get("status") == "blocked"]
    if blocked or earlier:
        why = reason or "; ".join(f"{p} : {(previous[p] or {}).get('error') or 'bloqué'}"
                                  for p in earlier)
        return PublishResult("youtube", PublishStatus.BLOCKED, error=f"non envoyé, droits : {why}")
    seen = any(c.clear for c in checks.values()) or any(
        (previous.get(p) or {}).get("status") == PublishStatus.PUBLISHED.value for p in META)
    if not seen:
        print("youtube: waits for Meta's check of the video (no clear check yet)",
              file=sys.stderr)
        return None
    if uploader is None:
        return PublishResult("youtube", PublishStatus.FAILED,
                             error="pas de jeton de mise en ligne YouTube "
                                   f"({youtube_mod.UPLOAD_SECRET})")
    if not reel.title or not reel.caption.strip():
        return PublishResult("youtube", PublishStatus.FAILED,
                             error="titre ou description YouTube absent du texte validé")
    conf = s.get("youtube") or {}
    video = youtube_mod.Video(
        path=reel.video, title=reel.title, description=reel.caption,
        tags=youtube_mod.tags_of(reel.hashtags), category=conf.get("category"),
        privacy=str(conf.get("privacy", "public")),
        made_for_kids=bool(conf.get("made_for_kids", False)),
        synthetic_media=bool(conf.get("synthetic_media", False)), long=film,
        language=conf.get("language"))
    print(f"youtube: uploading {reel.video.name} ({video.privacy})", file=sys.stderr)
    try:
        return uploader.upload(video, thumbnail=reel.cover_image, dedupe=True)
    except Exception as e:          # noqa: BLE001
        return PublishResult("youtube", PublishStatus.FAILED, error=f"{type(e).__name__}: {e}")


def publish_row(row: cal.Row, reels: dict[str, ThemeReel], publishers: dict, platforms: list[str],
                dry_run: bool, s: dict[str, Any] | None = None,
                previous: dict | None = None) -> dict[str, PublishResult]:
    from quran_reels.publish import check_rights  # imported here, as in publishers_for

    results: dict[str, PublishResult] = {}
    prepared: dict[str, str] = {}
    for name in (p for p in platforms if p in META):
        print(f"{name}: uploading {reels[name].video.name} unpublished "
              f"({reels[name].seconds or '?'} s)", file=sys.stderr)
        try:
            prepared[name] = publishers[name].prepare(reels[name])
        except (PublisherError, KeyError) as e:
            results[name] = PublishResult(name, PublishStatus.FAILED, error=str(e))
            print(f"{name}: failed {e}", file=sys.stderr)
    checks = {}
    for n, i in list(prepared.items()):
        prepared[n], checks[n] = check_rights(publishers[n], n, i, reels[n])
    for n, c in checks.items():
        print(f"{n}: rights check {c.status} after {c.seconds:.0f} s: {c.describe()}",
              file=sys.stderr)
    blocked = {n: c for n, c in checks.items() if not c.clear}
    reason = "; ".join(f"{n} : {c.describe()}" for n, c in blocked.items())
    for name in platforms:
        if name in results:
            continue
        if name in prepared:
            if dry_run:
                status = PublishStatus.DRAFT if name == "facebook" else PublishStatus.READY
                results[name] = PublishResult(name, status, remote_id=prepared[name])
            elif blocked:
                results[name] = PublishResult(name, PublishStatus.BLOCKED,
                                              remote_id=prepared[name],
                                              error=f"droits : {reason} — non publié")
            else:
                results[name] = publishers[name].commit(prepared[name], reels[name])
            results[name].rights = checks[name].as_dict()
        elif name == "youtube":
            v = row.videos.get("youtube")
            answer = to_youtube(s or {}, publishers.get("youtube"), reels[name], checks, blocked,
                                reason, previous or {}, dry_run,
                                film=bool(v and v.aspect == "16:9"))
            if answer is None:
                continue
            results[name] = answer
        elif name == "tiktok":
            if dry_run:
                results[name] = PublishResult(name, PublishStatus.CANCELLED,
                                              error="essai à blanc : pas de brouillon TikTok")
            elif blocked:
                results[name] = PublishResult(name, PublishStatus.BLOCKED,
                                              error=f"non envoyé, droits : {reason}")
            else:
                print(f"tiktok: uploading {reels[name].video.name} to the inbox", file=sys.stderr)
                results[name] = publishers[name].publish(reels[name])
        r = results[name]
        print(f"{name}: {r.status.value} {r.remote_id or ''} {r.url or ''} {r.error or ''}"
              .rstrip(), file=sys.stderr)
    if dry_run and "facebook" in prepared:
        cover = getattr(publishers["facebook"], "cover", None)
        if cover:                          # on the draft: does the token allow it?
            cover(prepared["facebook"], reels["facebook"])
        try:
            publishers["facebook"].remove(prepared["facebook"])
            print(f"facebook: dry run, unpublished copy {prepared['facebook']} deleted",
                  file=sys.stderr)
        except Exception as e:             # noqa: BLE001  (a leftover copy is harmless)
            print(f"warning: facebook copy {prepared['facebook']} not deleted: {e}",
                  file=sys.stderr)
    return results


# ------------------------------------------------------------------------------ the run


def youtube_video(row: cal.Row, videos: dict[str, texts_mod.Video]) -> texts_mod.Video | None:
    """The video YouTube gets that day: the short itself (or its short version), or the 16:9
    film; the one the run uploads when YouTube is among its platforms."""
    if "youtube" not in row.platforms:
        return None
    if "youtube" in row.videos:
        return row.videos["youtube"]
    return next((videos[f"{d}/{row.part}"] for d in row.docs
                 if f"{d}/{row.part}" in videos and "youtube" in videos[f"{d}/{row.part}"].platforms),
                None)


def _item(s: dict[str, Any], row: cal.Row, entry: dict,
          yt: texts_mod.Video | None = None) -> dict:
    """The day as the captions issue shows it (notify.merge_captions): the TikTok text to paste
    on the draft, the TikTok file, and what YouTube gets by hand."""
    v = row.videos.get("tiktok") or next(iter(row.videos.values()), None)
    results = {p: r for p, r in (entry.get("results") or {}).items() if p in row.platforms}
    notes = []
    done_yt = (results.get("youtube") or {})
    texts = youtube_texts(s, yt)
    if done_yt.get("status") == "published":
        link = (f"[mise en ligne par le run]({done_yt['url']})" if done_yt.get("url")
                else "mise en ligne par le run")
        notes = ["", f"**YouTube : {link}**. Rien à faire"
                 + (f" ({done_yt['error']})." if done_yt.get("error") else ".")
                 + (" Sur un Short, la « vidéo associée » (le film) se met à la main dans Studio."
                    if yt and yt.aspect != "16:9" else "")]
        if texts:
            texts["url"] = done_yt.get("url") or ""
    elif yt and yt.video:
        title = (yt.captions.get("youtube_title") or "").strip()
        why = (f"**YouTube : la mise en ligne par le run n'a pas abouti** "
               f"({done_yt.get('error') or done_yt.get('status')}) ; à la main : "
               if done_yt else "**YouTube (à la main)** : ")
        notes = ["", why
                 + f"[ce MP4]({asset_url(s, yt.doc, file_for('youtube', yt)[0])})"
                 + (f" · titre : `{title}`" if title else "")
                 + " · description : la page « À publier »."]
    tiktok = row.videos.get("tiktok")
    return {"key": item_key(row), "day": row.day.isoformat(),
            "time": time_for(s, row.day), "passage": row.label,
            "label": v.title if v else "", "results": results,
            "caption": tiktok.captions.get("tiktok", "") if tiktok else "",
            "files": {"mp4": asset_url(s, tiktok.doc, tiktok.tiktok)} if tiktok else None,
            "notes": notes, "youtube": texts, "match": match_keys(row)}


def item_key(row: cal.Row) -> str:
    """The day's video in the captions issue and on the page publier.html: « theme:<day> »; the
    second video of a day « theme:<day>-2 »."""
    return f"theme:{row.day.isoformat()}" + (f"-{row.n}" if row.n > 1 else "")


def youtube_texts(s: dict[str, Any], yt: texts_mod.Video | None) -> dict[str, str] | None:
    """What the page publier.html gives for YouTube: the file and its thumbnail (a film's, or a
    short's cover), then its title, description, credits and hashtags, word for word, each with
    its own Copy button (owner's request, 2026-11-19: the credits apart from the description)."""
    if not yt or not yt.video:
        return None
    parts = yt.cards.get("youtube") or []

    def joined(*kinds: str) -> str:
        return "\n\n".join(t for kind, t in parts if kind in kinds and t)

    image = yt.thumbnail or yt.cover
    return {"title": (yt.captions.get("youtube_title") or "").strip(),
            "description": joined("description") if parts
            else (yt.captions.get("youtube_description") or "").strip(),
            "credits": joined("crédits"), "hashtags": joined("hashtags"),
            "file": asset_url(s, yt.doc, file_for("youtube", yt)[0]),
            "thumbnail": asset_url(s, yt.doc, image) if image else ""}


def match_keys(row: cal.Row) -> list[str]:
    """The keys the statistics give this video (insights: theme:<doc>/<part>, a 16:9 film
    beside its 9:16 version), so that the page sees it on YouTube."""
    keys = [f"theme:{d}/{row.part}" for d in row.docs if row.part]
    if row.part == "film":
        keys += [f"theme:{d}-9x16/film" for d in row.docs if not d.endswith("-9x16")]
    return list(dict.fromkeys(keys))


def page_files(report_path: Path, hosting: Any = None, now: datetime | None = None) -> int:
    """After `themes run`: the day's video on the page publier.html (feed.py), as
    theme/<day>/reel.json on the branch `previews`, with the TikTok text of its draft and
    what YouTube gets by hand. Nothing for a dry run or a video that went nowhere. Never
    fails the run."""
    from quran_reels import feed
    from quran_reels.ondemand.flow import _RESULT_LABELS
    from quran_reels.ondemand.page import PLATFORM_LABELS

    if not report_path.is_file():
        return 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("dry_run"):
        return 0
    created = (now or datetime.now(UTC)).isoformat(timespec="seconds")
    files: dict[str, str] = {}
    for item in report.get("items") or []:
        results = item.get("results") or {}
        if not any((r or {}).get("status") in ("published", "draft") for r in results.values()):
            continue
        rid = "theme/" + str(item.get("key") or f"theme:{item['day']}").split(":", 1)[1]
        files[f"{rid}/reel.json"] = json.dumps({
            "kind": "theme", "id": rid, "created": created, "key": item["key"],
            "day": item["day"], "time": item.get("time", ""),
            "title": item.get("label") or item.get("passage", ""),
            "passage": item.get("passage", ""), "label": item.get("label", ""),
            "results": [{"name": PLATFORM_LABELS.get(p, p).split(" (")[0],
                         "url": (r or {}).get("url"),
                         "label": _RESULT_LABELS.get((r or {}).get("status"),
                                                     (r or {}).get("status"))}
                        for p, r in results.items()],
            "tiktok": item.get("caption", ""),
            "video": {"tiktok": (item.get("files") or {}).get("mp4")},
            "youtube": item.get("youtube"), "match": item.get("match") or [], "notes": [],
        }, ensure_ascii=False, indent=1)
    if not files:
        return 0
    try:
        if hosting is None:
            from quran_reels.ondemand.files import Hosting
            from quran_reels.ondemand.gh import GitHub

            hosting = Hosting(GitHub(), Path("."))
        hosting.publish(files, f"Vidéo thématique {', '.join(sorted(files))}",
                        derived=feed.files)
    except Exception as e:          # noqa: BLE001  (the page waits for the next one)
        print(f"warning: previews branch: {type(e).__name__}: {e}", file=sys.stderr)
    return 0


def run(cfg: Config, state_path: Path, now: datetime | None = None, dry_run: bool = False,
        day: date | None = None, platforms: list[str] | None = None, check: bool = False,
        src: Sources | None = None, make_publishers: Callable | None = None,
        download: Callable[..., Path] = _download, report: Path | None = None,
        encode: Callable[[Path], Path] = for_instagram,
        publish_file: Callable[[Path], str] = host,
        settings_path: Path | None = None) -> dict[str, Any]:
    s = settings(cfg, settings_path) if settings_path else settings(cfg)
    now = now or datetime.now(UTC)
    state = load_state(state_path)
    today = (day or now.astimezone(PARIS).date())
    src = src or fetch(s, today)
    if day is not None:                    # a chosen day (dry run): its rows, whatever the time
        rows = [r for r in src.rows if r.day == day]
    else:
        rows = due_rows(s, state, src, now)
    out: dict[str, Any] = {"due": bool(rows), "dry_run": dry_run, "items": [], "notes": []}
    if not rows or check:
        for row in rows:
            print(f"{row.day}: {row.label} — due", file=sys.stderr)
        if not rows:
            print(f"{now.astimezone(PARIS):%Y-%m-%d %H:%M} Paris: no theme video due",
                  file=sys.stderr)
        return out
    failed: list[str] = []
    problems: list[str] = []
    for row in rows:
        print(f"{row.day}: {row.label} → " + ", ".join(f"{p} {v.id}" for p, v in row.videos.items()),
              file=sys.stderr)
        if row.problems:
            problems += row.problems
            out["notes"].append(f"Vidéo thématique du {row.day:%d/%m} ({row.label}) non publiée : "
                                + " ; ".join(row.problems))
        entry = state["posts"].get(row.day.isoformat()) or {}
        previous = entry.get("results") or {}
        wanted = [p for p in (platforms or s.get("platforms", ["facebook", "instagram", "tiktok"]))
                  if p in row.videos and (dry_run or not done(previous.get(p)))]
        if wanted:
            reels = reels_for(s, row, cfg.out / "themes", download, encode, publish_file)
            pubs = (make_publishers or publishers_for)(cfg, s, row, wanted)
            results = publish_row(row, reels, pubs, wanted, dry_run, s, previous)
            # The day's entry, every row's platforms together (one video a day per platform).
            cut = (entry.get("cut") or {}) | {p: v.cut for p, v in row.videos.items()
                                               if p in CUT_PLATFORMS and v.cut}
            entry = {"label": entry.get("label") or row.label,
                     "videos": (entry.get("videos") or {}) | {p: v.id for p, v in row.videos.items()},
                     "at": now.isoformat(timespec="seconds"), **({"cut": cut} if cut else {}),
                     "results": previous | {n: asdict(r) | {"status": r.status.value}
                                            for n, r in results.items()}}
            if not dry_run:
                state["posts"][row.day.isoformat()] = entry
                save_state(state_path, state)
        out["items"].append(_item(s, row, entry, youtube_video(row, src.videos)))
        failed += [p for p, r in (entry.get("results") or {}).items()
                   if p in row.videos and r.get("status") in ("failed", "blocked")]
    if problems:
        out["problems"] = problems
    out["failed"] = failed or bool(problems)
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str),
                          encoding="utf-8")
    return out


def check_upcoming(cfg: Config, days: int = 14, today: date | None = None,
                   src: Sources | None = None, exists: Callable[[str], bool] | None = None,
                   settings_path: Path | None = None) -> tuple[list[str], list[str]]:
    """The next days' theme videos, and what would stop one: a row not tied to a video, a file
    page-<doc> does not hold. (lines to print, problems)"""
    s = settings(cfg, settings_path) if settings_path else settings(cfg)
    today = today or datetime.now(PARIS).date()
    src = src or fetch(s, today)
    if exists is None:
        import requests

        def exists(url: str) -> bool:
            # One byte, by GET: a release file redirects to a storage address signed for GET only,
            # which answers HEAD with 401 (2026-11-15: every file of page-* read as missing).
            try:
                with requests.get(url, headers={"Range": "bytes=0-0"}, allow_redirects=True,
                                  stream=True, timeout=30) as r:
                    return r.status_code in (200, 206)
            except requests.RequestException:
                return False
    first = date.fromisoformat(str(s.get("from"))) if s.get("from") else today
    lines, problems = [], []
    for row in src.rows:
        if not today <= row.day < today + timedelta(days=days) or row.published:
            continue
        auto = row.day >= first
        if row.todo:
            lines.append(f"{row.day} {row.label} : à faire")
            if auto:
                problems.append(f"{row.day} : rien à publier (« à faire »)")
            continue
        missing = []
        for platform, v in row.videos.items():
            names = [file_for(platform, v)[0]]
            if v.cover and platform != "tiktok":
                names.append(v.cover)
            missing += [n for n in names if not exists(asset_url(s, v.doc, n))]
        what = ", ".join(f"{p} {v.id}" for p, v in row.videos.items())
        lines.append(f"{row.day} {row.label} → {what}"
                     + ("" if auto else " (publiée à la main)")
                     + (f" — MANQUE : {', '.join(sorted(set(missing)))}" if missing else "")
                     + (f" — {'; '.join(row.problems)}" if row.problems else ""))
        if auto and (missing or row.problems):
            problems.append(f"{row.day} : " + "; ".join(
                ([f"fichiers absents de page-* : {', '.join(sorted(set(missing)))}"]
                 if missing else []) + row.problems))
    return lines, problems
