"""Utility functions for HKJC scraper."""

from datetime import datetime, timedelta
from typing import Generator


def generate_date_range(start_date: str, end_date: str) -> Generator[str, None, None]:
    """Generate dates from start to end (inclusive).

    Args:
        start_date: Start date in YYYY/MM/DD format
        end_date: End date in YYYY/MM/DD format

    Yields:
        Dates in YYYY/MM/DD format
    """
    start = datetime.strptime(start_date, "%Y/%m/%d")
    end = datetime.strptime(end_date, "%Y/%m/%d")

    current = start
    while current <= end:
        yield current.strftime("%Y/%m/%d")
        current += timedelta(days=1)


def parse_race_date(date_str: str) -> datetime:
    """Parse race date string to datetime.

    Args:
        date_str: Date in YYYY/MM/DD format

    Returns:
        datetime object
    """
    return datetime.strptime(date_str, "%Y/%m/%d")
