"""A deeper look at the channel's YouTube numbers, read only, on demand (owner, 2026-11-21: « t'as
accès aux stats YouTube par l'API, vois si tu peux récupérer plus d'info »).

The nightly reading (youtube.py) keeps what the statistics page compares: views, average watched,
shares, subscribers. This reads, for each video of the last `days`, what it does not keep:

- where the views come from (traffic sources: the Shorts feed, search, suggested videos, browse
  features, the channel page...), and the search terms and suggesting videos of the channel;
- the countries of the viewers (which language a title should start with);
- the audience retention curve (100 points: share of the audience still there at each 1 % of the
  video; above 1 on a Short watched again);
- engaged views, when YouTube serves them (Shorts: views past the first seconds).

Same OAuth client and read-only token as the nightly reading. Written to one JSON file for a
session to read (workflow insights, input `youtube_detail`: an artifact; nothing is saved on the
state branch). Thumbnail impressions and click-through rate are not served by this API: YouTube
Studio only (its export « Contenu »).

One query that YouTube refuses (an unknown metric, a report it does not serve for a Short) is noted
in `errors` and the rest is still read.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from quran_reels.insights.youtube import (
    ANALYTICS,
    PACIFIC,
    SHORT_MAX,
    YouTube,
    YouTubeEnv,
    YouTubeError,
)


def _rows(body: dict[str, Any]) -> list[dict[str, Any]]:
    names = [h.get("name") for h in body.get("columnHeaders") or []]
    return [dict(zip(names, row, strict=False)) for row in body.get("rows") or []]


class _Reader:
    def __init__(self, yt: YouTube, token: str, errors: list[str]):
        self.yt, self.token, self.errors = yt, token, errors

    def rows(self, what: str, start: date, end: date, **params: Any) -> list[dict[str, Any]] | None:
        try:
            body = self.yt.get(ANALYTICS, self.token, ids="channel==MINE",
                               startDate=start.isoformat(), endDate=end.isoformat(), **params)
        except YouTubeError as e:
            self.errors.append(f"{what}: {e}")
            return None
        return _rows(body)


def _share(rows: list[dict[str, Any]] | None, key: str) -> list[dict[str, Any]] | None:
    """Rows of views by `key`, each with its share of the views (%)."""
    if rows is None:
        return None
    total = sum(float(r.get("views") or 0) for r in rows) or 1.0
    out = []
    for r in rows:
        item = {key: r.get(key), "views": int(r.get("views") or 0),
                "pct": round(100 * float(r.get("views") or 0) / total, 1)}
        for k, name in (("estimatedMinutesWatched", "minutes"), ("averageViewDuration", "avg_watch")):
            if r.get(k) is not None:
                item[name] = round(float(r[k]), 1)
        out.append(item)
    return out


def read(yt: YouTube, token: str, now: datetime, days: int = 30) -> dict[str, Any]:
    errors: list[str] = []
    q = _Reader(yt, token, errors)
    ch = yt.channel(token)
    found = [v for v in yt.uploads(token, ch["uploads"], now - timedelta(days=days)) if v["id"]]
    stats = yt.videos(token, [v["id"] for v in found])
    end = now.astimezone(PACIFIC).date()
    videos = []
    for v in found:
        st = stats.get(v["id"])
        if not st:                                 # not public
            continue
        start = v["published"].astimezone(PACIFIC).date()
        one = {"filters": f"video=={v['id']}"}
        tag = f"{v['id']}"
        rec: dict[str, Any] = {
            "id": v["id"], "title": st.get("title") or v["title"],
            "published": v["published"].isoformat(timespec="seconds"),
            "seconds": st.get("seconds"), "views": st.get("views"),
            "short": st.get("seconds") is not None and st["seconds"] <= SHORT_MAX}
        rec["sources"] = _share(q.rows(f"{tag} sources", start, end, **one,
                                       metrics="views,estimatedMinutesWatched",
                                       dimensions="insightTrafficSourceType", sort="-views"),
                                "insightTrafficSourceType")
        rec["countries"] = _share(q.rows(f"{tag} countries", start, end, **one,
                                         metrics="views,averageViewDuration",
                                         dimensions="country", sort="-views", maxResults=10),
                                  "country")
        curve = q.rows(f"{tag} retention", start, end, **one,
                       metrics="audienceWatchRatio,relativeRetentionPerformance",
                       dimensions="elapsedVideoTimeRatio")
        rec["retention"] = None if curve is None else [
            [round(float(r.get("elapsedVideoTimeRatio") or 0), 2),
             round(float(r.get("audienceWatchRatio") or 0), 3),
             None if r.get("relativeRetentionPerformance") is None
             else round(float(r["relativeRetentionPerformance"]), 3)] for r in curve]
        engaged = q.rows(f"{tag} engaged views", start, end, **one,
                         metrics="views,engagedViews", dimensions="video")
        if engaged:
            e = engaged[0]
            rec["engaged"] = {"views": int(e.get("views") or 0),
                              "engaged_views": int(e.get("engagedViews") or 0)}
        videos.append(rec)
    first = min((date.fromisoformat(r["published"][:10]) for r in videos), default=end)
    channel = {
        "title": ch["title"], "subscribers": ch.get("subscribers"),
        "sources": _share(q.rows("channel sources", first, end,
                                 metrics="views,estimatedMinutesWatched",
                                 dimensions="insightTrafficSourceType", sort="-views"),
                          "insightTrafficSourceType"),
        "countries": _share(q.rows("channel countries", first, end,
                                   metrics="views,averageViewDuration", dimensions="country",
                                   sort="-views", maxResults=25), "country"),
        "search_terms": _share(q.rows("channel search terms", first, end, metrics="views",
                                      dimensions="insightTrafficSourceDetail",
                                      filters="insightTrafficSourceType==YT_SEARCH",
                                      sort="-views", maxResults=25),
                               "insightTrafficSourceDetail"),
        "suggested_by": _share(q.rows("channel suggested by", first, end, metrics="views",
                                      dimensions="insightTrafficSourceDetail",
                                      filters="insightTrafficSourceType==RELATED_VIDEO",
                                      sort="-views", maxResults=25),
                               "insightTrafficSourceDetail"),
    }
    return {"read": now.isoformat(timespec="seconds"), "from": first.isoformat(),
            "to": end.isoformat(), "channel": channel, "videos": videos, "errors": errors}


def summary(detail: dict[str, Any]) -> str:
    """A few lines for the job's log: no search term, nothing but numbers and our own titles."""
    lines = [(f"youtube detail: {len(detail['videos'])} public videos, {detail['from']} → "
              f"{detail['to']}, {len(detail['errors'])} queries refused")]
    for r in detail["videos"]:
        src = ", ".join(f"{s['insightTrafficSourceType']} {s['pct']:.0f}%"
                        for s in (r.get("sources") or [])[:3])
        geo = ", ".join(f"{c['country']} {c['pct']:.0f}%" for c in (r.get("countries") or [])[:3])
        lines.append(f"  {r['published'][:10]} {r['views']:>6} views  {r['title'][:48]:48}  "
                     f"| {src} | {geo}")
    for e in detail["errors"][:10]:
        lines.append(f"  refused: {e}")
    return "\n".join(lines)


def main(out: Path, days: int = 30, now: datetime | None = None,
         client: YouTube | None = None, env: YouTubeEnv | None = None,
         compact: bool = True) -> str:
    env = env or YouTubeEnv.from_environ()
    if env is None or not env.refresh_token:
        raise YouTubeError("YouTube secrets not set (YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, "
                           "YOUTUBE_REFRESH_TOKEN)")
    yt = client or YouTube(env.client_id, env.client_secret)
    token = yt.access(env.refresh_token)
    detail = read(yt, token, now or datetime.now(UTC), days)
    # Compact (no indent): the file lives on the state branch and is rewritten every night.
    out.write_text(json.dumps(detail, ensure_ascii=False,
                              **({"separators": (",", ":")} if compact else {"indent": 1})),
                   encoding="utf-8")
    return summary(detail)
