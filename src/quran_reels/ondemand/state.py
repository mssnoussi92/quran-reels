"""On-demand reels in published.json (branch `state`), next to the calendar's slots:

    "on_demand": {"42": {"passage": "93:1-11", "reciter": "minshawi", "background": null,
                         "platforms": [...], "preview": {"run": 1, "sha256": "…"},
                         "approved": {"by": "…", "at": "…", "comment": 7},
                         "results": {"facebook": {"status", "id", "url", "error", "at"}, …,
                                     "youtube": {"status": "manual" | "published",
                                                 "by_hand": true, "url", "at"}}}}

YouTube stays `manual` until `/youtube`; a request the owner drops without uploading it (a
test, #39) is closed « not planned » and its YouTube result set to `cancelled` by hand, with a
`note`. Neither counts as a post: the catalogue lists only requests that reached a platform.

One entry per request (issue), one result per platform. The calendar does not read it: a
passage published on demand is published again when the calendar reaches it (owner's choice,
2026-11-06). YouTube is marked by hand (`/youtube`), on a request or on a calendar slot.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from quran_reels.models import PublishResult, PublishStatus

KEY = "on_demand"
OK = (PublishStatus.PUBLISHED.value, PublishStatus.DRAFT.value)


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def requests(state: dict) -> dict[str, dict]:
    return state.setdefault(KEY, {})


def entry(state: dict, issue: int) -> dict | None:
    return (state.get(KEY) or {}).get(str(issue))


def done_platforms(state: dict, issue: int) -> set[str]:
    """Platforms this request already has (never published twice by the same request)."""
    return {p for p, r in ((entry(state, issue) or {}).get("results") or {}).items()
            if r.get("status") in OK}


def record(state: dict, issue: int, checked: dict, preview: dict, results: list[PublishResult],
           approved: dict) -> dict:
    """Write what a publication did, platform by platform (earlier results are kept)."""
    e = requests(state).setdefault(str(issue), {"results": {}})
    e.update({"passage": checked["key"], "reciter": checked["reciter"],
              "background": checked.get("background"), "platforms": checked["platforms"],
              "preview": {k: preview.get(k) for k in ("run", "sha256", "rid")},
              "approved": approved})
    for r in results:
        e["results"][r.platform] = {"status": r.status.value, "id": r.remote_id, "url": r.url,
                                    "error": r.error, "at": now()}
    return e


def offer_youtube(state: dict, issue: int, video_url: str) -> None:
    """The 1080p file is offered for YouTube (Meta's check was clean): to upload by hand."""
    e = requests(state).setdefault(str(issue), {"results": {}})
    current = e["results"].get("youtube") or {}
    if current.get("status") != PublishStatus.PUBLISHED.value:
        e["results"]["youtube"] = {"status": PublishStatus.MANUAL.value, "video": video_url,
                                   "at": now()}


def mark_youtube(record_: dict[str, Any], url: str | None) -> dict:
    """YouTube uploaded by hand: on an on-demand entry or a calendar slot record."""
    results = record_.setdefault("results", {})
    previous = results.get("youtube") or {}
    results["youtube"] = {**{k: v for k, v in previous.items() if k == "video"},
                          "status": PublishStatus.PUBLISHED.value, "by_hand": True,
                          "url": url, "error": None, "at": now()}
    return results["youtube"]
