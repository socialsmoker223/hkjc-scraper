"""
Pytest configuration and fixtures
"""

import pytest
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hkjc_scraper.models import Base


@pytest.fixture
def test_db_session():
    """Create in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()
    engine.dispose()


@pytest.fixture
def sample_race_data():
    """Sample race data for testing"""
    return {
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
        "horses": [
            {
                "code": "J344",
                "name_cn": "測試馬",
                "name_en": "Test Horse",
                "hkjc_horse_id": "HK_2023_J344",
            }
        ],
        "jockeys": [{"code": "MDLR", "name_cn": "測試騎師", "name_en": "Test Jockey"}],
        "trainers": [{"code": "YTP", "name_cn": "測試練馬師", "name_en": "Test Trainer"}],
        "runners": [
            {
                "horse_code": "J344",
                "jockey_code": "MDLR",
                "trainer_code": "YTP",
                "finish_position_num": 1,
                "horse_no": 1,
                "actual_weight": 120,
                "declared_weight": 1150,
                "draw": 5,
                "win_odds": 5.5,
            }
        ],
        "horse_sectionals": [],
        "horse_profiles": [],
        "validation_summary": {
            "runners_total": 1,
            "runners_valid": 1,
            "runners_invalid": 0,
            "profiles_total": 0,
            "profiles_valid": 0,
            "profiles_invalid": 0,
        },
    }


@pytest.fixture
def mock_http_response():
    """Factory for creating mock HTTP responses"""

    class MockResponse:
        def __init__(self, text, status_code=200):
            self.text = text
            self.status_code = status_code
            self.content = text.encode("utf-8")

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(f"HTTP {self.status_code}")

    return MockResponse


@pytest.fixture
def sample_html_race_header():
    """Sample HTML for race header table"""
    return """
    <table>
        <tr><td>第 1 場 (284)</td></tr>
        <tr><td>Empty</td></tr>
        <tr><td>第五班 - 1200米 - (40-0)</td></tr>
        <tr><td>Race Name</td></tr>
    </table>
    """


@pytest.fixture
def invalid_html_race_header():
    """Invalid HTML for race header (insufficient rows)"""
    return """
    <table>
        <tr><td>第 1 場 (284)</td></tr>
        <tr><td>Only two rows</td></tr>
    </table>
    """
