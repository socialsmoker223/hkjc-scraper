"""Command-line interface for HKJC spider."""
import argparse
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
import sys

from hkjc_scraper.spider import HKJCRacingSpider
from hkjc_scraper.database import (
    create_database,
    export_json_to_db,
    get_db_connection,
    import_dividends,
    import_horses,
    import_incidents,
    import_jockeys,
    import_performance,
    import_races,
    import_sectional_times,
    import_trainers,
    update_performance_gear,
)


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


def _setup_db(database_url: str | None = None) -> None:
    """Ensure database schema exists."""
    url = database_url or os.environ.get("DATABASE_URL")
    create_database(url)


def _flush_to_db(
    grouped: dict,
    database_url: str | None = None,
    accumulator: dict[str, int] | None = None,
) -> None:
    """Flush in-memory grouped data to PostgreSQL and update counts.

    Args:
        grouped: Dict of {table_name: [records]} to import.
        database_url: PostgreSQL connection string.
        accumulator: Optional dict to accumulate per-table counts across calls.
    """
    url = database_url or os.environ.get("DATABASE_URL")
    conn = get_db_connection(url)
    try:
        for table_name in _TABLE_ORDER:
            records = grouped.get(table_name, [])
            if not records:
                continue
            importer = _TABLE_IMPORTERS[table_name]
            inserted = importer(records, conn)
            conn.commit()
            if accumulator is not None:
                accumulator[table_name] = accumulator.get(table_name, 0) + inserted
    finally:
        conn.close()


_TABLE_IMPORTERS = {
    "races": import_races,
    "horses": import_horses,
    "jockeys": import_jockeys,
    "trainers": import_trainers,
    "performance": import_performance,
    "dividends": import_dividends,
    "incidents": import_incidents,
    "sectional_times": import_sectional_times,
    "performance_gear": update_performance_gear,
}

# Parent tables first to satisfy foreign keys.
# performance_gear runs last — it updates existing performance rows.
_TABLE_ORDER = [
    "races", "horses", "jockeys", "trainers",
    "performance", "dividends", "incidents", "sectional_times",
    "performance_gear",
]


def export_to_db(
    output_dir: str,
    database_url: str | None = None,
    grouped: dict | None = None,
) -> None:
    """Export data to PostgreSQL database.

    When ``grouped`` is provided, imports directly from in-memory data.
    Otherwise falls back to reading JSON files from ``output_dir``.

    Args:
        output_dir: Directory containing JSON data files (fallback).
        database_url: PostgreSQL connection string. If None, reads DATABASE_URL env var.
        grouped: Optional dict of {table_name: [records]} for direct import.
    """
    print("\nExporting to PostgreSQL database...")
    try:
        if grouped:
            _setup_db(database_url)
            counts: dict[str, int] = {}
            _flush_to_db(grouped, database_url, counts)
        else:
            url = database_url or os.environ.get("DATABASE_URL")
            counts = export_json_to_db(output_dir, url)

        print("\nDatabase export summary:")
        for table, count in counts.items():
            print(f"  {table}: {count} records")
    except Exception as e:
        print(f"Error exporting to database: {e}")


async def crawl_race(
    date: str | None = None,
    racecourse: str = "ST",
    output_dir: str = "data",
    export_db: bool = False,
    database_url: str | None = None,
) -> dict:
    """Crawl race data from HKJC website.

    Args:
        date: Race date in YYYY/MM/DD format, or None for latest
        racecourse: Race course code (ST for Sha Tin, HV for Happy Valley)
        output_dir: Directory to save output JSON files
        export_db: If True, export data to PostgreSQL after scraping
        database_url: PostgreSQL connection string

    Returns:
        Dictionary with table names as keys and lists of scraped data
    """
    spider = HKJCRacingSpider(
        dates=[date] if date else None,
        racecourse=racecourse,
    )
    result = await spider.run()
    grouped = group_items_by_table(result.items)

    if not export_db:
        # Save each table's data to a separate JSON file
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
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

    # Export to database directly from memory
    if export_db:
        export_to_db(output_dir, database_url, grouped=grouped)

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
        "--export-db",
        action="store_true",
        help="Export scraped JSON data to PostgreSQL database",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="PostgreSQL connection URL. Also reads DATABASE_URL env var.",
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

        if args.export_db:
            export_to_db(args.output, args.database_url)
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

        if not args.export_db:
            # Save each table's data to a separate JSON file
            out_path = Path(args.output)
            out_path.mkdir(parents=True, exist_ok=True)
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

        if args.export_db:
            export_to_db(args.output, args.database_url, grouped=grouped)
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
        date_strings = [entry["date"] for entry in dates]
        print(f"Discovered {len(dates)} race dates. Scraping...")

        if args.export_db:
            # Stream to DB: scrape one date at a time to keep memory bounded
            _setup_db(args.database_url)
            total_counts: dict[str, int] = {}
            for i, d in enumerate(date_strings, 1):
                print(f"\n[{i}/{len(date_strings)}] Scraping {d}...")
                per_date_spider = HKJCRacingSpider(
                    dates=[d], racecourse=args.racecourse,
                )
                result = await per_date_spider.run()
                grouped = group_items_by_table(result.items)
                _flush_to_db(grouped, args.database_url, total_counts)

            print("\nDatabase export summary:")
            for table, count in total_counts.items():
                print(f"  {table}: {count} records")
        else:
            # Batch mode: scrape all dates, save to JSON
            spider = HKJCRacingSpider(
                dates=date_strings, racecourse=args.racecourse,
            )
            result = await spider.run()
            grouped = group_items_by_table(result.items)

            out_path = Path(args.output)
            out_path.mkdir(parents=True, exist_ok=True)
            for table_name, data in grouped.items():
                if data:
                    file_path = out_path / f"{table_name}_batch.json"
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    print(f"Saved {len(data)} {table_name} records to {file_path}")

            print(f"\nSummary:")
            for table_name, data in grouped.items():
                print(f"  {table_name}: {len(data)} records")
            print(f"  Total requests: {result.stats.requests_count}")
        return

    # Default behavior: scrape single date
    await crawl_race(
        args.date,
        args.racecourse,
        args.output,
        args.export_db,
        args.database_url,
    )


def main() -> None:
    """Main entry point for the CLI (synchronous wrapper for async_main)."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
