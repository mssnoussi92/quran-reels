"""On-demand reels (docs/on-demand.md): request, rules, approval, publication, YouTube by hand,
direct downloads. No network: GitHub, Meta and the renderer are faked."""

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from quran_reels import publish as publish_mod
from quran_reels.config import load
from quran_reels.models import Passage, PublishResult, PublishStatus, Reel
from quran_reels.ondemand import comments, flow, media
from quran_reels.ondemand import state as od_state
from quran_reels.ondemand.check import check
from quran_reels.ondemand.commands import Refused, approval, authorized, command
from quran_reels.ondemand.files import Hosting, prune_folders
from quran_reels.ondemand.gh import BOT
from quran_reels.ondemand.request import Request, RequestError, body, is_request, parse
from quran_reels.reciters import Option

OWNER = "mssnoussi92"


@pytest.fixture
def cfg():
    return load()


# ---- the request ------------------------------------------------------------------------

CATALOGUE_BODY = """### Récitateur

minshawi

### Passage

93:1-5

### Fond

auto

### Plateformes

facebook, instagram, tiktok, youtube

---
Ouvert depuis le catalogue (https://mssnoussi92.github.io/quran-reels/catalog/#on-demand).
"""


def test_the_catalogue_body_is_read():
    req = parse(CATALOGUE_BODY)
    assert req == Request("minshawi", 93, 1, 5, "auto",
                          ("facebook", "instagram", "tiktok", "youtube"))
    assert parse(body(req)) == req                      # what body() writes is read back


@pytest.mark.parametrize("passage, expected", [
    ("93", (93, None, None)), ("Sourate 93 entière", (93, None, None)),
    ("2:255", (2, 255, 255)), ("18 : 1 – 10", (18, 1, 10)), ("`112`", (112, None, None))])
def test_passages(passage, expected):
    req = parse(f"### Passage\n\n{passage}\n")
    assert (req.surah, req.start, req.end) == expected
    assert req.reciter == "auto" and req.background == "auto"      # defaults


def test_platform_names_and_form_leftovers():
    req = parse("### Passage\n93\n### Plateformes\nTikTok (brouillon) + yt, fb\n"
                "### Fond\n_No response_\n")
    assert req.platforms == ("facebook", "tiktok", "youtube") and req.background == "auto"


@pytest.mark.parametrize("text, problem", [
    ("### Récitateur\nminshawi\n", "Passage"), ("### Passage\n115\n", "entre 1 et 114"),
    ("### Passage\n93:5-2\n", "93:5-2"), ("### Passage\n93\n### Plateformes\nsnapchat\n",
                                          "snapchat")])
def test_unreadable_requests_say_why(text, problem):
    with pytest.raises(RequestError) as e:
        parse(text)
    assert problem in str(e.value)


def test_a_request_is_recognised_by_its_title_or_headings():
    assert is_request("À la demande : 93 · auto", "")
    assert is_request("a la demande: 93", "")
    assert is_request("anything", CATALOGUE_BODY)
    assert not is_request("Catalogue : retirer le fond x", "Décision : …")


# ---- the rules: the calendar's, nothing looser ------------------------------------------

DUHA = {1: "By the morning brightness", 2: "And [by] the night when it covers with darkness,",
        3: "Your Lord has not taken leave of you, [O Muhammad], nor has He detested [you].",
        4: "And the Hereafter is better for you than the first [life].",
        5: "And your Lord is going to give you, and you will be satisfied.",
        6: "Did He not find you an orphan and give [you] refuge?",
        7: "And He found you lost and guided [you],",
        8: "And He found you poor and made [you] self-sufficient.",
        9: "So as for the orphan, do not oppress [him].",
        10: "And as for the petitioner, do not repel [him].",
        11: "But as for the favor of your Lord, report [it]."}


class Quran:
    def __init__(self):
        self.chapters = {93: {"verses_count": 11, "name_simple": "Ad-Duhaa",
                              "name_arabic": "الضحى"}}

    def ensure(self, slug):
        pass

    def translate(self, slug, refs):
        return {r: DUHA[r.ayah] for r in refs}


SRC = SimpleNamespace(quran=Quran(), translation_slug="en-sahih-international")
PACE = {"minshawi": 9.0, "sayegh": 5.0, "budair": 6.0, "fares_abbad": 7.0}


def seconds(name, key):
    """6 s an ayah for Budair, slower or quicker for the others; Omar Hisham not split."""
    if name == "omar_hisham":
        return Option(name, None, "surah 93 not split")
    a, b = (int(x) for x in key.split(":")[1].split("-"))
    return Option(name, round(PACE[name] * (b - a + 1) + 2, 1))


def verdict(cfg, reciter="budair", start=None, end=None, state=None, **kw):
    req = Request(reciter, 93, start, end, kw.pop("background", "auto"),
                  kw.pop("platforms", ("facebook", "instagram", "tiktok", "youtube")))
    return check(cfg, req, state or {}, src=SRC, seconds=kw.pop("seconds", seconds),
                 plan={93: [(1, 11)]})


def test_a_whole_short_surah_is_allowed(cfg):
    c = verdict(cfg, "sayegh")
    assert c.ok and c.key == "93:1-11" and c.seconds == 57.0 and c.reciter == "sayegh"


