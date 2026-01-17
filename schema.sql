-- ============================================================================
-- HKJC Horse Racing Database Schema (Optimized for Supabase)
-- 香港賽馬會賽事資料庫結構
-- ============================================================================
-- Optimizations:
-- 1. Efficient data types (SMALLINT, appropriate VARCHAR sizes)
-- 2. Strategic composite indexes for common queries
-- 3. Audit timestamps (created_at, updated_at)
-- 4. CHECK constraints for data validation
-- 5. Comments for PostgREST API documentation
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm; -- For text search optimization

-- ============================================================================
-- 賽日與賽事 (Meetings and Races)
-- ============================================================================

CREATE TABLE IF NOT EXISTS meeting (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    venue_code VARCHAR(4) NOT NULL CHECK (venue_code IN ('ST', 'HV', 'CH')),
    venue_name VARCHAR(32),
    source_url TEXT,
    season SMALLINT CHECK (season >= 2000 AND season <= 2100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(date, venue_code)
);

COMMENT ON TABLE meeting IS 'Race meeting information - one per day per venue';
COMMENT ON COLUMN meeting.venue_code IS 'Venue: ST=Sha Tin, HV=Happy Valley';
COMMENT ON COLUMN meeting.season IS 'Racing season start year (e.g. 2024 for 24/25)';

-- Indexes optimized for common queries
CREATE INDEX idx_meeting_date_desc ON meeting(date DESC);
CREATE INDEX idx_meeting_venue_date ON meeting(venue_code, date DESC);
CREATE INDEX idx_meeting_season ON meeting(season) WHERE season IS NOT NULL;

-- ============================================================================

CREATE TABLE IF NOT EXISTS race (
    id BIGSERIAL PRIMARY KEY,
    meeting_id BIGINT NOT NULL REFERENCES meeting(id) ON DELETE CASCADE,
    race_no SMALLINT NOT NULL CHECK (race_no >= 1 AND race_no <= 20),
    race_code INT,
    name_cn VARCHAR(128),
    class_text VARCHAR(32),
    distance_m SMALLINT CHECK (distance_m > 0),
    track_type VARCHAR(16) CHECK (track_type IN ('草地', '泥地', 'TURF', 'DIRT') OR track_type IS NULL),
    track_course VARCHAR(8),
    going VARCHAR(32),
    prize_total INT CHECK (prize_total >= 0),
    final_time_str VARCHAR(16),
    localresults_url TEXT,
    sectional_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(meeting_id, race_no)
);

COMMENT ON TABLE race IS 'Individual race information within a meeting';
COMMENT ON COLUMN race.distance_m IS 'Race distance in meters';
COMMENT ON COLUMN race.track_type IS 'Track surface type: 草地(turf) or 泥地(dirt)';

-- Composite indexes for efficient JOIN queries
CREATE INDEX idx_race_meeting_no ON race(meeting_id, race_no);
CREATE INDEX idx_race_distance ON race(distance_m) WHERE distance_m IS NOT NULL;
CREATE INDEX idx_race_class ON race(class_text) WHERE class_text IS NOT NULL;

-- ============================================================================
-- 馬匹與 Profile（含歷史）(Horses and Profiles with History)
-- ============================================================================

CREATE TABLE IF NOT EXISTS horse (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(16) NOT NULL,
    name_cn VARCHAR(128),
    name_en VARCHAR(128),
    hkjc_horse_id VARCHAR(32) UNIQUE NOT NULL,
    profile_url TEXT,
    origin VARCHAR(64),
    age SMALLINT CHECK (age >= 1 AND age <= 20),
    colour VARCHAR(32),
    sex VARCHAR(16), 
    import_type VARCHAR(64),
    season_prize_hkd INT CHECK (season_prize_hkd >= 0),
    lifetime_prize_hkd INT CHECK (lifetime_prize_hkd >= 0),
    record_wins SMALLINT CHECK (record_wins >= 0),
    record_seconds SMALLINT CHECK (record_seconds >= 0),
    record_thirds SMALLINT CHECK (record_thirds >= 0),
    record_starts SMALLINT CHECK (record_starts >= 0),
    last10_starts SMALLINT CHECK (last10_starts >= 0 AND last10_starts <= 10),
    current_location VARCHAR(64),
    current_location_date DATE,
    import_date DATE,
    owner_name VARCHAR(128),
    current_rating SMALLINT CHECK (current_rating >= 0),
    season_start_rating SMALLINT CHECK (season_start_rating >= 0),
    sire_name VARCHAR(128),
    dam_name VARCHAR(128),
    dam_sire_name VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE horse IS 'Horse master data with current profile information';
COMMENT ON COLUMN horse.code IS 'Short horse code (e.g. J344)';
COMMENT ON COLUMN horse.hkjc_horse_id IS 'Full HKJC ID (e.g. HK_2023_J344)';

-- Optimized indexes for lookups and text search
CREATE INDEX idx_horse_code ON horse(code);
CREATE INDEX idx_horse_name_en ON horse(name_en) WHERE name_en IS NOT NULL;
CREATE INDEX idx_horse_name_cn_trgm ON horse USING gin(name_cn gin_trgm_ops) WHERE name_cn IS NOT NULL;
CREATE INDEX idx_horse_rating ON horse(current_rating DESC) WHERE current_rating IS NOT NULL;

-- ============================================================================

CREATE TABLE IF NOT EXISTS horse_profile_history (
    id BIGSERIAL PRIMARY KEY,
    horse_id BIGINT NOT NULL REFERENCES horse(id) ON DELETE CASCADE,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    origin VARCHAR(64),
    age SMALLINT CHECK (age >= 2 AND age <= 20),
    colour VARCHAR(32),
    sex VARCHAR(16),
    import_type VARCHAR(64),
    season_prize_hkd INT CHECK (season_prize_hkd >= 0),
    lifetime_prize_hkd INT CHECK (lifetime_prize_hkd >= 0),
    record_wins SMALLINT CHECK (record_wins >= 0),
    record_seconds SMALLINT CHECK (record_seconds >= 0),
    record_thirds SMALLINT CHECK (record_thirds >= 0),
    record_starts SMALLINT CHECK (record_starts >= 0),
    last10_starts SMALLINT CHECK (last10_starts >= 0 AND last10_starts <= 10),
    current_location VARCHAR(64),
    current_location_date DATE,
    import_date DATE,
    owner_name VARCHAR(128),
    current_rating SMALLINT CHECK (current_rating >= 0 AND current_rating <= 150),
    season_start_rating SMALLINT CHECK (season_start_rating >= 0 AND season_start_rating <= 150),
    sire_name VARCHAR(128),
    dam_name VARCHAR(128),
    dam_sire_name VARCHAR(128),
    UNIQUE(horse_id, captured_at)
);

COMMENT ON TABLE horse_profile_history IS 'Historical snapshots of horse profile changes';

-- Optimized for time-series queries
CREATE INDEX idx_horse_profile_history_horse_time ON horse_profile_history(horse_id, captured_at DESC);
CREATE INDEX idx_horse_profile_history_captured ON horse_profile_history(captured_at DESC);

-- ============================================================================
-- 騎師與練馬師 (Jockeys and Trainers)
-- ============================================================================

CREATE TABLE IF NOT EXISTS jockey (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(16),
    name_cn VARCHAR(64) UNIQUE NOT NULL,
    name_en VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE jockey IS 'Jockey master data';
COMMENT ON COLUMN jockey.code IS 'Jockey code extracted from JockeyId parameter';

CREATE INDEX idx_jockey_name_en ON jockey(name_en) WHERE name_en IS NOT NULL;

-- ============================================================================

CREATE TABLE IF NOT EXISTS trainer (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(16), 
    name_cn VARCHAR(64)UNIQUE NOT NULL,
    name_en VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE trainer IS 'Trainer master data';
COMMENT ON COLUMN trainer.code IS 'Trainer code extracted from TrainerId parameter';

CREATE INDEX idx_trainer_name_en ON trainer(name_en) WHERE name_en IS NOT NULL;

-- ============================================================================
-- 每場每馬成績與分段 (Runner Performance and Sectionals)
-- ============================================================================

CREATE TABLE IF NOT EXISTS runner (
    id BIGSERIAL PRIMARY KEY,
    race_id BIGINT NOT NULL REFERENCES race(id) ON DELETE CASCADE,
    horse_id BIGINT NOT NULL REFERENCES horse(id) ON DELETE CASCADE,
    jockey_id BIGINT REFERENCES jockey(id) ON DELETE SET NULL,
    trainer_id BIGINT REFERENCES trainer(id) ON DELETE SET NULL,
    finish_position_raw VARCHAR(8),
    finish_position_num SMALLINT CHECK (finish_position_num >= 1 OR finish_position_num IS NULL),
    horse_no SMALLINT CHECK (horse_no >= 1 AND horse_no <= 20),
    actual_weight SMALLINT CHECK (actual_weight > 0),
    declared_weight SMALLINT CHECK (declared_weight > 0),
    draw SMALLINT CHECK (draw >= 1 AND draw <= 20),
    margin_raw VARCHAR(16),
    running_pos_raw VARCHAR(64),
    finish_time_str VARCHAR(16),
    win_odds DECIMAL(8,2) CHECK (win_odds >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(race_id, horse_id)
);

COMMENT ON TABLE runner IS 'Per-race per-horse performance data';
COMMENT ON COLUMN runner.horse_no IS 'Saddle number (鞍號)';
COMMENT ON COLUMN runner.finish_position_num IS 'Numeric finish position (NULL for non-finishers)';

-- Composite indexes optimized for common JOIN patterns
CREATE INDEX idx_runner_race_position ON runner(race_id, finish_position_num NULLS LAST);
CREATE INDEX idx_runner_horse_race ON runner(horse_id, race_id);
CREATE INDEX idx_runner_jockey_race ON runner(jockey_id, race_id) WHERE jockey_id IS NOT NULL;
CREATE INDEX idx_runner_trainer_race ON runner(trainer_id, race_id) WHERE trainer_id IS NOT NULL;

-- Covering index for leaderboard queries
CREATE INDEX idx_runner_race_covering ON runner(race_id, finish_position_num, horse_id, win_odds)
    WHERE finish_position_num IS NOT NULL;

-- ============================================================================

CREATE TABLE IF NOT EXISTS horse_sectional (
    id BIGSERIAL PRIMARY KEY,
    race_id BIGINT NOT NULL REFERENCES race(id) ON DELETE CASCADE,
    runner_id BIGINT NOT NULL REFERENCES runner(id) ON DELETE CASCADE,
    horse_id BIGINT NOT NULL REFERENCES horse(id) ON DELETE CASCADE,
    section_no SMALLINT NOT NULL CHECK (section_no >= 1 AND section_no <= 10),
    position SMALLINT CHECK (position >= 1),
    margin_raw VARCHAR(16),
    time_main DECIMAL(6,2) CHECK (time_main >= 0),
    time_sub1 DECIMAL(6,2) CHECK (time_sub1 >= 0),
    time_sub2 DECIMAL(6,2) CHECK (time_sub2 >= 0),
    time_sub3 DECIMAL(6,2) CHECK (time_sub3 >= 0),
    finish_time_str VARCHAR(16),
    raw_cell VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(runner_id, section_no)
);

COMMENT ON TABLE horse_sectional IS 'Sectional time data for each runner in each section';

-- Optimized for sectional analysis queries
CREATE INDEX idx_horse_sectional_runner_section ON horse_sectional(runner_id, section_no);
CREATE INDEX idx_horse_sectional_race_section ON horse_sectional(race_id, section_no);
CREATE INDEX idx_horse_sectional_horse_race ON horse_sectional(horse_id, race_id);

-- ============================================================================
-- Triggers for automatic updated_at timestamps
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers to tables with updated_at
CREATE TRIGGER update_meeting_updated_at BEFORE UPDATE ON meeting
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_race_updated_at BEFORE UPDATE ON race
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_horse_updated_at BEFORE UPDATE ON horse
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_jockey_updated_at BEFORE UPDATE ON jockey
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_trainer_updated_at BEFORE UPDATE ON trainer
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_runner_updated_at BEFORE UPDATE ON runner
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Row Level Security (RLS) - Uncomment to enable
-- ============================================================================
-- Note: Enable RLS if you need access control through Supabase Auth
-- For a scraper backend, RLS may not be necessary unless building a public API

-- Enable RLS on all tables
ALTER TABLE meeting ENABLE ROW LEVEL SECURITY;
ALTER TABLE race ENABLE ROW LEVEL SECURITY;
ALTER TABLE horse ENABLE ROW LEVEL SECURITY;
ALTER TABLE horse_profile_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE jockey ENABLE ROW LEVEL SECURITY;
ALTER TABLE trainer ENABLE ROW LEVEL SECURITY;
ALTER TABLE runner ENABLE ROW LEVEL SECURITY;
ALTER TABLE horse_sectional ENABLE ROW LEVEL SECURITY;

-- Example policy: Allow public read access
CREATE POLICY "Allow public read access" ON meeting FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON race FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON horse FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON horse_profile_history FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON jockey FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON trainer FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON runner FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON horse_sectional FOR SELECT USING (true);

-- Example policy: Restrict write access to service role only
-- (Service role bypasses RLS by default, these are for additional auth users)

-- ============================================================================
-- Helpful Views for Common Queries
-- ============================================================================

-- View: Latest race results with full details
CREATE OR REPLACE VIEW v_latest_results AS
SELECT
    m.date,
    m.venue_code,
    m.venue_name,
    r.race_no,
    r.name_cn as race_name,
    r.class_text,
    r.distance_m,
    h.code as horse_code,
    h.name_en as horse_name,
    run.finish_position_num,
    run.finish_position_raw,
    run.horse_no,
    j.name_en as jockey_name,
    t.name_en as trainer_name,
    run.win_odds,
    run.finish_time_str
FROM meeting m
JOIN race r ON r.meeting_id = m.id
JOIN runner run ON run.race_id = r.id
JOIN horse h ON h.id = run.horse_id
LEFT JOIN jockey j ON j.id = run.jockey_id
LEFT JOIN trainer t ON t.id = run.trainer_id
ORDER BY m.date DESC, r.race_no, run.finish_position_num NULLS LAST;

COMMENT ON VIEW v_latest_results IS 'Complete race results with all related entities';

-- View: Horse performance summary
CREATE OR REPLACE VIEW v_horse_performance AS
SELECT
    h.id,
    h.code,
    h.name_en,
    h.current_rating,
    h.record_wins,
    h.record_seconds,
    h.record_thirds,
    h.record_starts,
    CASE
        WHEN h.record_starts > 0
        THEN ROUND((h.record_wins::NUMERIC / h.record_starts) * 100, 2)
        ELSE 0
    END as win_percentage,
    h.lifetime_prize_hkd,
    h.owner_name,
    h.age
FROM horse h
WHERE h.record_starts > 0
ORDER BY h.current_rating DESC NULLS LAST;

COMMENT ON VIEW v_horse_performance IS 'Horse statistics with calculated metrics';

-- ============================================================================
-- Performance Statistics
-- ============================================================================

-- Create statistics for query optimizer
CREATE STATISTICS IF NOT EXISTS runner_race_horse_stats (dependencies)
    ON race_id, horse_id FROM runner;

CREATE STATISTICS IF NOT EXISTS runner_position_stats (dependencies)
    ON race_id, finish_position_num FROM runner;

-- ============================================================================
-- Maintenance Functions
-- ============================================================================

-- Function to analyze all tables (run periodically for optimization)
CREATE OR REPLACE FUNCTION analyze_all_tables()
RETURNS void AS $$
BEGIN
    ANALYZE meeting;
    ANALYZE race;
    ANALYZE horse;
    ANALYZE horse_profile_history;
    ANALYZE jockey;
    ANALYZE trainer;
    ANALYZE runner;
    ANALYZE horse_sectional;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION analyze_all_tables IS 'Run ANALYZE on all tables to update statistics';

-- ============================================================================
-- Initial Setup Complete
-- ============================================================================

-- Run initial analysis
SELECT analyze_all_tables();

-- Display schema summary
DO $$
BEGIN
    RAISE NOTICE '============================================';
    RAISE NOTICE 'HKJC Racing Database Schema Created';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'Tables: meeting, race, horse, horse_profile_history';
    RAISE NOTICE '        jockey, trainer, runner, horse_sectional';
    RAISE NOTICE 'Views: v_latest_results, v_horse_performance';
    RAISE NOTICE 'Optimizations: Composite indexes, CHECK constraints, Triggers';
    RAISE NOTICE '============================================';
END $$;
