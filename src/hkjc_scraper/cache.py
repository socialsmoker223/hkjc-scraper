"""Cache operations for discovered race dates."""

import json
from pathlib import Path
from datetime import datetime
from typing import Any


class DiscoveryCache:
    """Cache for discovered historical race dates."""

    def __init__(self, cache_path: str | None = None):
        """Initialize cache with file path.

        Args:
            cache_path: Path to cache file. Defaults to data/.discovered_dates.json
        """
        if cache_path is None:
            cache_path = "data/.discovered_dates.json"
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        self.data: dict[str, Any] = {
            "discovered": [],
            "season_breaks": [],
            "last_updated": None,
        }

    def load(self) -> bool:
        """Load cache from disk.

        Returns:
            True if cache was loaded, False if file doesn't exist or is invalid
        """
        if not self.cache_path.exists():
            return False

        try:
            content = self.cache_path.read_text(encoding="utf-8")
            self.data = json.loads(content)
            return True
        except (json.JSONDecodeError, IOError):
            return False

    def save(self) -> None:
        """Save cache to disk."""
        self.data["last_updated"] = datetime.now().isoformat()
        content = json.dumps(self.data, indent=2, ensure_ascii=False)
        self.cache_path.write_text(content, encoding="utf-8")

    def add_discovery(self, date: str, racecourse: str, race_count: int) -> None:
        """Add a discovered race date to the cache.

        Args:
            date: Race date in YYYY/MM/DD format
            racecourse: Racecourse code (ST or HV)
            race_count: Number of races found
        """
        entry = {
            "date": date,
            "racecourse": racecourse,
            "race_count": race_count
        }

        # Check if already exists
        for existing in self.data["discovered"]:
            if existing["date"] == date and existing["racecourse"] == racecourse:
                return  # Already cached

        self.data["discovered"].append(entry)

    def is_cached(self, date: str, racecourse: str) -> bool:
        """Check if a date + racecourse is already cached.

        Args:
            date: Race date in YYYY/MM/DD format
            racecourse: Racecourse code (ST or HV)

        Returns:
            True if cached, False otherwise
        """
        for entry in self.data["discovered"]:
            if entry["date"] == date and entry["racecourse"] == racecourse:
                return True
        return False

    def get_discovered(self) -> list[dict]:
        """Get all discovered race dates.

        Returns:
            List of dicts with keys: date, racecourse, race_count
        """
        return self.data.get("discovered", [])

    def mark_season_break(self, month: str) -> None:
        """Mark a month as season break (e.g., August).

        Args:
            month: Month in YYYY-MM format
        """
        if month not in self.data.get("season_breaks", []):
            self.data.setdefault("season_breaks", []).append(month)

    def is_season_break(self, date: str) -> bool:
        """Check if a date falls during season break (August).

        Args:
            date: Date in YYYY/MM/DD format

        Returns:
            True if August, False otherwise
        """
        # Extract month from date (YYYY/MM/DD -> MM)
        parts = date.split("/")
        if len(parts) >= 2:
            return parts[1] == "08"  # August is season break
        return False
