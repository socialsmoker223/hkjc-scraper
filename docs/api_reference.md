# API Reference

This page provides a complete reference for all public functions exported by the `hkjc_scraper` package.

## Contents

- [Database Functions](#database-functions)
- [Analytics Functions](#analytics-functions)
- [Data Parsing Functions](#data-parsing-functions)
- [ID Extraction Functions](#id-extraction-functions)
- [Career Record Parsing](#career-record-parsing)
- [Profile Parsing Functions](#profile-parsing-functions)

---

## Database Functions

### `create_database(db_path: str | Path) -> None`

Create the SQLite database schema with all tables and indexes.

This function creates a new SQLite database at the specified path with all required tables, foreign keys, and indexes. If the database already exists, it will add any missing tables or indexes.

**Parameters:**
- `db_path` - Path to the database file. Will be created if it doesn't exist.

**Raises:**
- `sqlite3.Error` - If database creation fails.

**Example:**
```python
from hkjc_scraper import create_database

create_database("hkjc_racing.db")
# Database created with all tables and indexes
```

**Note:** Foreign key constraints are enabled by default. Referential integrity is enforced with `ON DELETE CASCADE` for child records.

---

### `get_db_connection(db_path: str | Path) -> sqlite3.Connection`

Get a database connection with foreign keys enabled.

**Parameters:**
- `db_path` - Path to the database file.

**Returns:**
- A SQLite connection with foreign keys enabled.

**Example:**
```python
from hkjc_scraper import get_db_connection

conn = get_db_connection("hkjc_racing.db")
cursor = conn.execute("SELECT * FROM races LIMIT 10")
conn.close()
```

---

## Analytics Functions

### `calculate_jockey_performance(performances: list[dict], recent_races: int = 10) -> dict`

Calculate performance statistics for jockeys.

Analyzes jockey performance across races including win rate, place rate, recent form, and performance by track.

**Parameters:**
- `performances` - List of performance records containing `jockey_id`, `jockey`, `position`, `race_id`, `draw`, `finish_time`.
- `recent_races` - Number of recent races to analyze for form calculation (default: 10).

**Returns:**
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

**Example:**
```python
from hkjc_scraper import calculate_jockey_performance

performances = [
    {"jockey_id": "J1", "jockey": "John Doe", "position": "1", "race_id": "2026-03-01-ST-1"},
    {"jockey_id": "J1", "jockey": "John Doe", "position": "2", "race_id": "2026-03-01-ST-2"},
]
result = calculate_jockey_performance(performances)
print(result["J1"]["win_rate"])  # 0.5
```

---

### `calculate_trainer_performance(performances: list[dict]) -> dict`

Calculate performance statistics for trainers.

**Parameters:**
- `performances` - List of performance records containing `trainer_id`, `trainer`, `position`, `race_id`.

**Returns:**
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

**Example:**
```python
from hkjc_scraper import calculate_trainer_performance

performances = [
    {"trainer_id": "T1", "trainer": "Jane Smith", "position": "1"},
    {"trainer_id": "T1", "trainer": "Jane Smith", "position": "3"},
]
result = calculate_trainer_performance(performances)
print(result["T1"]["win_rate"])  # 0.5
```

---

### `calculate_draw_bias(performances: list[dict], races: list[dict] | None = None) -> dict`

Analyze the impact of draw position on winning chances.

Calculates win rates by draw position for each track and distance range.

**Parameters:**
- `performances` - List of performance records with `draw`, `position`, `race_id`.
- `races` - Optional list of race records with `race_id`, `distance`, `racecourse`. If provided, enables distance-specific analysis.

**Returns:**
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

**Example:**
```python
from hkjc_scraper import calculate_draw_bias

performances = [
    {"draw": "1", "position": "1", "race_id": "2026-03-01-ST-1"},
    {"draw": "7", "position": "5", "race_id": "2026-03-01-ST-1"},
]
result = calculate_draw_bias(performances)
print(result["summary"]["best_draw_overall"])  # 1
```

---

### `calculate_track_bias(performances: list[dict], races: list[dict]) -> dict`

Analyze track biases including running position patterns and going preferences.

Determines which running positions lead to wins at different tracks and identifies going/surface combinations that favor certain running styles.

**Parameters:**
- `performances` - List of performance records with `race_id`, `position`, `running_position`.
- `races` - List of race records with `race_id`, `racecourse`, `going`, `surface`.

**Returns:**
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

**Example:**
```python
from hkjc_scraper import calculate_track_bias

races = [
    {"race_id": "2026-03-01-ST-1", "racecourse": "沙田", "going": "好", "surface": "草地"},
]
performances = [
    {"race_id": "2026-03-01-ST-1", "position": "1", "running_position": ["1", "1", "1"]},
]
result = calculate_track_bias(performances, races)
print(result["by_track"]["ST"]["early_leaders_win_rate"])  # 1.0
```

---

### `calculate_class_performance(performances: list[dict], races: list[dict]) -> dict`

Analyze horse performance when moving between classes.

Tracks how horses perform when racing in different classes compared to their previous race.

**Parameters:**
- `performances` - List of performance records with `horse_id`, `position`, `race_id`, `date` (if available).
- `races` - List of race records with `race_id`, `class`.

**Returns:**
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

**Example:**
```python
from hkjc_scraper import calculate_class_performance

races = [
    {"race_id": "R1", "class": "第四班"},
    {"race_id": "R2", "class": "第三班"},
]
performances = [
    {"horse_id": "H1", "race_id": "R1", "position": "1"},
    {"horse_id": "H1", "race_id": "R2", "position": "2"},
]
result = calculate_class_performance(performances, races)
```

---

### `calculate_horse_form(performances: list[dict], horses: list[dict] | None = None, recent_races: int = 6) -> dict`

Analyze recent form trends for horses.

Calculates recent performance patterns including consistency, preferred distance, and track preferences.

**Parameters:**
- `performances` - List of performance records with `horse_id`, `position`, `race_id`, `finish_time`.
- `horses` - Optional list of horse profiles with `horse_id`, `name`, `current_rating`.
- `recent_races` - Number of recent races to analyze (default: 6).

**Returns:**
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

**Example:**
```python
from hkjc_scraper import calculate_horse_form

performances = [
    {"horse_id": "H1", "horse_name": "Speedy", "position": "1", "race_id": "2026-03-01-ST-1"},
    {"horse_id": "H1", "horse_name": "Speedy", "position": "2", "race_id": "2026-02-15-ST-2"},
]
result = calculate_horse_form(performances)
print(result["H1"]["recent_form"])  # '12'
```

---

### `calculate_jockey_trainer_combination(performances: list[dict], min_partnerships: int = 3) -> dict`

Analyze win rates for specific jockey-trainer combinations.

Identifies profitable partnerships between jockeys and trainers.

**Parameters:**
- `performances` - List of performance records with `jockey_id`, `trainer_id`, `position`.
- `min_partnerships` - Minimum number of rides together to be included (default: 3).

**Returns:**
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

**Example:**
```python
from hkjc_scraper import calculate_jockey_trainer_combination

performances = [
    {"jockey_id": "J1", "trainer_id": "T1", "position": "1", "jockey": "John", "trainer": "Jane"},
    {"jockey_id": "J1", "trainer_id": "T1", "position": "2", "jockey": "John", "trainer": "Jane"},
]
result = calculate_jockey_trainer_combination(performances)
print(result["combinations"][0]["win_rate"])  # 0.5
```

---

### `calculate_distance_preference(performances: list[dict], races: list[dict]) -> dict`

Analyze horse performance by distance.

Identifies which distance ranges each horse performs best at.

**Parameters:**
- `performances` - List of performance records with `horse_id`, `position`, `race_id`.
- `races` - List of race records with `race_id`, `distance`.

**Returns:**
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

**Example:**
```python
from hkjc_scraper import calculate_distance_preference

races = [{"race_id": "R1", "distance": 1000}]
performances = [{"horse_id": "H1", "race_id": "R1", "position": "1"}]
result = calculate_distance_preference(performances, races)
```

---

### `calculate_speed_ratings(performances: list[dict], races: list[dict]) -> dict`

Calculate speed ratings based on finish times and class.

Generates speed ratings by adjusting finish times for class, distance, and going conditions.

**Parameters:**
- `performances` - List of performance records with `race_id`, `position`, `finish_time`, `horse_id`.
- `races` - List of race records with `race_id`, `distance`, `class`, `going`.

**Returns:**
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

**Example:**
```python
from hkjc_scraper import calculate_speed_ratings

races = [{"race_id": "R1", "distance": 1200, "class": "第四班", "going": "好"}]
performances = [{"horse_id": "H1", "race_id": "R1", "position": "1", "finish_time": "1:10.5"}]
result = calculate_speed_ratings(performances, races)
```

---

### `generate_racing_summary(races: list[dict], performances: list[dict], horses: list[dict] | None = None, jockeys: list[dict] | None = None, trainers: list[dict] | None = None) -> dict`

Generate a comprehensive racing summary report.

Combines all analytics into a single summary report.

**Parameters:**
- `races` - List of race records.
- `performances` - List of performance records.
- `horses` - Optional list of horse profiles.
- `jockeys` - Optional list of jockey profiles.
- `trainers` - Optional list of trainer profiles.

**Returns:**
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

**Example:**
```python
from hkjc_scraper import generate_racing_summary

summary = generate_racing_summary(races, performances, horses, jockeys, trainers)
print(f"Total races: {summary['summary']['total_races']}")
```

---

## Data Parsing Functions

### `clean_position(text: str | None) -> str`

Clean position text by extracting digits or preserving special status codes.

**Parameters:**
- `text` - Raw position text (e.g., "1", "1 ", "第一名", "DISQ", "DNF") or None.

**Returns:**
Cleaned position string containing digits, special status code, or empty string.

**Special status codes** (preserved as-is, case-insensitive):
- `DISQ` - Disqualified (取消資格)
- `DNF` - Did Not Finish (未有跑畢全程)
- `FE` - Fell (馬匹在賽事中跌倒)
- `PU` - Pulled Up (拉停)
- `TNP` - Took No Part (并無參賽競逐)
- `TO` - Tailed Off (遙遙落後)
- `UR` - Unseated Rider (騎師墮馬)
- `VOID` - Void Race (賽事無效)
- `WR`, `WV`, `WV-A`, `WX`, `WX-A`, `WXNR` - Various withdrawal codes

**Example:**
```python
from hkjc_scraper import clean_position

clean_position("1")          # "1"
clean_position("第一名")       # "1"
clean_position("1/2")        # "12"
clean_position("DISQ")       # "DISQ"
clean_position("DNF")        # "DNF"
clean_position("")           # ""
clean_position(None)         # ""
```

---

### `parse_rating(rating_text: str) -> dict[str, int] | None`

Parse rating text in format `(min-max)`.

**Parameters:**
- `rating_text` - Rating text like "(60-40)" or "(40-60)".

**Returns:**
Dictionary with `'min'` and `'max'` keys, or `None` if invalid format.

**Example:**
```python
from hkjc_scraper import parse_rating

parse_rating("(60-40)")   # {"min": 60, "max": 40}
parse_rating("(40-60)")   # {"min": 40, "max": 60}
parse_rating("60-40")     # None
parse_rating("")          # None
```

---

### `parse_prize(prize_text: str) -> int`

Parse prize money text to integer value.

**Parameters:**
- `prize_text` - Prize text like "HK$ 1,170,000" or "1,170,000".

**Returns:**
Prize amount as integer, or 0 if invalid.

**Example:**
```python
from hkjc_scraper import parse_prize

parse_prize("HK$ 1,170,000")  # 1170000
parse_prize("HK$ 1000000")    # 1000000
parse_prize("1,170,000")      # 1170000
parse_prize("")               # 0
```

---

### `parse_running_position(element: Any) -> list[str]`

Parse running position from HTML element containing div elements.

**Parameters:**
- `element` - HTML element with div children containing position text.

**Returns:**
List of position strings.

**Example:**
```python
from hkjc_scraper import parse_running_position

# Mock element with div children containing "1", "2", "3"
parse_running_position(mock_elem)  # ["1", "2", "3"]
```

---

### `generate_race_id(race_date: str, racecourse: str, race_no: int) -> str`

Generate a unique race ID from date, course, and race number.

**Parameters:**
- `race_date` - Date in YYYY/MM/DD or YYYY-MM-DD format.
- `racecourse` - "ST" for Sha Tin, "HV" for Happy Valley.
- `race_no` - Race number (1-11).

**Returns:**
Unique race ID in format "YYYY-MM-DD-CC-N".

**Example:**
```python
from hkjc_scraper import generate_race_id

generate_race_id("2026/03/01", "ST", 1)  # "2026-03-01-ST-1"
generate_race_id("2026/03/01", "HV", 5)  # "2026-03-01-HV-5"
```

---

### `parse_sectional_time_cell(cell_text: str) -> dict[str, int | str | float] | None`

Extract position, margin, time from a section cell.

The cell contains position, margin, and time on separate lines. Some cells may have extra 200m split times that should be ignored.

**Parameters:**
- `cell_text` - Cell text like "3\n1/2\n13.52" or "1\nN\n13.44".

**Returns:**
`{"position": int, "margin": str, "time": float}` or `None` if empty.

**Example:**
```python
from hkjc_scraper import parse_sectional_time_cell

parse_sectional_time_cell("3\n1/2\n13.52")  # {"position": 3, "margin": "1/2", "time": 13.52}
parse_sectional_time_cell("1\nN\n13.44")     # {"position": 1, "margin": "N", "time": 13.44}
```

---

## ID Extraction Functions

### `extract_horse_id(href: str | None) -> str | None`

Extract horse ID from href attribute.

**Parameters:**
- `href` - URL href attribute containing `horseid` parameter.

**Returns:**
Horse ID string, or `None` if not found.

**Example:**
```python
from hkjc_scraper import extract_horse_id

extract_horse_id("https://hkjc.com/racing/horse/horseid=H123&foo=bar")  # "H123"
extract_horse_id(None)   # None
extract_horse_id("")     # None
```

---

### `extract_jockey_id(href: str | None) -> str | None`

Extract jockey ID from href attribute.

**Parameters:**
- `href` - URL href attribute containing `jockeyid` parameter.

**Returns:**
Jockey ID string, or `None` if not found.

**Example:**
```python
from hkjc_scraper import extract_jockey_id

extract_jockey_id("https://hkjc.com/racing/jockey/jockeyid=PZ&foo=bar")  # "PZ"
extract_jockey_id(None)   # None
```

---

### `extract_trainer_id(href: str | None) -> str | None`

Extract trainer ID from href attribute.

**Parameters:**
- `href` - URL href attribute containing `trainerid` parameter.

**Returns:**
Trainer ID string, or `None` if not found.

**Example:**
```python
from hkjc_scraper import extract_trainer_id

extract_trainer_id("https://hkjc.com/racing/trainer/trainerid=NPC&foo=bar")  # "NPC"
extract_trainer_id(None)   # None
```

---

## Career Record Parsing

### `parse_career_record(record_str: str) -> dict | None`

Parse career record string into wins, places, shows, total.

**Parameters:**
- `record_str` - Career record like "2-0-2-17" (wins-places-shows-total).

**Returns:**
`{"wins": int, "places": int, "shows": int, "total": int}` or `None`.

**Example:**
```python
from hkjc_scraper import parse_career_record

parse_career_record("2-0-2-17")  # {"wins": 2, "places": 0, "shows": 2, "total": 17}
parse_career_record("")          # None
```

---

## Profile Parsing Functions

### `parse_horse_profile(response: Any, horse_id: str, horse_name: str) -> dict`

Parse horse profile page response.

The HKJC website uses a 3-column table structure:
- Column 0: Label (e.g., "出生地 / 馬齡")
- Column 1: Separator (":")
- Column 2: Value (e.g., "紐西蘭 / 4")

**Parameters:**
- `response` - Scrapling response object (has `.css()` method and `.text` attribute).
- `horse_id` - Horse ID from href.
- `horse_name` - Horse name from race results.

**Returns:**
Dictionary with horse profile data including:
- Basic info: `horse_id`, `name`, `country_of_birth`, `age`, `colour`, `gender`
- Pedigree: `sire`, `dam`, `damsire`
- Ownership: `trainer`, `owner`
- Ratings: `current_rating`, `initial_rating`
- Prize money: `season_prize`, `total_prize`
- Career stats: `wins`, `places`, `shows`, `total` (flattened)
- Import info: `location`, `import_type`, `import_date` (if applicable)

**Example:**
```python
from hkjc_scraper import parse_horse_profile

profile = parse_horse_profile(response, "H123", "Speedy Horse")
print(profile["country_of_birth"])  # e.g., "紐西蘭"
print(profile["current_rating"])    # e.g., 85
```

---

### `parse_jockey_profile(response: Any, jockey_id: str, jockey_name: str) -> dict`

Parse jockey profile page response.

**Parameters:**
- `response` - Scrapling response object (has `.css()` method and `.text` attribute).
- `jockey_id` - Jockey ID from href.
- `jockey_name` - Jockey name from race results.

**Returns:**
Dictionary with jockey profile data including `jockey_id`, `name`, `age`, `background`, `achievements`, `career_wins`, `career_win_rate`, and `season_stats` (dict with `wins`, `places`, `win_rate`, `prize_money`).

**Example:**
```python
from hkjc_scraper import parse_jockey_profile

profile = parse_jockey_profile(response, "JZ", "John Smith")
print(profile["age"])           # e.g., 35
print(profile["career_wins"])   # e.g., 150
```

---

### `parse_trainer_profile(response: Any, trainer_id: str, trainer_name: str) -> dict`

Parse trainer profile page response.

**Parameters:**
- `response` - Scrapling response object (has `.css()` method and `.text` attribute).
- `trainer_id` - Trainer ID from href.
- `trainer_name` - Trainer name from race results.

**Returns:**
Dictionary with trainer profile data including `trainer_id`, `name`, `age`, `background`, `achievements`, `career_wins`, `career_win_rate`, and `season_stats` (dict with `wins`, `places`, `shows`, `fourth`, `total_runners`, `win_rate`, `prize_money`).

**Example:**
```python
from hkjc_scraper import parse_trainer_profile

profile = parse_trainer_profile(response, "NT", "Jane Trainer")
print(profile["career_wins"])   # e.g., 320
```
