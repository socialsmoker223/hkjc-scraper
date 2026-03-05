# Codebase Refactoring Implementation Plan

**Date:** 2026-03-05
**Status:** Approved
**Author:** Implementation Planner

## Executive Summary

This plan details the refactoring of the HKJC scraper codebase to improve maintainability and code organization. The refactoring splits large files into focused modules while maintaining backward compatibility with the public API.

## Goals

1. Split `parsers.py` into focused modules (`id_parsers.py`, `data_parsers.py`)
2. Split `profile_parsers.py` into domain-specific modules (`horse_parsers.py`, `jockey_trainer_parsers.py`, `common.py`)
3. Update `__init__.py` with explicit exports (remove wildcard import)
4. Delete obsolete `tests/integration_test.py` file
5. Ensure all tests pass after refactoring
6. Commit after each logical group of changes

## Constraints

- **No breaking changes** to the public API
- **All tests must pass** after refactoring
- Follow TDD approach: write failing test (if applicable), run to verify failure, implement, run to verify pass, commit

## Current State

### File Structure

```
src/hkjc_scraper/
├── __init__.py          # Uses wildcard import for profile_parsers
├── cli.py               # Imports from spider module
├── parsers.py           # 219 lines - contains ID and data parsing functions
├── profile_parsers.py   # 542 lines - contains all profile parsing + helpers
└── spider.py            # 549 lines - imports from both parsers

tests/
├── integration/         # New integration tests directory
├── integration_test.py  # Old integration test (to be deleted)
├── test_parsers.py      # Tests for parsers.py functions
└── test_profile_parsers.py  # Tests for profile_parsers.py functions
```

### Functions to Move

#### From `parsers.py`:

**To `id_parsers.py`:**
- `extract_horse_id(href: str) -> str | None`
- `extract_jockey_id(href: str) -> str | None`
- `extract_trainer_id(href: str) -> str | None`

**To `data_parsers.py`:**
- `clean_position(text: str | None) -> str`
- `parse_rating(rating_text: str) -> dict[str, int] | None`
- `parse_prize(prize_text: str) -> int`
- `parse_running_position(element: Any) -> list[str]`
- `generate_race_id(race_date: str, racecourse: str, race_no: int) -> str`
- `parse_sectional_time_cell(cell_text: str) -> dict[str, int | str | float] | None`

#### From `profile_parsers.py`:

**To `common.py`:**
- `parse_career_record(record_str: str) -> dict | None`
- `_extract_text_after_label(elements, label_text: str) -> str | None`
- `_parse_career_stats_from_elements(elements) -> tuple | None`

**To `horse_parsers.py`:**
- `parse_horse_profile(response: Any, horse_id: str, horse_name: str) -> dict`

**To `jockey_trainer_parsers.py`:**
- `parse_jockey_profile(response: Any, jockey_id: str, jockey_name: str) -> dict`
- `parse_trainer_profile(response: Any, trainer_id: str, trainer_name: str) -> dict`

## Implementation Tasks

### Task 1: Create `id_parsers.py` Module

**File:** `/home/jc/code/hkjc-scraper/src/hkjc_scraper/id_parsers.py`

**Functions to move:**
- `extract_horse_id`
- `extract_jockey_id`
- `extract_trainer_id`

**Steps:**
1. Create new file `id_parsers.py` with the three ID extraction functions from `parsers.py`
2. Add module docstring explaining purpose
3. Keep function signatures and implementations identical

**Verification:**
- No tests needed (functions are pure, existing tests will work via imports)

**Commit message:**
```
refactor: create id_parsers.py module

Extract ID extraction functions from parsers.py into dedicated module:
- extract_horse_id
- extract_jockey_id
- extract_trainer_id
```

---

### Task 2: Create `data_parsers.py` Module

**File:** `/home/jc/code/hkjc-scraper/src/hkjc_scraper/data_parsers.py`

**Functions to move:**
- `clean_position`
- `parse_rating`
- `parse_prize`
- `parse_running_position`
- `generate_race_id`
- `parse_sectional_time_cell`

