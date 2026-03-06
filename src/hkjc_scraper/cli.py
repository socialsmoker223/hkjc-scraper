"""Command-line interface for HKJC spider."""
import argparse
import asyncio
import csv
import json
from datetime import datetime
from pathlib import Path
import sys

from hkjc_scraper.spider import HKJCRacingSpider
from hkjc_scraper.database import export_json_to_db, load_from_db
from hkjc_scraper import (
    calculate_jockey_performance,
    calculate_trainer_performance,
    calculate_draw_bias,
    calculate_track_bias,
    calculate_class_performance,
    calculate_horse_form,
    calculate_jockey_trainer_combination,
    calculate_distance_preference,
    calculate_speed_ratings,
    generate_racing_summary,
)


def flatten_dict(data: dict, parent_key: str = "") -> dict:
    """Flatten nested dictionary, serializing complex values as JSON strings.

    Args:
        data: Dictionary to flatten
        parent_key: Optional prefix for nested keys

    Returns:
        Flattened dictionary with complex values serialized as JSON

    Examples:
        >>> flatten_dict({"name": "Test", "rating": {"high": 80, "low": 40}})
        {"name": "Test", "rating": '{"high": 80, "low": 40}'}
    """
    flattened = {}
    for key, value in data.items():
        new_key = f"{parent_key}.{key}" if parent_key else key
        if isinstance(value, dict):
            flattened[new_key] = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, list):
            flattened[new_key] = json.dumps(value, ensure_ascii=False)
        else:
            flattened[new_key] = value
    return flattened


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


