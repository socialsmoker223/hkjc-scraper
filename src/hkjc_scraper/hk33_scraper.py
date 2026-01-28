"""
HK33.com scraper for historical odds and offshore market data
HK33.com 歷史賠率及海外市場數據爬蟲
"""

import decimal
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytz
from bs4 import BeautifulSoup

from hkjc_scraper import config
from hkjc_scraper.exceptions import ParseError
from hkjc_scraper.http_utils import HTTPSession, rate_limited, retry_on_network_error

logger = logging.getLogger(__name__)

# Hong Kong timezone
HKT = pytz.timezone("Asia/Hong_Kong")

# Pre-compiled regex patterns for performance
_FULL_TIMESTAMP_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
_TIME_ONLY_PATTERN = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")

# Cookie cache
_cookies_loaded = False
_cookies = {}


def load_hk33_cookies() -> dict:
    """
    Load HK33 cookies from .hk33_cookies (JSON) or cookies.pkl (Selenium).

    Returns:
        Dict of cookie name → value pairs

    Note:
        Run extract_hk33_cookies.py to create the .hk33_cookies file,
        OR run the selenium login script to create cookies.pkl.
    """
    global _cookies_loaded, _cookies

    if _cookies_loaded:
        return _cookies

    # Try JSON file first (manual extraction)
    json_file = Path(".hk33_cookies")
    pickle_file = Path("cookies.pkl")

    if json_file.exists():
        try:
            with open(json_file) as f:
                _cookies = json.load(f)
            logger.info(f"Loaded {len(_cookies)} cookies from .hk33_cookies")
            _cookies_loaded = True
            return _cookies
        except Exception as e:
            logger.error(f"Failed to load cookies from .hk33_cookies: {e}")

    # Try Pickle file (selenium script)
    if pickle_file.exists():
        try:
            import pickle

            with open(pickle_file, "rb") as f:
                cookie_list = pickle.load(f)
                # Convert list of dicts (Selenium) to key-value dict (Requests)
                _cookies = {c["name"]: c["value"] for c in cookie_list if "name" in c and "value" in c}

            logger.info(f"Loaded {len(_cookies)} cookies from cookies.pkl")
            _cookies_loaded = True
            return _cookies
        except Exception as e:
            logger.error(f"Failed to load cookies from cookies.pkl: {e}")

    logger.warning(
        "No cookie file found (.hk33_cookies or cookies.pkl). HK33 scraping may fail with 403 errors. "
        "Run extract_hk33_cookies.py or login script created."
    )
    _cookies_loaded = True
    return {}


def get_browser_headers() -> dict:
    """Return headers that mimic browser requests to avoid 403 errors."""
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8,zh;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://horse.hk33.com/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Cache-Control": "max-age=0",
    }


def convert_timestamp_to_datetime(race_date: date, timestamp_str: str) -> datetime:
    """
    Convert a timestamp string to a timezone-aware datetime object.

    The timestamp_str can be in two formats:
    1. Full format: "YYYY-MM-DD HH:MM:SS" (already resolved by resolve_datetime_series)
    2. Time-only format: "HH:MM" or "HH:MM:SS" (needs date resolution)

    Args:
        race_date: The date of the race (used if timestamp_str is time-only)
        timestamp_str: Timestamp string in one of the formats above

    Returns:
        Timezone-aware datetime in Hong Kong timezone
    """
    try:
        # Try full timestamp format first (from resolve_datetime_series)
        if "-" in timestamp_str and " " in timestamp_str:
            dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            return HKT.localize(dt)

        # Try time-only format (HH:MM or HH:MM:SS)
        match = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", timestamp_str)
        if match:
            h, m = int(match.group(1)), int(match.group(2))
            s = int(match.group(3)) if match.group(3) else 0
            t = time(h, m, s)
            dt = datetime.combine(race_date, t)
            return HKT.localize(dt)

        # If we can't parse it, log error and return a default
        logger.error(f"Could not parse timestamp string: {timestamp_str}")
        return HKT.localize(datetime.combine(race_date, time(0, 0)))

    except Exception as e:
        logger.error(f"Error parsing timestamp '{timestamp_str}': {e}")
        return HKT.localize(datetime.combine(race_date, time(0, 0)))


