---
name: propose-series
description: Propose a new thematic series of passages (du'a, rizq, mercy, patience...) for the Quran Words Daily evening queue, for the owner to validate in a pull request. Use when the owner asks for new themes or when the themes queue runs low (quran-reels calendar).
---

# Propose a series

Content rule (CLAUDE.md, non negotiable): no Quranic text, translation or explanation is
generated. The proposal is a list of references with the rule that found them; every text comes
from Quran.com and the gloss edition at render time.

1. **State the rule**: a root (ر ح م), an opening («رَبَّنَا»), a list given by the owner (the
   seven munjiyat were theirs).
2. **Find candidates** with the quran.ai MCP (`search_quran`, `fetch_word_concordance`,
   `fetch_word_morphology`; read its grounding rules first and pass their nonce), or the cached
   Quran.com text. Keep each reference with why it matches.
3. **Shape passages**: whole sentences only (start after a sentence end, end with one: Sahih
   International punctuation, `selector/plan.py`), at most 90 s with a ready reciter; skip
   passages already in another series (`grep -r "<surah:ayah>" config/series`).
4. **Write** `config/series/<id>.yaml` (`title_ar`, `title_en`, `hashtags`, `passages`), add the
   id to a queue in `config/schedule.yaml`, then run `quran-reels series-check` and
   `quran-reels calendar --days 30`.
5. **Splits**: `QURAN_REELS_RECITER=<name> quran-reels split <passages>` for the rotation's
   reciters, or let the nightly `prepare` workflow do the next 8 days.
6. **Open a PR** listing every passage with its rule; the owner validates or edits the list.
