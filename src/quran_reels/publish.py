"""quran-reels publish / meta-check / tiktok-auth: send a rendered reel to the platforms.

Facebook and Instagram: every run checks the Page token first (validity, permissions, data
access expiry) and stops with a clear message if it cannot publish for at least
platforms.meta.min_days_left days. TikTok: draft mode, the reel goes to the TikTok inbox.
Results go to out/<passage>/publish.json and, on GitHub Actions, to the run summary.

Rights (publishers/rights.py): the reel is first uploaded unpublished to every Meta platform
(Facebook draft, Instagram container) and Meta's copyright check is read on each. Nothing is
published, TikTok included, unless every check is complete without a match: a recitation
that Rights Manager recognises gets the reel cut or muted after publication.

That check missed Alafasy and Nabil Ar-Rifai, claimed once published. So the check is read
again on the published reels (platforms.meta.rights_after_timeout, 300 s): a claim that mutes
or blocks one takes it down from Facebook and Instagram (status `removed`), and the TikTok
draft must not be posted (owner's choice, 2026-11-05). daily.py reads it again at later runs.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

from quran_reels.config import Config
from quran_reels.gh_secrets import save_secret
from quran_reels.models import Passage, PublishResult, PublishStatus, Reel, parse_passage
from quran_reels.publishers.base import PublisherError
from quran_reels.publishers.facebook import FacebookPublisher
from quran_reels.publishers.instagram import InstagramPublisher
from quran_reels.publishers.meta import (
    Graph,
    GraphError,
    MetaEnv,
    TokenProblem,
    TokenReport,
    check_token,
)
from quran_reels.publishers.tiktok import (
    REFRESH_SECRET,
    TikTok,
    TikTokEnv,
    TikTokError,
    TikTokPublisher,
)

PLATFORMS = ("facebook", "instagram", "tiktok")
META = ("facebook", "instagram")

_LABELS = {
    PublishStatus.PUBLISHED: "publié",
    PublishStatus.DRAFT: "brouillon, non publié (Meta Business Suite → Contenu → Brouillons)",
    PublishStatus.READY: "conteneur prêt, non publié (Instagram le supprime après 24 h)",
    PublishStatus.BLOCKED: "non publié : vérification des droits",
    PublishStatus.REMOVED: "retiré après publication : Meta l'a rendu muet ou bloqué",
    PublishStatus.FAILED: "échec",
}
_TIKTOK_DRAFT = "dans la boîte TikTok : notification dans l'app, à publier à la main"


def platforms_for(cfg: Config, requested: list[str] | None) -> list[str]:
    if requested:
        return list(dict.fromkeys(requested))
    conf = cfg.project.get("platforms") or {}
    return [p for p in PLATFORMS if (conf.get(p) or {}).get("enabled")
            and (conf.get(p) or {}).get("mode") in ("auto", "draft")]


def max_hashtags(cfg: Config, platform: str) -> int | None:
    value = ((cfg.project.get("platforms") or {}).get(platform) or {}).get("max_hashtags")
    return None if value is None else int(value)


def _meta(cfg: Config) -> dict:
    return (cfg.project.get("platforms") or {}).get("meta") or {}


def _summary(markdown: str) -> None:
    """Append to the GitHub Actions run summary, when there is one."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(markdown + "\n")


def meta_check(cfg: Config, platforms: list[str]) -> tuple[Graph, MetaEnv, TokenReport]:
    env = MetaEnv.from_environ(platforms)
    graph = Graph(env.token, _meta(cfg).get("graph_version", "v24.0"))
    try:
        report = check_token(graph, env.page_id, env.ig_user_id, platforms,
                             float(_meta(cfg).get("min_days_left", 14)))
    except (TokenProblem, GraphError) as e:
        _summary("## ❌ Jeton Meta\n\n" + "\n\n".join(str(e).splitlines()))
        raise SystemExit(f"Meta token check failed:\n{e}") from None
    for w in report.warnings:
        print(f"warning: {w}", file=sys.stderr)
    return graph, env, report