def resolve_datetime_series(race_date: date, time_strings: list[str]) -> list[datetime]:
    """
    Resolve a chronological list of time strings into timezone-aware datetimes,
    handling midnight crossovers for overnight odds tracking.

    Algorithm:
    1. Parse time strings into time objects or full timestamps
    2. Assume the LAST timestamp is on race_date (Day 0)
    3. Iterate backwards: if current_time > prev_time, we crossed midnight → decrement day
    4. Combine resolved date with time and localize to HKT timezone

    Example:
        race_date = date(2026, 1, 14)
        times = ["23:00", "23:59", "00:01", "12:00"]  # Crosses midnight at 00:01
        result = resolve_datetime_series(race_date, times)
        # Returns:
        # [2026-01-13 23:00:00+08:00,  ← Day -1
        #  2026-01-13 23:59:00+08:00,  ← Day -1
        #  2026-01-14 00:01:00+08:00,  ← Day 0 (race day)
        #  2026-01-14 12:00:00+08:00]  ← Day 0

    Args:
        race_date: The date of the race (Day 0)
        time_strings: Chronological list of time strings in HH:MM, HH:MM:SS, or full format

    Returns:
        List of HKT-localized datetimes corresponding to the input strings
    """
    if not time_strings:
        return []

    # Parse all times
    parsed_times = []
    for ts in time_strings:
        try:
            # Try full timestamp first (fast string check instead of regex)
            if len(ts) >= 19 and "-" in ts:
                dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                # If full timestamp is present, use its date
                parsed_times.append(("full", HKT.localize(dt)))
                continue

            # Try time-only formats using strptime (faster than regex + int conversion)
            try:
                t = datetime.strptime(ts, "%H:%M:%S").time()
                parsed_times.append(("time", t))
            except ValueError:
                try:
                    t = datetime.strptime(ts, "%H:%M").time()
                    parsed_times.append(("time", t))
                except ValueError:
                    logger.warning(f"Could not parse time string: {ts}")
                    parsed_times.append(("error", None))

        except Exception:
            parsed_times.append(("error", None))

    # Resolve dates by iterating backwards from race_date (Day 0)
    # Assumption: The last timestamp is on race_date; earlier timestamps may be on Day -1
    # When current_time > prev_time (going backwards), we crossed midnight → decrement day

    resolved_datetimes = [None] * len(parsed_times)
    current_date = race_date
    prev_time = None

    # Iterate backwards from last item to first
    for i in range(len(parsed_times) - 1, -1, -1):
        item_type, item_value = parsed_times[i]

        if item_type == "full":
            # Full timestamp already has date - use it directly
            resolved_datetimes[i] = item_value
            current_date = item_value.date()
            prev_time = item_value.time()
            continue

        if item_type == "error":
            continue

        current_time = item_value

        # Detect midnight crossover when going backwards
        # If current_time > prev_time, we crossed midnight backwards
        # Example: [23:59, 00:01] → processing 23:59 (i=0) after 00:01 (i=1)
        if prev_time is not None and current_time > prev_time:
            current_date = current_date - timedelta(days=1)

        dt = datetime.combine(current_date, current_time)
        resolved_datetimes[i] = HKT.localize(dt)
        prev_time = current_time

    return resolved_datetimes


