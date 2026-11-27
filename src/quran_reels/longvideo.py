"""A whole surah as one long video on YouTube (16:9), every word meaning of the Muyassar on it.

Owner's request, 2026-11-27: « tout sourat Kahf en 16:9 avec le maximum du tafsir sur les mots
possible ». config/long.yaml: the reels' renderer (render_passage) with
the 1920×1080 template long.html.j2, all the word meanings of each ayah (long.glosses), the
basmala first, YouTube's reciter (platforms.youtube.reciter), a generated scene drawn in 16:9.

Then, as for any YouTube version (rule 6): Meta's copyright check of the same sound before it goes
anywhere (publish.rights_only), in pieces a Facebook reel can take (long.check_seconds), each an
upright copy of its stretch of the video; every piece clear, or nothing goes up. YouTube: once
(state long.json, and a video of the same title among the channel's latest is not sent again),
public, Arabic declared, its title and description Arabic first, chapters, thumbnail.

    quran-reels long render 18                       # out/long/018_001-110.mp4, thumbnail.jpg
    quran-reels long publish 18 --state long.json    # render, Meta's check, YouTube
"""

from __future__ import annotations

import copy
import dataclasses
import json
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from quran_reels.config import Config
from quran_reels.reciters import with_reciter

LONG_DIR = "long"
_ARABIC = re.compile(r"[؀-ۿ]")


def settings(cfg: Config) -> dict[str, Any]:
    """config/long.yaml (its own file: the reels' cache is keyed on project.yaml)."""
    import yaml

    path = cfg.root / "config" / "long.yaml"
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.is_file() else {}


def reciter_of(cfg: Config) -> str:
    """YouTube's reciter (platforms.youtube.reciter), else the configured one."""
    yt = (cfg.project.get("platforms") or {}).get("youtube") or {}
    return yt.get("reciter") or cfg.content["reciter"]


def config_for(cfg: Config, reciter: str | None = None) -> Config:
    """cfg for a long video: its frame and template, every word meaning, the basmala, the
    reciter, out/long/."""
    s = settings(cfg)
    c = with_reciter(cfg, reciter or reciter_of(cfg))
    project = copy.deepcopy(c.project)
    project["video"].update(copy.deepcopy(s.get("video") or {}))
    project["video"].pop("hook", None)                  # no question: the whole surah
    project["content"]["glosses"].update(s.get("glosses") or {})
    project["content"].setdefault("basmala", {})["enabled"] = True
    return dataclasses.replace(c, project=project, out_dir=cfg.out / LONG_DIR)


def key_for(cfg: Config, surah: int) -> str:
    from quran_reels.sources import Sources

    src = Sources.from_config(cfg)
    src.quran.ensure(src.translation_slug)
    return f"{surah}:1-{src.quran.chapters[surah]['verses_count']}"


def render(cfg: Config, surah: int, reciter: str | None = None):
    """The surah's long video and its thumbnail (out/long/<slug>/thumbnail.jpg)."""
    from quran_reels.render import render_passage

    lcfg = config_for(cfg, reciter)
    result = render_passage(lcfg, key_for(lcfg, surah), variants=False,
                            background=settings(cfg).get("background"))
    thumbnail(lcfg, result)
    return result


def thumbnail(lcfg: Config, result) -> Path:
    """1280×720 JPEG: the surah's name large over a still of the scene, what the video holds."""
    from quran_reels.render.frames import FrameRenderer
    from quran_reels.sources import backgrounds

    p = result.passage
    reciter = lcfg.content["reciter"]
    png = result.workdir / "frames" / "thumb.png"
    with FrameRenderer(lcfg) as fr:
        fr.render("thumb", png, thumb={
            "title": f"سورة {p.surah_name_ar}",
            "subtitle": "كاملة · مع معاني الكلمات",
            "en": f"Surah {p.surah_name_en} · with word meanings",
            "reciter": reciter.get("label_ar") or reciter.get("label", "")})
    bg, _ = backgrounds.pick(lcfg, p, force=settings(lcfg).get("background"))
    dest = result.workdir / "thumbnail.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "8", "-i", str(bg), "-i", str(png),
                    "-filter_complex",
                    ("[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080[b];"
                     "[b][1:v]overlay=0:0,scale=1280:720"),
                    "-frames:v", "1", "-q:v", "3", str(dest)], check=True)
    return dest


