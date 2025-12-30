# Horse Profile Scraping - Implementation Summary

## Status: ✅ COMPLETE

Horse profile scraping has been successfully implemented and integrated into the HKJC scraper.

## What Was Implemented

### 1. Parsing Function (`hkjc_scraper.py:322-479`)
- **Function:** `scrape_horse_profile(hkjc_horse_id: str)`
- **Parses 21 fields** from Horse.aspx:
  - Basic info: origin, age, colour, sex, import_type
  - Statistics: season_prize_hkd, lifetime_prize_hkd
  - Record: wins, seconds, thirds, starts, last10_starts
  - Location: current_location, current_location_date, import_date
  - Ownership: owner_name
  - Ratings: current_rating, season_start_rating
  - Pedigree: sire_name, dam_name, dam_sire_name

### 2. Persistence Layer (`persistence.py:397-427`)
- **Updated:** `save_race_data()` to save horse profiles
- **Uses existing functions:**
  - `upsert_horse_profile()` - Updates current profile
  - `insert_horse_profile_history()` - Saves historical snapshot

### 3. Main Scraping Flow (`hkjc_scraper.py:609-674`)
- **Updated:** `scrape_meeting()` always scrapes horse profiles
- **Features:**
  - Deduplication (tracks scraped horses across races)
  - Error handling (continues on profile scraping failures)
  - Progress logging

### 4. CLI Integration (`main.py:33-110`)
- **Updated output:** Always shows profile count in summary

## Usage

### Command Line

```bash
# Scrape races (horse profiles always included)
python main.py 2025/12/23

# Dry run
python main.py 2025/12/23 --dry-run

# Using Makefile
make scrape DATE=2025/12/23
make dry-run DATE=2025/12/23
```

### Python Code

```python
from hkjc_scraper import scrape_meeting, scrape_horse_profile

# Scrape a single horse profile
profile = scrape_horse_profile('HK_2023_J344')
print(f"Horse: {profile['origin']}, Age: {profile['age']}")

# Scrape meeting (profiles always included)
races = scrape_meeting('2025/12/23')
for race in races:
    profiles = race.get('horse_profiles', [])
    print(f"Race {race['race']['race_no']}: {len(profiles)} profiles")
```

## Test Results

**Test Horse:** HK_2023_J344 (歷險大將)
**Result:** ✅ 21/21 fields (100%)

Sample output:
```
  Origin: 紐西蘭 | Age: 4
  Colour: 棗 | Sex: 閹
  Record: 1-0-0/11
  Prize Money: Season $490,000 | Total $490,000
  Rating: Current 29 | Season Start 33
  Pedigree: Ardrossan x Queen Of Pop (by Pins)
  Owner: 余智偉與Dr Jennie Peterson Yu
```

## Database Schema

Profiles are saved to two tables:

1. **horse_profile** - Current snapshot (1:1 with horse)
2. **horse_profile_history** - Historical changes (N:1 with horse)

Both tables are automatically populated during scraping.

## Performance Impact

- **Per race:** ~10-15 seconds (includes profile scraping)
- **Profile scraping:** Always enabled for complete data

## Known Limitations

1. **No English names:** HKJC Chinese site doesn't include English horse names in profiles
2. **Manual parsing:** Uses HTML table parsing (no official API)
3. **Rate limiting:** No rate limiting yet (recommended for production)

## Next Steps (Roadmap Phase 3)

- Add error handling and retry logic
- Implement rate limiting
- Add logging instead of print statements
- Add profile update detection (only save history if changed)

## Files Changed

1. `hkjc_scraper.py` - Added parsing and integration
2. `persistence.py` - Updated save function
3. `main.py` - Added CLI flag and output
4. (Existing) `models.py` - HorseProfile, HorseProfileHistory models
5. (Existing) `schema.sql` - Database schema

**Lines of Code Added:** ~180 lines
**Total Implementation Time:** ~2 hours
**Test Coverage:** Manual testing only (no automated tests yet)
