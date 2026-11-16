"""Assemble a passage from the sources: text, translation, anchored glosses, audio."""

from __future__ import annotations

import copy
import dataclasses
import sys
from dataclasses import dataclass
from datetime import date, datetime
from itertools import pairwise

from quran_reels.arabic import locate, normalize, quoted_words, similarity, trim, words
from quran_reels.config import Config
from quran_reels.models import Ayah, AyahRef, GlossEntry, Passage, WordGloss, parse_passage
from quran_reels.sources import Sources, basmala_stem
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


@dataclass(frozen=True)
class Choice:
    """One word meaning the source gives for an ayah, as the owner may pick it (on-demand
    reels, `/mots`): k is its rank among the ayah's entries in the source."""

    k: int
    entry: GlossEntry
    span: tuple[int, ...] | None       # the quotation's words in the ayah; None: not found
    gloss: str | None                  # what is shown; None: no whole sentence fits

    @property
    def usable(self) -> bool:
        return self.span is not None and self.gloss is not None


def choices(ref: AyahRef, entries: list[GlossEntry], text: str, cfg: Config,
            warn: bool = True) -> list[Choice]:
    """Every entry of the source for the ayah, anchored on its words when possible."""
    max_chars = int(cfg.content["glosses"].get("max_chars", 170))
    tokens = words(text)
    out = []
    for k, e in enumerate(entries):
        span = locate(e.lemma, tokens)
        gloss = excerpt(e.text, max_chars) if span is not None else None
        if warn and span is None:
            _warn(f"{ref}: «{e.lemma}» not found in the ayah, gloss left out")
        elif warn and gloss is None:
            _warn(f"{ref}: gloss of «{e.lemma}» longer than {max_chars} chars, left out")
        out.append(Choice(k, e, tuple(span) if span is not None else None, gloss))
    return out


def editorial_choices(ref: AyahRef, usable: list[Choice], cfg: Config, warn: bool = True
               ) -> dict[int, list[int]]:
    """config/glosses.yaml: each choice goes to the first gloss whose quotation holds its
    words → {k: indexes in the quotation}."""
    chosen: dict[int, list[int]] = {}
    for choice in cfg.gloss_headwords.get(str(ref), []):
        for c in usable:
            if c.k not in chosen and (idx := pick(choice, quoted_words(c.entry.lemma))) is not None:
                chosen[c.k] = idx
                break
        else:
            if warn:
                _warn(f"config/glosses.yaml, {ref}: «{' '.join(choice)}» is in no quotation of "
                      "this ayah, whole quotation kept")
    return chosen


def default_indexes(c: Choice, editorial: dict[int, list[int]]) -> list[int]:
    if c.k in editorial:
        return editorial[c.k]
    start, end = trim(quoted_words(c.entry.lemma))
    return list(range(start, end))


Selection = list[tuple[int, tuple[str, ...]]]     # (k, words to highlight, () = default)


