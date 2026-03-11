# HKJC Scraper - Claude Context

This file contains project-specific context for Claude Code to work effectively on this codebase.

## Project Overview

**HKJC Racing Scraper** extracts horse racing data from the Hong Kong Jockey Club (HKJC) website using the Scrapling Spider framework.

- **Language:** Python 3.13+
- **Framework:** Scrapling (async web scraping)
- **Testing:** pytest with asyncio support
- **Package:** `hkjc_scraper`

## Module Organization

The codebase is organized into focused modules under `src/hkjc_scraper/`:

### Core Modules

| Module | Purpose | Key Functions |
|--------|---------|---------------|
| `spider.py` | Main spider implementation | `HKJCRacingSpider` class |
| `cli.py` | Command-line interface | `main()` entry point with `--export-sqlite`, `--analyze` flags |
| `database.py` | SQLite database layer | `create_database`, `export_json_to_db`, `load_from_db`, `import_*` functions |
| `analytics.py` | Statistical analysis | `calculate_jockey_performance`, `calculate_draw_bias`, `generate_racing_summary`, etc. |
| `__init__.py` | Public API exports | 40+ exported functions |

### Parser Modules

| Module | Purpose | Key Functions |
|--------|---------|---------------|
| `data_parsers.py` | Data parsing utilities | `clean_position`, `parse_rating`, `parse_prize`, `parse_running_position`, `generate_race_id`, `parse_sectional_time_cell` |
| `id_parsers.py` | ID extraction from URLs | `extract_horse_id`, `extract_jockey_id`, `extract_trainer_id` |
| `common.py` | Shared helper functions | `parse_career_record`, `_extract_text_after_label`, `_parse_career_stats_from_elements` |
| `horse_parsers.py` | Horse profile parsing | `parse_horse_profile` |
| `jockey_trainer_parsers.py` | Jockey/trainer parsing | `parse_jockey_profile`, `parse_trainer_profile` |

## Key Patterns and Conventions

### HTML Parsing (HKJC Specific)

HKJC uses a **3-column table structure** for profile pages:

```python
# HKJC profile table structure:
# Column 0: Label (e.g., "出生地 / 馬齡")
# Column 1: Separator (":")
# Column 2: Value (e.g., "紐西蘭 / 4")
```

**Important:** Some values are inside nested `<a>` tags. When `.text` returns empty, extract from the nested link:

```python
value_cell = cells[2]
value = value_cell.text.strip()

# If cell.text is empty, try extracting from nested <a> tag
if not value:
    links = value_cell.css("a")
    if links:
        value = links[0].text.strip()
```

### CSS Selectators Over Regex

**Prefer CSS selectors over regex** for parsing HTML:

```python
# Good: CSS selectors
all_tds = response.css("td")
result = _extract_text_after_label(all_tds, "背景：")

# Avoid: Regex on full HTML
# This is fragile and should be avoided
```

### Career Record Parsing

Career records follow the pattern: `wins-places-shows-total` (e.g., "2-0-2-17")

The label may have an asterisk suffix: `冠-亞-季-總出賽次數*`

### Public API

All public functions are exported via `__init__.py`. Import from the top-level package:

```python
from hkjc_scraper import (
    clean_position,
    parse_horse_profile,
    parse_jockey_profile,
    # Database
    create_database,
    export_json_to_db,
    load_from_db,
    # Analytics
    calculate_jockey_performance,
    calculate_draw_bias,
    # ... etc
)
```

**Do NOT** import directly from submodules in user code or application code.

### Database Module (`database.py`)

SQLite is built into Python 3.13+ - no external dependencies needed.

**Core Functions:**
- `create_database(db_path)` - Creates all tables with indexes
- `get_db_connection(db_path)` - Returns connection with FKs enabled
- `export_json_to_db(data_dir, db_path)` - Bulk export from JSON files

