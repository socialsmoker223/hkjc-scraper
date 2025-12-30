# HKJC Horse Racing Data Scraper

A Python web scraper that collects horse racing data from the Hong Kong Jockey Club (HKJC) website and stores it in a PostgreSQL database.

## Features

- Scrapes race results, runner performance, and sectional times
- Stores data in normalized PostgreSQL database with 9 tables
- Automatic UPSERT operations to handle duplicate data
- Command-line interface for easy operation
- Tracks historical horse profile changes
- PostgreSQL runs in Docker for easy setup
- Modern Python tooling with `uv` package manager

## Project Structure

```
hkjc/
├── config.py                 # Configuration management
├── database.py              # Database connection and initialization
├── models.py                # SQLAlchemy ORM models
├── persistence.py           # Data persistence layer (UPSERT operations)
├── hkjc_scraper.py          # Web scraping functions
├── main.py                  # Main CLI script
├── pyproject.toml          # Project metadata and dependencies (uv)
├── requirements.txt        # Pinned dependencies (generated)
├── docker-compose.yml      # PostgreSQL + pgAdmin setup
├── Makefile                # Common commands
├── schema.sql              # Raw SQL schema
├── .env.example            # Environment variables template
├── .gitignore              # Git ignore file
├── data_model.md           # Database schema documentation
└── ROADMAP.md              # Development roadmap
```

## Requirements

- Python 3.9+
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer
- Docker and Docker Compose

## Quick Start

### 1. Install uv (if not already installed)

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Or with Homebrew:**
```bash
brew install uv
```

**Or with pip:**
```bash
pip install uv
```

### 2. Clone and Setup

```bash
cd /path/to/hkjc

# Create virtual environment with uv
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -e .

# Or use Makefile
make install
```

### 3. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# .env is already configured for Docker defaults - no changes needed!
```

Default `.env` values work with Docker setup:
```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=hkjc_racing
DB_USER=hkjc_user
DB_PASSWORD=hkjc_password
```

### 4. Start PostgreSQL with Docker

```bash
# Start PostgreSQL container
docker-compose up -d postgres

# Or use Makefile
make db-up

# Check it's running
docker-compose ps
```

### 5. Initialize Database

```bash
# Create tables
python database.py

# Or use Makefile
make init-db
```

### 6. Scrape Data!

```bash
# Scrape races for a specific date
python main.py 2025/12/23

# Or use Makefile
make scrape DATE=2025/12/23
```

## Usage

### Using Makefile (Recommended)

```bash
# Show all available commands
make help

# Database operations
make db-up              # Start PostgreSQL
make db-down            # Stop PostgreSQL
make db-reset           # Reset database (deletes all data)
make db-logs            # View database logs
make db-shell           # Open PostgreSQL shell
make pgadmin            # Start pgAdmin web UI

# Scraping
make scrape DATE=2025/12/23      # Scrape and save to DB
make dry-run DATE=2025/12/23     # Test without saving

# Development
make install            # Install dependencies
make dev                # Install with dev dependencies
make test               # Run tests
make lint               # Run linter
make format             # Format code
make clean              # Clean temporary files
```

### Using Python Directly

```bash
# Scrape races for a specific date
python main.py 2025/12/23

# Initialize database tables
python main.py 2025/12/23 --init-db

# Dry run (test without saving)
python main.py 2025/12/23 --dry-run
```

### Command-Line Options

```
python main.py [-h] [--init-db] [--dry-run] DATE

Arguments:
  DATE          Race date in YYYY/MM/DD format (e.g., 2025/12/23)

Options:
  -h, --help    Show help message
  --init-db     Initialize database tables before scraping
  --dry-run     Scrape data but don't save to database
```

## Database Management

### PostgreSQL (Docker)

```bash
# Start database
docker-compose up -d postgres

# Stop database
docker-compose down

# View logs
docker-compose logs -f postgres

# Access PostgreSQL shell
docker-compose exec postgres psql -U hkjc_user -d hkjc_racing

# Reset database (WARNING: deletes all data)
docker-compose down -v
docker-compose up -d postgres
python database.py
```

### pgAdmin (Web UI)

pgAdmin provides a graphical interface to browse and query the database.

```bash
# Start pgAdmin (optional)
docker-compose --profile tools up -d pgadmin

