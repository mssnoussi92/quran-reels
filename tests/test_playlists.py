"""The channel's YouTube playlists kept by the run (playlists.py, config/playlists.yaml). No network."""

import json
from pathlib import Path

import pytest

from quran_reels import playlists as P
from quran_reels.insights import youtube as Y

CONF = {
    "enabled": True, "since": "2026-11-21",
    "playlists": {"juz-amma": {"id": "PLjuz", "title": "جزء عمّ · Juz' 'Amma"},
                  "al-kahf": {"id": "PLkahf", "title": "سورة الكهف · Surah Al-Kahf"},
                  "stories": {"id": "PLstories", "title": "حكايات من القرآن · Stories from the Quran"},
                  "dua": {"id": "PLdua", "title": "الدعاء · Du'a"}},
    "series": {"juz-amma": ["juz-amma"], "al-kahf": ["al-kahf"], "dua": ["dua"], "mushaf": []},
    "hand": {"93:1-11": ["juz-amma"]},
    "docs": {"dua": ["dua"], "quiz": [],
             "qarnayn": {"film": ["stories"], "short": ["al-kahf", "stories"]}},
}
PUBLISHED = {"slots": {
    "2026-11-20/morning": {"item": "al-kahf/18:17-18", "passage": "18:17-18"},
    "2026-11-21/morning": {"item": "juz-amma/102:1-8", "passage": "102:1-8"},
    "2026-11-22/evening": {"item": "dua/2:186-186", "passage": "2:186-186"},
    "2026-11-23/morning": {"item": "juz-amma/101:1-11", "passage": "101:1-11"},
    "2026-11-29/evening": {"item": "rizq/11:6-6", "passage": "11:6-6"},
    "2027-03-01/morning": {"item": "mushaf/1:1-7", "passage": "1:1-7"}}}


def post(key, day):
    return {"platform": "youtube", "key": key, "published": f"{day}T07:40:00+00:00"}


INSIGHTS = {"posts": {
    "youtube:old": post("slot:2026-11-20/morning", "2026-11-20"),        # before: his, untouched
    "youtube:v102": post("slot:2026-11-21/morning", "2026-11-21"),       # filed by him already
    "youtube:vdua": post("slot:2026-11-22/evening", "2026-11-22"),
    "youtube:vfilm": post("theme:qarnayn/film", "2026-11-23"),
    "youtube:v101": post("slot:2026-11-23/morning", "2026-11-23"),
    "youtube:vq1": post("theme:qarnayn/short-1", "2026-11-24"),
    "youtube:vsigns": post("theme:signs/short-1", "2026-11-25"),
    "youtube:vsigns2": post("theme:signs/short-2", "2026-11-28"),
    "youtube:vrizq": post("slot:2026-11-29/evening", "2026-11-29"),
    "youtube:vquiz": post("theme:quiz/short-1", "2026-11-30"),
    "youtube:vfatiha": post("slot:2027-03-01/morning", "2027-03-01"),
    "facebook:x": {"platform": "facebook", "key": "slot:2026-11-22/evening", "published": "2026-11-22"},
}}


class FakeChannel:
    def __init__(self):
        self.lists = {
            "PLjuz": {"title": "Juz' 'Amma · جزء عمّ", "description": "His words.", "defaultLanguage": "en"},
            "PLkahf": {"title": "Surah Al-Kahf · سورة الكهف", "description": "Friday."},
            "PLstories": {"title": "My own title", "description": "Stories."},     # changed by him
            "PLdua": {"title": "الدعاء · Du'a", "description": ""},                   # already right
        }
        self.content = {"PLjuz": ["v102"], "PLkahf": ["old"], "PLstories": [], "PLdua": []}
        self.calls = []

    def playlists(self):
        return dict(self.lists)

    def items(self, pid):
        return list(self.content[pid])

    def rename(self, pid, title, snippet):
        self.calls.append(("rename", pid, title, snippet.get("description")))

    def create(self, title):
        pid = f"PLnew{len(self.lists)}"
        self.lists[pid] = {"title": title}
        self.content[pid] = []
        self.calls.append(("create", pid, title))
        return pid

    def add(self, pid, vid):
        self.content[pid].append(vid)
        self.calls.append(("add", pid, vid))