# ---- texts ------------------------------------------------------------------------------------

def _clock(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def chapters(cfg: Config, manifest: dict) -> list[str]:
    """« 0:00 أصحاب الكهف · The People of the Cave (18:9-26) »: long.chapters of the surah, the
    first at 0:00 (YouTube's rule), each from the start of its first ayah."""
    surah = manifest["surah"]["number"]
    rows = (settings(cfg).get("chapters") or {}).get(surah) or []
    starts = {int(a["ref"].split(":")[1]): a["start"] for a in manifest["ayahs"]}
    last = max(starts)
    out = []
    for i, (ayah, ar, en) in enumerate(rows):
        end = rows[i + 1][0] - 1 if i + 1 < len(rows) else last
        ref = f"{surah}:{ayah}-{end}" if end > ayah else f"{surah}:{ayah}"
        name = " · ".join(x for x in (ar, en) if x)
        at = 0.0 if i == 0 else starts[ayah]
        out.append(f"{_clock(at)} {name} ({ref})" if name else f"{_clock(at)} {ref}")
    return out


def texts(cfg: Config, manifest: dict) -> dict[str, str]:
    """YouTube's title and description, the Arabic first (owner, 2026-11-21), numbers 123."""
    from quran_reels.render import _recitation

    sur = manifest["surah"]
    reciter = cfg.content["reciter"]
    name_ar, name_en = sur["name_ar"], sur["name_en"]
    reciter_ar, reciter_en = reciter.get("label_ar") or reciter["label"], reciter["label"]
    title = (f"سورة {name_ar} كاملة مع معاني الكلمات · {reciter_ar} · "
             f"Surah {name_en} in full with word meanings")
    if len(title) > 100:
        title = f"سورة {name_ar} كاملة مع معاني الكلمات · Surah {name_en} with word meanings"
    g = cfg.content["glosses"]
    count = sum(len(a["glosses"]) for a in manifest["ayahs"])
    lines = [
        (f"سورة {name_ar} كاملة بصوت {reciter_ar}، مع معاني {count} كلمة من {g['label']}، "
         f"وترجمة {cfg.content['translation']['label']}."),
        (f"Surah {name_en} in full, recited by {reciter_en}, with the meaning of {count} of its "
         f"words from {g.get('label_en') or g['label']} and the "
         f"{cfg.content['translation']['label']} translation."),
        "",
        *chapters(cfg, manifest),
    ]
    credits = [_recitation(cfg), f"Translation: {cfg.content['translation']['label']}",
               f"Word meanings: {g.get('label_en') or g['label']}"]
    tags = manifest.get("hashtags") or []
    tags = [t for t in tags if _ARABIC.search(t)] + [t for t in tags if not _ARABIC.search(t)]
    lines += ["", " · ".join(credits), "", cfg.video["handle"], "", " ".join(tags)]
    return {"title": title, "description": "\n".join(lines).strip() + "\n"}


# ---- Meta's check -----------------------------------------------------------------------------

def pieces(manifest: dict, most: float) -> list[tuple[float, float]]:
    """(start, end) of stretches of the video, each `most` seconds at most, cut at an ayah's
    start when one falls in the last third of the stretch."""
    total = float(manifest["seconds"])
    starts = sorted(a["start"] for a in manifest["ayahs"])
    out, at = [], 0.0
    while total - at > most:
        cut = max((s for s in starts if at + most * 2 / 3 <= s <= at + most), default=at + most)
        out.append((at, cut))
        at = cut
    out.append((at, total))
    return out


def piece_files(video: Path, manifest: dict, most: float) -> list[Path]:
    """Each stretch as an upright reel (720×1280, the video letterboxed in it, its sound), in a
    folder with the manifest and caption that publish.load_reel reads."""
    work = video.with_suffix("")
    out = []
    for i, (a, b) in enumerate(pieces(manifest, most), 1):
        dest = work / f"check-{i}.mp4"
        folder = dest.with_suffix("")
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(work / "manifest.json", folder / "manifest.json")
        shutil.copyfile(work / "caption.txt", folder / "caption.txt")
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(video),
             "-vf", "scale=720:-2,pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=0x0b1026,setsar=1",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p",
             "-r", "30", "-g", "60", "-bf", "0", "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
             "-ac", "2", "-movflags", "+faststart", "-use_editlist", "0", str(dest)], check=True)
        out.append(dest)
        print(f"long: piece {i}, {a:.0f}–{b:.0f} s → {dest.name}", file=sys.stderr)
    return out


