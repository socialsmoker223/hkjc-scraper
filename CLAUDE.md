# HKJC Scraper - Claude Context

This file contains project-specific context for Claude Code to work effectively on this codebase.

## Project Overview

**HKJC Racing Scraper** extracts horse racing data from the Hong Kong Jockey Club (HKJC) website using the Scrapling Spider framework.

- **Language:** Python 3.13+
- **Framework:** Scrapling (async web scraping)
- **Testing:** pytest with asyncio support
- **Package:** `hkjc_scraper`

## Module Organization

The codebase is organized into focused modules under `src/hkjc_scraper/`:

### Core Modules

| Module | Purpose | Key Functions |
|--------|---------|---------------|
| `spider.py` | Main spider implementation | `HKJCRacingSpider` class |
| `cli.py` | Command-line interface | `main()` entry point |
| `__init__.py` | Public API exports | 13 exported functions |

### Parser Modules

| Module | Purpose | Key Functions |
|--------|---------|---------------|
| `data_parsers.py` | Data parsing utilities | `clean_position`, `parse_rating`, `parse_prize`, `parse_running_position`, `generate_race_id`, `parse_sectional_time_cell` |
| `id_parsers.py` | ID extraction from URLs | `extract_horse_id`, `extract_jockey_id`, `extract_trainer_id` |
| `common.py` | Shared helper functions | `parse_career_record`, `_extract_text_after_label`, `_parse_career_stats_from_elements` |
| `horse_parsers.py` | Horse profile parsing | `parse_horse_profile` |
| `jockey_trainer_parsers.py` | Jockey/trainer parsing | `parse_jockey_profile`, `parse_trainer_profile` |

## Key Patterns and Conventions

### HTML Parsing (HKJC Specific)

HKJC uses a **3-column table structure** for profile pages:

```python
# HKJC profile table structure:
# Column 0: Label (e.g., "出生地 / 馬齡")
# Column 1: Separator (":")
# Column 2: Value (e.g., "紐西蘭 / 4")
```

**Important:** Some values are inside nested `<a>` tags. When `.text` returns empty, extract from the nested link:

```python
value_cell = cells[2]
value = value_cell.text.strip()

# If cell.text is empty, try extracting from nested <a> tag
if not value:
    links = value_cell.css("a")
    if links:
        value = links[0].text.strip()
```

### CSS Selectators Over Regex

**Prefer CSS selectors over regex** for parsing HTML:

```python
# Good: CSS selectors
all_tds = response.css("td")
result = _extract_text_after_label(all_tds, "背景：")

# Avoid: Regex on full HTML
# This is fragile and should be avoided
```

### Career Record Parsing

Career records follow the pattern: `wins-places-shows-total` (e.g., "2-0-2-17")

The label may have an asterisk suffix: `冠-亞-季-總出賽次數*`

### Public API

All public functions are exported via `__init__.py`. Import from the top-level package:

```python
from hkjc_scraper import (
    clean_position,
    parse_horse_profile,
    parse_jockey_profile,
    # ... etc
)
```

**Do NOT** import directly from submodules in user code or application code.

## Testing

### Running Tests

```bash
# Unit tests only (no network requests)
uv run pytest tests/ -v -m "not integration"

# Integration tests (makes network requests)
uv run pytest tests/ -v -m integration

# All tests
uv run pytest tests/ -v
```

### Test Organization

- `tests/test_parsers.py` - Tests for `data_parsers.py` functions
- `tests/test_profile_parsers.py` - Tests for all profile parsers
- `tests/test_spider.py` - Tests for `HKJCRacingSpider` class
- `tests/integration/` - End-to-end integration tests

### Test Markers

- `@pytest.mark.integration` - Marks integration tests that make network requests

## Common Tasks

### Adding a New Parser Function

1. Add the function to the appropriate parser module
2. Add comprehensive docstring with Args, Returns, Examples
3. Add type hints
4. Write tests in the corresponding test file
5. Export from `__init__.py` if it's part of the public API

### Updating Profile Parsers

Profile parsers use the 3-column table pattern. Follow the existing structure:

```python
for row in rows:
    cells = row.css("td")
    if len(cells) >= 3:
        label = cells[0].text
        value_cell = cells[2]
        value = value_cell.text.strip()

        # Handle nested <a> tags
        if not value:
            links = value_cell.css("a")
            if links:
                value = links[0].text.strip()
```

### Running the Scraper

```bash
# Crawl specific date and racecourse
uv run hkjc-scrape --date 2026/03/01 --racecourse ST

# Auto-discover latest race
uv run hkjc-scrape --racecourse ST
```

## Data Model

### Output Tables

| Table | Description |
|-------|-------------|
| `races` | Race metadata (date, class, distance, going, prize) |
| `performance` | Horse results per race (position, time, odds, jockey_id, trainer_id) |
| `dividends` | Payout information by pool type |
| `incidents` | Race incident reports |
| `horses` | Horse profiles (sire, dam, age, colour, gender, ratings, prize money) |
| `jockeys` | Jockey profiles (background, achievements, career stats) |
| `trainers` | Trainer profiles (background, achievements, career stats) |
| `sectional_times` | Per-horse sectional time data |

### Output Format

Data is saved as JSON with UTF-8 encoding in the `data/` directory:
```
data/
├── races_2026-03-01.json
├── performance_2026-03-01.json
├── dividends_2026-03-01.json
├── incidents_2026-03-01.json
├── horses_2026-03-01.json
├── jockeys_2026-03-01.json
├── trainers_2026-03-01.json
└── sectional_times_2026-03-01.json
```

## Important Gotchas

### ID Extraction

IDs are extracted from URL query parameters:
- Horse ID: `horseid=XXX`
- Jockey ID: `jockeyid=XXX`
- Trainer ID: `trainerid=XXX`

The extraction functions use compiled regex patterns for performance.

### Chinese Numerals

The `_CHINESE_NUMERALS` constant maps Chinese numerals to digits for position parsing:
- 一 → 1, 二 → 2, 三 → 3, etc.

### Rating Format

Ratings are in format `(min-max)` e.g., "(60-40)" → `{"min": 60, "max": 40}`

### Prize Money

Prize money may include:
- Currency symbol: `HK$`
- Commas: `1,170,000`
- Must be cleaned before int conversion

### Async/Await

The spider uses async/await. When working with `HKJCRacingSpider`:

```python
import asyncio
from hkjc_scraper.spider import HKJCRacingSpider

async def main():
    spider = HKJCRacingSpider(dates=["2026/03/01"], racecourse="ST")
    result = await spider.run()
    # Process result.items

asyncio.run(main())
```

## Code Style

- **PEP 8** compliant
- **Type hints** required for all function signatures
- **Docstrings** required for all public functions (Google style)
- **Line length** ≤ 100 characters
- **Import order**: stdlib → third-party → local

## Git Workflow

1. Create feature branch from `master`
2. Make atomic commits with clear messages
3. Run tests before committing
4. PR to `master` for review

### Commit Message Format

```
<type>: <description>

<optional detailed description>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`
