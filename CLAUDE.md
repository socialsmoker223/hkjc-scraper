# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HKJC Horse Racing Data Scraper - A Python web scraper that collects horse racing data from the Hong Kong Jockey Club (HKJC) website and stores it in PostgreSQL. Uses modern Python tooling with `uv` package manager.

**Status**: Functional prototype (~60% complete). Core scraping and database infrastructure complete. Missing production hardening (error handling, logging, retries) and tests.

## Development Commands

### Setup
```bash
# Install dependencies
make install              # Production dependencies
make dev                  # Include dev dependencies (pytest, mypy, ruff)

# Or with uv directly
uv pip install -e .
uv pip install -e ".[dev]"
```

### Database Operations
```bash
make db-up               # Start PostgreSQL container
make db-down             # Stop PostgreSQL
make db-reset            # Reset database (WARNING: deletes all data)
make init-db             # Initialize/recreate tables
make db-shell            # Open psql shell
make db-logs             # View database logs
make pgadmin             # Start pgAdmin web UI (http://localhost:5050)
```

### Scraping
```bash
# Scrape races for a specific date
make scrape DATE=2025/12/23
hkjc-scraper 2025/12/23                      # Using console script
python -m hkjc_scraper 2025/12/23            # Using module

# Additional options
hkjc-scraper 2025/12/23 --dry-run            # Test without saving to DB
hkjc-scraper 2025/12/23 --init-db            # Initialize DB before scraping
hkjc-scraper 2025/12/23 --scrape-profiles    # Include horse profile scraping
```

### Code Quality
```bash
make format              # Format code with ruff
make lint                # Run ruff linter
make test                # Run pytest (no tests implemented yet)
uv run mypy .            # Type checking
make clean               # Clean temporary files
```

## Architecture

### File Structure & Responsibilities

**Package Structure (src/ layout):**
```
src/hkjc_scraper/
├── __init__.py         - Package exports and version
├── __main__.py         - Entry point for python -m hkjc_scraper
├── cli.py              - CLI interface with argparse (console scripts entry point)
├── config.py           - Configuration management using environment variables (.env)
├── database.py         - Database connection setup and table initialization
├── models.py           - SQLAlchemy ORM models (9 tables with full relationships)
├── persistence.py      - Data persistence layer with UPSERT operations
└── scraper.py          - Web scraping functions for HKJC website
```

**Console Scripts:**
- `hkjc-scraper` - Main CLI command (calls `hkjc_scraper.cli:main`)
- `hkjc` - Shorthand alias for `hkjc-scraper`

### Database Schema (9 Tables)

The database follows a normalized relational design:

**Core Entity Tables:**
- `meeting` - Race meetings (date, venue: ST/HV)
- `race` - Individual races (class, distance, track, going, prize)
- `horse` - Horse master data (code, names, HKJC ID)
- `jockey` - Jockey master data
- `trainer` - Trainer master data

**Performance Tables:**
- `runner` - Per-race per-horse performance (position, weights, odds, times)
- `horse_sectional` - Sectional time details (per-section positions, margins, split times)

**Profile Tables:**
- `horse_profile` - Current horse profile snapshot (1:1 with horse)
- `horse_profile_history` - Historical profile tracking (append-only)

**Key Relationships:**
- Meeting 1:N Race
- Race 1:N Runner
- Horse 1:N Runner, 1:N HorseSectional, 1:1 HorseProfile, 1:N HorseProfileHistory
- Runner 1:N HorseSectional
- Jockey/Trainer 1:N Runner

See `data_model.md` for detailed schema documentation (in Traditional Chinese).

### Data Flow

1. **Scraping** (`hkjc_scraper.py`):
   - `list_race_urls_for_meeting_all_courses()` - Discovers all races for a date from ResultsAll.aspx
   - `parse_localresults()` - Extracts race header + runner data from LocalResults.aspx
   - `parse_sectional_times()` - Extracts sectional data from DisplaySectionalTime.aspx
   - `scrape_horse_profile()` - Extracts horse profile from Horse.aspx (21 fields)

2. **Persistence** (`persistence.py`):
   - All functions follow `upsert_<entity>()` pattern
   - Uses SQLAlchemy SELECT + UPDATE/INSERT pattern (not native UPSERT)
   - Handles uniqueness constraints: meeting (date+venue), race (meeting+race_no), runner (race+horse)
   - Master entities (horse/jockey/trainer) use `code` as natural key

3. **Orchestration** (`main.py`):
   - Calls scraper functions
   - Batches data by race
   - Calls persistence layer
   - Commits per race (not per meeting)

### Important Patterns

**UPSERT Logic:**
All persistence functions follow this pattern:
```python
def upsert_entity(db: Session, data: Dict[str, Any]) -> Entity:
    stmt = select(Entity).where(Entity.unique_field == data["unique_field"])
    entity = db.execute(stmt).scalar_one_or_none()

    if entity:
        # Update existing
        for key, value in data.items():
            setattr(entity, key, value)
    else:
        # Insert new
        entity = Entity(**data)
        db.add(entity)

    db.flush()  # Get ID without committing
    return entity
```

**Code Extraction Pattern:**
HKJC uses URLs with IDs like `JockeyId=MDLR&...` or `HorseId=HK_2023_J344`. The scraper extracts these codes:
- Jockey code: Extract from `JockeyId` param (e.g., "MDLR")
- Trainer code: Extract from `TrainerId` param
- Horse code: Extract short code from `HorseId` (e.g., "J344" from "HK_2023_J344")
- HKJC Horse ID: Full ID like "HK_2023_J344"

**Data Conventions:**
- Traditional Chinese text stored as-is from HKJC site
- Date format in URLs: `YYYY/MM/DD` (forward slashes)
- Venues: "ST" (沙田/Sha Tin) or "HV" (跑馬地/Happy Valley)
- Track types: "草地" (turf) or "泥地" (dirt)

## Development Context

**Current State:**
- Phase 1 (Core Infrastructure): ✅ COMPLETED
- Phase 2 (Horse Profile Scraping): ✅ COMPLETED (see HORSE_PROFILE_IMPLEMENTATION.md)
- Phase 3 (Production Hardening): ❌ NOT STARTED
  - No error handling/retry logic
  - No logging system
  - No rate limiting
- Phase 5 (Testing & Quality): ❌ NOT STARTED
  - 0 tests written
  - pytest configured but unused

**Known Limitations:**
- No validation on scraped data
- No handling of HKJC website changes/errors
- No concurrent scraping (sequential only)
- Commit granularity is per-race (could be optimized)

See `ROADMAP.md` for complete development plan and feature list.

## Environment & Configuration

**Required Environment Variables** (`.env`):
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=hkjc_racing
DB_USER=hkjc_user
DB_PASSWORD=hkjc_password
```

Default values work with Docker setup. Copy `.env.example` to get started.

**Python Requirements:**
- Python 3.9+
- uv package manager
- Docker & Docker Compose

## Troubleshooting

**Database connection errors:**
- Check Docker container is running: `docker-compose ps`
- View logs: `make db-logs`
- Reset database: `make db-reset`

**Scraping errors:**
- Verify date format is `YYYY/MM/DD`
- Check if races exist for that date on HKJC website
- HKJC site structure may change (scraper uses BeautifulSoup with CSS selectors)

**uv issues:**
- Clear cache: `uv cache clean`
- Reinstall: `uv pip install -e . --reinstall`
