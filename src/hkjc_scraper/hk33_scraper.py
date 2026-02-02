"""
HK33.com scraper for historical odds and offshore market data
HK33.com 歷史賠率及海外市場數據爬蟲
"""

import decimal
import json
import logging
import random
import re
import time as time_module
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse

import pytz
import requests
from bs4 import BeautifulSoup

from hkjc_scraper import config
from hkjc_scraper.exceptions import ParseError
from hkjc_scraper.http_utils import HTTPSession

logger = logging.getLogger(__name__)

# Hong Kong timezone
HKT = pytz.timezone("Asia/Hong_Kong")

# Cookie cache (protected by _cookie_lock for thread safety)
_cookies_loaded = False
_cookies = {}
_cookie_lock = Lock()

# Session recovery: track re-login attempts per scraping session
_relogin_count = 0
_relogin_lock = Lock()

# User-Agent rotation pool
_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
]


class AdaptiveRateLimiter:
    """
    Adaptive rate limiter that applies different delays based on URL path changes.

    - Same URL path (different query params): Lower delay (RATE_LIMIT_HK33_SAME_PATH)
    - Different URL path: Higher delay (RATE_LIMIT_HK33_PATH_CHANGE)

    Thread-safe for concurrent usage.
    """

    def __init__(
        self,
        same_path_delay: float = config.RATE_LIMIT_HK33_SAME_PATH,
        path_change_delay: float = config.RATE_LIMIT_HK33_PATH_CHANGE,
    ):
        self.same_path_delay = same_path_delay
        self.path_change_delay = path_change_delay
        self._last_url_path = None
        self._last_request_time = 0.0
        self._lock = Lock()

    def wait_if_needed(self, url: str) -> None:
        """
        Wait if needed before making a request to the given URL.

        Args:
            url: The URL to be requested
        """
        parsed = urlparse(url)
        current_path = parsed.path

        with self._lock:
            now = time_module.time()
            elapsed = now - self._last_request_time

            # Determine required delay
            if self._last_url_path is None:
                # First request, no delay
                required_delay = 0.0
            elif current_path == self._last_url_path:
                # Same path, use lower delay
                required_delay = self.same_path_delay
                logger.debug(f"Same path detected: {current_path}, using {required_delay}s delay")
            else:
                # Different path, use higher delay
                required_delay = self.path_change_delay
                logger.info(
                    f"Path change detected: {self._last_url_path} -> {current_path}, using {required_delay}s delay"
                )

            # Add ±20% random jitter to avoid predictable request patterns
            if required_delay > 0:
                jitter = required_delay * random.uniform(-0.2, 0.2)
                required_delay = max(0, required_delay + jitter)

            # Calculate remaining wait time
            remaining = required_delay - elapsed
            if remaining > 0:
                logger.debug(f"Rate limiting: waiting {remaining:.2f}s before request")
                time_module.sleep(remaining)

            # Update state
            self._last_url_path = current_path
            self._last_request_time = time_module.time()


# Global adaptive rate limiter instance
_adaptive_rate_limiter = AdaptiveRateLimiter()


def refresh_hk33_session() -> dict[str, str]:
    """
    Refresh the HK33 session by performing a requests-based re-login.

    Clears the cookie cache and attempts to get fresh cookies via login.
    Respects the HK33_MAX_RELOGINS limit to avoid infinite loops.

    Returns:
        Dict of cookie name -> value on success, empty dict on failure or limit exceeded.
    """
    global _cookies_loaded, _cookies, _relogin_count

    with _relogin_lock:
        if _relogin_count >= config.HK33_MAX_RELOGINS:
            logger.error(
                f"Max re-login attempts ({config.HK33_MAX_RELOGINS}) reached. "
                f"Skipping re-login. Manual cookie refresh may be needed."
            )
            return {}

        _relogin_count += 1
        current_attempt = _relogin_count

    logger.warning(f"Refreshing HK33 session (attempt {current_attempt}/{config.HK33_MAX_RELOGINS})...")

    # Clear cookie cache
    with _cookie_lock:
        _cookies_loaded = False
        _cookies.clear()

    # Attempt requests-based login
    from hkjc_scraper.hk33_login import login_hk33_requests

    new_cookies = login_hk33_requests()

    if new_cookies:
        with _cookie_lock:
            _cookies.update(new_cookies)
            _cookies_loaded = True
        logger.info(f"HK33 session refreshed successfully ({len(new_cookies)} cookies)")
        return new_cookies

    # If requests login failed, try reloading from file (maybe Selenium was used externally)
    logger.warning("Requests-based login failed. Attempting to reload cookies from file...")
    return load_hk33_cookies()


