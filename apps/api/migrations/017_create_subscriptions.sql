-- Migration 017: Subscription entitlements and Wompi transaction audit trail.
-- Applies to: PostgreSQL (production)
-- SQLite (dev): handled automatically by SQLAlchemy create_all on server start.

CREATE TABLE IF NOT EXISTS subscriptions (
    id                         SERIAL PRIMARY KEY,
    user_id                    INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    wompi_payment_source_id    VARCHAR(100),
    plan                       VARCHAR(20) NOT NULL,
    status                     VARCHAR(30) NOT NULL,
    current_period_end        TIMESTAMPTZ NOT NULL,
    trial_ends_at              TIMESTAMPTZ,
    initial_transaction_id     VARCHAR(100),
    recurrence_enabled         BOOLEAN,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                 TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions (user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions (status);

CREATE TABLE IF NOT EXISTS subscription_transactions (
    id                       SERIAL PRIMARY KEY,
    subscription_id          INTEGER NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    wompi_transaction_id     VARCHAR(100) NOT NULL UNIQUE,
    reference                VARCHAR(255) NOT NULL UNIQUE,
    kind                     VARCHAR(20) NOT NULL,
    amount_in_cents          INTEGER NOT NULL,
    status                   VARCHAR(20) NOT NULL,
    processor_response_code  VARCHAR(50),
    status_message           VARCHAR(500),
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_subscription_transactions_subscription_id
    ON subscription_transactions (subscription_id);
