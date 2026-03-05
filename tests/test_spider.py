"""Tests for HKJCRacingSpider."""
import pytest
from scrapling.spiders import Spider
from hkjc_scraper.spider import HKJCRacingSpider


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
        race_items = [i for i in items if isinstance(i, dict) and i.get("table") == "races"]
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
        race_items = [i for i in items if isinstance(i, dict) and i.get("table") == "races"]
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
        race_items = [i for i in items if isinstance(i, dict) and i.get("table") == "races"]
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
        race_items = [i for i in items if isinstance(i, dict) and i.get("table") == "races"]
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
        race_items = [i for i in items if isinstance(i, dict) and i.get("table") == "races"]
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
        race_items = [i for i in items if isinstance(i, dict) and i.get("table") == "races"]
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
        race_items = [i for i in items if isinstance(i, dict) and i.get("table") == "races"]
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
        perf_items = [i for i in items if isinstance(i, dict) and i.get("table") == "performance"]
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
        perf_items = [i for i in items if isinstance(i, dict) and i.get("table") == "performance"]
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
        perf_items = [i for i in items if isinstance(i, dict) and i.get("table") == "performance"]
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
        perf_items = [i for i in items if isinstance(i, dict) and i.get("table") == "performance"]

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
        div_items = [i for i in items if isinstance(i, dict) and i.get("table") == "dividends"]
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
        div_items = [i for i in items if isinstance(i, dict) and i.get("table") == "dividends"]

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
        div_items = [i for i in items if isinstance(i, dict) and i.get("table") == "dividends"]

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
        div_items = [i for i in items if isinstance(i, dict) and i.get("table") == "dividends"]

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
        inc_items = [i for i in items if isinstance(i, dict) and i.get("table") == "incidents"]
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
        from scrapling.spiders import Request

        class EmptyResponse:
            def __init__(self):
                self.text = empty_html
                self.meta = {"date": "2026/03/01", "racecourse": "ST", "race_no": 1}

            def css(self, selector):
                return []

            def follow(self, url, callback=None, meta=None):
                """Mock follow method that returns a Request object."""
                req = Request(url)
                req.callback = callback
                req.meta = meta or {}
                return req

        spider = HKJCRacingSpider()
        response = EmptyResponse()
        items = []

        async def collect_items():
            async for item in spider.parse_race(response):
                items.append(item)

        await collect_items()
        # Should still yield the races table with metadata even if no other tables exist
        # Filter for dict items only (excluding Request objects)
        data_items = [i for i in items if isinstance(i, dict)]
        assert len(data_items) >= 1
        assert data_items[0]["table"] == "races"

    def test_clean_position_handles_empty(self):
        """Test that clean_position handles empty and None values."""
        from hkjc_scraper.parsers import clean_position
        assert clean_position("") == ""
        assert clean_position(None) == ""
        assert clean_position(" ") == ""


class TestDeduplicationSets:
    """Test deduplication set initialization."""

    def test_spider_has_deduplication_sets(self):
        """Test that spider initializes deduplication sets."""
        spider = HKJCRacingSpider()
        assert hasattr(spider, "_seen_horses")
        assert hasattr(spider, "_seen_jockeys")
        assert hasattr(spider, "_seen_trainers")
        assert isinstance(spider._seen_horses, set)
        assert isinstance(spider._seen_jockeys, set)
        assert isinstance(spider._seen_trainers, set)


