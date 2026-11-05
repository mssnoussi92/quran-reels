"""Rules 1-4 of docs/images.md: which gloss entries can become a Word of the day.

1. A gloss entry of Ibn Qutaybah anchored on 1 or 2 words of the ayah (the words chosen in
   config/glosses.yaml, otherwise its quotation minus the particles at its edges). One post =
   one entry.
2. The gloss is shown whole: its full text (editor's notes already removed) ends with a
   sentence and fits in max_chars. Otherwise the entry is left out, never shortened.
3. The verse image shows a complete sentence: the ayah starts after a sentence end (the
   previous ayah ends with . ? ! in Sahih International, or it is the first of its surah) and
   ends one. Otherwise it grows to the smallest run of ayahs that does, if it fits.
4. Every image fits without going below the readability threshold (min_scale).

Ayah of the day: every smallest run of ayahs forming whole sentences that fits its image.

The result is frozen in config/image-candidates.yaml (references only, like plan.yaml): the
daily run needs neither the 2 394 glosses nor a browser to know what comes next.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from quran_reels.arabic import locate, quoted_words, trim, words
from quran_reels.config import Config
from quran_reels.images.cards import WORD_CARDS, CardRenderer, content_for, template_digest
from quran_reels.models import AyahRef
from quran_reels.passage import pick, shown_words
from quran_reels.selector.plan import sentence_ends
from quran_reels.sources.tafsir_app import parse_entries

_WHOLE = re.compile(r"[.!؟]$")          # ends with a sentence


@dataclass(frozen=True)
class Candidate:
    id: str                          # "93:3#0": ayah and entry number, or "2:255-255" (ayah)
    kind: str                        # word | ayah
    surah: int
    context: tuple[int, int]         # ayahs on the verse image
    ayah: int = 0                    # word: the glossed ayah
    entry: int = 0                   # word: index of the entry among the ayah's entries
    positions: tuple[int, ...] = ()  # word: highlighted words in the ayah

    @property
    def key(self) -> str:            # the ayah (or run) for exclusions and messages
        return f"{self.surah}:{self.ayah}" if self.kind == "word" else self.id

    def row(self) -> list:
        if self.kind == "word":
            return [self.id, f"{self.context[0]}-{self.context[1]}", list(self.positions)]
        return [self.id]

    @classmethod
    def from_row(cls, kind: str, row: list) -> Candidate:
        if kind == "word":
            ref, entry = row[0].split("#")
            surah, ayah = (int(x) for x in ref.split(":"))
            a, b = (int(x) for x in row[1].split("-"))
            return cls(row[0], kind, surah, (a, b), ayah, int(entry), tuple(row[2]))
        surah, rng = row[0].split(":")
        a, b = (int(x) for x in rng.split("-"))
        return cls(row[0], kind, int(surah), (a, b))


def whole_gloss(text: str, max_chars: int) -> str | None:
    """The entry's full text on one line, if it ends with a sentence and fits; else None."""
    gloss = " ".join(p.strip() for p in text.split("\n") if p.strip())
    if not gloss or len(gloss) > max_chars or not _WHOLE.search(gloss):
        return None
    return gloss


def sentence_context(ayah: int, ends: set[int], count: int) -> tuple[int, int]:
    """The smallest run of ayahs around `ayah` that starts and ends with a sentence."""
    start = ayah
    while start > 1 and (start - 1) not in ends:
        start -= 1
    end = ayah
    while end < count and end not in ends:
        end += 1
    return start, end


def entry_positions(ref: AyahRef, entries: list, tokens: list[str],
                    choices: list[tuple[str, ...]]) -> dict[int, tuple[int, ...] | None]:
    """Highlighted word positions per entry, as the reels anchor them (passage.anchor);
    None when the quotation is not found in the ayah."""
    spans = {n: locate(e.lemma, tokens) for n, e in enumerate(entries)}
    chosen: dict[int, list[int]] = {}
    for choice in choices:          # each choice goes to the first quotation holding it
        for n, e in enumerate(entries):
            if n not in chosen and spans[n] is not None and \
                    (idx := pick(choice, quoted_words(e.lemma))) is not None:
                chosen[n] = idx
                break
    out: dict[int, tuple[int, ...] | None] = {}
    for n, e in enumerate(entries):
        span = spans[n]
        if span is None:
            out[n] = None
            continue
        if n in chosen:
            idx = chosen[n]
        else:
            a, b = trim(quoted_words(e.lemma))
            idx = list(range(a, b))
        out[n] = tuple(span[j] for j in idx)
    return out


def word_content(src: Any, c: Candidate, gloss_text: str, max_chars: int):
    """The images' content for a word candidate (sources needed: text, translation, gloss)."""
    from quran_reels.images.cards import content_for

    ref = AyahRef(c.surah, c.ayah)
    tokens = words(src.quran.text([ref])[ref])
    return content_for(src, c.surah, c.context, c.ayah, c.positions,
                       word=shown_words(tokens, c.positions),
                       gloss=whole_gloss(gloss_text, max_chars) or "")


