# Horse Profile Parser Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the horse profile parser to correctly extract data from HKJC horse profile pages by using the correct table cell index and handling the actual HTML structure.

**Architecture:** Rewrite parse_horse_profile to use cells[2] for values instead of cells[1], extract horse name from page, parse combined fields by splitting, and update data model structure.

**Tech Stack:** Python 3.13, pytest, Scrapling Spider

---

### Task 1: Add helper function for parsing career record

**Files:**
- Modify: `src/hkjc_scraper/profile_parsers.py`
- Test: `tests/test_profile_parsers.py`

**Step 1: Write the failing test**

Add to `tests/test_profile_parsers.py`:

```python
def test_parse_career_record():
    """Test parsing career record string into components."""
    from hkjc_scraper.profile_parsers import parse_career_record
    result = parse_career_record("2-0-2-17")
    assert result == {"wins": 2, "places": 0, "shows": 2, "total": 17}

def test_parse_career_record_single_digit():
    """Test parsing with single digit components."""
    from hkjc_scraper.profile_parsers import parse_career_record
    result = parse_career_record("1-2-3-10")
    assert result == {"wins": 1, "places": 2, "shows": 3, "total": 10}
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_profile_parsers.py::test_parse_career_record -v`
Expected: FAIL with "cannot import name 'parse_career_record'"

**Step 3: Write minimal implementation**

Add to `src/hkjc_scraper/profile_parsers.py` (after extract_trainer_id function):

```python
def parse_career_record(record_str: str) -> dict | None:
    """Parse career record string into wins, places, shows, total.

    Args:
        record_str: Career record like "2-0-2-17" (wins-places-shows-total)

    Returns:
        {"wins": int, "places": int, "shows": int, "total": int} or None
    """
    if not record_str:
        return None
    parts = record_str.strip().split("-")
    if len(parts) != 4:
        return None
    try:
        return {
            "wins": int(parts[0]),
            "places": int(parts[1]),
            "shows": int(parts[2]),
            "total": int(parts[3]),
        }
    except ValueError:
        return None
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_profile_parsers.py::test_parse_career_record tests/test_profile_parsers.py::test_parse_career_record_single_digit -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/hkjc_scraper/profile_parsers.py tests/test_profile_parsers.py
git commit -m "feat: add parse_career_record helper function"
```

---

### Task 2: Rewrite parse_horse_profile with correct cell indexing

**Files:**
- Modify: `src/hkjc_scraper/profile_parsers.py`
- Test: `tests/test_profile_parsers.py`

**Step 1: Write the failing test**

Add to `tests/test_profile_parsers.py`:

```python
def test_parse_horse_profile_basic_info():
    """Test parsing horse profile with correct cell indexing."""
    from hkjc_scraper.profile_parsers import parse_horse_profile

    # Mock response with 3-cell table structure
    mock_response = MockResponse()
    mock_rows = [
        # Row: 出生地 / 馬齡 : 紐西蘭 / 4
        MockRow([
            MockCell("出生地 / 馬齡"),
            MockCell(":"),
            MockCell("紐西蘭 / 4")
        ]),
        # Row: 毛色 / 性別 : 棗 / 閹
        MockRow([
            MockCell("毛色 / 性別"),
            MockCell(":"),
            MockCell("棗 / 閹")
        ]),
    ]
    mock_response.css = MockCss(return_value=mock_rows)

    result = parse_horse_profile(mock_response, "HK_2024_K306", "堅多福")

    assert result["horse_id"] == "HK_2024_K306"
    assert result["name"] == "堅多福"
    assert result["country_of_birth"] == "紐西蘭"
    assert result["age"] == "4"
    assert result["colour"] == "棗"
    assert result["gender"] == "閹"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_profile_parsers.py::test_parse_horse_profile_basic_info -v`
Expected: FAIL (current implementation uses cells[1])

**Step 3: Rewrite parse_horse_profile function**

Replace the entire `parse_horse_profile` function in `src/hkjc_scraper/profile_parsers.py`:

