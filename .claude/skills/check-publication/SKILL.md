---
name: check-publication
description: Check a Quran Words Daily publication run (daily.yml, images.yml, prepare.yml or publish-test.yml) and report to the owner. Use when a scheduled check fires, when the owner asks whether a post went out, or after dispatching a workflow.
---

# Check a publication

GitHub's cron never fires in this repo: runs come from `workflow_dispatch` (the scheduler
session « Quran Words Daily – planificateur », or a person). Read, don't guess.

1. **Find the run.** GitHub MCP `actions_list`, method `list_workflow_runs`, `resource_id` the
   workflow file, `perPage` 3. Note `head_branch`, `status`, `conclusion`, `created_at`.
2. **Still running?** `list_workflow_jobs` gives the steps. "Install ffmpeg and Chromium" takes
   seconds (static ffmpeg, no apt); a step stuck for more than 10 min is worth reporting. Never
   cancel a run that is publishing unless the owner asks or it would post something wrong.
3. **Read the outcome.**
   - daily: `git fetch origin state && git show origin/state:published.json`, then
     `slots["<day>/<slot>"]` (queue, item, passage, reciter, results per platform: status, id,
     url, error). A slot taken down or reopened is under `removed`.
   - images: `images.json` on the state branch.
   - publish-test: the run artifact (`actions_get` `download_workflow_run_artifact`, unzip in
     the scratchpad with `python3 -I`), file `<reciter>/<passage>/publish.json`.
   - errors: `get_job_logs` (`job_id`, `return_content`, `tail_lines` ≈ 120). The last lines are
     cleanup; the publish lines come before.
4. **Known failures.**
   - Instagram `ProcessingFailedError` / container still `IN_PROGRESS`: Instagram flakiness;
     a daily run inside the slot window retries only that platform, same passage and reciter.
   - status `blocked`: Meta's check refused the reel; not retried, change the reciter.
   - Meta token: follow docs/plateformes.md (renew `META_PAGE_TOKEN`).
   - "does not exist" (code 100, subcode 33) right after a Facebook publish: the reel may be
     live; check `facebook.com/plugins/video.php?href=…/reel/<id>/` logged out (hd_src present).
5. **Nothing ran for a due slot** (scheduler down): dispatch `daily.yml` on `main`, no inputs,
   while the window is open (3 h after 07:30 / 19:30 Paris). Publish nothing else on your own.
6. **Report in French, short:** passage, reciter, link per platform, the TikTok draft waiting
   in the inbox (caption in the pinned issue « 📋 Légendes à copier »), what the owner should
   do. For a reciter's first publication, remind them to look at Facebook's copyright page
   (« Mises en application des droits d'auteur ») a few minutes after.
