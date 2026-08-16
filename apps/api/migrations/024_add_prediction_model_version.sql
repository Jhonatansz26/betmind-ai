-- Migration 024: predictions.model_version — corte de versión del modelo.
-- Aditiva: las predicciones existentes quedan con NULL (= pre-versionado) y
-- toda predicción nueva se marca con MODEL_VERSION (betmind_ml/config.py).

ALTER TABLE predictions ADD COLUMN IF NOT EXISTS model_version VARCHAR(50);

CREATE INDEX IF NOT EXISTS idx_predictions_model_version
    ON predictions (model_version);