```python
def parse_horse_profile(response: Any, horse_id: str, horse_name: str) -> dict:
    """Parse horse profile page response.

    Args:
        response: Scrapling response object (has .css() method and .text attribute)
        horse_id: Horse ID from href
        horse_name: Horse name from race results

    Returns:
        Dictionary with horse profile data including:
        - horse_id, name, country_of_birth, age, colour, gender
        - sire, dam, damsire, trainer, owner
        - current_rating, initial_rating, season_prize, total_prize
        - career_wins, career_places, career_shows, career_total
        - import_type, import_date, location
    """
    # Input validation guard clause
    if response is None or not hasattr(response, 'css') or not hasattr(response, 'text'):
        return {
            "horse_id": horse_id,
            "name": horse_name,
            "country_of_birth": None,
            "age": None,
            "colour": None,
            "gender": None,
            "sire": None,
            "dam": None,
            "damsire": None,
            "owner": None,
            "trainer": None,
            "current_rating": None,
            "initial_rating": None,
            "season_prize": None,
            "total_prize": None,
            "career_wins": 0,
            "career_places": 0,
            "career_shows": 0,
            "career_total": 0,
            "import_type": None,
            "import_date": None,
            "location": None,
        }

    # Extract horse name from page if not provided
    if not horse_name:
        title_elems = response.css("h1")
        if title_elems:
            title_text = title_elems[0].text
            # Format: "堅多福 - 馬匹資料" or "堅多福 (K306)"
            horse_name = title_text.split("-")[0].split("(")[0].strip()

    result = {
        "horse_id": horse_id,
        "name": horse_name,
        "country_of_birth": None,
        "age": None,
        "colour": None,
        "gender": None,
        "sire": None,
        "dam": None,
        "damsire": None,
        "owner": None,
        "trainer": None,
        "current_rating": None,
        "initial_rating": None,
        "season_prize": None,
        "total_prize": None,
        "career_wins": 0,
        "career_places": 0,
        "career_shows": 0,
        "career_total": 0,
        "import_type": None,
        "import_date": None,
        "location": None,
    }

    rows = response.css("table tr")

    for row in rows:
        cells = row.css("td")
        # Need at least 3 cells: label, separator (:), value
        if len(cells) >= 3:
            label = cells[0].text.strip()
            value = cells[2].text.strip()  # CHANGED: Use cells[2] not cells[1]

            if not label or not value or value == ":":
                continue

            # Parse combined fields: 出生地 / 馬齡
            if "出生地" in label and "馬齡" in label:
                parts = value.split("/")
                if len(parts) >= 1:
                    result["country_of_birth"] = parts[0].strip()
                if len(parts) >= 2:
                    result["age"] = parts[1].strip()

            # Parse combined fields: 毛色 / 性別
            elif "毛色" in label and "性別" in label:
                parts = value.split("/")
                if len(parts) >= 1:
                    result["colour"] = parts[0].strip()
                if len(parts) >= 2:
                    result["gender"] = parts[1].strip()

            # Parse import type
            elif "進口類別" in label:
                result["import_type"] = value

            # Parse import date
            elif "進口日期" in label:
                result["import_date"] = value

            # Parse location
            elif "現在位置" in label:
                # Value format: "香港 (07/02/2026)"
                result["location"] = value.split("(")[0].strip()

            # Parse prize money
            elif "今季獎金" in label:
                from hkjc_scraper.parsers import parse_prize
                result["season_prize"] = parse_prize(value)

            elif "總獎金" in label:
                from hkjc_scraper.parsers import parse_prize
                result["total_prize"] = parse_prize(value)

            # Parse career record: 冠-亞-季-總出賽次數
            elif "出賽次數" in label:
                career = parse_career_record(value)
                if career:
                    result["career_wins"] = career["wins"]
                    result["career_places"] = career["places"]
                    result["career_shows"] = career["shows"]
                    result["career_total"] = career["total"]

            # Parse pedigree
            elif label == "父系":
                result["sire"] = value

            elif label == "母系":
                result["dam"] = value

            elif label == "外祖父":
                result["damsire"] = value

            # Parse trainer
            elif label == "練馬師":
                result["trainer"] = value

            # Parse owner
            elif label == "馬主":
                result["owner"] = value

            # Parse ratings
            elif "現時評分" in label:
                try:
                    result["current_rating"] = int(value)
                except ValueError:
                    pass

            elif "季初評分" in label:
                try:
                    result["initial_rating"] = int(value)
                except ValueError:
                    pass

    return result
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_profile_parsers.py::test_parse_horse_profile_basic_info -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/hkjc_scraper/profile_parsers.py tests/test_profile_parsers.py
git commit -m "feat: rewrite parse_horse_profile with correct cell indexing"
```

---

### Task 3: Update spider to use new data model

**Files:**
- Modify: `src/hkjc_scraper/spider.py`
- Test: `tests/test_spider.py`

