---
name: check-publication
description: Check a Quran Words Daily publication run (daily.yml, images.yml, prepare.yml, publish-test.yml or on-demand.yml) and report to the owner. Use when a scheduled check fires, when the owner asks whether a post went out, or after dispatching a workflow.
---

# Check a publication

GitHub's cron is not reliable in this repo: the runs that count come from `workflow_dispatch`
(the scheduler session « Quran Words Daily – planificateur », or a person). Since 2026-11-05
GitHub also starts some `schedule` runs, 6 to 8 hours late: a daily one finds nothing due and
ends in 20 s, which is not a missed slot. Read, don't guess.

While `config/schedule.yaml` has a `pause` covering today (no `until`, or `until` not past),
a daily run prints « paused … nothing published » and ends green: the reels are paused on the
owner's word, nothing is missing. Report it in one line (« en pause, rien publié, comme
prévu »), never as a failure, and never dispatch daily.yml again or reopen a slot to make it
publish. Only the owner ends the pause (`until`, docs/calendrier.md).

A slot outside its days (`days` of a slot in `config/schedule.yaml`) is not due either: since
2026-11-14 there is a reel every morning and the evening slot publishes on Sundays only (the
theme series; owner's choice, 2026-11-13). An evening run on any other day finds « nothing
due »: normal, say so in one line, never as a failure.

1. **Find the run.** GitHub MCP `actions_list`, method `list_workflow_runs`, `resource_id` the
   workflow file, `perPage` 3. Note `head_branch`, `status`, `conclusion`, `created_at`.
2. **Still running?** `list_workflow_jobs` gives the steps. "Install ffmpeg and Chromium" takes
   seconds (static ffmpeg, no apt); a step stuck for more than 10 min is worth reporting. Never
   cancel a run that is publishing unless the owner asks or it would post something wrong.
3. **Read the outcome.**
   - daily: `git fetch origin state && git show origin/state:published.json`, then
     `slots["<day>/<slot>"]` (queue, item, passage, reciter, results per platform: status, id,
     url, error). A slot taken down after a claim stays there with `claimed`; a reopened
     one is under `removed`; one published by hand has `by_hand` (`state record`); a slot no
     run took is under `missed`.
   - images: `images.json` on the state branch.
   - on-demand: the request issue's comments (preview, result) and `on_demand["<issue>"]` in
     `published.json` (results per platform, `youtube`: `manual` then `published`). Never post
     `/publier` yourself: the GitHub tools act as the owner, and only the owner approves.
   - publish-test: the run artifact (`actions_get` `download_workflow_run_artifact`, unzip in
     the scratchpad with `python3 -I`), file `<reciter>/<passage>/publish.json`.
   - errors: `get_job_logs` (`job_id`, `return_content`, `tail_lines` ≈ 120). The last lines are
     cleanup; the publish lines come before.
4. **Known failures.**
   - Instagram `ProcessingFailedError` / container still `IN_PROGRESS`: Instagram flakiness;
     the run tries that platform once more itself, 180 s later (log line « did not get the
     reel, tried again »); still failed, a daily run inside the slot window retries only that
     platform, same passage and reciter.
   - « save-state: … not saved » on the step that saves the state: the slot is not on the
     state branch. Do not dispatch `daily.yml` again (it would post the passage twice): tell
     the owner, with the run link.
   - status `blocked`: Meta's check refused the reel; not retried, change the reciter.
   - Meta token: follow docs/plateformes.md (renew `META_PAGE_TOKEN`).
   - conclusion `cancelled` with no job: a newer pending run of the `accounts` group replaced
     it (daily, images, publish-test, tiktok-auth, on-demand's publication share
     it; prepare has its own). Dispatch it again once the group is free, inside the window.
   - prepare prints « NO RECITER READY » for a passage: that slot would publish nothing. Say
     which passage and day; the fix is a split (test-reciter, step 2) or another reciter.
   - prepare ends green with the warning « youtube reciter not ready » (run annotations, or
     the log of « Split and check the coming week »): YouTube always takes Tawfiq As-Sayegh
     (`platforms.youtube.reciter`), so these passages would get nothing for YouTube. Tell the
     owner which passages and days; the fix is his split
     (`QURAN_REELS_RECITER=sayegh quran-reels split --audit --fix <surah>`, test-reciter step 2).
   - daily log « the basmala of surah N is cut wrong (… recited after a stop …); another
     reciter is chosen », or the captions issue says « découpe refusée » for YouTube: the
     render read on the recording that this reciter's basmala holds a stop (the start of
     ayah 1 after it, or an isti'adha before it), which recognition had let pass. Nothing was
     published with it. The nightly prepare cuts it again; if the same line comes back the
     next day, say so: `QURAN_REELS_RECITER=<name> quran-reels split --audit --fix <surah>`.
   - daily: the captions issue says « YouTube : rien pour ce créneau » and the slot has
     `youtube: {reciter: null, error}`: Tawfiq was not ready for that passage. The reel of the
     day must not go to YouTube in his place; report the reason given.
   - TikTok « could not be kept »: `GH_SECRETS_TOKEN` is missing or expired, the new refresh
     token was not saved. The owner makes a new token (docs/plateformes.md), then signs in
     again (tiktok-auth workflow) if the next run fails on the refresh.
   - issue « ⏰ Créneau jamais tenté »: no run took that slot. Look at the scheduler session's
     tasks and at GitHub's status that day; its passage goes out at the queue's next slot.
   - "does not exist" (code 100, subcode 33) right after a Facebook publish: the reel may be
     live; check `facebook.com/plugins/video.php?href=…/reel/<id>/` logged out (hd_src present).
5. **Nothing ran for a due slot** (scheduler down): dispatch `daily.yml` on `main`, no inputs,
   while the window is open (3 h after 07:30 / 19:30 Paris). Publish nothing else on your own.
6. **Report in French, short:** passage, reciter, link per platform, the TikTok draft waiting
   in the inbox (caption in the pinned issue « 📋 Légendes à copier »), the YouTube file
   (always recited by Tawfiq As-Sayegh: the same MP4 when the reel is his, else
   `youtube/<passage>.mp4`, the slot's `youtube`; its direct link and YouTube page are in the
   captions issue entry; or none for this slot, see step 4), what
   the owner should do. For a reciter's first publication, remind them to look at Facebook's copyright page
   (« Mises en application des droits d'auteur ») a few minutes after.
