"""quran-reels publish / meta-check / tiktok-auth: send a rendered reel to the platforms.

Facebook and Instagram: every run checks the Page token first (validity, permissions, data
access expiry) and stops with a clear message if it cannot publish for at least
platforms.meta.min_days_left days. TikTok: draft mode, the reel goes to the TikTok inbox.
Results go to out/<passage>/publish.json and, on GitHub Actions, to the run summary.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from quran_reels.config import Config
from quran_reels.gh_secrets import save_secret
from quran_reels.models import Passage, PublishResult, PublishStatus, Reel, parse_passage
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
            token: TokenReport | None) -> str:
    title = f"## {'🧪 Dry run' if dry_run else '📣 Publication'} {reel.passage.key}"
    rows = ["| Plateforme | Résultat | Identifiant / lien |", "|---|---|---|"]
    for r in results:
        label = _TIKTOK_DRAFT if (r.platform, r.status) == ("tiktok", PublishStatus.DRAFT) \
            else _LABELS[r.status]
        label += f" : {r.error}" if r.error else ""
        where = r.url or (f"`{r.remote_id}`" if r.remote_id else "")
        rows.append(f"| {r.platform} | {label} | {where} |")
    return "\n".join([title, "", *rows, "", token.summary() if token else ""]).rstrip()


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

    results = []
    for name in platforms:
        if name == "facebook":
            publisher = FacebookPublisher(graph, env.page_id,
                                          max_hashtags=max_hashtags(cfg, name))
        elif name == "instagram":
            publisher = InstagramPublisher(graph, str(env.ig_user_id),
                                           max_hashtags=max_hashtags(cfg, name))
        else:
            publisher = tiktok
        print(f"{name}: uploading {reel.video.name}{' (dry run)' if dry_run else ''}",
              file=sys.stderr)
        result = publisher.publish(reel, dry_run=dry_run)
        print(f"{name}: {result.status.value} {result.remote_id or ''} {result.url or ''} "
              f"{result.error or ''}".rstrip(), file=sys.stderr)
        results.append(result)

    out = video.with_suffix("") / "publish.json"
    out.write_text(json.dumps({"passage": reel.passage.key, "dry_run": dry_run,
                               "results": [asdict(r) | {"status": r.status.value}
                                           for r in results]},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    _summary(_report(reel, results, dry_run, token))
    return results


def run(cfg: Config, video: Path, platforms: list[str], dry_run: bool,
        checked: tuple[Graph, MetaEnv, TokenReport] | None = None) -> int:
    results = publish_reel(cfg, video, platforms, dry_run, checked)
    return 1 if any(r.status is PublishStatus.FAILED for r in results) else 0


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
