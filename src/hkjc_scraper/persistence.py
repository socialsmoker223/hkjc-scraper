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
# Batch upsert functions for save_race_data optimization
# ============================================================================


def batch_upsert_horses(db: Session, horse_list: list[dict[str, Any]]) -> dict[tuple[str, str | None], int]:
    """
    批量插入或更新馬匹 (使用 PostgreSQL ON CONFLICT)
    Batch upsert horses. Returns mapping of (code, name_cn) -> horse_id.
    """
    if not horse_list:
        return {}

    # Deduplicate by conflict key (hkjc_horse_id) — last wins
    deduped = {r["hkjc_horse_id"]: r for r in horse_list if r.get("hkjc_horse_id")}
    unique_list = list(deduped.values())

    if not unique_list:
        return {}

    stmt = insert(Horse).values(unique_list)
    stmt = stmt.on_conflict_do_update(
        index_elements=["hkjc_horse_id"],
        set_={k: stmt.excluded[k] for k in unique_list[0] if k != "hkjc_horse_id"},
    ).returning(Horse.id, Horse.code, Horse.name_cn)

    rows = db.execute(stmt).all()
    return {(row.code, row.name_cn): row.id for row in rows}


def batch_insert_horse_history(db: Session, history_list: list[dict[str, Any]]) -> int:
    """
    批量插入馬匹歷史快照 (append-only, no conflict handling)
    Batch insert horse history snapshots. Returns count of inserted records.
    """
    if not history_list:
        return 0

    db.execute(insert(HorseHistory).values(history_list))
    return len(history_list)


def batch_upsert_jockeys(db: Session, jockey_list: list[dict[str, Any]]) -> dict[str, int]:
    """
    批量插入或更新騎師 (使用 PostgreSQL ON CONFLICT)
    Batch upsert jockeys. Returns mapping of name_cn -> jockey_id.
    """
    if not jockey_list:
        return {}

    # Deduplicate by conflict key (name_cn) — last wins
    deduped = {r["name_cn"]: r for r in jockey_list}
    unique_list = list(deduped.values())

    stmt = insert(Jockey).values(unique_list)
    stmt = stmt.on_conflict_do_update(
        index_elements=["name_cn"],
        set_={k: stmt.excluded[k] for k in unique_list[0] if k != "name_cn"},
    ).returning(Jockey.id, Jockey.name_cn)

    rows = db.execute(stmt).all()
    return {row.name_cn: row.id for row in rows}


def batch_upsert_trainers(db: Session, trainer_list: list[dict[str, Any]]) -> dict[str, int]:
    """
    批量插入或更新練馬師 (使用 PostgreSQL ON CONFLICT)
    Batch upsert trainers. Returns mapping of name_cn -> trainer_id.
    """
    if not trainer_list:
        return {}

    # Deduplicate by conflict key (name_cn) — last wins
    deduped = {r["name_cn"]: r for r in trainer_list}
    unique_list = list(deduped.values())

    stmt = insert(Trainer).values(unique_list)
    stmt = stmt.on_conflict_do_update(
        index_elements=["name_cn"],
        set_={k: stmt.excluded[k] for k in unique_list[0] if k != "name_cn"},
    ).returning(Trainer.id, Trainer.name_cn)

    rows = db.execute(stmt).all()
    return {row.name_cn: row.id for row in rows}


def batch_upsert_runners(db: Session, runner_list: list[dict[str, Any]]) -> dict[int, int]:
    """
    批量插入或更新出賽馬匹 (使用 PostgreSQL ON CONFLICT)
    Batch upsert runners. Returns mapping of horse_id -> runner_id.
    """
    if not runner_list:
        return {}

    # Deduplicate by conflict key (race_id, horse_id) — last wins
    deduped = {(r["race_id"], r["horse_id"]): r for r in runner_list}
    unique_list = list(deduped.values())

    stmt = insert(Runner).values(unique_list)
    stmt = stmt.on_conflict_do_update(
        index_elements=["race_id", "horse_id"],
        set_={k: stmt.excluded[k] for k in unique_list[0] if k not in ["race_id", "horse_id"]},
    ).returning(Runner.id, Runner.horse_id)

    rows = db.execute(stmt).all()
    return {row.horse_id: row.id for row in rows}


