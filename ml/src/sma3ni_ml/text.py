"""Darija text normalization and Arabizi transliteration.

Single implementation of `docs/TRANSCRIPTION_GUIDELINES.md`. Training targets,
predictions before scoring and the server's output all go through this module,
so a change here moves every metric: update the guidelines in the same change
and re-run the benchmark.

Two normalization levels:

* `normalize()` - the canonical written form (guidelines section 1-3). Keeps
  light punctuation and tags, so it is what training targets and API responses
  use.
* `normalize_for_scoring()` - `normalize()` plus the scoring-only steps of
  sections 2, 4 and 5: hamza folding, non-speech tags removed, punctuation
  stripped. Every metric in `metrics.py` runs on this.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

RESOURCES = Path(__file__).resolve().parents[2] / "resources"

# Section 4 - removed before WER scoring.
NON_SPEECH_TAGS = frozenset({"[ضحك]", "[غير مفهوم]"})
# Section 6 - placeholders standing in for redacted content. Kept as tokens:
# they are part of the reference the model is expected to get wrong exactly once.
# TODO(question): confirm with a human transcriber that keeping these (rather
# than dropping them like non-speech tags) is the scoring convention we want.
PII_TAGS = frozenset({"[اسم]", "[رقم]", "[عنوان]"})

_TASHKEEL = re.compile(r"[ً-ٰٟۖ-ۭ]")
_TATWEEL = "ـ"
_TAG = re.compile(r"\[[^\[\]]*\]")
# Latin letters including the accented ones French needs (é, à, ç...), but not
# the maths signs that sit inside the same Unicode block.
_LATIN = re.compile(r"[A-Za-zÀ-ÖØ-öø-ɏ]")
_ARABIC = re.compile(r"[؀-ۿݐ-ݿ]")
_WHITESPACE = re.compile(r"\s+")
# Punctuation dropped for scoring (section 5). Brackets are excluded: tags are
# handled before this runs, and a stray bracket should stay visible to lint().
_PUNCTUATION = re.compile(r"[.,;:!?\"'()«»…؟،؛٬٫`*/\\|~^<>{}=+%@#&$]")
_HYPHENS = re.compile(r"[-‐-―_]")
_TRAILING_PUNCT = ".,!?؟،؛:"

_ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

# Section 2 - MSA forms that must be written as they are said in Darija.
MSA_TO_DARIJA = {
    "ما هذا": "شنوة",
    "ماذا": "شنوة",
    "الآن": "توا",
    "كثيرا": "برشا",
    "لماذا": "علاش",
    "أين": "وين",
    "أريد": "نحب",
    "حسنا": "باهي",
}

_HAMZA_FORMS = frozenset("أإآءئؤ")
_VOWEL_AFTER_WAW = frozenset("اىي")
_VOWEL_AFTER_YA = frozenset("او")


def normalize(text: str) -> str:
    """Canonical written form of a Darija transcript (guidelines section 1-3).

    Unicode NFC, no diacritics, no tatweel, ASCII digits, lowercase Latin,
    single spaces. Punctuation and tags are preserved.
    """
    text = unicodedata.normalize("NFC", text)
    text = _TASHKEEL.sub("", text).replace(_TATWEEL, "")
    text = text.translate(_ARABIC_INDIC_DIGITS)
    # Sections 1 and 5: French/English words are lowercase. Arabic has no case,
    # so only Latin letters are touched - never str.lower() on the whole string.
    text = _LATIN.sub(lambda m: m.group().lower(), text)
    return _WHITESPACE.sub(" ", text).strip()


def fold_hamza(text: str) -> str:
    """Scoring-only hamza / alef-maqsura folding (section 2).

    `ة` is deliberately kept, as the guidelines require.
    """
    text = text.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا"}))
    # ى -> ي only at word end.
    return re.sub(r"ى(?=\s|$)", "ي", text)


def strip_tags(text: str, *, keep_pii: bool = True) -> str:
    """Remove bracketed tags (section 4). PII placeholders are kept by default."""
    keep = PII_TAGS if keep_pii else frozenset()

    def replace(match: re.Match[str]) -> str:
        return match.group() if match.group() in keep else " "

    return _WHITESPACE.sub(" ", _TAG.sub(replace, text)).strip()


def normalize_for_scoring(text: str) -> str:
    """Normalization applied before every metric (sections 2, 4 and 5)."""
    text = normalize(text)
    text = strip_tags(text, keep_pii=True)
    text = fold_hamza(text)
    # A hyphen is a spelling choice ("rendez-vous" vs "rendez vous"), so it
    # becomes a space rather than vanishing, which keeps word counts stable.
    text = _HYPHENS.sub(" ", text)
    text = _PUNCTUATION.sub("", text)
    return _WHITESPACE.sub(" ", text).strip()


def tokenize(text: str) -> list[str]:
    """Whitespace tokens of an already scoring-normalized string."""
    return text.split()


def is_latin_word(token: str) -> bool:
    """True for a French/English token (used for the code-switch metric)."""
    return bool(_LATIN.search(token)) and not _ARABIC.search(token)


def has_arabic(token: str) -> bool:
    """True if the token contains at least one Arabic-script letter."""
    return bool(_ARABIC.search(token))


def _load_tsv(name: str) -> list[list[str]]:
    """Rows of a resource TSV, without comments or the header line."""
    path = RESOURCES / name
    rows: list[list[str]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            rows.append(line.split("\t"))
    return rows[1:]


@lru_cache(maxsize=1)
def arabizi_charmap() -> dict[str, tuple[str, str]]:
    """`{arabic char: (latin, latin_word_initial)}` from `resources/arabizi_map.tsv`."""
    charmap: dict[str, tuple[str, str]] = {}
    for row in _load_tsv("arabizi_map.tsv"):
        char, latin = row[0], row[1]
        initial = row[2] if len(row) > 2 and row[2] != "-" else latin
        charmap[char] = (latin, initial)
    return charmap


@lru_cache(maxsize=1)
def arabizi_lexicon() -> dict[str, str]:
    """Whole-word Arabizi overrides from `resources/arabizi_lexicon.tsv`."""
    return {row[0]: row[1] for row in _load_tsv("arabizi_lexicon.tsv")}


@lru_cache(maxsize=1)
def loanwords() -> dict[str, str]:
    """`{latin variant: arabic spelling}` from `resources/loanwords.tsv` (section 1)."""
    table: dict[str, str] = {}
    for row in _load_tsv("loanwords.tsv"):
        arabic, variants = row[0], row[1]
        for variant in variants.split(","):
            variant = variant.strip().lower()
            if variant:
                table[variant] = arabic
    return table


def arabizi_word(word: str) -> str:
    """Transliterate one Arabic-script word (section 7).

    Lexicon first, then the character map with these positional rules: a hamza
    form is `a` word-initially and `2` elsewhere; `و` is `w` word-initially or
    before a vowel letter and `ou` otherwise; `ي` is `y` word-initially or
    before a vowel letter and `i` otherwise.
    """
    lexicon = arabizi_lexicon()
    if word in lexicon:
        return lexicon[word]

    charmap = arabizi_charmap()
    out: list[str] = []
    for i, char in enumerate(word):
        initial = i == 0
        nxt = word[i + 1] if i + 1 < len(word) else ""
        if char in _HAMZA_FORMS:
            out.append("a" if initial else "2")
        elif char == "و":
            out.append("w" if initial or nxt in _VOWEL_AFTER_WAW else "ou")
        elif char == "ي":
            out.append("y" if initial or nxt in _VOWEL_AFTER_YA else "i")
        elif char in charmap:
            latin, latin_initial = charmap[char]
            out.append(latin_initial if initial else latin)
        else:
            out.append(char)
    return "".join(out)


def arabizi(text: str) -> str:
    """Transliterate Arabic script to Arabizi (section 7).

    App output only, never a training target and never scored. Latin words,
    digits and tags pass through untouched.
    """
    out: list[str] = []
    for token in normalize(text).split():
        if token in NON_SPEECH_TAGS or token in PII_TAGS or not has_arabic(token):
            out.append(token)
            continue
        # Keep trailing punctuation attached to the word it belongs to.
        core = token.rstrip(_TRAILING_PUNCT)
        trailing = token[len(core) :]
        out.append(arabizi_word(core) + trailing)
    return " ".join(out)


@dataclass(frozen=True)
class LintIssue:
    """One guidelines violation found in a transcript."""

    rule: str
    message: str
    token: str = ""

    def __str__(self) -> str:
        where = f" ({self.token})" if self.token else ""
        return f"[{self.rule}] {self.message}{where}"


def lint(text: str) -> list[LintIssue]:
    """Check a hand transcript against the guidelines.

    Used while building the test set: run it over every new transcript before
    the clip enters a manifest. Checks are conservative - only things the
    guidelines state outright.
    """
    issues: list[LintIssue] = []

    if _TASHKEEL.search(text):
        issues.append(LintIssue("section 2", "diacritics (tashkeel) must be removed"))
    if _TATWEEL in text:
        issues.append(LintIssue("section 2", "tatweel must be removed"))
    if any(digit in text for digit in "٠١٢٣٤٥٦٧٨٩"):
        issues.append(LintIssue("section 3", "write numbers with ASCII digits"))

    normalized = normalize(text)

    for msa, darija in MSA_TO_DARIJA.items():
        if msa in normalized:
            issues.append(LintIssue("section 2", f"write '{darija}', not the MSA form", msa))

    known_tags = NON_SPEECH_TAGS | PII_TAGS
    for tag in _TAG.findall(normalized):
        if tag not in known_tags:
            issues.append(LintIssue("section 4", "unknown tag", tag))

    table = loanwords()
    for token in normalized.split():
        bare = token.strip(_TRAILING_PUNCT).lower()
        if bare in table:
            issues.append(
                LintIssue("section 1", f"integrated loanword: write '{table[bare]}'", token)
            )

    # Section 2: negation is written with 'ما' separate and 'ش' attached.
    if re.search(r"(?:^|\s)ما\s+\S+\s+ش(?:\s|$)", normalized):
        issues.append(LintIssue("section 2", "attach the negation suffix to the verb"))

    return issues
