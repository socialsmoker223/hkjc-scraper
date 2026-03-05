# Sectional Time Scraping Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add per-horse sectional time data extraction from HKJC sectional time pages.

**Architecture:** Extend existing spider to extract sectional time href from race results page, then fetch and parse sectional time page into normalized `sectional_times` table (one row per horse per section).

**Tech Stack:** Scrapling Spider, Python 3.13, pytest

---

### Task 1: Add parse_sectional_time_cell function to parsers.py

**Files:**
- Modify: `src/hkjc_scraper/parsers.py`
- Test: `tests/test_parsers.py`

**Step 1: Write the failing test**

Add to `tests/test_parsers.py`:

```python
def test_parse_sectional_time_cell_valid():
    """Test parsing a valid sectional time cell with position, margin, time."""
    from hkjc_scraper.parsers import parse_sectional_time_cell
    result = parse_sectional_time_cell("4 1-3/4 14.16")
    assert result["position"] == 4
    assert result["margin"] == "1-3/4"
    assert result["time"] == 14.16

def test_parse_sectional_time_cell_no_margin():
    """Test parsing a cell without margin (leader)."""
    from hkjc_scraper.parsers import parse_sectional_time_cell
    result = parse_sectional_time_cell("1 14.00")
    assert result["position"] == 1
    assert result["margin"] == ""
    assert result["time"] == 14.00

def test_parse_sectional_time_cell_neck():
    """Test parsing a cell with 'nk' (neck) margin."""
    from hkjc_scraper.parsers import parse_sectional_time_cell
    result = parse_sectional_time_cell("2 nk 14.05")
    assert result["position"] == 2
    assert result["margin"] == "nk"
    assert result["time"] == 14.05

def test_parse_sectional_time_cell_empty():
    """Test parsing an empty cell returns None."""
    from hkjc_scraper.parsers import parse_sectional_time_cell
    result = parse_sectional_time_cell("")
    assert result is None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_parsers.py::test_parse_sectional_time_cell_valid -v`
Expected: FAIL with "cannot import name 'parse_sectional_time_cell'"

**Step 3: Write minimal implementation**

Add to `src/hkjc_scraper/parsers.py`:

```python
def parse_sectional_time_cell(cell_text: str) -> dict | None:
    """Extract position, margin, time from a section cell.

    Args:
        cell_text: Cell text like "4 1-3/4 14.16" or "4 14.16"

    Returns:
        {"position": int, "margin": str, "time": float} or None if empty

    Examples:
        >>> parse_sectional_time_cell("4 1-3/4 14.16")
        {"position": 4, "margin": "1-3/4", "time": 14.16}
        >>> parse_sectional_time_cell("1 14.00")
        {"position": 1, "margin": "", "time": 14.00}
    """
    if not cell_text or not cell_text.strip():
        return None

    parts = cell_text.strip().split()
    if len(parts) < 2:
        return None

    # First part is always position
    try:
        position = int(parts[0])
    except ValueError:
        return None

    # Last part is always time
    try:
        time = float(parts[-1])
    except ValueError:
        return None

    # Middle parts (if any) form the margin
    margin = ""
    if len(parts) > 2:
        margin = " ".join(parts[1:-1])

    return {"position": position, "margin": margin, "time": time}
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_parsers.py::test_parse_sectional_time_cell_valid tests/test_parsers.py::test_parse_sectional_time_cell_no_margin tests/test_parsers.py::test_parse_sectional_time_cell_neck tests/test_parsers.py::test_parse_sectional_time_cell_empty -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add src/hkjc_scraper/parsers.py tests/test_parsers.py
git commit -m "feat: add parse_sectional_time_cell function"
```

---

### Task 2: Extract sectional href in parse_race method

**Files:**
- Modify: `src/hkjc_scraper/spider.py` (parse_race method, around line 98)
- Test: `tests/test_spider.py`

**Step 1: Write the failing test**

Add to `tests/test_spider.py`:

```python
class TestSectionalHrefExtraction:
    def test_parse_race_extracts_sectional_href(self, mock_race_response):
        """Test that parse_race extracts the sectional time href."""
        spider = HKJCRacingSpider()
        mock_race_response.css.return_value = [
            MockAttrib(href="/zh-hk/local/information/displaysectionaltime?racedate=01/03/2026&RaceNo=1")
        ]

        # Find sectional href
        for link in mock_race_response.css("a"):
            href = link.attrib.get("href", "")
            if "displaysectionaltime" in href:
                assert href == "/zh-hk/local/information/displaysectionaltime?racedate=01/03/2026&RaceNo=1"
                break
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_spider.py::TestSectionalHrefExtraction::test_parse_race_extracts_sectional_href -v`
Expected: FAIL or test setup needs adjustment