**Import Functions** (one per table):
- `import_races(data, conn)` - Race metadata
- `import_performance(data, conn)` - Horse results per race
- `import_dividends(data, conn)` - Payout information
- `import_incidents(data, conn)` - Race incidents
- `import_horses(data, conn)` - Horse profiles
- `import_jockeys(data, conn)` - Jockey profiles
- `import_trainers(data, conn)` - Trainer profiles
- `import_sectional_times(data, conn)` - Sectional time data

**Query Functions:**
- `load_from_db(db_path, table, where_clause, params)` - Load data as dicts

**Database Schema Features:**
- Foreign key constraints with ON DELETE CASCADE/SET NULL
- Indexes on frequently queried columns (race_date, horse_id, jockey_id, trainer_id)
- Complex types serialized as JSON (rating, sectional_times, running_position)
- Unique constraints to prevent duplicates

### Analytics Module (`analytics.py`)

**Performance Analysis:**
- `calculate_jockey_performance(performances)` - Win rate, rides, places per jockey
- `calculate_trainer_performance(performances)` - Win rate, runners per trainer
- `calculate_horse_form(performances, horses, recent_races)` - Recent form analysis

**Track & Draw Analysis:**
- `calculate_draw_bias(performances, races)` - Win rate by draw position
- `calculate_track_bias(performances, races)` - Performance by going/surface
- `calculate_distance_preference(performances, races)` - Results by distance

**Combination Analysis:**
- `calculate_jockey_trainer_combination(performances)` - JT pair performance
- `calculate_class_performance(performances, races)` - Results by race class

**Speed & Summary:**
- `calculate_speed_ratings(performances, races)` - Relative speed ratings
- `generate_racing_summary(performances, races)` - Overall statistics

## Testing

### Running Tests

```bash
# Unit tests only (no network requests)
uv run pytest tests/ -v -m "not integration"

# Integration tests (makes network requests)
uv run pytest tests/ -v -m integration

# All tests
uv run pytest tests/ -v
```

### Test Organization

- `tests/test_parsers.py` - Tests for `data_parsers.py` functions
- `tests/test_profile_parsers.py` - Tests for all profile parsers
- `tests/test_spider.py` - Tests for `HKJCRacingSpider` class
- `tests/integration/` - End-to-end integration tests

### Test Markers

- `@pytest.mark.integration` - Marks integration tests that make network requests

## Common Tasks

### Adding a New Parser Function

1. Add the function to the appropriate parser module
2. Add comprehensive docstring with Args, Returns, Examples
3. Add type hints
4. Write tests in the corresponding test file
5. Export from `__init__.py` if it's part of the public API

### Updating Profile Parsers

Profile parsers use the 3-column table pattern. Follow the existing structure:

```python
for row in rows:
    cells = row.css("td")
    if len(cells) >= 3:
        label = cells[0].text
        value_cell = cells[2]
        value = value_cell.text.strip()

        # Handle nested <a> tags
        if not value:
            links = value_cell.css("a")
            if links:
                value = links[0].text.strip()
```

### Running the Scraper

```bash
# Crawl specific date and racecourse
uv run hkjc-scrape --date 2026/03/01 --racecourse ST

# Auto-discover latest race
uv run hkjc-scrape --racecourse ST

# Export to SQLite database after scraping
uv run hkjc-scrape --date 2026/03/01 --racecourse ST --export-sqlite

# Run analytics on existing data
uv run hkjc-scrape --analyze
```

### Scraping Historical Races

Historical races (pre-2024) are not in the dropdown but accessible via direct URLs:

```bash
# Discover races first
uv run hkjc-scrape --discover --start-date 2015/01/01 --end-date 2015/12/31

# Then scrape discovered dates
uv run hkjc-scrape --start-date 2015/01/01 --end-date 2015/12/31 --racecourse ST
```

The `data/.discovered_dates.json` cache stores discovered dates for fast re-runs.

### CLI Options

**Scraping Options:**
- `--date YYYY/MM/DD` - Specific race date to scrape
- `--latest` - Scrape today's races (auto-discovers dates)
- `--racecourse ST|HV` - Racecourse filter (default: ST)
- `--start-date YYYY/MM/DD` - Start date for batch discovery/scraping
- `--end-date YYYY/MM/DD` - End date for batch discovery/scraping
- `--discover` - Only discover race dates without scraping
- `--auto-all` - Discover all historical races (2000-2024)
- `--refresh-cache` - Re-verify cached dates during discovery

