"""SQLite database schema for HKJC racing data.

This module defines the database schema for storing horse racing data extracted
from the HKJC website. It includes tables for races, performances, dividends,
incidents, horses, jockeys, trainers, and sectional times.

The schema is designed with:
- Proper primary keys and foreign keys with ON DELETE behavior
- Indexes on frequently queried columns
- Appropriate SQLite data types (INTEGER, TEXT, REAL)
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Literal


def create_database(db_path: str | Path) -> None:
    """Create the SQLite database schema with all tables and indexes.

    This function creates a new SQLite database at the specified path with
    all required tables, foreign keys, and indexes. If the database already
    exists, it will add any missing tables or indexes.

    Args:
        db_path: Path to the database file. Will be created if it doesn't exist.

    Raises:
        sqlite3.Error: If database creation fails.

    Example:
        >>> create_database("hkjc_racing.db")
        >>> # Database created with all tables and indexes

    Note:
        Foreign key constraints are enabled by default. Referential integrity
        is enforced with ON DELETE CASCADE for child records.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    # Create tables in dependency order (parent tables first)
    _create_races_table(conn)
    _create_horses_table(conn)
    _create_jockeys_table(conn)
    _create_trainers_table(conn)
    _create_performance_table(conn)
    _create_dividends_table(conn)
    _create_incidents_table(conn)
    _create_sectional_times_table(conn)

    conn.commit()
    conn.close()


def _create_races_table(conn: sqlite3.Connection) -> None:
    """Create the races table with indexes.

    The races table stores race metadata including date, course, distance,
    and track conditions. Each race is identified by a unique race_id.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS races (
            -- Primary key
            race_id TEXT PRIMARY KEY NOT NULL,

            -- Race identification
            race_date TEXT NOT NULL,
            race_no INTEGER NOT NULL,
            racecourse TEXT NOT NULL,

            -- Race details
            class TEXT,
            distance INTEGER,
            going TEXT,
            surface TEXT,
            track TEXT,
            race_name TEXT,

            -- Rating stored as JSON string {"high": int, "low": int}
            rating TEXT,

            -- Sectional times stored as JSON array of strings
            sectional_times TEXT,

            -- Prize money in cents (to avoid floating point issues)
            prize_money INTEGER DEFAULT 0,

            -- Metadata
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Index for common queries by date
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_races_race_date
        ON races(race_date)
    """)

    # Index for racecourse queries
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_races_racecourse
        ON races(racecourse)
    """)

    # Composite index for date + racecourse queries
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_races_date_course
        ON races(race_date, racecourse)
    """)


