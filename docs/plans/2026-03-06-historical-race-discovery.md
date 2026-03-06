# Historical Race Discovery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add capability to discover and scrape historical HKJC race data (pre-2024) that is not shown in the website dropdown.

**Architecture:** Smart brute-force discovery with caching. Generate dates from start to end, skip August (off-season), try each date + racecourse combination, cache valid dates.

**Tech Stack:** Python 3.13+, Scrapling Spider, asyncio, pytest

---

## Task 1: Create Cache File Module

**Files:**
- Create: `src/hkjc_scraper/cache.py`

**Step 1: Create the cache module with cache file operations**

```python
"""Cache operations for discovered race dates."""

import json
from pathlib import Path
from datetime import datetime
from typing import Any


class DiscoveryCache:
    """Cache for discovered historical race dates."""

    def __init__(self, cache_path: str | None = None):
        """Initialize cache with file path.

        Args:
            cache_path: Path to cache file. Defaults to data/.discovered_dates.json
        """
        if cache_path is None:
            cache_path = "data/.discovered_dates.json"
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        self.data: dict[str, Any] = {
            "discovered": [],
            "season_breaks": [],
            "last_updated": None,
        }

    def load(self) -> bool:
        """Load cache from disk.

        Returns:
            True if cache was loaded, False if file doesn't exist or is invalid
        """
        if not self.cache_path.exists():
            return False

        try:
            content = self.cache_path.read_text(encoding="utf-8")
            self.data = json.loads(content)
            return True
        except (json.JSONDecodeError, IOError):
            return False

    def save(self) -> None:
        """Save cache to disk."""
        self.data["last_updated"] = datetime.now().isoformat()
        content = json.dumps(self.data, indent=2, ensure_ascii=False)
        self.cache_path.write_text(content, encoding="utf-8")

    def add_discovery(self, date: str, racecourse: str, race_count: int) -> None:
        """Add a discovered race date to the cache.

        Args:
            date: Race date in YYYY/MM/DD format
            racecourse: Racecourse code (ST or HV)
            race_count: Number of races found
        """
        entry = {
            "date": date,
            "racecourse": racecourse,
            "race_count": race_count
        }

        # Check if already exists
        for existing in self.data["discovered"]:
            if existing["date"] == date and existing["racecourse"] == racecourse:
                return  # Already cached

        self.data["discovered"].append(entry)

    def is_cached(self, date: str, racecourse: str) -> bool:
        """Check if a date + racecourse is already cached.

        Args:
            date: Race date in YYYY/MM/DD format
            racecourse: Racecourse code (ST or HV)

        Returns:
            True if cached, False otherwise
        """
        for entry in self.data["discovered"]:
            if entry["date"] == date and entry["racecourse"] == racecourse:
                return True
        return False

    def get_discovered(self) -> list[dict]:
        """Get all discovered race dates.

        Returns:
            List of dicts with keys: date, racecourse, race_count
        """
        return self.data.get("discovered", [])

    def mark_season_break(self, month: str) -> None:
        """Mark a month as season break (e.g., August).

        Args:
            month: Month in YYYY-MM format
        """
        if month not in self.data.get("season_breaks", []):
            self.data.setdefault("season_breaks", []).append(month)

    def is_season_break(self, date: str) -> bool:
        """Check if a date falls during season break (August).

        Args:
            date: Date in YYYY/MM/DD format

        Returns:
            True if August, False otherwise
        """
        # Extract month from date (YYYY/MM/DD -> MM)
        parts = date.split("/")
        if len(parts) >= 2:
            return parts[1] == "08"  # August is season break
        return False
```

**Step 2: Run the tests to verify they pass**

Run: `python -c "from hkjc_scraper.cache import DiscoveryCache; print('Import successful')"`
Expected: No import errors

**Step 3: Commit**

```bash
git add src/hkjc_scraper/cache.py
git commit -m "feat: add DiscoveryCache class

Add cache module for storing discovered historical race dates:
- Cache file operations (load, save)
- Add discovered entries with date, racecourse, race_count
- Check if entry is cached
- Mark and check season breaks (August)"
```

---

## Task 2: Add Date Range Generator Helper

**Files:**
- Create: `src/hkjc_scraper/utils.py`

**Step 1: Create the date range generator**