class TestPerformanceIdsExtraction:
    """Test jockey_id and trainer_id extraction from performance table."""

    def test_performance_extraction_includes_ids(self):
        """Test that performance items include jockey_id and trainer_id."""
        from bs4 import BeautifulSoup

        html = """
        <table class="draggable">
            <tbody>
                <tr>
                    <td>1</td>
                    <td>7</td>
                    <td><a href="/zh-hk/local/information/horse?horseid=HK_2024_K306">堅多福</a></td>
                    <td><a href="/zh-hk/local/information/jockeyprofile?jockeyid=BH&Season=Current">布文</a></td>
                    <td><a href="/zh-hk/local/information/trainerprofile?trainerid=FC&season=Current">方嘉柏</a></td>
                    <td>120</td>
                    <td>1050</td>
                    <td>3</td>
                    <td></td>
                    <td><div><div>1</div><div>2</div></div></td>
                    <td>1:49.35</td>
                    <td>12.5</td>
                </tr>
            </tbody>
        </table>
        """

        class MockResponse:
            def __init__(self, html):
                self.html = html

            def css(self, selector):
                soup = BeautifulSoup(self.html, "html.parser")
                results = soup.select(selector)
                return [self._element_to_mock(e) for e in results]

            def _element_to_mock(self, elem):
                class MockElem:
                    def __init__(self, el):
                        self._el = el
                        self.text = el.get_text(strip=True)
                        self.attrib = {"href": el.get("href", "")}

                    def css(self, selector):
                        return [MockElem(e) for e in self._el.select(selector)]

                return MockElem(elem)

        response = MockResponse(html)

        spider = HKJCRacingSpider()
        results = list(spider._parse_performance_table(response, "test-race-id"))

        assert len(results) == 1
        assert results[0]["data"]["jockey_id"] == "BH"
        assert results[0]["data"]["trainer_id"] == "FC"


class TestParseRaceCollectsProfileIds:
    """Test that parse_race collects profile IDs and yields profile fetch requests."""

    @pytest.mark.asyncio
    async def test_parse_race_collects_profile_ids(self):
        """Test that parse_race collects profile IDs and yields profile fetch requests."""
        from bs4 import BeautifulSoup
        from scrapling.spiders import Request

        spider = HKJCRacingSpider()

        # Minimal race HTML with profile links
        html = """
        <div>
            <table class="draggable">
                <tbody>
                    <tr>
                        <td>1</td>
                        <td>7</td>
                        <td><a href="/zh-hk/local/information/horse?horseid=HK_2024_K306">堅多福</a></td>
                        <td><a href="/zh-hk/local/information/jockeyprofile?jockeyid=BH&Season=Current">布文</a></td>
                        <td><a href="/zh-hk/local/information/trainerprofile?trainerid=FC&season=Current">方嘉柏</a></td>
                        <td>120</td>
                        <td>1050</td>
                        <td>3</td>
                        <td></td>
                        <td><div><div>1</div><div>2</div></div></td>
                        <td>1:49.35</td>
                        <td>12.5</td>
                    </tr>
                </tbody>
            </table>
        </div>
        """

        class MockResponse:
            def __init__(self, html):
                self.html = html
                self.meta = {}

            def css(self, selector):
                soup = BeautifulSoup(self.html, "html.parser")
                results = soup.select(selector)
                return [self._element_to_mock(e) for e in results]

            def _element_to_mock(self, elem):
                class MockElem:
                    def __init__(self, el):
                        self._el = el
                        self.text = el.get_text(strip=True)
                        self.attrib = {"href": el.get("href", "")}

                    def css(self, selector):
                        return [MockElem(e) for e in self._el.select(selector)]

                return MockElem(elem)

            def follow(self, url, callback, meta=None):
                req = Request(url, callback=callback)
                req.meta = meta or {}
                return req

        response = MockResponse(html)
        response.meta = {"date": "2026/03/04", "racecourse": "HV", "race_no": 1}

        results = []
        async for item in spider.parse_race(response):
            results.append(item)

        # Should have: races, performance, and 3 profile requests
        assert len(results) >= 5

        # Check we have the expected data items
        tables = [r["table"] for r in results if isinstance(r, dict) and "table" in r]
        assert "races" in tables
        assert "performance" in tables

        # Find the profile requests
        profile_requests = [r for r in results if hasattr(r, 'url') or hasattr(r, 'callback')]
        assert len(profile_requests) == 3

        # Verify we have one request for each profile type
        urls = [r.url for r in profile_requests]
        assert any("horseid=HK_2024_K306" in u for u in urls)
        assert any("jockeyid=BH" in u for u in urls)
        assert any("trainerid=FC" in u for u in urls)

        # Verify IDs are in seen sets
        assert "HK_2024_K306" in spider._seen_horses
        assert "BH" in spider._seen_jockeys
        assert "FC" in spider._seen_trainers


