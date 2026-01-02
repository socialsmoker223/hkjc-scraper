-- HKJC Horse Racing Database Schema
-- 香港賽馬會賽事資料庫結構
-- Generated from data_model.md

-- ============================================================================
-- 賽日與賽事 (Meetings and Races)
-- ============================================================================

CREATE TABLE IF NOT EXISTS meeting (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    venue_code VARCHAR(4) NOT NULL,  -- ST/HV
    venue_name VARCHAR(32),  -- 沙田 / 跑馬地
    source_url TEXT,
    season INT,  -- 賽季起始年 (e.g. 2024 for 24/25)
    UNIQUE(date, venue_code)
);

CREATE INDEX idx_meeting_date ON meeting(date);

CREATE TABLE IF NOT EXISTS race (
    id BIGSERIAL PRIMARY KEY,
    meeting_id BIGINT NOT NULL REFERENCES meeting(id) ON DELETE CASCADE,
    race_no INT NOT NULL,  -- 當日第幾場
    race_code INT,  -- 全季總場次, 每年9月重置
    name_cn VARCHAR(128),
    class_text VARCHAR(32),  -- 第四班等
    distance_m INT,
    track_type VARCHAR(16),  -- 草地 / 泥地
    track_course VARCHAR(8),  -- A, A+3, C+3…
    going VARCHAR(32),  -- 好地等
    prize_total INT,  -- 總獎金 HKD
    final_time_str VARCHAR(16),  -- 1:34.62 等
    localresults_url TEXT,
    sectional_url TEXT,
    UNIQUE(meeting_id, race_no)
);

CREATE INDEX idx_race_meeting ON race(meeting_id);

-- ============================================================================
-- 馬匹與 Profile（含歷史）(Horses and Profiles with History)
-- ============================================================================

CREATE TABLE IF NOT EXISTS horse (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(16) UNIQUE NOT NULL,  -- J344 等
    name_cn VARCHAR(128),
    name_en VARCHAR(128),
    hkjc_horse_id VARCHAR(32) UNIQUE,  -- HK_2023_J344
    profile_url TEXT
);

CREATE INDEX idx_horse_code ON horse(code);
CREATE INDEX idx_horse_hkjc_id ON horse(hkjc_horse_id);

CREATE TABLE IF NOT EXISTS horse_profile (
    id BIGSERIAL PRIMARY KEY,
    horse_id BIGINT NOT NULL REFERENCES horse(id) ON DELETE CASCADE,
    origin VARCHAR(64),
    age INT,
    colour VARCHAR(32),
    sex VARCHAR(16),
    import_type VARCHAR(64),
    season_prize_hkd INT,
    lifetime_prize_hkd INT,
    record_wins INT,
    record_seconds INT,
    record_thirds INT,
    record_starts INT,
    last10_starts INT,
    current_location VARCHAR(64),
    current_location_date DATE,
    import_date DATE,
    owner_name VARCHAR(128),
    current_rating INT,
    season_start_rating INT,
    sire_name VARCHAR(128),
    dam_name VARCHAR(128),
    dam_sire_name VARCHAR(128),
    UNIQUE(horse_id)
);

CREATE TABLE IF NOT EXISTS horse_profile_history (
    id BIGSERIAL PRIMARY KEY,
    horse_id BIGINT NOT NULL REFERENCES horse(id) ON DELETE CASCADE,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    origin VARCHAR(64),
    age INT,
    colour VARCHAR(32),
    sex VARCHAR(16),
    import_type VARCHAR(64),
    season_prize_hkd INT,
    lifetime_prize_hkd INT,
    record_wins INT,
    record_seconds INT,
    record_thirds INT,
    record_starts INT,
    last10_starts INT,
    current_location VARCHAR(64),
    current_location_date DATE,
    import_date DATE,
    owner_name VARCHAR(128),
    current_rating INT,
    season_start_rating INT,
    sire_name VARCHAR(128),
    dam_name VARCHAR(128),
    dam_sire_name VARCHAR(128),
    UNIQUE(horse_id, captured_at)
);

CREATE INDEX idx_horse_profile_history_horse_captured ON horse_profile_history(horse_id, captured_at DESC);

-- ============================================================================
-- 騎師與練馬師 (Jockeys and Trainers)
-- ============================================================================

CREATE TABLE IF NOT EXISTS jockey (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(16) UNIQUE NOT NULL,  -- 由 JockeyId 抽出
    name_cn VARCHAR(64),
    name_en VARCHAR(64)
);

CREATE INDEX idx_jockey_code ON jockey(code);

CREATE TABLE IF NOT EXISTS trainer (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(16) UNIQUE NOT NULL,  -- 由 TrainerId 抽出
    name_cn VARCHAR(64),
    name_en VARCHAR(64)
);

CREATE INDEX idx_trainer_code ON trainer(code);

-- ============================================================================
-- 每場每馬成績與分段 (Runner Performance and Sectionals)
-- ============================================================================

CREATE TABLE IF NOT EXISTS runner (
    id BIGSERIAL PRIMARY KEY,
    race_id BIGINT NOT NULL REFERENCES race(id) ON DELETE CASCADE,
    horse_id BIGINT NOT NULL REFERENCES horse(id) ON DELETE CASCADE,
    jockey_id BIGINT REFERENCES jockey(id) ON DELETE SET NULL,
    trainer_id BIGINT REFERENCES trainer(id) ON DELETE SET NULL,
    finish_position_raw VARCHAR(8),  -- 1, 2, PU 等
    finish_position_num INT,  -- 數字名次
    horse_no INT,  -- 鞍號
    actual_weight INT,
    declared_weight INT,
    draw INT,
    margin_raw VARCHAR(16),
    running_pos_raw VARCHAR(64),  -- 跑位字串
    finish_time_str VARCHAR(16),
    win_odds DECIMAL(8,2),
    UNIQUE(race_id, horse_id)
);

CREATE INDEX idx_runner_race ON runner(race_id);
CREATE INDEX idx_runner_horse ON runner(horse_id);
CREATE INDEX idx_runner_jockey ON runner(jockey_id);
CREATE INDEX idx_runner_trainer ON runner(trainer_id);

CREATE TABLE IF NOT EXISTS horse_sectional (
    id BIGSERIAL PRIMARY KEY,
    race_id BIGINT NOT NULL REFERENCES race(id) ON DELETE CASCADE,
    runner_id BIGINT NOT NULL REFERENCES runner(id) ON DELETE CASCADE,
    horse_id BIGINT NOT NULL REFERENCES horse(id) ON DELETE CASCADE,
    section_no INT NOT NULL,  -- 1..N
    position INT,  -- 段內位置
    margin_raw VARCHAR(16),  -- 段末距離字串
    time_main DECIMAL(6,2),  -- 主段時間
    time_sub1 DECIMAL(6,2),
    time_sub2 DECIMAL(6,2),
    time_sub3 DECIMAL(6,2),
    finish_time_str VARCHAR(16),  -- 全場時間
    raw_cell VARCHAR(64),  -- 原始 cell 文本
    UNIQUE(runner_id, section_no)
);

CREATE INDEX idx_horse_sectional_race ON horse_sectional(race_id);
CREATE INDEX idx_horse_sectional_runner ON horse_sectional(runner_id);
CREATE INDEX idx_horse_sectional_horse ON horse_sectional(horse_id);
