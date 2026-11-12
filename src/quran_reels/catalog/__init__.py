"""The catalogue: a public, read-only page to help the owner decide (docs/catalog.md).

`quran-reels catalog build` reads config/*.yaml, config/series/*.yaml and the state branch
(published.json, images.json, splits/), and writes a static folder:

    index.html   five sections: on-demand form, reciters, backgrounds, calendar and series,
                 recent posts
    data.json    everything the page shows, for other tools
    catalog.css, catalog.js
    previews/    a few seconds of each stock clip in 360p (never the clip itself)

It publishes nothing and changes nothing: no module of the publisher, the renderer or the
calendar is modified, it only calls them on copies of the state. Recitations are played from
their source (EveryAyah, mp3quran.net, archive.org), never copied. No secret reaches the page:
PIXABAY_API_KEY, if set, only resolves clip file URLs at build time. Every decision goes
through a pre-filled GitHub issue (catalog.issues).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from quran_reels.config import Config

HERE = Path(__file__).parent
SITE = HERE / "site"


def load_history() -> dict:
    return yaml.safe_load((HERE / "history.yaml").read_text(encoding="utf-8")) or {}


def _json(path: Path | None) -> dict:
    if path and path.is_file() and path.read_text(encoding="utf-8").strip():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def previous_backgrounds(source: str | None) -> dict[str, dict]:
    """Backgrounds of the posts as the previous catalogue recorded them (URL or file):
    a published reel keeps the background computed when it was first seen."""
    if not source:
        return {}
    try:
        if source.startswith(("http://", "https://")):
            from quran_reels.sources.http import Http

            data = Http(timeout=30).json(source)
        else:
            data = _json(Path(source))
    except Exception as e:     # noqa: BLE001  (first build, site down: computed again)
        print(f"note: previous catalogue not read ({type(e).__name__})", file=sys.stderr)
        return {}
    posts = (data or {}).get("posts") or {}
    return {p["id"]: p["background"] for p in (posts.get("slots") or []) + (
        posts.get("removed") or []) if p.get("id") and p.get("background")}


def _git(args: list[str], cwd: Path) -> str:
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def build(cfg: Config, out: Path, state_dir: Path | None = None, previous: str | None = None,
          clip_candidates: Path | None = None, manifests: list[Path] | None = None,
          previews: bool = True, days: int = 14, now: datetime | None = None,
          meanings_budget: float | None = None) -> Path:
    from quran_reels.catalog import backgrounds as bg_mod
    from quran_reels.catalog import ondemand as od_mod
    from quran_reels.catalog import posts as posts_mod
    from quran_reels.catalog import reciters as rec_mod
    from quran_reels.catalog import schedule as sched_mod
    from quran_reels.catalog.previews import Previews
    from quran_reels.selector.calendar import State, load_schedule, load_series
    from quran_reels.sources import Sources
    from quran_reels.sources.http import Http

    now = now or datetime.now(UTC)
    notes: list[str] = []
    state_path = state_dir / "published.json" if state_dir else None
    state = State.load(state_path) if state_path else State()
    images_state = state_dir / "images.json" if state_dir else None
    history = load_history()

    series = load_series(cfg)
    sched = load_schedule(cfg, series)
    today = now.astimezone(sched.tz).date()
    src = Sources.from_config(cfg)
    src.quran.ensure(src.translation_slug)
    picker = bg_mod.Picker(cfg, src)

    try:
        everyayah = rec_mod.recitations(Http(timeout=30).get(rec_mod.RECITATIONS_URL).text)
    except Exception as e:     # noqa: BLE001  (the candidates only)
        print(f"warning: EveryAyah list: {type(e).__name__}", file=sys.stderr)
        notes.append("Liste des récitations d'EveryAyah indisponible : pas de candidats cette fois.")
        everyayah = None
    reciters = rec_mod.collect(cfg, state.data, history, state_dir, everyayah)

    calendar = sched_mod.calendar(cfg, sched, series, state, today, days, picker, src)
    queues = sched_mod.progress(sched, series, state)
    try:
        words = sched_mod.words(cfg, src, images_state if images_state and images_state.is_file()
                                else None, now, 7)
    except Exception as e:     # noqa: BLE001
        print(f"warning: word of the day: {type(e).__name__}: {e}", file=sys.stderr)
        notes.append("Prochaines images « Word of the day » indisponibles.")
        words = {"enabled": False, "days": [], "time_utc": ""}

    found = bg_mod.manifests([cfg.out, *(manifests or [])])
    posts = posts_mod.collect(cfg, sched, series, state.data, picker,
                              previous_backgrounds(previous), found, src)

    used = [{"background": p["background"], "passage": p["passage"],
             "when": f"{p['date']} {p['slot']}"} for p in posts["slots"] + posts["removed"]
            if p.get("background")]
    planned = [{"background": s["background"], "passage": s["passage"],
                "when": f"{d['date']} {s['slot']}"} for d in calendar for s in d["slots"]
               if s.get("background") and not s.get("status")]
    shutil.rmtree(out / "previews", ignore_errors=True)       # only this build's clips
    shots = Previews(cfg, out, enabled=previews)
    cands = _json(clip_candidates) if clip_candidates else None
    if isinstance(cands, dict):
        cands = cands.get("candidates") or cands.get("hits") or []
    backgrounds = bg_mod.collect(cfg, history, used, planned, shots,
                                 cands if clip_candidates and clip_candidates.is_file() else None)
    notes += shots.notes

    data: dict[str, Any] = {
        "built": now.astimezone(UTC).isoformat(timespec="seconds"),
        "built_local": now.astimezone(sched.tz).strftime("%d/%m/%Y %H:%M"),
        "built_date": today.isoformat(),          # the calendar's first day (catalog.yml)
        "timezone": sched.tz.key,
        "commit": os.environ.get("GITHUB_SHA") or _git(["rev-parse", "HEAD"], cfg.root),
        "state_commit": _git(["rev-parse", "HEAD"], state_dir) if state_dir else "",
        "repo": os.environ.get("GITHUB_REPOSITORY", "mssnoussi92/quran-reels"),
        "schedule": {"enabled": sched.enabled,
                     "pause": sched_mod.pause_label(sched, today),
                     "slots": [{"name": s.name, "time": f"{s.at:%H:%M}", "queue": s.queue}
                               for s in sorted(sched.slots, key=lambda s: s.at)],
                     "fridays": sched.friday_queues, "days": days},
        "reciters": reciters, "backgrounds": backgrounds,
        "calendar": calendar, "queues": queues, "words": words,
        "posts": posts | {"images": posts_mod.images(_json(images_state)),
                          "on_demand": od_mod.posts(cfg, state.data, src)},
        "on_demand": od_mod.launcher(cfg, state.data, src),
        "notes": notes,
    }
    out.mkdir(parents=True, exist_ok=True)
    try:                        # the on-demand form: sentence ends and meanings per surah
        loaded = od_mod.surah_files(cfg, src, out / "surahs", od_mod.MEANINGS_BUDGET
                                    if meanings_budget is None else meanings_budget)
        data["on_demand"]["meanings"] = loaded
        if loaded["with_meanings"] < loaded["surahs"]:
            notes.append(f"Sens du Muyassar chargés pour {loaded['with_meanings']}/"
                         f"{loaded['surahs']} sourates "
                         "(formulaire « Publier ») ; la suite aux prochaines constructions.")
    except Exception as e:      # noqa: BLE001  (the form still works: words after the preview)
        print(f"warning: on-demand surah files: {type(e).__name__}: {e}", file=sys.stderr)
    (out / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    from quran_reels.catalog.page import render

    (out / "index.html").write_text(render(data), encoding="utf-8")
    for name in ("catalog.css", "catalog.js"):
        shutil.copyfile(SITE / name, out / name)
    return out
