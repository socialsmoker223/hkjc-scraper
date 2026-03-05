"""ID extraction utilities for HKJC scraper.

This module contains functions for extracting horse, jockey, and trainer IDs
from HKJC URL href attributes.
"""

import re
from typing import Final

# Compiled regex patterns for better performance
_HORSE_ID_PATTERN: Final = re.compile(r'horseid=([^&]+)')
_JOCKEY_ID_PATTERN: Final = re.compile(r'jockeyid=([^&]+)')
_TRAINER_ID_PATTERN: Final = re.compile(r'trainerid=([^&]+)')


def extract_horse_id(href: str) -> str | None:
    """Extract horse ID from href attribute.

    Args:
        href: URL href attribute containing horseid parameter

    Returns:
        Horse ID string, or None if not found

    Examples:
        >>> extract_horse_id("https://hkjc.com/racing/horse/horseid=H123&foo=bar")
        "H123"
        >>> extract_horse_id(None)
        None
        >>> extract_horse_id("")
        None
    """
    if not href:
        return None
    match = _HORSE_ID_PATTERN.search(href)
    return match.group(1) if match else None


def extract_jockey_id(href: str) -> str | None:
    """Extract jockey ID from href attribute.

    Args:
        href: URL href attribute containing jockeyid parameter

    Returns:
        Jockey ID string, or None if not found

    Examples:
        >>> extract_jockey_id("https://hkjc.com/racing/jockey/jockeyid=PZ&foo=bar")
        "PZ"
        >>> extract_jockey_id(None)
        None
    """
    if not href:
        return None
    match = _JOCKEY_ID_PATTERN.search(href)
    return match.group(1) if match else None


def extract_trainer_id(href: str) -> str | None:
    """Extract trainer ID from href attribute.

    Args:
        href: URL href attribute containing trainerid parameter

    Returns:
        Trainer ID string, or None if not found

    Examples:
        >>> extract_trainer_id("https://hkjc.com/racing/trainer/trainerid=NPC&foo=bar")
        "NPC"
        >>> extract_trainer_id(None)
        None
    """
    if not href:
        return None
    match = _TRAINER_ID_PATTERN.search(href)
    return match.group(1) if match else None
