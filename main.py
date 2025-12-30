"""
Main script to scrape HKJC racing data and save to database
主程式：抓取 HKJC 賽事資料並儲存至資料庫
"""
import argparse
import sys
from datetime import datetime

from database import get_db, init_db, check_connection
from persistence import save_meeting_data
from hkjc_scraper import scrape_meeting


def main():
    """主程式進入點"""
    parser = argparse.ArgumentParser(
        description="Scrape HKJC racing data and save to PostgreSQL database"
    )
    parser.add_argument(
        "date",
        help="Race date in YYYY/MM/DD format (e.g., 2025/12/23)",
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Initialize database tables before scraping",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape data but don't save to database (just print summary)",
    )

    args = parser.parse_args()

    # Validate date format
    try:
        datetime.strptime(args.date.replace("/", "-"), "%Y-%m-%d")
    except ValueError:
        print(f"Error: Invalid date format '{args.date}'. Use YYYY/MM/DD")
        sys.exit(1)

    # Check database connection
    print("Checking database connection...")
    if not check_connection():
        print("\nError: Cannot connect to database.")
        print("Please check your .env file and ensure PostgreSQL is running.")
        sys.exit(1)

    # Initialize database if requested
    if args.init_db:
        print("\nInitializing database tables...")
        init_db()

    # Scrape meeting data
    print(f"\n{'='*60}")
    print(f"Scraping races for {args.date}")
    print(f"{'='*60}\n")

    try:
        meeting_data = scrape_meeting(args.date)
    except Exception as e:
        print(f"Error during scraping: {e}")
        sys.exit(1)

    if not meeting_data:
        print(f"No races found for {args.date}")
        sys.exit(0)

    print(f"Successfully scraped {len(meeting_data)} races")

    # Print summary of scraped data
    total_profiles = 0
    for idx, race_data in enumerate(meeting_data, 1):
        race = race_data["race"]
        print(f"  Race {idx}: {race.get('name_cn', 'N/A')} "
              f"({race.get('race_no', '?')}場 - {race.get('class_text', 'N/A')})")
        total_profiles += len(race_data.get('horse_profiles', []))

    # Save to database or dry run
    if args.dry_run:
        print("\n[DRY RUN] Data not saved to database")
        print(f"Would save {len(meeting_data)} races")
        for race_data in meeting_data:
            print(f"  - {len(race_data['runners'])} runners")
            print(f"  - {len(race_data.get('horse_sectionals', []))} sectional records")
        if total_profiles > 0:
            print(f"  - {total_profiles} total horse profiles")
    else:
        print("\nSaving to database...")
        try:
            with get_db() as db:
                summary = save_meeting_data(db, meeting_data)

            print(f"\n{'='*60}")
            print("Save completed successfully!")
            print(f"{'='*60}")
            print(f"  Races saved:      {summary['races_saved']}")
            print(f"  Runners saved:    {summary['runners_saved']}")
            print(f"  Sectionals saved: {summary['sectionals_saved']}")
            print(f"  Profiles saved:   {summary['profiles_saved']}")
            print(f"{'='*60}\n")

        except Exception as e:
            print(f"\nError saving to database: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()
