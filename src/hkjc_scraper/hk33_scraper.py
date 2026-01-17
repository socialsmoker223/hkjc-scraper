"""
HK33.com scraper for historical odds and offshore market data
HK33.com 歷史賠率及海外市場數據爬蟲
"""

import decimal
import json
import re
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Optional
import logging

from bs4 import BeautifulSoup
import pytz

from hkjc_scraper import config
from hkjc_scraper.http_utils import HTTPSession, rate_limited, retry_on_network_error
from hkjc_scraper.exceptions import ParseError

logger = logging.getLogger(__name__)

# Hong Kong timezone
HKT = pytz.timezone("Asia/Hong_Kong")

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
            with open(json_file, 'r') as f:
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
            with open(pickle_file, 'rb') as f:
                cookie_list = pickle.load(f)
                # Convert list of dicts (Selenium) to key-value dict (Requests)
                _cookies = {c['name']: c['value'] for c in cookie_list if 'name' in c and 'value' in c}
            
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


def resolve_datetime_series(race_date: date, time_strings: list[str]) -> list[datetime]:
    """
    Resolve a chronological list of time strings (HH:MM or HH:MM:SS) into datetimes,
    handling the "Day - 1" vs "Day 0" logic.

    Logic:
    - The list is assumed to be in chronological order (Ascending).
    - It usually starts on Day - 1 (Overnight) and ends on Day 0 (Race Day).
    - We detect the midnight crossover (e.g. 23:59 -> 00:01).
    - Everything before crossover is Day - 1. Everything after is Day 0.
    - If no crossover is detected:
        - If times are all "large" (e.g. > 12:00) and it's a list head: probably Day -1?
        - Actually, if we just scan, we assume we start at Day X.
        - If we see a time drop (23:00 -> 00:00), we increment the day.
        - But "Day X" is the Race Day.
        - So we work BACKWARDS or FORWARDS?
        - If we assume the LAST record is Day 0 (Race Day), we can work backwards.
        
    Refined Logic:
    1. Parse all times into time objects.
    2. Assume the LAST time in the list is on `race_date`.
    3. Iterate backwards. If current_time > previous_time (e.g. 00:01 vs 23:59), we crossed midnight backwards. Decrement day.
    
    Args:
        race_date: The date of the race (Day 0)
        time_strings: List of time strings (e.g. "18:00", "23:59", "00:01", "12:00")

    Returns:
        List of timezone-aware datetimes corresponding to the input strings.
    """
    if not time_strings:
        return []

    # Parse all times
    parsed_times = []
    for ts in time_strings:
        try:
            # Try full timestamp first
            if "-" in ts and ":" in ts:
                dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                # If full timestamp is present, use its date, but respect race_date logic?
                # Usually if full timestamp is present, we trust it.
                parsed_times.append({'type': 'full', 'value': HKT.localize(dt)})
                continue
                
            # Try HH:MM:SS
            match = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", ts)
            if match:
                h, m = int(match.group(1)), int(match.group(2))
                s = int(match.group(3)) if match.group(3) else 0
                parsed_times.append({'type': 'time', 'value': time(h, m, s)})
            else:
                logger.warning(f"Could not parse time string: {ts}")
                parsed_times.append({'type': 'error', 'value': None})
                
        except Exception:
            parsed_times.append({'type': 'error', 'value': None})

    # Resolve dates (Backwards from last item)
    # We assume the last item is on race_date (or before).
    # Actually, odds stop at race start. So last item is definitely race_date.
    
    resolved_datetimes = [None] * len(parsed_times)
    
    current_date = race_date
    
    # Iterate backwards
    last_time = None
    
    for i in range(len(parsed_times) - 1, -1, -1):
        item = parsed_times[i]
        
        if item['type'] == 'full':
            resolved_datetimes[i] = item['value']
            # Reset heuristic tracking if we hit a hard date (optional, but good for hybrid lists)
            current_date = item['value'].date()
            if HKT.localize(datetime.combine(current_date, time(0,0))) > item['value']:
                 # If the date part of full timestamp is different, update current_date?
                 # Handled by just using the value.
                 pass
            last_time = item['value'].time()
            continue
            
        if item['type'] == 'error':
            continue
            
        t = item['value']
        
        # Check crossover (Backwards)
        # If we go from 12:00 (i) to 23:00 (i+1), current i is "earlier" in the day?
        # No, iterating backwards: list is [23:00, 01:00]
        # i=1 (01:00), i=0 (23:00).
        # Process i=1: last_time=01:00. day=race_date.
        # Process i=0: t=23:00. 23:00 > 01:00. This implies we stepped BACK into previous day?
        # Yes. If current_time (23:00) > last_seen_future_time (01:00), we crossed midnight backwards.
        
        if last_time is not None:
            # Tolerance: If difference is small/normal?
            # 23:59 vs 00:01 -> 23:59 > 00:01 -> day - 1
            # 14:00 vs 15:00 -> 14:00 < 15:00 -> same day
            if t > last_time:
                current_date = current_date - timedelta(days=1)
        
        dt = datetime.combine(current_date, t)
        resolved_datetimes[i] = HKT.localize(dt)
        last_time = t

    return resolved_datetimes


