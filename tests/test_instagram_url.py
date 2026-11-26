"""2026-11-26: the reels go to Instagram by video_url (the release `reels`), a YouTube version is
cleared by Facebook's clean check when Instagram does not process it, and a Short held back that
way in the last two days goes up again (owner's choices)."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from quran_reels import daily, publish
from quran_reels.config import Config
from quran_reels.models import PublishResult, PublishStatus
from quran_reels.selector.calendar import State


def cfg(upload: str | None) -> Config:
    ig = {"upload": upload} if upload else {}
    return Config(root=Path("."), backgrounds=[], gloss_headwords={},
                  project={"platforms": {"instagram": ig}})


def test_instagram_fetches_the_reel_from_the_release(tmp_path, monkeypatch):
    video = tmp_path / "098_006-008.mp4"
    video.write_bytes(b"reel")
    sent = []
    monkeypatch.setattr(publish, "host_file",
                        lambda path, name: sent.append((path, name)) or f"https://x/{name}")
    url = publish.instagram_url(cfg("url"), video)
    assert len(sent) == 1 and sent[0][0] == video
    name = sent[0][1]
    assert name.startswith("instagram-098_006-008-") and name.endswith(".mp4") and url.endswith(name)
    video.write_bytes(b"reel made again")              # another file: another name
    publish.instagram_url(cfg("url"), video)
    assert sent[1][1] != name
    assert publish.instagram_url(cfg(None), video) == ""          # sent as before
    assert publish.instagram_url(cfg("file"), video) == ""


def test_the_reel_is_sent_when_the_release_cannot_take_it(tmp_path, monkeypatch, capsys):
    video = tmp_path / "r.mp4"
    video.write_bytes(b"reel")

    def broken(path, name):
        raise RuntimeError("gh: not logged in")

    monkeypatch.setattr(publish, "host_file", broken)
    assert publish.instagram_url(cfg("url"), video) == ""
    assert "sent to Instagram instead" in capsys.readouterr().err


def test_instagrams_container_takes_the_address():
    from quran_reels.publishers.instagram import InstagramPublisher

    reel = SimpleNamespace(video_url="https://x/instagram-r.mp4", cover_url=None, cover_ms=1000,
                           text_for=lambda name, n=None: "caption")
    params = InstagramPublisher(None, "1")._params(reel)
    assert params["video_url"] == "https://x/instagram-r.mp4" and "upload_type" not in params


def _dry(fb: dict | None, ig: dict | None, ig_status=PublishStatus.READY):
    out = [PublishResult("facebook", PublishStatus.DRAFT if fb else PublishStatus.FAILED,
                         remote_id="1" if fb else None, error=None if fb else "upload failed")]
    out[0].rights = fb
    out.append(PublishResult("instagram", ig_status, remote_id="2" if ig else None,
                             error=None if ig else "container still processing after 240 s"))
    out[1].rights = ig
    return out


CLEAN = {"platform": "x", "status": "complete", "matches_found": False, "matches": [],
         "detail": "", "seconds": 0.1}
MATCH = {**CLEAN, "matches_found": True, "matches": [{"owner": "UMG"}]}


def test_a_youtube_version_is_cleared_by_facebook_when_instagram_does_not_process_it(monkeypatch):
    def check(results):
        monkeypatch.setattr(publish, "publish_reel", lambda *a, **k: results)
        return publish.rights_only(None, Path("v.mp4"))[0]

    assert check(_dry(CLEAN, CLEAN))
    assert check(_dry(CLEAN, None, PublishStatus.FAILED))             # Instagram never processed it
    assert not check(_dry(CLEAN, MATCH))                               # a match still blocks
    assert not check(_dry(MATCH, None, PublishStatus.FAILED))
    assert not check(_dry(None, CLEAN))                                # Facebook's check is needed


HELD = {"status": "blocked", "error": "droits (Meta) : facebook : aucune correspondance ; "
        "instagram : instagram container 1, 2, 3: still processing after 240 s — pas mise sur YouTube"}
CLAIMED = {"status": "blocked", "error": "droits (Meta) : facebook : contenu protégé reconnu : UMG ; "
           "instagram : aucune correspondance — pas mise sur YouTube"}


def test_a_short_held_back_by_instagram_alone_goes_up_again(monkeypatch):
    assert daily.youtube_held_by_instagram(HELD)
    assert not daily.youtube_held_by_instagram(CLAIMED)
    assert not daily.youtube_held_by_instagram({"status": "published", "id": "x"})
    assert not daily.youtube_settled({"results": {"youtube": HELD}})

    def slot(youtube, **more):
        return {"queue": "reading", "item": "juz-amma/98:1-5", "passage": "98:1-5",
                "results": {"facebook": {"status": "published"}, "youtube": youtube}, **more}

    state = State({"slots": {"2026-11-25/morning": slot(HELD),
                             "2026-11-23/morning": slot(HELD),                   # too old
                             "2026-11-24/morning": slot(CLAIMED),
                             "2026-11-26/morning": slot(HELD, claimed=True)}})
    sched = SimpleNamespace(tz=ZoneInfo("Europe/Paris"), slots=[SimpleNamespace(name="morning")])
    monkeypatch.setattr(daily, "item_by_id", lambda sched, series, queue, item: item)
    now = datetime(2026, 11, 27, 7, 15, tzinfo=ZoneInfo("Europe/Paris"))
    got = daily.youtube_catch_up(sched, {}, state, now, set())
    assert [(p.day, p.platforms, p.retry) for p in got] == [(date(2026, 11, 25), ["youtube"], True)]
    assert daily.youtube_catch_up(sched, {}, state, now, {(date(2026, 11, 25), "morning")}) == []
