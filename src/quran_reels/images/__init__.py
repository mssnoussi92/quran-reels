"""Daily image posts on Instagram and Facebook (docs/images.md).

Word of the day: a 3-image carousel (the word, its ayah, its meaning by Ibn Qutaybah).
Ayah of the day: one image (prepared, disabled in config/images.yaml).
Fully automatic and deterministic: no AI in the daily loop, no manual validation.

  candidates.py  rules 1-4: which gloss entries can be posted (frozen in
                 config/image-candidates.yaml by `quran-reels images build`)
  select.py      rules 5-6: exclusions (config/exclude.yaml), stable order, no two days in a
                 row on the same surah, state; `quran-reels images next --days 7`
  cards.py       what each image shows, rendered from templates/card.html.j2 (1080×1350)
  publish.py     Instagram carousel and Facebook multi-photo post
  daily.py       `quran-reels images run`: due now → pick → render → publish → state
"""
