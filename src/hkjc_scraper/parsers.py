"""Helper functions for parsing HKJC racing data."""

import re
from typing import Any

# Chinese numeral mapping for positions
_CHINESE_NUMERALS = {
    "一": "1",
    "二": "2",
    "三": "3",
    "四": "4",
    "五": "5",
    "六": "6",
    "七": "7",
    "八": "8",
    "九": "9",
    "十": "10",
    "零": "0",
}


def clean_position(text: str | None) -> str:
    """Clean position text by extracting digits.

    Args:
        text: Raw position text (e.g., "1", "1 ", "第一名", "1/2") or None

    Returns:
        Cleaned position string containing only digits, or empty string if none found.

    Examples:
        >>> clean_position("1")
        "1"
        >>> clean_position("第一名")
        "1"
        >>> clean_position("1/2")
        "12"
        >>> clean_position("")
        ""
        >>> clean_position(None)
        ""
    """
    if not text:
        return ""

    # First check for Chinese numerals (like "第一名", "第二名", etc.)
    for chinese, digit in _CHINESE_NUMERALS.items():
        if chinese in text:
            return digit

    # Extract all digits from the string
    digits = re.sub(r'[^\d]', '', text)
    return digits


def parse_rating(rating_text: str) -> dict[str, int] | None:
    """Parse rating text in format (min-max).

    Args:
        rating_text: Rating text like "(60-40)" or "(40-60)"

    Returns:
        Dictionary with 'min' and 'max' keys, or None if invalid format.

    Examples:
        >>> parse_rating("(60-40)")
        {"min": 60, "max": 40}
        >>> parse_rating("(40-60)")
        {"min": 40, "max": 60}
        >>> parse_rating("60-40")
        None
        >>> parse_rating("")
        None
    """
    if not rating_text:
        return None
    # Match pattern like (60-40) with parentheses
    match = re.match(r'\((\d+)-(\d+)\)', rating_text.strip())
    if match:
        min_val = int(match.group(1))
        max_val = int(match.group(2))
        return {"min": min_val, "max": max_val}
    return None


def parse_prize(prize_text: str) -> int:
    """Parse prize money text to integer value.

    Args:
        prize_text: Prize text like "HK$ 1,170,000" or "1,170,000"

    Returns:
        Prize amount as integer, or 0 if invalid.

    Examples:
        >>> parse_prize("HK$ 1,170,000")
        1170000
        >>> parse_prize("HK$ 1000000")
        1000000
        >>> parse_prize("1,170,000")
        1170000
        >>> parse_prize("")
        0
    """
    if not prize_text:
        return 0
    # Remove currency symbols, commas, and whitespace, then extract digits
    digits = re.sub(r'[^\d]', '', prize_text)
    if digits:
        return int(digits)
    return 0


def parse_running_position(element: Any) -> list[str]:
    """Parse running position from HTML element containing div elements.

    Args:
        element: HTML element with div children containing position text

    Returns:
        List of position strings

    Examples:
        >>> # Mock element with div children containing "1", "2", "3"
        >>> parse_running_position(mock_elem)
        ["1", "2", "3"]
    """
    positions: list[str] = []
    if element is None:
        return positions

    for pos_div in element.css("div > div"):
        pos_text = pos_div.text
        # Try to strip, handling various object types
        if isinstance(pos_text, str):
            pos_text = pos_text.strip()
        else:
            # For objects (including test mocks), convert to string first
            try:
                pos_text = str(pos_text).strip()
            except (TypeError, AttributeError):
                pos_text = ""

        if pos_text:
            positions.append(pos_text)
    return positions


def generate_race_id(race_date: str, racecourse: str, race_no: int) -> str:
    """Generate a unique race ID from date, course, and race number.

    Args:
        race_date: Date in YYYY/MM/DD or YYYY-MM-DD format
        racecourse: "ST" for Sha Tin, "HV" for Happy Valley
        race_no: Race number (1-11)

    Returns:
        Unique race ID in format "YYYY-MM-DD-CC-N"

    Examples:
        >>> generate_race_id("2026/03/01", "ST", 1)
        "2026-03-01-ST-1"
        >>> generate_race_id("2026/03/01", "HV", 5)
        "2026-03-01-HV-5"
    """
    # Normalize date format from YYYY/MM/DD to YYYY-MM-DD
    normalized_date = race_date.replace("/", "-")
    return f"{normalized_date}-{racecourse}-{race_no}"