@rate_limited(config.RATE_LIMIT_HK33)
@retry_on_network_error
def scrape_hk33_hkjc_odds(session: HTTPSession, date_ymd: str, race_no: int, bet_type: str) -> list[dict]:
    """
    Scrape hkjc Win/Place odds from HK33.
    Resolves timestamps relative to race date.
    """
    # Convert date format: 2026/01/14 → 2026-01-14
    date_dash = date_ymd.replace("/", "-")
    race_date = datetime.strptime(date_dash, "%Y-%m-%d").date()

    # Build URL
    url = f"{config.HK33_BASE_URL}/jc-wp-trends-history?date={date_dash}&race={race_no}&type={bet_type}"

    logger.debug(f"Scraping hkjc {bet_type} odds: {url}")

    # Load and set cookies
    cookies = load_hk33_cookies()
    for name, value in cookies.items():
        session.cookies.set(name, value, domain="horse.hk33.com")

    # Fetch page
    resp = session.get(url, headers=get_browser_headers(), timeout=config.HK33_REQUEST_TIMEOUT)
    resp.raise_for_status()

    # Parse HTML to get raw records
    soup = BeautifulSoup(resp.text, "html.parser")
    # Note: parse_odds_table uses ID='odds_table' for type='w'/'p' pages usually?
    # Or 'discounts_table'?
    # Based on observation, type=w uses 'odds_table' or similar structure.
    # We'll use the generic parser which looks for robust attributes.
    records = parse_odds_table(soup, f"hkjc-{bet_type}")

    if not records:
        return []

    # Default sort by existing order (implicit in list)
    # Extract unique timestamps in order of appearance (row by row)
    # But parse_odds_table returns a flat list of ALL cells.
    # We need to rely on the fact that parse_odds_table processes ROW by ROW.
    # So the list is ordered by time (groups of horses).

    # We can reconstruct the time series.
    # records[i]['timestamp_str']

    # We need to map distinct timestamp_str -> datetime
    # Preserve order of appearance
    seen_timestamps = []
    seen_set = set()
    for r in records:
        ts = r["timestamp_str"]
        if ts not in seen_set:
            seen_timestamps.append(ts)
            seen_set.add(ts)

    # Resolve dates
    resolved_dates = resolve_datetime_series(race_date, seen_timestamps)
    time_map = dict(zip(seen_timestamps, resolved_dates))

    # Update records with resolved datetimes (replace timestamp_str with valid string or add object?)
    # persistence.py expects 'timestamp_str' OR we can update persistence logic.
    # Better: Update persistence.py to accept 'timestamp_obj'.
    # For now, let's update 'timestamp_str' to be the full ISO format which convert_timestamp_to_datetime handles.

    for r in records:
        ts_str = r["timestamp_str"]
        if ts_str in time_map and time_map[ts_str]:
            # Format as YYYY-MM-DD HH:MM:SS
            # This ensures convert_timestamp_to_datetime (which now supports full format) works correctly
            # without logic changes in persistence.py
            r["timestamp_str"] = time_map[ts_str].strftime("%Y-%m-%d %H:%M:%S")
            r["bet_type"] = bet_type
            r["source_url"] = url

    logger.info(f"Scraped {len(records)} hkjc {bet_type} odds for race {race_no}")
    return records


