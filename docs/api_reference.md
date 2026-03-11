# API Reference

This page provides a complete reference for all public functions exported by the `hkjc_scraper` package.

## Contents

- [Database Functions](#database-functions)
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
