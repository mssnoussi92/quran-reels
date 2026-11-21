"""Exact subtitles for the calendar's Shorts on YouTube (owner's choice, 2026-11-21).

YouTube's automatic subtitles do not know a recitation; people look a verse up by its words. Each
reel the run puts on YouTube gets two subtitle tracks taken from its own manifest.json, word for
word, at its own timing: the Arabic text of the mushaf (Uthmani, Quran.com) and the translation
shown in the video (Sahih International). Nothing is written or rewritten here (rule 1).

The daily run writes them, right after the upload, into youtube-captions/<video id>.json on the
state branch; the nightly step of the playlists (playlists.py, workflow `playlists`) sends them with
its token (captions need youtube.force-ssl, which only that step holds) and marks them done. A
long ayah shown on several screens gets one subtitle per screen, from the moment its first word is
recited, as on screen.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

DIR = "youtube-captions"
NAMES = {"ar": "نص المصحف", "en": "Sahih International"}


def _time(seconds: float) -> str:
    ms = max(0, round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def cues(manifest: dict[str, Any], lang: str) -> list[tuple[float, float, str]]:
    """(start, end, text) of each subtitle: the basmala when the reel has it, then each ayah, or
    each screen of a long ayah."""
    arabic = lang == "ar"
    out: list[tuple[float, float, str]] = []
    b = manifest.get("basmala")
    if b:
        out.append((b["start"], b["start"] + b["seconds"],
                    b["text"] if arabic else b.get("translation") or ""))
    for a in manifest.get("ayahs") or []:
        end = a["start"] + a["seconds"]
        screens = a.get("screens") or []
        if screens:
            for i, sc in enumerate(screens):
                until = screens[i + 1]["start"] if i + 1 < len(screens) else end
                out.append((sc["start"], until, sc.get("words" if arabic else "translation") or ""))
        else:
            out.append((a["start"], end, a["text"] if arabic else a.get("translation") or ""))
    return [(s, e, " ".join(t.split())) for s, e, t in out if t.strip() and e > s]


def srt(manifest: dict[str, Any], lang: str) -> str:
    return "\n".join(f"{i}\n{_time(s)} --> {_time(e)}\n{t}\n"
                     for i, (s, e, t) in enumerate(cues(manifest, lang), 1))


def queue(folder: Path, video_id: str, manifest_path: Path, key: str,
          langs: list[str]) -> Path | None:
    """The tracks of a video just uploaded, waiting for the nightly step. None when its manifest
    is not there (nothing is guessed)."""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print(f"warning: no subtitles for {video_id}: {manifest_path} not read", file=sys.stderr)
        return None
    tracks = {lang: srt(manifest, lang) for lang in langs}
    tracks = {lang: text for lang, text in tracks.items() if text.strip()}
    if not tracks:
        return None
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{video_id}.json"
    path.write_text(json.dumps({"video": video_id, "key": key,
                                "passage": manifest.get("passage"), "tracks": tracks,
                                "done": {}}, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")
    print(f"youtube: subtitles of {video_id} ({', '.join(tracks)}) waiting for the night",
          file=sys.stderr)
    return path


def upload_pending(folder: Path, channel: Any, dry_run: bool = False) -> list[str]:
    """Send every track not sent yet; each one sent is marked in its file (never sent twice).
    A refusal is said and tried again the next night."""
    lines: list[str] = []
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        data = json.loads(path.read_text(encoding="utf-8"))
        done = data.setdefault("done", {})
        for lang, text in (data.get("tracks") or {}).items():
            if lang in done:
                continue
            lines.append(f"subtitles {lang} → {data['video']} ({data.get('key', '')})")
            if dry_run:
                continue
            try:
                done[lang] = channel.caption(data["video"], lang, NAMES.get(lang, lang), text)
            except Exception as e:      # noqa: BLE001  (the next night tries again)
                lines.append(f"warning: subtitles {lang} of {data['video']} not sent: "
                             f"{type(e).__name__}: {e}")
        if not dry_run:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")
    return lines