def _create_horses_table(conn: sqlite3.Connection) -> None:
    """Create the horses table with indexes.

    The horses table stores horse profile information including breeding,
    career stats, and ownership details.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS horses (
            -- Primary key
            horse_id TEXT PRIMARY KEY NOT NULL,

            -- Basic information
            name TEXT NOT NULL,
            country_of_birth TEXT,
            age TEXT,
            colour TEXT,
            gender TEXT,

            -- Breeding
            sire TEXT,
            dam TEXT,
            damsire TEXT,

            -- Connections
            trainer TEXT,
            owner TEXT,

            -- Rating
            current_rating INTEGER,
            initial_rating INTEGER,

            -- Prize money in cents
            season_prize INTEGER DEFAULT 0,
            total_prize INTEGER DEFAULT 0,

            -- Career statistics
            wins INTEGER DEFAULT 0,
            places INTEGER DEFAULT 0,
            shows INTEGER DEFAULT 0,
            total INTEGER DEFAULT 0,

            -- Import information
            location TEXT,
            import_type TEXT,
            import_date TEXT,

            -- Metadata
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Index for name searches
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_horses_name
        ON horses(name)
    """)

    # Index for trainer lookups
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_horses_trainer
        ON horses(trainer)
    """)


def _create_jockeys_table(conn: sqlite3.Connection) -> None:
    """Create the jockeys table with indexes.

    The jockeys table stores jockey profile information including career
    statistics and achievements.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jockeys (
            -- Primary key
            jockey_id TEXT PRIMARY KEY NOT NULL,

            -- Basic information
            name TEXT NOT NULL,
            age TEXT,

            -- Background
            background TEXT,
            achievements TEXT,

            -- Career statistics
            career_wins INTEGER DEFAULT 0,
            career_win_rate TEXT,

            -- Season stats stored as JSON
            -- {"wins": int, "places": int, "win_rate": str, "prize_money": int}
            season_stats TEXT,

            -- Metadata
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Index for name searches
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_jockeys_name
        ON jockeys(name)
    """)


def _create_trainers_table(conn: sqlite3.Connection) -> None:
    """Create the trainers table with indexes.

    The trainers table stores trainer profile information including career
    statistics and achievements.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trainers (
            -- Primary key
            trainer_id TEXT PRIMARY KEY NOT NULL,

            -- Basic information
            name TEXT NOT NULL,
            age TEXT,

            -- Background
            background TEXT,
            achievements TEXT,

            -- Career statistics
            career_wins INTEGER DEFAULT 0,
            career_win_rate TEXT,

            -- Season stats stored as JSON
            -- {"wins": int, "places": int, "shows": int, "fourth": int,
            --  "total_runners": int, "win_rate": str, "prize_money": int}
            season_stats TEXT,

            -- Metadata
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Index for name searches
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_trainers_name
        ON trainers(name)
    """)


def _create_performance_table(conn: sqlite3.Connection) -> None:
    """Create the performance table with foreign keys and indexes.

    The performance table stores horse results for each race. Each record
    represents a single horse's performance in a specific race.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS performance (
            -- Primary key (auto-generated)
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- Foreign keys
            race_id TEXT NOT NULL REFERENCES races(race_id) ON DELETE CASCADE,
            horse_id TEXT REFERENCES horses(horse_id) ON DELETE SET NULL,
            jockey_id TEXT REFERENCES jockeys(jockey_id) ON DELETE SET NULL,
            trainer_id TEXT REFERENCES trainers(trainer_id) ON DELETE SET NULL,

            -- Race identification
            horse_no TEXT NOT NULL,
            position TEXT NOT NULL,

            -- Horse information (denormalized for query performance)
            horse_name TEXT NOT NULL,
            jockey TEXT,
            trainer TEXT,

            -- Weight information
            actual_weight TEXT,
            body_weight TEXT,

            -- Race details
            draw TEXT,
            margin TEXT,
            finish_time TEXT,
            win_odds TEXT,

            -- Running position stored as JSON array
            -- e.g., ["1", "2", "3", "1"]
            running_position TEXT,

            -- Metadata
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            -- Unique constraint: one record per horse per race
            UNIQUE(race_id, horse_no)
        )
    """)

    # Index for race queries (most common)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_performance_race_id
        ON performance(race_id)
    """)

    # Index for horse history queries
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_performance_horse_id
        ON performance(horse_id)
    """)

    # Index for jockey statistics
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_performance_jockey_id
        ON performance(jockey_id)
    """)

    # Index for trainer statistics
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_performance_trainer_id
        ON performance(trainer_id)
    """)

    # Index for position queries (e.g., finding winners)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_performance_position
        ON performance(position)
    """)


def _create_dividends_table(conn: sqlite3.Connection) -> None:
    """Create the dividends table with foreign keys and indexes.

    The dividends table stores payout information for each race and pool type.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dividends (
            -- Primary key (auto-generated)
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- Foreign key
            race_id TEXT NOT NULL REFERENCES races(race_id) ON DELETE CASCADE,

            -- Pool information
            pool TEXT NOT NULL,
            winning_combination TEXT,
            payout TEXT,

            -- Metadata
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            -- Unique constraint: one record per pool per race
            UNIQUE(race_id, pool)
        )
    """)

    # Index for race queries
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_dividends_race_id
        ON dividends(race_id)
    """)


def _create_incidents_table(conn: sqlite3.Connection) -> None:
    """Create the incidents table with foreign keys and indexes.

    The incidents table stores race incident reports describing what
    happened to each horse during the race.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            -- Primary key (auto-generated)
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- Foreign key
            race_id TEXT NOT NULL REFERENCES races(race_id) ON DELETE CASCADE,

            -- Horse identification
            position TEXT,
            horse_no TEXT NOT NULL,
            horse_name TEXT NOT NULL,

            -- Incident details
            incident_report TEXT,

            -- Metadata
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Index for race queries
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_incidents_race_id
        ON incidents(race_id)
    """)

    # Index for horse incident lookups
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_incidents_horse_no
        ON incidents(horse_no)
    """)


