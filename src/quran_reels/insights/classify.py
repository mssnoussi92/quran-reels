"""Which video a post is: a reel of the calendar, a Word of the day, a theme video, or other.

The same video on Facebook and on Instagram gets the same `key`, so the dashboard shows them
side by side:

- reel of the calendar: its slot in published.json (« slot:2026-11-12/morning »), slots taken
  down included (`removed`); reel on demand: « od:39 »;
- Word of the day: images.json (« word:2026-11-15 »);
- theme video of quran-themes-demo: the first line of its caption is the English title of a
  section of publication-*.md (« theme:dua/short-1 »); its short version on Facebook and
  Instagram (themes.json `cut`, from 2026-11-24) stands with it, of its own kind
  (« theme-short-cut »), so that the comparison sets it beside the whole shorts;
- a reel published by hand (publish-test, before the calendar: 93:1-11 on 2026-11-05): the
  reference in the first line of its caption (« hand:93:1-11 »);
- anything else: the post alone (« facebook:<id> »), kind « other ».
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from quran_reels.insights.themes import ThemeIndex

KINDS = {   # kind → how the dashboard names it
    "reel-morning": "Reel du matin (lecture)",
    "reel-kahf": "Reel du vendredi (Al-Kahf)",
    "reel-series": "Reel du soir (série)",
    "reel-on-demand": "Reel à la demande",
    "reel-hand": "Reel publié à la main",
    "word": "Word of the day",
    "theme-film": "Thème : film",
    "theme-short": "Thème : short d'histoire",
    "theme-short-cut": "Thème : short, version courte",
    "theme-episode": "Thème : épisode de série",
    "other": "Autre publication",
}

PASSAGE = re.compile(r"\((\d{1,3}):(\d{1,3})(?:-(\d{1,3}))?\)")    # « (93:1-11) », « (9:51) »


def passage_of(line: str | None) -> str | None:
    """The reference of a reel's caption line, written as the calendar writes it (« 9:51-51 »)."""
    m = PASSAGE.search(line or "")
    if not m:
        return None
    surah, first, last = m.groups()
    return f"{int(surah)}:{int(first)}-{int(last or first)}"


def _reel_kind(record: dict, slot: str) -> str:
    queue = record.get("queue") or ""
    if queue in ("kahf", "kahf-first-ten"):
        return "reel-kahf"
    if queue == "themes" or slot.endswith("/evening"):
        return "reel-series"
    return "reel-morning"


class Classifier:
    def __init__(self, published: dict, images: dict, themes: ThemeIndex,
                 themes_state: dict | None = None):
        self.themes = themes
        self.by_id: dict[str, dict[str, Any]] = {}
        # theme videos sent in their short version (themepub, themes.json): « facebook:<id> » →
        # the file and the theme video's id
        self.cut: dict[str, dict[str, Any]] = {}
        for rec in ((themes_state or {}).get("posts") or {}).values():
            for platform, name in (rec.get("cut") or {}).items():
                res = (rec.get("results") or {}).get(platform) or {}
                rid = res.get("id") or res.get("remote_id")       # themes.json: PublishResult
                if rid:
                    self.cut[f"{platform}:{rid}"] = {
                        "file": name, "video": (rec.get("videos") or {}).get(platform)}
        slots = dict((published or {}).get("slots") or {})
        for r in (published or {}).get("removed") or []:
            if r.get("slot") and r.get("record"):
                slots.setdefault(r["slot"], r["record"] | {"removed": True})
        for slot, rec in slots.items():
            info = {"key": f"slot:{slot}", "kind": _reel_kind(rec, slot),
                    "label": rec.get("passage") or rec.get("item") or slot,
                    "ref": {"slot": slot, "queue": rec.get("queue"), "item": rec.get("item"),
                            "passage": rec.get("passage"), "reciter": rec.get("reciter"),
                            **({"removed": True} if rec.get("removed") else {})}}
            self._add(rec, info)
        for n, rec in ((published or {}).get("on_demand") or {}).items():
            self._add(rec, {"key": f"od:{n}", "kind": "reel-on-demand",
                            "label": rec.get("passage") or f"#{n}",
                            "ref": {"issue": n, "passage": rec.get("passage"),
                                    "reciter": rec.get("reciter")}})
        for day, rec in (((images or {}).get("word") or {}).get("posts") or {}).items():
            self._add(rec, {"key": f"word:{day}", "kind": "word",
                            "label": f"{rec.get('word', '')} · {rec.get('ayah', '')}".strip(" ·"),
                            "ref": {"day": day, "ayah": rec.get("ayah"), "word": rec.get("word")}})

    def _add(self, rec: dict, info: dict[str, Any]) -> None:
        for platform, res in (rec.get("results") or {}).items():
            if isinstance(res, dict) and res.get("id") and platform in ("facebook", "instagram"):
                self.by_id[f"{platform}:{res['id']}"] = info

    def one(self, uid: str, record: dict) -> dict[str, Any]:
        if uid in self.by_id:
            return self.by_id[uid]
        cut = self.cut.get(uid)
        video = self.themes.match(record.get("first_line"), record.get("platform", "")) or (
            self.themes.by_id.get(cut["video"]) if cut else None)
        if video:
            info = {"key": f"theme:{video.id}", "kind": video.kind,
                    "label": f"{video.title_en} · {video.title_ar}",
                    "ref": {"theme": video.id, "series": video.series, "part": video.part},
                    "seconds": video.seconds}
            if cut:          # its own length (Meta's), never the whole short's
                info |= {"kind": "theme-short-cut", "seconds": None}
                info["ref"]["cut"] = cut["file"]
            return info
        passage = passage_of(record.get("first_line"))
        if passage:
            return {"key": f"hand:{passage}", "kind": "reel-hand", "label": passage,
                    "ref": {"passage": passage}}
        return {"key": uid, "kind": "other", "label": record.get("first_line") or uid, "ref": {}}

    def apply(self, posts: dict[str, dict]) -> None:
        """Set key, kind, label and ref on every post; a post without its duration (Instagram)
        takes the one of its twin (Facebook) or of the theme's text."""
        for uid, rec in posts.items():
            info = self.one(uid, rec)
            rec |= {k: info[k] for k in ("key", "kind", "label", "ref")}
            if not rec.get("seconds") and info.get("seconds"):
                rec["seconds"] = info["seconds"]
        def which(rec: dict) -> tuple[str, str]:        # the short version is its own length
            return rec.get("key", ""), (rec.get("ref") or {}).get("cut") or ""

        lengths: dict[tuple[str, str], float] = {}
        for rec in posts.values():
            if rec.get("seconds") and rec.get("platform") == "facebook":
                lengths.setdefault(which(rec), rec["seconds"])
        for rec in posts.values():
            if not rec.get("seconds") and which(rec) in lengths:
                rec["seconds"] = lengths[which(rec)]


def day_of(record: dict) -> date | None:
    try:
        return date.fromisoformat(record.get("published", "")[:10])
    except ValueError:
        return None
