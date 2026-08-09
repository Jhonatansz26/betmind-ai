-- Migration 015: Create bankrolls and bankroll_movements tables
-- Applies to: PostgreSQL (production)
-- SQLite (dev): handled automatically by SQLAlchemy create_all on server start.

CREATE TABLE IF NOT EXISTS bankrolls (
    id               SERIAL PRIMARY KEY,
    user_id          INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    current_capital  DOUBLE PRECISION NOT NULL,
    risk_profile     VARCHAR(20) NOT NULL DEFAULT 'moderado',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_bankrolls_user_id ON bankrolls (user_id);

COMMENT ON TABLE bankrolls IS
    'One row per user. Tracks current capital and chosen Kelly-fraction risk profile.';
COMMENT ON COLUMN bankrolls.risk_profile IS
    'conservador (quarter-Kelly) | moderado (half-Kelly) | agresivo (full-Kelly)';

-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS bankroll_movements (
    id           SERIAL PRIMARY KEY,
    bankroll_id  INTEGER NOT NULL REFERENCES bankrolls(id) ON DELETE CASCADE,
    type         VARCHAR(30) NOT NULL,
    -- "ticket_won" | "ticket_lost" | "ticket_void" | "manual_adjustment"
    amount       DOUBLE PRECISION NOT NULL,
    -- Positive = credit, negative = debit
    ticket_id    INTEGER REFERENCES saved_tickets(id) ON DELETE SET NULL,
    reason       VARCHAR(500),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bankroll_movements_bankroll_id
    ON bankroll_movements (bankroll_id);

COMMENT ON TABLE bankroll_movements IS
    'Immutable audit trail of every capital change. Never update, only insert.';
