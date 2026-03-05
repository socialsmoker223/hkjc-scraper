"""Jockey and trainer profile parsing functions.

This module contains parsers for extracting profile data from HKJC jockey
and trainer profile pages. Both parsers use common helper functions from
the common module.
"""

from typing import Any

from .common import _extract_text_after_label, _parse_career_stats_from_elements


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

    # Use CSS selectors to find table cells containing the labels
    # This approach is more robust than regex on the full text
    all_tds = response.css("td")

    # Parse background from cells containing "背景："
    result["background"] = _extract_text_after_label(all_tds, "背景：")

    # Parse achievements from cells containing "成就："
    result["achievements"] = _extract_text_after_label(all_tds, "成就：")

    # Parse career stats from cells containing "在港累積"
    career_stats = _parse_career_stats_from_elements(all_tds)
    if career_stats:
        result["career_wins"] = career_stats[0]
        result["career_win_rate"] = career_stats[1]

    # Parse season stats and age from table rows
    rows = response.css("table tr")

    for row in rows:
        cells = row.css("td")
        # HKJC uses 6-column structure: label, ":", value, label, ":", value
        if len(cells) >= 3:
            label = cells[0].text

            # Extract value from cells[2], handling nested <a> tags
            value_cell = cells[2]
            value = value_cell.text.strip()

            # If cell.text is empty or whitespace, try extracting from nested <a> tag
            if not value:
                links = value_cell.css("a")
                if links:
                    value = links[0].text.strip()

            if not label or not value:
                continue

            # Parse age - extract digits from value like "45歲"
            if "年齡" in label:
                digits = ''.join(c for c in value if c.isdigit())
                if digits:
                    try:
                        result["age"] = int(digits)
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

    # Use CSS selectors to find table cells containing the labels
    all_tds = response.css("td")

    # Parse background from cells containing "背景："
    result["background"] = _extract_text_after_label(all_tds, "背景：")

    # Parse achievements from cells containing "成就："
    result["achievements"] = _extract_text_after_label(all_tds, "成就：")

    # Parse career stats from cells containing "在港累積"
    career_stats = _parse_career_stats_from_elements(all_tds)
    if career_stats:
        result["career_wins"] = career_stats[0]
        result["career_win_rate"] = career_stats[1]

    # Parse season stats and age from table rows
    rows = response.css("table tr")

    for row in rows:
        cells = row.css("td")
        # HKJC uses 6-column structure: label, ":", value, label, ":", value
        if len(cells) >= 3:
            label = cells[0].text

            # Extract value from cells[2], handling nested <a> tags
            value_cell = cells[2]
            value = value_cell.text.strip()

            # If cell.text is empty or whitespace, try extracting from nested <a> tag
            if not value:
                links = value_cell.css("a")
                if links:
                    value = links[0].text.strip()

            if not label or not value:
                continue

            # Parse age - extract digits from value like "58歲"
            if "年齡" in label:
                digits = ''.join(c for c in value if c.isdigit())
                if digits:
                    try:
                        result["age"] = int(digits)
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
