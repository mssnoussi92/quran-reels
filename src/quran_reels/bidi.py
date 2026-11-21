"""Each line of a text shown by someone else (YouTube) keeps its own direction, wherever it is shown.

A text that mixes Arabic and English lines is laid out by the app that shows it: a phone gives each
line the direction of its first letter, a web page may give the whole text one direction (the
first letter's: right to left for an Arabic-first text, then an English line ends with its period
on the left and « [This is] » moves to its end), or force left to right (then « (Sahih
International) » inside an Arabic line puts the Arabic words around it in the wrong order). An
invisible mark at the start of the line fixes its direction in all three cases: an embedding (RLE
or LRE, Unicode's explicit formatting characters), after the direction of its first letter, which
the end of the line closes (a paragraph separator ends every embedding). No word changes.

One mark, and only where a line needs it (YouTube counts the marks: the channel's description has
1 000 characters): a line that mixes both directions, or that begins or ends with a sign of no
direction of its own (a period, a bracket, a quote, a bullet, a number). A line of one direction
from its first letter to its last (a verse alone), or without a letter, is left as it is. So is a
line that begins with what YouTube reads at a line's start, which a mark before it could hide:
hashtags (« #Quran », the three shown above the title), a mention (« @quran_words_daily »), a
chapter's time (« 0:00 », « 1:02:03 ») or a link.
Embeddings, not isolates: a phone that reads a line's direction from its first letter skips what
is inside an isolate, and would read nothing.
"""

from __future__ import annotations

import re
import unicodedata

RLE, LRE, PDF = "\u202b", "\u202a", "\u202c"
MARKS = (RLE, LRE, PDF, "\u200e", "\u200f", "\u2066", "\u2067", "\u2068", "\u2069")
RTL, LTR = ("R", "AL"), ("L",)
IGNORED = ("NSM", "BN")         # vowel signs, invisible marks: they take the letter's direction
KEEP = re.compile(r"^\s*(?:[#@]|\d{1,2}(?::\d{2}){1,2}(?!\d)|https?://)")   # read by YouTube


def plain(text: str) -> str:
    """The text without any direction mark."""
    return text.translate({ord(m): None for m in MARKS})


def first_strong(line: str) -> str | None:
    """"rtl" or "ltr": the direction of the line's first letter; None without a letter."""
    for ch in line:
        kind = unicodedata.bidirectional(ch)
        if kind in RTL:
            return "rtl"
        if kind in LTR:
            return "ltr"
    return None


def needs_mark(line: str) -> bool:
    """Would the line read differently in another direction than its own?"""
    d = first_strong(line)
    if d is None or KEEP.match(line):
        return False
    kinds = [k for ch in line.strip() if (k := unicodedata.bidirectional(ch)) not in IGNORED]
    own, other = (RTL, LTR) if d == "rtl" else (LTR, RTL)
    return any(k in other for k in kinds) or kinds[0] not in own or kinds[-1] not in own


def directed(text: str) -> str:
    """Each line that needs it starts with the mark of its own direction (the same if run twice)."""
    out = []
    for line in plain(text).split("\n"):
        if needs_mark(line):
            line = (RLE if first_strong(line) == "rtl" else LRE) + line
        out.append(line)
    return "\n".join(out)


def directions(text: str) -> str:
    """Each line with a letter, for a log: « AR+ AR+ AR EN+ … » (+: a mark is put)."""
    return " ".join({"rtl": "AR", "ltr": "EN"}[d] + ("+" if needs_mark(line) else "")
                    for line in plain(text).split("\n") if (d := first_strong(line)))
