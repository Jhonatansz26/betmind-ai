-- Migration 014: Add PRO subscription fields to users table
-- Applies to: PostgreSQL (production)
-- SQLite (dev): handled automatically by SQLAlchemy create_all on server start.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS is_pro BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS pro_expires_at TIMESTAMPTZ DEFAULT NULL;

COMMENT ON COLUMN users.is_pro IS
    'Whether the user currently has an active PRO subscription. '
    'Set manually or via payment webhook (Wompi/MercadoPago).';

COMMENT ON COLUMN users.pro_expires_at IS
    'UTC datetime when the PRO subscription expires. NULL = no expiry set '
    'or subscription is indefinite/manual.';
