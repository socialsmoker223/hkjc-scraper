# HKJC Horse Racing Data Scraper - Roadmap

## Current State Summary

Your HKJC horse racing data scraper is a **functional prototype (≈85% complete)** with production-ready infrastructure and core scraping features:

**✅ What's Working:**
- ✅ **Web scraping for race results** (LocalResults.aspx in hkjc_scraper.py) - Fully implemented with 574 lines
  - Race header parsing (class, distance, track, going, prize)
  - Runner performance data (positions, weights, odds, times)
  - Horse, jockey, trainer extraction with code/ID parsing
- ✅ **Sectional time extraction** (DisplaySectionalTime.aspx in hkjc_scraper.py) - Fully implemented
  - Per-section performance for each horse
  - Section positions, margins, and split times
- ✅ **Meeting-level orchestration in hkjc_scraper.py** - Smart date-based scraping
  - Auto-detects all venues (ST/HV) for a given date
  - Scrapes all races across all venues
- ✅ **PostgreSQL database** with 9 normalized tables (1,705 total Python LOC)
- ✅ **SQLAlchemy ORM models** with full relationships
- ✅ **Data persistence layer** with UPSERT operations for all tables
- ✅ **Docker-based PostgreSQL** setup with pgAdmin web UI
- ✅ **Modern tooling** (uv package manager, Makefile, ruff formatter)
- ✅ **CLI interface** with argparse (dry-run mode, init-db flag)
- ✅ **Configuration management** (.env, config.py)
- ✅ **Comprehensive documentation** (README.md with quick start, troubleshooting)

**✅ Recently Completed:**
- ✅ **Horse profile scraping - FULLY IMPLEMENTED** (2025-12-24)
  - Parses all 21 fields from Horse.aspx
  - Integrated into main scraping flow with `--scrape-profiles` flag
  - Saves to both `horse_profile` and `horse_profile_history` tables
  - Includes deduplication and error handling
  - See `HORSE_PROFILE_IMPLEMENTATION.md` for details
- ✅ **Data validation - FULLY IMPLEMENTED** (2025-12-26)
  - Semi-strict validation mode with detailed logging
  - Validates positions, weights, odds, distances, ages
  - Horse profile consistency checks
  - Configurable via .env (VALIDATION_STRICT, VALIDATION_LOG_INVALID)
  - Test suite in tests/test_validators.py
- ✅ **Database migrations with Alembic - FULLY IMPLEMENTED** (2025-12-26)
  - Alembic configuration and migration scripts in alembic/
  - Makefile targets for all migration operations
  - Version control for database schema changes
- ✅ **Error handling and resilience - FULLY IMPLEMENTED** (2026-01-06)
  - Comprehensive error handling with retry logic
  - Network error recovery with exponential backoff
  - Parse failure handling and graceful degradation
  - Database transaction rollback on errors
  - Request timeouts and connection pooling
  - Rate limiting for politeness
- ✅ **Test suite fixes - FULLY IMPLEMENTED** (2026-01-06)
  - All validator tests now passing (100% pass rate)
  - Fixed 4 test failures in test_validators.py
  - Comprehensive validation test coverage

**❌ What's Missing:**
- **Phase 3**: Enhanced logging (structured logging, log rotation, summary reports)
- **Phase 3**: Supabase integration (cloud database option)
- **Phase 5**: Pytest test suite (unit/integration tests for scraping functions)
- **Phase 4**: Scheduling/automation (cron, APScheduler, systemd)

---

## Phase 1: Core Infrastructure (Foundation)
*Priority: Critical | Status: ✅ COMPLETED*

### 1.1 Database Setup
- [x] Create PostgreSQL database and tables from data_model.md schema
- [x] Set up SQLAlchemy ORM models with full relationships
- [x] Add indexes on foreign keys and frequently queried columns
- [x] Docker Compose setup for PostgreSQL
- [x] Optional pgAdmin web UI for database management
- [x] Create database migration system (Alembic) ✅ **COMPLETED**

