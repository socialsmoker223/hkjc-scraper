"""Horse profile parsing functions for HKJC scraper.

This module contains functions for parsing horse profile data from HKJC website responses.
"""

import re
from typing import Any

from .common import parse_career_record, extract_cell_value

# Career record pattern: matches "冠-亞-季-總出賽次數*: 1-2-3-4" format
_CAREER_RECORD_PATTERN = re.compile(
    r'冠-亞-季-總出賽次數\*?\s*[：:]?\s*(\d+)-(\d+)-(\d+)-(\d+)'
)


def parse_horse_profile(response: Any, horse_id: str, horse_name: str) -> dict:
    """Parse horse profile page response.

    The HKJC website uses a 3-column table structure:
    - Column 0: Label (e.g., "出生地 / 馬齡")
    - Column 1: Separator (":")
    - Column 2: Value (e.g., "紐西蘭 / 4")

    Args:
        response: Scrapling response object (has .css() method and .text attribute)
        horse_id: Horse ID from href
        horse_name: Horse name from race results

    Returns:
        Dictionary with horse profile data including:
        - Basic info: horse_id, name, country_of_birth, age, colour, gender
        - Pedigree: sire, dam, damsire
        - Ownership: trainer, owner
        - Ratings: current_rating, initial_rating
        - Prize money: season_prize, total_prize
        - Career stats: wins, places, shows, total (flattened)
        - Import info: location, import_type, import_date (if applicable)
    """
    # Input validation guard clause
    if response is None or not hasattr(response, 'css') or not hasattr(response, 'text'):
        return {
            "horse_id": horse_id,
            "name": horse_name,
        }

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
        "trainer": None,
        "owner": None,
        "current_rating": None,
        "initial_rating": None,
        "season_prize": None,
        "total_prize": None,
        # Flattened career fields
        "wins": 0,
        "places": 0,
        "shows": 0,
        "total": 0,
        # Import information
        "location": None,
        "import_type": None,
        "import_date": None,
    }

    rows = response.css("table tr")

    for row in rows:
        cells = row.css("td")
        # HKJC uses 3-column structure: label, ":", value
        if len(cells) >= 3:
            label = cells[0].text

            # Extract value from cells[2]
            # Some values are inside nested <a> tags
            value = extract_cell_value(cells[2])

            if not label or not value:
                continue

            # Parse country of birth and age: "出生地 / 馬齡"
            # Value format: "紐西蘭 / 4" or similar
            if "出生地" in label and "馬齡" in label:
                parts = value.strip().split("/")
                if len(parts) >= 2:
                    result["country_of_birth"] = parts[0].strip()
                    result["age"] = parts[1].strip()
                elif len(parts) == 1:
                    result["country_of_birth"] = parts[0].strip()

            # Parse colour and gender: "毛色 / 性別"
            # Value format: "棗 / 閹" or similar
            elif "毛色" in label and "性別" in label:
                parts = value.strip().split("/")
                if len(parts) >= 2:
                    result["colour"] = parts[0].strip()
                    result["gender"] = parts[1].strip()
                elif len(parts) == 1:
                    result["colour"] = parts[0].strip()

            # Parse pedigree: "父系", "母系", "外祖父"
            elif "父系" in label:
                result["sire"] = value.strip()
            elif "母系" in label:
                result["dam"] = value.strip()
            elif "外祖父" in label:
                result["damsire"] = value.strip()

            # Parse trainer: "練馬師"
            elif "練馬師" in label:
                result["trainer"] = value.strip()

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

            # Parse career record: "冠-亞-季-總出賽次數"
            # Label may have * suffix: "冠-亞-季-總出賽次數*"
            elif "冠-亞-季-總出賽次數" in label:
                career = parse_career_record(value.strip())
                if career:
                    result["wins"] = career["wins"]
                    result["places"] = career["places"]
                    result["shows"] = career["shows"]
                    result["total"] = career["total"]

            # Parse import information: "賽事地點", "來港自", "來港前國家"
            elif "賽事地點" in label or "馬房" in label:
                result["location"] = value.strip()
            elif "來港自" in label:
                result["import_type"] = value.strip()
            elif "來港前國家" in label or "原產地" in label:
                result["import_date"] = value.strip()

    # Fallback: Try to find career record using CSS selectors/text search
    # This handles cases where career record is not in the main table
    # but is in the page text (e.g., from a summary section)
    if result["wins"] == 0 and result["total"] == 0:
        # Try to use Scrapling's find_by_regex if available
        if hasattr(response, 'find_by_regex'):
            # Look for elements containing the career record pattern
            matches = response.find_by_regex(
                _CAREER_RECORD_PATTERN.pattern,
                first_match=True
            )
            if matches and matches.text:
                # Extract numbers from the matched text
                career_match = re.search(r'(\d+)-(\d+)-(\d+)-(\d+)', matches.text)
                if career_match:
                    record_str = (
                        f"{career_match.group(1)}-{career_match.group(2)}-"
                        f"{career_match.group(3)}-{career_match.group(4)}"
                    )
                    career = parse_career_record(record_str)
                    if career:
                        result["wins"] = career["wins"]
                        result["places"] = career["places"]
                        result["shows"] = career["shows"]
                        result["total"] = career["total"]
        else:
            # Fallback to regex on response.text for mock objects without find_by_regex
            career_match = _CAREER_RECORD_PATTERN.search(response.text)
            if career_match:
                record_str = (
                    f"{career_match.group(1)}-{career_match.group(2)}-"
                    f"{career_match.group(3)}-{career_match.group(4)}"
                )
                career = parse_career_record(record_str)
                if career:
                    result["wins"] = career["wins"]
                    result["places"] = career["places"]
                    result["shows"] = career["shows"]
                    result["total"] = career["total"]

    return result
