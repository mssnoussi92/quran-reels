"""quran-reels insights collect: read the Page's statistics once a night → insights.json.

Read only (GET): nothing is posted, changed or deleted on Facebook or Instagram. Every post of
the last `days` days (config/insights.yaml) is listed, recognised (`classify`) and read:

- at each checkpoint (48 h, 7 days, 28 days), a snapshot kept for good, the first night after
  that age: the owner's sheet compares videos at the same age;
- every night until `refresh_days`, the « latest » numbers.

The Meta app has about 200 calls an hour (2026-11-13: one run used them all and the next
publication could not even check its token). So the run stops as soon as Meta reports
`max_usage` % of the budget used (X-App-Usage) or after `max_calls` calls, saves what it has,
and the next night goes on. It runs at night, after prepare-splits, when nothing is posted.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from quran_reels.config import Config
from quran_reels.insights import metrics as M
from quran_reels.insights.classify import Classifier
from quran_reels.insights.themes import ThemeIndex
from quran_reels.publishers.meta import Graph, GraphError

PARIS = ZoneInfo("Europe/Paris")
KEEP_RUNS = 30
UNKNOWN_METRIC = re.compile(r"\bcode 100\b")      # Meta's « invalid parameter » (a metric name)


def settings(cfg: Config) -> dict[str, Any]:
    path = cfg.root / "config" / "insights.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}


class Stop(Exception):
    """The call budget of this run is spent."""


class Budget:
    """Graph GETs that stop before Meta's hourly budget runs out."""

    def __init__(self, graph: Graph, max_usage: float, max_calls: int):
        self.graph, self.max_usage, self.max_calls = graph, max_usage, max_calls
        self.calls = 0

    def get(self, path: str, **params: Any) -> dict:
        if self.calls >= self.max_calls:
            raise Stop(f"{self.calls} appels (limite max_calls)")
        if self.graph.usage >= self.max_usage:
            raise Stop(f"budget de l'app Meta à {self.graph.usage} % (limite {self.max_usage} %)")
        self.calls += 1
        return self.graph.get(path, **params)

    def pages(self, path: str, since: datetime, stamp: str, **params: Any) -> list[dict]:
        """Every item of a list edge newer than `since` (cursor pagination; the `next` URL is
        never followed, so no URL with a token can reach a log)."""
        out, after = [], None
        for _ in range(10):
            body = self.get(path, **params, **({"after": after} if after else {}))
            items = body.get("data") or []
            out += items
            older = [i for i in items if _when(i.get(stamp)) and _when(i.get(stamp)) < since]
            after = ((body.get("paging") or {}).get("cursors") or {}).get("after")
            if older or not items or not after or not (body.get("paging") or {}).get("next"):
                break
        return [i for i in out if _when(i.get(stamp)) and _when(i.get(stamp)) >= since]


