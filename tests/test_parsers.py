"""Tests for parser helper functions."""
import pytest
from hkjc_scraper.parsers import (
    clean_position,
    parse_rating,
    parse_prize,
    parse_running_position,
    generate_race_id,
)


class TestCleanPosition:
    """Test position cleaning."""

    def test_clean_position_digits_only(self):
        assert clean_position("1") == "1"

    def test_clean_position_with_spaces(self):
        assert clean_position("1 ") == "1"

    def test_clean_position_with_chinese(self):
        assert clean_position("第一名") == "1"

    def test_clean_position_empty(self):
        assert clean_position("") == ""

    def test_clean_position_with_slash(self):
        assert clean_position("1/2") == "12"


class TestParseRating:
    """Test rating parsing."""

    def test_parse_rating_standard(self):
        assert parse_rating("(60-40)") == {"min": 60, "max": 40}

    def test_parse_rating_reversed(self):
        assert parse_rating("(40-60)") == {"min": 40, "max": 60}

    def test_parse_rating_no_parens(self):
        assert parse_rating("60-40") is None

    def test_parse_rating_empty(self):
        assert parse_rating("") is None


class TestParsePrize:
    """Test prize money parsing."""

    def test_parse_prize_standard(self):
        assert parse_prize("HK$ 1,170,000") == 1170000

    def test_parse_prize_no_commas(self):
        assert parse_prize("HK$ 1000000") == 1000000

    def test_parse_prize_no_currency(self):
        assert parse_prize("1,170,000") == 1170000

    def test_parse_prize_empty(self):
        assert parse_prize("") == 0


class TestParseRunningPosition:
    """Test running position parsing."""

    def test_parse_running_position_single(self):
        # Mock element with positions
        class MockText:
            def __init__(self, text):
                self._text = text
            def strip(self):
                return self._text
            def __str__(self):
                return self._text

        class MockDiv:
            def __init__(self, text):
                self.text = MockText(text)

        class MockElem:
            def css(self, selector):
                return [MockDiv("1"), MockDiv("2"), MockDiv("3")]

        result = parse_running_position(MockElem())
        assert result == ["1", "2", "3"]

    def test_parse_running_position_empty(self):
        class MockElem:
            def css(self, selector):
                return []
        result = parse_running_position(MockElem())
        assert result == []


class TestGenerateRaceId:
    """Test race ID generation."""

    def test_generate_race_id_st(self):
        assert generate_race_id("2026/03/01", "ST", 1) == "2026-03-01-ST-1"

    def test_generate_race_id_hv(self):
        assert generate_race_id("2026/03/01", "HV", 5) == "2026-03-01-HV-5"
