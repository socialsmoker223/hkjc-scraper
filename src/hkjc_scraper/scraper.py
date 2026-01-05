import logging
import re
from datetime import datetime
from decimal import Decimal
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from hkjc_scraper.validators import validate_horse_profiles, validate_meeting, validate_race, validate_runners

BASE = "https://racing.hkjc.com/zh-hk/local/information"
logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Meeting level: 給定賽日，自動抓所有場地、所有 LocalResults
# -------------------------------------------------------------------


def list_race_urls_for_meeting_all_courses(date_ymd: str):
    """
    給一個賽日 (YYYY/MM/DD)，從 ResultsAll 抓該日所有場地、所有場次的 LocalResults 連結，
    並回傳其 Racecourse (ST/HV) 與 RaceNo。

    回傳: list[{'url': full_localresults_url, 'racecourse': 'ST' or 'HV', 'race_no': int}]
    """
    url = f"{BASE}/resultsall?racedate={date_ymd}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    out = []
    seen = set()

    for a in soup.find_all("a", href=re.compile(r"localresults?")):
        href = a.get("href") or ""
        full = urljoin("https://racing.hkjc.com", href)

        q = parse_qs(urlparse(full).query)
        racecourse = q.get("Racecourse", [None])[0]
        if racecourse != "HV" and racecourse != "ST":
            continue
        raceno = q.get("RaceNo", [None])[0]
        race_no = int(raceno) if raceno and raceno.isdigit() else None

        key = (full, racecourse, race_no)
        if key in seen:
            continue
        seen.add(key)

        out.append(
            {
                "url": full,
                "racecourse": racecourse,
                "race_no": race_no,
            }
        )

    # 依場地、場次排序，方便 debug
    out.sort(key=lambda x: ((x["racecourse"] or ""), x["race_no"] or 0))
    return out


# -------------------------------------------------------------------
# Race header 解析 → race 表欄位
# -------------------------------------------------------------------


def parse_race_header(info_table: BeautifulSoup):
    rows = info_table.find_all("tr")

    # 第 1 列: 「第 X 場 (284)」
    first = rows[0].get_text(" ", strip=True)
    m_no = re.search(r"第\s*(\d+)\s*場", first)
    race_no = int(m_no.group(1)) if m_no else None
    race_no = int(m_no.group(1)) if m_no else None
    m_code = re.search(r"\((\d+)\)", first)
    race_code = int(m_code.group(1)) if m_code else None  # Parse as INT

    # Extract race class from specific HTML element path
    # VERIFIED with browser inspection: class info is ALWAYS in row 2, cell 0
    # Table structure:
    #   Row 0: Race number (e.g., "第 1 場 (45)")
    #   Row 1: Empty row
    #   Row 2, Cell 0: Class + distance (e.g., "第五班 - 1200米 - (40-0)" or "三級賽 - 1400米")
    #   Row 3: Race name
    race_class_cell = rows[2].find_all("td")[0] if len(rows) > 2 else None
    if race_class_cell:
        cell_text = race_class_cell.get_text(strip=True)
        # Split by " - " and take first part (class is before distance)
        # Verified examples from actual HKJC pages:
        #   "第五班 - 1200米 - (40-0)" → "第五班"
        #   "三級賽 - 1400米" → "三級賽"
        #   "第十一班 - 1400米" → "第十一班"
        race_class = cell_text.split(" - ")[0].strip()
    else:
        race_class = None

    header_text = " ".join(r.get_text(" ", strip=True) for r in rows[1:5])

    m_dist = re.search(r"(\d{3,4})米", header_text)
    distance_m = int(m_dist.group(1)) if m_dist else None

    m_going = re.search(r"場地狀況\s*:\s*(\S+)", header_text)
    going = m_going.group(1) if m_going else None

    race_name = None
    track_type = None
    track_course = None
    for r in rows[1:5]:
        cells = r.find_all("td")
        if not cells:
            continue
        txt0 = cells[0].get_text(" ", strip=True)
        if any(k in txt0 for k in ["讓賽", "盃", "賽", "錦標"]):
            race_name = txt0
        tail = cells[-1].get_text(" ", strip=True)
        if "草地" in tail:
            track_type = "草地"
        if "泥地" in tail:
            track_type = "泥地"
        m_course = re.search(r"\"([A-Z]\+?\d?)\"", tail)
        if m_course:
            track_course = m_course.group(1)

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
    }


