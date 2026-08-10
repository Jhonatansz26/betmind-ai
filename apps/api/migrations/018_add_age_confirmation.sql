-- Migration 018: Age confirmation for new user registrations.
-- Applies to: PostgreSQL (production)
-- SQLite (dev): handled automatically by SQLAlchemy create_all on server start.

ALTER TABLE users ADD COLUMN IF NOT EXISTS age_confirmed_at TIMESTAMPTZ;
