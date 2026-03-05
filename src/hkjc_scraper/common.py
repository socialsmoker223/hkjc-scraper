"""Internal helper functions shared across HKJC scraper modules.

This module contains utility functions used by multiple parsers.
These functions are considered internal implementation details and
may change without notice.
"""

import re
from typing import Any


def parse_career_record(record_str: str) -> dict | None:
    """Parse career record string into wins, places, shows, total.

    Args:
        record_str: Career record like "2-0-2-17" (wins-places-shows-total)

    Returns:
        {"wins": int, "places": int, "shows": int, "total": int} or None
    """
    if not record_str:
        return None
    parts = record_str.strip().split("-")
    if len(parts) != 4:
        return None
    try:
        return {
            "wins": int(parts[0]),
            "places": int(parts[1]),
            "shows": int(parts[2]),
            "total": int(parts[3]),
        }
    except ValueError:
        return None


def _extract_text_after_label(elements: list[Any] | None, label_text: str) -> str | None:
    """Extract text content from elements containing a specific label.

    Finds elements that contain the label (e.g., "背景：") and extracts
    the text content after the label.

    Args:
        elements: List of Scrapling elements to search
        label_text: The label text to search for (e.g., "背景：")

    Returns:
        The extracted text content after the label, or None if not found
    """
    if not elements:
        return None

    for element in elements:
        text = element.text
        if label_text in text:
            # Extract text after the label
            idx = text.find(label_text)
            if idx != -1:
                result = text[idx + len(label_text):].strip()
                # Remove trailing newlines and extra whitespace
                result = result.split('\n')[0].strip()
                if result:
                    return result
    return None


def _parse_career_stats_from_elements(elements: list[Any] | None) -> tuple[int, float] | None:
    """Parse career stats (wins, win_rate) from elements containing "在港累積".

    Args:
        elements: List of Scrapling elements to search

    Returns:
        Tuple of (wins, win_rate) or None if not found
    """
    if not elements:
        return None

    for element in elements:
        text = element.text
        if "在港累積" in text and "場" in text and "勝出率" in text and "百分之" in text:
            # Parse: "在港累積232場勝出率百分之12.4"
            wins_match = re.search(r'在港累積\s*(\d+)\s*場', text)
            rate_match = re.search(r'百分之\s*([\d.]+)', text)
            if wins_match and rate_match:
                try:
                    return (int(wins_match.group(1)), float(rate_match.group(1)))
                except (ValueError, IndexError):
                    pass
    return None