**Database Export:**
- `--export-sqlite` - Export JSON data to SQLite after scraping
- `--db-path PATH` - Custom database path (default: data/hkjc_racing.db)

**Analytics:**
- `--analyze` - Run analytics on existing data
- `--analyze-format text|json` - Output format for analytics (default: text)

**Output:**
- `--output DIR` - Output directory for JSON files (default: data)
- `--format json|csv` - Output format (for CSV export feature)

## Data Model

### Output Tables

#### `races` - Race metadata
| Field | Type | Description |
|-------|------|-------------|
| `race_id` | string | Unique ID (format: YYYY-MM-DD-CC-N) |
| `race_date` | string | Race date (YYYY/MM/DD format) |
| `race_no` | int | Race number (1-11) |
| `racecourse` | string | "沙田" or "谷草" |
| `class` | string | Race class (e.g., "第四班") |
| `distance` | int | Race distance in meters |
| `rating` | object | `{"high": int, "low": int}` |
| `going` | string | Track condition |
| `surface` | string | "草地" or "全天候" |
| `track` | string | Full track description |
| `sectional_times` | array | List of sectional time strings |
| `prize_money` | int | Total prize money |
| `race_name` | string | Race name (optional) |

#### `performance` - Horse results per race
| Field | Type | Description |
|-------|------|-------------|
| `race_id` | string | Foreign key to races |
| `position` | string | Finishing position ("1", "2", "DISQ", "DNF", "PU", etc.) |
| `horse_no` | string | Horse number |
| `horse_id` | string | Horse ID (nullable) |
| `horse_name` | string | Horse name |
| `jockey` | string | Jockey name |
| `jockey_id` | string | Jockey ID (nullable) |
| `trainer` | string | Trainer name |
| `trainer_id` | string | Trainer ID (nullable) |
| `actual_weight` | string | Carried weight |
| `body_weight` | string | Horse weight |
| `draw` | string | Draw position |
| `margin` | string | Margin to winner |
| `running_position` | array | List of running positions |
| `finish_time` | string | Finishing time |
| `win_odds` | string | Winning odds |

#### `dividends` - Payout information
| Field | Type | Description |
|-------|------|-------------|
| `race_id` | string | Foreign key to races |
| `pool` | string | Pool type (獨贏, 位置, 連贏, etc.) |
| `winning_combination` | string | Winning numbers |
| `payout` | string | Payout amount |

#### `incidents` - Race incident reports
| Field | Type | Description |
|-------|------|-------------|
| `race_id` | string | Foreign key to races |
| `position` | string | Horse position |
| `horse_no` | string | Horse number |
| `horse_name` | string | Horse name |
| `incident_report` | string | Incident description |

#### `horses` - Horse profiles
| Field | Type | Description |
|-------|------|-------------|
| `horse_id` | string | Unique horse ID |
| `name` | string | Horse name |
| `country_of_birth` | string | Birth country |
| `age` | string | Horse age |
| `colour` | string | Horse colour |
| `gender` | string | Horse gender |
| `sire` | string | Sire name |
| `dam` | string | Dam name |
| `damsire` | string | Damsire name |
| `trainer` | string | Trainer name |
| `owner` | string | Owner name |
| `current_rating` | int | Current rating |
| `initial_rating` | int | Season start rating |
| `season_prize` | int | Season prize money |
| `total_prize` | int | Career prize money |
| `wins` | int | Career wins |
| `places` | int | Career places |
| `shows` | int | Career shows |
| `total` | int | Career total races |
| `location` | string | Import location |
| `import_type` | string | Import type |
| `import_date` | string | Import date |

#### `jockeys` - Jockey profiles
| Field | Type | Description |
|-------|------|-------------|
| `jockey_id` | string | Unique jockey ID |
| `name` | string | Jockey name |
| `age` | string | Jockey age |
| `background` | string | Background info |
| `achievements` | string | Achievements |
| `career_wins` | int | Career wins |
| `career_win_rate` | string | Career win rate |
| `season_stats` | object | `{wins, places, win_rate, prize_money}` |

