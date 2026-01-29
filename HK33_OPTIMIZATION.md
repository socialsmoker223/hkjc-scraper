# HK33 Scraper Optimization: Scrape by Type

## Problem

The original HK33 scraper was slow because it processed races sequentially:
- For each race, scrape all 6 bet_types/markets in parallel (w, p, bet-w, bet-p, eat-w, eat-p)
- Then move to the next race

For a meeting with 11 races:
- Process Race 1: 6 parallel requests
- Process Race 2: 6 parallel requests
- ... (11 times)

## Solution

**Flip the loop order**: Scrape by bet_type first, then all races for that type.

New approach:
- Scrape type "w" for all 11 races in parallel
- Scrape type "p" for all 11 races in parallel
- Scrape type "bet-w" for all 11 races in parallel
- Scrape type "bet-p" for all 11 races in parallel
- Scrape type "eat-w" for all 11 races in parallel
- Scrape type "eat-p" for all 11 races in parallel

## Benefits

1. **URL Path Locality**: Similar endpoints are hit consecutively, improving server-side caching
2. **Better Session Reuse**: Cookies and connection pooling work more efficiently
3. **Reduced Context Switching**: HTTP client maintains better state between similar requests
4. **Parallelism**: Still maintains parallel execution (up to `MAX_HK33_RACE_WORKERS` races at once)
5. **Adaptive Rate Limiting**: Smart delays based on URL path changes (see below)

## Implementation

### New Function: `scrape_hk33_meeting_by_type()`

Located in `src/hkjc_scraper/hk33_scraper.py`:

```python
def scrape_hk33_meeting_by_type(
    session: HTTPSession,
    date_ymd: str,
    race_numbers: list[int],
    scrape_hkjc: bool = True,
    scrape_market: bool = True,
) -> dict[int, dict]:
    """
    Scrape HK33 data by bet_type/market first, then all races for each type.

    Returns:
        Dict mapping race_no to data:
        {
            1: {'hkjc_data': [...], 'market_data': [...]},
            2: {'hkjc_data': [...], 'market_data': [...]},
            ...
        }
    """
```

### Updated CLI Function

`scrape_and_save_hk33_meeting()` in `src/hkjc_scraper/cli.py` now:
1. Calls `scrape_hk33_meeting_by_type()` to scrape all data efficiently
2. Processes and saves results to database in parallel
3. Maintains same return format for backwards compatibility

## Performance Comparison

### Before (by-race):
```
[Race 1] -> [w, p, bet-w, bet-p, eat-w, eat-p] (6 parallel)
[Race 2] -> [w, p, bet-w, bet-p, eat-w, eat-p] (6 parallel)
...
[Race 11] -> [w, p, bet-w, bet-p, eat-w, eat-p] (6 parallel)
```

### After (by-type):
```
[Type w] -> [Race 1, 2, 3, ..., 11] (up to MAX_HK33_RACE_WORKERS parallel)
[Type p] -> [Race 1, 2, 3, ..., 11] (up to MAX_HK33_RACE_WORKERS parallel)
[Type bet-w] -> [Race 1, 2, 3, ..., 11] (parallel)
[Type bet-p] -> [Race 1, 2, 3, ..., 11] (parallel)
[Type eat-w] -> [Race 1, 2, 3, ..., 11] (parallel)
[Type eat-p] -> [Race 1, 2, 3, ..., 11] (parallel)
```

## Adaptive Rate Limiting

The optimization includes intelligent rate limiting based on URL path changes:

### Rate Limiting Strategy

- **Same URL Path** (different query params): 0.3s delay (configurable via `RATE_LIMIT_HK33_SAME_PATH`)
  - Example: `/jc-wp-trends-history?race=1&type=w` → `/jc-wp-trends-history?race=2&type=w`
  - Used when scraping the same bet_type across different races

- **Different URL Path**: 15s delay (configurable via `RATE_LIMIT_HK33_PATH_CHANGE`)
  - Example: `/jc-wp-trends-history?...` → `/offshore-market-trends-history?...`
  - Used when switching between bet_types

### How It Works

The `AdaptiveRateLimiter` class tracks the last URL path requested:
1. First request: No delay
2. Same path as previous: Apply short delay (0.3s)
3. Different path from previous: Apply long delay (15s)

This approach:
- Minimizes delays within the same bet_type (fast scraping of all races)
- Adds longer pauses when changing bet_types (appears less aggressive to server)
- Thread-safe for concurrent usage

### Implementation

```python
class AdaptiveRateLimiter:
    """Thread-safe adaptive rate limiter"""

    def wait_if_needed(self, url: str) -> None:
        """Wait appropriate time based on URL path change"""
        # Compare current path with last path
        # Apply different delays accordingly
```

Both scraping functions now use adaptive rate limiting:
- `scrape_hk33_hkjc_odds()`
- `scrape_hk33_offshore_market()`

## 429 (Too Many Requests) Handling

The server implements aggressive rate limiting:
- **429 Response**: Warning that you're making too many requests
- **403 Response**: Ban if you continue after 429

### Retry Strategy

Both scraping functions include `@retry_on_429()` decorator:
- Automatically retries on 429 errors
- Waits 15 seconds before retry (respecting server's rate limit)
- Maximum 3 retry attempts
- Logs warnings for visibility
- Raises exception after max retries to prevent infinite loops

```python
@retry_on_429(max_retries=3, backoff_delay=15.0)
def scrape_hk33_hkjc_odds(...):
    ...
```

### Reduced Concurrency

To avoid triggering 429 errors:
- `MAX_HK33_RACE_WORKERS` reduced from 4 to 2 (default)
- Fewer simultaneous requests = less chance of rate limiting
- Still achieves good parallelism across multiple bet_types

## Configuration

### Required Config Variables

- `MAX_HK33_RACE_WORKERS`: Controls how many races to scrape in parallel for each type (default: 4)
- `HK33_REQUEST_TIMEOUT`: Request timeout (default: 30s)

### Adaptive Rate Limiting Config

- `RATE_LIMIT_HK33_SAME_PATH`: Delay for same URL path (default: 0.3s)
- `RATE_LIMIT_HK33_PATH_CHANGE`: Delay for path changes (default: 15s)

### Deprecated Config

- `RATE_LIMIT_HK33`: No longer used (replaced by adaptive rate limiting)

## Testing

To test the optimization:

```bash
# Make sure dependencies are installed
cd /Users/joseph/Projects/hkjc-scraper-opt-hk33-by-type
uv pip install -e .

# Copy .env from main directory (already done)
# Run scraper with HK33 odds
hkjc-scraper 2026/01/14 --scrape-hk33
```

## Backward Compatibility

✅ **Fully backward compatible**
- Same CLI interface
- Same return values
- Same database schema
- Same error handling

The old `scrape_hk33_race_all_types()` function is preserved for compatibility but not used by the CLI.

## Next Steps

1. Test with real data to measure performance improvement
2. Monitor logs to verify correct operation
3. Consider backporting to main branch if successful
4. Add configuration option to switch between strategies if needed
