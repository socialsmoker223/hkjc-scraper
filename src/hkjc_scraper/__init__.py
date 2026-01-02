"""
HKJC Racing Data Scraper
香港賽馬會賽事資料抓取工具

A Python web scraper that collects horse racing data from the Hong Kong Jockey Club (HKJC)
website and stores it in a PostgreSQL database.
"""

__version__ = "0.1.0"

# Export main scraping function
# Export config
from hkjc_scraper.config import config

# Export database functions
from hkjc_scraper.database import check_connection, get_db, init_db

# Export models
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

# Export persistence functions
from hkjc_scraper.persistence import save_meeting_data
from hkjc_scraper.scraper import scrape_meeting

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
