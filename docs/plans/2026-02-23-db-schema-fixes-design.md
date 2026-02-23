# DB Schema Fixes — Design Document

**Date**: 2026-02-23
**Branch**: `review/database-design-and-data-models`
**Scope**: Issues 1+2, 4, 5, 8 from the database design review

---

## Issues 1+2 — Enforce `hkjc_horse_id NOT NULL`

### Problem

`batch_upsert_horses` silently filters out horses with a NULL `hkjc_horse_id`:

```python
deduped = {r["hkjc_horse_id"]: r for r in horse_list if r.get("hkjc_horse_id")}
```

These horses are never inserted. `hkjc_horse_id` is the conflict key for all horse upserts, so a NULL value means the record is simply discarded without any error. `hkjc_horse_id` should always be present — if it is missing, that indicates a scraping failure that must be surfaced, not swallowed.

### Design

**`models.py`**
- Change `hkjc_horse_id` from `Optional[str]` to `str` (non-nullable)
- Remove `Optional` type annotation; add `nullable=False` to the column definition

**Alembic migration**
- `ALTER TABLE horse ALTER COLUMN hkjc_horse_id SET NOT NULL`
- Note: any existing rows with NULL `hkjc_horse_id` must be resolved before running migration

**`persistence.py` — `batch_upsert_horses`**
- Remove the `if r.get("hkjc_horse_id")` filter
- Add assertion at the top: raise `ValueError` if any horse dict in `horse_list` is missing `hkjc_horse_id`

**`persistence.py` — `upsert_horse`**
- Add guard: raise `ValueError` if `horse_data` is missing `hkjc_horse_id`

**`scraper.py` — `scrape_race_page`**
- If the horse cell has no `<a>` tag (no URL → no `hkjc_horse_id`), raise `ParseError` instead of setting `hkjc_horse_id = None`

### Unchanged
- `UniqueConstraint("code", "name_cn")` stays as-is

---

## Issue 4 — Runner gear (配備)

### Problem

Gear worn by a horse in a race is not stored anywhere. It is not on the LocalResults page. It appears in the horse's profile page under the 所有往績 (All Past Performances) table, one row per past race, with a `配備` column showing slash-separated gear codes (e.g. `"SR/TT"`, `"B-/SR2/TT"`).

The `scrape_horse_profile()` function already fetches the profile page per horse, but only parses the `<dl>` profile block. The往績 table is in the same HTTP response — parsing it costs zero extra requests.

The `場次` column in the往績 table is the season race code, which matches `race.race_code` already stored in the DB. This is the join key.

**Gear code format**:
Slash-separated codes with optional suffixes: `1` = first use, `2` = second use, `-` = removed.
Common codes: `TT` (tongue tie), `SR` (nose strap), `B` (blinkers), `V` (visor), `ER` (ear plug), `P` (hood/pacifier), `XB` (cross blinkers), `PC` (prickers).

### Design

**`models.py` + migration**
- Add to `Runner`: `gear: Mapped[Optional[str]] = mapped_column(VARCHAR(64))`

**`scraper.py` — `scrape_horse_profile`**
- Extend return value from a flat dict to a structured dict:
  ```python
  {
      "profile": { ...existing 20 fields... },
      "past_gear": { 444: "SR/TT", 395: "SR/TT", 305: "B-/SR/TT", ... }
                  # race_code (int) → gear_str (str)
  }
  ```
- Parse the 所有往績 table: locate it by its column headers (look for `場次` and `配備`); for each data row extract `場次` as `int` and `配備` as `str` (empty string → `None`)
- Callers that previously accessed the return value directly need to access `result["profile"]` instead

**`scraper.py` — `scrape_meeting` / orchestration**
- After calling `scrape_horse_profile(hkjc_horse_id)`, accumulate:
  ```python
  gear_map: dict[str, dict[int, str]]
  # hkjc_horse_id → { race_code → gear_str }
  ```