def anchor(ref: AyahRef, entries: list[GlossEntry], text: str, cfg: Config,
           selection: Selection | None = None) -> list[WordGloss]:
    """Tie each gloss entry to the Uthmani words it explains; keep what fits on screen.

    Highlighted: the one or two words chosen in config/glosses.yaml for that gloss, otherwise
    the source's whole quotation minus the particles at its edges.
    selection: the owner's choice for this ayah (on-demand reels, checked by
    ondemand.check): these entries, in this order, each with its words or the default ones.
    """
    max_per_ayah = int(cfg.content["glosses"].get("max_per_ayah", 2))
    tokens = words(text)
    found = choices(ref, entries, text, cfg, warn=selection is None)
    usable = [c for c in found if c.usable]
    editorial = editorial_choices(ref, usable, cfg, warn=selection is None)
    if selection is not None:
        picked = []
        for k, chosen_words in selection:
            c = found[k] if 0 <= k < len(found) else None
            if c is None or not c.usable:
                raise SystemExit(f"{ref}: word meaning #{k + 1} cannot be shown")
            idx = (pick(chosen_words, quoted_words(c.entry.lemma)) if chosen_words
                   else default_indexes(c, editorial))
            if idx is None:
                raise SystemExit(f"{ref}: «{' '.join(chosen_words)}» is not in «{c.entry.lemma}»")
            picked.append((c, idx))
    else:
        picked = [(c, default_indexes(c, editorial)) for c in usable]

    out: list[WordGloss] = []
    used: set[int] = set()
    for c, indexes in picked:
        positions = tuple(c.span[j] for j in indexes)
        if used.intersection(positions):
            if selection is not None:
                raise SystemExit(f"{ref}: two chosen meanings highlight the same word")
            continue
        used.update(positions)
        out.append(WordGloss(ref=ref, word=shown_words(tokens, positions), gloss=c.gloss,
                             edition=c.entry.edition, lemma=c.entry.lemma, positions=positions))
        if selection is None and len(out) >= max_per_ayah:
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


def _day(value: object, where: str) -> date | None:
    """A day of project.yaml (YAML reads 2026-11-16 as a date); empty: None."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise SystemExit(f"{where}: «{value}» is not a day such as 2026-11-16") from None


def basmala_off(cfg: Config) -> tuple[date, date | None] | None:
    """content.basmala.days_off: the days the calendar's reels go without the basmala, as
    (first day, last day or None: until the owner turns it back on). None: no such days."""
    raw = (cfg.content.get("basmala") or {}).get("days_off")
    if not raw:
        return None
    where = "config/project.yaml, content.basmala.days_off"
    if not isinstance(raw, dict) or set(raw) - {"from", "until"}:
        raise SystemExit(f"{where}: only from and until, e.g. `from: 2026-11-16`")
    start = _day(raw.get("from"), f"{where}, from")
    end = _day(raw.get("until"), f"{where}, until")
    if start is None:
        raise SystemExit(f"{where}: give its first day, `from: 2026-11-16`")
    if end is not None and end < start:
        raise SystemExit(f"{where}: until ({end}) is before from ({start})")
    return start, end


def basmala_on(cfg: Config, day: date) -> bool:
    """Do the calendar's reels of that day open with the basmala? content.basmala.enabled,
    and the day outside content.basmala.days_off (owner's choice, 2026-11-15: none from
    2026-11-16, at the start of a surah too, until the owner turns it back on). On-demand
    reels: the form's «Basmala» box, ticked by default when this is true (ondemand/check.py)."""
    if not (cfg.content.get("basmala") or {}).get("enabled", False):
        return False
    off = basmala_off(cfg)
    return off is None or not (off[0] <= day and (off[1] is None or day <= off[1]))


def without_basmala(cfg: Config) -> Config:
    """The same configuration, every passage without the basmala (1:1 stays: an ayah)."""
    project = copy.deepcopy(cfg.project)
    project["content"].setdefault("basmala", {})["enabled"] = False
    return dataclasses.replace(cfg, project=project)


def for_day(cfg: Config, day: date) -> Config:
    """cfg as the calendar's reels of that day use it: without the basmala on its days off."""
    return cfg if basmala_on(cfg, day) else without_basmala(cfg)


def build(cfg: Config, key: str, src: Sources | None = None,
          glosses: dict[str, Selection] | None = None) -> Passage:
    """glosses: the owner's choice of word meanings, {"93:2": [(k, words)]} for every ayah
    (an ayah missing: none); None: the usual rules."""
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
            audio=src.audio.basmala(surah, basmala_stem(cfg)),
        )
    for r in refs:
        passage.ayahs.append(Ayah(
            ref=r,
            text=texts[r],
            translation=translations[r],
            glosses=anchor(r, entries[r], texts[r], cfg,
                           None if glosses is None else glosses.get(str(r), [])),
            audio=src.audio.fetch(r),
        ))
    return passage