def build(cfg: Config, src: Any, progress: bool = True, surahs: list[int] | None = None
          ) -> tuple[list[Candidate], list[Candidate], Counter]:
    """All Word of the day and Ayah of the day candidates, and why the others were left out.
    surahs: only these (tests, trials)."""
    settings = images_settings(cfg)
    min_scale = float(settings.get("min_scale", 0.7))
    max_chars = int(cfg.content["glosses"].get("max_chars", 170))
    edition = cfg.content["glosses"]["edition"]
    src.quran.ensure(src.translation_slug)
    chapters = src.quran.chapters
    left_out: Counter = Counter()
    words_out: list[Candidate] = []
    ayahs_out: list[Candidate] = []
    fits: dict[tuple, bool] = {}

    with CardRenderer(cfg) as renderer:
        def fit(cards: tuple[str, ...], content) -> bool:
            return all(renderer.measure(card, content) >= min_scale for card in cards)

        for surah in surahs or sorted(chapters):
            count = chapters[surah]["verses_count"]
            refs = [AyahRef(surah, a) for a in range(1, count + 1)]
            ends = sentence_ends({r.ayah: t for r, t in
                                  src.quran.translate(src.translation_slug, refs).items()})
            texts = src.quran.text(refs)

            # Ayah of the day: the runs of whole sentences.
            start = 1
            for a in range(1, count + 1):
                if a in ends or a == count:
                    content = content_for(src, surah, (start, a))
                    if fit(("ayah",), content):
                        ayahs_out.append(Candidate(f"{surah}:{start}-{a}", "ayah", surah,
                                                   (start, a)))
                    else:
                        left_out["ayah: does not fit"] += 1
                    start = a + 1

            # Word of the day.
            glossed = [r for r in refs if src.glosses.has_entry(src.quran.global_index(r))]
            raw = src.glosses.raw(glossed, src.quran.global_index) if glossed else {}
            for ref in glossed:
                entries = parse_entries(raw.get(ref, ""), ref, edition)
                tokens = words(texts[ref])
                positions = entry_positions(ref, entries, tokens,
                                            cfg.gloss_headwords.get(str(ref), []))
                for n, e in enumerate(entries):
                    pos = positions[n]
                    if pos is None:
                        left_out["word: quotation not found in the ayah"] += 1
                        continue
                    if not 1 <= len(pos) <= 2:
                        left_out["word: more than 2 words highlighted"] += 1
                        continue
                    gloss = whole_gloss(e.text, max_chars)
                    if gloss is None:
                        left_out[f"word: gloss over {max_chars} chars or not a whole sentence"] += 1
                        continue
                    context = sentence_context(ref.ayah, ends, count)
                    c = Candidate(f"{ref}#{n}", "word", surah, context, ref.ayah, n, pos)
                    content = content_for(src, surah, context, ref.ayah, pos,
                                          word=shown_words(tokens, pos), gloss=gloss)
                    key = (surah, context, ref.ayah, pos, gloss)
                    if key not in fits:
                        fits[key] = fit(WORD_CARDS, content)
                    if fits[key]:
                        words_out.append(c)
                    else:
                        left_out["word: does not fit on the images"] += 1
            if progress:
                print(f"surah {surah}: {len(words_out)} words, {len(ayahs_out)} ayahs so far",
                      file=sys.stderr)
    return words_out, ayahs_out, left_out


# ---- settings and the frozen list -------------------------------------------------------

def images_settings(cfg: Config) -> dict[str, Any]:
    path = cfg.root / "config" / "images.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {} if path.is_file() else {}


def candidates_path(cfg: Config) -> Path:
    return cfg.root / "config" / "image-candidates.yaml"


def write(cfg: Config, words_out: list[Candidate], ayahs_out: list[Candidate],
          left_out: Counter) -> Path:
    path = candidates_path(cfg)
    lines = [
        "# Image post candidates (docs/images.md, rules 1-4), frozen so that the daily choice",
        "# does not move when a source changes. Written by `quran-reels images build`; rebuild",
        "# after changing config/glosses.yaml, the template or min_scale. References only.",
        "# word: [ayah#entry, ayahs on the verse image, highlighted word positions]",
        f"template: {template_digest()}",
        "left_out:",
        *(f"  {reason!r}: {n}" for reason, n in sorted(left_out.items())),
        f"word:   # {len(words_out)}",
        *(f"  - {c.row()!r}".replace("'", '"') for c in words_out),
        f"ayah:   # {len(ayahs_out)}",
        *(f'  - ["{c.id}"]' for c in ayahs_out),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def load(cfg: Config, kind: str) -> list[Candidate]:
    path = candidates_path(cfg)
    if not path.is_file():
        raise SystemExit(f"{path} is missing: run `quran-reels images build`")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [Candidate.from_row(kind, row) for row in raw.get(kind) or []]
