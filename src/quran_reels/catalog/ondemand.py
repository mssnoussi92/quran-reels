"""The catalogue's « À la demande » form and the on-demand posts (docs/on-demand.md).

The form only builds a pre-filled issue « À la demande : … » (same body as
ondemand.request.body); the `on-demand` workflow checks it, previews it and publishes after
the owner's `/publier`. Lists come from config/ at build time: the reciters allowed for
publishing (rotation minus claimed), the 114 surahs with their ayah counts, the backgrounds.
"""

from __future__ import annotations

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