def load_reel(video: Path) -> Reel:
    """A reel rendered by `quran-reels render`: the MP4 and its out/<passage>/ folder."""
    work = video.with_suffix("")
    manifest = json.loads((work / "manifest.json").read_text(encoding="utf-8"))
    surah, start, end = parse_passage(manifest["passage"])
    passage = Passage(surah, start, end, manifest["surah"]["name_ar"],
                      manifest["surah"]["name_en"])
    ayahs = manifest["ayahs"]
    cover = next((a for a in ayahs if a["glosses"]), ayahs[0])   # a frame with a word meaning
    text = (work / "caption.txt").read_text(encoding="utf-8")
    tags = manifest.get("hashtags") or []
    tag_line = " ".join(tags)
    if tags and text.rstrip().endswith(tag_line):         # written by render: body + tags
        text = text.rstrip()[: -len(tag_line)].rstrip() + "\n"
    return Reel(passage=passage, video=video, caption=text, hashtags=list(tags),
                cover=work / "preview" / f"{surah:03d}{int(cover['ref'].split(':')[1]):03d}.png",
                cover_ms=int((cover["start"] + cover["seconds"] / 2) * 1000))


def _report(reel: Reel, results: list[PublishResult], dry_run: bool,
            token: TokenReport | None, reciter: str = "") -> str:
    title = f"## {'🧪 Dry run' if dry_run else '📣 Publication'} {reel.passage.key}" + (
        f" · {reciter}" if reciter else "")
    rows = ["| Plateforme | Résultat | Droits (Meta) | Identifiant / lien |", "|---|---|---|---|"]
    for r in results:
        label = _TIKTOK_DRAFT if (r.platform, r.status) == ("tiktok", PublishStatus.DRAFT) \
            else _LABELS[r.status]
        label += f" : {r.error}" if r.error else ""
        rights = (("✅ " if r.rights["clear"] else "⛔ ") + r.rights["summary"]) if r.rights else ""
        if r.rights_after:
            ok = not (r.rights_after.get("matches_found") and r.status == PublishStatus.REMOVED)
            rights += f" · après publication : {'✅' if ok else '⛔'} {r.rights_after['summary']}"
        where = r.url or (f"`{r.remote_id}`" if r.remote_id else "")
        rows.append(f"| {r.platform} | {label} | {rights} | {where} |")
    return "\n".join([title, "", *rows, "", token.summary() if token else ""]).rstrip()


def after_timeout(cfg: Config | None) -> float:
    """platforms.meta.rights_after_timeout: how long Meta's check is read on the published
    reels (publish.after_check, daily.recheck); 0: off, the owner checks by hand."""
    if getattr(cfg, "project", None) is None:
        return 0.0
    return float(_meta(cfg).get("rights_after_timeout", 0))


def meta_publishers(cfg: Config, graph: Graph, env: MetaEnv, platforms: list[str]) -> dict:
    rights_timeout = float(_meta(cfg).get("rights_timeout", 600))
    out: dict = {}
    if "facebook" in platforms:
        out["facebook"] = FacebookPublisher(graph, env.page_id,
                                            max_hashtags=max_hashtags(cfg, "facebook"),
                                            rights_timeout=rights_timeout)
    if "instagram" in platforms:
        out["instagram"] = InstagramPublisher(graph, str(env.ig_user_id),
                                              max_hashtags=max_hashtags(cfg, "instagram"),
                                              rights_timeout=rights_timeout)
    return out


def take_down(publishers: dict, results: dict[str, dict], reason: str) -> None:
    """Remove every published Meta reel of a claimed passage. results: platform → {status,
    id, error} (a slot record's, or PublishResult fields); changed in place."""
    for name, r in results.items():
        if name in publishers and r.get("status") == PublishStatus.PUBLISHED.value and r.get("id"):
            try:
                publishers[name].remove(r["id"])
                r["status"] = PublishStatus.REMOVED.value
                r["error"] = f"retiré après publication : {reason}"
            except GraphError as e:
                r["error"] = f"À RETIRER À LA MAIN ({e}) : {reason}"
        elif name == "tiktok" and r.get("status") == PublishStatus.DRAFT.value:
            r["error"] = f"ne publie pas ce brouillon TikTok : {reason}"


