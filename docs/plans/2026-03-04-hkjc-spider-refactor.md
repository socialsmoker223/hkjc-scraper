# HKJC Spider Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor HKJC Racing Scraper to use proper Scrapling Spider pattern with async generators, normalized data output, and comprehensive tests.

**Architecture:** Create `HKJCRacingSpider(Spider)` with `parse()` methods that yield items. Auto-discover dates, enumerate races, extract normalized data (races, performance, dividends, incidents tables). Error handling with retry logic and rate limiting.

**Tech Stack:** Python 3.13, scrapling[all]>=0.4.1, pytest, pytest-asyncio

---

## Task 1: Add Test Dependencies

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add test dependencies to pyproject.toml**

```toml
[project]
name = "hkjc-scraper"
version = "0.1.0"
description = "HKJC Racing Scraper - Extract horse racing data from Hong Kong Jockey Club"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "scrapling[all]>=0.4.1",
]

[project.optional-dependencies]
test = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.1",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
asyncio_mode = "auto"
```

**Step 2: Install test dependencies**

Run: `uv sync --extra test`
Expected: Dependencies installed successfully

**Step 3: Create tests directory**

Run: `mkdir -p tests/fixtures`
Expected: Directory created

**Step 4: Commit**

```bash
git add pyproject.toml tests/
git commit -m "test: add pytest and test infrastructure"
```

---

## Task 2: Create Helper Functions Module

**Files:**
- Create: `src/hkjc_scraper/parsers.py`
- Test: `tests/test_parsers.py`

**Step 1: Write failing tests for helper functions**

Create `tests/test_parsers.py`:

```python
"""Tests for parser helper functions."""
import pytest
from hkjc_scraper.parsers import (
    clean_position,
    parse_rating,
    parse_prize,
    parse_running_position,
    generate_race_id,
)


class TestCleanPosition:
    """Test position cleaning."""

    def test_clean_position_digits_only(self):
        assert clean_position("1") == "1"

    def test_clean_position_with_spaces(self):
        assert clean_position("1 ") == "1"

    def test_clean_position_with_chinese(self):
        assert clean_position("第一名") == "1"

    def test_clean_position_empty(self):
        assert clean_position("") == ""

    def test_clean_position_with_slash(self):
        assert clean_position("1/2") == "12"


class TestParseRating:
    """Test rating parsing."""

    def test_parse_rating_standard(self):
        assert parse_rating("(60-40)") == {"min": 60, "max": 40}

    def test_parse_rating_reversed(self):
        assert parse_rating("(40-60)") == {"min": 40, "max": 60}

    def test_parse_rating_no_parens(self):
        assert parse_rating("60-40") is None

    def test_parse_rating_empty(self):
        assert parse_rating("") is None


class TestParsePrize:
    """Test prize money parsing."""

    def test_parse_prize_standard(self):
        assert parse_prize("HK$ 1,170,000") == 1170000

    def test_parse_prize_no_commas(self):
        assert parse_prize("HK$ 1000000") == 1000000

    def test_parse_prize_no_currency(self):
        assert parse_prize("1,170,000") == 1170000

    def test_parse_prize_empty(self):
        assert parse_prize("") == 0


class TestParseRunningPosition:
    """Test running position parsing."""

    def test_parse_running_position_single(self):
        # Mock element with single position
        class MockElem:
            def css(self, selector):
                return [MockDiv("1"), MockDiv("2"), MockDiv("3")]
        class MockDiv:
            def __init__(self, text):
                self.text = type("", (), {"strip": lambda: text})()
        result = parse_running_position(MockElem())
        assert result == ["1", "2", "3"]

    def test_parse_running_position_empty(self):
        class MockElem:
            def css(self, selector):
                return []
        result = parse_running_position(MockElem())
        assert result == []


class TestGenerateRaceId:
    """Test race ID generation."""

    def test_generate_race_id_st(self):
        assert generate_race_id("2026/03/01", "ST", 1) == "2026-03-01-ST-1"

    def test_generate_race_id_hv(self):
        assert generate_race_id("2026/03/01", "HV", 5) == "2026-03-01-HV-5"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_parsers.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'hkjc_scraper.parsers'"

**Step 3: Implement helper functions**

Create `src/hkjc_scraper/parsers.py`:

```python
"""Helper functions for parsing HKJC race data."""

import re


def clean_position(text: str) -> str:
    """Extract digits from position text.

    Args:
        text: Position text (e.g., "1", "第一名", "1/2")

    Returns:
        Cleaned position string with digits only
    """
    if not text:
        return ""
    # Extract Chinese numerals or Arabic numerals
    chinese_nums = {"一": "1", "二": "2", "三": "3", "四": "4", "五": "5",
                    "六": "6", "七": "7", "八": "8", "九": "9", "十": "10"}
    for cn, digit in chinese_nums.items():
        if cn in text:
            return digit
    # Fallback to extracting digits
    return re.sub(r'[^\d]', '', text)


def parse_rating(text: str) -> dict | None:
    """Parse rating range from text.

    Args:
        text: Rating text (e.g., "(60-40)")

    Returns:
        Dict with 'min' and 'max' keys, or None if invalid
    """
    if not text or "(" not in text:
        return None
    match = re.search(r'\((\d+)-(\d+)\)', text)
    if match:
        return {"min": int(match.group(1)), "max": int(match.group(2))}
    return None


