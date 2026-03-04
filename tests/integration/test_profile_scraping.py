import pytest
from hkjc_scraper.spider import HKJCRacingSpider


@pytest.mark.integration
async def test_profile_scraping_end_to_end():
    """Test full profile scraping with live data."""
    spider = HKJCRacingSpider(dates=["2026/03/04"], racecourse="HV")
    result = await spider.run()

    # Check that profile tables exist
    tables = {item["table"] for item in result.items}
    assert "horses" in tables
    assert "jockeys" in tables
    assert "trainers" in tables

    # Verify deduplication (no duplicate horse IDs)
    horse_items = [i for i in result.items if i["table"] == "horses"]
    horse_ids = [i["data"].get("horse_id") for i in horse_items if i["data"].get("horse_id")]
    assert len(horse_ids) == len(set(horse_ids)), "Duplicate horse IDs found"

    # Verify performance has foreign keys
    perf_items = [i for i in result.items if i["table"] == "performance"]
    if perf_items:
        # At least some should have jockey_id and trainer_id
        items_with_jockey_id = [i for i in perf_items if i["data"].get("jockey_id")]
        items_with_trainer_id = [i for i in perf_items if i["data"].get("trainer_id")]
        assert len(items_with_jockey_id) > 0, "No jockey_id found in performance items"
        assert len(items_with_trainer_id) > 0, "No trainer_id found in performance items"