def parse_odds_table(soup: BeautifulSoup, data_type: str) -> list[dict]:
    """
    Parse HK33 odds table structure using data attributes.

    Target table ID: 'discounts_table'
    Attributes:
        tr['data-date-time']: Full timestamp
        td['data-horse-num']: Horse number (1-14)
        td text: Odds value

    Args:
        soup: BeautifulSoup object of the page
        data_type: "hkjc" or "market" (for logging)

    Returns:
        List of dicts with format:
        [
            {
                'horse_no': 1,
                'timestamp_str': '2026-01-14 12:08:00',
                'odds_value': Decimal('3.5')
            },
            ...
        ]
    """
    try:
        # 1. Try finding by ID first (most robust)
        data_table = soup.find(id="discounts_table")

        # 2. If not found by ID, try finding any table with 'data-race-num' attribute
        if not data_table:
            data_table = soup.find("table", attrs={"data-race-num": True})

        if not data_table:
            # Fallback: legacy detection (search for time pattern)
            # This handles cases where ID might be missing or different
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    if cells and re.match(r"\d{1,2}:\d{2}", cells[0].get_text(strip=True)):
                        data_table = table
                        logger.warning(f"Found table by text pattern fallback for {data_type}")
                        break
                if data_table:
                    break

        if not data_table:
            logger.warning(f"No data table found for {data_type} page")
            return []

        # Process rows
        results = []
        rows = data_table.find_all("tr")

        # Identify horses from header if possible, or assume 1-14 based on data attributes
        # We rely on data attributes in the cells now

        for row in rows:
            # Try to get timestamp from data attribute
            timestamp_str = row.get("data-date-time")

            # If no data attribute, try first cell text
            if not timestamp_str:
                cells = row.find_all(["td", "th"])
                if cells:
                    text = cells[0].get_text(strip=True)
                    if re.search(r"\d{1,2}:\d{2}", text):
                        timestamp_str = text

            if not timestamp_str:
                continue

            # Iterate through cells to find odds with horse numbers
            cells = row.find_all(["td", "th"])

            # Approach 1: Use data-horse-num attribute (Robust)
            found_horse_data = False
            for cell in cells:
                horse_num_str = cell.get("data-horse-num")
                if horse_num_str and horse_num_str.isdigit():
                    horse_no = int(horse_num_str)
                    odds_text = cell.get_text(strip=True)

                    if not odds_text or odds_text == "-" or odds_text == "":
                        continue

                    try:
                        cleaned_odds = odds_text.replace(",", "")
                        odds_value = Decimal(cleaned_odds)
                        results.append(
                            {
                                "horse_no": horse_no,
                                "timestamp_str": timestamp_str,
                                "odds_value": odds_value,
                            }
                        )
                        found_horse_data = True
                    except (ValueError, decimal.InvalidOperation):
                        continue

            # Approach 2: Fallback to column index if no data attributes
            if not found_horse_data and len(cells) > 1:
                # Assume standard layout: Time, Horse 1, Horse 2...
                # We need to skip the first cell (Time)
                for idx, cell in enumerate(cells[1:], start=1):
                    # We assume column 1 = Horse 1, column 2 = Horse 2...
                    # This is risky but a necessary fallback for legacy tables
                    horse_no = idx
                    odds_text = cell.get_text(strip=True)

                    if not odds_text or odds_text == "-" or not re.match(r"[\d\.,]+", odds_text):
                        continue

                    try:
                        cleaned_odds = odds_text.replace(",", "")
                        odds_value = Decimal(cleaned_odds)
                        results.append(
                            {
                                "horse_no": horse_no,
                                "timestamp_str": timestamp_str,
                                "odds_value": odds_value,
                            }
                        )
                    except (ValueError, decimal.InvalidOperation):
                        continue

        logger.info(f"Parsed {len(results)} odds records from {data_type} table")
        return results

    except Exception as e:
        raise ParseError(f"Failed to parse {data_type} odds table: {e}") from e


def parse_hk33_odds_from_html(html: str, url: str, bet_type: str, data_type: str) -> list[dict]:
    """
    Parse HK33 odds from HTML content (for browser automation).

    Args:
        html: HTML content of the page
        url: Source URL
        bet_type: "w", "p", "bet-w", "bet-p", "eat-w", "eat-p"
        data_type: "hkjc" or "market" (for logging)

    Returns:
        List of odds records with source_url and bet_type/market_type
    """
    soup = BeautifulSoup(html, "html.parser")
    results = parse_odds_table(soup, data_type)

    # Add metadata
    for record in results:
        record["source_url"] = url
        if data_type.startswith("hkjc"):
            record["bet_type"] = bet_type
        else:
            record["market_type"] = bet_type

    return results


