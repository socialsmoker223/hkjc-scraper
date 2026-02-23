# DB Schema Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix five database design issues: enforce `hkjc_horse_id NOT NULL`, add `runner.gear` sourced from the horse往績 table, capture `race.sectional_times_str`, and rename the misleading `offshore_odds` relationship.

**Architecture:** Schema changes land in two Alembic migrations. Scraper and persistence changes are guarded by tests written first. `scrape_horse_profile` return shape changes from a flat dict to `{"profile": {...}, "past_gear": {race_code: gear_str}}` — `scrape_meeting` is updated to unwrap it and build a `gear_map` used to populate `runner["gear"]` before persistence.

**Tech Stack:** Python 3.9+, SQLAlchemy 2.x mapped columns, Alembic, pytest, BeautifulSoup4, uv

---

## Task 1: Enforce `hkjc_horse_id NOT NULL` in model + migration

**Files:**
- Modify: `src/hkjc_scraper/models.py:110`
- Create: new Alembic migration via `make migrate-create`

**Step 1: Pre-check — verify no NULL rows exist**

```bash
make db-shell
# In psql:
SELECT COUNT(*) FROM horse WHERE hkjc_horse_id IS NULL;
```
Expected: `0`. If not zero, investigate and fix those rows before continuing.

**Step 2: Update model**

In `models.py` line 110, change:
```python
# Before
hkjc_horse_id: Mapped[Optional[str]] = mapped_column(VARCHAR(32), unique=True)
```
```python
# After
hkjc_horse_id: Mapped[str] = mapped_column(VARCHAR(32), nullable=False, unique=True)
```
Also remove `Optional` from the import if it becomes unused (check other usages first).

**Step 3: Create migration**

```bash
make migrate-create MSG="enforce_hkjc_horse_id_not_null"
```

Open the generated file in `migrations/versions/` and set the `upgrade` / `downgrade` functions:
```python
def upgrade() -> None:
    op.alter_column("horse", "hkjc_horse_id", nullable=False)

def downgrade() -> None:
    op.alter_column("horse", "hkjc_horse_id", nullable=True)
```

**Step 4: Run migration**

```bash
make migrate
```
Expected: migration applies without error.

**Step 5: Verify**

```bash
make db-shell
# In psql:
\d horse
```
Expected: `hkjc_horse_id` column shows `not null`.

**Step 6: Run existing tests**

```bash
make test
```
Expected: all pass (no tests rely on NULL hkjc_horse_id).

**Step 7: Commit**

```bash
git add src/hkjc_scraper/models.py migrations/versions/
git commit -m "feat(schema): enforce hkjc_horse_id NOT NULL on horse table"
```

---

## Task 2: Persistence guard — raise on missing `hkjc_horse_id`

**Files:**
- Modify: `src/hkjc_scraper/persistence.py:184,394`
- Test: `tests/test_persistence_merge.py`

**Step 1: Write failing tests**

Add to `tests/test_persistence_merge.py`:
```python
import pytest
from hkjc_scraper.persistence import upsert_horse, batch_upsert_horses


def test_upsert_horse_raises_if_no_hkjc_horse_id(test_db_session):
    """upsert_horse must raise ValueError when hkjc_horse_id is missing."""
    with pytest.raises(ValueError, match="hkjc_horse_id"):
        upsert_horse(test_db_session, {"code": "J344", "name_cn": "測試馬"})


def test_batch_upsert_horses_raises_if_any_missing_hkjc_horse_id(test_db_session):
    """batch_upsert_horses must raise ValueError when any horse is missing hkjc_horse_id."""
    horses = [
        {"code": "J344", "name_cn": "馬A", "hkjc_horse_id": "HK_2023_J344"},
        {"code": "K999", "name_cn": "馬B"},  # missing hkjc_horse_id
    ]
    with pytest.raises(ValueError, match="hkjc_horse_id"):
        batch_upsert_horses(test_db_session, horses)
```

**Step 2: Run to verify failure**

```bash
uv run pytest tests/test_persistence_merge.py::test_upsert_horse_raises_if_no_hkjc_horse_id tests/test_persistence_merge.py::test_batch_upsert_horses_raises_if_any_missing_hkjc_horse_id -v
```
Expected: FAIL — no ValueError raised yet.

**Step 3: Implement guards**

