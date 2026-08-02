-- SofaScore post-match data used by the advanced match views.
CREATE TABLE IF NOT EXISTS match_events (
    id BIGSERIAL PRIMARY KEY,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    event_type VARCHAR(20) NOT NULL CHECK (event_type IN ('goal', 'card', 'sub')),
    minute INTEGER NOT NULL CHECK (minute >= 0),
    added_time INTEGER NOT NULL DEFAULT 0 CHECK (added_time >= 0),
    is_home BOOLEAN,
    player_name VARCHAR(150),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (match_id, event_type, minute, added_time, is_home, player_name)
);

CREATE INDEX IF NOT EXISTS idx_match_events_match_id ON match_events(match_id);

CREATE TABLE IF NOT EXISTS match_advanced_stats (
    match_id INTEGER PRIMARY KEY REFERENCES matches(id) ON DELETE CASCADE,
    home_xg DOUBLE PRECISION,
    away_xg DOUBLE PRECISION,
    home_shots INTEGER,
    away_shots INTEGER,
    home_shots_on_target INTEGER,
    away_shots_on_target INTEGER,
    home_corners INTEGER,
    away_corners INTEGER,
    home_fouls INTEGER,
    away_fouls INTEGER,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS referee_profiles (
    referee_id BIGINT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    matches_count INTEGER NOT NULL DEFAULT 0 CHECK (matches_count >= 0),
    yellow_cards INTEGER NOT NULL DEFAULT 0 CHECK (yellow_cards >= 0),
    red_cards INTEGER NOT NULL DEFAULT 0 CHECK (red_cards >= 0),
    yellow_cards_avg DOUBLE PRECISION NOT NULL DEFAULT 0,
    red_cards_avg DOUBLE PRECISION NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE matches
    ADD COLUMN IF NOT EXISTS sofascore_event_id BIGINT UNIQUE;

ALTER TABLE matches
    ADD COLUMN IF NOT EXISTS referee_id BIGINT REFERENCES referee_profiles(referee_id);

CREATE INDEX IF NOT EXISTS idx_matches_referee_id ON matches(referee_id);
CREATE INDEX IF NOT EXISTS idx_matches_sofascore_event_id ON matches(sofascore_event_id);
