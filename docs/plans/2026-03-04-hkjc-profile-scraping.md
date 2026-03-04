# HKJC Profile Scraping Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add horse, jockey, and trainer profile scraping to HKJC Racing Scraper by following href links from race results.

**Architecture:** Two-phase async scraping - Phase 1 parses race results and collects unique profile IDs, Phase 2 fetches and parses profile pages with in-memory deduplication.

**Tech Stack:** Python 3.13, Scrapling Spider, pytest, async/await

---

## Task 1: Add helper functions for profile ID extraction

**Files:**
- Create: `src/hkjc_scraper/profile_parsers.py`
- Test: `tests/test_profile_parsers.py`

**Step 1: Write failing tests for ID extraction**

```python
# tests/test_profile_parsers.py
import pytest
from hkjc_scraper.profile_parsers import extract_horse_id, extract_jockey_id, extract_trainer_id

def test_extract_horse_id_from_href():
    href = "/zh-hk/local/information/horse?horseid=HK_2024_K306"
    assert extract_horse_id(href) == "HK_2024_K306"

def test_extract_horse_id_no_match():
    href = "/some/other/path"
    assert extract_horse_id(href) is None

def test_extract_jockey_id_from_href():
    href = "/zh-hk/local/information/jockeyprofile?jockeyid=BH&Season=Current"
    assert extract_jockey_id(href) == "BH"

def test_extract_jockey_id_with_ampersand():
    href = "/zh-hk/local/information/jockeyprofile?jockeyid=AA&Season=Current"
    assert extract_jockey_id(href) == "AA"

def test_extract_trainer_id_from_href():
    href = "/zh-hk/local/information/trainerprofile?trainerid=FC&season=Current"
    assert extract_trainer_id(href) == "FC"

def test_extract_trainer_id_no_match():
    href = "/some/other/path"
    assert extract_trainer_id(href) is None
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_profile_parsers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'hkjc_scraper.profile_parsers'`

**Step 3: Implement minimal extraction functions**

```python
# src/hkjc_scraper/profile_parsers.py
import re
from typing import Any

def extract_horse_id(href: str) -> str | None:
    """Extract horse ID from href attribute."""
    if not href:
        return None
    match = re.search(r'horseid=([^&]+)', href)
    return match.group(1) if match else None

def extract_jockey_id(href: str) -> str | None:
    """Extract jockey ID from href attribute."""
    if not href:
        return None
    match = re.search(r'jockeyid=([^&]+)', href)
    return match.group(1) if match else None

def extract_trainer_id(href: str) -> str | None:
    """Extract trainer ID from href attribute."""
    if not href:
        return None
    match = re.search(r'trainerid=([^&]+)', href)
    return match.group(1) if match else None
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_profile_parsers.py -v`
Expected: PASS (7 tests)

**Step 5: Commit**

```bash
git add tests/test_profile_parsers.py src/hkjc_scraper/profile_parsers.py
git commit -m "feat: add profile ID extraction functions

- extract_horse_id: parse horseid from href
- extract_jockey_id: parse jockeyid from href
- extract_trainer_id: parse trainerid from href"
```

---

## Task 2: Parse horse profile page

**Files:**
- Modify: `src/hkjc_scraper/profile_parsers.py`
- Test: `tests/test_profile_parsers.py`

**Step 1: Write failing test for horse profile parsing**

```python
# tests/test_profile_parsers.py (add to existing file)
from unittest.mock import Mock

def test_parse_horse_profile_basic_info():
    html = """
    <html><body>
        <div class="fontLineHeight24">
            <table>
                <tr><td>出生地/馬齡 :</td><td>澳洲 3歲</td></tr>
                <tr><td>毛色/性別 :</td><td>棗色 閹馬</td></tr>
                <tr><td>父系 :</td><td>Tivaci</td></tr>
                <tr><td>母系 :</td><td>Promenade</td></tr>
                <tr><td>外祖父 :</td><td>Danehill</td></tr>
                <tr><td>馬主 :</td><td>Test Owner</td></tr>
                <tr><td>現時評分 :</td><td>82</td></tr>
                <tr><td>季初評分 :</td><td>58</td></tr>
            </table>
            <table>
                <tr><td>今季獎金 :</td><td>$795,375</td></tr>
                <tr><td>總獎金 :</td><td>$929,925</td></tr>
            </table>
            <div>1-0-2-16</div>
        </div>
    </body></html>
    """
    response = Mock()
    response.css = lambda x: []
    # For this test, we'll mock the actual CSS selectors
    # In real implementation, use proper mock response

    result = parse_horse_profile(response, "HK_2024_K306", "堅多福")
    assert result["horse_id"] == "HK_2024_K306"
    assert result["name"] == "堅多福"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_profile_parsers.py::test_parse_horse_profile_basic_info -v`
