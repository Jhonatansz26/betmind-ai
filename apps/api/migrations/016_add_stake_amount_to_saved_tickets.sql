-- Migration 016: Persist the amount staked on saved tickets.
-- Applies to: PostgreSQL (production)
-- SQLite (dev): handled automatically by SQLAlchemy create_all on server start.

ALTER TABLE saved_tickets
ADD COLUMN IF NOT EXISTS stake_amount DOUBLE PRECISION;

COMMENT ON COLUMN saved_tickets.stake_amount IS
    'Optional stake amount used to calculate automatic bankroll movements.';

-- A ticket can have at most one automatic bankroll movement. The partial
-- index keeps manual movements (which have no ticket_id) unrestricted.
CREATE UNIQUE INDEX IF NOT EXISTS uq_bankroll_movements_ticket_id
    ON bankroll_movements (ticket_id)
    WHERE ticket_id IS NOT NULL;