def test_a_range_that_cuts_a_sentence_is_refused_with_valid_ranges(cfg):
    c = verdict(cfg, "sayegh", 3, 5)
    assert not c.ok and "93:2 ne la finit pas" in c.problems[0]
    assert [s.key for s in c.suggestions] == ["93:1-5", "93:4-5", "93:1-11"]
    assert str(c.suggestions[0]) == "93:1-5 (27 s)"
    c = verdict(cfg, "sayegh", 1, 7)
    assert "93:7 ne la finit pas" in c.problems[0]
    assert [s.key for s in c.suggestions][:2] == ["93:1-8", "93:1-6"]


def test_too_long_for_the_reciter_is_refused_with_pieces_and_other_reciters(cfg):
    c = verdict(cfg, "minshawi")                   # 9 s an ayah: 101 s
    assert c.problems == ["93:1-11 dure 101 s avec Muhammad Siddiq Al-Minshawi, plus que 90 s"]
    assert [s.key for s in c.suggestions][:2] == ["93:1-9", "93:10-11"]    # whole sentences
    assert all(s.seconds <= 90 for s in c.suggestions)
    assert [str(a) for a in c.alternatives] == ["Tawfiq As-Sayegh (57 s)", "Salah Budair (68 s)",
                                                "Fares Abbad (79 s)"]


def test_a_recording_not_split_yet_is_split_first(cfg):
    c = verdict(cfg, "omar_hisham")
    assert not c.problems and c.split == "omar_hisham" and not c.ok
    assert c.not_ready == "sourate 93 pas encore découpée"
    assert "Tawfiq As-Sayegh (57 s)" in [str(a) for a in c.alternatives]


def test_auto_follows_the_rotation_rule(cfg):
    c = verdict(cfg, "auto", 1, 5)                 # closest to 60 s among the ready ones
    assert c.reciter == "minshawi" and c.seconds == 47.0
    recent = {"slots": {"2026-11-05/morning": {"reciter": "minshawi", "results": {}}}}
    assert verdict(cfg, "auto", 1, 5, state=recent).reciter != "minshawi"     # avoid_last


def test_only_reciters_allowed_for_publishing(cfg):
    assert "pas autorisé" in verdict(cfg, "alafasy").problems[0]          # not in the rotation
    claimed = {"claimed": {"sayegh": {"reason": "muted"}}}
    assert "revendication" in verdict(cfg, "sayegh", state=claimed).problems[0]
    assert "inconnu" in verdict(cfg, "nobody").problems[0]


def test_youtube_is_dropped_for_a_reciter_content_id_claims(cfg):
    c = verdict(cfg, "budair")
    assert c.ok and c.platforms == ("facebook", "instagram", "tiktok")
    assert "YouTube retiré" in c.notes[0] and "Tawfiq As-Sayegh" in c.notes[0]
    alone = verdict(cfg, "budair", platforms=("youtube",))
    assert not alone.ok and "YouTube retiré" in alone.problems[0]


def test_backgrounds_from_the_list_only(cfg):
    assert verdict(cfg, "sayegh", background="night").background == "night"
    assert "absent de config/backgrounds.yaml" in verdict(cfg, "sayegh",
                                                          background="disco").problems[0]


def test_a_passage_published_before_is_noted_not_refused(cfg):
    state = {"slots": {"2026-11-01/morning": {"passage": "93:1-11", "results": {
        "facebook": {"status": "published"}}}},
             "on_demand": {"7": {"passage": "93:1-11", "results": {
                 "tiktok": {"status": "draft"}}}}}
    c = verdict(cfg, "sayegh", state=state)
    assert c.ok and c.notes == ["déjà publié : calendrier, 2026-11-01/morning (facebook)",
                                "déjà publié : à la demande, #7 (tiktok)",
                                ("déjà publié à la main, hors calendrier (schedule.yaml, "
                                 "published_by_hand)")]    # 93:1-11, 2026-11-05


# ---- who may drive it ---------------------------------------------------------------------

def owner_comment(body, cid=10, at="2026-11-06T10:00:00Z", login=OWNER, assoc="OWNER"):
    return {"id": cid, "body": body, "created_at": at, "user": {"login": login},
            "author_association": assoc}


def bot_preview(meta, at="2026-11-06T09:00:00Z", cid=5, login=BOT):
    return {"id": cid, "body": comments.marker(meta) + "\n## 👀 Aperçu", "created_at": at,
            "user": {"login": login}, "author_association": "NONE"}


@pytest.mark.parametrize("text, expected", [
    ("/publier", ("publish", "")), ("/Publier\nmerci", ("publish", "")),
    ("/essai", ("dry-run", "")), ("/aperçu", ("preview", "")),
    ("/youtube https://youtube.com/shorts/x", ("youtube", "https://youtube.com/shorts/x")),
    ("publier", ("", "")), ("/unknown", ("", ""))])
def test_commands(text, expected):
    assert command(text) == expected


def test_only_the_owner_drives_the_flow():
    issue = {"user": {"login": OWNER}, "author_association": "OWNER", "number": 3}
    assert authorized("issues", {"issue": issue, "sender": {"login": OWNER}}, OWNER) is None
    assert authorized("issues", {"issue": issue, "sender": {"login": "eve"}}, OWNER)
    other = {"user": {"login": "eve"}, "author_association": "NONE"}
    assert authorized("issues", {"issue": other, "sender": {"login": "eve"}}, OWNER)
    ok = {"issue": issue, "comment": owner_comment("/publier")}
    assert authorized("issue_comment", ok, OWNER) is None
    for c in (owner_comment("/publier", login="eve"),
              owner_comment("/publier", assoc="CONTRIBUTOR")):
        assert authorized("issue_comment", {"issue": issue, "comment": c}, OWNER)
    pr = {"issue": issue | {"pull_request": {}}, "comment": owner_comment("/publier")}
    assert authorized("issue_comment", pr, OWNER)
    assert authorized("workflow_dispatch", {"sender": {"login": "eve"}}, OWNER)


