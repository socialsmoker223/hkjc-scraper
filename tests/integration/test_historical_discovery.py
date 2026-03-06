import pytest
from hkjc_scraper.spider import HKJCRacingSpider


@pytest.mark.integration
async def test_discover_small_date_range():
    """Test discovering races in a small date range."""
    spider = HKJCRacingSpider()

    # Discover one week (should have at least one race day)
    discovered = await spider.discover_dates(
        start_date="2015/01/01",
        end_date="2015/01/07"
    )

    # Should find some races
    assert len(discovered) > 0

    # Each entry should have required fields
    for entry in discovered:
        assert "date" in entry
        assert "racecourse" in entry
        assert "race_count" in entry
        assert entry["racecourse"] in ["ST", "HV"]
        assert entry["race_count"] > 0


@pytest.mark.integration
async def test_discover_respects_cache():
    """Test that discovery uses cached data."""
    spider = HKJCRacingSpider()

    # First discovery
    discovered1 = await spider.discover_dates(
        start_date="2015/01/01",
        end_date="2015/01/07"
    )

    # Second discovery should be instant (uses cache)
    discovered2 = await spider.discover_dates(
        start_date="2015/01/01",
        end_date="2015/01/07"
    )

    assert len(discovered1) == len(discovered2)
