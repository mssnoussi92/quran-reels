"""The YouTube channel's keywords and description, applied once (channel.py). No network."""

from pathlib import Path
from typing import ClassVar

import pytest

from quran_reels import channel as C

KEYWORDS = '"القرآن الكريم" Quran'
BRANDING = {"channel": {"title": "Quran Words Daily · القرآن", "description": "Quran recitation, twice a day",
                        "country": "FR", "unsubscribedTrailer": "abc"},
            "watch": {"featuredPlaylistId": "PLx"}, "image": {"bannerExternalUrl": "deprecated"}}


class FakeChannel:
    def __init__(self):
        self.branding, self.sent = {k: dict(v) for k, v in BRANDING.items()}, []
        outer = self

        class Client:
            def get(self, url, token, **params):
                assert params["part"] == "brandingSettings" and params["mine"] == "true"
                return {"items": [{"id": "UC1", "brandingSettings": outer.branding}]}
        self.client, self.token = Client(), "at"

    def _send(self, method, url, part, body):
        self.sent.append((method, part, body))
        self.branding = {**self.branding, **body["brandingSettings"]}
        return {}


def config(tmp_path, text):
    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "config" / "channel.yaml").write_text(text, encoding="utf-8")


def test_only_keywords_and_description_change_the_rest_is_sent_back(tmp_path, capsys):
    import yaml

    config(tmp_path, yaml.safe_dump({"validated": True, "keywords": KEYWORDS,
                                     "description": "عربي أولاً · Arabic first"}, allow_unicode=True))
    ch = FakeChannel()
    assert C.run(tmp_path, dry_run=True, ch=ch) == 0 and ch.sent == []       # a dry run: nothing
    assert "would change keywords, description" in capsys.readouterr().out
    assert C.run(tmp_path, dry_run=False, ch=ch) == 0
    (method, part, body), = ch.sent
    assert (method, part, body["id"]) == ("PUT", "brandingSettings", "UC1")
    sent = body["brandingSettings"]
    assert sent["channel"] == {"title": "Quran Words Daily · القرآن",      # with its direction mark
                               "description": "\u202bعربي أولاً · Arabic first", "country": "FR",
                               "unsubscribedTrailer": "abc", "keywords": KEYWORDS}
    assert sent["watch"] == {"featuredPlaylistId": "PLx"} and "image" not in sent
    assert "every other setting as it was" in capsys.readouterr().out
    assert C.run(tmp_path, dry_run=False, ch=ch) == 0 and len(ch.sent) == 1   # already there


def test_the_texts_are_arabic_first_true_and_within_youtubes_limits():
    conf = C.settings(Path(__file__).resolve().parents[1])
    assert len(conf["description"]) <= 1000 and len(conf["keywords"]) <= 500
    assert len(C.wanted({}, conf)["channel"]["description"]) <= 1000     # marks included
    assert conf["description"].startswith("القرآن والسنة في حياتك اليومية · Quran & Sunnah")
    assert "twice a day" not in conf["description"] and "every morning" in conf["description"]
    assert conf["description"].rstrip().endswith("(Sad, 38:29)")
    assert conf["keywords"].startswith('"القرآن الكريم"') and len(conf["keywords"]) <= 500
    assert len(conf["description"].encode("utf-8")) <= 5000


def test_without_its_token_it_says_how_to_sign_in(tmp_path, monkeypatch):
    monkeypatch.delenv("YOUTUBE_PLAYLISTS_REFRESH_TOKEN", raising=False)
    config(tmp_path, "keywords: x\n")
    with pytest.raises(SystemExit, match="youtube-login.html"):
        C.run(tmp_path, dry_run=True)


def test_nothing_is_applied_unvalidated_nor_over_the_limits(tmp_path):
    import yaml

    config(tmp_path, yaml.safe_dump({"keywords": KEYWORDS, "description": "x"}))
    ch = FakeChannel()
    assert C.run(tmp_path, dry_run=True, ch=ch) == 0                       # a dry run shows it
    with pytest.raises(SystemExit, match="not validated"):
        C.run(tmp_path, dry_run=False, ch=ch)
    config(tmp_path, yaml.safe_dump({"validated": True, "keywords": KEYWORDS, "description": "x" * 1001}))
    with pytest.raises(SystemExit, match=r"description \(1001 > 1000\)"):
        C.run(tmp_path, dry_run=True, ch=ch)
    assert ch.sent == []


# ------------------------------------------------------------- a series' name, at its first video

class Names:
    series: ClassVar[dict] = {"rizq": ("Provision (rizq) in the Quran", "آيات الرزق"),
              "tawba": ("Repentance and forgiveness in the Quran", "آيات التوبة والاستغفار")}

    @staticmethod
    def of_doc(doc):
        return {"qadar": ("Free will or fate?", "مخيّر ولا مسيّر؟"),
                "hayyin": ("You Think It Is Small", "وتحسبونه هيّنًا")}.get(doc)


TABLE = {"series_keywords": {"series": {"juz-amma": "جزء عم", "mushaf": None,
                                        "tawba": "آيات التوبة"},
                             "docs": {"sahw": ["إزاي أعملها", "سجود السهو"], "quiz": None}}}