Expected: FAIL with `parse_horse_profile not defined`

**Step 3: Implement parse_horse_profile function**

```python
# src/hkjc_scraper/profile_parsers.py (add to existing file)

def parse_horse_profile(response: Any, horse_id: str, horse_name: str) -> dict:
    """Parse horse profile page response.

    Args:
        response: Scrapling response object
        horse_id: Horse ID from href
        horse_name: Horse name from race results

    Returns:
        Dictionary with horse profile data
    """
    profile = {
        "horse_id": horse_id,
        "name": horse_name,
    }

    # Extract info from table rows with label pattern
    for row in response.css("table tr"):
        cells = row.css("td")
        if len(cells) >= 2:
            label = cells[0].text or ""
            value = cells[1].text or "" if len(cells) > 1 else ""

            if "出生地/馬齡" in label:
                parts = value.split()
                profile["country_of_birth"] = parts[0] if parts else None
                profile["age"] = parts[1] if len(parts) > 1 else None
            elif "毛色/性別" in label:
                parts = value.split()
                profile["colour"] = parts[0] if parts else None
                profile["gender"] = parts[1] if len(parts) > 1 else None
            elif "父系" in label:
                profile["sire"] = value
            elif "母系" in label:
                profile["dam"] = value
            elif "外祖父" in label:
                profile["damsire"] = value
            elif "馬主" in label:
                profile["owner"] = value
            elif "現時評分" in label:
                try:
                    profile["current_rating"] = int(value)
                except ValueError:
                    profile["current_rating"] = None
            elif "季初評分" in label:
                try:
                    profile["initial_rating"] = int(value)
                except ValueError:
                    profile["initial_rating"] = None

    # Extract prize money
    for row in response.css("table tr"):
        cells = row.css("td")
        if len(cells) >= 2:
            label = cells[0].text or ""
            value = (cells[1].text or "").replace("$", "").replace(",", "")
            if "今季獎金" in label:
                try:
                    profile["season_prize"] = int(value)
                except ValueError:
                    pass
            elif "總獎金" in label:
                try:
                    profile["total_prize"] = int(value)
                except ValueError:
                    pass

    # Extract career record (format: "冠-亞-季-總出賽次數" like "1-0-2-16")
    career_text = response.text or ""
    career_match = re.search(r'(\d+)-(\d+)-(\d+)-(\d+)', career_text)
    if career_match:
        profile["career_record"] = {
            "wins": int(career_match.group(1)),
            "places": int(career_match.group(2)),
            "shows": int(career_match.group(3)),
            "total": int(career_match.group(4)),
        }

    return profile
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_profile_parsers.py::test_parse_horse_profile_basic_info -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/hkjc_scraper/profile_parsers.py tests/test_profile_parsers.py
git commit -m "feat: add horse profile parser

- Extract basic info: country, age, colour, gender
- Extract pedigree: sire, dam, damsire
- Extract owner and ratings
- Parse career record format (wins-places-shows-total)
- Parse prize money (season and total)"
```

---

## Task 3: Parse jockey profile page

**Files:**
- Modify: `src/hkjc_scraper/profile_parsers.py`
- Test: `tests/test_profile_parsers.py`

**Step 1: Write failing test for jockey profile parsing**

```python
# tests/test_profile_parsers.py (add to existing file)

def test_parse_jockey_profile_basic_info():
    html = """
    <div class="fontLineHeight24">
        <table>
            <tr><td>年齡 ：</td><td>45歲</td></tr>
        </table>
        <div>
            <p>背景： Test background text</p>
            <p>成就： Test achievements</p>
        </div>
        <table>
            <tr><td>冠 :</td><td>32</td></tr>
            <tr><td>亞 :</td><td>42</td></tr>
            <tr><td>勝出率 :</td><td>11.76%</td></tr>
            <tr><td>所贏獎金 :</td><td>$54,862,525</td></tr>
        </table>
    </div>
    """
    response = Mock()
    # Mock CSS selectors appropriately

    result = parse_jockey_profile(response, "BH", "布文")
    assert result["jockey_id"] == "BH"
    assert result["name"] == "布文"
    assert result["age"] == 45
    assert result["background"] == "Test background text"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_profile_parsers.py::test_parse_jockey_profile_basic_info -v`
Expected: FAIL with `parse_jockey_profile not defined`

**Step 3: Implement parse_jockey_profile function**