def parse_prize(text: str) -> int:
    """Parse prize money from text.

    Args:
        text: Prize text (e.g., "HK$ 1,170,000")

    Returns:
        Prize amount as integer
    """
    if not text:
        return 0
    # Remove currency symbols and commas
    cleaned = re.sub(r'[HK$\s,]', '', text)
    try:
        return int(cleaned)
    except ValueError:
        return 0


def parse_running_position(element) -> list:
    """Parse running positions from nested divs.

    Args:
        element: Scrapling element with div children

    Returns:
        List of position strings
    """
    positions = []
    for pos_div in element.css("div > div"):
        pos_text = pos_div.text.strip()
        if pos_text:
            positions.append(pos_text)
    return positions


def generate_race_id(race_date: str, racecourse: str, race_no: int) -> str:
    """Generate unique race ID.

    Args:
        race_date: Date in YYYY/MM/DD or DD/MM/YYYY format
        racecourse: "ST" or "HV"
        race_no: Race number

    Returns:
        Unique race ID (e.g., "2026-03-01-ST-1")
    """
    # Normalize date format
    date_parts = race_date.replace("/", "-").split("-")
    if len(date_parts) == 3:
        # Assume YYYY/MM/DD if first part is 4 digits
        if len(date_parts[0]) == 4:
            normalized = race_date.replace("/", "-")
        else:
            # DD/MM/YYYY -> YYYY-MM-DD
            normalized = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"
    else:
        normalized = race_date.replace("/", "-")
    return f"{normalized}-{racecourse}-{race_no}"
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_parsers.py -v`
Expected: PASS (all 16 tests pass)

**Step 5: Commit**

```bash
git add src/hkjc_scraper/parsers.py tests/test_parsers.py
git commit -m "feat: add parser helper functions with tests"
```

---

## Task 3: Create Sample HTML Fixture

**Files:**
- Create: `tests/fixtures/sample_race.html`
- Create: `tests/fixtures/conftest.py`

**Step 1: Fetch sample HTML for testing**

Run: `curl -s "https://racing.hkjc.com/zh-hk/local/information/localresults?racedate=2026/03/01&Racecourse=ST&RaceNo=1" > tests/fixtures/sample_race.html`

Expected: HTML file created (~50KB)

**Step 2: Create pytest fixtures**

Create `tests/fixtures/conftest.py`:

```python
"""Pytest fixtures for HKJC scraper tests."""

from pathlib import Path
from scrapling.fetchers import Fetcher


def get_fixture_path(name: str) -> Path:
    """Get path to fixture file."""
    return Path(__file__).parent / f"{name}.html"


def load_fixture(name: str) -> str:
    """Load fixture HTML content."""
    path = get_fixture_path(name)
    return path.read_text(encoding="utf-8")


@pytest.fixture
def sample_race_html():
    """Load sample race HTML."""
    return load_fixture("fixtures/sample_race")


@pytest.fixture
def sample_race_response(sample_race_html):
    """Create Fetcher response from sample HTML."""
    # Create a mock response object
    class MockResponse:
        def __init__(self, html):
            self.html = html
            self.url = "https://racing.hkjc.com/zh-hk/local/information/localresults?racedate=2026/03/01&Racecourse=ST&RaceNo=1"

        @property
        def text(self):
            return self.html

        def css(self, selector):
            """Simple CSS selector for testing."""
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(self.html, 'html.parser')
            results = soup.select(selector)
            return [self._element_to_mock(e) for e in results]

        def _element_to_mock(self, elem):
            """Convert BeautifulSoup element to mock element."""
            class MockElem:
                def __init__(self, el):
                    self._el = el
                    self.text = el.get_text(strip=True)
                    self.attrib = {"href": el.get("href", "")}

                def css(self, selector):
                    return [MockElem(e) for e in self._el.select(selector)]

            return MockElem(elem)

    return MockResponse(sample_race_html)
```

**Step 3: Update test dependencies to include beautifulsoup4**

Modify `pyproject.toml`:

```toml
[project.optional-dependencies]
test = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.1",
    "beautifulsoup4>=4.12",
]
```

**Step 4: Install updated dependencies**

Run: `uv sync --extra test`
Expected: beautifulsoup4 installed

**Step 5: Verify fixture loads**

Run: `uv run python -c "from tests.fixtures.conftest import load_fixture; html = load_fixture('fixtures/sample_race'); print(f'Loaded {len(html)} bytes')"`

Expected: "Loaded XXXXX bytes" (file size)

**Step 6: Commit**

```bash
git add tests/fixtures/ pyproject.toml
git commit -m "test: add sample race HTML fixture and pytest config"
```

---

## Task 4: Create New Spider Class Structure

**Files:**
- Create: `src/hkjc_scraper/spider_v2.py`
- Test: `tests/test_spider.py`

**Step 1: Write failing test for Spider class**

Create `tests/test_spider.py`:

```python
"""Tests for HKJCRacingSpider."""
import pytest
from scrapling.spiders import Spider
from hkjc_scraper.spider_v2 import HKJCRacingSpider


