# Horse Profile Parser Fix Design

**Goal:** Fix the horse profile parser which is currently returning null/empty values due to incorrect HTML structure parsing.

**Date:** 2026-03-05

---

## Problem Analysis

### Current Issue
The horse profile data shows null/empty values:
```json
{
  "horse_id": "HK_2024_K306",
  "name": "",
  "country_of_birth": null,
  "sire": ":",
  "dam": ":",
  ...
}
```

### Root Cause
The parser uses `cells[1]` to extract values, but the HKJC page uses a 3-column table structure:
- `cells[0]` = label (e.g., "出生地 / 馬齡")
- `cells[1]` = ":" separator
- `cells[2]` = actual value ← **Should use this!**

### Page Structure Research
The horse profile page (`/zh-hk/local/information/horse?horseid=HK_2024_K306`) has:

**Table 1 - Basic Info:**
- 出生地 / 馬齡: 紐西蘭 / 4
- 毛色 / 性別: 棗 / 閹
- 進口類別: 自購新馬
- 今季獎金*: $1,285,375
- 總獎金*: $1,419,925
- 冠-亞-季-總出賽次數*: 2-0-2-17
- 最近十個賽馬日 出賽場數: 1
- 現在位置 (到達日期): 香港 (07/02/2026)
- 進口日期: 07/11/2024

**Table 2 - Trainer, Owner, Pedigree:**
- 練馬師: 方嘉柏
- 馬主: 劉耀棠與劉心暉
- 現時評分: 35
- 季初評分: 36
- 父系: Tivaci
- 母系: Promenade
- 外祖父: Savabeel

---

## Updated Data Model

### Revised `horses` Table

| Field | Type | Source | Example |
|-------|------|--------|---------|
| horse_id | string | URL | HK_2024_K306 |
| name | string | Page title | 堅多福 |
| country_of_birth | string | 出生地/馬齡 (split /) | 紐西蘭 |
| age | string | 出生地/馬齡 (split /) | 4 |
| colour | string | 毛色/性別 (split /) | 棗 |
| gender | string | 毛色/性別 (split /) | 閹 |
| import_type | string | 進口類別 | 自購新馬 |
| import_date | string | 進口日期 | 07/11/2024 |
| location | string | 現在位置 | 香港 |
| season_prize | int | 今季獎金* | 1285375 |
| total_prize | int | 總獎金* | 1419925 |
| career_wins | int | 冠-亞-季-總 (1st num) | 2 |
| career_places | int | 冠-亞-季-總 (2nd num) | 0 |
| career_shows | int | 冠-亞-季-總 (3rd num) | 2 |
| career_total | int | 冠-亞-季-總 (4th num) | 17 |
| current_rating | int | 現時評分 | 35 |
| initial_rating | int | 季初評分 | 36 |
| sire | string | 父系 | Tivaci |
| dam | string | 母系 | Promenade |
| damsire | string | 外祖父 | Savabeel |
| trainer | string | 練馬師 | 方嘉柏 |
| owner | string | 馬主 | 劉耀棠與劉心暉 |

**Changes from original model:**
- Changed `career_record` object to 4 separate columns (wins, places, shows, total)
- Added `trainer` and `owner` fields
- Added `location`, `import_date`, `import_type`
- Removed nested `career_record` structure for normalized storage

---

## Implementation

### Parser Rewrite

**File:** `src/hkjc_scraper/profile_parsers.py`

**Key changes:**
1. Use `cells[2]` for value extraction instead of `cells[1]`
2. Extract horse name from page title or h1 element
3. Parse combined fields (出生地/馬齡, 毛色/性別) by splitting on "/"
4. Parse prize money by removing "$" and "," then convert to int
5. Parse career record "W-P-S-T" format (e.g., "2-0-2-17")

**New implementation structure:**

```python
def parse_horse_profile(response: Any, horse_id: str, horse_name: str) -> dict:
    # Input validation
    if response is None or not hasattr(response, 'css'):
        return {"horse_id": horse_id, "name": horse_name}

    result = {default values...}

    # Extract horse name from page if not provided
    if not horse_name:
        # Try page title or h1
        title_elem = response.css("h1")
        if title_elem:
            horse_name = title_elem[0].text.split("(")[0].strip()

    rows = response.css("table tr")

    for row in rows:
        cells = row.css("td")
        if len(cells) >= 3:
            label = cells[0].text.strip()
            value = cells[2].text.strip()  # CHANGED: cells[2] not cells[1]

            # Parse combined fields
            if "出生地 / 馬齡" in label:
                parts = value.split("/")
                result["country_of_birth"] = parts[0].strip()
                result["age"] = parts[1].strip() if len(parts) > 1 else None

            elif "毛色 / 性別" in label:
                parts = value.split("/")
                result["colour"] = parts[0].strip()
                result["gender"] = parts[1].strip() if len(parts) > 1 else None

            # Parse prize money
            elif "今季獎金" in label:
                result["season_prize"] = parse_prize(value)

            # Parse career record
            elif "冠-亞-季-總出賽次數" in label:
                parts = value.split("-")
                if len(parts) >= 4:
                    result["career_wins"] = int(parts[0])
                    result["career_places"] = int(parts[1])
                    result["career_shows"] = int(parts[2])
                    result["career_total"] = int(parts[3])

            # Parse pedigree
            elif "父系" in label:
                result["sire"] = value
            elif "母系" in label:
                result["dam"] = value
            elif "外祖父" in label:
                result["damsire"] = value

            # Parse trainer and owner
            elif "練馬師" in label:
                result["trainer"] = value
            elif "馬主" in label:
                result["owner"] = value

            # Parse ratings
            elif "現時評分" in label:
                result["current_rating"] = int(value)
            elif "季初評分" in label:
                result["initial_rating"] = int(value)
```

---

## Testing

### Updated Unit Tests

**File:** `tests/test_profile_parsers.py`

**Tests to update:**
- `test_parse_horse_profile_basic_info` - Update for new field names and structure
- `test_parse_horse_profile_pedigree` - Test sire, dam, damsire extraction
- Remove old tests that don't match new structure

**New tests to add:**
- `test_parse_horse_profile_combined_fields` - Test splitting of 出生地/馬齡, 毛色/性別
- `test_parse_horse_profile_prize_money` - Test prize parsing ($1,285,375 → 1285375)
- `test_parse_horse_profile_career_record` - Test "2-0-2-17" → {wins: 2, places: 0, shows: 2, total: 17}
- `test_parse_horse_profile_trainer_owner` - Test trainer and owner extraction
- `test_parse_horse_profile_name_extraction` - Test horse name from page

**Integration test:**
- Run with live HKJC data
- Verify fields are populated (not null/empty)
- Sample assertion: `assert result["name"] != ""`
- `assert result["sire"] != ":"`

---

## Success Criteria

- [ ] Horse name is correctly extracted
- [ ] Sire/dam fields contain actual names, not ":"
- [ ] Country of birth, age, colour, gender are populated
- [ ] Prize money is correctly parsed as integer
- [ ] Career record is split into 4 fields
- [ ] Trainer and owner are extracted
- [ ] All unit tests pass
- [ ] Integration test shows real data
- [ ] Existing jockey/trainer profile parsers still work (no regression)

---

## Dependencies

- No new dependencies
- Uses existing `parse_prize` function from parsers.py
