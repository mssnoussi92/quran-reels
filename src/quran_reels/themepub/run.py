"""quran-reels themes run|check: the day's theme video on the Page at 19:00 (docs/themes.md).

The video of the day is the row of docs/retention/calendar.md (quran-themes-demo) for today; its
texts are those of publication-<doc>.md, word for word; its files those of the public
pre-release page-<doc> (workflow page-files). Same rule as the reels:

1. Facebook and Instagram get the video unpublished (Facebook: a draft reel up to 90 s, an
   unpublished Page video above, facebook_video.py; Instagram: a container), with its cover.
2. Meta's copyright check is read on both. Anything but clear on one, and nothing goes out,
   TikTok included.
3. Facebook and Instagram are published; TikTok gets its own version (signed
   @quran.words.daily) as a draft in the inbox; YouTube stays by hand (the captions issue
   gives the file and the title).

A platform already done for the day (themes.json, branch `state`) is never sent again; one that
failed before anything reached it is tried again by the next run of the window. A dry run
uploads, reads the checks, deletes the Facebook copy and records nothing; it never sends
TikTok a draft (it would land in the owner's inbox).
"""

from __future__ import annotations

import json
import os
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


def settings(cfg: Config) -> dict[str, Any]:
    path = cfg.root / "config" / "themes.yaml"
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


def slot(s: dict[str, Any], day: date) -> datetime:
    hh, mm = (int(x) for x in str(s.get("time", "19:00")).split(":"))
    return datetime.combine(day, time(hh, mm), PARIS)


def due(s: dict[str, Any], state: dict, src: Sources, now: datetime) -> cal.Row | None:
    """Today's row if its time has come (from early_minutes before, for window_hours) and a
    platform of it is still to do; None otherwise."""
    if not s.get("enabled", True):
        return None
    today = now.astimezone(PARIS).date()
    first = date.fromisoformat(str(s.get("from"))) if s.get("from") else today
    if today < first:
        return None
    at = slot(s, today)
    start = at - timedelta(minutes=float(s.get("early_minutes", 20)))
    end = at + timedelta(hours=float(s.get("window_hours", 3)))
    if not start <= now.astimezone(PARIS) <= end:
        return None
    row = next((r for r in src.rows if r.day == today and not r.published), None)
    if row is None:
        return None
    results = (state["posts"].get(today.isoformat()) or {}).get("results") or {}
    if row.problems or any(not done(results.get(p)) for p in row.videos):
        return row
    return None


# ------------------------------------------------------------------------------ publishing


def _download(s: dict[str, Any], doc: str, name: str, folder: Path) -> Path:
    from quran_reels.sources.http import Http

    dest = folder / doc / name
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    return Http(timeout=600).download(asset_url(s, doc, name), dest, min_bytes=1000)


def reels_for(s: dict[str, Any], row: cal.Row, folder: Path,
              download: Callable[..., Path] = _download) -> dict[str, ThemeReel]:
    """Each platform's file and text, downloaded from page-<doc>."""
    out = {}
    for platform, v in row.videos.items():
        name = v.tiktok if platform == "tiktok" else v.video
        cover = download(s, v.doc, v.cover, folder) if v.cover and platform != "tiktok" else None
        out[platform] = ThemeReel(
            video=download(s, v.doc, name, folder), caption=v.captions[platform],
            title=v.title, seconds=v.seconds, cover_image=cover,
            cover_url=asset_url(s, v.doc, v.cover) if v.cover else None)
    return out


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
        fb = row.videos.get("facebook")
        if "facebook" in out and fb and (fb.seconds or 0) > float(s.get("reels_max_seconds", 90)):
            out["facebook"] = FacebookVideoPublisher(
                graph, env.page_id, rights_timeout=out["facebook"].rights_timeout)
    if "tiktok" in platforms:
        out["tiktok"] = publish_mod.tiktok_publisher()
    return out


def publish_row(row: cal.Row, reels: dict[str, ThemeReel], publishers: dict, platforms: list[str],
                dry_run: bool) -> dict[str, PublishResult]:
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
    checks = {n: publishers[n].rights(i) for n, i in prepared.items()}
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
    """The video YouTube gets that day, by hand: the short itself, or the 16:9 film."""
    if "youtube" not in row.platforms:
        return None
    return next((videos[f"{d}/{row.part}"] for d in row.docs
                 if f"{d}/{row.part}" in videos and "youtube" in videos[f"{d}/{row.part}"].platforms),
                None)


