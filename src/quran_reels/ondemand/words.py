"""Which words are highlighted and explained: the owner's choice on an on-demand reel.

The meanings come from the source only (غريب التفسير الميسر, rule 1): the owner chooses
among the entries the source gives for the passage's ayahs, never writes one. The preview
numbers them (1, 2, … over the passage, in the source's order); `/mots 2 5` keeps those,
`/mots 5=قلى` highlights that word of the quotation, `/mots aucun` none, `/mots auto` the
usual rules (config/glosses.yaml, at most max_per_ayah per ayah).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from quran_reels.arabic import quoted_words, words
from quran_reels.config import Config
from quran_reels.models import AyahRef, parse_passage
from quran_reels.ondemand.request import Words
from quran_reels.passage import Choice, Selection, choices, default_indexes, editorial_choices, pick
from quran_reels.passage import shown_words as _shown


@dataclass
class Meaning:
    n: int                          # number in the preview's list
    ref: str                        # "93:2"
    choice: Choice
    tokens: list[str]               # the ayah's words
    default: list[int]              # indexes in the quotation highlighted by default

    @property
    def usable(self) -> bool:
        return self.choice.usable

    @property
    def quoted(self) -> str:
        return self.choice.entry.lemma

    @property
    def why(self) -> str:
        if self.choice.span is None:
            return "pas retrouvé dans le texte de l'ayah"
        return "" if self.choice.gloss else "sens trop long pour l'écran (phrases entières)"

    def word(self, indexes: list[int] | None = None) -> str:
        """The highlighted words as the box shows them."""
        if not self.usable:
            return self.quoted
        idx = self.default if indexes is None else indexes
        return _shown(self.tokens, tuple(self.choice.span[j] for j in idx))

    def as_dict(self, shown: bool = False) -> dict[str, Any]:
        return {"n": self.n, "ref": self.ref, "quoted": self.quoted, "word": self.word(),
                "gloss": self.choice.gloss or "", "usable": self.usable, "why": self.why,
                "shown": shown}


def meanings(cfg: Config, src: Any, key: str) -> list[Meaning]:
    """Every word meaning of the source for the passage, numbered from 1."""
    surah, start, end = parse_passage(key)
    refs = [AyahRef(surah, a) for a in range(start, end + 1)]
    texts = src.quran.text(refs)
    entries = src.glosses.entries(refs, src.quran.global_index)
    out: list[Meaning] = []
    for r in refs:
        found = choices(r, entries[r], texts[r], cfg, warn=False)
        editorial = editorial_choices(r, [c for c in found if c.usable], cfg, warn=False)
        tokens = words(texts[r])
        for c in found:
            out.append(Meaning(len(out) + 1, str(r), c, tokens,
                               default_indexes(c, editorial) if c.usable else []))
    return out


def selection(cfg: Config, found: list[Meaning], chosen: Words
              ) -> tuple[dict[str, Selection], list[str]]:
    """The owner's numbers → {ayah: [(k, words)]} for passage.build, and the problems."""
    max_per_ayah = int(cfg.content["glosses"].get("max_per_ayah", 2))
    by_n = {m.n: m for m in found}
    out: dict[str, Selection] = {}
    used: dict[str, dict[int, int]] = {}         # ayah → position → number
    problems: list[str] = []
    for n, ws in chosen:
        m = by_n.get(n)
        if m is None:
            problems.append(f"mot n° {n} : il n'y en a que {len(found)} pour ce passage"
                            if found else "le Muyassar n'explique aucun mot de ce passage")
            continue
        if not m.usable:
            problems.append(f"mot n° {n} ({m.quoted}) : {m.why}")
            continue
        idx = m.default
        if ws:
            idx = pick(ws, quoted_words(m.quoted))
            if idx is None:
                problems.append(f"mot n° {n} : « {' '.join(ws)} » n'est pas dans la citation "
                                f"du Muyassar « {m.quoted} »")
                continue
        positions = [m.choice.span[j] for j in idx]
        taken = used.setdefault(m.ref, {})
        clash = sorted({taken[p] for p in positions if p in taken})
        if clash:
            problems.append(f"mots n° {clash[0]} et {n} surlignent le même mot de {m.ref}")
            continue
        taken.update(dict.fromkeys(positions, n))
        out.setdefault(m.ref, []).append((m.choice.k, tuple(ws)))
    for ref, picked in out.items():
        if len(picked) > max_per_ayah:
            problems.append(f"{ref} : {len(picked)} mots choisis, {max_per_ayah} au plus par "
                            "ayah (la place à l'écran)")
    return out, problems


def shown_numbers(found: list[Meaning], manifest: dict) -> set[int]:
    """Numbers of the meanings a rendered reel shows (manifest.json)."""
    shown = {(a["ref"], g["lemma"]) for a in manifest.get("ayahs") or []
             for g in a.get("glosses") or []}
    return {m.n for m in found if (m.ref, m.quoted) in shown}