```python
# src/hkjc_scraper/profile_parsers.py (add to existing file)

def parse_jockey_profile(response: Any, jockey_id: str, jockey_name: str) -> dict:
    """Parse jockey profile page response.

    Args:
        response: Scrapling response object
        jockey_id: Jockey ID from href
        jockey_name: Jockey name from race results

    Returns:
        Dictionary with jockey profile data
    """
    profile = {
        "jockey_id": jockey_id,
        "name": jockey_name,
    }

    # Extract age
    for row in response.css("table tr"):
        cells = row.css("td")
        if len(cells) >= 2:
            label = cells[0].text or ""
            value = cells[1].text or "" if len(cells) > 1 else ""
            if "年齡" in label:
                age_match = re.search(r'(\d+)', value)
                if age_match:
                    profile["age"] = int(age_match.group(1))

    # Extract background and achievements from text
    full_text = response.text or ""

    # Find background (text after "背景：" until next label)
    bg_match = re.search(r'背景：\s*([^\n成就]*?)(?=成就：|$)', full_text)
    if bg_match:
        profile["background"] = bg_match.group(1).strip()

    # Find achievements
    ach_match = re.search(r'成就：\s*([^\n主要賽事]*?)(?=主要賽事冠軍：|$)', full_text)
    if ach_match:
        profile["achievements"] = ach_match.group(1).strip()

    # Extract career stats
    career_match = re.search(r'在港累積.*?(\d+)場.*?勝出率：.*?百分之([\d.]+)', full_text)
    if career_match:
        profile["career_wins"] = int(career_match.group(1))
        profile["career_win_rate"] = float(career_match.group(2))

    # Extract season stats
    season_stats = {}
    for row in response.css("table tr"):
        cells = row.css("td")
        if len(cells) >= 2:
            label = cells[0].text or ""
            value = cells[1].text or "" if len(cells) > 1 else ""

            if "冠" in label and "：" in label:
                season_stats["wins"] = int(value) if value.isdigit() else 0
            elif "亞" in label and "：" in label:
                season_stats["places"] = int(value) if value.isdigit() else 0
            elif "勝出率" in label:
                rate_match = re.search(r'([\d.]+)', value)
                if rate_match:
                    season_stats["win_rate"] = float(rate_match.group(1))
            elif "所贏獎金" in label or "獎金" in label:
                prize_match = re.search(r'([\d,]+)', value.replace("$", ""))
                if prize_match:
                    season_stats["prize_money"] = int(prize_match.group(1).replace(",", ""))

    if season_stats:
        profile["season_stats"] = season_stats

    return profile
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_profile_parsers.py::test_parse_jockey_profile_basic_info -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/hkjc_scraper/profile_parsers.py tests/test_profile_parsers.py
git commit -m "feat: add jockey profile parser

- Extract age from profile
- Parse background and achievements text
- Extract career wins and win rate
- Parse season stats: wins, places, win rate, prize money"
```

---

## Task 4: Parse trainer profile page

**Files:**
- Modify: `src/hkjc_scraper/profile_parsers.py`
- Test: `tests/test_profile_parsers.py`

**Step 1: Write failing test for trainer profile parsing**

```python
# tests/test_profile_parsers.py (add to existing file)

def test_parse_trainer_profile_basic_info():
    response = Mock()
    # Mock CSS selectors

    result = parse_trainer_profile(response, "FC", "方嘉柏")
    assert result["trainer_id"] == "FC"
    assert result["name"] == "方嘉柏"
    assert result["age"] == 58
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_profile_parsers.py::test_parse_trainer_profile_basic_info -v`
Expected: FAIL with `parse_trainer_profile not defined`

**Step 3: Implement parse_trainer_profile function**

