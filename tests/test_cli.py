"""Tests for CLI."""
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hkjc_scraper.cli import group_items_by_table, save_json


class TestGroupItemsByTable:
    """Test group_items_by_table function."""

    def test_group_items_by_table_empty(self):
        result = group_items_by_table([])
        assert result == {}

    def test_group_items_by_table_single_item(self):
        items = [{"table": "races", "data": {"race_id": "1"}}]
        result = group_items_by_table(items)
        assert result == {"races": [{"race_id": "1"}]}

    def test_group_items_by_table_multiple_tables(self):
        items = [
            {"table": "races", "data": {"race_id": "1"}},
            {"table": "races", "data": {"race_id": "2"}},
            {"table": "performance", "data": {"horse_no": "1"}},
        ]
        result = group_items_by_table(items)
        assert result == {
            "races": [{"race_id": "1"}, {"race_id": "2"}],
            "performance": [{"horse_no": "1"}],
        }

    def test_group_items_by_table_unknown_table(self):
        items = [
            {"table": "races", "data": {"race_id": "1"}},
            {"data": {"no_table": "value"}},  # No table key
        ]
        result = group_items_by_table(items)
        assert result == {
            "races": [{"race_id": "1"}],
            "unknown": [{"no_table": "value"}],
        }


class TestSaveJson:
    """Tests for save_json function."""

    def test_save_json(self, tmp_path: Path):
        """Test saving data to JSON file."""
        data = [{"name": "Test1"}, {"name": "Test2"}]
        file_path = tmp_path / "test.json"
        save_json(data, file_path)

        assert file_path.exists()
        with open(file_path, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data

    def test_save_json_chinese(self, tmp_path: Path):
        """Test that Chinese text is saved correctly."""
        data = [{"name": "測試", "location": "沙田"}]
        file_path = tmp_path / "test.json"
        save_json(data, file_path)

        with open(file_path, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded[0]["name"] == "測試"

    def test_save_json_empty_data(self, tmp_path: Path):
        """Test saving empty data list."""
        file_path = tmp_path / "test.json"
        save_json([], file_path)
        assert file_path.exists()


class TestExportToDbIfNeeded:
    """Tests for export_to_db_if_needed function."""

    def test_export_to_db_if_needed_creates_database(self, tmp_path: Path):
        """Test that export creates database file."""
        from unittest.mock import patch

        # Create sample JSON data files
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        races_data = [{
            "race_id": "2026-03-01-ST-1",
            "race_date": "2026/03/01",
            "race_no": 1,
            "racecourse": "沙田",
            "distance": 1200,
        }]
        with open(data_dir / "races_2026-03-01.json", "w", encoding="utf-8") as f:
            json.dump(races_data, f)

        db_path = tmp_path / "test.db"

        from hkjc_scraper.cli import export_to_db_if_needed
        export_to_db_if_needed(str(data_dir), str(db_path))

        assert db_path.exists()

    def test_export_to_db_if_needed_handles_errors(self, tmp_path: Path, capsys):
        """Test error handling in export."""
        from hkjc_scraper.cli import export_to_db_if_needed

        # Use non-existent directory
        export_to_db_if_needed("/nonexistent/path", str(tmp_path / "test.db"))

        captured = capsys.readouterr()
        assert "Error" in captured.out


class TestCrawlRace:
    """Tests for crawl_race function."""

    def test_crawl_race_creates_output_dir(self, tmp_path: Path):
        """Test that crawl_race creates output directory."""
        from unittest.mock import AsyncMock, patch
        import asyncio

        output_dir = tmp_path / "output"

        # Mock the spider
        with patch("hkjc_scraper.cli.HKJCRacingSpider") as mock_spider_class:
            mock_spider = AsyncMock()
            mock_spider.run = AsyncMock()
            mock_result = MagicMock()
            mock_result.items = [
                {"table": "races", "data": {"race_id": "R1"}},
                {"table": "performance", "data": {"horse_no": "1"}},
            ]
            mock_result.stats.requests_count = 10
            mock_spider.run.return_value = mock_result
            mock_spider_class.return_value = mock_spider

            mock_spider_class.return_value = mock_spider

            from hkjc_scraper.cli import crawl_race
            asyncio.run(crawl_race(
                date="2026/03/01",
                racecourse="ST",
                output_dir=str(output_dir),
            ))

        assert output_dir.exists()

    def test_crawl_race_saves_json_files(self, tmp_path: Path):
        """Test that crawl_race saves JSON files."""
        from unittest.mock import AsyncMock, patch
        import asyncio

        output_dir = tmp_path / "output"

        # Mock the spider
        with patch("hkjc_scraper.cli.HKJCRacingSpider") as mock_spider_class:
            mock_spider = AsyncMock()
            mock_spider.run = AsyncMock()
            mock_result = MagicMock()
            mock_result.items = [
                {"table": "races", "data": {"race_id": "R1", "race_date": "2026/03/01"}},
            ]
            mock_result.stats.requests_count = 5
            mock_spider.run.return_value = mock_result
            mock_spider_class.return_value = mock_spider

            from hkjc_scraper.cli import crawl_race
            asyncio.run(crawl_race(
                date="2026/03/01",
                racecourse="ST",
                output_dir=str(output_dir),
            ))

        # Check files were created
        assert (output_dir / "races_2026-03-01.json").exists()

    def test_crawl_race_exports_to_db(self, tmp_path: Path):
        """Test that crawl_race exports to SQLite when requested."""
        from unittest.mock import AsyncMock, patch, MagicMock
        import asyncio

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        db_path = tmp_path / "test.db"

        # Create sample JSON file
        races_data = [{"race_id": "R1", "race_date": "2026/03/01", "race_no": 1, "racecourse": "沙田"}]
        with open(output_dir / "races_2026-03-01.json", "w", encoding="utf-8") as f:
            json.dump(races_data, f)

        # Mock the spider
        with patch("hkjc_scraper.cli.HKJCRacingSpider") as mock_spider_class:
            mock_spider = AsyncMock()
            mock_spider.run = AsyncMock()
            mock_result = MagicMock()
            mock_result.items = []
            mock_result.stats.requests_count = 0
            mock_spider.run.return_value = mock_result
            mock_spider_class.return_value = mock_spider

            from hkjc_scraper.cli import crawl_race
            asyncio.run(crawl_race(
                date="2026/03/01",
                racecourse="ST",
                output_dir=str(output_dir),
                export_sqlite=True,
                db_path=str(db_path),
            ))

        assert db_path.exists()
