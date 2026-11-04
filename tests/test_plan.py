from quran_reels.selector.plan import sentence_ends, split

KW = {"target": 60, "low": 40, "high": 90, "overhead": 1.6}


def test_sentence_ends_follow_the_translation_punctuation():
    tr = {1: "By the morning brightness", 2: "And [by] the night when it covers with darkness,",
          3: "Your Lord has not taken leave of you, [O Muḥammad], nor has He detested [you].",
          6: "Did He not find you an orphan and give [you] refuge?",
          7: 'and the disbeliever will say, "Oh, I wish that I were dust!"'}
    assert sentence_ends(tr) == {3, 6, 7}


def test_never_cut_mid_sentence_or_inside_a_tafsir_group():
    seconds = [10.0] * 12                         # 120 s: too long for one video
    ends = {2, 4, 6, 8, 10, 12}
    groups = [(1, 2), (3, 6), (7, 8), (9, 12)]    # 4 and 10 end a sentence inside a group
    parts = split(seconds, ends, groups, **KW)
    assert [(a, b) for a, b, _ in parts] == [(1, 6), (7, 12)]
    assert not any(r for *_, r in parts)


def test_passages_aim_at_about_a_minute():
    seconds = [6.0] * 40                          # 240 s, a sentence end after every ayah
    parts = split(seconds, set(range(1, 41)), [(a, a) for a in range(1, 41)], **KW)
    assert [b - a + 1 for a, b, _ in parts] == [10, 10, 10, 10]   # 4 × 61.6 s


def test_block_longer_than_a_video_is_cut_at_a_sentence_end():
    seconds = [20.0] * 6                          # one tafsir group of 120 s
    parts = split(seconds, {1, 3, 6}, [(1, 6)], **KW)
    assert [(a, b, r) for a, b, r in parts] == [(1, 3, True), (4, 6, True)]
