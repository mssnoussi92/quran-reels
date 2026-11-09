"""quran-reels notify against a fake gh: failure issue, recovery, captions to copy."""

import json

from quran_reels import notify


class FakeGh:
    """Just enough of `gh issue` to keep a list of issues in memory."""

    def __init__(self):
        self.issues: list[dict] = []
        self.calls: list[tuple] = []

    def __call__(self, *args, stdin=None):
        self.calls.append((args[1], stdin))
        cmd = args[1]
        if cmd == "list":
            return json.dumps([i for i in self.issues if i["state"] == "open"])
        if cmd == "create":
            title = args[args.index("--title") + 1]
            assignee = args[args.index("--assignee") + 1] if "--assignee" in args else None
            n = len(self.issues) + 1
            self.issues.append({"number": n, "title": title, "body": stdin, "state": "open",
                                "assignee": assignee, "comments": [], "pinned": False})
            return f"https://github.com/o/r/issues/{n}\n"
        issue = self.issues[int(args[2]) - 1]
        if cmd == "comment":
            issue["comments"].append(stdin)
        elif cmd == "edit":
            issue["body"] = stdin
        elif cmd == "close":
            issue["state"] = "closed"
        elif cmd == "pin":
            issue["pinned"] = True
        return ""


def item(slot="morning", passage="114:1-6", status=None, caption="Surah An-Nas\n\n#Quran\n"):
    results = status or {"facebook": {"status": "published", "url": "https://fb/1", "error": None},
                         "instagram": {"status": "published", "url": "https://ig/1",
                                       "error": None},
                         "tiktok": {"status": "draft", "url": None, "error": None}}
    return {"key": f"2026-11-05/{slot}", "day": "2026-11-05",
            "time": "07:30" if slot == "morning" else "19:30", "passage": passage, "label": "",
            "retry": False, "caption": caption, "results": results}


def write(tmp_path, items, errors=(), dry_run=False):
    path = tmp_path / "daily-report.json"
    path.write_text(json.dumps({"dry_run": dry_run, "items": items, "errors": list(errors)}),
                    encoding="utf-8")
    return path


def test_a_failure_opens_one_issue_assigned_to_the_owner_then_comments(tmp_path):
    gh = FakeGh()
    failed = item(status={"facebook": {"status": "published", "url": "https://fb/1",
                                       "error": None},
                          "instagram": {"status": "failed", "url": None,
                                        "error": "instagram container 1: still processing"}})
    report = write(tmp_path, [failed])
    issues = notify.Issues("o/r", runner=gh)
    notify.run(report, "failure", "https://run/1", "owner", issues)
    notify.run(report, "failure", "https://run/2", "owner", issues)
    [alert] = [i for i in gh.issues if i["title"] == notify.FAILURE_TITLE]
    assert alert["assignee"] == "owner" and alert["body"].startswith("@owner")
    assert "jeu. 5 nov. · 07:30 · 114:1-6" in alert["body"]
    assert "still processing" in alert["body"] and "https://run/1" in alert["body"]
    assert len(alert["comments"]) == 1 and "https://run/2" in alert["comments"][0]


def test_the_next_successful_publication_closes_the_issue(tmp_path):
    gh = FakeGh()
    issues = notify.Issues("o/r", runner=gh)
    notify.run(tmp_path / "missing.json", "failure", "https://run/1", "owner", issues)
    assert "avant de publier" in gh.issues[0]["body"]          # no report: crashed early
    notify.run(write(tmp_path, [item()]), "success", "https://run/2", "owner", issues)
    alert = gh.issues[0]
    assert alert["state"] == "closed" and "Réglé par https://run/2" in alert["comments"][0]


def test_token_check_failure_is_quoted(tmp_path):
    gh = FakeGh()
    report = write(tmp_path, [], errors=["Meta token check failed:\nrenew it: Graph Explorer"])
    notify.run(report, "failure", "https://run/1", None, notify.Issues("o/r", runner=gh))
    assert "Graph Explorer" in gh.issues[0]["body"] and gh.issues[0]["assignee"] is None


def test_captions_issue_keeps_the_latest_four_newest_first(tmp_path):
    gh = FakeGh()
    issues = notify.Issues("o/r", runner=gh)
    for n, (slot, passage) in enumerate([("morning", "114:1-6"), ("evening", "2:255-255")] * 3):
        it = item(slot, passage, caption=f"caption {n}\n")
        it["key"] = f"2026-11-0{5 + n // 2}/{slot}"
        it["day"] = f"2026-11-0{5 + n // 2}"
        notify.run(write(tmp_path, [it]), "success", f"https://run/{n}", "owner", issues)
    [captions] = gh.issues
    assert captions["title"] == notify.CAPTIONS_TITLE and captions["pinned"]
    body = captions["body"]
    assert [f"caption {n}" in body for n in range(6)] == [False, False, True, True, True, True]
    assert body.index("caption 5") < body.index("caption 2")
    assert "brouillon dans ta boîte TikTok" in body and "[publié](https://ig/1)" in body


def test_a_retry_replaces_its_slot_entry(tmp_path):
    body = notify.merge_captions("", {"items": [item(caption="first\n")]})
    body = notify.merge_captions(body, {"items": [item(caption="second\n")]})
    assert "second" in body and "first" not in body and body.count("<!-- entry") == 1


def test_a_dry_run_updates_captions_but_never_the_failure_issue(tmp_path):
    gh = FakeGh()
    report = write(tmp_path, [item()], dry_run=True)
    notify.run(report, "failure", "https://run/1", "owner", notify.Issues("o/r", runner=gh))
    assert [i["title"] for i in gh.issues] == [notify.CAPTIONS_TITLE]
    assert "(dry run)" in gh.issues[0]["body"]


