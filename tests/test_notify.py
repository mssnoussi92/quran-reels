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
