"""Image posts: rules, order, exclusions, due slots, caption, publishing (no network)."""

from datetime import UTC, date, datetime
from types import SimpleNamespace

import yaml

from quran_reels.images import caption as caption_mod
from quran_reels.images import daily as images_daily
from quran_reels.images.candidates import (
    Candidate,
    entry_positions,
    sentence_context,
    whole_gloss,
)
from quran_reels.images.cards import Content
from quran_reels.images.publish import ImagePublisher
from quran_reels.images.select import (
    ImageState,
    next_candidate,
    parse_exclusions,
    rank,
    upcoming,
)
from quran_reels.models import AyahRef, GlossEntry, PublishStatus

# ---- rules 1-3 ---------------------------------------------------------------------------

def test_the_gloss_is_whole_or_left_out():
    assert whole_gloss("ما أبْغَضك.", 170) == "ما أبْغَضك."
    assert whole_gloss("إذا سكَن.\nوذلك عند تناهي ظلامه.", 170) == "إذا سكَن. وذلك عند تناهي ظلامه."
    assert whole_gloss("كلام بلا نهاية", 170) is None                 # not a whole sentence
    assert whole_gloss("كلمة. " * 40, 170) is None                    # never shortened


def test_the_verse_image_shows_a_whole_sentence():
    ends = {3, 5, 8, 11}                       # 93: oath in 1-2, sentence ends at 3
    assert sentence_context(3, ends, 11) == (1, 3)
    assert sentence_context(4, ends, 11) == (4, 5)
    assert sentence_context(11, ends, 11) == (9, 11)
    assert sentence_context(9, set(), 11) == (1, 11)   # no end at all: the whole surah


def test_one_or_two_words_anchored_as_the_reels_do():
    tokens = ["وَٱلَّيۡلِ", "إِذَا", "سَجَىٰ"]
    entries = [GlossEntry(AyahRef(93, 2), "واللَّيلِ إذا سَجَى", "إذا سكَن.", "e")]
    assert entry_positions(AyahRef(93, 2), entries, tokens, []) == {0: (0, 1, 2)}   # 3 words
    assert entry_positions(AyahRef(93, 2), entries, tokens, [("سجى",)]) == {0: (2,)}


def test_candidate_rows_round_trip():
    c = Candidate("93:3#0", "word", 93, (1, 3), 3, 0, (4,))
    assert Candidate.from_row("word", c.row()) == c
    a = Candidate("2:255-255", "ayah", 2, (255, 255))
    assert Candidate.from_row("ayah", a.row()) == a


# ---- rules 5-6 ---------------------------------------------------------------------------

def test_exclusions_keep_unquoted_references_as_text():
    raw = yaml.load("exclude: [9, 2:55, 2:1-5]", Loader=yaml.BaseLoader)["exclude"]
    ex = parse_exclusions(raw)
    assert ex.surahs == {9} and (2, 55, 55) in ex.ranges and (2, 1, 5) in ex.ranges
    assert ex.excludes(Candidate("2:4#0", "word", 2, (4, 4), 4))
    assert ex.excludes(Candidate("2:56#0", "word", 2, (54, 56), 56))      # 2:55 on the image
    assert not ex.excludes(Candidate("2:6#0", "word", 2, (6, 7), 6))


def cands(*specs):
    return [Candidate(f"{s}:{a}#0", "word", s, (a, a), a, 0, (0,)) for s, a in specs]


def test_order_is_stable_and_never_repeats_before_the_end():
    pool = cands((93, 3), (94, 1), (95, 4), (96, 2), (97, 1))
    picks = upcoming(pool, ImageState(), "word", "seed", parse_exclusions([]),
                     date(2026, 11, 6), 5)
    assert sorted(c.id for _, c in picks) == sorted(c.id for c in pool)
    again = upcoming(list(reversed(pool)), ImageState(), "word", "seed", parse_exclusions([]),
                     date(2026, 11, 6), 5)
    assert [c.id for _, c in picks] == [c.id for _, c in again]          # order of the file
    assert rank("seed", 1, "93:3#0") != rank("seed", 2, "93:3#0")         # new round, new order


def test_yesterdays_surah_waits_when_another_is_available():
    pool = cands((2, 1), (2, 2), (2, 3), (3, 1))
    state = ImageState()
    state.set_post("word", date(2026, 11, 5), {"id": "x", "surah": 2})
    c = next_candidate(pool, state, "word", "s", parse_exclusions([]), date(2026, 11, 6))
    assert c.surah == 3                                  # the only other surah, whatever rank
    only_two = cands((2, 1))
    assert next_candidate(only_two, state, "word", "s", parse_exclusions([]),
                          date(2026, 11, 6)).surah == 2  # nothing else left: no gap day


def test_a_new_round_starts_when_all_are_done():
    pool = cands((93, 3), (94, 1))
    state = ImageState()
    for c in pool:
        state.mark_done("word", c)
    c = next_candidate(pool, state, "word", "s", parse_exclusions([]), date(2026, 11, 6))
    assert c is not None and state.kind("word")["round"] == 2 and state.kind("word")["done"] == []


def test_upcoming_leaves_the_state_alone():
    state = ImageState()
    upcoming(cands((93, 3)), state, "word", "s", parse_exclusions([]), date(2026, 11, 6), 3)
    assert state.data == {}


# ---- due slots ---------------------------------------------------------------------------