### 1.2 Configuration Management
- [x] Create `pyproject.toml` for uv package manager
- [x] Set up `.env` for database credentials and settings
- [x] Create `config.py` for centralized configuration (DB URL, timeouts, base URLs)
- [x] Add `.gitignore` for Python projects (including uv and Docker)
- [x] Create Makefile with common commands

### 1.3 Data Persistence Layer
- [x] Implement UPSERT logic for all 9 tables:
  - `meeting` (unique: date + venue_code)
  - `race` (unique: meeting_id + race_no)
  - `horse`, `jockey`, `trainer` (unique: code)
  - `runner` (unique: race_id + horse_id)
  - `horse_sectional` (unique: runner_id + section_no)
- [x] Add transaction management with rollback on errors
- [x] Create foreign key resolution (code → database PK)
- [x] High-level save functions for complete race data

---

## Phase 2: Complete Scraping (Feature Parity)
*Priority: High | Status: ✅ COMPLETED*

### 2.1 Horse Profile Scraping ✅ **COMPLETED (2025-12-24)**
**Implementation:** `hkjc_scraper.py:322-479`, integrated into main flow

**What was implemented:**
- [x] **Parse horseProfile table from Horse.aspx HTML** (BeautifulSoup implementation) ✅
  - Extract basic info: origin, age, colour, sex, import_type ✅
  - Extract statistics: season_prize_hkd, lifetime_prize_hkd ✅
  - Extract record: wins, seconds, thirds, starts, last10_starts ✅
  - Extract location: current_location, current_location_date, import_date ✅
  - Extract ownership: owner_name ✅
  - Extract ratings: current_rating, season_start_rating ✅
  - Extract pedigree: sire_name, dam_name, dam_sire_name ✅
- [x] **Add date parsing** for current_location_date, import_date fields ✅
- [x] **Add numeric parsing** with error handling for prize money, ratings, records ✅
- [x] **Integrate into main scraping flow** ✅
  - **Implementation:** Option A (scrape during race scraping with `--scrape-profiles` flag)
  - Includes deduplication to avoid re-scraping same horse
  - Error handling continues on failure
- [x] **Persistence logic** already existed in `persistence.py`: ✅
  - `upsert_horse_profile()` function (line 179)
  - `insert_horse_profile_history()` function (line 208)
  - Updated `save_race_data()` to save profiles (line 397-427)

**Test Results:** 21/21 fields (100%) - See `HORSE_PROFILE_IMPLEMENTATION.md`

### 2.2 Data Validation ✅ **COMPLETED (2025-12-26)**
**Implementation:** `validators.py`, integrated into scraping flow

**What was implemented:**
- [x] Add validation for critical fields (dates, race numbers, numeric values)
- [x] Implement data quality checks:
  - [x] Finish positions should be 1, 2, 3... or special values (PU, DNF, etc.)
  - [x] Weights validation (95-165 lbs for actual and 900-1400 declared)
  - [x] Odds validation (must be positive)
  - [x] Distance validation (1000-2850 meters)
  - [x] Horse age validation (2-14 years)
  - [x] Horse profile consistency (wins+seconds+thirds <= starts, season_prize <= lifetime_prize)
- [x] Log warnings for anomalies without failing scrapes (semi-strict mode)
- [x] Configurable validation via .env (VALIDATION_STRICT, VALIDATION_LOG_INVALID)
- [x] Test suite in tests/test_validators.py

---

## Phase 3: Production Hardening (Reliability)
*Priority: High | Status: 65% Complete ⬆️ - Error handling complete, logging needs enhancement*

**Current state:**
- ✅ Comprehensive error handling with retry logic
- ✅ Network error recovery with exponential backoff
- ✅ Parse failure handling and graceful degradation
- ✅ Database transaction rollback on errors
- ✅ Request timeouts and connection pooling
- ✅ Rate limiting for politeness
- ⚠️ Basic logging configured (hkjc_scraper.log) but needs enhancement
- ❌ No cloud database option (Supabase integration not implemented)

