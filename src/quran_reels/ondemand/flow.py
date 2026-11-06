"""The steps of the `on-demand` workflow (`quran-reels on-demand …`) and the direct downloads of
the daily reels. Each step reads the issue from GitHub, never from the shell's arguments."""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from quran_reels import publish as publish_mod
from quran_reels import reciters as rec
from quran_reels.config import Config
from quran_reels.models import PublishResult, PublishStatus, parse_passage
from quran_reels.ondemand import comments, media, page
from quran_reels.ondemand import state as od_state
from quran_reels.ondemand.check import Checked, check, label
from quran_reels.ondemand.commands import Refused, approval, authorized, command
from quran_reels.ondemand.files import Hosting
from quran_reels.ondemand.gh import GitHub
from quran_reels.ondemand.request import (
    RequestError,
    is_request,
    parse,
    parse_words,
    with_words,
    words_text,
)
from quran_reels.selector.calendar import State

WORKFLOW = ".github/workflows/on-demand.yml"
LABEL = "on-demand"
CAPTIONS_TITLE = "📋 Légendes à copier (TikTok, YouTube)"     # notify.CAPTIONS_TITLE
_RESULT_LABELS = {"published": "publié", "draft": "brouillon, non publié", "ready":
                  "conteneur prêt, non publié", "blocked": "non publié (droits)",
                  "removed": "retiré après publication", "failed": "échec",
                  "manual": "à mettre en ligne à la main",
                  "cancelled": "annulé, pas mis en ligne"}


def output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")
    print(f"{name}={value}")


def slug(key: str) -> str:
    s, a, b = parse_passage(key)
    return f"{s:03d}_{a:03d}-{b:03d}"


# ---- routing ----------------------------------------------------------------------------

def route(event: str, payload: dict, owner: str) -> dict:
    """What this run does: {command, issue, kind}; command "" when nothing is to be done."""
    why = authorized(event, payload, owner)
    issue = payload.get("issue") or {}
    out = {"command": "", "issue": issue.get("number") or "", "kind": "", "args": ""}
    if why:
        out["why"] = why
        return out
    if event == "workflow_dispatch":
        inputs = payload.get("inputs") or {}
        out.update(command=(inputs.get("command") or "").strip(),
                   issue=int(inputs.get("issue") or 0), kind="request",
                   args=(inputs.get("args") or "").strip())
        return out
    title, body = issue.get("title") or "", issue.get("body") or ""
    if title == CAPTIONS_TITLE:
        out["kind"] = "captions"
    elif is_request(title, body):
        out["kind"] = "request"
    else:
        out["why"] = "ni une demande « À la demande », ni le ticket des légendes"
        return out
    if event == "issues":
        if out["kind"] == "request" and issue.get("state") == "open":
            out["command"] = "preview"
        return out
    cmd, args = command((payload.get("comment") or {}).get("body"))
    if out["kind"] == "captions" and cmd != "youtube":
        cmd = ""
    if issue.get("state") != "open" and cmd != "youtube":
        cmd = ""
    out.update(command=cmd, args=args)
    return out


# ---- check ------------------------------------------------------------------------------

def _request_issue(gh: GitHub, number: int) -> dict:
    issue = gh.issue(number)
    login = (issue.get("user") or {}).get("login")
    if login != gh.owner or issue.get("author_association") != "OWNER":
        raise SystemExit(f"#{number}: not opened by {gh.owner}, ignored")
    return issue


def run_check(cfg: Config, gh: GitHub, number: int, state: dict,
              split_seconds: float | None = None, comment: bool = True
              ) -> tuple[str, Checked | None, dict]:
    """(ok | refused | split, verdict, issue); refused and split are explained in a
    comment."""
    issue = _request_issue(gh, number)
    try:
        req = parse(issue.get("body") or "")
    except RequestError as e:
        if comment:
            gh.comment(number, comments.refused(None, e.problems))
        return "refused", None, issue
    checked = check(cfg, req, state)
    if checked.problems:
        if comment:
            gh.comment(number, comments.refused(checked, checked.problems, req.passage))
        return "refused", checked, issue
    if checked.split:
        if split_seconds is not None:      # split already tried in this run
            msg = (f"la récitation de {label(cfg, checked.split)} a été découpée en "
                   f"{_minutes(split_seconds)}, mais {checked.key} n'est pas entièrement "
                   f"vérifié ({checked.not_ready}) : une coupe entre deux ayahs n'est pas "
                   "nette (un mot d'une ayah entendu dans la voisine), elle ne sera pas "
                   "publiée ainsi. Choisis un autre récitateur ou `auto`")
            if comment:
                gh.comment(number, comments.refused(checked, [msg], req.passage))
            return "refused", checked, issue
        if comment:
            gh.comment(number, comments.splitting(label(cfg, checked.split), checked.key))
        return "split", checked, issue
    return "ok", checked, issue