In `persistence.py`, update `upsert_horse` (line ~184):
```python
def upsert_horse(db: Session, horse_data: dict[str, Any]) -> Horse:
    if not horse_data.get("hkjc_horse_id"):
        raise ValueError(
            f"hkjc_horse_id is required but missing for horse: {horse_data.get('code')}"
        )
    # ... rest of existing function unchanged
```

In `persistence.py`, update `batch_upsert_horses` (line ~394):
```python
def batch_upsert_horses(db: Session, horse_list: list[dict[str, Any]]) -> dict[str, int]:
    if not horse_list:
        return {}

    missing = [r.get("code") for r in horse_list if not r.get("hkjc_horse_id")]
    if missing:
        raise ValueError(f"hkjc_horse_id is required but missing for horses: {missing}")

    # Remove old silent-drop filter — was: if r.get("hkjc_horse_id")
    deduped = {r["hkjc_horse_id"]: r for r in horse_list}
    # ... rest of existing function unchanged
```

**Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_persistence_merge.py::test_upsert_horse_raises_if_no_hkjc_horse_id tests/test_persistence_merge.py::test_batch_upsert_horses_raises_if_any_missing_hkjc_horse_id -v
```
Expected: PASS.

**Step 5: Run full suite**

```bash
make test
```
Expected: all pass.

**Step 6: Commit**

```bash
git add src/hkjc_scraper/persistence.py tests/test_persistence_merge.py
git commit -m "feat(persistence): raise ValueError when hkjc_horse_id missing in horse upserts"
```

---

## Task 3: Scraper guard — raise `ParseError` when horse cell has no link

**Files:**
- Modify: `src/hkjc_scraper/scraper.py:308-315`
- Test: `tests/test_error_handling.py`

**Step 1: Write failing test**

Add to `tests/test_error_handling.py`:
```python
from unittest.mock import MagicMock
from hkjc_scraper.scraper import scrape_race_page
from hkjc_scraper.exceptions import ParseError


def test_scrape_race_page_raises_on_missing_horse_link(mock_http_response):
    """scrape_race_page must raise ParseError when a horse row has no URL link."""
    # Minimal HTML: valid race header + one runner row with NO <a> tag on horse cell
    html = """
    <html><body>
    <table>
      <tr><td>第 1 場 (444)</td></tr>
      <tr><td></td></tr>
      <tr><td>第五班 - 1200米 - (40-0)</td></tr>
      <tr><td>賽事日期: 19/02/2026 沙田</td><td></td><td>HK$ 875,000 (1:09.86)</td></tr>
    </table>
    <table>
      <tr>
        <td>名次</td><td>馬號</td><td>馬名</td><td>騎師</td><td>練馬師</td>
        <td>實際負磅</td><td>排位體重</td><td>檔位</td><td>頭馬距離</td>
        <td>沿途走位</td><td>完成時間</td><td>獨贏賠率</td>
      </tr>
      <tr>
        <td>1</td><td>2</td>
        <td>金快飛飛 (K121)</td>
        <td><a href="/racing/information/Chinese/Jockey/Jockey.aspx?JockeyId=PZ">平沙</a></td>
        <td><a href="/racing/information/Chinese/Trainer/Trainer.aspx?TrainerId=YTP">丁冠豪</a></td>
        <td>133</td><td>1073</td><td>4</td><td>—</td>
        <td>1 2 3</td><td>1:09.86</td><td>6.2</td>
      </tr>
    </table>
    </body></html>
    """
    mock_session = MagicMock()
    mock_session.get.return_value = mock_http_response(html)

    with pytest.raises(ParseError, match="hkjc_horse_id"):
        scrape_race_page("http://example.com/race", mock_session, venue_code="ST")
```

**Step 2: Run to verify failure**

```bash
uv run pytest tests/test_error_handling.py::test_scrape_race_page_raises_on_missing_horse_link -v
```
Expected: FAIL — no ParseError raised yet.

**Step 3: Implement guard**

In `scraper.py`, the horse link block (around line 308-315):
```python
# Before
hkjc_horse_id = None
horse_profile_url = None
if horse_link:
    hkjc_horse_id, horse_profile_url = parse_horse_link(horse_link)
```
```python
# After
if not horse_link:
    raise ParseError(
        f"Horse row has no URL link — cannot extract hkjc_horse_id "
        f"(horse name: {horse_name_cn})"
    )
