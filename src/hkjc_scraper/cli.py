"""
Main script to scrape HKJC racing data and save to database
主程式：抓取 HKJC 賽事資料並儲存至資料庫
"""

import argparse
import logging
import sys
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


def main():
    """主程式進入點"""
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
    print("Checking database connection...")
    if not check_connection():
        print("\nError: Cannot connect to database.")
        print("Please check your .env file and ensure PostgreSQL is running.")
        sys.exit(1)

    # Initialize database if requested
    if args.init_db:
        print("\nInitializing database tables (legacy mode)...")
        init_db()
        sys.exit(0)

    # Run migrations if requested
    if args.migrate:
        print("\nRunning database migrations...")
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
                print("Error: Start date must be before end date")
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
                print("No existing data found. Cannot use --update. Please use --backfill or provide a date first.")
                sys.exit(1)

            start_date = last_date + timedelta(days=1)
            end_date = datetime.now().date()

            if start_date > end_date:
                print(f"Database is already up to date (Last date: {last_date})")
                sys.exit(0)

            print(f"Updating from {start_date} to {end_date}")
            curr = start_date
            while curr <= end_date:
                dates_to_scrape.append(curr)
                curr += timedelta(days=1)

    except ValueError:
        print("Error: Invalid date format. Use YYYY/MM/DD")
        sys.exit(1)

    if not dates_to_scrape:
        print("No dates selected to scrape.")
        sys.exit(0)

    print(f"\nTargeting {len(dates_to_scrape)} days for scraping...")

    # Main scraping loop
    success_count = 0
    skip_count = 0
    error_count = 0

    # Use tqdm only if scraping more than 1 day
    iterator = tqdm(dates_to_scrape, desc="Processing") if len(dates_to_scrape) > 1 else dates_to_scrape

    for date_obj in iterator:
        date_ymd = date_obj.strftime("%Y/%m/%d")

        # Display current date if not using tqdm or using it for multiple days
        if len(dates_to_scrape) == 1:
            print(f"\n{'=' * 60}")
            print(f"Scraping races for {date_ymd}")
            print(f"{'=' * 60}\n")

        # Check if exists
        if not args.force:
            with get_db() as db:
                if check_meeting_exists(db, date_obj):
                    msg = f"Skipping {date_ymd} - Already exists (use --force to override)"
                    if len(dates_to_scrape) > 1:
                        tqdm.write(msg)
                    else:
                        print(msg)
                    skip_count += 1
                    continue

        try:
            meeting_data = scrape_meeting(date_ymd)

            if not meeting_data:
                msg = f"No races found for {date_ymd}"
                if len(dates_to_scrape) > 1:
                    pass  # Quietly skip empty days in bulk mode
                else:
                    print(msg)
                continue

            # Save to database or dry run
            if args.dry_run:
                msg = f"[DRY RUN] {date_ymd}: Would save {len(meeting_data)} races"
                if len(dates_to_scrape) > 1:
                    tqdm.write(msg)
                else:
                    print(msg)
                success_count += 1
            else:
                with get_db() as db:
                    summary = save_meeting_data(db, meeting_data)

                # Collect validation stats
                total_invalid = sum(
                    race.get("validation_summary", {}).get("runners_invalid", 0)
                    + race.get("validation_summary", {}).get("profiles_invalid", 0)
                    for race in meeting_data
                )

                msg = f"Saved {date_ymd}: {summary['races_saved']} races, {summary['runners_saved']} runners"
                if total_invalid > 0:
                    msg += f" (skipped {total_invalid} invalid records)"

                if len(dates_to_scrape) > 1:
                    tqdm.write(msg)
                else:
                    print(msg)
                success_count += 1

        except requests.RequestException as e:
            error_count += 1
            logger.error(f"Network error scraping {date_ymd}: {e}")
            msg = f"Network error for {date_ymd} (check connection)"
            if len(dates_to_scrape) > 1:
                tqdm.write(msg)
            else:
                print(msg)
            continue
        except ParseError as e:
            error_count += 1
            logger.error(f"Parse error for {date_ymd}: {e}")
            msg = f"Parse error for {date_ymd} (HKJC site may have changed)"
            if len(dates_to_scrape) > 1:
                tqdm.write(msg)
            else:
                print(msg)
            continue
        except SQLAlchemyError as e:
            error_count += 1
            logger.error(f"Database error for {date_ymd}: {e}")
            msg = f"Database error for {date_ymd} (check DB connection)"
            if len(dates_to_scrape) > 1:
                tqdm.write(msg)
            else:
                print(msg)
            continue
        except Exception as e:
            error_count += 1
            logger.exception(f"Unexpected error for {date_ymd}: {e}")
            msg = f"Unexpected error for {date_ymd}: {str(e)}"
            if len(dates_to_scrape) > 1:
                tqdm.write(msg)
            else:
                print(msg)
            continue

    # Final summary
    print(f"\n{'=' * 60}")
    print("Batch Scraping Completed")
    print(f"{'=' * 60}")
    print(f"Total days processed: {len(dates_to_scrape)}")
    print(f"Successfully scraped: {success_count}")
    print(f"Skipped (existing):   {skip_count}")
    print(f"Errors:               {error_count}")
    if error_count > 0:
        print(f"\nCheck {config.LOG_FILE} for error details")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
