"""Meta's insights → the few numbers the owner's sheet asks for, the same on both platforms.

| number      | what                                  | Instagram (reel)           | Facebook (reel / video)          |
|-------------|---------------------------------------|----------------------------|----------------------------------|
| views       | the size of the trial                 | views                      | blue_reels_play_count / total_video_views |
| reach       | people who saw it                     | reach                      | post_impressions_unique / total_video_impressions_unique |
| hook        | % of views past 3 s                   | 100 − reels_skip_rate      | — (see below)                    |
| avg_watch   | seconds watched on average            | ig_reels_avg_watch_time    | post_video_avg_time_watched      |
| watch_pct   | avg_watch ÷ duration                  | computed                   | computed                         |
| kept_30s    | % still there at 0:30 (films)         | —                          | — (see below)                    |
| shares, saves, comments, likes, follows, replays: as Meta counts them. |

Meta names a few of these « in development »: an empty answer stays empty, never 0.

Facebook's retention graph is kept raw (insights.json, `retention`) and not read: on the first
real reading (2026-11-15) it gave 41 points whatever the length, at 100 % until 3 s on some
reels whose average watch was 4 to 8 s, so neither « seconds » nor « 40 intervals » fits.
`retention_at` is ready for the day its meaning is checked against Meta Business Suite.
Facebook's reach is not served for Reels (post_impressions_unique refused, code 100), and for
photo posts post_total_media_view_unique answers 0 next to real views: no reach on Facebook.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Any

# What is asked for each kind of post (Graph metric names). Meta refuses the whole call when one
# name is unknown for that post: the collector then learns which ones are not served
# (insights.json, `unsupported`) and stops asking for them.
REQUEST = {
    "instagram-reel": ["views", "reach", "likes", "comments", "shares", "saved",
                       "total_interactions", "ig_reels_avg_watch_time",
                       "ig_reels_video_view_total_time", "reels_skip_rate"],
    "instagram-post": ["views", "reach", "likes", "comments", "shares", "saved",
                       "total_interactions", "follows", "profile_visits"],
    "facebook-reel": ["blue_reels_play_count", "fb_reels_total_plays", "fb_reels_replay_count",
                      "post_impressions_unique", "post_video_avg_time_watched",
                      "post_video_view_time", "post_video_followers",
                      "post_video_social_actions", "post_video_likes_by_reaction_type",
                      "post_video_retention_graph"],
    "facebook-video": ["total_video_views", "total_video_views_unique",
                       "total_video_impressions_unique", "total_video_avg_time_watched",
                       "total_video_view_total_time", "total_video_retention_graph",
                       "total_video_stories_by_action_type", "total_video_reactions_by_type_total"],
    "facebook-photo": ["post_media_view", "post_reactions_by_type_total", "post_clicks"],
}
NUMBERS = ("views", "reach", "hook", "avg_watch", "watch_pct", "kept_30s", "shares", "saves",
           "comments", "likes", "follows", "replays",
           "finished")      # % who watched to the end (TikTok: « A regardé la vidéo en entier »)


def values(answer: dict[str, Any]) -> dict[str, Any]:
    """{"data": [{"name", "values": [{"value"}]} or {"name", "total_value": {"value"}}]} →
    {name: value} (lifetime values: the last one)."""
    out: dict[str, Any] = {}
    for item in (answer or {}).get("data") or []:
        name = item.get("name")
        if not name:
            continue
        if isinstance(item.get("total_value"), dict) and "value" in item["total_value"]:
            out[name] = item["total_value"]["value"]
        elif item.get("values"):
            out[name] = item["values"][-1].get("value")
    return out


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict):                 # by type: the total
        nums = [float(x) for x in v.values() if isinstance(x, (int, float))]
        return sum(nums) if nums else None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _key(d: dict[str, Any], *names: str) -> float | None:
    """The first of these keys present in a by-type dict (e.g. SHARE, share, shares)."""
    if not isinstance(d, dict):
        return None
    low = {str(k).casefold(): v for k, v in d.items()}
    for n in names:
        if n in low:
            return _num(low[n])
    return None


def retention_at(graph: Any, second: float, duration: float | None) -> float | None:
    """% of plays still there at `second`, from a retention graph.

    Two shapes are seen: keys in seconds ({"0": 1.0, "1": 0.82, …}, reels) or 40 equal intervals
    of the video ({"0" … "40"}, page videos); values as fractions or as percentages."""
    if not isinstance(graph, dict) or not graph:
        return None
    try:
        points = sorted((float(k), float(v)) for k, v in graph.items())
    except (TypeError, ValueError):
        return None
    last = points[-1][0]
    if duration and last in (39.0, 40.0) and duration > last + 1:
        points = [(k * duration / 40.0, v) for k, v in points]       # intervals → seconds
    if second > points[-1][0]:
        return None
    scale = 100.0 if max(v for _, v in points) <= 1.5 else 1.0
    for (t0, v0), (t1, v1) in pairwise(points):
        if t0 <= second <= t1:
            v = v0 if t1 == t0 else v0 + (v1 - v0) * (second - t0) / (t1 - t0)
            return round(v * scale, 1)
    return round(points[0][1] * scale, 1) if second <= points[0][0] else None


def normalize(kind: str, raw: dict[str, Any], duration: float | None) -> dict[str, Any]:
    """Meta's values for one post → NUMBERS (only those Meta gave)."""
    m: dict[str, Any] = {}

    def put(name: str, value: float | None, digits: int = 0) -> None:
        if value is not None:
            m[name] = round(value, digits) if digits else round(value)

    if kind.startswith("instagram"):
        put("views", _num(raw.get("views")))
        put("reach", _num(raw.get("reach")))
        put("likes", _num(raw.get("likes")))
        put("comments", _num(raw.get("comments")))
        put("shares", _num(raw.get("shares")))
        put("saves", _num(raw.get("saved")))
        put("follows", _num(raw.get("follows")))
        skip = _num(raw.get("reels_skip_rate"))
        if skip is not None:
            skip = skip * 100 if skip <= 1 else skip
            put("hook", 100 - skip, 1)
        ms = _num(raw.get("ig_reels_avg_watch_time"))
        if ms is not None:
            put("avg_watch", ms / 1000, 1)
    elif kind == "facebook-reel":
        put("views", _num(raw.get("blue_reels_play_count")))
        put("reach", _num(raw.get("post_impressions_unique")))
        put("replays", _num(raw.get("fb_reels_replay_count")))
        put("follows", _num(raw.get("post_video_followers")))
        put("likes", _num(raw.get("post_video_likes_by_reaction_type")))
        social = raw.get("post_video_social_actions")
        put("shares", _key(social, "share", "shares"))
        put("comments", _key(social, "comment", "comments"))
        ms = _num(raw.get("post_video_avg_time_watched"))
        if ms is not None:
            put("avg_watch", ms / 1000, 1)
    elif kind == "facebook-video":
        put("views", _num(raw.get("total_video_views")))
        put("reach", _num(raw.get("total_video_impressions_unique")))
        put("likes", _num(raw.get("total_video_reactions_by_type_total")))
        stories = raw.get("total_video_stories_by_action_type")
        put("shares", _key(stories, "share", "shares"))
        put("comments", _key(stories, "comment", "comments"))
        ms = _num(raw.get("total_video_avg_time_watched"))
        if ms is not None:
            put("avg_watch", ms / 1000, 1)
    elif kind == "facebook-photo":
        put("views", _num(raw.get("post_media_view")))
        put("likes", _num(raw.get("post_reactions_by_type_total")))
    if "avg_watch" in m and duration:
        m["watch_pct"] = round(100 * m["avg_watch"] / duration, 1)
    return m