```python
"""Utility functions for HKJC scraper."""

from datetime import datetime, timedelta
from typing import Generator


def generate_date_range(start_date: str, end_date: str) -> Generator[str, None, None]:
    """Generate dates from start to end (inclusive).

    Args:
        start_date: Start date in YYYY/MM/DD format
        end_date: End date in YYYY/MM/DD format

    Yields:
        Dates in YYYY/MM/DD format
    """
    start = datetime.strptime(start_date, "%Y/%m/%d")
    end = datetime.strptime(end_date, "%Y/%m/%d")

    current = start
    while current <= end:
        yield current.strftime("%Y/%m/%d")
        current += timedelta(days=1)


def parse_race_date(date_str: str) -> datetime:
    """Parse race date string to datetime.

    Args:
        date_str: Date in YYYY/MM/DD format

    Returns:
        datetime object
    """
    return datetime.strptime(date_str, "%Y/%m/%d")
```

**Step 2: Run the tests to verify they pass**

Run: `python -c "from hkjc_scraper.utils import generate_date_range; print(list(generate_date_range('2015/01/01', '2015/01/03')))"`
Expected: `['2015/01/01', '2015/01/02', '2015/01/03']`

**Step 3: Commit**

```bash
git add src/hkjc_scraper/utils.py
git commit -m "feat: add date range generator utility

Add generate_date_range() function for iterating dates.
Add parse_race_date() helper for date parsing."
```

---

## Task 3: Add Discovery Method to Spider

**Files:**
- Modify: `src/hkjc_scraper/spider.py`

**Step 1: Add imports for cache and utilities**

Add at the top with other imports:
```python
from hkjc_scraper.cache import DiscoveryCache
from hkjc_scraper.utils import generate_date_range, parse_race_date
```

**Step 2: Add the discover_dates method**

Add this method to the `HKJCRacingSpider` class:

```python
async def discover_dates(
    self,
    start_date: str,
    end_date: str,
    refresh_cache: bool = False,
) -> list[dict]:
    """Discover valid race dates in the given range.

    Args:
        start_date: Start date in YYYY/MM/DD format
        end_date: End date in YYYY/MM/DD format
        refresh_cache: If True, re-verify cached dates

    Returns:
        List of dicts with keys: date, racecourse, race_count
    """
    cache = DiscoveryCache()
    cache.load()

    discovered = []
    racecourses = ["ST", "HV"]
    check_count = 0
    save_interval = 50

    async def check_date(date: str, racecourse: str) -> dict | None:
        """Check if a date + racecourse has valid races."""
        # Check cache first unless refreshing
        if not refresh_cache and cache.is_cached(date, racecourse):
            return None

        # Skip August (season break)
        if cache.is_season_break(date):
            cache.mark_season_break(date[:7])  # YYYY-MM format
            return None

        url = f"{self.BASE_URL}?racedate={date}&Racecourse={racecourse}"
        try:
            response = await self.fetch(url)

            if response and self._is_valid_race_page(response):
                race_count = self._count_races(response)
                cache.add_discovery(date, racecourse, race_count)

                return {
                    "date": date,
                    "racecourse": racecourse,
                    "race_count": race_count
                }
        except Exception as e:
            self.logger.warning(f"Error checking {date} {racecourse}: {e}")

        return None

    # Check each date + racecourse combination
    for date in generate_date_range(start_date, end_date):
        for racecourse in racecourses:
            result = await check_date(date, racecourse)
            if result:
                discovered.append(result)

            # Periodic cache save
            check_count += 1
            if check_count % save_interval == 0:
                cache.save()

    cache.save()
    return discovered
```

**Step 3: Run the tests to verify they pass**

Run: `python -c "from hkjc_scraper.spider import HKJCRacingSpider; print('Import successful')"`
Expected: No import errors

**Step 4: Commit**

```bash
git add src/hkjc_scraper/spider.py
git commit -m "feat: add discover_dates method to spider

Add async method to discover historical race dates:
- Checks each date + racecourse combination
- Uses cache to avoid redundant requests
- Skips August dates (season break)
- Returns list of discovered (date, racecourse, race_count) tuples"
```

---

## Task 4: Add Helper Methods to Spider

**Files:**
- Modify: `src/hkjc_scraper/spider.py`

**Step 1: Add _is_valid_race_page helper**

Add this method to the `HKJCRacingSpider` class:

```python
def _is_valid_race_page(self, response) -> bool:
    """Check if response contains valid race data.

    Args:
        response: Scrapling response object

    Returns:
        True if page has valid race data, False otherwise
    """
    # Check for common indicators of no data
    text = response.text

    # No data indicators
    no_data_patterns = [
        "沒有赛事",  # No races (Chinese)
        "沒有賽事",
        "No races",
        "暫沒有賽事",  # No races at the moment
    ]

    for pattern in no_data_patterns:
        if pattern in text:
            return False

    # Check for race number selector or links
    # Valid pages have race number options or links
    if response.css("#selectId option"):
        return True

    if response.css('a[href*="RaceNo="]'):
        return True

    return False
```