### 3.1 Error Handling & Resilience ✅ **COMPLETED (2026-01-06)**
- [x] **Wrap all HTTP requests with retry logic** (in hkjc_scraper.py) ✅
  - Uses `tenacity` library with exponential backoff
  - Exponential backoff: 1s, 2s, 4s, 8s, max 3 retries
  - Only retries on network errors (not 404/500)
- [x] **Comprehensive exception handling** (in hkjc_scraper.py) ✅
  - Network errors: `requests.exceptions.RequestException`
  - Parse failures: catch `AttributeError`, `IndexError` from BeautifulSoup
  - DB errors: catch `SQLAlchemyError`, rollback transaction
  - File-specific error handling in each scraping function
- [x] **Add request timeouts** (in hkjc_scraper.py) ✅
  - Configurable via config.py
  - Connection timeout separate from read timeout
- [x] **Connection pooling** (in hkjc_scraper.py) ✅
  - Uses `requests.Session()` instead of `requests.get()`
  - Reuses connections across requests in same meeting
- [x] **Rate limiting (politeness)** (in hkjc_scraper.py) ✅
  - Configurable delays between race scrapes
  - Configurable delays between sectional/profile requests
  - Configured via config.py

### 3.2 Logging & Monitoring
**Current state:** Basic logging configured (writes to hkjc_scraper.log) but needs enhancement

- [ ] **Replace all `print()` with proper logging**
  - Use Python `logging` module (stdlib) or `loguru` (recommended)
  - Configure in config.py
- [ ] **Set up log levels:**
  - `INFO`: "Scraping race X/Y", "Saved N runners", "Meeting complete"
  - `WARNING`: "Missing field: horse_no", "Skipping invalid row"
  - `ERROR`: "HTTP 404 for race", "Database rollback", "Parse failed"
  - `DEBUG`: Raw HTML snippets, intermediate data structures
- [ ] **Log to multiple destinations:**
  - Console: INFO and above (for user feedback)
  - File: DEBUG and above (for debugging) - rotate daily
  - Path: `logs/hkjc_YYYY-MM-DD.log`
- [ ] **Add structured logging fields:**
  - `date`, `venue`, `race_no` for context
  - `duration` for performance tracking
- [ ] **Create summary reports at end of scraping:**
  ```
  === Scraping Summary ===
  Date: 2025/12/23
  Duration: 45.2 seconds
  Races scraped: 10/10 (100%)
  Runners saved: 123
  Sectionals saved: 1,230
  Errors: 0
  Warnings: 3 (see log for details)
  ```

### 3.3 Incremental Updates & Smart Scraping
**Current behavior:** Smart scraping with database checks and incremental update support

- [x] **Check database before scraping** (avoid redundant downloads)
  - Query if meeting exists for (date, venue)
  - Query if race exists for (meeting_id, race_no)
  - Skip scraping if data already present (unless --force flag)
- [x] **Implement "backfill" mode** for historical data
  - `python main.py --backfill 2024/01/01 2024/12/31`
  - Iterate through date range
  - Skip weekdays with no races (check HKJC calendar)
- [x] **Implement "update" mode** (only scrape new data)
  - `python main.py --update` (no date required)
  - Find max date in database: `SELECT MAX(date) FROM meeting`
  - Scrape from (max_date + 1 day) to today
- [x] **Add date range support**
  - `python main.py --date-range 2025/12/01 2025/12/31`
  - Validate date ranges
  - Progress bar for multi-date scraping (use `tqdm`)
- [x] **Add --force flag to re-scrape existing data**
  - `python main.py 2025/12/23 --force`
  - Useful when HKJC updates results (e.g., inquiry changes)

### 3.4 Supabase Integration
**Goal:** Add Supabase as a cloud database option for easy deployment and real-time features

