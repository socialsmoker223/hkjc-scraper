"""Integration tests for PostgreSQL database schema and constraints.

These tests verify:
- Database creation with correct schema
- Foreign key constraints
- Index creation
- Edge cases (NULL values, special characters)

Requires: docker compose up db -d
Set DATABASE_URL environment variable.
"""

import os

import psycopg2
import pytest

from hkjc_scraper.database import (
    create_database,
    get_db_connection,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("DATABASE_URL"),
        reason="DATABASE_URL not set (run: docker compose up db -d)",
    ),
]


@pytest.fixture()
def db_url():
    return os.environ["DATABASE_URL"]


@pytest.fixture()
def db_conn(db_url):
    """Get a database connection and clean up after each test."""
    create_database(db_url)
    conn = get_db_connection(db_url)
    yield conn

    cursor = conn.cursor()
    for table in [
        "sectional_times", "incidents", "dividends",
        "performance", "horses", "jockeys", "trainers", "races",
    ]:
        cursor.execute(f"DELETE FROM {table}")
    conn.commit()
    conn.close()


class TestDatabaseCreation:
    """Test database schema creation and structure."""

    def test_creates_all_tables(self, db_url) -> None:
        """Verify all 8 tables are created with correct schema."""
        create_database(db_url)
        conn = get_db_connection(db_url)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' ORDER BY table_name
        """)
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        expected = {
            "races", "horses", "jockeys", "trainers",
            "performance", "dividends", "incidents", "sectional_times",
        }
        assert tables == expected

    def test_indexes_created(self, db_url) -> None:
        """Verify all expected indexes are created."""
        create_database(db_url)
        conn = get_db_connection(db_url)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT indexname FROM pg_indexes WHERE schemaname = 'public'
        """)
        indexes = {row[0] for row in cursor.fetchall()}
        conn.close()

        expected_indexes = {
            "idx_races_race_date",
            "idx_races_racecourse",
            "idx_races_date_course",
            "idx_horses_name",
            "idx_horses_trainer",
            "idx_jockeys_name",
            "idx_trainers_name",
            "idx_performance_race_id",
            "idx_performance_horse_id",
            "idx_performance_jockey_id",
            "idx_performance_trainer_id",
            "idx_performance_position",
            "idx_dividends_race_id",
            "idx_incidents_race_id",
            "idx_incidents_horse_no",
            "idx_sectional_times_race_id",
            "idx_sectional_times_horse_no",
            "idx_sectional_times_race_horse",
        }
        assert expected_indexes.issubset(indexes), f"Missing: {expected_indexes - indexes}"


