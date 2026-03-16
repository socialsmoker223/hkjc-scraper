# HKJC Racing Scraper

Extract horse racing data from Hong Kong Jockey Club (HKJC) using Scrapling Spider.

## Features

- Race results with horse details, jockey, trainer
- Dividends (Win, Place, Quinella, Tierce, Quartet, etc.)
- Incident reports for each race
- Historical data (auto-discover race dates)
- Profile scraping (horse, jockey, trainer profiles with stats)
- Async crawling with concurrent requests
- Normalized Supabase-compatible output
- Sectional times (per-horse, per-section position and time data)
- PostgreSQL database export (via Docker Compose)
- Analytics module for performance analysis and insights

## Module Organization

The scraper is organized into focused modules:

- **data_parsers.py** - General data parsing utilities (positions, ratings, prizes, race IDs)
- **id_parsers.py** - ID extraction from HKJC URLs (horse, jockey, trainer)
- **common.py** - Shared helper functions (career record parsing)
- **horse_parsers.py** - Horse profile parsing
- **jockey_trainer_parsers.py** - Jockey and trainer profile parsing
- **spider.py** - Main spider implementation
- **cli.py** - Command-line interface
- **database.py** - PostgreSQL database schema and import/export functions
- **analytics.py** - Statistical analysis functions for racing data

### Public API

The `__init__.py` exports all public functions. Import from the top-level package:

```python
from hkjc_scraper import (
    clean_position,
    parse_horse_profile,
    parse_jockey_profile,
    # ... etc
)
```

## Installation

```bash
uv sync --extra test
```

## Usage

### CLI

```bash
# Crawl specific date
uv run hkjc-scrape --date 2026/03/01 --racecourse ST

# Discover and crawl latest race
uv run hkjc-scrape --racecourse ST

# Export to PostgreSQL database after scraping
uv run hkjc-scrape --date 2026/03/01 --racecourse ST --export-db

# With explicit database URL
uv run hkjc-scrape --date 2026/03/01 --export-db \
  --database-url postgresql://hkjc:hkjc_dev@localhost:5432/hkjc_racing

# Or set DATABASE_URL env var (auto-detected by --export-db)
export DATABASE_URL=postgresql://hkjc:hkjc_dev@localhost:5432/hkjc_racing
uv run hkjc-scrape --date 2026/03/01 --export-db

# Run analytics on existing data
uv run hkjc-scrape --analyze

# Run analytics with JSON output
uv run hkjc-scrape --analyze --analyze-format json
```

### Programmatic Usage

```python
import asyncio
from hkjc_scraper.spider import HKJCRacingSpider

async def main():
    spider = HKJCRacingSpider(
        dates=["2026/03/01"],
        racecourse="ST"
    )
    result = await spider.run()
    for item in result.items:
        print(item["table"], item["data"])

asyncio.run(main())
```

### Historical Races

The scraper can discover and scrape historical races (pre-2024) that are not shown in the website dropdown:

```bash
# Discover historical races in a date range
uv run hkjc-scrape --discover --start-date 2015/01/01 --end-date 2019/12/31

# Scrape specific date range (uses cache)
uv run hkjc-scrape --start-date 2015/01/01 --end-date 2019/12/31 --racecourse ST

# Discover all historical races (2000-2024)
uv run hkjc-scrape --discover --start-date 2000/01/01 --end-date 2024/09/01 --auto-all
```

**Note:** Racing seasons run from September to July. August is the off-season with only overseas races.

## Data Model

### Tables
- **races** - Race metadata (date, class, distance, going, prize)
- **performance** - Horse results per race (position, time, odds, jockey_id, trainer_id)
- **dividends** - Payout information by pool type
- **incidents** - Race incident reports
- **horses** - Horse profiles (sire, dam, age, colour, gender, ratings, prize money)
- **jockeys** - Jockey profiles (background, achievements, career stats, season stats)
- **trainers** - Trainer profiles (background, achievements, career stats, season stats)
- **sectional_times** - Per-horse sectional time data (position, margin, time at each section)

### Output Format

Data is saved as JSON with UTF-8 encoding:
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

### PostgreSQL Database

The database includes:
- All 8 tables with proper foreign key constraints
- Indexes on frequently queried columns
- ON DELETE CASCADE for referential integrity
- JSONB columns for native JSON querying (rating, sectional_times, running_position)

### Analytics

The analytics module provides statistical analysis:

```bash
# Run analytics (text output)
uv run hkjc-scrape --analyze

# JSON output for programmatic use
uv run hkjc-scrape --analyze --analyze-format json
```

Analytics include:
- Jockey performance (win rate, top jockeys)
- Trainer performance (win rate, top trainers)
- Draw bias analysis (position advantages)
- Track bias (going, surface preferences)
- Class performance breakdown
- Horse form trends
- Jockey-Trainer combinations
- Distance preferences
- Speed ratings

## Testing

```bash
# Run unit tests only (no database required)
uv run pytest tests/ -v -m "not integration"

# Run integration tests (requires PostgreSQL: docker compose up db -d)
DATABASE_URL=postgresql://hkjc:hkjc_dev@localhost:5432/hkjc_racing \
  uv run pytest tests/ -v -m integration

# Run all tests
uv run pytest tests/ -v
```

## Docker Compose

The project includes Docker Compose for local development with PostgreSQL.

```bash
# Start PostgreSQL
docker compose up db -d

# Connect to PostgreSQL directly
psql postgresql://hkjc:hkjc_dev@localhost:5432/hkjc_racing

# Run the scraper in Docker
docker compose run app --date 2026/03/01 --racecourse ST --export-db

# Stop and clean up
docker compose down

# Stop and remove data volumes
docker compose down -v
```

### Configuration

Copy `.env.example` to `.env` to customize:

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_DB` | `hkjc_racing` | Database name |
| `POSTGRES_USER` | `hkjc` | Database user |
| `POSTGRES_PASSWORD` | `hkjc_dev` | Database password |
| `POSTGRES_PORT` | `5432` | Host port for PostgreSQL |
| `DATABASE_URL` | (derived) | Full connection string |

## Architecture
- Extends `scrapling.spiders.Spider` for async crawling
- Auto-discovers race dates from site dropdown
- Concurrent requests with built-in `download_delay`
- Error handling with retry logic
