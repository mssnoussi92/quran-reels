"""Reciters: the list of config/project.yaml, what the state says about each, and the
recitations of EveryAyah not in the list yet (candidates).

Every reciter gets the same sample (SAMPLE_SURAH) so that the voices can be compared. Audio
is never copied: the page plays the files from their source (EveryAyah, mp3quran.net,
archive.org).
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from quran_reels.catalog import issues
from quran_reels.config import Config
from quran_reels.selector.calendar import OK_STATUSES
from quran_reels.sources.everyayah import BASE as EVERYAYAH

SAMPLE_SURAH = 112                # Al-Ikhlas: short, recited by every reciter of the list
SAMPLE_AYAHS = 4
RECITATIONS_URL = f"{EVERYAYAH}/recitations.js"

_STYLES = ("murattal", "mujawwad", "muallim")
_SITES = re.compile(r"\b(QuranExplorer\.Com|KetabAllah\.Net)\b", re.IGNORECASE)
_KBPS = re.compile(r"(\d+)\s*kbps", re.IGNORECASE)
_STOP = {"al", "ar", "as", "ash", "ad", "an", "el", "ibn", "bin", "abu"}


# ---- sources and samples ----------------------------------------------------------------

def source_of(r: dict[str, Any]) -> dict[str, str]:
    """Where a reciter's audio comes from: name of the site and a page to open."""
    url = r.get("surah_url")
    if not url:
        return {"name": "EveryAyah", "kind": "un MP3 par ayah",
                "page": f"{EVERYAYAH}/{r['id']}/"}
    host = urlparse(url).netloc
    if host.endswith("archive.org"):
        item = urlparse(url).path.split("/")[2]
        return {"name": "archive.org", "kind": "sourates entières, copies de tiers",
                "page": f"https://archive.org/details/{item}"}
    if "mp3quran" in host:
        return {"name": "mp3quran.net", "kind": "sourates entières + minutage par ayah",
                "page": url.format(surah=SAMPLE_SURAH)}
    return {"name": host, "kind": "sourates entières", "page": url.format(surah=SAMPLE_SURAH)}


def sample(cfg: Config, r: dict[str, Any]) -> list[str]:
    """URLs played one after the other: the basmala and Al-Ikhlas, from the source."""
    if r.get("surah_url"):                    # the surah's file starts with the basmala
        return [r["surah_url"].format(surah=SAMPLE_SURAH)]
    stem = r.get("basmala") or (cfg.content.get("basmala") or {}).get("audio", "bismillah")
    return everyayah_sample(r["id"], stem)


def everyayah_sample(folder: str, basmala: str = "bismillah") -> list[str]:
    return [f"{EVERYAYAH}/{folder}/{basmala}.mp3"] + [
        f"{EVERYAYAH}/{folder}/{SAMPLE_SURAH:03d}{a:03d}.mp3" for a in range(1, SAMPLE_AYAHS + 1)]


# ---- names ------------------------------------------------------------------------------

def tokens(name: str) -> list[str]:
    words = re.findall(r"[a-z]+", name.lower())
    return [w for w in words if w not in _STOP and w not in _STYLES and w != "kbps"]


def _close(a: str, b: str) -> bool:
    return SequenceMatcher(None, a, b).ratio() >= 0.8


def same_reciter(everyayah_name: str, label: str) -> bool:
    """«Ghamadi» is Saad Al-Ghamdi, «Salah Al Budair» Salah Budair, «Hani Rifai» is not Nabil
    Ar-Rifai: the family name must match, and every other name given too."""
    ea, ours = tokens(everyayah_name), tokens(label)
    if not ea or not ours:
        return False
    family = ours[-1]
    hit = next((t for t in ea if _close(t, family)), None)
    if hit is None:
        return False
    return all(any(_close(t, o) for o in ours) for t in ea if t != hit)


