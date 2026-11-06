"""Is an on-demand request allowed? The same rules as the calendar, nothing looser.

- reciter: `auto` (the rotation's rule, reciters.best) or one of content.rotation that was
  never claimed (state `claimed`);
- passage: whole sentences only (rule 4: starts at ayah 1 or after an ayah that ends a
  sentence in Sahih International, ends with the surah or a sentence, as `series-check`);
- duration: at most content.passage.max_seconds (90 s) with that reciter, as its checked
  split says; a recording not split yet for this passage is split first (`split`);
- background: `auto` or an id of config/backgrounds.yaml;
- YouTube with a reciter its Content ID claims (platforms.youtube.exclude_reciters): YouTube
  is dropped, the others go ahead (owner's choice, 2026-11-06).

A refused request gets reasons and valid ranges to try (whole sentences, within the limit).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from quran_reels import reciters as rec
from quran_reels.config import Config
from quran_reels.models import AyahRef
from quran_reels.ondemand.request import AUTO, Request, words_text
from quran_reels.reciters import Option
from quran_reels.selector.plan import ends_sentence, sentence_ends, starts_sentence

MAX_SUGGESTIONS = 6
OK_STATUSES = ("published", "draft")


@dataclass
class Suggestion:
    key: str
    seconds: float | None          # None: unknown until the recording is split

    def __str__(self) -> str:
        return self.key + (f" ({self.seconds:.0f} s)" if self.seconds is not None else "")


@dataclass
class Checked:
    request: Request
    key: str = ""                              # normalised passage, e.g. 93:1-11
    surah_en: str = ""
    surah_ar: str = ""
    reciter: str = ""                          # the reciter chosen (auto resolved)
    seconds: float | None = None
    background: str | None = None              # None: chosen from the passage
    platforms: tuple[str, ...] = ()
    problems: list[str] = field(default_factory=list)      # refused when not empty
    suggestions: list[Suggestion] = field(default_factory=list)
    alternatives: list[Suggestion] = field(default_factory=list)   # other reciters, same key
    notes: list[str] = field(default_factory=list)
    split: str = ""                            # this reciter's recording to split first
    not_ready: str = ""                        # why the split is needed (for a refusal)
    reciter_label: str = ""
    options: list[Option] = field(default_factory=list)
    glosses: dict | None = None                # the owner's word meanings (passage.build)

    @property
    def ok(self) -> bool:
        return not self.problems and not self.split

    def as_dict(self) -> dict[str, Any]:
        return {"key": self.key, "surah_en": self.surah_en, "surah_ar": self.surah_ar,
                "reciter": self.reciter, "seconds": self.seconds,
                "background": self.background, "platforms": list(self.platforms),
                "problems": self.problems, "suggestions": [str(s) for s in self.suggestions],
                "alternatives": [str(s) for s in self.alternatives], "notes": self.notes,
                "split": self.split, "words": words_text(self.request.words), "request": {
                    "reciter": self.request.reciter, "passage": self.request.passage,
                    "background": self.request.background,
                    "platforms": list(self.request.platforms),
                    "words": words_text(self.request.words)}}


def allowed_reciters(cfg: Config, state: dict) -> list[str]:
    """Reciters an on-demand reel may use: the rotation's, minus those claimed on Meta."""
    claimed = set(state.get("claimed") or {})
    return [n for n in rec.rotation(cfg) if n not in claimed]


def label(cfg: Config, name: str) -> str:
    return ((cfg.content.get("reciters") or {}).get(name) or {}).get("label", name)


def why(option: Option) -> str:
    """reciters.passage_seconds' reason, for the owner."""
    text = option.why or (f"{option.seconds:.0f} s" if option.seconds is not None else "")
    text = re.sub(r"^surah (\d+) not split$", r"sourate \1 pas encore découpée", text)
    return re.sub(r"^(\S+) not checked$", r"\1 pas encore vérifiées", text)


def _excerpt(text: str, n: int = 70) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else "…" + text[-(n - 1):]


