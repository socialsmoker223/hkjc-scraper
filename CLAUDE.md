# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HKJC Horse Racing Data Scraper - A Python web scraper that collects horse racing data from the Hong Kong Jockey Club (HKJC) website and stores it in PostgreSQL. Uses modern Python tooling with `uv` package manager.

**Status**: Production-ready system (~99% complete). Core scraping, database infrastructure, error handling, HK33 odds scraping, and CLI features complete. Missing pytest test suite for scraping functions.

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
make init-db             # Initialize tables (legacy, SQLAlchemy create_all)
make migrate             # Run migrations (RECOMMENDED, Alembic)
make migrate-create MSG="description"  # Create new migration
make migrate-history     # Show migration history
make migrate-current     # Show current revision
make migrate-downgrade   # Downgrade one migration
make db-shell            # Open psql shell
make db-logs             # View database logs
make pgadmin             # Start pgAdmin web UI (http://localhost:5050)
```

### Scraping
```bash
# Scrape races for a specific date
make scrape DATE=2025/12/23
hkjc-scraper 2025/12/23                      # Using console script
hkjc 2025/12/23                              # Using shorthand alias
python -m hkjc_scraper 2025/12/23            # Using module

# Additional options
hkjc-scraper --version                       # Show version number
hkjc-scraper 2025/12/23 --dry-run            # Test without saving to DB
hkjc-scraper --init-db                       # Initialize DB tables only
hkjc-scraper 2025/12/23 --force              # Force re-scrape existing data

# Horse profile scraping (enabled by default)
hkjc-scraper 2025/12/23                      # Includes profile scraping
hkjc-scraper 2025/12/23 --no-profiles        # Skip profiles for faster execution

# Date range and bulk operations
hkjc-scraper --date-range 2025/12/01 2025/12/31   # Scrape date range
hkjc-scraper --backfill 2024/01/01 2024/12/31     # Backfill historical data
hkjc-scraper --update                             # Update from last DB entry to today

# HK33 Odds Scraping (Requires .hk33_cookies or cookies.pkl)
hkjc-scraper 2026/01/14 --scrape-hk33             # Scrape HKJC and Offshore odds
hkjc-scraper 2026/01/14 --scrape-hk33-odds        # HKJC Win/Place odds only
hkjc-scraper 2026/01/14 --scrape-hk33-market      # Offshore market only
hkjc-scraper --login-hk33                         # Selenium auto-login (refresh cookies)
```

### Code Quality
```bash
make format              # Format code with ruff
make lint                # Run ruff linter
make test                # Run pytest
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

**Odds Tables:**
- `hkjc_odds` - Time-series HKJC win/place odds
- `offshore_market` - Offshore market buy/sell prices (blue/red columns)

**Key Relationships:**
- Meeting 1:N Race
- Race 1:N Runner
- Horse 1:N Runner, 1:N HorseSectional, 1:1 HorseProfile, 1:N HorseProfileHistory
- Horse 1:N HkjcOdds, 1:N OffshoreMarket
- Runner 1:N HorseSectional, 1:N HkjcOdds, 1:N OffshoreMarket
- Jockey/Trainer 1:N Runner

See `data_model.md` for detailed schema documentation (in Traditional Chinese).

### Data Flow

1. **Scraping** (`scraper.py`):
   - `list_race_urls_for_meeting_all_courses()` - Discovers all races for a date from ResultsAll.aspx
   - `parse_localresults()` - Extracts race header + runner data from LocalResults.aspx
   - `parse_sectional_times()` - Extracts sectional data from DisplaySectionalTime.aspx
   - `parse_sectional_times()` - Extracts sectional data from DisplaySectionalTime.aspx
   - `scrape_horse_profile()` - Extracts horse profile from Horse.aspx (21 fields)
   - `scrape_hk33_odds()` - Extracts odds from HK33.com using cookies (hk33_scraper.py)

2. **Persistence** (`persistence.py`):
   - All functions follow `upsert_<entity>()` pattern
   - Uses SQLAlchemy SELECT + UPDATE/INSERT pattern (not native UPSERT)
   - Handles uniqueness constraints: meeting (date+venue), race (meeting+race_no), runner (race+horse)
   - Master entities (horse/jockey/trainer) use `code` as natural key

3. **Orchestration** (`cli.py`):
   - Parses command-line arguments and selects mode (single date, date range, backfill, update)
   - Helper functions: `parse_date()`, `generate_date_range()`, `log_and_display()`
   - `ScrapingSummary` dataclass tracks statistics and generates reports
   - Calls scraper functions for each date
   - Batches data by race
   - Calls persistence layer
   - Commits per race (not per meeting)
   - Shows progress bars for multi-date operations

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