hkjc_horse_id, horse_profile_url = parse_horse_link(horse_link)
if not hkjc_horse_id:
    raise ParseError(
        f"Could not extract hkjc_horse_id from link href for horse: {horse_name_cn}"
    )
```

**Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_error_handling.py::test_scrape_race_page_raises_on_missing_horse_link -v
```
Expected: PASS.

**Step 5: Run full suite**

```bash
make test
```
Expected: all pass.

**Step 6: Commit**

```bash
git add src/hkjc_scraper/scraper.py tests/test_error_handling.py
git commit -m "feat(scraper): raise ParseError when horse row has no URL link"
```

---

## Task 4: Add `runner.gear` + `race.sectional_times_str` — model + migration

**Files:**
- Modify: `src/hkjc_scraper/models.py` (Runner ~line 244, Race ~line 68)
- Create: new Alembic migration via `make migrate-create`

**Step 1: Update Runner model**

In `models.py`, add to `Runner` after `win_odds`:
```python
gear: Mapped[Optional[str]] = mapped_column(VARCHAR(64))
```

**Step 2: Update Race model**

In `models.py`, add to `Race` after `final_time_str`:
```python
sectional_times_str: Mapped[Optional[str]] = mapped_column(VARCHAR(128))
```

**Step 3: Create migration**

```bash
make migrate-create MSG="add_runner_gear_race_sectional_times"
```

In the generated migration file:
```python
def upgrade() -> None:
    op.add_column("runner", sa.Column("gear", sa.VARCHAR(64), nullable=True))
    op.add_column("race", sa.Column("sectional_times_str", sa.VARCHAR(128), nullable=True))

def downgrade() -> None:
    op.drop_column("runner", "gear")
    op.drop_column("race", "sectional_times_str")
```

**Step 4: Run migration**

```bash
make migrate
```
Expected: applies without error.

**Step 5: Verify columns exist**

```bash
make db-shell
# In psql:
\d runner
\d race
```
Expected: `gear` on runner, `sectional_times_str` on race.

**Step 6: Run full suite**

```bash
make test
```
Expected: all pass.

**Step 7: Commit**

```bash
git add src/hkjc_scraper/models.py migrations/versions/
git commit -m "feat(schema): add runner.gear and race.sectional_times_str columns"
```

---

## Task 5: Extend `scrape_horse_profile` to parse往績 gear

**Files:**
- Modify: `src/hkjc_scraper/scraper.py:439-603`
- Test: `tests/test_scraper_profile.py` (new file)

**Step 1: Write failing test**

