"""Metrics: alignment counts, corpus-level rates, code-switch F1, slices."""

from __future__ import annotations

import pytest

from sma3ni_ml import metrics


class TestAlign:
    def test_identical_sequences(self) -> None:
        counts = metrics.align(["a", "b"], ["a", "b"])
        assert counts == metrics.EditCounts(hits=2)
        assert counts.rate == 0.0

    def test_substitution(self) -> None:
        counts = metrics.align(["a", "b"], ["a", "c"])
        assert (counts.substitutions, counts.deletions, counts.insertions) == (1, 0, 0)

    def test_deletion(self) -> None:
        counts = metrics.align(["a", "b"], ["a"])
        assert (counts.substitutions, counts.deletions, counts.insertions) == (0, 1, 0)

    def test_insertion(self) -> None:
        counts = metrics.align(["a"], ["a", "b"])
        assert (counts.substitutions, counts.deletions, counts.insertions) == (0, 0, 1)

    def test_empty_hypothesis_is_all_deletions(self) -> None:
        counts = metrics.align(["a", "b", "c"], [])
        assert counts.deletions == 3
        assert counts.rate == 1.0

    def test_empty_reference_with_output_is_rate_one(self) -> None:
        counts = metrics.align([], ["a", "b"])
        assert counts.insertions == 2
        assert counts.rate == 1.0

    def test_both_empty(self) -> None:
        assert metrics.align([], []).rate == 0.0

    def test_counts_add_up_to_reference_length(self) -> None:
        counts = metrics.align(["a", "b", "c", "d"], ["a", "x", "d", "e"])
        assert counts.reference_length == 4


class TestRates:
    def test_wer_counts_one_error_in_four_words(self) -> None:
        assert metrics.wer(["شنوة أخبارك يا صاحبي"], ["شنوة أحوالك يا صاحبي"]) == pytest.approx(
            0.25
        )

    def test_wer_is_corpus_level_not_an_average(self) -> None:
        refs = ["a b c d e f g h i j", "x"]
        hyps = ["a b c d e f g h i j", "y"]
        # 1 error over 11 reference words, not the mean of 0.0 and 1.0.
        assert metrics.wer(refs, hyps) == pytest.approx(1 / 11)

    def test_normalization_is_applied_before_scoring(self) -> None:
        # Punctuation, diacritics and hamza differences must not count as errors.
        assert metrics.wer(["أنا بَرشا، باهي."], ["انا برشا باهي"]) == 0.0

    def test_cer_is_character_level(self) -> None:
        assert metrics.cer(["برشا"], ["برشة"]) == pytest.approx(0.25)

    def test_mismatched_lengths_raise(self) -> None:
        with pytest.raises(ValueError, match="references but"):
            metrics.wer(["a", "b"], ["a"])


class TestCodeSwitchF1:
    def test_perfect_code_switch(self) -> None:
        score = metrics.code_switch_f1(["نمشي للـ réunion"], ["نمشي للـ réunion"])
        assert score.f1 == 1.0
        assert score.support == 1

    def test_latin_word_transcribed_in_arabic_script_is_a_miss(self) -> None:
        score = metrics.code_switch_f1(["نمشي للـ réunion"], ["نمشي لل ريونيون"])
        assert score.recall == 0.0
        assert score.f1 == 0.0

    def test_hallucinated_latin_word_hurts_precision(self) -> None:
        score = metrics.code_switch_f1(["نمشي للدار"], ["نمشي للدار demain"])
        assert score.precision == 0.0
        assert score.predicted == 1

    def test_repeated_word_must_be_transcribed_twice(self) -> None:
        score = metrics.code_switch_f1(["ok ok"], ["ok"])
        assert score.recall == pytest.approx(0.5)
        assert score.precision == 1.0

    def test_no_latin_words_at_all(self) -> None:
        score = metrics.code_switch_f1(["برشا خير"], ["برشا خير"])
        assert score.support == 0
        assert score.f1 == 0.0


class TestEvaluate:
    def test_reports_every_metric(self) -> None:
        result = metrics.evaluate(["شنوة أخبارك"], ["شنوة أخبارك"])
        assert result.utterances == 1
        assert result.wer == 0.0
        assert result.cer == 0.0
        assert result.word_counts.reference_length == 2

    def test_as_dict_is_json_friendly(self) -> None:
        payload = metrics.evaluate(["برشا"], ["برشا"]).as_dict()
        assert payload["wer"] == 0.0
        assert payload["ref_words"] == 1
        assert set(payload) >= {"wer", "cer", "cs_f1", "utterances"}


class TestSliceReport:
    def test_groups_by_label(self) -> None:
        refs = ["a b", "c d"]
        hyps = ["a b", "c x"]
        report = metrics.slice_report(refs, hyps, ["region=tunis", "region=sfax"])
        assert report["region=tunis"].wer == 0.0
        assert report["region=sfax"].wer == pytest.approx(0.5)

    def test_drops_small_slices(self) -> None:
        report = metrics.slice_report(["a"], ["a"], ["region=tunis"], min_utterances=10)
        assert report == {}

    def test_length_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="same length"):
            metrics.slice_report(["a"], ["a"], [])
