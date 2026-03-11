"""Command-line interface for HKJC spider."""
import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
import sys

from hkjc_scraper.spider import HKJCRacingSpider
from hkjc_scraper.database import export_json_to_db


def save_json(data: list, file_path: Path) -> None:
    """Save data to JSON file with UTF-8 encoding.

    Args:
        data: List of dictionaries to save
        file_path: Path to output JSON file
    """
    if not data:
        # Create empty file for empty data
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2, ensure_ascii=False)
        return

    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def group_items_by_table(items: list) -> dict:
    """Group scraped items by table name.

    Args:
        items: List of dictionaries with 'table' and 'data' keys

    Returns:
        Dictionary with table names as keys and lists of data as values
    """
    grouped = {}
    for item in items:
        table = item.get("table", "unknown")
        if table not in grouped:
            grouped[table] = []
        grouped[table].append(item.get("data", {}))
    return grouped


def export_to_db_if_needed(
    output_dir: str,
    db_path: str,
) -> None:
    """Export JSON data to SQLite database if requested.

    Args:
        output_dir: Directory containing JSON data files.
        db_path: Path to the SQLite database file.
    """
    print(f"\nExporting to SQLite database: {db_path}")
    try:
        counts = export_json_to_db(output_dir, db_path)
        print("\nDatabase export summary:")
        for table, count in counts.items():
            print(f"  {table}: {count} records")
    except Exception as e:
        print(f"Error exporting to database: {e}")


async def crawl_race(
    date: str | None = None,
    racecourse: str = "ST",
    output_dir: str = "data",
    export_sqlite: bool = False,
    db_path: str = "data/hkjc_racing.db",
) -> dict:
    """Crawl race data from HKJC website.

    Args:
        date: Race date in YYYY/MM/DD format, or None for latest
        racecourse: Race course code (ST for Sha Tin, HV for Happy Valley)
        output_dir: Directory to save output JSON files
        export_sqlite: If True, export data to SQLite database after scraping
        db_path: Path to SQLite database file

    Returns:
        Dictionary with table names as keys and lists of scraped data
    """
    spider = HKJCRacingSpider(
        dates=[date] if date else None,
        racecourse=racecourse,
    )
    result = await spider.run()
    grouped = group_items_by_table(result.items)

    # Create output directory
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Save each table's data to a separate JSON file
    date_str = date.replace("/", "-") if date else "latest"
    for table_name, data in grouped.items():
        if data:
            file_path = out_path / f"{table_name}_{date_str}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Saved {len(data)} {table_name} records to {file_path}")

    # Print summary
    print(f"\nSummary:")
    for table_name, data in grouped.items():
        print(f"  {table_name}: {len(data)} records")
    print(f"  Total requests: {result.stats.requests_count}")

    # Export to database if requested
    if export_sqlite:
        export_to_db_if_needed(output_dir, db_path)

    return grouped


