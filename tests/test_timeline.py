from quran_reels.render.video import SAMPLE_RATE, build_timeline


def test_frames_follow_the_recitation():
    # 93:1-3 with Alafasy: 1.801 s, 2.970 s, 4.357 s
    samples = [round(s * SAMPLE_RATE) for s in (1.801, 2.970, 4.357)]
    tl = build_timeline(samples, fps=30, lead=0.4, tail=1.2)
    counts = tl.frame_counts()
    assert sum(counts) == tl.total_frames
    # the second image appears when the second ayah starts, to the frame
    assert counts[0] == round((0.4 + 1.801) * 30)
    assert abs(tl.starts()[1] - 2.201) < 1e-3
    # audio and video end together: whole frames of audio
    assert tl.total_frames * tl.samples_per_frame >= tl.lead_samples + sum(samples)
    assert abs(tl.seconds - (0.4 + sum((1.801, 2.970, 4.357)) + 1.2)) < 1 / 30
