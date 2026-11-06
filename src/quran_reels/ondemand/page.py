"""reel.json: what docs/reel.html shows for one reel (on-demand or from the calendar), and what
the comments are written from. Texts come from the rendered reel (caption.txt, hashtags) and
publish.youtube_texts; nothing is worded here but labels."""

from __future__ import annotations

from typing import Any

from quran_reels import publish as publish_mod
from quran_reels.config import Config
from quran_reels.models import Reel

STAGES = {
    "preview": "Aperçu : rien n'est publié",
    "dry-run": "Essai (dry run) : rien de public",
    "published": "Publié",
    "partial": "Publié en partie",
    "failed": "Échec",
    "blocked": "Bloqué par la vérification des droits : rien n'est publié",
    "checked": "Droits vérifiés : prêt pour YouTube",
    "daily": "Publié par le calendrier",
}
PLATFORM_LABELS = {"facebook": "Facebook", "instagram": "Instagram",
                   "tiktok": "TikTok (brouillon)", "youtube": "YouTube (à la main)"}
THEMES = {"mountains": "montagnes", "sea": "mer", "rivers": "rivières", "dawn": "aube",
          "rain": "pluie", "gardens": "jardins", "night": "nuit", "sky": "ciel",
          "default": "par défaut", "chosen": "choisi à la main"}


def captions(cfg: Config, reel: Reel, platforms: list[str]) -> list[dict[str, str]]:
    """The caption of each platform at its hashtag limit; identical ones shown once."""
    out: dict[str, list[str]] = {}
    for p in platforms:
        if p == "youtube":
            continue
        text = reel.text(publish_mod.max_hashtags(cfg, p))
        out.setdefault(text, []).append(PLATFORM_LABELS[p].split(" (")[0])
    return [{"label": ", ".join(names), "text": text} for text, names in out.items()]


def background_label(info: dict | None) -> str:
    if not info:
        return ""
    theme = str(info.get("theme", ""))
    base = theme.replace(" (fallback)", "")
    word = THEMES.get(base, base)
    return f"{info.get('id', '')} ({word}{', repli' if 'fallback' in theme else ''})"


def data(cfg: Config, reel: Reel, *, kind: str, rid: str, stage: str, created: str,
         reciter: str, seconds: float | None, platforms: list[str],
         background: dict | None = None, issue: dict | None = None,
         video: dict | None = None, frames: list[str] | None = None,
         youtube_file: str | None = None, results: list[dict] | None = None,
         notes: list[str] | None = None, command: str = "") -> dict[str, Any]:
    p = reel.passage
    yt = None
    if "youtube" in platforms:
        yt = publish_mod.youtube_texts(reel, publish_mod.max_hashtags(cfg, "youtube")) | {
            "file": youtube_file, "command": command}
    return {
        "kind": kind, "id": rid, "stage": stage, "stage_label": STAGES.get(stage, stage),
        "created": created, "passage": p.key,
        "surah": {"en": p.surah_name_en, "ar": p.surah_name_ar},
        "title": f"{p.key} · Surah {p.surah_name_en} · سورة {p.surah_name_ar}",
        "reciter": reciter, "seconds": seconds, "background": background_label(background),
        "platforms": [PLATFORM_LABELS.get(x, x) for x in platforms],
        "issue": issue, "video": video or {}, "frames": frames or [],
        "captions": captions(cfg, reel, platforms), "youtube": yt,
        "results": results or [], "notes": notes or [],
    }
