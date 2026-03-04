import pytest
from hkjc_scraper.profile_parsers import (
    extract_horse_id,
    extract_jockey_id,
    extract_trainer_id,
    parse_horse_profile,
)

def test_extract_horse_id_from_href():
    href = "/zh-hk/local/information/horse?horseid=HK_2024_K306"
    assert extract_horse_id(href) == "HK_2024_K306"

def test_extract_horse_id_no_match():
    href = "/some/other/path"
    assert extract_horse_id(href) is None

def test_extract_jockey_id_from_href():
    href = "/zh-hk/local/information/jockeyprofile?jockeyid=BH&Season=Current"
    assert extract_jockey_id(href) == "BH"

def test_extract_jockey_id_with_ampersand():
    href = "/zh-hk/local/information/jockeyprofile?jockeyid=AA&Season=Current"
    assert extract_jockey_id(href) == "AA"

def test_extract_trainer_id_from_href():
    href = "/zh-hk/local/information/trainerprofile?trainerid=FC&season=Current"
    assert extract_trainer_id(href) == "FC"

def test_extract_trainer_id_no_match():
    href = "/some/other/path"
    assert extract_trainer_id(href) is None


def test_parse_horse_profile_basic_info():
    # Create a mock response with css method that returns mock elements
    class MockCell:
        def __init__(self, text):
            self.text = text

    class MockRow:
        def __init__(self, cells):
            self.cells = [MockCell(t) for t in cells]

        def css(self, sel):
            return self.cells

    class MockResponse:
        def __init__(self):
            self.text = "冠-亞-季-總出賽次數 1-0-2-16"
            self.rows = [
                MockRow(["出生地/馬齡 ：", "澳洲 3歲"]),
                MockRow(["毛色/性別 ：", "棗色 閹馬"]),
                MockRow(["父系 ：", "Tivaci"]),
                MockRow(["母系 ：", "Promenade"]),
                MockRow(["外祖父 ：", "Danehill"]),
                MockRow(["馬主 ：", "Test Owner"]),
                MockRow(["現時評分 ：", "82"]),
                MockRow(["季初評分 ：", "58"]),
                MockRow(["今季獎金 ：", "$795,375"]),
                MockRow(["總獎金 ：", "$929,925"]),
            ]

        def css(self, selector):
            return self.rows

    response = MockResponse()
    result = parse_horse_profile(response, "HK_2024_K306", "堅多福")

    assert result["horse_id"] == "HK_2024_K306"
    assert result["name"] == "堅多福"
    assert result["country_of_birth"] == "澳洲"
    assert result["age"] == "3歲"
    assert result["colour"] == "棗色"
    assert result["gender"] == "閹馬"
    assert result["sire"] == "Tivaci"
    assert result["dam"] == "Promenade"
    assert result["damsire"] == "Danehill"
    assert result["owner"] == "Test Owner"
    assert result["current_rating"] == 82
    assert result["initial_rating"] == 58
    assert result["season_prize"] == 795375
    assert result["total_prize"] == 929925
    assert result["career_record"]["wins"] == 1
    assert result["career_record"]["places"] == 0
    assert result["career_record"]["shows"] == 2
    assert result["career_record"]["total"] == 16
