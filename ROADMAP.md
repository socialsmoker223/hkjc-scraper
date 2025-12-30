# HKJC Horse Racing Data Scraper - Roadmap

## Current State Summary

Your HKJC horse racing data scraper is a **functional prototype (≈60% complete)** with production-ready infrastructure and core scraping features:

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

**❌ What's Missing:**
- **Phase 3**: Production hardening (error handling, logging, retries, rate limiting)
- **Phase 5**: Testing infrastructure (0 tests written)
- **Phase 5**: Code quality setup (mypy, linting rules not configured)
- **Phase 2**: Data validation logic

---

## Phase 1: Core Infrastructure (Foundation)
*Priority: Critical | Status: ✅ COMPLETED*

### 1.1 Database Setup
- [x] Create PostgreSQL database and tables from data_model.md schema
- [x] Set up SQLAlchemy ORM models with full relationships
- [x] Add indexes on foreign keys and frequently queried columns
- [x] Docker Compose setup for PostgreSQL
- [x] Optional pgAdmin web UI for database management
- [ ] Create database migration system (Alembic recommended)

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
*Priority: High | Status: 90% Complete (race/sectional/profile done, validation pending)*

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

### 2.2 Data Validation
- [ ] Add validation for critical fields (dates, race numbers, numeric values)
- [ ] Implement data quality checks:
  - [ ] Finish positions should be 1, 2, 3... or special values (PU, DNF, etc.)
  - [ ] Horse numbers should be unique per race
  - [ ] Sectional times should increase monotonically
  - [ ] All foreign keys should resolve (horse_code → horse.id)
- [ ] Log warnings for anomalies without failing scrapes
- [ ] Add optional `--strict` mode to fail on validation errors

---

## Phase 3: Production Hardening (Reliability)
*Priority: High | Status: 0% Complete - Critical for production use*

**Current issues:**
- ❌ No error handling beyond basic `try/except` in main.py
- ❌ No logging (only `print()` statements throughout codebase)
- ❌ No retry logic (network failures = immediate crash)
- ❌ No rate limiting (could trigger HKJC rate limits)
- ❌ HTTP errors bubble up with stack traces (in hkjc_scraper.py)

### 3.1 Error Handling & Resilience
- [ ] **Wrap all HTTP requests with retry logic** (in hkjc_scraper.py)
  - Use `tenacity` or `backoff` library
  - Exponential backoff: 1s, 2s, 4s, 8s, max 3 retries
  - Only retry on network errors (not 404/500)
- [ ] **Comprehensive exception handling** (in hkjc_scraper.py)
  - Network errors: `requests.exceptions.RequestException`
  - Parse failures: catch `AttributeError`, `IndexError` from BeautifulSoup
  - DB errors: catch `SQLAlchemyError`, rollback transaction
  - File-specific error handling in each scraping function
- [ ] **Add request timeouts** (in hkjc_scraper.py)
  - Current: 15s timeout (hardcoded in hkjc_scraper.py)
  - Make configurable via config.py
  - Add connection timeout separate from read timeout
- [ ] **Connection pooling** (in hkjc_scraper.py)
  - Use `requests.Session()` instead of `requests.get()`
  - Reuse connections across requests in same meeting
- [ ] **Rate limiting (politeness)** (in hkjc_scraper.py)
  - Add 1-2 second delay between race scrapes
  - Add 0.5 second delay between sectional/profile requests
  - Make configurable via config.py

### 3.2 Logging & Monitoring
**Current state:** Only `print()` statements, no log files, no levels

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
**Current behavior:** Scrapes everything, relies on UPSERT to handle duplicates (inefficient)

- [ ] **Check database before scraping** (avoid redundant downloads)
  - Query if meeting exists for (date, venue)
  - Query if race exists for (meeting_id, race_no)
  - Skip scraping if data already present (unless --force flag)
- [ ] **Implement "backfill" mode** for historical data
  - `python main.py --backfill --start 2024/01/01 --end 2024/12/31`
  - Iterate through date range
  - Skip weekdays with no races (check HKJC calendar)
- [ ] **Implement "update" mode** (only scrape new data)
  - `python main.py --update` (no date required)
  - Find max date in database: `SELECT MAX(date) FROM meeting`
  - Scrape from (max_date + 1 day) to today
- [ ] **Add date range support**
  - `python main.py --start 2025/12/01 --end 2025/12/31`
  - Validate date ranges
  - Progress bar for multi-date scraping (use `tqdm`)
- [ ] **Add --force flag to re-scrape existing data**
  - `python main.py 2025/12/23 --force`
  - Useful when HKJC updates results (e.g., inquiry changes)

---

## Phase 4: Usability & Automation (Operationalization)
*Priority: Medium | Status: 60% Complete (CLI done, scheduling pending)*

### 4.1 CLI & Scheduling
**Current state:** Basic CLI implemented in `main.py` with argparse

- [x] **Single date scraping** - `python main.py 2025/12/23` ✅
- [x] **Dry-run mode** - `--dry-run` flag ✅
- [x] **Initialize DB** - `--init-db` flag ✅
- [ ] **Enhanced CLI features** (move to Click for better UX):
  - [ ] Date range scraping: `--start 2024/01/01 --end 2024/12/31`
  - [ ] Backfill mode: `--backfill --start DATE --end DATE`
  - [ ] Update mode: `--update` (scrape since last DB entry)
  - [ ] Force re-scrape: `--force` (ignore existing data)
  - [ ] Verbose mode: `-v`, `-vv`, `-vvv` (control log level)
  - [ ] Progress bars for multi-date operations (tqdm)
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
*Priority: Medium | Status: 10% Complete (tooling ready, no tests written)*

