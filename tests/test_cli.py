"""Unit tests for CLI functions."""

import csv
import json
from pathlib import Path

import pytest

from hkjc_scraper.cli import flatten_dict, save_csv, save_json


class TestFlattenDict:
    """Tests for flatten_dict function."""

    def test_flatten_dict_simple(self):
        """Test flattening a simple dictionary."""
        data = {"name": "Test", "value": 123}
        result = flatten_dict(data)
        assert result == {"name": "Test", "value": 123}

    def test_flatten_dict_nested_dict(self):
        """Test flattening nested dictionary as JSON string."""
        data = {"name": "Test", "rating": {"high": 80, "low": 40}}
        result = flatten_dict(data)
        assert result["name"] == "Test"
        # Nested dict should be serialized as JSON
        assert json.loads(result["rating"]) == {"high": 80, "low": 40}

    def test_flatten_dict_list(self):
        """Test flattening list as JSON string."""
        data = {"name": "Test", "positions": ["1", "2", "3"]}
        result = flatten_dict(data)
        assert result["name"] == "Test"
        # List should be serialized as JSON
        assert json.loads(result["positions"]) == ["1", "2", "3"]

    def test_flatten_dict_with_parent_key(self):
        """Test flattening with parent key prefix."""
        data = {"nested": {"value": 123}}
        result = flatten_dict(data, parent_key="parent")
        assert "parent.nested" in result
        assert json.loads(result["parent.nested"]) == {"value": 123}

    def test_flatten_dict_chinese_text(self):
        """Test that Chinese text is preserved."""
        data = {"name": "測試", "location": "沙田"}
        result = flatten_dict(data)
        assert result["name"] == "測試"
        assert result["location"] == "沙田"


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


class TestSaveCsv:
    """Tests for save_csv function."""

    def test_save_csv(self, tmp_path: Path):
        """Test saving data to CSV file."""
        data = [
            {"name": "Test1", "value": 123},
            {"name": "Test2", "value": 456},
        ]
        file_path = tmp_path / "test.csv"
        save_csv(data, file_path)

        assert file_path.exists()
        with open(file_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["name"] == "Test1"
        assert rows[0]["value"] == "123"

    def test_save_csv_chinese(self, tmp_path: Path):
        """Test that Chinese text is saved correctly in CSV."""
        data = [{"name": "測試", "location": "沙田"}]
        file_path = tmp_path / "test.csv"
        save_csv(data, file_path)

        with open(file_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows[0]["name"] == "測試"
        assert rows[0]["location"] == "沙田"

    def test_save_csv_nested_structures(self, tmp_path: Path):
        """Test that nested structures are serialized as JSON in CSV."""
        data = [
            {"name": "Test", "rating": {"high": 80, "low": 40}},
        ]
        file_path = tmp_path / "test.csv"
        save_csv(data, file_path)

        with open(file_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert json.loads(rows[0]["rating"]) == {"high": 80, "low": 40}

    def test_save_csv_empty_data(self, tmp_path: Path):
        """Test saving empty data list does not create file."""
        file_path = tmp_path / "test.csv"
        save_csv([], file_path)
        assert not file_path.exists()

    def test_save_csv_missing_keys(self, tmp_path: Path):
        """Test that all keys across records are included."""
        data = [
            {"name": "Test1", "value": 123},
            {"name": "Test2", "extra": "field"},
        ]
        file_path = tmp_path / "test.csv"
        save_csv(data, file_path)

        with open(file_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert set(rows[0].keys()) == {"extra", "name", "value"}
        assert rows[0]["value"] == "123"
        assert rows[1]["extra"] == "field"
