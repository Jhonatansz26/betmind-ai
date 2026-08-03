-- Migration 011: Add match_type column to matches table
-- match_type: 'LEAGUE' | 'KNOCKOUT_CUP'
-- Default 'LEAGUE' for all existing rows.

-- Step 1: Add column with default
ALTER TABLE matches
    ADD COLUMN IF NOT EXISTS match_type VARCHAR(20) NOT NULL DEFAULT 'LEAGUE';

-- Step 2: Backfill KNOCKOUT_CUP for known cup/international leagues
-- Using external_id from leagues table to identify cups/knockouts
UPDATE matches
SET match_type = 'KNOCKOUT_CUP'
WHERE league_id IN (
    SELECT id FROM leagues
    WHERE external_id IN (
        -- LATAM Copas
        241,   -- Copa Colombia
        130,   -- Copa de la Liga Profesional (Argentina)
        73,    -- Copa do Brasil
        254,   -- US Open Cup
        13,    -- CONMEBOL Libertadores
        11,    -- CONMEBOL Sudamericana
        -- UEFA
        2,     -- UEFA Champions League
        3,     -- UEFA Europa League
        848    -- UEFA Conference League
    )
);

-- Step 3: Create index for ML orchestrator filtering
CREATE INDEX IF NOT EXISTS idx_matches_match_type ON matches(match_type);
