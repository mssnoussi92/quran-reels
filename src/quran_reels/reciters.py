"""Which reciter recites a passage (content.rotation in config/project.yaml).

The owner's reciters (2026-11-05): Omar Hisham, Al-Minshawi, Saad Al-Ghamdi, Nabil Ar-Rifai,
Tawfiq As-Sayegh, Salah Budair. For each passage, among those that are ready for it (their
recording split and every needed ayah checked, config/splits/) and fit in max_seconds:

1. not one of the last `avoid_last` reciters published (variety), unless no other fits;
2. the closest to target_seconds: a long passage goes to a quick reciter (As-Sayegh,
   Ar-Rifai: about 0.77 of Alafasy's time), a short surah to a slower one (Al-Minshawi 1.16,
   Omar Hisham); ties go to the order of the list.

Deterministic: the same state gives the same choice. When no reciter of the rotation is ready,
nothing is published for that slot (an error names the command that prepares it).

A platform may have its own reciter, whatever the rotation chose (platforms.<name>.reciter:
YouTube, always Tawfiq As-Sayegh, owner's choice 2026-11-11): other_for.
"""

from __future__ import annotations

import copy
import dataclasses
import re
from collections.abc import Iterable
from dataclasses import dataclass

from quran_reels.config import Config
from quran_reels.models import parse_passage


@dataclass(frozen=True)
class Option:
    name: str
    seconds: float | None        # None: not ready (recording not split or not checked)
    why: str = ""


def rotation(cfg: Config | None) -> list[str]:
    """The reciters chosen from, per passage; empty: content.reciter for every passage."""
    if cfg is None:
        return []
    return list((cfg.content.get("rotation") or {}).get("reciters") or [])


def with_reciter(cfg: Config, name: str) -> Config:
    """The same configuration with another reciter of the catalogue."""
    catalogue = cfg.content.get("reciters") or {}
    if name not in catalogue:
        raise SystemExit(f"unknown reciter {name!r}: config/project.yaml has {', '.join(catalogue)}")
    project = copy.deepcopy(cfg.project)
    project["content"]["reciter"] = {"name": name, **catalogue[name]}
    return dataclasses.replace(cfg, project=project)


def passage_seconds(cfg: Config, key: str) -> Option:
    """How long the passage lasts with cfg's reciter (basmala, lead and tail included)."""
    from quran_reels.passage import needs_basmala
    from quran_reels.sources import Sources
    from quran_reels.sources.surah_audio import MIN_MATCH, SurahFiles

    name = cfg.content["reciter"]["name"]
    surah, start, end = parse_passage(key)
    src = Sources.from_config(cfg)
    v = cfg.video
    overhead = float(v.get("lead_seconds", 0.4)) + float(v.get("tail_seconds", 1.2))
    if isinstance(src.audio, SurahFiles):
        if not src.audio.split_path(surah).is_file():
            return Option(name, None, f"surah {surah} not split")
        segments = src.audio.segments(surah)
        match = src.audio.matches(surah)
        labels = [str(a) for a in range(start, end + 1)]
        if needs_basmala(cfg, surah, start):
            labels.insert(0, "basmala" if surah not in (1, 9) else "1")
        missing = [k for k in labels if match.get(k, 0) < MIN_MATCH]
        if missing:
            return Option(name, None, f"{surah}:{','.join(missing)} not checked")
        return Option(name, round(sum(segments[k][1] - segments[k][0] for k in labels)
                              + overhead, 1))
    src.quran.ensure(src.translation_slug)
    seconds = src.ayah_seconds(cfg, surah)
    total = sum(seconds[a] for a in range(start, end + 1)) + overhead
    if needs_basmala(cfg, surah, start):
        total += src.basmala_seconds(cfg, surah)
    return Option(name, round(total, 1))


def options(cfg: Config, key: str, claimed: Iterable[str] = ()) -> list[Option]:
    """Each reciter of the rotation for key; a claimed one (Meta muted or blocked one of its
    reels: state `claimed`, daily.py) is never ready again."""
    claimed = set(claimed)
    return [Option(name, None, "écarté : un de ses reels a été revendiqué sur Meta")
            if name in claimed else passage_seconds(with_reciter(cfg, name), key)
            for name in rotation(cfg)]


def choose(cfg: Config, key: str, recent: list[str], claimed: Iterable[str] = ()
           ) -> tuple[str, list[Option]]:
    """The reciter for a passage, and every option considered (for the log).
    recent: reciters published so far, oldest first; claimed: never chosen."""
    opts = options(cfg, key, claimed)
    name = best(cfg, opts, recent)
    if name is None:
        why = "; ".join(f"{o.name}: {o.why or f'{o.seconds} s'}" for o in opts)
        raise SystemExit(f"{key}: no reciter of the rotation is ready ({why}); "
                         f"prepare it with: quran-reels split {key}")
    return name, opts


def best(cfg: Config, opts: list[Option], recent: list[str]) -> str | None:
    """The rotation's rule on given options: ready and within max_seconds, not one of the last
    `avoid_last` published unless none else fits, then the closest to target_seconds (ties:
    the list's order). None when no option fits."""
    rot = cfg.content.get("rotation") or {}
    p = cfg.content["passage"]
    high, target = float(p["max_seconds"]), float(p.get("target_seconds", 60))
    fits = [o for o in opts if o.seconds is not None and o.seconds <= high]
    if not fits:
        return None
    avoid = set(recent[-int(rot.get("avoid_last", 2)):]) if rot.get("avoid_last", 2) else set()
    pool = [o for o in fits if o.name not in avoid] or fits
    return min(pool, key=lambda o: abs(o.seconds - target)).name     # min keeps the list order


