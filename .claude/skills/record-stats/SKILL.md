---
name: record-stats
description: Record the statistics screenshots the owner of Quran Words Daily sends (TikTok Studio above all; a YouTube Studio page for what the API does not give) on the Page's « Statistiques » page, from any session - identify each video (a reel by its passage, a theme video by its id or title), read every number on the image and only those, show them to the owner and ask before saving, then dispatch the insights workflow of quran-reels with the input `manual` and check the page. Use whenever the owner sends a screenshot of statistics or numbers of a video, in any session (quran-reels, quran-themes-demo, the planner), and for the TikTok part of the Sunday review.
---

# Record statistics screenshots

Owner's request, 2026-11-15: « que je puisse envoyer les captures TikTok dans n'importe quelle
session ». Facebook, Instagram and YouTube are read every night by the workflow `insights`
(docs/insights.md); **TikTok has no API for us: its numbers exist only through these
screenshots**. They all go to one place, `insights.json` on the branch `state` of quran-reels,
shown on https://mssnoussi92.github.io/quran-reels/catalog/stats.html beside the same video on
the other platforms. Never a second copy elsewhere (a sheet, a doc).

Rules that never bend:
- **Only what is on the image.** A number not shown is not written, never estimated (not from a
  curve, not from another platform). « 1,2 K » is written 1200 with the source « capture
  (arrondi) ».
- **Nothing is saved before the owner's yes** to the table of what was read.
- Reading statistics changes nothing on the accounts; the workflow only writes `insights.json`.

## 1. Which video is each line

From the screenshot: the first words of the caption, the cover, the date TikTok shows (the day the
owner published the draft, which can be later than the slot: never identify by the date alone).

