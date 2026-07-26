CREATE TABLE IF NOT EXISTS bookmaker_odds (
    id              BIGSERIAL PRIMARY KEY,
    match_id        BIGINT NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    market_name     VARCHAR(50) NOT NULL,
    bookmaker_name  VARCHAR(100) NOT NULL DEFAULT 'api_football',
    odds_value      DOUBLE PRECISION NOT NULL,
    external_fixture_id BIGINT,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ,

    CONSTRAINT uq_match_market_bookmaker UNIQUE (match_id, market_name, bookmaker_name)
);

CREATE INDEX IF NOT EXISTS idx_bookmaker_odds_match_id ON bookmaker_odds(match_id);
CREATE INDEX IF NOT EXISTS idx_bookmaker_odds_fetched_at ON bookmaker_odds(fetched_at);

ALTER TABLE bookmaker_odds ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read access on bookmaker_odds"
    ON bookmaker_odds FOR SELECT
    USING (true);