def _minutes(seconds: float) -> str:
    m, s = divmod(round(seconds), 60)
    return f"{m} min {s:02d} s" if m else f"{s} s"


# ---- preview ----------------------------------------------------------------------------

def run_preview(cfg: Config, gh: GitHub, hosting: Hosting, number: int, state: dict,
                run_id: str, split_seconds: float | None = None) -> int:
    from quran_reels.render import render_passage

    status, checked, issue_data = run_check(cfg, gh, number, state, split_seconds)
    if status != "ok":
        return 0
    gh.react(number, "eyes")
    pcfg = rec.with_reciter(cfg, checked.reciter)
    result = render_passage(pcfg, checked.key, background=checked.background,
                            glosses=checked.glosses)
    video = result.video
    reel = publish_mod.load_reel(video)
    manifest = json.loads((video.with_suffix("") / "manifest.json").read_text(encoding="utf-8"))
    work = cfg.out / "on-demand"
    small = media.light(video, work / "apercu.mp4")
    shots = media.frames(video, work / "frames")
    digest = media.sha256(video)
    rid = f"od/{number}/{run_id}"
    created = od_state.now()
    preview_url = hosting.upload(small, f"od{number}-{result.passage.slug}-{run_id}-apercu.mp4")
    files: dict[str, Path | str] = {f"{rid}/{p.name}": p for p in shots}
    issue = {"number": number, "url": f"https://github.com/{gh.repo}/issues/{number}"}
    notes = list(checked.notes)
    if split_seconds is not None:
        notes.insert(0, f"récitation de {label(cfg, checked.reciter)} découpée et vérifiée "
                        f"pour ce passage en {_minutes(split_seconds)}")
    shown_bg = manifest.get("background") or {}
    if checked.background and shown_bg.get("id") != checked.background:
        notes.append(f"le fond {checked.background} n'a pas pu être chargé : "
                     f"{shown_bg.get('id')} à la place")
    d = page.data(pcfg, reel, kind="on-demand", rid=rid, stage="preview", created=created,
                  reciter=label(cfg, checked.reciter), seconds=round(result.seconds, 1),
                  platforms=list(checked.platforms), background=shown_bg, issue=issue,
                  video={"preview": preview_url},
                  frames=[hosting.raw_url(f"{rid}/{p.name}") for p in shots], notes=notes)
    d["words"] = word_list(pcfg, checked.key, manifest)
    d["words_mode"] = words_text(checked.request.words)
    files[f"{rid}/reel.json"] = json.dumps(d, ensure_ascii=False, indent=1)
    hosting.publish(files, f"Aperçu #{number} {checked.key}")
    meta = {"run": int(run_id) if str(run_id).isdigit() else run_id,
            "artifact": artifact_name(number, run_id), "sha256": digest,
            "body": comments.body_hash(issue_data.get("body")), "rid": rid,
            "key": checked.key, "slug": result.passage.slug, "reciter": checked.reciter,
            "background": checked.background, "platforms": list(checked.platforms),
            "seconds": round(result.seconds, 1), "words": words_text(checked.request.words)}
    (work / "checked.json").write_text(json.dumps(checked.as_dict() | {"meta": meta},
                                                  ensure_ascii=False, indent=1), "utf-8")
    gh.comment(number, comments.preview(d, meta, hosting.page_url(rid, "1"), notes))
    gh.label(number, LABEL, description="Publication à la demande (docs/on-demand.md)")
    output("rid", rid)
    return 0


def word_list(cfg: Config, key: str, manifest: dict) -> list[dict]:
    """The source's word meanings for the passage, numbered, those the reel shows marked."""
    from quran_reels.ondemand import words as words_mod
    from quran_reels.sources import Sources

    try:
        found = words_mod.meanings(cfg, Sources.from_config(cfg), key)
    except Exception as e:      # noqa: BLE001  (the list is a help, the reel is rendered)
        print(f"warning: word meanings of {key}: {type(e).__name__}: {e}", file=sys.stderr)
        return []
    shown = words_mod.shown_numbers(found, manifest)
    return [m.as_dict(m.n in shown) for m in found]


