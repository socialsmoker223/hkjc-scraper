"""
HTTP utilities with retry logic and rate limiting
"""

import logging
import time
from functools import wraps
from threading import Lock
from typing import Callable

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from hkjc_scraper.config import config

logger = logging.getLogger(__name__)

# Thread-safe rate limiting state
_last_request_time = {}
_rate_limit_lock = Lock()


class HTTPSession:
    """
    Context manager for HTTP session with connection pooling

    Usage:
        with HTTPSession() as session:
            response = session.get(url)
    """

    def __init__(self):
        self.session = None

    def __enter__(self):
        """Create and configure requests session"""
        self.session = requests.Session()

        # Set default headers
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
            }
        )

        # Configure connection pooling
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=0,  # We handle retries with tenacity
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        logger.debug("HTTP session created")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close session and cleanup resources"""
        if self.session:
            self.session.close()
            logger.debug("HTTP session closed")

    def get(self, url: str, **kwargs) -> requests.Response:
        """
        Make GET request with configured timeout

        Args:
            url: URL to fetch
            **kwargs: Additional arguments to pass to requests.get()

        Returns:
            requests.Response object
        """
        # Set default timeouts if not provided
        if "timeout" not in kwargs:
            kwargs["timeout"] = (config.REQUEST_CONNECT_TIMEOUT, config.REQUEST_TIMEOUT)

        return self.session.get(url, **kwargs)


def retry_on_network_error(func: Callable) -> Callable:
    """
    Decorator to retry function on network errors with exponential backoff

    Retries on:
        - requests.ConnectionError (connection failed)
        - requests.Timeout (request timeout)

    Does NOT retry on:
        - requests.HTTPError (4xx/5xx responses)
        - Other request exceptions (invalid URLs, etc.)

    Configuration:
        - Max attempts: config.RETRY_MAX_ATTEMPTS (default: 3)
        - Backoff: exponential with base config.RETRY_BACKOFF_BASE (default: 2)
        - Wait times: 1s, 2s, 4s, 8s...
    """

    @retry(
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        stop=stop_after_attempt(config.RETRY_MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=30, exp_base=config.RETRY_BACKOFF_BASE),
        reraise=True,
    )
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (requests.ConnectionError, requests.Timeout) as e:
            logger.warning(f"Network error in {func.__name__}: {e}, retrying...")
            raise

    return wrapper


def rate_limited(delay_seconds: float) -> Callable:
    """
    Decorator to enforce rate limiting between function calls

    Args:
        delay_seconds: Minimum delay between calls in seconds

    Usage:
        @rate_limited(1.0)  # 1 second delay
        def scrape_page(url):
            return requests.get(url)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__name__

            with _rate_limit_lock:
                last_time = _last_request_time.get(func_name, 0)
                current_time = time.time()
                time_since_last = current_time - last_time

                if time_since_last < delay_seconds:
                    sleep_time = delay_seconds - time_since_last
                    logger.debug(f"Rate limiting {func_name}: sleeping {sleep_time:.2f}s")
                    time.sleep(sleep_time)

                _last_request_time[func_name] = time.time()

            return func(*args, **kwargs)

        return wrapper

    return decorator


def log_request(func: Callable) -> Callable:
    """
    Decorator to log HTTP requests for debugging

    Usage:
        @log_request
        def scrape_page(url):
            return requests.get(url)
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        func_name = func.__name__
        logger.debug(f"HTTP request: {func_name}(*{args}, **{kwargs})")

        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.debug(f"{func_name} completed in {duration:.2f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"{func_name} failed after {duration:.2f}s: {e}")
            raise

    return wrapper