def _create_sectional_times_table(conn: sqlite3.Connection) -> None:
    """Create the sectional_times table with foreign keys and indexes.

    The sectional_times table stores per-horse sectional time data,
    recording position and margin at each section of the race.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sectional_times (
            -- Primary key (auto-generated)
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- Foreign key
            race_id TEXT NOT NULL REFERENCES races(race_id) ON DELETE CASCADE,

            -- Horse identification
            horse_no TEXT NOT NULL,
            section_number INTEGER NOT NULL,

            -- Section data
            position INTEGER,
            margin TEXT,
            time REAL,

            -- Metadata
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            -- Unique constraint: one record per horse per section
            UNIQUE(race_id, horse_no, section_number)
        )
    """)

    # Index for race queries
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_sectional_times_race_id
        ON sectional_times(race_id)
    """)

    # Index for horse sectional analysis
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_sectional_times_horse_no
        ON sectional_times(horse_no)
    """)

    # Composite index for race + horse queries
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_sectional_times_race_horse
        ON sectional_times(race_id, horse_no)
    """)


# Type aliases for query results
Racecourse = Literal["沙田", "谷草"]


def get_db_connection(db_path: str | Path) -> sqlite3.Connection:
    """Get a database connection with foreign keys enabled.

    Args:
        db_path: Path to the database file.

    Returns:
        A SQLite connection with foreign keys enabled.

    Example:
        >>> conn = get_db_connection("hkjc_racing.db")
        >>> cursor = conn.execute("SELECT * FROM races LIMIT 10")
        >>> conn.close()
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def import_races(data: list[dict], conn: sqlite3.Connection) -> int:
    """Import race records into the database.

    Args:
        data: List of race dictionaries from JSON export.
        conn: Database connection.

    Returns:
        Number of records imported.

    Example:
        >>> with open("races_2026-03-01.json") as f:
        ...     races = json.load(f)
        >>> conn = get_db_connection("hkjc_racing.db")
        >>> count = import_races(races, conn)
        >>> print(f"Imported {count} races")
        >>> conn.close()
    """
    if not data:
        return 0

    count = 0
    for record in data:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO races (
                    race_id, race_date, race_no, racecourse, class, distance,
                    going, surface, track, race_name, rating, sectional_times,
                    prize_money, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                record.get("race_id"),
                record.get("race_date"),
                record.get("race_no"),
                record.get("racecourse"),
                record.get("class"),
                record.get("distance"),
                record.get("going"),
                record.get("surface"),
                record.get("track"),
                record.get("race_name"),
                json.dumps(record.get("rating")) if record.get("rating") else None,
                json.dumps(record.get("sectional_times", [])),
                record.get("prize_money") or 0,
            ))
            count += 1
        except sqlite3.Error:
            # Skip records with invalid data
            pass

    conn.commit()
    return count


def import_performance(data: list[dict], conn: sqlite3.Connection) -> int:
    """Import performance records into the database.

    Args:
        data: List of performance dictionaries from JSON export.
        conn: Database connection.

    Returns:
        Number of records imported.

    Example:
        >>> with open("performance_2026-03-01.json") as f:
        ...     performances = json.load(f)
        >>> conn = get_db_connection("hkjc_racing.db")
        >>> count = import_performance(performances, conn)
        >>> print(f"Imported {count} performance records")
        >>> conn.close()
    """
    if not data:
        return 0

    count = 0
    for record in data:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO performance (
                    race_id, horse_id, jockey_id, trainer_id, horse_no,
                    position, horse_name, jockey, trainer, actual_weight,
                    body_weight, draw, margin, finish_time, win_odds,
                    running_position
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.get("race_id"),
                record.get("horse_id"),
                record.get("jockey_id"),
                record.get("trainer_id"),
                record.get("horse_no"),
                record.get("position"),
                record.get("horse_name"),
                record.get("jockey"),
                record.get("trainer"),
                record.get("actual_weight"),
                record.get("body_weight"),
                record.get("draw"),
                record.get("margin"),
                record.get("finish_time"),
                record.get("win_odds"),
                json.dumps(record.get("running_position", [])),
            ))
            count += 1
        except sqlite3.Error:
            # Skip records with invalid data (e.g., missing foreign key)
            pass

    conn.commit()
    return count