def run_words(gh: GitHub, number: int, args: str) -> bool:
    """`/mots …`: the choice is written in the request's «Mots» section (the preview that
    follows checks it). False, with a comment, when it cannot be read."""
    issue = _request_issue(gh, number)
    try:
        chosen = parse_words(args)
    except ValueError as e:
        gh.comment(number, f"⛔ `/mots` : {e}" + comments.FOOTER)
        return False
    gh.edit_issue(number, body=with_words(issue.get("body") or "", chosen))
    gh.react(number, "eyes")
    return True


def artifact_name(number: int, run_id: str) -> str:
    return f"on-demand-{number}-{run_id}"


# ---- publish ----------------------------------------------------------------------------

def _rows(results: list[PublishResult]) -> list[dict]:
    rows = []
    for r in results:
        lab = _RESULT_LABELS.get(r.status.value, r.status.value)
        if (r.platform, r.status) == ("tiktok", PublishStatus.DRAFT):
            lab = "brouillon dans ta boîte TikTok"
        rows.append({"platform": r.platform, "name": page.PLATFORM_LABELS[r.platform],
                     "label": lab, "url": r.url, "error": r.error, "rights": r.rights})
    return rows


def _clean(results: list[PublishResult], earlier: bool = False) -> bool:
    """Meta's check is clean: nothing blocked, and at least one check complete without a
    match (in this run, or earlier for this request)."""
    if any(r.status in (PublishStatus.BLOCKED, PublishStatus.REMOVED) for r in results):
        return False
    checks = [r.rights for r in results if r.rights]
    return (bool(checks) or earlier) and all(c.get("clear") for c in checks)


def _stage(results: list[PublishResult], dry_run: bool) -> str:
    if any(r.status == PublishStatus.BLOCKED for r in results):
        return "blocked"
    if dry_run:
        return "dry-run"
    ok = [r.status in (PublishStatus.PUBLISHED, PublishStatus.DRAFT) for r in results]
    return "published" if ok and all(ok) else "partial" if any(ok) else "failed"


