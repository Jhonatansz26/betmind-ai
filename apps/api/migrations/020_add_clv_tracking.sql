-- Migración 020: Monitoreo de CLV (Closing Line Value)
-- Registra la cuota de cierre capturada 5-10 min antes del kickoff y el delta
-- contra la línea de apertura del modelo (bookmaker_odds).

ALTER TABLE public.matches
    ADD COLUMN IF NOT EXISTS closing_odds JSONB,
    ADD COLUMN IF NOT EXISTS clv_value DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS closing_odds_captured_at TIMESTAMPTZ;

-- Índice parcial para el job: partidos del día aún sin captura de cierre.
CREATE INDEX IF NOT EXISTS idx_matches_closing_pending
    ON public.matches (match_date)
    WHERE status = 'SCHEDULED' AND closing_odds_captured_at IS NULL;

COMMENT ON COLUMN public.matches.closing_odds IS
    'JSONB por mercado: {"1X2_HOME": {"opening_odds": 2.1, "closing_odds": 1.95, "clv": 0.077, "captured_at": "...", "source": "api_football"}}';
COMMENT ON COLUMN public.matches.clv_value IS
    'Media del CLV por mercado = mean((opening_odds / closing_odds) - 1). Positivo = el modelo venció la línea de cierre.';
