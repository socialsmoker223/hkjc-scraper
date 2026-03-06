"""HKJC Racing Spider - Proper Scrapling Spider implementation."""

import re
from scrapling.spiders import Spider, Request

from hkjc_scraper.data_parsers import (
    clean_position,
    parse_rating,
    parse_prize,
    parse_running_position,
    generate_race_id,
    parse_sectional_time_cell,
)
from hkjc_scraper.cache import DiscoveryCache
from hkjc_scraper.utils import generate_date_range, parse_race_date

from hkjc_scraper.horse_parsers import (
    parse_horse_profile as parse_horse_profile_data,
)
from hkjc_scraper.jockey_trainer_parsers import (
    parse_jockey_profile as parse_jockey_profile_data,
    parse_trainer_profile as parse_trainer_profile_data,
)

# Racecourse code to full name mapping
_RACECOURSE_NAMES = {
    "ST": "沙田",
    "HV": "谷草",
}


class HKJCRacingSpider(Spider):
    """Spider for crawling HKJC horse racing data using async pattern."""

    name = "hkjc_racing"
    BASE_URL = "https://racing.hkjc.com/zh-hk/local/information/localresults"
    concurrent_requests = 5

    def __init__(self, dates: list | None = None, racecourse: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.dates = dates
        self.racecourse = racecourse
        # Initialize deduplication sets
        self._seen_horses = set()
        self._seen_jockeys = set()
        self._seen_trainers = set()

    async def start_requests(self):
        if self.dates:
            for date in self.dates:
                racecourse = self.racecourse or "ST"
                url = f"{self.BASE_URL}?racedate={date}&Racecourse={racecourse}"
                yield Request(url, callback=self.parse_all_results, meta={"date": date, "racecourse": racecourse})
        else:
            yield Request(self.BASE_URL, callback=self.parse_discover_dates)

    async def parse_discover_dates(self, response):
        for opt in response.css("#selectId option"):
            date_val = opt.attrib.get("value")
            if date_val:
                racecourse = self.racecourse or "ST"
                url = f"{self.BASE_URL}?racedate={date_val}&Racecourse={racecourse}"
                yield response.follow(url, callback=self.parse_all_results, meta={"date": date_val, "racecourse": racecourse})

    async def parse_all_results(self, response):
        meta = response.meta
        date = meta.get("date", "")
        racecourse = meta.get("racecourse", "ST")
        for race_no in range(1, 12):
            url = f"{self.BASE_URL}?racedate={date}&Racecourse={racecourse}&RaceNo={race_no}"
            yield response.follow(url, callback=self.parse_race, meta={"date": date, "racecourse": racecourse, "race_no": race_no})

    async def parse_race(self, response):
        meta = response.meta
        date = meta.get("date", "")
        racecourse = meta.get("racecourse", "ST")
        race_no = meta.get("race_no", 1)
        race_data = self._parse_race_metadata(response, date, racecourse, race_no)
        yield {"table": "races", "data": race_data}
        race_id = race_data["race_id"]

        # Collect profile IDs and names during performance parsing
        horses = {}  # horse_id -> horse_name
        jockeys = {}  # jockey_id -> jockey_name
        trainers = {}  # trainer_id -> trainer_name

        # Parse performance table and collect IDs and names
        for perf_item in self._parse_performance_table(response, race_id):
            yield perf_item
            # Collect IDs and names
            data = perf_item.get("data", {})
            if data.get("horse_id") and data.get("horse_name"):
                horses[data["horse_id"]] = data["horse_name"]
            if data.get("jockey_id") and data.get("jockey"):
                jockeys[data["jockey_id"]] = data["jockey"]
            if data.get("trainer_id") and data.get("trainer"):
                trainers[data["trainer_id"]] = data["trainer"]

        # Parse dividends and incidents
        for div_item in self._parse_dividends(response, race_id):
            yield div_item
        for inc_item in self._parse_incidents(response, race_id):
            yield inc_item

        # Extract sectional time href and yield request
        sectional_href = None
        for link in response.css("a"):
            href = link.attrib.get("href", "")
            if "displaysectionaltime" in href:
                sectional_href = href
                break

        if sectional_href:
            url = response.urljoin(sectional_href)
            yield Request(url, callback=self.parse_sectional_times, meta={"race_id": race_id})
        else:
            self.logger.warning(f"No sectional time link found for race {race_id}")

        # Yield profile fetching requests directly
        # Fetch horse profiles
        for horse_id, horse_name in horses.items():
            if horse_id not in self._seen_horses:
                self._seen_horses.add(horse_id)
                url = f"https://racing.hkjc.com/zh-hk/local/information/horse?horseid={horse_id}"
                yield Request(url, callback=self.parse_horse_profile, meta={"horse_id": horse_id, "horse_name": horse_name})

        # Fetch jockey profiles
        for jockey_id, jockey_name in jockeys.items():
            if jockey_id not in self._seen_jockeys:
                self._seen_jockeys.add(jockey_id)
                # Note: HKJC uses uppercase 'Season' for jockey URLs
                url = f"https://racing.hkjc.com/zh-hk/local/information/jockeyprofile?jockeyid={jockey_id}&Season=Current"
                yield Request(url, callback=self.parse_jockey_profile, meta={"jockey_id": jockey_id, "jockey_name": jockey_name})

        # Fetch trainer profiles
        for trainer_id, trainer_name in trainers.items():
            if trainer_id not in self._seen_trainers:
                self._seen_trainers.add(trainer_id)
                # Note: HKJC uses lowercase 'season' for trainer URLs (site-specific parameter casing)
                url = f"https://racing.hkjc.com/zh-hk/local/information/trainerprofile?trainerid={trainer_id}&season=Current"
                yield Request(url, callback=self.parse_trainer_profile, meta={"trainer_id": trainer_id, "trainer_name": trainer_name})

    def _parse_race_metadata(self, response, date: str, racecourse: str, race_no: int) -> dict:
        """Extract race metadata from the race page response.

        Args:
            response: The HTTP response object
            date: Race date in YYYY/MM/DD format
            racecourse: Race course code (ST or HV)
            race_no: Race number

        Returns:
            Dictionary containing race metadata
        """
        # Generate unique race ID
        race_id = generate_race_id(date, racecourse, race_no)

        # Get full racecourse name
        racecourse_name = _RACECOURSE_NAMES.get(racecourse, racecourse)

        # Initialize result dict
        race_data = {
            "race_id": race_id,
            "race_date": date,
            "race_no": race_no,
            "racecourse": racecourse_name,
        }

        # Extract race info from the race table
        # The race info is typically in a table with class "race_tab" or similar
        race_tables = response.css(".race_tab table tbody tr")

        for row in race_tables:
            cells = row.css("td")
            if len(cells) < 2:
                continue

            # Get text from first cell (label) and second cell (value)
            # The pattern varies, so we need to handle multiple cases

            # Case 1: Class, Distance, Rating in one cell
            # Format: "第四班 - 1800米 - (60-40)"
            first_cell_text = cells[0].text if cells[0].text else ""

            # Extract class (第X班)
            class_match = re.search(r'第[一二三四五六七八九]班', first_cell_text)
            if class_match:
                race_data["class"] = class_match.group(0)

            # Extract distance (digits followed by 米)
            distance_match = re.search(r'(\d+)米', first_cell_text)
            if distance_match:
                race_data["distance"] = int(distance_match.group(1))

            # Extract rating ((high-low) or full-width version)
            # HKJC displays ratings as "(60-40)" where 60 is the higher rating
            # and 40 is the lower rating for horses eligible for this race
            rating_match = re.search(r'[(\uff08](\d+)-(\d+)[)\uff09]', first_cell_text)
            if rating_match:
                race_data["rating"] = {
                    "high": int(rating_match.group(1)),
                    "low": int(rating_match.group(2)),
                }

            # Case 2: Field label in second cell, value in third cell
            if len(cells) >= 2:
                label = cells[1].text if cells[1].text else ""
                value = cells[2].text if len(cells) > 2 and cells[2].text else ""

                if "場地狀況" in label:
                    race_data["going"] = value
                elif "賽道" in label and len(cells) > 2:
                    # Track info: "草地 - &quot;B+2&quot; 賽道"
                    track_text = cells[2].text if cells[2].text else ""
                    # Extract surface (草地 or 沙田)
                    if "草地" in track_text:
                        race_data["surface"] = "草地"
                    elif "沙田" in track_text or "全天候" in track_text:
                        race_data["surface"] = "全天候"
                    # Extract track info
                    race_data["track"] = track_text
                # Check for exact match "時間 :" (not "分段時間")
                elif label == "時間 :":
                    # Sectional times are in cells 3-7
                    sectional_times = []
                    for i in range(2, min(7, len(cells))):
                        cell_text = cells[i].text if cells[i].text else ""
                        if cell_text:
                            # Remove parentheses
                            time_text = cell_text.strip("()")
                            if time_text:
                                sectional_times.append(time_text)
                    if sectional_times:
                        race_data["sectional_times"] = sectional_times

        # Extract race name and prize money
        # The race name is typically in the first cell of a row,
        # and the prize money (HK$) is in the first cell of another row.
        # The race name row often has "賽道 :" in the second cell.
        for row in race_tables:
            cells = row.css("td")
            if len(cells) < 2:
                continue

            first_cell_text = cells[0].text if cells[0].text else ""
            second_cell_text = cells[1].text if len(cells) > 1 and cells[1].text else ""

            # Check if this is the prize money row (HK$ X,XXX,XXX)
            if "HK$" in first_cell_text or ("HK" in first_cell_text and "$" in first_cell_text):
                prize = parse_prize(first_cell_text)
                if prize > 0:
                    race_data["prize_money"] = prize

            # Check if this is the race name row (second cell is "賽道 :")
            elif "賽道" in second_cell_text and ":" in second_cell_text:
                # First cell should be the race name
                if first_cell_text and len(first_cell_text) > 3:
                    race_data["race_name"] = first_cell_text

        return race_data

    def _validate_performance_item(self, item: dict) -> bool:
        """Validate that a performance item has required fields.

        Args:
            item: Dictionary containing performance data

        Returns:
            True if item has all required fields with non-empty values
        """
        required_fields = ["race_id", "horse_no"]
        return all(item.get(field) for field in required_fields)

    def _parse_performance_table(self, response, race_id: str):
        """Extract performance (horse results) table.

        Args:
            response: The HTTP response object
            race_id: Unique race identifier

        Yields:
            Dictionaries with "table": "performance" and horse performance data
        """
        results_table = response.css("table.draggable")
        if not results_table:
            return
        rows = results_table[0].css("tbody tr")
        for row in rows:
            cells = row.css("td")
            if len(cells) >= 12:
                try:
                    horse_link = cells[2].css("a")
                    horse_name = ""
                    horse_id = None
                    if horse_link:
                        horse_name = horse_link[0].text.strip()
                        href = horse_link[0].attrib.get("href", "")
                        if "horseid=" in href:
                            horse_id = href.split("horseid=")[1].split("&")[0]
                    jockey_link = cells[3].css("a")
                    jockey = jockey_link[0].text.strip() if jockey_link else ""
                    jockey_id = None
                    if jockey_link:
                        href = jockey_link[0].attrib.get("href", "")
                        if "jockeyid=" in href:
                            jockey_id = href.split("jockeyid=")[1].split("&")[0]
                    trainer_link = cells[4].css("a")
                    trainer = trainer_link[0].text.strip() if trainer_link else ""
                    trainer_id = None
                    if trainer_link:
                        href = trainer_link[0].attrib.get("href", "")
                        if "trainerid=" in href:
                            trainer_id = href.split("trainerid=")[1].split("&")[0]
                    pos_text = cells[0].text.strip()
                    position = clean_position(pos_text) if pos_text else ""
                    running_pos = parse_running_position(cells[9])
                    performance = {
                        "race_id": race_id,
                        "position": position,
                        "horse_no": cells[1].text.strip(),
                        "horse_id": horse_id,
                        "horse_name": horse_name,
                        "jockey": jockey,
                        "jockey_id": jockey_id,
                        "trainer": trainer,
                        "trainer_id": trainer_id,
                        "actual_weight": cells[5].text.strip(),
                        "body_weight": cells[6].text.strip(),
                        "draw": cells[7].text.strip(),
                        "margin": cells[8].text.strip(),
                        "running_position": running_pos,
                        "finish_time": cells[10].text.strip(),
                        "win_odds": cells[11].text.strip()
                    }
                    if self._validate_performance_item(performance):
                        yield {"table": "performance", "data": performance}
                except Exception:
                    continue

    def _parse_dividends(self, response, race_id: str):
        """Extract dividends table.

        Args:
            response: The HTTP response object
            race_id: Unique race identifier

        Yields:
            Dictionaries with "table": "dividends" and dividend data
        """
        for table in response.css("table.table_bd"):
            header = table.css("thead tr td")
            if header and "派彩" in header[0].text:
                current_pool = None
                for row in table.css("tbody tr"):
                    cells = row.css("td")
                    # Handle rows with 3 cells (has pool name) or 2 cells (rowspan continuation)
                    if len(cells) >= 2:
                        if len(cells) >= 3:
                            first_cell = cells[0].text.strip()
                            if first_cell:
                                current_pool = first_cell
                            elif current_pool is None:
                                continue  # Skip rows with no pool context
                            winning_combination = cells[1].text.strip()
                            payout = cells[2].text.strip()
                        else:
                            # Row has only 2 cells (first cell is rowspan from above)
                            if current_pool is None:
                                continue  # Skip rows with no pool context
                            winning_combination = cells[0].text.strip()
                            payout = cells[1].text.strip()
                        dividend = {
                            "race_id": race_id,
                            "pool": current_pool,
                            "winning_combination": winning_combination,
                            "payout": payout
                        }
                        yield {"table": "dividends", "data": dividend}

    def _parse_incidents(self, response, race_id: str):
        """Extract incidents table.

        Args:
            response: The HTTP response object
            race_id: Unique race identifier

        Yields:
            Dictionaries with "table": "incidents" and incident data
        """
        for table in response.css("table.table_bd"):
            header = table.css("thead tr td")
            if header and any("競賽事件" in h.text for h in header):
                for row in table.css("tbody tr"):
                    cells = row.css("td")
                    if len(cells) >= 4:
                        horse_link = cells[2].css("a")
                        horse_name = horse_link[0].text.strip() if horse_link else ""
                        incident = {
                            "race_id": race_id,
                            "position": cells[0].text.strip(),
                            "horse_no": cells[1].text.strip(),
                            "horse_name": horse_name,
                            "incident_report": cells[3].text.strip()
                        }
                        yield {"table": "incidents", "data": incident}

    async def parse(self, response):
        """Default parse method required by Spider base class."""
        yield  # Make this a generator for type checkers

    async def parse_horse_profile(self, response):
        """Parse horse profile page and yield horse data."""
        meta = response.meta
        horse_id = meta.get("horse_id")
        horse_name = meta.get("horse_name", "")

        profile_data = parse_horse_profile_data(response, horse_id, horse_name)
        profile_data["horse_id"] = horse_id
        yield {"table": "horses", "data": profile_data}

    async def parse_jockey_profile(self, response):
        """Parse jockey profile page and yield jockey data."""
        meta = response.meta
        jockey_id = meta.get("jockey_id")
        jockey_name = meta.get("jockey_name", "")

        profile_data = parse_jockey_profile_data(response, jockey_id, jockey_name)
        profile_data["jockey_id"] = jockey_id
        yield {"table": "jockeys", "data": profile_data}

    async def parse_sectional_times(self, response):
        """Parse sectional time page and yield per-horse, per-section records.

        Yields:
            {"table": "sectional_times", "data": {...}}
        """
        race_id = response.meta.get("race_id")

        # Check for "沒有相關資料" or similar empty state
        page_text = response.get_all_text()
        if "沒有相關資料" in page_text or "不提供" in page_text:
            self.logger.warning(f"No sectional time data available for race {race_id}")
            return

        # Find the main sectional table
        # The table has rows with horse data, skip header rows
        if "分段時間" not in page_text:
            self.logger.warning(f"No sectional table found for race {race_id}")
            return

        # Get all table rows
        rows = response.css("table tbody tr")
        if not rows:
            self.logger.warning(f"No sectional table found for race {race_id}")
            return

        # Process data rows (skip headers)
        for row in rows:
            cells = row.css("td")
            if len(cells) < 5:
                continue

            # First cell should be finishing position (number)
            # Check for empty string before accessing first character
            first_cell = cells[0].text
            if not first_cell or not first_cell[0].isdigit():
                continue

            # Second cell is horse_no
            horse_no = cells[1].text.strip()
            if not horse_no or not horse_no.isdigit():
                continue

            # Parse each section column (starts at index 3, skip last cell which is finish time)
            section_num = 1
            for cell in cells[3:-1]:
                # Extract position and margin from the f_clear paragraph
                f_clear = cell.css("p.f_clear")
                if not f_clear:
                    # Empty cell (blank image), skip but count section
                    section_num += 1
                    continue

                # Position is in span.f_fl
                position_span = f_clear[0].css("span.f_fl")
                if not position_span:
                    section_num += 1
                    continue
                position_text = position_span[0].text.strip()
                if not position_text.isdigit():
                    section_num += 1
                    continue

                # Margin is in <i> tag
                margin_i = f_clear[0].css("i")
                margin = margin_i[0].text.strip() if margin_i else ""

                # Time is in p.sectional_200, just the first value
                sectional_p = cell.css("p.sectional_200")
                time = None
                if sectional_p:
                    time_text = sectional_p[0].text.strip().split()[0] if sectional_p[0].text else None
                    if time_text:
                        try:
                            time = float(time_text)
                        except ValueError:
                            pass

                if time is not None:
                    yield {
                        "table": "sectional_times",
                        "data": {
                            "race_id": race_id,
                            "horse_no": horse_no,
                            "section_number": section_num,
                            "position": int(position_text),
                            "margin": margin,
                            "time": time,
                        }
                    }

                section_num += 1

    async def parse_trainer_profile(self, response):
        """Parse trainer profile page and yield trainer data."""
        meta = response.meta
        trainer_id = meta.get("trainer_id")
        trainer_name = meta.get("trainer_name", "")

        profile_data = parse_trainer_profile_data(response, trainer_id, trainer_name)
        profile_data["trainer_id"] = trainer_id
        yield {"table": "trainers", "data": profile_data}

    async def run(self):
        """Run the spider and collect all results.

        Returns:
            A result object with items and stats attributes.
        """
        items = []
        stats = None
        async for item in self.stream():
            items.append(item)
            # Capture stats during the crawl
            stats = self.stats

        class Result:
            def __init__(self, items, stats):
                self.items = items
                self.stats = stats

        return Result(items, stats)

    async def discover_dates(
        self,
        start_date: str,
        end_date: str,
        refresh_cache: bool = False,
    ) -> list[dict]:
        """Discover valid race dates in the given range.

        Args:
            start_date: Start date in YYYY/MM/DD format
            end_date: End date in YYYY/MM/DD format
            refresh_cache: If True, re-verify cached dates

        Returns:
            List of dicts with keys: date, racecourse, race_count
        """
        cache = DiscoveryCache()
        cache.load()

        discovered = []
        racecourses = ["ST", "HV"]
        check_count = 0
        save_interval = 50

        async def check_date(date: str, racecourse: str) -> dict | None:
            """Check if a date + racecourse has valid races."""
            # Check cache first unless refreshing
            if not refresh_cache and cache.is_cached(date, racecourse):
                return None

            # Skip August (season break)
            if cache.is_season_break(date):
                cache.mark_season_break(date[:7])  # YYYY-MM format
                return None

            url = f"{self.BASE_URL}?racedate={date}&Racecourse={racecourse}"
            try:
                response = await self.fetch(url)

                if response and self._is_valid_race_page(response):
                    race_count = self._count_races(response)
                    cache.add_discovery(date, racecourse, race_count)

                    return {
                        "date": date,
                        "racecourse": racecourse,
                        "race_count": race_count
                    }
            except Exception as e:
                self.logger.warning(f"Error checking {date} {racecourse}: {e}")

            return None

        # Check each date + racecourse combination
        for date in generate_date_range(start_date, end_date):
            for racecourse in racecourses:
                result = await check_date(date, racecourse)
                if result:
                    discovered.append(result)

                # Periodic cache save
                check_count += 1
                if check_count % save_interval == 0:
                    cache.save()

        cache.save()
        return discovered

    def _is_valid_race_page(self, response) -> bool:
        """Check if response contains valid race data.

        Args:
            response: Scrapling response object

        Returns:
            True if page has valid race data, False otherwise
        """
        # Check for common indicators of no data
        text = response.text

        # No data indicators
        no_data_patterns = [
            "沒有赛事",  # No races (Chinese)
            "沒有賽事",
            "No races",
            "暫沒有賽事",  # No races at the moment
        ]

        for pattern in no_data_patterns:
            if pattern in text:
                return False

        # Check for race number selector or links
        # Valid pages have race number options or links
        if response.css("#selectId option"):
            return True

        if response.css('a[href*="RaceNo="]'):
            return True

        return False

    def _count_races(self, response) -> int:
        """Count the number of races on the page.

        Args:
            response: Scrapling response object

        Returns:
            Number of races (1-11)
        """
        # Try to count from dropdown options
        options = response.css("#selectId option")
        if options:
            return len(options)

        # Alternative: count race number links
        race_links = response.css('a[href*="RaceNo="]')
        if race_links:
            # Extract unique race numbers
            race_numbers = set()
            for link in race_links:
                href = link.attrib.get("href", "")
                # Extract RaceNo=XX from href
                if "RaceNo=" in href:
                    match = re.search(r'RaceNo=(\d+)', href)
                    if match:
                        race_numbers.add(int(match.group(1)))

            return len(race_numbers) if race_numbers else 1

        return 1  # Default to at least 1 race