def test_approval_needs_a_bot_preview_then_the_owners_command():
    meta = {"run": 1, "sha256": "abc"}
    fake = bot_preview({"run": 666}, at="2026-11-06T09:30:00Z", cid=6, login="eve")
    comments_ = [bot_preview(meta), fake, owner_comment("/publier", 11)]
    got = approval(comments_, OWNER, "publish", 11)
    assert got.meta == meta and got.comment["id"] == 11           # the fake marker is ignored
    with pytest.raises(Refused, match="pas d'aperçu"):
        approval([fake, owner_comment("/publier")], OWNER, "publish")
    early = owner_comment("/publier", 4, at="2026-11-06T08:00:00Z")
    with pytest.raises(Refused, match="précède le dernier aperçu"):
        approval([early, bot_preview(meta)], OWNER, "publish", 4)
    with pytest.raises(Refused, match="pas de `/publier`"):
        approval([bot_preview(meta), owner_comment("/publier", 12, login="eve")], OWNER,
                 "publish")
    assert approval([bot_preview(meta), owner_comment("/essai", 13)], OWNER,
                    "dry-run").comment["id"] == 13


def payload(body="/publier", title="À la demande : 93 · auto", state="open", login=OWNER):
    issue = {"number": 42, "title": title, "body": CATALOGUE_BODY, "state": state,
             "user": {"login": OWNER}, "author_association": "OWNER"}
    return {"issue": issue, "comment": owner_comment(body, login=login),
            "sender": {"login": login}}


def test_route():
    p = payload()
    assert flow.route("issues", p, OWNER)["command"] == "preview"
    assert flow.route("issue_comment", p, OWNER)["command"] == "publish"
    assert flow.route("issue_comment", payload("/essai"), OWNER)["command"] == "dry-run"
    assert flow.route("issue_comment", payload(login="eve"), OWNER)["command"] == ""
    assert flow.route("issue_comment", payload(state="closed"), OWNER)["command"] == ""
    captions = payload("/youtube 2026-11-06/morning", title=flow.CAPTIONS_TITLE)
    assert flow.route("issue_comment", captions, OWNER).items() >= {
        "command": "youtube", "kind": "captions"}.items()
    assert flow.route("issue_comment", payload(title=flow.CAPTIONS_TITLE), OWNER)[
        "command"] == ""
    other = payload(title="Catalogue : retirer le fond x")
    other["issue"]["body"] = "Décision"
    assert flow.route("issues", other, OWNER)["command"] == ""


# ---- texts ---------------------------------------------------------------------------------

def reel(caption="Surah Ad-Duhaa (93:1-11) · سورة الضحى\n\nبِسْمِ\n\nRecitation: X\n"):
    return Reel(Passage(93, 1, 11, "الضحى", "Ad-Duhaa"), Path("x.mp4"), caption,
                hashtags=["#QuranWordsDaily", "#Quran", "#SurahAdDuhaa", "#سورة_الضحى",
                          "#القرآن_الكريم", "#Minshawi"])


def test_youtube_texts_come_from_the_caption():
    yt = publish_mod.youtube_texts(reel())
    assert yt["title"] == "Surah Ad-Duhaa (93:1-11) · سورة الضحى"
    assert yt["description"].startswith(yt["title"]) and "Recitation: X" in yt["description"]
    assert yt["hashtags"].split() == reel().hashtags
    series = publish_mod.youtube_texts(reel("Supplications from the Quran · آيات الدعاء · 3/38\n"
                                            "Surah Al-Baqarah (2:201) · سورة البقرة\n\nx\n"))
    assert series["title"] == ("Supplications from the Quran · آيات الدعاء · 3/38 · "
                               "Surah Al-Baqarah (2:201) · سورة البقرة")


def test_a_long_youtube_title_keeps_both_languages():
    """Shortened by whole parts: the counter, then the series; never one language alone
    (owner, 2026-11-09)."""
    surah = "Surah Al-Baqarah (2:222) · سورة البقرة"
    no_count = publish_mod.youtube_texts(reel(
        f"Repentance and forgiveness in the Quran · آيات التوبة · 12/16\n{surah}\n\nx\n"))
    assert no_count["title"] == f"Repentance and forgiveness in the Quran · آيات التوبة · {surah}"
    long = publish_mod.youtube_texts(reel(
        "The first ten verses of Surah Al-Kahf · أول عشر آيات من سورة الكهف\n"
        "Surah Al-Kahf (18:1-10) · سورة الكهف\n\nx\n"))
    assert long["title"] == "Surah Al-Kahf (18:1-10) · سورة الكهف"
    assert publish_mod.youtube_texts(reel(), 3)["hashtags"] == "#QuranWordsDaily #Quran #SurahAdDuhaa"


