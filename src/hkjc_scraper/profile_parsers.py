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


def parse_horse_profile(response: Any, horse_id: str, horse_name: str) -> dict:
    """Parse horse profile page response.

    Args:
        response: Scrapling response object (has .css() method and .text attribute)
        horse_id: Horse ID from href
        horse_name: Horse name from race results

    Returns:
        Dictionary with horse profile data
    """
    result = {
        "horse_id": horse_id,
        "name": horse_name,
        "country_of_birth": None,
        "age": None,
        "colour": None,
        "gender": None,
        "sire": None,
        "dam": None,
        "damsire": None,
        "owner": None,
        "current_rating": None,
        "initial_rating": None,
        "season_prize": None,
        "total_prize": None,
        "career_record": {"wins": 0, "places": 0, "shows": 0, "total": 0},
    }

    rows = response.css("table tr")

    for row in rows:
        cells = row.css("td")
        if len(cells) >= 2:
            label = cells[0].text
            value = cells[1].text

            if not label or not value:
                continue

            # Parse country of birth and age: "出生地/馬齡"
            if "出生地/馬齡" in label:
                parts = value.strip().split()
                if len(parts) >= 2:
                    result["country_of_birth"] = parts[0]
                    result["age"] = parts[1]
                elif len(parts) == 1:
                    result["country_of_birth"] = parts[0]

            # Parse colour and gender: "毛色/性別"
            elif "毛色/性別" in label:
                parts = value.strip().split()
                if len(parts) >= 2:
                    result["colour"] = parts[0]
                    result["gender"] = parts[1]
                elif len(parts) == 1:
                    result["colour"] = parts[0]

            # Parse pedigree: "父系", "母系", "外祖父"
            elif "父系" in label:
                result["sire"] = value.strip()
            elif "母系" in label:
                result["dam"] = value.strip()
            elif "外祖父" in label:
                result["damsire"] = value.strip()

            # Parse owner: "馬主"
            elif "馬主" in label:
                result["owner"] = value.strip()

            # Parse ratings: "現時評分", "季初評分"
            elif "現時評分" in label:
                try:
                    result["current_rating"] = int(value.strip())
                except ValueError:
                    result["current_rating"] = None
            elif "季初評分" in label:
                try:
                    result["initial_rating"] = int(value.strip())
                except ValueError:
                    result["initial_rating"] = None

            # Parse prize money: "今季獎金", "總獎金"
            elif "今季獎金" in label:
                cleaned = value.strip().replace("$", "").replace(",", "")
                try:
                    result["season_prize"] = int(cleaned)
                except ValueError:
                    result["season_prize"] = None
            elif "總獎金" in label:
                cleaned = value.strip().replace("$", "").replace(",", "")
                try:
                    result["total_prize"] = int(cleaned)
                except ValueError:
                    result["total_prize"] = None

    # Parse career record from response.text using regex
    # Format: "冠-亞-季-總出賽次數 X-X-X-X"
    career_match = re.search(r'(\d+)-(\d+)-(\d+)-(\d+)', response.text)
    if career_match:
        result["career_record"] = {
            "wins": int(career_match.group(1)),
            "places": int(career_match.group(2)),
            "shows": int(career_match.group(3)),
            "total": int(career_match.group(4)),
        }

    return result
