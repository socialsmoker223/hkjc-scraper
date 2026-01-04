"""
Data persistence layer with UPSERT operations
資料持久化層，提供 UPSERT 操作
"""

from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hkjc_scraper.models import (
    Horse,
    HorseProfile,
    HorseProfileHistory,
    HorseSectional,
    Jockey,
    Meeting,
    Race,
    Runner,
    Trainer,
)

# ============================================================================
# Meeting and Race persistence
# ============================================================================


def upsert_meeting(db: Session, meeting_data: dict[str, Any]) -> Meeting:
    """
    插入或更新 meeting
    Insert or update meeting (unique by date + venue_code)

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
    # Note: 'season' is now a valid field in Meeting model, so we don't pop it

    stmt = select(Meeting).where(Meeting.date == clean_data["date"], Meeting.venue_code == clean_data["venue_code"])
    meeting = db.execute(stmt).scalar_one_or_none()

    if meeting:
        # Update existing
        for key, value in clean_data.items():
            setattr(meeting, key, value)
    else:
        # Insert new
        meeting = Meeting(**clean_data)
        db.add(meeting)

    db.flush()  # Get the ID without committing
    return meeting


def upsert_race(db: Session, race_data: dict[str, Any]) -> Race:
    """
    插入或更新 race
    Insert or update race (unique by meeting_id + race_no)

    Args:
        db: Database session
        race_data: Dictionary with race fields including meeting_id

    Returns:
        Race object
    """
    stmt = select(Race).where(Race.meeting_id == race_data["meeting_id"], Race.race_no == race_data["race_no"])
    race = db.execute(stmt).scalar_one_or_none()

    if race:
        # Update existing
        for key, value in race_data.items():
            setattr(race, key, value)
    else:
        # Insert new
        race = Race(**race_data)
        db.add(race)

    db.flush()
    return race


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
    插入或更新 horse
    Insert or update horse (unique by code)

    Args:
        db: Database session
        horse_data: Dictionary with keys: code, name_cn, name_en, hkjc_horse_id, profile_url

    Returns:
        Horse object
    """
    stmt = select(Horse).where(Horse.code == horse_data["code"])
    horse = db.execute(stmt).scalar_one_or_none()

    if horse:
        # Update existing
        for key, value in horse_data.items():
            if key != "code":  # Don't update the unique key
                setattr(horse, key, value)
    else:
        # Insert new
        horse = Horse(**horse_data)
        db.add(horse)

    db.flush()
    return horse


def upsert_jockey(db: Session, jockey_data: dict[str, Any]) -> Jockey:
    """
    插入或更新 jockey
    Insert or update jockey (unique by code)

    Args:
        db: Database session
        jockey_data: Dictionary with keys: code, name_cn, name_en

    Returns:
        Jockey object
    """
    stmt = select(Jockey).where(Jockey.code == jockey_data["code"])
    jockey = db.execute(stmt).scalar_one_or_none()

    if jockey:
        # Update existing
        for key, value in jockey_data.items():
            if key != "code":
                setattr(jockey, key, value)
    else:
        # Insert new
        jockey = Jockey(**jockey_data)
        db.add(jockey)

    db.flush()
    return jockey


def upsert_trainer(db: Session, trainer_data: dict[str, Any]) -> Trainer:
    """
    插入或更新 trainer
    Insert or update trainer (unique by code)

    Args:
        db: Database session
        trainer_data: Dictionary with keys: code, name_cn, name_en

    Returns:
        Trainer object
    """
    stmt = select(Trainer).where(Trainer.code == trainer_data["code"])
    trainer = db.execute(stmt).scalar_one_or_none()

    if trainer:
        # Update existing
        for key, value in trainer_data.items():
            if key != "code":
                setattr(trainer, key, value)
    else:
        # Insert new
        trainer = Trainer(**trainer_data)
        db.add(trainer)

    db.flush()
    return trainer


# ============================================================================
# Horse Profile persistence
# ============================================================================


def upsert_horse_profile(db: Session, horse_id: int, profile_data: dict[str, Any]) -> HorseProfile:
    """
    插入或更新 horse_profile (最新快照)
    Insert or update horse_profile (current snapshot, unique by horse_id)

    Args:
        db: Database session
        horse_id: Horse ID
        profile_data: Dictionary with profile fields

    Returns:
        HorseProfile object
    """
    stmt = select(HorseProfile).where(HorseProfile.horse_id == horse_id)
    profile = db.execute(stmt).scalar_one_or_none()

    if profile:
        # Update existing
        for key, value in profile_data.items():
            setattr(profile, key, value)
    else:
        # Insert new
        profile = HorseProfile(horse_id=horse_id, **profile_data)
        db.add(profile)

    db.flush()
    return profile


def insert_horse_profile_history(
    db: Session, horse_id: int, profile_data: dict[str, Any], captured_at: Optional[datetime] = None
) -> HorseProfileHistory:
    """
    插入 horse_profile_history 快照
    Insert horse_profile_history snapshot

    Args:
        db: Database session
        horse_id: Horse ID
        profile_data: Dictionary with profile fields
        captured_at: Timestamp of capture (defaults to now)

    Returns:
        HorseProfileHistory object
    """
    if captured_at is None:
        captured_at = datetime.now()

    history = HorseProfileHistory(horse_id=horse_id, captured_at=captured_at, **profile_data)
    db.add(history)
    db.flush()
    return history


# ============================================================================
# Runner and Sectional persistence
# ============================================================================