def test_preview_comment(cfg):
    from quran_reels.ondemand import page

    d = page.data(cfg, reel(), kind="on-demand", rid="od/42/1", stage="preview", created="t",
                  reciter="Muhammad Siddiq Al-Minshawi", seconds=58.3,
                  platforms=["facebook", "instagram", "tiktok", "youtube"],
                  background={"id": "night", "theme": "chosen"},
                  video={"preview": "https://p.mp4"}, frames=["https://f1", "https://f2"])
    text = comments.preview(d, {"run": 1, "sha256": "s"}, "https://page", ["note"])
    assert comments.read_marker(text) == {"run": 1, "sha256": "s"}
    assert "night (choisi à la main)" in text and '<img src="https://f1"' in text
    assert "réponds `/publier`" in text and "> ⚠️ note" in text
    labels = [c["label"] for c in d["captions"]]
    assert labels == ["Facebook", "Instagram, TikTok"]       # 8 hashtags, then 5 for both
    assert d["captions"][1]["text"].rstrip().endswith("#القرآن_الكريم")


# ---- publication: the previewed file, after the owner's command ---------------------------

class FakeGh:
    repo, owner = f"{OWNER}/quran-reels", OWNER

    def __init__(self, comments_, artifact_dir):
        self._comments, self.artifact_dir = comments_, artifact_dir
        self.posted, self.edits, self.reactions = [], [], []
        self.body = CATALOGUE_BODY
        self.run = {"path": flow.WORKFLOW, "repository": {"full_name": self.repo}}

    def issue(self, number):
        return {"number": number, "body": self.body, "user": {"login": OWNER},
                "author_association": "OWNER", "html_url": f"https://github.com/i/{number}"}

    def comments(self, number):
        return self._comments

    def comment(self, number, text):
        self.posted.append(text)

    def react(self, number, content="eyes", comment_id=None):
        self.reactions.append(content)

    def label(self, *a, **k):
        pass

    def edit_issue(self, number, **fields):
        self.edits.append(fields)

    def run_info(self, run_id):
        return self.run

    def download_artifact(self, run_id, name, dest):
        import shutil

        shutil.copytree(self.artifact_dir, dest, dirs_exist_ok=True)

    def api_list(self, path):
        return []


class FakeHosting:
    def __init__(self):
        self.uploaded, self.pages = {}, {}

    def upload(self, path, name):
        self.uploaded[name] = path
        return f"https://dl/{name}"

    def publish(self, files, message, **kw):
        self.pages.update(files)

    def read(self, rel):
        return self.pages.get(rel)

    def page_url(self, rid, version=""):
        return f"https://page/{rid}"

    def raw_url(self, path):
        return f"https://raw/{path}"

    def prune_assets(self, *a, **k):
        return []


def make_reel(folder: Path, key="93:1-11") -> Path:
    """A rendered reel as load_reel reads it: MP4, manifest.json, caption.txt."""
    slug = flow.slug(key)
    (folder / slug / "preview").mkdir(parents=True)
    video = folder / f"{slug}.mp4"
    video.write_bytes(b"mp4 bytes")
    (folder / slug / "manifest.json").write_text(json.dumps({
        "passage": key, "surah": {"name_ar": "الضحى", "name_en": "Ad-Duhaa"},
        "hashtags": ["#QuranWordsDaily", "#Quran"],
        "ayahs": [{"ref": "93:1", "glosses": [], "start": 0.4, "seconds": 3.0}]}), "utf-8")
    (folder / slug / "caption.txt").write_text(
        "Surah Ad-Duhaa (93:1-11) · سورة الضحى\n\nx\n\n#QuranWordsDaily #Quran\n", "utf-8")
    return video


@pytest.fixture
def world(cfg, tmp_path, monkeypatch):
    artifact = tmp_path / "artifact"
    video = make_reel(artifact)
    out = tmp_path / "out"
    cfg = cfg.__class__(**{**cfg.__dict__, "out_dir": out})
    meta = {"run": 99, "artifact": "on-demand-42-99", "sha256": media.sha256(video),
            "body": comments.body_hash(CATALOGUE_BODY), "rid": "od/42/99", "key": "93:1-11",
            "slug": "093_001-011", "reciter": "minshawi", "background": None,
            "platforms": ["facebook", "instagram", "tiktok", "youtube"], "seconds": 58.0}
    gh = FakeGh([bot_preview(meta), owner_comment("/publier", 11)], artifact)
    calls = []
    answers = {"rights": {"clear": True, "summary": "complete, aucune correspondance"}}

    def publish_reel(pcfg, v, platforms, dry_run, checked=None):
        calls.append((list(platforms), dry_run, pcfg.content["reciter"]["name"]))
        status = PublishStatus.DRAFT if dry_run else PublishStatus.PUBLISHED
        blocked = not answers["rights"]["clear"]
        out_ = []
        for p in platforms:
            st = PublishStatus.BLOCKED if blocked and not dry_run else (
                PublishStatus.DRAFT if p == "tiktok" else status)
            r = PublishResult(p, st, url=f"https://{p}/r" if st == PublishStatus.PUBLISHED
                              else None)
            if p in publish_mod.META:
                r.rights = answers["rights"]
            out_.append(r)
        return out_

    monkeypatch.setattr(publish_mod, "publish_reel", publish_reel)
    monkeypatch.setattr(publish_mod, "meta_check", lambda c, p: ("graph", "env", "token"))
    state_path = tmp_path / "state" / "published.json"
    return SimpleNamespace(cfg=cfg, gh=gh, hosting=FakeHosting(), calls=calls, answers=answers,
                           state=state_path, meta=meta)


def go(w, mode="publish", comment_id=11):
    return flow.run_publish(w.cfg, w.gh, w.hosting, 42, mode, w.state, comment_id)


def saved(w):
    return json.loads(w.state.read_text(encoding="utf-8"))