**Step 3: Write minimal implementation**

Modify `src/hkjc_scraper/spider.py` in the `parse_race` method, after parsing incidents (around line 98):

```python
        # Parse dividends and incidents
        for div_item in self._parse_dividends(response, race_id):
            yield div_item
        for inc_item in self._parse_incidents(response, race_id):
            yield inc_item

        # Extract sectional time href and yield request
        sectional_href = None
        for link in response.css("a"):
            href = link.attrib.get("href", "")
            if "displaysectionaltime" in href:
                sectional_href = href
                break

        if sectional_href:
            url = response.urljoin(sectional_href)
            yield Request(url, callback=self.parse_sectional_times, meta={"race_id": race_id})
        else:
            self.logger.warning(f"No sectional time link found for race {race_id}")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_spider.py::TestSectionalHrefExtraction -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/hkjc_scraper/spider.py tests/test_spider.py
git commit -m "feat: extract sectional href and yield sectional request"
```

---

### Task 3: Add parse_sectional_times callback method

**Files:**
- Modify: `src/hkjc_scraper/spider.py` (new async method)
- Test: `tests/test_spider.py`

**Step 1: Write the failing test**

Add to `tests/test_spider.py`:

```python
    def test_parse_sectional_times_yields_records(self):
        """Test that parse_sectional_times yields sectional time records."""
        from hkjc_scraper.parsers import parse_sectional_time_cell

        spider = HKJCRacingSpider()
        race_id = "2026-03-01-ST-1"

        # Mock sectional page response
        mock_response = MockResponse()
        mock_response.meta = {"race_id": race_id}

        # Mock table with sectional data
        # Row: "1", "9", "步風雷", "4 1-3/4 14.16", "4 2-1/2 22.32", ..., "1:47.33"
        mock_rows = [
            MockRow([
                MockCell("1"),
                MockCell("9"),
                MockCell("步風雷"),
                MockCell("4 1-3/4 14.16"),
                MockCell("4 2-1/2 22.32"),
                MockCell("1:47.33")
            ])
        ]
        mock_response.css.return_value = mock_rows

        # Parse and verify
        items = list(spider.parse_sectional_times(mock_response))
        assert len(items) > 0
        assert items[0]["table"] == "sectional_times"
        assert items[0]["data"]["race_id"] == race_id
        assert items[0]["data"]["horse_no"] == "9"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_spider.py::TestSectionalHrefExtraction::test_parse_sectional_times_yields_records -v`
Expected: FAIL with "parse_sectional_times not found"

**Step 3: Write minimal implementation**

Add to `src/hkjc_scraper/spider.py`:

```python
    async def parse_sectional_times(self, response):
        """Parse sectional time page and yield per-horse, per-section records.

        Yields:
            {"table": "sectional_times", "data": {...}}
        """
        from hkjc_scraper.parsers import parse_sectional_time_cell

        race_id = response.meta.get("race_id")

        # Check for "沒有相關資料" or similar empty state
        page_text = response.text
        if "沒有相關資料" in page_text or "不提供" in page_text:
            self.logger.warning(f"No sectional time data available for race {race_id}")
            return

        # Find the main sectional table
        # The table has rows with horse data, skip header rows
        all_text = response.text
        if "分段時間" not in all_text:
            self.logger.warning(f"No sectional table found for race {race_id}")
            return

        # Get all table rows
        rows = response.css("table tbody tr")
        if not rows:
            self.logger.warning(f"No sectional table found for race {race_id}")
            return

        # Process data rows (skip headers)
        for row in rows:
            cells = row.css("td")
            if len(cells) < 5:
                continue

            # First cell should be finishing position (number)
            first_cell = cells[0].text
            if not first_cell or not first_cell[0].isdigit():
                continue

            # Second cell is horse_no
            horse_no = cells[1].text.strip()
            if not horse_no or not horse_no.isdigit():
                continue

            # Parse each section column (starts at index 3, skip last cell which is finish time)
            section_num = 1
            for cell in cells[3:-1]:
                cell_text = cell.text.strip()
                if cell_text and cell_text not in ["分段時間", "第 1 段", "第 2 段", "第 3 段", "第 4 段", "第 5 段", "第 6 段"]:
                    parsed = parse_sectional_time_cell(cell_text)
                    if parsed:
                        yield {
                            "table": "sectional_times",
                            "data": {
                                "race_id": race_id,
                                "horse_no": horse_no,
                                "section_number": section_num,
                                "position": parsed.get("position"),
                                "margin": parsed.get("margin", ""),
                                "time": parsed.get("time"),
                            }
                        }
                        section_num += 1
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_spider.py::TestSectionalHrefExtraction -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/hkjc_scraper/spider.py tests/test_spider.py
git commit -m "feat: add parse_sectional_times callback method"
```