def after_check(publishers: dict, results: dict[str, PublishResult], timeout: float,
                interval: float = 30, clock=time.monotonic, sleep=time.sleep) -> str | None:
    """Meta's check read on the published reels, again and again for `timeout` seconds: the
    claims on Ar-Rifai and Al-Ghamdi came minutes after publication, while the field may say
    complete without a match at once. A claim that mutes or blocks one reel takes the passage
    down everywhere. The reason, or None when nothing was claimed."""
    live = {n: r for n, r in results.items()
            if n in publishers and r.status == PublishStatus.PUBLISHED and r.remote_id}
    checks: dict = {}
    start = clock()
    while live:
        for name, r in live.items():
            checks[name] = publishers[name].rights_after(r.remote_id)
            r.rights_after = checks[name].as_dict()
            print(f"{name}: rights after publication (+{clock() - start:.0f} s) "
                  f"{checks[name].status}: {checks[name].describe()}", file=sys.stderr)
        if any(c.restricted for c in checks.values()) or clock() - start + interval > timeout:
            break
        sleep(interval)
    claimed = {n: c for n, c in checks.items() if c.restricted}
    if not claimed:
        return None
    reason = "; ".join(f"{n} : {c.describe()}" for n, c in claimed.items())
    plain = {n: {"status": r.status.value, "id": r.remote_id, "error": r.error}
             for n, r in results.items()}
    take_down(publishers, plain, reason)
    for name, r in results.items():
        r.status, r.error = PublishStatus(plain[name]["status"]), plain[name]["error"]
    return reason


def tiktok_publisher() -> TikTokPublisher:
    env = TikTokEnv.from_environ()
    return TikTokPublisher(TikTok(env.client_key, env.client_secret), str(env.refresh_token),
                           save_refresh=lambda value: save_secret(REFRESH_SECRET, value))