def excluded_on(cfg: Config, platform: str) -> set[str]:
    """Reciters a platform claims but the others do not (platforms.<name>.exclude_reciters):
    YouTube's Content ID has Salah Budair, Meta does not."""
    return set(((cfg.project.get("platforms") or {}).get(platform) or {})
               .get("exclude_reciters") or [])


def fixed_on(cfg: Config, platform: str) -> str | None:
    """The one reciter a platform takes (platforms.<name>.reciter): YouTube, always Tawfiq
    As-Sayegh (owner's choice, 2026-11-11). None: any reciter it does not exclude."""
    name = ((cfg.project.get("platforms") or {}).get(platform) or {}).get("reciter")
    return str(name) if name else None


def fixed_reciters(cfg: Config) -> list[str]:
    """The reciters some platform always takes, to prepare like the rotation's (prepare)."""
    return list(dict.fromkeys(name for platform in (cfg.project.get("platforms") or {})
                              if (name := fixed_on(cfg, platform))))


def allowed_on(cfg: Config, platform: str, reciter: str) -> bool:
    """May a reel by `reciter` go to `platform` as it is? Its own reciter only, when it has
    one; else any reciter it does not exclude."""
    fixed = fixed_on(cfg, platform)
    return reciter == fixed if fixed else reciter not in excluded_on(cfg, platform)


def choose_for(cfg: Config, platform: str, reciter: str, opts: list[Option]) -> str | None:
    """Who recites the passage on a platform without its own reciter: the rotation's choice,
    unless the platform excludes it; then the ready reciter closest to target_seconds within
    the platform's max_seconds (YouTube Shorts: 3 min) that it does not exclude. None: no one
    fits."""
    excluded = excluded_on(cfg, platform)
    if reciter not in excluded:
        return reciter
    high, target = _limits(cfg, platform)
    fits = [o for o in opts if o.seconds is not None and o.seconds <= high
            and o.name not in excluded]
    return min(fits, key=lambda o: abs(o.seconds - target)).name if fits else None


def other_for(cfg: Config, platform: str, key: str, reciter: str,
              claimed: Iterable[str] = ()) -> Option | None:
    """Who recites `key` on `platform` when the reel is by `reciter` and may not go there as
    it is (allowed_on); None: the same video goes there.

    A platform with its own reciter (fixed_on) gets him and no one else: ready when his split
    of the passage is checked and it fits the platform's max_seconds. A claim on Meta (state
    `claimed`) does not count: YouTube's Content ID is not Meta's Rights Manager.
    Otherwise choose_for, among the rotation's reciters.
    Option.seconds None: no one can, Option.why says why (nothing goes to the platform)."""
    if allowed_on(cfg, platform, reciter):
        return None
    own = own_option(cfg, platform, key)
    if own is not None:
        return own
    opts = options(cfg, key, claimed)
    name = choose_for(cfg, platform, reciter, opts)
    if name is None:
        return Option("", None, "aucun autre récitateur prêt pour ce passage")
    return next(o for o in opts if o.name == name)


def own_option(cfg: Config, platform: str, key: str) -> Option | None:
    """A platform's own reciter for a passage (fixed_on; None without one): ready when his
    split of the passage is checked and it fits the platform's max_seconds."""
    fixed = fixed_on(cfg, platform)
    if not fixed:
        return None
    high, _ = _limits(cfg, platform)
    opt = passage_seconds(with_reciter(cfg, fixed), key)
    if opt.seconds is not None and opt.seconds > high:
        return Option(fixed, None, f"{opt.seconds:.0f} s, over {high:.0f} s")
    return opt


def fixed_gaps(cfg: Config, platform: str, keys: Iterable[str]) -> dict[str, str]:
    """The passages a platform's own reciter is not ready for, with the reason (prepare):
    each would get nothing on that platform. Empty without an own reciter."""
    return {key: opt.why for key in keys
            if (opt := own_option(cfg, platform, key)) is not None and opt.seconds is None}


def _limits(cfg: Config, platform: str) -> tuple[float, float]:
    """(longest video the platform takes, target_seconds)."""
    conf = (cfg.project.get("platforms") or {}).get(platform) or {}
    p = cfg.content["passage"]
    return float(conf.get("max_seconds") or p["max_seconds"]), float(p.get("target_seconds", 60))


def why(option: Option) -> str:
    """passage_seconds' reason, for the owner (captions issue, on-demand answers)."""
    text = option.why or (f"{option.seconds:.0f} s" if option.seconds is not None else "")
    text = re.sub(r"^surah (\d+) not split$", r"sourate \1 pas encore découpée", text)
    text = re.sub(r"^(\d+) s, over (\d+) s$", r"\1 s, plus que \2 s", text)
    return re.sub(r"^(\S+) not checked$", r"\1 pas encore vérifiées", text)


def claimed_reciters(state) -> set[str]:
    """Reciters taken out after a claim (selector.calendar.State, key `claimed`)."""
    return set(state.data.get("claimed") or {})


def recent_reciters(state, slot_order: dict[str, int]) -> list[str]:
    """Reciters of the published slots, oldest first (state: selector.calendar.State)."""
    def order(key: str) -> tuple[str, int]:
        day, slot = key.split("/")
        return day, slot_order.get(slot, 0)
    return [rec["reciter"] for key, rec in sorted(state.data["slots"].items(),
                                                  key=lambda kv: order(kv[0]))
            if rec.get("reciter")]