def save_csv(data: list, file_path: Path) -> None:
    """Save data to CSV file with UTF-8 encoding.

    Nested structures (dicts, lists) are serialized as JSON strings.
    All keys across all records are included as columns.

    Args:
        data: List of dictionaries to save
        file_path: Path to output CSV file
    """
    if not data:
        return  # Don't create file for empty data

    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Collect all unique keys from all records
    all_keys = set()
    for record in data:
        all_keys.update(record.keys())

    # Flatten nested structures and get all flattened keys
    flattened_data = []
    all_flat_keys = set()
    for record in data:
        flat = flatten_dict(record)
        flattened_data.append(flat)
        all_flat_keys.update(flat.keys())

    fieldnames = sorted(all_flat_keys)

    with open(file_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(flattened_data)


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
    rate_limit: float | None = None,
    rate_jitter: float = 0.0,
    export_sqlite: bool = False,
    db_path: str = "data/hkjc_racing.db",
) -> dict:
    """Crawl race data from HKJC website.

    Args:
        date: Race date in YYYY/MM/DD format, or None for latest
        racecourse: Race course code (ST for Sha Tin, HV for Happy Valley)
        output_dir: Directory to save output JSON files
        rate_limit: Maximum requests per second (None for no limit)
        rate_jitter: Random jitter factor for request intervals (0.0-1.0)
        export_sqlite: If True, export data to SQLite database after scraping
        db_path: Path to SQLite database file

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

    # Export to database if requested
    if export_sqlite:
        export_to_db_if_needed(output_dir, db_path)

    return grouped


def run_analytics(
    data_dir: str | Path = "data",
    db_path: str | Path | None = None,
    output_format: str = "text",
) -> None:
    """Run analytics on racing data.

    Args:
        data_dir: Directory containing JSON data files (used if db_path is None).
        db_path: Path to SQLite database (if provided, reads from database).
        output_format: Output format ('text' or 'json').
    """
    if db_path:
        print(f"Loading data from database: {db_path}")
        performances = load_from_db(db_path, "performance")
        races = load_from_db(db_path, "races")
        horses = load_from_db(db_path, "horses")
        print(f"Loaded {len(performances)} performance records")
        print(f"Loaded {len(races)} race records")
        print(f"Loaded {len(horses)} horse records")
    else:
        data_path = Path(data_dir)
        print(f"Loading data from directory: {data_path}")

        performances = []
        races = []
        horses = []

        for json_file in data_path.glob("performance_*.json"):
            with open(json_file, encoding="utf-8") as f:
                performances.extend(json.load(f))

        for json_file in data_path.glob("races_*.json"):
            with open(json_file, encoding="utf-8") as f:
                races.extend(json.load(f))

        for json_file in data_path.glob("horses_*.json"):
            with open(json_file, encoding="utf-8") as f:
                horses.extend(json.load(f))

        print(f"Loaded {len(performances)} performance records")
        print(f"Loaded {len(races)} race records")
        print(f"Loaded {len(horses)} horse records")

    if not performances:
        print("No data available for analysis.")
        return

    results = {}

    # Jockey performance
    print("\nCalculating jockey performance...")
    jockey_stats = calculate_jockey_performance(performances)
    results["jockey_performance"] = jockey_stats

    # Trainer performance
    print("Calculating trainer performance...")
    trainer_stats = calculate_trainer_performance(performances)
    results["trainer_performance"] = trainer_stats

    # Draw bias
    print("Calculating draw bias...")
    draw_bias = calculate_draw_bias(performances, races if races else None)
    results["draw_bias"] = draw_bias

    # Track bias (requires races data)
    if races:
        print("Calculating track bias...")
        track_bias = calculate_track_bias(performances, races)
        results["track_bias"] = track_bias

    # Class performance
    print("Calculating class performance...")
    class_perf = calculate_class_performance(performances, races if races else None)
    results["class_performance"] = class_perf

    # Horse form (top horses only)
    if horses:
        print("Calculating horse form...")
        horse_form = calculate_horse_form(performances, horses, recent_races=5)
        # Limit to top 20 horses by wins
        top_horses = dict(sorted(
            horse_form.items(),
            key=lambda x: x[1].get("wins", 0),
            reverse=True,
        )[:20])
        results["horse_form"] = top_horses

    # Jockey-Trainer combinations
    print("Calculating jockey-trainer combinations...")
    jt_combos = calculate_jockey_trainer_combination(performances)
    results["jockey_trainer_combinations"] = jt_combos

    # Distance preference
    print("Calculating distance preferences...")
    dist_pref = calculate_distance_preference(performances, races if races else None)
    results["distance_preference"] = dist_pref

    # Speed ratings
    print("Calculating speed ratings...")
    speed_ratings = calculate_speed_ratings(performances, races if races else None)
    # Limit to top 20
    top_speeds = dict(sorted(
        speed_ratings.items(),
        key=lambda x: x[1].get("avg_speed_rating", 0),
        reverse=True,
    )[:20])
    results["speed_ratings"] = top_speeds

    # Generate summary
    print("Generating racing summary...")
    summary = generate_racing_summary(performances, races if races else None)
    results["summary"] = summary

    # Output results
    if output_format == "json":
        print("\n" + json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print("\n" + "=" * 60)
        print("RACING ANALYSIS SUMMARY")
        print("=" * 60)

        # Summary stats
        print(f"\nTotal Races Analyzed: {summary.get('total_races', 0)}")
        print(f"Total Performances: {summary.get('total_performances', 0)}")
        print(f"Date Range: {summary.get('date_range', {}).get('earliest', 'N/A')} to "
              f"{summary.get('date_range', {}).get('latest', 'N/A')}")

        # Top jockeys
        print("\n--- Top Jockeys by Win Rate (min 5 rides) ---")
        jockeys_by_rate = sorted(
            [(j, d) for j, d in jockey_stats.items() if d.get("total_rides", 0) >= 5],
            key=lambda x: x[1].get("win_rate", 0),
            reverse=True,
        )[:5]
        for jockey_id, stats in jockeys_by_rate:
            print(f"  {stats.get('name', jockey_id)}: "
                  f"{stats.get('wins', 0)} wins from {stats.get('total_rides', 0)} rides "
                  f"({stats.get('win_rate', 0):.1%})")

        # Top trainers
        print("\n--- Top Trainers by Win Rate (min 5 runners) ---")
        trainers_by_rate = sorted(
            [(t, d) for t, d in trainer_stats.items() if d.get("total_runners", 0) >= 5],
            key=lambda x: x[1].get("win_rate", 0),
            reverse=True,
        )[:5]
        for trainer_id, stats in trainers_by_rate:
            print(f"  {stats.get('name', trainer_id)}: "
                  f"{stats.get('wins', 0)} wins from {stats.get('total_runners', 0)} runners "
                  f"({stats.get('win_rate', 0):.1%})")

        # Draw bias summary
        if draw_bias.get("summary"):
            print("\n--- Draw Bias Summary ---")
            summary_data = draw_bias["summary"]
            print(f"  Best Draw Overall: {summary_data.get('best_draw_overall', 'N/A')}")
            print(f"  Worst Draw Overall: {summary_data.get('worst_draw_overall', 'N/A')}")
            print(f"  Low Draw Advantage: {summary_data.get('low_draw_advantage', False)}")

        # Class performance
        print("\n--- Performance by Class ---")
        for class_name, stats in list(class_perf.items())[:5]:
            print(f"  {class_name or 'Unknown'}: "
                  f"{stats.get('win_rate', 0):.1%} win rate "
                  f"({stats.get('wins', 0)} wins from {stats.get('runs', 0)} runs)")


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

    # Analytics options
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Run analytics on existing data (reads from --db-path or --output directory)",
    )
    parser.add_argument(
        "--analyze-format",
        type=str,
        choices=["text", "json"],
        default="text",
        help="Output format for analytics (default: text)",
    )

    args = parser.parse_args()

    # Handle --analyze mode (runs without async operations)
    if args.analyze:
        run_analytics(
            data_dir=args.output,
            db_path=args.db_path if Path(args.db_path).exists() else None,
            output_format=args.analyze_format,
        )
        return

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

        # Export to database if requested
        if args.export_sqlite:
            export_to_db_if_needed(args.output, args.db_path)
        return

    # Default behavior: scrape single date
    await crawl_race(
        args.date,
        args.racecourse,
        args.output,
        args.rate_limit,
        args.rate_jitter,
        args.export_sqlite,
        args.db_path,
    )


def main() -> None:
    """Main entry point for the CLI (synchronous wrapper for async_main)."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