def publish_reel(cfg: Config, video: Path, platforms: list[str], dry_run: bool,
                 checked: tuple[Graph, MetaEnv, TokenReport] | None = None
                 ) -> list[PublishResult]:
    """Send a rendered reel to each platform; results also in publish.json and the summary."""
    token = None
    if any(p in META for p in platforms):
        graph, env, token = checked or meta_check(cfg, [p for p in platforms if p in META])
        print(token.summary(), file=sys.stderr)
    tiktok = tiktok_publisher() if "tiktok" in platforms else None
    reel = load_reel(video)

    publishers = meta_publishers(cfg, graph, env, platforms) if token else {}
    if tiktok:
        publishers["tiktok"] = tiktok

    # 1. Meta: upload unpublished everywhere, then read every copyright check.
    results: dict[str, PublishResult] = {}
    prepared: dict[str, str] = {}
    for name in (p for p in platforms if p in META):
        print(f"{name}: uploading {reel.video.name} unpublished", file=sys.stderr)
        try:
            prepared[name] = publishers[name].prepare(reel)
        except (PublisherError, KeyError) as e:
            results[name] = PublishResult(name, PublishStatus.FAILED, error=str(e))
    checks = {}
    for name, object_id in prepared.items():
        checks[name] = publishers[name].rights(object_id)
        print(f"{name}: rights check {checks[name].status} after {checks[name].seconds:.0f} s: "
              f"{checks[name].describe()}", file=sys.stderr)
    blocked = {n: c for n, c in checks.items() if not c.clear}
    reason = "; ".join(f"{n} : {c.describe()}" for n, c in blocked.items())

    # 2. Publish only if no platform found a problem.
    for name in platforms:
        if name in results:
            continue
        check = checks.get(name)
        if name in prepared:
            if dry_run:
                status = PublishStatus.DRAFT if name == "facebook" else PublishStatus.READY
                results[name] = PublishResult(name, status, remote_id=prepared[name])
            elif blocked:
                results[name] = PublishResult(
                    name, PublishStatus.BLOCKED, remote_id=prepared[name],
                    error=f"droits : {reason} — {reel.passage.key} non publié")
            else:
                results[name] = publishers[name].commit(prepared[name], reel)
            results[name].rights = check.as_dict()
        elif blocked:
            results[name] = PublishResult(name, PublishStatus.BLOCKED,
                                          error=f"non envoyé, droits : {reason}")
        else:
            print(f"{name}: uploading {reel.video.name}{' (dry run)' if dry_run else ''}",
                  file=sys.stderr)
            results[name] = publishers[name].publish(reel, dry_run=dry_run)
        r = results[name]
        print(f"{name}: {r.status.value} {r.remote_id or ''} {r.url or ''} {r.error or ''}"
              .rstrip(), file=sys.stderr)
    # 3. Meta's check read again on what went live (it missed Alafasy and Ar-Rifai). Never
    #    lets a publication fail: what went out must still be recorded.
    seconds = after_timeout(cfg)                # 0: off
    if not dry_run and seconds > 0:
        try:
            after_check({n: p for n, p in publishers.items() if n in META}, results,
                        seconds)
        except Exception as e:      # noqa: BLE001
            print(f"warning: rights check after publication failed: {type(e).__name__}: {e}",
                  file=sys.stderr)
    results_list = [results[n] for n in platforms]

    out = video.with_suffix("") / "publish.json"
    out.write_text(json.dumps({"passage": reel.passage.key, "dry_run": dry_run,
                               "reciter": (cfg.project.get("content") or {}).get("reciter"),
                               "results": [asdict(r) | {"status": r.status.value}
                                           for r in results_list]},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    reciter = ((getattr(cfg, "project", None) or {}).get("content") or {}).get("reciter") or {}
    _summary(_report(reel, results_list, dry_run, token,
                     reciter.get("label", "") if isinstance(reciter, dict) else ""))
    return results_list


def run(cfg: Config, video: Path, platforms: list[str], dry_run: bool,
        checked: tuple[Graph, MetaEnv, TokenReport] | None = None) -> int:
    results = publish_reel(cfg, video, platforms, dry_run, checked)
    return 1 if any(r.status in (PublishStatus.FAILED, PublishStatus.BLOCKED,
                                 PublishStatus.REMOVED) for r in results) else 0


def _event_input(name: str) -> str | None:
    """A workflow_dispatch input read from the event file: never printed in the step's log."""
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path or not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return ((json.load(f).get("inputs") or {}).get(name) or "").strip() or None


def tiktok_auth(cfg: Config, code: str | None) -> int:
    """Exchange the one-time code from tiktok-callback.html; save the refresh token."""
    from datetime import UTC, datetime, timedelta

    from quran_reels.gh_secrets import SecretSaveError, mask

    code = code or os.environ.get("TIKTOK_AUTH_CODE") or _event_input("code")
    if not code:
        raise SystemExit("no authorization code: pass --code or run the tiktok-auth workflow")
    mask(code)
    conf = (cfg.project.get("platforms") or {}).get("tiktok") or {}
    env = TikTokEnv.from_environ(need_refresh=False)
    client = TikTok(env.client_key, env.client_secret)
    try:
        t = client.exchange(code, conf["redirect_uri"])
        user = client.user(t["access_token"])
    except TikTokError as e:
        _summary(f"## ❌ Connexion TikTok\n\n{e}\n\nLe code ne sert qu'une fois et expire en "
                 "quelques minutes : recommencer depuis tiktok-login.html.")
        raise SystemExit(f"TikTok sign-in failed: {e}") from None
    scopes = sorted(s for s in (t.get("scope") or "").split(",") if s)
    if "video.upload" not in scopes:
        raise SystemExit(f"TikTok granted {scopes}, video.upload is missing: authorize it again")
    try:
        save_secret(REFRESH_SECRET, t["refresh_token"])
    except SecretSaveError as e:
        _summary(f"## ❌ Connexion TikTok\n\nJeton obtenu mais non enregistré : {e}")
        raise SystemExit(str(e)) from None
    until = datetime.now(UTC) + timedelta(seconds=int(t.get("refresh_expires_in", 0)))
    lines = [f"Compte : {user.get('display_name', '?')}", f"Autorisations : {', '.join(scopes)}",
             (f"{REFRESH_SECRET} enregistré, valable jusqu'au {until:%Y-%m-%d} environ "
              "(renouvelé à chaque publication).")]
    _summary("## ✅ TikTok connecté\n\n" + "\n\n".join(lines))
    print("\n".join(lines), file=sys.stderr)
    return 0