def batch_upsert_races(db: Session, race_list: list[dict[str, Any]]) -> dict[int, int]:
    """
    批量插入或更新賽事 (使用 PostgreSQL ON CONFLICT)
    Batch upsert races. Returns mapping of race_no -> race_id.
    """
    if not race_list:
        return {}

    # Deduplicate by conflict key (meeting_id, race_no) — last wins
    deduped = {(r["meeting_id"], r["race_no"]): r for r in race_list}
    unique_list = list(deduped.values())

    stmt = insert(Race).values(unique_list)
    stmt = stmt.on_conflict_do_update(
        index_elements=["meeting_id", "race_no"],
        set_={k: stmt.excluded[k] for k in unique_list[0] if k not in ["meeting_id", "race_no"]},
    ).returning(Race.id, Race.race_no)

    rows = db.execute(stmt).all()
    return {row.race_no: row.id for row in rows}


def _batch_upsert_runners_meeting(db: Session, runner_list: list[dict[str, Any]]) -> dict[tuple[int, int], int]:
    """
    批量插入或更新出賽馬匹 (meeting-level, keyed by race_id+horse_id)
    Batch upsert runners. Returns mapping of (race_id, horse_id) -> runner_id.

    Unlike batch_upsert_runners which keys by horse_id alone (sufficient within
    a single race), this variant keys by (race_id, horse_id) so it works across
    multiple races in a meeting.
    """
    if not runner_list:
        return {}

    # Deduplicate by conflict key (race_id, horse_id) — last wins
    deduped = {(r["race_id"], r["horse_id"]): r for r in runner_list}
    unique_list = list(deduped.values())

    stmt = insert(Runner).values(unique_list)
    stmt = stmt.on_conflict_do_update(
        index_elements=["race_id", "horse_id"],
        set_={k: stmt.excluded[k] for k in unique_list[0] if k not in ["race_id", "horse_id"]},
    ).returning(Runner.id, Runner.race_id, Runner.horse_id)

    rows = db.execute(stmt).all()
    return {(row.race_id, row.horse_id): row.id for row in rows}


