# HKJC Profile Scraping Design

**Goal:** Add horse, jockey, and trainer profile scraping to extract detailed information from HKJC profile pages.

**Date:** 2026-03-04

---

## Overview

Currently, the spider extracts horse, jockey, and trainer names from race results but does not capture detailed profile information. This design adds support for following profile hrefs to extract:

- **Basic info** (name, age, background)
- **Career/season stats summaries** (wins, places, win rate, prize money)
- **Key relationships** (sire/dam for horses)

Full race history records are intentionally excluded to avoid duplication with the `performance` table.

---

## Architecture

### Two-Phase Approach

```
Phase 1: Race Results           Phase 2: Profile Fetching
├─ Parse race results page      ├─ Deduplicate profile IDs
├─ Extract profile IDs          ├─ Concurrent profile requests
├─ Store performance records    ├─ Parse profile pages
└─ Collect unique profile IDs   └─ Yield profile data
```

**Rationale:** Two-phase approach enables:
1. Efficient deduplication (fetch each profile once)
2. Rate limit respect (profile fetching is isolated)
3. Graceful degradation (profile fetch failures don't affect race data)

### New Tables

| Table | Description | Key Fields |
|-------|-------------|------------|
| `horses` | Horse profiles | horse_id, name, sire, dam, age, colour, gender, ratings, prize_money, career_record |
| `jockeys` | Jockey profiles | jockey_id, name, age, background, achievements, career_wins, season_stats |
| `trainers` | Trainer profiles | trainer_id, name, age, background, achievements, career_wins, season_stats |

### Modified Tables

| Table | Changes |
|-------|---------|
| `performance` | Add `jockey_id`, `trainer_id` columns (currently only names) |

---

## Data Flow

### Phase 1: Race Results (existing)

1. Parse race results page
2. Extract `horse_id`, `jockey_id`, `trainer_id` from href attributes
3. Store performance records
4. Collect unique profile IDs in sets

### Phase 2: Profile Fetching (new)

1. Deduplicate profile IDs using in-memory sets
2. Yield `Request` objects for each unique profile
3. Parse profile pages using new parser functions
4. Yield `{table: "horses"/"jockeys"/"trainers", data: {...}}`

### URL Patterns

| Type | URL Pattern | Example |
|------|-------------|---------|
| Horse | `/zh-hk/local/information/horse?horseid=<id>` | `horseid=HK_2024_K306` |
| Jockey | `/zh-hk/local/information/jockeyprofile?jockeyid=<id>&Season=Current` | `jockeyid=BH` |
| Trainer | `/zh-hk/local/information/trainerprofile?trainerid=<id>&season=Current` | `trainerid=FC` |

---

## Implementation

### parsers.py Additions

```python
def parse_horse_profile(response) -> dict:
    """Extract horse profile data from profile page.

    Returns:
        {
            "horse_id": "HK_2024_K306",
            "name": "堅多福",
            "country_of_birth": "澳洲",
            "age": "3歲",
            "colour": "棗色",
            "gender": "閹馬",
            "import_type": "...",
            "sire": "Tivaci",
            "dam": "Promenade",
            "damsire": "...",
            "owner": "...",
            "current_rating": 82,
            "initial_rating": 58,
            "season_prize": 795375,
            "total_prize": 929925,
            "career_record": {"wins": 1, "places": 0, "shows": 2, "total": 16},
            "location": "...",
            "import_date": "..."
        }
    """

def parse_jockey_profile(response) -> dict:
    """Extract jockey profile data from profile page.

    Returns:
        {
            "jockey_id": "BH",
            "name": "布文",
            "age": 45,
            "background": "長篇介紹...",
            "achievements": "四屆悉尼冠軍騎師...",
            "major_wins": "...",
            "career_wins": 232,
            "career_win_rate": 12.4,
            "season_stats": {
                "season": "25/26",
                "wins": 32,
                "places": 42,
                "shows": 21,
                "fourth": 27,
                "total_rides": 272,
                "win_rate": 11.76,
                "prize_money": 54862525
            }
        }
    """

def parse_trainer_profile(response) -> dict:
    """Extract trainer profile data from profile page.

    Returns:
        {
            "trainer_id": "FC",
            "name": "方嘉柏",
            "age": 58,
            "background": "方嘉柏曾為其已故父親方祿麟擔任助手...",
            "achievements": "香港冠軍練馬師（2006/2007...）",
            "major_wins": "香港打吡大賽...",
            "career_wins": 1166,
            "career_win_rate": 9.6,
            "season_stats": {
                "season": "25/26",
                "wins": 37,
                "places": 27,
                "shows": 22,
                "fourth": 22,
                "fifth": 22,
                "total_runners": 310,
                "win_rate": 11.94,
                "prize_money": 49009255
            }
        }
    """
```

### spider.py Changes

#### 1. Update `_parse_performance_table`

Add jockey_id and trainer_id extraction:

```python
# Around line 230-233, add:
jockey_link = cells[3].css("a")
jockey = jockey_link[0].text.strip() if jockey_link else ""
jockey_id = None
if jockey_link:
    href = jockey_link[0].attrib.get("href", "")
    if "jockeyid=" in href:
        jockey_id = href.split("jockeyid=")[1].split("&")[0]

trainer_link = cells[4].css("a")
trainer = trainer_link[0].text.strip() if trainer_link else ""
trainer_id = None
if trainer_link:
    href = trainer_link[0].attrib.get("href", "")
    if "trainerid=" in href:
        trainer_id = href.split("trainerid=")[1].split("&")[0]
```

Add to performance dict:
```python
performance = {
    # ... existing fields ...
    "jockey_id": jockey_id,
    "trainer_id": trainer_id,
}
```

#### 2. New Callback Methods

```python
async def parse_horse_profile(self, response):
    """Parse horse profile page."""
    meta = response.meta
    horse_id = meta.get("horse_id")
    profile_data = parse_horse_profile(response)
    profile_data["horse_id"] = horse_id
    yield {"table": "horses", "data": profile_data}

async def parse_jockey_profile(self, response):
    """Parse jockey profile page."""
    meta = response.meta
    jockey_id = meta.get("jockey_id")
    profile_data = parse_jockey_profile(response)
    profile_data["jockey_id"] = jockey_id
    yield {"table": "jockeys", "data": profile_data}

async def parse_trainer_profile(self, response):
    """Parse trainer profile page."""
    meta = response.meta
    trainer_id = meta.get("trainer_id")
    profile_data = parse_trainer_profile(response)
    profile_data["trainer_id"] = trainer_id
    yield {"table": "trainers", "data": profile_data}
```

#### 3. Deduplication

```python
def __init__(self, dates: list | None = None, racecourse: str | None = None, **kwargs):
    super().__init__(**kwargs)
    # ... existing ...
    self._seen_horses = set()
    self._seen_jockeys = set()
    self._seen_trainers = set()
```

#### 4. Profile Fetching Logic

After collecting all race results, yield profile requests:

```python
async def _fetch_profiles(self, response):
    """Yield requests for unique profiles."""
    horse_ids = response.meta.get("horse_ids", set())
    jockey_ids = response.meta.get("jockey_ids", set())
    trainer_ids = response.meta.get("trainer_ids", set())

    for horse_id in horse_ids:
        if horse_id not in self._seen_horses:
            self._seen_horses.add(horse_id)
            url = f"{self.BASE_URL.replace('localresults', 'horse')}?horseid={horse_id}"
            yield Request(url, callback=self.parse_horse_profile, meta={"horse_id": horse_id})

    # Similar for jockeys and trainers
```

---

## Testing

### Unit Tests

```python
# tests/test_profile_parsers.py

def test_parse_horse_profile_basic_info():
    response = MockResponse(horse_profile_html)
    result = parse_horse_profile(response)
    assert result["horse_id"] == "HK_2024_K306"
    assert result["name"] == "堅多福"
    assert result["sire"] == "Tivaci"
    assert result["dam"] == "Promenade"

def test_parse_horse_profile_career_stats():
    # Test "冠-亞-季-總出賽次數" parsing
    assert result["career_record"]["wins"] == 1
    assert result["career_record"]["places"] == 0
    assert result["career_record"]["shows"] == 2
    assert result["career_record"]["total"] == 16

def test_parse_jockey_profile_season_stats():
    # Test season stats extraction

def test_parse_trainer_profile_season_stats():
    # Test season stats extraction

def test_extract_jockey_id_from_href():
    href = "/zh-hk/local/information/jockeyprofile?jockeyid=BH&Season=Current"
    assert extract_jockey_id(href) == "BH"
```

### Integration Tests

```python
@pytest.mark.integration
async def test_profile_scraping_end_to_end():
    spider = HKJCRacingSpider(dates=["2026/03/04"], racecourse="HV")
    result = await spider.run()

    # Check profile tables exist
    tables = {item["table"] for item in result.items}
    assert "horses" in tables
    assert "jockeys" in tables
    assert "trainers" in tables

    # Verify deduplication
    horse_items = [i for i in result.items if i["table"] == "horses"]
    horse_ids = [i["data"]["horse_id"] for i in horse_items]
    assert len(horse_ids) == len(set(horse_ids))

    # Verify foreign keys in performance
    perf_items = [i for i in result.items if i["table"] == "performance"]
    assert all("jockey_id" in i["data"] for i in perf_items)
    assert all("trainer_id" in i["data"] for i in perf_items)
```

---

## Error Handling

| Scenario | Handling |
|----------|----------|
| Profile page returns "沒有相關資料" | Skip, log warning |
| Profile fetch timeout | Log error, continue with other profiles |
| Malformed profile HTML | Return minimal data (ID + name), log warning |
| Duplicate profile ID | Skip (deduplication) |

---

## Open Questions & Resolutions

1. **Profile refresh frequency** - Should profiles be re-fetched on subsequent runs?
   - *Resolution*: Add `--refresh-profiles` CLI flag, default is to skip profiles that were already fetched in previous runs (check JSON files)

2. **Season parameter** - Fetch previous seasons for historical data?
   - *Resolution*: Start with `Season=Current` only. Add as enhancement if needed.

3. **Profile fetch timing** - Phase 2 vs interleaved?
   - *Resolution*: Phase 2 (after all races) for better deduplication efficiency.

---

## Dependencies

- Scrapling Spider (existing)
- No new external dependencies

---

## Success Criteria

- [ ] Horse profiles extracted with sire/dam information
- [ ] Jockey profiles with season stats
- [ ] Trainer profiles with season stats
- [ ] Foreign keys (jockey_id, trainer_id) added to performance table
- [ ] Deduplication working (no duplicate profiles)
- [ ] Unit tests for all parser functions
- [ ] Integration test passing with live data
- [ ] CLI unchanged (backward compatible)