- When building runner dicts, look up:
  ```python
  runner["gear"] = gear_map.get(hkjc_horse_id, {}).get(race_code)
  ```

**`persistence.py`**
- `runner` upsert already sets all keys from the runner dict via `setattr` loop — `gear` will be included automatically once the column and dict key exist. No changes required.

---

## Issue 5 — Race-level sectional splits

### Problem

The LocalResults race header contains cumulative leader times at each call point, e.g. `(23.70) (46.53) (1:09.86)`. `parse_race_header()` extracts all of them via `re.findall(r"\(([^)]+)\)", txt)` but keeps only the last value as `final_time_str`. The intermediate splits are discarded. These are essential for pace analysis.

The number of splits varies by race distance (3 for 1000m, up to 7+ for 2400m), so fixed columns won't work.

### Design

**`models.py` + migration**
- Add to `Race`: `sectional_times_str: Mapped[Optional[str]] = mapped_column(VARCHAR(128))`
- Stores all cumulative splits as a comma-separated string: `"23.70,46.53,1:09.86"`
- The last value in this string always equals `final_time_str` (kept for backwards compatibility)

**`scraper.py` — `parse_race_header`**
- Currently:
  ```python
  if m_times:
      final_time_str = m_times[-1]
  ```
- Change to:
  ```python
  if m_times:
      final_time_str = m_times[-1]
      sectional_times_str = ",".join(m_times)   # includes final time
  ```
- Add `sectional_times_str` to the returned dict

**`persistence.py`**
- `race` upsert uses a key-loop pattern — `sectional_times_str` is included automatically. No changes required.

---

## Issue 8 — Rename `offshore_odds` relationship

### Problem

`Race.offshore_odds` and `Horse.offshore_odds` are SQLAlchemy relationships pointing to the `HkjcOdds` model (HKJC's own pre-race odds). The name implies offshore/external data but it is HKJC data. The actual offshore data is `Race.offshore_markets` / `Horse.offshore_markets` (→ `OffshoreMarket`).

### Design

**`models.py` only — no DB migration required**

Rename relationships:
- `Race.offshore_odds` → `Race.hkjc_odds`
- `Horse.offshore_odds` → `Horse.hkjc_odds`

Update `back_populates` on `HkjcOdds`:
- `HkjcOdds.race` back_populates stays `"hkjc_odds"` on Race
- `HkjcOdds.horse` back_populates stays `"hkjc_odds"` on Horse

**Call sites** — grep and update all references to `.offshore_odds` across the codebase (expected in `persistence.py`, `hk33_scraper.py`, `cli.py`).

---

## Migration plan

Two Alembic migrations required (schema changes only):

**Migration 1**: `horse_hkjc_id_not_null`
```sql
ALTER TABLE horse ALTER COLUMN hkjc_horse_id SET NOT NULL;
```
Pre-condition: verify no existing NULL rows before running.

**Migration 2**: `runner_gear_race_sectional_times`
```sql
ALTER TABLE runner ADD COLUMN gear VARCHAR(64);
ALTER TABLE race ADD COLUMN sectional_times_str VARCHAR(128);
```

Issue 8 (relationship rename) requires no migration.

---

## Files affected

| File | Changes |
|------|---------|
| `src/hkjc_scraper/models.py` | `hkjc_horse_id NOT NULL`; add `Runner.gear`; add `Race.sectional_times_str`; rename `offshore_odds` → `hkjc_odds` |
| `src/hkjc_scraper/persistence.py` | Guard missing `hkjc_horse_id` in upserts; update `.offshore_odds` call sites |
| `src/hkjc_scraper/scraper.py` | Raise on missing horse URL; extend `scrape_horse_profile` return; populate gear in `scrape_meeting`; add `sectional_times_str` to `parse_race_header` |
| `migrations/versions/` | Two new Alembic migration files |
| Any other files | Grep for `.offshore_odds` and update |