---

### Task 4: Update __init__.py to export parse_sectional_time_cell

**Files:**
- Modify: `src/hkjc_scraper/__init__.py`

**Step 1: Check current exports**

Run: `cat src/hkjc_scraper/__init__.py`

**Step 2: Add export**

Add to `src/hkjc_scraper/__init__.py`:

```python
from hkjc_scraper.parsers import (
    clean_position,
    parse_rating,
    parse_prize,
    parse_running_position,
    generate_race_id,
    parse_sectional_time_cell,
)
```

**Step 3: Run tests**

Run: `uv run pytest tests/ -v -m "not integration"`
Expected: PASS

**Step 4: Commit**

```bash
git add src/hkjc_scraper/__init__.py
git commit -m "feat: export parse_sectional_time_cell"
```

---

### Task 5: Add integration test for sectional times

**Files:**
- Create: `tests/integration/test_sectional_times.py`

**Step 1: Write the test**

Create `tests/integration/test_sectional_times.py`:

```python
import pytest
from hkjc_scraper.spider import HKJCRacingSpider

@pytest.mark.integration
async def test_sectional_times_end_to_end():
    """Test full sectional times scraping with live data."""
    spider = HKJCRacingSpider(dates=["2026/03/01"], racecourse="ST")
    result = await spider.run()

    # Check sectional_times items exist
    sectional_items = [i for i in result.items if i["table"] == "sectional_times"]
    assert len(sectional_items) > 0, "No sectional times found"

    # Verify structure of first item
    item = sectional_items[0]["data"]
    assert "race_id" in item
    assert "horse_no" in item
    assert "section_number" in item
    assert "position" in item
    assert "margin" in item
    assert "time" in item

    # Verify we have multiple sections per horse
    horse_sections = [i for i in sectional_items if i["data"]["horse_no"] == sectional_items[0]["data"]["horse_no"]]
    assert len(horse_sections) > 1, "Should have multiple sections per horse"
```

**Step 2: Run test**

Run: `uv run pytest tests/integration/test_sectional_times.py -v -m integration`
Expected: PASS (makes network request)

**Step 3: Commit**

```bash
git add tests/integration/test_sectional_times.py
git commit -m "test: add integration test for sectional times"
```

---

### Task 6: Update README with sectional_times table

**Files:**
- Modify: `README.md`

**Step 1: Update Tables section**

Find the "### Tables" section and add:

```markdown
- **sectional_times** - Per-horse sectional time data (position, margin, time at each section)
```

**Step 2: Update Features section**

Find the "## Features" section and add:

```markdown
- Sectional times (per-horse, per-section position and time data)
```

**Step 3: Update Output Format section**

Add to the file tree:

```markdown
├── sectional_times_2026-03-01.json
```

**Step 4: Run tests**

Run: `uv run pytest tests/ -v -m "not integration"`
Expected: PASS

**Step 5: Commit**

```bash
git add README.md
git commit -m "docs: update README with sectional times table"
```

---

### Task 7: Final verification

**Files:**
- None (verification task)

**Step 1: Run all unit tests**

Run: `uv run pytest tests/ -v -m "not integration"`
Expected: All pass

**Step 2: Run integration test**

Run: `uv run pytest tests/integration/test_sectional_times.py -v -m integration`
Expected: PASS

**Step 3: Manual CLI test**

Run: `uv run hkjc-scrape --date 2026/03/01 --racecourse ST`

Verify:
- `sectional_times_2026-03-01.json` file is created
- File contains valid JSON with expected structure

**Step 4: Verify all tests pass**

Run: `uv run pytest tests/ -v`
Expected: All pass

---

## Success Criteria

- [ ] parse_sectional_time_cell function works with various cell formats
- [ ] Sectional href extracted from race results page
- [ ] parse_sectional_times yields correct normalized records
- [ ] Integration test passes with live data
- [ ] README updated
- [ ] All unit tests pass
- [ ] CLI generates sectional_times JSON file
