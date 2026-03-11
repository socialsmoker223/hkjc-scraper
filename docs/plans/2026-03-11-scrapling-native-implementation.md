# Scrapling Native Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace custom rate limiting with Scrapling's built-in features for cleaner code and better performance.

**Architecture:** Remove custom asyncio.Semaphore-based rate limiting, use Scrapling's native `download_delay` and `FetcherSession` for async discovery.

**Tech Stack:** Python 3.13, Scrapling 0.4.1, pytest, asyncio

---

## Task 1: Add Spider Class Attributes

**Files:**
- Modify: `src/hkjc_scraper/spider.py:35-40`

**Step 1: Add new class attributes**

Add `concurrent_requests_per_domain` and `download_delay` to the spider class:

```python
class HKJCRacingSpider(Spider):
    """Spider for crawling HKJC horse racing data using async pattern."""

    name = "hkjc_racing"
    BASE_URL = "https://racing.hkjc.com/zh-hk/local/information/localresults"
    concurrent_requests = 15
    concurrent_requests_per_domain = 10  # NEW: limit per domain
    download_delay = 0.1  # NEW: 100ms between requests
```

**Step 2: Run tests to verify no breakage**

Run: `uv run pytest tests/test_spider.py -v -k "concurrent"`
Expected: PASS (test should verify new attribute value)

**Step 3: Commit**

```bash
git add src/hkjc_scraper/spider.py
git commit -m "feat: add Scrapling native concurrency attributes"
```

---

## Task 2: Remove Rate Limit Parameters from __init__

**Files:**
- Modify: `src/hkjc_scraper/spider.py:42-76`

**Step 1: Remove parameters from __init__ signature**

Remove `rate_limit` and `rate_jitter` parameters:

```python
def __init__(
    self,
    dates: list | None = None,
    racecourse: str | None = None,
    **kwargs,  # Remove rate_limit and rate_jitter
):
```

**Step 2: Remove rate limiting instance variables**

Remove these lines from `__init__`:
- `self._rate_limit = rate_limit`
- `self._rate_jitter = max(0.0, min(1.0, rate_jitter))`
- `self._limiter = None`
- `self._last_request_time = 0`
- `self._min_interval = 1.0 / rate_limit if rate_limit and rate_limit > 0 else 0`

Remove the entire block:
```python
if self._rate_limit and self._rate_limit > 0:
    self._limiter = asyncio.Semaphore(self.concurrent_requests)
```

**Step 3: Run tests to verify import works**

Run: `uv run python -c "from hkjc_scraper.spider import HKJCRacingSpider; s = HKJCRacingSpider(); print('OK')"`
Expected: OK (no errors)

**Step 4: Commit**

```bash
git add src/hkjc_scraper/spider.py
git commit -m "refactor: remove custom rate limiting from spider __init__"
```

---

## Task 3: Remove _apply_rate_limit Method

**Files:**
- Modify: `src/hkjc_scraper/spider.py:78-109`

**Step 1: Delete the entire method**

Remove lines 78-109 (`async def _apply_rate_limit(self):` through the end of the method).

**Step 2: Run tests**