def test_publish_sends_the_previewed_file_then_offers_youtube(world):
    assert go(world) == 0
    assert world.calls == [(["facebook", "instagram", "tiktok"], False, "minshawi")]
    entry = saved(world)["on_demand"]["42"]
    assert {p: r["status"] for p, r in entry["results"].items()} == {
        "facebook": "published", "instagram": "published", "tiktok": "draft",
        "youtube": "manual"}
    assert entry["results"]["youtube"]["video"] == "https://dl/od42-093_001-011-99.mp4"
    assert entry["approved"]["comment"] == 11 and entry["passage"] == "93:1-11"
    text = world.gh.posted[-1]
    assert "Télécharger le MP4 1080p](https://dl/od42-093_001-011-99.mp4)" in text
    assert "**Titre** (" in text and "/youtube <lien du Short>" in text
    assert "Légende à coller sur le brouillon TikTok" in text
    page = json.loads(world.hosting.pages["od/42/99/reel.json"])
    assert page["stage"] == "published" and page["youtube"]["file"].endswith("-99.mp4")
    assert not world.gh.edits               # stays open until /youtube


def test_nothing_is_published_twice_by_one_request(world):
    go(world)
    world.gh._comments.append(owner_comment("/publier", 12, at="2026-11-06T11:00:00Z"))
    go(world, comment_id=12)
    assert len(world.calls) == 1              # every platform already there: YouTube only
    assert "youtube" in saved(world)["on_demand"]["42"]["results"]


def test_a_rights_match_publishes_nothing_and_offers_no_youtube(world):
    world.answers["rights"] = {"clear": False, "summary": "correspondance : X"}
    assert go(world) == 1
    entry = saved(world)["on_demand"]["42"]
    assert {r["status"] for r in entry["results"].values()} == {"blocked"}
    assert not world.hosting.uploaded and "Bloqué" in world.gh.posted[-1]


def test_tiktok_alone_still_goes_through_metas_check(world):
    world.meta["platforms"] = ["tiktok"]
    world.gh._comments[0] = bot_preview(world.meta)
    go(world)
    assert world.calls == [(["facebook", "instagram"], True, "minshawi"),     # rights only
                           (["tiktok"], False, "minshawi")]


def test_youtube_alone_checks_the_rights_and_shows_no_empty_table(world):
    world.meta["platforms"] = ["youtube"]
    world.gh._comments[0] = bot_preview(world.meta)
    assert go(world) == 0
    assert world.calls == [(["facebook", "instagram"], True, "minshawi")]     # rights only
    text = world.gh.posted[-1]
    assert "| Plateforme |" not in text and "Télécharger le MP4 1080p" in text

def test_a_dry_run_changes_no_state_and_skips_tiktok(world):
    world.gh._comments.append(owner_comment("/essai", 13))
    assert go(world, "dry-run", 13) == 0
    assert world.calls == [(["facebook", "instagram"], True, "minshawi")]
    assert not world.state.exists()
    assert "Essai" in world.gh.posted[-1] and world.hosting.uploaded     # YouTube step testable


@pytest.mark.parametrize("change, why", [
    ("body", "le ticket a changé"), ("run", "ne vient pas du workflow"),
    ("approval", "précède le dernier aperçu")])
def test_publication_refused(world, change, why):
    if change == "body":
        world.gh.body = CATALOGUE_BODY.replace("93:1-5", "93:1-11")
    if change == "run":
        world.gh.run = {"path": ".github/workflows/tests.yml",
                        "repository": {"full_name": world.gh.repo}}
    if change == "approval":
        world.gh._comments.insert(0, owner_comment("/publier", 3, at="2026-11-06T08:00:00Z"))
    assert go(world, comment_id=3 if change == "approval" else 11) == 0
    assert why in world.gh.posted[-1] and not world.calls


def test_a_different_file_is_never_published(world):
    (world.gh.artifact_dir / "093_001-011.mp4").write_bytes(b"another video")
    assert go(world) == 1
    assert "empreinte" in world.gh.posted[-1] and not world.calls


# ---- YouTube by hand -------------------------------------------------------------------------

def test_youtube_is_recorded_once_offered(world):
    assert flow.run_youtube(world.cfg, world.gh, 42, "https://youtu.be/x", world.state) == 0
    assert "pas encore proposé" in world.gh.posted[-1]
    go(world)
    flow.run_youtube(world.cfg, world.gh, 42, "https://youtu.be/x", world.state)
    yt = saved(world)["on_demand"]["42"]["results"]["youtube"]
    assert yt.items() >= {"status": "published", "by_hand": True,
                          "url": "https://youtu.be/x"}.items()
    assert world.gh.edits[-1] == {"state": "closed", "state_reason": "completed"}


def test_youtube_on_the_captions_issue_marks_a_calendar_slot(world):
    world.state.parent.mkdir(parents=True)
    world.state.write_text(json.dumps({"slots": {
        "2026-11-06/morning": {"passage": "18:1-10", "results": {
            "facebook": {"status": "published"}}},
        "2026-11-05/evening": {"passage": "2:255-255", "results": {
            "facebook": {"status": "published"}}}}}), "utf-8")
    world.gh.body = "<!-- entry 2026-11-06/morning -->\nCommente ici `/youtube 2026-11-06/morning <lien>`"
    flow.run_youtube(world.cfg, world.gh, 5, "2026-11-06/morning https://youtu.be/k",
                     world.state, comment_id=77, kind="captions")
    slots = saved(world)["slots"]
    assert slots["2026-11-06/morning"]["results"]["youtube"]["url"] == "https://youtu.be/k"
    assert "✅ YouTube : [mis en ligne](https://youtu.be/k)" in world.gh.edits[-1]["body"]
    flow.run_youtube(world.cfg, world.gh, 5, "", world.state, kind="captions")   # the latest
    assert saved(world)["slots"]["2026-11-05/evening"]["results"]["youtube"]["by_hand"]
    flow.run_youtube(world.cfg, world.gh, 5, "2026-01-01/morning", world.state, kind="captions")
    assert "introuvable" in world.gh.posted[-1]