def upsert_runner(db: Session, runner_data: dict[str, Any]) -> Runner:
    """
    插入或更新 runner
    Insert or update runner (unique by race_id + horse_id)

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

    stmt = select(Runner).where(Runner.race_id == clean_data["race_id"], Runner.horse_id == clean_data["horse_id"])
    runner = db.execute(stmt).scalar_one_or_none()

    if runner:
        # Update existing
        for key, value in clean_data.items():
            setattr(runner, key, value)
    else:
        # Insert new
        runner = Runner(**clean_data)
        db.add(runner)

    db.flush()
    return runner


def upsert_horse_sectional(db: Session, sectional_data: dict[str, Any]) -> HorseSectional:
    """
    插入或更新 horse_sectional
    Insert or update horse_sectional (unique by runner_id + section_no)

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

    stmt = select(HorseSectional).where(
        HorseSectional.runner_id == clean_data["runner_id"], HorseSectional.section_no == clean_data["section_no"]
    )
    sectional = db.execute(stmt).scalar_one_or_none()

    if sectional:
        # Update existing
        for key, value in clean_data.items():
            setattr(sectional, key, value)
    else:
        # Insert new
        sectional = HorseSectional(**clean_data)
        db.add(sectional)

    db.flush()
    return sectional


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
    result = {}

    # 1. Save meeting
    meeting = upsert_meeting(db, race_data["meeting"])
    result["meeting_id"] = meeting.id

    # 2. Save race (with meeting_id)
    race_dict = race_data["race"].copy()
    race_dict["meeting_id"] = meeting.id
    race = upsert_race(db, race_dict)
    result["race_id"] = race.id

    # 3. Save horses and create code -> horse_id mapping
    horse_map = {}  # code -> horse_id
    for horse_data in race_data["horses"]:
        horse = upsert_horse(db, horse_data)
        horse_map[horse.code] = horse.id

    # 4. Save jockeys and create code -> jockey_id mapping
    jockey_map = {}  # code -> jockey_id
    for jockey_data in race_data["jockeys"]:
        jockey = upsert_jockey(db, jockey_data)
        jockey_map[jockey.code] = jockey.id

    # 5. Save trainers and create code -> trainer_id mapping
    trainer_map = {}  # code -> trainer_id
    for trainer_data in race_data["trainers"]:
        trainer = upsert_trainer(db, trainer_data)
        trainer_map[trainer.code] = trainer.id

    # 6. Save runners (with FK resolution)
    runner_map = {}  # horse_code -> runner_id
    for runner_data in race_data["runners"]:
        runner_dict = runner_data.copy()

        # Resolve foreign keys
        runner_dict["race_id"] = race.id
        runner_dict["horse_id"] = horse_map[runner_data["horse_code"]]
        runner_dict["jockey_id"] = jockey_map.get(runner_data.get("jockey_code"))
        runner_dict["trainer_id"] = trainer_map.get(runner_data.get("trainer_code"))

        # Remove code fields (not in Runner model)
        runner_dict.pop("horse_code", None)
        runner_dict.pop("jockey_code", None)
        runner_dict.pop("trainer_code", None)

        runner = upsert_runner(db, runner_dict)
        runner_map[runner_data["horse_code"]] = runner.id

    result["runner_count"] = len(runner_map)

    # 7. Save horse sectionals (with FK resolution)
    sectional_count = 0
    for sectional_data in race_data.get("horse_sectionals", []):
        sectional_dict = sectional_data.copy()

        # Resolve foreign keys
        horse_code = sectional_data["horse_code"]
        sectional_dict["race_id"] = race.id
        sectional_dict["horse_id"] = horse_map[horse_code]
        sectional_dict["runner_id"] = runner_map[horse_code]

        # Remove code field
        sectional_dict.pop("horse_code", None)

        upsert_horse_sectional(db, sectional_dict)
        sectional_count += 1

    result["sectional_count"] = sectional_count

    # 8. Save horse profiles (if provided)
    profile_count = 0
    for profile_data in race_data.get("horse_profiles", []):
        # Match profile to horse by hkjc_horse_id
        hkjc_horse_id = profile_data.get("hkjc_horse_id")
        if not hkjc_horse_id:
            continue

        # Find the horse_id for this hkjc_horse_id
        horse_id = None
        for code, h_id in horse_map.items():
            # Find the horse object to get its hkjc_horse_id
            for horse_data in race_data["horses"]:
                if horse_data["code"] == code and horse_data.get("hkjc_horse_id") == hkjc_horse_id:
                    horse_id = h_id
                    break
            if horse_id:
                break

        if horse_id:
            profile_dict = profile_data.copy()
            profile_dict.pop("hkjc_horse_id", None)  # Remove matching field

            # Update current profile
            upsert_horse_profile(db, horse_id, profile_dict)

            # Save to history (with current timestamp)
            insert_horse_profile_history(db, horse_id, profile_dict)
            profile_count += 1

    result["profile_count"] = profile_count

    return result


def save_meeting_data(db: Session, meeting_data: list[dict[str, Any]]) -> dict[str, Any]:
    """
    儲存整個賽日的多場賽事資料
    Save all races for a meeting

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
        result = save_race_data(db, race_data)
        summary["races_saved"] += 1
        summary["runners_saved"] += result["runner_count"]
        summary["sectionals_saved"] += result["sectional_count"]
        summary["profiles_saved"] += result.get("profile_count", 0)

    db.commit()

    return summary
