"""Tests for PostgreSQL database module.

These tests require a running PostgreSQL instance.
Set DATABASE_URL environment variable or they will be skipped.

Run with: uv run pytest tests/test_database.py -v
Requires: docker compose up db -d
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

# Skip all tests if DATABASE_URL is not set
pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set (run: docker compose up db -d)",
)


@pytest.fixture()
def db_url():
    """Get DATABASE_URL from environment."""
    return os.environ["DATABASE_URL"]


@pytest.fixture()
def db_conn(db_url):
    """Get a database connection and clean up tables after each test."""
    from hkjc_scraper.database import create_database, get_db_connection

    create_database(db_url)
    conn = get_db_connection(db_url)
    yield conn

    # Clean up all data after each test
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sectional_times")
    cursor.execute("DELETE FROM incidents")
    cursor.execute("DELETE FROM dividends")
    cursor.execute("DELETE FROM performance")
    cursor.execute("DELETE FROM horses")
    cursor.execute("DELETE FROM jockeys")
    cursor.execute("DELETE FROM trainers")
    cursor.execute("DELETE FROM races")
    conn.commit()
    conn.close()


class TestCreateDatabase:
    """Tests for create_database function."""

    def test_creates_all_tables(self, db_url) -> None:
        """Test that all required tables are created."""
        from hkjc_scraper.database import create_database, get_db_connection

        create_database(db_url)
        conn = get_db_connection(db_url)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' ORDER BY table_name
        """)
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        expected_tables = [
            "dividends",
            "horses",
            "incidents",
            "jockeys",
            "performance",
            "races",
            "sectional_times",
            "trainers",
        ]
        assert tables == expected_tables


