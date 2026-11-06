---
name: add-background
description: Find, check and propose new background clips (Pixabay) for Quran Words Daily reels, or remove one the owner dislikes. Use when the owner asks for new or different backgrounds or complains about one.
---

# Backgrounds

The owner's rules: no people, no animals, no text, no buildings or city lights; slow motion
only (`pb-moving-clouds`, a fast timelapse, was removed: hard on the eyes); white text must stay
readable. Backgrounds are chosen by the passage's words (themes in `config/backgrounds.yaml`),
and the same passage always gets the same one.

1. **Search** with the `backgrounds-search` workflow (manual, optional theme) or
   `quran-reels backgrounds search` (needs `PIXABAY_API_KEY`; never print it). Pixabay's rules:
   answers cached 24 h, at most one request every 0.7 s, previews one every 5 s, honour
   `Retry-After` (their CDN answers 429 otherwise).
2. **Sort** on tags first; the search already leaves out a clip that moves faster than
   `max_motion` (30, `config/backgrounds.yaml`: its preview's change between frames 1 s apart,
   16 px wide; the refused fast clouds scored 34.9, the kept clips at most 23.5) and gives each
   candidate its `motion`. Then check each preview (`_tiny.mp4`) frame by frame: 8 frames, zoom
   on beaches and lakes. `quran-reels backgrounds motion [files]` scores clips by hand.
3. **Propose** 2–3 per theme to the owner with stills (SendUserFile). Add only the approved
   ones to `config/backgrounds.yaml`: `source: pixabay`, `pixabay_id`, `author`, `page`,
   `tags`, `note`.
4. **Remove** a clip: delete its entry and leave a comment with the date and the reason (see
   95188 in `backgrounds.yaml`), and add it under `backgrounds.refused` in
   `src/quran_reels/catalog/history.yaml` (the catalogue shows it). Check what a passage gets now:
   ```python
   from quran_reels import config
   from quran_reels.passage import build
   from quran_reels.sources import backgrounds
   cfg = config.load()
   print(backgrounds.choose(cfg, build(cfg, "2:255-255"))[0].id)
   ```