Create `tests/test_scraper_profile.py`:
```python
"""Tests for scrape_horse_profile gear extraction from 所有往績 table."""
from unittest.mock import MagicMock
import pytest
from hkjc_scraper.scraper import scrape_horse_profile


PROFILE_HTML_WITH_GEAR = """
<html><body>
<table>
  <tr><td>出生地 / 馬齡</td><td>:</td><td>英國 / 5</td></tr>
  <tr><td>毛色 / 性別</td><td>:</td><td>棗色 / 閹馬</td></tr>
  <tr><td>現時評分</td><td>:</td><td>47</td></tr>
</table>
<table>
  <tr>
    <td>場次</td><td>名次</td><td>日期</td><td>馬場</td><td>途程</td>
    <td>場地狀況</td><td>賽事班次</td><td>檔位</td><td>評分</td>
    <td>練馬師</td><td>騎師</td><td>頭馬距離</td><td>獨贏賠率</td>
    <td>實際負磅</td><td>沿途走位</td><td>完成時間</td><td>排位體重</td>
    <td>配備</td><td>賽事重播</td>
  </tr>
  <tr>
    <td>444</td><td>1</td><td>19/02/26</td><td>沙田</td><td>1200</td>
    <td>好</td><td>5</td><td>4</td><td>40</td>
    <td>丁冠豪</td><td>金霍</td><td>—</td><td>6.2</td>
    <td>133</td><td>1 2 3</td><td>1:09.86</td><td>1073</td>
    <td>SR/TT</td><td></td>
  </tr>
  <tr>
    <td>395</td><td>5</td><td>01/02/26</td><td>沙田</td><td>1200</td>
    <td>好/快</td><td>5</td><td>2</td><td>40</td>
    <td>丁冠豪</td><td>金霍</td><td>3</td><td>12</td>
    <td>131</td><td>3 4 5</td><td>1:10.50</td><td>1075</td>
    <td>SR/TT</td><td></td>
  </tr>
  <tr>
    <td>305</td><td>3</td><td>01/01/26</td><td>沙田</td><td>1200</td>
    <td>好</td><td>5</td><td>1</td><td>42</td>
    <td>丁冠豪</td><td>金霍</td><td>2</td><td>8</td>
    <td>128</td><td>2 3 4</td><td>1:10.20</td><td>1070</td>
    <td>B-/SR/TT</td><td></td>
  </tr>
</table>
</body></html>
"""


@pytest.fixture
def mock_session(mock_http_response):
    session = MagicMock()
    session.get.return_value = mock_http_response(PROFILE_HTML_WITH_GEAR)
    return session


def test_scrape_horse_profile_returns_profile_and_past_gear(mock_session):
    """scrape_horse_profile should return dict with 'profile' and 'past_gear' keys."""
    result = scrape_horse_profile("HK_2024_K121", mock_session)

    assert "profile" in result
    assert "past_gear" in result


def test_scrape_horse_profile_profile_fields_intact(mock_session):
    """Profile fields should still be accessible under result['profile']."""
    result = scrape_horse_profile("HK_2024_K121", mock_session)
    profile = result["profile"]

    assert profile["origin"] == "英國"
    assert profile["age"] == 5
    assert profile["current_rating"] == 47


def test_scrape_horse_profile_past_gear_keyed_by_race_code(mock_session):
    """past_gear should be a dict of {race_code (int): gear_str}."""
    result = scrape_horse_profile("HK_2024_K121", mock_session)
    past_gear = result["past_gear"]

    assert past_gear[444] == "SR/TT"
    assert past_gear[395] == "SR/TT"
    assert past_gear[305] == "B-/SR/TT"


def test_scrape_horse_profile_empty_gear_stored_as_none(mock_http_response):
    """Empty 配備 cell should produce None, not empty string."""
    html = PROFILE_HTML_WITH_GEAR.replace(
        "<td>SR/TT</td><td></td>\n  </tr>",
        "<td></td><td></td>\n  </tr>",
    )
    session = MagicMock()
    session.get.return_value = mock_http_response(html)
    result = scrape_horse_profile("HK_2024_K121", session)

    assert result["past_gear"].get(444) is None
```

**Step 2: Run to verify failure**

```bash
uv run pytest tests/test_scraper_profile.py -v
```
Expected: FAIL — `scrape_horse_profile` returns a flat dict, not `{"profile": ..., "past_gear": ...}`.

**Step 3: Implement**

In `scraper.py`, update `scrape_horse_profile`. The function currently ends with `return profile`. Change to:

1. After parsing the profile `<dl>` block (the existing loop over `all_rows`), add a second loop to parse the往績 table:

```python
# Parse 所有往績 table for gear data
past_gear: dict[int, Optional[str]] = {}

# Find the table containing both 場次 and 配備 headers
for table in all_tables:
    headers = [td.get_text(strip=True) for td in table.find_all("td")]
    if "場次" in headers and "配備" in headers:
        header_row = table.find("tr")
        if not header_row:
            continue
        header_cells = [td.get_text(strip=True) for td in header_row.find_all("td")]
        try:
            race_code_idx = header_cells.index("場次")
            gear_idx = header_cells.index("配備")
        except ValueError:
            continue

        for row in table.find_all("tr")[1:]:
            cells = row.find_all("td")
            if len(cells) <= max(race_code_idx, gear_idx):
                continue
            race_code_text = cells[race_code_idx].get_text(strip=True)
            gear_text = cells[gear_idx].get_text(strip=True)
            if race_code_text.isdigit():
                past_gear[int(race_code_text)] = gear_text if gear_text else None
        break  # found the right table

return {"profile": profile, "past_gear": past_gear}
```

**Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_scraper_profile.py -v
```
Expected: all 4 tests PASS.

**Step 5: Run full suite**

```bash
make test
```
Expected: all pass.

**Step 6: Commit**

```bash
git add src/hkjc_scraper/scraper.py tests/test_scraper_profile.py
git commit -m "feat(scraper): extend scrape_horse_profile to return past_gear from 所有往績 table"
```

---

## Task 6: Wire gear into `scrape_meeting` + runner dicts

**Files:**
- Modify: `src/hkjc_scraper/scraper.py:812-843`

**Step 1: Read current code**

In `scrape_meeting` (line ~834-841), the profile loop currently does:
```python
profile = future.result()
horse.update(profile)
```
After Task 5, `future.result()` returns `{"profile": {...}, "past_gear": {...}}`. This breaks `horse.update(profile)` — it would set `horse["profile"]` and `horse["past_gear"]` keys instead of the flat profile fields.

**Step 2: Update `scrape_meeting`**

Replace the profile-scraping section (lines ~816-842):

```python
if all_horses_to_scrape:
    logger.info(f"Scraping {len(all_horses_to_scrape)} horse profiles concurrently...")

    # gear_map: hkjc_horse_id -> {race_code -> gear_str}
    gear_map: dict[str, dict[int, Optional[str]]] = {}

    with ThreadPoolExecutor(max_workers=config.MAX_PROFILE_WORKERS) as executor:
        future_to_horse = {
            executor.submit(scrape_horse_profile, hkjc_id, session): (horse, hkjc_id)
            for horse, hkjc_id in all_horses_to_scrape
        }
        for future in as_completed(future_to_horse):
            horse, hkjc_id = future_to_horse[future]
            try:
                result = future.result()
                horse.update(result["profile"])          # flat profile fields as before
                gear_map[hkjc_id] = result["past_gear"]  # accumulate gear
                logger.debug(f"Scraped profile: {hkjc_id} ({horse.get('name_cn', 'N/A')})")
            except Exception as e:
                logger.warning(f"Failed to scrape profile for {hkjc_id}: {e}")

    # Assign gear to each runner using gear_map
    for race_data in all_races:
        race_code = race_data["race"].get("race_code")
        for runner in race_data["runners"]:
            hkjc_id = runner.get("hkjc_horse_id")
            if hkjc_id and race_code:
                runner["gear"] = gear_map.get(hkjc_id, {}).get(race_code)
```

**Step 3: Run full suite**

```bash
make test
```
Expected: all pass.

**Step 4: Commit**

```bash
git add src/hkjc_scraper/scraper.py
git commit -m "feat(scraper): populate runner gear from horse profile past_gear map"
```

---

## Task 7: Capture `sectional_times_str` in `parse_race_header`

**Files:**
- Modify: `src/hkjc_scraper/scraper.py:151-162`
- Test: `tests/test_error_handling.py`

**Step 1: Write failing test**

Add to `tests/test_error_handling.py`:
```python
def test_parse_race_header_captures_sectional_times_str():
    """parse_race_header should return sectional_times_str with comma-separated cumulative splits."""
    html = """
    <table>
        <tr><td>第 1 場 (444)</td></tr>
        <tr><td></td></tr>
        <tr><td>第五班 - 1200米 - (40-0)</td></tr>
        <tr><td>好地</td><td>草地 "A"</td></tr>
        <tr><td>場地狀況 : 好地 HK$ 875,000 (23.70) (46.53) (1:09.86)</td></tr>
    </table>
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    result = parse_race_header(table)

    assert result["sectional_times_str"] == "23.70,46.53,1:09.86"
    assert result["final_time_str"] == "1:09.86"


def test_parse_race_header_sectional_times_str_none_when_absent():
    """sectional_times_str should be None when no times are in the header."""
    html = """
    <table>
        <tr><td>第 1 場 (444)</td></tr>
        <tr><td></td></tr>
        <tr><td>第五班 - 1200米 - (40-0)</td></tr>
        <tr><td>場地狀況 : 好地 HK$ 875,000</td></tr>
    </table>
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    result = parse_race_header(table)

    assert result["sectional_times_str"] is None
    assert result["final_time_str"] is None
```

**Step 2: Run to verify failure**

```bash
uv run pytest tests/test_error_handling.py::test_parse_race_header_captures_sectional_times_str tests/test_error_handling.py::test_parse_race_header_sectional_times_str_none_when_absent -v
```
Expected: FAIL — `sectional_times_str` key not in result dict.

**Step 3: Implement**

In `scraper.py`, update the `prize/final_time` block in `parse_race_header` (lines ~151-162):

```python
# Before
prize = None
final_time_str = None
for r in rows:
    txt = r.get_text(" ", strip=True)
    if "HK$" in txt:
        m_prize = re.search(r"HK\$\s*([\d,]+)", txt)
        if m_prize:
            prize = int(m_prize.group(1).replace(",", ""))
        m_times = re.findall(r"\(([^)]+)\)", txt)
        if m_times:
            final_time_str = m_times[-1]
        break