**Current State (Overall: ~99% Complete):**
- Phase 1 (Core Infrastructure): ✅ 100% COMPLETED
  - ✅ Database, ORM, persistence, config, Docker all working
  - ✅ Alembic migrations implemented (--migrate command)

- Phase 2 (Complete Scraping): ✅ 100% COMPLETED
  - ✅ Race results scraping (LocalResults.aspx)
  - ✅ Sectional time scraping (DisplaySectionalTime.aspx)
  - ✅ Horse profile scraping (Horse.aspx) - see HORSE_PROFILE_IMPLEMENTATION.md

- Phase 3 (Production Hardening): ✅ 98% COMPLETED
  - ✅ Error handling & retry logic (Phase 3.1 - tenacity library with exponential backoff)
  - ✅ Rate limiting & connection pooling (Phase 3.1)
  - ✅ Enhanced logging system with dual output (Phase 3.2 - console + file)
  - ✅ Summary reports with detailed statistics (Phase 3.2)
  - ✅ Supabase cloud database integration (Phase 3.4)
  - ✅ Incremental updates implemented (--date-range, --backfill, --update, --force)

- Phase 4 (Usability & Automation): ✅ 85% COMPLETED
  - ✅ Full-featured CLI with all modes
  - ✅ Console scripts (hkjc-scraper, hkjc)
  - ✅ Progress bars for multi-date operations
  - ✅ HK33 Odds Integration (Phase 6 features brought forward)
  - ❌ Missing: Scheduling/automation (cron, APScheduler)

- Phase 5 (Testing & Quality): ⏳ 30% IN PROGRESS
  - ✅ Tooling configured: pytest, mypy, ruff, pre-commit
  - ✅ Tests directory created
  - ❌ No pytest unit/integration tests for scraping functions yet

**Known Limitations:**
- No concurrent scraping (sequential only, could be optimized with async)
- Commit granularity is per-race (could batch by meeting)
- No pytest unit/integration tests for scraping functions

**Next Priority: Comprehensive Test Suite (Phase 5)**
Write pytest unit and integration tests for scraping functions to achieve better test coverage.

See `ROADMAP.md` for complete development plan and feature list.

## Environment & Configuration

**Database Configuration:**

The scraper supports two database backends:
- **Local PostgreSQL** (default): Uses Docker container
- **Supabase**: Cloud-hosted PostgreSQL

Switch between them using `DATABASE_TYPE` in `.env`:

```bash
# Local PostgreSQL (default)
DATABASE_TYPE=local
DB_HOST=localhost
DB_PORT=5432
DB_NAME=hkjc_racing
DB_USER=hkjc_user
DB_PASSWORD=hkjc_password

# Supabase (cloud)
DATABASE_TYPE=supabase
SUPABASE_URL=postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
```

**Key Points:**
- `config.get_db_url()` returns appropriate connection string based on `DATABASE_TYPE`
- Supabase uses smaller connection pool (pool_size=3) for PgBouncer compatibility
- Supabase URL uses port 6543 (pooler) for connections
- See `SUPABASE_SETUP.md` for complete Supabase setup guide

**Logging Configuration:**
```bash
LOG_LEVEL=INFO              # DEBUG, INFO, WARNING, ERROR
LOG_FILE=hkjc_scraper.log   # Path to log file
```

**HK33 Scraping Configuration:**
```bash
# HK33 Authentication (optional, for HK33.com odds scraping)
HK33_EMAIL=your_email@example.com
HK33_PASSWORD=your_password

# HK33 Rate Limiting & Timeouts
RATE_LIMIT_HK33=0.5              # Delay between requests (seconds)
HK33_REQUEST_TIMEOUT=30          # Request timeout (seconds)

# HK33 Concurrency Settings
MAX_HK33_RACE_WORKERS=4          # Concurrent race scraping
MAX_HK33_ODDS_WORKERS=6          # Concurrent odds type scraping per race
```

See `HK33_BROWSER_SCRAPING.md` for cookie extraction guide.

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

**HK33 scraping errors:**
- Error 403 Forbidden: Cookies expired, run `python extract_hk33_cookies.py` or `hkjc-scraper --login-hk33`
- Missing .hk33_cookies: Extract cookies from browser (see HK33_BROWSER_SCRAPING.md)

**uv issues:**
- Clear cache: `uv cache clean`
- Reinstall: `uv pip install -e . --reinstall`