**Dependencies:**
- `re` module
- `_CHINESE_NUMERALS` constant (must be included)

**Steps:**
1. Create new file `data_parsers.py` with data parsing functions
2. Include the `_CHINESE_NUMERALS` constant mapping
3. Add module docstring

**Verification:**
- No tests needed (existing tests will work via imports)

**Commit message:**
```
refactor: create data_parsers.py module

Extract data parsing functions from parsers.py into dedicated module:
- clean_position
- parse_rating
- parse_prize
- parse_running_position
- generate_race_id
- parse_sectional_time_cell
```

---

### Task 3: Create `common.py` Module

**File:** `/home/jc/code/hkjc-scraper/src/hkjc_scraper/common.py`

**Functions to move:**
- `parse_career_record`
- `_extract_text_after_label`
- `_parse_career_stats_from_elements`

**Steps:**
1. Create new file `common.py` with helper functions
2. Add module docstring explaining these are internal helpers

**Verification:**
- No tests needed (functions are tested indirectly via profile parser tests)

**Commit message:**
```
refactor: create common.py module

Extract shared helper functions from profile_parsers.py:
- parse_career_record
- _extract_text_after_label
- _parse_career_stats_from_elements
```

---

### Task 4: Create `horse_parsers.py` Module

**File:** `/home/jc/code/hkjc-scraper/src/hkjc_scraper/horse_parsers.py`

**Functions to move:**
- `parse_horse_profile`

**Dependencies:**
- `parse_career_record` from `common.py` (import)

**Steps:**
1. Create new file `horse_parsers.py`
2. Move `parse_horse_profile` function
3. Add import: `from .common import parse_career_record`

**Verification:**
- No tests needed (existing tests will work via imports)

**Commit message:**
```
refactor: create horse_parsers.py module

Extract horse profile parsing from profile_parsers.py:
- parse_horse_profile

Dependencies:
- parse_career_record from common.py
```

---

### Task 5: Create `jockey_trainer_parsers.py` Module

**File:** `/home/jc/code/hkjc-scraper/src/hkjc_scraper/jockey_trainer_parsers.py`

**Functions to move:**
- `parse_jockey_profile`
- `parse_trainer_profile`

**Dependencies:**
- `_extract_text_after_label` from `common.py` (import)
- `_parse_career_stats_from_elements` from `common.py` (import)

**Steps:**
1. Create new file `jockey_trainer_parsers.py`
2. Move both profile parsing functions
3. Add imports from `common.py`

**Verification:**
- No tests needed (existing tests will work via imports)

**Commit message:**
```
refactor: create jockey_trainer_parsers.py module

Extract jockey and trainer profile parsing from profile_parsers.py:
- parse_jockey_profile
- parse_trainer_profile

Dependencies:
- _extract_text_after_label from common.py
- _parse_career_stats_from_elements from common.py
```

---

### Task 6: Update `__init__.py` with Explicit Exports

**File:** `/home/jc/code/hkjc-scraper/src/hkjc_scraper/__init__.py`

**Current content:**
```python
"""HKJC Racing Scraper - Extract horse racing data from HKJC."""

from hkjc_scraper.parsers import (
    clean_position,
    parse_rating,
    parse_prize,
    parse_running_position,
    generate_race_id,
    parse_sectional_time_cell,
)
from hkjc_scraper.profile_parsers import *
```