def import_dividends(data: list[dict], conn: sqlite3.Connection) -> int:
    """Import dividend records into the database.

    Args:
        data: List of dividend dictionaries from JSON export.
        conn: Database connection.

    Returns:
        Number of records imported.

    Example:
        >>> with open("dividends_2026-03-01.json") as f:
        ...     dividends = json.load(f)
        >>> conn = get_db_connection("hkjc_racing.db")
        >>> count = import_dividends(dividends, conn)
        >>> print(f"Imported {count} dividend records")
        >>> conn.close()
    """
    if not data:
        return 0

    count = 0
    for record in data:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO dividends (
                    race_id, pool, winning_combination, payout
                ) VALUES (?, ?, ?, ?)
            """, (
                record.get("race_id"),
                record.get("pool"),
                record.get("winning_combination"),
                record.get("payout"),
            ))
            count += 1
        except sqlite3.Error:
            # Skip records with invalid data
            pass

    conn.commit()
    return count


def import_incidents(data: list[dict], conn: sqlite3.Connection) -> int:
    """Import incident records into the database.

    Args:
        data: List of incident dictionaries from JSON export.
        conn: Database connection.

    Returns:
        Number of records imported.

    Example:
        >>> with open("incidents_2026-03-01.json") as f:
        ...     incidents = json.load(f)
        >>> conn = get_db_connection("hkjc_racing.db")
        >>> count = import_incidents(incidents, conn)
        >>> print(f"Imported {count} incident records")
        >>> conn.close()
    """
    if not data:
        return 0

    count = 0
    for record in data:
        try:
            conn.execute("""
                INSERT INTO incidents (
                    race_id, position, horse_no, horse_name, incident_report
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                record.get("race_id"),
                record.get("position"),
                record.get("horse_no"),
                record.get("horse_name"),
                record.get("incident_report"),
            ))
            count += 1
        except sqlite3.Error:
            # Skip records with invalid data
            pass

    conn.commit()
    return count


def import_horses(data: list[dict], conn: sqlite3.Connection) -> int:
    """Import horse profile records into the database.

    Args:
        data: List of horse dictionaries from JSON export.
        conn: Database connection.

    Returns:
        Number of records imported.

    Example:
        >>> with open("horses_2026-03-01.json") as f:
        ...     horses = json.load(f)
        >>> conn = get_db_connection("hkjc_racing.db")
        >>> count = import_horses(horses, conn)
        >>> print(f"Imported {count} horse profiles")
        >>> conn.close()
    """
    if not data:
        return 0

    count = 0
    for record in data:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO horses (
                    horse_id, name, country_of_birth, age, colour, gender,
                    sire, dam, damsire, trainer, owner, current_rating,
                    initial_rating, season_prize, total_prize, wins, places,
                    shows, total, location, import_type, import_date,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                record.get("horse_id"),
                record.get("name"),
                record.get("country_of_birth"),
                record.get("age"),
                record.get("colour"),
                record.get("gender"),
                record.get("sire"),
                record.get("dam"),
                record.get("damsire"),
                record.get("trainer"),
                record.get("owner"),
                record.get("current_rating"),
                record.get("initial_rating"),
                record.get("season_prize") or 0,
                record.get("total_prize") or 0,
                record.get("wins") or 0,
                record.get("places") or 0,
                record.get("shows") or 0,
                record.get("total") or 0,
                record.get("location"),
                record.get("import_type"),
                record.get("import_date"),
            ))
            count += 1
        except sqlite3.Error:
            # Skip records with invalid data
            pass

    conn.commit()
    return count


