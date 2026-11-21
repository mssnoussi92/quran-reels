"""quran-reels youtube-channel: the YouTube channel's keywords and description (config/channel.yaml).

Proposed on 2026-11-21 (the keywords were empty, the description said « twice a day » in English
first) and applied once, by hand (workflow `youtube-channel`), only once the owner has validated the
two texts (`validated: true`): a dry run shows them, an apply refuses them unvalidated or over
YouTube's limits (1 000 characters for the description, 500 for the keywords). channels.update
replaces the whole brandingSettings it is given (a setting left out is cleared): the channel's
settings are read first, only `keywords` and `description` change, the rest is sent back as it was.
A dry run prints the two fields before and after and changes nothing. Never run by a schedule: what
the owner later writes in Studio is not written over.

Access: the playlists' token (YOUTUBE_PLAYLISTS_REFRESH_TOKEN, youtube.force-ssl): channels.update
needs it, the upload token cannot.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from quran_reels.insights.youtube import DATA, YouTubeError

FIELDS = ("keywords", "description")
LIMITS = {"keywords": 500, "description": 1000}     # YouTube's, in characters
WRITABLE = ("channel", "watch")         # brandingSettings parts channels.update keeps


def settings(root: Path) -> dict[str, Any]:
    path = root / "config" / "channel.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}


def read(ch: Any) -> tuple[str, dict[str, Any]]:
    """(channel id, its brandingSettings) as YouTube has them now."""
    items = ch.client.get(f"{DATA}/channels", ch.token, part="brandingSettings",
                          mine="true").get("items") or []
    if not items:
        raise YouTubeError("no YouTube channel for this token")
    return items[0]["id"], items[0].get("brandingSettings") or {}


def wanted(branding: dict[str, Any], conf: dict[str, Any]) -> dict[str, Any]:
    """The brandingSettings to send: the writable parts as they are, keywords and description
    replaced by the validated ones."""
    out = {k: dict(branding[k]) for k in WRITABLE if branding.get(k)}
    out.setdefault("channel", {})
    for f in FIELDS:
        if conf.get(f) is not None:
            out["channel"][f] = str(conf[f]).strip()
    return out


def run(root: Path, dry_run: bool = True, ch: Any = None) -> int:
    from quran_reels.playlists import Channel

    conf = settings(root)
    if not any(conf.get(f) for f in FIELDS):
        print("youtube-channel: nothing in config/channel.yaml")
        return 0
    too_long = [f"{f} ({len(str(conf[f]).strip())} > {n})" for f, n in LIMITS.items()
                if conf.get(f) and len(str(conf[f]).strip()) > n]
    if too_long:
        raise SystemExit(f"youtube-channel: over YouTube's limit: {', '.join(too_long)}")
    if not dry_run and not conf.get("validated"):
        raise SystemExit("youtube-channel: config/channel.yaml is not validated by the owner "
                         "(`validated: true` on his word only): nothing applied")
    ch = ch or Channel.from_environ()
    if ch is None:
        raise SystemExit("youtube-channel: no token (YOUTUBE_PLAYLISTS_REFRESH_TOKEN): sign in "
                         "with youtube-login.html → Playlists, then the workflow youtube-auth")
    cid, branding = read(ch)
    new = wanted(branding, conf)
    before = branding.get("channel") or {}
    changed = [f for f in FIELDS if (before.get(f) or "").strip() != new["channel"].get(f, "")]
    for f in FIELDS:
        print(f"--- {f}, now:\n{before.get(f) or '(empty)'}\n--- {f}, validated:\n"
              f"{new['channel'].get(f, '')}\n")
    if not changed:
        print("youtube-channel: the channel has them already, nothing to do")
        return 0
    if dry_run:
        print(f"youtube-channel: dry run, would change {', '.join(changed)}")
        return 0
    ch._send("PUT", f"{DATA}/channels", "brandingSettings", {"id": cid, "brandingSettings": new})
    _, after = read(ch)
    left = [f for f in changed if ((after.get("channel") or {}).get(f) or "").strip()
            != new["channel"][f]]
    if left:
        raise SystemExit(f"youtube-channel: YouTube did not keep {', '.join(left)}")
    others = [k for k in (before.keys() | (after.get("channel") or {}).keys())
              if k not in FIELDS and before.get(k) != (after.get("channel") or {}).get(k)]
    print(f"youtube-channel: {', '.join(changed)} changed"
          + (f"; warning: also changed by YouTube: {', '.join(sorted(others))}" if others else
             "; every other setting as it was"))
    return 0