**New content:**
```python
"""HKJC Racing Scraper - Extract horse racing data from HKJC."""

# Data parsing utilities
from hkjc_scraper.data_parsers import (
    clean_position,
    parse_rating,
    parse_prize,
    parse_running_position,
    generate_race_id,
    parse_sectional_time_cell,
)

# ID extraction utilities
from hkjc_scraper.id_parsers import (
    extract_horse_id,
    extract_jockey_id,
    extract_trainer_id,
)

# Career record parsing
from hkjc_scraper.common import (
    parse_career_record,
)

# Profile parsing
from hkjc_scraper.horse_parsers import (
    parse_horse_profile,
)
from hkjc_scraper.jockey_trainer_parsers import (
    parse_jockey_profile,
    parse_trainer_profile,
)

__all__ = [
    # Data parsers
    "clean_position",
    "parse_rating",
    "parse_prize",
    "parse_running_position",
    "generate_race_id",
    "parse_sectional_time_cell",
    # ID parsers
    "extract_horse_id",
    "extract_jockey_id",
    "extract_trainer_id",
    # Common
    "parse_career_record",
    # Profile parsers
    "parse_horse_profile",
    "parse_jockey_profile",
    "parse_trainer_profile",
]
```

**Steps:**
1. Replace wildcard import with explicit imports from each new module
2. Add `__all__` list for explicit public API

**Verification:**
- Run tests to ensure public API is intact

**Commit message:**
```
refactor: update __init__.py with explicit exports

Replace wildcard import with explicit imports from new modules:
- data_parsers
- id_parsers
- common
- horse_parsers
- jockey_trainer_parsers

Add __all__ to define public API explicitly.
```

---

### Task 7: Update Imports in `spider.py`

**File:** `/home/jc/code/hkjc-scraper/src/hkjc_scraper/spider.py`

**Current imports:**
```python
from hkjc_scraper.parsers import (
    clean_position,
    parse_rating,
    parse_prize,
    parse_running_position,
    generate_race_id,
    parse_sectional_time_cell,
)

from hkjc_scraper.profile_parsers import (
    parse_horse_profile as parse_horse_profile_data,
    parse_jockey_profile as parse_jockey_profile_data,
    parse_trainer_profile as parse_trainer_profile_data,
)
```

**New imports:**
```python
from hkjc_scraper.data_parsers import (
    clean_position,
    parse_rating,
    parse_prize,
    parse_running_position,
    generate_race_id,
    parse_sectional_time_cell,
)

from hkjc_scraper.horse_parsers import (
    parse_horse_profile as parse_horse_profile_data,
)
from hkjc_scraper.jockey_trainer_parsers import (
    parse_jockey_profile as parse_jockey_profile_data,
    parse_trainer_profile as parse_trainer_profile_data,
)
```

**Steps:**
1. Update imports from `parsers` to `data_parsers`
2. Update imports from `profile_parsers` to the specific modules

**Verification:**
- Run `pytest tests/test_spider.py -v`
- Ensure all spider tests pass

**Commit message:**
```
refactor: update imports in spider.py

Update imports to use new module structure:
- parsers -> data_parsers
- profile_parsers -> horse_parsers, jockey_trainer_parsers
```

---

### Task 8: Update Imports in `cli.py`

**File:** `/home/jc/code/hkjc-scraper/src/hkjc_scraper/cli.py`

**Analysis:** The `cli.py` file only imports `HKJCRacingSpider` from `spider.py`, not directly from parser modules. No changes needed.

**Verification:**
- Run `pytest tests/ -v` to ensure CLI still works

**Commit message:**
```
refactor: verify cli.py compatibility

No import changes needed - cli.py only imports from spider module.
Verified that CLI still works with new module structure.
```

---

### Task 9: Delete Old `parsers.py` File

**File:** `/home/jc/code/hkjc-scraper/src/hkjc_scraper/parsers.py`

**Prerequisites:**
- All functions have been moved to new modules
- All imports updated
- Tests pass

**Steps:**
1. Delete `parsers.py` file
2. Run tests to ensure nothing still imports from it

**Verification:**
- Run full test suite: `pytest tests/ -v`
- Should have no import errors

**Commit message:**
```
refactor: remove old parsers.py file

All functions have been moved to specialized modules:
- id_parsers.py
- data_parsers.py
```

---

### Task 10: Delete Old `profile_parsers.py` File

**File:** `/home/jc/code/hkjc-scraper/src/hkjc_scraper/profile_parsers.py`

**Prerequisites:**
- All functions have been moved to new modules
- All imports updated
- Tests pass