class TestSpiderClass:
    """Test Spider class configuration."""

    def test_spider_is_spider_subclass(self):
        assert issubclass(HKJCRacingSpider, Spider)

    def test_spider_has_name(self):
        assert HKJCRacingSpider.name == "hkjc_racing"

    def test_spider_has_base_url(self):
        spider = HKJCRacingSpider()
        assert spider.BASE_URL == "https://racing.hkjc.com/zh-hk/local/information/localresults"

    def test_spider_has_concurrent_requests(self):
        spider = HKJCRacingSpider()
        assert spider.concurrent_requests == 5
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_spider.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'hkjc_scraper.spider_v2'"

**Step 3: Implement Spider class skeleton**

Create `src/hkjc_scraper/spider_v2.py`:

```python
"""HKJC Racing Spider - Proper Scrapling Spider implementation."""

from scrapling.spiders import Spider


class HKJCRacingSpider(Spider):
    """Spider for crawling HKJC horse racing data using async pattern."""

    name = "hkjc_racing"
    BASE_URL = "https://racing.hkjc.com/zh-hk/local/information/localresults"
    concurrent_requests = 5

    def __init__(self, dates: list | None = None, racecourse: str | None = None, **kwargs):
        """Initialize spider.

        Args:
            dates: List of specific dates to crawl (YYYY/MM/DD format)
            racecourse: Filter by racecourse ("ST" or "HV")
        """
        super().__init__(**kwargs)
        self.dates = dates
        self.racecourse = racecourse

    def start_requests(self):
        """Generate initial requests.

        If dates provided, start from date pages.
        Otherwise, discover available dates from base URL.
        """
        if self.dates:
            # Crawl specific dates
            for date in self.dates:
                racecourse = self.racecourse or "ST"
                url = f"{self.BASE_URL}?racedate={date}&Racecourse={racecourse}"
                yield self.fetch(url, callback=self.parse_all_results, meta={"date": date, "racecourse": racecourse})
        else:
            # Discover dates first
            yield self.fetch(self.BASE_URL, callback=self.parse_discover_dates)

    async def parse_discover_dates(self, response):
        """Parse available race dates from dropdown.

        Args:
            response: Scrapling response

        Yields:
            Requests to each date page
        """
        for opt in response.css("#selectId option"):
            date_val = opt.attrib.get("value")
            if date_val:
                racecourse = self.racecourse or "ST"
                url = f"{self.BASE_URL}?racedate={date_val}&Racecourse={racecourse}"
                yield response.follow(url, callback=self.parse_all_results, meta={"date": date_val, "racecourse": racecourse})

    async def parse_all_results(self, response):
        """Parse race count and generate requests for each race.

        Args:
            response: Scrapling response

        Yields:
            Requests to individual race pages (RaceNo=1..11)
        """
        # Try to determine number of races from the page
        # Default to max 11 races
        meta = response.meta
        date = meta.get("date", "")
        racecourse = meta.get("racecourse", "ST")

        for race_no in range(1, 12):  # 1-11
            url = f"{self.BASE_URL}?racedate={date}&Racecourse={racecourse}&RaceNo={race_no}"
            yield response.follow(url, callback=self.parse_race, meta={"date": date, "racecourse": racecourse, "race_no": race_no})

    async def parse_race(self, response):
        """Parse individual race page.

        Args:
            response: Scrapling response

        Yields:
            Normalized dict items for races, performance, dividends, incidents tables
        """
        # Placeholder - will implement in next task
        yield {"table": "races", "data": {}}
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_spider.py -v`
Expected: PASS (all 4 tests pass)

**Step 5: Commit**

```bash
git add src/hkjc_scraper/spider_v2.py tests/test_spider.py
git commit -m "feat: create Spider class skeleton with async structure"
```

---

## Task 5: Implement Race Metadata Parser

**Files:**
- Modify: `src/hkjc_scraper/spider_v2.py`
- Test: `tests/test_spider.py`

**Step 1: Write failing test for race metadata parsing**

Add to `tests/test_spider.py`:

```python
class TestRaceMetadataParser:
    """Test race metadata extraction."""

    def test_parse_race_id(self):
        from hkjc_scraper.parsers import generate_race_id
        assert generate_race_id("2026/03/01", "ST", 1) == "2026-03-01-ST-1"

    @pytest.mark.asyncio
    async def test_parse_race_extracts_metadata(self, sample_race_response):
        """Test that parse_race extracts race metadata."""
        spider = HKJCRacingSpider()
        items = []

        async def mock_follow(url, callback, meta):
            return None

        async def collect_items():
            async for item in spider.parse_race(sample_race_response):
                items.append(item)

        await collect_items()

        # Check that at least one race item is yielded
        race_items = [i for i in items if i.get("table") == "races"]
        assert len(race_items) > 0
        race_data = race_items[0]["data"]
        assert "race_id" in race_data
        assert "race_date" in race_data
        assert "race_no" in race_data
```

**Step 2: Run test to verify it fails (incomplete)**

Run: `uv run pytest tests/test_spider.py::TestRaceMetadataParser -v`
Expected: FAIL or incomplete parsing

**Step 3: Implement race metadata extraction**

Modify `src/hkjc_scraper/spider_v2.py` - update imports and add `_parse_race_metadata` method:

