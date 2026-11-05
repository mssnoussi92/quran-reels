"""Assemble a passage from the sources: text, translation, anchored glosses, audio."""

from __future__ import annotations

import sys
from itertools import pairwise

from quran_reels.arabic import locate, normalize, quoted_words, similarity, trim, words
from quran_reels.config import Config
from quran_reels.models import Ayah, AyahRef, GlossEntry, Passage, WordGloss, parse_passage
from quran_reels.sources import Sources
from quran_reels.sources.tafsir_app import excerpt


def _warn(msg: str) -> None:
    print(f"warning: {msg}", file=sys.stderr)


# A chosen word must clearly be one of the quotation's words, spelling aside (سجى = سَجَىٰ).
CHOICE_SIMILARITY = 0.9


def pick(choice: tuple[str, ...], quoted: list[str]) -> list[int] | None:
    """Indexes, among the quoted words, of the one or two chosen words; None if one is missing."""
    picked: list[int] = []
    for word in choice:
        scores = [similarity(word, q) for q in quoted]
        best = max(range(len(quoted)), key=scores.__getitem__)
        if scores[best] < CHOICE_SIMILARITY or best in picked:
            return None
        picked.append(best)
    return sorted(picked)


def shown_words(tokens: list[str], positions: tuple[int, ...]) -> str:
    """The highlighted words as the box shows them; «…» where words of the ayah are skipped."""
    out = tokens[positions[0]]
    for prev, cur in pairwise(positions):
        skipped = any(normalize(t) for t in tokens[prev + 1:cur])
        out += (" … " if skipped else " ") + tokens[cur]
    return out


def anchor(ref: AyahRef, entries: list[GlossEntry], text: str, cfg: Config) -> list[WordGloss]:
    """Tie each gloss entry to the Uthmani words it explains; keep what fits on screen.

    Highlighted: the one or two words chosen in config/glosses.yaml for that gloss, otherwise
    the source's whole quotation minus the particles at its edges.
    """
    g = cfg.content["glosses"]
    max_per_ayah, max_chars = int(g.get("max_per_ayah", 2)), int(g.get("max_chars", 170))
    tokens = words(text)

    located: list[tuple[GlossEntry, list[int], str]] = []
    for e in entries:
        span = locate(e.lemma, tokens)
        if span is None:
            _warn(f"{ref}: «{e.lemma}» not found in the ayah, gloss left out")
            continue
        gloss = excerpt(e.text, max_chars)
        if gloss is None:
            _warn(f"{ref}: gloss of «{e.lemma}» longer than {max_chars} chars, left out")
            continue
        located.append((e, span, gloss))

    # Each editorial choice goes to the first gloss whose quotation holds its words.
    chosen: dict[int, list[int]] = {}
    for choice in cfg.gloss_headwords.get(str(ref), []):
        for k, (e, _, _) in enumerate(located):
            if k not in chosen and (idx := pick(choice, quoted_words(e.lemma))) is not None:
                chosen[k] = idx
                break
        else:
            _warn(f"config/glosses.yaml, {ref}: «{' '.join(choice)}» is in no quotation of this "
                  "ayah, whole quotation kept")

    out: list[WordGloss] = []
    used: set[int] = set()
    for k, (e, span, gloss) in enumerate(located):
        if k in chosen:
            indexes = chosen[k]
        else:
            start, end = trim(quoted_words(e.lemma))
            indexes = list(range(start, end))
        positions = tuple(span[j] for j in indexes)
        if used.intersection(positions):
            continue
        used.update(positions)
        out.append(WordGloss(ref=ref, word=shown_words(tokens, positions), gloss=gloss,
                             edition=e.edition, lemma=e.lemma, positions=positions))
        if len(out) >= max_per_ayah:
            break
    return out


BASMALA = AyahRef(1, 1)


def needs_basmala(cfg: Config, surah: int, start: int) -> bool:
    """Basmala before every passage, even mid-surah; never for At-Tawbah, nor before 1:1."""
    b = cfg.content.get("basmala") or {}
    if not b.get("enabled", False):
        return False
    if surah in (b.get("skip_surahs") or []):
        return False
    return not (surah == BASMALA.surah and start == BASMALA.ayah)


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
    if needs_basmala(cfg, surah, start):
        passage.basmala = Ayah(
            ref=BASMALA,
            text=src.quran.text([BASMALA])[BASMALA],
            translation=src.quran.translate(src.translation_slug, [BASMALA])[BASMALA],
            audio=src.audio.fetch_file(cfg.content["reciter"].get("basmala")
                                       or cfg.content["basmala"].get("audio", "bismillah")),
        )
    for r in refs:
        passage.ayahs.append(Ayah(
            ref=r,
            text=texts[r],
            translation=translations[r],
            glosses=anchor(r, entries[r], texts[r], cfg),
            audio=src.audio.fetch(r),
        ))
    return passage
