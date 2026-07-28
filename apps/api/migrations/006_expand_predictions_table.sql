-- Migración 006: Expandir tabla predictions con campos cuantitativos
-- Fase 3: Persistencia del motor Poisson + EV

-- Nuevas columnas para almacenar el output completo del motor cuantitativo
ALTER TABLE predictions
    ADD COLUMN IF NOT EXISTS lambda_home        DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS lambda_away        DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS home_attack_index  DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS away_attack_index  DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS home_defense_index DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS away_defense_index DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS markets_json       TEXT;

-- Índice compuesto para LEFT JOIN desde matches (match_id + created_at DESC)
CREATE INDEX IF NOT EXISTS idx_predictions_match_created
    ON predictions(match_id, created_at DESC);

-- Comentarios de documentación
COMMENT ON COLUMN predictions.lambda_home        IS 'Goles esperados (xG) equipo local según Poisson';
COMMENT ON COLUMN predictions.lambda_away        IS 'Goles esperados (xG) equipo visitante según Poisson';
COMMENT ON COLUMN predictions.home_attack_index  IS 'Índice de ataque del equipo local';
COMMENT ON COLUMN predictions.away_attack_index  IS 'Índice de ataque del equipo visitante';
COMMENT ON COLUMN predictions.home_defense_index IS 'Índice de defensa del equipo local';
COMMENT ON COLUMN predictions.away_defense_index IS 'Índice de defensa del equipo visitante';
COMMENT ON COLUMN predictions.markets_json       IS 'Probabilidades de mercados serializadas en JSON';