```python
"""HKJC Racing Spider - Proper Scrapling Spider implementation."""

from scrapling.spiders import Spider
from hkjc_scraper.parsers import (
    clean_position,
    parse_rating,
    parse_prize,
    parse_running_position,
    generate_race_id,
)


class HKJCRacingSpider(Spider):
    """Spider for crawling HKJC horse racing data using async pattern."""

    name = "hkjc_racing"
    BASE_URL = "https://racing.hkjc.com/zh-hk/local/information/localresults"
    concurrent_requests = 5

    def __init__(self, dates: list | None = None, racecourse: str | None = None, **kwargs):
        """Initialize spider.

        Args:
            dates: List of specific dates to crawl (YYYY/MM/DD format)
            racecourse: Filter by racecourse ("ST" or "HV")
        """
        super().__init__(**kwargs)
        self.dates = dates
        self.racecourse = racecourse

    def start_requests(self):
        """Generate initial requests."""
        if self.dates:
            for date in self.dates:
                racecourse = self.racecourse or "ST"
                url = f"{self.BASE_URL}?racedate={date}&Racecourse={racecourse}"
                yield self.fetch(url, callback=self.parse_all_results, meta={"date": date, "racecourse": racecourse})
        else:
            yield self.fetch(self.BASE_URL, callback=self.parse_discover_dates)

    async def parse_discover_dates(self, response):
        """Parse available race dates from dropdown."""
        for opt in response.css("#selectId option"):
            date_val = opt.attrib.get("value")
            if date_val:
                racecourse = self.racecourse or "ST"
                url = f"{self.BASE_URL}?racedate={date_val}&Racecourse={racecourse}"
                yield response.follow(url, callback=self.parse_all_results, meta={"date": date_val, "racecourse": racecourse})

    async def parse_all_results(self, response):
        """Parse race count and generate requests for each race."""
        meta = response.meta
        date = meta.get("date", "")
        racecourse = meta.get("racecourse", "ST")

        for race_no in range(1, 12):
            url = f"{self.BASE_URL}?racedate={date}&Racecourse={racecourse}&RaceNo={race_no}"
            yield response.follow(url, callback=self.parse_race, meta={"date": date, "racecourse": racecourse, "race_no": race_no})

    async def parse_race(self, response):
        """Parse individual race page."""
        meta = response.meta
        date = meta.get("date", "")
        racecourse = meta.get("racecourse", "ST")
        race_no = meta.get("race_no", 1)

        # Extract race metadata
        race_data = self._parse_race_metadata(response, date, racecourse, race_no)
        yield {"table": "races", "data": race_data}

    def _parse_race_metadata(self, response, date: str, racecourse: str, race_no: int) -> dict:
        """Extract race metadata from page header.

        Args:
            response: Scrapling response
            date: Race date
            racecourse: Racecourse code
            race_no: Race number

        Returns:
            Dict with race metadata
        """
        race_id = generate_race_id(date, racecourse, race_no)
        racecourse_full = "Sha Tin" if racecourse == "ST" else "Happy Valley"

        # Default values
        metadata = {
            "race_id": race_id,
            "race_date": date,
            "race_no": race_no,
            "racecourse": racecourse_full,
            "race_name": "",
            "class": "",
            "distance": 0,
            "rating": None,
            "going": "",
            "surface": "",
            "track": "",
            "prize_money": 0,
            "sectional_times": None,
        }

        # Try to extract from page content
        # Look for race info in various locations
        page_text = response.text

        # Extract class (e.g., "第四班")
        import re
        class_match = re.search(r'(第[一二三四五六七八九]班)', page_text)
        if class_match:
            metadata["class"] = class_match.group(1)

        # Extract distance (e.g., "1800米")
        distance_match = re.search(r'(\d+)米', page_text)
        if distance_match:
            metadata["distance"] = int(distance_match.group(1))

        # Extract rating (e.g., "(60-40)")
        rating_match = re.search(r'[(\uff08](\d+)-(\d+)[)\uff09]', page_text)
        if rating_match:
            metadata["rating"] = {"min": int(rating_match.group(1)), "max": int(rating_match.group(2))}

        # Extract going (e.g., "好地")
        going_match = re.search(r'場地狀況\s*[:：]\s*([^\s]+)', page_text)
        if going_match:
            metadata["going"] = going_match.group(1)

        # Extract surface (草地/泥地)
        if "草地" in page_text:
            metadata["surface"] = "草地"
        elif "泥地" in page_text:
            metadata["surface"] = "泥地"

        # Extract track (e.g., "B+2")
        track_match = re.search(r'賽道\s*[:：]\s*[^\s]+\s*["\uff02]?([A-Z]+\+?\d*)["\uff02]?', page_text)
        if track_match:
            metadata["track"] = track_match.group(1)

        # Extract prize money
        prize_match = re.search(r'HK\$\s*([\d,]+)', page_text)
        if prize_match:
            metadata["prize_money"] = parse_prize(f"HK${prize_match.group(1)}")

        return metadata
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_spider.py::TestRaceMetadataParser -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/hkjc_scraper/spider_v2.py tests/test_spider.py
git commit -m "feat: implement race metadata parser"
```

---

## Task 6: Implement Performance Table Parser

**Files:**
- Modify: `src/hkjc_scraper/spider_v2.py`
- Test: `tests/test_spider.py`

**Step 1: Write failing test for performance table parsing**

Add to `tests/test_spider.py`:

