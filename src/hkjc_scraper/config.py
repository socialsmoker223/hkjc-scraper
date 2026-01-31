"""
Configuration management for HKJC scraper
從環境變數或 .env 檔案載入設定
"""

import os

from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()


class Config:
    """Application configuration"""

    # Database type selection
    DATABASE_TYPE = os.getenv("DATABASE_TYPE", "local")  # "local" or "supabase"

    # Local PostgreSQL settings
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "5432"))
    DB_NAME = os.getenv("DB_NAME", "hkjc_racing")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    # Supabase settings
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")

    # Database timeout settings (for Supabase)
    DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "30"))  # Connection timeout in seconds
    DB_STATEMENT_TIMEOUT = int(os.getenv("DB_STATEMENT_TIMEOUT", "60000"))  # Query timeout in milliseconds

    @classmethod
    def get_db_url(cls) -> str:
        """
        Build SQLAlchemy database connection URL based on DATABASE_TYPE
        建構 SQLAlchemy 資料庫連線 URL（根據 DATABASE_TYPE）
        """
        if cls.DATABASE_TYPE == "supabase":
            if not cls.SUPABASE_URL:
                raise ValueError("SUPABASE_URL must be set when DATABASE_TYPE=supabase")
            return cls.SUPABASE_URL
        else:
            # Local PostgreSQL (default)
            return f"postgresql://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"

    @classmethod
    def get_db_type_display(cls) -> str:
        """Get human-readable database type for logging"""
        return "Supabase (Cloud PostgreSQL)" if cls.DATABASE_TYPE == "supabase" else "Local PostgreSQL"

    # Scraping settings
    HKJC_BASE_URL = os.getenv("HKJC_BASE_URL", "https://racing.hkjc.com/racing/information/Chinese")
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "15"))
    REQUEST_CONNECT_TIMEOUT = int(os.getenv("REQUEST_CONNECT_TIMEOUT", "5"))
    RATE_LIMIT_DELAY = float(os.getenv("RATE_LIMIT_DELAY", "1.0"))

    # Error handling & retry settings
    RETRY_MAX_ATTEMPTS = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
    RETRY_BACKOFF_BASE = int(os.getenv("RETRY_BACKOFF_BASE", "2"))
    RATE_LIMIT_RACE = float(os.getenv("RATE_LIMIT_RACE", "0.3"))  # Reduced for concurrent execution
    RATE_LIMIT_DETAIL = float(os.getenv("RATE_LIMIT_DETAIL", "0.2"))  # Reduced for concurrent execution

    # Concurrency settings
    MAX_RACE_WORKERS = int(os.getenv("MAX_RACE_WORKERS", "4"))  # Concurrent race scraping
    MAX_PROFILE_WORKERS = int(os.getenv("MAX_PROFILE_WORKERS", "8"))  # Concurrent profile scraping

    # HK33 scraping settings
    HK33_BASE_URL = "https://horse.hk33.com/analysis"
    HK33_REQUEST_TIMEOUT = int(os.getenv("HK33_REQUEST_TIMEOUT", "30"))
    HK33_EMAIL = os.getenv("HK33_EMAIL", "")
    HK33_PASSWORD = os.getenv("HK33_PASSWORD", "")

    # HK33 session recovery
    HK33_MAX_RELOGINS = int(os.getenv("HK33_MAX_RELOGINS", "3"))
    HK33_LOGIN_URL = "https://www.hk33.com/zh-yue/user-ajaj/user.login.ajaj"

    # HK33 adaptive rate limiting
    RATE_LIMIT_HK33_SAME_PATH = float(os.getenv("RATE_LIMIT_HK33_SAME_PATH", "0.3"))  # Same endpoint, different params
    RATE_LIMIT_HK33_PATH_CHANGE = float(os.getenv("RATE_LIMIT_HK33_PATH_CHANGE", "15.0"))  # Different endpoint

    # HK33 concurrency settings
    MAX_HK33_RACE_WORKERS = int(
        os.getenv("MAX_HK33_RACE_WORKERS", "2")
    )  # Concurrent HK33 race scraping (reduced to avoid 429)
    MAX_HK33_ODDS_WORKERS = int(os.getenv("MAX_HK33_ODDS_WORKERS", "6"))  # Concurrent odds type scraping per race

    # Logging settings
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "hkjc_scraper.log")


# Singleton config instance
config = Config()
