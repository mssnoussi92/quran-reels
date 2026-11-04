"""Assemble a passage from the sources: text, translation, anchored glosses, audio."""

from __future__ import annotations

import sys

from quran_reels.arabic import locate, normalize, quoted_words, similarity, trim, words
from quran_reels.config import Config
from quran_reels.models import Ayah, AyahRef, GlossEntry, Passage, WordGloss, parse_passage
from quran_reels.sources import Sources
from quran_reels.sources.tafsir_app import excerpt


def _warn(msg: str) -> None:
    print(f"warning: {msg}", file=sys.stderr)


def _override(entry: GlossEntry, overrides: dict[str, dict[str, str]]) -> list[int] | None:
    """Indexes, among the quoted words, chosen by the editor in config/glosses.yaml."""
    for lemma, chosen in (overrides.get(str(entry.ref)) or {}).items():
        if normalize(lemma) != normalize(entry.lemma):
            continue
        quoted = quoted_words(entry.lemma)
        picked = []
        for word in words(chosen):
            scores = [similarity(word, q) for q in quoted]
            best = max(range(len(quoted)), key=scores.__getitem__)
            if scores[best] < 0.7:
                raise SystemExit(f"config/glosses.yaml, {entry.ref}: «{word}» is not in «{lemma}»")
            picked.append(best)
        return sorted(set(picked))
    return None


def anchor(entries: list[GlossEntry], text: str, cfg: Config) -> list[WordGloss]:
    """Tie each gloss entry to the Uthmani words it explains; keep what fits on screen.

    The highlighted words are the source's quotation, minus the particles at its edges, or the
    words chosen in config/glosses.yaml.
    """
    g = cfg.content["glosses"]
    max_per_ayah, max_chars = int(g.get("max_per_ayah", 2)), int(g.get("max_chars", 170))
    tokens = words(text)
    out: list[WordGloss] = []
    used: set[int] = set()
    for e in entries:
        span = locate(e.lemma, tokens)
        if span is None:
            _warn(f"{e.ref}: «{e.lemma}» not found in the ayah, gloss left out")
            continue
        gloss = excerpt(e.text, max_chars)
        if gloss is None:
            _warn(f"{e.ref}: gloss of «{e.lemma}» longer than {max_chars} chars, left out")
            continue
        chosen = _override(e, cfg.gloss_headwords)
        if chosen is None:
            start, end = trim(quoted_words(e.lemma))
            chosen = list(range(start, end))
        positions = tuple(span[j] for j in chosen)
        if used.intersection(positions):
            continue
        used.update(positions)
        out.append(WordGloss(ref=e.ref, word=" ".join(tokens[p] for p in positions),
                             gloss=gloss, edition=e.edition, lemma=e.lemma, positions=positions))
        if len(out) >= max_per_ayah:
            break
    return out


def build(cfg: Config, key: str, src: Sources | None = None) -> Passage:
    src = src or Sources.from_config(cfg)
    surah, start, end = parse_passage(key)
    src.quran.ensure(src.translation_slug)
    chapter = src.quran.chapters[surah]
    if end > chapter["verses_count"]:
        raise SystemExit(f"surah {surah} has {chapter['verses_count']} ayahs, {key} is out of range")

    refs = [AyahRef(surah, a) for a in range(start, end + 1)]
    texts = src.quran.text(refs)
    translations = src.quran.translate(src.translation_slug, refs)
    entries = src.glosses.entries(refs, src.quran.global_index)

    passage = Passage(surah=surah, start=start, end=end,
                      surah_name_ar=chapter["name_arabic"], surah_name_en=chapter["name_simple"])
    for r in refs:
        passage.ayahs.append(Ayah(
            ref=r,
            text=texts[r],
            translation=translations[r],
            glosses=anchor(entries[r], texts[r], cfg),
            audio=src.audio.fetch(r),
        ))
    return passage
