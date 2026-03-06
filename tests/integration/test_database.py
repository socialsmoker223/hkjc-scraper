"""Integration tests for SQLite database schema and constraints.

These tests verify:
- Database creation with correct schema
- Foreign key constraints
- Index creation
- Edge cases (NULL values, special characters)
"""

import sqlite3
from pathlib import Path

import pytest

from hkjc_scraper.database import (
    create_database,
    get_db_connection,
)


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Create a temporary database path.

    Args:
        tmp_path: Pytest temporary path fixture

    Returns:
        Path to temporary database file
    """
    return tmp_path / "test_hkjc.db"


@pytest.mark.integration
class TestDatabaseCreation:
    """Test database schema creation and structure."""

    def test_creates_all_tables(self, temp_db_path: Path) -> None:
        """Verify all 8 tables are created with correct schema."""
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)
        cursor = conn.cursor()

        # Get all table names
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = {row[0] for row in cursor.fetchall()}

        expected_tables = {
            "races",
            "horses",
            "jockeys",
            "trainers",
            "performance",
            "dividends",
            "incidents",
            "sectional_times",
        }
        assert tables == expected_tables, f"Missing tables: {expected_tables - tables}"

        conn.close()

    def test_races_table_schema(self, temp_db_path: Path) -> None:
        """Verify races table has correct columns and types."""
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(races)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        # Verify key columns exist
        expected_columns = {
            "race_id": "TEXT",
            "race_date": "TEXT",
            "race_no": "INTEGER",
            "racecourse": "TEXT",
            "class": "TEXT",
            "distance": "INTEGER",
            "going": "TEXT",
            "surface": "TEXT",
            "track": "TEXT",
            "prize_money": "INTEGER",
            "race_name": "TEXT",
        }

        for col, expected_type in expected_columns.items():
            assert col in columns, f"Missing column: {col}"
            assert columns[col] == expected_type, f"Column {col} has wrong type: {columns[col]}"

        conn.close()

    def test_performance_table_schema(self, temp_db_path: Path) -> None:
        """Verify performance table has correct columns and types."""
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(performance)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected_columns = {
            "id": "INTEGER",
            "race_id": "TEXT",
            "horse_id": "TEXT",
            "jockey_id": "TEXT",
            "trainer_id": "TEXT",
            "horse_no": "TEXT",
            "position": "TEXT",
            "horse_name": "TEXT",
            "jockey": "TEXT",
            "trainer": "TEXT",
            "actual_weight": "TEXT",
            "body_weight": "TEXT",
            "draw": "TEXT",
            "margin": "TEXT",
            "finish_time": "TEXT",
            "win_odds": "TEXT",
            "running_position": "TEXT",
        }

        for col, expected_type in expected_columns.items():
            assert col in columns, f"Missing column: {col}"
            assert columns[col] == expected_type, f"Column {col} has wrong type: {columns[col]}"

        conn.close()

    def test_horses_table_schema(self, temp_db_path: Path) -> None:
        """Verify horses table has correct columns and types."""
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(horses)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected_columns = {
            "horse_id": "TEXT",
            "name": "TEXT",
            "country_of_birth": "TEXT",
            "age": "TEXT",
            "colour": "TEXT",
            "gender": "TEXT",
            "sire": "TEXT",
            "dam": "TEXT",
            "damsire": "TEXT",
            "trainer": "TEXT",
            "owner": "TEXT",
            "current_rating": "INTEGER",
            "initial_rating": "INTEGER",
            "season_prize": "INTEGER",
            "total_prize": "INTEGER",
            "wins": "INTEGER",
            "places": "INTEGER",
            "shows": "INTEGER",
            "total": "INTEGER",
        }

        for col, expected_type in expected_columns.items():
            assert col in columns, f"Missing column: {col}"
            assert columns[col] == expected_type, f"Column {col} has wrong type: {columns[col]}"

        conn.close()

    def test_foreign_keys_enabled(self, temp_db_path: Path) -> None:
        """Verify foreign key constraints are enabled."""
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)
        cursor = conn.cursor()

        # Check if foreign keys are enabled
        cursor.execute("PRAGMA foreign_keys")
        fk_enabled = cursor.fetchone()[0]
        assert fk_enabled == 1, "Foreign keys should be enabled"

        conn.close()

    def test_indexes_created(self, temp_db_path: Path) -> None:
        """Verify all expected indexes are created."""
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}

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

        assert expected_indexes.issubset(
            indexes
        ), f"Missing indexes: {expected_indexes - indexes}"

        conn.close()


@pytest.mark.integration
class TestForeignKeysConstraints:
    """Test foreign key constraint enforcement."""

    def test_performance_requires_valid_race_id(self, temp_db_path: Path) -> None:
        """Test that performance record requires valid race_id."""
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)

        # Try to insert performance without race
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO performance (race_id, horse_no, position, horse_name)
                   VALUES (?, ?, ?, ?)""",
                ("nonexistent-race", "1", "1", "Test Horse"),
            )
            conn.commit()

        conn.close()

    def test_dividend_requires_valid_race_id(self, temp_db_path: Path) -> None:
        """Test that dividend record requires valid race_id."""
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO dividends (race_id, pool)
                   VALUES (?, ?)""",
                ("nonexistent-race", "獨贏"),
            )
            conn.commit()

        conn.close()

    def test_incident_requires_valid_race_id(self, temp_db_path: Path) -> None:
        """Test that incident record requires valid race_id."""
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO incidents (race_id, horse_no, horse_name)
                   VALUES (?, ?, ?)""",
                ("nonexistent-race", "1", "Test Horse"),
            )
            conn.commit()

        conn.close()

    def test_sectional_time_requires_valid_race_id(self, temp_db_path: Path) -> None:
        """Test that sectional_time record requires valid race_id."""
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO sectional_times (race_id, horse_no, section_number)
                   VALUES (?, ?, ?)""",
                ("nonexistent-race", "1", 1),
            )
            conn.commit()

        conn.close()

    def test_cascade_delete_on_race_removal(self, temp_db_path: Path) -> None:
        """Test that deleting a race cascades to related records."""
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)
        cursor = conn.cursor()

        # Insert a race
        cursor.execute(
            """INSERT INTO races (race_id, race_date, race_no, racecourse)
               VALUES (?, ?, ?, ?)""",
            ("2026-03-01-ST-1", "2026/03/01", 1, "沙田"),
        )

        # Insert related records
        cursor.execute(
            """INSERT INTO performance (race_id, horse_no, position, horse_name)
               VALUES (?, ?, ?, ?)""",
            ("2026-03-01-ST-1", "1", "1", "Test Horse"),
        )
        cursor.execute(
            """INSERT INTO dividends (race_id, pool)
               VALUES (?, ?)""",
            ("2026-03-01-ST-1", "獨贏"),
        )
        conn.commit()

        # Verify records exist
        cursor.execute("SELECT COUNT(*) FROM performance WHERE race_id = ?", ("2026-03-01-ST-1",))
        assert cursor.fetchone()[0] == 1

        # Delete race
        cursor.execute("DELETE FROM races WHERE race_id = ?", ("2026-03-01-ST-1",))
        conn.commit()

        # Verify related records are deleted (cascade)
        cursor.execute("SELECT COUNT(*) FROM performance WHERE race_id = ?", ("2026-03-01-ST-1",))
        assert cursor.fetchone()[0] == 0

        cursor.execute("SELECT COUNT(*) FROM dividends WHERE race_id = ?", ("2026-03-01-ST-1",))
        assert cursor.fetchone()[0] == 0

        conn.close()

    def test_null_foreign_keys_allowed_in_performance(self, temp_db_path: Path) -> None:
        """Test that NULL foreign keys are allowed in performance table."""
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)
        cursor = conn.cursor()

        # Insert a race
        cursor.execute(
            """INSERT INTO races (race_id, race_date, race_no, racecourse)
               VALUES (?, ?, ?, ?)""",
            ("2026-03-01-ST-1", "2026/03/01", 1, "沙田"),
        )

        # Insert performance with NULL foreign keys (horse_id, jockey_id, trainer_id)
        cursor.execute(
            """INSERT INTO performance (race_id, horse_no, position, horse_name, horse_id, jockey_id, trainer_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("2026-03-01-ST-1", "1", "1", "Test Horse", None, None, None),
        )
        conn.commit()

        # Verify record was inserted
        cursor.execute(
            "SELECT horse_id, jockey_id, trainer_id FROM performance WHERE horse_no = ?", ("1",)
        )
        row = cursor.fetchone()

        assert row is not None
        assert row[0] is None  # horse_id
        assert row[1] is None  # jockey_id
        assert row[2] is None  # trainer_id

        conn.close()