# Or use Makefile
make pgadmin
```

Then open http://localhost:5050 in your browser:
- **Email:** admin@hkjc.local
- **Password:** admin

**Add Server in pgAdmin:**
1. Right-click "Servers" → "Create" → "Server"
2. Name: `HKJC Racing`
3. Connection tab:
   - Host: `postgres` (Docker network name)
   - Port: `5432`
   - Database: `hkjc_racing`
   - Username: `hkjc_user`
   - Password: `hkjc_password`

## Database Schema

The database consists of 9 tables:

### Core Tables
- **meeting** - Race meetings (date, venue)
- **race** - Individual races (class, distance, track info)
- **horse** - Horse master data
- **jockey** - Jockey master data
- **trainer** - Trainer master data

### Performance Tables
- **runner** - Per-race, per-horse performance
- **horse_sectional** - Sectional time details

### Profile Tables
- **horse_profile** - Current horse profile snapshot
- **horse_profile_history** - Historical profile tracking

See `data_model.md` for detailed schema documentation.

## What Gets Scraped

### From LocalResults.aspx
- Meeting information (date, venue)
- Race details (name, class, distance, track, going, prize)
- Runner performance (finish position, weights, draw, times, odds)
- Horse, jockey, trainer information

### From DisplaySectionalTime.aspx
- Per-section performance for each horse
- Section positions and margins
- Split times for each section

### From Horse.aspx (Not Yet Implemented)
- Horse profiles (origin, age, colour, sex, import type)
- Career statistics (prizes, wins, ratings)
- Owner and pedigree information

## Development

### Install Dev Dependencies

```bash
# With uv
uv pip install -e ".[dev]"

# Or with Makefile
make dev
```

Dev dependencies include:
- `pytest` - Testing framework
- `pytest-cov` - Test coverage
- `mypy` - Type checking
- `ruff` - Fast linter and formatter
- `ipython` - Enhanced Python shell

### Code Quality

```bash
# Format code
make format

# Run linter
make lint

# Run tests (when implemented)
make test

# Type checking
uv run mypy .
```

### Project Structure Best Practices

- Keep scraping logic in `hkjc_scraper.py`
- Database operations in `persistence.py`
- ORM models in `models.py`
- CLI interface in `main.py`
- Configuration in `config.py`

## Troubleshooting

### Docker Issues

**Error: `Cannot connect to the Docker daemon`**
- Make sure Docker Desktop is running
- Check: `docker ps`

**Error: `port is already allocated`**
- Another service is using port 5432
- Change port in `.env`: `DB_PORT=5433`
- Update `docker-compose.yml` ports: `5433:5432`

### Database Connection Errors

**Error: `could not connect to server`**
- Check Docker container is running: `docker-compose ps`
- Check logs: `docker-compose logs postgres`
- Verify credentials in `.env` match `docker-compose.yml`

**Error: `database "hkjc_racing" does not exist`**
- Run: `make db-reset` to recreate database
- Or manually: `python database.py`

### Scraping Errors

**Error: `No races found`**
- Verify the date has races scheduled on HKJC website
- Check date format is correct (YYYY/MM/DD)

**Error: `HTTP 404` or `Timeout`**
- HKJC website structure may have changed
- Check internet connection
- Try again later (site may be down)

### uv Issues

**Error: `uv: command not found`**
- Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Or: `brew install uv` (macOS)

**Dependencies not resolving**
- Clear cache: `uv cache clean`
- Reinstall: `uv pip install -e . --reinstall`

## Development Status

**Phase 1: Core Infrastructure** ✅ COMPLETED
- ✅ Database setup with SQLAlchemy ORM
- ✅ Configuration management
- ✅ Data persistence layer with UPSERT operations
- ✅ Command-line interface
- ✅ Docker setup with PostgreSQL
- ✅ Modern tooling (uv, Makefile, ruff)

**Next Steps (Phase 2):**
- Implement horse profile scraping
- Add data validation
- Error handling and retry logic
- Logging system

See `ROADMAP.md` for the complete development plan.

## Notes

- The scraper respects HKJC's website structure as of December 2024
- Data is stored in Traditional Chinese (as presented on HKJC site)
- UPSERT logic prevents duplicate data on re-scraping
- Only scrapes publicly available data
- Docker volumes persist data between container restarts

## License

This project is for educational and personal use only. Please respect HKJC's terms of service and robots.txt.

## Contributing

See `ROADMAP.md` for planned features and improvements.
