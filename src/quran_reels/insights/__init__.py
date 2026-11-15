"""Statistics of the Page (docs/insights.md).

`quran-reels insights collect` reads, once a night, the Facebook and Instagram numbers of every
post of the last weeks (reels of the calendar, Word of the day, theme videos of
quran-themes-demo), and writes insights.json on the state branch. `quran-reels insights add`
records numbers read on a screenshot (YouTube, TikTok). The catalogue's « Statistiques » page
shows them (catalog/stats.py). Read only: nothing is posted or changed anywhere.
"""
