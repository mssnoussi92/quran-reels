"""Arabic text helpers: normalisation and matching of gloss lemmas to Uthmani words.

Gloss books quote the Quran in ordinary (imla'i) spelling while the reel shows the Uthmani
script, e.g. «وَاللَّيْلِ إِذَا سَجَى» vs «وَٱلَّيْلِ إِذَا سَجَىٰ». Matching therefore works on
normalised forms: no diacritics or Quranic marks, one alif, one ya, ta marbuta as ha.

Nothing here changes what is displayed. These functions only decide which displayed words a
gloss belongs to.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

# Written as escapes on purpose: these are invisible combining marks.
_MARKS = re.compile(  # harakat, Quranic annotation marks, dagger alef, tatweel
    "[\\u0610-\\u061a\\u064b-\\u065f\\u0670\\u06d6-\\u06ed\\u08d3-\\u08ff\\u0640]")
_TANWEEN = re.compile("[\\u064b-\\u064d\\u08f0-\\u08f2]")
# Uthmani waw carrying a dagger alef stands for a plain alif (ٱلصَّلَوٰةَ = الصلاة).
_WAW_ALEF = re.compile("\\u0648[\\u064b-\\u065f]*\\u0670")
_LETTERS = str.maketrans({
    "ٱ": "ا", "أ": "ا", "إ": "ا", "آ": "ا", "ٲ": "ا", "ٳ": "ا",
    "ى": "ي", "ی": "ي", "ئ": "ي",
    "ؤ": "و",
    "ة": "ه",
    "ک": "ك",
})
_NON_LETTER = re.compile("[^\\u0621-\\u064a]")


def normalize(word: str) -> str:
    """Comparable form of a word: letters only, unified alif/ya, no marks."""
    w = unicodedata.normalize("NFC", word)
    w = _WAW_ALEF.sub("ا", w)
    w = _MARKS.sub("", w)
    w = w.translate(_LETTERS)
    return _NON_LETTER.sub("", w)


def skeleton(word: str) -> str:
    """Looser form for Uthmani/imla'i differences in long vowels (كِتَٰب / كتاب)."""
    return normalize(word).replace("ا", "").replace("ء", "")


_PREFIX = re.compile("^(?:[وف])?(?:[بلك])?(?:ال|ل(?=ل))?")


def core(word: str) -> str:
    """Skeleton without the attached و ف ب ل ك and article: فَطَلٌّ and الطَّلُّ → طل."""
    n = normalize(word)
    stripped = _PREFIX.sub("", n)
    return skeleton(stripped if len(stripped) >= 2 else n)


def words(text: str) -> list[str]:
    """Whitespace tokens, as displayed (pause marks such as ۚ are their own tokens)."""
    return text.split()


_VOCATIVE = {"يا", "ها"}


def quoted_words(lemma: str) -> list[str]:
    """The quotation's words, joined where the Uthmani script joins them (يَا بُشْرَى → يَـٰبُشْرَىٰ)."""
    out: list[str] = []
    for w in words(lemma):
        if not normalize(w):
            continue
        if out and normalize(out[-1]) in _VOCATIVE:
            out[-1] += w
        else:
            out.append(w)
    return out


def similarity(a: str, b: str) -> float:
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    # Looser forms only when two letters or more remain: لَا, إِلًّا and الإِلّ all reduce to ل.
    sa, sb = skeleton(a), skeleton(b)
    if len(sa) >= 2 and sa == sb:
        return 0.95
    ca, cb = core(a), core(b)
    if len(ca) >= 2 and ca == cb:
        return 0.9
    ratios = [SequenceMatcher(None, na, nb).ratio()]
    for x, y in ((sa, sb), (ca, cb)):
        if len(x) >= 2 and len(y) >= 2:
            ratios.append(SequenceMatcher(None, x, y).ratio())
    return max(ratios)


def locate(lemma: str, tokens: list[str], threshold: float = 0.7) -> list[int] | None:
    """Indexes of the ayah tokens matching each quoted word, or None if it is not there."""
    quoted = quoted_words(lemma)
    real = [i for i, t in enumerate(tokens) if normalize(t)]
    if not quoted or len(quoted) > len(real):
        return None
    best_score, best = 0.0, None
    for s in range(len(real) - len(quoted) + 1):
        span = real[s:s + len(quoted)]
        score = sum(similarity(q, tokens[i]) for q, i in zip(quoted, span, strict=True))
        if score / len(quoted) > best_score:
            best_score, best = score / len(quoted), span
    return best if best_score >= threshold else None


# Particles that never carry the meaning a gloss explains, when they open or close a quotation.
_PARTICLES = {normalize(w) for w in (  # noqa: SIM905 (reads as Arabic text)
    "ما لا لم لن إذا إذ إن أن من في على عن إلى قد لقد ثم أو بل يا مع حتى إلا ألا لما كما بما مما "
    "عما فيما الذي التي الذين اللذان هو هي هم هن أنتم"
).split()}
_PRONOUN_PREP = re.compile("^(?:ل|ب|ك|علي|الي|في|من|عن|عند|لدي|مع|ايا)(?:ه|ها|هما|هم|هن|ك|كما|كم|كن|نا|ي)$")


def _is_particle(word: str) -> bool:
    if _TANWEEN.search(word):          # بُكْمٌ is a noun, not بِكُمْ
        return False
    n = normalize(word)
    for form in (n, n[1:] if len(n) > 2 and n[0] in "وف" else n):
        if form in _PARTICLES or _PRONOUN_PREP.match(form):
            return True
    return False


def trim(quoted: list[str]) -> tuple[int, int]:
    """[start, end) of the quotation without the particles at its edges.

    «فَإِنْ عُثِرَ» → عُثِرَ, «فَلا جُنَاحَ عَلَيْهِمَا» → جُنَاحَ. Inner words are kept: the gloss
    explains the quotation as a whole, and guessing a single word inside it is wrong too often.
    """
    start, end = 0, len(quoted)
    while start < end - 1 and _is_particle(quoted[start]):
        start += 1
    while end - 1 > start and _is_particle(quoted[end - 1]):
        end -= 1
    return start, end


_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def arabic_digits(n: int) -> str:
    return str(n).translate(_DIGITS)
