"""quran-reels youtube-channel: the YouTube channel's keywords and description (config/channel.yaml).

Proposed on 2026-11-21 (the keywords were empty, the description said « twice a day » in English
first) and applied once, by hand (workflow `youtube-channel`), only once the owner has validated the
two texts (`validated: true`): a dry run shows them, an apply refuses them unvalidated or over
YouTube's limits (1 000 characters for the description, 500 for the keywords). channels.update
replaces the whole brandingSettings it is given (a setting left out is cleared): the channel's
settings are read first, only `keywords` and `description` change, the rest is sent back as it was.
A dry run prints the two fields before and after and changes nothing. The two texts are never
written by a schedule: what the owner later writes in Studio is not written over.

The one exception, his choice (2026-11-21): the Arabic name of a series joins the keywords the night
its first video is on YouTube (series_keywords, called by the nightly playlists step): added at the
end, never one taken out, the description never touched; once the 500 characters are reached, the
step says which name it could not add, and the owner chooses what to take out.

The description mixes Arabic and English lines: a line that needs it starts with the invisible
mark of its own direction (bidi.directed, no word changed; owner, 2026-11-21: « être sûr que
l'affichage de l'arabe sera bon »), so that it reads right wherever YouTube shows it. The marks
count in YouTube's 1 000 characters.

Access: the playlists' token (YOUTUBE_PLAYLISTS_REFRESH_TOKEN, youtube.force-ssl): channels.update
needs it, the upload token cannot.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import yaml

from quran_reels.arabic import _MARKS, normalize
from quran_reels.bidi import directed, directions, plain
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
            text = str(conf[f]).strip()
            out["channel"][f] = directed(text) if f == "description" else text
    return out


def run(root: Path, dry_run: bool = True, ch: Any = None) -> int:
    from quran_reels.playlists import Channel

    conf = settings(root)
    if not any(conf.get(f) for f in FIELDS):
        print("youtube-channel: nothing in config/channel.yaml")
        return 0
    sent = wanted({}, conf)["channel"]                   # as sent: the marks count too
    too_long = [f"{f} ({len(sent[f])} > {n})" for f, n in LIMITS.items()
                if sent.get(f) and len(sent[f]) > n]
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
              f"{plain(new['channel'].get(f, ''))}\n")
    if new["channel"].get("description"):
        print(f"each line (+: a direction mark): {directions(new['channel']['description'])}")
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


# ------------------------------------------------------------- a series' name, at its first video

QUOTED = re.compile(r'"([^"]+)"|(\S+)')
LONGEST = 40              # a name longer than this is not a keyword someone types


def keywords_of(text: str) -> list[str]:
    """The channel's keywords as YouTube keeps them: words, and phrases in quotes."""
    return [a or b for a, b in QUOTED.findall(text or "")]


def same(phrase: str) -> str:
    """A keyword's comparable form: Arabic without vowel signs and with one alif, Latin lowercased."""
    return " ".join(normalize(w) or w.lower() for w in phrase.split())


def bare_name(name: str) -> str:
    """An Arabic name as one types it in a search: no vowel sign, no punctuation
    (« مخيّر ولا مسيّر؟ » → « مخير ولا مسير »)."""
    text = _MARKS.sub("", unicodedata.normalize("NFC", name))
    return " ".join("".join(ch for ch in text if unicodedata.category(ch)[0] not in "PS").split())


def series_words(groups: list[tuple[str, str]], conf: dict[str, Any], names: Any) -> list[str]:
    """The keywords of the series (reels) and documents (theme videos) that have a video on
    YouTube, in the order of their first one: the name written in config/channel.yaml
    (series_keywords; null: none), else the Arabic validated name, bare."""
    table = conf.get("series_keywords") or {}
    out: list[str] = []
    for kind, group in groups:
        written = table.get(kind) or {}
        if group in written:
            value = written[group]
            words = [] if value is None else [value] if isinstance(value, str) else list(value)
        else:
            found = names.series.get(group) if kind == "series" else names.of_doc(group)
            words = [w for w in ([bare_name(found[1])] if found else []) if 0 < len(w) <= LONGEST]
        out += [str(w) for w in words if str(w) not in out]
    return out


def add_keywords(ch: Any, words: list[str], dry_run: bool) -> list[str]:
    """The words the channel's keywords lack, added at the end within YouTube's 500 characters;
    every other setting sent back as it was. The lines of what was (dry run: would be) done."""
    cid, branding = read(ch)
    current = ((branding.get("channel") or {}).get("keywords") or "").strip()
    have = {same(k) for k in keywords_of(current)}
    text, added, lines = current, [], []
    for w in words:
        if same(w) in have:
            continue
        token = f'"{w}"' if " " in w else w
        if len(f"{text} {token}".strip()) > LIMITS["keywords"]:
            lines.append(f"warning: the channel's keywords are full ({len(text)}/"
                         f"{LIMITS['keywords']}): « {w} » not added, the owner chooses what to take out")
            continue
        text = f"{text} {token}".strip()
        have.add(same(w))
        added.append(w)
    if added:
        lines.insert(0, f"{'would add' if dry_run else 'add'} to the channel's keywords: "
                        + ", ".join(f"« {w} »" for w in added))
        if not dry_run:
            body = {k: dict(branding[k]) for k in WRITABLE if branding.get(k)}
            body.setdefault("channel", {})["keywords"] = text
            ch._send("PUT", f"{DATA}/channels", "brandingSettings",
                     {"id": cid, "brandingSettings": body})
    return lines


def series_keywords(root: Path, groups: list[tuple[str, str]], ch: Any, names: Any,
                    dry_run: bool) -> list[str]:
    """The nightly step: the names of the series with a video on YouTube, in the keywords."""
    conf = settings(root)
    if not conf.get("series_keywords"):
        return []
    words = series_words(groups, conf, names)
    if not words:
        return []
    try:
        return add_keywords(ch, words, dry_run)
    except YouTubeError as e:            # the playlists are done; the keywords wait a night
        return [f"warning: the channel's keywords not changed ({e})"]