def names():
    return P.Names(series={"rizq": ("Provision (rizq) in the Quran", "آيات الرزق"),
                           "dua": ("Supplications from the Quran", "آيات الدعاء")},
                   doc=lambda d: {"signs": ("We Will Show Them Our Signs", "سنريهم آياتنا")}.get(d))


def test_his_playlists_are_taken_over_and_the_new_videos_filed_at_the_end():
    ch, state = FakeChannel(), {}
    lines = P.sync(CONF, INSIGHTS, PUBLISHED, state, ch, names())
    renames = [c for c in ch.calls if c[0] == "rename"]
    # Arabic first, once, his description sent back; a title he wrote otherwise is left alone
    assert renames == [("rename", "PLjuz", "جزء عمّ · Juz' 'Amma", "His words."),
                       ("rename", "PLkahf", "سورة الكهف · Surah Al-Kahf", "Friday.")]
    assert ch.content["PLjuz"] == ["v102", "v101"]            # 102 was there: not twice
    assert ch.content["PLkahf"] == ["old", "vq1"]             # the film not in Al-Kahf (as he did)
    assert ch.content["PLstories"] == ["vfilm", "vq1"]
    assert ch.content["PLdua"] == ["vdua"]
    # a series and a document without a playlist get their own, with their first video
    created = [c for c in ch.calls if c[0] == "create"]
    assert [c[2] for c in created] == ["سنريهم آياتنا · We Will Show Them Our Signs",
                                       "آيات الرزق · Provision (rizq) in the Quran"]
    signs = state["playlists"]["signs"]
    assert ch.content[signs] == ["vsigns", "vsigns2"]
    assert ch.content[state["playlists"]["rizq"]] == ["vrizq"]
    # the quiz and the Quran in order: no playlist; the video before the handover: untouched
    assert not any("vquiz" in c or "vfatiha" in c or "old" in c for c in ch.calls if c[0] == "add")
    assert "add theme:qarnayn/film (vfilm) → stories" in lines
    # the next night: nothing more, and his playlists are never made again
    ch.calls.clear()
    assert P.sync(CONF, INSIGHTS, PUBLISHED, state, ch, names()) == [
        "rename « Juz' 'Amma · جزء عمّ » → « جزء عمّ · Juz' 'Amma »",
        "rename « Surah Al-Kahf · سورة الكهف » → « سورة الكهف · Surah Al-Kahf »"]  # the fake keeps old titles
    assert not [c for c in ch.calls if c[0] in ("create", "add")]


def test_a_dry_run_changes_nothing():
    ch, state = FakeChannel(), {}
    lines = P.sync(CONF, INSIGHTS, PUBLISHED, state, ch, names(), dry_run=True)
    assert ch.calls == [] and state == {}
    assert "create « سنريهم آياتنا · We Will Show Them Our Signs » (signs)" in lines
    assert "add theme:signs/short-2 (vsigns2) → signs" in lines


