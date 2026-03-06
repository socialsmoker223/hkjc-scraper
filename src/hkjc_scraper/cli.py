"""Command-line interface for HKJC spider."""
import argparse
import asyncio
import json
from pathlib import Path
import sys

from hkjc_scraper.spider import HKJCRacingSpider


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


async def crawl_race(
    date: str | None = None,
    racecourse: str = "ST",
    output_dir: str = "data",
    rate_limit: float | None = None,
    rate_jitter: float = 0.0,
) -> dict:
    """Crawl race data from HKJC website.

    Args:
        date: Race date in YYYY/MM/DD format, or None for latest
        racecourse: Race course code (ST for Sha Tin, HV for Happy Valley)
        output_dir: Directory to save output JSON files
        rate_limit: Maximum requests per second (None for no limit)
        rate_jitter: Random jitter factor for request intervals (0.0-1.0)

    Returns:
        Dictionary with table names as keys and lists of scraped data
    """
    spider = HKJCRacingSpider(
        dates=[date] if date else None,
        racecourse=racecourse,
        rate_limit=rate_limit,
        rate_jitter=rate_jitter,
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
        "--racecourse",
        choices=["ST", "HV"],
        default="ST",
        help="Racecourse (ST=Sha Tin, HV=Happy Valley)",
    )
    parser.add_argument("--output", default="data", help="Output directory")

    # Rate limiting options
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=None,
        help="Maximum requests per second (e.g., 2.0 for 2 requests/second). "
             "Default: no limit (use with caution to avoid IP bans).",
    )
    parser.add_argument(
        "--rate-jitter",
        type=float,
        default=0.2,
        help="Random jitter factor for request intervals (0.0-1.0). "
             "Adds randomness to request timing to appear more human-like. "
             "Default: 0.2 (20%% variance).",
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
        spider = HKJCRacingSpider(
            rate_limit=args.rate_limit,
            rate_jitter=args.rate_jitter,
        )
        dates = await spider.discover_dates(
            start_date=start_date,
            end_date=end_date,
            refresh_cache=args.refresh_cache,
        )
        print(f"\nDiscovered {len(dates)} race dates:")
        for entry in sorted(dates, key=lambda d: (d["date"], d["racecourse"])):
            print(f"  {entry['date']} @ {entry['racecourse']} ({entry['race_count']} races)")
        return

    # Handle --start-date mode: discover dates first, then scrape discovered dates
    if start_date:
        spider = HKJCRacingSpider(
            rate_limit=args.rate_limit,
            rate_jitter=args.rate_jitter,
        )
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
            rate_limit=args.rate_limit,
            rate_jitter=args.rate_jitter,
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
        return

    # Default behavior: scrape single date
    await crawl_race(args.date, args.racecourse, args.output, args.rate_limit, args.rate_jitter)


def main() -> None:
    """Main entry point for the CLI (synchronous wrapper for async_main)."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
