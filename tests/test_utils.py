"""Unit tests for the utils module."""

from hkjc_scraper.utils import generate_date_range, parse_race_date


def test_generate_date_range_single_day():
    """Test generating a single day range."""
    dates = list(generate_date_range("2015/01/01", "2015/01/01"))
    assert dates == ["2015/01/01"]


def test_generate_date_range_multiple_days():
    """Test generating multiple days."""
    dates = list(generate_date_range("2015/01/01", "2015/01/03"))
    assert dates == ["2015/01/01", "2015/01/02", "2015/01/03"]


def test_generate_date_range_august_skipped():
    """Test that August dates are included (filtering happens elsewhere)."""
    dates = list(generate_date_range("2015/07/31", "2015/08/02"))
    assert "2015/07/31" in dates
    assert "2015/08/01" in dates
    assert "2015/08/02" in dates


def test_parse_race_date():
    """Test parsing race date string."""
    dt = parse_race_date("2015/01/01")
    assert dt.year == 2015
    assert dt.month == 1
    assert dt.day == 1