def test_nothing_is_done_without_its_token(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv(P.SECRET, raising=False)
    root = tmp_path / "repo"
    (root / "config").mkdir(parents=True)
    (root / "config" / "playlists.yaml").write_text("enabled: true\n", encoding="utf-8")
    assert P.run(root, tmp_path) == 0
    assert "no token" in capsys.readouterr().out
    assert not (tmp_path / P.STATE).exists()


def test_the_run_reads_and_keeps_its_state(tmp_path):
    root = tmp_path / "repo"
    (root / "config").mkdir(parents=True)
    import yaml
    (root / "config" / "playlists.yaml").write_text(yaml.safe_dump(CONF, allow_unicode=True),
                                                     encoding="utf-8")
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "insights.json").write_text(json.dumps(INSIGHTS), encoding="utf-8")
    (state_dir / "published.json").write_text(json.dumps(PUBLISHED), encoding="utf-8")
    ch = FakeChannel()
    assert P.run(root, state_dir, channel=ch, names=names()) == 0
    saved = json.loads((state_dir / P.STATE).read_text(encoding="utf-8"))
    assert set(saved["playlists"]) == {"signs", "rizq"}
    ch2 = FakeChannel()
    ch2.lists |= {pid: {"title": "x"} for pid in saved["playlists"].values()}
    ch2.content |= {pid: list(ch.content[pid]) for pid in saved["playlists"].values()}
    P.run(root, state_dir, channel=ch2, names=names())
    assert not [c for c in ch2.calls if c[0] == "create"]      # its own, found again by id


class Http:
    def __init__(self):
        self.sent = []

    def request(self, method, url, params=None, json=None, headers=None, timeout=None):
        self.sent.append((method, url.rsplit("/", 1)[-1], params, json))

        class R:
            status_code = 200

            def json(self):
                return {"id": "PLx"}
        return R()


def test_a_rename_sends_his_description_back_and_an_add_no_position():
    http = Http()
    ch = P.Channel(Y.YouTube("cid", "secret", http), "at")
    ch.rename("PLjuz", "جزء عمّ · Juz' 'Amma", {"title": "Juz' 'Amma · جزء عمّ",
                                                 "description": "His words.", "defaultLanguage": "en"})
    ch.add("PLjuz", "v1")
    assert ch.create("آيات الرزق · Provision (rizq) in the Quran") == "PLx"
    (m1, u1, p1, b1), (m2, u2, _, b2), (_, _, _, b3) = http.sent
    assert (m1, u1, p1) == ("PUT", "playlists", {"part": "snippet"})
    assert b1 == {"id": "PLjuz", "snippet": {"title": "جزء عمّ · Juz' 'Amma",
                                             "description": "His words.", "defaultLanguage": "en"}}
    assert (m2, u2) == ("POST", "playlistItems") and "position" not in b2["snippet"]
    assert b3["status"] == {"privacyStatus": "public"}


def test_the_playlists_sign_in_saves_its_own_secret(monkeypatch):
    url = Y.auth_url("cid", "https://x/cb", "s", playlists=True)
    assert "youtube.force-ssl" in url and "upload" not in url

    class Exchange:
        def post(self, url, data=None, timeout=None):
            class R:
                status_code = 200

                def json(self):
                    return {"access_token": "at", "refresh_token": "rt-lists",
                            "scope": " ".join(P.SCOPES)}
            return R()

        def get(self, url, params=None, headers=None, timeout=None):
            class R:
                status_code = 200

                def json(self):
                    return {"items": [{"id": "UC1", "snippet": {"title": "Quran Words Daily"},
                                       "statistics": {},
                                       "contentDetails": {"relatedPlaylists": {"uploads": "U"}}}]}
            return R()

    saved = {}
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "cid")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "secret")
    monkeypatch.setattr("quran_reels.gh_secrets.save_secret", lambda n, v: saved.update({n: v}))
    assert Y.auth("https://x/cb", "code", Y.YouTube("cid", "secret", Exchange())) == 0
    assert saved == {P.SECRET: "rt-lists"}


def test_the_configuration_names_his_six_playlists():
    conf = P.settings(Path(__file__).resolve().parents[1])
    assert len(conf["playlists"]) == 6 and conf["since"]
    for v in conf["playlists"].values():          # Arabic first: the first half has Arabic letters
        first = v["title"].split(" · ")[0]
        assert any("؀" <= ch <= "ۿ" for ch in first), v["title"]


@pytest.mark.parametrize(("title", "turned"), [("A · ب", "ب · A"), ("one", "one"),
                                               ("a · b · c", "a · b · c")])
def test_only_a_title_of_two_halves_is_turned(title, turned):
    assert P.swapped(title) == turned