# ---- daily reels: direct downloads ----------------------------------------------------------

def test_daily_reels_get_a_direct_download_and_a_youtube_page(world, tmp_path):
    from quran_reels import notify

    out = world.cfg.out
    make_reel(out, "18:1-10")
    make_reel(out / "youtube", "18:1-10")
    report = {"items": [{"key": "2026-11-06/morning", "day": "2026-11-06", "time": "07:30",
                         "passage": "18:1-10", "label": "", "reciter": "budair",
                         "caption": "Al-Kahf\n", "results": {
                             "facebook": {"status": "published", "url": "https://f"}},
                         "youtube": {"reciter": "sayegh", "video": "youtube/018_001-010.mp4",
                                     "label": "Tawfiq As-Sayegh", "caption": "c",
                                     "instead_of": "Salah Budair"}}]}
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), "utf-8")
    assert flow.daily_files(world.cfg, world.hosting, path) == 0
    assert set(world.hosting.uploaded) == {"2026-11-06-morning-018_001-010.mp4",
                                           "2026-11-06-morning-018_001-010-youtube.mp4"}
    item = json.loads(path.read_text("utf-8"))["items"][0]
    assert item["files"]["youtube_mp4"].endswith("-youtube.mp4")
    page = json.loads(world.hosting.pages["daily/2026-11-06-morning/reel.json"])
    assert page["youtube"]["command"] == "/youtube 2026-11-06/morning"
    entry = notify.merge_captions("", {"items": [item]})
    assert "⬇️ [MP4](https://dl/2026-11-06-morning-018_001-010.mp4)" in entry
    assert "`/youtube 2026-11-06/morning <lien>`" in entry
    assert "mais [ce MP4](https://dl/2026-11-06-morning-018_001-010-youtube.mp4)" in entry


# ---- files ------------------------------------------------------------------------------------

def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_the_previews_branch_is_written_and_old_folders_pruned(tmp_path):
    remote = tmp_path / "remote.git"
    git("init", "-q", "--bare", str(remote), cwd=tmp_path)
    repo = tmp_path / "repo"
    git("init", "-q", str(repo), cwd=tmp_path)
    git("remote", "add", "origin", str(remote), cwd=repo)
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "m",
        cwd=repo)
    h = Hosting(SimpleNamespace(repo=f"{OWNER}/quran-reels"), repo, sleep=lambda s: None)
    old = (datetime.now(UTC) - timedelta(days=40)).isoformat()
    h.publish({"od/1/1/reel.json": json.dumps({"created": old})}, "first")
    h.publish({"od/2/5/reel.json": json.dumps({"created": datetime.now(UTC).isoformat()}),
               "od/2/5/frame-1.jpg": "jpg"}, "second")
    listing = subprocess.run(["git", "ls-tree", "-r", "--name-only", "previews"], cwd=remote,
                             capture_output=True, text=True, check=True).stdout.split()
    assert listing == ["od/2/5/frame-1.jpg", "od/2/5/reel.json"]          # the old one pruned
    assert json.loads(h.read("od/2/5/reel.json"))["created"]
    assert h.asset_url("a.mp4") == (f"https://github.com/{OWNER}/quran-reels/releases/download/"
                                    "reels/a.mp4")
    assert h.page_url("od/2/5", "1") == ("https://mssnoussi92.github.io/quran-reels/reel.html"
                                         "?r=od/2/5&v=1")


def test_prune_keeps_what_is_being_written(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "reel.json").write_text(json.dumps({"created": "2020-01-01T00:00:00+00:00"}))
    assert prune_folders(tmp_path, 30, keep={"a/reel.json"}) == []
    assert prune_folders(tmp_path, 30) == ["a"]


def test_assets_older_than_30_days_are_deleted():
    now = datetime(2026, 12, 10, tzinfo=UTC)
    deleted = []
    gh = SimpleNamespace(
        repo="o/r", release=lambda *a: {"id": 1},
        assets=lambda rid: [{"id": 1, "name": "old.mp4", "created_at": "2026-11-01T00:00:00Z"},
                            {"id": 2, "name": "new.mp4", "created_at": "2026-12-01T00:00:00Z"}],
        delete_asset=deleted.append)
    assert Hosting(gh, Path(".")).prune_assets(30, now) == ["old.mp4"] and deleted == [1]


def test_key_frames_first_glossed_last():
    manifest = {"ayahs": [
        {"start": 0.4, "seconds": 4, "glosses": []},
        {"start": 4.4, "seconds": 4, "glosses": []},
        {"start": 8.4, "seconds": 4, "glosses": [{"word": "x"}]},
        {"start": 12.4, "seconds": 6, "glosses": [], "screens": [
            {"start": 12.4}, {"start": 15.4}]}]}
    assert media.moments(manifest) == [2.4, 10.4, 16.9]
    assert media.moments({"ayahs": [{"start": 0.4, "seconds": 3, "glosses": []}]}) == [1.9]


