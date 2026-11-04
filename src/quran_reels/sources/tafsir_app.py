"""Gloss books from tafsir.app (Nuqayah's الباحث القرآني).

Two endpoints are enough:
  /sources/sources.json             every book, with the list of ayahs that have an entry
  /get.php?src=<book>&s=<s>&a=<a>   the entry for one ayah, {"data": "<text>"}

For Ibn Qutaybah's *Tafsir Gharib al-Qur'an* (src=ghareeb-ibn-qutaybah) 2,394 ayahs out of
6,236 have an entry, so a full ingestion is 2,394 throttled requests, resumable. Raw texts
are stored per surah in .cache/tafsir.app/<book>/SSS.json, exactly as served.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

from quran_reels.models import AyahRef, GlossEntry
from quran_reels.sources.http import Http, read_json, write_json

BASE = "https://tafsir.app"

# Editor's footnotes (tahqiq), not the author's words: [[...]]
_FOOTNOTE = re.compile(r"\s*\[\[.*?\]\]", re.DOTALL)
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([.،؛:!؟])")
# An entry opens a line with the quoted Quran words: ﴿...﴾ or (…), optionally after «و» or
# «وقوله [تعالى|عز وجل]:».
_ENTRY = re.compile(
    r"^(?:و?قوله(?:\s+(?:تعالى|عز وجل))?\s*:?\s*|و\s*)?"
    r"(?:﴿(?P<a>[^﴾]+)﴾|\((?P<b>[^)]+)\))\s*(?P<rest>.*)$", re.DOTALL)
_SENTENCE_END = re.compile(r"(?<=[.!؟])\s+")


def parse_entries(raw: str, ref: AyahRef, edition: str) -> list[GlossEntry]:
    """Split a tafsir.app text into (lemma, explanation) entries.

    Lines that do not open with a quotation continue the previous entry. Text before the
    first quotation has no anchor in the ayah and is ignored.
    """
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", _FOOTNOTE.sub("", raw))
    entries: list[tuple[str, list[str]]] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if m := _ENTRY.match(line):
            rest = m["rest"].strip().removeprefix(":").strip()    # «(الإلُّ) : العهدُ»
            entries.append(((m["a"] or m["b"]).strip(), [rest]))
        elif entries:
            entries[-1][1].append(line)
    return [
        GlossEntry(ref=ref, lemma=lemma, text="\n".join(p for p in paras if p), edition=edition)
        for lemma, paras in entries
        if any(paras)
    ]


def excerpt(text: str, max_chars: int) -> str | None:
    """Whole sentences from the start of the first paragraph, within max_chars.

    The source is quoted, never rephrased: either complete sentences fit, or nothing.
    """
    first = text.split("\n", 1)[0].strip()
    out = ""
    for sentence in _SENTENCE_END.split(first):
        candidate = f"{out} {sentence}".strip()
        if len(candidate) > max_chars:
            break
        out = candidate
    return out or None


class TafsirApp:
    def __init__(self, cache: Path, http: Http, src: str, edition: str):
        self.root = cache / "tafsir.app"
        self.dir = self.root / src
        self.http = http
        self.src = src
        self.edition = edition
        self._book: dict | None = None

    # ---- index -----------------------------------------------------------------------

    def book(self, refresh: bool = False) -> dict:
        path = self.root / "sources.json"
        if refresh or not path.is_file():
            write_json(path, self.http.json(f"{BASE}/sources/sources.json"))
            self._book = None
        if self._book is None:
            sources = read_json(path)
            if self.src not in sources:
                raise SystemExit(f"tafsir.app has no source {self.src!r}")
            self._book = sources[self.src]
        return self._book

    def has_entry(self, index: int) -> bool:
        """keys_flag 1: keys lists ayahs with an entry; -1: ayahs without one."""
        book = self.book()
        flag, keys = book.get("keys_flag"), set(book.get("keys") or ())
        if flag == 1:
            return index in keys
        if flag == -1:
            return index not in keys
        return True

    # ---- raw texts -------------------------------------------------------------------

    def _surah_path(self, surah: int) -> Path:
        return self.dir / f"{surah:03d}.json"

    def _load_surah(self, surah: int) -> dict[str, str]:
        path = self._surah_path(surah)
        return read_json(path)["ayahs"] if path.is_file() else {}

    def _save_surah(self, surah: int, ayahs: dict[str, str]) -> None:
        ordered = dict(sorted(ayahs.items(), key=lambda kv: int(kv[0])))
        write_json(self._surah_path(surah), {
            "source": f"{BASE}/get.php?src={self.src}&s={surah}&a=<ayah>&ver=1",
            "ayahs": ordered,
        })

    def fetch(self, refs: Iterable[AyahRef], index: Callable[[AyahRef], int],
              progress: bool = False) -> int:
        """Download the missing entries for refs. Returns the number of requests made."""
        todo: dict[int, list[AyahRef]] = {}
        for ref in refs:
            todo.setdefault(ref.surah, []).append(ref)
        total = sum(len(v) for v in todo.values())
        done = requests = 0
        for surah, surah_refs in sorted(todo.items()):
            cached = self._load_surah(surah)
            dirty = False
            for ref in surah_refs:
                done += 1
                if str(ref.ayah) in cached or not self.has_entry(index(ref)):
                    continue
                data = self.http.json(f"{BASE}/get.php", src=self.src, s=ref.surah,
                                      a=ref.ayah, ver=1)
                cached[str(ref.ayah)] = data.get("data") or ""
                requests += 1
                dirty = True
                if requests % 50 == 0:
                    self._save_surah(surah, cached)
                    if progress:
                        print(f"  {self.src}: {done}/{total} ayahs checked, {requests} fetched",
                              file=sys.stderr)
            if dirty:
                self._save_surah(surah, cached)
        return requests

    def raw(self, refs: list[AyahRef], index: Callable[[AyahRef], int]) -> dict[AyahRef, str]:
        self.fetch(refs, index)
        out: dict[AyahRef, str] = {}
        for surah in {r.surah for r in refs}:
            cached = self._load_surah(surah)
            for r in refs:
                if r.surah == surah:
                    out[r] = cached.get(str(r.ayah), "")
        return out

    def entries(self, refs: list[AyahRef],
                index: Callable[[AyahRef], int]) -> dict[AyahRef, list[GlossEntry]]:
        return {r: parse_entries(text, r, self.edition) for r, text in self.raw(refs, index).items()}