def candidates(start: int, end: int, ayahs: int, ends: set[int],
               plan: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Ranges close to start-end made of whole sentences: widened, narrowed, then the plan's
    passages that overlap it (config/plan.yaml, already whole sentences)."""
    out: list[tuple[int, int]] = []
    a_w = max(a for a in range(1, start + 1) if starts_sentence(a, ends))
    b_w = min(b for b in range(end, ayahs + 1) if ends_sentence(b, ayahs, ends))
    out.append((a_w, b_w))
    a_n = next((a for a in range(start, end + 1) if starts_sentence(a, ends)), None)
    b_n = next((b for b in range(end, start - 1, -1) if ends_sentence(b, ayahs, ends)), None)
    if a_n is not None and b_n is not None and a_n <= b_n:
        out.append((a_n, b_n))
    out += [(a, b) for a, b in plan if a <= end and b >= start]
    return list(dict.fromkeys(out))


def chunks(surah: int, start: int, end: int, ayahs: int, ends: set[int],
           seconds: Callable[[str], float | None], high: float) -> list[tuple[int, int]]:
    """A valid range too long for one video, cut at sentence ends into the longest pieces
    that fit (greedy). Stops at a piece that cannot fit or whose length is unknown."""
    out = []
    a = start
    stops = sorted(e for e in ends | {ayahs} if start <= e <= end)
    while a <= end:
        best = None
        for b in (e for e in stops if e >= a):
            d = seconds(f"{surah}:{a}-{b}")
            if d is None or d > high:
                break
            best = b
        if best is None:
            break
        out.append((a, best))
        a = best + 1
    return out


def by_hand(cfg: Config) -> frozenset[str]:
    """Passages posted outside the calendar (config/schedule.yaml, published_by_hand)."""
    try:
        from quran_reels.selector.calendar import load_schedule

        return load_schedule(cfg).published_by_hand
    except (SystemExit, OSError, AttributeError, TypeError):
        return frozenset()


def published_before(state: dict, key: str) -> list[str]:
    """Where this passage already went: calendar slots and earlier on-demand requests."""
    out = []
    for slot, r in sorted((state.get("slots") or {}).items()):
        done = [p for p, x in (r.get("results") or {}).items() if x.get("status") in OK_STATUSES]
        if r.get("passage") == key and done:
            out.append(f"calendrier, {slot} ({', '.join(done)})")
    for issue, r in sorted((state.get("on_demand") or {}).items()):
        done = [p for p, x in (r.get("results") or {}).items()
                if x.get("status") in OK_STATUSES]
        if r.get("passage") == key and done:
            out.append(f"à la demande, #{issue} ({', '.join(done)})")
    return out


def check(cfg: Config, req: Request, state: dict, src: Any = None,
          seconds: Callable[[str, str], Option] | None = None,
          plan: dict[int, list[tuple[int, int]]] | None = None,
          meanings: Callable[[str], list] | None = None) -> Checked:
    """The verdict on a request. seconds(reciter, key) → Option (reciters.passage_seconds by
    default); plan: {surah: [(start, end)]} (config/plan.yaml by default); meanings(key) →
    the source's word meanings for the passage (ondemand.words.meanings by default)."""
    if src is None:
        from quran_reels.sources import Sources

        src = Sources.from_config(cfg)
    src.quran.ensure(src.translation_slug)
    if seconds is None:
        def seconds(name: str, key: str) -> Option:
            return rec.passage_seconds(rec.with_reciter(cfg, name), key)
    memo: dict[tuple[str, str], Option] = {}

    def secs(name: str, key: str) -> Option:
        if (name, key) not in memo:
            memo[(name, key)] = seconds(name, key)
        return memo[(name, key)]

    out = Checked(request=req, platforms=tuple(req.platforms))
    catalogue = cfg.content.get("reciters") or {}
    allowed = allowed_reciters(cfg, state)
    high = float(cfg.content["passage"]["max_seconds"])

    if req.reciter != AUTO:
        if req.reciter not in catalogue:
            out.problems.append(f"récitateur « {req.reciter} » inconnu (au choix : auto, "
                                f"{', '.join(allowed)})")
        elif req.reciter not in allowed:
            reason = ("écarté après une revendication sur Meta" if req.reciter in
                      (state.get("claimed") or {}) else "hors de la rotation")
            out.problems.append(f"{label(cfg, req.reciter)} n'est pas autorisé pour la "
                                f"publication ({reason}) ; au choix : auto, {', '.join(allowed)}")
    if req.background != AUTO:
        ids = [str(b.get("id")) for b in cfg.backgrounds.get("backgrounds") or []]
        if req.background not in ids:
            out.problems.append(f"fond « {req.background} » absent de config/backgrounds.yaml "
                                f"(au choix : auto, {', '.join(ids)})")
        else:
            out.background = req.background

    chapter = src.quran.chapters.get(req.surah)
    ayahs = int(chapter["verses_count"])
    out.surah_en, out.surah_ar = chapter["name_simple"], chapter["name_arabic"]
    start, end = (1, ayahs) if req.whole else (req.start, req.end)
    if end > ayahs:
        out.problems.append(f"la sourate {req.surah} ({out.surah_en}) a {ayahs} ayahs")
        return out
    out.key = f"{req.surah}:{start}-{end}"
    refs = [AyahRef(req.surah, a) for a in range(1, ayahs + 1)]
    texts = {r.ayah: t for r, t in src.quran.translate(src.translation_slug, refs).items()}
    ends = sentence_ends(texts)
    cut = False
    if not starts_sentence(start, ends):
        cut = True
        out.problems.append(f"{out.key} commence au milieu d'une phrase : {req.surah}:{start - 1}"
                            f" ne la finit pas (« {_excerpt(texts[start - 1])} »)")
    if not ends_sentence(end, ayahs, ends):
        cut = True
        out.problems.append(f"{out.key} finit au milieu d'une phrase : {req.surah}:{end} ne la "
                            f"finit pas (« {_excerpt(texts[end])} »)")

    # Who recites, and how long it lasts.
    names = allowed if req.reciter == AUTO else [req.reciter]
    if req.reciter == AUTO:
        out.options = [secs(n, out.key) for n in allowed]
        from quran_reels.selector.calendar import State

        order = {"morning": 0, "evening": 1}
        chosen = rec.best(cfg, out.options, rec.recent_reciters(State(dict(state)), order))
        if chosen:
            out.reciter = chosen
            out.seconds = secs(chosen, out.key).seconds
        elif not out.problems:
            reasons = "; ".join(f"{label(cfg, o.name)} : {why(o)}" for o in out.options)
            out.problems.append(f"aucun récitateur prêt pour {out.key} en {high:.0f} s au "
                                f"plus ({reasons})")
    elif req.reciter in allowed:
        out.reciter = req.reciter
        opt = secs(req.reciter, out.key)
        out.seconds = opt.seconds
        if opt.seconds is None:
            out.not_ready = why(opt)
            out.alternatives = [Suggestion(label(cfg, n), o.seconds) for n in allowed
                                if n != req.reciter for o in [secs(n, out.key)]
                                if o.seconds is not None and o.seconds <= high]
            if catalogue[req.reciter].get("surah_url") and not out.problems:
                out.split = req.reciter
            elif not out.problems:
                out.problems.append(f"{label(cfg, req.reciter)} pas prêt pour {out.key} : "
                                    f"{why(opt)}")
        elif opt.seconds > high:
            out.problems.append(f"{out.key} dure {opt.seconds:.0f} s avec "
                                f"{label(cfg, req.reciter)}, plus que {high:.0f} s")
            out.alternatives = [Suggestion(label(cfg, n), o.seconds) for n in allowed
                                if n != req.reciter
                                for o in [secs(n, out.key)]
                                if o.seconds is not None and o.seconds <= high]

    too_long = out.seconds is not None and out.seconds > high
    if req.reciter == AUTO and not out.reciter:
        too_long = any(o.seconds is not None and o.seconds > high for o in out.options)
    if cut or too_long:
        def dur(key: str) -> float | None:
            ready = [secs(n, key).seconds for n in names if n in allowed]
            ready = [d for d in ready if d is not None]
            return min(ready) if ready else None

        if plan is None:
            from quran_reels.models import parse_passage
            from quran_reels.selector.calendar import load_plan

            plan = {s: [parse_passage(e.key)[1:] for e in entries]
                    for s, entries in load_plan(cfg).items()}
        found = candidates(start, end, ayahs, ends, plan.get(req.surah, []))
        if too_long and not cut:
            found = chunks(req.surah, start, end, ayahs, ends, dur, high) + found
        for a, b in dict.fromkeys(found):
            key = f"{req.surah}:{a}-{b}"
            d = dur(key)
            if key != out.key and (d is None or d <= high):
                out.suggestions.append(Suggestion(key, d))
            if len(out.suggestions) >= MAX_SUGGESTIONS:
                break

    out.reciter_label = label(cfg, out.reciter) if out.reciter else ""
    if out.key and req.words is not None:          # the owner's word meanings (/mots)
        if not req.words:
            out.glosses = {}
        else:
            from quran_reels.ondemand import words as words_mod

            found = (meanings or (lambda k: words_mod.meanings(cfg, src, k)))(out.key)
            out.glosses, problems = words_mod.selection(cfg, found, req.words)
            out.problems += problems
    if out.reciter and "youtube" in out.platforms and \
            out.reciter in rec.excluded_on(cfg, "youtube"):
        out.platforms = tuple(p for p in out.platforms if p != "youtube")
        others = [label(cfg, n) for n in allowed if n not in rec.excluded_on(cfg, "youtube")]
        msg = (f"YouTube retiré : {label(cfg, out.reciter)} y est revendiqué par Content ID "
               f"(un Short de plus d'une minute revendiqué est bloqué partout) ; pour YouTube, "
               f"une autre demande avec : {', '.join(others)}")
        (out.notes if out.platforms else out.problems).append(msg)
    if out.key:
        for where in published_before(state, out.key):
            out.notes.append(f"déjà publié : {where}")
        if out.key in by_hand(cfg):
            out.notes.append("déjà publié à la main, hors calendrier (schedule.yaml, "
                             "published_by_hand)")
    return out
