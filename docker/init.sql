-- HKJC Racing PostgreSQL Schema
-- Equivalent to the SQLite schema in database.py

-- Races table
CREATE TABLE IF NOT EXISTS races (
    race_id TEXT PRIMARY KEY NOT NULL,
    race_date TEXT NOT NULL,
    race_no INTEGER NOT NULL,
    racecourse TEXT NOT NULL,
    class TEXT,
    distance INTEGER,
    going TEXT,
    surface TEXT,
    track TEXT,
    race_name TEXT,
    rating JSONB,
    sectional_times JSONB DEFAULT '[]',
    prize_money INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_races_race_date ON races(race_date);
CREATE INDEX IF NOT EXISTS idx_races_racecourse ON races(racecourse);
CREATE INDEX IF NOT EXISTS idx_races_date_course ON races(race_date, racecourse);

-- Horses table
CREATE TABLE IF NOT EXISTS horses (
    horse_id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    country_of_birth TEXT,
    age TEXT,
    colour TEXT,
    gender TEXT,
    sire TEXT,
    dam TEXT,
    damsire TEXT,
    trainer TEXT,
    owner TEXT,
    current_rating INTEGER,
    initial_rating INTEGER,
    season_prize INTEGER DEFAULT 0,
    total_prize INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    places INTEGER DEFAULT 0,
    shows INTEGER DEFAULT 0,
    total INTEGER DEFAULT 0,
    location TEXT,
    import_type TEXT,
    import_date TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_horses_name ON horses(name);
CREATE INDEX IF NOT EXISTS idx_horses_trainer ON horses(trainer);

-- Jockeys table
CREATE TABLE IF NOT EXISTS jockeys (
    jockey_id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    age TEXT,
    background TEXT,
    achievements TEXT,
    career_wins INTEGER DEFAULT 0,
    career_win_rate TEXT,
    season_stats JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jockeys_name ON jockeys(name);

-- Trainers table
CREATE TABLE IF NOT EXISTS trainers (
    trainer_id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    age TEXT,
    background TEXT,
    achievements TEXT,
    career_wins INTEGER DEFAULT 0,
    career_win_rate TEXT,
    season_stats JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trainers_name ON trainers(name);

-- Performance table
CREATE TABLE IF NOT EXISTS performance (
    id SERIAL PRIMARY KEY,
    race_id TEXT NOT NULL REFERENCES races(race_id) ON DELETE CASCADE,
    horse_id TEXT REFERENCES horses(horse_id) ON DELETE SET NULL,
    jockey_id TEXT REFERENCES jockeys(jockey_id) ON DELETE SET NULL,
    trainer_id TEXT REFERENCES trainers(trainer_id) ON DELETE SET NULL,
    horse_no TEXT NOT NULL,
    position TEXT NOT NULL,
    horse_name TEXT NOT NULL,
    jockey TEXT,
    trainer TEXT,
    actual_weight TEXT,
    body_weight TEXT,
    draw TEXT,
    margin TEXT,
    finish_time TEXT,
    win_odds TEXT,
    running_position JSONB DEFAULT '[]',
    gear TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(race_id, horse_no)
);

CREATE INDEX IF NOT EXISTS idx_performance_race_id ON performance(race_id);
CREATE INDEX IF NOT EXISTS idx_performance_horse_id ON performance(horse_id);
CREATE INDEX IF NOT EXISTS idx_performance_jockey_id ON performance(jockey_id);
CREATE INDEX IF NOT EXISTS idx_performance_trainer_id ON performance(trainer_id);
CREATE INDEX IF NOT EXISTS idx_performance_position ON performance(position);

-- Dividends table
CREATE TABLE IF NOT EXISTS dividends (
    id SERIAL PRIMARY KEY,
    race_id TEXT NOT NULL REFERENCES races(race_id) ON DELETE CASCADE,
    pool TEXT NOT NULL,
    winning_combination TEXT,
    payout TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(race_id, pool)
);

CREATE INDEX IF NOT EXISTS idx_dividends_race_id ON dividends(race_id);

-- Incidents table
CREATE TABLE IF NOT EXISTS incidents (
    id SERIAL PRIMARY KEY,
    race_id TEXT NOT NULL REFERENCES races(race_id) ON DELETE CASCADE,
    position TEXT,
    horse_no TEXT NOT NULL,
    horse_name TEXT NOT NULL,
    incident_report TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_incidents_race_id ON incidents(race_id);
CREATE INDEX IF NOT EXISTS idx_incidents_horse_no ON incidents(horse_no);

-- Sectional times table
CREATE TABLE IF NOT EXISTS sectional_times (
    id SERIAL PRIMARY KEY,
    race_id TEXT NOT NULL REFERENCES races(race_id) ON DELETE CASCADE,
    horse_no TEXT NOT NULL,
    section_number INTEGER NOT NULL,
    position INTEGER,
    margin TEXT,
    time DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(race_id, horse_no, section_number)
);

CREATE INDEX IF NOT EXISTS idx_sectional_times_race_id ON sectional_times(race_id);
CREATE INDEX IF NOT EXISTS idx_sectional_times_horse_no ON sectional_times(horse_no);
CREATE INDEX IF NOT EXISTS idx_sectional_times_race_horse ON sectional_times(race_id, horse_no);