def run_publish(cfg: Config, gh: GitHub, hosting: Hosting, number: int, mode: str,
                state_path: Path, comment_id: int | None = None) -> int:
    """mode: publish (/publier) or dry-run (/essai). Publishes the previewed file only."""
    dry_run = mode == "dry-run"
    issue = _request_issue(gh, number)
    try:
        ok = approval(gh.comments(number), gh.owner, mode, comment_id)
        meta = ok.meta
        if comments.body_hash(issue.get("body")) != meta.get("body"):
            raise Refused("le ticket a changé depuis l'aperçu : attends le nouvel aperçu")
        run = gh.run_info(int(meta["run"]))
        if run.get("path") != WORKFLOW or (run.get("repository") or {}).get(
                "full_name") != gh.repo:
            raise Refused("l'aperçu ne vient pas du workflow on-demand de ce dépôt")
        state = State.load(state_path)
        done = od_state.done_platforms(state.data, number)
        todo = [p for p in meta["platforms"] if p != "youtube" and p not in done]
        if not dry_run and not todo and "youtube" not in meta["platforms"]:
            raise Refused("déjà publié partout pour cette demande ; pour republier, ouvre une "
                          "nouvelle demande")
    except Refused as e:
        gh.comment(number, f"⛔ {e}" + comments.FOOTER)
        return 0
    gh.react(number, "rocket", comment_id=ok.comment.get("id"))

    gh.download_artifact(int(meta["run"]), meta["artifact"], cfg.out)
    video = cfg.out / f"{meta['slug']}.mp4"
    if not video.is_file() or media.sha256(video) != meta["sha256"]:
        gh.comment(number, "⛔ le fichier de l'aperçu ne correspond pas (empreinte) : rien "
                           "n'est publié ; `/apercu` pour le refaire." + comments.FOOTER)
        return 1
    pcfg = rec.with_reciter(cfg, meta["reciter"])
    reel = publish_mod.load_reel(video)
    meta_todo = [p for p in todo if p in publish_mod.META]
    if dry_run:
        meta_todo = [p for p in meta["platforms"] if p in publish_mod.META]
        todo = meta_todo
    checked = publish_mod.meta_check(pcfg, list(publish_mod.META))

    results: list[PublishResult] = []
    rights_only = None
    earlier = bool(done & set(publish_mod.META))
    if not meta_todo and not earlier:
        # No Meta platform asked (TikTok or YouTube only): Meta's check all the same (rule 6),
        # on an unpublished draft and container, deleted or left to expire.
        dry = publish_mod.publish_reel(pcfg, video, list(publish_mod.META), True, checked)
        blocked = [r for r in dry if not (r.rights and r.rights.get("clear"))]
        rights_only = {"clear": not blocked, "summary": " ; ".join(
            f"{r.platform} : {(r.rights or {}).get('summary') or r.error or r.status.value}"
            for r in dry)}
        if blocked:
            results = [PublishResult(p, PublishStatus.BLOCKED,
                                     error=f"droits : {rights_only['summary']}")
                       for p in todo or ["youtube"]]
        earlier = not blocked
    if todo and not results:
        platforms = [p for p in todo if p != "tiktok" or not dry_run]
        if platforms:
            results = publish_mod.publish_reel(pcfg, video, platforms, dry_run, checked)

    clean = _clean(results, earlier)
    stage = _stage(results, dry_run) if results else ("dry-run" if dry_run else "checked")
    approved = {"by": gh.owner, "at": od_state.now(), "comment": ok.comment.get("id"),
                "mode": mode}
    youtube_file = None
    if clean:
        name = f"od{number}-{meta['slug']}-{meta['run']}.mp4"
        youtube_file = hosting.upload(video, name)
    if not dry_run:
        rec_entry = od_state.record(state.data, number, meta, meta,
                                    [r for r in results if r.platform != "youtube"], approved)
        if rights_only:
            rec_entry["rights"] = rights_only
        if clean and "youtube" in meta["platforms"]:
            od_state.offer_youtube(state.data, number, youtube_file)
        state.save(state_path)

    rows = _rows(results)
    rid = meta["rid"]
    d = page.data(pcfg, reel, kind="on-demand", rid=rid, stage=stage, created=od_state.now(),
                  reciter=label(cfg, meta["reciter"]), seconds=meta.get("seconds"),
                  platforms=meta["platforms"], issue={"number": number, "url": issue["html_url"]},
                  video={"preview": None, "full": youtube_file}, youtube_file=youtube_file,
                  results=rows, command="/youtube")
    try:                        # what the preview showed: frames, light MP4, background
        old = json.loads(hosting.read(f"{rid}/reel.json") or "{}")
        d["frames"], d["video"]["preview"] = old.get("frames", []), (old.get("video") or {}
                                                                    ).get("preview")
        d["background"] = old.get("background", "")
        d["created"] = old.get("created") or d["created"]
    except Exception as e:     # noqa: BLE001  (the page is a convenience)
        print(f"warning: preview page of {rid}: {type(e).__name__}: {e}", file=sys.stderr)
    hosting.publish({f"{rid}/reel.json": json.dumps(d, ensure_ascii=False, indent=1)},
                    f"{'Essai' if dry_run else 'Publication'} #{number} {meta['key']}")
    tiktok = next((r for r in results if r.platform == "tiktok"
                   and r.status == PublishStatus.DRAFT), None)
    caption = reel.text(publish_mod.max_hashtags(cfg, "tiktok")) if tiktok else ""
    gh.comment(number, comments.result(d, rows, hosting.page_url(rid, "2"), rights_only,
                                       caption))
    if not dry_run and stage == "published" and "youtube" not in meta["platforms"]:
        gh.edit_issue(number, state="closed", state_reason="completed")
    return 1 if stage in ("blocked", "failed") or any(
        r.status == PublishStatus.FAILED for r in results) else 0


# ---- youtube ----------------------------------------------------------------------------

def _url(args: str) -> str | None:
    for word in args.split():
        if word.startswith(("https://", "http://")):
            return word
    return None


def run_youtube(cfg: Config, gh: GitHub, number: int, args: str, state_path: Path,
                comment_id: int | None = None, kind: str = "request") -> int:
    """`/youtube [link]` on a request, `/youtube <day>/<slot> [link]` on the captions issue."""
    state = State.load(state_path)
    url = _url(args)
    try:
        if kind == "captions":
            key = next((w for w in args.split() if "/" in w and not w.startswith("http")), "")
            slots = state.data.get("slots") or {}
            if not key:             # the latest reel that went out and is not marked yet
                key = next((k for k, r in sorted(slots.items(), reverse=True)
                            if any(x.get("status") in od_state.OK for p, x in
                                   r.get("results", {}).items() if p != "youtube")
                            and (r.get("results", {}).get("youtube") or {}).get("status")
                            != "published"), "")
            if key not in slots:
                raise Refused(f"créneau « {key or '?'} » introuvable : écris "
                              "`/youtube <jour>/<créneau> <lien>`, ex. "
                              "`/youtube 2026-11-06/morning https://youtube.com/shorts/…`")
            od_state.mark_youtube(slots[key], url)
            what = f"le créneau {key} ({slots[key].get('passage', '')})"
        else:
            entry = od_state.entry(state.data, number)
            offered = entry and ((entry.get("results") or {}).get("youtube") or {}).get("status")
            if not offered:
                raise Refused("YouTube n'est pas encore proposé pour cette demande : il l'est "
                              "après une publication dont la vérification des droits est "
                              "propre (`/publier`)")
            od_state.mark_youtube(entry, url)
            what = f"la demande #{number} ({entry.get('passage', '')})"
    except Refused as e:
        gh.comment(number, f"⛔ {e}")
        return 0
    state.save(state_path)
    if kind == "captions":
        gh.react(number, "+1", comment_id=comment_id)
        _mark_caption_entry(gh, number, key, url)
    else:
        gh.comment(number, comments.youtube_done(url, what))
        gh.edit_issue(number, state="closed", state_reason="completed")
    return 0