@rate_limited(config.RATE_LIMIT_HK33)
def scrape_hk33_jchk_odds(session: HTTPSession, date_ymd: str, race_no: int, bet_type: str) -> list[dict]:
    """
    Scrape JCHK Win/Place odds from HK33.
    Resolves timestamps relative to race date.
    """
    # Convert date format: 2026/01/14 → 2026-01-14
    date_dash = date_ymd.replace("/", "-")
    race_date = datetime.strptime(date_dash, "%Y-%m-%d").date()

    # Build URL
    url = f"{config.HK33_BASE_URL}/jc-wp-trends-history?date={date_dash}&race={race_no}&type={bet_type}"

    logger.debug(f"Scraping JCHK {bet_type} odds: {url}")

    # Load and set cookies
    cookies = load_hk33_cookies()
    for name, value in cookies.items():
        session.cookies.set(name, value, domain='horse.hk33.com')

    # Fetch page
    resp = session.get(url, headers=get_browser_headers(), timeout=config.HK33_REQUEST_TIMEOUT)
    resp.raise_for_status()

    # Parse HTML to get raw records
    soup = BeautifulSoup(resp.text, "html.parser")
    # Note: parse_odds_table uses ID='odds_table' for type='w'/'p' pages usually?
    # Or 'discounts_table'?
    # Based on observation, type=w uses 'odds_table' or similar structure.
    # We'll use the generic parser which looks for robust attributes.
    records = parse_odds_table(soup, f"jchk-{bet_type}")

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
        ts = r['timestamp_str']
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
        ts_str = r['timestamp_str']
        if ts_str in time_map and time_map[ts_str]:
            # Format as YYYY-MM-DD HH:MM:SS
            # This ensures convert_timestamp_to_datetime (which now supports full format) works correctly
            # without logic changes in persistence.py
            r['timestamp_str'] = time_map[ts_str].strftime("%Y-%m-%d %H:%M:%S")
            r['bet_type'] = bet_type
            r['source_url'] = url

    logger.info(f"Scraped {len(records)} JCHK {bet_type} odds for race {race_no}")
    return records

    """
    Parse HK33 odds table structure using data attributes.
    
    Target table ID: 'discounts_table'
    Attributes:
        tr['data-date-time']: Full timestamp
        td['data-horse-num']: Horse number (1-14)
        td text: Odds value

    Args:
        soup: BeautifulSoup object of the page
        data_type: "jchk" or "market" (for logging)

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
                        results.append({
                            "horse_no": horse_no,
                            "timestamp_str": timestamp_str,
                            "odds_value": odds_value,
                        })
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
                        results.append({
                            "horse_no": horse_no,
                            "timestamp_str": timestamp_str,
                            "odds_value": odds_value,
                        })
                    except:
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
        data_type: "jchk" or "market" (for logging)

    Returns:
        List of odds records with source_url and bet_type/market_type
    """
    soup = BeautifulSoup(html, "html.parser")
    results = parse_odds_table(soup, data_type)

    # Add metadata
    for record in results:
        record["source_url"] = url
        if data_type.startswith("jchk"):
            record["bet_type"] = bet_type
        else:
            record["market_type"] = bet_type

    return results