def batch_upsert_horse_sectionals(db: Session, sectional_list: list[dict[str, Any]]) -> int:
    """
    批量插入或更新分段時間 (使用 PostgreSQL ON CONFLICT)
    Batch upsert horse sectionals. Returns count of records processed.
    """
    if not sectional_list:
        return 0

    # Deduplicate by conflict key (runner_id, section_no) — last wins
    deduped = {(r["runner_id"], r["section_no"]): r for r in sectional_list}
    unique_list = list(deduped.values())

    stmt = insert(HorseSectional).values(unique_list)
    stmt = stmt.on_conflict_do_update(
        index_elements=["runner_id", "section_no"],
        set_={k: stmt.excluded[k] for k in unique_list[0] if k not in ["runner_id", "section_no"]},
    )

    db.execute(stmt)
    return len(unique_list)


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

        # 1. Save meeting (single record)
        meeting = upsert_meeting(db, race_data["meeting"])
        result["meeting_id"] = meeting.id

        # 2. Save race (single record, with meeting_id)
        race_dict = race_data["race"].copy()
        race_dict["meeting_id"] = meeting.id
        race = upsert_race(db, race_dict)
        result["race_id"] = race.id

        # 3. Batch upsert horses → build (code, name_cn) -> horse_id mapping
        horse_map = batch_upsert_horses(db, race_data["horses"])

        # 3b. Batch insert horse history for horses with profile data
        history_batch = []
        history_valid_fields = {
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
        captured_at = datetime.now()
        for horse_data in race_data["horses"]:
            if horse_data.get("origin") or horse_data.get("current_rating"):
                h_key = (horse_data["code"], horse_data.get("name_cn"))
                horse_id = horse_map.get(h_key)
                if horse_id:
                    history_record = {"horse_id": horse_id, "captured_at": captured_at}
                    for k, v in horse_data.items():
                        if k in history_valid_fields:
                            history_record[k] = v
                    history_batch.append(history_record)
        batch_insert_horse_history(db, history_batch)

        # 4. Batch upsert jockeys → build name_cn -> jockey_id mapping
        jockey_map = batch_upsert_jockeys(db, race_data["jockeys"])

        # 5. Batch upsert trainers → build name_cn -> trainer_id mapping
        trainer_map = batch_upsert_trainers(db, race_data["trainers"])

        # 6. Batch upsert runners (with FK resolution)
        runner_batch = []
        for runner_data in race_data["runners"]:
            runner_dict = runner_data.copy()
            runner_dict["race_id"] = race.id

            h_key = (runner_data["horse_code"], runner_data.get("horse_name_cn"))
            runner_dict["horse_id"] = horse_map[h_key]

            runner_dict["jockey_id"] = jockey_map.get(runner_data.get("jockey_name_cn"))
            runner_dict["trainer_id"] = trainer_map.get(runner_data.get("trainer_name_cn"))

            # Remove fields not in Runner model
            runner_dict.pop("horse_code", None)
            runner_dict.pop("horse_name_cn", None)
            runner_dict.pop("jockey_code", None)
            runner_dict.pop("trainer_code", None)
            runner_dict.pop("hkjc_horse_id", None)
            runner_dict.pop("jockey_name_cn", None)
            runner_dict.pop("trainer_name_cn", None)

            runner_batch.append(runner_dict)

        # horse_id -> runner_id
        runner_id_map = batch_upsert_runners(db, runner_batch)
        result["runner_count"] = len(runner_id_map)

        # 7. Batch upsert horse sectionals (with FK resolution)
        sectional_batch = []
        for sectional_data in race_data.get("horse_sectionals", []):
            sectional_dict = sectional_data.copy()

            horse_code = sectional_data["horse_code"]
            horse_name_cn = sectional_data.get("horse_name_cn")
            h_key = (horse_code, horse_name_cn)

            horse_id = horse_map[h_key]
            runner_id = runner_id_map[horse_id]

            sectional_dict["race_id"] = race.id
            sectional_dict["horse_id"] = horse_id
            sectional_dict["runner_id"] = runner_id

            # Remove code/name fields not in model
            sectional_dict.pop("horse_code", None)
            sectional_dict.pop("horse_name_cn", None)
            sectional_dict.pop("finish_order", None)
            sectional_dict.pop("horse_no", None)
            sectional_dict.pop("hkjc_horse_id", None)

            sectional_batch.append(sectional_dict)

        result["sectional_count"] = batch_upsert_horse_sectionals(db, sectional_batch)
        result["profile_count"] = len(race_data["horses"])

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
    儲存整個賽日的多場賽事資料 (meeting-level batch)
    Save all races for a meeting using meeting-level batch operations.

    Aggregates all entities across races, then executes 8 batch operations in FK
    dependency order with a single commit. This reduces DB round-trips from
    ~88 (8 ops × 11 races) to ~8 total.

    Args:
        db: Database session
        meeting_data: List of race_data dictionaries (from scrape_meeting)

    Returns:
        Summary statistics
    """
    if not meeting_data:
        return {
            "races_saved": 0,
            "runners_saved": 0,
            "sectionals_saved": 0,
            "profiles_saved": 0,
        }

    try:
        # ================================================================
        # Phase 1: Aggregate all entities across races
        # ================================================================
        all_horses: list[dict[str, Any]] = []
        all_jockeys: list[dict[str, Any]] = []
        all_trainers: list[dict[str, Any]] = []
        all_races: list[dict[str, Any]] = []
        # Tagged with race_no for FK resolution later
        all_runners: list[tuple[int, dict[str, Any]]] = []  # (race_no, runner_data)
        all_sectionals: list[tuple[int, dict[str, Any]]] = []  # (race_no, sectional_data)
        all_horse_data_for_history: list[dict[str, Any]] = []  # raw horse dicts with profile data

        for race_data in meeting_data:
            race_no = race_data["race"]["race_no"]

            all_races.append(race_data["race"].copy())
            all_horses.extend(race_data["horses"])
            all_jockeys.extend(race_data["jockeys"])
            all_trainers.extend(race_data["trainers"])

            for runner in race_data["runners"]:
                all_runners.append((race_no, runner))

            for sectional in race_data.get("horse_sectionals", []):
                all_sectionals.append((race_no, sectional))

            # Collect horse data that has profile info for history
            for horse_data in race_data["horses"]:
                if horse_data.get("origin") or horse_data.get("current_rating"):
                    all_horse_data_for_history.append(horse_data)

        # ================================================================
        # Phase 2: Persist in FK dependency order (8 batch ops)
        # ================================================================

        # 1. Meeting (single record — same meeting for all races)
        meeting = upsert_meeting(db, meeting_data[0]["meeting"])
        meeting_id = meeting.id

        # 2. Races batch
        for race_dict in all_races:
            race_dict["meeting_id"] = meeting_id
        race_map = batch_upsert_races(db, all_races)  # {race_no: race_id}

        # 3. Horses batch (deduplicated across all races)
        horse_map = batch_upsert_horses(db, all_horses)  # {(code, name_cn): horse_id}

        # 4. Horse history batch (append-only)
        history_valid_fields = {
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
        captured_at = datetime.now()
        history_batch: list[dict[str, Any]] = []
        # Deduplicate history by hkjc_horse_id (same horse across races → one snapshot)
        seen_history_horses: set[str] = set()
        for horse_data in all_horse_data_for_history:
            hkjc_id = horse_data.get("hkjc_horse_id", "")
            if hkjc_id in seen_history_horses:
                continue
            seen_history_horses.add(hkjc_id)

            h_key = (horse_data["code"], horse_data.get("name_cn"))
            horse_id = horse_map.get(h_key)
            if horse_id:
                history_record: dict[str, Any] = {"horse_id": horse_id, "captured_at": captured_at}
                for k, v in horse_data.items():
                    if k in history_valid_fields:
                        history_record[k] = v
                history_batch.append(history_record)
        batch_insert_horse_history(db, history_batch)

        # 5. Jockeys batch (deduplicated across all races)
        jockey_map = batch_upsert_jockeys(db, all_jockeys)  # {name_cn: jockey_id}

        # 6. Trainers batch (deduplicated across all races)
        trainer_map = batch_upsert_trainers(db, all_trainers)  # {name_cn: trainer_id}

        # 7. Runners batch (all runners across all races, FKs resolved)
        runner_batch: list[dict[str, Any]] = []
        for race_no, runner_data in all_runners:
            runner_dict = runner_data.copy()
            runner_dict["race_id"] = race_map[race_no]

            h_key = (runner_data["horse_code"], runner_data.get("horse_name_cn"))
            runner_dict["horse_id"] = horse_map[h_key]
            runner_dict["jockey_id"] = jockey_map.get(runner_data.get("jockey_name_cn"))
            runner_dict["trainer_id"] = trainer_map.get(runner_data.get("trainer_name_cn"))

            # Remove fields not in Runner model
            for field in (
                "horse_code",
                "horse_name_cn",
                "jockey_code",
                "trainer_code",
                "hkjc_horse_id",
                "jockey_name_cn",
                "trainer_name_cn",
            ):
                runner_dict.pop(field, None)

            runner_batch.append(runner_dict)

        # Key by (race_id, horse_id) since same horse won't appear in same race twice
        # but could theoretically appear in different races
        runner_id_map = _batch_upsert_runners_meeting(db, runner_batch)
        # runner_id_map: {(race_id, horse_id): runner_id}

        # 8. Sectionals batch (all sectionals, FKs resolved)
        sectional_batch: list[dict[str, Any]] = []
        for race_no, sectional_data in all_sectionals:
            sectional_dict = sectional_data.copy()
            race_id = race_map[race_no]

            horse_code = sectional_data["horse_code"]
            horse_name_cn = sectional_data.get("horse_name_cn")
            h_key = (horse_code, horse_name_cn)

            horse_id = horse_map[h_key]
            runner_id = runner_id_map[(race_id, horse_id)]

            sectional_dict["race_id"] = race_id
            sectional_dict["horse_id"] = horse_id
            sectional_dict["runner_id"] = runner_id

            for field in ("horse_code", "horse_name_cn", "finish_order", "horse_no", "hkjc_horse_id"):
                sectional_dict.pop(field, None)

            sectional_batch.append(sectional_dict)

        sectional_count = batch_upsert_horse_sectionals(db, sectional_batch)

        # ================================================================
        # Single commit for entire meeting
        # ================================================================
        db.commit()

        return {
            "races_saved": len(race_map),
            "runners_saved": len(runner_id_map),
            "sectionals_saved": sectional_count,
            "profiles_saved": len(all_horses),
        }

    except IntegrityError as e:
        logger.warning(f"Duplicate data detected (meeting already exists): {e}")
        db.rollback()
        return {"races_saved": 0, "runners_saved": 0, "sectionals_saved": 0, "profiles_saved": 0}
    except (OperationalError, SQLAlchemyError) as e:
        logger.error(f"Database error saving meeting: {e}")
        db.rollback()
        raise


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


def batch_upsert_hkjc_odds(db: Session, odds_list: list[dict[str, Any]]) -> int:
    """
    批量插入或更新 HKJC 賠率 (使用 PostgreSQL ON CONFLICT)
    Batch insert/update HKJC odds using PostgreSQL ON CONFLICT.

    Args:
        db: Database session
        odds_list: List of odds dicts (race_id, runner_id, horse_id, bet_type,
                   odds_value, recorded_at, source_url)

    Returns:
        Number of records processed
    """
    if not odds_list:
        return 0

    # Deduplicate by conflict key (runner_id, bet_type, recorded_at) — last wins.
    # PostgreSQL ON CONFLICT cannot handle two rows with the same key in one INSERT.
    deduped = {(r["runner_id"], r["bet_type"], r["recorded_at"]): r for r in odds_list}
    unique_list = list(deduped.values())

    stmt = insert(HkjcOdds).values(unique_list)
    stmt = stmt.on_conflict_do_update(
        index_elements=["runner_id", "bet_type", "recorded_at"],
        set_={
            "odds_value": stmt.excluded.odds_value,
            "source_url": stmt.excluded.source_url,
            "scraped_at": func.now(),
        },
    )

    db.execute(stmt)
    return len(unique_list)


def batch_upsert_offshore_market(db: Session, market_list: list[dict[str, Any]]) -> int:
    """
    批量插入或更新海外市場資料 (使用 PostgreSQL ON CONFLICT)
    Batch insert/update offshore market data using PostgreSQL ON CONFLICT.

    Args:
        db: Database session
        market_list: List of market dicts (race_id, runner_id, horse_id, market_type,
                     price, recorded_at, source_url)

    Returns:
        Number of records processed
    """
    if not market_list:
        return 0

    # Deduplicate by conflict key (runner_id, market_type, recorded_at) — last wins.
    # PostgreSQL ON CONFLICT cannot handle two rows with the same key in one INSERT.
    deduped = {(r["runner_id"], r["market_type"], r["recorded_at"]): r for r in market_list}
    unique_list = list(deduped.values())

    stmt = insert(OffshoreMarket).values(unique_list)
    stmt = stmt.on_conflict_do_update(
        index_elements=["runner_id", "market_type", "recorded_at"],
        set_={
            "price": stmt.excluded.price,
            "source_url": stmt.excluded.source_url,
            "scraped_at": func.now(),
        },
    )

    db.execute(stmt)
    return len(unique_list)


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


def get_meeting_runner_maps(db: Session, race_date: date) -> dict[int, dict[int, tuple[int, int]]]:
    """
    批量查詢整個賽日的所有 runner 對應資料
    Pre-fetch runner maps for all races in a meeting.

    Args:
        db: Database session
        race_date: Date of the meeting

    Returns:
        Dict mapping race_no → {horse_no → (runner_id, horse_id)}
        Example: {1: {1: (123, 456), 2: (124, 457)}, 2: {1: (125, 458), ...}}
    """
    stmt = (
        select(Race.race_no, Runner.id, Runner.horse_id, Runner.horse_no)
        .join(Race, Runner.race_id == Race.id)
        .join(Meeting, Race.meeting_id == Meeting.id)
        .where(Meeting.date == race_date)
    )

    results = db.execute(stmt).all()

    # Group by race_no
    meeting_maps: dict[int, dict[int, tuple[int, int]]] = {}
    for row in results:
        race_no = row.race_no
        if race_no not in meeting_maps:
            meeting_maps[race_no] = {}
        if row.horse_no is not None:
            meeting_maps[race_no][row.horse_no] = (row.id, row.horse_id)

    return meeting_maps


def get_meeting_race_ids(db: Session, race_date: date) -> dict[int, int]:
    """
    批量查詢整個賽日的所有 race_id
    Pre-fetch race IDs for all races in a meeting.

    Args:
        db: Database session
        race_date: Date of the meeting

    Returns:
        Dict mapping race_no → race_id
        Example: {1: 101, 2: 102, 3: 103, ...}
    """
    stmt = select(Race.race_no, Race.id).join(Meeting, Race.meeting_id == Meeting.id).where(Meeting.date == race_date)

    results = db.execute(stmt).all()
    return {row.race_no: row.id for row in results}


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


@db_retry
def save_hk33_data_batch(
    db: Session,
    race_id: int,
    race_date: date,
    runner_map: dict[int, tuple[int, int]],
    hkjc_data: list[dict],
    offshore_data: list[dict],
) -> dict[str, int]:
    """
    批量儲存 HK33 賠率和海外市場資料 (OPTIMIZED)
    Save HK33 data using batch operations for better performance.

    This function builds batch lists and executes bulk UPSERTs instead of
    per-record operations, reducing database round-trips dramatically.

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

    # Build batch lists
    hkjc_batch = []
    offshore_batch = []

    # Process HKJC odds into batch list
    for record in hkjc_data:
        horse_no = record["horse_no"]

        if horse_no not in runner_map:
            logger.warning(f"Horse #{horse_no} not found in runner map, skipping odds record")
            continue

        runner_id, horse_id = runner_map[horse_no]
        recorded_at = convert_timestamp_to_datetime(race_date, record["timestamp_str"])

        hkjc_batch.append(
            {
                "race_id": race_id,
                "runner_id": runner_id,
                "horse_id": horse_id,
                "bet_type": record["bet_type"],
                "odds_value": record["odds_value"],
                "recorded_at": recorded_at,
                "source_url": record.get("source_url"),
            }
        )

    # Process offshore market into batch list
    for record in offshore_data:
        horse_no = record["horse_no"]

        if horse_no not in runner_map:
            logger.warning(f"Horse #{horse_no} not found in runner map, skipping market record")
            continue

        runner_id, horse_id = runner_map[horse_no]
        recorded_at = convert_timestamp_to_datetime(race_date, record["timestamp_str"])

        offshore_batch.append(
            {
                "race_id": race_id,
                "runner_id": runner_id,
                "horse_id": horse_id,
                "market_type": record["market_type"],
                "price": record["odds_value"],  # Note: 'odds_value' field contains price
                "recorded_at": recorded_at,
                "source_url": record.get("source_url"),
            }
        )

    # Execute batch upserts (2 operations instead of thousands)
    hkjc_saved = batch_upsert_hkjc_odds(db, hkjc_batch)
    offshore_saved = batch_upsert_offshore_market(db, offshore_batch)

    logger.debug(f"Batch saved {hkjc_saved} HKJC odds and {offshore_saved} offshore records")
    return {"hkjc_saved": hkjc_saved, "offshore_saved": offshore_saved}
