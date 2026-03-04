"""HKJC Racing Spider - Proper Scrapling Spider implementation."""

import re
from scrapling.spiders import Spider

from hkjc_scraper.parsers import (
    clean_position,
    parse_rating,
    parse_prize,
    parse_running_position,
    generate_race_id,
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

    def start_requests(self):
        if self.dates:
            for date in self.dates:
                racecourse = self.racecourse or "ST"
                url = f"{self.BASE_URL}?racedate={date}&Racecourse={racecourse}"
                yield self.fetch(url, callback=self.parse_all_results, meta={"date": date, "racecourse": racecourse})
        else:
            yield self.fetch(self.BASE_URL, callback=self.parse_discover_dates)

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

    async def parse(self, response):
        """Default parse method required by Spider base class."""
        yield  # Make this a generator for type checkers