| Video | `video` | How to find it |
| --- | --- | --- |
| Reel of the calendar | its passage as the calendar writes it: `107:1-7`, a single ayah `9:51-51` | the reference in the caption (`(107:1-7)`; for a series, on the line after the series name); else the page « À publier » (https://mssnoussi92.github.io/quran-reels/publier.html: each video's TikTok text) or `published.json` on `state` (`slots`, passage by day) |
| Theme video (quran-themes-demo) | `<doc>/<part>`: `moussa-khidr/short-2`, `dua/film`, `dua-9x16/film` | the caption's first line is the video's English title, the heading of its section in `docs/retention/publication-<doc>.md` of quran-themes-demo; the day in `docs/retention/calendar.md` |
| Reel published by hand | `93:1-11` | its reference |

When a line cannot be tied to one video with certainty, ask the owner (choice question), don't
pick.

## 2. Which numbers

`metrics` takes only these names (`insights/metrics.py`, `NUMBERS`); percentages as numbers
(`31.8`, not « 31,8 % »), durations in seconds (« 1 min 5 s » → 65).

| On the screenshot (TikTok, fr / en) | `metrics` |
| --- | --- |
| Vues de la vidéo · Video views | `views` |
| Durée moyenne de visionnage · Average watch time | `avg_watch` |
| A regardé la vidéo en entier · Watched full video | `finished` |
| Nouveaux abonnés · New followers | `follows` |
| J'aime · Likes | `likes` |
| Commentaires · Comments | `comments` |
| Partages · Shares | `shares` |
| Enregistrements, Favoris · Saves, Favorites | `saves` |
| Spectateurs touchés · Reached audience | `reach` |
| 100 − « taux de saut », only if shown as a number | `hook` |

Not recorded: total play time (it is views × average), traffic sources, the retention curve
(unless a value is written on it, e.g. « 45 % à 0:03 » → `hook` when it is at 3 s).

YouTube is read by the API (views, likes, comments, average watched, shares, follows): from a
YouTube Studio screenshot or export record only what the API lacks:

| YouTube Studio (fr / en) | `metrics` |
| --- | --- |
| Impressions de miniatures · Impressions | `impressions` |
| Taux de clics sur la miniature (%) · Impressions click-through rate (%) | `ctr` |
| Ont choisi de regarder (%) · Viewed (vs. swiped away) (%) (a Short) | `viewed_pct` |
| « Introduction » of a film's retention (still there at 0:30) | `kept_30s` |

Facebook reels from a Meta Business Suite export: « Portée » · Reach → `reach` (the API does not give
it for reels); the rest is read every night. Instagram: nothing to record; say so.

The list « Contenu » of TikTok Studio (all videos at once) usually shows views, likes and
comments; a video's own page adds the average, the full views, the followers. Both are fine.

## 2b. The YouTube Studio export (a zip, weekly)

The owner may send the zip YouTube Studio exports (Analytics → Advanced mode → export; French
names: « Totaux.csv », « Données de graphique.csv », « Informations relatives aux tableaux.csv »).
Instead of reading images:

1. Check out the `state` branch of quran-reels (a worktree or `git clone --branch state`), save the
   zip in a new empty folder outside the repository.
2. `quran-reels insights import-youtube --zip FILE.zip --state <state checkout> --seen YYYY-MM-DD`
   (today, or the export's day; `--csv` for the table alone). It prints ONE line of JSON, the list
   of entries (platform `youtube`, `video` = the page key of the video, `impressions`, `ctr`,
   `viewed_pct` if the export has the column, source « export YouTube Studio »); ids not in
   `insights.json` are listed on stderr and left out: tell the owner.
3. Show the owner the table (video, impressions, CTR, viewed %), French, short; ask as in § 3.
4. After the yes, dispatch `insights.yml` with that exact line as `manual` (§ 4) and check (§ 5).

## 3. Show, then ask

Write the table back to the owner, in French, short: date de publication, vidéo (passage or title),
plateforme, then each number read. Ask with the choice tool (CLAUDE.md, « Les questions, toujours à
choix »): « Je les enregistre sur la page Statistiques ? », options « Oui, enregistre (Recommandé) »,
« Corriger un chiffre », « Ne rien enregistrer ». Without the tool (a scheduled session): put the
table and the question in the report, record nothing.

## 4. Save

Dispatch the workflow `insights.yml` of **mssnoussi92/quran-reels** on `main`, input `manual` = the
JSON list on one line (GitHub tools: `actions_run_trigger`, `run_workflow`; from a quran-themes-demo
session too). If the session's GitHub tools cannot reach quran-reels, attach it
(`add_repo`, owner `mssnoussi92`, repo `quran-reels`, access `push`); if that is refused, tell the
owner to send the screenshots in a quran-reels session, with the table you read.

```json
[{"platform": "tiktok", "video": "107:1-7", "published": "2026-11-14", "seen": "2026-11-22",
  "metrics": {"views": 676, "likes": 144, "comments": 1, "avg_watch": 9.8, "finished": 31.2}}]
```

- `platform`: `tiktok` (or `youtube` for § 2). `published`: the day TikTok shows for the video
  (YYYY-MM-DD), or the slot's day. `seen`: the day of the screenshot (today, unless the owner says
  otherwise). `source` (optional): « capture (arrondi) », « capture (7 jours) » when the screen
  shows a period, not the lifetime.
- The same platform, video and `seen` day replaces the entry before: to correct a number, send the
  same entry again, corrected.

## 5. Check

The run must end in success and its log say « insights: N manual entries saved »; the workflow
`catalog` rebuilds the page after it (a few minutes). Then on the statistics page each capture
must sit under its video (« TikTok · capture du … »), **not** under « Captures sans vidéo
reconnue »: an entry there has a wrong `video`; send it again with the right one, and take the
wrong one back in the same list: `{"platform": "tiktok", "video": "<the wrong one>", "seen":
"<its day>", "remove": true}`. Answer in two or three lines: what is recorded, the link to the page,
and what the numbers say only if there are enough (CLAUDE.md, « Statistiques »: below 3 videos or 12
points, no difference is claimed).
