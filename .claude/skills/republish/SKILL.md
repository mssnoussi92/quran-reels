---
name: republish
description: Publish a Quran Words Daily calendar slot again after the owner deleted its posts (bad cut, disliked background, rights claim) — fix the cause, reopen the slot in the state branch, then run the daily workflow or publish by hand. Use when the owner says they deleted a reel and want it back.
---

# Publish a slot again

1. **Fix the cause first**, on the branch that will publish:
   - background: remove or change it in `config/backgrounds.yaml` (comment why);
   - reciter claimed: remove it from `content.rotation` (comment who claimed, where);
   - either: a dated line in `src/quran_reels/catalog/history.yaml` (the catalogue shows it);
   - bad cut: `QURAN_REELS_RECITER=<name> quran-reels split --audit --fix <surah>`, render and
     check by recognition (test-reciter skill, step 3).
2. **Reopen the slot** on the state branch:
   ```bash
   git fetch origin state && git worktree add --detach <scratchpad>/state origin/state
   quran-reels state reopen <day>/<slot> --why "<reason>" [--claimed] \
     --state <scratchpad>/state/published.json
   git -C <scratchpad>/state -c user.name=quran-reels \
     -c user.email=41898282+github-actions[bot]@users.noreply.github.com \
     commit -am "État : <day>/<slot> rouvert (<reason>)"
   git -C <scratchpad>/state push origin HEAD:state
   ```
   The old record stays under `removed`; `--claimed` keeps the reciter out for good.
3. **Publish.**
   - Inside the slot window (3 h after 07:30 / 19:30 Paris): dispatch `daily.yml` on the ref
     with the fix, no inputs. It publishes the passage again with the rotation's choice and
     records it.
   - Outside it: the next slot of the same queue publishes it.
   - Now, by hand: `publish-test.yml` (`mode: publish`, `confirm: PUBLIER`, `platforms`,
     `reciters`), then write the new posts into the slot (results, reciter) on the state
     branch, so the rotation and the captions issue stay right.
4. **One run at a time.** `daily` and `publish-test` share the concurrency group `accounts`;
   a newer pending run cancels the older pending one. A daily run in the window retries a
   failed platform with the same reciter: cancel it if the reciter has to change.
