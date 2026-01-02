"""
Database connection and session management
資料庫連線與 session 管理
"""
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from hkjc_scraper.config import config
from hkjc_scraper.models import Base

# Create engine with connection pooling
engine = create_engine(
    config.get_db_url(),
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # Verify connections before using
    echo=False,  # Set to True for SQL debugging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """
    初始化資料庫，建立所有表格
    Initialize database and create all tables
    """
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully")


def drop_db():
    """
    刪除所有表格（危險操作，僅供開發使用）
    Drop all tables (dangerous, development only)
    """
    Base.metadata.drop_all(bind=engine)
    print("Database tables dropped")


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
        print("Database connection successful")
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
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
