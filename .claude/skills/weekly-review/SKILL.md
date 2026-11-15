---
name: weekly-review
description: Sunday review of the Page for the owner of Quran Words Daily - read the statistics (insights.json on the state branch, the catalogue's « Statistiques » page), both calendars (reels of quran-reels, theme videos of quran-themes-demo), the theme stock, record the YouTube and TikTok screenshots the owner sends, and propose one to three changes for the next two weeks, each with its evidence and how sure it is. Use when the weekly scheduled task fires, when the owner sends statistics screenshots, or when the owner asks what the numbers say.
---

# Weekly review (Sunday)

The owner decides; the review proposes. Nothing here publishes, changes a calendar or a file on
`main` by itself: a change the owner accepts goes through the usual way (a PR in quran-reels,
`docs/retention/calendar.md` in quran-themes-demo with his word). Read docs/insights.md first.

1. **Read the numbers.** `git fetch origin state && git show origin/state:insights.json`, and
   the page https://mssnoussi92.github.io/quran-reels/catalog/stats.html. Check `updated` (less
   than 36 h old), the last run (`stopped`, `errors`): a relevé that did not run is said first,
   with the run link (workflow `insights`).
2. **Read both calendars.** `quran-reels calendar --days 21 --state <state checkout>` (reels),
   `docs/retention/calendar.md` of quran-themes-demo (themes: what is published, struck; what is
   « à faire »). Note the **stock**: the first day without a theme video, three weeks ahead.
3. **Screenshots (YouTube, TikTok).** When the owner sends some: read each number on the image,
   write them back to him in a short table (video, platform, views, hook, average watched,
   shares, follows) and ask « je les enregistre ? ». On his yes, dispatch `insights.yml` on
   `main` with input `manual` (JSON list, docs/insights.md); never a number that is not on the
   image. Check the next catalogue build shows them.
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