**Current state:**
- ✅ `pytest` in dev dependencies (pyproject.toml)
- ✅ `ruff` in dev dependencies
- ✅ `mypy` in dev dependencies
- ✅ Makefile has `test`, `lint`, `format` targets
- ❌ **Zero test files exist** (no `tests/` directory)
- ❌ No ruff configuration
- ❌ No mypy configuration
- ❌ No pre-commit hooks

### 5.1 Testing Infrastructure ⚠️ **CRITICAL - ZERO TESTS**
- [ ] **Set up test infrastructure**
  - [ ] Create `tests/` directory
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
  - [ ] Add return type hints to all functions in hkjc_scraper.py
  - [ ] Add parameter type hints to all functions
  - [ ] Add type hints to persistence.py
- [ ] **Set up mypy for type checking**
  - [ ] Create `mypy.ini` or add `[tool.mypy]` to pyproject.toml
  - [ ] Configure strict mode
  - [ ] Fix all type errors
  - [ ] Add `make typecheck` target to Makefile
- [ ] **Configure linting (ruff)**
  - [ ] Create `ruff.toml` or add `[tool.ruff]` to pyproject.toml
  - [ ] Enable recommended rules
  - [ ] Configure line length (default 88 or 120)
  - [ ] Enable import sorting
  - [ ] Fix all linting errors
- [ ] **Pre-commit hooks**
  - [ ] Create `.pre-commit-config.yaml`
  - [ ] Add ruff formatting hook
  - [ ] Add ruff linting hook
  - [ ] Add mypy hook
  - [ ] Add trailing whitespace removal
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

**Current Phase:** Phase 3 - Production Hardening (making it production-ready)
**Overall Completion:** 70% → 75% (+5% from horse profile implementation)
**Last Updated:** 2025-12-24 (updated after horse profile implementation)
**Total Python Code:** ~1,900 lines across 6 files (+~180 lines for horse profiles)

### Completion by Phase
- ✅ **Phase 1: Core Infrastructure** - **95%** (NEARLY COMPLETE)
  - Database migration system (Alembic) still pending
  - Everything else working: DB, ORM, persistence, config, Docker

- ✅ **Phase 2: Complete Scraping** - **90%** (NEARLY COMPLETE ⬆️ from 50%)
  - ✅ Race results scraping: 100% (LocalResults.aspx fully parsed)
  - ✅ Sectional time scraping: 100% (DisplaySectionalTime.aspx fully parsed)
  - ✅ Horse profile scraping: **100%** ⬆️ (fully implemented 2025-12-24)
  - ❌ Data validation: 0% (only remaining item in Phase 2)

- ⏳ **Phase 3: Production Hardening** - **0%** (CRITICAL FOR PRODUCTION)
  - ❌ No error handling
  - ❌ No logging system
  - ❌ No retry logic
  - ❌ No rate limiting
  - ❌ No incremental updates

- ⏳ **Phase 4: Usability & Automation** - **60%** (CLI DONE, SCHEDULING PENDING)
  - ✅ Basic CLI: 100% (argparse, dry-run, init-db)
  - ✅ Documentation: 100% (comprehensive README.md)
  - ❌ Enhanced CLI: 0% (date ranges, backfill, update mode)
  - ❌ Scheduling: 0%

- ⏳ **Phase 5: Quality & Testing** - **10%** (TOOLING READY, NO TESTS)
  - ✅ Dependencies installed: pytest, mypy, ruff
  - ✅ Makefile targets: test, lint, format
  - ❌ Tests: 0% (no tests/ directory exists)
  - ❌ Configuration: 0% (no mypy.ini, ruff.toml, pre-commit)

- ⏳ **Phase 6: Advanced Features** - **15%** (DOCKER ONLY)
  - ✅ Docker Compose: 100% (PostgreSQL + pgAdmin)
  - ❌ Export functionality: 0%
  - ❌ Analytics: 0%
  - ❌ Async scraping: 0%

---

## Priority Recommendations

### Immediate Priorities (Get to Production MVP)
1. ~~**Implement horse profile scraping** (Phase 2.1)~~ ✅ **COMPLETED 2025-12-24**

2. **Add basic error handling & logging** (Phase 3.1, 3.2) ⬅️ **NEW TOP PRIORITY**
   - Critical for reliability
   - Replace print() with logging
   - Add try/except around HTTP requests

3. **Implement incremental updates** (Phase 3.3)
   - Check DB before scraping
   - Add --force flag to re-scrape

### Medium-Term Priorities (Production Ready)
4. **Write tests** (Phase 5.1)
   - At least test parsing functions
   - Save fixture HTML files

5. **Add data validation** (Phase 2.2)
   - Catch data quality issues early

6. **Enhanced CLI** (Phase 4.1)
   - Date range scraping
   - Progress bars (tqdm)

### Nice-to-Have (Future)
7. **Async scraping** (Phase 6.2) - 4x speed improvement
8. **Export functionality** (Phase 6.1) - CSV/JSON exports
9. **Analytics dashboards** (Phase 6.1) - Streamlit/Jupyter

---

## Quick Wins (Low Effort, High Value)
- ✅ Set up ruff configuration (5 minutes)
- ✅ Add logging.basicConfig() to main.py (10 minutes)
- ✅ Create .gitignore entry for logs/ directory (1 minute)
- ✅ Add --force flag to CLI (15 minutes)
- ✅ Add database existence check (30 minutes)
