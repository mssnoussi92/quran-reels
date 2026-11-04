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

## Status

Work in progress. See [`CLAUDE.md`](CLAUDE.md) for the architecture and decisions
(in French) and [`docs/plateformes.md`](docs/plateformes.md) for platform constraints.

## Credits

Fonts: Amiri Quran, Amiri (Khaled Hosny) and Lora, under the SIL Open Font License
(see `assets/fonts/`). Quran data, translation, tafsir and recitations belong to their
respective publishers and are downloaded at build time, not redistributed here.

## License

Code: MIT.