- [ ] **Supabase connection support**
  - [ ] Add Supabase configuration to `.env` (SUPABASE_URL, SUPABASE_KEY)
  - [ ] Create Supabase client wrapper in `database.py`
  - [ ] Support both local PostgreSQL and Supabase via config flag
  - [ ] Update connection string builder to handle Supabase format
- [ ] **Schema migration to Supabase**
  - [ ] Export current schema to Supabase-compatible SQL
  - [ ] Run Alembic migrations against Supabase database
  - [ ] Verify all table relationships and indexes in Supabase dashboard
  - [ ] Test UPSERT operations with Supabase (may need adjustments for RLS)
- [ ] **Real-time features (optional)**
  - [ ] Set up Supabase real-time subscriptions for data changes
  - [ ] Enable Row-Level Security (RLS) policies for multi-user access
  - [ ] Create public API views for read-only access
- [ ] **Deployment benefits**
  - [ ] No Docker/PostgreSQL setup required
  - [ ] Automatic backups and point-in-time recovery
  - [ ] Built-in authentication for future web interface
  - [ ] Global CDN for faster access
  - [ ] Free tier: 500MB database, 2GB bandwidth

---

## Phase 4: Usability & Automation (Operationalization)
*Priority: Medium | Status: 85% Complete (CLI features complete, scheduling pending)*

### 4.1 CLI & Scheduling
**Current state:** Full-featured CLI implemented in `cli.py` with argparse, console scripts, and progress tracking

- [x] **Single date scraping** - `hkjc-scraper 2025/12/23` ✅
- [x] **Dry-run mode** - `--dry-run` flag ✅
- [x] **Initialize DB** - `--init-db` flag ✅
- [x] **Enhanced CLI features** ✅ **COMPLETED**
  - [x] Date range scraping: `--date-range 2024/01/01 2024/12/31`
  - [x] Backfill mode: `--backfill 2024/01/01 2024/12/31`
  - [x] Update mode: `--update` (scrape since last DB entry)
  - [x] Force re-scrape: `--force` (ignore existing data)
  - [x] Progress bars for multi-date operations (tqdm)
  - [ ] Verbose mode: `-v`, `-vv`, `-vvv` (control log level)
- [ ] **Scheduling & Automation**
  - [ ] Add cron job example in docs (run daily at 10 PM HKT)
  - [ ] Or use APScheduler for in-process scheduling
  - [ ] Or create systemd service file (Linux)
  - [ ] Handle HKJC race schedule (only scrape on race days)
  - [ ] Send notifications on failures (email/Slack/Discord)

### 4.2 Documentation ✅ **COMPLETED**
**Current state:** Comprehensive README.md with 393 lines covering all essential topics

- [x] Project description and features ✅
- [x] Installation instructions (uv, Docker, PostgreSQL) ✅
- [x] Configuration guide (.env variables) ✅
- [x] Usage examples (CLI commands, Makefile) ✅
- [x] Database management (Docker, pgAdmin) ✅
- [x] Troubleshooting section ✅
- [x] Development status and roadmap reference ✅
- [ ] **Still missing (nice-to-have):**
  - [ ] Database schema diagram (ERD)
  - [ ] Architecture/data flow diagram
  - [ ] HKJC website structure documentation
  - [ ] API documentation (if building REST API later)

---

## Phase 5: Quality & Testing (Maturity)
*Priority: Medium | Status: 50% Complete ⬆️ (tooling configured, validator tests passing)*

**Current state:**
- ✅ `pytest` in dev dependencies (pyproject.toml)
- ✅ `ruff` in dev dependencies
- ✅ `mypy` in dev dependencies
- ✅ Makefile has `test`, `lint`, `format` targets
- ✅ `tests/` directory created with test_validators.py
- ✅ Ruff configured in pyproject.toml (line-length, linting rules)
- ✅ Mypy configured in pyproject.toml (type checking settings)
- ✅ Pre-commit hooks configured (.pre-commit-config.yaml)
- ✅ **Validator tests complete** - 100% pass rate (test_validators.py) ⬆️
- ❌ **No pytest tests for scraping functions** (need unit/integration tests)

