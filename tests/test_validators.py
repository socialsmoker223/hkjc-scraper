"""
Manual test cases for validators
Run with: uv run python tests/test_validators.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from decimal import Decimal

from hkjc_scraper.validators import (
    ValidationError,
    validate_distance,
    validate_draw,
    validate_horse_age,
    validate_horse_profile,
    validate_meeting,
    validate_odds,
    validate_position,
    validate_race,
    validate_runner,
    validate_weight,
)


def test_position():
    print("Testing position validation...")

    # Valid positions - numeric
    assert validate_position("1") == "1"
    assert validate_position("14") == "14"

    # Valid positions - special codes
    assert validate_position("PU") == "PU"
    assert validate_position("WD") == "WD"
    assert validate_position("DNF") == "DNF"

    # Valid positions - dead heats
    assert validate_position("1 平頭馬") == "1 平頭馬"
    assert validate_position("2 平頭馬") == "2 平頭馬"
    assert validate_position("3 平頭馬") == "3 平頭馬"

    # Invalid positions
    try:
        validate_position("0")
        raise AssertionError("Should raise ValidationError")
    except ValidationError:
        pass

    try:
        validate_position("15")
        raise AssertionError("Should raise ValidationError")
    except ValidationError:
        pass

    try:
        validate_position("15 平頭馬")  # Out of range dead heat
        raise AssertionError("Should raise ValidationError")
    except ValidationError:
        pass

    print("  ✓ Position validation passed")


def test_weight():
    print("Testing weight validation...")

    # Valid weights
    assert validate_weight(133, "actual_weight") == 133
    assert validate_weight(None, "actual_weight") is None

    # Invalid weights
    try:
        validate_weight(90, "actual_weight")
        raise AssertionError("Should raise ValidationError")
    except ValidationError:
        pass

    try:
        validate_weight(170, "actual_weight")
        raise AssertionError("Should raise ValidationError")
    except ValidationError:
        pass

    print("  ✓ Weight validation passed")


def test_odds():
    print("Testing odds validation...")

    # Valid odds
    assert validate_odds(Decimal("5.5")) == Decimal("5.5")
    assert validate_odds(None) is None

    # Invalid odds
    try:
        validate_odds(Decimal("0"))
        raise AssertionError("Should raise ValidationError")
    except ValidationError:
        pass

    try:
        validate_odds(Decimal("-1.5"))
        raise AssertionError("Should raise ValidationError")
    except ValidationError:
        pass

    print("  ✓ Odds validation passed")


def test_draw():
    print("Testing draw validation...")

    # Valid draw
    assert validate_draw(1) == 1
    assert validate_draw(14) == 14
    assert validate_draw(None) is None

    # Invalid draw
    try:
        validate_draw(0)
        raise AssertionError("Should raise ValidationError")
    except ValidationError:
        pass

    try:
        validate_draw(15)
        raise AssertionError("Should raise ValidationError")
    except ValidationError:
        pass

    print("  ✓ Draw validation passed")


def test_distance():
    print("Testing distance validation...")

    # Valid distance
    assert validate_distance(1200) == 1200
    assert validate_distance(None) is None

    # Invalid distance
    try:
        validate_distance(500)
        raise AssertionError("Should raise ValidationError")
    except ValidationError:
        pass

    try:
        validate_distance(3000)
        raise AssertionError("Should raise ValidationError")
    except ValidationError:
        pass

    print("  ✓ Distance validation passed")


def test_horse_age():
    print("Testing horse age validation...")

    # Valid age
    assert validate_horse_age(5) == 5
    assert validate_horse_age(None) is None

    # Invalid age
    try:
        validate_horse_age(1)
        raise AssertionError("Should raise ValidationError")
    except ValidationError:
        pass

    try:
        validate_horse_age(15)
        raise AssertionError("Should raise ValidationError")
    except ValidationError:
        pass

    print("  ✓ Horse age validation passed")


def test_runner():
    print("Testing runner validation...")

    # Valid runner
    valid_runner = {
        "horse_code": "J344",
        "finish_position_raw": "1",
        "actual_weight": 133,
        "declared_weight": 1100,  # Horse body weight (900-1400 lbs)
        "draw": 5,
        "win_odds": Decimal("5.5"),
    }
    validate_runner(valid_runner)  # Should not raise

    # Invalid runner (missing horse_code)
    invalid_runner = {
        "finish_position_raw": "1",
    }
    try:
        validate_runner(invalid_runner)
        raise AssertionError("Should raise ValidationError")
    except ValidationError:
        pass

    # Invalid runner (bad weight)
    invalid_runner2 = {
        "horse_code": "J344",
        "actual_weight": 200,
    }
    try:
        validate_runner(invalid_runner2)
        raise AssertionError("Should raise ValidationError")
    except ValidationError:
        pass

    print("  ✓ Runner validation passed")


def test_race():
    print("Testing race validation...")

    # Valid race
    valid_race = {
        "race_no": 5,
        "distance_m": 1200,
    }
    validate_race(valid_race)  # Should not raise

    # Invalid race (missing race_no)
    invalid_race = {
        "distance_m": 1200,
    }
    try:
        validate_race(invalid_race)
        raise AssertionError("Should raise ValidationError")
    except ValidationError:
        pass

    # Invalid race (bad race_no)
    invalid_race2 = {
        "race_no": 15,
    }
    try:
        validate_race(invalid_race2)
        raise AssertionError("Should raise ValidationError")
    except ValidationError:
        pass

    print("  ✓ Race validation passed")


def test_meeting():
    print("Testing meeting validation...")

    # Valid meeting
    valid_meeting = {
        "date": "2025/12/23",
        "venue_code": "ST",
    }
    validate_meeting(valid_meeting)  # Should not raise

    # Invalid meeting (missing date)
    invalid_meeting = {
        "venue_code": "ST",
    }
    try:
        validate_meeting(invalid_meeting)
        raise AssertionError("Should raise ValidationError")
    except ValidationError:
        pass

    # Invalid meeting (bad venue_code)
    invalid_meeting2 = {
        "date": "2025/12/23",
        "venue_code": "XX",
    }
    try:
        validate_meeting(invalid_meeting2)
        raise AssertionError("Should raise ValidationError")
    except ValidationError:
        pass

    print("  ✓ Meeting validation passed")


def test_horse_profile():
    print("Testing horse profile validation...")

    # Valid profile
    valid_profile = {
        "age": 5,
        "record_wins": 3,
        "record_seconds": 2,
        "record_thirds": 1,
        "record_starts": 10,
        "season_prize_hkd": 500000,
        "lifetime_prize_hkd": 2000000,
    }
    validate_horse_profile(valid_profile)  # Should not raise

    # Invalid profile (wins + seconds + thirds > starts)
    invalid_profile = {
        "record_wins": 5,
        "record_seconds": 5,
        "record_thirds": 5,
        "record_starts": 10,
    }
    try:
        validate_horse_profile(invalid_profile)
        raise AssertionError("Should raise ValidationError")
    except ValidationError:
        pass

    # Invalid profile (season > lifetime)
    invalid_profile2 = {
        "season_prize_hkd": 3000000,
        "lifetime_prize_hkd": 2000000,
    }
    try:
        validate_horse_profile(invalid_profile2)
        raise AssertionError("Should raise ValidationError")
    except ValidationError:
        pass

    # Invalid age
    invalid_profile3 = {
        "age": 15,
    }
    try:
        validate_horse_profile(invalid_profile3)
        raise AssertionError("Should raise ValidationError")
    except ValidationError:
        pass

    print("  ✓ Horse profile validation passed")


if __name__ == "__main__":
    print("Running validator tests...\n")
    test_position()
    test_weight()
    test_odds()
    test_draw()
    test_distance()
    test_horse_age()
    test_runner()
    test_race()
    test_meeting()
    test_horse_profile()
    print("\n✓ All tests passed!")
