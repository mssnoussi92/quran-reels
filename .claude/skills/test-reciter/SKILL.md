---
name: test-reciter
description: Prepare and test a reciter for Quran Words Daily (split and check the recording, owner listens, first publication on Facebook only, owner checks the rights, then Instagram), or add or remove one in the rotation. Use when the owner asks to try, add or drop a reciter, or before a reciter's first publication.
---

# Test a reciter

Meta's check before publication is blind: Alafasy, Nabil Ar-Rifai (2:255, muted in 24
territories) and Saad Al-Ghamdi (2:255, UMG, muted in Russia) all passed it and were claimed a
few minutes after going live. So the owner checks every new reciter on Facebook first.

| Result so far | Reciters |
|---|---|
| no claim | Omar Hisham (114), Salah Budair (2:255) |
| claimed, removed | Alafasy, Nabil Ar-Rifai, Saad Al-Ghamdi |
| not published yet | check `content.rotation` and the state's reciters |

1. **Catalogue.** `config/project.yaml` → `content.reciters` (`surah_url` + `mp3quran` read id,
   or an EveryAyah folder) and `content.rotation.reciters` (who is chosen, per passage).
2. **Split and check** the passage, then audit its cuts (asr extra, torch CPU):
   `QURAN_REELS_RECITER=<name> quran-reels split <surah:a-b>` then
   `QURAN_REELS_RECITER=<name> quran-reels split --audit --fix <surah>`.
   Commit `config/splits/<id>/SSS.json` (times only).
3. **Render and listen by recognition** before anyone hears it:
   `QURAN_REELS_RECITER=<name> quran-reels render <passage>`, then recognise the MP4's audio
   (`quran_reels.sources.recognition.Recognizer().text`) on the basmala, 2 s after it (the
   ayah's first words) and the last 4 s (its last words, nothing of the next ayah). Send the
   MP4 to the owner with SendUserFile.
4. **Facebook only:** `publish-test.yml` on the branch that has the split, inputs
   `{passage, mode: publish, platforms: facebook, confirm: PUBLIER, reciters: <name>}`.
5. **The owner checks** Facebook's copyright page a few minutes later.
   - Clean: the same with `platforms: instagram` (same render: same reel).
   - Claimed: the owner deletes it; remove the reciter from `content.rotation` with a comment
     (who claimed, where), add a `claim` line for it in `src/quran_reels/catalog/history.yaml`
     (shown by the catalogue), update the Récitateurs row of CLAUDE.md and this table.
6. A test that stands in for a calendar slot: record it in the state (republish skill).

Limits: Facebook Reels 3–90 s (18:1-10 fits only with Budair, 87.6 s); Omar Hisham's
recordings over 15 min are not split (`split_max_minutes`).
