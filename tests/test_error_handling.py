"""
Tests for error handling in scraper and persistence layers
"""

from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup
from sqlalchemy.exc import SQLAlchemyError

from hkjc_scraper.exceptions import ParseError
from hkjc_scraper.persistence import save_race_data
from hkjc_scraper.scraper import parse_race_header


class TestParseErrorHandling:
    """Test error handling in parsing functions"""

    def test_parse_race_header_with_insufficient_rows(self, invalid_html_race_header):
        """Test safe DOM navigation with insufficient rows"""
        soup = BeautifulSoup(invalid_html_race_header, "html.parser")
        table = soup.find("table")

        with pytest.raises(ParseError) as exc_info:
            parse_race_header(table)

        assert "Insufficient rows" in str(exc_info.value)

    def test_parse_race_header_with_valid_html(self, sample_html_race_header):
        """Test parsing with valid HTML structure"""
        soup = BeautifulSoup(sample_html_race_header, "html.parser")
        table = soup.find("table")

        # Should not raise an exception
        result = parse_race_header(table)
        assert result is not None
        assert isinstance(result, dict)

    def test_parse_race_header_with_missing_cells(self):
        """Test handling of missing table cells"""
        html = """
        <table>
            <tr><td>第 1 場 (284)</td></tr>
            <tr><td>Empty</td></tr>
            <tr></tr>  <!-- No cells in row 2 -->
        </table>
        """
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")

        # Should handle gracefully (race_class = None)
        result = parse_race_header(table)
        assert result is not None
        # race_class should be None when cells are missing
        assert result.get("race_class") is None


class TestDatabaseErrorHandling:
    """Test error handling in database operations"""

    def test_save_race_data_success(self, test_db_session, sample_race_data):
        """Test successful save operation"""
        result = save_race_data(test_db_session, sample_race_data)

        assert result is not None
        assert result["race_id"] is not None
        assert result["runner_count"] == 1
        assert result["sectional_count"] == 0
        # profile_count is now based on horses list length since we merge profiles
        # In sample_race_data, there is 1 horse, so count should be 1
        assert result["profile_count"] == 1

    def test_save_race_data_with_duplicate(self, test_db_session, sample_race_data):
        """Test UPSERT behavior for duplicate data"""
        # First save should succeed
        result1 = save_race_data(test_db_session, sample_race_data)
        assert result1["race_id"] is not None
        race_id_1 = result1["race_id"]

        # Commit the transaction
        test_db_session.commit()

        # Second save should update existing record (UPSERT behavior)
        result2 = save_race_data(test_db_session, sample_race_data)

        # Should return same race_id (update, not insert)
        assert result2["race_id"] == race_id_1
        assert result2["runner_count"] == 1  # Still has 1 runner

    def test_save_race_data_with_db_error(self, test_db_session, sample_race_data):
        """Test SQLAlchemyError handling"""
        # Mock flush to raise SQLAlchemyError
        with patch.object(test_db_session, "flush", side_effect=SQLAlchemyError("DB error")):
            with pytest.raises(SQLAlchemyError):
                save_race_data(test_db_session, sample_race_data)

    def test_save_race_data_rollback_on_error(self, test_db_session, sample_race_data):
        """Test that database session is rolled back on error"""
        # Mock flush to raise an error
        with patch.object(test_db_session, "flush", side_effect=SQLAlchemyError("DB error")):
            with patch.object(test_db_session, "rollback") as mock_rollback:
                with pytest.raises(SQLAlchemyError):
                    save_race_data(test_db_session, sample_race_data)

                # Verify rollback was called
                mock_rollback.assert_called_once()


class TestValidationErrorHandling:
    """Test validation error handling"""

    def test_invalid_position_code(self):
        """Test handling of invalid position codes"""
        # This test would require the validators module
        # For now, just verify the structure exists
        from hkjc_scraper import validators

        assert hasattr(validators, "validate_runners")
        assert hasattr(validators, "validate_meeting")
        assert hasattr(validators, "validate_race")


class TestNoneValueHandling:
    """Test handling of None values and missing data"""

    def test_parse_header_with_none_table(self):
        """Test parse_race_header with None input"""
        with pytest.raises((AttributeError, ParseError)):
            parse_race_header(None)

    def test_save_race_data_with_empty_lists(self, test_db_session):
        """Test saving race data with empty runners/sectionals"""
        minimal_data = {
            "meeting": {
                "date": "2025/12/23",
                "date_dmy": "23/12/2025",
                "venue_code": "ST",
                "venue_name": "沙田",
                "season": 2025,
            },
            "race": {
                "race_no": 1,
                "race_code": 284,
                "class_text": "第五班",
                "distance_m": 1200,
                "track_type": "草地",
                "going": "好地",
                "prize_total": 750000,
            },
            "horses": [],
            "jockeys": [],
            "trainers": [],
            "runners": [],
            "horse_sectionals": [],
            "horse_profiles": [],
        }

        result = save_race_data(test_db_session, minimal_data)

        assert result is not None
        assert result["race_id"] is not None
        assert result["runner_count"] == 0
        assert result["sectional_count"] == 0