**Step 2: Add _count_races helper**

Add this method to the `HKJCRacingSpider` class:

```python
def _count_races(self, response) -> int:
    """Count the number of races on the page.

    Args:
        response: Scrapling response object

    Returns:
        Number of races (1-11)
    """
    # Try to count from dropdown options
    options = response.css("#selectId option")
    if options:
        return len(options)

    # Alternative: count race number links
    race_links = response.css('a[href*="RaceNo="]')
    if race_links:
        # Extract unique race numbers
        race_numbers = set()
        for link in race_links:
            href = link.attrib.get("href", "")
            # Extract RaceNo=XX from href
            if "RaceNo=" in href:
                import re
                match = re.search(r'RaceNo=(\d+)', href)
                if match:
                    race_numbers.add(int(match.group(1)))

        return len(race_numbers) if race_numbers else 1

    return 1  # Default to at least 1 race
```

**Step 3: Run the tests to verify they pass**

Run: `python -c "from hkjc_scraper.spider import HKJCRacingSpider; s = HKJCRacingSpider(); print(hasattr(s, '_is_valid_race_page')); print(hasattr(s, '_count_races'))"`
Expected: `True True`

**Step 4: Commit**

```bash
git add src/hkjc_scraper/spider.py
git commit -m "feat: add helper methods for race page validation

Add _is_valid_race_page() to check if page has valid race data.
Add _count_races() to count number of races on a page."
```

---

## Task 5: Update CLI with New Options

**Files:**
- Modify: `src/hkjc_scraper/cli.py`

**Step 1: Read current CLI implementation**

Read the file first to understand the current argument parser setup.

**Step 2: Add new CLI options**

Add to the argument parser:

```python
parser.add_argument(
    "--discover",
    action="store_true",
    help="Discover historical race dates (don't scrape data)"
)
parser.add_argument(
    "--start-date",
    type=str,
    help="Start date for discovery/scraping (YYYY/MM/DD format)"
)
parser.add_argument(
    "--end-date",
    type=str,
    help="End date for discovery/scraping (YYYY/MM/DD format)"
)
parser.add_argument(
    "--auto-all",
    action="store_true",
    help="Discover all historical races from 2000-01-01 to 2024-09-01"
)
parser.add_argument(
    "--refresh-cache",
    action="store_true",
    help="Re-verify cached dates during discovery"
)
```

**Step 3: Update main function to handle new options**

Modify the main() function to handle the new options:

```python
async def main():
    parser = argparse.ArgumentParser(description="HKJC Racing Scraper")
    # ... existing arguments ...
    parser.add_argument("--discover", action="store_true", ...)
    parser.add_argument("--start-date", type=str, ...)
    parser.add_argument("--end-date", type=str, ...)
    parser.add_argument("--auto-all", action="store_true", ...)
    parser.add_argument("--refresh-cache", action="store_true", ...)

    args = parser.parse_args()

    spider = HKJCRacingSpider(
        dates=[args.date] if args.date else None,
        racecourse=args.racecourse
    )

    # Handle auto-all mode
    if args.auto_all:
        args.start_date = "2000/01/01"
        args.end_date = "2024/09/01"
        print("WARNING: Discovering all historical races (2000-2024)")
        print("This may take a while...")

    # Handle discovery mode
    if args.discover:
        if not args.start_date:
            parser.error("--discover requires --start-date")

        end_date = args.end_date or args.start_date

        print(f"Discovering races from {args.start_date} to {end_date}...")
        discovered = await spider.discover_dates(
            start_date=args.start_date,
            end_date=end_date,
            refresh_cache=args.refresh_cache
        )

        print(f"\nDiscovered {len(discovered)} race dates:")
        for entry in discovered:
            print(f"  {entry['date']} {entry['racecourse']}: {entry['race_count']} races")
        return

    # Handle date range mode
    if args.start_date:
        if not args.end_date:
            args.end_date = args.start_date

        # Discover dates first
        discovered = await spider.discover_dates(
            start_date=args.start_date,
            end_date=args.end_date,
            refresh_cache=args.refresh_cache
        )

        # Use discovered dates for scraping
        dates_to_scrape = set()
        for entry in discovered:
            if args.racecourse is None or entry['racecourse'] == args.racecourse:
                dates_to_scrape.add(entry['date'])

        spider.dates = sorted(list(dates_to_scrape))
        print(f"Scraping {len(spider.dates)} discovered dates...")

    # Existing scraping logic
    result = await spider.run()

    # Save results...
```