**Steps:**
1. Delete `profile_parsers.py` file
2. Run tests to ensure nothing still imports from it

**Verification:**
- Run full test suite: `pytest tests/ -v`
- Should have no import errors

**Commit message:**
```
refactor: remove old profile_parsers.py file

All functions have been moved to specialized modules:
- common.py
- horse_parsers.py
- jockey_trainer_parsers.py
```

---

### Task 11: Delete Obsolete `tests/integration_test.py`

**File:** `/home/jc/code/hkjc-scraper/tests/integration_test.py`

**Reason:** This file is superseded by the `tests/integration/` directory which contains more comprehensive integration tests.

**Steps:**
1. Delete `tests/integration_test.py`
2. Verify new integration tests in `tests/integration/` still work

**Verification:**
- Run `pytest tests/integration/ -v -m integration`
- All integration tests should pass

**Commit message:**
```
refactor: remove obsolete integration_test.py

Superseded by tests/integration/ directory which contains
more comprehensive integration tests.
```

---

### Task 12: Update `test_parsers.py` Imports

**File:** `/home/jc/code/hkjc-scraper/tests/test_parsers.py`

**Current imports:**
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

**New imports:**
```python
from hkjc_scraper.data_parsers import (
    clean_position,
    parse_rating,
    parse_prize,
    parse_running_position,
    generate_race_id,
    parse_sectional_time_cell,
)
```

**Steps:**
1. Update import statement
2. Run tests to verify

**Verification:**
- Run `pytest tests/test_parsers.py -v`
- All tests should pass

**Commit message:**
```
refactor: update imports in test_parsers.py

Update to import from data_parsers module instead of parsers.
```

---

### Task 13: Update `test_profile_parsers.py` Imports

**File:** `/home/jc/code/hkjc-scraper/tests/test_profile_parsers.py`

**Current imports:**
```python
from hkjc_scraper.profile_parsers import (
    extract_horse_id,
    extract_jockey_id,
    extract_trainer_id,
    parse_horse_profile,
    parse_jockey_profile,
    parse_trainer_profile,
    parse_career_record,
)
```

**New imports:**
```python
from hkjc_scraper.id_parsers import (
    extract_horse_id,
    extract_jockey_id,
    extract_trainer_id,
)
from hkjc_scraper.common import (
    parse_career_record,
)
from hkjc_scraper.horse_parsers import (
    parse_horse_profile,
)
from hkjc_scraper.jockey_trainer_parsers import (
    parse_jockey_profile,
    parse_trainer_profile,
)
```

**Steps:**
1. Update import statements
2. Run tests to verify

**Verification:**
- Run `pytest tests/test_profile_parsers.py -v`
- All tests should pass

**Commit message:**
```
refactor: update imports in test_profile_parsers.py

Update to import from new module structure:
- id_parsers
- common
- horse_parsers
- jockey_trainer_parsers
```

---

### Task 14: Update Integration Test Imports

**Files:**
- `/home/jc/code/hkjc-scraper/tests/integration/test_profile_scraping.py`
- `/home/jc/code/hkjc-scraper/tests/integration/test_sectional_times.py`

**Analysis:** Check if these files import directly from parser modules.

**Steps:**
1. Read both files to check imports
2. Update if needed
3. Run integration tests to verify

**Commit message:**
```
refactor: update imports in integration tests

Update integration tests to use new module structure.
```

---

### Task 15: Run Full Test Suite

**Command:**
```bash
pytest tests/ -v
```

**Expected results:**
- All unit tests pass
- All integration tests pass (if running with integration marker)

**Acceptance criteria:**
- Zero test failures
- Zero import errors
- All tests that previously passed still pass

**Commit message:**
```
test: verify full test suite passes after refactoring

Ran complete test suite after module reorganization:
- All unit tests passing
- All integration tests passing
- No import errors
- Public API intact
```

---

### Task 16: Update README Documentation

**File:** `/home/jc/code/hkjc-scraper/README.md`

