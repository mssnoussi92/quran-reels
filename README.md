# quran-reels

Open-source pipeline behind **Quran Words Daily**: one Quran passage every day as a vertical
reel, with Mishary Alafasy's recitation, the Uthmani text, the Sahih International English
translation and the meaning of its difficult words from Ibn Qutaybah's *Tafsir Gharib al-Qur'an*.

Published on Facebook, Instagram, TikTok and YouTube Shorts as `@quran_words_daily`.

![Mockup](docs/mockup/apercu-reel-93-2.png)

## Principles

- No Quran text, translation or explanation is ever written by AI. Everything comes from
  published, referenced editions.
- Every video credits the reciter, the translation and the word-meaning source.
- Free and open-source tooling only: Python, ffmpeg, Chromium, GitHub Actions.

## Usage

Requires Python 3.11+, ffmpeg and Chromium for Playwright.

```bash
pip install -e ".[dev]"
python -m playwright install chromium
quran-reels ingest                 # Quran text, translation, chapters, gloss index → .cache/
quran-reels render 93:1-3          # → out/093_001-003.mp4
```

`render` downloads whatever is missing from the cache (glosses and recitation of the passage).
`quran-reels ingest --all-glosses` fetches every Ibn Qutaybah entry at once (about 2,400
requests, throttled and resumable). Next to the video, `out/093_001-003/` holds the image
layers, previews, the caption and a `manifest.json` that lists every text shown with its
edition and source.

Data sources: [Quran.com API](https://api.quran.com/api/v4) (Uthmani text, Sahih
International), [tafsir.app](https://tafsir.app) (Ibn Qutaybah, *Tafsir Gharib al-Qur'an*),
[EveryAyah](https://everyayah.com) (recitations).

## Status

Work in progress: rendering works, publishing does not yet. See [`CLAUDE.md`](CLAUDE.md) for the architecture and decisions
(in French) and [`docs/plateformes.md`](docs/plateformes.md) for platform constraints.

## Credits

Fonts: Amiri Quran, Amiri (Khaled Hosny) and Lora, under the SIL Open Font License
(see `assets/fonts/`). Quran data, translation, tafsir and recitations belong to their
respective publishers and are downloaded at build time, not redistributed here.

## License

Code: MIT.
