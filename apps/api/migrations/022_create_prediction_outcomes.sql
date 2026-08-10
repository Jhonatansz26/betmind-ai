-- Migración 022: Tabla prediction_outcomes — evaluación post-partido
--
-- Compara las predicciones persistidas (markets_json) contra el resultado
-- real del partido: es la base para medir Brier score y calibración
-- (win rate real vs. probabilidad predicha) por mercado y por liga.
--
-- Una fila por (match_id, market_name). El job evaluate_predictions inserta
-- con ON CONFLICT DO NOTHING: es idempotente.

CREATE TABLE IF NOT EXISTS public.prediction_outcomes (
    id                  BIGSERIAL PRIMARY KEY,
    match_id            BIGINT NOT NULL REFERENCES public.matches(id) ON DELETE CASCADE,
    market_name         VARCHAR(50) NOT NULL,
    our_probability     DOUBLE PRECISION NOT NULL,
    predicted_verdict   VARCHAR(50),
    actual_outcome      VARCHAR(10) NOT NULL CHECK (actual_outcome IN ('WON', 'LOST')),
    brier_component     DOUBLE PRECISION NOT NULL,
    evaluated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ,

    CONSTRAINT uq_prediction_outcome_match_market UNIQUE (match_id, market_name)
);

CREATE INDEX IF NOT EXISTS idx_prediction_outcomes_match_id
    ON public.prediction_outcomes(match_id);
CREATE INDEX IF NOT EXISTS idx_prediction_outcomes_evaluated_at
    ON public.prediction_outcomes(evaluated_at);

ALTER TABLE public.prediction_outcomes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read access on prediction_outcomes"
    ON public.prediction_outcomes FOR SELECT
    USING (true);

COMMENT ON COLUMN public.prediction_outcomes.our_probability IS
    'Probabilidad que el modelo persistió en markets_json al momento de predecir';
COMMENT ON COLUMN public.prediction_outcomes.actual_outcome IS
    'WON si el mercado ganó con el resultado real, LOST si no';
COMMENT ON COLUMN public.prediction_outcomes.brier_component IS
    '(our_probability - actual)^2 con actual = 1 (WON) / 0 (LOST)';
