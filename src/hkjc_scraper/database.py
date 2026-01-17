"""
Database connection and session management
資料庫連線與 session 管理
"""

import logging
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from hkjc_scraper.config import config
from hkjc_scraper.models import Base

logger = logging.getLogger(__name__)

# Supabase-specific connection pool settings
if config.DATABASE_TYPE == "supabase":
    pool_config = {
        "poolclass": QueuePool,
        "pool_size": 3,  # Smaller for Supabase PgBouncer
        "max_overflow": 7,  # Total 10 connections max
        "pool_pre_ping": True,
        "pool_recycle": 300,  # Recycle connections every 5 minutes
        "connect_args": {
            "connect_timeout": config.DB_CONNECT_TIMEOUT,
            "application_name": "hkjc_scraper",
            "options": f"-c statement_timeout={config.DB_STATEMENT_TIMEOUT}"  # Query timeout in milliseconds
        },
        "echo": False,
    }
else:
    # Local PostgreSQL settings
    pool_config = {
        "poolclass": QueuePool,
        "pool_size": 5,
        "max_overflow": 10,
        "pool_pre_ping": True,
        "echo": False,
    }

# Create engine with connection pooling
engine = create_engine(config.get_db_url(), **pool_config)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """
    初始化資料庫，建立所有表格
    Initialize database and create all tables
    """
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


def drop_db():
    """
    刪除所有表格（危險操作，僅供開發使用）
    Drop all tables (dangerous, development only)
    """
    Base.metadata.drop_all(bind=engine)
    logger.warning("Database tables dropped")


def migrate_db(command: str = "upgrade", revision: str = "head"):
    """
    運行 Alembic 遷移
    Run Alembic migrations programmatically

    Args:
        command: Alembic command ('upgrade', 'downgrade', 'current', 'history')
        revision: Target revision (default: 'head' for latest)

    Examples:
        migrate_db()                    # Upgrade to latest
        migrate_db("current")           # Show current revision
        migrate_db("downgrade", "-1")   # Downgrade one revision
    """
    from pathlib import Path

    from alembic.config import Config

    from alembic import command as alembic_command

    # Get project root (database.py is in src/hkjc_scraper/)
    project_root = Path(__file__).resolve().parents[2]
    alembic_ini = project_root / "alembic.ini"

    if not alembic_ini.exists():
        raise FileNotFoundError(f"Alembic config not found at {alembic_ini}. Run 'alembic init alembic' first.")

    alembic_cfg = Config(str(alembic_ini))

    # Execute command
    if command == "upgrade":
        alembic_command.upgrade(alembic_cfg, revision)
        logger.info(f"Database migrated to revision: {revision}")
    elif command == "downgrade":
        alembic_command.downgrade(alembic_cfg, revision)
        logger.info(f"Database downgraded to revision: {revision}")
    elif command == "current":
        alembic_command.current(alembic_cfg)
    elif command == "history":
        alembic_command.history(alembic_cfg)
    else:
        raise ValueError(f"Unknown command: {command}")


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    取得資料庫 session 的 context manager
    Get database session context manager

    Usage:
        with get_db() as db:
            # Your database operations
            db.add(obj)
            db.commit()
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_connection() -> bool:
    """
    檢查資料庫連線是否正常
    Check if database connection is working

    Returns:
        bool: True if connection is successful
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_type = config.get_db_type_display()
        logger.info(f"Database connection successful ({db_type})")
        print(f"Database connection successful ({db_type})")  # Also print for user visibility
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        print(f"Database connection failed: {e}")  # Also print for user visibility
        return False


if __name__ == "__main__":
    # Test database connection and initialization
    print(f"Database URL: {config.get_db_url()}")

    if check_connection():
        print("\nInitializing database...")
        init_db()
        print("\nDatabase setup complete!")
    else:
        print("\nFailed to connect to database. Please check your .env configuration.")