def test_a_background_can_be_imposed(cfg):
    from quran_reels.sources import backgrounds

    assert backgrounds.by_id(cfg, "night").scene == "night"
    with pytest.raises(SystemExit):
        backgrounds.by_id(cfg, "disco")


def test_state_records_each_platform():
    state = {}
    od_state.record(state, 42, {"key": "93:1-11", "reciter": "x", "platforms": ["facebook"]},
                    {"run": 1}, [PublishResult("facebook", PublishStatus.FAILED, error="e")], {})
    assert od_state.done_platforms(state, 42) == set()
    od_state.record(state, 42, {"key": "93:1-11", "reciter": "x", "platforms": ["facebook"]},
                    {"run": 1}, [PublishResult("facebook", PublishStatus.PUBLISHED)], {})
    assert od_state.done_platforms(state, 42) == {"facebook"}


# ---- which words are highlighted and explained (/mots) -------------------------------------

def test_the_words_section():
    from quran_reels.ondemand.request import parse_words, with_words, words_text

    assert parse_words("auto") is None and parse_words("") is None
    assert parse_words("aucun") == () and parse_words("Aucun") == ()
    assert parse_words("2, 5=زهرة الحياة, 7") == ((2, ()), (5, ("زهرة", "الحياة")), (7, ()))
    assert parse_words("٢ ٤") == ((2, ()), (4, ()))                    # Arabic-Indic digits
    for bad in ("x", "2 2", "5=a b c d"):
        with pytest.raises(ValueError):
            parse_words(bad)
    text = with_words(CATALOGUE_BODY, ((2, ()), (4, ("قلى",))))
    assert parse(text).words == ((2, ()), (4, ("قلى",)))
    assert text.index("### Mots") < text.index("---")              # before the footer
    assert parse(with_words(text, ())).words == ()                 # replaced, not added
    assert with_words(text, ()).count("### Mots") == 1
    assert words_text(None) == "auto" and parse(body(parse(text))) == parse(text)


TEXTS_93 = {1: "وَٱلضُّحَىٰ", 2: "وَٱلَّيْلِ إِذَا سَجَىٰ", 3: "مَا وَدَّعَكَ رَبُّكَ وَمَا قَلَىٰ"}
ENTRIES_93 = {1: [("وَالضُّحَى", "أقسم الله بوقت الضحى.")], 2: [("سَجَى", "اشتد ظلامه.")],
              3: [("مَا وَدَّعَكَ", "ما تركك."), ("وَمَا قَلَى", "وما أبغضك."),
                  ("غَيْرُ مَوْجُودٍ", "نص."), ("وَدَّعَكَ رَبُّكَ", "ما تركك ربك.")]}


def word_src():
    from quran_reels.models import GlossEntry

    quran = SimpleNamespace(text=lambda refs: {r: TEXTS_93[r.ayah] for r in refs},
                            global_index=lambda r: r.ayah)
    glosses = SimpleNamespace(entries=lambda refs, index: {
        r: [GlossEntry(r, lemma, text, "ar-tafsir-muyassar-ghareeb")
            for lemma, text in ENTRIES_93[r.ayah]] for r in refs})
    return SimpleNamespace(quran=quran, glosses=glosses)


def test_the_preview_numbers_every_meaning_of_the_source(cfg):
    from quran_reels.ondemand import words

    found = words.meanings(cfg, word_src(), "93:1-3")
    assert [(m.n, m.ref, m.word()) for m in found if m.usable] == [
        (1, "93:1", "وَٱلضُّحَىٰ"), (2, "93:2", "سَجَىٰ"), (3, "93:3", "وَدَّعَكَ"),
        (4, "93:3", "قَلَىٰ"), (6, "93:3", "وَدَّعَكَ رَبُّكَ")]
    assert found[4].why == "pas retrouvé dans le texte de l'ayah"
    manifest = {"ayahs": [{"ref": "93:2", "glosses": [{"lemma": "سَجَى"}]}]}
    assert words.shown_numbers(found, manifest) == {2}


@pytest.mark.parametrize("chosen, problem", [
    (((9, ()),), "il n'y en a que 6"), (((5, ()),), "pas retrouvé"),
    (((3, ("قلى",)),), "n'est pas dans la citation"),
    (((3, ()), (6, ())), "surlignent le même mot"),
    (((3, ()), (4, ()), (1, ())), None)])
def test_the_owners_choice_is_checked(cfg, chosen, problem):
    from quran_reels.ondemand import words

    found = words.meanings(cfg, word_src(), "93:1-3")
    picked, problems = words.selection(cfg, found, chosen)
    if problem:
        assert problem in problems[0]
    else:
        assert not problems
        assert picked == {"93:3": [(0, ()), (1, ())], "93:1": [(0, ())]}


def test_at_most_max_per_ayah(cfg):
    import copy

    from quran_reels.ondemand import words

    one = copy.deepcopy(cfg)
    one.project["content"]["glosses"]["max_per_ayah"] = 1
    found = words.meanings(one, word_src(), "93:1-3")
    _, problems = words.selection(one, found, ((3, ()), (4, ())))
    assert problems == ["93:3 : 2 mots choisis, 1 au plus par ayah (la place à l'écran)"]