@pytest.mark.integration
class TestDataIntegrity:
    """Test data integrity and constraints."""

    def test_primary_key_uniqueness_races(self, temp_db_path: Path) -> None:
        """Test that race_id primary key is unique."""
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)
        cursor = conn.cursor()

        # Insert same race twice
        cursor.execute(
            """INSERT INTO races (race_id, race_date, race_no, racecourse)
               VALUES (?, ?, ?, ?)""",
            ("2026-03-01-ST-1", "2026/03/01", 1, "沙田"),
        )

        # Second insert with same race_id should fail
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                """INSERT INTO races (race_id, race_date, race_no, racecourse)
                   VALUES (?, ?, ?, ?)""",
                ("2026-03-01-ST-1", "2026/03/01", 1, "沙田"),
            )
            conn.commit()

        conn.close()

    def test_unique_constraint_performance(self, temp_db_path: Path) -> None:
        """Test UNIQUE(race_id, horse_no) constraint in performance table."""
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)
        cursor = conn.cursor()

        # Insert a race
        cursor.execute(
            """INSERT INTO races (race_id, race_date, race_no, racecourse)
               VALUES (?, ?, ?, ?)""",
            ("2026-03-01-ST-1", "2026/03/01", 1, "沙田"),
        )

        # Insert performance record
        cursor.execute(
            """INSERT INTO performance (race_id, horse_no, position, horse_name)
               VALUES (?, ?, ?, ?)""",
            ("2026-03-01-ST-1", "1", "1", "Test Horse"),
        )

        # Try to insert duplicate horse_no for same race
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                """INSERT INTO performance (race_id, horse_no, position, horse_name)
                   VALUES (?, ?, ?, ?)""",
                ("2026-03-01-ST-1", "1", "2", "Test Horse"),
            )
            conn.commit()

        conn.close()

    def test_unique_constraint_dividends(self, temp_db_path: Path) -> None:
        """Test UNIQUE(race_id, pool) constraint in dividends table."""
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)
        cursor = conn.cursor()

        # Insert a race
        cursor.execute(
            """INSERT INTO races (race_id, race_date, race_no, racecourse)
               VALUES (?, ?, ?, ?)""",
            ("2026-03-01-ST-1", "2026/03/01", 1, "沙田"),
        )

        # Insert dividend record
        cursor.execute(
            """INSERT INTO dividends (race_id, pool, winning_combination)
               VALUES (?, ?, ?)""",
            ("2026-03-01-ST-1", "獨贏", "1"),
        )

        # Try to insert duplicate pool for same race
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                """INSERT INTO dividends (race_id, pool, winning_combination)
                   VALUES (?, ?, ?)""",
                ("2026-03-01-ST-1", "獨贏", "2"),
            )
            conn.commit()

        conn.close()

    def test_unique_constraint_sectional_times(self, temp_db_path: Path) -> None:
        """Test UNIQUE(race_id, horse_no, section_number) constraint."""
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)
        cursor = conn.cursor()

        # Insert a race
        cursor.execute(
            """INSERT INTO races (race_id, race_date, race_no, racecourse)
               VALUES (?, ?, ?, ?)""",
            ("2026-03-01-ST-1", "2026/03/01", 1, "沙田"),
        )

        # Insert sectional time record
        cursor.execute(
            """INSERT INTO sectional_times (race_id, horse_no, section_number, time)
               VALUES (?, ?, ?, ?)""",
            ("2026-03-01-ST-1", "1", 1, 24.5),
        )

        # Try to insert duplicate section for same horse/race
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                """INSERT INTO sectional_times (race_id, horse_no, section_number, time)
                   VALUES (?, ?, ?, ?)""",
                ("2026-03-01-ST-1", "1", 1, 25.0),
            )
            conn.commit()

        conn.close()

    def test_special_characters_in_text_fields(self, temp_db_path: Path) -> None:
        """Test that special characters are handled correctly."""
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)
        cursor = conn.cursor()

        # Insert race with special characters
        special_track = '草地 - "A"跑道 (測試\'特殊\\字符)'
        cursor.execute(
            """INSERT INTO races (race_id, race_date, race_no, racecourse, track)
               VALUES (?, ?, ?, ?, ?)""",
            ("2026-03-01-ST-99", "2026/03/01", 99, "沙田", special_track),
        )
        conn.commit()

        # Verify data was stored correctly
        cursor.execute("SELECT track FROM races WHERE race_id = ?", ("2026-03-01-ST-99",))
        track = cursor.fetchone()[0]

        assert '草地 - "A"跑道' in track

        conn.close()


