"""Command-line interface for HKJC spider."""
import argparse
import asyncio
import json
from pathlib import Path

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


async def crawl_race(date: str | None = None, racecourse: str = "ST", output_dir: str = "data") -> dict:
    """Crawl race data from HKJC website.

    Args:
        date: Race date in YYYY/MM/DD format, or None for latest
        racecourse: Race course code (ST for Sha Tin, HV for Happy Valley)
        output_dir: Directory to save output JSON files

    Returns:
        Dictionary with table names as keys and lists of scraped data
    """
    spider = HKJCRacingSpider(dates=[date] if date else None, racecourse=racecourse)
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


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description="HKJC Racing Scraper")
    parser.add_argument("--date", help="Race date (YYYY/MM/DD format)")
    parser.add_argument(
        "--racecourse",
        choices=["ST", "HV"],
        default="ST",
        help="Racecourse (ST=Sha Tin, HV=Happy Valley)",
    )
    parser.add_argument("--output", default="data", help="Output directory")
    args = parser.parse_args()

    asyncio.run(crawl_race(args.date, args.racecourse, args.output))


if __name__ == "__main__":
    main()
