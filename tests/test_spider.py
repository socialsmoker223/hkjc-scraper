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
        assert race_data["rating"] == {"high": 60, "low": 40}

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

    @pytest.mark.asyncio
    async def test_parse_race_full_racecourse_name_hv(self, sample_race_response):
        spider = HKJCRacingSpider()
        items = []

        async def collect_items():
            async for item in spider.parse_race(sample_race_response):
                items.append(item)

        # Test HV (Happy Valley)
        sample_race_response.meta = {
            "date": "2026/03/01",
            "racecourse": "HV",
            "race_no": 1
        }

        await collect_items()
        race_items = [i for i in items if i.get("table") == "races"]
        race_data = race_items[0]["data"]

        assert "racecourse" in race_data
        assert race_data["racecourse"] == "谷草"


class TestPerformanceParser:
    """Test performance (horse results) table parsing."""

    @pytest.mark.asyncio
    async def test_parse_race_yields_performance_items(self, sample_race_response):
        spider = HKJCRacingSpider()
        items = []
        async def collect_items():
            async for item in spider.parse_race(sample_race_response):
                items.append(item)
        await collect_items()
        perf_items = [i for i in items if i.get("table") == "performance"]
        assert len(perf_items) > 0
        perf_data = perf_items[0]["data"]
        assert "horse_no" in perf_data
        assert "horse_name" in perf_data
        assert "position" in perf_data

    @pytest.mark.asyncio
    async def test_parse_performance_extracts_horse_details(self, sample_race_response):
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
        perf_items = [i for i in items if i.get("table") == "performance"]
        assert len(perf_items) > 0

        # Check first horse (winner: 步風雷)
        winner = perf_items[0]["data"]
        assert winner["horse_no"] == "9"
        assert winner["horse_name"] == "步風雷"
        assert winner["horse_id"] == "HK_2023_J452"
        assert winner["position"] == "1"
        assert winner["jockey"] == "艾兆禮"
        assert winner["trainer"] == "伍鵬志"
        assert winner["actual_weight"] == "120"
        assert winner["body_weight"] == "1060"
        assert winner["draw"] == "5"
        assert winner["margin"] == "-"
        assert winner["finish_time"] == "1:47.33"
        assert winner["win_odds"] == "10"
        assert winner["race_id"] == "2026-03-01-ST-1"

    @pytest.mark.asyncio
    async def test_parse_performance_extracts_running_position(self, sample_race_response):
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
        perf_items = [i for i in items if i.get("table") == "performance"]
        assert len(perf_items) > 0

        # Check running position for winner (步風雷)
        winner = perf_items[0]["data"]
        assert "running_position" in winner
        assert winner["running_position"] == ["4", "4", "4", "3", "1"]

    @pytest.mark.asyncio
    async def test_parse_performance_multiple_horses(self, sample_race_response):
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
        perf_items = [i for i in items if i.get("table") == "performance"]

        # Should have multiple horses
        assert len(perf_items) >= 14  # 14 horses in the sample race

        # Check second place
        second_place = perf_items[1]["data"]
        assert second_place["position"] == "2"
        assert second_place["horse_name"] == "同益善"
        assert second_place["horse_no"] == "7"
        assert second_place["margin"] == "3/4"


class TestDividendsParser:
    """Test dividends table parsing."""

    @pytest.mark.asyncio
    async def test_parse_race_yields_dividends(self, sample_race_response):
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
        div_items = [i for i in items if i.get("table") == "dividends"]
        assert len(div_items) > 0
        div_data = div_items[0]["data"]
        assert "pool" in div_data
        assert "winning_combination" in div_data

    @pytest.mark.asyncio
    async def test_parse_dividends_rowspan_handling(self, sample_race_response):
        """Test that rowspan entries for '位置' pool are handled correctly."""
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
        div_items = [i for i in items if i.get("table") == "dividends"]

        # Filter for "位置" (Place) pool entries
        place_dividends = [d for d in div_items if d["data"]["pool"] == "位置"]

        # Should have 3 entries for "位置" (rowspan=3)
        assert len(place_dividends) == 3

    @pytest.mark.asyncio
    async def test_parse_dividends_specific_pool_values(self, sample_race_response):
        """Test that specific dividend values are extracted correctly."""
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
        div_items = [i for i in items if i.get("table") == "dividends"]

        # Check 獨贏 (Win) pool
        win_dividends = [d for d in div_items if d["data"]["pool"] == "獨贏"]
        assert len(win_dividends) == 1
        assert win_dividends[0]["data"]["winning_combination"] == "9"
        assert win_dividends[0]["data"]["payout"] == "108.00"

        # Check first 位置 (Place) entry
        place_dividends = [d for d in div_items if d["data"]["pool"] == "位置"]
        assert place_dividends[0]["data"]["winning_combination"] == "9"
        assert place_dividends[0]["data"]["payout"] == "32.00"

    @pytest.mark.asyncio
    async def test_parse_dividends_all_pools_exist(self, sample_race_response):
        """Test that all expected dividend pools are parsed."""
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
        div_items = [i for i in items if i.get("table") == "dividends"]

        # Extract unique pool names
        pools = set(d["data"]["pool"] for d in div_items)

        # Verify key pools exist
        assert "獨贏" in pools
        assert "位置" in pools
        assert "連贏" in pools


class TestIncidentsParser:
    """Test incidents table parsing."""

    @pytest.mark.asyncio
    async def test_parse_race_yields_incidents(self, sample_race_response):
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
        inc_items = [i for i in items if i.get("table") == "incidents"]
        # Don't assert count - incidents may not exist in all races
        if inc_items:
            inc_data = inc_items[0]["data"]
            assert "incident_report" in inc_data


class TestErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_parse_race_handles_missing_tables(self):
        """Test that parse_race handles pages with no data tables gracefully."""
        empty_html = "<html><body>No tables</body></html>"

        class EmptyResponse:
            def __init__(self):
                self.text = empty_html
                self.meta = {"date": "2026/03/01", "racecourse": "ST", "race_no": 1}

            def css(self, selector):
                return []

        spider = HKJCRacingSpider()
        response = EmptyResponse()
        items = []

        async def collect_items():
            async for item in spider.parse_race(response):
                items.append(item)

        await collect_items()
        # Should still yield the races table with metadata even if no other tables exist
        assert len(items) >= 1
        assert items[0]["table"] == "races"

    def test_clean_position_handles_empty(self):
        """Test that clean_position handles empty and None values."""
        from hkjc_scraper.parsers import clean_position
        assert clean_position("") == ""
        assert clean_position(None) == ""
        assert clean_position(" ") == ""