def _when(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    try:
        return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S%z").astimezone(UTC)
    except ValueError:
        try:
            return datetime.fromisoformat(stamp).astimezone(UTC)
        except ValueError:
            return None


@dataclass
class Post:
    platform: str               # facebook | instagram
    id: str
    published: datetime
    kind: str                   # metrics.REQUEST key: facebook-reel, instagram-post, …
    caption: str = ""
    url: str = ""
    seconds: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def uid(self) -> str:
        return f"{self.platform}:{self.id}"


# ------------------------------------------------------------------------------ listing


def _listed(budget: Budget, errors: list[str], path: str, since: datetime, stamp: str,
            **params: Any) -> list[dict]:
    """One list edge; Meta refusing it costs that list only (Stop still ends the run)."""
    try:
        return budget.pages(path, since, stamp, **params)
    except GraphError as e:
        errors.append(str(e))
        return []


def list_posts(budget: Budget, page_id: str, ig_id: str | None, since: datetime,
               images: dict, errors: list[str] | None = None) -> list[Post]:
    errors = [] if errors is None else errors
    posts: dict[str, Post] = {}
    fields = "id,created_time,description,length,permalink_url,published"
    for item in _listed(budget, errors, f"{page_id}/video_reels", since, "created_time",
                        fields=fields, limit=50):
        if item.get("published") is False:
            continue
        p = Post("facebook", str(item["id"]), _when(item["created_time"]), "facebook-reel",
                 item.get("description") or "", _fb_url(item.get("permalink_url")),
                 _float(item.get("length")))
        posts[p.uid] = p
    # Long videos the owner posts by hand (the 9:16 films) may not be Reels for the API.
    for item in _listed(budget, errors, f"{page_id}/videos", since, "created_time",
                        fields=fields, limit=50):
        uid = f"facebook:{item['id']}"
        # /videos also lists what is not public: drafts left by tests, posts scheduled by hand
        # (2026-11-15: nine at 0 views, and short 3 of Moussa and al-Khidr scheduled).
        if uid not in posts and item.get("published") is not False:
            posts[uid] = Post("facebook", str(item["id"]), _when(item["created_time"]),
                              "facebook-video", item.get("description") or "",
                              _fb_url(item.get("permalink_url")), _float(item.get("length")))
    # Word of the day on Facebook: photo posts, known by their id (images.json).
    for day, post in ((images.get("word") or {}).get("posts") or {}).items():
        res = (post.get("results") or {}).get("facebook") or {}
        when = datetime.fromisoformat(f"{day}T11:30:00+00:00")
        if res.get("id") and res.get("status") == "published" and when >= since:
            p = Post("facebook", str(res["id"]), when, "facebook-photo", "", res.get("url") or "")
            posts.setdefault(p.uid, p)
    if ig_id:
        for item in _listed(budget, errors, f"{ig_id}/media", since, "timestamp",
                            fields="id,timestamp,caption,media_type,media_product_type,permalink",
                            limit=50):
            reel = item.get("media_product_type") == "REELS"
            p = Post("instagram", str(item["id"]), _when(item["timestamp"]),
                     "instagram-reel" if reel else "instagram-post", item.get("caption") or "",
                     item.get("permalink") or "")
            posts[p.uid] = p
    return sorted(posts.values(), key=lambda p: p.published)


def _fb_url(link: str | None) -> str:
    if not link:
        return ""
    return link if link.startswith("http") else f"https://www.facebook.com{link}"


def _float(v: Any) -> float | None:
    try:
        return round(float(v), 1) if v is not None else None
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------------------ reading


def edge(kind: str) -> str:
    return {"facebook-reel": "video_insights", "facebook-video": "video_insights"}.get(
        kind, "insights")


def read(budget: Budget, post: Post, unsupported: dict[str, list[str]]) -> dict[str, Any]:
    """Meta's raw values for one post. A metric Meta refuses for this kind of post is learnt
    once (each metric asked alone) and never asked again."""
    known_bad = set(unsupported.get(post.kind) or [])
    names = [n for n in M.REQUEST[post.kind] if n not in known_bad]
    if not names:
        return {}
    path = f"{post.id}/{edge(post.kind)}"
    try:
        return M.values(budget.get(path, metric=",".join(names)))
    except GraphError as e:
        if not UNKNOWN_METRIC.search(str(e)) or len(names) == 1:
            raise
    raw: dict[str, Any] = {}
    for name in names:
        try:
            raw |= M.values(budget.get(path, metric=name))
        except GraphError as e:
            if not UNKNOWN_METRIC.search(str(e)):
                raise
            unsupported.setdefault(post.kind, [])
            if name not in unsupported[post.kind]:
                unsupported[post.kind].append(name)
    return raw


def due(record: dict, age_h: float, s: dict[str, Any]) -> list[str]:
    """The snapshots to take for a post of this age: checkpoints first, then « latest »."""
    tol = float(s.get("tolerance_hours", 48))
    have = record.get("snapshots") or {}
    out = [name for name, hours in (s.get("checkpoints") or {}).items()
           if name not in have and float(hours) <= age_h < float(hours) + tol]
    if age_h < float(s.get("refresh_days", 8)) * 24 or out:
        out.append("latest")
    return out


# ------------------------------------------------------------------------------ state


VERSION = 2


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() and \
        path.read_text(encoding="utf-8").strip() else {}
    for k in ("posts", "accounts", "unsupported"):
        data.setdefault(k, {})
    for k in ("manual", "runs"):
        data.setdefault(k, [])
    if data.get("version", VERSION if not data["posts"] else 1) < 2:
        # Version 1 (the first reading, 2026-11-15) read Facebook's retention graph and photo
        # reach, which proved wrong (metrics.py): those numbers are taken out of every snapshot.
        for rec in data["posts"].values():
            if rec.get("platform") != "facebook":
                continue
            for snap in (rec.get("snapshots") or {}).values():
                for k in ("hook", "kept_30s") + (("reach",) if rec.get("kind_meta") ==
                                                  "facebook-photo" else ()):
                    (snap.get("m") or {}).pop(k, None)
    data["version"] = VERSION
    return data


def save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _json(path: Path) -> dict:
    if path.is_file() and path.read_text(encoding="utf-8").strip():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


# ------------------------------------------------------------------------------ run


def run(cfg: Config, state_dir: Path, graph: Graph, page_id: str, ig_id: str | None,
        themes: ThemeIndex | None = None, now: datetime | None = None,
        dry_run: bool = False, notes: list[str] | None = None) -> dict[str, Any]:
    s = settings(cfg)
    now = now or datetime.now(UTC)
    path = state_dir / "insights.json"
    data = load(path)
    published = _json(state_dir / "published.json")
    images = _json(state_dir / "images.json")
    classifier = Classifier(published, images, themes or ThemeIndex([]))
    budget = Budget(graph, float(s.get("max_usage", 75)), int(s.get("max_calls", 150)))
    since = now - timedelta(days=int(s.get("days", 35)))
    errors: list[str] = []
    stopped = ""
    taken = 0

    try:
        today = now.astimezone(PARIS).date().isoformat()
        page = budget.get(page_id, fields="followers_count,fan_count")
        data["accounts"].setdefault("facebook", {})[today] = {
            k: page[k] for k in ("followers_count", "fan_count") if k in page}
        if ig_id:
            ig = budget.get(ig_id, fields="followers_count,media_count")
            data["accounts"].setdefault("instagram", {})[today] = {
                k: ig[k] for k in ("followers_count", "media_count") if k in ig}

        posts = list_posts(budget, page_id, ig_id, since, images, errors)
        listed = now.isoformat(timespec="seconds")
        data["listed"] = listed                 # the page shows what this listing found
        for p in posts:
            rec = data["posts"].setdefault(p.uid, {"snapshots": {}})
            rec["seen"] = listed
            rec |= {"platform": p.platform, "id": p.id, "url": p.url or rec.get("url", ""),
                    "published": p.published.isoformat(timespec="seconds"), "kind_meta": p.kind,
                    "first_line": next((ln.strip() for ln in p.caption.splitlines()
                                        if ln.strip()), rec.get("first_line", ""))[:140]}
            if p.seconds:
                rec["seconds"] = p.seconds
        classifier.apply(data["posts"])          # key, kind, label, seconds of the twin

        todo = []
        for p in posts:
            rec = data["posts"][p.uid]
            age_h = (now - p.published).total_seconds() / 3600
            names = due(rec, age_h, s)
            if names:
                todo.append((0 if names != ["latest"] else 1, age_h, p, names))
        for _, age_h, p, names in sorted(todo, key=lambda t: (t[0], t[1])):
            rec = data["posts"][p.uid]
            if rec.get("profile") == "facebook-video":
                p.kind = rec["kind_meta"] = "facebook-video"      # learnt on an earlier night
            try:
                raw = read(budget, p, data["unsupported"])
                if p.kind == "facebook-reel" and raw and not any(
                        raw.get(k) is not None for k in ("blue_reels_play_count",
                                                         "post_video_avg_time_watched")):
                    # a long video the API lists as a reel without reel numbers
                    p.kind = rec["kind_meta"] = rec["profile"] = "facebook-video"
                    raw = read(budget, p, data["unsupported"])
            except GraphError as e:
                errors.append(f"{p.uid}: {e}")
                continue
            numbers = M.normalize(p.kind, raw, rec.get("seconds"))
            snap = {"at": now.isoformat(timespec="seconds"), "age_h": round(age_h, 1),
                    "m": numbers}
            for name in names:
                rec["snapshots"][name] = snap
            graph_raw = raw.get("post_video_retention_graph") or raw.get(
                "total_video_retention_graph")
            if isinstance(graph_raw, dict):
                rec["retention"] = graph_raw
            taken += 1
    except Stop as e:
        stopped = str(e)
    except GraphError as e:
        errors.append(str(e))

    # posts older than the window keep their snapshots; nothing is deleted
    data["updated"] = now.isoformat(timespec="seconds")
    data["runs"] = (data["runs"] + [{
        "at": now.isoformat(timespec="seconds"), "calls": budget.calls, "usage": graph.usage,
        "read": taken, "stopped": stopped, "errors": errors[:20],
        "notes": list(notes or [])}])[-KEEP_RUNS:]
    if not dry_run:
        save(path, data)
    return {"calls": budget.calls, "usage": graph.usage, "read": taken, "stopped": stopped,
            "errors": errors, "notes": list(notes or []), "posts": len(data["posts"])}


# ------------------------------------------------------------------------------ manual

MANUAL_PLATFORMS = ("youtube", "tiktok", "facebook", "instagram")


def add_manual(path: Path, entries: list[dict[str, Any]], now: datetime | None = None) -> int:
    """Numbers read by the owner on a screenshot (YouTube Studio, TikTok), copied by a session.

    Each entry: {"platform", "video" (a theme video id such as "dua/short-1", a reel passage
    such as "106:1-4", or a title), "published" (YYYY-MM-DD), "seen" (YYYY-MM-DD, the day of the
    screenshot), "metrics": {views, hook, avg_watch, watch_pct, kept_30s, shares, saves,
    comments, likes, follows}}. The same platform, video and seen day replaces the old entry."""
    now = now or datetime.now(UTC)
    data = load(path)
    for e in entries:
        platform = str(e.get("platform", "")).casefold()
        if platform not in MANUAL_PLATFORMS:
            raise ValueError(f"platform must be one of {', '.join(MANUAL_PLATFORMS)}: {platform!r}")
        video = str(e.get("video") or "").strip()
        if not video:
            raise ValueError("video is missing")
        seen = str(e.get("seen") or now.astimezone(PARIS).date().isoformat())
        date.fromisoformat(seen)
        if e.get("published"):
            date.fromisoformat(str(e["published"]))
        nums = {}
        for k, v in (e.get("metrics") or {}).items():
            if k not in M.NUMBERS:
                raise ValueError(f"unknown number {k!r} (one of {', '.join(M.NUMBERS)})")
            if v is not None:
                nums[k] = float(v) if isinstance(v, float) or "." in str(v) else int(v)
        if not nums:
            raise ValueError(f"no numbers for {video}")
        entry = {"platform": platform, "video": video, "published": e.get("published") or "",
                 "seen": seen, "m": nums, "source": e.get("source") or "capture",
                 "added": now.isoformat(timespec="seconds")}
        data["manual"] = [m for m in data["manual"] if not (
            m["platform"] == platform and m["video"] == video and m["seen"] == seen)] + [entry]
    save(path, data)
    return len(entries)


def main_collect(cfg: Config, state_dir: Path, dry_run: bool = False) -> int:
    """CLI: token check, the themes of quran-themes-demo, the run, a short summary."""
    from quran_reels import publish as publish_mod
    from quran_reels.insights import themes as themes_mod

    s = settings(cfg)
    if not s.get("enabled", True):
        print("insights: disabled in config/insights.yaml")
        return 0
    graph, env, report = publish_mod.meta_check(cfg, ["facebook", "instagram"])
    notes = []
    missing = {"read_insights", "instagram_manage_insights"} - set(report.scopes)
    if missing:
        notes.append("jeton sans " + ", ".join(sorted(missing)) +
                      " : statistiques incomplètes (docs/plateformes.md, « Renouveler le jeton »)")
    try:
        index, _ = themes_mod.load_github(s["themes"], datetime.now(PARIS).date(),
                                          os.environ.get("GITHUB_TOKEN"))
    except Exception as e:      # noqa: BLE001  (the reels are still read)
        index = None
        notes.append(f"vidéos thématiques non lues ({type(e).__name__}) : non reconnues ce soir")
    out = run(cfg, state_dir, graph, env.page_id, env.ig_user_id, index,
              dry_run=dry_run, notes=notes)
    print(f"insights: {out['read']} posts read, {out['calls']} calls, Meta budget "
          f"{out['usage']} %, {out['posts']} posts known"
          + (f" · stopped: {out['stopped']}" if out["stopped"] else "")
          + (" · dry run, nothing saved" if dry_run else ""))
    for note in out["notes"]:
        print(f"  note: {note}", file=sys.stderr)
    for err in out["errors"]:
        print(f"  error: {err}", file=sys.stderr)
    return 0
