"""Backgrounds: config/backgrounds.yaml, how often each was used and by which theme, the
clips refused (catalogue history) and the Pixabay candidates of the last search.

Which background a passage gets is computed with the renderer's own rule
(sources.backgrounds.choose: the passage's translation, the themes, a stable hash), so the
catalogue needs neither the video nor its manifest. A slot keeps the background computed when
the catalogue first saw it (the previous data.json), and a manifest found in out/ wins over
both: config/backgrounds.yaml can change after a reel is published.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from quran_reels.catalog import issues
from quran_reels.catalog.previews import Previews
from quran_reels.catalog.schedule import ref
from quran_reels.config import Config
from quran_reels.models import Ayah, AyahRef, Passage, parse_passage
from quran_reels.sources import backgrounds as bgmod

LICENCES = {
    "pexels": {"name": "Licence Pexels", "url": "https://www.pexels.com/license/"},
    "pixabay": {"name": "Licence de contenu Pixabay",
                "url": "https://pixabay.com/service/license-summary/"},
    "generated": {"name": "scène générée (code du dépôt, MIT)",
                  "url": f"https://github.com/{issues.REPO}/tree/main/src/quran_reels/sources/scenes"},
}
SOURCES = {"pexels": "Pexels", "pixabay": "Pixabay", "generated": "Générée"}


class Picker:
    """The background the renderer gives a passage, from its translation."""

    def __init__(self, cfg: Config, src: Any):
        self.cfg, self.src = cfg, src
        self._memo: dict[str, dict | None] = {}

    def pick(self, key: str) -> dict | None:
        if key not in self._memo:
            surah, start, end = parse_passage(key)
            refs = [AyahRef(surah, a) for a in range(start, end + 1)]
            tr = self.src.quran.translate(self.src.translation_slug, refs)
            passage = Passage(surah, start, end, "", "",
                              ayahs=[Ayah(r, "", tr[r]) for r in refs])
            got = bgmod.choose(self.cfg, passage)
            self._memo[key] = None if got is None else {
                "id": got[0].id, "theme": got[1] or "default", "scores": dict(got[2])}
        return self._memo[key]


def manifests(paths: list[Path]) -> dict[tuple[str, str], dict]:
    """(passage, reciter name) → the background a rendered reel recorded."""
    out: dict[tuple[str, str], dict] = {}
    for base in paths:
        for path in sorted(base.glob("**/manifest.json")) if base.is_dir() else []:
            try:
                m = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if m.get("background") and m.get("passage"):
                out[(m["passage"], (m.get("reciter") or {}).get("name", ""))] = m["background"]
    return out


def _clip_facts(c: dict) -> dict[str, object]:
    return {"Source": SOURCES.get(c.get("source", ""), c.get("source")),
            "Auteur": c.get("author"), "Page": c.get("page"),
            "Thèmes": ", ".join(c.get("tags") or []), "Note": c.get("note")}


def collect(cfg: Config, history: dict, used: list[dict], planned: list[dict],
            previews: Previews, clip_candidates: list[dict] | None) -> dict[str, Any]:
    """used / planned: [{"background": {"id", "theme"}, "passage", "when"}] of the published
    and the coming slots."""
    from quran_reels.sources import scenes

    uses: dict[str, list[dict]] = defaultdict(list)
    for u in used:
        if u.get("background"):
            uses[u["background"]["id"]].append(u)
    soon: dict[str, list[dict]] = defaultdict(list)
    for u in planned:
        if u.get("background"):
            soon[u["background"]["id"]].append(u)

    raw = cfg.backgrounds
    cards = []
    for c in raw.get("backgrounds") or []:
        bid = str(c["id"])
        source = c.get("source") or ("generated" if c.get("scene") else "")
        card = {
            "id": bid, "source": source, "source_label": SOURCES.get(source, source),
            "licence": LICENCES.get(source), "author": c.get("author", ""),
            "page": c.get("page", ""), "tags": list(c.get("tags") or []),
            "note": c.get("note", ""), "pixabay_id": c.get("pixabay_id"),
            "default": bid in (raw.get("default") or []),
            "uses": [{"when": u["when"], "passage": ref(u["passage"]),
                      "theme": u["background"]["theme"]} for u in uses.get(bid, [])],
            "themes": dict(Counter(u["background"]["theme"] for u in uses.get(bid, []))),
            "planned": [{"when": u["when"], "passage": ref(u["passage"]),
                         "theme": u["background"]["theme"]} for u in soon.get(bid, [])],
            "preview": None, "shader": None,
        }
        if c.get("scene"):
            try:
                card["shader"] = scenes.source(c["scene"])
            except (OSError, ValueError) as e:
                card["note"] += f" (shader illisible : {type(e).__name__})"
        elif c.get("pixabay_id"):
            pid = int(c["pixabay_id"])
            card["preview"] = previews.clip(bid, f"pixabay:{pid}", lambda pid=pid: _pixabay(cfg, pid),
                                            float(c.get("focus", .5)))
        elif c.get("file"):
            card["preview"] = previews.clip(bid, c["file"], c["file"], float(c.get("focus", .5)))
        facts = _clip_facts(card) | {"Utilisations": len(card["uses"]),
                                     "Prévu (14 jours)": len(card["planned"])}
        card["issue"] = issues.remove_background(bid, facts)
        cards.append(card)

    refused = []
    for r in (history.get("backgrounds") or {}).get("refused") or []:
        refused.append({k: (str(v) if k == "date" else v) for k, v in r.items()}
                       | {"source_label": SOURCES.get(r.get("source", ""), r.get("source"))})

    listed = {int(c.get("pixabay_id") or 0) for c in raw.get("backgrounds") or []}
    listed |= {int(r.get("pixabay_id") or 0) for r in refused}
    cands = []
    for c in clip_candidates or []:
        try:
            pid = int(c["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if pid in listed:
            continue
        listed.add(pid)
        key = f"pixabay-{pid}"
        card = {"id": key, "pixabay_id": pid, "theme": c.get("theme", ""),
                "author": c.get("author", ""), "page": c.get("page", ""),
                "tags": _first_tags(c.get("tags", "")), "duration": c.get("duration"),
                "size": c.get("large", ""), "licence": LICENCES["pixabay"],
                "preview": previews.clip(key, f"pixabay:{pid}:candidate",
                                         lambda c=c, pid=pid: _candidate_url(cfg, pid, c),
                                         soften=False)}
        facts = {"Pixabay": pid, "Auteur": card["author"], "Page": card["page"],
                 "Thème cherché": card["theme"], "Tags Pixabay": card["tags"],
                 "Durée": f"{card['duration']} s" if card["duration"] else ""}
        card["approve"] = issues.clip_decision(True, key, facts)
        card["refuse"] = issues.clip_decision(False, key, facts)
        cands.append(card)

    themes = [{"tag": t, "pattern": p, "weight": w,
               "count": sum(1 for c in cards if t in c["tags"])}
              for t, (p, w) in (raw.get("themes") or {}).items()]
    return {"list": cards, "refused": refused,
            "unrecorded": (history.get("backgrounds") or {}).get("unrecorded", ""),
            "candidates": cands, "candidates_searched": clip_candidates is not None,
            "themes": themes, "default": list(raw.get("default") or [])}


def _first_tags(tags: str, keep: int = 8) -> str:
    """Pixabay's tags, the first few (a search hit can carry thirty)."""
    words = [t.strip() for t in str(tags or "").split(",") if t.strip()]
    return ", ".join(words[:keep]) + (" …" if len(words) > keep else "")


def _candidate_url(cfg: Config, pid: int, c: dict) -> str:
    """The `small` file through the API; without a key, the search's own preview URL."""
    from quran_reels.sources.pixabay import PixabayError

    try:
        return _pixabay(cfg, pid)
    except PixabayError:
        return str(c.get("preview") or "")


def _pixabay(cfg: Config, pid: int) -> str:
    """A Pixabay clip's file URL, `small` rendition (enough for 360p, light to download)."""
    from quran_reels.sources.pixabay import Pixabay

    return Pixabay(cfg.cache).file_url(pid, "small")
