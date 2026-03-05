# Sectional Time Scraping Design

**Goal:** Add per-horse sectional time data extraction from HKJC sectional time pages.

**Date:** 2026-03-05

---

## Overview

Currently, the spider extracts race results but does not capture detailed sectional time data showing each horse's position, margin, and time at each section of the race. This design adds support for:

- **Per-horse sectional data** - position, margin from leader, and time at each section
- **Normalized storage** - one row per horse per section for easy analysis
- **Automatic fetching** - follows the sectional time href from race results pages
- **Graceful degradation** - logs warning for races without sectional data (e.g., year 2002)

---

## Architecture

### Two-Phase Approach

```
Phase 1: Race Results                Phase 2: Sectional Times
├─ Parse race results page           ├─ Extract horse rows
├─ Extract sectional href            ├─ Parse each section column
├─ Store race/performance data       ├─ Extract: position, margin, time
└─ Yield sectional Request           └─ Yield sectional_times records
```

### New Table: `sectional_times`

| Column | Type | Description |
|--------|------|-------------|
| race_id | string | Foreign key to races (format: YYYY-MM-DD-CC-N) |
| horse_no | string | Horse number from performance table |
| section_number | int | Section number (1-6, varies by race distance) |
| position | int | Position at this section (1-14) |
| margin | string | Distance to leader (e.g., "1-3/4", "2", "1/2", "nk") |
| time | float | Cumulative time at this section (e.g., 14.16) |

**Primary Key:** (race_id, horse_no, section_number)

---

## Data Flow

### URL Pattern

Sectional time URL is found on race results page as a link (typically an image/icon):
```
/zh-hk/local/information/displaysectionaltime?racedate=DD/MM/YYYY&RaceNo=N
```

**Note:** Date format in sectional URL differs from our spider (DD/MM/YYYY vs YYYY/MM/DD).
We will parse the href directly from the page to handle whatever format the site uses.

### Page Structure

**Summary table:**
- "時間" row: cumulative times at finish
- "分段時間" row: individual split times

**Main table (per horse):**
| Column | Content |
|--------|---------|
| 過終點次序 | Final position |
| 馬號 | Horse number |
| 馬名 | Horse name (with horse_id link) |
| 第1段, 第2段, ... | Position + margin + time for each section |

**Cell format example:** `4 1-3/4 14.16`
- `4` = position
- `1-3/4` = margin (1 3/4 lengths)
- `14.16` = cumulative time

---

## Implementation

### parsers.py Addition

```python
def parse_sectional_time_cell(cell_text: str) -> dict:
    """Extract position, margin, time from a section cell.

    Args:
        cell_text: Cell text like "4 1-3/4 14.16" or "4 14.16"

    Returns:
        {"position": 4, "margin": "1-3/4", "time": 14.16}

    Examples:
        >>> parse_sectional_time_cell("4 1-3/4 14.16")
        {"position": 4, "margin": "1-3/4", "time": 14.16}
        >>> parse_sectional_time_cell("1 14.00")
        {"position": 1, "margin": "", "time": 14.00}
    """
```

### spider.py Changes

#### 1. Modify `parse_race` to extract sectional href

```python
# After parsing dividends and incidents
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

#### 2. New callback method

```python
async def parse_sectional_times(self, response):
    """Parse sectional time page and yield per-horse, per-section records.

    Yields:
        {"table": "sectional_times", "data": {...}}
    """
    race_id = response.meta.get("race_id")

    # Check for "沒有相關資料" or similar empty state
    page_text = response.text
    if "沒有相關資料" in page_text or "不提供" in page_text:
        self.logger.warning(f"No sectional time data available for race {race_id}")
        return

    # Find the main sectional table
    rows = response.css("table tbody tr")
    if not rows:
        self.logger.warning(f"No sectional table found for race {race_id}")
        return

    # Skip header rows (過終點 次序 | 馬號 | 馬名 | ... | 完成時間)
    data_rows = [r for r in rows if _is_data_row(r)]

    for row in data_rows:
        cells = row.css("td")
        if len(cells) < 3:
            continue

        horse_no = cells[1].text.strip()
        if not horse_no.isdigit():
            continue

        # Parse each section column (starts at index 3)
        section_num = 1
        for cell in cells[3:-1]:  # Skip: position, horse_no, horse_name, finish_time
            cell_text = cell.text.strip()
            if cell_text:
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

---

## Error Handling

| Scenario | Handling |
|----------|----------|
| No sectional href on race page | Log warning, continue (old races like 2002) |
| Sectional page returns "沒有相關資料" | Log warning, return early |
| Sectional table missing/malformed | Log warning, return early |
| Empty cell in sectional table | Skip that section for that horse |

---

## Testing

### Unit Tests

```python
# tests/test_parsers.py

def test_parse_sectional_time_cell_valid():
    result = parse_sectional_time_cell("4 1-3/4 14.16")
    assert result["position"] == 4
    assert result["margin"] == "1-3/4"
    assert result["time"] == 14.16

def test_parse_sectional_time_cell_no_margin():
    result = parse_sectional_time_cell("1 14.00")
    assert result["position"] == 1
    assert result["margin"] == ""
    assert result["time"] == 14.00

def test_parse_sectional_time_cell_empty():
    result = parse_sectional_time_cell("")
    assert result is None or result == {}
```

### Spider Tests

```python
# tests/test_spider.py

class TestSectionalTimes:
    def test_parse_race_yields_sectional_request(self):
        # Verify sectional request is yielded when href exists

    def test_parse_sectional_times_yields_records(self):
        # Mock sectional page response, verify records yielded

    def test_parse_sectional_handles_missing_data(self):
        # Test warning log when no sectional data available
```

### Integration Test

```python
@pytest.mark.integration
async def test_sectional_times_end_to_end():
    spider = HKJCRacingSpider(dates=["2026/03/01"], racecourse="ST")
    result = await spider.run()

    sectional_items = [i for i in result.items if i["table"] == "sectional_times"]
    assert len(sectional_items) > 0

    # Verify structure
    item = sectional_items[0]["data"]
    assert "race_id" in item
    assert "horse_no" in item
    assert "section_number" in item
    assert "position" in item
    assert "margin" in item
    assert "time" in item
```

---

## Documentation Updates

### README.md

Add to Tables section:
```markdown
- **sectional_times** - Per-horse sectional time data (position, margin, time at each section)
```

Add to Features:
```markdown
- Sectional times (per-horse, per-section position and time data)
```

Add to Output Format:
```markdown
├── sectional_times_2026-03-01.json
```

---

## Success Criteria

- [ ] Sectional time href extracted from race results page
- [ ] Sectional times page parsed correctly
- [ ] `sectional_times` table created with normalized structure
- [ ] Error handling for missing/unavailable data
- [ ] Unit tests for parser function
- [ ] Spider tests for sectional parsing
- [ ] Integration test passing
- [ ] README updated
- [ ] CLI unchanged (backward compatible)

---

## Dependencies

- None (uses existing Scrapling Spider infrastructure)