@rate_limited(config.RATE_LIMIT_HK33)
def scrape_hk33_jchk_odds(session: HTTPSession, date_ymd: str, race_no: int, bet_type: str) -> list[dict]:
    """
    Scrape JCHK Win/Place odds from HK33 using HTTP.

    Args:
        session: HTTP session for making requests
        date_ymd: Date in "YYYY/MM/DD" format (e.g., "2026/01/14")
        race_no: Race number (1-11)
        bet_type: "w" (Win) or "p" (Place)

    Returns:
        List of odds records:
        [
            {
                'horse_no': 1,
                'timestamp_str': '12:08',
                'odds_value': Decimal('3.5')
            },
            ...
        ]

    Raises:
        HTTPError: If request fails
        ParseError: If page structure is unexpected
    """
    # Convert date format: 2026/01/14 → 2026-01-14
    date_dash = date_ymd.replace("/", "-")

    # Build URL
    url = f"{config.HK33_BASE_URL}/jc-wp-trends-history?date={date_dash}&race={race_no}&type={bet_type}"

    logger.debug(f"Scraping JCHK {bet_type} odds: {url}")

    # Load cookies
    cookies = load_hk33_cookies()

    # Set cookies in session
    for name, value in cookies.items():
        session.cookies.set(name, value, domain='horse.hk33.com')

    # Fetch page with browser headers and cookies
    resp = session.get(url, headers=get_browser_headers(), timeout=config.HK33_REQUEST_TIMEOUT)
    resp.raise_for_status()

    # Parse HTML
    results = parse_hk33_odds_from_html(resp.text, url, bet_type, f"jchk-{bet_type}")

    logger.info(f"Scraped {len(results)} JCHK {bet_type} odds for race {race_no}")
    return results


@rate_limited(config.RATE_LIMIT_HK33)
def scrape_hk33_offshore_market(
    session: HTTPSession, date_ymd: str, race_no: int, market_type: str
) -> list[dict]:
    """
    Scrape offshore market Bet/Eat data from HK33 using HTTP.

    Args:
        session: HTTP session for making requests
        date_ymd: Date in "YYYY/MM/DD" format
        race_no: Race number (1-11)
        market_type: "bet-w", "bet-p", "eat-w", "eat-p"

    Returns:
        List of market records (same format as scrape_hk33_jchk_odds):
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
    for name, value in cookies.items():
        session.cookies.set(name, value, domain='horse.hk33.com')

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
    scrape_jchk: bool = True,
    scrape_market: bool = True,
) -> dict:
    """
    Scrape all odds types for a single race.

    Args:
        session: HTTP session
        date_ymd: Date in "YYYY/MM/DD" format
        race_no: Race number
        scrape_jchk: Whether to scrape JCHK Win/Place odds
        scrape_market: Whether to scrape offshore market data

    Returns:
        Dict with two keys:
        {
            'jchk_data': [...],  # Combined Win + Place odds
            'market_data': [...]  # Combined bet-w, bet-p, eat-w, eat-p data
        }
    """
    jchk_data = []
    market_data = []

    # Scrape JCHK odds
    if scrape_jchk:
        try:
            jchk_data.extend(scrape_hk33_jchk_odds(session, date_ymd, race_no, "w"))
            jchk_data.extend(scrape_hk33_jchk_odds(session, date_ymd, race_no, "p"))
        except Exception as e:
            logger.error(f"Failed to scrape JCHK odds for race {race_no}: {e}")

    # Scrape offshore market
    if scrape_market:
        for market_type in ["bet-w", "bet-p", "eat-w", "eat-p"]:
            try:
                market_data.extend(scrape_hk33_offshore_market(session, date_ymd, race_no, market_type))
            except Exception as e:
                logger.error(f"Failed to scrape {market_type} for race {race_no}: {e}")

    return {"jchk_data": jchk_data, "market_data": market_data}