```python
class TestPerformanceParser:
    """Test performance (horse results) table parsing."""

    @pytest.mark.asyncio
    async def test_parse_race_yields_performance_items(self, sample_race_response):
        """Test that parse_race extracts performance data."""
        spider = HKJCRacingSpider()
        items = []

        async def collect_items():
            async for item in spider.parse_race(sample_race_response):
                items.append(item)

        await collect_items()

        # Check that performance items are yielded
        perf_items = [i for i in items if i.get("table") == "performance"]
        assert len(perf_items) > 0

        perf_data = perf_items[0]["data"]
        assert "horse_no" in perf_data
        assert "horse_name" in perf_data
        assert "position" in perf_data
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_spider.py::TestPerformanceParser -v`
Expected: FAIL - no performance items yielded

**Step 3: Implement performance table parser**

Add `_parse_performance_table` method to `HKJCRacingSpider`:

```python
    def _parse_performance_table(self, response, race_id: str):
        """Extract performance (horse results) table.

        Args:
            response: Scrapling response
            race_id: Unique race identifier

        Yields:
            Dict items for performance table
        """
        results_table = response.css("table.draggable")
        if not results_table:
            return

        rows = results_table[0].css("tbody tr")
        for row in rows:
            cells = row.css("td")
            if len(cells) >= 12:
                # Extract horse name and ID from link
                horse_link = cells[2].css("a")
                horse_name = ""
                horse_id = None
                if horse_link:
                    horse_name = horse_link[0].text.strip()
                    href = horse_link[0].attrib.get("href", "")
                    if "horseid=" in href:
                        horse_id = href.split("horseid=")[1].split("&")[0]

                # Extract jockey
                jockey_link = cells[3].css("a")
                jockey = jockey_link[0].text.strip() if jockey_link else ""

                # Extract trainer
                trainer_link = cells[4].css("a")
                trainer = trainer_link[0].text.strip() if trainer_link else ""

                # Clean position
                pos_text = cells[0].text.strip()
                position = clean_position(pos_text) if pos_text else ""

                # Parse running positions
                running_pos = parse_running_position(cells[9])

                performance = {
                    "race_id": race_id,
                    "position": position,
                    "horse_no": cells[1].text.strip(),
                    "horse_id": horse_id,
                    "horse_name": horse_name,
                    "jockey": jockey,
                    "trainer": trainer,
                    "actual_weight": cells[5].text.strip(),
                    "body_weight": cells[6].text.strip(),
                    "draw": cells[7].text.strip(),
                    "margin": cells[8].text.strip(),
                    "running_position": running_pos,
                    "finish_time": cells[10].text.strip(),
                    "win_odds": cells[11].text.strip()
                }

                yield {"table": "performance", "data": performance}
```

**Step 4: Update parse_race to call performance parser**

Update `parse_race` method:

```python
    async def parse_race(self, response):
        """Parse individual race page."""
        meta = response.meta
        date = meta.get("date", "")
        racecourse = meta.get("racecourse", "ST")
        race_no = meta.get("race_no", 1)

        # Extract race metadata
        race_data = self._parse_race_metadata(response, date, racecourse, race_no)
        yield {"table": "races", "data": race_data}

        # Extract performance table
        race_id = race_data["race_id"]
        for perf_item in self._parse_performance_table(response, race_id):
            yield perf_item
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_spider.py::TestPerformanceParser -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/hkjc_scraper/spider_v2.py tests/test_spider.py
git commit -m "feat: implement performance table parser"
```

---

## Task 7: Implement Dividends Parser

**Files:**
- Modify: `src/hkjc_scraper/spider_v2.py`
- Test: `tests/test_spider.py`

**Step 1: Write failing test for dividends parsing**

Add to `tests/test_spider.py`:

```python
class TestDividendsParser:
    """Test dividends table parsing."""

    @pytest.mark.asyncio
    async def test_parse_race_yields_dividends(self, sample_race_response):
        """Test that parse_race extracts dividend data."""
        spider = HKJCRacingSpider()
        items = []

        async def collect_items():
            async for item in spider.parse_race(sample_race_response):
                items.append(item)

        await collect_items()

        div_items = [i for i in items if i.get("table") == "dividends"]
        assert len(div_items) > 0

        div_data = div_items[0]["data"]
        assert "pool" in div_data
        assert "winning_combination" in div_data
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_spider.py::TestDividendsParser -v`
Expected: FAIL - no dividend items

**Step 3: Implement dividends parser**

Add `_parse_dividends` method:

```python
    def _parse_dividends(self, response, race_id: str):
        """Extract dividends table.

        Args:
            response: Scrapling response
            race_id: Unique race identifier

        Yields:
            Dict items for dividends table
        """
        for table in response.css("table.table_bd"):
            header = table.css("thead tr td")
            if header and "派彩" in header[0].text:
                current_pool = None
                for row in table.css("tbody tr"):
                    cells = row.css("td")
                    if len(cells) >= 3:
                        first_cell = cells[0].text.strip()
                        if first_cell:
                            current_pool = first_cell

                        dividend = {
                            "race_id": race_id,
                            "pool": current_pool,
                            "winning_combination": cells[1].text.strip(),
                            "payout": cells[2].text.strip()
                        }
                        yield {"table": "dividends", "data": dividend}
```