# -------------------------------------------------------------------
# LocalResults → meeting / race / horse / jockey / trainer / runner
# -------------------------------------------------------------------


def parse_horse_link(a_tag):
    """
    <a href="/racing/information/Chinese/Horse/Horse.aspx?HorseId=HK_2023_J344&Option=1">
    回傳: (hkjc_horse_id, horse_profile_url)
    """
    href = a_tag.get("href") or ""
    full = urljoin("https://racing.hkjc.com", href)
    m_id = re.search(r"HorseId=(HK_\d+_[A-Z0-9]+)", href)
    hkjc_horse_id = m_id.group(1) if m_id else None
    return hkjc_horse_id, full


def parse_jockey_link(a_tag):
    href = a_tag.get("href") or ""
    m = re.search(r"JockeyId=([A-Z0-9]+)", href)
    code = m.group(1) if m else None
    name_cn = a_tag.get_text(strip=True)
    return code, name_cn


def parse_trainer_link(a_tag):
    href = a_tag.get("href") or ""
    m = re.search(r"TrainerId=([A-Z0-9]+)", href)
    code = m.group(1) if m else None
    name_cn = a_tag.get_text(strip=True)
    return code, name_cn


def scrape_race_page(local_url: str, venue_code: str = None):
    """
    解析一場 LocalResults：
      meeting, race, horses, jockeys, trainers, runners
    """
    resp = requests.get(local_url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    text = soup.get_text("\n", strip=True)

    # Meeting：賽事日期 + 場地（中文）
    m_meet = re.search(r"賽事日期:\s*(\d{2}/\d{2}/\d{4})\s+(\S+)", text)
    meeting_date_dmy = m_meet.group(1) if m_meet else None
    meeting_venue = m_meet.group(2) if m_meet else None
    if meeting_date_dmy:
        d, m, y = meeting_date_dmy.split("/")
        meeting_date_ymd = f"{y}/{m}/{d}"

    # Calculate Season (Start Year)
    season_start_year = None
    if meeting_date_ymd:
        dt = datetime.strptime(meeting_date_ymd, "%Y/%m/%d").date()
        year = dt.year
        month = dt.month
        # Season starts in September (9)
        # If Jan-Aug (1-8): Season is Year-1 (e.g. 2025 Jan -> 2024 season)
        # If Sep-Dec (9-12): Season is Year (e.g. 2024 Sep -> 2024 season)
        if month < 9:
            season_start_year = year - 1
        else:
            season_start_year = year

    meeting = {
        "date_dmy": meeting_date_dmy,
        "date": meeting_date_ymd,
        "venue_name": meeting_venue,
        "venue_code": venue_code,  # 由呼叫者傳入 (ST/HV)
        "source_url": local_url,
        "season": season_start_year,
    }

    # Race header
    header_cell = soup.find("td", string=re.compile(r"第\s*\d+\s*場"))
    info_table = header_cell.find_parent("table")
    race = parse_race_header(info_table)
    race["localresults_url"] = local_url
    race["sectional_url"] = None  # 由 scrape_meeting 補

    # VALIDATION: Validate meeting and race
    try:
        validate_meeting(meeting)
    except Exception as e:
        logger.error(f"Invalid meeting data: {e}")
        raise

    try:
        validate_race(race)
    except Exception as e:
        logger.error(f"Invalid race data: {e}")
        raise

    # Runners table
    result_header = soup.find("td", string=re.compile("名次"))
    result_table = result_header.find_parent("table")
    rows_res = result_table.find_all("tr")[1:]

    runners = []
    horses = {}
    jockeys = {}
    trainers = {}

    def to_int_or_none(x):
        return int(x) if x and x.isdigit() else None

    def to_decimal_or_none(x):
        x = x.replace(",", "") if x else ""
        return Decimal(x) if re.fullmatch(r"\d+(\.\d+)?", x) else None

    for tr in rows_res:
        tds = tr.find_all("td")
        if not tds:
            continue
        pos_raw = tds[0].get_text(strip=True)
        if not pos_raw:
            continue

        finish_position_raw = pos_raw
        finish_position_num = int(pos_raw) if pos_raw.isdigit() else None

        horse_no_raw = tds[1].get_text(strip=True)
        horse_cell = tds[2]
        horse_name_cn = horse_cell.get_text(" ", strip=True)
        horse_link = horse_cell.find("a")

        hkjc_horse_id = None
        horse_profile_url = None
        if horse_link:
            hkjc_horse_id, horse_profile_url = parse_horse_link(horse_link)

        m_code = re.search(r"\(([A-Z0-9]+)\)", horse_name_cn)
        horse_code = m_code.group(1) if m_code else None

        jockey_cell = tds[3]
        jockey_link = jockey_cell.find("a")
        jockey_code, jockey_name_cn = (None, jockey_cell.get_text(strip=True))
        if jockey_link:
            jockey_code, jockey_name_cn = parse_jockey_link(jockey_link)

        trainer_cell = tds[4]
        trainer_link = trainer_cell.find("a")
        trainer_code, trainer_name_cn = (None, trainer_cell.get_text(strip=True))
        if trainer_link:
            trainer_code, trainer_name_cn = parse_trainer_link(trainer_link)

        actual_wt_raw = tds[5].get_text(strip=True)
        declared_wt_raw = tds[6].get_text(strip=True)
        draw_raw = tds[7].get_text(strip=True)
        margin_raw = tds[8].get_text(strip=True)
        running_pos_raw = tds[9].get_text(" ", strip=True)
        finish_time_str = tds[10].get_text(strip=True)
        win_odds_raw = tds[11].get_text(strip=True)

        actual_weight = to_int_or_none(actual_wt_raw)
        declared_weight = to_int_or_none(declared_wt_raw)
        draw = to_int_or_none(draw_raw)
        win_odds = to_decimal_or_none(win_odds_raw)

        # horse master
        if horse_code not in horses:
            horses[horse_code] = {
                "code": horse_code,
                "name_cn": horse_name_cn,
                "name_en": None,
                "hkjc_horse_id": hkjc_horse_id,
                "profile_url": horse_profile_url,
            }

        if jockey_code and jockey_code not in jockeys:
            jockeys[jockey_code] = {
                "code": jockey_code,
                "name_cn": jockey_name_cn,
                "name_en": None,
            }

        if trainer_code and trainer_code not in trainers:
            trainers[trainer_code] = {
                "code": trainer_code,
                "name_cn": trainer_name_cn,
                "name_en": None,
            }

        runners.append(
            {
                "finish_position_raw": finish_position_raw,
                "finish_position_num": finish_position_num,
                "horse_no": to_int_or_none(horse_no_raw),
                "horse_code": horse_code,
                "horse_name_cn": horse_name_cn,
                "hkjc_horse_id": hkjc_horse_id,
                "jockey_code": jockey_code,
                "jockey_name_cn": jockey_name_cn,
                "trainer_code": trainer_code,
                "trainer_name_cn": trainer_name_cn,
                "actual_weight": actual_weight,
                "declared_weight": declared_weight,
                "draw": draw,
                "margin_raw": margin_raw,
                "running_pos_raw": running_pos_raw,
                "finish_time_str": finish_time_str,
                "win_odds": win_odds,
            }
        )

    # VALIDATION: Validate runners before returning
    runners_validation = validate_runners(runners)

    if runners_validation.invalid_count > 0:
        logger.warning(
            f"Skipped {runners_validation.invalid_count}/{runners_validation.total_count} "
            f"invalid runners in race {race.get('race_no')}"
        )

    # Use only valid runners
    runners = runners_validation.valid_records

    return {
        "meeting": meeting,
        "race": race,
        "horses": list(horses.values()),
        "jockeys": list(jockeys.values()),
        "trainers": list(trainers.values()),
        "runners": runners,  # Now validated
        "validation_summary": {
            "runners_total": runners_validation.total_count,
            "runners_valid": runners_validation.valid_count,
            "runners_invalid": runners_validation.invalid_count,
        },
    }


# -------------------------------------------------------------------
# Horse Profile（馬匹資料頁） → profile snapshot（DB 層再寫入 horse_profile/history）
# -------------------------------------------------------------------


def scrape_horse_profile(hkjc_horse_id: str):
    """
    給一個 HKJC horse id（例如 'HK_2023_J344'），抓馬匹資料頁中的 horseProfile 區塊。
    回傳一份 profile snapshot dict（欄位對齊 horse_profile 表）。

    HTML structure: Uses <dl> definition list with <dt> labels and <dd> values.
    """
    from datetime import datetime

    url = f"{BASE}/horse?horseid={hkjc_horse_id}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    profile = {
        "origin": None,
        "age": None,
        "colour": None,
        "sex": None,
        "import_type": None,
        "season_prize_hkd": None,
        "lifetime_prize_hkd": None,
        "record_wins": None,
        "record_seconds": None,
        "record_thirds": None,
        "record_starts": None,
        "last10_starts": None,
        "current_location": None,
        "current_location_date": None,
        "import_date": None,
        "owner_name": None,
        "current_rating": None,
        "season_start_rating": None,
        "sire_name": None,
        "dam_name": None,
        "dam_sire_name": None,
    }

    # Find all tables on the page and search for profile data
    # Horse profile data is spread across multiple tables
    all_tables = soup.find_all("table")
    all_rows = []

    for table in all_tables:
        all_rows.extend(table.find_all("tr"))

    # Parse table rows (format: label | : | value)
    for row in all_rows:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        label = cells[0].get_text(strip=True)
        value = cells[2].get_text(strip=True)  # Third cell is the value

        # Parse "出生地 / 馬齡" → origin and age
        if "出生地" in label or "馬齡" in label:
            parts = value.split("/")
            if len(parts) >= 1:
                profile["origin"] = parts[0].strip()
            if len(parts) >= 2:
                age_str = parts[1].strip()
                if age_str.isdigit():
                    profile["age"] = int(age_str)

        # Parse "毛色 / 性別" → colour and sex
        elif "毛色" in label or "性別" in label:
            parts = value.split("/")
            if len(parts) >= 1:
                profile["colour"] = parts[0].strip()
            if len(parts) >= 2:
                profile["sex"] = parts[1].strip()

        # Parse "進口類別"
        elif "進口類別" in label:
            profile["import_type"] = value

        # Parse "今季獎金"
        elif "今季獎金" in label:
            # Remove "$" and "," then convert to int
            clean = value.replace("$", "").replace(",", "").strip()
            if clean.isdigit():
                profile["season_prize_hkd"] = int(clean)

        # Parse "總獎金"
        elif "總獎金" in label:
            clean = value.replace("$", "").replace(",", "").strip()
            if clean.isdigit():
                profile["lifetime_prize_hkd"] = int(clean)

        # Parse "冠-亞-季-總出賽次數" → wins-seconds-thirds-starts
        elif "冠" in label and "亞" in label and "季" in label and "出賽" in label:
            parts = value.split("-")
            if len(parts) >= 4:
                if parts[0].isdigit():
                    profile["record_wins"] = int(parts[0])
                if parts[1].isdigit():
                    profile["record_seconds"] = int(parts[1])
                if parts[2].isdigit():
                    profile["record_thirds"] = int(parts[2])
                if parts[3].isdigit():
                    profile["record_starts"] = int(parts[3])

        # Parse "最近十個賽馬日出賽場數"
        elif "最近" in label and "出賽" in label:
            if value.isdigit():
                profile["last10_starts"] = int(value)

        # Parse "現在位置 (到達日期)" → location and date
        elif "現在位置" in label or "到達日期" in label:
            # Format: "香港 (25/01/2024)"
            location_match = re.search(r"^([^(]+)", value)
            if location_match:
                profile["current_location"] = location_match.group(1).strip()

            date_match = re.search(r"\((\d{2}/\d{2}/\d{4})\)", value)
            if date_match:
                try:
                    date_str = date_match.group(1)
                    profile["current_location_date"] = datetime.strptime(date_str, "%d/%m/%Y").date()
                except ValueError:
                    pass

        # Parse "進口日期"
        elif "進口日期" in label:
            try:
                # Format: "25/01/2024"
                profile["import_date"] = datetime.strptime(value, "%d/%m/%Y").date()
            except ValueError:
                pass

        # Parse "馬主"
        elif "馬主" in label:
            profile["owner_name"] = value

        # Parse "現時評分"
        elif "現時評分" in label:
            if value.isdigit():
                profile["current_rating"] = int(value)

        # Parse "季初評分"
        elif "季初評分" in label:
            if value.isdigit():
                profile["season_start_rating"] = int(value)

        # Parse "父系" (exact match to avoid matching "同父系馬")
        elif label == "父系":
            profile["sire_name"] = value

        # Parse "母系"
        elif label == "母系":
            profile["dam_name"] = value

        # Parse "外祖父"
        elif label == "外祖父":
            profile["dam_sire_name"] = value

    return profile