class TestSectionalHrefExtraction:
    """Test sectional time href extraction and request yielding."""

    def test_extract_sectional_href_from_links(self):
        """Test that we can extract sectional href from anchor tags."""
        from bs4 import BeautifulSoup

        html = """
        <div>
            <a href="/other/link">Other</a>
            <a href="/zh-hk/local/information/displaysectionaltime?racedate=01/03/2026&RaceNo=1">Sectional</a>
            <a href="/another/link">Another</a>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        links = soup.find_all("a")

        sectional_href = None
        for link in links:
            href = link.get("href", "")
            if "displaysectionaltime" in href:
                sectional_href = href
                break

        assert sectional_href == "/zh-hk/local/information/displaysectionaltime?racedate=01/03/2026&RaceNo=1"

    @pytest.mark.asyncio
    async def test_parse_race_yields_sectional_request(self, sample_race_response):
        """Test that parse_race yields a sectional time request."""
        from scrapling.spiders import Request

        spider = HKJCRacingSpider()

        sample_race_response.meta = {
            "date": "2026/03/01",
            "racecourse": "ST",
            "race_no": 1
        }

        results = []
        async for item in spider.parse_race(sample_race_response):
            results.append(item)

        # Find the sectional request
        sectional_requests = []
        for item in results:
            if hasattr(item, 'url') and 'displaysectionaltime' in item.url:
                sectional_requests.append(item)

        assert len(sectional_requests) == 1, f"Expected 1 sectional request, got {len(sectional_requests)}"
        sectional_req = sectional_requests[0]

        # Verify the URL is correctly constructed
        assert "displaysectionaltime" in sectional_req.url
        assert "racedate=01/03/2026" in sectional_req.url
        assert "RaceNo=1" in sectional_req.url

        # Verify meta includes race_id
        assert sectional_req.meta.get("race_id") == "2026-03-01-ST-1"

        # Verify callback is set
        assert sectional_req.callback is not None
        assert sectional_req.callback.__name__ == "parse_sectional_times"


class TestProfileParsers:
    """Test profile parser callback methods."""

    @pytest.mark.asyncio
    async def test_parse_horse_profile_yields_correct_table(self):
        """Test that parse_horse_profile yields horses table."""
        from bs4 import BeautifulSoup

        class MockResponse:
            def __init__(self, html):
                self.html = html
                self.meta = {}

            @property
            def text(self):
                return self.html

            def css(self, selector):
                soup = BeautifulSoup(self.html, "html.parser")
                results = soup.select(selector)
                return [self._element_to_mock(e) for e in results]

            def _element_to_mock(self, elem):
                class MockElem:
                    def __init__(self, el):
                        self._el = el
                        self.text = el.get_text(strip=True)
                        self.attrib = {"href": el.get("href", "")}

                    def css(self, selector):
                        return [MockElem(e) for e in self._el.select(selector)]

                return MockElem(elem)

        spider = HKJCRacingSpider()
        spider._seen_horses.add("HK_2024_K306")

        html = '<div><table><tr><td>父系 :</td><td>Tivaci</td></tr></table></div>'
        response = MockResponse(html)
        response.meta = {"horse_id": "HK_2024_K306", "horse_name": "堅多福"}

        items = []

        async def collect_items():
            async for item in spider.parse_horse_profile(response):
                items.append(item)

        await collect_items()
        assert len(items) == 1
        assert items[0]["table"] == "horses"
        assert items[0]["data"]["horse_id"] == "HK_2024_K306"