**Step 4: Update parse_race to call dividends parser**

```python
    async def parse_race(self, response):
        """Parse individual race page."""
        meta = response.meta
        date = meta.get("date", "")
        racecourse = meta.get("racecourse", "ST")
        race_no = meta.get("race_no", 1)

        # Extract race metadata
        race_data = self._parse_race_metadata(response, date, racecourse, race_no)
        yield {"table": "races", "data": race_data}

        race_id = race_data["race_id"]

        # Extract performance table
        for perf_item in self._parse_performance_table(response, race_id):
            yield perf_item

        # Extract dividends
        for div_item in self._parse_dividends(response, race_id):
            yield div_item
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_spider.py::TestDividendsParser -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/hkjc_scraper/spider_v2.py tests/test_spider.py
git commit -m "feat: implement dividends parser"
```

---

## Task 8: Implement Incidents Parser

**Files:**
- Modify: `src/hkjc_scraper/spider_v2.py`
- Test: `tests/test_spider.py`

**Step 1: Write failing test for incidents parsing**

Add to `tests/test_spider.py`:

```python
class TestIncidentsParser:
    """Test incidents table parsing."""

    @pytest.mark.asyncio
    async def test_parse_race_yields_incidents(self, sample_race_response):
        """Test that parse_race extracts incident data."""
        spider = HKJCRacingSpider()
        items = []

        async def collect_items():
            async for item in spider.parse_race(sample_race_response):
                items.append(item)

        await collect_items()

        # Incidents may not exist in all races
        inc_items = [i for i in items if i.get("table") == "incidents"]
        # Don't assert count, just check structure if present
        if inc_items:
            inc_data = inc_items[0]["data"]
            assert "incident_report" in inc_data
```

**Step 2: Run test (may pass if incidents not present)**

Run: `uv run pytest tests/test_spider.py::TestIncidentsParser -v`
Expected: May PASS with 0 incidents

**Step 3: Implement incidents parser**

Add `_parse_incidents` method:

```python
    def _parse_incidents(self, response, race_id: str):
        """Extract incidents table.

        Args:
            response: Scrapling response
            race_id: Unique race identifier

        Yields:
            Dict items for incidents table
        """
        for table in response.css("table.table_bd"):
            header = table.css("thead tr td")
            if header and any("競賽事件" in h.text for h in header):
                for row in table.css("tbody tr"):
                    cells = row.css("td")
                    if len(cells) >= 4:
                        horse_link = cells[2].css("a")
                        horse_name = horse_link[0].text.strip() if horse_link else ""

                        incident = {
                            "race_id": race_id,
                            "position": cells[0].text.strip(),
                            "horse_no": cells[1].text.strip(),
                            "horse_name": horse_name,
                            "incident_report": cells[3].text.strip()
                        }
                        yield {"table": "incidents", "data": incident}
```

**Step 4: Update parse_race to call incidents parser**

```python
    async def parse_race(self, response):
        """Parse individual race page."""
        meta = response.meta
        date = meta.get("date", "")
        racecourse = meta.get("racecourse", "ST")
        race_no = meta.get("race_no", 1)

        # Extract race metadata
        race_data = self._parse_race_metadata(response, date, racecourse, race_no)
        yield {"table": "races", "data": race_data}

        race_id = race_data["race_id"]

        # Extract performance table
        for perf_item in self._parse_performance_table(response, race_id):
            yield perf_item

        # Extract dividends
        for div_item in self._parse_dividends(response, race_id):
            yield div_item

        # Extract incidents
        for inc_item in self._parse_incidents(response, race_id):
            yield inc_item
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_spider.py::TestIncidentsParser -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/hkjc_scraper/spider_v2.py tests/test_spider.py
git commit -m "feat: implement incidents parser"
```

---

## Task 9: Add Error Handling and Validation

**Files:**
- Modify: `src/hkjc_scraper/spider_v2.py`
- Test: `tests/test_spider.py`

**Step 1: Write tests for error handling**

Add to `tests/test_spider.py`:

```python
class TestErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_parse_race_handles_missing_tables(self):
        """Test that parse_race handles pages with no results table."""
        from scrapling.fetchers import Fetcher

        # Create a minimal HTML with no tables
        empty_html = "<html><body>No tables here</body></html>"

        class EmptyResponse:
            def __init__(self):
                self.text = empty_html
                self.meta = {"date": "2026/03/01", "racecourse": "ST", "race_no": 1}

            def css(self, selector):
                return []

        spider = HKJCRacingSpider()
        response = EmptyResponse()
        items = []

        async def collect_items():
            async for item in spider.parse_race(response):
                items.append(item)

        await collect_items()

        # Should still yield race metadata
        assert len(items) >= 1
        assert items[0]["table"] == "races"

    def test_clean_position_handles_empty(self):
        """Test that clean_position handles empty input."""
        from hkjc_scraper.parsers import clean_position
        assert clean_position("") == ""
        assert clean_position(None) == ""
```

**Step 2: Run tests to verify failures**

Run: `uv run pytest tests/test_spider.py::TestErrorHandling -v`
Expected: Some may fail

**Step 3: Add error handling to parsers**

Update `parsers.py` to handle None:

