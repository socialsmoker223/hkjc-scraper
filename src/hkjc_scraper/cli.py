"""
Main script to scrape HKJC racing data and save to database
主程式：抓取 HKJC 賽事資料並儲存至資料庫
"""

import argparse
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

import requests
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from tqdm import tqdm

from hkjc_scraper import __version__
from hkjc_scraper.config import config
from hkjc_scraper.database import check_connection, get_db, init_db
from hkjc_scraper.exceptions import ParseError
from hkjc_scraper.hk33_scraper import scrape_hk33_race_all_types
from hkjc_scraper.http_utils import HTTPSession
from hkjc_scraper.persistence import (
    check_meeting_exists,
    get_max_meeting_date,
    get_runner_map,
    save_hk33_data,
    save_meeting_data,
)
from hkjc_scraper.scraper import scrape_meeting

logger = logging.getLogger(__name__)

# Constants
SEPARATOR = "=" * 60


def parse_date(date_str: str) -> date:
    """Parse date string in YYYY/MM/DD or YYYY-MM-DD format."""
    return datetime.strptime(date_str.replace("/", "-"), "%Y-%m-%d").date()


def generate_date_range(start_date: date, end_date: date) -> list[date]:
    """Generate list of dates between start and end (inclusive)."""
    dates = []
    curr = start_date
    while curr <= end_date:
        dates.append(curr)
        curr += timedelta(days=1)
    return dates


def log_and_display(msg: str, use_tqdm: bool) -> None:
    """Log message and optionally display via tqdm.write for progress bar compatibility."""
    logger.info(msg)
    if use_tqdm:
        tqdm.write(msg)