def _mark_caption_entry(gh: GitHub, number: int, key: str, url: str | None) -> None:
    issue = gh.issue(number)
    body = issue.get("body") or ""
    hint = f"`/youtube {key}"
    lines = body.split("\n")
    done = f"✅ YouTube : {'[mis en ligne](' + url + ')' if url else 'mis en ligne'} (à la main)"
    changed = [done if hint in line else line for line in lines]
    if changed != lines:
        gh.edit_issue(number, body="\n".join(changed))


# ---- daily reels: direct downloads -------------------------------------------------------

def daily_files(cfg: Config, hosting: Hosting, report_path: Path) -> int:
    """After `quran-reels daily`: each reel that went out goes to the release (and its YouTube
    version, when it has one), with a page for YouTube; the report gets the links, for the
    captions issue (notify.py). Never fails the daily run."""
    from quran_reels.notify import _has_caption

    if not report_path.is_file():
        return 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    files: dict[str, Path | str] = {}
    tag = "-essai" if report.get("dry_run") else ""
    try:                        # where /youtube <day>/<slot> is answered
        captions = next((i for i in hosting.gh.api_list("issues?state=open&per_page=100")
                         if i.get("title") == CAPTIONS_TITLE), None)
    except Exception:           # noqa: BLE001
        captions = None
    for item in report.get("items") or []:
        if not _has_caption(item):
            continue
        try:
            s = slug(item["passage"])
            video = cfg.out / f"{s}.mp4"
            if not video.is_file():
                continue
            day, slot = item["key"].split("/")
            name = f"{day}-{slot}-{s}{tag}"
            main = hosting.upload(video, f"{name}.mp4")
            yt_video = cfg.out / item["youtube"]["video"] if (item.get("youtube") or {}).get(
                "video") else None
            yt = hosting.upload(yt_video, f"{name}-youtube.mp4") if yt_video and \
                yt_video.is_file() else main
            reel = publish_mod.load_reel(yt_video if yt != main else video)
            rid = f"daily/{day}-{slot}"
            reciter = (item.get("youtube") or {}).get("label") if yt != main else None
            names = cfg.content.get("reciters") or {}
            reciter = reciter or (names.get(item.get("reciter") or "") or {}).get(
                "label", item.get("reciter") or "")
            d = page.data(cfg, reel, kind="daily", rid=rid, stage="daily",
                          created=od_state.now(), reciter=reciter, seconds=None,
                          platforms=["facebook", "instagram", "tiktok", "youtube"],
                          video={"full": main, "youtube": yt}, youtube_file=yt,
                          results=[{"name": page.PLATFORM_LABELS.get(p, p), "url": r.get("url"),
                                    "label": _RESULT_LABELS.get(r.get("status"),
                                                                r.get("status"))}
                                   for p, r in item["results"].items()],
                          command=f"/youtube {item['key']}")
            d["issue"] = {"title": CAPTIONS_TITLE, "url": (captions or {}).get("html_url")}
            files[f"{rid}/reel.json"] = json.dumps(d, ensure_ascii=False, indent=1)
            item["files"] = {"mp4": main, "youtube_mp4": yt,
                             "page": hosting.page_url(rid, datetime.now(UTC).strftime("%H%M")),
                             "command": f"/youtube {item['key']}"}
        except Exception as e:      # noqa: BLE001  (a link less, never a failed run)
            print(f"warning: direct download of {item.get('key')}: {type(e).__name__}: {e}",
                  file=sys.stderr)
    try:
        if files:
            hosting.publish(files, f"Reels du calendrier {datetime.now(UTC):%Y-%m-%d %H:%M}")
        hosting.prune_assets()
    except Exception as e:          # noqa: BLE001
        print(f"warning: previews branch: {type(e).__name__}: {e}", file=sys.stderr)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0

