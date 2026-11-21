"""What the owner publishes by hand, on one page with a fixed link (docs/publier.html).

Owner's request, 2026-11-15: the issue « 📋 Légendes à copier » is hard to use from the phone
(open it, scroll, copy a code block). The page https://mssnoussi92.github.io/quran-reels/publier.html
reads `feed.json` on the branch `previews` when it opens: the last FEED_DAYS days of videos, the
latest first, each with the TikTok text to paste on its draft, the YouTube MP4 to download, its
thumbnail (theme videos), title, description, credits (theme videos: apart from the description,
owner's request of 2026-11-19) and hashtags, and the links of what is already out.

`feed.json` is derived, never written by hand: every time a publishing run writes the `reel.json`
of a video on `previews` (daily: `on-demand daily-files`; theme videos: `themes files`),
`Hosting.publish` rebuilds it from all the `reel.json` there (`files`), in the same commit. A
video's YouTube state is mostly not in it: the page reads it from the state branch (the nightly
reading of the channel, insights.json; the run's upload or a `/youtube` command, published.json);
a theme video the run put on YouTube carries its address (`youtube.url`).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

FEED = "feed.json"
FEED_DAYS = 14
PAGE = "https://mssnoussi92.github.io/quran-reels/publier.html"
SLOT_TIMES = {"morning": "07:30", "evening": "19:30"}     # reel.json written before 2026-11-16


def entry(meta: dict[str, Any]) -> dict[str, Any] | None:
    """One video of the page, from its reel.json (daily or theme); None for anything else."""
    rid = str(meta.get("id") or "")
    kind = rid.split("/", 1)[0]
    if kind not in ("daily", "theme") or meta.get("dry_run"):
        return None
    key, day, time = meta.get("key"), meta.get("day"), meta.get("time")
    if kind == "daily" and not key:            # « daily/2026-11-14-morning »
        day, slot = rid[len("daily/"):len("daily/") + 10], rid[len("daily/") + 11:]
        key, time = f"{day}/{slot}", SLOT_TIMES.get(slot, "")
    tiktok = meta.get("tiktok")
    if tiktok is None:                        # the caption TikTok shares with another platform
        tiktok = next((c.get("text", "") for c in meta.get("captions") or []
                       if "TikTok" in str(c.get("label", ""))), "")
    yt = meta.get("youtube") or None
    return {
        "id": rid, "kind": kind, "key": key, "day": day or str(meta.get("created", ""))[:10],
        "time": time or "", "created": meta.get("created", ""),
        "title": meta.get("title", ""), "passage": meta.get("passage", ""),
        "label": meta.get("label", ""), "reciter": meta.get("reciter", ""),
        "results": meta.get("results") or [], "tiktok": tiktok,
        "video": meta.get("video") or {},
        "youtube": {k: yt.get(k, "") for k in ("title", "description", "credits", "hashtags", "file",
                                               "thumbnail")} | ({"url": yt["url"]} if yt.get("url") else {})
        if yt and yt.get("file") else None,
        "notes": meta.get("notes") or [],
        "match": meta.get("match") or ([f"slot:{key}"] if kind == "daily" else []),
    }


def build(root: Path, now: datetime | None = None, days: int = FEED_DAYS) -> str:
    """feed.json from the reel.json under daily/ and theme/ of a checkout of `previews`: the
    videos of the last `days` days, the latest first."""
    now = now or datetime.now(UTC)
    limit = (now - timedelta(days=days)).date().isoformat()
    out = []
    for folder in ("daily", "theme"):
        for path in sorted((root / folder).glob("*/reel.json")):
            try:
                e = entry(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
            if e and e["day"] >= limit:
                out.append(e)
    out.sort(key=lambda e: (e["day"], e["time"], e["created"]), reverse=True)
    return json.dumps({"updated": now.isoformat(timespec="seconds"), "days": days,
                       "entries": out}, ensure_ascii=False, indent=1)


def files(root: Path) -> dict[str, str]:
    """For Hosting.publish(derived=…): feed.json rebuilt in the same commit as the reel.json."""
    return {FEED: build(root)}
