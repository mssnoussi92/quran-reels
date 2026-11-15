"""The « Statistiques » page: insights.json (state branch) → what the owner reads on the phone.

- followers on each platform, and their change over 7 days;
- each kind of video compared at the same age (the 48 h snapshot), as medians, with how many
  videos: below `compare.min_videos` videos, or `compare.min_points` points apart, no difference
  is claimed (docs/retention.md of quran-themes-demo, « Mesurer »);
- every video of the last weeks, Facebook and Instagram side by side, plus the numbers copied
  from screenshots (YouTube, TikTok).
"""

from __future__ import annotations

import statistics
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from quran_reels.insights.classify import KINDS
from quran_reels.insights.metrics import NUMBERS

PLATFORMS = {"facebook": "Facebook", "instagram": "Instagram", "youtube": "YouTube",
             "tiktok": "TikTok"}
DAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
COLUMNS = (("views", "vues"), ("hook", "passent 3 s"), ("watch_pct", "% regardé"),
           ("engage", "partages + enreg."), ("follows", "abonnés"))


def _engage(m: dict[str, Any]) -> int | None:
    parts = [m[k] for k in ("shares", "saves") if m.get(k) is not None]
    return sum(parts) if parts else None


def _full(m: dict[str, Any] | None) -> dict[str, Any]:
    """Every number, None where Meta gave nothing, and shares + saves."""
    m = m or {}
    return {k: m.get(k) for k in NUMBERS} | {"engage": _engage(m)}


def _median(values: list[float]) -> float | None:
    vals = [v for v in values if v is not None]
    return round(statistics.median(vals), 1) if vals else None


def _age(hours: float) -> str:
    return f"{hours:.0f} h" if hours < 48 else f"{hours / 24:.0f} j"


def _followers(accounts: dict, today: date) -> list[dict[str, Any]]:
    out = []
    for platform in ("facebook", "instagram"):
        days = accounts.get(platform) or {}
        if not days:
            continue
        series = sorted((d, v.get("followers_count")) for d, v in days.items()
                        if v.get("followers_count") is not None)
        if not series:
            continue
        last_day, now = series[-1]
        week = (date.fromisoformat(last_day) - timedelta(days=7)).isoformat()
        before = [n for d, n in series if d <= week]
        out.append({"platform": PLATFORMS[platform], "now": now, "day": last_day,
                    "delta": now - before[-1] if before else None,
                    "series": series[-30:]})
    return out


def _manual_key(entry: dict, posts: dict, themes: Any) -> str:
    """Which video a screenshot entry is about: a theme id, a reel passage, or a title."""
    video = entry.get("video", "")
    if themes is not None and video in getattr(themes, "by_id", {}):
        return f"theme:{video}"
    for rec in posts.values():
        ref = rec.get("ref") or {}
        if video and video in (ref.get("passage"), ref.get("theme"), rec.get("key")):
            return rec["key"]
    if themes is not None:
        found = themes.match(video, entry.get("platform", ""))
        if found:
            return f"theme:{found.id}"
    return f"manual:{video}"


