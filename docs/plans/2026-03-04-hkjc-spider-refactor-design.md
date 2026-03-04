# HKJC Spider Refactor Design

**Date:** 2026-03-04
**Status:** Approved
**Author:** Claude + User

## Overview

Refactor the HKJC Racing Scraper to properly use Scrapling's `Spider` class instead of using `Fetcher.get()` directly. Goals are both speed (concurrent crawling) and clean architecture (proper async Spider pattern).

**New Base URL:** `https://racing.hkjc.com/zh-hk/local/information/localresults`

## Architecture

**Approach:** Single Spider with Multiple Parse Methods

- `HKJCRacingSpider` extends `scrapling.spiders.Spider`
- Async-based with `yield` for items and `response.follow()` for navigation
- Auto-discovers race dates, crawls all races concurrently
- Output: Supabase-compatible normalized data structure

**URL Format:**
```
https://racing.hkjc.com/zh-hk/local/information/localresults?racedate=YYYY/MM/DD&Racecourse=HV/ST&RaceNo=N
```

## Data Model

Normalized schema for Supabase integration:

### `races` table
Race metadata extracted from page header.

| Field | Type | Description |
|-------|------|-------------|
| race_date | string | DD/MM/YYYY format |
| race_no | int | Race number (1-11) |
| race_id | string | Combined identifier (e.g., "2026-03-01-ST-1") |
| racecourse | string | "Happy Valley" or "Sha Tin" |
| race_name | string | Event name (e.g., "花旗銀行CITI WEALTH讓賽") |
| class | string | Race class (e.g., "第四班") |
| distance | int | Distance in meters (e.g., 1800) |
| rating | object | Min/max rating (e.g., {"min": 60, "max": 40}) |
| going | string | Track condition (e.g., "好地") |
| surface | string | "草地" or "泥地" |
| track | string | Track variant (e.g., "B+2") |
| prize_money | int | Total prize in HKD |
| sectional_times | object | Sectional time data if available |

### `performance` table
Race results per horse (was "horses", renamed).

| Field | Type | Description |
|-------|------|-------------|
| race_id | string | Foreign key to races |
| position | string | Finishing position (cleaned digits) |
| horse_no | string | Horse number |
| horse_id | string | HKJC horse ID |
| horse_name | string | Horse name (Chinese) |
| jockey | string | Jockey name |
| trainer | string | Trainer name |
| actual_weight | string | Weight carried (lbs) |
| body_weight | string | Declared weight (lbs) |
| draw | string | Barrier draw |
| margin | string | Distance from winner |
| running_position | list | Position at each section |
| finish_time | string | Finishing time |
| win_odds | string | Starting odds |

### `horses` table
Horse profile data (placeholder for future scraping).

| Field | Type | Description |
|-------|------|-------------|
| horse_id | string | Primary key (HKJC ID) |
| horse_name | string | Horse name (Chinese) |
| sire | string | Sire name (to be scraped) |
| dam | string | Dam name (to be scraped) |
| ... | ... | Additional profile fields |

### `dividends` table
Payout information.

| Field | Type | Description |
|-------|------|-------------|
| race_id | string | Foreign key to races |
| pool | string | Pool type (獨贏, 位置, 連贏, etc.) |
| winning_combination | string | Winning numbers |
| payout | string | Dividend amount |

### `incidents` table
Race incident reports.

| Field | Type | Description |
|-------|------|-------------|
| race_id | string | Foreign key to races |
| position | string | Position where incident occurred |
| horse_no | string | Horse number |
| horse_name | string | Horse name |
| incident_report | string | Incident description |

## Components

### `HKJCRacingSpider` Class

**Configuration:**
```python
name = "hkjc_racing"
concurrent_requests = 5
custom_settings = {
    "download_delay": 0.5,
    "retry_times": 3,
}
```

**Core Methods:**

1. **`start_requests()`** - Entry point
   - Accepts optional `dates`, `racecourse` parameters
   - Defaults to date discovery if none provided
   - Yields initial requests

2. **`parse_discover_dates(response)`** - Date discovery
   - Parses `#selectId option` elements
   - Yields `response.follow()` for each date

3. **`parse_all_results(response)`** - Race enumeration
   - Extracts race count from navigation
   - Yields `response.follow()` for RaceNo=1..11

4. **`parse_race(response)`** - Main parser
   - Extracts race metadata, performance, dividends, incidents
   - Yields normalized dicts with table type indicator

**Helper Methods:**
- `_clean_position(text)` - Remove non-digits
- `_parse_running_pos(element)` - Convert divs to list
- `_parse_rating(text)` - Parse "(60-40)" format
- `_parse_prize(text)` - Convert "HK$ 1,170,000" to int

## Data Flow

```
start_requests()
    ↓
parse_discover_dates() → yields date pages
    ↓
parse_all_results() → yields race pages (RaceNo=1..11)
    ↓
parse_race() → yields 5 dict types
```

**Item Yield Pattern:**
```python
yield {"table": "races", "data": {...}}
yield {"table": "performance", "data": {...}}  # one per horse
yield {"table": "dividends", "data": {...}}  # one per pool
yield {"table": "incidents", "data": {...}}  # if any
```

**Output:**
- `CrawlResult.items` - List of all yielded dicts
- Post-processor separates by table type for Supabase inserts

## Error Handling

| Error Type | Handling |
|------------|----------|
| 404/Not Found | Log warning, skip race gracefully |
| Timeout/Network | Retry 3x with exponential backoff |
| Missing Tables | Log warning, yield empty arrays |
| Malformed Data | Skip row, log debug message |
| Rate Limit (429) | Auto-increase download_delay |
| Missing Required Fields | Skip item, log error |

**Validation:**
- Required fields: race_date, race_no, racecourse
- Type coercion for numeric fields
- Empty string defaults for optional links

## Testing

**Unit Tests (pytest):**
- Selector tests with mock HTML
- Helper function tests (_clean_position, _parse_rating, etc.)
- Edge case handling (empty tables, missing links)

**Integration Tests:**
- Live crawl test on known race (2026/03/01 ST RaceNo=1)
- Date discovery test
- Full date crawl test (limited scope)

**Fixtures:**
- `sample_race_html` - Cached HTML
- `mock_response()` - Response factory

## Implementation Plan

Next step: Invoke `writing-plans` skill to create detailed implementation tasks.

## References

- Scrapling documentation via Context7
- Current implementation: `src/hkjc_scraper/spider.py`
- Sample data URL: https://racing.hkjc.com/zh-hk/local/information/localresults?racedate=2026/03/01&Racecourse=ST&RaceNo=1