```
```python
# After
prize = None
final_time_str = None
sectional_times_str = None
for r in rows:
    txt = r.get_text(" ", strip=True)
    if "HK$" in txt:
        m_prize = re.search(r"HK\$\s*([\d,]+)", txt)
        if m_prize:
            prize = int(m_prize.group(1).replace(",", ""))
        m_times = re.findall(r"\(([^)]+)\)", txt)
        if m_times:
            final_time_str = m_times[-1]
            sectional_times_str = ",".join(m_times)
        break
```

Also add `sectional_times_str` to the returned dict:
```python
return {
    "race_no": race_no,
    "race_code": race_code,
    "name_cn": race_name,
    "class_text": race_class,
    "distance_m": distance_m,
    "track_type": track_type,
    "track_course": track_course,
    "going": going,
    "prize_total": prize,
    "final_time_str": final_time_str,
    "sectional_times_str": sectional_times_str,   # new
}
```

**Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_error_handling.py::test_parse_race_header_captures_sectional_times_str tests/test_error_handling.py::test_parse_race_header_sectional_times_str_none_when_absent -v
```
Expected: PASS.

**Step 5: Run full suite**

```bash
make test
```
Expected: all pass.

**Step 6: Commit**

```bash
git add src/hkjc_scraper/scraper.py tests/test_error_handling.py
git commit -m "feat(scraper): capture sectional_times_str in parse_race_header"
```

---

## Task 8: Rename `offshore_odds` → `hkjc_odds` relationship

**Files:**
- Modify: `src/hkjc_scraper/models.py` (lines 82, 144, 281, 358-360)

No migration needed — SQLAlchemy relationship names are Python-only.

**Step 1: Confirm no call sites outside models.py**

```bash
grep -rn "\.offshore_odds" src/ tests/
```
Expected: results only in `models.py`. If other files appear, update them in this step too.

**Step 2: Rename in `Race` model (line ~82)**

```python
# Before
offshore_odds: Mapped[list["HkjcOdds"]] = relationship(
    "HkjcOdds", back_populates="race", cascade="all, delete-orphan"
)
```
```python
# After
hkjc_odds: Mapped[list["HkjcOdds"]] = relationship(
    "HkjcOdds", back_populates="race", cascade="all, delete-orphan"
)
```

**Step 3: Rename in `Horse` model (line ~144)**

```python
# Before
offshore_odds: Mapped[list["HkjcOdds"]] = relationship(
    "HkjcOdds", back_populates="horse", cascade="all, delete-orphan"
)
```
```python
# After
hkjc_odds: Mapped[list["HkjcOdds"]] = relationship(
    "HkjcOdds", back_populates="horse", cascade="all, delete-orphan"
)
```

**Step 4: Rename in `Runner` model (line ~281)**

```python
# Before
offshore_odds: Mapped[list["HkjcOdds"]] = relationship(
    "HkjcOdds", back_populates="runner", cascade="all, delete-orphan"
)
```
```python
# After
hkjc_odds: Mapped[list["HkjcOdds"]] = relationship(
    "HkjcOdds", back_populates="runner", cascade="all, delete-orphan"
)
```

**Step 5: Update `back_populates` on `HkjcOdds` (lines ~358-360)**

```python
# Before
race: Mapped["Race"] = relationship("Race", back_populates="offshore_odds")
runner: Mapped["Runner"] = relationship("Runner", back_populates="offshore_odds")
horse: Mapped["Horse"] = relationship("Horse", back_populates="offshore_odds")
```
```python
# After
race: Mapped["Race"] = relationship("Race", back_populates="hkjc_odds")
runner: Mapped["Runner"] = relationship("Runner", back_populates="hkjc_odds")
horse: Mapped["Horse"] = relationship("Horse", back_populates="hkjc_odds")
```

**Step 6: Run full suite**

```bash
make test
```
Expected: all pass.

**Step 7: Commit**

```bash
git add src/hkjc_scraper/models.py
git commit -m "refactor(models): rename offshore_odds relationship to hkjc_odds"
```

---

## Final verification

```bash
make test
make lint
```
Expected: all tests pass, no lint errors.

```bash
git log --oneline -8
```
Expected: 8 clean commits visible.