**Step 4: Run the tests to verify they pass**

Run: `uv run hkjc-scrape --help`
Expected: Help text shows new options

**Step 5: Commit**

```bash
git add src/hkjc_scraper/cli.py
git commit -m "feat: add historical race discovery CLI options

Add --discover, --start-date, --end-date, --auto-all, --refresh-cache options.
Update main() to handle discovery mode and date range scraping."
```

---

## Task 6: Add Unit Tests for Cache Module

**Files:**
- Create: `tests/test_cache.py`

**Step 1: Write the failing test**

```python
import pytest
import tempfile
from pathlib import Path
from hkjc_scraper.cache import DiscoveryCache


def test_cache_creation():
    """Test cache file is created with correct structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "test_cache.json"
        cache = DiscoveryCache(str(cache_path))

        assert cache.cache_path == cache_path
        assert cache.data == {
            "discovered": [],
            "season_breaks": [],
            "last_updated": None,
        }


def test_cache_add_and_retrieve():
    """Test adding and retrieving discovered entries."""
    cache = DiscoveryCache(":memory:")  # Use in-memory path
    cache.add_discovery("2015/01/01", "ST", 8)
    cache.add_discovery("2015/01/01", "HV", 8)
    cache.add_discovery("2015/01/04", "ST", 10)

    discovered = cache.get_discovered()
    assert len(discovered) == 3

    # Check specific entry
    st_entry = [e for e in discovered if e["date"] == "2015/01/01" and e["racecourse"] == "ST"][0]
    assert st_entry["race_count"] == 8


def test_cache_is_cached():
    """Test checking if entry is cached."""
    cache = DiscoveryCache(":memory:")
    cache.add_discovery("2015/01/01", "ST", 8)

    assert cache.is_cached("2015/01/01", "ST") is True
    assert cache.is_cached("2015/01/01", "HV") is False
    assert cache.is_cached("2015/01/02", "ST") is False


def test_cache_save_and_load():
    """Test saving and loading cache."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "test_cache.json"
        cache = DiscoveryCache(str(cache_path))

        cache.add_discovery("2015/01/01", "ST", 8)
        cache.save()

        # Load into new cache instance
        cache2 = DiscoveryCache(str(cache_path))
        loaded = cache2.load()

        assert loaded is True
        discovered = cache2.get_discovered()
        assert len(discovered) == 1
        assert discovered[0] == {"date": "2015/01/01", "racecourse": "ST", "race_count": 8}


def test_season_break_check():
    """Test August is detected as season break."""
    cache = DiscoveryCache(":memory:")

    assert cache.is_season_break("2015/08/01") is True
    assert cache.is_season_break("2015/07/31") is False
    assert cache.is_season_break("2015/09/01") is False


def test_no_duplicate_entries():
    """Test adding same entry twice doesn't create duplicates."""
    cache = DiscoveryCache(":memory:")
    cache.add_discovery("2015/01/01", "ST", 8)
    cache.add_discovery("2015/01/01", "ST", 8)  # Duplicate

    discovered = cache.get_discovered()
    assert len(discovered) == 1
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cache.py -v`
Expected: Tests fail (module or functions not implemented yet)

**Step 3: Run tests to verify they pass**

Run: `pytest tests/test_cache.py -v`
Expected: All 6 tests pass

**Step 4: Commit**

```bash
git add tests/test_cache.py
git commit -m "test: add cache module unit tests

Test cache creation, add/retrieve, is_cached, save/load,
season break detection, and duplicate prevention."
```

---

## Task 7: Add Unit Tests for Utils Module

**Files:**
- Create: `tests/test_utils.py`

**Step 1: Write the failing test**

```python
from hkjc_scraper.utils import generate_date_range, parse_race_date


def test_generate_date_range_single_day():
    """Test generating a single day range."""
    dates = list(generate_date_range("2015/01/01", "2015/01/01"))
    assert dates == ["2015/01/01"]


def test_generate_date_range_multiple_days():
    """Test generating multiple days."""
    dates = list(generate_date_range("2015/01/01", "2015/01/03"))
    assert dates == ["2015/01/01", "2015/01/02", "2015/01/03"]


def test_generate_date_range_august_skipped():
    """Test that August dates are included (filtering happens elsewhere)."""
    dates = list(generate_date_range("2015/07/31", "2015/08/02"))
    assert "2015/07/31" in dates
    assert "2015/08/01" in dates
    assert "2015/08/02" in dates


def test_parse_race_date():
    """Test parsing race date string."""
    dt = parse_race_date("2015/01/01")
    assert dt.year == 2015
    assert dt.month == 1
    assert dt.day == 1
```

