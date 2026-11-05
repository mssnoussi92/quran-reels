"""Recent posts: the slots of published.json, newest first, with their public links, the
TikTok status, the reciter and the background; and what was taken down (`removed`).

Only public facts: status labels and public post URLs, never ids of inbox uploads nor raw
error messages (the page is public).
"""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from typing import Any

from quran_reels.catalog.schedule import SLOTS_FR, day_label, ref, slot_status, surah_name
from quran_reels.config import Config
from quran_reels.selector.calendar import Schedule, Series

STATUS = {"published": "publié", "draft": "brouillon", "ready": "prêt (dry run)",
          "manual": "à publier à la main", "failed": "échec", "blocked": "bloqué (droits)",
          "removed": "retiré (Meta l'a rendu muet ou bloqué)"}
PLATFORMS = {"facebook": "Facebook", "instagram": "Instagram", "tiktok": "TikTok",
             "youtube": "YouTube"}
KEEP = 30


def results(record: dict) -> list[dict]:
    out = []
    for name, r in (record.get("results") or {}).items():
        status = r.get("status", "")
        label = STATUS.get(status, status)
        if name == "tiktok" and status == "draft":
            label = "brouillon dans la boîte TikTok"
        elif status == "published" and not r.get("url"):
            label = "publié à la main"
        url = r.get("url") if name in ("facebook", "instagram", "youtube") else None
        out.append({"platform": name, "name": PLATFORMS.get(name, name), "status": status,
                    "label": label, "url": url if status in ("published",) else None})
    return out


def identity(slot: str, record: dict) -> str:
    """One publication: a slot can be published again after a removal."""
    times = sorted(r.get("at", "") for r in (record.get("results") or {}).values())
    return f"{slot}|{record.get('passage', '')}|{record.get('reciter', '')}|{times[0] if times else ''}"


def _when(slot_key: str, sched: Schedule) -> dict[str, str]:
    day_s, slot = slot_key.split("/", 1)
    times = {s.name: f"{s.at:%H:%M}" for s in sched.slots}
    d = date.fromisoformat(day_s)
    return {"date": day_s, "day": day_label(d), "slot": slot,
            "slot_fr": SLOTS_FR.get(slot, slot), "time": times.get(slot, "")}


def collect(cfg: Config, sched: Schedule, series: dict[str, Series], state: dict,
            picker: Any, previous: dict[str, dict], manifest_bgs: dict[tuple[str, str], dict],
            src: Any = None) -> dict[str, Any]:
    labels = {n: r.get("label", n) for n, r in (cfg.content.get("reciters") or {}).items()}

    def background(ident: str, record: dict, removed: bool) -> dict | None:
        found = manifest_bgs.get((record.get("passage", ""), record.get("reciter") or ""))
        if found:
            return {"id": found.get("id"), "theme": found.get("theme", ""), "from": "manifeste"}
        if previous.get(ident):
            return previous[ident]
        if removed:         # published before the catalogue existed: not guessed
            return None
        try:
            got = picker.pick(record["passage"]) if picker else None
        except Exception as e:     # noqa: BLE001
            print(f"warning: background of {record.get('passage')}: {type(e).__name__}",
                  file=sys.stderr)
            return None
        return got and {"id": got["id"], "theme": got["theme"],
                        "from": f"calculé le {datetime.now(UTC).date().isoformat()}"}

    def item(slot_key: str, record: dict, removed_why: str = "", removed: bool = False) -> dict:
        ident = identity(slot_key, record)
        sid = (record.get("item") or "").split("/", 1)[0]
        s = series.get(sid)
        key = record.get("passage", "")
        label = ""
        if s:
            n = len(s.passages)
            idx = next((i for i, k in enumerate(s.passages, 1) if k == key), 0)
            label = (s.title_en if n == 1 or not idx else f"{s.title_en} · {idx}/{n}") \
                if s.title_en else sid
        return _when(slot_key, sched) | {
            "id": ident, "passage": key, "ref": ref(key), "surah": surah_name(src, key),
            "series": sid, "label": label,
            "queue": record.get("queue", ""),
            "reciter": record.get("reciter") or "",
            "reciter_label": labels.get(record.get("reciter") or "", record.get("reciter") or ""),
            "results": results(record), "status": slot_status(record),
            "note": record.get("note", ""), "claimed": record.get("claimed", ""),
            "why": removed_why, "background": background(ident, record, removed)}

    slots = [item(k, r) for k, r in sorted((state.get("slots") or {}).items(),
                                           key=lambda kv: _order(kv[0], sched), reverse=True)]
    removed = [item(x.get("slot", ""), x.get("record") or {}, x.get("why", ""), removed=True)
               for x in state.get("removed") or [] if x.get("slot")]
    return {"slots": slots[:KEEP], "total": len(slots), "removed": removed,
            "by_hand": sorted(sched.published_by_hand)}


def _order(slot_key: str, sched: Schedule) -> tuple[str, str]:
    day_s, slot = slot_key.split("/", 1)
    times = {s.name: f"{s.at:%H:%M}" for s in sched.slots}
    return day_s, times.get(slot, slot)


def images(state: dict | None, keep: int = 10) -> list[dict]:
    """The last image posts (images.json), when there are some."""
    out = []
    for kind, data in (state or {}).items():
        if not isinstance(data, dict):
            continue
        for day_s, post in (data.get("posts") or {}).items():
            if not isinstance(post, dict) or post.get("planned"):
                continue
            out.append({"date": day_s, "day": day_label(date.fromisoformat(day_s)),
                        "kind": kind, "ayah": post.get("ayah") or post.get("id", ""),
                        "word": post.get("word", ""), "results": results(post)})
    out.sort(key=lambda p: p["date"], reverse=True)
    return out[:keep]
