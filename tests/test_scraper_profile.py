"""Tests for scrape_horse_profile gear extraction from 所有往績 table."""
from unittest.mock import MagicMock

import pytest

from hkjc_scraper.scraper import scrape_horse_profile

PROFILE_HTML_WITH_GEAR = """
<html><body>
<table>
  <tr><td>出生地 / 馬齡</td><td>:</td><td>英國 / 5</td></tr>
  <tr><td>毛色 / 性別</td><td>:</td><td>棗色 / 閹馬</td></tr>
  <tr><td>現時評分</td><td>:</td><td>47</td></tr>
</table>
<table>
  <tr>
    <td>場次</td><td>名次</td><td>日期</td><td>馬場</td><td>途程</td>
    <td>場地狀況</td><td>賽事班次</td><td>檔位</td><td>評分</td>
    <td>練馬師</td><td>騎師</td><td>頭馬距離</td><td>獨贏賠率</td>
    <td>實際負磅</td><td>沿途走位</td><td>完成時間</td><td>排位體重</td>
    <td>配備</td><td>賽事重播</td>
  </tr>
  <tr>
    <td>444</td><td>1</td><td>19/02/26</td><td>沙田</td><td>1200</td>
    <td>好</td><td>5</td><td>4</td><td>40</td>
    <td>丁冠豪</td><td>金霍</td><td>—</td><td>6.2</td>
    <td>133</td><td>1 2 3</td><td>1:09.86</td><td>1073</td>
    <td>SR/TT</td><td></td>
  </tr>
  <tr>
    <td>395</td><td>5</td><td>01/02/26</td><td>沙田</td><td>1200</td>
    <td>好/快</td><td>5</td><td>2</td><td>40</td>
    <td>丁冠豪</td><td>金霍</td><td>3</td><td>12</td>
    <td>131</td><td>3 4 5</td><td>1:10.50</td><td>1075</td>
    <td>SR/TT</td><td></td>
  </tr>
  <tr>
    <td>305</td><td>3</td><td>01/01/26</td><td>沙田</td><td>1200</td>
    <td>好</td><td>5</td><td>1</td><td>42</td>
    <td>丁冠豪</td><td>金霍</td><td>2</td><td>8</td>
    <td>128</td><td>2 3 4</td><td>1:10.20</td><td>1070</td>
    <td>B-/SR/TT</td><td></td>
  </tr>
</table>
</body></html>
"""


@pytest.fixture
def mock_session(mock_http_response):
    session = MagicMock()
    session.get.return_value = mock_http_response(PROFILE_HTML_WITH_GEAR)
    return session


def test_scrape_horse_profile_returns_profile_and_past_gear(mock_session):
    """scrape_horse_profile should return dict with 'profile' and 'past_gear' keys."""
    result = scrape_horse_profile("HK_2024_K121", mock_session)
    assert "profile" in result
    assert "past_gear" in result


def test_scrape_horse_profile_profile_fields_intact(mock_session):
    """Profile fields should still be accessible under result['profile']."""
    result = scrape_horse_profile("HK_2024_K121", mock_session)
    profile = result["profile"]
    assert profile["origin"] == "英國"
    assert profile["age"] == 5
    assert profile["current_rating"] == 47


def test_scrape_horse_profile_past_gear_keyed_by_race_code(mock_session):
    """past_gear should be a dict of {race_code (int): gear_str}."""
    result = scrape_horse_profile("HK_2024_K121", mock_session)
    past_gear = result["past_gear"]
    assert past_gear[444] == "SR/TT"
    assert past_gear[395] == "SR/TT"
    assert past_gear[305] == "B-/SR/TT"


def test_scrape_horse_profile_empty_gear_stored_as_none(mock_http_response):
    """Empty 配備 cell should produce None, not empty string."""
    # Replace first SR/TT with empty
    html = PROFILE_HTML_WITH_GEAR.replace(
        "<td>SR/TT</td><td></td>\n  </tr>\n  <tr>\n    <td>395</td>",
        "<td></td><td></td>\n  </tr>\n  <tr>\n    <td>395</td>",
    )
    session = MagicMock()
    session.get.return_value = mock_http_response(html)
    result = scrape_horse_profile("HK_2024_K121", session)
    assert result["past_gear"].get(444) is None
