"""Unit tests for the DiscoveryCache module."""

import pytest
import tempfile
from pathlib import Path
from hkjc_scraper.cache import DiscoveryCache


def test_cache_creation():
    """Test cache file is created with correct structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "test_cache.json"
        cache = DiscoveryCache(str(cache_path))

        assert cache.cache_path == cache_path
        assert cache.data == {
            "discovered": [],
            "season_breaks": [],
            "last_updated": None,
        }


def test_cache_add_and_retrieve():
    """Test adding and retrieving discovered entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "test_cache.json"
        cache = DiscoveryCache(str(cache_path))

        cache.add_discovery("2015/01/01", "ST", 8)
        cache.add_discovery("2015/01/01", "HV", 8)
        cache.add_discovery("2015/01/04", "ST", 10)

        discovered = cache.get_discovered()
        assert len(discovered) == 3

        # Check specific entry
        st_entry = [e for e in discovered if e["date"] == "2015/01/01" and e["racecourse"] == "ST"][0]
        assert st_entry["race_count"] == 8


def test_cache_is_cached():
    """Test checking if entry is cached."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "test_cache.json"
        cache = DiscoveryCache(str(cache_path))
        cache.add_discovery("2015/01/01", "ST", 8)

        assert cache.is_cached("2015/01/01", "ST") is True
        assert cache.is_cached("2015/01/01", "HV") is False
        assert cache.is_cached("2015/01/02", "ST") is False


def test_cache_save_and_load():
    """Test saving and loading cache."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "test_cache.json"
        cache = DiscoveryCache(str(cache_path))

        cache.add_discovery("2015/01/01", "ST", 8)
        cache.save()

        # Load into new cache instance
        cache2 = DiscoveryCache(str(cache_path))
        loaded = cache2.load()

        assert loaded is True
        discovered = cache2.get_discovered()
        assert len(discovered) == 1
        assert discovered[0] == {"date": "2015/01/01", "racecourse": "ST", "race_count": 8}


def test_season_break_check():
    """Test August is detected as season break."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "test_cache.json"
        cache = DiscoveryCache(str(cache_path))

        assert cache.is_season_break("2015/08/01") is True
        assert cache.is_season_break("2015/07/31") is False
        assert cache.is_season_break("2015/09/01") is False


def test_no_duplicate_entries():
    """Test adding same entry twice doesn't create duplicates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "test_cache.json"
        cache = DiscoveryCache(str(cache_path))

        cache.add_discovery("2015/01/01", "ST", 8)
        cache.add_discovery("2015/01/01", "ST", 8)  # Duplicate

        discovered = cache.get_discovered()
        assert len(discovered) == 1