@pytest.mark.integration
class TestDefaultValues:
    """Test default value constraints."""

    def test_default_values_performance(self, temp_db_path: Path) -> None:
        """Test default values in performance table."""
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)
        cursor = conn.cursor()

        # Insert a race
        cursor.execute(
            """INSERT INTO races (race_id, race_date, race_no, racecourse)
               VALUES (?, ?, ?, ?)""",
            ("2026-03-01-ST-1", "2026/03/01", 1, "沙田"),
        )

        # Insert performance with minimal fields
        cursor.execute(
            """INSERT INTO performance (race_id, horse_no, position, horse_name)
               VALUES (?, ?, ?, ?)""",
            ("2026-03-01-ST-1", "1", "1", "Test Horse"),
        )
        conn.commit()

        # Verify auto-generated id exists
        cursor.execute("SELECT id FROM performance WHERE horse_no = ?", ("1",))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] is not None  # Auto-generated id

        conn.close()

    def test_default_values_horses(self, temp_db_path: Path) -> None:
        """Test default values in horses table."""
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)
        cursor = conn.cursor()

        # Insert horse with minimal fields
        cursor.execute(
            """INSERT INTO horses (horse_id, name)
               VALUES (?, ?)""",
            ("H001", "Test Horse"),
        )
        conn.commit()

        # Verify default values
        cursor.execute(
            """SELECT wins, places, shows, total, season_prize, total_prize
               FROM horses WHERE horse_id = ?""",
            ("H001",),
        )
        row = cursor.fetchone()

        assert row == (0, 0, 0, 0, 0, 0)

        conn.close()

    def test_default_values_jockeys(self, temp_db_path: Path) -> None:
        """Test default values in jockeys table."""
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)
        cursor = conn.cursor()

        # Insert jockey with minimal fields
        cursor.execute(
            """INSERT INTO jockeys (jockey_id, name)
               VALUES (?, ?)""",
            ("J001", "Test Jockey"),
        )
        conn.commit()

        # Verify default values
        cursor.execute(
            """SELECT career_wins FROM jockeys WHERE jockey_id = ?""",
            ("J001",),
        )
        row = cursor.fetchone()

        assert row == (0,)

        conn.close()

    def test_metadata_timestamps(self, temp_db_path: Path) -> None:
        """Test that created_at timestamps are set."""
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)
        cursor = conn.cursor()

        # Insert a race
        cursor.execute(
            """INSERT INTO races (race_id, race_date, race_no, racecourse)
               VALUES (?, ?, ?, ?)""",
            ("2026-03-01-ST-1", "2026/03/01", 1, "沙田"),
        )
        conn.commit()

        # Verify created_at is set
        cursor.execute("SELECT created_at FROM races WHERE race_id = ?", ("2026-03-01-ST-1",))
        row = cursor.fetchone()

        assert row is not None
        assert row[0] is not None  # Timestamp should be set

        conn.close()


