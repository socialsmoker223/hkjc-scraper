"""Tests for CLI."""
from unittest.mock import MagicMock

import pytest

from hkjc_scraper.cli import group_items_by_table


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