@rate_limited(config.RATE_LIMIT_HK33)
@retry_on_network_error
def scrape_hk33_offshore_market(session: HTTPSession, date_ymd: str, race_no: int, market_type: str) -> list[dict]:
    """
    Scrape offshore market Bet/Eat data from HK33 using HTTP.

    Args:
        session: HTTP session for making requests
        date_ymd: Date in "YYYY/MM/DD" format
        race_no: Race number (1-11)
        market_type: "bet-w", "bet-p", "eat-w", "eat-p"

    Returns:
        List of market records (same format as scrape_hk33_hkjc_odds):
        [
            {
                'horse_no': 1,
                'timestamp_str': '12:08',
                'odds_value': Decimal('78.0'),
                'market_type': 'bet-w',
                'source_url': '...'
            },
            ...
        ]

    Raises:
        HTTPError: If request fails
        ParseError: If page structure is unexpected
    """
    # Convert date format
    date_dash = date_ymd.replace("/", "-")

    # Build URL
    url = f"{config.HK33_BASE_URL}/offshore-market-trends-history?date={date_dash}&race={race_no}&type={market_type}"

    logger.debug(f"Scraping offshore market {market_type}: {url}")

    # Load cookies
    cookies = load_hk33_cookies()

    # Set cookies in session
    if session.cookies is not None:
        for name, value in cookies.items():
            session.cookies.set(name, value, domain="horse.hk33.com")

    # Fetch page with browser headers and cookies
    resp = session.get(url, headers=get_browser_headers(), timeout=config.HK33_REQUEST_TIMEOUT)
    resp.raise_for_status()

    # Parse HTML
    results = parse_hk33_odds_from_html(resp.text, url, market_type, f"market-{market_type}")

    logger.info(f"Scraped {len(results)} {market_type} market records for race {race_no}")
    return results


def scrape_hk33_race_all_types(
    session: HTTPSession,
    date_ymd: str,
    race_no: int,
    scrape_hkjc: bool = True,
    scrape_market: bool = True,
) -> dict:
    """
    Scrape all odds types for a single race using parallel requests.

    Args:
        session: HTTP session
        date_ymd: Date in "YYYY/MM/DD" format
        race_no: Race number
        scrape_hkjc: Whether to scrape hkjc Win/Place odds
        scrape_market: Whether to scrape offshore market data

    Returns:
        Dict with two keys:
        {
            'hkjc_data': [...],  # Combined Win + Place odds
            'market_data': [...]  # Combined bet-w, bet-p, eat-w, eat-p data
        }
    """
    hkjc_data = []
    market_data = []

    # Build list of scraping tasks
    tasks = []

    if scrape_hkjc:
        tasks.append(("hkjc", "w"))
        tasks.append(("hkjc", "p"))

    if scrape_market:
        for market_type in ["bet-w", "bet-p", "eat-w", "eat-p"]:
            tasks.append(("market", market_type))

    # Execute tasks in parallel (max 6 workers for 6 types)
    with ThreadPoolExecutor(max_workers=config.MAX_HK33_ODDS_WORKERS) as executor:
        future_to_task = {}

        for task_type, odds_type in tasks:
            if task_type == "hkjc":
                future = executor.submit(scrape_hk33_hkjc_odds, session, date_ymd, race_no, odds_type)
            else:  # market
                future = executor.submit(scrape_hk33_offshore_market, session, date_ymd, race_no, odds_type)

            future_to_task[future] = (task_type, odds_type)

        # Collect results as they complete
        for future in as_completed(future_to_task):
            task_type, odds_type = future_to_task[future]
            try:
                result = future.result()
                if task_type == "hkjc":
                    hkjc_data.extend(result)
                else:
                    market_data.extend(result)
            except Exception as e:
                logger.error(f"Failed to scrape {task_type} {odds_type} for race {race_no}: {e}")

    return {"hkjc_data": hkjc_data, "market_data": market_data}