@pytest.mark.integration
class TestDatabaseRecreation:
    """Test database behavior when run multiple times."""

    def test_create_database_idempotent(self, temp_db_path: Path) -> None:
        """Test that create_database can be called multiple times safely."""
        # Create database first time
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO races (race_id, race_date, race_no, racecourse)
               VALUES (?, ?, ?, ?)""",
            ("2026-03-01-ST-1", "2026/03/01", 1, "沙田"),
        )
        conn.commit()
        conn.close()

        # Create database again (should use existing tables)
        create_database(temp_db_path)

        # Verify data still exists
        conn = get_db_connection(temp_db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM races")
        count = cursor.fetchone()[0]

        assert count == 1, "Data should persist after recreate"

        conn.close()

    def test_add_missing_tables_on_recreate(self, temp_db_path: Path) -> None:
        """Test that missing tables are added when calling create_database."""
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)
        cursor = conn.cursor()

        # Verify all tables exist
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables_before = {row[0] for row in cursor.fetchall()}
        conn.close()

        # Call create_database again
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables_after = {row[0] for row in cursor.fetchall()}

        assert tables_before == tables_after

        conn.close()


@pytest.mark.integration
class TestConnectionHelper:
    """Test database connection helper functions."""

    def test_get_db_connection_enables_foreign_keys(self, tmp_path: Path) -> None:
        """Test that get_db_connection enables foreign keys."""
        db_path = tmp_path / "test.db"

        # Create empty database
        import sqlite3 as sqlite
        sqlite.connect(db_path).close()

        conn = get_db_connection(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA foreign_keys")
        fk_enabled = cursor.fetchone()[0]

        assert fk_enabled == 1, "get_db_connection should enable foreign keys"

        conn.close()

    def test_get_db_connection_returns_valid_connection(self, temp_db_path: Path) -> None:
        """Test that get_db_connection returns a working connection."""
        create_database(temp_db_path)

        conn = get_db_connection(temp_db_path)
        cursor = conn.cursor()

        # Should be able to execute queries
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()

        assert len(tables) > 0

        conn.close()