# -------------------------------------------------------------------
# SectionalTime → horse_sectional（每場每馬每段）
# -------------------------------------------------------------------


def scrape_sectional_time(date_dmy: str, race_no: int):
    """
    date_dmy: '23/12/2025'
    回傳:
      {
        'horse_sectionals': [...]
      }
    只保留馬匹級分段。
    """
    url = f"{BASE}/displaysectionaltime?racedate={date_dmy}&RaceNo={race_no}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    container = soup.find("div", class_="dispalySectionalTime")
    if not container:
        return {"horse_sectionals": []}

    pending = container.find("p")
    if pending and "有關資料將於稍後公佈" in pending.get_text(strip=True):
        return {"horse_sectionals": []}

    main_table = None
    for tbl in container.find_all("table"):
        if tbl.find(string=re.compile("過終點")):
            main_table = tbl
            break

    horse_sectionals = []
    if not main_table:
        return {"horse_sectionals": []}

    rows = main_table.find_all("tr")

    # header 行：含「第1段」
    header_row = None
    for tr in rows:
        if tr.find(string=re.compile("第1段")):
            header_row = tr
            break

    num_sections = 0
    if header_row:
        header_tds = header_row.find_all("td")
        for td in header_tds:
            txt = td.get_text(strip=True)
            if re.match(r"第\d+段", txt):
                num_sections += 1

    # data rows：第 1 格是名次
    data_rows = []
    for tr in rows:
        tds = tr.find_all("td")
        if not tds:
            continue
        first = tds[0].get_text(strip=True)
        if first.isdigit():
            data_rows.append(tr)

    for tr in data_rows:
        tds = tr.find_all("td")
        finish_order = int(tds[0].get_text(strip=True))
        horse_no_raw = tds[1].get_text(strip=True)
        horse_cell = tds[2]
        horse_name = horse_cell.get_text(strip=True)
        h_link = horse_cell.find("a")

        horse_code = None
        hkjc_horse_id = None
        if h_link:
            hkjc_horse_id, _ = parse_horse_link(h_link)
            m_code = re.search(r"\(([A-Z0-9]+)\)", horse_name)
            horse_code = m_code.group(1) if m_code else None

        finish_time_str = tds[-1].get_text(strip=True)

        segment_cells = tds[3:-1]
        if num_sections:
            segment_cells = segment_cells[:num_sections]

        for idx, cell in enumerate(segment_cells, start=1):
            raw = cell.get_text(" ", strip=True) or ""
            raw_norm = re.sub(r"\s+", " ", raw).strip()

            pos = None
            margin = None
            times = []

            if raw_norm:
                parts = raw_norm.split(" ")
                if parts and parts[0].isdigit():
                    pos = int(parts[0])
                if len(parts) >= 2:
                    margin = parts[1]
                for v in parts[2:]:
                    if re.match(r"\d+\.\d+", v):
                        times.append(Decimal(v))

            time_main = times[0] if len(times) >= 1 else None
            time_sub1 = times[1] if len(times) >= 2 else None
            time_sub2 = times[2] if len(times) >= 3 else None
            time_sub3 = times[3] if len(times) >= 4 else None

            horse_sectionals.append(
                {
                    # DB：之後 join runner / horse / race 填 id
                    "finish_order": finish_order,
                    "horse_no": int(horse_no_raw) if horse_no_raw.isdigit() else None,
                    "horse_code": horse_code,
                    "hkjc_horse_id": hkjc_horse_id,
                    "section_no": idx,
                    "position": pos,
                    "margin_raw": margin,
                    "time_main": time_main,
                    "time_sub1": time_sub1,
                    "time_sub2": time_sub2,
                    "time_sub3": time_sub3,
                    "finish_time_str": finish_time_str,
                    "raw_cell": raw_norm,
                }
            )

    return {"horse_sectionals": horse_sectionals}