**Step 2: Run tests to verify they pass**

Run: `pytest tests/test_utils.py -v`
Expected: All 4 tests pass

**Step 3: Commit**

```bash
git add tests/test_utils.py
git commit -m "test: add utils module unit tests

Test generate_date_range with single day, multiple days,
and parse_race_date function."
```

---

## Task 8: Add Integration Test for Discovery

**Files:**
- Create: `tests/integration/test_historical_discovery.py`

**Step 1: Write the integration test**

```python
import pytest
from hkjc_scraper.spider import HKJCRacingSpider


@pytest.mark.integration
async def test_discover_small_date_range():
    """Test discovering races in a small date range."""
    spider = HKJCRacingSpider()

    # Discover one week (should have at least one race day)
    discovered = await spider.discover_dates(
        start_date="2015/01/01",
        end_date="2015/01/07"
    )

    # Should find some races
    assert len(discovered) > 0

    # Each entry should have required fields
    for entry in discovered:
        assert "date" in entry
        assert "racecourse" in entry
        assert "race_count" in entry
        assert entry["racecourse"] in ["ST", "HV"]
        assert entry["race_count"] > 0


@pytest.mark.integration
async def test_discover_respects_cache():
    """Test that discovery uses cached data."""
    spider = HKJCRacingSpider()

    # First discovery
    discovered1 = await spider.discover_dates(
        start_date="2015/01/01",
        end_date="2015/01/07"
    )

    # Second discovery should be instant (uses cache)
    discovered2 = await spider.discover_dates(
        start_date="2015/01/01",
        end_date="2015/01/07"
    )

    assert len(discovered1) == len(discovered2)
```

**Step 2: Run tests to verify they pass**

Run: `pytest tests/integration/test_historical_discovery.py -v -m integration`
Expected: Tests pass (may take a minute to run)

**Step 3: Commit**

```bash
git add tests/integration/test_historical_discovery.py
git commit -m "test: add integration test for historical discovery

Test discovering races in small date range and cache usage."
```

---

## Task 9: Update Documentation

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

**Step 1: Update README.md**

Add section after "Usage":

```markdown
### Historical Races

The scraper can discover and scrape historical races (pre-2024) that are not shown in the website dropdown:

```bash
# Discover historical races in a date range
hkjc-scrape --discover --start-date 2015/01/01 --end-date 2019/12/31

# Scrape specific date range (uses cache)
hkjc-scrape --start-date 2015/01/01 --end-date 2019/12/31 --racecourse ST

# Discover all historical races (2000-2024)
hkjc-scrape --discover --start-date 2000/01/01 --end-date 2024/09/01 --auto-all
```

**Note:** Racing seasons run from September to July. August is the off-season with only overseas races.
```

**Step 2: Update CLAUDE.md**

Add section to "Common Tasks":

```markdown
### Scraping Historical Races

Historical races (pre-2024) are not in the dropdown but accessible via direct URLs:

```bash
# Discover races first
hkjc-scrape --discover --start-date 2015/01/01 --end-date 2015/12/31

# Then scrape discovered dates
hkjc-scrape --start-date 2015/01/01 --end-date 2015/12/31 --racecourse ST
```

The `data/.discovered_dates.json` cache stores discovered dates for fast re-runs.
```

**Step 3: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: document historical race discovery feature

Add documentation for historical race scraping including
CLI examples and notes about racing seasons."
```

---

## Task 10: Final Verification

**Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests pass

**Step 2: Test CLI help**

Run: `uv run hkjc-scrape --help`
Expected: Help shows new options

**Step 3: Test discovery on small range**

Run: `uv run hkjc-scrape --discover --start-date 2015/01/01 --end-date 2015/01/07`
Expected: Discovery completes and shows results

**Step 4: Commit**

```bash
git add .
git commit -m "feat: complete historical race discovery feature

All tasks complete:
- Cache module for storing discovered dates
- Date range generator utility
- discover_dates() method in spider
- Helper methods for validation and counting
- CLI options for discovery
- Unit and integration tests
- Documentation updates

Ready for testing with larger date ranges."
```
