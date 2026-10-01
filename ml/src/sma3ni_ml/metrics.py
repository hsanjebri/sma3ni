"""WER, CER and code-switch F1 for Darija transcripts.

Every number reported in `RESULTS.md` comes from here, and every input passes
through `text.normalize_for_scoring()` first (pass `already_normalized=True`
only if you have already applied it). No ad hoc scoring anywhere else.

Rates are corpus-level: total edits over total reference length, not the mean of
per-utterance rates. A mean over utterances lets a three-word clip weigh as much
as a one-minute one.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from sma3ni_ml.text import is_latin_word, normalize_for_scoring

Normalizer = Callable[[str], str]


@dataclass(frozen=True)
class EditCounts:
    """Alignment counts between a reference and a hypothesis."""

    hits: int = 0
    substitutions: int = 0
    deletions: int = 0
    insertions: int = 0

    @property
    def reference_length(self) -> int:
        return self.hits + self.substitutions + self.deletions

    @property
    def errors(self) -> int:
        return self.substitutions + self.deletions + self.insertions

    @property
    def rate(self) -> float:
        """Errors over reference length; 0.0 for an empty reference with no output."""
        if self.reference_length == 0:
            return 0.0 if self.insertions == 0 else 1.0
        return self.errors / self.reference_length

    def __add__(self, other: EditCounts) -> EditCounts:
        return EditCounts(
            hits=self.hits + other.hits,
            substitutions=self.substitutions + other.substitutions,
            deletions=self.deletions + other.deletions,
            insertions=self.insertions + other.insertions,
        )


def align(ref: Sequence[str], hyp: Sequence[str]) -> EditCounts:
    """Levenshtein alignment counts between two token (or character) sequences."""
    # Row of (distance, hits, substitutions, deletions, insertions).
    previous: list[tuple[int, int, int, int, int]] = [(j, 0, 0, 0, j) for j in range(len(hyp) + 1)]

    for i, ref_token in enumerate(ref, start=1):
        current = [(i, 0, 0, i, 0)]
        for j, hyp_token in enumerate(hyp, start=1):
            if ref_token == hyp_token:
                dist, hits, subs, dels, ins = previous[j - 1]
                current.append((dist, hits + 1, subs, dels, ins))
                continue
            sub = previous[j - 1]
            delete = previous[j]
            insert = current[j - 1]
            best = min(sub[0], delete[0], insert[0]) + 1
            if sub[0] <= delete[0] and sub[0] <= insert[0]:
                current.append((best, sub[1], sub[2] + 1, sub[3], sub[4]))
            elif delete[0] <= insert[0]:
                current.append((best, delete[1], delete[2], delete[3] + 1, delete[4]))
            else:
                current.append((best, insert[1], insert[2], insert[3], insert[4] + 1))
        previous = current

    _, hits, subs, dels, ins = previous[-1]
    return EditCounts(hits=hits, substitutions=subs, deletions=dels, insertions=ins)


def _prepare(
    texts: Iterable[str], normalizer: Normalizer | None, already_normalized: bool
) -> list[str]:
    if already_normalized:
        return list(texts)
    normalize = normalizer or normalize_for_scoring
    return [normalize(text) for text in texts]


def _check_pairs(refs: Sequence[str], hyps: Sequence[str]) -> None:
    if len(refs) != len(hyps):
        raise ValueError(f"{len(refs)} references but {len(hyps)} hypotheses")


def word_counts(
    refs: Sequence[str],
    hyps: Sequence[str],
    *,
    normalizer: Normalizer | None = None,
    already_normalized: bool = False,
) -> EditCounts:
    """Corpus-level word-alignment counts."""
    _check_pairs(refs, hyps)
    refs = _prepare(refs, normalizer, already_normalized)
    hyps = _prepare(hyps, normalizer, already_normalized)
    total = EditCounts()
    for ref, hyp in zip(refs, hyps, strict=True):
        total = total + align(ref.split(), hyp.split())
    return total


def char_counts(
    refs: Sequence[str],
    hyps: Sequence[str],
    *,
    normalizer: Normalizer | None = None,
    already_normalized: bool = False,
) -> EditCounts:
    """Corpus-level character-alignment counts. Spaces count as characters."""
    _check_pairs(refs, hyps)
    refs = _prepare(refs, normalizer, already_normalized)
    hyps = _prepare(hyps, normalizer, already_normalized)
    total = EditCounts()
    for ref, hyp in zip(refs, hyps, strict=True):
        total = total + align(list(ref), list(hyp))
    return total


def wer(refs: Sequence[str], hyps: Sequence[str], **kwargs: object) -> float:
    """Word error rate (primary metric)."""
    return word_counts(refs, hyps, **kwargs).rate  # type: ignore[arg-type]


def cer(refs: Sequence[str], hyps: Sequence[str], **kwargs: object) -> float:
    """Character error rate."""
    return char_counts(refs, hyps, **kwargs).rate  # type: ignore[arg-type]


@dataclass(frozen=True)
class CodeSwitchScore:
    """Precision / recall / F1 over Latin-script (French / English) words."""

    precision: float
    recall: float
    f1: float
    support: int
    """Latin words in the references - the metric is meaningless when this is 0."""

    predicted: int


def code_switch_f1(
    refs: Sequence[str],
    hyps: Sequence[str],
    *,
    normalizer: Normalizer | None = None,
    already_normalized: bool = False,
) -> CodeSwitchScore:
    """How well the model keeps French / English words in Latin script.

    Compares the multiset of Latin tokens per utterance, so a word said twice
    must be transcribed twice.
    """
    _check_pairs(refs, hyps)
    refs = _prepare(refs, normalizer, already_normalized)
    hyps = _prepare(hyps, normalizer, already_normalized)

    true_positives = 0
    support = 0
    predicted = 0
    for ref, hyp in zip(refs, hyps, strict=True):
        ref_latin = Counter(token for token in ref.split() if is_latin_word(token))
        hyp_latin = Counter(token for token in hyp.split() if is_latin_word(token))
        true_positives += sum((ref_latin & hyp_latin).values())
        support += sum(ref_latin.values())
        predicted += sum(hyp_latin.values())

    precision = true_positives / predicted if predicted else 0.0
    recall = true_positives / support if support else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return CodeSwitchScore(
        precision=precision, recall=recall, f1=f1, support=support, predicted=predicted
    )


@dataclass(frozen=True)
class Metrics:
    """Everything reported for one model on one set of clips."""

    utterances: int
    wer: float
    cer: float
    code_switch: CodeSwitchScore
    word_counts: EditCounts
    char_counts: EditCounts

    def as_dict(self) -> dict[str, object]:
        return {
            "utterances": self.utterances,
            "wer": round(self.wer, 4),
            "cer": round(self.cer, 4),
            "cs_precision": round(self.code_switch.precision, 4),
            "cs_recall": round(self.code_switch.recall, 4),
            "cs_f1": round(self.code_switch.f1, 4),
            "cs_support": self.code_switch.support,
            "ref_words": self.word_counts.reference_length,
            "substitutions": self.word_counts.substitutions,
            "deletions": self.word_counts.deletions,
            "insertions": self.word_counts.insertions,
        }


def evaluate(
    refs: Sequence[str],
    hyps: Sequence[str],
    *,
    normalizer: Normalizer | None = None,
    already_normalized: bool = False,
) -> Metrics:
    """All metrics for one model on one set of clips."""
    _check_pairs(refs, hyps)
    # Normalize once, then score on the normalized text.
    refs = _prepare(refs, normalizer, already_normalized)
    hyps = _prepare(hyps, normalizer, already_normalized)
    words = word_counts(refs, hyps, already_normalized=True)
    chars = char_counts(refs, hyps, already_normalized=True)
    return Metrics(
        utterances=len(refs),
        wer=words.rate,
        cer=chars.rate,
        code_switch=code_switch_f1(refs, hyps, already_normalized=True),
        word_counts=words,
        char_counts=chars,
    )


def slice_report(
    refs: Sequence[str],
    hyps: Sequence[str],
    groups: Sequence[str],
    *,
    normalizer: Normalizer | None = None,
    already_normalized: bool = False,
    min_utterances: int = 1,
) -> dict[str, Metrics]:
    """Metrics per slice (noise level, region, gender, duration bucket...).

    `groups[i]` is the slice label of pair `i`. Slices with fewer than
    `min_utterances` clips are dropped: a WER over three clips is noise.
    """
    if not len(refs) == len(hyps) == len(groups):
        raise ValueError("refs, hyps and groups must have the same length")
    refs = _prepare(refs, normalizer, already_normalized)
    hyps = _prepare(hyps, normalizer, already_normalized)

    buckets: dict[str, tuple[list[str], list[str]]] = {}
    for ref, hyp, group in zip(refs, hyps, groups, strict=True):
        bucket = buckets.setdefault(group, ([], []))
        bucket[0].append(ref)
        bucket[1].append(hyp)

    return {
        group: evaluate(group_refs, group_hyps, already_normalized=True)
        for group, (group_refs, group_hyps) in sorted(buckets.items())
        if len(group_refs) >= min_utterances
    }
