"""
HKJC Racing Data Scraper
香港賽馬會賽事資料抓取工具

A Python web scraper that collects horse racing data from the Hong Kong Jockey Club (HKJC)
website and stores it in a PostgreSQL database.
"""

import logging
import sys

from hkjc_scraper.config import config
from hkjc_scraper.database import check_connection, get_db, init_db
from hkjc_scraper.models import (
    Base,
    Horse,
    HorseHistory,
    HorseSectional,
    Jockey,
    Meeting,
    Race,
    Runner,
    Trainer,
)
from hkjc_scraper.persistence import save_meeting_data
from hkjc_scraper.scraper import scrape_meeting

__version__ = "0.1.0"


def setup_logging(level=None, log_file=None):
    """Setup package-level logging with config support"""
    # Import config here to avoid circular dependency
    from hkjc_scraper import config as cfg

    # Use config values if not explicitly provided
    if level is None:
        level_str = cfg.LOG_LEVEL.upper()
        level = getattr(logging, level_str, logging.INFO)

    if log_file is None:
        log_file = cfg.LOG_FILE

    # Create formatters
    detailed_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    console_formatter = logging.Formatter("%(message)s")  # Simplified for console

    # Console handler (stdout) - shows INFO and above with simple format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    # File handler - shows everything with detailed format
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


# Setup logging on import
setup_logging()

__all__ = [
    "__version__",
    # Scraping
    "scrape_meeting",
    # Database
    "get_db",
    "init_db",
    "check_connection",
    # Persistence
    "save_meeting_data",
    # Models
    "Base",
    "Meeting",
    "Race",
    "Horse",
    "HorseHistory",
    "Jockey",
    "Trainer",
    "Runner",
    "HorseSectional",
    # Config
    "config",
]
