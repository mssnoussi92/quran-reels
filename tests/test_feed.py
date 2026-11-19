"""The page publier.html (feed.py): what the owner publishes by hand, on one fixed link, rebuilt
from the reel.json of the branch `previews` in the same commit. No network."""

import json
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

from quran_reels import feed, notify
from quran_reels.ondemand.files import Hosting
from quran_reels.themepub import calendar as cal
from quran_reels.themepub import run as R

NOW = datetime(2026, 11, 24, 19, 5, tzinfo=UTC)


def write(root: Path, rel: str, data: dict) -> None:
    path = root / rel / "reel.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def previews(root: Path) -> None:
    # written before 2026-11-16: no slot, the TikTok text shared with Instagram
    write(root, "daily/2026-11-14-morning", {
        "id": "daily/2026-11-14-morning", "created": "2026-11-14T06:45:00+00:00",
        "title": "107:1-7 · Surah Al-Ma'un · سورة الماعون", "passage": "107:1-7",
        "captions": [{"label": "Facebook", "text": "FB"}, {"label": "Instagram, TikTok", "text": "IG"}],
        "youtube": {"title": "T", "description": "D", "hashtags": "#h", "file": "https://dl/y.mp4",
                    "command": "/youtube 2026-11-14/morning"},
        "results": [{"name": "Facebook", "url": "https://f", "label": "publié"}]})
    write(root, "daily/2026-11-24-morning", {
        "id": "daily/2026-11-24-morning", "created": "2026-11-24T06:40:00+00:00",
        "key": "2026-11-24/morning", "day": "2026-11-24", "time": "07:30", "tiktok": "TT",
        "title": "105:1-5", "passage": "105:1-5", "youtube": None,
        "notes": ["YouTube : rien pour ce créneau"], "match": ["slot:2026-11-24/morning"]})
    write(root, "theme/2026-11-24", {
        "kind": "theme", "id": "theme/2026-11-24", "created": "2026-11-24T18:50:00+00:00",
        "key": "theme:2026-11-24", "day": "2026-11-24", "time": "19:00", "tiktok": "Theme TT",
        "title": "Patient… and he asked", "youtube": {"title": "YT", "description": "", "hashtags": "",
                                                      "credits": "Quoted: …", "file": "https://dl/short.mp4",
                                                      "thumbnail": "https://dl/short-cover.jpg"},
        "match": ["theme:dua/short-1"]})
    write(root, "daily/2026-11-23-evening-essai", {"id": "daily/2026-11-23-evening-essai", "dry_run": True,
                                             "created": "2026-11-23T18:40:00+00:00"})
    write(root, "daily/2026-11-01-morning", {"id": "daily/2026-11-01-morning",
                                             "created": "2026-11-01T06:40:00+00:00"})
    write(root, "od/39/1", {"id": "od/39/1", "created": "2026-11-24T10:00:00+00:00"})


def test_the_page_lists_the_last_two_weeks_latest_first(tmp_path):
    previews(tmp_path)
    data = json.loads(feed.build(tmp_path, NOW))
    assert data["updated"] == "2026-11-24T19:05:00+00:00" and data["days"] == 14
    assert [e["id"] for e in data["entries"]] == [          # dry run, too old, on demand: out
        "theme/2026-11-24", "daily/2026-11-24-morning", "daily/2026-11-14-morning"]
    theme, morning, old = data["entries"]
    assert (theme["kind"], theme["tiktok"], theme["youtube"]["file"]) == (
        "theme", "Theme TT", "https://dl/short.mp4")
    # 2026-11-19: a theme video's thumbnail, and its credits apart from the description
    assert (theme["youtube"]["thumbnail"], theme["youtube"]["credits"]) == (
        "https://dl/short-cover.jpg", "Quoted: …")
    assert morning["youtube"] is None and morning["notes"] == ["YouTube : rien pour ce créneau"]
    # a reel.json from before: its slot from its folder, TikTok's text from the shared caption
    assert (old["key"], old["day"], old["time"], old["tiktok"], old["match"]) == (
        "2026-11-14/morning", "2026-11-14", "07:30", "IG", ["slot:2026-11-14/morning"])
    assert old["youtube"] == {"title": "T", "description": "D", "credits": "", "hashtags": "#h",
                              "file": "https://dl/y.mp4", "thumbnail": ""}


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_the_feed_is_rebuilt_in_the_same_commit_as_the_video(tmp_path):
    remote = tmp_path / "remote.git"
    git("init", "-q", "--bare", str(remote), cwd=tmp_path)
    repo = tmp_path / "repo"
    git("init", "-q", str(repo), cwd=tmp_path)
    git("remote", "add", "origin", str(remote), cwd=repo)
    h = Hosting(SimpleNamespace(repo="o/quran-reels"), repo, sleep=lambda s: None)
    meta = {"id": "daily/2026-11-24-morning", "created": datetime.now(UTC).isoformat(),
            "key": "2026-11-24/morning", "day": datetime.now(UTC).date().isoformat(),
            "time": "07:30", "tiktok": "TT"}
    h.publish({"daily/2026-11-24-morning/reel.json": json.dumps(meta)}, "reel", derived=feed.files)
    shown = subprocess.run(["git", "show", "previews:feed.json"], cwd=remote, capture_output=True,
                           text=True, check=True).stdout
    assert [e["tiktok"] for e in json.loads(shown)["entries"]] == ["TT"]
    log = subprocess.run(["git", "log", "--oneline", "previews"], cwd=remote, capture_output=True,
                         text=True, check=True).stdout.splitlines()
    assert len(log) == 1


def test_a_film_is_seen_on_youtube_in_16_9_or_beside_its_vertical_twin():
    row = cal.Row(day=date(2026, 11, 23), label="Du'a : le film", where="YouTube ; Facebook",
                  docs=["dua", "dua-9x16"], part="film", platforms=["facebook", "youtube"])
    assert R.match_keys(row) == ["theme:dua/film", "theme:dua-9x16/film"]


def test_the_issue_and_the_page_point_to_each_other():
    body = notify.merge_captions("", {"items": []})
    assert feed.PAGE in body.splitlines()[0]
    page = (Path(__file__).parents[1] / "docs" / "publier.html").read_text(encoding="utf-8")
    assert feed.PAGE.endswith("/" + "publier.html")
    for path in ("previews/feed.json", "state/insights.json", "state/published.json"):
        assert f'fresh("{path}")' in page
