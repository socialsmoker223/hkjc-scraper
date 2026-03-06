# Historical Race Discovery Implementation Plan

**Date:** 2026-03-06
**Status:** Approved
**Author:** Implementation Planner

## Executive Summary

Add capability to discover and scrape historical HKJC race data (pre-2024) that exists but is not shown in the website's dropdown. The discovery uses smart brute-force with caching to efficiently find valid race dates.

## Goals

1. Add `--discover` CLI option to find historical race dates
2. Support date range discovery with `--start-date` and `--end-date`
3. Cache discovered dates to avoid redundant HTTP requests
4. Seamlessly integrate with existing scraping workflow
5. Handle racing season patterns (September to July, August is off-season)

## Constraints

- **Discovery range:** 2000-01-01 to 2024-09-01 (dropdown works after this)
- **Season awareness:** Skip August entirely (off-season with overseas races only)
- **Local races only:** ST (沙田) and HV (谷草)
- **No breaking changes** to existing functionality
- **Respect rate limiting** with existing `concurrent_requests` setting

## Background

HKJC racing data exists before 2024 but is not shown in the website dropdown. Direct URLs still work:
```
https://racing.hkjc.com/zh-hk/local/information/localresults?racedate=2015/01/01&Racecourse=ST&RaceNo=1
```

**Racing Season Pattern:**
- Season starts: September
- Season ends: July
- August: Off-season (only overseas races)
- Typical race days: Wednesday, Saturday, Sunday

## CLI Interface

### New Options

```bash
# Discover races in a date range
hkjc-scrape --discover --start-date 2015/01/01 --end-date 2019/12/31

# Scrape specific date range (uses cache if available)
hkjc-scrape --start-date 2015/01/01 --end-date 2019/12/31 --racecourse ST

# Discover all old races (with warning about scale)
hkjc-scrape --discover --start-date 2000/01/01 --auto-all

# Combined: discover and scrape in one command
hkjc-scrape --start-date 2015/01/01 --end-date 2019/12/31 --racecourse ST --scrape

# Refresh cached dates (re-verify)
hkjc-scrape --discover --start-date 2015/01/01 --end-date 2015/12/31 --refresh-cache
```

### Behavior

- `--discover`: Only finds dates, doesn't scrape race data
- `--start-date` defaults to current behavior (dropdown discovery)
- `--end-date` optional (defaults to start-date)
- `--auto-all`: Discovers from 2000-01-01 to 2024-09-01 (shows warning)
- `--refresh-cache`: Re-validates all cached dates

## Discovery Algorithm

### Date Generation

1. Generate dates from `start_date` to `end_date` (day by day)
2. **Skip August dates entirely** (off-season)
3. For each date, try both ST and HV racecourses

### Validation

For each date + racecourse combination:
1. Make request to: `localresults?racedate={date}&Racecourse={racecourse}`
2. Check if response has valid race data (not 404, not "no data" message)
3. If valid, count the number of races (1-11)
4. Add to discovered list

### Optimization

- **Concurrent requests:** Use existing `concurrent_requests` setting (5 parallel)
- **Progress reporting:** Show progress counter during discovery
- **Periodic saves:** Save cache every N discoveries

## Caching Strategy

### Cache File

**Location:** `data/.discovered_dates.json`

**Format:**
```json
{
  "discovered": [
    {"date": "2015/01/01", "racecourse": "ST", "race_count": 8},
    {"date": "2015/01/01", "racecourse": "HV", "race_count": 8},
    {"date": "2015/01/04", "racecourse": "ST", "race_count": 10}
  ],
  "season_breaks": ["2015-08", "2016-08", ...],
  "last_updated": "2026-03-06T10:30:00"
}
```

### Cache Behavior

- **Load on startup:** Read cache if exists
- **Skip cached dates:** Don't re-verify unless `--refresh-cache`
- **Update incrementally:** Add new discoveries as they're found
- **Save periodically:** Every 50 discoveries or on interruption
- **No expiry:** Valid race data doesn't change

### Cache Invalidation

- `--refresh-cache`: Re-verify all cached dates
- Corrupt cache: Log warning, rebuild from scratch
- Write failure: Log warning, continue without cache

## Data Flow

### Discovery Mode

