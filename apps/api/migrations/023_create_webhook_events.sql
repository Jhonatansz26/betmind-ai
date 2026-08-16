-- Migration 023: webhook_events — cola durable de eventos crudos de Wompi.
-- El webhook persiste el payload ANTES de responder 200; un job periódico
-- reintenta los eventos en received/failed que quedaron sin procesar.

CREATE TABLE IF NOT EXISTS webhook_events (
    id                    SERIAL PRIMARY KEY,
    event_name            VARCHAR(50),
    wompi_transaction_id  VARCHAR(100),
    event_timestamp       DOUBLE PRECISION,
    payload               JSONB NOT NULL,
    status                VARCHAR(20) NOT NULL DEFAULT 'received',
    attempts              INTEGER NOT NULL DEFAULT 0,
    error_message         TEXT,
    received_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at          TIMESTAMPTZ,
    CONSTRAINT uq_webhook_event_transaction_timestamp
        UNIQUE (wompi_transaction_id, event_timestamp)
);

CREATE INDEX IF NOT EXISTS idx_webhook_events_status ON webhook_events (status);
CREATE INDEX IF NOT EXISTS idx_webhook_events_transaction_id
    ON webhook_events (wompi_transaction_id);
