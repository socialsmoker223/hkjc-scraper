# HKJC Racing Scraper - User Guide

Extract horse racing data from the Hong Kong Jockey Club (HKJC) website.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Common Workflows](#common-workflows)
  - [Scraping a Specific Date](#scraping-a-specific-date)
  - [Scraping Today's Races](#scraping-todays-races)
  - [Historical Race Discovery](#historical-race-discovery)
  - [Scraping Historical Data](#scraping-historical-data)
- [Understanding Output Files](#understanding-output-files)
- [Using the Database Module](#using-the-database-module)
- [CLI Reference](#cli-reference)
- [Data Model Reference](#data-model-reference)
- [Tips and Best Practices](#tips-and-best-practices)

---

## Installation

### Prerequisites

- Python 3.13 or later
- [uv](https://github.com/astral-sh/uv) (recommended Python package manager)

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/hkjc-scraper.git
cd hkjc-scraper

# Install dependencies with uv
uv sync

# Install with test dependencies (optional)
uv sync --extra test
```

### Verification

```bash
# Verify installation
uv run hkjc-scrape --help
```

---

## Quick Start

### Scrape Your First Race

```bash
# Scrape Sha Tin races for a specific date
uv run hkjc-scrape --date 2026/03/01 --racecourse ST
```

**Expected output:**

```
Saved 11 races records to data/races_2026-03-01.json
Saved 143 performance records to data/performance_2026-03-01.json
Saved 88 dividends records to data/dividends_2026-03-01.json
Saved 35 incidents records to data/incidents_2026-03-01.json

Summary:
  races: 11 records
  performance: 143 records
  dividends: 88 records
  incidents: 35 records
  Total requests: 11
```

### Scrape Today's Races

```bash
# Auto-discover and scrape today's races
uv run hkjc-scrape --latest
```

---

## Common Workflows

### Scraping a Specific Date

```bash
# Scrape Sha Tin (ST) races
uv run hkjc-scrape --date 2026/03/01 --racecourse ST

# Scrape Happy Valley (HV) races
uv run hkjc-scrape --date 2026/03/01 --racecourse HV
```

**Date format:** Must be in `YYYY/MM/DD` format.

**Racecourse codes:**
- `ST` - Sha Tin (沙田)
- `HV` - Happy Valley (谷草)

### Scraping Today's Races

The `--latest` flag automatically discovers today's races and scrapes them:

```bash
# Scrape all races today (both ST and HV)
uv run hkjc-scrape --latest

# Scrape only Sha Tin races today
uv run hkjc-scrape --latest --racecourse ST
```

### Historical Race Discovery

Historical races (pre-2024) are not shown in the website dropdown but are accessible via direct URLs. The scraper can discover these dates:

```bash
# Discover races for a date range
uv run hkjc-scrape --discover --start-date 2015/01/01 --end-date 2015/12/31
```

**Expected output:**

```
Discovering race dates from 2015/01/01 to 2015/12/31...
Discovered 89 race dates:
  2015/01/01 @ ST (11 races)
  2015/01/07 @ HV (8 races)
  2015/01/11 @ ST (10 races)
  ...
```

**Cached discovery:** Results are cached in `data/.discovered_dates.json`. Subsequent runs are instant.

```bash
# Re-verify cached dates (refresh from website)
uv run hkjc-scrape --discover --start-date 2015/01/01 --refresh-cache

# Discover all historical races (2000-2024)
# WARNING: This takes a long time!
uv run hkjc-scrape --discover --auto-all
```

### Scraping Historical Data

After discovering dates, scrape the actual race data:

```bash
# Scrape a date range (uses discovered dates)
uv run hkjc-scrape --start-date 2015/01/01 --end-date 2015/03/31 --racecourse ST

# Output is saved to batch files
# data/races_batch.json
# data/performance_batch.json
# etc.
```

**Important:** Racing seasons run from September to July. August is typically the off-season with only overseas races.

---

## Understanding Output Files

### File Structure

All output files are saved in the `data/` directory:

```
data/
├── races_2026-03-01.json       # Race metadata
├── performance_2026-03-01.json # Horse performance per race
├── dividends_2026-03-01.json   # Payout information
├── incidents_2026-03-01.json   # Race incident reports
├── horses_2026-03-01.json      # Horse profiles
├── jockeys_2026-03-01.json     # Jockey profiles
├── trainers_2026-03-01.json    # Trainer profiles
└── sectional_times_2026-03-01.json  # Per-horse sectional times
```

**Batch mode** (when using `--start-date`):
- Files are named `*_batch.json` instead of `*_YYYY-MM-DD.json`

### Example: races_2026-03-01.json

```json
[
  {
    "race_id": "2026-03-01-ST-1",
    "race_date": "2026/03/01",
    "race_no": 1,
    "racecourse": "沙田",
    "class": "第四班",
    "distance": 1200,
    "going": "好地",
    "surface": "草地",
    "track": "草地 - \"A\" 賽道",
    "rating": {"high": 60, "low": 40},
    "sectional_times": ["24.68", "23.03", "22.81", "22.76"],
    "prize_money": 1170000,
    "race_name": "讓賽"
  }
]
```

### Example: performance_2026-03-01.json

```json
[
  {
    "race_id": "2026-03-01-ST-1",
    "position": "1",
    "horse_no": "1",
    "horse_id": "C123",
    "horse_name": "GOOD Luck",
    "jockey": "Moreira",
    "jockey_id": "BAC",
    "trainer": "Mo",
    "trainer_id": "MY",
    "actual_weight": "133",
    "body_weight": "1076",
    "draw": "7",
    "margin": "",
    "running_position": ["3", "3", "2", "1"],
    "finish_time": "1.09.28",
    "win_odds": "15"
  }
]
```

### Race ID Format

All records use `race_id` as a foreign key. Format: `YYYY-MM-DD-CC-N`

- `YYYY-MM-DD`: Race date
- `CC`: Racecourse (ST or HV)
- `N`: Race number (1-11)

Example: `2026-03-01-ST-1` = Sha Tin Race 1 on March 1, 2026

### Position Codes

Special position codes (non-finishing):

| Code | Meaning | Chinese |
|------|---------|---------|
| DISQ | Disqualified | 取消資格 |
| DNF | Did Not Finish | 未有跑畢全程 |
| FE | Fell | 馬匹在賽事中跌倒 |
| PU | Pulled Up | 拉停 |
| TNP | Took No Part | 并無參賽競逐 |
| TO | Tailed Off | 遙遙落後 |
| UR | Unseated Rider | 騎師墮馬 |
| WV | Withdrawn Veterinary | 因健康理由宣佈退出 |

---

## Using the Database Module

The database module provides SQLite storage for racing data with proper schema, indexes, and foreign keys.

### Creating a Database

```python
from hkjc_scraper import create_database

# Create database schema
create_database("data/hkjc_racing.db")
```

This creates all tables with proper indexes:
- `races` - Race metadata
- `horses` - Horse profiles
- `jockeys` - Jockey profiles
- `trainers` - Trainer profiles
- `performance` - Horse results per race
- `dividends` - Payout information
- `incidents` - Race incident reports
- `sectional_times` - Per-horse sectional times

### Exporting JSON to SQLite

```python
import json
import sqlite3
from pathlib import Path
from hkjc_scraper import get_db_connection

# Load JSON data
with open("data/races_2026-03-01.json") as f:
    races = json.load(f)

# Insert into database
conn = get_db_connection("data/hkjc_racing.db")
cursor = conn.cursor()

for race in races:
    # Convert rating dict to JSON string
    rating = json.dumps(race["rating"]) if race.get("rating") else None
    sectional_times = json.dumps(race["sectional_times"]) if race.get("sectional_times") else None

    cursor.execute("""
        INSERT OR REPLACE INTO races
        (race_id, race_date, race_no, racecourse, class, distance,
         going, surface, track, rating, sectional_times, prize_money, race_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        race["race_id"], race["race_date"], race["race_no"],
        race["racecourse"], race.get("class"), race.get("distance"),
        race.get("going"), race.get("surface"), race.get("track"),
        rating, sectional_times, race.get("prize_money", 0),
        race.get("race_name")
    ))

conn.commit()
conn.close()
```

### Querying the Database

```python
import sqlite3
from hkjc_scraper import get_db_connection

conn = get_db_connection("data/hkjc_racing.db")

# Find all races for a specific date
cursor = conn.execute("""
    SELECT * FROM races
    WHERE race_date = '2026/03/01'
    ORDER BY race_no
""")

for row in cursor.fetchall():
    print(row)

# Find winners by jockey
cursor = conn.execute("""
    SELECT p.jockey, COUNT(*) as wins
    FROM performance p
    WHERE p.position = '1'
    GROUP BY p.jockey
    ORDER BY wins DESC
    LIMIT 10
""")

conn.close()
```

---

## CLI Reference

### Options

| Option | Description |
|--------|-------------|
| `--date DATE` | Specific race date (YYYY/MM/DD format) |
| `--latest` | Scrape today's races (auto-discovers dates) |
| `--racecourse {ST,HV}` | Racecourse: ST (Sha Tin) or HV (Happy Valley) |
| `--output DIR` | Output directory (default: `data`) |
| `--discover` | Discover historical race dates (don't scrape) |
| `--start-date DATE` | Start date for discovery/scraping |
| `--end-date DATE` | End date for discovery/scraping |
| `--auto-all` | Discover all races from 2000-2024 (slow!) |
| `--refresh-cache` | Re-verify cached dates during discovery |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |

---

## Data Model Reference

### Tables

#### races
Race metadata including date, course, distance, and track conditions.

| Field | Type | Description |
|-------|------|-------------|
| race_id | string | Unique ID (YYYY-MM-DD-CC-N) |
| race_date | string | Race date (YYYY/MM/DD) |
| race_no | int | Race number (1-11) |
| racecourse | string | "沙田" or "谷草" |
| class | string | Race class (e.g., "第四班") |
| distance | int | Distance in meters |
| going | string | Track condition |
| surface | string | "草地" or "全天候" |
| track | string | Full track description |
| rating | object | {"high": int, "low": int} |
| sectional_times | array | List of sectional time strings |
| prize_money | int | Total prize money |
| race_name | string | Race name (optional) |

#### performance
Horse results for each race.

| Field | Type | Description |
|-------|------|-------------|
| race_id | string | Foreign key to races |
| position | string | Finishing position ("1", "2", "DISQ", etc.) |
| horse_no | string | Horse number |
| horse_id | string | Horse ID (nullable) |
| horse_name | string | Horse name |
| jockey | string | Jockey name |
| jockey_id | string | Jockey ID (nullable) |
| trainer | string | Trainer name |
| trainer_id | string | Trainer ID (nullable) |
| actual_weight | string | Carried weight |
| body_weight | string | Horse weight |
| draw | string | Draw position |
| margin | string | Margin to winner |
| running_position | array | List of running positions |
| finish_time | string | Finishing time |
| win_odds | string | Winning odds |

#### dividends
Payout information by pool type.

| Field | Type | Description |
|-------|------|-------------|
| race_id | string | Foreign key to races |
| pool | string | Pool type (獨贏, 位置, 連贏, etc.) |
| winning_combination | string | Winning numbers |
| payout | string | Payout amount |

#### incidents
Race incident reports.

| Field | Type | Description |
|-------|------|-------------|
| race_id | string | Foreign key to races |
| position | string | Horse position |
| horse_no | string | Horse number |
| horse_name | string | Horse name |
| incident_report | string | Incident description |

#### horses
Horse profiles with breeding, stats, and ownership.

| Field | Type | Description |
|-------|------|-------------|
| horse_id | string | Unique horse ID |
| name | string | Horse name |
| country_of_birth | string | Birth country |
| age | string | Horse age |
| colour | string | Horse colour |
| gender | string | Horse gender |
| sire | string | Sire name |
| dam | string | Dam name |
| damsire | string | Damsire name |
| trainer | string | Trainer name |
| owner | string | Owner name |
| current_rating | int | Current rating |
| initial_rating | int | Season start rating |
| season_prize | int | Season prize money |
| total_prize | int | Career prize money |
| wins | int | Career wins |
| places | int | Career places |
| shows | int | Career shows |
| total | int | Career total races |

#### jockeys
Jockey profiles with career statistics.

| Field | Type | Description |
|-------|------|-------------|
| jockey_id | string | Unique jockey ID |
| name | string | Jockey name |
| age | string | Jockey age |
| background | string | Background info |
| achievements | string | Achievements |
| career_wins | int | Career wins |
| career_win_rate | string | Career win rate |
| season_stats | object | {wins, places, win_rate, prize_money} |

#### trainers
Trainer profiles with career statistics.

| Field | Type | Description |
|-------|------|-------------|
| trainer_id | string | Unique trainer ID |
| name | string | Trainer name |
| age | string | Trainer age |
| background | string | Background info |
| achievements | string | Achievements |
| career_wins | int | Career wins |
| career_win_rate | string | Career win rate |
| season_stats | object | {wins, places, shows, fourth, total_runners, win_rate, prize_money} |

#### sectional_times
Per-horse sectional time data.

| Field | Type | Description |
|-------|------|-------------|
| race_id | string | Foreign key to races |
| horse_no | string | Horse number |
| section_number | int | Section number |
| position | int | Position at section |
| margin | string | Margin at section |
| time | float | Sectional time |

---

## Tips and Best Practices

1. **Start with discovery** - Before scraping large date ranges, run `--discover` first to see what data is available.

2. **Check the cache** - Discovery results are cached in `data/.discovered_dates.json`. Delete this file to force fresh discovery.

4. **Racing seasons** - Remember that HKJC racing seasons run September to July. August typically has no local racing.

5. **Data freshness** - Race results are usually available within an hour after the last race completes.

6. **Profile scraping** - Horse, jockey, and trainer profiles are only available when explicitly scraping races that include links to profiles.