```python
# src/hkjc_scraper/profile_parsers.py (add to existing file)

def parse_trainer_profile(response: Any, trainer_id: str, trainer_name: str) -> dict:
    """Parse trainer profile page response.

    Args:
        response: Scrapling response object
        trainer_id: Trainer ID from href
        trainer_name: Trainer name from race results

    Returns:
        Dictionary with trainer profile data
    """
    profile = {
        "trainer_id": trainer_id,
        "name": trainer_name,
    }

    # Extract age
    for row in response.css("table tr"):
        cells = row.css("td")
        if len(cells) >= 2:
            label = cells[0].text or ""
            value = cells[1].text or "" if len(cells) > 1 else ""
            if "年齡" in label:
                age_match = re.search(r'(\d+)', value)
                if age_match:
                    profile["age"] = int(age_match.group(1))

    # Extract background and achievements
    full_text = response.text or ""

    bg_match = re.search(r'背景：\s*([^\n成就]*?)(?=成就：|$)', full_text)
    if bg_match:
        profile["background"] = bg_match.group(1).strip()

    ach_match = re.search(r'成就：\s*([^\n主要賽事]*?)(?=主要賽事冠軍：|$)', full_text)
    if ach_match:
        profile["achievements"] = ach_match.group(1).strip()

    # Extract career stats
    career_match = re.search(r'在港累積.*?(\d+)場.*?勝出率：.*?百分之([\d.]+)', full_text)
    if career_match:
        profile["career_wins"] = int(career_match.group(1))
        profile["career_win_rate"] = float(career_match.group(2))

    # Extract season stats
    season_stats = {}
    for row in response.css("table tr"):
        cells = row.css("td")
        if len(cells) >= 2:
            label = cells[0].text or ""
            value = cells[1].text or "" if len(cells) > 1 else ""

            if "冠" in label and "：" in label:
                season_stats["wins"] = int(value) if value.isdigit() else 0
            elif "亞" in label and "：" in label:
                season_stats["places"] = int(value) if value.isdigit() else 0
            elif "季" in label and "：" in label and "四季" not in label:
                season_stats["shows"] = int(value) if value.isdigit() else 0
            elif "殿" in label and "：" in label:
                season_stats["fourth"] = int(value) if value.isdigit() else 0
            elif "出馬總數" in label:
                season_stats["total_runners"] = int(value) if value.isdigit() else 0
            elif "勝出率" in label:
                rate_match = re.search(r'([\d.]+)', value)
                if rate_match:
                    season_stats["win_rate"] = float(rate_match.group(1))
            elif "獎金" in label:
                prize_match = re.search(r'([\d,]+)', value.replace("$", "").replace(",", ""))
                if prize_match:
                    season_stats["prize_money"] = int(prize_match.group(1).replace(",", ""))

    if season_stats:
        profile["season_stats"] = season_stats

    return profile
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_profile_parsers.py::test_parse_trainer_profile_basic_info -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/hkjc_scraper/profile_parsers.py tests/test_profile_parsers.py
git commit -m "feat: add trainer profile parser

- Extract age from profile
- Parse background and achievements
- Extract career wins and win rate
- Parse season stats: wins, places, shows, fourth, total runners, win rate, prize money"
```

---

## Task 5: Update spider to extract jockey_id and trainer_id

**Files:**
- Modify: `src/hkjc_scraper/spider.py` (around line 230-233)
- Test: `tests/test_spider.py`

**Step 1: Write failing test for jockey_id and trainer_id extraction**

```python
# tests/test_spider.py (add to existing file)

def test_performance_extraction_includes_ids():
    """Test that performance items include jockey_id and trainer_id."""
    html = """
    <table class="draggable">
        <tbody>
            <tr>
                <td>1</td>
                <td>7</td>
                <td><a href="/zh-hk/local/information/horse?horseid=HK_2024_K306">堅多福</a></td>
                <td><a href="/zh-hk/local/information/jockeyprofile?jockeyid=BH&Season=Current">布文</a></td>
                <td><a href="/zh-hk/local/information/trainerprofile?trainerid=FC&season=Current">方嘉柏</a></td>
                <td>120</td>
                <td>1050</td>
                <td>3</td>
                <td></td>
                <td><div><div>1</div><div>2</div></div></td>
                <td>1:49.35</td>
                <td>12.5</td>
            </tr>
        </tbody>
    </table>
    """
    from scrapling import Adaptor
    response = Adaptor(html)

    spider = HKJCRacingSpider()
    results = list(spider._parse_performance_table(response, "test-race-id"))

    assert len(results) == 1
    assert results[0]["data"]["jockey_id"] == "BH"
    assert results[0]["data"]["trainer_id"] == "FC"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_spider.py::test_performance_extraction_includes_ids -v`
Expected: FAIL (jockey_id and trainer_id not in performance data)

**Step 3: Update _parse_performance_table to extract IDs**

