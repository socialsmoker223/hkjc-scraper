from sqlalchemy import select

from hkjc_scraper.models import Horse, HorseHistory
from hkjc_scraper.persistence import save_race_data


def test_save_race_data_merges_profile(test_db_session):
    """Test that save_race_data saves profile info into Horse table"""
    db = test_db_session

    # constructed race data with profile
    race_data = {
        "meeting": {
            "date": "2025/01/01",
            "venue_code": "ST",
        },
        "race": {"race_no": 1, "meeting_id": 1},
        "horses": [
            {
                "code": "H001",
                "name_cn": "馬匹一",
                "hkjc_horse_id": "HK_2025_H001",
                "origin": "AUS",
                "age": 4,
                "current_rating": 60,
                "owner_name": "Test Owner",
            }
        ],
        "jockeys": [],
        "trainers": [],
        "runners": [
            {
                "horse_code": "H001",
                "race_id": 1,
                "horse_id": 1,  # Mock ID, logic will resolve it
                # other fields needed by upsert_runner but cleaned
            }
        ],
        "horse_sectionals": [],
        # horse_profiles removed
    }

    # Execute
    save_race_data(db, race_data)

    # Verify Horse table has profile data
    stmt = select(Horse).where(Horse.code == "H001")
    horse = db.execute(stmt).scalar_one()

    assert horse.hkjc_horse_id == "HK_2025_H001"
    assert horse.origin == "AUS"
    assert horse.age == 4
    assert horse.current_rating == 60
    assert horse.owner_name == "Test Owner"

    # Verify History created with identity
    stmt_hist = select(HorseHistory).where(HorseHistory.horse_id == horse.id)
    history = db.execute(stmt_hist).scalars().all()
    assert len(history) == 1
    assert history[0].origin == "AUS"
    assert history[0].current_rating == 60
    assert history[0].code == "H001"
    assert history[0].name_cn == "馬匹一"
    assert history[0].hkjc_horse_id == "HK_2025_H001"


def test_update_existing_horse_profile(test_db_session):
    """Test updating existing horse profile data"""
    db = test_db_session

    # 1. Create horse
    horse = Horse(code="H002", name_cn="馬匹二", hkjc_horse_id="HK_2025_H002")
    db.add(horse)
    db.commit()

    # 2. Update with new profile data
    race_data = {
        "meeting": {"date": "2025/01/02", "venue_code": "HV"},
        "race": {"race_no": 1},
        "horses": [{"code": "H002", "hkjc_horse_id": "HK_2025_H002", "origin": "NZ", "current_rating": 55}],
        "jockeys": [],
        "trainers": [],
        "runners": [{"horse_code": "H002"}],
        # horse_profiles removed
    }

    save_race_data(db, race_data)

    # Verify update
    db.expire_all()
    updated_horse = db.get(Horse, horse.id)
    assert updated_horse.origin == "NZ"
    assert updated_horse.current_rating == 55
