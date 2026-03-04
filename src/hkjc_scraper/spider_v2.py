"""HKJC Racing Spider - Proper Scrapling Spider implementation."""

from scrapling.spiders import Spider


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
        yield {"table": "races", "data": {}}

    async def parse(self, response):
        """Default parse method required by Spider base class."""
        yield  # Make this a generator for type checkers