def test_each_series_gives_its_written_or_bare_arabic_name_once():
    groups = [("series", "juz-amma"), ("docs", "qadar"), ("series", "mushaf"), ("docs", "quiz"),
              ("series", "rizq"), ("docs", "qadar"), ("docs", "sahw"), ("series", "tawba"),
              ("docs", "hayyin"), ("docs", "unknown")]
    assert C.series_words(groups, TABLE, Names()) == [
        "جزء عم", "مخير ولا مسير", "آيات الرزق", "إزاي أعملها", "سجود السهو", "آيات التوبة",
        "وتحسبونه هينا"]


def test_a_new_series_name_is_added_at_the_end_nothing_else_changes():
    ch = FakeChannel()
    ch.branding["channel"]["keywords"] = '"القرآن الكريم" "جزء عمّ" Quran'
    lines = C.add_keywords(ch, ["جزء عم", "مخير ولا مسير", "تلاوة"], dry_run=False)
    assert lines == ["add to the channel's keywords: « مخير ولا مسير », « تلاوة »"]
    (_, _, body), = ch.sent
    sent = body["brandingSettings"]
    assert sent["channel"]["keywords"] == '"القرآن الكريم" "جزء عمّ" Quran "مخير ولا مسير" تلاوة'
    assert sent["channel"]["description"] == "Quran recitation, twice a day"   # untouched
    assert sent["watch"] == {"featuredPlaylistId": "PLx"}
    assert C.add_keywords(ch, ["مخير ولا مسير", "تلاوة"], dry_run=False) == []   # already there
    assert len(ch.sent) == 1


def test_a_dry_run_says_it_and_a_full_list_is_never_cut():
    ch = FakeChannel()
    ch.branding["channel"]["keywords"] = "x" * 490
    assert C.add_keywords(ch, ["آيات الرزق", "صبر"], dry_run=True) == [
        "would add to the channel's keywords: « صبر »",
        ("warning: the channel's keywords are full (490/500): « آيات الرزق » not added, "
         "the owner chooses what to take out")]
    assert ch.sent == []


def test_the_nightly_step_reads_its_table_and_waits_a_night_on_an_error(tmp_path):
    import yaml

    from quran_reels.insights.youtube import YouTubeError

    config(tmp_path, yaml.safe_dump(TABLE, allow_unicode=True))
    ch = FakeChannel()
    assert C.series_keywords(tmp_path, [("docs", "qadar")], ch, Names(), dry_run=False) == [
        "add to the channel's keywords: « مخير ولا مسير »"]

    class Broken(FakeChannel):
        def _send(self, *a):
            raise YouTubeError("HTTP 403 forbidden")
    assert C.series_keywords(tmp_path, [("docs", "hayyin")], Broken(), Names(), dry_run=False) == [
        "warning: the channel's keywords not changed (HTTP 403 forbidden)"]
    config(tmp_path, "keywords: x\n")                                     # no table: nothing
    assert C.series_keywords(tmp_path, [("docs", "qadar")], ch, Names(), dry_run=False) == []


def test_a_video_belongs_to_its_series_or_its_document():
    from quran_reels.playlists import group_of

    published = {"slots": {"2026-11-29/evening": {"item": "rizq/11:6-6"}}}
    assert group_of("slot:2026-11-29/evening", published) == ("series", "rizq")
    assert group_of("theme:qadar-9x16/film", published) == ("docs", "qadar")
    assert group_of("hand:93:1-11", published) is None
    assert group_of("slot:2026-01-01/morning", published) is None


def test_the_repository_table_names_series_that_exist():
    root = Path(__file__).resolve().parents[1]
    table = C.settings(root)["series_keywords"]
    series = {p.stem for p in (root / "config" / "series").glob("*.yaml")}
    assert set(table["series"]) <= series
    assert all(len(w) <= C.LONGEST for v in (table["series"] | table["docs"]).values() if v
               for w in ([v] if isinstance(v, str) else v))


def test_a_change_youtube_serves_late_is_read_again_not_called_refused(tmp_path, capsys):
    """2026-11-21: read at once after the change, both fields seemed refused; they were there."""
    import yaml

    config(tmp_path, yaml.safe_dump({"validated": True, "keywords": KEYWORDS,
                                     "description": "عربي أولاً · Arabic first"}, allow_unicode=True))

    class Late(FakeChannel):
        def __init__(self, stale_reads):
            super().__init__()
            self.stale, self.old = stale_reads, None
            outer, inner = self, self.client

            class Client:
                def get(self, url, token, **params):
                    if outer.old is not None and outer.stale > 0:
                        outer.stale -= 1
                        return {"items": [{"id": "UC1", "brandingSettings": outer.old}]}
                    return inner.get(url, token, **params)
            self.client = Client()

        def _send(self, method, url, part, body):
            self.old = {k: dict(v) for k, v in self.branding.items()}
            return super()._send(method, url, part, body)

    waits = []
    assert C.run(tmp_path, dry_run=False, ch=Late(stale_reads=2), sleep=waits.append) == 0
    assert waits == [C.WAIT, C.WAIT] and "every other setting as it was" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="did not keep keywords, description"):
        C.run(tmp_path, dry_run=False, ch=Late(stale_reads=99), sleep=lambda s: None)
