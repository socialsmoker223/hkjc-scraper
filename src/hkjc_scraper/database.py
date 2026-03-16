"""PostgreSQL database layer for HKJC racing data.

This module provides functions for importing scraped racing data into PostgreSQL
and querying it back. Uses psycopg2 with execute_values for efficient batch inserts.

Usage:
    Set DATABASE_URL environment variable:
        postgresql://user:password@host:port/dbname

    Or pass the URL directly to functions.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import psycopg2
import psycopg2.extras
from psycopg2.extras import execute_values

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Sequence


def _chunks[T](lst: Sequence[T], n: int) -> Generator[Sequence[T], None, None]:
    """Yield successive n-sized chunks from a list."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def get_database_url() -> str:
    """Get PostgreSQL connection URL from environment.

    Returns:
        PostgreSQL connection string.

    Raises:
        ValueError: If DATABASE_URL is not set.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise ValueError(
            "DATABASE_URL environment variable is not set. "
            "Example: postgresql://hkjc:hkjc_dev@localhost:5432/hkjc_racing"
        )
    return url


def get_db_connection(
    database_url: str | None = None,
) -> psycopg2.extensions.connection:
    """Get a PostgreSQL database connection.

    Args:
        database_url: PostgreSQL connection string.
            If None, reads from DATABASE_URL env var.

    Returns:
        A psycopg2 connection.
    """
    url = database_url or get_database_url()
    return psycopg2.connect(url)


def create_database(database_url: str | None = None) -> None:
    """Create the PostgreSQL database schema with all tables and indexes.

    Reads and executes the docker/init.sql schema file. Safe to run multiple
    times due to IF NOT EXISTS clauses.

    Args:
        database_url: PostgreSQL connection string.
            If None, reads from DATABASE_URL env var.
    """
    conn = get_db_connection(database_url)
    try:
        cursor = conn.cursor()
        init_sql = Path(__file__).parent.parent.parent / "docker" / "init.sql"
        if not init_sql.exists():
            raise FileNotFoundError(
                f"Schema file not found: {init_sql}. "
                "Ensure docker/init.sql exists in the project root."
            )
        cursor.execute(init_sql.read_text())
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Generic batch upsert helper
# ---------------------------------------------------------------------------

def _batch_upsert(
    data: list[dict],
    conn: psycopg2.extensions.connection,
    sql: str,
    prepare_row: Callable[[dict], tuple | None],
    conflict_keys: tuple[int, ...] = (0,),
    batch_size: int = 500,
    template: str | None = None,
) -> int:
    """Insert records in batches using execute_values.

    Records are prepared first (validated and serialized), deduplicated by
    conflict key, then inserted in batches. Invalid records are silently
    skipped.

    Args:
        data: Raw record dicts from JSON.
        conn: PostgreSQL connection (caller manages transaction).
        sql: INSERT ... VALUES %s ... ON CONFLICT ... statement.
            Must use a single ``%s`` placeholder for the VALUES list.
        prepare_row: Callable that converts a dict to a tuple of values,
            or returns None to skip the record.
        conflict_keys: Tuple of positional indices in the prepared row that
            form the unique/conflict key. Duplicates are resolved by keeping
            the last occurrence. Defaults to (0,) (first column).
        batch_size: Number of records per batch.
        template: Optional psycopg2 execute_values template string for
            rows that include SQL expressions like NOW().

    Returns:
        Number of records successfully prepared and inserted.
    """
    if not data:
        return 0

    seen: dict[tuple, int] = {}
    rows: list[tuple] = []
    for record in data:
        try:
            row = prepare_row(record)
            if row is None:
                continue
            key = tuple(row[i] for i in conflict_keys)
            if key in seen:
                # Keep last occurrence — overwrite earlier duplicate
                rows[seen[key]] = row
            else:
                seen[key] = len(rows)
                rows.append(row)
        except (KeyError, TypeError, ValueError):
            continue

    if not rows:
        return 0

    cursor = conn.cursor()
    for batch in _chunks(rows, batch_size):
        execute_values(cursor, sql, batch, template=template)

    return len(rows)


# ---------------------------------------------------------------------------
# Per-table import functions
# ---------------------------------------------------------------------------

def import_races(
    data: list[dict], conn: psycopg2.extensions.connection,
) -> int:
    """Import race records into PostgreSQL."""

    def _prepare(r: dict) -> tuple:
        rating = r.get("rating")
        return (
            r.get("race_id"),
            r.get("race_date"),
            r.get("race_no"),
            r.get("racecourse"),
            r.get("class"),
            r.get("distance"),
            r.get("going"),
            r.get("surface"),
            r.get("track"),
            r.get("race_name"),
            json.dumps(rating) if rating else None,
            json.dumps(r.get("sectional_times", [])),
            r.get("prize_money") or 0,
        )

    return _batch_upsert(data, conn, """
        INSERT INTO races (
            race_id, race_date, race_no, racecourse, class, distance,
            going, surface, track, race_name, rating, sectional_times,
            prize_money, updated_at
        ) VALUES %s
        ON CONFLICT (race_id) DO UPDATE SET
            race_date = EXCLUDED.race_date,
            race_no = EXCLUDED.race_no,
            racecourse = EXCLUDED.racecourse,
            class = EXCLUDED.class,
            distance = EXCLUDED.distance,
            going = EXCLUDED.going,
            surface = EXCLUDED.surface,
            track = EXCLUDED.track,
            race_name = EXCLUDED.race_name,
            rating = EXCLUDED.rating,
            sectional_times = EXCLUDED.sectional_times,
            prize_money = EXCLUDED.prize_money,
            updated_at = NOW()
    """, _prepare, template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())")


def import_performance(
    data: list[dict], conn: psycopg2.extensions.connection,
) -> int:
    """Import performance records into PostgreSQL."""

    def _prepare(r: dict) -> tuple:
        return (
            r.get("race_id"),
            r.get("horse_id"),
            r.get("jockey_id"),
            r.get("trainer_id"),
            r.get("horse_no"),
            r.get("position"),
            r.get("horse_name"),
            r.get("jockey"),
            r.get("trainer"),
            r.get("actual_weight"),
            r.get("body_weight"),
            r.get("draw"),
            r.get("margin"),
            r.get("finish_time"),
            r.get("win_odds"),
            json.dumps(r.get("running_position", [])),
            r.get("gear"),
        )

    return _batch_upsert(data, conn, """
        INSERT INTO performance (
            race_id, horse_id, jockey_id, trainer_id, horse_no,
            position, horse_name, jockey, trainer, actual_weight,
            body_weight, draw, margin, finish_time, win_odds,
            running_position, gear
        ) VALUES %s
        ON CONFLICT (race_id, horse_no) DO UPDATE SET
            horse_id = EXCLUDED.horse_id,
            jockey_id = EXCLUDED.jockey_id,
            trainer_id = EXCLUDED.trainer_id,
            position = EXCLUDED.position,
            horse_name = EXCLUDED.horse_name,
            jockey = EXCLUDED.jockey,
            trainer = EXCLUDED.trainer,
            actual_weight = EXCLUDED.actual_weight,
            body_weight = EXCLUDED.body_weight,
            draw = EXCLUDED.draw,
            margin = EXCLUDED.margin,
            finish_time = EXCLUDED.finish_time,
            win_odds = EXCLUDED.win_odds,
            running_position = EXCLUDED.running_position,
            gear = EXCLUDED.gear
    """, _prepare, conflict_keys=(0, 4))


def import_dividends(
    data: list[dict], conn: psycopg2.extensions.connection,
) -> int:
    """Import dividend records into PostgreSQL."""

    def _prepare(r: dict) -> tuple:
        return (
            r.get("race_id"),
            r.get("pool"),
            r.get("winning_combination"),
            r.get("payout"),
        )

    return _batch_upsert(data, conn, """
        INSERT INTO dividends (race_id, pool, winning_combination, payout)
        VALUES %s
        ON CONFLICT (race_id, pool) DO UPDATE SET
            winning_combination = EXCLUDED.winning_combination,
            payout = EXCLUDED.payout
    """, _prepare, conflict_keys=(0, 1))


def import_incidents(
    data: list[dict], conn: psycopg2.extensions.connection,
) -> int:
    """Import incident records into PostgreSQL."""

    def _prepare(r: dict) -> tuple:
        return (
            r.get("race_id"),
            r.get("position"),
            r.get("horse_no"),
            r.get("horse_name"),
            r.get("incident_report"),
        )

    return _batch_upsert(data, conn, """
        INSERT INTO incidents (race_id, position, horse_no, horse_name, incident_report)
        VALUES %s
    """, _prepare)


def import_horses(
    data: list[dict], conn: psycopg2.extensions.connection,
) -> int:
    """Import horse profile records into PostgreSQL."""

    def _prepare(r: dict) -> tuple:
        return (
            r.get("horse_id"),
            r.get("name"),
            r.get("country_of_birth"),
            r.get("age"),
            r.get("colour"),
            r.get("gender"),
            r.get("sire"),
            r.get("dam"),
            r.get("damsire"),
            r.get("trainer"),
            r.get("owner"),
            r.get("current_rating"),
            r.get("initial_rating"),
            r.get("season_prize") or 0,
            r.get("total_prize") or 0,
            r.get("wins") or 0,
            r.get("places") or 0,
            r.get("shows") or 0,
            r.get("total") or 0,
            r.get("location"),
            r.get("import_type"),
            r.get("import_date"),
        )

    return _batch_upsert(data, conn, """
        INSERT INTO horses (
            horse_id, name, country_of_birth, age, colour, gender,
            sire, dam, damsire, trainer, owner, current_rating,
            initial_rating, season_prize, total_prize, wins, places,
            shows, total, location, import_type, import_date, updated_at
        ) VALUES %s
        ON CONFLICT (horse_id) DO UPDATE SET
            name = EXCLUDED.name,
            country_of_birth = EXCLUDED.country_of_birth,
            age = EXCLUDED.age,
            colour = EXCLUDED.colour,
            gender = EXCLUDED.gender,
            sire = EXCLUDED.sire,
            dam = EXCLUDED.dam,
            damsire = EXCLUDED.damsire,
            trainer = EXCLUDED.trainer,
            owner = EXCLUDED.owner,
            current_rating = EXCLUDED.current_rating,
            initial_rating = EXCLUDED.initial_rating,
            season_prize = EXCLUDED.season_prize,
            total_prize = EXCLUDED.total_prize,
            wins = EXCLUDED.wins,
            places = EXCLUDED.places,
            shows = EXCLUDED.shows,
            total = EXCLUDED.total,
            location = EXCLUDED.location,
            import_type = EXCLUDED.import_type,
            import_date = EXCLUDED.import_date,
            updated_at = NOW()
    """, _prepare, template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())")


def import_jockeys(
    data: list[dict], conn: psycopg2.extensions.connection,
) -> int:
    """Import jockey profile records into PostgreSQL."""

    def _prepare(r: dict) -> tuple:
        season_stats = r.get("season_stats")
        return (
            r.get("jockey_id"),
            r.get("name"),
            r.get("age"),
            r.get("background"),
            r.get("achievements"),
            r.get("career_wins") or 0,
            r.get("career_win_rate"),
            json.dumps(season_stats) if season_stats else None,
        )

    return _batch_upsert(data, conn, """
        INSERT INTO jockeys (
            jockey_id, name, age, background, achievements,
            career_wins, career_win_rate, season_stats, updated_at
        ) VALUES %s
        ON CONFLICT (jockey_id) DO UPDATE SET
            name = EXCLUDED.name,
            age = EXCLUDED.age,
            background = EXCLUDED.background,
            achievements = EXCLUDED.achievements,
            career_wins = EXCLUDED.career_wins,
            career_win_rate = EXCLUDED.career_win_rate,
            season_stats = EXCLUDED.season_stats,
            updated_at = NOW()
    """, _prepare, template="(%s, %s, %s, %s, %s, %s, %s, %s, NOW())")


def import_trainers(
    data: list[dict], conn: psycopg2.extensions.connection,
) -> int:
    """Import trainer profile records into PostgreSQL."""

    def _prepare(r: dict) -> tuple:
        season_stats = r.get("season_stats")
        return (
            r.get("trainer_id"),
            r.get("name"),
            r.get("age"),
            r.get("background"),
            r.get("achievements"),
            r.get("career_wins") or 0,
            r.get("career_win_rate"),
            json.dumps(season_stats) if season_stats else None,
        )

    return _batch_upsert(data, conn, """
        INSERT INTO trainers (
            trainer_id, name, age, background, achievements,
            career_wins, career_win_rate, season_stats, updated_at
        ) VALUES %s
        ON CONFLICT (trainer_id) DO UPDATE SET
            name = EXCLUDED.name,
            age = EXCLUDED.age,
            background = EXCLUDED.background,
            achievements = EXCLUDED.achievements,
            career_wins = EXCLUDED.career_wins,
            career_win_rate = EXCLUDED.career_win_rate,
            season_stats = EXCLUDED.season_stats,
            updated_at = NOW()
    """, _prepare, template="(%s, %s, %s, %s, %s, %s, %s, %s, NOW())")


def import_sectional_times(
    data: list[dict], conn: psycopg2.extensions.connection,
) -> int:
    """Import sectional time records into PostgreSQL."""

    def _prepare(r: dict) -> tuple:
        return (
            r.get("race_id"),
            r.get("horse_no"),
            r.get("section_number"),
            r.get("position"),
            r.get("margin"),
            r.get("time"),
        )

    return _batch_upsert(data, conn, """
        INSERT INTO sectional_times (
            race_id, horse_no, section_number, position, margin, time
        ) VALUES %s
        ON CONFLICT (race_id, horse_no, section_number) DO UPDATE SET
            position = EXCLUDED.position,
            margin = EXCLUDED.margin,
            time = EXCLUDED.time
    """, _prepare, conflict_keys=(0, 1, 2))


def update_performance_gear(
    data: list[dict], conn: psycopg2.extensions.connection,
) -> int:
    """Update gear on existing performance records.

    Uses (race_id, horse_id) to match records since gear data comes from
    horse profile pages where horse_no is not available.

    Args:
        data: List of dicts with keys: race_id, horse_id, gear.
        conn: PostgreSQL connection (caller manages transaction).

    Returns:
        Number of records updated.
    """
    if not data:
        return 0

    cursor = conn.cursor()
    updated = 0
    for record in data:
        race_id = record.get("race_id")
        horse_id = record.get("horse_id")
        gear = record.get("gear")
        if not race_id or not horse_id or not gear:
            continue
        cursor.execute(
            "UPDATE performance SET gear = %s WHERE race_id = %s AND horse_id = %s",
            (gear, race_id, horse_id),
        )
        updated += cursor.rowcount
    return updated


# ---------------------------------------------------------------------------
# Bulk export / query
# ---------------------------------------------------------------------------

def export_json_to_db(
    data_dir: str | Path,
    database_url: str | None = None,
) -> dict[str, int]:
    """Export JSON files from data directory to PostgreSQL database.

    Args:
        data_dir: Directory containing the JSON data files.
        database_url: PostgreSQL connection string.
            If None, reads from DATABASE_URL env var.

    Returns:
        Dictionary with table names as keys and record counts as values.

    Raises:
        FileNotFoundError: If data directory doesn't exist.
    """
    data_path = Path(data_dir)
    if not data_path.exists():
        raise FileNotFoundError(f"Data directory not found: {data_path}")

    create_database(database_url)

    conn = get_db_connection(database_url)
    try:
        counts: dict[str, int] = {}

        importers: dict[str, Callable] = {
            "races": import_races,
            "horses": import_horses,
            "jockeys": import_jockeys,
            "trainers": import_trainers,
            "performance": import_performance,
            "dividends": import_dividends,
            "incidents": import_incidents,
            "sectional_times": import_sectional_times,
        }

        # Parent tables first to satisfy foreign keys
        table_order = [
            "races", "horses", "jockeys", "trainers",
            "performance", "dividends", "incidents", "sectional_times",
        ]

        json_files = list(data_path.glob("*.json"))

        for table_name in table_order:
            importer = importers[table_name]
            table_files = [
                f for f in json_files
                if f.stem.startswith(table_name + "_")
            ]

            for json_file in sorted(table_files):
                with open(json_file, encoding="utf-8") as f:
                    records = json.load(f)

                if not records:
                    continue

                inserted = importer(records, conn)
                conn.commit()
                counts[table_name] = counts.get(table_name, 0) + inserted
                print(
                    f"Imported {inserted} records into "
                    f"{table_name} from {json_file.name}"
                )

        return counts
    finally:
        conn.close()


def load_from_db(
    table: str,
    where_clause: str | None = None,
    params: tuple | None = None,
    database_url: str | None = None,
) -> list[dict]:
    """Load data from database table as list of dictionaries.

    Args:
        table: Table name to query.
        where_clause: Optional WHERE clause (without the 'WHERE' keyword).
        params: Query parameters for the WHERE clause.
        database_url: PostgreSQL connection string.
            If None, reads from DATABASE_URL env var.

    Returns:
        List of dictionaries with column names as keys.
    """
    conn = get_db_connection(database_url)
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        query = f"SELECT * FROM {table}"
        if where_clause:
            query += f" WHERE {where_clause}"

        cursor.execute(query, params or ())
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()