def clean(name: str) -> tuple[str, str]:
    """EveryAyah's display name → (reciter, style): «Husary (Muallim)» → (Husary, muallim)."""
    n = _SITES.sub(" ", name.replace("_", " "))
    n = _KBPS.sub(" ", n)
    style = ""
    for word in re.findall(r"[A-Za-z]+", n):
        if word.lower() in _STYLES:
            style = word.lower()
    n = re.sub(r"\([^)]*\)", " ", n)
    n = " ".join(w for w in n.split() if w.lower() not in _STYLES)
    return n.strip(" -"), style


def recitations(text: str) -> list[dict[str, Any]]:
    """EveryAyah's recitations.js: {"1": {"subfolder", "name", "bitrate"}, ...}."""
    raw = json.loads(text)
    out = []
    for v in raw.values():
        if not isinstance(v, dict) or "subfolder" not in v:
            continue
        m = _KBPS.search(v.get("bitrate", "")) or _KBPS.search(v["subfolder"])
        out.append({"folder": v["subfolder"], "name": v.get("name", ""),
                    "kbps": int(m[1]) if m else 0})
    return out


def _excluded(r: dict[str, Any]) -> str:
    folder, name = r["folder"].lower(), r["name"].lower()
    if folder.startswith(("translations/", "english/", "multilanguage/")) \
            or "translat" in name or "(english)" in name:
        return "translation"
    if folder.startswith("warsh/") or "warsh" in name:
        return "warsh"
    return ""


def candidates(cfg: Config, rows: list[dict[str, Any]]) -> tuple[list[dict], dict[str, list],
                                                                  dict[str, int]]:
    """(candidates, EveryAyah folders of reciters already listed, recitations left out).

    One candidate per reciter and style (bitrates grouped). Left out: translations, and Warsh
    recitations (the text shown is Hafs).
    """
    listed = cfg.content.get("reciters") or {}
    own = {r["id"] for r in listed.values()}
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    names: dict[tuple[str, str], str] = {}
    known: dict[str, list] = defaultdict(list)
    left_out: dict[str, int] = defaultdict(int)
    for r in rows:
        why = _excluded(r)
        if why:
            left_out[why] += 1
            continue
        name, style = clean(r["name"])
        match = next((n for n, x in listed.items()
                      if r["folder"] == x["id"] or same_reciter(name, x.get("label", n))), None)
        if match:
            if r["folder"] not in own:
                known[match].append({"folder": r["folder"], "kbps": r["kbps"],
                                     "style": style, "page": f"{EVERYAYAH}/{r['folder']}/"})
            continue
        key = ("".join(tokens(name)) or name.lower(), style)
        groups[key].append(r)
        if key not in names or len(name) < len(names[key]):
            names[key] = name                     # the plainest spelling
    out = []
    for key, rows_ in groups.items():
        rows_.sort(key=lambda r: -r["kbps"])
        best = rows_[0]
        label = names[key] + (f" ({key[1]})" if key[1] else "")
        facts = {"Dossier EveryAyah": best["folder"], "Débit": f"{best['kbps']} kb/s",
                 "Écouter": f"{EVERYAYAH}/{best['folder']}/{SAMPLE_SURAH:03d}001.mp3"}
        out.append({
            "id": "cand-" + re.sub(r"[^a-z0-9]+", "-", f"{key[0]}-{key[1]}".lower()).strip("-"),
            "label": label, "style": key[1] or "murattal",
            "folders": [{"folder": r["folder"], "kbps": r["kbps"],
                         "page": f"{EVERYAYAH}/{r['folder']}/"} for r in rows_],
            "sample": everyayah_sample(best["folder"]),
            "page": f"{EVERYAYAH}/{best['folder']}/",
            "issue": issues.add_candidate(best["folder"], label, facts)})
    out.sort(key=lambda c: c["label"].lower())
    return out, dict(known), dict(left_out)


# ---- the list ---------------------------------------------------------------------------

def split_surahs(cfg: Config, reciter_id: str, state_dir: Path | None) -> int:
    """How many surahs have a split (committed, or on the state branch)."""
    dirs = [cfg.root / "config" / "splits" / reciter_id]
    if state_dir:
        dirs.append(state_dir / "splits" / reciter_id)
    return len({p.name for d in dirs if d.is_dir() for p in d.glob("*.json")})