**Step 1: Update parse_horse_profile callback in spider**

The callback in spider.py calls the profile parser. Update to handle the new return structure with flattened career fields.

In `src/hkjc_scraper/spider.py`, the `parse_horse_profile` method should be updated to pass the data through correctly. The current implementation should work but verify:

```python
async def parse_horse_profile(self, response):
    """Parse horse profile page and yield horse data."""
    meta = response.meta
    horse_id = meta.get("horse_id")
    horse_name = meta.get("horse_name", "")

    profile_data = parse_horse_profile_data(response, horse_id, horse_name)
    profile_data["horse_id"] = horse_id
    yield {"table": "horses", "data": profile_data}
```

No changes needed if it just passes through the dict. Verify this works.

**Step 2: Run tests**

```bash
uv run pytest tests/test_spider.py::TestProfileParsers -v
```

**Step 3: Update output format to handle new fields**

The JSON output will have the new field structure. Verify integration still works.

**Step 4: Commit if needed**

```bash
git add src/hkjc_scraper/spider.py tests/test_spider.py
git commit -m "feat: update spider for new horse profile data model"
```

---

### Task 4: Update tests for new data model

**Files:**
- Modify: `tests/test_profile_parsers.py`
- Modify: `tests/integration/test_profile_scraping.py`

**Step 1: Remove/update old tests**

Remove or update tests that reference the old `career_record` object structure.

Old tests to update:
- `test_parse_horse_profile_career_stats` - Update to test individual fields
- Any test expecting `career_record` dict

**Step 2: Add tests for new fields**

Add tests for:
- Trainer extraction
- Owner extraction
- Location extraction
- Import type/date
- Ratings parsing

**Step 3: Update integration test**

In `tests/integration/test_profile_scraping.py`, update assertions:

```python
# Verify new fields are populated
assert result.get("name") not in [None, "", ":"]
assert result.get("sire") not in [None, "", ":"]
assert result.get("trainer") not in [None, "", ":"]
```

**Step 4: Run tests**

```bash
uv run pytest tests/test_profile_parsers.py -v
uv run pytest tests/integration/test_profile_scraping.py -v -m integration
```

**Step 5: Commit**

```bash
git add tests/test_profile_parsers.py tests/integration/test_profile_scraping.py
git commit -m "test: update tests for new horse profile data model"
```

---

### Task 5: Fix jockey and trainer parsers if needed

**Files:**
- Check: `src/hkjc_scraper/profile_parsers.py`
- Check: `tests/test_profile_parsers.py`

**Step 1: Verify jockey and trainer parsers**

Check if `parse_jockey_profile` and `parse_trainer_profile` have the same cell indexing issue.

```bash
uv run pytest tests/test_profile_parsers.py::TestJockeyProfileParser -v
uv run pytest tests/test_profile_parsers.py::TestTrainerProfileParser -v
```

**Step 2: Fix if needed**

If they use the same incorrect cell indexing, apply the same fix (use cells[2] instead of cells[1]).

**Step 3: Commit if changes made**

```bash
git add src/hkjc_scraper/profile_parsers.py tests/test_profile_parsers.py
git commit -m "fix: apply correct cell indexing to jockey/trainer parsers"
```

---

### Task 6: Integration test verification

**Files:**
- None (verification task)

**Step 1: Run all unit tests**

```bash
uv run pytest tests/ -v -m "not integration"
```

**Step 2: Run integration test with live data**

```bash
uv run pytest tests/integration/test_profile_scraping.py -v -m integration
```

**Step 3: Manual verification**

Run spider and check output:

```bash
uv run hkjc-scrape --date 2026/03/04 --racecourse HV
cat data/horses_2026-03-04.json | head -50
```

Verify:
- `name` field is populated (not empty)
- `sire`, `dam` contain horse names (not ":")
- `country_of_birth`, `age`, `colour`, `gender` are populated
- `trainer`, `owner` are populated

**Step 4: Final verification**

If all checks pass, the fix is complete. If issues remain, debug and fix.

---

## Success Criteria

- [ ] parse_career_record helper works correctly
- [ ] parse_horse_profile uses cells[2] for value extraction
- [ ] Horse name is extracted from page title
- [ ] Combined fields (出生地/馬齡, 毛色/性別) are split correctly
- [ ] Prize money is parsed to integer
- [ ] Career record is split into 4 fields
- [ ] All unit tests pass
- [ ] Integration test shows real data (not null/empty)
- [ ] Manual verification confirms correct extraction