### 5.1 Testing Infrastructure ⏳ **IN PROGRESS - Validator tests complete, scraping tests needed**
- [x] **Set up test infrastructure**
  - [x] Create `tests/` directory
  - [x] Create `tests/test_validators.py` - 100% pass rate ✅ **COMPLETED (2026-01-06)**
  - [ ] Create `tests/conftest.py` with pytest fixtures
  - [ ] Create `tests/test_parsing.py` for scraping functions
  - [ ] Create `tests/test_persistence.py` for database operations
  - [ ] Create `tests/fixtures/` for mock HTML files
- [ ] **Unit tests for parsing functions** (from hkjc_scraper.py)
  - [ ] `test_parse_race_header()` - test race class, distance, going extraction
  - [ ] `test_parse_runner_rows()` - test horse/jockey/trainer extraction
  - [ ] `test_scrape_sectional_time()` - test sectional parsing
  - [ ] `test_scrape_horse_profile()` - test profile parsing
  - [ ] Test edge cases: missing fields, malformed HTML, Chinese characters
- [ ] **Integration tests with mock HTML responses**
  - [ ] Save real HKJC HTML to `tests/fixtures/`
  - [ ] Mock `requests.get()` to return fixture HTML
  - [ ] Test end-to-end parsing without hitting real HKJC site
- [ ] **Database integration tests**
  - [ ] Use in-memory SQLite or separate test PostgreSQL DB
  - [ ] Test `upsert_meeting()`, `upsert_race()`, etc.
  - [ ] Test foreign key resolution (horse_code → horse.id)
  - [ ] Test transaction rollback on errors
- [ ] **End-to-end tests**
  - [ ] Test complete scraping workflow with fixtures
  - [ ] Test CLI commands (subprocess calls)
  - [ ] Test dry-run mode
- [ ] **Test coverage**
  - [ ] Set up pytest-cov
  - [ ] Target: >80% code coverage
  - [ ] Generate HTML coverage reports

### 5.2 Code Quality
- [ ] **Type hints** (partially done, needs completion)
  - Current: models.py has full type hints via SQLAlchemy Mapped[]
  - [ ] Add return type hints to all functions in scraper.py
  - [ ] Add parameter type hints to all functions
  - [ ] Add type hints to persistence.py
- [x] **Set up mypy for type checking**
  - [x] Add `[tool.mypy]` to pyproject.toml
  - [x] Configure basic settings (check_untyped_defs, no_implicit_optional, etc.)
  - [ ] Configure strict mode
  - [ ] Fix all type errors
  - [x] Add `make typecheck` target to Makefile
- [x] **Configure linting (ruff)**
  - [x] Add `[tool.ruff]` to pyproject.toml
  - [x] Enable recommended rules (E, W, F, I, B, C4, UP)
  - [x] Configure line length (120)
  - [x] Enable import sorting
  - [ ] Fix all linting errors
- [x] **Pre-commit hooks**
  - [x] Create `.pre-commit-config.yaml`
  - [x] Add ruff formatting hook
  - [x] Add ruff linting hook
  - [ ] Add mypy hook
  - [x] Add trailing whitespace removal
  - [ ] Document setup in README

---

## Phase 6: Advanced Features (Enhancements)
*Priority: Low | Status: 15% Complete (Docker done)*

### 6.1 Data Analytics & Export
- [ ] **Create data export functionality**
  - [ ] CSV export: `python main.py --export csv --table runners --output data.csv`
  - [ ] JSON export for API consumption
  - [ ] Parquet export for data science (pandas/polars)
  - [ ] Export filters: by date range, venue, horse, jockey