```
CLI → HKJCRacingSpider.discover_dates(start, end)
       ↓
    Generate dates (skip August)
       ↓
    For each date + racecourse (ST, HV):
       ↓
    Request URL (concurrent)
       ↓
    Check response validity
       ↓
    If valid: Count races, add to discovered
       ↓
    Save cache periodically
       ↓
    Return discovered list
```

### Combined Discover + Scrape

```
CLI → HKJCRacingSpider.discover_dates(start, end)
       ↓
    Get discovered (date, racecourse, race_count) tuples
       ↓
    For each discovered tuple:
       ↓
    Yield requests to parse_all_results (existing flow)
       ↓
    Scrape race data, profiles, sectional times
```

## Implementation

### Files to Modify

| File | Changes |
|------|---------|
| `cli.py` | Add new CLI options (`--discover`, `--start-date`, `--end-date`, `--auto-all`, `--refresh-cache`) |
| `spider.py` | Add `discover_dates()` method, `_is_valid_race_date()` helper, cache handling |
| `tests/test_spider.py` | Add discovery tests |

### New Dependencies

None - uses existing `asyncio`, `json`, `pathlib`

### New Method: `discover_dates()`

```python
async def discover_dates(
    self,
    start_date: str,
    end_date: str,
    refresh_cache: bool = False,
    progress_callback: Callable | None = None
) -> list[dict]:
    """Discover valid race dates in the given range.

    Args:
        start_date: Start date in YYYY/MM/DD format
        end_date: End date in YYYY/MM/DD format
        refresh_cache: If True, re-verify cached dates
        progress_callback: Optional callback for progress updates

    Returns:
        List of dicts with keys: date, racecourse, race_count
    """
```

## Error Handling

### HTTP Errors

| Error | Handling |
|-------|----------|
| 404 | Expected - mark as no races for this date/racecourse |
| 500/503 | Retry with exponential backoff (max 3 retries) |
| Timeout | Retry up to 3 times |
| Login required | Skip (shouldn't happen for local results) |
| Maintenance page | Log warning, skip date |

### Interruption Handling

- **Ctrl+C:** Save cache before exit
- **Crash:** Cache saved periodically, minimal data loss
- **Cache write failure:** Log warning, continue without caching

### Logging Format

```
Discovering 2015-01-01 to 2015-01-31...
  ✓ 2015-01-01 ST: 8 races found
  ✓ 2015-01-01 HV: 8 races found
  ✗ 2015-01-02 ST: No races (off day)
  ✗ 2015-01-02 HV: No races (off day)
  ✓ 2015-01-04 ST: 10 races found
  ...
Cache saved: 452 race dates discovered
```

## Testing Strategy

### Unit Tests

1. **Date generation:** Test season awareness (skip August)
2. **Cache operations:** Load, save, read, merge
3. **Response validation:** `_is_valid_race_date()` with various responses
4. **Race counting:** Count races from valid page

### Integration Tests

1. **Small range discovery:** Test with 1-week range
2. **Cache file:** Verify cache is created and reused correctly
3. **Refresh cache:** Verify re-validation happens

### Test Commands

```bash
# Quick test - discover 1 week
hkjc-scrape --discover --start-date 2015/01/01 --end-date 2015/01/07

# Full discovery test (1 year)
hkjc-scrape --discover --start-date 2000/01/01 --end-date 2000/12/31

# Combined discover + scrape (small range)
hkjc-scrape --start-date 2015/01/01 --end-date 2015/01/07 --scrape
```

## Implementation Tasks

1. Add `--discover`, `--start-date`, `--end-date`, `--auto-all`, `--refresh-cache` CLI options
2. Implement cache file operations (load, save, merge)
3. Implement `discover_dates()` method in `HKJCRacingSpider`
4. Implement `_is_valid_race_date()` helper
5. Implement `_count_races()` helper
6. Add progress reporting for discovery
7. Add interruption handling (save cache on exit)
8. Add unit tests for discovery functionality
9. Add integration test for discovery
10. Update documentation

## Rollback Plan

If issues arise:
- Feature is additive - doesn't affect existing scraping
- Can disable via CLI (just don't use `--discover`)
- Cache file can be deleted to reset

## Success Criteria

- [ ] Can discover races from 2015-2019 (sample range)
- [ ] Cache file is created and reused correctly
- [ ] August dates are skipped
- [ ] Progress reporting works
- [ ] Existing scraping still works (no regressions)
- [ ] Tests pass