# -------------------------------------------------------------------
# Meeting 級 scraping：只傳 date_ymd，自動找 ST/HV + 所有場次
# -------------------------------------------------------------------


def scrape_meeting(date_ymd: str):
    """
    例: scrape_meeting('2025/12/23')

    回傳 list，每元素是一場:
      {
        'meeting': {...},
        'race': {...},
        'horses': [...],
        'jockeys': [...],
        'trainers': [...],
        'runners': [...],
        'horse_sectionals': [...],
        'horse_profiles': [...]
      }

    Args:
        date_ymd: Race date in YYYY/MM/DD format
    """
    race_links = list_race_urls_for_meeting_all_courses(date_ymd)
    all_races = []
    scraped_horse_ids = set()  # Track which horses we've already scraped to avoid duplicates

    for item in race_links:
        local_url = item["url"]
        venue_code = item["racecourse"]  # ST / HV
        print(f"Scraping race page: {local_url}")
        race_data = scrape_race_page(local_url, venue_code=venue_code)

        date_dmy = race_data["meeting"]["date_dmy"]
        race_no = race_data["race"]["race_no"]

        sectional_url = f"{BASE}/displaysectionaltime?racedate={date_dmy}&RaceNo={race_no}"
        race_data["race"]["sectional_url"] = sectional_url

        print(f"  Scraping sectional: date={date_dmy}, race_no={race_no}")
        sectional = scrape_sectional_time(date_dmy, race_no)

        race_data["horse_sectionals"] = sectional["horse_sectionals"]

        # Scrape horse profiles for all horses in this race
        horse_profiles = []
        for horse in race_data["horses"]:
            hkjc_horse_id = horse.get("hkjc_horse_id")
            if hkjc_horse_id and hkjc_horse_id not in scraped_horse_ids:
                print(f"    Scraping horse profile: {hkjc_horse_id} ({horse.get('name_cn', 'N/A')})")
                try:
                    profile = scrape_horse_profile(hkjc_horse_id)
                    profile["hkjc_horse_id"] = hkjc_horse_id  # Add ID for matching
                    horse_profiles.append(profile)
                    scraped_horse_ids.add(hkjc_horse_id)
                except Exception as e:
                    print(f"      Warning: Failed to scrape profile for {hkjc_horse_id}: {e}")

        # VALIDATION: Validate profiles before adding to race_data
        if horse_profiles:
            profiles_validation = validate_horse_profiles(horse_profiles)

            if profiles_validation.invalid_count > 0:
                logger.warning(
                    f"Skipped {profiles_validation.invalid_count}/{profiles_validation.total_count} "
                    "invalid horse profiles"
                )

            race_data["horse_profiles"] = profiles_validation.valid_records
            race_data["validation_summary"]["profiles_total"] = profiles_validation.total_count
            race_data["validation_summary"]["profiles_valid"] = profiles_validation.valid_count
            race_data["validation_summary"]["profiles_invalid"] = profiles_validation.invalid_count
        else:
            race_data["horse_profiles"] = []

        all_races.append(race_data)

    return all_races


# -------------------------------------------------------------------
# Demo：抓一個賽日，用 pandas 看結構
# -------------------------------------------------------------------


if __name__ == "__main__":
    import sys

    import pandas as pd

    meeting_date = "2025/12/23"
    races = scrape_meeting(meeting_date)

    print(f"\nTotal races scraped: {len(races)}")

    if not races:
        sys.exit(0)

    sample = races[0]

    print("\n=== Meeting info ===")
    print(sample["meeting"])

    print("\n=== Race info ===")
    print(sample["race"])

    runners_df = pd.DataFrame(sample["runners"])
    print("\n=== Runners (performance) ===")
    print(runners_df)

    horse_secs_df = pd.DataFrame(sample["horse_sectionals"])
    print("\n=== Horse sectional times (first 50 rows) ===")
    print(horse_secs_df.head(50))

    horses_df = pd.DataFrame(sample["horses"])
    print("\n=== Horses master (from LocalResults) ===")
    print(horses_df)
