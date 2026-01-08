"""
Data validation for scraped HKJC racing data
資料驗證模組
"""

import logging
from decimal import Decimal
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom exception for validation failures"""

    pass


class ValidationResult:
    """Container for validation results"""

    def __init__(self):
        self.valid_records: list[dict[str, Any]] = []
        self.invalid_records: list[tuple[dict[str, Any], str]] = []  # (record, reason)

    @property
    def valid_count(self) -> int:
        return len(self.valid_records)

    @property
    def invalid_count(self) -> int:
        return len(self.invalid_records)

    @property
    def total_count(self) -> int:
        return self.valid_count + self.invalid_count

    def add_valid(self, record: dict[str, Any]):
        self.valid_records.append(record)

    def add_invalid(self, record: dict[str, Any], reason: str):
        self.invalid_records.append((record, reason))
        logger.warning(f"Invalid record skipped: {reason} | Record: {record}")

    def summary(self) -> dict[str, int]:
        return {
            "total": self.total_count,
            "valid": self.valid_count,
            "invalid": self.invalid_count,
        }


# ============================================================================
# Field-Level Validators
# ============================================================================


def validate_position(position_raw: Optional[str]) -> Optional[str]:
    """
    Validate finish position (1-14 or special codes)

    Valid values:
        - "1", "2", ..., "14" (numeric positions)
        - "PU", "WD", "RO", "DNF", "DQ", "F", "WV" (special codes)
        - "1 平頭馬", "2 平頭馬", etc. (dead heats in Traditional Chinese)
    Returns: position_raw if valid, raises ValidationError if invalid
    """
    if not position_raw:
        raise ValidationError("Position is required")

    # Numeric position: 1-14
    if position_raw.isdigit():
        pos_num = int(position_raw)
        if not (1 <= pos_num <= 14):
            raise ValidationError(f"Position number must be 1-14, got: {pos_num}")
        return position_raw

    # Dead heat pattern: "1 平頭馬", "2 平頭馬", etc.
    if "平頭馬" in position_raw:
        # Extract the numeric part before "平頭馬"
        try:
            pos_part = position_raw.split()[0]  # Get first part before space
            if pos_part.isdigit():
                pos_num = int(pos_part)
                if 1 <= pos_num <= 14:
                    return position_raw  # Valid dead heat position
        except (IndexError, ValueError):
            pass  # Fall through to error

    # Special codes
    valid_codes = [
        "DISQ",  # 取消資格
        "DNF",  # 未有跑畢全程
        "FE",  # 馬匹在賽事中跌倒
        "ML",  # 多個馬位
        "PU",  # 拉停
        "TNP",  # 并無參賽競逐
        "TO",  # 遙遙落後
        "UR",  # 騎師墮馬
        "VOID",  # 賽事無效
        "WD",   # 退出
        "WR",  # 司閘員著令退出
        "WV",  # 因健康理由宣佈退出
        "WV-A",  # 因健康理由於騎師過磅后宣佈退出
        "WX",  # 競賽董事小組著令退出
        "WX-A",  # 於騎師過磅後被競賽董事小組著令退出
        "WXNR",  # 競賽董事小組著令退出，視作無出賽馬匹
    ]
    if position_raw not in valid_codes:
        raise ValidationError(
            f"Invalid position code: {position_raw}, expected numeric (1-14), "
            f"dead heat (e.g. '1 平頭馬'), or special codes {valid_codes}"
        )

    return position_raw


def validate_weight(weight: Optional[int], field_name: str) -> Optional[int]:
    """
    Validate horse weight

    Args:
        weight: Weight in pounds
        field_name: "actual_weight" or "declared_weight" (for error messages)

    Returns: weight if valid, raises ValidationError if invalid

    Note:
        - actual_weight: Handicap weight (95-165 lbs)
        - declared_weight: Horse body weight at draw (900-1400 lbs)
    """
    if weight is None:
        return None  # Optional field

    if not isinstance(weight, int):
        raise ValidationError(f"{field_name} must be integer, got: {type(weight)}")

    # Different validation ranges for different weight types
    if field_name == "actual_weight":
        # Handicap weight range
        if not (95 <= weight <= 165):
            raise ValidationError(f"{field_name} must be 95-165 lbs, got: {weight}")
    elif field_name == "declared_weight":
        # Horse body weight range
        if not (900 <= weight <= 1400):
            raise ValidationError(f"{field_name} must be 900-1400 lbs (horse body weight), got: {weight}")
    else:
        # Fallback for unknown field names - use handicap weight range
        if not (95 <= weight <= 165):
            raise ValidationError(f"{field_name} must be 95-165 lbs, got: {weight}")

    return weight


def validate_odds(odds: Optional[Decimal]) -> Optional[Decimal]:
    """
    Validate win odds (must be positive)

    Returns: odds if valid, raises ValidationError if invalid
    """
    if odds is None:
        return None  # Optional for scratched horses

    if not isinstance(odds, Decimal):
        raise ValidationError(f"Odds must be Decimal, got: {type(odds)}")

    if odds <= 0:
        raise ValidationError(f"Odds must be positive, got: {odds}")

    return odds


def validate_draw(draw: Optional[int]) -> Optional[int]:
    """
    Validate draw position (1-14)

    Returns: draw if valid, raises ValidationError if invalid
    """
    if draw is None:
        return None  # Optional for scratched horses

    if not isinstance(draw, int):
        raise ValidationError(f"Draw must be integer, got: {type(draw)}")

    if not (1 <= draw <= 14):
        raise ValidationError(f"Draw must be 1-14, got: {draw}")

    return draw


def validate_distance(distance_m: Optional[int]) -> Optional[int]:
    """
    Validate race distance (1000-2850 meters)

    Returns: distance_m if valid, raises ValidationError if invalid
    """
    if distance_m is None:
        return None  # Optional field

    if not isinstance(distance_m, int):
        raise ValidationError(f"Distance must be integer, got: {type(distance_m)}")

    if not (1000 <= distance_m <= 2850):
        raise ValidationError(f"Distance must be 1000-2850m, got: {distance_m}")

    return distance_m


def validate_horse_age(age: Optional[int]) -> Optional[int]:
    """
    Validate horse age (2-14)

    Returns: age if valid, raises ValidationError if invalid
    """
    if age is None:
        return None  # Optional field

    if not isinstance(age, int):
        raise ValidationError(f"Age must be integer, got: {type(age)}")

    if not (2 <= age <= 14):
        raise ValidationError(f"Age must be 2-14, got: {age}")

    return age


# ============================================================================
# Entity-Level Validators
# ============================================================================


def validate_runner(runner: dict[str, Any]) -> None:
    """
    Validate runner record (single horse in single race)

    Raises: ValidationError if validation fails
    """
    # Required fields
    required = ["horse_code", "horse_name_cn"]
    for field in required:
        if not runner.get(field):
            raise ValidationError(f"Required field missing: {field}")

    # Position
    if "finish_position_raw" in runner:
        validate_position(runner["finish_position_raw"])

    # Weights
    if "actual_weight" in runner:
        validate_weight(runner["actual_weight"], "actual_weight")
    if "declared_weight" in runner:
        validate_weight(runner["declared_weight"], "declared_weight")

    # Odds
    if "win_odds" in runner:
        validate_odds(runner["win_odds"])

    # Draw
    if "draw" in runner:
        validate_draw(runner["draw"])


def validate_race(race: dict[str, Any]) -> None:
    """
    Validate race record

    Raises: ValidationError if validation fails
    """
    # Required fields
    required = ["race_no"]
    for field in required:
        if not race.get(field):
            raise ValidationError(f"Required field missing: {field}")

    # Race number (1-12 typical, up to 14 for special days)
    race_no = race.get("race_no")
    if race_no and not (1 <= race_no <= 14):
        raise ValidationError(f"Race number must be 1-14, got: {race_no}")

    # Distance
    if "distance_m" in race:
        validate_distance(race["distance_m"])


def validate_meeting(meeting: dict[str, Any]) -> None:
    """
    Validate meeting record

    Raises: ValidationError if validation fails
    """
    # Required fields
    required = ["date", "venue_code"]
    for field in required:
        if not meeting.get(field):
            raise ValidationError(f"Required field missing: {field}")

    # Venue code (ST or HV)
    venue_code = meeting.get("venue_code")
    if venue_code and venue_code not in ["ST", "HV"]:
        raise ValidationError(f"Venue code must be ST or HV, got: {venue_code}")

    # Date validation (should be date object or string in YYYY/MM/DD format)
    date_val = meeting.get("date")
    if isinstance(date_val, str):
        # Simple format check (full parsing done in persistence layer)
        if not date_val.count("/") == 2:
            raise ValidationError(f"Date must be in YYYY/MM/DD format, got: {date_val}")


def validate_horse_profile(profile: dict[str, Any]) -> None:
    """
    Validate horse profile record

    Raises: ValidationError if validation fails
    """
    # Age validation
    if "age" in profile:
        validate_horse_age(profile["age"])

    # Record consistency: wins + seconds + thirds <= starts
    wins = profile.get("record_wins", 0) or 0
    seconds = profile.get("record_seconds", 0) or 0
    thirds = profile.get("record_thirds", 0) or 0
    starts = profile.get("record_starts", 0) or 0

    if starts > 0:  # Only validate if starts is set
        total_placements = wins + seconds + thirds
        if total_placements > starts:
            raise ValidationError(
                f"Invalid record: wins({wins}) + seconds({seconds}) + thirds({thirds}) = "
                f"{total_placements} > starts({starts})"
            )

    # Prize consistency: season_prize <= lifetime_prize
    season_prize = profile.get("season_prize_hkd", 0) or 0
    lifetime_prize = profile.get("lifetime_prize_hkd", 0) or 0

    if season_prize > 0 and lifetime_prize > 0:  # Only validate if both set
        if season_prize > lifetime_prize:
            raise ValidationError(f"Invalid prize: season_prize({season_prize}) > lifetime_prize({lifetime_prize})")


# ============================================================================
# Batch Validators
# ============================================================================


def validate_runners(runners: list[dict[str, Any]]) -> ValidationResult:
    """
    Validate list of runner records

    Returns: ValidationResult with valid/invalid records separated
    """
    result = ValidationResult()

    for runner in runners:
        try:
            validate_runner(runner)
            result.add_valid(runner)
        except ValidationError as e:
            result.add_invalid(runner, str(e))

    return result


def validate_horse_profiles(profiles: list[dict[str, Any]]) -> ValidationResult:
    """
    Validate list of horse profile records

    Returns: ValidationResult with valid/invalid records separated
    """
    result = ValidationResult()

    for profile in profiles:
        try:
            validate_horse_profile(profile)
            result.add_valid(profile)
        except ValidationError as e:
            result.add_invalid(profile, str(e))

    return result
