# Scrapling Native Optimization Design

**Date:** 2026-03-11
**Status:** Approved

## Overview

Replace custom rate limiting and HTTP fetching logic with Scrapling's built-in features to simplify code and improve performance.

## Goals

1. Remove custom rate limiting code in favor of native `download_delay`
2. Add `concurrent_requests_per_domain` for politeness
3. Use `FetcherSession` for async discovery phase
4. Remove `--rate-limit` and `--rate-jitter` CLI flags

## Changes

### Spider Class Attributes

```python
class HKJCRacingSpider(Spider):
    name = "hkjc_racing"
    concurrent_requests = 15
    concurrent_requests_per_domain = 10
    download_delay = 0.1
```

### Remove from `__init__`

- `rate_limit` parameter
- `rate_jitter` parameter
- `self._rate_limit`
- `self._rate_jitter`
- `self._limiter`
- `self._last_request_time`
- `self._min_interval`

### Remove Method

- `_apply_rate_limit()` (entire method, ~30 lines)

### Simplify `fetch()` Method

```python
async def fetch(self, url: str):
    return Fetcher.get(url)
```

### Use FetcherSession for Discovery

Replace current `Fetcher.get` in thread pool with async `FetcherSession`:

```python
from scrapling.fetchers import FetcherSession

async with FetcherSession() as session:
    tasks = [session.get(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, Exception):
            self.logger.warning(f"Discovery failed: {result}")
```

### CLI Changes

Remove arguments:
- `--rate-limit`
- `--rate-jitter`

## Files to Modify

| File | Changes |
|------|---------|
| `src/hkjc_scraper/spider.py` | Add attributes, remove rate limiting, add FetcherSession |
| `src/hkjc_scraper/cli.py` | Remove --rate-limit and --rate-jitter flags |
| `tests/test_spider.py` | Update/remove rate limiting tests |

## Testing

- Run all 174 tests
- Verify discovery still works correctly
- Verify normal scraping works correctly
- Check logs for warning messages on discovery failures