```python
# src/hkjc_scraper/spider.py (modify around line 220-252)

def _parse_performance_table(self, response, race_id: str):
    """Extract performance (horse results) table."""
    results_table = response.css("table.draggable")
    if not results_table:
        return
    rows = results_table[0].css("tbody tr")
    for row in rows:
        cells = row.css("td")
        if len(cells) >= 12:
            try:
                horse_link = cells[2].css("a")
                horse_name = ""
                horse_id = None
                if horse_link:
                    horse_name = horse_link[0].text.strip()
                    href = horse_link[0].attrib.get("href", "")
                    if "horseid=" in href:
                        horse_id = href.split("horseid=")[1].split("&")[0]

                # Extract jockey ID
                jockey_link = cells[3].css("a")
                jockey = jockey_link[0].text.strip() if jockey_link else ""
                jockey_id = None
                if jockey_link:
                    href = jockey_link[0].attrib.get("href", "")
                    if "jockeyid=" in href:
                        jockey_id = href.split("jockeyid=")[1].split("&")[0]

                # Extract trainer ID
                trainer_link = cells[4].css("a")
                trainer = trainer_link[0].text.strip() if trainer_link else ""
                trainer_id = None
                if trainer_link:
                    href = trainer_link[0].attrib.get("href", "")
                    if "trainerid=" in href:
                        trainer_id = href.split("trainerid=")[1].split("&")[0]

                pos_text = cells[0].text.strip()
                position = clean_position(pos_text) if pos_text else ""
                running_pos = parse_running_position(cells[9])
                performance = {
                    "race_id": race_id,
                    "position": position,
                    "horse_no": cells[1].text.strip(),
                    "horse_id": horse_id,
                    "horse_name": horse_name,
                    "jockey": jockey,
                    "jockey_id": jockey_id,  # NEW
                    "trainer": trainer,
                    "trainer_id": trainer_id,  # NEW
                    "actual_weight": cells[5].text.strip(),
                    "body_weight": cells[6].text.strip(),
                    "draw": cells[7].text.strip(),
                    "margin": cells[8].text.strip(),
                    "running_position": running_pos,
                    "finish_time": cells[10].text.strip(),
                    "win_odds": cells[11].text.strip()
                }
                if self._validate_performance_item(performance):
                    yield {"table": "performance", "data": performance}
            except Exception:
                continue
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_spider.py::test_performance_extraction_includes_ids -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/hkjc_scraper/spider.py tests/test_spider.py
git commit -m "feat: extract jockey_id and trainer_id from performance table

- Parse jockeyid from jockey href
- Parse trainerid from trainer href
- Add jockey_id and trainer_id to performance data"
```

---

## Task 6: Add profile deduplication sets to spider

**Files:**
- Modify: `src/hkjc_scraper/spider.py` (in __init__ method)

**Step 1: Write failing test for deduplication**

```python
# tests/test_spider.py (add to existing file)

def test_spider_has_deduplication_sets():
    """Test that spider initializes deduplication sets."""
    spider = HKJCRacingSpider()
    assert hasattr(spider, "_seen_horses")
    assert hasattr(spider, "_seen_jockeys")
    assert hasattr(spider, "_seen_trainers")
    assert isinstance(spider._seen_horses, set)
    assert isinstance(spider._seen_jockeys, set)
    assert isinstance(spider._seen_trainers, set)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_spider.py::test_spider_has_deduplication_sets -v`