Run: `uv run pytest tests/test_spider.py -v`
Expected: PASS (tests shouldn't directly call this private method)

**Step 3: Commit**

```bash
git add src/hkjc_scraper/spider.py
git commit -m "refactor: remove _apply_rate_limit method"
```

---

## Task 4: Simplify fetch Method

**Files:**
- Modify: `src/hkjc_scraper/spider.py:111-133`

**Step 1: Replace fetch method with simple Fetcher.get call**

Replace the entire `fetch` method with:

```python
def fetch(self, url: str):
    """Fetch a URL directly using Fetcher.

    Used by discover_dates for initial race discovery.

    Args:
        url: URL to fetch

    Returns:
        Response object with text and css methods
    """
    return Fetcher.get(url)
```

Note: Changed from `async def` to regular `def` since `Fetcher.get` is synchronous.

**Step 2: Update discover_dates to not await fetch**

Find in `discover_dates` function around line 680:
```python
# OLD: result = await self.fetch(url)
# NEW:
result = self.fetch(url)
```

**Step 3: Run tests**

Run: `uv run pytest tests/test_spider.py -v -k "fetch or discovery"`
Expected: PASS

**Step 4: Commit**

```bash
git add src/hkjc_scraper/spider.py
git commit -m "refactor: simplify fetch method to use Fetcher.get directly"
```

---

## Task 5: Add FetcherSession for Discovery

**Files:**
- Modify: `src/hkjc_scraper/spider.py:1-10` (add import)
- Modify: `src/hkjc_scraper/spider.py:657-720` (discover_dates function)

**Step 1: Add FetcherSession import**

Add to imports at top of file:
```python
from scrapling.fetchers import Fetcher, FetcherSession
```

**Step 2: Add helper function for FetcherSession**

Add before the `discover_dates` function:

```python
def _check_date_with_session(session: FetcherSession, date: str, racecourse: str, cache: DiscoveryCache) -> dict | None:
    """Check if races exist for a specific date and racecourse using FetcherSession.

    Args:
        session: FetcherSession instance
        date: Race date in YYYY/MM/DD format
        racecourse: Race course code (ST or HV)
        cache: Discovery cache instance

    Returns:
        Dictionary with race count if races found, None otherwise
    """
    url = f"{HKJCRacingSpider.BASE_URL}?racedate={date}&Racecourse={racecourse}"

    # Check cache first
    cached = cache.get(url)
    if cached is not None:
        return cached

    # Fetch the page
    response = session.get(url)
    if response and _is_valid_race_page(response):
        count = _count_races(response)
        cache.add_discovery(date, racecourse, count)
        return {"date": date, "racecourse": racecourse, "count": count}
    return None
```

**Step 3: Update discover_dates to use FetcherSession**

Replace the `discover_dates` function with:

```python
async def discover_dates(
    start_date: str,
    end_date: str,
    racecourses: list[str] | None = None,
    cache_path: str | None = None,
) -> list[dict]:
    """Discover race dates within a range.

    Args:
        start_date: Start date in YYYY/MM/DD format
        end_date: End date in YYYY/MM/DD format
        racecourses: List of racecourse codes (default: ['ST', 'HV'])
        cache_path: Path to cache file

    Returns:
        List of dictionaries with discovered race dates
    """
    from hkjc_scraper.spider import _is_valid_race_page, _count_races

    if racecourses is None:
        racecourses = ['ST', 'HV']

    cache = DiscoveryCache(cache_path)
    discovered = []

    # Pre-build all combinations to process
    combinations = [
        (date, racecourse)
        for date in generate_date_range(start_date, end_date)
        for racecourse in racecourses
    ]

    # Process in chunks for parallel execution with crash resilience
    CHUNK_SIZE = 50
    async with FetcherSession() as session:
        for i in range(0, len(combinations), CHUNK_SIZE):
            chunk = combinations[i:i + CHUNK_SIZE]

            # Process all items in this chunk in parallel
            tasks = [
                _check_date_with_session(session, d, rc, cache)
                for d, rc in chunk
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Collect non-None results and log errors
            for result in results:
                if isinstance(result, Exception):
                    # Log warning but continue processing
                    print(f"Warning: Discovery check failed: {result}")
                elif result:
                    discovered.append(result)

            # Save cache after each chunk (crash resilience)
            cache.save()

    return discovered
```

**Step 4: Remove unused asyncio import if no longer needed**

Check if `asyncio` is still used elsewhere in the file. If not, remove:
```python
import asyncio  # Remove this line
```

**Step 5: Run tests**

Run: `uv run pytest tests/test_spider.py -v -k "discover"`
Expected: PASS

**Step 6: Commit**

```bash
git add src/hkjc_scraper/spider.py
git commit -m "feat: use FetcherSession for async discovery with error logging"
```

---

## Task 6: Remove CLI Rate Limit Flags

**Files:**
- Modify: `src/hkjc_scraper/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Remove rate_limit and rate_jitter from CLI args**

Find the `Args` class or argument parser and remove:
- `--rate-limit` argument definition
- `--rate-jitter` argument definition

**Step 2: Remove rate_limit and rate_jitter from spider instantiation**

Find where `HKJCRacingSpider` is instantiated in `crawl_race` function and remove:
```python
# Remove these lines:
rate_limit=args.rate_limit,
rate_jitter=args.rate_jitter,
```

**Step 3: Update or remove affected tests**

Run: `uv run pytest tests/test_cli.py -v -k "rate"`
Expected: Tests may fail - update them to not test rate limiting

**Step 4: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests pass

**Step 5: Commit**

```bash
git add src/hkjc_scraper/cli.py tests/test_cli.py
git commit -m "refactor: remove --rate-limit and --rate-jitter CLI flags"
```

---

## Task 7: Update Documentation

**Files:**
- Modify: `docs/user_guide.md`
- Modify: `docs/api_reference.md`

**Step 1: Remove rate limiting documentation**

Remove sections mentioning:
- `--rate-limit` flag
- `--rate-jitter` flag
- Custom rate limiting implementation

**Step 2: Update CLI reference table**

Remove these rows from CLI options table:
- `--rate-limit N`
- `--rate-jitter N`

**Step 3: Commit**

```bash
git add docs/
git commit -m "docs: remove deprecated rate limiting documentation"
```

---

## Task 8: Final Verification

**Files:**
- Test: All tests

**Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All 174 tests pass

**Step 2: Test actual scraping**

Run: `uv run hkjc-scrape --date 2026/03/08 --racecourse ST`
Expected: Successful scrape with no rate limiting warnings

**Step 3: Test discovery**

Run: `uv run hkjc-scrape --discover --start-date 2026/03/01 --end-date 2026/03/31`
Expected: Discovery completes successfully

**Step 4: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: final adjustments for Scrapling native optimization"
```

---

## Summary

This plan removes ~100 lines of custom rate limiting code and replaces it with Scrapling's built-in features:

- **Before:** Custom asyncio.Semaphore-based rate limiting (~40 lines)
- **After:** Native `download_delay` and `concurrent_requests_per_domain` (2 lines)

- **Before:** `Fetcher.get` in thread pool for discovery
- **After:** `FetcherSession` with proper async handling

Total changes across 3 files: `spider.py`, `cli.py`, documentation.
