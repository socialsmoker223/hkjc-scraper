import re
from typing import Any

def extract_horse_id(href: str) -> str | None:
    """Extract horse ID from href attribute."""
    if not href:
        return None
    match = re.search(r'horseid=([^&]+)', href)
    return match.group(1) if match else None

def extract_jockey_id(href: str) -> str | None:
    """Extract jockey ID from href attribute."""
    if not href:
        return None
    match = re.search(r'jockeyid=([^&]+)', href)
    return match.group(1) if match else None

def extract_trainer_id(href: str) -> str | None:
    """Extract trainer ID from href attribute."""
    if not href:
        return None
    match = re.search(r'trainerid=([^&]+)', href)
    return match.group(1) if match else None