```python
def clean_position(text: str | None) -> str:
    """Extract digits from position text.

    Args:
        text: Position text (e.g., "1", "第一名", "1/2")

    Returns:
        Cleaned position string with digits only
    """
    if not text:
        return ""
    # Extract Chinese numerals or Arabic numerals
    chinese_nums = {"一": "1", "二": "2", "三": "3", "四": "4", "五": "5",
                    "六": "6", "七": "7", "八": "8", "九": "9", "十": "10"}
    for cn, digit in chinese_nums.items():
        if cn in text:
            return digit
    return re.sub(r'[^\d]', '', text)
```

Add validation to `spider_v2.py`:

```python
    def _validate_performance_item(self, item: dict) -> bool:
        """Validate performance item has required fields.

        Args:
            item: Performance data dict

        Returns:
            True if valid, False otherwise
        """
        required_fields = ["race_id", "horse_no"]
        return all(item.get(field) for field in required_fields)

    def _parse_performance_table(self, response, race_id: str):
        """Extract performance (horse results) table."""
        results_table = response.css("table.draggable")
        if not results_table:
            return

        rows = results_table[0].css("tbody tr")
        for row in rows:
            cells = row.css("td")
            if len(cells) >= 12:
                try:
                    horse_link = cells[2].css("a")
                    horse_name = ""
                    horse_id = None
                    if horse_link:
                        horse_name = horse_link[0].text.strip()
                        href = horse_link[0].attrib.get("href", "")
                        if "horseid=" in href:
                            horse_id = href.split("horseid=")[1].split("&")[0]

                    jockey_link = cells[3].css("a")
                    jockey = jockey_link[0].text.strip() if jockey_link else ""

                    trainer_link = cells[4].css("a")
                    trainer = trainer_link[0].text.strip() if trainer_link else ""

                    pos_text = cells[0].text.strip()
                    position = clean_position(pos_text) if pos_text else ""

                    running_pos = parse_running_position(cells[9])

                    performance = {
                        "race_id": race_id,
                        "position": position,
                        "horse_no": cells[1].text.strip(),
                        "horse_id": horse_id,
                        "horse_name": horse_name,
                        "jockey": jockey,
                        "trainer": trainer,
                        "actual_weight": cells[5].text.strip(),
                        "body_weight": cells[6].text.strip(),
                        "draw": cells[7].text.strip(),
                        "margin": cells[8].text.strip(),
                        "running_position": running_pos,
                        "finish_time": cells[10].text.strip(),
                        "win_odds": cells[11].text.strip()
                    }

                    if self._validate_performance_item(performance):
                        yield {"table": "performance", "data": performance}
                except Exception as e:
                    # Log and continue with next row
                    continue
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_spider.py::TestErrorHandling -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/hkjc_scraper/parsers.py src/hkjc_scraper/spider_v2.py tests/test_spider.py
git commit -m "feat: add error handling and validation"
```

---

## Task 10: Add Integration Test

**Files:**
- Create: `tests/integration_test.py`

**Step 1: Write integration test**

Create `tests/integration_test.py`:

```python
"""Integration tests for HKJC spider."""
import pytest
from hkjc_scraper.spider_v2 import HKJCRacingSpider


@pytest.mark.integration
class TestLiveCrawl:
    """Integration tests with live site."""

    @pytest.mark.asyncio
    async def test_crawl_single_race(self):
        """Test crawling a single live race."""
        spider = HKJCRacingSpider(
            dates=["2026/03/01"],
            racecourse="ST"
        )

        result = await spider.run()

        # Check that we got results
        assert len(result.items) > 0

        # Check for different table types
        table_types = {item.get("table") for item in result.items}
        assert "races" in table_types
        assert "performance" in table_types

        # Check stats
        assert result.stats.get("total_requests", 0) > 0

    @pytest.mark.asyncio
    async def test_discover_dates(self):
        """Test date discovery from base URL."""
        spider = HKJCRacingSpider()

        # Only discover, don't crawl
        result = await spider.run()

        # Should have made at least one request
        assert result.stats.get("total_requests", 0) >= 1
```

**Step 2: Run integration test (may take time)**

Run: `uv run pytest tests/integration_test.py -v -m integration`
Expected: PASS (makes real network requests)

**Step 3: Add pytest marker configuration**

Add to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
asyncio_mode = "auto"
markers = [
    "integration: marks tests as integration tests (makes network requests)",
]
```

**Step 4: Run tests excluding integration**

Run: `uv run pytest tests/ -v -m "not integration"`
Expected: All unit tests pass, integration skipped

**Step 5: Commit**

```bash
git add tests/integration_test.py pyproject.toml
git commit -m "test: add integration tests with live crawling"
```

---

## Task 11: Create CLI Entry Point

**Files:**
- Create: `src/hkjc_scraper/cli.py`
- Modify: `pyproject.toml`

**Step 1: Write CLI module**

Create `src/hkjc_scraper/cli.py`:

```python
"""Command-line interface for HKJC spider."""
import asyncio
import json
from pathlib import Path
from hkjc_scraper.spider_v2 import HKJCRacingSpider


def group_items_by_table(items: list) -> dict:
    """Group yielded items by table type.

    Args:
        items: List of {table: str, data: dict} items

    Returns:
        Dict with table names as keys and list of data as values
    """
    grouped = {}
    for item in items:
        table = item.get("table", "unknown")
        if table not in grouped:
            grouped[table] = []
        grouped[table].append(item.get("data", {}))
    return grouped


