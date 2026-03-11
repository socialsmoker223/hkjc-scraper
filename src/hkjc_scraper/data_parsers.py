"""Data parsing functions for HKJC racing data.

This module contains utility functions for parsing and cleaning various
data formats from HKJC racing data, including positions, ratings, prizes,
and sectional times.
"""

import re
from typing import Any, Final

# Special race position status codes from HKJC special race index
# https://racing.hkjc.com/zh-hk/local/page/special-race-index
_SPECIAL_POSITION_CODES = {
    "DISQ",  # 取消資格 / Disqualified
    "DNF",   # 未有跑畢全程 / Did Not Finish
    "FE",    # 馬匹在賽事中跌倒 / Fell
    "ML",    # 多個馬位 / Multiple Lengths
    "PU",    # 拉停 / Pulled Up
    "TNP",   # 并無參賽競逐 / Took No Part
    "TO",    # 遙遙落後 / Tailged Off
    "UR",    # 騎師墮馬 / Unseated Rider
    "VOID",  # 賽事無效 / Void Race
    "WR",    # 司閘員著令退出 / Withdrawn by Starter
    "WV",    # 因健康理由宣佈退出 / Withdrawn Veterinary
    "WV-A",  # 因健康理由於騎師過磅后宣佈退出 / Withdrawn Veterinary After Weigh-in
    "WX",    # 競賽董事小組著令退出 / Withdrawn Stewards
    "WX-A",  # 於騎師過磅後被競賽董事小組著令退出 / Withdrawn Stewards After Weigh-in
    "WXNR",  # 競賽董事小組著令退出，視作無出賽馬匹 / Withdrawn Stewards No Runner
}

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

# Compiled regex patterns for performance
_DIGITS_ONLY_PATTERN: Final = re.compile(r'[^\d]')
_RATING_PATTERN: Final = re.compile(r'\((\d+)-(\d+)\)')

# Racecourse mapping for Chinese names to codes
RACECOURSE_MAP = {
    "沙田": "ST",  # Sha Tin
    "谷草": "HV",  # Happy Valley (grass)
}

# Reverse mapping for codes to Chinese names
RACECOURSE_NAMES = {
    "ST": "沙田",
    "HV": "谷草",
}


def clean_position(text: str | None) -> str:
    """Clean position text by extracting digits or preserving special status codes.

    Args:
        text: Raw position text (e.g., "1", "1 ", "第一名", "DISQ", "DNF") or None

    Returns:
        Cleaned position string containing digits, special status code, or empty string.

    Examples:
        >>> clean_position("1")
        "1"
        >>> clean_position("第一名")
        "1"
        >>> clean_position("1/2")
        "12"
        >>> clean_position("DISQ")
        "DISQ"
        >>> clean_position("DNF")
        "DNF"
        >>> clean_position("PU")
        "PU"
        >>> clean_position("")
        ""
        >>> clean_position(None)
        ""
    """
    if not text:
        return ""

    text = text.strip().upper()

    # First check for special position status codes
    if text in _SPECIAL_POSITION_CODES:
        return text

    # Check for Chinese numerals (like "第一名", "第二名", etc.)
    for chinese, digit in _CHINESE_NUMERALS.items():
        if chinese in text:
            return digit

    # Extract all digits from the string
    digits = _DIGITS_ONLY_PATTERN.sub('', text)
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
    match = _RATING_PATTERN.match(rating_text.strip())
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
    digits = _DIGITS_ONLY_PATTERN.sub('', prize_text)
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


def parse_sectional_time_cell(cell_text: str) -> dict[str, int | str | float] | None:
    """Extract position, margin, time from a section cell.

    Args:
        cell_text: Cell text like "3\n1/2\n13.52" or "1\nN\n13.44"

    The cell contains position, margin, and time on separate lines.
    Some cells may have extra 200m split times that should be ignored.

    Returns:
        {"position": int, "margin": str, "time": float} or None if empty
    """
    if not cell_text or not cell_text.strip():
        return None

    # Split by whitespace (including newlines) and filter empty strings
    parts = [p for p in cell_text.strip().split() if p]
    if len(parts) < 2:
        return None

    # First part is always position
    try:
        position = int(parts[0])
    except ValueError:
        return None

    # Find the time - it's the last numeric value that can be parsed as float
    # Skip values that look like times with colons (e.g., 1:21.96)
    time = None
    time_idx = None
    for i in range(len(parts) - 1, 0, -1):  # Skip position at index 0
        try:
            if ":" not in parts[i]:  # Skip finish times
                time = float(parts[i])
                time_idx = i
                break
        except ValueError:
            continue

    if time is None:
        return None

    # Margin is everything between position and time
    margin = ""
    if time_idx and time_idx > 1:
        margin = " ".join(parts[1:time_idx])

    return {"position": position, "margin": margin, "time": time}
