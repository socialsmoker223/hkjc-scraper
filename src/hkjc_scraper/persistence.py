"""
Data persistence layer with UPSERT operations
資料持久化層，提供 UPSERT 操作
"""

import logging
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from hkjc_scraper.models import (
    HkjcOdds,
    Horse,
    HorseHistory,
    HorseSectional,
    Jockey,
    Meeting,
    OffshoreMarket,
    Race,
    Runner,
    Trainer,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Database retry decorator for timeout and connection errors
# ============================================================================

# Retry decorator for database operations prone to timeouts
db_retry = retry(
    retry=retry_if_exception_type(OperationalError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    before_sleep=lambda retry_state: logger.warning(
        f"Database operation failed (attempt {retry_state.attempt_number}), retrying..."
    ),
)

# ============================================================================
# Meeting and Race persistence
# ============================================================================


def upsert_meeting(db: Session, meeting_data: dict[str, Any]) -> Meeting:
    """
    插入或更新 meeting (使用 PostgreSQL ON CONFLICT UPSERT)
    Insert or update meeting using PostgreSQL native ON CONFLICT (unique by date + venue_code)

    Args:
        db: Database session
        meeting_data: Dictionary with keys: date, venue_code, venue_name, source_url

    Returns:
        Meeting object
    """
    # Clean the data: convert date string to date object and remove extra fields
    clean_data = meeting_data.copy()

    # Convert date string (YYYY/MM/DD) to date object if it's a string
    if isinstance(clean_data.get("date"), str):
        date_str = clean_data["date"]
        clean_data["date"] = datetime.strptime(date_str, "%Y/%m/%d").date()

    # Remove fields that aren't in the Meeting model
    clean_data.pop("date_dmy", None)

    # Use PostgreSQL's native ON CONFLICT for true UPSERT in 1 query (was 2)
    stmt = insert(Meeting).values(clean_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["date", "venue_code"],
        set_={k: v for k, v in clean_data.items() if k not in ["date", "venue_code"]},
    ).returning(Meeting)

    result = db.execute(stmt)
    return result.scalar_one()


def upsert_race(db: Session, race_data: dict[str, Any]) -> Race:
    """
    插入或更新 race (使用 PostgreSQL ON CONFLICT UPSERT)
    Insert or update race using PostgreSQL native ON CONFLICT (unique by meeting_id + race_no)

    Args:
        db: Database session
        race_data: Dictionary with race fields including meeting_id

    Returns:
        Race object
    """
    # Use PostgreSQL's native ON CONFLICT for true UPSERT in 1 query (was 2)
    stmt = insert(Race).values(race_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["meeting_id", "race_no"],
        set_={k: v for k, v in race_data.items() if k not in ["meeting_id", "race_no"]},
    ).returning(Race)

    result = db.execute(stmt)
    return result.scalar_one()


def check_meeting_exists(db: Session, race_date: date) -> bool:
    """
    Check if meeting data exists for a given date
    """
    stmt = select(Meeting).where(Meeting.date == race_date)
    return db.execute(stmt).first() is not None


def get_max_meeting_date(db: Session) -> Optional[date]:
    """
    Get the latest meeting date in the database
    """
    stmt = select(func.max(Meeting.date))
    return db.execute(stmt).scalar()


# ============================================================================
# Horse, Jockey, Trainer persistence (entity master tables)
# ============================================================================


def upsert_horse(db: Session, horse_data: dict[str, Any]) -> Horse:
    """
    插入或更新 horse (使用 PostgreSQL ON CONFLICT UPSERT)
    Insert or update horse using PostgreSQL native ON CONFLICT (unique by hkjc_horse_id)

    Args:
        db: Database session
        horse_data: Dictionary with keys: code, name_cn, name_en, hkjc_horse_id, profile_url

    Returns:
        Horse object
    """
    # Use PostgreSQL's native ON CONFLICT for true UPSERT in 1 query (was 2)
    # Use hkjc_horse_id as unique key (always present, handles NULL name_en)
    stmt = insert(Horse).values(horse_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["hkjc_horse_id"], set_={k: v for k, v in horse_data.items() if k != "hkjc_horse_id"}
    ).returning(Horse)

    result = db.execute(stmt)
    return result.scalar_one()


def upsert_jockey(db: Session, jockey_data: dict[str, Any]) -> Jockey:
    """
    插入或更新 jockey (使用 PostgreSQL ON CONFLICT UPSERT)
    Insert or update jockey using PostgreSQL native ON CONFLICT (unique by code)

    Args:
        db: Database session
        jockey_data: Dictionary with keys: code, name_cn, name_en

    Returns:
        Jockey object
    """
    # Use PostgreSQL's native ON CONFLICT for true UPSERT in 1 query (was 2)
    stmt = insert(Jockey).values(jockey_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["name_cn"], set_={k: v for k, v in jockey_data.items() if k != "name_cn"}
    ).returning(Jockey)

    result = db.execute(stmt)
    return result.scalar_one()


def upsert_trainer(db: Session, trainer_data: dict[str, Any]) -> Trainer:
    """
    插入或更新 trainer (使用 PostgreSQL ON CONFLICT UPSERT)
    Insert or update trainer using PostgreSQL native ON CONFLICT (unique by code)

    Args:
        db: Database session
        trainer_data: Dictionary with keys: code, name_cn, name_en

    Returns:
        Trainer object
    """
    # Use PostgreSQL's native ON CONFLICT for true UPSERT in 1 query (was 2)
    stmt = insert(Trainer).values(trainer_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["name_cn"], set_={k: v for k, v in trainer_data.items() if k != "name_cn"}
    ).returning(Trainer)

    result = db.execute(stmt)
    return result.scalar_one()


# ============================================================================
# Horse Profile persistence
# ============================================================================


def insert_horse_history(
    db: Session, horse_id: int, horse_data: dict[str, Any], captured_at: Optional[datetime] = None
) -> HorseHistory:
    """
    插入 horse_history 快照
    Insert horse_history snapshot

    Args:
        db: Database session
        horse_id: Horse ID
        horse_data: Dictionary with horse fields (including identity and profile)
        captured_at: Timestamp of capture (defaults to now)

    Returns:
        HorseHistory object
    """
    if captured_at is None:
        captured_at = datetime.now()

    # Filter data to match HorseHistory columns
    # We can rely on SQLAlchemy to ignore extra fields if we pass via **kwargs carefully,
    # or just copy the dictionary.
    # However, to be safe and clean, let's create the history object.

    # Note: horse_data might contain 'id' or other irrelevant fields from a previous scrape/obj
    # so we should be careful.

    history = HorseHistory(horse_id=horse_id, captured_at=captured_at)

    # Copy fields that exist in HorseHistory
    # identity + profile fields
    valid_fields = {
        "code",
        "name_cn",
        "name_en",
        "hkjc_horse_id",
        "profile_url",
        "origin",
        "age",
        "colour",
        "sex",
        "import_type",
        "season_prize_hkd",
        "lifetime_prize_hkd",
        "record_wins",
        "record_seconds",
        "record_thirds",
        "record_starts",
        "last10_starts",
        "current_location",
        "current_location_date",
        "import_date",
        "owner_name",
        "current_rating",
        "season_start_rating",
        "sire_name",
        "dam_name",
        "dam_sire_name",
    }

    for key, value in horse_data.items():
        if key in valid_fields:
            setattr(history, key, value)

    db.add(history)
    db.flush()
    return history


# ============================================================================
# Runner and Sectional persistence
# ============================================================================


def upsert_runner(db: Session, runner_data: dict[str, Any]) -> Runner:
    """
    插入或更新 runner (使用 PostgreSQL ON CONFLICT UPSERT)
    Insert or update runner using PostgreSQL native ON CONFLICT (unique by race_id + horse_id)

    Args:
        db: Database session
        runner_data: Dictionary with runner fields including race_id, horse_id

    Returns:
        Runner object
    """
    # Clean the data: remove fields that aren't in the Runner model
    clean_data = runner_data.copy()
    clean_data.pop("horse_name_cn", None)
    clean_data.pop("jockey_name_cn", None)
    clean_data.pop("trainer_name_cn", None)
    clean_data.pop("hkjc_horse_id", None)

    # Use PostgreSQL's native ON CONFLICT for true UPSERT in 1 query (was 2)
    stmt = insert(Runner).values(clean_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["race_id", "horse_id"],
        set_={k: v for k, v in clean_data.items() if k not in ["race_id", "horse_id"]},
    ).returning(Runner)

    result = db.execute(stmt)
    return result.scalar_one()


def upsert_horse_sectional(db: Session, sectional_data: dict[str, Any]) -> HorseSectional:
    """
    插入或更新 horse_sectional (使用 PostgreSQL ON CONFLICT UPSERT)
    Insert or update horse_sectional using PostgreSQL native ON CONFLICT (unique by runner_id + section_no)

    Args:
        db: Database session
        sectional_data: Dictionary with sectional fields including runner_id, section_no

    Returns:
        HorseSectional object
    """
    # Clean the data: remove fields that aren't in the HorseSectional model
    clean_data = sectional_data.copy()
    clean_data.pop("finish_order", None)
    clean_data.pop("horse_no", None)
    clean_data.pop("hkjc_horse_id", None)

    # Use PostgreSQL's native ON CONFLICT for true UPSERT in 1 query (was 2)
    stmt = insert(HorseSectional).values(clean_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["runner_id", "section_no"],
        set_={k: v for k, v in clean_data.items() if k not in ["runner_id", "section_no"]},
    ).returning(HorseSectional)

    result = db.execute(stmt)
    return result.scalar_one()


# ============================================================================
# High-level save function for complete race data
# ============================================================================


def save_race_data(db: Session, race_data: dict[str, Any]) -> dict[str, Any]:
    """
    儲存完整的賽事資料（meeting, race, horses, jockeys, trainers, runners, sectionals）
    Save complete race data including all related entities

    Args:
        db: Database session
        race_data: Dictionary with structure:
            {
                'meeting': {...},
                'race': {...},
                'horses': [{...}, ...],
                'jockeys': [{...}, ...],
                'trainers': [{...}, ...],
                'runners': [{...}, ...],
                'horse_sectionals': [{...}, ...]
            }

    Returns:
        Dictionary with saved object IDs
    """
    try:
        result = {}

        # 1. Save meeting
        meeting = upsert_meeting(db, race_data["meeting"])
        result["meeting_id"] = meeting.id

        # 2. Save race (with meeting_id)
        race_dict = race_data["race"].copy()
        race_dict["meeting_id"] = meeting.id
        race = upsert_race(db, race_dict)
        result["race_id"] = race.id

        # 3. Save horses and create (code, name_cn) -> horse_id mapping
        horse_map = {}  # (code, name_cn) -> horse_id
        for horse_data in race_data["horses"]:
            horse = upsert_horse(db, horse_data)
            horse_map[(horse.code, horse.name_cn)] = horse.id

            # If we have profile data (e.g. origin is set), create a history record
            # We check a few key profile fields to determine if we should save history
            # TODO: update insert horse history rule, only insert when the horse data has changed.
            if horse_data.get("origin") or horse_data.get("current_rating"):
                # Use horse_data directly as it now contains merged profile info
                insert_horse_history(db, horse.id, horse_data)

        # 4. Save jockeys and create name_cn -> jockey_id mapping
        jockey_map = {}  # name_cn -> jockey_id
        for jockey_data in race_data["jockeys"]:
            jockey = upsert_jockey(db, jockey_data)
            jockey_map[jockey.name_cn] = jockey.id

        # 5. Save trainers and create name_cn -> trainer_id mapping
        trainer_map = {}  # name_cn -> trainer_id
        for trainer_data in race_data["trainers"]:
            trainer = upsert_trainer(db, trainer_data)
            trainer_map[trainer.name_cn] = trainer.id

        # 6. Save runners (with FK resolution)
        runner_map = {}  # (horse_code, horse_name_cn) -> runner_id
        for runner_data in race_data["runners"]:
            runner_dict = runner_data.copy()

            # Resolve foreign keys
            runner_dict["race_id"] = race.id

            # Use composite key for lookup
            h_key = (runner_data["horse_code"], runner_data.get("horse_name_cn"))
            runner_dict["horse_id"] = horse_map[h_key]

            runner_dict["jockey_id"] = jockey_map.get(runner_data.get("jockey_name_cn"))
            runner_dict["trainer_id"] = trainer_map.get(runner_data.get("trainer_name_cn"))

            # Remove fields not in Runner model
            runner_dict.pop("horse_code", None)
            runner_dict.pop("horse_name_cn", None)  # Ensure this is popped
            runner_dict.pop("jockey_code", None)
            runner_dict.pop("trainer_code", None)

            runner = upsert_runner(db, runner_dict)
            runner_map[h_key] = runner.id

        result["runner_count"] = len(runner_map)

        # 7. Save horse sectionals (with FK resolution)
        sectional_count = 0
        for sectional_data in race_data.get("horse_sectionals", []):
            sectional_dict = sectional_data.copy()

            # Resolve foreign keys
            horse_code = sectional_data["horse_code"]
            horse_name_cn = sectional_data.get("horse_name_cn")
            h_key = (horse_code, horse_name_cn)

            sectional_dict["race_id"] = race.id
            sectional_dict["horse_id"] = horse_map[h_key]
            sectional_dict["runner_id"] = runner_map[h_key]

            # Remove code/name fields
            sectional_dict.pop("horse_code", None)
            sectional_dict.pop("horse_name_cn", None)

            upsert_horse_sectional(db, sectional_dict)
            sectional_count += 1

        result["sectional_count"] = sectional_count

        # 8. Save horse profiles (Removed - merged into step 3)
        # Profile data is now part of the 'horses' list and handled in step 3

        result["profile_count"] = len(race_data["horses"])  # approximate, or track real count above

        return result

    except IntegrityError as e:
        logger.warning(f"Duplicate data detected (race already exists): {e}")
        db.rollback()
        return {"race_id": None, "runner_count": 0, "sectional_count": 0, "profile_count": 0}
    except (OperationalError, SQLAlchemyError) as e:
        logger.error(f"Database error saving race: {e}")
        db.rollback()
        raise


def save_meeting_data(db: Session, meeting_data: list[dict[str, Any]]) -> dict[str, Any]:
    """
    儲存整個賽日的多場賽事資料
    Save all races for a meeting

    Note: Commits after EACH race to prevent timeout with large transactions.
    This is critical for Supabase to avoid "could not receive data from server" errors.

    Args:
        db: Database session
        meeting_data: List of race_data dictionaries (from scrape_meeting)

    Returns:
        Summary statistics
    """
    summary = {
        "races_saved": 0,
        "runners_saved": 0,
        "sectionals_saved": 0,
        "profiles_saved": 0,
    }

    for race_data in meeting_data:
        try:
            result = save_race_data(db, race_data)

            # CRITICAL: Commit after EACH race to prevent timeout with large transactions
            # This reduces transaction size from thousands of rows to ~100-200 rows per commit
            db.commit()

            # Update summary after successful commit
            summary["races_saved"] += 1
            summary["runners_saved"] += result["runner_count"]
            summary["sectionals_saved"] += result["sectional_count"]
            summary["profiles_saved"] += result.get("profile_count", 0)

        except Exception as e:
            # Rollback this race only, continue with next race
            db.rollback()
            logger.error(f"Failed to save race (rolling back): {e}")
            raise  # Re-raise to let caller handle

    return summary


# ============================================================================
# HK33 Odds and Offshore Market persistence
# ============================================================================


def upsert_hkjc_odds(db: Session, odds_data: dict[str, Any]) -> HkjcOdds:
    """
    插入或更新 hkjc 賠率 (使用 PostgreSQL ON CONFLICT UPSERT)
    Insert or update hkjc odds using PostgreSQL native ON CONFLICT
    (unique by runner_id + bet_type + recorded_at)

    Args:
        db: Database session
        odds_data: Dict with keys: race_id, runner_id, horse_id, bet_type,
                   odds_value, recorded_at, source_url

    Returns:
        HkjcOdds object
    """
    stmt = insert(HkjcOdds).values(odds_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["runner_id", "bet_type", "recorded_at"],
        set_={"odds_value": stmt.excluded.odds_value, "source_url": stmt.excluded.source_url, "scraped_at": func.now()},
    ).returning(HkjcOdds)

    result = db.execute(stmt)
    return result.scalar_one()


def upsert_offshore_market(db: Session, market_data: dict[str, Any]) -> OffshoreMarket:
    """
    插入或更新海外市場資料 (使用 PostgreSQL ON CONFLICT UPSERT)
    Insert or update offshore market data using PostgreSQL native ON CONFLICT
    (unique by runner_id + market_type + recorded_at)

    Args:
        db: Database session
        market_data: Dict with keys: race_id, runner_id, horse_id, market_type,
                     price, recorded_at, source_url

    Returns:
        OffshoreMarket object
    """
    stmt = insert(OffshoreMarket).values(market_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["runner_id", "market_type", "recorded_at"],
        set_={"price": stmt.excluded.price, "source_url": stmt.excluded.source_url, "scraped_at": func.now()},
    ).returning(OffshoreMarket)

    result = db.execute(stmt)
    return result.scalar_one()


def get_runner_map(db: Session, race_date: date, race_no: int) -> dict[int, tuple[int, int]]:
    """
    查詢資料庫以對應馬號到 runner_id 和 horse_id
    Query database to map horse_no → (runner_id, horse_id) for a race

    Args:
        db: Database session
        race_date: Date of the race
        race_no: Race number

    Returns:
        Dict mapping horse_no to (runner_id, horse_id)
        Example: {1: (123, 456), 2: (124, 457), ...}
    """
    stmt = (
        select(Runner.id, Runner.horse_id, Runner.horse_no)
        .join(Race, Runner.race_id == Race.id)
        .join(Meeting, Race.meeting_id == Meeting.id)
        .where(Meeting.date == race_date, Race.race_no == race_no)
    )

    results = db.execute(stmt).all()
    return {row.horse_no: (row.id, row.horse_id) for row in results if row.horse_no is not None}


@db_retry
def save_hk33_data(
    db: Session,
    race_id: int,
    race_date: date,
    runner_map: dict[int, tuple[int, int]],
    hkjc_data: list[dict],
    offshore_data: list[dict],
) -> dict[str, int]:
    """
    儲存 HK33 賠率和海外市場資料
    Save HK33 hkjc odds and offshore market data for a race

    Args:
        db: Database session
        race_id: ID of the race
        race_date: Date of the race (for timestamp conversion)
        runner_map: Dict mapping horse_no → (runner_id, horse_id)
        hkjc_data: List of hkjc odds records from scraper
        offshore_data: List of offshore market records from scraper

    Returns:
        Dict with counts: {'hkjc_saved': int, 'offshore_saved': int}
    """
    from hkjc_scraper.hk33_scraper import convert_timestamp_to_datetime

    hkjc_saved = 0
    offshore_saved = 0

    # Process hkjc odds
    for record in hkjc_data:
        horse_no = record["horse_no"]

        # Skip if horse not found in runner map
        if horse_no not in runner_map:
            logger.warning(f"Horse #{horse_no} not found in runner map, skipping odds record")
            continue

        runner_id, horse_id = runner_map[horse_no]

        # Convert timestamp to datetime
        recorded_at = convert_timestamp_to_datetime(race_date, record["timestamp_str"])

        # Prepare data for UPSERT
        odds_data = {
            "race_id": race_id,
            "runner_id": runner_id,
            "horse_id": horse_id,
            "bet_type": record["bet_type"],
            "odds_value": record["odds_value"],
            "recorded_at": recorded_at,
            "source_url": record.get("source_url"),
        }

        try:
            upsert_hkjc_odds(db, odds_data)
            hkjc_saved += 1
        except Exception as e:
            logger.error(f"Failed to save hkjc odds for horse #{horse_no}: {e}")
            continue

    # Process offshore market data
    for record in offshore_data:
        horse_no = record["horse_no"]

        # Skip if horse not found in runner map
        if horse_no not in runner_map:
            logger.warning(f"Horse #{horse_no} not found in runner map, skipping market record")
            continue

        runner_id, horse_id = runner_map[horse_no]

        # Convert timestamp to datetime
        recorded_at = convert_timestamp_to_datetime(race_date, record["timestamp_str"])

        # Prepare data for UPSERT
        market_data = {
            "race_id": race_id,
            "runner_id": runner_id,
            "horse_id": horse_id,
            "market_type": record["market_type"],
            "price": record["odds_value"],  # Note: 'odds_value' field contains price
            "recorded_at": recorded_at,
            "source_url": record.get("source_url"),
        }

        try:
            upsert_offshore_market(db, market_data)
            offshore_saved += 1
        except Exception as e:
            logger.error(f"Failed to save offshore market data for horse #{horse_no}: {e}")
            continue

    logger.info(f"Saved {hkjc_saved} hkjc odds and {offshore_saved} offshore market records")
    return {"hkjc_saved": hkjc_saved, "offshore_saved": offshore_saved}
