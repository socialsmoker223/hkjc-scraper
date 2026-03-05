import pytest
from hkjc_scraper.spider import HKJCRacingSpider

@pytest.mark.integration
async def test_sectional_times_end_to_end():
    """Test full sectional times scraping with live data."""
    spider = HKJCRacingSpider(dates=["2026/03/01"], racecourse="ST")
    result = await spider.run()

    # Check sectional_times items exist
    sectional_items = [i for i in result.items if i["table"] == "sectional_times"]
    assert len(sectional_items) > 0, "No sectional times found"

    # Verify structure of first item
    item = sectional_items[0]["data"]
    assert "race_id" in item
    assert "horse_no" in item
    assert "section_number" in item
    assert "position" in item
    assert "margin" in item
    assert "time" in item

    # Verify we have multiple sections per horse
    horse_sections = [i for i in sectional_items if i["data"]["horse_no"] == sectional_items[0]["data"]["horse_no"]]
    assert len(horse_sections) > 1, "Should have multiple sections per horse"
