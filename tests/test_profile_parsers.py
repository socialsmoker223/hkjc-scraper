import pytest
from hkjc_scraper.profile_parsers import (
    extract_horse_id,
    extract_jockey_id,
    extract_trainer_id,
    parse_horse_profile,
    parse_jockey_profile,
    parse_trainer_profile,
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


def test_parse_horse_profile_with_none_response():
    """Test that None response is handled gracefully."""
    result = parse_horse_profile(None, "HK_2024_K306", "Test Horse")
    assert result["horse_id"] == "HK_2024_K306"
    assert result["name"] == "Test Horse"


def test_parse_horse_profile_with_invalid_response():
    """Test that invalid response object (missing css/text) is handled gracefully."""
    class InvalidResponse:
        pass  # No css or text attributes

    result = parse_horse_profile(InvalidResponse(), "HK_2024_K306", "Test Horse")
    assert result["horse_id"] == "HK_2024_K306"
    assert result["name"] == "Test Horse"


def test_parse_horse_profile_with_malformed_rating():
    """Test that non-numeric ratings are handled gracefully."""
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
            self.text = "冠-亞-季-總出賽次數 5-3-2-15"
            self.rows = [
                MockRow(["現時評分 ：", "N/A"]),
                MockRow(["季初評分 ：", ""]),
            ]

        def css(self, selector):
            return self.rows

    response = MockResponse()
    result = parse_horse_profile(response, "HK_2024_K306", "Test Horse")

    assert result["current_rating"] is None
    assert result["initial_rating"] is None


def test_parse_horse_profile_with_empty_data_fields():
    """Test that empty data fields are handled gracefully."""
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
            # No career record in text
            self.text = "Some random text 1-2-3-4 without proper label"
            self.rows = [
                MockRow(["出生地/馬齡 ：", ""]),
                MockRow(["父系 ：", ""]),
            ]

        def css(self, selector):
            return self.rows

    response = MockResponse()
    result = parse_horse_profile(response, "HK_2024_K306", "Test Horse")

    # Empty strings are skipped by the parser (line 70: if not value)
    # so default None values are retained
    assert result["country_of_birth"] is None
    assert result["sire"] is None
    # Career record should remain at default (no match without proper label)
    assert result["career_record"]["wins"] == 0
    assert result["career_record"]["places"] == 0
    assert result["career_record"]["shows"] == 0
    assert result["career_record"]["total"] == 0


def test_parse_horse_profile_career_record_not_matched_without_label():
    """Test that career record regex only matches with proper Chinese label."""
    class MockCell:
        def __init__(self, text):
            self.text = text

    class MockRow:
        def __init__(self, cells):
            self.cells = [MockCell(t) for t in cells]

        def css(self, sel):
            return self.cells

    class MockResponse:
        def __init__(self, text):
            self.text = text
            self.rows = []

        def css(self, selector):
            return self.rows

    # Text with pattern but no label - should NOT match
    response = MockResponse("Some random 10-5-3-25 numbers in text")
    result = parse_horse_profile(response, "HK_2024_K306", "Test Horse")
    assert result["career_record"]["wins"] == 0
    assert result["career_record"]["total"] == 0

    # Text with proper label - SHOULD match
    response2 = MockResponse("冠-亞-季-總出賽次數 10-5-3-25")
    result2 = parse_horse_profile(response2, "HK_2024_K306", "Test Horse")
    assert result2["career_record"]["wins"] == 10
    assert result2["career_record"]["places"] == 5
    assert result2["career_record"]["shows"] == 3
    assert result2["career_record"]["total"] == 25


def test_parse_jockey_profile_basic_info():
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
            self.text = """
                背景： Test background text
                成就： Test achievements
                在港累積232場勝出率百分之12.4
            """
            self.rows = [
                MockRow(["年齡 ：", "45歲"]),
                MockRow(["冠 ：", "32"]),
                MockRow(["亞 ：", "42"]),
                MockRow(["勝出率 ：", "11.76%"]),
                MockRow(["所贏獎金 ：", "$54,862,525"]),
            ]

        def css(self, selector):
            return self.rows

    response = MockResponse()
    result = parse_jockey_profile(response, "BH", "布文")

    assert result["jockey_id"] == "BH"
    assert result["name"] == "布文"
    assert result["age"] == 45
    assert result["background"] == "Test background text"
    assert result["achievements"] == "Test achievements"
    assert result["career_wins"] == 232
    assert result["career_win_rate"] == 12.4
    assert result["season_stats"]["wins"] == 32
    assert result["season_stats"]["places"] == 42
    assert result["season_stats"]["win_rate"] == 11.76
    assert result["season_stats"]["prize_money"] == 54862525


def test_parse_jockey_profile_with_none_response():
    """Test that None response is handled gracefully."""
    result = parse_jockey_profile(None, "BH", "Test Jockey")
    assert result["jockey_id"] == "BH"
    assert result["name"] == "Test Jockey"


def test_parse_jockey_profile_with_invalid_response():
    """Test that invalid response object is handled gracefully."""
    class InvalidResponse:
        pass  # No css or text attributes

    result = parse_jockey_profile(InvalidResponse(), "BH", "Test Jockey")
    assert result["jockey_id"] == "BH"
    assert result["name"] == "Test Jockey"


def test_parse_jockey_profile_with_missing_data():
    """Test that missing data fields are handled gracefully."""
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
            self.text = "Some text without proper patterns"
            self.rows = [
                MockRow(["冠 ：", ""]),
            ]

        def css(self, selector):
            return self.rows

    response = MockResponse()
    result = parse_jockey_profile(response, "BH", "Test Jockey")

    assert result["jockey_id"] == "BH"
    assert result["name"] == "Test Jockey"
    assert result["age"] is None
    assert result["background"] is None
    assert result["achievements"] is None
    assert result["career_wins"] is None
    assert result["career_win_rate"] is None
    assert result["season_stats"]["wins"] is None
    assert result["season_stats"]["places"] is None
    assert result["season_stats"]["win_rate"] is None
    assert result["season_stats"]["prize_money"] is None


def test_parse_trainer_profile_basic_info():
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
            self.text = """
                背景： Test background
                成就： Test achievements
                在港累積1166場勝出率百分之9.6
            """
            self.rows = [
                MockRow(["年齡 ：", "58歲"]),
                MockRow(["冠 ：", "37"]),
                MockRow(["亞 ：", "27"]),
                MockRow(["季 ：", "22"]),
                MockRow(["殿 ：", "22"]),
                MockRow(["出馬總數 ：", "310"]),
                MockRow(["勝出率 ：", "11.94%"]),
                MockRow(["所贏獎金 ：", "$49,009,255"]),
            ]

        def css(self, selector):
            return self.rows

    response = MockResponse()
    result = parse_trainer_profile(response, "FC", "方嘉柏")

    assert result["trainer_id"] == "FC"
    assert result["name"] == "方嘉柏"
    assert result["age"] == 58
    assert result["background"] == "Test background"
    assert result["achievements"] == "Test achievements"
    assert result["career_wins"] == 1166
    assert result["career_win_rate"] == 9.6
    assert result["season_stats"]["wins"] == 37
    assert result["season_stats"]["places"] == 27
    assert result["season_stats"]["shows"] == 22
    assert result["season_stats"]["fourth"] == 22
    assert result["season_stats"]["total_runners"] == 310
    assert result["season_stats"]["win_rate"] == 11.94
    assert result["season_stats"]["prize_money"] == 49009255


def test_parse_trainer_profile_with_none_response():
    """Test that None response is handled gracefully."""
    result = parse_trainer_profile(None, "FC", "Test Trainer")
    assert result["trainer_id"] == "FC"
    assert result["name"] == "Test Trainer"


def test_parse_trainer_profile_with_invalid_response():
    """Test that invalid response object is handled gracefully."""
    class InvalidResponse:
        pass  # No css or text attributes

    result = parse_trainer_profile(InvalidResponse(), "FC", "Test Trainer")
    assert result["trainer_id"] == "FC"
    assert result["name"] == "Test Trainer"


def test_parse_trainer_profile_with_missing_data():
    """Test that missing data fields are handled gracefully."""
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
            self.text = "Some text without proper patterns"
            self.rows = [
                MockRow(["冠 ：", ""]),
            ]

        def css(self, selector):
            return self.rows

    response = MockResponse()
    result = parse_trainer_profile(response, "FC", "Test Trainer")

    assert result["trainer_id"] == "FC"
    assert result["name"] == "Test Trainer"
    assert result["age"] is None
    assert result["background"] is None
    assert result["achievements"] is None
    assert result["career_wins"] is None
    assert result["career_win_rate"] is None
    assert result["season_stats"]["wins"] is None
    assert result["season_stats"]["places"] is None
    assert result["season_stats"]["shows"] is None
    assert result["season_stats"]["fourth"] is None
    assert result["season_stats"]["total_runners"] is None
    assert result["season_stats"]["win_rate"] is None
    assert result["season_stats"]["prize_money"] is None