def test_check_passes_the_choice_to_the_rendering(cfg):
    from quran_reels.ondemand import words

    found = words.meanings(cfg, word_src(), "93:1-3")
    c = verdict(cfg, "sayegh", 1, 3, meanings=lambda key: found)
    assert c.glosses is None                                   # the usual rules
    req = Request("sayegh", 93, 1, 3, words=((4, ("قلى",)),))
    c = check(cfg, req, {}, src=SRC, seconds=seconds, plan={93: [(1, 11)]},
              meanings=lambda key: found)
    assert c.ok and c.glosses == {"93:3": [(1, ("قلى",))]}
    req = Request("sayegh", 93, 1, 3, words=())
    assert check(cfg, req, {}, src=SRC, seconds=seconds, plan={},
                 meanings=lambda key: found).glosses == {}
    req = Request("sayegh", 93, 1, 3, words=((9, ()),))
    assert "il n'y en a que 6" in check(cfg, req, {}, src=SRC, seconds=seconds, plan={},
                                         meanings=lambda key: found).problems[0]


def test_mots_rewrites_the_request_then_previews_again(world):
    assert flow.route("issue_comment", payload("/mots 2 4=قلى"), OWNER)["command"] == "words"
    assert flow.run_words(world.gh, 42, "2 4=قلى") is True
    assert "### Mots\n\n2, 4=قلى" in world.gh.edits[-1]["body"]
    assert flow.run_words(world.gh, 42, "deux") is False
    assert "`/mots`" in world.gh.posted[-1]


def test_the_preview_lists_the_words_and_how_to_choose(cfg):
    from quran_reels.ondemand import page

    d = page.data(cfg, reel(), kind="on-demand", rid="od/42/1", stage="preview", created="t",
                  reciter="x", seconds=50, platforms=["facebook"])
    d["words"] = [{"n": 1, "ref": "93:1", "word": "وَٱلضُّحَىٰ", "gloss": "أقسم الله بوقت الضحى.",
                   "usable": True, "why": "", "shown": True},
                  {"n": 2, "ref": "93:3", "word": "غير", "gloss": "", "usable": False,
                   "why": "pas retrouvé dans le texte de l'ayah", "shown": False}]
    d["words_mode"] = "auto"
    text = comments.preview(d, {"run": 1}, "https://page", [])
    assert "<b>Mots expliqués</b> : 1 sur 2 (choisis par les règles habituelles)" in text
    assert "- ✅ n° **1** · 93:1 · وَٱلضُّحَىٰ — أقسم الله بوقت الضحى." in text
    assert "- ✖️ n° **2** · 93:3 · غير — _pas retrouvé" in text
    assert "`/mots 1 4`" in text


# ---- the catalogue's form: ayahs and meanings before the issue ----------------------------

def form_src(missing=0):
    src = word_src()
    src.quran.chapters = {93: {"verses_count": 3, "name_simple": "Ad-Duhaa",
                               "name_arabic": "الضحى"}}
    src.quran.translate = lambda slug, refs: {r: DUHA[r.ayah] for r in refs}
    src.translation_slug = "en-sahih-international"
    calls = []
    src.glosses.missing = lambda refs, index: missing
    src.glosses.fetch = lambda refs, index: calls.append(len(list(refs)))
    return src, calls


def test_the_form_numbers_the_meanings_like_the_preview(cfg):
    from quran_reels.catalog import ondemand as od_cat
    from quran_reels.ondemand import words

    src, _ = form_src()
    data = od_cat.surah_data(cfg, src, 93)
    assert data["ends"] == [3] and data["ayahs"] == 3          # 93:1-2 is one sentence
    for a, b in ((1, 3), (2, 3), (3, 3)):                     # the page counts ayah by ayah
        page = [(i, m["k"]) for i in range(a, b + 1) for m in data["meanings"].get(str(i), [])]
        found = words.meanings(cfg, src, f"93:{a}-{b}")
        assert page == [(int(m.ref.split(":")[1]), m.choice.k) for m in found]
    third = data["meanings"]["3"]
    assert [(m["word"], m["usable"], m["auto"]) for m in third] == [
        ("وَدَّعَكَ", True, True), ("قَلَىٰ", True, True), ("غَيْرُ مَوْجُودٍ", False, False),
        ("وَدَّعَكَ رَبُّكَ", True, False)]          # the usual rules: 2 per ayah, no overlap


def test_meanings_are_downloaded_within_a_budget(cfg, tmp_path):
    from quran_reels.catalog import ondemand as od_cat

    src, calls = form_src(missing=5)
    ticks = iter([0, 0, 2000, 2000])                            # the budget is spent after one
    got = od_cat.surah_files(cfg, src, tmp_path, budget=900, clock=lambda: next(ticks),
                             surahs=[93, 93])
    assert got == {"surahs": 2, "with_meanings": 1} and calls == [3]
    saved = json.loads((tmp_path / "093.json").read_text("utf-8"))
    assert saved["meanings"] is None and saved["ends"] == [3]   # the second: words after preview


def test_the_catalogue_lists_only_requests_that_reached_a_platform(cfg):
    from quran_reels.catalog import ondemand as catalog_od

    def request(**results):
        return {"passage": "101:1-11", "reciter": "omar_hisham",
                "approved": {"at": "2026-11-06T13:51:29+00:00"},
                "results": {p: {"status": s} for p, s in results.items()}}

    state = {"on_demand": {"39": request(youtube="cancelled"), "40": request(youtube="manual"),
                           "41": request(facebook="blocked", instagram="blocked"),
                           "42": request(facebook="published", youtube="cancelled")}}
    posts = catalog_od.posts(cfg, state)
    assert [p["issue"] for p in posts] == [42]
    assert {r["platform"]: r["label"] for r in posts[0]["results"]}["youtube"] == (
        "annulé (pas mis en ligne)")