@dataclass
class ScrapingSummary:
    """Track scraping statistics for summary reporting"""

    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None

    # Date tracking
    total_dates: int = 0
    dates_scraped: int = 0
    dates_skipped: int = 0
    dates_failed: int = 0

    # Data statistics
    races_scraped: int = 0
    runners_saved: int = 0
    sectionals_saved: int = 0
    profiles_saved: int = 0

    # HK33 statistics
    hk33_hkjc_saved: int = 0
    hk33_offshore_saved: int = 0
    hk33_errors: int = 0

    # Error tracking
    network_errors: int = 0
    parse_errors: int = 0
    db_errors: int = 0
    other_errors: int = 0

    def mark_complete(self):
        """Mark scraping as complete and calculate duration"""
        self.end_time = datetime.now()

    @property
    def duration_seconds(self) -> float:
        """Calculate total duration in seconds"""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage"""
        if self.total_dates == 0:
            return 0.0
        return (self.dates_scraped / self.total_dates) * 100

    def format_report(self) -> str:
        """Format summary report for display"""
        lines = [
            SEPARATOR,
            "SCRAPING SUMMARY",
            SEPARATOR,
            f"Duration: {self.duration_seconds:.1f}s ({self.duration_seconds / 60:.1f} minutes)",
            "",
            "Date Statistics:",
            f"  Total dates processed: {self.total_dates}",
            f"  Successfully scraped:  {self.dates_scraped}",
            f"  Skipped (existing):    {self.dates_skipped}",
            f"  Failed (errors):       {self.dates_failed}",
            f"  Success rate:          {self.success_rate:.1f}%",
            "",
            "Data Statistics:",
            f"  Races scraped:         {self.races_scraped}",
            f"  Runners saved:         {self.runners_saved}",
            f"  Sectionals saved:      {self.sectionals_saved}",
            f"  Profiles saved:        {self.profiles_saved}",
        ]

        # Add HK33 statistics if any data was scraped
        if self.hk33_hkjc_saved > 0 or self.hk33_offshore_saved > 0 or self.hk33_errors > 0:
            lines.extend(
                [
                    "",
                    "HK33 Statistics:",
                    f"  hkjc odds saved:       {self.hk33_hkjc_saved}",
                    f"  Offshore market saved: {self.hk33_offshore_saved}",
                    f"  HK33 errors:           {self.hk33_errors}",
                ]
            )

        # Add error breakdown if any errors
        total_errors = self.network_errors + self.parse_errors + self.db_errors + self.other_errors
        if total_errors > 0:
            lines.extend(
                [
                    "",
                    "Error Breakdown:",
                    f"  Network errors:        {self.network_errors}",
                    f"  Parse errors:          {self.parse_errors}",
                    f"  Database errors:       {self.db_errors}",
                    f"  Other errors:          {self.other_errors}",
                    f"  Total errors:          {total_errors}",
                ]
            )

        lines.append(SEPARATOR)
        return "\n".join(lines)


def scrape_and_save_hk33_meeting(db, date_obj, meeting_data, session, scrape_odds: bool, scrape_market: bool) -> dict:
    """
    Scrape and save HK33 data for all races in a meeting using parallel execution.

    Args:
        db: Database session (unused, kept for API compatibility)
        date_obj: Date object of the meeting
        meeting_data: List of race data dicts from HKJC scraper
        session: HTTP session for making requests
        scrape_odds: Whether to scrape hkjc odds
        scrape_market: Whether to scrape offshore market

    Returns:
        Dict with counts: {'hkjc_saved': int, 'offshore_saved': int}
    """
    from hkjc_scraper.models import Meeting, Race

    date_ymd = date_obj.strftime("%Y/%m/%d")
    hkjc_total = 0
    offshore_total = 0

    def scrape_single_hk33_race(race_data_dict):
        """Helper function to scrape and save HK33 data for a single race"""
        race_no = race_data_dict["race"]["race_no"]

        try:
            # Get runner mapping from DB
            with get_db() as race_db:
                runner_map = get_runner_map(race_db, date_obj, race_no)
                if not runner_map:
                    logger.warning(f"No runners found for race {race_no} on {date_ymd}, skipping HK33")
                    return {"hkjc_saved": 0, "offshore_saved": 0}

                # Get race_id from DB
                stmt = (
                    select(Race.id)
                    .join(Meeting, Race.meeting_id == Meeting.id)
                    .where(Meeting.date == date_obj, Race.race_no == race_no)
                )
                race_id = race_db.execute(stmt).scalar_one_or_none()

                if not race_id:
                    logger.warning(f"Race {race_no} not found in DB for {date_ymd}, skipping HK33")
                    return {"hkjc_saved": 0, "offshore_saved": 0}

                # Scrape HK33 data (parallelized within each race)
                hk33_data = scrape_hk33_race_all_types(
                    session, date_ymd, race_no, scrape_hkjc=scrape_odds, scrape_market=scrape_market
                )

                # Save to database
                result = save_hk33_data(
                    race_db,
                    race_id,
                    date_obj,
                    runner_map,
                    hk33_data["hkjc_data"],
                    hk33_data["market_data"],
                )

                # Commit within the race's own DB session
                race_db.commit()

                logger.debug(f"HK33 Race {race_no}: {result['hkjc_saved']} hkjc, {result['offshore_saved']} offshore")
                return result

        except Exception as e:
            logger.error(f"Failed to scrape/save HK33 data for race {race_no}: {e}")
            return {"hkjc_saved": 0, "offshore_saved": 0}

    # Scrape all races in parallel
    with ThreadPoolExecutor(max_workers=config.MAX_HK33_RACE_WORKERS) as executor:
        future_to_race = {executor.submit(scrape_single_hk33_race, race_data): race_data for race_data in meeting_data}

        for future in as_completed(future_to_race):
            try:
                result = future.result()
                hkjc_total += result["hkjc_saved"]
                offshore_total += result["offshore_saved"]
            except Exception as e:
                race_data = future_to_race[future]
                race_no = race_data["race"]["race_no"]
                logger.error(f"Unexpected error processing HK33 for race {race_no}: {e}")

    return {"hkjc_saved": hkjc_total, "offshore_saved": offshore_total}


def main():
    """主程式進入點"""
    # Initialize summary tracking
    summary = ScrapingSummary()

    parser = argparse.ArgumentParser(description="Scrape HKJC racing data and save to PostgreSQL database")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    # Mutually exclusive group for date selection modes
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "date",
        nargs="?",
        help="Race date in YYYY/MM/DD format (e.g., 2025/12/23)",
    )
    group.add_argument(
        "--init-db",
        action="store_true",
        help="Initialize database tables (legacy, uses SQLAlchemy create_all)",
    )
    group.add_argument(
        "--migrate",
        action="store_true",
        help="Run database migrations (uses Alembic, recommended)",
    )
    group.add_argument("--date-range", nargs=2, metavar=("START", "END"), help="Scrape a range of dates (YYYY/MM/DD)")
    group.add_argument(
        "--backfill", nargs=2, metavar=("START", "END"), help="Backfill mode: scrape range of dates (YYYY/MM/DD)"
    )
    group.add_argument("--update", action="store_true", help="Update mode: scrape from last DB entry to today")

    # Optional flags
    parser.add_argument("--start", help="Start date for range scraping (deprecated, use --date-range instead)")
    parser.add_argument("--end", help="End date for range scraping")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape data but don't save to database (just print summary)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-scrape even if data exists in database",
    )
    parser.add_argument(
        "--scrape-profiles",
        action="store_true",
        default=True,
        help="Include horse profile scraping (default: enabled)",
    )
    parser.add_argument(
        "--no-profiles",
        action="store_true",
        help="Skip horse profile scraping for faster execution",
    )
    parser.add_argument(
        "--scrape-hk33",
        action="store_true",
        help="Scrape HK33 odds data (both hkjc odds and offshore market)",
    )
    parser.add_argument(
        "--scrape-hk33-odds",
        action="store_true",
        help="Scrape only hkjc Win/Place odds from HK33",
    )
    parser.add_argument(
        "--scrape-hk33-market",
        action="store_true",
        help="Scrape only offshore market data from HK33",
    )
    parser.add_argument(
        "--login-hk33",
        action="store_true",
        help="Run automated login to refresh HK33 cookies",
    )

    args = parser.parse_args()

    # Check database connection
    logger.info("Checking database connection...")
    if not check_connection():
        logger.error("Cannot connect to database. Check .env and ensure PostgreSQL is running.")
        sys.exit(1)

    # Initialize database if requested
    if args.init_db:
        logger.info("Initializing database tables (legacy mode)...")
        init_db()
        sys.exit(0)

    # Run migrations if requested
    if args.migrate:
        logger.info("Running database migrations...")
        from hkjc_scraper.database import migrate_db

        migrate_db(command="upgrade", revision="head")
        sys.exit(0)

    # Run HK33 Login if requested
    if args.login_hk33:
        logger.info("Starting HK33 automated login...")
        from hkjc_scraper.hk33_login import perform_hk33_login

        if perform_hk33_login():
            logger.info("Login process completed successfully.")
            sys.exit(0)
        else:
            logger.error("Login process failed.")
            sys.exit(1)

    # Determine dates to scrape
    dates_to_scrape: list[date] = []

    try:
        if args.date:
            # Single date mode
            dates_to_scrape.append(parse_date(args.date))

        elif args.date_range or args.backfill:
            # Range mode
            range_args = args.date_range or args.backfill
            start_str, end_str = range_args
            start_date = parse_date(start_str)
            end_date = parse_date(end_str)

            if start_date > end_date:
                logger.error("Start date must be before end date")
                sys.exit(1)

            dates_to_scrape = generate_date_range(start_date, end_date)

        elif args.start and args.end:
            # Legacy range flags support
            start_date = parse_date(args.start)
            end_date = parse_date(args.end)
            dates_to_scrape = generate_date_range(start_date, end_date)

        elif args.update:
            # Update mode
            with get_db() as db:
                last_date = get_max_meeting_date(db)

            if not last_date:
                logger.error(
                    "No existing data found. Cannot use --update. Please use --backfill or provide a date first."
                )
                sys.exit(1)

            start_date = last_date + timedelta(days=1)
            end_date = datetime.now().date()

            if start_date > end_date:
                logger.info(f"Database is already up to date (Last date: {last_date})")
                sys.exit(0)

            logger.info(f"Updating from {start_date} to {end_date}")
            dates_to_scrape = generate_date_range(start_date, end_date)

    except ValueError:
        logger.error("Invalid date format. Use YYYY/MM/DD")
        sys.exit(1)

    if not dates_to_scrape:
        logger.warning("No dates selected to scrape.")
        sys.exit(0)

    logger.info(f"Targeting {len(dates_to_scrape)} days for scraping...")

    # Main scraping loop
    summary.total_dates = len(dates_to_scrape)
    use_tqdm = len(dates_to_scrape) > 1

    # Use tqdm only if scraping more than 1 day
    iterator = tqdm(dates_to_scrape, desc="Processing") if use_tqdm else dates_to_scrape

    for date_obj in iterator:
        date_ymd = date_obj.strftime("%Y/%m/%d")

        # Display current date if not using tqdm
        if not use_tqdm:
            logger.info(f"\n{SEPARATOR}\nScraping races for {date_ymd}\n{SEPARATOR}\n")

        # Check if exists
        if not args.force:
            with get_db() as db:
                if check_meeting_exists(db, date_obj):
                    log_and_display(
                        f"Skipping {date_ymd} - Already exists (use --force to override)",
                        use_tqdm,
                    )
                    summary.dates_skipped += 1
                    continue

        try:
            scrape_profiles = args.scrape_profiles and not args.no_profiles
            meeting_data = scrape_meeting(date_ymd, scrape_profiles=scrape_profiles)

            if not meeting_data:
                if not use_tqdm:
                    logger.info(f"No races found for {date_ymd}")
                continue

            # Save to database or dry run
            if args.dry_run:
                log_and_display(
                    f"[DRY RUN] {date_ymd}: Would save {len(meeting_data)} races",
                    use_tqdm,
                )
                summary.dates_scraped += 1
            else:
                with get_db() as db:
                    save_result = save_meeting_data(db, meeting_data)

                # Update summary statistics
                summary.dates_scraped += 1
                summary.races_scraped += save_result.get("races_saved", 0)
                summary.runners_saved += save_result.get("runners_saved", 0)
                summary.sectionals_saved += save_result.get("sectionals_saved", 0)
                summary.profiles_saved += save_result.get("profiles_saved", 0)

                log_and_display(
                    f"Saved {date_ymd}: {save_result['races_saved']} races, {save_result['runners_saved']} runners",
                    use_tqdm,
                )

                # Scrape HK33 data if requested
                if args.scrape_hk33 or args.scrape_hk33_odds or args.scrape_hk33_market:
                    try:
                        scrape_odds = args.scrape_hk33 or args.scrape_hk33_odds
                        scrape_market = args.scrape_hk33 or args.scrape_hk33_market

                        with HTTPSession() as session:
                            hk33_result = scrape_and_save_hk33_meeting(
                                None, date_obj, meeting_data, session, scrape_odds, scrape_market
                            )

                            summary.hk33_hkjc_saved += hk33_result["hkjc_saved"]
                            summary.hk33_offshore_saved += hk33_result["offshore_saved"]

                            log_and_display(
                                f"HK33 {date_ymd}: {hk33_result['hkjc_saved']} hkjc odds, {hk33_result['offshore_saved']} offshore records",
                                use_tqdm,
                            )

                    except Exception as e:
                        summary.hk33_errors += 1
                        logger.error(f"Failed to scrape HK33 data for {date_ymd}: {e}")
                        if use_tqdm:
                            tqdm.write(f"HK33 error for {date_ymd}")

        except requests.RequestException as e:
            summary.network_errors += 1
            summary.dates_failed += 1
            logger.error(f"Network error scraping {date_ymd}: {e}")
            if use_tqdm:
                tqdm.write(f"Network error for {date_ymd} (check connection)")
            continue
        except ParseError as e:
            summary.parse_errors += 1
            summary.dates_failed += 1
            logger.error(f"Parse error for {date_ymd}: {e}")
            if use_tqdm:
                tqdm.write(f"Parse error for {date_ymd} (HKJC site may have changed)")
            continue
        except SQLAlchemyError as e:
            summary.db_errors += 1
            summary.dates_failed += 1
            logger.error(f"Database error for {date_ymd}: {e}")
            if use_tqdm:
                tqdm.write(f"Database error for {date_ymd} (check DB connection)")
            continue
        except Exception as e:
            summary.other_errors += 1
            summary.dates_failed += 1
            logger.exception(f"Unexpected error for {date_ymd}: {e}")
            if use_tqdm:
                tqdm.write(f"Unexpected error for {date_ymd}: {e!s}")
            continue

    # Final summary
    summary.mark_complete()

    # Log completion
    logger.info(f"Scraping completed: {summary.dates_scraped}/{summary.total_dates} successful")
    logger.info(f"Total duration: {summary.duration_seconds:.1f}s")

    # Display user-friendly report
    print("\n" + summary.format_report())

    if summary.dates_failed > 0:
        print(f"\nCheck {config.LOG_FILE} for detailed error logs")


if __name__ == "__main__":
    main()
