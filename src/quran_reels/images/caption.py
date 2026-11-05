"""The caption of an image post: a fixed template (docs/images.md), no AI."""

from __future__ import annotations

from typing import Any

from quran_reels.config import Config
from quran_reels.images.cards import Content
from quran_reels.render import _tag


def hashtags(settings: dict[str, Any], content: Content) -> list[str]:
    conf = settings.get("hashtags") or {}
    tags = [*(conf.get("before") or []), f"#Surah{_tag(content.surah_name_en)}",
            f"#سورة_{_tag(content.surah_name_ar, '_')}", *(conf.get("after") or [])]
    return list(dict.fromkeys(tags))


def caption(cfg: Config, kind: str, content: Content) -> str:
    """Body without hashtags (Reel.text adds them, capped per platform)."""
    translation = cfg.content["translation"]["label"]
    if kind == "word":
        meaning = cfg.content["glosses"].get("label_en") or cfg.content["glosses"]["label"]
        return "\n".join([f"Word of the day: {content.word}",
                          f"Surah {content.surah_name_en} {content.ref}", "",
                          f"Translation: {translation}", f"Meaning: {meaning}", ""])
    return "\n".join(["Ayah of the day", f"Surah {content.surah_name_en} {content.context_ref}",
                      "", f"Translation: {translation}", ""])


def text(body: str, tags: list[str], max_hashtags: int | None) -> str:
    kept = tags if max_hashtags is None else tags[:max_hashtags]
    return body.rstrip("\n") + ("\n\n" + " ".join(kept) if kept else "") + "\n"