def import_jockeys(data: list[dict], conn: sqlite3.Connection) -> int:
    """Import jockey profile records into the database.

    Args:
        data: List of jockey dictionaries from JSON export.
        conn: Database connection.

    Returns:
        Number of records imported.

    Example:
        >>> with open("jockeys_2026-03-01.json") as f:
        ...     jockeys = json.load(f)
        >>> conn = get_db_connection("hkjc_racing.db")
        >>> count = import_jockeys(jockeys, conn)
        >>> print(f"Imported {count} jockey profiles")
        >>> conn.close()
    """
    if not data:
        return 0

    count = 0
    for record in data:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO jockeys (
                    jockey_id, name, age, background, achievements,
                    career_wins, career_win_rate, season_stats, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                record.get("jockey_id"),
                record.get("name"),
                record.get("age"),
                record.get("background"),
                record.get("achievements"),
                record.get("career_wins") or 0,
                record.get("career_win_rate"),
                json.dumps(record.get("season_stats")) if record.get("season_stats") else None,
            ))
            count += 1
        except sqlite3.Error:
            # Skip records with invalid data
            pass

    conn.commit()
    return count


def import_trainers(data: list[dict], conn: sqlite3.Connection) -> int:
    """Import trainer profile records into the database.

    Args:
        data: List of trainer dictionaries from JSON export.
        conn: Database connection.

    Returns:
        Number of records imported.

    Example:
        >>> with open("trainers_2026-03-01.json") as f:
        ...     trainers = json.load(f)
        >>> conn = get_db_connection("hkjc_racing.db")
        >>> count = import_trainers(trainers, conn)
        >>> print(f"Imported {count} trainer profiles")
        >>> conn.close()
    """
    if not data:
        return 0

    count = 0
    for record in data:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO trainers (
                    trainer_id, name, age, background, achievements,
                    career_wins, career_win_rate, season_stats, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                record.get("trainer_id"),
                record.get("name"),
                record.get("age"),
                record.get("background"),
                record.get("achievements"),
                record.get("career_wins") or 0,
                record.get("career_win_rate"),
                json.dumps(record.get("season_stats")) if record.get("season_stats") else None,
            ))
            count += 1
        except sqlite3.Error:
            # Skip records with invalid data
            pass

    conn.commit()
    return count


def import_sectional_times(data: list[dict], conn: sqlite3.Connection) -> int:
    """Import sectional time records into the database.

    Args:
        data: List of sectional time dictionaries from JSON export.
        conn: Database connection.

    Returns:
        Number of records imported.

    Example:
        >>> with open("sectional_times_2026-03-01.json") as f:
        ...     sectional_times = json.load(f)
        >>> conn = get_db_connection("hkjc_racing.db")
        >>> count = import_sectional_times(sectional_times, conn)
        >>> print(f"Imported {count} sectional time records")
        >>> conn.close()
    """
    if not data:
        return 0

    count = 0
    for record in data:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO sectional_times (
                    race_id, horse_no, section_number, position, margin, time
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                record.get("race_id"),
                record.get("horse_no"),
                record.get("section_number"),
                record.get("position"),
                record.get("margin"),
                record.get("time"),
            ))
            count += 1
        except sqlite3.Error:
            # Skip records with invalid data
            pass

    conn.commit()
    return count


