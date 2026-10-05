"""One test per rule in docs/TRANSCRIPTION_GUIDELINES.md."""

from __future__ import annotations

from pathlib import Path

import pytest

from sma3ni_ml import text


class TestNormalize:
    def test_removes_diacritics_and_tatweel(self) -> None:
        assert text.normalize("بَرْشــا") == "برشا"

    def test_keeps_arabic_script_and_latin_words_side_by_side(self) -> None:
        # Section 1: Darija in Arabic script, French in Latin script.
        assert text.normalize("نمشي للـ réunion متاع demain") == "نمشي لل réunion متاع demain"

    def test_lowercases_latin_only(self) -> None:
        assert text.normalize("RÉUNION متاع Demain") == "réunion متاع demain"

    def test_converts_arabic_indic_digits(self) -> None:
        assert text.normalize("٣ ساعات") == "3 ساعات"

    def test_collapses_whitespace(self) -> None:
        assert text.normalize("  برشا\t\tخير\n") == "برشا خير"

    def test_keeps_light_punctuation_and_tags(self) -> None:
        assert text.normalize("شنوة؟ [ضحك]") == "شنوة؟ [ضحك]"

    def test_is_idempotent(self) -> None:
        once = text.normalize("بَرْشــا ٣ RÉUNION")
        assert text.normalize(once) == once


class TestFoldHamza:
    @pytest.mark.parametrize("raw", ["أنا", "إنا", "آنا"])
    def test_folds_alef_variants(self, raw: str) -> None:
        assert text.fold_hamza(raw) == "انا"

    def test_folds_alef_maqsura_only_at_word_end(self) -> None:
        assert text.fold_hamza("على") == "علي"
        # Mid-word alef maqsura is left alone.
        assert text.fold_hamza("علىها") == "علىها"

    def test_keeps_ta_marbuta(self) -> None:
        assert text.fold_hamza("شنوة") == "شنوة"


class TestTags:
    def test_strips_non_speech_tags(self) -> None:
        assert text.strip_tags("برشا [ضحك] خير") == "برشا خير"

    def test_keeps_pii_placeholders_by_default(self) -> None:
        assert text.strip_tags("كلمت [اسم] توا") == "كلمت [اسم] توا"

    def test_can_drop_pii_placeholders_too(self) -> None:
        assert text.strip_tags("كلمت [اسم] توا", keep_pii=False) == "كلمت توا"

    def test_unintelligible_tag_removed_before_scoring(self) -> None:
        assert text.normalize_for_scoring("برشا [غير مفهوم] خير") == "برشا خير"


class TestNormalizeForScoring:
    def test_removes_punctuation(self) -> None:
        assert text.normalize_for_scoring("شنوة؟ باهي، برشا.") == "شنوة باهي برشا"

    def test_hyphen_becomes_a_space_so_word_counts_match(self) -> None:
        assert text.normalize_for_scoring("rendez-vous") == "rendez vous"

    def test_applies_hamza_folding(self) -> None:
        assert text.normalize_for_scoring("أنا") == "انا"

    def test_is_idempotent(self) -> None:
        once = text.normalize_for_scoring("أنا شنوة؟ [ضحك] rendez-vous")
        assert text.normalize_for_scoring(once) == once


class TestLatinDetection:
    @pytest.mark.parametrize("token", ["réunion", "demain", "ok"])
    def test_latin_words(self, token: str) -> None:
        assert text.is_latin_word(token)

    @pytest.mark.parametrize("token", ["برشا", "25", "[اسم]"])
    def test_non_latin_words(self, token: str) -> None:
        assert not text.is_latin_word(token)


