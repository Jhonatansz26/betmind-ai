-- Migration 012: Persist generated tickets for user tracking/history.
CREATE TABLE IF NOT EXISTS saved_tickets (
    id SERIAL PRIMARY KEY,
    ticket_data JSONB NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'WON', 'LOST', 'VOID')),
    total_odds DOUBLE PRECISION NOT NULL,
    total_ev DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_saved_tickets_created_at
    ON saved_tickets (created_at DESC);
