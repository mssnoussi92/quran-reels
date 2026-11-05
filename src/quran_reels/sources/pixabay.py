"""Pixabay videos API: search nature footage for the background themes, resolve a clip by id.

Their rules (pixabay.com/api/docs), followed here:
- every answer is cached 24 hours (.cache/pixabay/, keyed by the request without the key);
- rate limit 100 requests per 60 s: at most one request every 0.7 s, and a pause until the
  window resets when X-RateLimit-Remaining reaches 0;
- no systematic mass downloads: a search returns metadata only; a clip is downloaded once,
  when the owner has approved it (config/backgrounds.yaml), then kept in the cache.

The key (PIXABAY_API_KEY: GitHub secret, or the session's environment) travels as a query
parameter, as the API requires. It is never printed: errors are rebuilt from the status and
Pixabay's message, never from the request URL.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from quran_reels.sources.http import USER_AGENT, read_json, write_json

API = "https://pixabay.com/api/videos/"
CACHE_HOURS = 24
MIN_INTERVAL = 0.7                 # seconds between requests: under 100 per minute

# Words in a clip's tags that rule it out before anyone looks at it (people, animals, text,
# towns). Only a first filter: every candidate is still checked frame by frame.
EXCLUDED_TAGS = {
    "people", "person", "man", "men", "woman", "women", "girl", "boy", "child", "children",
    "kid", "baby", "human", "hand", "hands", "face", "portrait", "tourist", "hiker", "hiking",
    "surfer", "surfing", "swimmer", "couple", "family", "crowd", "silhouette", "fisherman",
    "animal", "animals", "bird", "birds", "dog", "cat", "horse", "cow", "cows", "sheep", "goat",
    "fish", "deer", "duck", "ducks", "seagull", "gull", "insect", "butterfly", "bee", "wildlife",
    "eagle", "swan", "camel", "city", "town", "street", "road", "car", "cars", "traffic",
    "building", "buildings", "text", "logo", "word", "letters", "boat", "ship", "drone shot of a",
}


class PixabayError(RuntimeError):
    pass


class Pixabay:
    def __init__(self, cache: Path, key: str | None = None,
                 session: requests.Session | None = None):
        self.dir = cache / "pixabay"
        self.key = key if key is not None else os.environ.get("PIXABAY_API_KEY", "")
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._last = 0.0

    # ---- requests -----------------------------------------------------------------------

    def _cache_path(self, params: dict[str, Any]) -> Path:
        stable = json.dumps(sorted(params.items()), ensure_ascii=False)
        return self.dir / f"{hashlib.sha1(stable.encode()).hexdigest()[:16]}.json"

    def _get(self, params: dict[str, Any]) -> dict:
        """An API answer, from the 24-hour cache when it is there."""
        path = self._cache_path(params)
        if path.is_file():
            cached = read_json(path)
            if datetime.now(UTC) - datetime.fromisoformat(cached["fetched"]) < \
                    timedelta(hours=CACHE_HOURS):
                return cached["data"]
        if not self.key:
            raise PixabayError("PIXABAY_API_KEY is not set (GitHub secret or environment)")
        wait = self._last + MIN_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        try:
            r = self.session.get(API, params={**params, "key": self.key}, timeout=30)
        except requests.RequestException as e:
            raise PixabayError(f"pixabay: network error ({type(e).__name__})") from None
        self._last = time.monotonic()
        if r.headers.get("X-RateLimit-Remaining") == "0":
            time.sleep(float(r.headers.get("X-RateLimit-Reset", 60)))
        if r.status_code != 200:
            detail = (r.text or "").replace(self.key, "***")[:200].strip()
            raise PixabayError(f"pixabay: HTTP {r.status_code} {detail}")
        data = r.json()
        write_json(path, {"fetched": datetime.now(UTC).isoformat(timespec="seconds"),
                          "params": params, "data": data})
        return data

    # ---- what the pipeline uses -----------------------------------------------------------

    def search(self, q: str, per_page: int = 30, min_width: int = 1920) -> list[dict]:
        """Nature films for a query, most popular first, safe search on."""
        data = self._get({"q": q, "video_type": "film", "category": "nature",
                          "safesearch": "true", "order": "popular", "per_page": per_page,
                          "min_width": min_width})
        return list(data.get("hits") or [])

    def video(self, video_id: int) -> dict | None:
        hits = self._get({"id": int(video_id)}).get("hits") or []
        return hits[0] if hits else None

    def file_url(self, video_id: int, rendition: str = "large") -> str:
        """The clip's current file URL (resolved through the API, as Pixabay asks, rather
        than kept for good in the config)."""
        hit = self.video(video_id)
        if not hit:
            raise PixabayError(f"pixabay video {video_id}: not found (removed?)")
        videos = hit.get("videos") or {}
        for name in (rendition, "large", "medium"):
            url = (videos.get(name) or {}).get("url")
            if url:
                return url
        raise PixabayError(f"pixabay video {video_id}: no file")


def tags_of(hit: dict) -> set[str]:
    return {t.strip().lower() for t in (hit.get("tags") or "").split(",") if t.strip()}


def ruled_out(hit: dict) -> set[str]:
    """The tags that rule a clip out at once (people, animals, text...)."""
    words = set()
    for tag in tags_of(hit):
        words |= {tag, *tag.split()}
    return words & EXCLUDED_TAGS


def summary(hit: dict, theme: str) -> dict:
    """What a candidate list keeps about a hit (no key, nothing private)."""
    videos = hit.get("videos") or {}
    large = videos.get("large") or {}
    return {"theme": theme, "id": hit["id"], "author": hit.get("user", ""),
            "page": hit.get("pageURL", ""), "tags": hit.get("tags", ""),
            "duration": hit.get("duration"), "large": f"{large.get('width')}x{large.get('height')}",
            "preview": (videos.get("tiny") or videos.get("small") or {}).get("url", "")}


def candidates(cfg: Any, themes: list[str] | None = None, per_theme: int = 4,
               min_seconds: int = 8) -> list[dict]:
    """Up to per_theme new clips per theme, from the search terms in config/backgrounds.yaml:
    nature films, no excluded tag, long enough, not already listed. To be checked frame by
    frame before anything is added."""
    terms = (cfg.backgrounds.get("pixabay") or {})
    listed = {int(c.get("pixabay_id") or 0) for c in cfg.backgrounds.get("backgrounds") or []}
    client = Pixabay(cfg.cache)
    out: list[dict] = []
    seen: set[int] = set(listed)
    for theme in themes or list(terms):
        picked = 0
        for q in terms.get(theme) or []:
            for hit in client.search(q):
                if picked >= per_theme:
                    break
                if hit["id"] in seen or ruled_out(hit) or (hit.get("duration") or 0) < min_seconds:
                    continue
                seen.add(hit["id"])
                out.append(summary(hit, theme) | {"query": q})
                picked += 1
    return out