class TestForeignKeyConstraints:
    """Test foreign key constraint enforcement."""

    def test_performance_requires_valid_race_id(self, db_conn) -> None:
        """Test that performance record requires valid race_id."""
        cursor = db_conn.cursor()

        with pytest.raises(psycopg2.IntegrityError):
            cursor.execute(
                """INSERT INTO performance (race_id, horse_no, position, horse_name)
                   VALUES (%s, %s, %s, %s)""",
                ("nonexistent-race", "1", "1", "Test Horse"),
            )

        db_conn.rollback()

    def test_cascade_delete_on_race_removal(self, db_conn) -> None:
        """Test that deleting a race cascades to related records."""
        cursor = db_conn.cursor()

        cursor.execute(
            """INSERT INTO races (race_id, race_date, race_no, racecourse)
               VALUES (%s, %s, %s, %s)""",
            ("2026-03-01-ST-1", "2026/03/01", 1, "沙田"),
        )
        cursor.execute(
            """INSERT INTO performance (race_id, horse_no, position, horse_name)
               VALUES (%s, %s, %s, %s)""",
            ("2026-03-01-ST-1", "1", "1", "Test Horse"),
        )
        cursor.execute(
            """INSERT INTO dividends (race_id, pool)
               VALUES (%s, %s)""",
            ("2026-03-01-ST-1", "獨贏"),
        )
        db_conn.commit()

        cursor.execute("DELETE FROM races WHERE race_id = %s", ("2026-03-01-ST-1",))
        db_conn.commit()

        cursor.execute("SELECT COUNT(*) FROM performance WHERE race_id = %s", ("2026-03-01-ST-1",))
        assert cursor.fetchone()[0] == 0

        cursor.execute("SELECT COUNT(*) FROM dividends WHERE race_id = %s", ("2026-03-01-ST-1",))
        assert cursor.fetchone()[0] == 0

    def test_null_foreign_keys_allowed_in_performance(self, db_conn) -> None:
        """Test that NULL foreign keys are allowed in performance table."""
        cursor = db_conn.cursor()

        cursor.execute(
            """INSERT INTO races (race_id, race_date, race_no, racecourse)
               VALUES (%s, %s, %s, %s)""",
            ("2026-03-01-ST-1", "2026/03/01", 1, "沙田"),
        )
        cursor.execute(
            """INSERT INTO performance (race_id, horse_no, position, horse_name,
               horse_id, jockey_id, trainer_id) VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            ("2026-03-01-ST-1", "1", "1", "Test Horse", None, None, None),
        )
        db_conn.commit()

        cursor.execute(
            "SELECT horse_id, jockey_id, trainer_id FROM performance WHERE horse_no = %s", ("1",)
        )
        row = cursor.fetchone()
        assert row == (None, None, None)


class TestDataIntegrity:
    """Test data integrity and constraints."""

    def test_primary_key_uniqueness_races(self, db_conn) -> None:
        """Test that race_id primary key is unique."""
        cursor = db_conn.cursor()

        cursor.execute(
            """INSERT INTO races (race_id, race_date, race_no, racecourse)
               VALUES (%s, %s, %s, %s)""",
            ("2026-03-01-ST-1", "2026/03/01", 1, "沙田"),
        )

        with pytest.raises(psycopg2.IntegrityError):
            cursor.execute(
                """INSERT INTO races (race_id, race_date, race_no, racecourse)
                   VALUES (%s, %s, %s, %s)""",
                ("2026-03-01-ST-1", "2026/03/01", 1, "沙田"),
            )

        db_conn.rollback()

    def test_special_characters_in_text_fields(self, db_conn) -> None:
        """Test that special characters are handled correctly."""
        cursor = db_conn.cursor()

        special_track = '草地 - "A"跑道 (測試\'特殊\\字符)'
        cursor.execute(
            """INSERT INTO races (race_id, race_date, race_no, racecourse, track)
               VALUES (%s, %s, %s, %s, %s)""",
            ("2026-03-01-ST-99", "2026/03/01", 99, "沙田", special_track),
        )
        db_conn.commit()

        cursor.execute("SELECT track FROM races WHERE race_id = %s", ("2026-03-01-ST-99",))
        assert '草地 - "A"跑道' in cursor.fetchone()[0]


class TestDefaultValues:
    """Test default value constraints."""

    def test_default_values_horses(self, db_conn) -> None:
        """Test default values in horses table."""
        cursor = db_conn.cursor()

        cursor.execute(
            "INSERT INTO horses (horse_id, name) VALUES (%s, %s)",
            ("H001", "Test Horse"),
        )
        db_conn.commit()

        cursor.execute(
            "SELECT wins, places, shows, total, season_prize, total_prize FROM horses WHERE horse_id = %s",
            ("H001",),
        )
        assert cursor.fetchone() == (0, 0, 0, 0, 0, 0)

    def test_metadata_timestamps(self, db_conn) -> None:
        """Test that created_at timestamps are set."""
        cursor = db_conn.cursor()

        cursor.execute(
            """INSERT INTO races (race_id, race_date, race_no, racecourse)
               VALUES (%s, %s, %s, %s)""",
            ("2026-03-01-ST-1", "2026/03/01", 1, "沙田"),
        )
        db_conn.commit()

        cursor.execute("SELECT created_at FROM races WHERE race_id = %s", ("2026-03-01-ST-1",))
        assert cursor.fetchone()[0] is not None


class TestDatabaseRecreation:
    """Test database behavior when run multiple times."""

    def test_create_database_idempotent(self, db_url) -> None:
        """Test that create_database can be called multiple times safely."""
        create_database(db_url)

        conn = get_db_connection(db_url)
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO races (race_id, race_date, race_no, racecourse)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT DO NOTHING""",
            ("idempotent-test", "2026/03/01", 1, "沙田"),
        )
        conn.commit()
        conn.close()

        # Call create_database again
        create_database(db_url)

        conn = get_db_connection(db_url)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM races WHERE race_id = %s", ("idempotent-test",))
        assert cursor.fetchone()[0] == 1

        # Clean up
        cursor.execute("DELETE FROM races WHERE race_id = %s", ("idempotent-test",))
        conn.commit()
        conn.close()
