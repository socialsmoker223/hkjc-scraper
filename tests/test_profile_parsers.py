import pytest
from hkjc_scraper.profile_parsers import extract_horse_id, extract_jockey_id, extract_trainer_id

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
