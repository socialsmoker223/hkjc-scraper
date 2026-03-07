"""Analytics functions for HKJC racing data.

This module provides statistical analysis functions for horse racing data,
including jockey/trainer performance, track biases, draw analysis, and horse
form trends.

All functions accept lists of records (loaded from JSON files) and return
dictionaries with analysis results.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

# Constants for position filtering
_WIN_POSITION = "1"
_PLACE_POSITIONS = {"1", "2", "3"}
_SHOW_POSITIONS = {"1", "2", "3", "4"}
_NON_FINISHING_CODES = {
    "DISQ", "DNF", "FE", "PU", "TNP", "TO", "UR", "VOID", "WR", "WV",
    "WV-A", "WX", "WX-A", "WXNR",
}
_RACECOURSE_MAP = {"沙田": "ST", "谷草": "HV"}


def _is_valid_finish(position: str | None) -> bool:
    """Check if a position represents a valid finishing result.

    Args:
        position: The position string to check.

    Returns:
        True if the horse finished the race (not a non-finishing code).
    """
    if not position:
        return False
    return position not in _NON_FINISHING_CODES


def _position_to_int(position: str | None) -> int | None:
    """Convert position string to integer.

    Args:
        position: The position string to convert.

    Returns:
        Integer position or None if not convertible.
    """
    if not position or not _is_valid_finish(position):
        return None
    try:
        return int(position)
    except ValueError:
        return None


def calculate_jockey_performance(
    performances: list[dict],
    recent_races: int = 10,
) -> dict:
    """Calculate performance statistics for jockeys.

    Analyzes jockey performance across races including win rate, place rate,
    recent form, and performance by track.

    Args:
        performances: List of performance records containing jockey_id,
            jockey, position, race_id, draw, finish_time.
        recent_races: Number of recent races to analyze for form calculation.

    Returns:
        Dictionary with jockey IDs as keys and performance stats as values:
        ```python
        {
            "jockey_id": {
                "name": str,                    # Jockey name
                "total_rides": int,              # Total races
                "wins": int,                     # 1st place finishes
                "places": int,                   # 2nd or 3rd place
                "shows": int,                    # 4th place
                "win_rate": float,               # Wins / total_rides
                "place_rate": float,             # Places / total_rides
                "top4_rate": float,              # Top 4 / total_rides
                "recent_form": list[str],        # Last N positions (newest first)
                "avg_finish": float,             # Average finishing position
                "by_track": {                    # Stats by racecourse
                    "ST": {"wins": int, "rides": int, "win_rate": float},
                    "HV": {...}
                },
                "best_draws": list[int],         # Draws with most wins
                "avg_odds": float,               # Average winning odds
            }
        }
        ```

    Examples:
        >>> performances = [
        ...     {"jockey_id": "J1", "jockey": "John Doe", "position": "1", "race_id": "2026-03-01-ST-1"},
        ...     {"jockey_id": "J1", "jockey": "John Doe", "position": "2", "race_id": "2026-03-01-ST-2"},
        ... ]
        >>> result = calculate_jockey_performance(performances)
        >>> result["J1"]["win_rate"]
        0.5
    """
    # Group data by jockey
    jockey_data: defaultdict[str, dict] = defaultdict(lambda: {
        "name": None,
        "positions": [],
        "tracks": [],
        "draws": [],
        "odds": [],
        "race_ids": [],
    })

    for perf in performances:
        jockey_id = perf.get("jockey_id") or perf.get("jockey", "")
        if not jockey_id:
            continue

        position = perf.get("position", "")
        jockey_data[jockey_id]["name"] = perf.get("jockey", "")
        jockey_data[jockey_id]["positions"].append(position)
        jockey_data[jockey_id]["race_ids"].append(perf.get("race_id", ""))

        # Track data
        race_id = perf.get("race_id", "")
        if race_id:
            parts = race_id.split("-")
            if len(parts) >= 4:
                jockey_data[jockey_id]["tracks"].append(parts[3])

        # Draw data
        draw = perf.get("draw")
        if draw:
            try:
                jockey_data[jockey_id]["draws"].append(int(draw))
            except (ValueError, TypeError):
                pass

        # Odds data
        odds = perf.get("win_odds")
        if odds:
            try:
                odds_clean = float(str(odds).replace(",", ""))
                jockey_data[jockey_id]["odds"].append(odds_clean)
            except (ValueError, TypeError):
                pass

    # Calculate statistics for each jockey
    result: dict[str, dict] = {}

    for jockey_id, data in jockey_data.items():
        positions = data["positions"]
        valid_finishes = [
            p for p in positions if _is_valid_finish(p) and p.isdigit()
        ]

        if not valid_finishes:
            continue

        total_rides = len([p for p in positions if _is_valid_finish(p)])
        wins = positions.count(_WIN_POSITION)
        places = sum(1 for p in positions if p in {"2", "3"})
        shows = positions.count("4")

        # Calculate average finishing position
        finish_positions = [_position_to_int(p) for p in positions]
        avg_finish = sum(
            fp for fp in finish_positions if fp is not None
        ) / len([fp for fp in finish_positions if fp is not None])

        # Recent form (last N positions, most recent first)
        recent_form = list(reversed(positions[-recent_races:]))

        # Track-specific stats
        track_stats: dict[str, dict] = {}
        for track in ["ST", "HV"]:
            track_indices = [
                i for i, t in enumerate(data["tracks"]) if t == track
            ]
            if track_indices:
                track_positions = [positions[i] for i in track_indices]
                track_valid = [
                    p for p in track_positions if _is_valid_finish(p)
                ]
                track_wins = track_positions.count(_WIN_POSITION)
                track_stats[track] = {
                    "wins": track_wins,
                    "rides": len(track_valid),
                    "win_rate": track_wins / len(track_valid) if track_valid else 0.0,
                }

        # Best draws
        winning_draws = [
            data["draws"][i] for i, p in enumerate(positions)
            if p == _WIN_POSITION and i < len(data["draws"])
        ]
        draw_counter = Counter(winning_draws)
        best_draws = [d for d, _ in draw_counter.most_common(3)]

        # Average odds
        avg_odds = 0.0
        if data["odds"]:
            avg_odds = sum(data["odds"]) / len(data["odds"])

        result[jockey_id] = {
            "name": data["name"],
            "total_rides": total_rides,
            "wins": wins,
            "places": places,
            "shows": shows,
            "win_rate": wins / total_rides if total_rides > 0 else 0.0,
            "place_rate": places / total_rides if total_rides > 0 else 0.0,
            "top4_rate": (wins + places + shows) / total_rides if total_rides > 0 else 0.0,
            "recent_form": recent_form,
            "avg_finish": round(avg_finish, 2),
            "by_track": track_stats,
            "best_draws": best_draws,
            "avg_odds": round(avg_odds, 2),
        }

    return result


def calculate_trainer_performance(
    performances: list[dict],
) -> dict:
    """Calculate performance statistics for trainers.

    Args:
        performances: List of performance records containing trainer_id,
            trainer, position, race_id.

    Returns:
        Dictionary with trainer IDs as keys and performance stats:
        ```python
        {
            "trainer_id": {
                "name": str,
                "total_runners": int,
                "wins": int,
                "places": int,
                "win_rate": float,
                "place_rate": float,
                "by_track": {
                    "ST": {"wins": int, "runners": int, "win_rate": float},
                    "HV": {...}
                },
            }
        }
        ```

    Examples:
        >>> performances = [
        ...     {"trainer_id": "T1", "trainer": "Jane Smith", "position": "1"},
        ...     {"trainer_id": "T1", "trainer": "Jane Smith", "position": "3"},
        ... ]
        >>> result = calculate_trainer_performance(performances)
        >>> result["T1"]["win_rate"]
        0.5
    """
    # Group data by trainer
    trainer_data: defaultdict[str, dict] = defaultdict(lambda: {
        "name": None,
        "positions": [],
        "tracks": [],
    })

    for perf in performances:
        trainer_id = perf.get("trainer_id") or perf.get("trainer", "")
        if not trainer_id:
            continue

        position = perf.get("position", "")
        trainer_data[trainer_id]["name"] = perf.get("trainer", "")
        trainer_data[trainer_id]["positions"].append(position)

        # Track data
        race_id = perf.get("race_id", "")
        if race_id:
            parts = race_id.split("-")
            if len(parts) >= 4:
                trainer_data[trainer_id]["tracks"].append(parts[3])

    # Calculate statistics
    result: dict[str, dict] = {}

    for trainer_id, data in trainer_data.items():
        positions = data["positions"]
        valid_finishes = [p for p in positions if _is_valid_finish(p)]

        if not valid_finishes:
            continue

        total_runners = len(valid_finishes)
        wins = positions.count(_WIN_POSITION)
        places = sum(1 for p in positions if p in {"2", "3"})

        # Track-specific stats
        track_stats: dict[str, dict] = {}
        for track in ["ST", "HV"]:
            track_indices = [
                i for i, t in enumerate(data["tracks"]) if t == track
            ]
            if track_indices:
                track_positions = [positions[i] for i in track_indices]
                track_valid = [
                    p for p in track_positions if _is_valid_finish(p)
                ]
                track_wins = track_positions.count(_WIN_POSITION)
                track_stats[track] = {
                    "wins": track_wins,
                    "runners": len(track_valid),
                    "win_rate": track_wins / len(track_valid) if track_valid else 0.0,
                }

        result[trainer_id] = {
            "name": data["name"],
            "total_runners": total_runners,
            "wins": wins,
            "places": places,
            "win_rate": wins / total_runners if total_runners > 0 else 0.0,
            "place_rate": places / total_runners if total_runners > 0 else 0.0,
            "by_track": track_stats,
        }

    return result


def calculate_draw_bias(
    performances: list[dict],
    races: list[dict] | None = None,
) -> dict:
    """Analyze the impact of draw position on winning chances.

    Calculates win rates by draw position for each track and distance range.

    Args:
        performances: List of performance records with draw, position, race_id.
        races: Optional list of race records with race_id, distance, racecourse.
            If provided, enables distance-specific analysis.

    Returns:
        Dictionary with draw bias statistics:
        ```python
        {
            "overall": {
                "draw_1": {"runs": int, "wins": int, "win_rate": float},
                "draw_2": {...},
                ...
            },
            "by_track": {
                "ST": {
                    "draw_1": {"runs": int, "wins": int, "win_rate": float},
                    ...
                },
                "HV": {...}
            },
            "by_distance": {  # Only if races provided
                "1000-1200": {
                    "draw_1": {"runs": int, "wins": int, "win_rate": float},
                    ...
                },
                ...
            },
            "summary": {
                "best_draw_overall": int,
                "worst_draw_overall": int,
                "low_draw_advantage": bool,  # Draws 1-6 vs 7+
            }
        }
        ```

    Examples:
        >>> performances = [
        ...     {"draw": "1", "position": "1", "race_id": "2026-03-01-ST-1"},
        ...     {"draw": "7", "position": "5", "race_id": "2026-03-01-ST-1"},
        ... ]
        >>> result = calculate_draw_bias(performances)
        >>> result["summary"]["best_draw_overall"]
        1
    """
    # Build race info lookup if provided
    race_info: dict[str, dict] = {}
    distance_ranges = ["1000-1200", "1201-1400", "1401-1650", "1651-1800", "1801+"]

    if races:
        for race in races:
            race_id = race.get("race_id", "")
            distance = race.get("distance", 0)
            racecourse = race.get("racecourse", "")

            # Categorize distance
            distance_cat = "1401-1650"  # Default
            if distance <= 1200:
                distance_cat = "1000-1200"
            elif distance <= 1400:
                distance_cat = "1201-1400"
            elif distance <= 1650:
                distance_cat = "1401-1650"
            elif distance <= 1800:
                distance_cat = "1651-1800"
            else:
                distance_cat = "1801+"

            # Map racecourse
            course_code = _RACECOURSE_MAP.get(racecourse, racecourse)

            race_info[race_id] = {
                "distance_cat": distance_cat,
                "course": course_code,
            }

    # Initialize counters
    overall_draws: defaultdict[int, dict] = defaultdict(lambda: {"runs": 0, "wins": 0})
    track_draws: defaultdict[str, defaultdict] = defaultdict(lambda: defaultdict(lambda: {"runs": 0, "wins": 0}))
    distance_draws: defaultdict[str, defaultdict] = defaultdict(lambda: defaultdict(lambda: {"runs": 0, "wins": 0}))

    # Process performances
    for perf in performances:
        draw_str = perf.get("draw")
        if not draw_str:
            continue

        try:
            draw = int(draw_str)
        except (ValueError, TypeError):
            continue

        position = perf.get("position", "")
        if not _is_valid_finish(position):
            continue

        race_id = perf.get("race_id", "")
        is_win = position == _WIN_POSITION

        # Overall stats
        overall_draws[draw]["runs"] += 1
        if is_win:
            overall_draws[draw]["wins"] += 1

        # Track-specific stats
        if race_id and race_id in race_info:
            course = race_info[race_id]["course"]
            track_draws[course][draw]["runs"] += 1
            if is_win:
                track_draws[course][draw]["wins"] += 1

            # Distance-specific stats
            dist_cat = race_info[race_id]["distance_cat"]
            distance_draws[dist_cat][draw]["runs"] += 1
            if is_win:
                distance_draws[dist_cat][draw]["wins"] += 1
        elif race_id:
            # Extract track from race_id format (YYYY-MM-DD-CC-N)
            parts = race_id.split("-")
            if len(parts) >= 4:
                course = parts[3]
                track_draws[course][draw]["runs"] += 1
                if is_win:
                    track_draws[course][draw]["wins"] += 1

    # Build result with win rates
    def _calc_stats(draws_dict: dict) -> dict:
        result = {}
        for draw, stats in sorted(draws_dict.items()):
            result[f"draw_{draw}"] = {
                "runs": stats["runs"],
                "wins": stats["wins"],
                "win_rate": stats["wins"] / stats["runs"] if stats["runs"] > 0 else 0.0,
            }
        return result

    result = {
        "overall": _calc_stats(overall_draws),
        "by_track": {
            track: _calc_stats(draws)
            for track, draws in track_draws.items()
        },
    }

    # Add distance analysis if races provided
    if races:
        result["by_distance"] = {
            dist: _calc_stats(draws)
            for dist, draws in distance_draws.items()
        }

    # Summary statistics
    draw_rates = {
        draw: stats["wins"] / stats["runs"] if stats["runs"] >= 5 else 0.0
        for draw, stats in overall_draws.items()
        if stats["runs"] >= 5
    }

    if draw_rates:
        best_draw = max(draw_rates, key=draw_rates.get)
        worst_draw = min(draw_rates, key=draw_rates.get)

        # Low draw advantage (1-6 vs 7+)
        low_draw_wins = sum(overall_draws[d]["wins"] for d in range(1, 7))
        low_draw_runs = sum(overall_draws[d]["runs"] for d in range(1, 7))
        high_draw_wins = sum(overall_draws[d]["wins"] for d in range(7, 15))
        high_draw_runs = sum(overall_draws[d]["runs"] for d in range(7, 15))

        low_draw_rate = low_draw_wins / low_draw_runs if low_draw_runs > 0 else 0.0
        high_draw_rate = high_draw_wins / high_draw_runs if high_draw_runs > 0 else 0.0

        result["summary"] = {
            "best_draw_overall": best_draw,
            "worst_draw_overall": worst_draw,
            "low_draw_advantage": low_draw_rate > high_draw_rate,
            "low_draw_rate": round(low_draw_rate, 4),
            "high_draw_rate": round(high_draw_rate, 4),
        }

    return result


def calculate_track_bias(
    performances: list[dict],
    races: list[dict],
) -> dict:
    """Analyze track biases including running position patterns and going preferences.

    Determines which running positions lead to wins at different tracks
    and identifies going/surface combinations that favor certain running styles.

    Args:
        performances: List of performance records with race_id, position,
            running_position.
        races: List of race records with race_id, racecourse, going, surface.

    Returns:
        Dictionary with track bias analysis:
        ```python
        {
            "by_track": {
                "ST": {
                    "early_leaders_win_rate": float,  # Win rate for horses 1st at 1st call
                    "front_runners_win_rate": float,  # Win rate for positions 1-3 at 1st call
                    "finishers_win_rate": float,      # Win rate for positions last-3 at 1st call
                    "optimal_running_position": int,  # Best position at 1st call
                },
                "HV": {...}
            },
            "by_going": {
                "好": {"early_speed_win_rate": float, "late_closing_win_rate": float},
                "快": {...},
                ...
            },
            "by_surface": {
                "草地": {"early_speed_win_rate": float, "late_closing_win_rate": float},
                "全天候": {...}
            }
        }
        ```

    Examples:
        >>> races = [
        ...     {"race_id": "2026-03-01-ST-1", "racecourse": "沙田", "going": "好", "surface": "草地"},
        ... ]
        >>> performances = [
        ...     {"race_id": "2026-03-01-ST-1", "position": "1", "running_position": ["1", "1", "1"]},
        ... ]
        >>> result = calculate_track_bias(performances, races)
        >>> result["by_track"]["ST"]["early_leaders_win_rate"]
        1.0
    """
    # Build race lookup
    race_lookup: dict[str, dict] = {}
    for race in races:
        race_id = race.get("race_id", "")
        racecourse = race.get("racecourse", "")
        going = race.get("going", "")
        surface = race.get("surface", "")

        course_code = _RACECOURSE_MAP.get(racecourse, racecourse)

        race_lookup[race_id] = {
            "course": course_code,
            "going": going,
            "surface": surface,
        }

    # Initialize counters
    track_stats: defaultdict[str, dict] = defaultdict(lambda: {
        "leader_runs": 0,
        "leader_wins": 0,
        "front_runs": 0,
        "front_wins": 0,
        "back_runs": 0,
        "back_wins": 0,
        "position_wins": defaultdict(int),
        "position_runs": defaultdict(int),
    })

    going_stats: defaultdict[str, dict] = defaultdict(lambda: {
        "leader_runs": 0, "leader_wins": 0,
        "back_runs": 0, "back_wins": 0,
    })

    surface_stats: defaultdict[str, dict] = defaultdict(lambda: {
        "leader_runs": 0, "leader_wins": 0,
        "back_runs": 0, "back_wins": 0,
    })

    for perf in performances:
        race_id = perf.get("race_id", "")
        if race_id not in race_lookup:
            continue

        race_info = race_lookup[race_id]
        position = perf.get("position", "")
        running_pos = perf.get("running_position", [])

        if not _is_valid_finish(position) or not running_pos:
            continue

        is_win = position == _WIN_POSITION

        # Get first running position (1st call)
        try:
            first_call_pos = int(running_pos[0])
        except (ValueError, TypeError, IndexError):
            continue

        # Track stats
        course = race_info["course"]
        track_stats[course]["position_runs"][first_call_pos] += 1
        if is_win:
            track_stats[course]["position_wins"][first_call_pos] += 1

        if first_call_pos == 1:
            track_stats[course]["leader_runs"] += 1
            if is_win:
                track_stats[course]["leader_wins"] += 1
        elif first_call_pos <= 3:
            track_stats[course]["front_runs"] += 1
            if is_win:
                track_stats[course]["front_wins"] += 1

        # Late closers (last 3 positions)
        field_size = len(running_pos) if running_pos else 14
        if first_call_pos >= max(1, field_size - 3):
            track_stats[course]["back_runs"] += 1
            if is_win:
                track_stats[course]["back_wins"] += 1

        # Going stats
        going = race_info["going"]
        if going:
            if first_call_pos == 1:
                going_stats[going]["leader_runs"] += 1
                if is_win:
                    going_stats[going]["leader_wins"] += 1
            if first_call_pos >= max(1, field_size - 3):
                going_stats[going]["back_runs"] += 1
                if is_win:
                    going_stats[going]["back_wins"] += 1

        # Surface stats
        surface = race_info["surface"]
        if surface:
            if first_call_pos == 1:
                surface_stats[surface]["leader_runs"] += 1
                if is_win:
                    surface_stats[surface]["leader_wins"] += 1
            if first_call_pos >= max(1, field_size - 3):
                surface_stats[surface]["back_runs"] += 1
                if is_win:
                    surface_stats[surface]["back_wins"] += 1

    # Build result
    result: dict[str, dict] = {"by_track": {}, "by_going": {}, "by_surface": {}}

    for track, stats in track_stats.items():
        # Find optimal running position
        position_rates = {
            pos: stats["position_wins"][pos] / stats["position_runs"][pos]
            for pos in stats["position_runs"]
            if stats["position_runs"][pos] >= 3
        }

        optimal_pos = max(position_rates, key=position_rates.get) if position_rates else None

        result["by_track"][track] = {
            "early_leaders_win_rate": (
                stats["leader_wins"] / stats["leader_runs"]
                if stats["leader_runs"] > 0 else 0.0
            ),
            "front_runners_win_rate": (
                stats["front_wins"] / stats["front_runs"]
                if stats["front_runs"] > 0 else 0.0
            ),
            "finishers_win_rate": (
                stats["back_wins"] / stats["back_runs"]
                if stats["back_runs"] > 0 else 0.0
            ),
            "optimal_running_position": optimal_pos,
        }

    for going, stats in going_stats.items():
        result["by_going"][going] = {
            "early_speed_win_rate": (
                stats["leader_wins"] / stats["leader_runs"]
                if stats["leader_runs"] > 0 else 0.0
            ),
            "late_closing_win_rate": (
                stats["back_wins"] / stats["back_runs"]
                if stats["back_runs"] > 0 else 0.0
            ),
        }

    for surface, stats in surface_stats.items():
        result["by_surface"][surface] = {
            "early_speed_win_rate": (
                stats["leader_wins"] / stats["leader_runs"]
                if stats["leader_runs"] > 0 else 0.0
            ),
            "late_closing_win_rate": (
                stats["back_wins"] / stats["back_runs"]
                if stats["back_runs"] > 0 else 0.0
            ),
        }

    return result


def calculate_class_performance(
    performances: list[dict],
    races: list[dict],
) -> dict:
    """Analyze horse performance when moving between classes.

    Tracks how horses perform when racing in different classes compared
    to their previous race.

    Args:
        performances: List of performance records with horse_id, position,
            race_id, date (if available).
        races: List of race records with race_id, class.

    Returns:
        Dictionary with class movement analysis:
        ```python
        {
            "by_current_class": {
                "第一班": {
                    "winners_from_higher": int,   # Won from higher class
                    "winners_from_same": int,     # Won from same class
                    "winners_from_lower": int,    # Won from lower class
                    "avg_finish_rating": float,
                },
                ...
            },
            "class_transitions": {
                ("第四班", "第三班"): {
                    "total_moves": int,
                    "wins_after_move": int,
                    "win_rate": float,
                },
                ...
            },
            "class_hierarchy": {
                "第一班": 1,
                "第二班": 2,
                ...
            }
        }
        ```

    Examples:
        >>> races = [
        ...     {"race_id": "R1", "class": "第四班"},
        ...     {"race_id": "R2", "class": "第三班"},
        ... ]
        >>> performances = [
        ...     {"horse_id": "H1", "race_id": "R1", "position": "1"},
        ...     {"horse_id": "H1", "race_id": "R2", "position": "2"},
        ... ]
        >>> result = calculate_class_performance(performances, races)
    """
    # Class hierarchy (lower number = higher class)
    class_rank: dict[str, int] = {
        "第一班": 1,
        "第二班": 2,
        "第三班": 3,
        "第四班": 4,
        "第五班": 5,
        "新馬賽": 6,
    }

    # Build race lookup
    race_lookup: dict[str, dict] = {}
    for race in races:
        race_id = race.get("race_id", "")
        race_class = race.get("class", "")
        race_lookup[race_id] = {"class": race_class}

    # Group performances by horse
    horse_perfs: defaultdict[str, list[dict]] = defaultdict(list)

    for perf in performances:
        horse_id = perf.get("horse_id")
        if horse_id:
            horse_perfs[horse_id].append(perf)

    # Initialize result structures
    class_stats: defaultdict[str, dict] = defaultdict(lambda: {
        "from_higher": 0,
        "from_same": 0,
        "from_lower": 0,
        "ratings": [],
    })

    transitions: defaultdict[tuple[str, str], dict] = defaultdict(lambda: {
        "moves": 0,
        "wins": 0,
    })

    # Process each horse's performances
    for horse_id, perfs in horse_perfs.items():
        # Sort by race_id (includes date)
        sorted_perfs = sorted(perfs, key=lambda p: p.get("race_id", ""))

        for i, perf in enumerate(sorted_perfs):
            race_id = perf.get("race_id", "")
            if race_id not in race_lookup:
                continue

            current_class = race_lookup[race_id]["class"]
            if not current_class or current_class not in class_rank:
                continue

            position = perf.get("position", "")
            is_win = position == _WIN_POSITION

            # Compare with previous race
            if i > 0:
                prev_race_id = sorted_perfs[i - 1].get("race_id", "")
                if prev_race_id in race_lookup:
                    prev_class = race_lookup[prev_race_id]["class"]

                    if prev_class in class_rank:
                        prev_rank = class_rank[prev_class]
                        current_rank = class_rank[current_class]

                        if prev_rank < current_rank:
                            class_stats[current_class]["from_higher"] += 1
                        elif prev_rank == current_rank:
                            class_stats[current_class]["from_same"] += 1
                        else:
                            class_stats[current_class]["from_lower"] += 1

                        # Track transitions
                        transition = (prev_class, current_class)
                        transitions[transition]["moves"] += 1
                        if is_win:
                            transitions[transition]["wins"] += 1

            # Record finish position as rating proxy
            if _is_valid_finish(position):
                try:
                    class_stats[current_class]["ratings"].append(int(position))
                except ValueError:
                    pass

    # Build final result
    result: dict[str, dict] = {
        "by_current_class": {},
        "class_transitions": {},
        "class_hierarchy": class_rank,
    }

    for cls, stats in class_stats.items():
        ratings = stats["ratings"]
        avg_finish = sum(ratings) / len(ratings) if ratings else 0.0

        result["by_current_class"][cls] = {
            "winners_from_higher": stats["from_higher"],
            "winners_from_same": stats["from_same"],
            "winners_from_lower": stats["from_lower"],
            "avg_finish_rating": round(avg_finish, 2),
        }

    for (from_cls, to_cls), trans in transitions.items():
        result["class_transitions"][f"{from_cls}->{to_cls}"] = {
            "total_moves": trans["moves"],
            "wins_after_move": trans["wins"],
            "win_rate": trans["wins"] / trans["moves"] if trans["moves"] > 0 else 0.0,
        }

    return result


def calculate_horse_form(
    performances: list[dict],
    horses: list[dict] | None = None,
    recent_races: int = 6,
) -> dict:
    """Analyze recent form trends for horses.

    Calculates recent performance patterns including consistency,
    preferred distance, and track preferences.

    Args:
        performances: List of performance records with horse_id, position,
            race_id, finish_time.
        horses: Optional list of horse profiles with horse_id, name,
            current_rating.
        recent_races: Number of recent races to analyze.

    Returns:
        Dictionary with form analysis:
        ```python
        {
            "horse_id": {
                "name": str,
                "recent_form": str,              # e.g., "12143"
                "recent_form_summary": {         # Summary of last N races
                    "wins": int,
                    "places": int,
                    "shows": int,
                    "avg_position": float,
                },
                "current_streak": str,           # "winning", "placing", "cold"
                "days_off": int,                 # Days since last race (if dates available)
                "consistency_score": float,      # Lower = more consistent
                "preferred_track": str,          # Track with best win rate
                "preferred_distance": str,       # Distance range with best results
                "career_trend": str,             # "improving", "declining", "stable"
            }
        }
        ```

    Examples:
        >>> performances = [
        ...     {"horse_id": "H1", "horse_name": "Speedy", "position": "1", "race_id": "2026-03-01-ST-1"},
        ...     {"horse_id": "H1", "horse_name": "Speedy", "position": "2", "race_id": "2026-02-15-ST-2"},
        ... ]
        >>> result = calculate_horse_form(performances)
        >>> result["H1"]["recent_form"]
        '12'
    """
    # Build horse lookup
    horse_lookup: dict[str, dict] = {}
    if horses:
        for horse in horses:
            horse_id = horse.get("horse_id")
            if horse_id:
                horse_lookup[horse_id] = {
                    "name": horse.get("name", ""),
                    "rating": horse.get("current_rating"),
                }

    # Group performances by horse
    horse_perfs: defaultdict[str, list[dict]] = defaultdict(list)

    for perf in performances:
        horse_id = perf.get("horse_id")
        if horse_id:
            horse_perfs[horse_id].append(perf)

    result: dict[str, dict] = {}

    for horse_id, perfs in horse_perfs.items():
        # Sort by race_id descending (most recent first)
        sorted_perfs = sorted(perfs, key=lambda p: p.get("race_id", ""), reverse=True)

        # Get recent form (positions as single chars)
        recent_positions = []
        for perf in sorted_perfs[:recent_races]:
            pos = perf.get("position", "")
            if pos.isdigit():
                recent_positions.append(pos)
            elif pos in _NON_FINISHING_CODES:
                recent_positions.append("-")  # Non-finish marker

        recent_form = "".join(recent_positions)

        # Summary of recent form
        recent_valid = [p for p in recent_positions if p != "-"]
        wins = recent_valid.count("1")
        places = sum(1 for p in recent_valid if p in {"2", "3"})
        shows = sum(1 for p in recent_valid if p == "4")

        avg_position = 0.0
        if recent_valid:
            try:
                avg_position = sum(int(p) for p in recent_valid) / len(recent_valid)
            except ValueError:
                pass

        # Current streak
        streak = "cold"
        if recent_valid:
            if recent_valid[0] == "1":
                # Check for multiple wins
                streak_len = 0
                for pos in recent_valid:
                    if pos == "1":
                        streak_len += 1
                    else:
                        break
                streak = f"winning_{streak_len}"
            elif recent_valid[0] in {"2", "3"}:
                streak = "placing"
            elif recent_valid[0] in {"4", "5", "6"}:
                streak = "competitive"

        # Consistency score (standard deviation of positions)
        consistency_score = 0.0
        if recent_valid and len(recent_valid) > 1:
            try:
                positions = [int(p) for p in recent_valid]
                mean = sum(positions) / len(positions)
                variance = sum((p - mean) ** 2 for p in positions) / len(positions)
                consistency_score = variance ** 0.5
            except ValueError:
                pass

        # Career trend
        all_positions = []
        for perf in sorted_perfs:
            pos = perf.get("position", "")
            if pos.isdigit():
                try:
                    all_positions.append(int(pos))
                except ValueError:
                    pass

        career_trend = "stable"
        if len(all_positions) >= 4:
            first_half = all_positions[len(all_positions) // 2:]
            second_half = all_positions[:len(all_positions) // 2]

            if first_half and second_half:
                first_avg = sum(first_half) / len(first_half)
                second_avg = sum(second_half) / len(second_half)

                if second_avg < first_avg - 2:
                    career_trend = "improving"
                elif second_avg > first_avg + 2:
                    career_trend = "declining"

        # Track preference (if race_id available)
        track_wins: defaultdict[str, int] = defaultdict(int)
        track_runs: defaultdict[str, int] = defaultdict(int)

        for perf in sorted_perfs:
            race_id = perf.get("race_id", "")
            position = perf.get("position", "")
            parts = race_id.split("-")

            if len(parts) >= 4:
                track = parts[3]
                if _is_valid_finish(position):
                    track_runs[track] += 1
                    if position == "1":
                        track_wins[track] += 1

        preferred_track = ""
        if track_runs:
            track_rates = {
                track: track_wins[track] / track_runs[track]
                for track in track_runs
                if track_runs[track] >= 2
            }
            if track_rates:
                preferred_track = max(track_rates, key=track_rates.get)

        result[horse_id] = {
            "name": horse_lookup.get(horse_id, {}).get("name", perfs[0].get("horse_name", "")),
            "recent_form": recent_form,
            "recent_form_summary": {
                "wins": wins,
                "places": places,
                "shows": shows,
                "avg_position": round(avg_position, 2),
            },
            "current_streak": streak,
            "consistency_score": round(consistency_score, 2),
            "preferred_track": preferred_track,
            "career_trend": career_trend,
        }

    return result


def calculate_jockey_trainer_combination(
    performances: list[dict],
    min_partnerships: int = 3,
) -> dict:
    """Analyze win rates for specific jockey-trainer combinations.

    Identifies profitable partnerships between jockeys and trainers.

    Args:
        performances: List of performance records with jockey_id, trainer_id,
            position.
        min_partnerships: Minimum number of rides together to be included.

    Returns:
        Dictionary with partnership statistics:
        ```python
        {
            "combinations": [
                {
                    "jockey_id": str,
                    "trainer_id": str,
                    "jockey_name": str,
                    "trainer_name": str,
                    "rides": int,
                    "wins": int,
                    "win_rate": float,
                    "place_rate": float,
                    "profit_potential": float,  # Win rate vs expected
                }
            ],
            "top_partnerships": {
                "by_win_rate": [...],  # Top 10 by win rate
                "by_volume": [...],    # Top 10 by rides
            }
        }
        ```

    Examples:
        >>> performances = [
        ...     {"jockey_id": "J1", "trainer_id": "T1", "position": "1", "jockey": "John", "trainer": "Jane"},
        ...     {"jockey_id": "J1", "trainer_id": "T1", "position": "2", "jockey": "John", "trainer": "Jane"},
        ... ]
        >>> result = calculate_jockey_trainer_combination(performances)
        >>> result["combinations"][0]["win_rate"]
        0.5
    """
    # Track combination stats
    combo_stats: defaultdict[tuple, dict] = defaultdict(lambda: {
        "rides": 0,
        "wins": 0,
        "places": 0,
        "jockey_name": None,
        "trainer_name": None,
    })

    for perf in performances:
        jockey_id = perf.get("jockey_id") or perf.get("jockey", "")
        trainer_id = perf.get("trainer_id") or perf.get("trainer", "")

        if not jockey_id or not trainer_id:
            continue

        position = perf.get("position", "")
        if not _is_valid_finish(position):
            continue

        combo = (jockey_id, trainer_id)
        combo_stats[combo]["rides"] += 1
        combo_stats[combo]["jockey_name"] = perf.get("jockey", "")
        combo_stats[combo]["trainer_name"] = perf.get("trainer", "")

        if position == "1":
            combo_stats[combo]["wins"] += 1
        if position in {"2", "3"}:
            combo_stats[combo]["places"] += 1

    # Build result
    combinations = []

    for (jockey_id, trainer_id), stats in combo_stats.items():
        if stats["rides"] < min_partnerships:
            continue

        win_rate = stats["wins"] / stats["rides"]
        place_rate = stats["places"] / stats["rides"]

        combinations.append({
            "jockey_id": jockey_id,
            "trainer_id": trainer_id,
            "jockey_name": stats["jockey_name"],
            "trainer_name": stats["trainer_name"],
            "rides": stats["rides"],
            "wins": stats["wins"],
            "win_rate": round(win_rate, 4),
            "place_rate": round(place_rate, 4),
            "profit_potential": round(win_rate * 10, 2),  # Simple score
        })

    # Sort for rankings
    by_win_rate = sorted(combinations, key=lambda x: x["win_rate"], reverse=True)
    by_volume = sorted(combinations, key=lambda x: x["rides"], reverse=True)

    return {
        "combinations": combinations,
        "top_partnerships": {
            "by_win_rate": by_win_rate[:10],
            "by_volume": by_volume[:10],
        },
    }


def calculate_distance_preference(
    performances: list[dict],
    races: list[dict],
) -> dict:
    """Analyze horse performance by distance.

    Identifies which distance ranges each horse performs best at.

    Args:
        performances: List of performance records with horse_id, position,
            race_id.
        races: List of race records with race_id, distance.

    Returns:
        Dictionary with distance analysis:
        ```python
        {
            "horse_id": {
                "name": str,
                "preferred_distance": str,      # Best distance range
                "preferred_distance_win_rate": float,
                "all_distances": {
                    "1000-1200": {
                        "runs": int,
                        "wins": int,
                        "win_rate": float,
                        "avg_position": float,
                    },
                    ...
                },
                "distance_profile": str,        # "sprinter", "middle", "stayer"
            }
        }
        ```

    Examples:
        >>> races = [{"race_id": "R1", "distance": 1000}]
        >>> performances = [{"horse_id": "H1", "race_id": "R1", "position": "1"}]
        >>> result = calculate_distance_preference(performances, races)
    """
    # Distance categories
    distance_ranges = [
        ("sprint", 1000, 1200),
        ("sprint_extended", 1201, 1400),
        ("mile", 1401, 1650),
        ("intermediate", 1651, 1800),
        ("staying", 1801, 9999),
    ]

    def _get_distance_category(distance: int) -> str:
        for cat, min_dist, max_dist in distance_ranges:
            if min_dist <= distance <= max_dist:
                return cat
        return "mile"

    def _get_distance_range(distance: int) -> str:
        if distance <= 1200:
            return "1000-1200"
        elif distance <= 1400:
            return "1201-1400"
        elif distance <= 1650:
            return "1401-1650"
        elif distance <= 1800:
            return "1651-1800"
        else:
            return "1801+"

    # Build race lookup
    race_lookup: dict[str, dict] = {}
    for race in races:
        race_id = race.get("race_id", "")
        distance = race.get("distance", 0)
        if distance:
            race_lookup[race_id] = {
                "distance": distance,
                "category": _get_distance_category(distance),
                "range": _get_distance_range(distance),
            }

    # Group by horse
    horse_data: defaultdict[str, defaultdict] = defaultdict(lambda: defaultdict(lambda: {
        "runs": 0,
        "wins": 0,
        "positions": [],
    }))

    horse_names: dict[str, str] = {}

    for perf in performances:
        horse_id = perf.get("horse_id")
        if not horse_id:
            continue

        horse_names[horse_id] = perf.get("horse_name", "")

        race_id = perf.get("race_id", "")
        if race_id not in race_lookup:
            continue

        position = perf.get("position", "")
        if not _is_valid_finish(position):
            continue

        race_info = race_lookup[race_id]
        dist_range = race_info["range"]

        horse_data[horse_id][dist_range]["runs"] += 1
        if position == "1":
            horse_data[horse_id][dist_range]["wins"] += 1

        try:
            horse_data[horse_id][dist_range]["positions"].append(int(position))
        except ValueError:
            pass

    # Build result
    result: dict[str, dict] = {}

    for horse_id, distances in horse_data.items():
        best_distance = ""
        best_win_rate = 0.0

        all_distances = {}

        for dist_range, stats in distances.items():
            runs = stats["runs"]
            wins = stats["wins"]
            win_rate = wins / runs if runs > 0 else 0.0
            positions = stats["positions"]
            avg_pos = sum(positions) / len(positions) if positions else 0.0

            all_distances[dist_range] = {
                "runs": runs,
                "wins": wins,
                "win_rate": round(win_rate, 4),
                "avg_position": round(avg_pos, 2),
            }

            if runs >= 2 and win_rate > best_win_rate:
                best_win_rate = win_rate
                best_distance = dist_range

        # Determine distance profile
        profile = "middle"
        if best_distance:
            if best_distance in {"1000-1200", "1201-1400"}:
                profile = "sprinter"
            elif best_distance in {"1651-1800", "1801+"}:
                profile = "stayer"

        result[horse_id] = {
            "name": horse_names.get(horse_id, ""),
            "preferred_distance": best_distance,
            "preferred_distance_win_rate": round(best_win_rate, 4),
            "all_distances": all_distances,
            "distance_profile": profile,
        }

    return result


def calculate_speed_ratings(
    performances: list[dict],
    races: list[dict],
) -> dict:
    """Calculate speed ratings based on finish times and class.

    Generates speed ratings by adjusting finish times for class,
    distance, and going conditions.

    Args:
        performances: List of performance records with race_id, position,
            finish_time, horse_id.
        races: List of race records with race_id, distance, class, going.

    Returns:
        Dictionary with speed ratings:
        ```python
        {
            "race_id": {
                "distance": int,
                "class": str,
                "going": str,
                "winning_time": float,
                "standard_time": float,          # Par time for this distance/going
                "ratings": [
                    {
                        "horse_id": str,
                        "horse_name": str,
                        "position": str,
                        "finish_time": float,
                        "margin_lengths": float,
                        "speed_rating": int,
                    },
                    ...
                ]
            }
        }
        ```
    """
    # Standard times (seconds) for each distance at Sha Tin (good going)
    standard_times: dict[int, float] = {
        1000: 57.5,
        1200: 68.5,
        1400: 80.5,
        1600: 92.5,
        1650: 96.0,
        1800: 105.0,
        2000: 117.0,
        2200: 129.0,
        2400: 141.0,
    }

    # Class adjustments (lower is better)
    class_adjustments: dict[str, int] = {
        "第一班": 0,
        "第二班": -3,
        "第三班": -6,
        "第四班": -9,
        "第五班": -12,
    }

    # Going adjustments
    going_adjustments: dict[str, int] = {
        "好": 0,
        "快": 1,
        "黏": -2,
        "軟": -4,
    }

    # Build race lookup
    race_lookup: dict[str, dict] = {}
    for race in races:
        race_id = race.get("race_id", "")
        distance = race.get("distance", 0)
        race_class = race.get("class", "")
        going = race.get("going", "")

        race_lookup[race_id] = {
            "distance": distance,
            "class": race_class,
            "going": going,
        }

    # Group performances by race
    race_perfs: defaultdict[str, list[dict]] = defaultdict(list)

    for perf in performances:
        race_id = perf.get("race_id", "")
        finish_time = perf.get("finish_time", "")

        # Parse finish time (format: "1:23.45" or "59.50")
        if not finish_time:
            continue

        time_parts = finish_time.split(":")
        try:
            if len(time_parts) == 2:
                minutes = int(time_parts[0])
                seconds = float(time_parts[1])
                total_seconds = minutes * 60 + seconds
            else:
                total_seconds = float(time_parts[0])
        except (ValueError, IndexError):
            continue

        race_perfs[race_id].append({
            **perf,
            "finish_time_seconds": total_seconds,
        })

    result: dict[str, dict] = {}

    for race_id, perfs in race_perfs.items():
        if race_id not in race_lookup:
            continue

        race_info = race_lookup[race_id]
        distance = race_info["distance"]
        race_class = race_info["class"]
        going = race_info["going"]

        # Get standard time
        standard_time = standard_times.get(distance, 0)

        # Get class adjustment
        class_adj = class_adjustments.get(race_class, 0)

        # Get going adjustment
        going_adj = going_adjustments.get(going, 0)

        # Calculate ratings
        ratings = []
        winning_time = None

        # Sort by position to find winner
        sorted_perfs = sorted(
            perfs,
            key=lambda p: (
                999 if not _is_valid_finish(p.get("position", ""))
                else int(p.get("position", "999"))
            )
        )

        if sorted_perfs:
            winner = sorted_perfs[0]
            if _is_valid_finish(winner.get("position", "")):
                winning_time = winner["finish_time_seconds"]

        for perf in sorted_perfs:
            position = perf.get("position", "")
            if not _is_valid_finish(position):
                continue

            finish_time = perf["finish_time_seconds"]

            # Calculate margin from winner (in lengths, approx 0.2s per length)
            if winning_time:
                margin_lengths = (finish_time - winning_time) / 0.2
            else:
                margin_lengths = 0

            # Base rating: 100 minus time behind standard (in pounds)
            # 1 second ~ 5-6 lengths ~ 1-1.5 lb at sprint, more at distance
            time_diff = finish_time - standard_time if standard_time > 0 else 0
            base_rating = 100 - (time_diff * 2)  # Simplified calculation

            # Apply class and going adjustments
            final_rating = int(base_rating + class_adj + going_adj - margin_lengths)

            ratings.append({
                "horse_id": perf.get("horse_id", ""),
                "horse_name": perf.get("horse_name", ""),
                "position": position,
                "finish_time": round(finish_time, 2),
                "margin_lengths": round(margin_lengths, 1),
                "speed_rating": final_rating,
            })

        result[race_id] = {
            "distance": distance,
            "class": race_class,
            "going": going,
            "winning_time": round(winning_time, 2) if winning_time else None,
            "standard_time": standard_time,
            "ratings": ratings,
        }

    return result


def generate_racing_summary(
    races: list[dict],
    performances: list[dict],
    horses: list[dict] | None = None,
    jockeys: list[dict] | None = None,
    trainers: list[dict] | None = None,
) -> dict:
    """Generate a comprehensive racing summary report.

    Combines all analytics into a single summary report.

    Args:
        races: List of race records.
        performances: List of performance records.
        horses: Optional list of horse profiles.
        jockeys: Optional list of jockey profiles.
        trainers: Optional list of trainer profiles.

    Returns:
        Comprehensive summary dictionary:
        ```python
        {
            "summary": {
                "total_races": int,
                "total_performances": int,
                "date_range": str,
                "racecourses": list[str],
            },
            "jockey_stats": dict,  # From calculate_jockey_performance
            "trainer_stats": dict,  # From calculate_trainer_performance
            "draw_bias": dict,      # From calculate_draw_bias
            "track_bias": dict,     # From calculate_track_bias
            "horse_form": dict,     # From calculate_horse_form
            "class_performance": dict,  # From calculate_class_performance
        }
        ```
    """
    # Basic summary stats
    racecourses = set()
    dates = set()

    for race in races:
        racecourses.add(race.get("racecourse", ""))
        dates.add(race.get("race_date", ""))

    summary = {
        "total_races": len(races),
        "total_performances": len(performances),
        "date_range": f"{min(dates) if dates else 'N/A'} to {max(dates) if dates else 'N/A'}",
        "racecourses": sorted(racecourses),
    }

    return {
        "summary": summary,
        "jockey_stats": calculate_jockey_performance(performances),
        "trainer_stats": calculate_trainer_performance(performances),
        "draw_bias": calculate_draw_bias(performances, races),
        "track_bias": calculate_track_bias(performances, races),
        "horse_form": calculate_horse_form(performances, horses),
        "class_performance": calculate_class_performance(performances, races),
    }
