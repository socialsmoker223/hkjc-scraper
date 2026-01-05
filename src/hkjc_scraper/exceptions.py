"""
Custom exceptions for HKJC scraper
"""


class HKJCScraperError(Exception):
    """Base exception for HKJC scraper"""

    pass


class NetworkError(HKJCScraperError):
    """Network-related errors (retryable)"""

    pass


class ParseError(HKJCScraperError):
    """Data parsing errors (not retryable)"""

    pass


class DataValidationError(HKJCScraperError):
    """Data validation errors (not retryable)"""

    pass