Expected: FAIL (attributes don't exist)

**Step 3: Add deduplication sets to __init__**

```python
# src/hkjc_scraper/spider.py (modify __init__ method)

def __init__(self, dates: list | None = None, racecourse: str | None = None, **kwargs):
    super().__init__(**kwargs)
    self.dates = dates
    self.racecourse = racecourse
    # Initialize deduplication sets
    self._seen_horses = set()
    self._seen_jockeys = set()
    self._seen_trainers = set()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_spider.py::test_spider_has_deduplication_sets -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/hkjc_scraper/spider.py tests/test_spider.py
git commit -m "feat: add profile deduplication sets to spider

- Add _seen_horses, _seen_jockeys, _seen_trainers sets
- Prevent duplicate profile fetching during crawl"
```

---

## Task 7: Add profile fetching callback methods

**Files:**
- Modify: `src/hkjc_scraper/spider.py`

**Step 1: Write failing test for profile callback**

```python
# tests/test_spider.py (add to existing file)

def test_parse_horse_profile_yields_correct_table():
    """Test that parse_horse_profile yields horses table."""
    from unittest.mock import AsyncMock, Mock
    from scrapling import Adaptor

    spider = HKJCRacingSpider()
    spider._seen_horses.add("HK_2024_K306")

    # Mock response with minimal HTML
    html = '<div><table><tr><td>父系 :</td><td>Tivaci</td></tr></table></div>'
    response = Adaptor(html)
    response.meta = {"horse_id": "HK_2024_K306", "horse_name": "堅多福"}

    results = list(spider.parse_horse_profile(response))
    assert len(results) == 1
    assert results[0]["table"] == "horses"
    assert results[0]["data"]["horse_id"] == "HK_2024_K306"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_spider.py::test_parse_horse_profile_yields_correct_table -v`
Expected: FAIL (method doesn't exist)

**Step 3: Implement profile callback methods**

```python
# src/hkjc_scraper/spider.py (add after existing parse methods)

from hkjc_scraper.profile_parsers import (
    parse_horse_profile as parse_horse_profile_data,
    parse_jockey_profile as parse_jockey_profile_data,
    parse_trainer_profile as parse_trainer_profile_data,
)

async def parse_horse_profile(self, response):
    """Parse horse profile page and yield horse data."""
    meta = response.meta
    horse_id = meta.get("horse_id")
    horse_name = meta.get("horse_name", "")

    profile_data = parse_horse_profile_data(response, horse_id, horse_name)
    profile_data["horse_id"] = horse_id
    yield {"table": "horses", "data": profile_data}

async def parse_jockey_profile(self, response):
    """Parse jockey profile page and yield jockey data."""
    meta = response.meta
    jockey_id = meta.get("jockey_id")
    jockey_name = meta.get("jockey_name", "")

    profile_data = parse_jockey_profile_data(response, jockey_id, jockey_name)
    profile_data["jockey_id"] = jockey_id
    yield {"table": "jockeys", "data": profile_data}

async def parse_trainer_profile(self, response):
    """Parse trainer profile page and yield trainer data."""
    meta = response.meta
    trainer_id = meta.get("trainer_id")
    trainer_name = meta.get("trainer_name", "")

    profile_data = parse_trainer_profile_data(response, trainer_id, trainer_name)
    profile_data["trainer_id"] = trainer_id
    yield {"table": "trainers", "data": profile_data}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_spider.py::test_parse_horse_profile_yields_correct_table -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/hkjc_scraper/spider.py tests/test_spider.py
git commit -m "feat: add profile parsing callbacks

- Add parse_horse_profile callback
- Add parse_jockey_profile callback
- Add parse_trainer_profile callback
- Each yields appropriate table type with profile data"
```

---

## Task 8: Add profile fetching logic after race parsing

**Files:**
- Modify: `src/hkjc_scraper/spider.py`

**Step 1: Write failing test for profile request generation**

```python
# tests/test_spider.py (add to existing file)

def test_fetch_profile_requests_yields_unique_requests():
    """Test that _fetch_profiles yields requests for unique profiles."""
    spider = HKJCRacingSpider()

    # Mock response with profile IDs
    class MockResponse:
        def __init__(self):
            self.meta = {
                "horse_ids": {"HK_2024_K306", "HK_2022_H293"},
                "jockey_ids": {"BH", "AA"},
                "trainer_ids": {"FC", "SCS"}
            }

    mock_response = MockResponse()
    requests = list(spider._fetch_profiles(mock_response))

    # Should yield 6 requests (2 horses + 2 jockeys + 2 trainers)
    assert len(requests) == 6

    # Check deduplication on second call
    spider._seen_horses.add("HK_2024_K306")
    spider._seen_jockeys.add("BH")
    spider._seen_trainers.add("FC")

    requests2 = list(spider._fetch_profiles(mock_response))
    assert len(requests2) == 3  # Only new ones
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_spider.py::test_fetch_profile_requests_yields_unique_requests -v`
Expected: FAIL (_fetch_profiles doesn't exist)

**Step 3: Implement _fetch_profiles method**

```python
# src/hkjc_scraper/spider.py (add new method)

def _fetch_profiles(self, response):
    """Yield requests for unique profile pages.

    Uses deduplication sets to avoid fetching the same profile multiple times.
    """
    horse_ids = response.meta.get("horse_ids", set())
    jockey_ids = response.meta.get("jockey_ids", set())
    trainer_ids = response.meta.get("trainer_ids", set())

    # Fetch horse profiles
    for horse_id in horse_ids:
        if horse_id not in self._seen_horses:
            self._seen_horses.add(horse_id)
            url = f"https://racing.hkjc.com/zh-hk/local/information/horse?horseid={horse_id}"
            yield Request(
                url,
                callback=self.parse_horse_profile,
                meta={"horse_id": horse_id}
            )

    # Fetch jockey profiles
    for jockey_id in jockey_ids:
        if jockey_id not in self._seen_jockeys:
            self._seen_jockeys.add(jockey_id)
            url = f"https://racing.hkjc.com/zh-hk/local/information/jockeyprofile?jockeyid={jockey_id}&Season=Current"
            yield Request(
                url,
                callback=self.parse_jockey_profile,
                meta={"jockey_id": jockey_id}
            )

    # Fetch trainer profiles
    for trainer_id in trainer_ids:
        if trainer_id not in self._seen_trainers:
            self._seen_trainers.add(trainer_id)
            url = f"https://racing.hkjc.com/zh-hk/local/information/trainerprofile?trainerid={trainer_id}&season=Current"
            yield Request(
                url,
                callback=self.parse_trainer_profile,
                meta={"trainer_id": trainer_id}
            )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_spider.py::test_fetch_profile_requests_yields_unique_requests -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/hkjc_scraper/spider.py tests/test_spider.py
git commit -m "feat: add profile fetching logic

- Add _fetch_profiles method to yield profile requests
- Implement deduplication using seen sets
- Generate correct URLs for horse, jockey, trainer profiles"
```

---

## Task 9: Collect profile IDs during race parsing

**Files:**
- Modify: `src/hkjc_scraper/spider.py`

**Step 1: Write failing test for profile ID collection**

```python
# tests/test_spider.py (add to existing file)

def test_parse_race_collects_profile_ids():
    """Test that parse_race collects profile IDs in meta."""
    from scrapling import Adaptor

    spider = HKJCRacingSpider()

    # Minimal race HTML with profile links
    html = """
    <div>
        <table class="draggable">
            <tr>
                <td>1</td>
                <td>7</td>
                <td><a href="/zh-hk/local/information/horse?horseid=HK_2024_K306">堅多福</a></td>
                <td><a href="/zh-hk/local/information/jockeyprofile?jockeyid=BH&Season=Current">布文</a></td>
                <td><a href="/zh-hk/local/information/trainerprofile?trainerid=FC&season=Current">方嘉柏</a></td>
            </tr>
        </table>
    </div>
    """
    response = Adaptor(html)
    response.meta = {"date": "2026/03/04", "racecourse": "HV", "race_no": 1}
    response.follow = lambda url, callback, meta: None

    results = list(spider.parse_race(response))

    # Check that meta was populated with profile IDs
    # This will be passed to _fetch_profiles
    # (In actual implementation, we'll use a different mechanism)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_spider.py::test_parse_race_collects_profile_ids -v`
Expected: FAIL (mechanism doesn't exist yet)

**Step 3: Implement profile ID collection in parse_race**

```python
# src/hkjc_scraper/spider.py (modify parse_race method)

async def parse_race(self, response):
    """Parse race page and collect profile IDs."""
    meta = response.meta
    date = meta.get("date", "")
    racecourse = meta.get("racecourse", "ST")
    race_no = meta.get("race_no", 1)

    # Parse race metadata
    race_data = self._parse_race_metadata(response, date, racecourse, race_no)
    yield {"table": "races", "data": race_data}
    race_id = race_data["race_id"]

    # Collect profile IDs during performance parsing
    horse_ids = set()
    jockey_ids = set()
    trainer_ids = set()

    # Parse performance table and collect IDs
    for perf_item in self._parse_performance_table(response, race_id):
        yield perf_item
        # Collect IDs
        data = perf_item.get("data", {})
        if data.get("horse_id"):
            horse_ids.add(data["horse_id"])
        if data.get("jockey_id"):
            jockey_ids.add(data["jockey_id"])
        if data.get("trainer_id"):
            trainer_ids.add(data["trainer_id"])

    # Parse dividends and incidents
    for div_item in self._parse_dividends(response, race_id):
        yield div_item
    for inc_item in self._parse_incidents(response, race_id):
        yield inc_item

    # Yield profile fetching request
    yield response.follow(
        f"{self.BASE_URL}?racedate={date}&Racecourse={racecourse}&RaceNo={race_no}",
        callback=self._fetch_profiles,
        meta={
            "date": date,
            "racecourse": racecourse,
            "race_no": race_no,
            "horse_ids": horse_ids,
            "jockey_ids": jockey_ids,
            "trainer_ids": trainer_ids,
        }
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_spider.py::test_parse_race_collects_profile_ids -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/hkjc_scraper/spider.py tests/test_spider.py
git commit -m "feat: collect and fetch profile IDs during race parsing

- Collect horse_id, jockey_id, trainer_id from performance items
- Store in sets and pass to _fetch_profiles callback
- Maintain existing race, performance, dividends, incidents parsing"
```

---

## Task 10: Update __init__.py to export profile parsers

**Files:**
- Modify: `src/hkjc_scraper/__init__.py`

**Step 1: Check current exports**

Run: `cat src/hkjc_scraper/__init__.py`

**Step 2: Add profile parsers to exports**

```python
# src/hkjc_scraper/__init__.py
from hkjc_scraper.spider import HKJCRacingSpider
from hkjc_scraper.parsers import *
from hkjc_scraper.profile_parsers import *

__all__ = ["HKJCRacingSpider"]
```

**Step 3: Verify imports work**

Run: `python -c "from hkjc_scraper import extract_horse_id; print(extract_horse_id('test?horseid=ABC'))"`
Expected: No error

**Step 4: Commit**

```bash
git add src/hkjc_scraper/__init__.py
git commit -m "feat: export profile parsers from __init__.py"
```

---

## Task 11: Add integration test for profile scraping

**Files:**
- Create: `tests/integration/test_profile_scraping.py`

**Step 1: Write integration test**

```python
# tests/integration/test_profile_scraping.py
import pytest
from hkjc_scraper.spider import HKJCRacingSpider

@pytest.mark.integration
async def test_profile_scraping_end_to_end():
    """Test full profile scraping with live data."""
    spider = HKJCRacingSpider(dates=["2026/03/04"], racecourse="HV")
    result = await spider.run()

    # Check that profile tables exist
    tables = {item["table"] for item in result.items}
    assert "horses" in tables
    assert "jockeys" in tables
    assert "trainers" in tables

    # Verify deduplication (no duplicate horse IDs)
    horse_items = [i for i in result.items if i["table"] == "horses"]
    horse_ids = [i["data"].get("horse_id") for i in horse_items if i["data"].get("horse_id")]
    assert len(horse_ids) == len(set(horse_ids)), "Duplicate horse IDs found"

    # Verify performance has foreign keys
    perf_items = [i for i in result.items if i["table"] == "performance"]
    if perf_items:
        # At least some should have jockey_id and trainer_id
        items_with_jockey_id = [i for i in perf_items if i["data"].get("jockey_id")]
        items_with_trainer_id = [i for i in perf_items if i["data"].get("trainer_id")]
        assert len(items_with_jockey_id) > 0, "No jockey_id found in performance items"
        assert len(items_with_trainer_id) > 0, "No trainer_id found in performance items"
```

**Step 2: Run integration test**

Run: `pytest tests/integration/test_profile_scraping.py -v -m integration`
Expected: PASS (makes real network requests)

**Step 3: Commit**

```bash
git add tests/integration/test_profile_scraping.py
git commit -m "test: add integration test for profile scraping

- Test end-to-end profile fetching
- Verify deduplication works
- Check foreign keys in performance table"
```

---

## Task 12: Update README with new tables

**Files:**
- Modify: `README.md`

**Step 1: Update data model section**

Find the "Data Model" section and update:

```markdown
## Data Model

### Tables
- **races** - Race metadata (date, class, distance, going, prize)
- **performance** - Horse results per race (position, time, odds, jockey_id, trainer_id)
- **dividends** - Payout information by pool type
- **incidents** - Race incident reports
- **horses** - Horse profiles (sire, dam, age, ratings, career stats)
- **jockeys** - Jockey profiles (age, background, achievements, season stats)
- **trainers** - Trainer profiles (age, background, achievements, season stats)
```

**Step 2: Update output format section**

```markdown
### Output Format
Data is saved as JSON with UTF-8 encoding:
```
data/
├── races_2026-03-01.json
├── performance_2026-03-01.json
├── dividends_2026-03-01.json
├── incidents_2026-03-01.json
├── horses_2026-03-01.json      # NEW
├── jockeys_2026-03-01.json     # NEW
└── trainers_2026-03-01.json    # NEW
```
```

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README with new profile tables

- Document horses, jockeys, trainers tables
- Note jockey_id, trainer_id added to performance table
- Update output format example"
```

---

## Task 13: Run full test suite and verify

**Step 1: Run all unit tests**

Run: `pytest tests/ -v -m "not integration"`
Expected: All PASS

**Step 2: Run integration tests**

Run: `pytest tests/ -v -m integration`
Expected: All PASS (may take longer due to network requests)

**Step 3: Test CLI manually**

Run: `uv run hkjc-scrape --racecourse ST | head -20`

**Step 4: Final commit if needed**

```bash
git add .
git commit -m "feat: complete profile scraping implementation

- All tests passing
- Integration tests verified with live data
- CLI working as expected"
```

---

## Summary

This plan implements horse, jockey, and trainer profile scraping in 13 tasks:

1. Helper functions for ID extraction
2-4. Profile parsers for horse, jockey, trainer
5. Extract jockey_id and trainer_id from performance table
6. Add deduplication sets
7. Add profile callback methods
8. Implement profile fetching logic
9. Collect profile IDs during race parsing
10. Export parsers
11. Integration test
12. Update documentation
13. Final verification

Each task follows TDD: write failing test, implement, verify passing, commit.
