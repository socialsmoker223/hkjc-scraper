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


def parse_horse_profile(response: Any, horse_id: str, horse_name: str) -> dict:
    """Parse horse profile page response.

    Args:
        response: Scrapling response object (has .css() method and .text attribute)
        horse_id: Horse ID from href
        horse_name: Horse name from race results

    Returns:
        Dictionary with horse profile data
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
    career_match = re.search(r'冠-亞-季-總出賽次數\s*(\d+)-(\d+)-(\d+)-(\d+)', response.text)
    if career_match:
        result["career_record"] = {
            "wins": int(career_match.group(1)),
            "places": int(career_match.group(2)),
            "shows": int(career_match.group(3)),
            "total": int(career_match.group(4)),
        }

    return result


def parse_jockey_profile(response: Any, jockey_id: str, jockey_name: str) -> dict:
    """Parse jockey profile page response.

    Args:
        response: Scrapling response object (has .css() method and .text attribute)
        jockey_id: Jockey ID from href
        jockey_name: Jockey name from race results

    Returns:
        Dictionary with jockey profile data
    """
    # Input validation guard clause
    if response is None or not hasattr(response, 'css') or not hasattr(response, 'text'):
        return {
            "jockey_id": jockey_id,
            "name": jockey_name,
        }

    result = {
        "jockey_id": jockey_id,
        "name": jockey_name,
        "age": None,
        "background": None,
        "achievements": None,
        "career_wins": None,
        "career_win_rate": None,
        "season_stats": {
            "wins": None,
            "places": None,
            "win_rate": None,
            "prize_money": None,
        },
    }

    full_text = response.text

    # Parse background: text after "背景：" until "成就：" or end of line
    # Match until the next label or end
    background_match = re.search(r'背景[：:]\s*(.*?)(?=\s*成就[：:]|\n\s*[在成主]|$)', full_text, re.DOTALL)
    if background_match:
        result["background"] = background_match.group(1).strip()

    # Parse achievements: text after "成就：" until "主要賽事冠軍：" or end of line
    achievements_match = re.search(r'成就[：:]\s*(.*?)(?=\s*主要賽事冠軍[：:]|\n\s*在港累積|\n\s*[主在]|$)', full_text, re.DOTALL)
    if achievements_match:
        result["achievements"] = achievements_match.group(1).strip()

    # Parse career stats: "在港累積XXX場勝出率：百分之XX.X" or "在港累積XXX場勝出率百分之XX.X"
    career_match = re.search(r'在港累積.*?(\d+)場.*?勝出率[：:]*.*?百分之([\d.]+)', full_text)
    if career_match:
        result["career_wins"] = int(career_match.group(1))
        result["career_win_rate"] = float(career_match.group(2))

    # Parse season stats and age from table rows
    rows = response.css("table tr")

    for row in rows:
        cells = row.css("td")
        if len(cells) >= 2:
            label = cells[0].text
            value = cells[1].text

            if not label or not value:
                continue

            # Parse age
            if "年齡" in label:
                age_match = re.search(r'(\d+)', value)
                if age_match:
                    try:
                        result["age"] = int(age_match.group(1))
                    except ValueError:
                        result["age"] = None

            # Parse season stats
            elif "冠" in label and "：" in label:
                try:
                    result["season_stats"]["wins"] = int(value.strip())
                except ValueError:
                    result["season_stats"]["wins"] = None

            elif "亞" in label and "：" in label:
                try:
                    result["season_stats"]["places"] = int(value.strip())
                except ValueError:
                    result["season_stats"]["places"] = None

            elif "勝出率" in label:
                # Extract percentage value, removing % symbol if present
                win_rate_str = value.strip().replace("%", "")
                try:
                    result["season_stats"]["win_rate"] = float(win_rate_str)
                except ValueError:
                    result["season_stats"]["win_rate"] = None

            elif "獎金" in label:
                # Parse prize money: remove $ and commas
                cleaned = value.strip().replace("$", "").replace(",", "")
                try:
                    result["season_stats"]["prize_money"] = int(cleaned)
                except ValueError:
                    result["season_stats"]["prize_money"] = None

    return result


def parse_trainer_profile(response: Any, trainer_id: str, trainer_name: str) -> dict:
    """Parse trainer profile page response.

    Args:
        response: Scrapling response object (has .css() method and .text attribute)
        trainer_id: Trainer ID from href
        trainer_name: Trainer name from race results

    Returns:
        Dictionary with trainer profile data
    """
    # Input validation guard clause
    if response is None or not hasattr(response, 'css') or not hasattr(response, 'text'):
        return {
            "trainer_id": trainer_id,
            "name": trainer_name,
        }

    result = {
        "trainer_id": trainer_id,
        "name": trainer_name,
        "age": None,
        "background": None,
        "achievements": None,
        "career_wins": None,
        "career_win_rate": None,
        "season_stats": {
            "wins": None,
            "places": None,
            "shows": None,
            "fourth": None,
            "total_runners": None,
            "win_rate": None,
            "prize_money": None,
        },
    }

    full_text = response.text

    # Parse background: text after "背景：" until "成就：" or end of line
    # Match until the next label or end
    background_match = re.search(r'背景[：:]\s*(.*?)(?=\s*成就[：:]|\n\s*[在成主]|$)', full_text, re.DOTALL)
    if background_match:
        result["background"] = background_match.group(1).strip()

    # Parse achievements: text after "成就：" until "主要賽事冠軍：" or end of line
    achievements_match = re.search(r'成就[：:]\s*(.*?)(?=\s*主要賽事冠軍[：:]|\n\s*在港累積|\n\s*[主在]|$)', full_text, re.DOTALL)
    if achievements_match:
        result["achievements"] = achievements_match.group(1).strip()

    # Parse career stats: "在港累積XXX場勝出率：百分之XX.X" or "在港累積XXX場勝出率百分之XX.X"
    career_match = re.search(r'在港累積.*?(\d+)場.*?勝出率[：:]*.*?百分之([\d.]+)', full_text)
    if career_match:
        result["career_wins"] = int(career_match.group(1))
        result["career_win_rate"] = float(career_match.group(2))

    # Parse season stats and age from table rows
    rows = response.css("table tr")

    for row in rows:
        cells = row.css("td")
        if len(cells) >= 2:
            label = cells[0].text
            value = cells[1].text

            if not label or not value:
                continue

            # Parse age
            if "年齡" in label:
                age_match = re.search(r'(\d+)', value)
                if age_match:
                    try:
                        result["age"] = int(age_match.group(1))
                    except ValueError:
                        result["age"] = None

            # Parse season stats
            elif "冠" in label and "：" in label:
                try:
                    result["season_stats"]["wins"] = int(value.strip())
                except ValueError:
                    result["season_stats"]["wins"] = None

            elif "亞" in label and "：" in label:
                try:
                    result["season_stats"]["places"] = int(value.strip())
                except ValueError:
                    result["season_stats"]["places"] = None

            elif "季" in label and "：" in label:
                try:
                    result["season_stats"]["shows"] = int(value.strip())
                except ValueError:
                    result["season_stats"]["shows"] = None

            elif "殿" in label and "：" in label:
                try:
                    result["season_stats"]["fourth"] = int(value.strip())
                except ValueError:
                    result["season_stats"]["fourth"] = None

            elif "出馬總數" in label:
                try:
                    result["season_stats"]["total_runners"] = int(value.strip())
                except ValueError:
                    result["season_stats"]["total_runners"] = None

            elif "勝出率" in label:
                # Extract percentage value, removing % symbol if present
                win_rate_str = value.strip().replace("%", "")
                try:
                    result["season_stats"]["win_rate"] = float(win_rate_str)
                except ValueError:
                    result["season_stats"]["win_rate"] = None

            elif "獎金" in label:
                # Parse prize money: remove $ and commas
                cleaned = value.strip().replace("$", "").replace(",", "")
                try:
                    result["season_stats"]["prize_money"] = int(cleaned)
                except ValueError:
                    result["season_stats"]["prize_money"] = None

    return result