async def async_main() -> None:
    """Async main entry point for the CLI."""
    parser = argparse.ArgumentParser(description="HKJC Racing Scraper")

    # Historical race discovery options
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Discover historical race dates (don't scrape data)"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date for discovery/scraping (YYYY/MM/DD format)"
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date for discovery/scraping (YYYY/MM/DD format)"
    )
    parser.add_argument(
        "--auto-all",
        action="store_true",
        help="Discover all historical races from 2000-01-01 to 2024-09-01"
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Re-verify cached dates during discovery"
    )

    # Existing options
    parser.add_argument("--date", help="Race date (YYYY/MM/DD format)")
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Scrape today's races (auto-discovers dates, defaults to both ST and HV)",
    )
    parser.add_argument(
        "--racecourse",
        choices=["ST", "HV"],
        default="ST",
        help="Racecourse (ST=Sha Tin, HV=Happy Valley)",
    )
    parser.add_argument("--output", default="data", help="Output directory")

    # Database export options
    parser.add_argument(
        "--export-sqlite",
        action="store_true",
        help="Export scraped JSON data to SQLite database",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="data/hkjc_racing.db",
        help="Path to SQLite database file (default: data/hkjc_racing.db)",
    )

    args = parser.parse_args()

    # Handle --auto-all mode
    start_date = args.start_date
    end_date = args.end_date
    if args.auto_all:
        print("WARNING: --auto-all will discover races from 2000/01/01 to 2024/09/01")
        print("This may take a long time and use significant network resources.")
        response = input("Continue? (y/N): ")
        if response.lower() != "y":
            print("Aborted.")
            sys.exit(0)
        start_date = "2000/01/01"
        end_date = "2024/09/01"

    # Handle --discover mode
    if args.discover:
        spider = HKJCRacingSpider()
        dates = await spider.discover_dates(
            start_date=start_date,
            end_date=end_date,
            refresh_cache=args.refresh_cache,
        )
        print(f"\nDiscovered {len(dates)} race dates:")
        for entry in sorted(dates, key=lambda d: (d["date"], d["racecourse"])):
            print(f"  {entry['date']} @ {entry['racecourse']} ({entry['race_count']} races)")

        # Export to database if requested (for any existing data)
        if args.export_sqlite:
            export_to_db_if_needed(args.output, args.db_path)
        return

    # Handle --latest mode: discover and scrape today's races
    if args.latest:
        today = datetime.now().strftime("%Y/%m/%d")
        spider = HKJCRacingSpider()
        print(f"Discovering races for {today}...")
        dates = await spider.discover_dates(
            start_date=today,
            end_date=today,
            refresh_cache=args.refresh_cache,
        )

        if not dates:
            print(f"No races found for {today}")
            return

        # Group by racecourse and display summary
        by_racecourse = {"ST": 0, "HV": 0}
        for entry in dates:
            by_racecourse[entry["racecourse"]] = entry["race_count"]

        total_races = sum(by_racecourse.values())
        print(f"Found {total_races} races:")
        if by_racecourse["ST"]:
            print(f"  Sha Tin (ST): {by_racecourse['ST']} races")
        if by_racecourse["HV"]:
            print(f"  Happy Valley (HV): {by_racecourse['HV']} races")
        print("Scraping...")

        # Scrape all discovered dates (respects --racecourse if specified)
        date_strings = [entry["date"] for entry in dates]
        spider = HKJCRacingSpider(dates=date_strings, racecourse=args.racecourse)
        result = await spider.run()
        grouped = group_items_by_table(result.items)

        # Create output directory
        out_path = Path(args.output)
        out_path.mkdir(parents=True, exist_ok=True)

        # Save each table's data to a separate JSON file
        for table_name, data in grouped.items():
            if data:
                file_path = out_path / f"{table_name}_{today.replace('/', '-')}.json"
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"Saved {len(data)} {table_name} records to {file_path}")

        # Print summary
        print(f"\nSummary:")
        for table_name, data in grouped.items():
            print(f"  {table_name}: {len(data)} records")
        print(f"  Total requests: {result.stats.requests_count}")

        # Export to database if requested
        if args.export_sqlite:
            export_to_db_if_needed(args.output, args.db_path)
        return

    # Handle --start-date mode: discover dates first, then scrape discovered dates
    if start_date:
        spider = HKJCRacingSpider()
        print(f"Discovering race dates from {start_date}" + (f" to {end_date}" if end_date else "..."))
        dates = await spider.discover_dates(
            start_date=start_date,
            end_date=end_date,
            refresh_cache=args.refresh_cache,
        )
        print(f"Discovered {len(dates)} race dates. Scraping...")
        # Extract just the date strings for scraping
        date_strings = [entry["date"] for entry in dates]
        spider = HKJCRacingSpider(
            dates=date_strings,
            racecourse=args.racecourse,
        )
        result = await spider.run()
        grouped = group_items_by_table(result.items)

        # Create output directory
        out_path = Path(args.output)
        out_path.mkdir(parents=True, exist_ok=True)

        # Save each table's data to a separate JSON file
        for table_name, data in grouped.items():
            if data:
                file_path = out_path / f"{table_name}_batch.json"
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"Saved {len(data)} {table_name} records to {file_path}")

        # Print summary
        print(f"\nSummary:")
        for table_name, data in grouped.items():
            print(f"  {table_name}: {len(data)} records")
        print(f"  Total requests: {result.stats.requests_count}")

        # Export to database if requested
        if args.export_sqlite:
            export_to_db_if_needed(args.output, args.db_path)
        return

    # Default behavior: scrape single date
    await crawl_race(
        args.date,
        args.racecourse,
        args.output,
        args.export_sqlite,
        args.db_path,
    )


def main() -> None:
    """Main entry point for the CLI (synchronous wrapper for async_main)."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