def test_only_enabled_formats_are_due_in_their_window(monkeypatch):
    monkeypatch.setattr(images_daily, "settings", lambda cfg: {
        "window_hours": 6, "platforms": ["facebook", "instagram"],
        "formats": {"word": {"enabled": True, "time_utc": "11:30"},
                    "ayah": {"enabled": False, "time_utc": "11:30"}}})
    def at(h, m):
        return datetime(2026, 11, 6, h, m, tzinfo=UTC)
    assert images_daily.due_formats(None, ImageState(), at(11, 0)) == []
    assert images_daily.due_formats(None, ImageState(), at(11, 41)) == [
        ("word", date(2026, 11, 6), ["facebook", "instagram"])]
    assert images_daily.due_formats(None, ImageState(), at(17, 41)) == []      # window over
    state = ImageState()
    state.set_post("word", date(2026, 11, 6), {"id": "x", "surah": 1, "results": {
        "facebook": {"status": "published"}, "instagram": {"status": "failed"}}})
    assert images_daily.due_formats(None, state, at(12, 41)) == [
        ("word", date(2026, 11, 6), ["instagram"])]                          # retry IG only


# ---- caption -----------------------------------------------------------------------------

def content():
    return Content(93, "الضحى", "Ad-Duhaa", "93:3", (1, 3), {}, {}, {}, word="قَلَىٰ",
                   gloss="ما أبْغَضك.")


def test_caption_follows_the_template_and_instagram_keeps_five_tags():
    cfg = SimpleNamespace(content={"translation": {"label": "Sahih International"},
                                   "glosses": {"label": "التفسير الميسر",
                                               "label_en": "Tafsir al-Muyassar, King Fahd Complex"}})
    settings = {"hashtags": {"before": ["#Quran", "#ArabicWords", "#QuranWordsDaily"],
                             "after": ["#القرآن_الكريم"]}}
    body = caption_mod.caption(cfg, "word", content())
    tags = caption_mod.hashtags(settings, content())
    assert caption_mod.text(body, tags, None) == (
        "Word of the day: قَلَىٰ\nSurah Ad-Duhaa 93:3\n\nTranslation: Sahih International\n"
        "Meaning: Tafsir al-Muyassar, King Fahd Complex\n\n"
        "#Quran #ArabicWords #QuranWordsDaily #SurahAdDuhaa #سورة_الضحى #القرآن_الكريم\n")
    assert caption_mod.text(body, tags, 5).rstrip().endswith("#سورة_الضحى")


# ---- publishing --------------------------------------------------------------------------

class FakeGraph:
    def __init__(self):
        self.calls = []
        self.n = 0

    def _id(self):
        self.n += 1
        return str(self.n)

    def post_file(self, path, field, file, **data):
        self.calls.append(("photo", path, file.name, data))
        return {"id": f"photo{self._id()}"}

    def get(self, path, **params):
        self.calls.append(("get", path, params.get("fields")))
        if params.get("fields") == "images":
            return {"images": [{"width": 720, "source": "small"},
                               {"width": 1080, "source": f"https://cdn/{path}.jpg"}]}
        if params.get("fields") == "status_code,status":
            return {"status_code": "FINISHED"}
        if path.endswith("content_publishing_limit"):
            return {"data": [{"quota_usage": 1, "config": {"quota_total": 50}}]}
        return {"permalink_url": "/p", "permalink": "https://ig/p"}

    def post(self, path, **data):
        self.calls.append(("post", path, data))
        return {"id": f"{path.split('/')[-1]}{self._id()}"}

    def delete(self, path):
        self.calls.append(("delete", path))
        return {"success": True}


def test_carousel_and_multi_photo_post_in_order(tmp_path):
    files = [tmp_path / f"{n}.jpg" for n in (1, 2, 3)]
    for f in files:
        f.write_bytes(b"jpg")
    g = FakeGraph()
    results = ImagePublisher(g, "page", "ig", poll_interval=0).publish(
        files, {"facebook": "fb text", "instagram": "ig text"}, ["facebook", "instagram"])
    assert [r.status for r in results] == [PublishStatus.PUBLISHED, PublishStatus.PUBLISHED]
    photos = [c for c in g.calls if c[0] == "photo"]
    assert [c[2] for c in photos] == ["1.jpg", "2.jpg", "3.jpg"]
    assert all(c[3] == {"published": "false"} for c in photos)
    media = [c[2] for c in g.calls if c[0] == "post" and c[1] == "ig/media"]
    assert [m.get("image_url") for m in media[:3]] == [
        "https://cdn/photo1.jpg", "https://cdn/photo2.jpg", "https://cdn/photo3.jpg"]
    assert media[3]["media_type"] == "CAROUSEL" and media[3]["caption"] == "ig text"
    assert media[3]["children"] == "media4,media5,media6"
    [feed] = [c[2] for c in g.calls if c[0] == "post" and c[1] == "page/feed"]
    assert feed["message"] == "fb text"
    assert [feed[f"attached_media[{i}]"] for i in range(3)] == [
        '{"media_fbid": "photo1"}', '{"media_fbid": "photo2"}', '{"media_fbid": "photo3"}']
    assert not [c for c in g.calls if c[0] == "delete"]


def test_dry_run_publishes_nothing_and_deletes_the_photos(tmp_path):
    f = tmp_path / "1.jpg"
    f.write_bytes(b"jpg")
    g = FakeGraph()
    results = ImagePublisher(g, "page", "ig", poll_interval=0).publish(
        [f, f, f], {"facebook": "a", "instagram": "b"}, ["facebook", "instagram"], dry_run=True)
    assert [r.status for r in results] == [PublishStatus.DRAFT, PublishStatus.READY]
    assert not [c for c in g.calls if c[0] == "post" and c[1] in ("ig/media_publish", "page/feed")]
    assert len([c for c in g.calls if c[0] == "delete"]) == 3