def test_a_rights_block_says_what_to_change(tmp_path):
    gh = FakeGh()
    blocked = item(status={"facebook": {"status": "blocked", "url": None,
                                        "error": "droits : instagram : contenu protégé reconnu"},
                           "instagram": {"status": "blocked", "url": None, "error": "droits"}})
    notify.run(write(tmp_path, [blocked]), "failure", "https://run/1", "owner",
               notify.Issues("o/r", runner=gh))
    [alert] = [i for i in gh.issues if i["title"] == notify.FAILURE_TITLE]
    assert "bloqué par la vérification des droits" in alert["body"]
    assert "content.reciter" in alert["body"]
    assert not [i for i in gh.issues if i["title"] == notify.CAPTIONS_TITLE]   # nothing to copy


def test_a_reel_taken_down_after_publication_warns_about_the_tiktok_draft(tmp_path):
    gh = FakeGh()
    reason = "facebook : contenu protégé reconnu : Recitations Ltd — MUTE dans 24 territoires"
    removed = item(status={
        "facebook": {"status": "removed", "url": None, "error": f"retiré après publication : {reason}"},
        "instagram": {"status": "removed", "url": None, "error": "retiré"},
        "tiktok": {"status": "draft", "url": None, "error": f"ne publie pas ce brouillon : {reason}"}})
    notify.run(write(tmp_path, [removed]), "failure", "https://run/1", "owner",
               notify.Issues("o/r", runner=gh))
    [alert] = [i for i in gh.issues if i["title"] == notify.FAILURE_TITLE]
    assert "retiré après publication" in alert["body"] and "MUTE dans 24 territoires" in alert["body"]
    assert "ne publie pas le brouillon TikTok" in alert["body"]
    assert not [i for i in gh.issues if i["title"] == notify.CAPTIONS_TITLE]   # nothing to copy


def test_the_captions_issue_says_which_video_goes_to_youtube():
    from quran_reels.notify import merge_captions
    item = {"key": "2026-11-06/morning", "day": "2026-11-06", "time": "07:30",
            "passage": "18:1-10", "label": "", "reciter": "budair", "retry": False,
            "caption": "Al-Kahf by Salah Budair\n",
            "results": {"facebook": {"status": "published", "url": "https://f", "error": None}},
            "youtube": {"reciter": "sayegh", "video": "youtube/018_001-010.mp4",
                        "caption": "Al-Kahf by Tawfiq As-Sayegh\n", "label": "Tawfiq As-Sayegh",
                        "instead_of": "Salah Budair"}}
    body = merge_captions("", {"items": [item]})
    assert "**YouTube : pas cette vidéo** (Salah Budair y est revendiqué" in body
    assert "`youtube/018_001-010.mp4`, récitée par Tawfiq As-Sayegh" in body
    assert "Al-Kahf by Tawfiq As-Sayegh" in body
    item["youtube"] = {"reciter": None, "error": "aucun autre récitateur prêt pour ce passage"}
    assert "**YouTube : ne pas mettre cette vidéo**" in merge_captions("", {"items": [item]})


def test_a_slot_nobody_tried_opens_the_alert_even_when_this_run_published(tmp_path):
    """The alert is written by a run: for a slot no run took, a later run has to say it, and
    its own success must not close what it has just opened."""
    gh = FakeGh()
    issues = notify.Issues("o/r", runner=gh)
    notify.run(write(tmp_path, [item("evening")]), "success", "https://run/9", "owner", issues,
               missed=["2026-11-05/morning"])
    [alert] = [i for i in gh.issues if i["title"] == notify.FAILURE_TITLE]
    assert alert["state"] == "open" and alert["assignee"] == "owner"
    assert "Créneau jamais tenté : jeu. 5 nov. · morning" in alert["body"]
    assert "https://run/9" in alert["body"]
    notify.run(write(tmp_path, [item("evening")]), "success", "https://run/10", "owner", issues)
    assert alert["state"] == "closed"                    # the next publication closes it


def test_a_missed_slot_with_nothing_due_and_with_a_failure(tmp_path):
    gh = FakeGh()
    issues = notify.Issues("o/r", runner=gh)
    # GitHub's late cron: nothing due, no report at all
    notify.run(tmp_path / "missing.json", "success", "https://run/1", "owner", issues,
               missed=["2026-11-05/evening", "2026-11-06/morning"])
    [alert] = [i for i in gh.issues if i["title"] == notify.FAILURE_TITLE]
    assert "ces créneaux" in alert["body"] and "ven. 6 nov. · morning" in alert["body"]
    notify.run(tmp_path / "missing.json", "failure", "https://run/2", "owner", issues,
               missed=["2026-11-06/evening"])
    assert "ven. 6 nov. · evening" in alert["comments"][0]
    assert "Le run a échoué avant de publier" in alert["comments"][0]


def test_a_note_of_the_run_reaches_the_owner_without_closing_anything(tmp_path):
    gh = FakeGh()
    issues = notify.Issues("o/r", runner=gh)
    path = tmp_path / "daily-report.json"
    path.write_text(json.dumps({"dry_run": False, "items": [item()], "errors": [],
                                "notes": ["🔑 **Le jeton GitHub `GH_SECRETS_TOKEN` expire"]}),
                    encoding="utf-8")
    notify.run(path, "success", "https://run/1", "owner", issues)
    [alert] = [i for i in gh.issues if i["title"] == notify.FAILURE_TITLE]
    assert alert["state"] == "open" and "GH_SECRETS_TOKEN" in alert["body"]