def reset_relogin_counter() -> None:
    """Reset the re-login counter. Call at the start of each scraping session."""
    global _relogin_count
    with _relogin_lock:
        _relogin_count = 0


def _is_login_redirect(response: requests.Response) -> bool:
    """Check if a response is a redirect to the login page or contains a login form."""
    # Check redirect chain
    if response.history:
        for r in response.history:
            if "login" in r.headers.get("Location", "").lower():
                return True

    # Check final URL
    if "login" in response.url.lower() and "login-register" in response.url.lower():
        return True

    # Check HTML content for login form (lightweight check)
    if "login-register" in response.text[:2000]:
        return True

    return False


def _handle_login_redirect(
    resp: requests.Response, session: HTTPSession, url: str
) -> requests.Response | None:
    """
    Check if response is a login redirect and attempt session recovery.

    Returns:
        The original response if no redirect, a new response after successful
        re-login, or None if recovery failed.
    """
    if not _is_login_redirect(resp):
        return resp

    logger.warning(f"Login redirect detected for {url} - session expired")
    new_cookies = refresh_hk33_session()
    if not new_cookies:
        logger.error("Session refresh failed after login redirect")
        return None

    for name, value in new_cookies.items():
        session.cookies.set(name, value, domain="horse.hk33.com")
    resp = session.get(url, headers=get_browser_headers(), timeout=config.HK33_REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp


def retry_on_hk33_error(max_retries: int = 3, backoff_delay: float = 15.0):
    """
    Decorator to retry HTTP requests on HK33 errors with session recovery.

    Handles:
    - 429 (Too Many Requests): Wait backoff_delay, then retry
    - 403 (Forbidden/Session Expired): Refresh session via re-login, then retry
    - Connection errors (RemoteDisconnected, ConnectionReset): Backoff and retry
    - Login page redirects: Treat as session expired

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        backoff_delay: Time to wait after 429 before retrying (default: 15s)
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)

                    # Check if the response was a login redirect (session expired)
                    # The function returns data, not the response directly,
                    # so we handle redirects inside the scraping functions instead.
                    return result

                except requests.ConnectionError as e:
                    # RemoteDisconnected, ConnectionResetError, etc.
                    if attempt < max_retries:
                        wait = backoff_delay * (attempt + 1)
                        logger.warning(
                            f"Connection error (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Waiting {wait:.0f}s before retry..."
                        )
                        time_module.sleep(wait)
                        continue
                    else:
                        logger.error(f"Max retries ({max_retries}) exceeded for connection errors.")
                        raise

                except requests.HTTPError as e:
                    status = e.response.status_code if e.response is not None else None

                    if status == 429:
                        if attempt < max_retries:
                            logger.warning(
                                f"429 Too Many Requests (attempt {attempt + 1}/{max_retries + 1}). "
                                f"Waiting {backoff_delay}s before retry..."
                            )
                            time_module.sleep(backoff_delay)
                            continue
                        else:
                            logger.error(f"Max retries ({max_retries}) exceeded for 429 errors.")
                            raise

                    elif status == 403:
                        if attempt < max_retries:
                            logger.warning(
                                f"403 Forbidden - session likely expired (attempt {attempt + 1}/{max_retries + 1}). "
                                f"Attempting session refresh..."
                            )
                            new_cookies = refresh_hk33_session()
                            if not new_cookies:
                                logger.error("Session refresh failed. Cannot retry.")
                                raise
                            # Brief pause after re-login before retrying
                            time_module.sleep(2.0)
                            continue
                        else:
                            logger.error(f"Max retries ({max_retries}) exceeded for 403 errors.")
                            raise

                    else:
                        raise

                except Exception:
                    raise

        return wrapper

    return decorator


def _pass_age_gate(cookie_dict: dict) -> dict:
    """
    Pass HK33 age verification gate if not already done.

    The site requires POSTing action=set_18 to get an 'i_am_18_or_over' cookie,
    otherwise pages return an empty shell with no data tables.

    Args:
        cookie_dict: Current cookies (must include PHPSESSID)

    Returns:
        Updated cookie dict with i_am_18_or_over added
    """
    if "i_am_18_or_over" in cookie_dict:
        return cookie_dict

    try:
        session = requests.Session()
        for name, value in cookie_dict.items():
            session.cookies.set(name, value)

        resp = session.post(
            "https://horse.hk33.com/ajaj/landing.ajaj",
            data={"action": "set_18"},
            headers={
                "User-Agent": random.choice(_USER_AGENTS),
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://horse.hk33.com/",
            },
            timeout=10,
        )

        if resp.status_code == 200:
            new_cookies = dict(session.cookies)
            if "i_am_18_or_over" in new_cookies:
                cookie_dict["i_am_18_or_over"] = new_cookies["i_am_18_or_over"]
                logger.info("Passed HK33 age verification gate")
            else:
                # Set it manually as fallback — the server expects any truthy value
                cookie_dict["i_am_18_or_over"] = "1"
                logger.info("Set age gate cookie manually")
        else:
            logger.warning(f"Age gate POST returned {resp.status_code}, setting cookie manually")
            cookie_dict["i_am_18_or_over"] = "1"

    except Exception as e:
        logger.warning(f"Failed to pass age gate: {e}, setting cookie manually")
        cookie_dict["i_am_18_or_over"] = "1"

    return cookie_dict


def load_hk33_cookies() -> dict:
    """
    Load HK33 cookies from .hk33_cookies (JSON) or cookies.pkl (Selenium).
    Ensures the age verification gate cookie is present.

    Returns:
        Dict of cookie name → value pairs

    Note:
        Run hkjc-scraper --login-hk33 to create the .hk33_cookies file.
    """
    global _cookies_loaded, _cookies

    with _cookie_lock:
        if _cookies_loaded:
            return _cookies.copy()

        # Load from JSON cookie file
        json_file = Path(".hk33_cookies")

        if json_file.exists():
            try:
                with open(json_file) as f:
                    _cookies = json.load(f)
                logger.info(f"Loaded {len(_cookies)} cookies from .hk33_cookies")
            except Exception as e:
                logger.error(f"Failed to load cookies from .hk33_cookies: {e}")

        if not _cookies:
            logger.warning(
                "No cookie file found (.hk33_cookies). HK33 scraping may fail with 403 errors. "
                "Run hkjc-scraper --login-hk33 to create."
            )

        # Ensure age gate cookie is present
        if _cookies:
            _cookies = _pass_age_gate(_cookies)

        _cookies_loaded = True
        return _cookies.copy()


def get_browser_headers() -> dict:
    """Return headers that mimic browser requests with randomized User-Agent."""
    return {
        "User-Agent": random.choice(_USER_AGENTS),
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


@retry_on_hk33_error(max_retries=3, backoff_delay=15.0)
def scrape_hk33_hkjc_odds(session: HTTPSession, date_ymd: str, race_no: int, bet_type: str) -> list[dict]:
    """
    Scrape hkjc Win/Place odds from HK33.
    Resolves timestamps relative to race date.
    Uses adaptive rate limiting based on URL path changes.
    Retries on 429 (Too Many Requests) with 15s backoff.
    """
    # Convert date format: 2026/01/14 → 2026-01-14
    date_dash = date_ymd.replace("/", "-")
    race_date = datetime.strptime(date_dash, "%Y-%m-%d").date()

    # Build URL
    url = f"{config.HK33_BASE_URL}/jc-wp-trends-history?date={date_dash}&race={race_no}&type={bet_type}"

    logger.debug(f"Scraping hkjc {bet_type} odds: {url}")

    # Adaptive rate limiting
    _adaptive_rate_limiter.wait_if_needed(url)

    # Load and set cookies
    cookies = load_hk33_cookies()
    for name, value in cookies.items():
        session.cookies.set(name, value, domain="horse.hk33.com")

    # Fetch page
    resp = session.get(url, headers=get_browser_headers(), timeout=config.HK33_REQUEST_TIMEOUT)
    resp.raise_for_status()

    # Handle login redirect (session expired)
    resp = _handle_login_redirect(resp, session, url)
    if resp is None:
        return []

    # Parse HTML to get raw records
    soup = BeautifulSoup(resp.text, "html.parser")
    records = parse_odds_table(soup, f"hkjc-{bet_type}")

    if not records:
        return []

    # Extract unique timestamps in order of appearance, resolve dates
    seen_timestamps = []
    seen_set = set()
    for r in records:
        ts = r["timestamp_str"]
        if ts not in seen_set:
            seen_timestamps.append(ts)
            seen_set.add(ts)

    resolved_dates = resolve_datetime_series(race_date, seen_timestamps)
    time_map = dict(zip(seen_timestamps, resolved_dates))

    # Replace timestamp_str with full YYYY-MM-DD HH:MM:SS format for persistence layer
    for r in records:
        ts_str = r["timestamp_str"]
        if ts_str in time_map and time_map[ts_str]:
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
        # 1. Try finding by known table IDs
        #    - odds_table: used on jc-wp-trends-history (HKJC odds)
        #    - discounts_table: used on offshore-market-trends-history (offshore market)
        data_table = soup.find(id="odds_table") or soup.find(id="discounts_table")

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


@retry_on_hk33_error(max_retries=3, backoff_delay=15.0)
def scrape_hk33_offshore_market(session: HTTPSession, date_ymd: str, race_no: int, market_type: str) -> list[dict]:
    """
    Scrape offshore market Bet/Eat data from HK33 using HTTP.
    Uses adaptive rate limiting based on URL path changes.
    Retries on 429 (Too Many Requests) with 15s backoff.

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

    # Adaptive rate limiting
    _adaptive_rate_limiter.wait_if_needed(url)

    # Load and set cookies
    cookies = load_hk33_cookies()
    for name, value in cookies.items():
        session.cookies.set(name, value, domain="horse.hk33.com")

    # Fetch page
    resp = session.get(url, headers=get_browser_headers(), timeout=config.HK33_REQUEST_TIMEOUT)
    resp.raise_for_status()

    # Handle login redirect (session expired)
    resp = _handle_login_redirect(resp, session, url)
    if resp is None:
        return []

    # Parse HTML
    results = parse_hk33_odds_from_html(resp.text, url, market_type, f"market-{market_type}")

    logger.info(f"Scraped {len(results)} {market_type} market records for race {race_no}")
    return results


def scrape_hk33_meeting_by_type(
    session: HTTPSession,
    date_ymd: str,
    race_numbers: list[int],
    scrape_hkjc: bool = True,
    scrape_market: bool = True,
) -> dict[int, dict]:
    """
    Scrape HK33 data by bet_type/market first, then all races for each type.
    This optimizes for URL path locality and better server-side caching.

    Algorithm:
    1. Build list of bet_types to scrape (hkjc: w, p; market: bet-w, bet-p, eat-w, eat-p)
    2. For each bet_type:
       - Scrape all races in parallel (max MAX_HK33_RACE_WORKERS workers)
       - Collect results
    3. Organize results by race_no for backwards compatibility

    Args:
        session: HTTP session
        date_ymd: Date in "YYYY/MM/DD" format
        race_numbers: List of race numbers to scrape (e.g., [1, 2, 3, ..., 11])
        scrape_hkjc: Whether to scrape hkjc Win/Place odds
        scrape_market: Whether to scrape offshore market data

    Returns:
        Dict mapping race_no to data dict:
        {
            1: {'hkjc_data': [...], 'market_data': [...]},
            2: {'hkjc_data': [...], 'market_data': [...]},
            ...
        }
    """
    # Initialize results structure
    results = {race_no: {"hkjc_data": [], "market_data": []} for race_no in race_numbers}

    # Build list of bet_types to scrape
    bet_types = []
    if scrape_hkjc:
        bet_types.append(("hkjc", "w"))
        bet_types.append(("hkjc", "p"))
    if scrape_market:
        for market_type in ["bet-w", "bet-p", "eat-w", "eat-p"]:
            bet_types.append(("market", market_type))

    logger.info(
        f"Starting optimized HK33 scraping: {len(bet_types)} types × {len(race_numbers)} races = {len(bet_types) * len(race_numbers)} requests"
    )

    # Process each bet_type, scraping all races in parallel
    for task_type, odds_type in bet_types:
        logger.info(f"Scraping {task_type} {odds_type} for all {len(race_numbers)} races...")

        with ThreadPoolExecutor(max_workers=config.MAX_HK33_RACE_WORKERS) as executor:
            # Submit all races for this bet_type
            future_to_race = {}
            for race_no in race_numbers:
                if task_type == "hkjc":
                    future = executor.submit(scrape_hk33_hkjc_odds, session, date_ymd, race_no, odds_type)
                else:  # market
                    future = executor.submit(scrape_hk33_offshore_market, session, date_ymd, race_no, odds_type)
                future_to_race[future] = race_no

            # Collect results as they complete
            for future in as_completed(future_to_race):
                race_no = future_to_race[future]
                try:
                    data = future.result()
                    if task_type == "hkjc":
                        results[race_no]["hkjc_data"].extend(data)
                    else:
                        results[race_no]["market_data"].extend(data)
                except Exception as e:
                    logger.error(f"Failed to scrape {task_type} {odds_type} for race {race_no}: {e}")

    # Log summary
    total_hkjc = sum(len(r["hkjc_data"]) for r in results.values())
    total_market = sum(len(r["market_data"]) for r in results.values())
    logger.info(f"Completed HK33 scraping: {total_hkjc} hkjc records, {total_market} market records")

    return results
