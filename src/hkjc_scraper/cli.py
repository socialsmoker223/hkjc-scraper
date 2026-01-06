"""
Main script to scrape HKJC racing data and save to database
主程式：抓取 HKJC 賽事資料並儲存至資料庫
"""

import argparse
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import requests
from sqlalchemy.exc import SQLAlchemyError
from tqdm import tqdm

from hkjc_scraper.config import config
from hkjc_scraper.database import check_connection, get_db, init_db
from hkjc_scraper.exceptions import ParseError
from hkjc_scraper.persistence import (
    check_meeting_exists,
    get_max_meeting_date,
    save_meeting_data,
)
from hkjc_scraper.scraper import scrape_meeting

logger = logging.getLogger(__name__)


@dataclass
class ScrapingSummary:
    """Track scraping statistics for summary reporting"""

    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime = None

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

    # Validation statistics
    runners_invalid: int = 0
    profiles_invalid: int = 0

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
            "=" * 60,
            "SCRAPING SUMMARY",
            "=" * 60,
            f"Duration: {self.duration_seconds:.1f}s ({self.duration_seconds/60:.1f} minutes)",
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

        # Add validation stats if any invalid records
        if self.runners_invalid > 0 or self.profiles_invalid > 0:
            lines.extend(
                [
                    "",
                    "Validation Statistics:",
                    f"  Invalid runners:       {self.runners_invalid}",
                    f"  Invalid profiles:      {self.profiles_invalid}",
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

        lines.append("=" * 60)
        return "\n".join(lines)


def main():
    """主程式進入點"""
    # Initialize summary tracking
    summary = ScrapingSummary()

    parser = argparse.ArgumentParser(description="Scrape HKJC racing data and save to PostgreSQL database")

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

    # Determine dates to scrape
    dates_to_scrape = []

    try:
        if args.date:
            # Single date mode
            date_obj = datetime.strptime(args.date.replace("/", "-"), "%Y-%m-%d").date()
            dates_to_scrape.append(date_obj)

        elif args.date_range or args.backfill:
            # Range mode
            range_args = args.date_range or args.backfill
            start_str, end_str = range_args
            start_date = datetime.strptime(start_str.replace("/", "-"), "%Y-%m-%d").date()
            end_date = datetime.strptime(end_str.replace("/", "-"), "%Y-%m-%d").date()

            if start_date > end_date:
                logger.error("Start date must be before end date")
                sys.exit(1)

            curr = start_date
            while curr <= end_date:
                dates_to_scrape.append(curr)
                curr += timedelta(days=1)

        elif args.start and args.end:
            # Legacy range flags support
            start_date = datetime.strptime(args.start.replace("/", "-"), "%Y-%m-%d").date()
            end_date = datetime.strptime(args.end.replace("/", "-"), "%Y-%m-%d").date()

            curr = start_date
            while curr <= end_date:
                dates_to_scrape.append(curr)
                curr += timedelta(days=1)

        elif args.update:
            # Update mode
            with get_db() as db:
                last_date = get_max_meeting_date(db)

            if not last_date:
                logger.error("No existing data found. Cannot use --update. Please use --backfill or provide a date first.")
                sys.exit(1)

            start_date = last_date + timedelta(days=1)
            end_date = datetime.now().date()

            if start_date > end_date:
                logger.info(f"Database is already up to date (Last date: {last_date})")
                sys.exit(0)

            logger.info(f"Updating from {start_date} to {end_date}")
            curr = start_date
            while curr <= end_date:
                dates_to_scrape.append(curr)
                curr += timedelta(days=1)

    except ValueError:
        logger.error("Invalid date format. Use YYYY/MM/DD")
        sys.exit(1)

    if not dates_to_scrape:
        logger.warning("No dates selected to scrape.")
        sys.exit(0)

    logger.info(f"Targeting {len(dates_to_scrape)} days for scraping...")

    # Main scraping loop
    summary.total_dates = len(dates_to_scrape)

    # Use tqdm only if scraping more than 1 day
    iterator = tqdm(dates_to_scrape, desc="Processing") if len(dates_to_scrape) > 1 else dates_to_scrape

    for date_obj in iterator:
        date_ymd = date_obj.strftime("%Y/%m/%d")

        # Display current date if not using tqdm or using it for multiple days
        if len(dates_to_scrape) == 1:
            logger.info(f"\n{'=' * 60}\nScraping races for {date_ymd}\n{'=' * 60}\n")

        # Check if exists
        if not args.force:
            with get_db() as db:
                if check_meeting_exists(db, date_obj):
                    msg = f"Skipping {date_ymd} - Already exists (use --force to override)"
                    logger.info(msg)
                    if len(dates_to_scrape) > 1:
                        tqdm.write(msg)
                    summary.dates_skipped += 1
                    continue

        try:
            meeting_data = scrape_meeting(date_ymd)

            if not meeting_data:
                msg = f"No races found for {date_ymd}"
                if len(dates_to_scrape) == 1:
                    logger.info(msg)
                continue

            # Save to database or dry run
            if args.dry_run:
                msg = f"[DRY RUN] {date_ymd}: Would save {len(meeting_data)} races"
                logger.info(msg)
                if len(dates_to_scrape) > 1:
                    tqdm.write(msg)
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

                # Track validation issues
                for race in meeting_data:
                    val = race.get("validation_summary", {})
                    summary.runners_invalid += val.get("runners_invalid", 0)
                    summary.profiles_invalid += val.get("profiles_invalid", 0)

                # Collect validation stats for message
                total_invalid = sum(
                    race.get("validation_summary", {}).get("runners_invalid", 0)
                    + race.get("validation_summary", {}).get("profiles_invalid", 0)
                    for race in meeting_data
                )

                msg = f"Saved {date_ymd}: {save_result['races_saved']} races, {save_result['runners_saved']} runners"
                if total_invalid > 0:
                    msg += f" (skipped {total_invalid} invalid records)"

                logger.info(msg)
                if len(dates_to_scrape) > 1:
                    tqdm.write(msg)

        except requests.RequestException as e:
            summary.network_errors += 1
            summary.dates_failed += 1
            logger.error(f"Network error scraping {date_ymd}: {e}")
            msg = f"Network error for {date_ymd} (check connection)"
            if len(dates_to_scrape) > 1:
                tqdm.write(msg)
            continue
        except ParseError as e:
            summary.parse_errors += 1
            summary.dates_failed += 1
            logger.error(f"Parse error for {date_ymd}: {e}")
            msg = f"Parse error for {date_ymd} (HKJC site may have changed)"
            if len(dates_to_scrape) > 1:
                tqdm.write(msg)
            continue
        except SQLAlchemyError as e:
            summary.db_errors += 1
            summary.dates_failed += 1
            logger.error(f"Database error for {date_ymd}: {e}")
            msg = f"Database error for {date_ymd} (check DB connection)"
            if len(dates_to_scrape) > 1:
                tqdm.write(msg)
            continue
        except Exception as e:
            summary.other_errors += 1
            summary.dates_failed += 1
            logger.exception(f"Unexpected error for {date_ymd}: {e}")
            msg = f"Unexpected error for {date_ymd}: {str(e)}"
            if len(dates_to_scrape) > 1:
                tqdm.write(msg)
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