def _slot_label(key: str) -> str:
    from datetime import date

    from quran_reels.catalog.schedule import SLOTS_FR, day_label

    day, _, slot = key.partition("/")
    return f"{day_label(date.fromisoformat(day))}, {SLOTS_FR.get(slot, slot)}"


def _ok(record: dict) -> bool:
    return any(r.get("status") in OK_STATUSES for r in (record.get("results") or {}).values())


def collect(cfg: Config, state: dict, history: dict, state_dir: Path | None,
            everyayah: list[dict[str, Any]] | None) -> dict[str, Any]:
    content = cfg.content
    listed = content.get("reciters") or {}
    rotation = list((content.get("rotation") or {}).get("reciters") or [])
    default = content["reciter"]["name"] if isinstance(content.get("reciter"), dict) \
        else content.get("reciter")
    claimed = state.get("claimed") or {}

    published: dict[str, list[str]] = defaultdict(list)
    unattributed = 0
    for key, rec in sorted((state.get("slots") or {}).items()):
        if not _ok(rec):
            continue
        if rec.get("reciter"):
            published[rec["reciter"]].append(key)
        else:
            unattributed += 1
    removed: dict[str, list[dict]] = defaultdict(list)
    for item in state.get("removed") or []:
        rec = item.get("record") or {}
        if rec.get("reciter"):
            removed[rec["reciter"]].append({"slot": item.get("slot", ""),
                                            "passage": rec.get("passage", ""),
                                            "why": item.get("why", "")})

    known: dict[str, list] = {}
    cands: list[dict] = []
    left_out: dict[str, int] = {}
    if everyayah is not None:
        cands, known, left_out = candidates(cfg, everyayah)

    cards = []
    for name, r in listed.items():
        status = "rotation" if name in rotation else "retired"
        if not rotation and name == default:
            status = "rotation"
        events = [dict(e, date=str(e.get("date", ""))) for e in
                  (history.get("reciters") or {}).get(name) or []]
        if name in claimed:
            c = claimed[name]
            events.append({"date": str(c.get("at", ""))[:10], "kind": "claim",
                           "text": f"{c.get('passage', '')} : {c.get('reason', '')} "
                                   "(écarté automatiquement)"})
        src = source_of(r)
        facts = {"Récitateur": r.get("label", name), "Source": f"{src['name']} ({src['kind']})",
                 "Droits": r.get("rights", ""),
                 "Vidéos publiées": len(published.get(name, [])),
                 "Revendications": "; ".join(e["text"] for e in events if e["kind"] == "claim")}
        card = {
            "name": name, "label": r.get("label", name), "producer": r.get("producer", ""),
            "status": status, "default": name == default, "source": src,
            "rights": r.get("rights", ""), "hashtags": list(r.get("hashtags") or []),
            "published": len(published.get(name, [])),
            "last": _slot_label(published[name][-1]) if published.get(name) else "",
            "removed": removed.get(name, []), "events": events,
            "claimed": name in claimed or any(e["kind"] == "claim" for e in events),
            "sample": sample(cfg, r),
            "splits": split_surahs(cfg, r["id"], state_dir) if r.get("surah_url") else None,
            "also_everyayah": known.get(name, []) if r.get("surah_url") else [],
            "issue": (issues.remove_reciter(name, r.get("label", name), facts)
                      if status == "rotation" else
                      issues.add_reciter(name, r.get("label", name), facts)),
        }
        cards.append(card)
    order = {n: i for i, n in enumerate(rotation)}
    cards.sort(key=lambda c: (c["status"] != "rotation", order.get(c["name"], 99)))
    return {"sample": {"surah": SAMPLE_SURAH, "ayahs": SAMPLE_AYAHS},
            "rotation": rotation, "avoid_last": (content.get("rotation") or {}).get("avoid_last"),
            "list": cards, "unattributed": unattributed,
            "candidates": cands, "candidates_left_out": left_out,
            "candidates_source": RECITATIONS_URL if everyayah is not None else ""}
