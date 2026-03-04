"""Integration tests for HKJC spider."""
import pytest
from hkjc_scraper.spider_v2 import HKJCRacingSpider


@pytest.mark.integration
class TestLiveCrawl:
    """Integration tests with live site."""

    @pytest.mark.asyncio
    async def test_crawl_single_race(self):
        spider = HKJCRacingSpider(
            dates=["2026/03/01"],
            racecourse="ST"
        )
        # Collect all items from streaming
        items = []
        requests_count = 0
        async for item in spider.stream():
            items.append(item)
            # Access stats inside the stream loop
            requests_count = spider.stats.requests_count

        assert len(items) > 0
        table_types = {item.get("table") for item in items}
        assert "races" in table_types
        assert "performance" in table_types
        assert requests_count > 0

    @pytest.mark.asyncio
    async def test_discover_dates(self):
        spider = HKJCRacingSpider()
        # Collect items from date discovery
        items = []
        requests_count = 0
        async for item in spider.stream():
            items.append(item)
            # Access stats inside the stream loop
            requests_count = spider.stats.requests_count
            # Limit collection for testing purposes
            if len(items) >= 10:
                break

        assert requests_count >= 1
