"""quran-reels images run: post the image formats due now (config/images.yaml), record them.

The images workflow runs every hour; a format is due from its time_utc for window_hours. A
day's post is chosen once (state), so a retry after a failed platform posts the same images.
Results go to out/images/<day>-<kind>/ (images, caption, manifest, publish.json) and to the
state (images.json on the `state` branch).
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from quran_reels.config import Config
from quran_reels.images import candidates as cand_mod
from quran_reels.images import caption as caption_mod
from quran_reels.images.cards import WORD_CARDS, CardRenderer, content_for
from quran_reels.images.select import ImageState, load_exclusions, next_candidate
from quran_reels.models import AyahRef, PublishResult, PublishStatus

OK = ("published", "draft", "ready")


@dataclass
class Rendered:
    kind: str
    day: date
    candidate: cand_mod.Candidate
    files: list[Path]
    body: str                     # caption without hashtags
    hashtags: list[str]
    folder: Path


def settings(cfg: Config) -> dict[str, Any]:
    return cand_mod.images_settings(cfg)


def due_formats(cfg: Config, state: ImageState, now: datetime) -> list[tuple[str, date, list[str]]]:
    """(kind, day, platforms still to do) for each enabled format due now."""
    s = settings(cfg)
    window = timedelta(hours=float(s.get("window_hours", 6)))
    platforms = list(s.get("platforms") or ["facebook", "instagram"])
    out = []
    for kind, conf in (s.get("formats") or {}).items():
        if not conf.get("enabled"):
            continue
        hh, mm = (int(x) for x in str(conf["time_utc"]).split(":"))
        now_utc = now.astimezone(UTC)
        for day in (now_utc.date(), now_utc.date() - timedelta(days=1)):
            slot = datetime.combine(day, time(hh, mm), UTC)
            if slot <= now_utc < slot + window:
                record = state.post(kind, day)
                done = {p for p, r in (record or {}).get("results", {}).items()
                        if r.get("status") in OK}
                todo = [p for p in platforms if p not in done]
                if todo:
                    out.append((kind, day, todo))
    return out


def render(cfg: Config, src: Any, kind: str, day: date, c: cand_mod.Candidate,
           out_dir: Path, renderer: CardRenderer | None = None) -> Rendered:
    """The images and caption of a post (sources: text, translation, the ayah's gloss)."""
    s = settings(cfg)
    max_chars = int(cfg.content["glosses"].get("max_chars", 170))
    if kind == "word":
        from quran_reels.sources.tafsir_app import parse_entries

        ref = AyahRef(c.surah, c.ayah)
        raw = src.glosses.raw([ref], src.quran.global_index).get(ref, "")
        entries = parse_entries(raw, ref, cfg.content["glosses"]["edition"])
        if c.entry >= len(entries):
            raise SystemExit(f"{c.id}: the source has no entry {c.entry} any more: "
                             "run `quran-reels images build`")
        content = cand_mod.word_content(src, c, entries[c.entry].text, max_chars)
        cards = WORD_CARDS
    else:
        content = content_for(src, c.surah, c.context)
        cards = ("ayah",)
    folder = out_dir / f"{day.isoformat()}-{kind}"
    files = []
    own = renderer is None
    renderer = renderer or CardRenderer(cfg).__enter__()
    try:
        min_scale = float(s.get("min_scale", 0.7))
        for n, card in enumerate(cards, 1):
            dest = folder / f"{n}-{card}.jpg"
            fit = renderer.render(card, content, dest)
            if fit < min_scale:
                print(f"warning: {c.id} {card}: text scaled to {fit:.0%}", file=sys.stderr)
            files.append(dest)
    finally:
        if own:
            renderer.__exit__(None, None, None)
    body = caption_mod.caption(cfg, kind, content)
    tags = caption_mod.hashtags(s, content)
    (folder / "caption.txt").write_text(caption_mod.text(body, tags, None), encoding="utf-8")
    (folder / "manifest.json").write_text(json.dumps({
        "kind": kind, "day": day.isoformat(), "candidate": c.id, "ayah": c.key,
        "context": content.context_ref, "word": content.word, "gloss": content.gloss,
        "editions": {"text": cfg.content["quran_text"]["edition"],
                     "translation": cfg.content["translation"]["edition"],
                     "glosses": cfg.content["glosses"]["edition"]},
        "hashtags": tags}, ensure_ascii=False, indent=2), encoding="utf-8")
    return Rendered(kind, day, c, files, body, tags, folder)


def run(cfg: Config, state_path: Path, now: datetime | None = None, dry_run: bool = False,
        check: bool = False, report: Path | None = None) -> int:
    from quran_reels import publish as publish_mod
    from quran_reels.daily import _output
    from quran_reels.images.publish import ImagePublisher
    from quran_reels.sources import Sources

    now = now or datetime.now(UTC)
    state = ImageState.load(state_path)
    todo = due_formats(cfg, state, now)
    for kind, day, platforms in todo:
        print(f"{day} {kind}: {'+'.join(platforms)}")
    if not todo:
        print(f"{now.astimezone(UTC):%Y-%m-%d %H:%M} UTC: no image post due")
    _output("due", "true" if todo else "false")
    if check or not todo:
        return 0

    s = settings(cfg)
    exclusions = load_exclusions(cfg)
    src = Sources.from_config(cfg)
    src.quran.ensure(src.translation_slug)
    graph, env, _token = publish_mod.meta_check(cfg, ["facebook", "instagram"])
    publisher = ImagePublisher(graph, env.page_id, env.ig_user_id)
    log: dict = {"dry_run": dry_run, "items": [], "errors": []}
    failed = False
    try:
        for kind, day, platforms in todo:
            candidates = cand_mod.load(cfg, kind)
            record = state.post(kind, day)
            if record:                                  # retry: the same post
                c = next(x for x in candidates if x.id == record["id"])
            else:
                c = next_candidate(candidates, state, kind, s["formats"][kind]["seed"],
                                   exclusions, day)
                if c is None:
                    print(f"warning: {kind}: no candidate left", file=sys.stderr)
                    continue
            post = render(cfg, src, kind, day, c, cfg.out / "images")
            captions = {p: caption_mod.text(post.body, post.hashtags,
                                            publish_mod.max_hashtags(cfg, p)) for p in platforms}
            results = publisher.publish(post.files, captions, platforms, dry_run)
            failed |= any(r.status is PublishStatus.FAILED for r in results)
            _record(post, results, log)
            log["items"][-1]["time"] = f"{s['formats'][kind]['time_utc']} UTC"
            if dry_run:
                continue
            record = record or {"id": c.id, "surah": c.surah, "ayah": c.key,
                                "word": json.loads((post.folder / "manifest.json").read_text(
                                    encoding="utf-8"))["word"], "results": {}}
            for r in results:
                record["results"][r.platform] = {"status": r.status.value, "id": r.remote_id,
                                                 "url": r.url, "error": r.error}
            state.set_post(kind, day, record)
            if any(r["status"] in OK for r in record["results"].values()):
                state.mark_done(kind, c)
            state.save(state_path)
    except BaseException as e:
        log["errors"].append(str(e) if isinstance(e, SystemExit) else f"{type(e).__name__}: {e}")
        raise
    finally:
        if report:
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if failed else 0


def _record(post: Rendered, results: list[PublishResult], log: dict) -> None:
    from quran_reels.publish import _summary

    (post.folder / "publish.json").write_text(json.dumps(
        {"candidate": post.candidate.id, "results": [asdict(r) | {"status": r.status.value}
                                                     for r in results]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    rows = [f"| {r.platform} | {r.status.value}{' : ' + r.error if r.error else ''} | "
            f"{r.url or r.remote_id or ''} |" for r in results]
    _summary("\n".join([f"## 🖼️ {post.kind} {post.day} · {post.candidate.key}", "",
                        "| Plateforme | Résultat | Lien |", "|---|---|---|", *rows]))
    log["items"].append({"key": f"{post.day.isoformat()}/{post.kind}",
                         "day": post.day.isoformat(), "passage": post.candidate.key,
                         "results": {r.platform: {"status": r.status.value, "url": r.url,
                                                  "error": r.error} for r in results}})
