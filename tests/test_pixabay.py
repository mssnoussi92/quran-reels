"""Pixabay: 24-hour cache, rate limit, the key never shown, the first filter on tags."""

from datetime import UTC, datetime, timedelta

import pytest

from quran_reels.sources import pixabay
from quran_reels.sources.pixabay import Pixabay, PixabayError, ruled_out

KEY = "12345678-secret-pixabay-key"


class Resp:
    def __init__(self, status=200, body=None, text="", headers=None):
        self.status_code, self._body, self.text = status, body, text
        self.headers = headers or {"X-RateLimit-Remaining": "99"}

    def json(self):
        return self._body


class Session:
    def __init__(self, *answers):
        self.answers, self.calls, self.headers = list(answers), [], {}

    def get(self, url, params=None, timeout=None):
        self.calls.append(params)
        return self.answers.pop(0)


HIT = {"id": 7, "user": "Author", "pageURL": "https://pixabay.com/videos/id-7/",
       "tags": "mountains, clouds, nature", "duration": 20,
       "videos": {"large": {"url": "https://cdn.pixabay.com/7_large.mp4", "width": 3840,
                            "height": 2160}, "tiny": {"url": "https://cdn.pixabay.com/7_tiny.mp4"}}}


@pytest.fixture(autouse=True)
def no_wait(monkeypatch):
    monkeypatch.setattr(pixabay.time, "sleep", lambda s: None)


def test_answers_are_cached_24_hours_without_the_key(tmp_path):
    s = Session(Resp(body={"hits": [HIT]}), Resp(body={"hits": [HIT]}))
    p = Pixabay(tmp_path, KEY, session=s)
    assert p.search("mountains")[0]["id"] == 7
    assert p.search("mountains")[0]["id"] == 7
    assert len(s.calls) == 1                                  # second time: the cache
    assert s.calls[0]["category"] == "nature" and s.calls[0]["safesearch"] == "true"
    [cached] = (tmp_path / "pixabay").glob("*.json")
    assert KEY not in cached.read_text()                      # never stored either
    old = cached.read_text().replace(cached.read_text().split('"fetched": "')[1][:25],
                                     (datetime.now(UTC) - timedelta(hours=25)).isoformat(
                                         timespec="seconds"))
    cached.write_text(old)
    p.search("mountains")
    assert len(s.calls) == 2                                  # older than 24 h: asked again


def test_errors_never_show_the_key(tmp_path):
    s = Session(Resp(400, text=f"[ERROR 400] Invalid or missing API key {KEY}"))
    with pytest.raises(PixabayError) as e:
        Pixabay(tmp_path, KEY, session=s).search("sea")
    assert KEY not in str(e.value) and "HTTP 400" in str(e.value)


def test_without_a_key_nothing_is_asked(tmp_path):
    with pytest.raises(PixabayError, match="PIXABAY_API_KEY"):
        Pixabay(tmp_path, "", session=Session()).search("sea")


def test_the_file_url_comes_from_the_api_by_id(tmp_path):
    p = Pixabay(tmp_path, KEY, session=Session(Resp(body={"hits": [HIT]})))
    assert p.file_url(7) == "https://cdn.pixabay.com/7_large.mp4"


@pytest.mark.parametrize(("tags", "out"), [
    ("mountains, clouds", set()), ("sea, waves, surfer", {"surfer"}),
    ("forest, deer in the forest", {"deer"}), ("river, birds flying", {"birds"})])
def test_first_filter_on_tags(tags, out):
    assert ruled_out({"tags": tags}) == out
