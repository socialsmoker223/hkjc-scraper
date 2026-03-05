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

## Module Organization

The scraper is organized into focused modules:

- **data_parsers.py** - General data parsing utilities (positions, ratings, prizes, race IDs)
- **id_parsers.py** - ID extraction from HKJC URLs (horse, jockey, trainer)
- **common.py** - Shared helper functions (career record parsing)
- **horse_parsers.py** - Horse profile parsing
- **jockey_trainer_parsers.py** - Jockey and trainer profile parsing
- **spider.py** - Main spider implementation
- **cli.py** - Command-line interface

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
cd /home/jc/code/hkjc-scraper
uv sync --extra test
```

## Usage

### CLI

```bash
# Crawl specific date
uv run hkjc-scrape --date 2026/03/01 --racecourse ST

# Discover and crawl latest race
uv run hkjc-scrape --racecourse ST
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

## Testing

```bash
# Run unit tests only
uv run pytest tests/ -v -m "not integration"

# Run integration tests (makes network requests)
uv run pytest tests/ -v -m integration

# Run all tests
uv run pytest tests/ -v
```

## Architecture
- Extends `scrapling.spiders.Spider` for async crawling
- Auto-discovers race dates from site dropdown
- Concurrent requests (5 by default) with rate limiting
- Error handling with retry logic
