"""Tests for HKJCRacingSpider."""
import pytest
from scrapling.spiders import Spider
from hkjc_scraper.spider_v2 import HKJCRacingSpider


class TestSpiderClass:
    """Test Spider class configuration."""

    def test_spider_is_spider_subclass(self):
        assert issubclass(HKJCRacingSpider, Spider)

    def test_spider_has_name(self):
        assert HKJCRacingSpider.name == "hkjc_racing"

    def test_spider_has_base_url(self):
        spider = HKJCRacingSpider()
        assert spider.BASE_URL == "https://racing.hkjc.com/zh-hk/local/information/localresults"

    def test_spider_has_concurrent_requests(self):
        spider = HKJCRacingSpider()
        assert spider.concurrent_requests == 5


class TestRaceMetadataParser:
    """Test race metadata extraction."""

    def test_parse_race_id(self):
        from hkjc_scraper.parsers import generate_race_id
        assert generate_race_id("2026/03/01", "ST", 1) == "2026-03-01-ST-1"
        assert generate_race_id("2026/03/01", "HV", 5) == "2026-03-01-HV-5"
        # Test with already normalized date
        assert generate_race_id("2026-03-01", "ST", 1) == "2026-03-01-ST-1"

    @pytest.mark.asyncio
    async def test_parse_race_extracts_metadata(self, sample_race_response):
        spider = HKJCRacingSpider()
        items = []

        async def collect_items():
            async for item in spider.parse_race(sample_race_response):
                items.append(item)

        # Set the required meta attributes
        sample_race_response.meta = {
            "date": "2026/03/01",
            "racecourse": "ST",
            "race_no": 1
        }

        await collect_items()
        race_items = [i for i in items if i.get("table") == "races"]
        assert len(race_items) > 0
        race_data = race_items[0]["data"]
        assert "race_id" in race_data
        assert "race_date" in race_data
        assert "race_no" in race_data
        assert race_data["race_id"] == "2026-03-01-ST-1"
        assert race_data["race_no"] == 1

    @pytest.mark.asyncio
    async def test_parse_race_extracts_class_and_distance(self, sample_race_response):
        spider = HKJCRacingSpider()
        items = []

        async def collect_items():
            async for item in spider.parse_race(sample_race_response):
                items.append(item)

        sample_race_response.meta = {
            "date": "2026/03/01",
            "racecourse": "ST",
            "race_no": 1
        }

        await collect_items()
        race_items = [i for i in items if i.get("table") == "races"]
        race_data = race_items[0]["data"]

        # Check class parsing
        assert "class" in race_data
        assert race_data["class"] == "第四班"

        # Check distance parsing
        assert "distance" in race_data
        assert race_data["distance"] == 1800

        # Check rating parsing
        assert "rating" in race_data
        assert race_data["rating"] == {"min": 60, "max": 40}

    @pytest.mark.asyncio
    async def test_parse_race_extracts_track_info(self, sample_race_response):
        spider = HKJCRacingSpider()
        items = []

        async def collect_items():
            async for item in spider.parse_race(sample_race_response):
                items.append(item)

        sample_race_response.meta = {
            "date": "2026/03/01",
            "racecourse": "ST",
            "race_no": 1
        }

        await collect_items()
        race_items = [i for i in items if i.get("table") == "races"]
        race_data = race_items[0]["data"]

        # Check going (track condition)
        assert "going" in race_data
        assert race_data["going"] == "好地"

        # Check surface
        assert "surface" in race_data
        assert race_data["surface"] == "草地"

        # Check track (full text including surface and track designation)
        assert "track" in race_data
        assert "B+2" in race_data["track"]
        assert "賽道" in race_data["track"]

    @pytest.mark.asyncio
    async def test_parse_race_extracts_prize_and_name(self, sample_race_response):
        spider = HKJCRacingSpider()
        items = []

        async def collect_items():
            async for item in spider.parse_race(sample_race_response):
                items.append(item)

        sample_race_response.meta = {
            "date": "2026/03/01",
            "racecourse": "ST",
            "race_no": 1
        }

        await collect_items()
        race_items = [i for i in items if i.get("table") == "races"]
        race_data = race_items[0]["data"]

        # Check race name
        assert "race_name" in race_data
        assert race_data["race_name"] == "花旗銀行CITI WEALTH讓賽"

        # Check prize money
        assert "prize_money" in race_data
        assert race_data["prize_money"] == 1170000

    @pytest.mark.asyncio
    async def test_parse_race_extracts_sectional_times(self, sample_race_response):
        spider = HKJCRacingSpider()
        items = []

        async def collect_items():
            async for item in spider.parse_race(sample_race_response):
                items.append(item)

        sample_race_response.meta = {
            "date": "2026/03/01",
            "racecourse": "ST",
            "race_no": 1
        }

        await collect_items()
        race_items = [i for i in items if i.get("table") == "races"]
        race_data = race_items[0]["data"]

        # Check sectional times
        assert "sectional_times" in race_data
        expected_times = ["13.88", "36.08", "59.71", "1:23.74", "1:47.33"]
        assert race_data["sectional_times"] == expected_times

    @pytest.mark.asyncio
    async def test_parse_race_full_racecourse_name(self, sample_race_response):
        spider = HKJCRacingSpider()
        items = []

        async def collect_items():
            async for item in spider.parse_race(sample_race_response):
                items.append(item)

        # Test ST (Sha Tin)
        sample_race_response.meta = {
            "date": "2026/03/01",
            "racecourse": "ST",
            "race_no": 1
        }

        await collect_items()
        race_items = [i for i in items if i.get("table") == "races"]
        race_data = race_items[0]["data"]

        assert "racecourse" in race_data
        assert race_data["racecourse"] == "沙田"
