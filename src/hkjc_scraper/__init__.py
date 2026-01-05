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
    HorseProfile,
    HorseProfileHistory,
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


def setup_logging(level=logging.INFO):
    """Setup package-level logging"""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("hkjc_scraper.log", encoding="utf-8")],
    )


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
    "HorseProfile",
    "HorseProfileHistory",
    "Jockey",
    "Trainer",
    "Runner",
    "HorseSectional",
    # Config
    "config",
]