class TestArabizi:
    @pytest.mark.parametrize(
        ("arabic", "expected"),
        [("شنوة", "chnowa"), ("برشا", "barcha"), ("عسلامة", "3aslema")],
    )
    def test_documented_examples(self, arabic: str, expected: str) -> None:
        # Section 7 examples. These carry short vowels Arabic script does not
        # write, so they come from resources/arabizi_lexicon.tsv.
        assert text.arabizi(arabic) == expected

    @pytest.mark.parametrize(
        ("arabic", "expected"),
        [
            ("نمشي", "nmchi"),  # ي word-final -> i
            ("خدمة", "5dma"),  # خ -> 5, ة -> a
            ("وقتاش", "w9tach"),  # و word-initial -> w, ق -> 9, ش -> ch
            ("حمام", "7mam"),  # ح -> 7
            ("غدوة", "ghdoua"),  # غ -> gh, و before ة -> ou
            ("يامي", "yami"),  # ي initial -> y, then i
        ],
    )
    def test_character_map_fallback(self, arabic: str, expected: str) -> None:
        assert text.arabizi(arabic) == expected

    @pytest.mark.parametrize(
        ("arabic", "expected"),
        [
            ("الكرهبة", "elkarhba"),  # article + a lexicon word
            ("الدار", "eldar"),  # article + character map
            ("المدينة", "elmdina"),
            ("الواحد", "elwa7d"),  # the stem's first letter is still word-initial
        ],
    )
    def test_definite_article_is_el_not_al(self, arabic: str, expected: str) -> None:
        assert text.arabizi(arabic) == expected

    def test_short_word_starting_with_alef_lam_is_not_an_article(self) -> None:
        # Needs two letters after the article, so `الو` (hello) is left alone.
        assert text.arabizi("الو") == "alou"

    def test_hamza_is_a_word_initially_and_2_elsewhere(self) -> None:
        assert text.arabizi_word("أكل").startswith("a")
        assert "2" in text.arabizi_word("مأكلة")

    def test_latin_and_digits_pass_through(self) -> None:
        assert text.arabizi("نمشي للـ réunion 14h") == "nmchi ll réunion 14h"

    def test_tags_pass_through(self) -> None:
        assert text.arabizi("برشا [ضحك]") == "barcha [ضحك]"

    def test_keeps_trailing_punctuation(self) -> None:
        assert text.arabizi("شنوة؟") == "chnowa؟"


class TestResources:
    def test_charmap_covers_the_alphabet(self) -> None:
        charmap = text.arabizi_charmap()
        for char in "ابتثجحخدذرزسشصضطظعغفقكلمنهوي":
            assert char in charmap, char

    def test_lexicon_and_loanwords_load(self) -> None:
        assert text.arabizi_lexicon()["برشا"] == "barcha"
        assert text.loanwords()["karhba"] == "كرهبة"

    def test_tables_live_inside_the_package(self) -> None:
        # The server installs sma3ni-ml as a wheel, which only carries what is
        # under src/sma3ni_ml/. A table outside it would load here and break there.
        package_dir = Path(text.__file__).resolve().parent
        for name in ("arabizi_map.tsv", "arabizi_lexicon.tsv", "loanwords.tsv"):
            assert (package_dir / "resources" / name).is_file(), name


class TestLint:
    def test_accepts_a_clean_transcript(self) -> None:
        assert text.lint("شنوة أخبارك؟ نمشي لل réunion متاع demain") == []

    def test_flags_diacritics(self) -> None:
        rules = [issue.rule for issue in text.lint("بَرْشا")]
        assert "section 2" in rules

    def test_flags_arabic_indic_digits(self) -> None:
        assert any(issue.rule == "section 3" for issue in text.lint("٣ ساعات"))

    def test_flags_msa_forms(self) -> None:
        issues = text.lint("ماذا تعمل")
        assert any("شنوة" in issue.message for issue in issues)

    def test_flags_latin_loanword_that_should_be_arabic(self) -> None:
        issues = text.lint("جبت karhba جديدة")
        assert any("كرهبة" in issue.message for issue in issues)

    def test_flags_unknown_tag(self) -> None:
        issues = text.lint("برشا [صوت]")
        assert any(issue.rule == "section 4" for issue in issues)

    def test_flags_detached_negation_suffix(self) -> None:
        issues = text.lint("ما نجم ش")
        assert any("negation" in issue.message for issue in issues)

    def test_accepts_attached_negation(self) -> None:
        assert text.lint("ما نجمش") == []

    def test_issue_is_printable(self) -> None:
        issue = text.LintIssue("section 1", "message", "token")
        assert str(issue) == "[section 1] message (token)"
