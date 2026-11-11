---
name: test-reciter
description: Prepare and test a reciter for Quran Words Daily (split and check the recording, owner listens, first publication on Facebook only, owner checks the rights, then Instagram), then add it to the rotation or drop it. Use when the owner asks to try, add or drop a reciter, or before a reciter's first publication.
---

# Test a reciter

Meta's check before publication is blind: Alafasy, Nabil Ar-Rifai (2:255, muted in 24
territories) and Saad Al-Ghamdi (2:255, UMG, muted in Russia) all passed it and were claimed a
few minutes after going live. So the owner checks every new reciter on Facebook first.

**Where each reciter stands: read it, do not remember it.** `content.rotation` in
`config/project.yaml` (who is chosen, with the dated comments), the state's `claimed` and the
`reciter` of its slots (`git show origin/state:published.json`), the claims in
`src/quran_reels/catalog/history.yaml`, `platforms.youtube.reciter` (the one reciter of
YouTube) and `platforms.youtube.exclude_reciters`.

**Only the owner decides a publication.** Steps 4 and 5 post for real: each needs the owner's
explicit go for that publication, after they heard the MP4 of step 3. Typing `PUBLIER` is
theirs to ask for, not yours to decide.

1. **Catalogue.** `config/project.yaml` → `content.reciters` (`surah_url` + `mp3quran` read id,
   or an EveryAyah folder) and `content.rotation.reciters` (who is chosen, per passage).
2. **Split and check** the passage, then audit its cuts (asr extra, torch CPU):
   `QURAN_REELS_RECITER=<name> quran-reels split <surah:a-b>` then
   `QURAN_REELS_RECITER=<name> quran-reels split --audit --fix <surah>`.
   Commit `config/splits/<id>/SSS.json` (times only).
   A reciter with one file per ayah (an EveryAyah folder, no `surah_url`: Fares Abbad,
   Husary) has nothing to split: the command says so. Skip this step.
3. **Render and listen by recognition** before anyone hears it:
   `QURAN_REELS_RECITER=<name> quran-reels render <passage>`, then recognise the MP4's audio
   (`quran_reels.sources.recognition.Recognizer().text`) on the basmala, 2 s after it (the
   ayah's first words) and the last 4 s (its last words, nothing of the next ayah).
   **Recognition does not hear everything**: it heard the basmala alone in a segment that
   ended with the first 0.7 s of «الم» (Tawfiq As-Sayegh, 29:60 on YouTube, 2026-11-11), and
   it let an isti'adha before a basmala pass (his 78). So also read the recording itself:
   `Sources.from_config(cfg).audio.basmala_problem(<surah>)` must be empty (the render
   refuses the cut otherwise), and look at the loudness of the first seconds of the MP4:
   after the basmala, a stop, then the ayah, nothing between. A duration and a frame are not
   a check of the sound. Send the MP4 to the owner with SendUserFile and wait for their
   answer.
4. **Facebook only**, on the owner's go: `publish-test.yml` on the branch that has the split,
   inputs `{passage, mode: publish, platforms: facebook, confirm: PUBLIER, reciters: <name>}`.
5. **The owner checks** Facebook's copyright page a few minutes later.
   - Clean, and the owner says so: the same with `platforms: instagram` (same render: same
     reel).
   - Claimed: the owner deletes it; remove the reciter from `content.rotation` with a comment
     (who claimed, where), add a `claim` line for it in `src/quran_reels/catalog/history.yaml`
     (shown by the catalogue), update the Récitateurs row of CLAUDE.md.
6. **YouTube** (by hand, Content ID, not Meta's): nothing to test for a new reciter of the
   rotation. YouTube always takes Tawfiq As-Sayegh (`platforms.youtube.reciter`, owner's
   choice, 2026-11-11): a reel by anyone else gets its YouTube version by him
   (`daily.youtube_version`), and a new reciter never goes there. Only if the owner changes
   YouTube's reciter: they upload his first Short as private and look at the claims before
   making it public; claimed there, he cannot be YouTube's reciter (a line in
   `catalog/history.yaml`, and `platforms.youtube.exclude_reciters`, the rule used when
   `reciter` is unset).
7. **A test that stands in for a calendar slot** is recorded with `quran-reels state record`
   (republish skill, step 3, by hand), after each publication: Facebook, then Instagram. The
   slot is marked `by_hand`, so the daily run does not post Instagram or TikTok with this
   reciter before the owner has looked at the rights. A test outside the calendar (a passage
   the queues do not hold next) is not recorded.
8. **Into the rotation: the owner's decision**, once Facebook and Instagram are clean (or at
   once on their word, as for Fares Abbad). In a PR the owner merges: the reciter's id in
   `content.rotation.reciters` with a dated comment (asked by whom, tested on which reel),
   its splits committed, the Récitateurs row and the reciters list of CLAUDE.md. Then
   `quran-reels split --upcoming 8 --state <checkout>/published.json` (or the prepare
   workflow) shows it ready for the coming passages, and `quran-reels calendar --days 7`
   where it is chosen.

Limits: Facebook Reels 3–90 s (18:1-10 fits only with Budair, 87.6 s); Omar Hisham's
recordings over 15 min are not split (`split_max_minutes`).
