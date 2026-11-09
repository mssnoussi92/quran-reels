---
name: republish
description: Publish a Quran Words Daily calendar slot again after the owner deleted its posts (bad cut, disliked background, rights claim) — fix the cause on main, reopen the slot in the state branch, then run the daily workflow or publish by hand and record it. Use when the owner says they deleted a reel and want it back, and to record any publication made by hand in the state.
---

# Publish a slot again

Reopening a slot acts at once and for every platform: the next daily run on `main` posts its
passage everywhere, with whatever `main` holds. Two ways to post twice follow from that; the
steps below close them.

0. **Ask, then look.**
   - Which platforms did the owner delete, and why? A reel still online somewhere would be
     posted there a second time: reopen only when it is gone everywhere, or publish by hand on
     the platforms that lost it (step 3, by hand).
   - No run of the `accounts` group queued or running (`actions_list` → `list_workflow_runs`
     on daily.yml, publish-test.yml, on-demand.yml, images.yml): a run that read
     the state before your push writes its own answer after it.
1. **Fix the cause, on `main`, before reopening** (a PR the owner merges; never merge it
   yourself). The scheduler's next run is on `main`: a fix left on a branch is not used and the
   same reel goes out again.
   - background: remove or change it in `config/backgrounds.yaml` (comment why);
   - reciter claimed: remove it from `content.rotation` (comment who claimed, where);
   - either: a dated line in `src/quran_reels/catalog/history.yaml` (the catalogue shows it);
   - bad cut: `QURAN_REELS_RECITER=<name> quran-reels split --audit --fix <surah>`, render and
     check by recognition (test-reciter skill, step 3).
2. **Reopen the slot** on the state branch, saved with the script every workflow uses (it
   replays your commit if the branch moved; never `git push --force` this branch):
   ```bash
   git fetch origin state && git worktree add --detach <scratchpad>/state origin/state
   quran-reels state reopen <day>/<slot> --why "<reason>" [--claimed] \
     --state <scratchpad>/state/published.json
   (cd <scratchpad>/state && bash <repo>/.github/scripts/save-state.sh \
     "État : <day>/<slot> rouvert" published.json)
   ```
   The old record stays under `removed`; `--claimed` keeps the reciter out for good.
3. **Publish.**
   - Inside the slot window (3 h after 07:30 / 19:30 Paris): dispatch `daily.yml` on `main`,
     no inputs. It publishes the passage on every platform with the rotation's choice and
     records it.
   - Outside it: nothing to do, the next slot of the same queue publishes it.
   - By hand (some platforms only, or a given reciter), **on the owner's explicit go for this
     publication**: `publish-test.yml` (`mode: publish`, `confirm: PUBLIER`, `platforms`,
     `reciters`), then record it from the run's artifact:
     ```bash
     quran-reels state record <day>/<slot> --publish <reciter>/<passage>/publish.json \
       --reciter <id> --state <scratchpad>/state/published.json
     (cd <scratchpad>/state && bash <repo>/.github/scripts/save-state.sh \
       "État : <day>/<slot> publié à la main" published.json)
     ```
     `state record` writes the slot **and** puts its passage back as done in its queue. Never
     edit `published.json` by hand instead: with the slot alone, the passage stays first in
     its queue and the next slot publishes it again. The slot is marked `by_hand`: the daily
     run does not add the platforms you left out.
4. **Read the state back**: `git fetch origin state && git show origin/state:published.json`
   → the slot's results, its item in `queues.<queue>.done`; `quran-reels calendar --days 3
   --state <checkout>/published.json` must not show the passage again.
5. **One run at a time.** daily, images, publish-test, tiktok-auth and on-demand's
   publication share the concurrency group `accounts` (prepare has its own); a newer pending run cancels the older
   pending one. A daily run in the window retries a failed platform with the same reciter:
   cancel it if the reciter has to change.