def export_json_to_db(
    data_dir: str | Path,
    db_path: str | Path = "data/hkjc_racing.db",
) -> dict[str, int]:
    """Export JSON files from data directory to SQLite database.

    Reads all JSON files matching the pattern '{table}_{date}.json' or
    '{table}_batch.json' and inserts them into the corresponding database tables.
    Creates the database schema if it doesn't exist.

    Args:
        data_dir: Directory containing the JSON data files.
        db_path: Path to the SQLite database file (will be created if needed).

    Returns:
        Dictionary with table names as keys and record counts as values.

    Raises:
        FileNotFoundError: If data directory doesn't exist.
        sqlite3.Error: If database operation fails.

    Example:
        >>> counts = export_json_to_db("data", "racing.db")
        >>> print(counts)
        {'races': 120, 'performance': 1320, 'horses': 450, ...}
    """
    data_path = Path(data_dir)
    if not data_path.exists():
        raise FileNotFoundError(f"Data directory not found: {data_path}")

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Ensure database schema exists
    create_database(db_path)

    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    counts: dict[str, int] = {}

    # Table schemas for column mapping
    table_schemas = {
        "races": [
            "race_id", "race_date", "race_no", "racecourse", "class", "distance",
            "going", "surface", "track", "race_name", "rating", "sectional_times",
            "prize_money",
        ],
        "horses": [
            "horse_id", "name", "country_of_birth", "age", "colour", "gender",
            "sire", "dam", "damsire", "trainer", "owner", "current_rating",
            "initial_rating", "season_prize", "total_prize", "wins", "places",
            "shows", "total", "location", "import_type", "import_date",
        ],
        "jockeys": [
            "jockey_id", "name", "age", "background", "achievements",
            "career_wins", "career_win_rate", "season_stats",
        ],
        "trainers": [
            "trainer_id", "name", "age", "background", "achievements",
            "career_wins", "career_win_rate", "season_stats",
        ],
        "performance": [
            "race_id", "horse_id", "jockey_id", "trainer_id", "horse_no",
            "position", "horse_name", "jockey", "trainer", "actual_weight",
            "body_weight", "draw", "margin", "finish_time", "win_odds",
            "running_position",
        ],
        "dividends": ["race_id", "pool", "winning_combination", "payout"],
        "incidents": ["race_id", "position", "horse_no", "horse_name", "incident_report"],
        "sectional_times": ["race_id", "horse_no", "section_number", "position", "margin", "time"],
    }

    # Find and process all JSON files
    json_files = list(data_path.glob("*.json"))

    for json_file in sorted(json_files):
        # Extract table name from filename (e.g., "races_2026-03-01.json" -> "races")
        parts = json_file.stem.split("_")
        if len(parts) < 2:
            continue

        table_name = parts[0]
        if table_name not in table_schemas:
            continue

        # Read JSON data
        with open(json_file, encoding="utf-8") as f:
            records = json.load(f)

        if not records:
            continue

        # Get column schema for this table
        columns = table_schemas[table_name]

        # Build insert query with UPSERT (INSERT OR REPLACE)
        placeholders = ", ".join(["?"] * len(columns))
        column_list = ", ".join(columns)
        query = f"INSERT OR REPLACE INTO {table_name} ({column_list}) VALUES ({placeholders})"

        # Prepare and execute batch insert
        inserted = 0
        for record in records:
            values = []
            for col in columns:
                value = record.get(col)

                # Serialize complex types as JSON
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)

                values.append(value)

            try:
                cursor.execute(query, values)
                inserted += 1
            except sqlite3.Error as e:
                print(f"Warning: Failed to insert record into {table_name}: {e}")

        counts[table_name] = counts.get(table_name, 0) + inserted
        print(f"Imported {inserted} records into {table_name} from {json_file.name}")

    conn.commit()
    conn.close()

    return counts


def load_from_db(
    db_path: str | Path,
    table: str,
    where_clause: str | None = None,
    params: tuple | None = None,
) -> list[dict]:
    """Load data from database table as list of dictionaries.

    Args:
        db_path: Path to the SQLite database file.
        table: Table name to query.
        where_clause: Optional WHERE clause (without the 'WHERE' keyword).
        params: Query parameters for the WHERE clause.

    Returns:
        List of dictionaries with column names as keys.

    Raises:
        sqlite3.Error: If query fails.

    Example:
        >>> races = load_from_db("racing.db", "races", "race_date = ?", ("2026/03/01",))
        >>> len(races)
        8
    """
    conn = get_db_connection(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = f"SELECT * FROM {table}"
    if where_clause:
        query += f" WHERE {where_clause}"

    cursor.execute(query, params or ())
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]