def _item(s: dict[str, Any], row: cal.Row, entry: dict,
          yt: texts_mod.Video | None = None) -> dict:
    """The day as the captions issue shows it (notify.merge_captions): the TikTok text to paste
    on the draft, the TikTok file, and what YouTube gets by hand."""
    v = row.videos.get("tiktok") or next(iter(row.videos.values()), None)
    notes = []
    if yt and yt.video:
        title = (yt.captions.get("youtube_title") or "").strip()
        notes = ["", f"**YouTube (à la main)** : [ce MP4]({asset_url(s, yt.doc, yt.video)})"
                 + (f" · titre : `{title}`" if title else "")
                 + " · description : ta page « Films et shorts à publier »."]
    tiktok = row.videos.get("tiktok")
    return {"key": f"theme:{row.day.isoformat()}", "day": row.day.isoformat(),
            "time": s.get("time", "19:00"), "passage": row.label,
            "label": v.title if v else "", "results": entry.get("results") or {},
            "caption": tiktok.captions.get("tiktok", "") if tiktok else "",
            "files": {"mp4": asset_url(s, tiktok.doc, tiktok.tiktok)} if tiktok else None,
            "notes": notes}


def run(cfg: Config, state_path: Path, now: datetime | None = None, dry_run: bool = False,
        day: date | None = None, platforms: list[str] | None = None, check: bool = False,
        src: Sources | None = None, make_publishers: Callable | None = None,
        download: Callable[..., Path] = _download, report: Path | None = None) -> dict[str, Any]:
    s = settings(cfg)
    now = now or datetime.now(UTC)
    state = load_state(state_path)
    today = (day or now.astimezone(PARIS).date())
    src = src or fetch(s, today)
    if day is not None:                    # a chosen day (dry run): its row, whatever the time
        row = next((r for r in src.rows if r.day == day), None)
    else:
        row = due(s, state, src, now)
    out: dict[str, Any] = {"due": row is not None, "dry_run": dry_run, "items": [], "notes": []}
    if row is None or check:
        if row is not None:
            print(f"{row.day}: {row.label} — due", file=sys.stderr)
        else:
            print(f"{now.astimezone(PARIS):%Y-%m-%d %H:%M} Paris: no theme video due",
                  file=sys.stderr)
        return out
    print(f"{row.day}: {row.label} → " + ", ".join(f"{p} {v.id}" for p, v in row.videos.items()),
          file=sys.stderr)
    if row.problems:
        out["problems"] = row.problems
        out["notes"].append(f"Vidéo thématique du {row.day:%d/%m} ({row.label}) non publiée : "
                            + " ; ".join(row.problems))
    entry = state["posts"].get(row.day.isoformat()) or {}
    previous = entry.get("results") or {}
    wanted = [p for p in (platforms or s.get("platforms", ["facebook", "instagram", "tiktok"]))
              if p in row.videos and (dry_run or not done(previous.get(p)))]
    if wanted:
        reels = reels_for(s, row, cfg.out / "themes", download)
        pubs = (make_publishers or publishers_for)(cfg, s, row, wanted)
        results = publish_row(row, reels, pubs, wanted, dry_run)
        entry = {"label": row.label, "videos": {p: v.id for p, v in row.videos.items()},
                 "at": now.isoformat(timespec="seconds"),
                 "results": previous | {n: asdict(r) | {"status": r.status.value}
                                        for n, r in results.items()}}
        if not dry_run:
            state["posts"][row.day.isoformat()] = entry
            save_state(state_path, state)
    out["items"].append(_item(s, row, entry, youtube_video(row, src.videos)))
    out["failed"] = [p for p, r in (entry.get("results") or {}).items()
                     if r.get("status") in ("failed", "blocked")] or bool(row.problems)
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str),
                          encoding="utf-8")
    return out


def check_upcoming(cfg: Config, days: int = 14, today: date | None = None,
                   src: Sources | None = None, exists: Callable[[str], bool] | None = None
                   ) -> tuple[list[str], list[str]]:
    """The next days' theme videos, and what would stop one: a row not tied to a video, a file
    page-<doc> does not hold. (lines to print, problems)"""
    s = settings(cfg)
    today = today or datetime.now(PARIS).date()
    src = src or fetch(s, today)
    if exists is None:
        import requests

        def exists(url: str) -> bool:
            try:
                return requests.head(url, allow_redirects=True, timeout=30).status_code == 200
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
            names = [v.tiktok if platform == "tiktok" else v.video]
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