#### `trainers` - Trainer profiles
| Field | Type | Description |
|-------|------|-------------|
| `trainer_id` | string | Unique trainer ID |
| `name` | string | Trainer name |
| `age` | string | Trainer age |
| `background` | string | Background info |
| `achievements` | string | Achievements |
| `career_wins` | int | Career wins |
| `career_win_rate` | string | Career win rate |
| `season_stats` | object | `{wins, places, shows, fourth, total_runners, win_rate, prize_money}` |

#### `sectional_times` - Per-horse sectional time data
| Field | Type | Description |
|-------|------|-------------|
| `race_id` | string | Foreign key to races |
| `horse_no` | string | Horse number |
| `section_number` | int | Section number |
| `position` | int | Position at section |
| `margin` | string | Margin at section |
| `time` | float | Sectional time |

### Output Format

Data is saved as JSON with UTF-8 encoding in the `data/` directory:
```
data/
├── races_2026-03-01.json
├── performance_2026-03-01.json
├── dividends_2026-03-01.json
├── incidents_2026-03-01.json
├── horses_2026-03-01.json
├── jockeys_2026-03-01.json
├── trainers_2026-03-01.json
└── sectional_times_2026-03-01.json
```

## Important Gotchas

### ID Extraction

IDs are extracted from URL query parameters:
- Horse ID: `horseid=XXX`
- Jockey ID: `jockeyid=XXX`
- Trainer ID: `trainerid=XXX`

The extraction functions use compiled regex patterns for performance.

### Position Parsing

The `clean_position` function handles multiple position formats:

1. **Special status codes** - Preserved as-is (case-insensitive):
   - `DISQ` - Disqualified (取消資格)
   - `DNF` - Did Not Finish (未有跑畢全程)
   - `FE` - Fell (馬匹在賽事中跌倒)
   - `ML` - Multiple Lengths (多個馬位)
   - `PU` - Pulled Up (拉停)
   - `TNP` - Took No Part (并無參賽競逐)
   - `TO` - Tailed Off (遙遙落後)
   - `UR` - Unseated Rider (騎師墮馬)
   - `VOID` - Void Race (賽事無效)
   - `WR` - Withdrawn by Starter (司閘員著令退出)
   - `WV` - Withdrawn Veterinary (因健康理由宣佈退出)
   - `WV-A` - Withdrawn Veterinary After Weigh-in
   - `WX` - Withdrawn Stewards (競賽董事小組著令退出)
   - `WX-A` - Withdrawn Stewards After Weigh-in
   - `WXNR` - Withdrawn Stewards No Runner

2. **Chinese numerals** - Mapped to digits:
   - 一 → 1, 二 → 2, 三 → 3, etc.

3. **Numeric positions** - Extracted from strings

See: https://racing.hkjc.com/zh-hk/local/page/special-race-index

### Chinese Numerals

### Rating Format

Ratings are in format `(min-max)` e.g., "(60-40)" → `{"min": 60, "max": 40}`

### Prize Money

Prize money may include:
- Currency symbol: `HK$`
- Commas: `1,170,000`
- Must be cleaned before int conversion

### Async/Await

The spider uses async/await. When working with `HKJCRacingSpider`:

```python
import asyncio
from hkjc_scraper.spider import HKJCRacingSpider

async def main():
    spider = HKJCRacingSpider(dates=["2026/03/01"], racecourse="ST")
    result = await spider.run()
    # Process result.items

asyncio.run(main())
```

## Code Style

- **PEP 8** compliant
- **Type hints** required for all function signatures
- **Docstrings** required for all public functions (Google style)
- **Line length** ≤ 100 characters
- **Import order**: stdlib → third-party → local

## Git Workflow

1. Create feature branch from `master`
2. Make atomic commits with clear messages
3. Run tests before committing
4. PR to `master` for review

### Commit Message Format

```
<type>: <description>

<optional detailed description>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`