- [ ] **Build analytics queries**
  - [ ] Horse performance trends (win rate by distance, track, class)
  - [ ] Jockey/trainer statistics (ROI, strike rate, favorite performance)
  - [ ] Sectional analysis (identify speed horses vs closers)
  - [ ] Create SQL views for common queries
- [ ] **Data visualization**
  - [ ] Jupyter notebooks with example analyses
  - [ ] Interactive dashboards (Streamlit, Dash, or Metabase)
  - [ ] Horse form charts, sectional heatmaps
  - [ ] Track bias analysis (rail position advantage)

### 6.2 Deployment & Scaling
- [x] **Docker Compose setup** ✅ (PostgreSQL + pgAdmin)
- [ ] **Dockerize application**
  - [ ] Create `Dockerfile` for scraper application
  - [ ] Multi-stage build (builder + runtime)
  - [ ] Update docker-compose.yml to include scraper service
  - [ ] Add health checks
- [ ] **Environment-specific configs**
  - [ ] `.env.dev`, `.env.staging`, `.env.prod`
  - [ ] Different DB hosts, credentials per environment
  - [ ] Feature flags (enable/disable horse profiles, etc.)
- [ ] **Performance optimization**
  - [ ] Async scraping with `aiohttp` + `asyncio`
  - [ ] Parallel requests for multiple races
  - [ ] Could reduce scraping time from ~45s to ~10s for 10 races
- [ ] **Distributed scraping** (if dataset grows to years of history)
  - [ ] Celery workers + Redis/RabbitMQ
  - [ ] Task queue for date ranges
  - [ ] Monitor with Flower dashboard

### 6.3 Data Enrichment
- [ ] **Scrape additional HKJC pages**
  - [ ] Dividends page (WIN/PLA/QIN/QPL/TCE/TRI/F-F/Quartet pools)
  - [ ] Track work times (gallop times between races)
  - [ ] Veterinary reports (injuries, medications)
  - [ ] Jockey bookings (declared runners before race day)
  - [ ] Barrier trial results (practice races)
- [ ] **Add calculated fields** (derived metrics)
  - [ ] Speed ratings (compare finish times across different conditions)
  - [ ] Form indicators (last 3 runs, days since last run)
  - [ ] Class rise/drop (comparing current race to previous)
  - [ ] Weight carried vs. optimal weight
  - [ ] Sectional speed ratings (identify acceleration patterns)
- [ ] **Historical trend tables** (materialized views or separate tables)
  - [ ] Horse career statistics by surface, distance, class
  - [ ] Jockey/trainer partnership stats
  - [ ] Head-to-head records between horses
- [ ] **Machine learning features** (optional, advanced)
  - [ ] Feature engineering for race prediction
  - [ ] Export to ML-friendly format (feature matrix + labels)
  - [ ] Integration with scikit-learn, XGBoost, LightGBM

---

## Progress Tracking

**Current Phase:** Phase 3 - Production Hardening (error handling complete, logging enhancement needed)
**Overall Completion:** 88% ⬆️ (+3% from error handling and test fixes)
**Last Updated:** 2026-01-06 (updated after error handling implementation and test fixes)
**Total Python Code:** ~2,100 lines across 8 files (+validators.py, +test_validators.py)

### Completion by Phase
- ✅ **Phase 1: Core Infrastructure** - **100% COMPLETED** ⬆️
  - ✅ Database migration system (Alembic): **100%** ⬆️ (implemented with alembic/)
  - ✅ Everything working: DB, ORM, persistence, config, Docker

- ✅ **Phase 2: Complete Scraping** - **100% COMPLETED** ⬆️
  - ✅ Race results scraping: 100% (LocalResults.aspx fully parsed)
  - ✅ Sectional time scraping: 100% (DisplaySectionalTime.aspx fully parsed)
  - ✅ Horse profile scraping: 100% (fully implemented 2025-12-24)
  - ✅ Data validation: **100%** ⬆️ (implemented with validators.py 2025-12-26)

