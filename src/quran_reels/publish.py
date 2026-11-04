"""quran-reels publish / meta-check: send a rendered reel to Facebook and Instagram.

Every run checks the Page token first (validity, permissions, data access expiry) and stops
with a clear message if it cannot publish for at least platforms.meta.min_days_left days.
Results go to out/<passage>/publish.json and, on GitHub Actions, to the run summary.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from quran_reels.config import Config
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

PLATFORMS = ("facebook", "instagram")

_LABELS = {
    PublishStatus.PUBLISHED: "publié",
    PublishStatus.DRAFT: "brouillon, non publié (Meta Business Suite → Contenu → Brouillons)",
    PublishStatus.READY: "conteneur prêt, non publié (Instagram le supprime après 24 h)",
    PublishStatus.FAILED: "échec",
}


def platforms_for(cfg: Config, requested: list[str] | None) -> list[str]:
    if requested:
        return list(dict.fromkeys(requested))
    conf = cfg.project.get("platforms") or {}
    return [p for p in PLATFORMS
            if (conf.get(p) or {}).get("enabled") and (conf.get(p) or {}).get("mode") == "auto"]


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
    return Reel(passage=passage, video=video,
                caption=(work / "caption.txt").read_text(encoding="utf-8"),
                cover=work / "preview" / f"{surah:03d}{int(cover['ref'].split(':')[1]):03d}.png",
                cover_ms=int((cover["start"] + cover["seconds"] / 2) * 1000))


def _report(reel: Reel, results: list[PublishResult], dry_run: bool, token: TokenReport) -> str:
    title = f"## {'🧪 Dry run' if dry_run else '📣 Publication'} {reel.passage.key}"
    rows = ["| Plateforme | Résultat | Identifiant / lien |", "|---|---|---|"]
    for r in results:
        label = _LABELS[r.status] + (f" : {r.error}" if r.error else "")
        where = r.url or (f"`{r.remote_id}`" if r.remote_id else "")
        rows.append(f"| {r.platform} | {label} | {where} |")
    return "\n".join([title, "", *rows, "", token.summary()])


def run(cfg: Config, video: Path, platforms: list[str], dry_run: bool,
        checked: tuple[Graph, MetaEnv, TokenReport] | None = None) -> int:
    graph, env, token = checked or meta_check(cfg, platforms)
    print(token.summary(), file=sys.stderr)
    reel = load_reel(video)

    results = []
    for name in platforms:
        if name == "facebook":
            publisher = FacebookPublisher(graph, env.page_id)
        else:
            publisher = InstagramPublisher(graph, str(env.ig_user_id))
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
    return 1 if any(r.status is PublishStatus.FAILED for r in results) else 0