def check(cfg: Config, video: Path, manifest: dict) -> tuple[bool, list[str]]:
    """Meta's check of every piece (publish.rights_only): clear only when all of them are."""
    from quran_reels import publish as pub

    checked = pub.meta_check(cfg, list(pub.META))
    clear, report = True, []
    for piece in piece_files(video, manifest, float(settings(cfg).get("check_seconds", 600))):
        ok, summary = pub.rights_only(cfg, piece, checked)
        report.append(f"{piece.stem} : {'✅' if ok else '❌'} {summary}")
        print(f"long: {piece.stem}: {'clear' if ok else 'NOT clear'}: {summary}", file=sys.stderr)
        clear = clear and ok
        if not ok:
            break                       # nothing goes up: no need to send the others
    return clear, report


# ---- publication ------------------------------------------------------------------------------

def state_key(manifest: dict) -> str:
    return f"{manifest['passage']}/{manifest['editions']['reciter']}"


def load_state(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def publish(cfg: Config, surah: int, state_path: Path, dry_run: bool = False,
            reciter: str | None = None, video: Path | None = None) -> int:
    """Render (or take `video`), check, upload once, record. 0 when it is on YouTube (or the dry
    run went through), 1 otherwise; a summary for the run's page."""
    from quran_reels.publishers.youtube import Uploader, Video

    lcfg = config_for(cfg, reciter)
    if video is None:
        video = render(cfg, surah, reciter).video
    work = video.with_suffix("")
    manifest = json.loads((work / "manifest.json").read_text(encoding="utf-8"))
    state = load_state(state_path)
    key = state_key(manifest)
    done = (state.get(key) or {}).get("youtube") or {}
    t = texts(lcfg, manifest)
    lines = [f"## {t['title']}", "", f"Durée : {_clock(manifest['seconds'])}", ""]
    if done.get("status") == "published":
        lines.append(f"Déjà sur YouTube : {done.get('url')} — rien de renvoyé.")
        _summary(lines)
        return 0
    clear, report = check(lcfg, video, manifest)
    lines += ["### Vérification des droits de Meta", "", *[f"- {r}" for r in report], ""]
    entry = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "video": video.name,
             "seconds": manifest["seconds"], "rights": report, "title": t["title"]}
    if not clear:
        lines.append("❌ Droits : rien n'est mis en ligne (règle 6).")
        _summary(lines)
        if not dry_run:
            state[key] = {**entry, "youtube": {"status": "blocked"}}
            _save(state_path, state)
        return 1
    if dry_run:
        lines += ["Essai à blanc : droits propres, rien mis en ligne.", "", "```",
                  t["description"], "```"]
        _summary(lines)
        return 0
    up = settings(cfg).get("upload") or {}
    uploader = Uploader.from_environ()
    if uploader is None:
        lines.append("❌ YOUTUBE_UPLOAD_REFRESH_TOKEN absent : rien mis en ligne.")
        _summary(lines)
        return 1
    result = uploader.upload(Video(
        path=video, title=t["title"], description=t["description"],
        privacy=up.get("privacy", "public"), made_for_kids=bool(up.get("made_for_kids", False)),
        synthetic_media=bool(up.get("synthetic_media", False)), long=True,
        language=up.get("language")), thumbnail=work / "thumbnail.jpg", dedupe=True)
    state[key] = {**entry, "youtube": {"status": result.status.value, "id": result.remote_id,
                                       "url": result.url, "error": result.error}}
    _save(state_path, state)
    ok = result.status.value == "published"
    lines.append(f"{'✅' if ok else '❌'} YouTube : {result.url or ''} {result.error or ''}".rstrip())
    _summary(lines)
    return 0 if ok else 1


def _save(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _summary(lines: list[str]) -> None:
    import os

    text = "\n".join(lines) + "\n"
    print(text, file=sys.stderr)
    if path := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)