- ⏳ **Phase 3: Production Hardening** - **65%** ⬆️ (ERROR HANDLING COMPLETE, LOGGING NEEDS ENHANCEMENT)
  - ✅ Error handling & resilience: 100% ⬆️ (retry logic, timeouts, connection pooling, rate limiting)
  - ⚠️ Logging & monitoring: 50% (hkjc_scraper.log configured, needs structured logging enhancement)
  - ✅ Incremental updates: 100% (smart scraping, backfill, update, range)
  - ❌ Supabase integration: 0%

- ⏳ **Phase 4: Usability & Automation** - **85%** (CLI FEATURES COMPLETE, SCHEDULING PENDING)
  - ✅ Basic CLI: 100% (argparse, dry-run, init-db)
  - ✅ Documentation: 100% (comprehensive README.md)
  - ✅ Enhanced CLI: 100% (date-range, backfill, update mode, force flag, progress bars)
  - ❌ Scheduling: 0% (cron jobs, APScheduler, systemd services)

- ⏳ **Phase 5: Quality & Testing** - **50%** ⬆️ (TOOLING CONFIGURED, VALIDATOR TESTS PASSING)
  - ✅ Dependencies installed: pytest, mypy, ruff, pre-commit
  - ✅ Makefile targets: test, lint, format, typecheck
  - ✅ Configuration: ruff, mypy, pre-commit hooks all configured
  - ✅ Tests directory created (tests/__init__.py)
  - ✅ Validator tests: 100% pass rate ⬆️ (test_validators.py - all tests passing)
  - ❌ Scraping function tests: 0% (no pytest suite for scraping/persistence yet)

- ⏳ **Phase 6: Advanced Features** - **15%** (DOCKER ONLY)
  - ✅ Docker Compose: 100% (PostgreSQL + pgAdmin)
  - ❌ Export functionality: 0%
  - ❌ Analytics: 0%
  - ❌ Async scraping: 0%

---

## Priority Recommendations

### Immediate Priorities (Get to Production MVP)
1. ~~**Implement horse profile scraping** (Phase 2.1)~~ ✅ **COMPLETED 2025-12-24**

2. ~~**Implement incremental updates** (Phase 3.3)~~ ✅ **COMPLETED 2025-01-02**

3. ~~**Add data validation** (Phase 2.2)~~ ✅ **COMPLETED 2025-12-26**

4. ~~**Database migrations with Alembic** (Phase 1.1)~~ ✅ **COMPLETED 2025-12-26**

5. ~~**Add comprehensive error handling & retry logic** (Phase 3.1)~~ ✅ **COMPLETED 2026-01-06**

6. ~~**Fix test failures** (Phase 5.1)~~ ✅ **COMPLETED 2026-01-06**

7. **Enhance logging system** (Phase 3.2) ⬅️ **NEW TOP PRIORITY**
   - Replace print() with structured logging
   - Log rotation and levels (INFO/WARNING/ERROR/DEBUG)
   - Summary reports at end of scraping
   - Multi-destination logging (console + file)

8. **Write pytest test suite for scraping** (Phase 5.1)
   - Test parsing functions with fixtures
   - Integration tests for database operations
   - Save fixture HTML files
   - Unit tests for all scraping functions

### Nice-to-Have (Future)
9. **Async scraping** (Phase 6.2) - 4x speed improvement
10. **Export functionality** (Phase 6.1) - CSV/JSON exports
11. **Analytics dashboards** (Phase 6.1) - Streamlit/Jupyter

---

## Quick Wins (Low Effort, High Value)
- ✅ Set up ruff configuration (5 minutes)
- ✅ Add logging.basicConfig() to main.py (10 minutes)
- ✅ Create .gitignore entry for logs/ directory (1 minute)
- ✅ Add --force flag to CLI (15 minutes)
- ✅ Add database existence check (30 minutes)
