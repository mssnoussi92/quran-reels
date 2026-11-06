"""The catalogue's « À la demande » form and the on-demand posts (docs/on-demand.md).

The form only builds a pre-filled issue « À la demande : … » (same body as
ondemand.request.body); the `on-demand` workflow checks it, previews it and publishes after
the owner's `/publier`. Lists come from config/ at build time: the reciters allowed for
publishing (rotation minus claimed), the 114 surahs with their ayah counts, the backgrounds.
"""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from quran_reels import reciters as rec
from quran_reels.catalog.issues import REPO, SITE
from quran_reels.catalog.schedule import ref, surah_name
from quran_reels.config import Config
from quran_reels.ondemand.check import allowed_reciters
from quran_reels.ondemand.request import LABELS, PLATFORMS, TITLE_PREFIX

DOC = f"https://github.com/{REPO}/blob/main/docs/on-demand.md"
PLATFORM_LABELS = {"facebook": "Facebook", "instagram": "Instagram",
                   "tiktok": "TikTok (brouillon)", "youtube": "YouTube (à la main)"}
FOOTER = ("Ouvert depuis le catalogue (" + SITE + "#on-demand). Un aperçu arrive en "
          "commentaire ; rien n'est publié avant ta réponse /publier.")


MEANINGS_BUDGET = 15 * 60       # seconds of tafsir.app downloads per build (≈ 0.5 s a request)


def surah_data(cfg: Config, src: Any, surah: int, with_meanings: bool = True) -> dict[str, Any]:
    """What the form shows before the issue exists (docs/on-demand.md): the ayahs ending a
    sentence (whole passages only) and, per ayah, the Muyassar's meanings as the preview
    numbers them (ondemand.words, same code), pre-ticked as the usual rules show them. The
    Arabic and the translation are read by the page from Quran.com, never copied here."""
    from quran_reels.models import AyahRef
    from quran_reels.ondemand import words as words_mod
    from quran_reels.selector.plan import sentence_ends

    n = int(src.quran.chapters[surah]["verses_count"])
    refs = [AyahRef(surah, a) for a in range(1, n + 1)]
    texts = {r.ayah: t for r, t in src.quran.translate(src.translation_slug, refs).items()}
    out: dict[str, Any] = {"surah": surah, "ayahs": n, "ends": sorted(sentence_ends(texts)),
                           "meanings": None}
    if not with_meanings:
        return out
    key = f"{surah}:1-{n}"
    found = words_mod.meanings(cfg, src, key)
    auto = words_mod.auto_numbers(cfg, src, key, found)
    per_ayah: dict[str, list[dict]] = {}
    for m in found:
        per_ayah.setdefault(m.ref.split(":")[1], []).append({
            "k": m.choice.k, "word": m.word(), "gloss": m.choice.gloss or "",
            "usable": m.usable, "why": m.why, "auto": m.n in auto})
    out["meanings"] = per_ayah
    return out


READING_ORDER = [*range(114, 77, -1), *range(1, 78)]   # Juz' 'Amma first, as the calendar


def surah_files(cfg: Config, src: Any, out: Path, budget: float = MEANINGS_BUDGET,
                clock: Callable[[], float] = time.monotonic,
                surahs: list[int] = READING_ORDER) -> dict[str, int]:
    """catalog/surahs/SSS.json for the 114 surahs. Meanings not cached yet are downloaded
    for at most `budget` seconds (the cache keeps them for the next builds); a surah still
    incomplete gets no meanings: its words are chosen after the preview (/mots)."""
    from quran_reels.models import AyahRef

    out.mkdir(parents=True, exist_ok=True)
    start = clock()
    done = 0
    for surah in surahs:
        n = int(src.quran.chapters[surah]["verses_count"])
        refs = [AyahRef(surah, a) for a in range(1, n + 1)]
        ready = not src.glosses.missing(refs, src.quran.global_index)
        if not ready and clock() - start < budget:
            try:
                src.glosses.fetch(refs, src.quran.global_index)
                ready = True
            except Exception as e:      # noqa: BLE001  (next build)
                print(f"warning: Muyassar, surah {surah}: {type(e).__name__}", file=sys.stderr)
        data = surah_data(cfg, src, surah, with_meanings=ready)
        (out / f"{surah:03d}.json").write_text(json.dumps(data, ensure_ascii=False,
                                                          separators=(",", ":")), "utf-8")
        done += ready
    return {"surahs": len(surahs), "with_meanings": done}


def launcher(cfg: Config, state: dict, src: Any = None) -> dict[str, Any]:
    names = cfg.content.get("reciters") or {}
    no_youtube = rec.excluded_on(cfg, "youtube")
    surahs = []
    if src is not None:
        for n, c in sorted(src.quran.chapters.items()):
            surahs.append({"n": int(n), "name": c["name_simple"], "ar": c["name_arabic"],
                           "ayahs": int(c["verses_count"])})
    return {
        "reciters": [{"name": n, "label": (names.get(n) or {}).get("label", n),
                      "youtube": n not in no_youtube} for n in allowed_reciters(cfg, state)],
        "surahs": surahs,
        "backgrounds": [{"id": str(b["id"]), "tags": ", ".join(b.get("tags") or []),
                         "note": str(b.get("note") or "")}
                        for b in cfg.backgrounds.get("backgrounds") or []
                        if b.get("scene") or b.get("file") or b.get("pixabay_id")],
        "platforms": [{"id": p, "label": PLATFORM_LABELS[p]} for p in PLATFORMS],
        "new_issue": f"https://github.com/{REPO}/issues/new",
        "title_prefix": TITLE_PREFIX, "headings": LABELS, "footer": FOOTER, "doc": DOC,
        "max_seconds": int(cfg.content["passage"]["max_seconds"]),
        "max_per_ayah": int(cfg.content["glosses"].get("max_per_ayah", 2)),
        "translation_id": src.quran.translation_id(src.translation_slug) if src else None,
        "quran_api": "https://api.quran.com/api/v4",
    }


def posts(cfg: Config, state: dict, src: Any = None, keep: int = 20) -> list[dict]:
    """On-demand requests that reached a platform, newest first (public facts only)."""
    from quran_reels.catalog.posts import results

    names = cfg.content.get("reciters") or {}
    out = []
    for issue, e in (state.get("on_demand") or {}).items():
        key = e.get("passage", "")
        out.append({"issue": int(issue), "url": f"https://github.com/{REPO}/issues/{issue}",
                    "passage": key, "ref": ref(key) if key else "",
                    "surah": surah_name(src, key) if key else "",
                    "reciter_label": (names.get(e.get("reciter") or "") or {}).get(
                        "label", e.get("reciter") or ""),
                    "at": ((e.get("approved") or {}).get("at") or "")[:10],
                    "results": results(e)})
    out.sort(key=lambda p: (p["at"], p["issue"]), reverse=True)
    return out[:keep]