def build(insights: dict[str, Any] | None, settings: dict[str, Any], now: datetime,
          tz: ZoneInfo, themes: Any = None,
          reciters: dict[str, str] | None = None) -> dict[str, Any]:
    if not insights or not (insights.get("posts") or insights.get("manual")):
        return {"empty": True}
    posts: dict[str, dict] = insights.get("posts") or {}
    compare = settings.get("compare") or {}
    min_videos, min_points = int(compare.get("min_videos", 3)), int(compare.get("min_points", 12))
    since = now - timedelta(days=int(settings.get("days", 35)))

    listed = insights.get("listed")

    def gone(rec: dict) -> bool:
        """Young enough to be listed by the last reading, and it was not: not public any more,
        or never was (a draft left by a test, a post scheduled by hand)."""
        try:
            young = datetime.fromisoformat(rec.get("published", "")) >= since
        except ValueError:
            return False
        return bool(listed) and young and rec.get("seen") != listed

    groups: dict[str, dict[str, Any]] = {}
    for uid, rec in posts.items():
        if gone(rec):
            continue
        try:
            published = datetime.fromisoformat(rec["published"])
        except (KeyError, ValueError):
            continue
        if published < since:
            continue
        g = groups.setdefault(rec.get("key") or uid, {
            "key": rec.get("key") or uid, "kind": rec.get("kind", "other"),
            "kind_label": KINDS.get(rec.get("kind", "other"), rec.get("kind", "")),
            "label": rec.get("label") or uid, "ref": rec.get("ref") or {},
            "published": published, "seconds": rec.get("seconds"), "rows": [], "manual": []})
        g["published"] = min(g["published"], published)
        g["seconds"] = g["seconds"] or rec.get("seconds")
        snaps = rec.get("snapshots") or {}
        row = {"platform": PLATFORMS.get(rec.get("platform"), rec.get("platform")),
               "url": rec.get("url", ""), "views": []}
        for name, title in (("48h", "à 48 h"), ("latest", "dernier relevé")):
            s = snaps.get(name)
            if name == "latest" and s and snaps.get("48h", {}).get("at") == s.get("at"):
                continue                     # the same reading: shown once, as « à 48 h »
            if s:
                m = _full(s.get("m"))
                row["views"].append({"name": name, "title": title, "age": _age(s.get("age_h", 0)),
                                     "m": m})
        g["rows"].append(row)

    manual_loose = []
    for e in insights.get("manual") or []:
        key = _manual_key(e, posts, themes)
        m = _full(e.get("m"))
        item = {"platform": PLATFORMS.get(e["platform"], e["platform"]), "seen": e.get("seen"),
                "video": e.get("video"), "published": e.get("published"), "m": m}
        if key in groups:
            groups[key]["manual"].append(item)
        else:
            manual_loose.append(item)

    videos = sorted(groups.values(), key=lambda g: g["published"], reverse=True)
    for g in videos:
        local = g["published"].astimezone(tz)
        g["when"] = f"{DAYS[local.weekday()]} {local:%d/%m} · {local:%H:%M}"
        g["published"] = g["published"].isoformat()
        if g["ref"].get("reciter"):
            g["reciter"] = (reciters or {}).get(g["ref"]["reciter"], g["ref"]["reciter"])
        g["rows"].sort(key=lambda r: r["platform"])

    # Each kind compared at 48 h, platform by platform.
    table: dict[tuple[str, str], list[dict]] = {}
    for rec in posts.values():
        s = (rec.get("snapshots") or {}).get("48h")
        if s and not gone(rec):
            table.setdefault((rec.get("kind", "other"), rec.get("platform", "")), []).append(
                _full(s.get("m")))
    kinds = []
    for (kind, platform), rows in sorted(table.items(), key=lambda kv: (
            list(KINDS).index(kv[0][0]) if kv[0][0] in KINDS else 99, kv[0][1])):
        kinds.append({"kind": KINDS.get(kind, kind), "platform": PLATFORMS.get(platform, platform),
                      "n": len(rows), "few": len(rows) < min_videos,
                      **{c: _median([r.get(c) for r in rows]) for c, _ in COLUMNS}})

    runs = insights.get("runs") or []
    last = runs[-1] if runs else {}
    try:
        updated = datetime.fromisoformat(insights.get("updated", ""))
    except ValueError:
        updated = None
    unsupported = {k: v for k, v in (insights.get("unsupported") or {}).items() if v}
    return {
        "empty": False,
        "updated": updated.astimezone(tz).strftime("%d/%m %H:%M") if updated else "",
        "stale": bool(updated and now - updated > timedelta(hours=36)),
        "stopped": last.get("stopped", ""), "errors": len(last.get("errors") or []),
        "notes": list(last.get("notes") or []),
        "calls": last.get("calls"), "usage": last.get("usage"),
        "unsupported": unsupported,
        "followers": _followers(insights.get("accounts") or {}, now.astimezone(tz).date()),
        "kinds": kinds, "columns": [list(c) for c in COLUMNS],
        "min_videos": min_videos, "min_points": min_points,
        "videos": videos, "manual": manual_loose,
        "days": int(settings.get("days", 35)),
    }


def merge_calendar(calendar: list[dict], theme_days: list[Any], time: str) -> None:
    """Put the theme videos of quran-themes-demo in the catalogue's calendar (each day: `themes`).
    The reels stay computed by their own calendar; the themes come from calendar.md as written."""
    by_day: dict[str, list[dict]] = {}
    for t in theme_days:
        by_day.setdefault(t.day, []).append(t.to_dict() | {"time": time})
    for day in calendar:
        day["themes"] = by_day.get(day.get("date", ""), [])


def now_utc() -> datetime:
    return datetime.now(UTC)
