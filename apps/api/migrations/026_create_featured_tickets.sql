-- Migration 026: featured_tickets — boletos destacados del sistema.
--
-- Sección pública "Resultados": boletos que genera el SISTEMA (no un usuario)
-- con la lógica existente de ticket_builder.py, persistidos como snapshot
-- INMUTABLE en el momento de la generación (legs con cuota + probabilidad del
-- instante, combined_odds, real_ev del parlay). El status se resuelve
-- post-partido contra prediction_outcomes: PENDING -> WON / LOST.
--
-- Difiere de saved_tickets (boletos personales del usuario): acá no hay
-- user_id ni stake; la fecha es el día COT de generación y el snapshot es la
-- única fuente de verdad para la trazabilidad pública.

CREATE TABLE IF NOT EXISTS public.featured_tickets (
    id            SERIAL PRIMARY KEY,
    ticket_date   DATE NOT NULL,
    mode          VARCHAR(20) NOT NULL,
    legs          JSONB NOT NULL,
    combined_odds DOUBLE PRECISION NOT NULL,
    real_ev       DOUBLE PRECISION NOT NULL,
    status        VARCHAR(10) NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'WON', 'LOST')),
    resolved_at   TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ,

    CONSTRAINT uq_featured_ticket_date_mode UNIQUE (ticket_date, mode)
);

CREATE INDEX IF NOT EXISTS idx_featured_tickets_date
    ON public.featured_tickets (ticket_date DESC);

-- Lectura pública (marketing/confianza, sin login). Las escrituras son del
-- backend (rol postgres, ignora RLS por diseño).
ALTER TABLE public.featured_tickets ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS featured_tickets_public_read ON public.featured_tickets;
CREATE POLICY featured_tickets_public_read ON public.featured_tickets
    FOR SELECT
    USING (true);

COMMENT ON COLUMN public.featured_tickets.legs IS
    'Snapshot inmutable de las patas al momento de generacion (match_id, market_name, odds, probabilidad)';
COMMENT ON COLUMN public.featured_tickets.real_ev IS
    'EV real del parlay (P conjunta x cuota combinada - 1), no el promedio de EVs';