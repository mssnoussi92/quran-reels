---
name: weekly-review
description: The review of the Page for the owner of Quran Words Daily (his « revue », weekly, on Sunday) - read the statistics (insights.json on the state branch, the catalogue's « Statistiques » page), both calendars (reels of quran-reels, theme videos of quran-themes-demo), the theme stock and every point left for this review in docs/insights.md (a trial to judge, a question to ask), ask for the TikTok screenshots (recorded with the skill record-stats), and propose one to three changes for the next two weeks, each with its evidence and how sure it is. Use when the weekly scheduled task fires, and whenever the owner says, in any session and in any words, « on commence la revue », « la revue (du dimanche, de la semaine) », « on fait le point », « fais le point sur les chiffres », « qu'est-ce que disent les stats », or asks what the numbers say; screenshots sent on their own go to the skill record-stats.
---

# Weekly review (Sunday)

## When the owner asks for it

Owner's request, 2026-11-17: every session must know what to do when he says « on commence la revue (dimanche) »,
« on fait le point », « la revue de la semaine » or anything like it, in quran-reels, quran-themes-demo or the planner.

- **Now, with him** (he says it on the day, or « maintenant », « vas-y »): do the review below in this conversation.
  Give him the findings in the chat, short, and each decision as a choice question (CLAUDE.md, « Les questions,
  toujours à choix »), one at a time where one depends on another; then write the issue (step 6) as the record.
- **For a day to come** (« dimanche », « on fait le point dimanche »): the scheduled task « Revue de la semaine
  (Quran Words Daily) » does it every Sunday at 09:23 Paris (`list_triggers`) and writes the issue; check it is
  enabled, and write what this review must look at in docs/insights.md (« À la revue du <date> », a PR he merges),
  since that is what the task reads. Say so in one line. If he wants it with him instead, it is the case above.
- **Unclear which** (« on commence la revue » on a weekday): ask, with a choice question: « Maintenant
  (Recommandé) » or « Dimanche à 09:23, la revue automatique ».
- From a quran-themes-demo session: this file is
  https://raw.githubusercontent.com/mssnoussi92/quran-reels/main/.claude/skills/weekly-review/SKILL.md (that
  repository's skill `weekly-review` points here); attach quran-reels with `add_repo` when its tools are needed.

## The review

The owner decides; the review proposes. Nothing here publishes, changes a calendar or a file on
`main` by itself: a change the owner accepts goes through the usual way (a PR in quran-reels,
`docs/retention/calendar.md` in quran-themes-demo with his word). Read docs/insights.md first.

0. **What this review must look at.** In docs/insights.md, every section « À regarder à la prochaine revue » and
   « À la revue du <date> » that is not done yet (a trial to judge, a question to ask the owner): each one gets its
   answer in the review, with its numbers. Once answered, a PR moves it to what was decided.
1. **Read the numbers.** `git fetch origin state && git show origin/state:insights.json`, and
   the page https://mssnoussi92.github.io/quran-reels/catalog/stats.html. Check `updated` (less
   than 36 h old), the last run (`stopped`, `errors`): a relevé that did not run is said first,
   with the run link (workflow `insights`).
2. **Read both calendars.** `quran-reels calendar --days 21 --state <state checkout>` (reels),
   `docs/retention/calendar.md` of quran-themes-demo (themes: what is published, struck; what is
   « à faire »). Note the **stock**: the first day without a theme video, three weeks ahead.
3. **Screenshots (TikTok).** Facebook, Instagram and YouTube are read every night; TikTok only
   through the owner's screenshots. Ask for the list « Contenu » of TikTok Studio (and a video's
   own page when one matters); when they come, follow the skill `record-stats` (read, show, ask,
   save, check). The owner may send them any day, in any session: the same skill.
4. **What the data says.** Compare kinds at 48 h (medians, n). Below 3 videos or 12 points,
   say « pas encore de différence » — never a conclusion from noise. Look for: the hook (first
   frame), the share of the video watched, shares and saves, follows; the film against its
   shorts on Facebook; the series against the stories; whether the Word of the day takes reach
   from the videos (three posts a day). The day and the kind of video go together in the grid:
   say so when it matters.
5. **Propose one to three changes**, each: what, why (the numbers, with n), how sure, what it
   costs, and what would make us change our mind. Contradict the owner where the evidence points
   elsewhere (CLAUDE.md). « Ne rien changer cette semaine » is a valid proposal.
6. **Write it up**: an issue « 📊 Revue de la semaine du <date> » in quran-reels (label none), in
   French, short: état (relevé, stock), ce que disent les chiffres, propositions, questions au
   propriétaire. End with the link to the statistics page. The scheduled task's answer (a push
   notification) is three lines and the issue link.
