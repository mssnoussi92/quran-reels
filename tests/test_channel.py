"""The YouTube channel's keywords and description, applied once (channel.py). No network."""

from pathlib import Path

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