class TestImportRaces:
    """Tests for import_races function."""

    def test_import_single_race(self, db_conn) -> None:
        """Test importing a single race record."""
        from hkjc_scraper.database import import_races

        data = [{
            "race_id": "2026-03-01-ST-1",
            "race_date": "2026/03/01",
            "race_no": 1,
            "racecourse": "沙田",
            "class": "第四班",
            "distance": 1200,
            "going": "好",
            "surface": "草地",
            "track": "草地 - \"A\"跑道",
            "rating": {"high": 60, "low": 40},
            "sectional_times": ["24.5", "22.8"],
            "prize_money": 1170000,
        }]

        count = import_races(data, db_conn)
        db_conn.commit()
        assert count == 1

        cursor = db_conn.cursor()
        cursor.execute(
            "SELECT race_date, race_no, racecourse FROM races WHERE race_id = %s",
            ("2026-03-01-ST-1",),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "2026/03/01"
        assert row[1] == 1
        assert row[2] == "沙田"

    def test_import_empty_list(self, db_conn) -> None:
        """Test importing empty list returns 0."""
        from hkjc_scraper.database import import_races

        count = import_races([], db_conn)
        assert count == 0

    def test_import_handles_json_fields(self, db_conn) -> None:
        """Test that dict/list fields are serialized as JSON."""
        from hkjc_scraper.database import import_races

        data = [{
            "race_id": "2026-03-01-ST-1",
            "race_date": "2026/03/01",
            "race_no": 1,
            "racecourse": "沙田",
            "rating": {"high": 60, "low": 40},
            "sectional_times": ["24.5", "22.8"],
            "prize_money": 0,
        }]

        import_races(data, db_conn)
        db_conn.commit()

        cursor = db_conn.cursor()
        cursor.execute(
            "SELECT rating, sectional_times FROM races WHERE race_id = %s",
            ("2026-03-01-ST-1",),
        )
        row = cursor.fetchone()
        assert row is not None
        # PostgreSQL JSONB returns Python dicts/lists directly
        assert row[0] == {"high": 60, "low": 40}
        assert row[1] == ["24.5", "22.8"]

    def test_upsert_updates_existing(self, db_conn) -> None:
        """Test that importing same race_id updates the record."""
        from hkjc_scraper.database import import_races

        data = [{
            "race_id": "2026-03-01-ST-1",
            "race_date": "2026/03/01",
            "race_no": 1,
            "racecourse": "沙田",
            "distance": 1200,
        }]
        import_races(data, db_conn)
        db_conn.commit()

        # Update distance
        data[0]["distance"] = 1400
        import_races(data, db_conn)
        db_conn.commit()

        cursor = db_conn.cursor()
        cursor.execute(
            "SELECT distance FROM races WHERE race_id = %s",
            ("2026-03-01-ST-1",),
        )
        assert cursor.fetchone()[0] == 1400


class TestImportPerformance:
    """Tests for import_performance function."""

    def test_import_performance_record(self, db_conn) -> None:
        """Test importing a performance record."""
        from hkjc_scraper.database import import_performance, import_races

        # Create prerequisite race
        import_races([{
            "race_id": "2026-03-01-ST-1",
            "race_date": "2026/03/01",
            "race_no": 1,
            "racecourse": "沙田",
        }], db_conn)
        db_conn.commit()

        data = [{
            "race_id": "2026-03-01-ST-1",
            "horse_no": "1",
            "position": "1",
            "horse_name": "Test Horse",
            "running_position": ["1", "1", "1", "1"],
        }]

        count = import_performance(data, db_conn)
        db_conn.commit()
        assert count == 1

        cursor = db_conn.cursor()
        cursor.execute(
            "SELECT horse_no, position FROM performance WHERE race_id = %s",
            ("2026-03-01-ST-1",),
        )
        row = cursor.fetchone()
        assert row[0] == "1"
        assert row[1] == "1"


class TestImportHorses:
    """Tests for import_horses function."""

    def test_import_horse_record(self, db_conn) -> None:
        """Test importing a horse profile."""
        from hkjc_scraper.database import import_horses

        data = [{
            "horse_id": "H123",
            "name": "Test Horse",
            "country_of_birth": "紐西蘭",
            "age": "4",
            "wins": 3,
            "total": 10,
        }]

        count = import_horses(data, db_conn)
        db_conn.commit()
        assert count == 1

        cursor = db_conn.cursor()
        cursor.execute("SELECT name, wins FROM horses WHERE horse_id = %s", ("H123",))
        row = cursor.fetchone()
        assert row[0] == "Test Horse"
        assert row[1] == 3


class TestImportJockeys:
    """Tests for import_jockeys function."""

    def test_import_jockey_record(self, db_conn) -> None:
        """Test importing a jockey profile."""
        from hkjc_scraper.database import import_jockeys

        data = [{
            "jockey_id": "J456",
            "name": "Test Jockey",
            "career_wins": 100,
            "season_stats": {"wins": 10, "win_rate": "12%"},
        }]

        count = import_jockeys(data, db_conn)
        db_conn.commit()
        assert count == 1


class TestImportTrainers:
    """Tests for import_trainers function."""

    def test_import_trainer_record(self, db_conn) -> None:
        """Test importing a trainer profile."""
        from hkjc_scraper.database import import_trainers

        data = [{
            "trainer_id": "T789",
            "name": "Test Trainer",
            "career_wins": 200,
        }]

        count = import_trainers(data, db_conn)
        db_conn.commit()
        assert count == 1


class TestImportDividends:
    """Tests for import_dividends function."""

    def test_import_dividend_record(self, db_conn) -> None:
        """Test importing a dividend record."""
        from hkjc_scraper.database import import_dividends, import_races

        import_races([{
            "race_id": "2026-03-01-ST-1",
            "race_date": "2026/03/01",
            "race_no": 1,
            "racecourse": "沙田",
        }], db_conn)
        db_conn.commit()

        data = [{
            "race_id": "2026-03-01-ST-1",
            "pool": "獨贏",
            "winning_combination": "1",
            "payout": "25.5",
        }]

        count = import_dividends(data, db_conn)
        db_conn.commit()
        assert count == 1


class TestImportIncidents:
    """Tests for import_incidents function."""

    def test_import_incident_record(self, db_conn) -> None:
        """Test importing an incident record."""
        from hkjc_scraper.database import import_incidents, import_races

        import_races([{
            "race_id": "2026-03-01-ST-1",
            "race_date": "2026/03/01",
            "race_no": 1,
            "racecourse": "沙田",
        }], db_conn)
        db_conn.commit()

        data = [{
            "race_id": "2026-03-01-ST-1",
            "position": "5",
            "horse_no": "3",
            "horse_name": "Test Horse",
            "incident_report": "在未過終點時受阻",
        }]

        count = import_incidents(data, db_conn)
        db_conn.commit()
        assert count == 1


class TestImportSectionalTimes:
    """Tests for import_sectional_times function."""

    def test_import_sectional_time_record(self, db_conn) -> None:
        """Test importing a sectional time record."""
        from hkjc_scraper.database import import_races, import_sectional_times

        import_races([{
            "race_id": "2026-03-01-ST-1",
            "race_date": "2026/03/01",
            "race_no": 1,
            "racecourse": "沙田",
        }], db_conn)
        db_conn.commit()

        data = [{
            "race_id": "2026-03-01-ST-1",
            "horse_no": "1",
            "section_number": 1,
            "position": 1,
            "margin": "0.5",
            "time": 24.5,
        }]

        count = import_sectional_times(data, db_conn)
        db_conn.commit()
        assert count == 1


class TestExportJsonToDb:
    """Tests for export_json_to_db function."""

    def test_export_creates_records(self, db_url) -> None:
        """Test that export imports records from JSON files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            races_data = [{
                "race_id": "2026-03-01-ST-1",
                "race_date": "2026/03/01",
                "race_no": 1,
                "racecourse": "沙田",
                "distance": 1200,
            }]
            with open(data_dir / "races_2026-03-01.json", "w", encoding="utf-8") as f:
                json.dump(races_data, f)

            from hkjc_scraper.database import export_json_to_db

            counts = export_json_to_db(data_dir, db_url)
            assert "races" in counts
            assert counts["races"] == 1

        # Clean up
        conn = __import__("psycopg2").connect(db_url)
        conn.cursor().execute("DELETE FROM races")
        conn.commit()
        conn.close()

    def test_export_nonexistent_dir_raises_error(self, db_url) -> None:
        """Test export with non-existent directory raises error."""
        from hkjc_scraper.database import export_json_to_db

        with pytest.raises(FileNotFoundError):
            export_json_to_db("/nonexistent/path", db_url)


class TestLoadFromDb:
    """Tests for load_from_db function."""

    def test_load_all_from_table(self, db_conn, db_url) -> None:
        """Test loading all records from a table."""
        from hkjc_scraper.database import import_races, load_from_db

        import_races([
            {"race_id": "2026-03-01-ST-1", "race_date": "2026/03/01", "race_no": 1, "racecourse": "沙田"},
            {"race_id": "2026-03-01-ST-2", "race_date": "2026/03/01", "race_no": 2, "racecourse": "沙田"},
        ], db_conn)
        db_conn.commit()

        races = load_from_db("races", database_url=db_url)
        assert len(races) == 2

    def test_load_with_where_clause(self, db_conn, db_url) -> None:
        """Test loading records with WHERE clause."""
        from hkjc_scraper.database import import_races, load_from_db

        import_races([
            {"race_id": "2026-03-01-ST-1", "race_date": "2026/03/01", "race_no": 1, "racecourse": "沙田"},
            {"race_id": "2026-03-01-HV-1", "race_date": "2026/03/01", "race_no": 1, "racecourse": "谷草"},
        ], db_conn)
        db_conn.commit()

        hv_races = load_from_db("races", "racecourse = %s", ("谷草",), database_url=db_url)
        assert len(hv_races) == 1
        assert hv_races[0]["racecourse"] == "谷草"

    def test_load_empty_table(self, db_url) -> None:
        """Test loading from empty table."""
        from hkjc_scraper.database import load_from_db

        races = load_from_db("races", database_url=db_url)
        assert races == []