**Add section on module organization:**

```markdown
## Module Organization

The scraper is organized into focused modules:

- **data_parsers.py** - General data parsing utilities (positions, ratings, prizes, race IDs)
- **id_parsers.py** - ID extraction from HKJC URLs (horse, jockey, trainer)
- **common.py** - Shared helper functions (career record parsing)
- **horse_parsers.py** - Horse profile parsing
- **jockey_trainer_parsers.py** - Jockey and trainer profile parsing
- **spider.py** - Main spider implementation
- **cli.py** - Command-line interface

### Public API

The `__init__.py` exports all public functions. Import from the top-level package:

```python
from hkjc_scraper import (
    clean_position,
    parse_horse_profile,
    parse_jockey_profile,
    # ... etc
)
```
```

**Steps:**
1. Add module organization section to README
2. Update any outdated module references

**Commit message:**
```
docs: update README with new module structure

Document the reorganized module layout and public API.
```

---

### Task 17: Final Verification

**Steps:**
1. Run full test suite again
2. Check for any remaining references to old modules in code
3. Verify `cli.py` still works: `uv run hkjc-scrape --help`
4. Verify programmatic usage still works
5. Check for any TODO or FIXME comments added during refactoring

**Commands:**
```bash
# Full test suite
pytest tests/ -v

# Check for old module references
grep -r "from hkjc_scraper.parsers" src/ tests/
grep -r "from hkjc_scraper.profile_parsers" src/ tests/

# CLI verification
uv run hkjc-scrape --help
```

**Acceptance criteria:**
- No references to old modules remain
- All tests pass
- CLI works
- No temporary comments or code

**Commit message:**
```
refactor: complete codebase refactoring

Completed reorganization of parser modules:

New structure:
- data_parsers.py - data parsing utilities
- id_parsers.py - ID extraction functions
- common.py - shared helpers
- horse_parsers.py - horse profile parsing
- jockey_trainer_parsers.py - jockey/trainer parsing

Removed:
- parsers.py (replaced by data_parsers.py, id_parsers.py)
- profile_parsers.py (split into 3 modules)
- tests/integration_test.py (superseded by tests/integration/)

All tests passing. Public API intact.
```

---

## Summary of Changes

### Files Created
1. `src/hkjc_scraper/id_parsers.py`
2. `src/hkjc_scraper/data_parsers.py`
3. `src/hkjc_scraper/common.py`
4. `src/hkjc_scraper/horse_parsers.py`
5. `src/hkjc_scraper/jockey_trainer_parsers.py`

### Files Modified
1. `src/hkjc_scraper/__init__.py` - Updated exports
2. `src/hkjc_scraper/spider.py` - Updated imports
3. `tests/test_parsers.py` - Updated imports
4. `tests/test_profile_parsers.py` - Updated imports
5. `tests/integration/test_profile_scraping.py` - May need import updates
6. `tests/integration/test_sectional_times.py` - May need import updates
7. `README.md` - Document new structure

### Files Deleted
1. `src/hkjc_scraper/parsers.py`
2. `src/hkjc_scraper/profile_parsers.py`
3. `tests/integration_test.py`

## Testing Strategy

### Unit Tests
- Existing tests in `test_parsers.py` and `test_profile_parsers.py` cover all moved functions
- Only import statements need updating
- No test logic changes required

### Integration Tests
- Tests in `tests/integration/` verify end-to-end functionality
- These test the spider which imports from the new modules

### Regression Testing
- Run full test suite after each task
- Public API remains unchanged, so external code continues to work

## Rollback Plan

If issues arise:
1. Each task is committed separately
2. Can revert individual commits
3. Can restore old files from git history

To rollback completely:
```bash
git revert <commit-range> --no-commit
```

## Completion Checklist

- [ ] All new modules created
- [ ] All imports updated
- [ ] Old files deleted
- [ ] All tests pass
- [ ] README updated
- [ ] No references to old modules remain
- [ ] CLI works correctly
- [ ] Integration tests pass