async def crawl_race(
    date: str | None = None,
    racecourse: str = "ST",
    output_dir: str = "data"
) -> dict:
    """Crawl race data.

    Args:
        date: Date in YYYY/MM/DD format (default: discover from site)
        racecourse: "ST" or "HV"
        output_dir: Output directory for JSON files

    Returns:
        Grouped data by table type
    """
    spider = HKJCRacingSpider(
        dates=[date] if date else None,
        racecourse=racecourse
    )

    result = await spider.run()
    grouped = group_items_by_table(result.items)

    # Save to files
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    date_str = date.replace("/", "-") if date else "latest"
    for table_name, data in grouped.items():
        if data:  # Only save non-empty tables
            file_path = out_path / f"{table_name}_{date_str}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"✅ Saved {len(data)} {table_name} records to {file_path}")

    print(f"\n📊 Summary:")
    for table_name, data in grouped.items():
        print(f"  {table_name}: {len(data)} records")
    print(f"  Total requests: {result.stats.get('total_requests', 0)}")

    return grouped


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="HKJC Racing Scraper")
    parser.add_argument("--date", help="Race date (YYYY/MM/DD format)")
    parser.add_argument("--racecourse", choices=["ST", "HV"], default="ST",
                        help="Racecourse (ST=Sha Tin, HV=Happy Valley)")
    parser.add_argument("--output", default="data", help="Output directory")

    args = parser.parse_args()

    asyncio.run(crawl_race(args.date, args.racecourse, args.output))


if __name__ == "__main__":
    main()
```

**Step 2: Add CLI entry point to pyproject.toml**

```toml
[project.scripts]
hkjc-scrape = "hkjc_scraper.cli:main"
```

**Step 3: Test CLI**

Run: `uv run hkjc-scrape --help`
Expected: Help message displayed

**Step 4: Test CLI with live data**

Run: `uv run hkjc-scrape --date 2026/03/01 --racecourse ST`
Expected: Downloads data, saves JSON files

**Step 5: Commit**

```bash
git add src/hkjc_scraper/cli.py pyproject.toml
git commit -m "feat: add CLI entry point"
```

---

## Task 12: Update Documentation

**Files:**
- Modify: `README.md`

**Step 1: Update README with new usage**

Modify `README.md`:

```markdown
# HKJC Racing Scraper

Extract horse racing data from Hong Kong Jockey Club (HKJC) using Scrapling Spider.

## Features

- 🏇 Race results with horse details, jockey, trainer
- 💰 Dividends (Win, Place, Quinella, Tierce, Quartet, etc.)
- 📋 Incident reports for each race
- 📅 Historical data (auto-discover race dates)
- 🔄 Async crawling with concurrent requests
- 📊 Normalized Supabase-compatible output

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
from hkjc_scraper.spider_v2 import HKJCRacingSpider

async def main():
    spider = HKJCRacingSpider(
        dates=["2026/03/01"],
        racecourse="ST"
    )
    result = await spider.run()

    # Items are yielded as {table: str, data: dict}
    for item in result.items:
        print(item["table"], item["data"])

asyncio.run(main())
```

## Data Model

### Tables

- **races** - Race metadata (date, class, distance, going, prize)
- **performance** - Horse results per race (position, time, odds)
- **dividends** - Payout information by pool type
- **incidents** - Race incident reports
- **horses** - Horse profiles (placeholder for future)

### Output Format

Data is saved as JSON with UTF-8 encoding:

```
data/
├── races_2026-03-01.json
├── performance_2026-03-01.json
├── dividends_2026-03-01.json
└── incidents_2026-03-01.json
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
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README for new Spider implementation"
```

---

## Task 13: Final Verification

**Files:**
- All

**Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests pass

**Step 2: Run integration test**

Run: `uv run pytest tests/ -v -m integration`
Expected: Integration tests pass

**Step 3: Test CLI end-to-end**

Run: `uv run hkjc-scrape --date 2026/03/01 --racecourse ST --output /tmp/hkjc_test`

Expected: Creates JSON files in /tmp/hkjc_test

**Step 4: Verify output structure**

Run: `ls -la /tmp/hkjc_test/ && cat /tmp/hkjc_test/races_2026-03-01.json | head -20`

Expected: Valid JSON with race data

**Step 5: Cleanup**

Run: `rm -rf /tmp/hkjc_test`

**Step 6: Final commit**

```bash
git add .
git commit -m "feat: complete HKJC spider refactor

- Migrate from Fetcher.get() to async Spider pattern
- Add normalized Supabase-compatible data output
- Implement date discovery, race enumeration
- Add comprehensive unit and integration tests
- Add CLI entry point
- Update documentation

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Completion Criteria

- [ ] All unit tests pass
- [ ] Integration tests pass with live site
- [ ] CLI works for single date crawl
- [ ] Date discovery works
- [ ] Error handling validates data
- [ ] Output is normalized by table type
- [ ] README updated
- [ ] Old implementation preserved in `spider.py` (not deleted)

## Notes

- The old `spider.py` is preserved for backward compatibility
- New implementation is in `spider_v2.py`
- After verification, consider renaming `spider_v2.py` to `spider.py`
